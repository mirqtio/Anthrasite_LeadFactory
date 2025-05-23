#!/usr/bin/env python
"""
Budget Gate
---------
This module provides a budget gate mechanism to prevent expensive operations
when the monthly budget threshold has been reached. It integrates with the
cost tracking system and provides decorators and utility functions to gate
expensive operations.

Usage:
    from bin.budget_gate import budget_gate, budget_gated

    # Check if budget gate is active
    if budget_gate.is_active():
        # Skip expensive operation
        logger.info("Skipping expensive operation due to budget gate")
    else:
        # Perform expensive operation
        perform_expensive_operation()

    # Or use the decorator
    @budget_gated(operation="gpt-4")
    def call_gpt4(prompt):
        # This function will be skipped if budget gate is active
        return openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
"""

import functools
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any

# Add parent directory to path to allow importing metrics and cost_tracking
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bin.cost_tracking import cost_tracker
from bin.metrics import metrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "budget_gate.log")),
    ],
)
logger = logging.getLogger("budget_gate")


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
        # If gate is disabled or override is set, always return False
        if not self.enabled or self.override:
            return False

        # Check with cost tracker
        active = cost_tracker.is_budget_gate_active()

        # Update metrics if active
        if active:
            metrics.update_budget_gate_status(True)

        return active

    def gate_operation(self, operation: str) -> bool:
        """Gate an operation based on budget status.

        Args:
            operation: Name of the operation to gate

        Returns:
            True if operation should proceed, False if it should be skipped
        """
        if self.is_active():
            # Operation should be skipped
            if operation not in self.skipped_operations:
                self.skipped_operations[operation] = 0

            self.skipped_operations[operation] += 1

            # Update metrics
            metrics.increment_budget_gate_skipped(operation)

            logger.warning(f"Operation '{operation}' skipped due to budget gate")
            return False
        else:
            # Operation can proceed
            return True

    def get_skipped_operations(self) -> dict[str, int]:
        """Get a dictionary of skipped operations and their counts.

        Returns:
            Dictionary mapping operation names to skip counts
        """
        return self.skipped_operations.copy()

    def reset_skipped_operations(self):
        """Reset the skipped operations counter."""
        self.skipped_operations = {}
        logger.info("Reset skipped operations counter")

    def set_enabled(self, enabled: bool):
        """Set whether the budget gate is enabled.

        Args:
            enabled: Whether the gate should be enabled
        """
        self.enabled = enabled
        logger.info(f"Budget gate {'enabled' if enabled else 'disabled'}")

    def set_override(self, override: bool):
        """Set whether to override the budget gate.

        Args:
            override: Whether to override the gate
        """
        self.override = override
        logger.info(f"Budget gate override {'enabled' if override else 'disabled'}")

    def set_threshold(self, threshold: float):
        """Set the budget threshold.

        Args:
            threshold: Budget threshold in USD
        """
        self.threshold = threshold
        logger.info(f"Budget gate threshold set to ${threshold:.2f}")


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
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if budget_gate.gate_operation(operation):
                # Budget gate is not active, proceed with operation
                return func(*args, **kwargs)
            else:
                # Budget gate is active, skip operation
                logger.info(
                    f"Skipped {func.__name__} due to budget gate (operation: {operation})"
                )

                # Log the skipped operation
                logger.info(f"SKIPPED_DUE_TO_BUDGET: {operation}")

                # Call fallback function if provided
                if fallback_function:
                    return fallback_function(*args, **kwargs)

                # Return fallback value
                return fallback_value

        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    # Example function with budget gate
    @budget_gated(
        operation="gpt-4",
        fallback_value={"text": "Budget limit reached, skipping GPT-4 call"},
    )
    def call_gpt4(prompt):
        # Simulate an expensive API call
        time.sleep(1)
        return {"text": "This is a simulated GPT-4 response"}

    # Test with budget gate inactive
    budget_gate.set_override(True)
    result = call_gpt4("Tell me a joke")

    # Test with budget gate active
    budget_gate.set_override(False)
    cost_tracker.budget_gate_active = True  # Simulate active budget gate
    result = call_gpt4("Tell me another joke")

    # Print skipped operations
