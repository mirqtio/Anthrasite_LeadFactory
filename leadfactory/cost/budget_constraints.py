"""
Budget Constraints System
------------------------
This module provides budget-based cost control to replace tier-based limitations.
It includes cost simulation, validation before execution, and budget limits that
prevent execution when costs would exceed limits.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CostEstimate:
    """Represents a cost estimate for an operation."""

    service: str
    operation: str
    estimated_cost: float
    confidence: float  # 0.0 to 1.0
    details: Optional[dict[str, Any]] = None


@dataclass
class BudgetLimit:
    """Represents a budget limit configuration."""

    name: str
    limit_amount: float
    period: str  # 'daily', 'monthly', 'yearly'
    warning_threshold: float = 0.8  # Warn at 80% of limit
    critical_threshold: float = 0.95  # Critical at 95% of limit


@dataclass
class BudgetStatus:
    """Represents current budget status."""

    current_spent: float
    limit: BudgetLimit
    remaining: float
    utilization_percent: float
    is_warning: bool
    is_critical: bool
    is_exceeded: bool


class BudgetConstraints:
    """Budget-based cost control system."""

    def __init__(self):
        """Initialize budget constraints system."""
        self.cost_tracker = self._get_cost_tracker()

        # Load budget limits from environment or defaults
        self.budget_limits = self._load_budget_limits()

        # Cost estimation models
        self.cost_models = self._initialize_cost_models()

        logger.info("Budget constraints system initialized")

    def _get_cost_tracker(self):
        """Get cost tracker instance."""
        try:
            from leadfactory.cost.cost_tracking import cost_tracker

            return cost_tracker
        except ImportError:
            logger.warning("Cost tracker not available, using mock")
            return None

    def _load_budget_limits(self) -> dict[str, BudgetLimit]:
        """Load budget limits from environment variables."""
        return {
            "daily": BudgetLimit(
                name="daily",
                limit_amount=float(os.environ.get("DAILY_BUDGET_LIMIT", "50.0")),
                period="daily",
                warning_threshold=float(
                    os.environ.get("DAILY_WARNING_THRESHOLD", "0.8")
                ),
                critical_threshold=float(
                    os.environ.get("DAILY_CRITICAL_THRESHOLD", "0.95")
                ),
            ),
            "monthly": BudgetLimit(
                name="monthly",
                limit_amount=float(os.environ.get("MONTHLY_BUDGET_LIMIT", "1000.0")),
                period="monthly",
                warning_threshold=float(
                    os.environ.get("MONTHLY_WARNING_THRESHOLD", "0.8")
                ),
                critical_threshold=float(
                    os.environ.get("MONTHLY_CRITICAL_THRESHOLD", "0.95")
                ),
            ),
        }

    def _initialize_cost_models(self) -> dict[str, dict[str, float]]:
        """Initialize cost estimation models for different services."""
        return {
            "openai": {
                "gpt-4o": 0.005,  # per 1k tokens (input)
                "gpt-4o-output": 0.015,  # per 1k tokens (output)
                "gpt-4": 0.03,  # per 1k tokens (input)
                "gpt-4-output": 0.06,  # per 1k tokens (output)
                "dall-e-3": 0.04,  # per image
            },
            "semrush": {
                "domain-overview": 0.10,  # per request
                "backlinks": 0.05,  # per request
                "keywords": 0.08,  # per request
            },
            "screenshot": {
                "capture": 0.001,  # per screenshot
                "full-page": 0.002,  # per full page screenshot
            },
            "gpu": {
                "hourly-rate": float(os.environ.get("GPU_HOURLY_RATE", "2.5")),
                "minimum-charge": 0.1,  # Minimum 6 minutes
            },
        }

    def estimate_operation_cost(
        self, service: str, operation: str, parameters: Optional[dict[str, Any]] = None
    ) -> CostEstimate:
        """Estimate the cost of an operation before execution."""
        if service not in self.cost_models:
            logger.warning(f"No cost model for service: {service}")
            return CostEstimate(
                service=service,
                operation=operation,
                estimated_cost=0.0,
                confidence=0.0,
                details={"error": "No cost model available"},
            )

        service_model = self.cost_models[service]

        if operation not in service_model:
            logger.warning(f"No cost model for operation: {service}.{operation}")
            return CostEstimate(
                service=service,
                operation=operation,
                estimated_cost=0.0,
                confidence=0.0,
                details={"error": "No operation model available"},
            )

        base_cost = service_model[operation]

        # Apply parameter-based scaling
        estimated_cost = self._scale_cost_by_parameters(
            base_cost, service, operation, parameters or {}
        )

        return CostEstimate(
            service=service,
            operation=operation,
            estimated_cost=estimated_cost,
            confidence=0.8,  # Default confidence
            details={"base_cost": base_cost, "parameters": parameters},
        )

    def _scale_cost_by_parameters(
        self, base_cost: float, service: str, operation: str, parameters: dict[str, Any]
    ) -> float:
        """Scale base cost based on operation parameters."""
        if service == "openai":
            # Scale by token count
            if "tokens" in parameters:
                return base_cost * (parameters["tokens"] / 1000)
            elif "prompt_length" in parameters:
                # Estimate tokens as ~4 characters per token
                estimated_tokens = parameters["prompt_length"] / 4
                return base_cost * (estimated_tokens / 1000)
            else:
                # Default estimate for typical prompt
                return base_cost * 2  # ~2k tokens average

        elif service == "gpu":
            # Scale by duration
            if "duration_hours" in parameters:
                return base_cost * parameters["duration_hours"]
            else:
                # Default minimum charge
                return self.cost_models[service]["minimum-charge"]

        # For other services, return base cost
        return base_cost

    def get_budget_status(self, period: str = "daily") -> BudgetStatus:
        """Get current budget status for a period."""
        if period not in self.budget_limits:
            raise ValueError(f"Unknown budget period: {period}")

        limit = self.budget_limits[period]

        # Get current spending
        if self.cost_tracker:
            if period == "daily":
                current_spent = self.cost_tracker.get_daily_cost()
            elif period == "monthly":
                current_spent = self.cost_tracker.get_monthly_cost()
            else:
                current_spent = 0.0
        else:
            current_spent = 0.0

        remaining = max(0.0, limit.limit_amount - current_spent)
        utilization_percent = (current_spent / limit.limit_amount) * 100

        return BudgetStatus(
            current_spent=current_spent,
            limit=limit,
            remaining=remaining,
            utilization_percent=utilization_percent,
            is_warning=utilization_percent >= (limit.warning_threshold * 100),
            is_critical=utilization_percent >= (limit.critical_threshold * 100),
            is_exceeded=current_spent >= limit.limit_amount,
        )

    def can_execute_operation(
        self,
        service: str,
        operation: str,
        parameters: Optional[dict[str, Any]] = None,
        check_periods: list[str] = None,
    ) -> tuple[bool, str, list[CostEstimate]]:
        """
        Check if an operation can be executed within budget constraints.

        Returns:
            Tuple of (can_execute, reason, cost_estimates)
        """
        if check_periods is None:
            check_periods = ["daily", "monthly"]

        # Estimate operation cost
        cost_estimate = self.estimate_operation_cost(service, operation, parameters)

        # Check each budget period
        for period in check_periods:
            budget_status = self.get_budget_status(period)

            # Check if operation would exceed budget
            if cost_estimate.estimated_cost > budget_status.remaining:
                return (
                    False,
                    f"Operation would exceed {period} budget: "
                    f"${cost_estimate.estimated_cost:.2f} > ${budget_status.remaining:.2f} remaining",
                    [cost_estimate],
                )

            # Check if operation would push us over critical threshold
            projected_spent = budget_status.current_spent + cost_estimate.estimated_cost
            projected_utilization = (
                projected_spent / budget_status.limit.limit_amount
            ) * 100

            if projected_utilization >= (budget_status.limit.critical_threshold * 100):
                return (
                    False,
                    f"Operation would exceed {period} critical threshold: "
                    f"{projected_utilization:.1f}% >= {budget_status.limit.critical_threshold * 100:.1f}%",
                    [cost_estimate],
                )

        return (True, "Operation within budget constraints", [cost_estimate])

    def simulate_pipeline_costs(
        self, operations: list[tuple[str, str, Optional[dict[str, Any]]]]
    ) -> dict[str, Any]:
        """
        Simulate the total cost of a pipeline execution.

        Args:
            operations: List of (service, operation, parameters) tuples

        Returns:
            Dictionary with simulation results
        """
        total_estimated_cost = 0.0
        operation_estimates = []

        for service, operation, parameters in operations:
            estimate = self.estimate_operation_cost(service, operation, parameters)
            operation_estimates.append(estimate)
            total_estimated_cost += estimate.estimated_cost

        # Check budget impact
        daily_status = self.get_budget_status("daily")
        monthly_status = self.get_budget_status("monthly")

        daily_remaining_after = daily_status.remaining - total_estimated_cost
        monthly_remaining_after = monthly_status.remaining - total_estimated_cost

        return {
            "total_estimated_cost": total_estimated_cost,
            "operation_estimates": operation_estimates,
            "budget_impact": {
                "daily": {
                    "current_remaining": daily_status.remaining,
                    "remaining_after": daily_remaining_after,
                    "would_exceed": daily_remaining_after < 0,
                },
                "monthly": {
                    "current_remaining": monthly_status.remaining,
                    "remaining_after": monthly_remaining_after,
                    "would_exceed": monthly_remaining_after < 0,
                },
            },
            "can_execute": daily_remaining_after >= 0 and monthly_remaining_after >= 0,
        }

    def get_budget_report(self) -> dict[str, Any]:
        """Generate a comprehensive budget report."""
        daily_status = self.get_budget_status("daily")
        monthly_status = self.get_budget_status("monthly")

        return {
            "timestamp": datetime.now().isoformat(),
            "daily": {
                "limit": daily_status.limit.limit_amount,
                "spent": daily_status.current_spent,
                "remaining": daily_status.remaining,
                "utilization_percent": daily_status.utilization_percent,
                "status": self._get_status_level(daily_status),
            },
            "monthly": {
                "limit": monthly_status.limit.limit_amount,
                "spent": monthly_status.current_spent,
                "remaining": monthly_status.remaining,
                "utilization_percent": monthly_status.utilization_percent,
                "status": self._get_status_level(monthly_status),
            },
            "cost_models": self.cost_models,
        }

    def _get_status_level(self, status: BudgetStatus) -> str:
        """Get status level string."""
        if status.is_exceeded:
            return "exceeded"
        elif status.is_critical:
            return "critical"
        elif status.is_warning:
            return "warning"
        else:
            return "normal"


# Create singleton instance
budget_constraints = BudgetConstraints()


def budget_check(
    service: str, operation: str, parameters: Optional[dict[str, Any]] = None
) -> tuple[bool, str]:
    """
    Convenience function to check if an operation can be executed.

    Returns:
        Tuple of (can_execute, reason)
    """
    can_execute, reason, _ = budget_constraints.can_execute_operation(
        service, operation, parameters
    )
    return can_execute, reason


def estimate_cost(
    service: str, operation: str, parameters: Optional[dict[str, Any]] = None
) -> float:
    """
    Convenience function to estimate operation cost.

    Returns:
        Estimated cost in USD
    """
    estimate = budget_constraints.estimate_operation_cost(
        service, operation, parameters
    )
    return estimate.estimated_cost


def get_budget_summary() -> dict[str, Any]:
    """
    Convenience function to get budget summary.

    Returns:
        Budget summary dictionary
    """
    return budget_constraints.get_budget_report()
