"""
Throttling Decorators
--------------------
This module provides decorators that integrate with the throttling service
to enforce budget limits and rate limiting on function calls.
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from leadfactory.cost.throttling_service import (
    ThrottlingAction,
    ThrottlingStrategy,
    apply_throttling_decision,
    apply_throttling_decision_async,
    get_throttling_service,
    should_throttle_request,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ThrottlingError(Exception):
    """Exception raised when a request is throttled."""

    def __init__(self, message: str, decision: Any = None):
        super().__init__(message)
        self.decision = decision


def throttled(
    service: str,
    model: str,
    endpoint: str,
    cost_estimator: Optional[Callable] = None,
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    fallback_value: Any = None,
    fallback_function: Optional[Callable] = None,
    raise_on_throttle: bool = False,
    auto_downgrade: bool = True,
):
    """
    Decorator that applies throttling to a function based on budget constraints.

    Args:
        service: Service name (e.g., 'openai', 'semrush')
        model: Model name (e.g., 'gpt-4o', 'domain-overview')
        endpoint: Endpoint name (e.g., 'chat', 'completions')
        cost_estimator: Function to estimate cost from function args/kwargs
        strategy: Throttling strategy to use
        fallback_value: Value to return if request is throttled
        fallback_function: Function to call if request is throttled
        raise_on_throttle: Whether to raise exception when throttled
        auto_downgrade: Whether to automatically use alternative models

    Returns:
        Decorated function with throttling applied
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Estimate cost
            estimated_cost = 0.0
            if cost_estimator:
                try:
                    estimated_cost = cost_estimator(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cost estimation failed: {e}")

            # Get throttling decision
            throttling_service = get_throttling_service()
            decision = throttling_service.should_throttle(
                service, model, endpoint, estimated_cost, strategy
            )

            # Handle model downgrade
            actual_model = model
            if decision.action == ThrottlingAction.DOWNGRADE and auto_downgrade:
                if decision.alternative_model:
                    actual_model = decision.alternative_model
                    logger.info(f"Auto-downgrading from {model} to {actual_model}")

                    # Update kwargs if model is passed as parameter
                    if "model" in kwargs:
                        kwargs["model"] = actual_model
                    elif len(args) > 0 and hasattr(args[0], "model"):
                        # Handle case where model is an attribute of first argument
                        args[0].model = actual_model

            # Apply throttling decision
            should_proceed = apply_throttling_decision(decision)

            if not should_proceed:
                if raise_on_throttle:
                    raise ThrottlingError(
                        f"Request throttled: {decision.reason}", decision
                    )

                # Return fallback
                if fallback_function:
                    return fallback_function(*args, **kwargs)
                else:
                    return fallback_value

            # Record request start
            throttling_service.record_request_start(service, actual_model, endpoint)

            try:
                # Execute the function
                result = func(*args, **kwargs)
                return result
            finally:
                # Record request end
                throttling_service.record_request_end(service, actual_model, endpoint)

        return wrapper

    return decorator


def async_throttled(
    service: str,
    model: str,
    endpoint: str,
    cost_estimator: Optional[Callable] = None,
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    fallback_value: Any = None,
    fallback_function: Optional[Callable] = None,
    raise_on_throttle: bool = False,
    auto_downgrade: bool = True,
):
    """
    Async version of the throttled decorator.

    Args:
        service: Service name (e.g., 'openai', 'semrush')
        model: Model name (e.g., 'gpt-4o', 'domain-overview')
        endpoint: Endpoint name (e.g., 'chat', 'completions')
        cost_estimator: Function to estimate cost from function args/kwargs
        strategy: Throttling strategy to use
        fallback_value: Value to return if request is throttled
        fallback_function: Async function to call if request is throttled
        raise_on_throttle: Whether to raise exception when throttled
        auto_downgrade: Whether to automatically use alternative models

    Returns:
        Decorated async function with throttling applied
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Estimate cost
            estimated_cost = 0.0
            if cost_estimator:
                try:
                    estimated_cost = cost_estimator(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cost estimation failed: {e}")

            # Get throttling decision
            throttling_service = get_throttling_service()
            decision = throttling_service.should_throttle(
                service, model, endpoint, estimated_cost, strategy
            )

            # Handle model downgrade
            actual_model = model
            if decision.action == ThrottlingAction.DOWNGRADE and auto_downgrade:
                if decision.alternative_model:
                    actual_model = decision.alternative_model
                    logger.info(f"Auto-downgrading from {model} to {actual_model}")

                    # Update kwargs if model is passed as parameter
                    if "model" in kwargs:
                        kwargs["model"] = actual_model
                    elif len(args) > 0 and hasattr(args[0], "model"):
                        # Handle case where model is an attribute of first argument
                        args[0].model = actual_model

            # Apply throttling decision (async)
            should_proceed = await apply_throttling_decision_async(decision)

            if not should_proceed:
                if raise_on_throttle:
                    raise ThrottlingError(
                        f"Request throttled: {decision.reason}", decision
                    )

                # Return fallback
                if fallback_function:
                    if asyncio.iscoroutinefunction(fallback_function):
                        return await fallback_function(*args, **kwargs)
                    else:
                        return fallback_function(*args, **kwargs)
                else:
                    return fallback_value

            # Record request start
            throttling_service.record_request_start(service, actual_model, endpoint)

            try:
                # Execute the async function
                result = await func(*args, **kwargs)
                return result
            finally:
                # Record request end
                throttling_service.record_request_end(service, actual_model, endpoint)

        return wrapper

    return decorator


# Specialized decorators for common services


def openai_throttled(
    model: str = "gpt-4o",
    endpoint: str = "chat",
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    auto_downgrade: bool = True,
    **kwargs,
):
    """
    Specialized throttling decorator for OpenAI operations.

    Args:
        model: OpenAI model name
        endpoint: OpenAI endpoint name
        strategy: Throttling strategy
        auto_downgrade: Whether to auto-downgrade to cheaper models
        **kwargs: Additional arguments passed to throttled decorator
    """

    def openai_cost_estimator(*args, **func_kwargs):
        """Estimate OpenAI API cost based on tokens or prompt length."""
        # Base cost per 1K tokens (approximate)
        cost_per_1k_tokens = {
            "gpt-4o": 0.005,
            "gpt-4o-mini": 0.0005,
            "gpt-3.5-turbo": 0.0015,
            "gpt-4": 0.03,
            "gpt-4-turbo": 0.01,
        }

        base_cost = cost_per_1k_tokens.get(model, 0.005)

        # Try to estimate tokens from various parameters
        tokens = 0

        # Check for explicit token count
        if "max_tokens" in func_kwargs:
            tokens += func_kwargs["max_tokens"]

        # Estimate from prompt length
        if "prompt" in func_kwargs:
            prompt_text = func_kwargs["prompt"]
            if isinstance(prompt_text, str):
                tokens += len(prompt_text.split()) * 1.3  # Rough token estimation

        # Check for messages (chat format)
        if "messages" in func_kwargs:
            messages = func_kwargs["messages"]
            if isinstance(messages, list):
                for message in messages:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str):
                            tokens += len(content.split()) * 1.3

        # Default minimum cost if no tokens estimated
        if tokens == 0:
            tokens = 100  # Assume minimum 100 tokens

        return (tokens / 1000) * base_cost

    return throttled(
        service="openai",
        model=model,
        endpoint=endpoint,
        cost_estimator=openai_cost_estimator,
        strategy=strategy,
        auto_downgrade=auto_downgrade,
        **kwargs,
    )


def async_openai_throttled(
    model: str = "gpt-4o",
    endpoint: str = "chat",
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    auto_downgrade: bool = True,
    **kwargs,
):
    """
    Async version of OpenAI throttling decorator.
    """

    def openai_cost_estimator(*args, **func_kwargs):
        """Estimate OpenAI API cost based on tokens or prompt length."""
        cost_per_1k_tokens = {
            "gpt-4o": 0.005,
            "gpt-4o-mini": 0.0005,
            "gpt-3.5-turbo": 0.0015,
            "gpt-4": 0.03,
            "gpt-4-turbo": 0.01,
        }

        base_cost = cost_per_1k_tokens.get(model, 0.005)
        tokens = 0

        if "max_tokens" in func_kwargs:
            tokens += func_kwargs["max_tokens"]

        if "prompt" in func_kwargs:
            prompt_text = func_kwargs["prompt"]
            if isinstance(prompt_text, str):
                tokens += len(prompt_text.split()) * 1.3

        if "messages" in func_kwargs:
            messages = func_kwargs["messages"]
            if isinstance(messages, list):
                for message in messages:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str):
                            tokens += len(content.split()) * 1.3

        if tokens == 0:
            tokens = 100

        return (tokens / 1000) * base_cost

    return async_throttled(
        service="openai",
        model=model,
        endpoint=endpoint,
        cost_estimator=openai_cost_estimator,
        strategy=strategy,
        auto_downgrade=auto_downgrade,
        **kwargs,
    )


def semrush_throttled(
    operation: str = "domain-overview",
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    **kwargs,
):
    """
    Specialized throttling decorator for SEMrush operations.

    Args:
        operation: SEMrush operation name
        strategy: Throttling strategy
        **kwargs: Additional arguments passed to throttled decorator
    """

    def semrush_cost_estimator(*args, **func_kwargs):
        """Estimate SEMrush API cost."""
        # Base costs for different operations
        operation_costs = {
            "domain-overview": 0.10,
            "domain-organic": 0.15,
            "domain-adwords": 0.15,
            "keyword-overview": 0.05,
            "keyword-difficulty": 0.08,
        }

        return operation_costs.get(operation, 0.10)

    return throttled(
        service="semrush",
        model=operation,
        endpoint="api",
        cost_estimator=semrush_cost_estimator,
        strategy=strategy,
        auto_downgrade=False,  # SEMrush doesn't have model alternatives
        **kwargs,
    )


def screenshot_throttled(
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE, **kwargs
):
    """
    Specialized throttling decorator for screenshot operations.

    Args:
        strategy: Throttling strategy
        **kwargs: Additional arguments passed to throttled decorator
    """

    def screenshot_cost_estimator(*args, **func_kwargs):
        """Estimate screenshot cost based on dimensions and format."""
        base_cost = 0.01  # Base cost per screenshot

        # Adjust cost based on dimensions
        width = func_kwargs.get("width", 1920)
        height = func_kwargs.get("height", 1080)

        # Higher resolution = higher cost
        pixel_multiplier = (width * height) / (1920 * 1080)

        return base_cost * pixel_multiplier

    return throttled(
        service="screenshot",
        model="browser",
        endpoint="capture",
        cost_estimator=screenshot_cost_estimator,
        strategy=strategy,
        auto_downgrade=False,
        **kwargs,
    )


def gpu_throttled(
    gpu_type: str = "A100",
    strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
    **kwargs,
):
    """
    Specialized throttling decorator for GPU operations.

    Args:
        gpu_type: Type of GPU being used
        strategy: Throttling strategy
        **kwargs: Additional arguments passed to throttled decorator
    """

    def gpu_cost_estimator(*args, **func_kwargs):
        """Estimate GPU cost based on duration and type."""
        # Hourly costs for different GPU types
        gpu_costs_per_hour = {
            "A100": 2.50,
            "V100": 1.50,
            "T4": 0.50,
            "RTX3090": 1.00,
        }

        hourly_cost = gpu_costs_per_hour.get(gpu_type, 1.00)
        duration_hours = func_kwargs.get("duration_hours", 1.0)

        return hourly_cost * duration_hours

    return throttled(
        service="gpu",
        model=gpu_type,
        endpoint="compute",
        cost_estimator=gpu_cost_estimator,
        strategy=strategy,
        auto_downgrade=False,
        **kwargs,
    )


# Context managers for manual throttling control


class ThrottlingContext:
    """Context manager for manual throttling control."""

    def __init__(
        self,
        service: str,
        model: str,
        endpoint: str,
        estimated_cost: float = 0.0,
        strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
        raise_on_throttle: bool = True,
    ):
        self.service = service
        self.model = model
        self.endpoint = endpoint
        self.estimated_cost = estimated_cost
        self.strategy = strategy
        self.raise_on_throttle = raise_on_throttle
        self.throttling_service = get_throttling_service()
        self.decision = None

    def __enter__(self):
        """Enter the throttling context."""
        self.decision = self.throttling_service.should_throttle(
            self.service, self.model, self.endpoint, self.estimated_cost, self.strategy
        )

        should_proceed = apply_throttling_decision(self.decision)

        if not should_proceed and self.raise_on_throttle:
            raise ThrottlingError(
                f"Request throttled: {self.decision.reason}", self.decision
            )

        if should_proceed:
            self.throttling_service.record_request_start(
                self.service, self.model, self.endpoint
            )

        return self.decision

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the throttling context."""
        if self.decision and self.decision.action != ThrottlingAction.REJECT:
            self.throttling_service.record_request_end(
                self.service, self.model, self.endpoint
            )


class AsyncThrottlingContext:
    """Async context manager for manual throttling control."""

    def __init__(
        self,
        service: str,
        model: str,
        endpoint: str,
        estimated_cost: float = 0.0,
        strategy: ThrottlingStrategy = ThrottlingStrategy.ADAPTIVE,
        raise_on_throttle: bool = True,
    ):
        self.service = service
        self.model = model
        self.endpoint = endpoint
        self.estimated_cost = estimated_cost
        self.strategy = strategy
        self.raise_on_throttle = raise_on_throttle
        self.throttling_service = get_throttling_service()
        self.decision = None

    async def __aenter__(self):
        """Enter the async throttling context."""
        self.decision = self.throttling_service.should_throttle(
            self.service, self.model, self.endpoint, self.estimated_cost, self.strategy
        )

        should_proceed = await apply_throttling_decision_async(self.decision)

        if not should_proceed and self.raise_on_throttle:
            raise ThrottlingError(
                f"Request throttled: {self.decision.reason}", self.decision
            )

        if should_proceed:
            self.throttling_service.record_request_start(
                self.service, self.model, self.endpoint
            )

        return self.decision

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async throttling context."""
        if self.decision and self.decision.action != ThrottlingAction.REJECT:
            self.throttling_service.record_request_end(
                self.service, self.model, self.endpoint
            )
