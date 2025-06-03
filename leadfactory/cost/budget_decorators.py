"""
Budget Constraint Decorators
---------------------------
This module provides decorators for budget-constrained operations to replace
tier-based cost control decorators.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional

from leadfactory.cost.budget_constraints import budget_constraints
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def budget_constrained(
    service: str,
    operation: str,
    parameters_func: Optional[Callable] = None,
    fallback_value: Any = None,
    fallback_function: Optional[Callable] = None,
    check_periods: Optional[list] = None,
):
    """
    Decorator to enforce budget constraints on a function.

    Args:
        service: Service name (e.g., 'openai', 'semrush')
        operation: Operation name (e.g., 'gpt-4o', 'domain-overview')
        parameters_func: Function to extract parameters from function args/kwargs
        fallback_value: Value to return if budget is exceeded
        fallback_function: Function to call if budget is exceeded
        check_periods: List of budget periods to check (default: ['daily', 'monthly'])

    Returns:
        Decorated function that checks budget before execution
    """
    if check_periods is None:
        check_periods = ["daily", "monthly"]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract parameters for cost estimation
            parameters = {}
            if parameters_func:
                try:
                    parameters = parameters_func(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        f"Failed to extract parameters for cost estimation: {e}"
                    )

            # Check budget constraints
            can_execute, reason, estimates = budget_constraints.can_execute_operation(
                service, operation, parameters, check_periods
            )

            if not can_execute:
                logger.warning(f"Budget constraint violation: {reason}")

                # Track the blocked operation
                if budget_constraints.cost_tracker:
                    budget_constraints.cost_tracker.add_cost(
                        amount=0.0,
                        service=service,
                        operation=f"{operation}_blocked",
                        details={
                            "reason": reason,
                            "estimated_cost": (
                                estimates[0].estimated_cost if estimates else 0.0
                            ),
                            "function": func.__name__,
                        },
                    )

                # Return fallback
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                else:
                    return fallback_value

            # Execute the function and track actual cost
            try:
                result = func(*args, **kwargs)

                # Track successful execution
                if budget_constraints.cost_tracker and estimates:
                    budget_constraints.cost_tracker.add_cost(
                        amount=estimates[0].estimated_cost,
                        service=service,
                        operation=operation,
                        details={
                            "function": func.__name__,
                            "parameters": parameters,
                            "estimated": True,
                        },
                    )

                return result

            except Exception as e:
                logger.error(f"Function {func.__name__} failed: {e}")
                raise

        return wrapper

    return decorator


def openai_budget_check(
    operation: str = "gpt-4o", token_param: str = "tokens", prompt_param: str = "prompt"
):
    """
    Specialized decorator for OpenAI operations.

    Args:
        operation: OpenAI operation (e.g., 'gpt-4o', 'dall-e-3')
        token_param: Parameter name for token count
        prompt_param: Parameter name for prompt text (for token estimation)

    Returns:
        Budget-constrained decorator for OpenAI operations
    """

    def extract_openai_parameters(*args, **kwargs):
        parameters = {}

        # Try to get token count
        if token_param in kwargs:
            parameters["tokens"] = kwargs[token_param]
        elif len(args) > 0 and hasattr(args[0], token_param):
            parameters["tokens"] = getattr(args[0], token_param)

        # Try to estimate from prompt length
        if "tokens" not in parameters and prompt_param in kwargs:
            prompt = kwargs[prompt_param]
            if isinstance(prompt, str):
                parameters["prompt_length"] = len(prompt)

        return parameters

    return budget_constrained(
        service="openai", operation=operation, parameters_func=extract_openai_parameters
    )


def semrush_budget_check(operation: str = "domain-overview"):
    """
    Specialized decorator for SEMrush operations.

    Args:
        operation: SEMrush operation name

    Returns:
        Budget-constrained decorator for SEMrush operations
    """
    return budget_constrained(service="semrush", operation=operation)


def screenshot_budget_check(operation: str = "capture"):
    """
    Specialized decorator for screenshot operations.

    Args:
        operation: Screenshot operation name

    Returns:
        Budget-constrained decorator for screenshot operations
    """
    return budget_constrained(service="screenshot", operation=operation)


def gpu_budget_check(duration_param: str = "duration_hours"):
    """
    Specialized decorator for GPU operations.

    Args:
        duration_param: Parameter name for duration in hours

    Returns:
        Budget-constrained decorator for GPU operations
    """

    def extract_gpu_parameters(*args, **kwargs):
        parameters = {}

        if duration_param in kwargs:
            parameters["duration_hours"] = kwargs[duration_param]

        return parameters

    return budget_constrained(
        service="gpu", operation="usage", parameters_func=extract_gpu_parameters
    )


class BudgetConstraintError(Exception):
    """Exception raised when budget constraints are violated."""

    def __init__(
        self, message: str, service: str, operation: str, estimated_cost: float
    ):
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.estimated_cost = estimated_cost


def enforce_budget_constraint(
    service: str,
    operation: str,
    parameters: Optional[Dict[str, Any]] = None,
    raise_on_violation: bool = True,
) -> bool:
    """
    Enforce budget constraint for an operation.

    Args:
        service: Service name
        operation: Operation name
        parameters: Operation parameters for cost estimation
        raise_on_violation: Whether to raise exception on violation

    Returns:
        True if operation can proceed, False otherwise

    Raises:
        BudgetConstraintError: If raise_on_violation=True and constraint violated
    """
    can_execute, reason, estimates = budget_constraints.can_execute_operation(
        service, operation, parameters
    )

    if not can_execute:
        estimated_cost = estimates[0].estimated_cost if estimates else 0.0

        if raise_on_violation:
            raise BudgetConstraintError(reason, service, operation, estimated_cost)

        logger.warning(f"Budget constraint violation: {reason}")
        return False

    return True


def simulate_operation_cost(
    service: str, operation: str, parameters: Optional[Dict[str, Any]] = None
) -> float:
    """
    Simulate the cost of an operation without executing it.

    Args:
        service: Service name
        operation: Operation name
        parameters: Operation parameters

    Returns:
        Estimated cost in USD
    """
    estimate = budget_constraints.estimate_operation_cost(
        service, operation, parameters
    )
    return estimate.estimated_cost
