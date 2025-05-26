"""
Budget Gate
---------
This module provides a budget gate mechanism to prevent expensive operations
when the monthly budget threshold has been reached. It integrates with the
cost tracking system and provides decorators and utility functions to gate
expensive operations.
"""

import argparse
import logging
import os
import sys
from functools import wraps
from typing import Any, Callable, Dict, Optional

# Initialize logging
logger = logging.getLogger(__name__)


def _get_cost_tracker():
    """Get cost tracker singleton instance."""
    try:
        from leadfactory.cost.cost_tracking import cost_tracker

        return cost_tracker
    except ImportError:
        logger.warning("Cost tracker not available")
        return None


def _get_metrics():
    """Get metrics singleton instance."""
    try:
        from leadfactory.utils.metrics import metrics

        return metrics
    except ImportError:
        logger.warning("Metrics not available")
        return None


# Create instances to use in the code
cost_tracker = _get_cost_tracker()
metrics = _get_metrics()


class BudgetGate:
    """Budget gate mechanism to prevent expensive operations."""

    def __init__(self):
        """Initialize budget gate."""
        # Load configuration from environment variables
        self.enabled = os.environ.get("BUDGET_GATE_ENABLED", "true").lower() == "true"
        self.threshold = float(os.environ.get("BUDGET_GATE_THRESHOLD", "1000.0"))
        self.override = (
            os.environ.get("BUDGET_GATE_OVERRIDE", "false").lower() == "true"
        )

        # Track skipped operations
        self.skipped_operations = {}

        logger.info(
            f"Budget gate initialized (enabled={self.enabled}, threshold=${self.threshold:.2f}, override={self.override})"
        )

    def is_active(self) -> bool:
        """Check if the budget gate is active.

        Returns:
            True if budget gate is active and should block expensive operations
        """
        if not self.enabled:
            return False

        if self.override:
            return False

        if cost_tracker is None:
            logger.warning("Cost tracker not available, budget gate inactive")
            return False

        monthly_cost = cost_tracker.get_monthly_cost()
        is_active = monthly_cost >= self.threshold

        if is_active and metrics:
            metrics.update_budget_gate_status(active=True)

        return is_active

    def gate_operation(self, operation: str) -> bool:
        """Gate an operation based on budget status.

        Args:
            operation: Name of the operation to gate

        Returns:
            True if operation should proceed, False if it should be skipped
        """
        if not self.is_active():
            return True

        if operation not in self.skipped_operations:
            self.skipped_operations[operation] = 0

        self.skipped_operations[operation] += 1
        logger.warning(
            f"Operation '{operation}' skipped due to budget gate (threshold=${self.threshold:.2f})"
        )

        if metrics:
            metrics.increment_budget_gate_skipped(operation)

        return False

    def get_skipped_operations(self) -> Dict[str, int]:
        """Get a dictionary of skipped operations and their counts.

        Returns:
            Dictionary mapping operation names to skip counts
        """
        return self.skipped_operations.copy()

    def reset_skipped_operations(self) -> None:
        """Reset the skipped operations counter."""
        self.skipped_operations = {}

    def set_enabled(self, enabled: bool) -> None:
        """Set whether the budget gate is enabled.

        Args:
            enabled: Whether the gate should be enabled
        """
        self.enabled = enabled
        logger.info(f"Budget gate enabled={enabled}")

    def set_override(self, override: bool) -> None:
        """Set whether to override the budget gate.

        Args:
            override: Whether to override the gate
        """
        self.override = override
        logger.info(f"Budget gate override={override}")

    def set_threshold(self, threshold: float) -> None:
        """Set the budget threshold.

        Args:
            threshold: Budget threshold in USD
        """
        self.threshold = threshold
        logger.info(f"Budget gate threshold=${threshold:.2f}")


# Create a singleton instance
budget_gate = BudgetGate()


def budget_gated(
    operation: str,
    fallback_value: Any = None,
    fallback_function: Optional[Callable] = None,
):
    """Decorator to gate a function based on budget status.

    Args:
        operation: Name of the operation to gate
        fallback_value: Value to return if operation is skipped
        fallback_function: Function to call if operation is skipped

    Returns:
        Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if budget_gate.gate_operation(operation):
                return func(*args, **kwargs)
            else:
                if fallback_function is not None:
                    return fallback_function(*args, **kwargs)
                else:
                    return fallback_value

        return wrapper

    return decorator


def main():
    """Main function for the budget gate module."""
    parser = argparse.ArgumentParser(description="Budget Gate Management")
    parser.add_argument(
        "--check", action="store_true", help="Check if budget gate is active"
    )
    parser.add_argument(
        "--set-enabled",
        type=str,
        choices=["true", "false"],
        help="Set whether budget gate is enabled",
    )
    parser.add_argument(
        "--set-override",
        type=str,
        choices=["true", "false"],
        help="Set whether to override budget gate",
    )
    parser.add_argument(
        "--set-threshold", type=float, help="Set budget threshold in USD"
    )
    parser.add_argument(
        "--skipped", action="store_true", help="Show skipped operations"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.check:
        is_active = budget_gate.is_active()
        print(f"Budget gate is {'active' if is_active else 'inactive'}")
        print(f"  Enabled: {budget_gate.enabled}")
        print(f"  Override: {budget_gate.override}")
        print(f"  Threshold: ${budget_gate.threshold:.2f}")
        if cost_tracker:
            monthly_cost = cost_tracker.get_monthly_cost()
            print(f"  Monthly cost: ${monthly_cost:.2f}")
        else:
            print("  Monthly cost: Unknown (cost tracker not available)")

    if args.set_enabled is not None:
        budget_gate.set_enabled(args.set_enabled.lower() == "true")

    if args.set_override is not None:
        budget_gate.set_override(args.set_override.lower() == "true")

    if args.set_threshold is not None:
        budget_gate.set_threshold(args.set_threshold)

    if args.skipped:
        skipped = budget_gate.get_skipped_operations()
        if skipped:
            print("Skipped operations:")
            for op, count in skipped.items():
                print(f"  {op}: {count}")
        else:
            print("No operations have been skipped")

    return 0
