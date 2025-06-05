"""
Throttling and Rate Limiting Service
-----------------------------------
This module provides sophisticated throttling mechanisms that enforce budget
limits by controlling API request rates, blocking requests when budgets are
exceeded, and implementing graceful degradation strategies.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from threading import Lock, RLock
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from leadfactory.cost.budget_alerting import (
    AlertType,
    send_budget_alert,
    send_budget_alert_async,
)
from leadfactory.cost.budget_config import AlertLevel, get_budget_config
from leadfactory.cost.gpt_usage_tracker import get_gpt_usage_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ThrottlingStrategy(Enum):
    """Available throttling strategies."""

    SOFT = "soft"  # Delay requests
    HARD = "hard"  # Reject requests
    GRACEFUL = "graceful"  # Use smaller/cheaper models
    ADAPTIVE = "adaptive"  # Combine strategies based on budget status


class ThrottlingAction(Enum):
    """Actions that can be taken by the throttling service."""

    ALLOW = "allow"  # Allow the request to proceed
    DELAY = "delay"  # Delay the request
    REJECT = "reject"  # Reject the request
    DOWNGRADE = "downgrade"  # Use a cheaper alternative


@dataclass
class ThrottlingDecision:
    """Represents a throttling decision."""

    action: ThrottlingAction
    delay_seconds: float = 0.0
    alternative_model: Optional[str] = None
    reason: str = ""
    estimated_cost: float = 0.0
    budget_utilization: float = 0.0


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_concurrent_requests: int = 10
    burst_allowance: int = 5  # Allow short bursts above the rate limit


@dataclass
class RequestTracker:
    """Tracks request timing and counts."""

    timestamps: list[float] = field(default_factory=list)
    concurrent_count: int = 0
    lock: RLock = field(default_factory=RLock)

    def add_request(self) -> None:
        """Record a new request."""
        with self.lock:
            current_time = time.time()
            self.timestamps.append(current_time)
            self.concurrent_count += 1

            # Clean old timestamps (older than 1 hour)
            cutoff_time = current_time - 3600
            self.timestamps = [ts for ts in self.timestamps if ts > cutoff_time]

    def complete_request(self) -> None:
        """Mark a request as completed."""
        with self.lock:
            self.concurrent_count = max(0, self.concurrent_count - 1)

    def get_request_counts(self) -> tuple[int, int]:
        """Get request counts for the last minute and hour."""
        with self.lock:
            current_time = time.time()
            minute_ago = current_time - 60
            hour_ago = current_time - 3600

            minute_count = sum(1 for ts in self.timestamps if ts > minute_ago)
            hour_count = sum(1 for ts in self.timestamps if ts > hour_ago)

            return minute_count, hour_count


class ThrottlingService:
    """
    Advanced throttling service that implements multiple strategies
    for budget enforcement and rate limiting.
    """

    def __init__(self):
        """Initialize the throttling service."""
        self.budget_config = get_budget_config()
        self.usage_tracker = get_gpt_usage_tracker()
        self.rate_limit_config = RateLimitConfig()
        self.request_trackers: dict[str, RequestTracker] = {}
        self.lock = Lock()

        # Model alternatives for graceful degradation
        self.model_alternatives = {
            "gpt-4o": ["gpt-4o-mini", "gpt-3.5-turbo"],
            "gpt-4": ["gpt-4o-mini", "gpt-3.5-turbo"],
            "gpt-4-turbo": ["gpt-4o", "gpt-4o-mini"],
            "claude-3-opus": ["claude-3-sonnet", "claude-3-haiku"],
            "claude-3-sonnet": ["claude-3-haiku"],
        }

        # Cost multipliers for different models (relative to base model)
        self.model_cost_multipliers = {
            "gpt-4o": 1.0,
            "gpt-4o-mini": 0.1,
            "gpt-3.5-turbo": 0.05,
            "gpt-4": 1.5,
            "gpt-4-turbo": 1.2,
            "claude-3-opus": 2.0,
            "claude-3-sonnet": 0.6,
            "claude-3-haiku": 0.1,
        }

        logger.info("Throttling service initialized")

    def should_throttle(
        self,
        service: str,
        model: str,
        endpoint: str,
        estimated_cost: float,
        strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    ) -> ThrottlingDecision:
        """
        Determine if a request should be throttled and what action to take.

        Args:
            service: Service name (e.g., 'openai')
            model: Model name (e.g., 'gpt-4o')
            endpoint: Endpoint name (e.g., 'chat')
            estimated_cost: Estimated cost of the operation
            strategy: Throttling strategy to use

        Returns:
            ThrottlingDecision with the recommended action
        """
        try:
            # Get current budget status
            budget_status = self._get_budget_status(service, model, endpoint)

            # Check rate limits
            rate_limit_decision = self._check_rate_limits(service, model, endpoint)
            if rate_limit_decision.action != ThrottlingAction.ALLOW:
                return rate_limit_decision

            # Make throttling decision based on budget status
            if strategy == ThrottlingStrategy.ADAPTIVE:
                strategy = self._choose_adaptive_strategy(budget_status)

            decision = self._make_throttling_decision(
                service, model, endpoint, estimated_cost, budget_status, strategy
            )

            logger.debug(
                f"Throttling decision for {service}/{model}/{endpoint}: "
                f"{decision.action.value} (reason: {decision.reason})"
            )

            return decision

        except Exception as e:
            logger.error(f"Error in throttling decision: {e}", exc_info=True)
            # Default to allowing the request if there's an error
            return ThrottlingDecision(
                action=ThrottlingAction.ALLOW,
                reason=f"Error in throttling service: {e}",
            )

    def _get_budget_status(
        self, service: str, model: str, endpoint: str
    ) -> dict[str, float]:
        """Get current budget utilization status."""
        try:
            # Get usage for different periods using get_usage_stats
            daily_usage = self.usage_tracker.get_usage_stats(
                start_time=datetime.now() - timedelta(days=1),
                end_time=datetime.now(),
                model=model,
            )
            weekly_usage = self.usage_tracker.get_usage_stats(
                start_time=datetime.now() - timedelta(weeks=1),
                end_time=datetime.now(),
                model=model,
            )
            monthly_usage = self.usage_tracker.get_usage_stats(
                start_time=datetime.now() - timedelta(days=30),
                end_time=datetime.now(),
                model=model,
            )

            # Extract total costs from the summary
            daily_cost = daily_usage.get("summary", {}).get("total_cost", 0.0)
            weekly_cost = weekly_usage.get("summary", {}).get("total_cost", 0.0)
            monthly_cost = monthly_usage.get("summary", {}).get("total_cost", 0.0)

            # Get budget limits
            daily_limit = self.budget_config.get_budget_limit("daily", model, endpoint)
            weekly_limit = self.budget_config.get_budget_limit(
                "weekly", model, endpoint
            )
            monthly_limit = self.budget_config.get_budget_limit(
                "monthly", model, endpoint
            )

            # Calculate utilization percentages
            daily_utilization = daily_cost / daily_limit if daily_limit > 0 else 0
            weekly_utilization = weekly_cost / weekly_limit if weekly_limit > 0 else 0
            monthly_utilization = (
                monthly_cost / monthly_limit if monthly_limit > 0 else 0
            )

            # Calculate remaining budgets
            daily_remaining = (
                max(0, daily_limit - daily_cost) if daily_limit > 0 else float("inf")
            )
            weekly_remaining = (
                max(0, weekly_limit - weekly_cost) if weekly_limit > 0 else float("inf")
            )
            monthly_remaining = (
                max(0, monthly_limit - monthly_cost)
                if monthly_limit > 0
                else float("inf")
            )

            return {
                "daily_utilization": daily_utilization,
                "weekly_utilization": weekly_utilization,
                "monthly_utilization": monthly_utilization,
                "daily_remaining": daily_remaining,
                "weekly_remaining": weekly_remaining,
                "monthly_remaining": monthly_remaining,
            }

        except Exception as e:
            logger.warning(f"Failed to get budget status: {e}")
            # Return safe defaults
            return {
                "daily_utilization": 0,
                "weekly_utilization": 0,
                "monthly_utilization": 0,
                "daily_remaining": float("inf"),
                "weekly_remaining": float("inf"),
                "monthly_remaining": float("inf"),
            }

    def _check_rate_limits(
        self, service: str, model: str, endpoint: str
    ) -> ThrottlingDecision:
        """Check if request violates rate limits."""
        key = f"{service}:{model}:{endpoint}"

        with self.lock:
            if key not in self.request_trackers:
                self.request_trackers[key] = RequestTracker()

            tracker = self.request_trackers[key]
            minute_count, hour_count = tracker.get_request_counts()

            # Check concurrent requests
            if (
                tracker.concurrent_count
                >= self.rate_limit_config.max_concurrent_requests
            ):
                return ThrottlingDecision(
                    action=ThrottlingAction.DELAY,
                    delay_seconds=1.0,
                    reason=f"Too many concurrent requests ({tracker.concurrent_count})",
                )

            # Check per-minute rate limit
            if minute_count >= self.rate_limit_config.max_requests_per_minute:
                delay = 60.0 / self.rate_limit_config.max_requests_per_minute
                return ThrottlingDecision(
                    action=ThrottlingAction.DELAY,
                    delay_seconds=delay,
                    reason=f"Per-minute rate limit exceeded ({minute_count}/min)",
                )

            # Check per-hour rate limit
            if hour_count >= self.rate_limit_config.max_requests_per_hour:
                return ThrottlingDecision(
                    action=ThrottlingAction.REJECT,
                    reason=f"Per-hour rate limit exceeded ({hour_count}/hour)",
                )

            return ThrottlingDecision(action=ThrottlingAction.ALLOW)

    def _choose_adaptive_strategy(
        self, budget_status: dict[str, float]
    ) -> ThrottlingStrategy:
        """Choose the best strategy based on current budget status."""
        max_utilization = max(
            budget_status["daily_utilization"],
            budget_status["weekly_utilization"],
            budget_status["monthly_utilization"],
        )

        if max_utilization < 0.7:
            return ThrottlingStrategy.SOFT
        elif max_utilization < 0.9:
            return ThrottlingStrategy.GRACEFUL
        else:
            return ThrottlingStrategy.HARD

    def _make_throttling_decision(
        self,
        service: str,
        model: str,
        endpoint: str,
        estimated_cost: float,
        budget_status: dict[str, float],
        strategy: ThrottlingStrategy,
    ) -> ThrottlingDecision:
        """Make the actual throttling decision based on strategy."""
        max_utilization = max(
            budget_status["daily_utilization"],
            budget_status["weekly_utilization"],
            budget_status["monthly_utilization"],
        )

        min_remaining = min(
            budget_status["daily_remaining"],
            budget_status["weekly_remaining"],
            budget_status["monthly_remaining"],
        )

        # Get alert thresholds
        alert_thresholds = self.budget_config.get_alert_thresholds()
        warning_threshold = alert_thresholds[0].percentage if alert_thresholds else 0.8
        critical_threshold = (
            alert_thresholds[1].percentage if len(alert_thresholds) > 1 else 0.95
        )

        # Determine budget limit for alerting
        budget_limit = None
        if budget_status["daily_remaining"] == min_remaining:
            budget_limit = self.budget_config.get_budget_limit("daily", model, endpoint)
        elif budget_status["weekly_remaining"] == min_remaining:
            budget_limit = self.budget_config.get_budget_limit(
                "weekly", model, endpoint
            )
        else:
            budget_limit = self.budget_config.get_budget_limit(
                "monthly", model, endpoint
            )

        current_cost = (
            budget_limit - min_remaining
            if budget_limit and budget_limit != float("inf")
            else None
        )

        # Check if cost would exceed remaining budget
        if estimated_cost > min_remaining:
            if strategy == ThrottlingStrategy.HARD:
                # Send budget exceeded alert
                self._send_throttling_alert(
                    AlertType.BUDGET_EXCEEDED,
                    AlertLevel.CRITICAL,
                    service,
                    model,
                    endpoint,
                    f"Request rejected: Cost ${estimated_cost:.4f} exceeds remaining budget ${min_remaining:.4f}",
                    current_cost,
                    budget_limit,
                    max_utilization * 100,
                )

                return ThrottlingDecision(
                    action=ThrottlingAction.REJECT,
                    reason=f"Cost ${estimated_cost:.4f} exceeds remaining budget ${min_remaining:.4f}",
                    estimated_cost=estimated_cost,
                    budget_utilization=max_utilization,
                )
            elif strategy == ThrottlingStrategy.GRACEFUL:
                alternative = self._find_cheaper_alternative(
                    model, estimated_cost, min_remaining
                )
                if alternative:
                    # Send service degraded alert
                    self._send_throttling_alert(
                        AlertType.SERVICE_DEGRADED,
                        AlertLevel.WARNING,
                        service,
                        model,
                        endpoint,
                        f"Service downgraded from {model} to {alternative} due to budget constraints",
                        current_cost,
                        budget_limit,
                        max_utilization * 100,
                    )

                    return ThrottlingDecision(
                        action=ThrottlingAction.DOWNGRADE,
                        alternative_model=alternative,
                        reason=f"Downgrading from {model} to {alternative} to stay within budget",
                        estimated_cost=estimated_cost,
                        budget_utilization=max_utilization,
                    )
                else:
                    # Send budget exceeded alert
                    self._send_throttling_alert(
                        AlertType.BUDGET_EXCEEDED,
                        AlertLevel.CRITICAL,
                        service,
                        model,
                        endpoint,
                        f"Request rejected: No cheaper alternative available for {model}",
                        current_cost,
                        budget_limit,
                        max_utilization * 100,
                    )

                    return ThrottlingDecision(
                        action=ThrottlingAction.REJECT,
                        reason=f"No cheaper alternative available for {model}",
                        estimated_cost=estimated_cost,
                        budget_utilization=max_utilization,
                    )

        # Apply strategy based on utilization level
        if max_utilization >= critical_threshold:
            if strategy == ThrottlingStrategy.SOFT:
                delay = self._calculate_delay(max_utilization, critical_threshold)

                # Send throttling activated alert
                self._send_throttling_alert(
                    AlertType.THROTTLING_ACTIVATED,
                    AlertLevel.CRITICAL,
                    service,
                    model,
                    endpoint,
                    f"Request delayed by {delay:.1f}s due to critical budget utilization ({max_utilization:.1%})",
                    current_cost,
                    budget_limit,
                    max_utilization * 100,
                )

                return ThrottlingDecision(
                    action=ThrottlingAction.DELAY,
                    delay_seconds=delay,
                    reason=f"Critical budget utilization ({max_utilization:.1%})",
                    estimated_cost=estimated_cost,
                    budget_utilization=max_utilization,
                )
            elif strategy == ThrottlingStrategy.HARD:
                # Send budget exceeded alert
                self._send_throttling_alert(
                    AlertType.BUDGET_EXCEEDED,
                    AlertLevel.CRITICAL,
                    service,
                    model,
                    endpoint,
                    f"Request rejected due to critical budget utilization ({max_utilization:.1%})",
                    current_cost,
                    budget_limit,
                    max_utilization * 100,
                )

                return ThrottlingDecision(
                    action=ThrottlingAction.REJECT,
                    reason=f"Critical budget utilization ({max_utilization:.1%})",
                    estimated_cost=estimated_cost,
                    budget_utilization=max_utilization,
                )
            elif strategy == ThrottlingStrategy.GRACEFUL:
                alternative = self._find_cheaper_alternative(
                    model, estimated_cost, min_remaining
                )
                if alternative:
                    # Send service degraded alert
                    self._send_throttling_alert(
                        AlertType.SERVICE_DEGRADED,
                        AlertLevel.CRITICAL,
                        service,
                        model,
                        endpoint,
                        f"Critical utilization - service downgraded to {alternative}",
                        current_cost,
                        budget_limit,
                        max_utilization * 100,
                    )

                    return ThrottlingDecision(
                        action=ThrottlingAction.DOWNGRADE,
                        alternative_model=alternative,
                        reason=f"Critical utilization - downgrading to {alternative}",
                        estimated_cost=estimated_cost,
                        budget_utilization=max_utilization,
                    )

        elif max_utilization >= warning_threshold:
            if strategy == ThrottlingStrategy.SOFT:
                delay = self._calculate_delay(max_utilization, warning_threshold)

                # Send throttling activated alert (warning level)
                self._send_throttling_alert(
                    AlertType.THROTTLING_ACTIVATED,
                    AlertLevel.WARNING,
                    service,
                    model,
                    endpoint,
                    f"Request delayed by {delay:.1f}s due to warning budget utilization ({max_utilization:.1%})",
                    current_cost,
                    budget_limit,
                    max_utilization * 100,
                )

                return ThrottlingDecision(
                    action=ThrottlingAction.DELAY,
                    delay_seconds=delay,
                    reason=f"Warning budget utilization ({max_utilization:.1%})",
                    estimated_cost=estimated_cost,
                    budget_utilization=max_utilization,
                )
            elif strategy == ThrottlingStrategy.GRACEFUL:
                # Consider downgrading for expensive operations
                if (
                    estimated_cost > min_remaining * 0.1
                ):  # If cost is >10% of remaining budget
                    alternative = self._find_cheaper_alternative(
                        model, estimated_cost, min_remaining
                    )
                    if alternative:
                        # Send service degraded alert
                        self._send_throttling_alert(
                            AlertType.SERVICE_DEGRADED,
                            AlertLevel.WARNING,
                            service,
                            model,
                            endpoint,
                            "Warning utilization - suggesting cheaper alternative",
                            current_cost,
                            budget_limit,
                            max_utilization * 100,
                        )

                        return ThrottlingDecision(
                            action=ThrottlingAction.DOWNGRADE,
                            alternative_model=alternative,
                            reason=f"Warning utilization - downgrading to {alternative}",
                            estimated_cost=estimated_cost,
                            budget_utilization=max_utilization,
                        )

        # Allow the request
        return ThrottlingDecision(
            action=ThrottlingAction.ALLOW,
            reason="Within budget limits",
            estimated_cost=estimated_cost,
            budget_utilization=max_utilization,
        )

    def _find_cheaper_alternative(
        self, model: str, estimated_cost: float, remaining_budget: float
    ) -> Optional[str]:
        """Find a cheaper alternative model that fits within the remaining budget."""
        if model not in self.model_alternatives:
            return None

        base_cost_multiplier = self.model_cost_multipliers.get(model, 1.0)

        for alternative in self.model_alternatives[model]:
            alt_multiplier = self.model_cost_multipliers.get(alternative, 1.0)
            alt_cost = estimated_cost * (alt_multiplier / base_cost_multiplier)

            if alt_cost <= remaining_budget:
                return alternative

        return None

    def _calculate_delay(self, utilization: float, threshold: float) -> float:
        """Calculate delay based on utilization level."""
        # Exponential backoff based on how much over threshold we are
        excess = utilization - threshold
        max_delay = 30.0  # Maximum delay of 30 seconds

        # Scale delay exponentially with excess utilization
        delay = min(max_delay, 1.0 + (excess * 100) ** 1.5)
        return delay

    def _send_throttling_alert(
        self,
        alert_type: AlertType,
        alert_level: AlertLevel,
        service: str,
        model: str,
        endpoint: str,
        message: str,
        current_cost: Optional[float],
        budget_limit: Optional[float],
        utilization: float,
    ) -> None:
        """Send a throttling alert."""
        try:
            send_budget_alert(
                alert_type=alert_type,
                severity=alert_level,
                title=f"Budget Throttling: {service}",
                message=message,
                service=service,
                model=model,
                endpoint=endpoint,
                current_cost=current_cost,
                budget_limit=budget_limit,
                utilization_percentage=utilization,
            )
        except Exception as e:
            logger.warning(f"Failed to send throttling alert: {e}")

    def record_request_start(self, service: str, model: str, endpoint: str) -> None:
        """Record the start of a request for rate limiting."""
        key = f"{service}:{model}:{endpoint}"

        with self.lock:
            if key not in self.request_trackers:
                self.request_trackers[key] = RequestTracker()

            self.request_trackers[key].add_request()

    def record_request_end(self, service: str, model: str, endpoint: str) -> None:
        """Record the end of a request for rate limiting."""
        key = f"{service}:{model}:{endpoint}"

        with self.lock:
            if key in self.request_trackers:
                self.request_trackers[key].complete_request()

    def get_throttling_stats(self) -> dict[str, Any]:
        """Get current throttling statistics."""
        stats = {
            "rate_limit_config": {
                "max_requests_per_minute": self.rate_limit_config.max_requests_per_minute,
                "max_requests_per_hour": self.rate_limit_config.max_requests_per_hour,
                "max_concurrent_requests": self.rate_limit_config.max_concurrent_requests,
            },
            "active_trackers": {},
        }

        with self.lock:
            for key, tracker in self.request_trackers.items():
                minute_count, hour_count = tracker.get_request_counts()
                stats["active_trackers"][key] = {
                    "concurrent_requests": tracker.concurrent_count,
                    "requests_last_minute": minute_count,
                    "requests_last_hour": hour_count,
                }

        return stats

    def update_rate_limits(
        self,
        max_requests_per_minute: Optional[int] = None,
        max_requests_per_hour: Optional[int] = None,
        max_concurrent_requests: Optional[int] = None,
    ) -> None:
        """Update rate limiting configuration."""
        if max_requests_per_minute is not None:
            self.rate_limit_config.max_requests_per_minute = max_requests_per_minute
        if max_requests_per_hour is not None:
            self.rate_limit_config.max_requests_per_hour = max_requests_per_hour
        if max_concurrent_requests is not None:
            self.rate_limit_config.max_concurrent_requests = max_concurrent_requests

        logger.info(f"Updated rate limits: {self.rate_limit_config}")


# Global throttling service instance
_throttling_service = None
_throttling_lock = Lock()


def get_throttling_service() -> ThrottlingService:
    """Get the global throttling service instance."""
    global _throttling_service

    if _throttling_service is None:
        with _throttling_lock:
            if _throttling_service is None:
                _throttling_service = ThrottlingService()

    return _throttling_service


def reset_throttling_service() -> None:
    """Reset the global throttling service instance (for testing)."""
    global _throttling_service

    with _throttling_lock:
        _throttling_service = None


# Convenience functions
def should_throttle_request(
    service: str,
    model: str,
    endpoint: str,
    estimated_cost: float,
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
) -> ThrottlingDecision:
    """Convenience function to check if a request should be throttled."""
    throttling_service = get_throttling_service()
    return throttling_service.should_throttle(
        service, model, endpoint, estimated_cost, strategy
    )


def apply_throttling_decision(decision: ThrottlingDecision) -> bool:
    """
    Apply a throttling decision.

    Args:
        decision: The throttling decision to apply

    Returns:
        True if the request should proceed, False if it should be blocked
    """
    if decision.action == ThrottlingAction.ALLOW:
        return True
    elif decision.action == ThrottlingAction.DELAY:
        if decision.delay_seconds > 0:
            logger.info(
                f"Throttling: delaying request for {decision.delay_seconds:.2f}s - {decision.reason}"
            )
            time.sleep(decision.delay_seconds)
        return True
    elif decision.action == ThrottlingAction.REJECT:
        logger.warning(f"Throttling: rejecting request - {decision.reason}")
        return False
    elif decision.action == ThrottlingAction.DOWNGRADE:
        logger.info(
            f"Throttling: suggesting model downgrade to {decision.alternative_model} - {decision.reason}"
        )
        return True  # Let the caller handle the downgrade

    return True


async def apply_throttling_decision_async(decision: ThrottlingDecision) -> bool:
    """
    Apply a throttling decision asynchronously.

    Args:
        decision: The throttling decision to apply

    Returns:
        True if the request should proceed, False if it should be blocked
    """
    if decision.action == ThrottlingAction.ALLOW:
        return True
    elif decision.action == ThrottlingAction.DELAY:
        if decision.delay_seconds > 0:
            logger.info(
                f"Throttling: delaying request for {decision.delay_seconds:.2f}s - {decision.reason}"
            )
            await asyncio.sleep(decision.delay_seconds)
        return True
    elif decision.action == ThrottlingAction.REJECT:
        logger.warning(f"Throttling: rejecting request - {decision.reason}")
        return False
    elif decision.action == ThrottlingAction.DOWNGRADE:
        logger.info(
            f"Throttling: suggesting model downgrade to {decision.alternative_model} - {decision.reason}"
        )
        return True  # Let the caller handle the downgrade

    return True
