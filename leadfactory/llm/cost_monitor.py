"""
LLM Cost Monitoring System

This module provides real-time cost tracking for LLM API calls,
budget management, and cost-based decision making for the fallback system.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class BudgetPeriod(Enum):
    """Budget period options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AlertLevel(Enum):
    """Cost alert levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class CostEntry:
    """Individual cost entry for tracking."""

    provider: str
    timestamp: float
    cost: float
    tokens_used: int
    request_type: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetConfig:
    """Budget configuration for cost monitoring."""

    daily_limit: float = 100.0
    weekly_limit: float = 500.0
    monthly_limit: float = 2000.0
    warning_threshold: float = 0.8  # 80% of limit
    critical_threshold: float = 0.95  # 95% of limit
    enable_auto_pause: bool = True  # Auto-pause when limit exceeded
    alert_email: Optional[str] = None
    slack_webhook: Optional[str] = None


@dataclass
class CostStats:
    """Cost statistics for a given period."""

    period: BudgetPeriod
    start_time: float
    end_time: float
    total_cost: float = 0.0
    total_requests: int = 0
    total_tokens: int = 0
    provider_costs: Dict[str, float] = field(default_factory=dict)
    model_costs: Dict[str, float] = field(default_factory=dict)
    average_cost_per_request: float = 0.0
    average_cost_per_token: float = 0.0


class CostMonitor:
    """
    Real-time cost monitoring and budget management.

    This class tracks LLM API costs, enforces budget limits,
    and provides cost-based decision making for the fallback system.
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        """
        Initialize the cost monitor.

        Args:
            config: Budget configuration (uses defaults if None)
        """
        self.config = config or BudgetConfig()
        self.cost_entries: List[CostEntry] = []
        self._lock = None  # Will be initialized when first needed
        self._alert_callbacks: List[callable] = []
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # Cleanup old entries every hour

        logger.info(
            f"Cost monitor initialized with daily limit: ${self.config.daily_limit}"
        )

    def _get_lock(self):
        """Get or create the async lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def record_cost(
        self,
        provider: str,
        cost: float,
        tokens_used: int,
        request_type: str = "completion",
        model: str = "unknown",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a cost entry.

        Args:
            provider: Provider name (e.g., "gpt4o", "claude")
            cost: Cost in USD
            tokens_used: Total tokens used
            request_type: Type of request (completion, embedding, etc.)
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            metadata: Additional metadata
        """
        async with self._get_lock():
            entry = CostEntry(
                provider=provider,
                timestamp=time.time(),
                cost=cost,
                tokens_used=tokens_used,
                request_type=request_type,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                metadata=metadata or {},
            )

            self.cost_entries.append(entry)

            logger.debug(
                f"Recorded cost: {provider} ${cost:.4f} "
                f"({tokens_used} tokens, {model})"
            )

            # Check budget limits and trigger alerts if needed
            await self._check_budget_limits()

            # Cleanup old entries periodically
            await self._cleanup_old_entries()

    async def get_current_costs(
        self, period: BudgetPeriod = BudgetPeriod.DAILY, provider: Optional[str] = None
    ) -> CostStats:
        """
        Get current cost statistics for a period.

        Args:
            period: Budget period to calculate for
            provider: Specific provider to filter by (optional)

        Returns:
            Cost statistics for the period
        """
        async with self._get_lock():
            now = time.time()
            start_time = self._get_period_start(now, period)

            # Filter entries by time period and provider
            filtered_entries = [
                entry
                for entry in self.cost_entries
                if entry.timestamp >= start_time
                and (provider is None or entry.provider == provider)
            ]

            if not filtered_entries:
                return CostStats(period=period, start_time=start_time, end_time=now)

            # Calculate statistics
            total_cost = sum(entry.cost for entry in filtered_entries)
            total_requests = len(filtered_entries)
            total_tokens = sum(entry.tokens_used for entry in filtered_entries)

            # Provider breakdown
            provider_costs = {}
            for entry in filtered_entries:
                provider_costs[entry.provider] = (
                    provider_costs.get(entry.provider, 0) + entry.cost
                )

            # Model breakdown
            model_costs = {}
            for entry in filtered_entries:
                model_costs[entry.model] = model_costs.get(entry.model, 0) + entry.cost

            # Averages
            avg_cost_per_request = (
                total_cost / total_requests if total_requests > 0 else 0
            )
            avg_cost_per_token = total_cost / total_tokens if total_tokens > 0 else 0

            return CostStats(
                period=period,
                start_time=start_time,
                end_time=now,
                total_cost=total_cost,
                total_requests=total_requests,
                total_tokens=total_tokens,
                provider_costs=provider_costs,
                model_costs=model_costs,
                average_cost_per_request=avg_cost_per_request,
                average_cost_per_token=avg_cost_per_token,
            )

    async def check_budget_status(
        self, period: BudgetPeriod = BudgetPeriod.DAILY
    ) -> Dict[str, Any]:
        """
        Check current budget status.

        Args:
            period: Budget period to check

        Returns:
            Dictionary with budget status information
        """
        stats = await self.get_current_costs(period)
        limit = self._get_period_limit(period)

        usage_percentage = (stats.total_cost / limit) * 100 if limit > 0 else 0
        remaining_budget = max(0, limit - stats.total_cost)

        # Determine alert level
        alert_level = AlertLevel.INFO
        if usage_percentage >= self.config.critical_threshold * 100:
            alert_level = AlertLevel.CRITICAL
        elif usage_percentage >= self.config.warning_threshold * 100:
            alert_level = AlertLevel.WARNING

        if stats.total_cost >= limit:
            alert_level = AlertLevel.EMERGENCY

        return {
            "period": period.value,
            "limit": limit,
            "current_cost": stats.total_cost,
            "remaining_budget": remaining_budget,
            "usage_percentage": usage_percentage,
            "alert_level": alert_level.value,
            "should_pause": (
                self.config.enable_auto_pause and stats.total_cost >= limit
            ),
            "stats": stats,
        }

    async def is_budget_exceeded(
        self, period: BudgetPeriod = BudgetPeriod.DAILY
    ) -> bool:
        """
        Check if budget is exceeded for a period.

        Args:
            period: Budget period to check

        Returns:
            True if budget is exceeded
        """
        status = await self.check_budget_status(period)
        return status["should_pause"]

    async def get_cheapest_provider(
        self, providers: List[str], period: BudgetPeriod = BudgetPeriod.DAILY
    ) -> Optional[str]:
        """
        Get the cheapest provider based on recent usage.

        Args:
            providers: List of provider names to compare
            period: Period to analyze costs for

        Returns:
            Name of cheapest provider, or None if no data
        """
        provider_costs = {}

        for provider in providers:
            stats = await self.get_current_costs(period, provider)
            if stats.total_requests > 0:
                provider_costs[provider] = stats.average_cost_per_request

        if not provider_costs:
            return None

        return min(provider_costs, key=provider_costs.get)

    def add_alert_callback(self, callback: callable) -> None:
        """
        Add a callback function for budget alerts.

        Args:
            callback: Function to call when alerts are triggered
        """
        self._alert_callbacks.append(callback)

    async def export_cost_data(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        format: str = "json",
    ) -> Union[Dict[str, Any], str]:
        """
        Export cost data for analysis.

        Args:
            start_time: Start timestamp (default: 24 hours ago)
            end_time: End timestamp (default: now)
            format: Export format ("json" or "csv")

        Returns:
            Exported data in requested format
        """
        async with self._get_lock():
            now = time.time()
            start_time = start_time or (now - 86400)  # 24 hours ago
            end_time = end_time or now

            filtered_entries = [
                entry
                for entry in self.cost_entries
                if start_time <= entry.timestamp <= end_time
            ]

            if format == "json":
                return {
                    "start_time": start_time,
                    "end_time": end_time,
                    "total_entries": len(filtered_entries),
                    "entries": [
                        {
                            "provider": entry.provider,
                            "timestamp": entry.timestamp,
                            "cost": entry.cost,
                            "tokens_used": entry.tokens_used,
                            "request_type": entry.request_type,
                            "model": entry.model,
                            "prompt_tokens": entry.prompt_tokens,
                            "completion_tokens": entry.completion_tokens,
                            "metadata": entry.metadata,
                        }
                        for entry in filtered_entries
                    ],
                }
            elif format == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write header
                writer.writerow(
                    [
                        "provider",
                        "timestamp",
                        "cost",
                        "tokens_used",
                        "request_type",
                        "model",
                        "prompt_tokens",
                        "completion_tokens",
                    ]
                )

                # Write data
                for entry in filtered_entries:
                    writer.writerow(
                        [
                            entry.provider,
                            entry.timestamp,
                            entry.cost,
                            entry.tokens_used,
                            entry.request_type,
                            entry.model,
                            entry.prompt_tokens,
                            entry.completion_tokens,
                        ]
                    )

                return output.getvalue()
            else:
                raise ValueError(f"Unsupported format: {format}")

    async def _check_budget_limits(self) -> None:
        """Check budget limits and trigger alerts if needed."""
        for period in BudgetPeriod:
            status = await self.check_budget_status(period)

            if status["alert_level"] in [
                AlertLevel.WARNING.value,
                AlertLevel.CRITICAL.value,
                AlertLevel.EMERGENCY.value,
            ]:
                await self._trigger_alert(period, status)

    async def _trigger_alert(
        self, period: BudgetPeriod, status: Dict[str, Any]
    ) -> None:
        """Trigger budget alert."""
        alert_message = (
            f"Budget alert for {period.value}: "
            f"${status['current_cost']:.2f} / ${status['limit']:.2f} "
            f"({status['usage_percentage']:.1f}%) - "
            f"Level: {status['alert_level']}"
        )

        logger.warning(alert_message)

        # Call registered callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(period, status)
                else:
                    callback(period, status)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def _get_period_start(self, timestamp: float, period: BudgetPeriod) -> float:
        """Get the start timestamp for a budget period."""
        dt = datetime.fromtimestamp(timestamp)

        if period == BudgetPeriod.DAILY:
            start_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.WEEKLY:
            days_since_monday = dt.weekday()
            start_dt = (dt - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == BudgetPeriod.MONTHLY:
            start_dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported period: {period}")

        return start_dt.timestamp()

    def _get_period_limit(self, period: BudgetPeriod) -> float:
        """Get the budget limit for a period."""
        if period == BudgetPeriod.DAILY:
            return self.config.daily_limit
        elif period == BudgetPeriod.WEEKLY:
            return self.config.weekly_limit
        elif period == BudgetPeriod.MONTHLY:
            return self.config.monthly_limit
        else:
            raise ValueError(f"Unsupported period: {period}")

    async def _cleanup_old_entries(self) -> None:
        """Clean up old cost entries to prevent memory bloat."""
        now = time.time()

        # Only cleanup once per hour
        if now - self._last_cleanup < self._cleanup_interval:
            return

        # Keep entries from the last 30 days
        cutoff_time = now - (30 * 24 * 3600)

        original_count = len(self.cost_entries)
        self.cost_entries = [
            entry for entry in self.cost_entries if entry.timestamp >= cutoff_time
        ]

        removed_count = original_count - len(self.cost_entries)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old cost entries")

        self._last_cleanup = now
