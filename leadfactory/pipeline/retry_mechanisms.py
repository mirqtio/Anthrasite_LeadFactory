"""
Retry Mechanisms for Transient Failures in LeadFactory Pipeline.

This module provides intelligent retry logic with exponential backoff, circuit breakers,
and configurable retry policies to handle transient failures gracefully.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Union

from leadfactory.pipeline.error_handling import (
    ErrorCategory,
    PipelineError,
    RetryStrategy,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to prevent thundering herd
    backoff_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_exceptions: list[type] = field(
        default_factory=lambda: [ConnectionError, TimeoutError, OSError]
    )
    retryable_categories: list[ErrorCategory] = field(
        default_factory=lambda: [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.EXTERNAL_API,
        ]
    )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Number of failures before opening circuit
    recovery_timeout: float = 60.0  # Seconds to wait before trying half-open
    success_threshold: int = 3  # Successful calls needed to close circuit
    timeout: float = 30.0  # Request timeout in seconds


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures during retry attempts."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.call_count = 0
        self.success_rate_window: list[bool] = []

    def can_execute(self) -> bool:
        """Check if a call can be executed based on circuit breaker state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        """Record a successful call."""
        self.call_count += 1
        self.success_rate_window.append(True)
        self._trim_window()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker closed after successful recovery")
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record a failed call."""
        self.call_count += 1
        self.success_rate_window.append(False)
        self._trim_window()
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker reopened during half-open test")

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        success_rate = 0.0
        if self.success_rate_window:
            success_rate = sum(self.success_rate_window) / len(self.success_rate_window)

        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "call_count": self.call_count,
            "success_rate": success_rate,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout

    def _trim_window(self, max_size: int = 100):
        """Trim the success rate window to prevent memory growth."""
        if len(self.success_rate_window) > max_size:
            self.success_rate_window = self.success_rate_window[-max_size:]


class RetryManager:
    """Manages retry attempts with configurable strategies and circuit breakers."""

    def __init__(
        self,
        retry_config: RetryConfig,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.retry_config = retry_config
        self.circuit_breaker = (
            CircuitBreaker(circuit_breaker_config) if circuit_breaker_config else None
        )
        self.retry_stats: dict[str, int] = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "circuit_breaker_rejections": 0,
        }

    def is_retryable_error(self, error: Union[Exception, PipelineError]) -> bool:
        """Determine if an error is retryable."""
        if isinstance(error, PipelineError):
            # Check if error category is retryable
            if error.category in self.retry_config.retryable_categories:
                return True
            # Check if retry strategy allows retries
            return error.retry_strategy != RetryStrategy.NONE
        elif isinstance(error, Exception):
            # Check if exception type is retryable
            return any(
                isinstance(error, exc_type)
                for exc_type in self.retry_config.retryable_exceptions
            )
        return False

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt."""
        if self.retry_config.backoff_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (
                self.retry_config.exponential_base ** (attempt - 1)
            )
        elif self.retry_config.backoff_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * attempt
        elif self.retry_config.backoff_strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        else:
            delay = self.retry_config.base_delay

        # Apply maximum delay limit
        delay = min(delay, self.retry_config.max_delay)

        # Add jitter to prevent thundering herd
        if self.retry_config.jitter:
            jitter_amount = delay * 0.1 * random.random()
            delay += jitter_amount

        return delay

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_error = None

        for attempt in range(1, self.retry_config.max_attempts + 1):
            self.retry_stats["total_attempts"] += 1

            # Check circuit breaker
            if self.circuit_breaker and not self.circuit_breaker.can_execute():
                self.retry_stats["circuit_breaker_rejections"] += 1
                raise Exception("Circuit breaker is open - rejecting call")

            try:
                result = func(*args, **kwargs)

                # Record success
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                if attempt > 1:
                    self.retry_stats["successful_retries"] += 1
                    logger.info(f"Function succeeded on attempt {attempt}")

                return result

            except Exception as error:
                last_error = error

                # Record failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Check if error is retryable
                if not self.is_retryable_error(error):
                    logger.warning(f"Non-retryable error encountered: {error}")
                    break

                # Check if we have more attempts
                if attempt >= self.retry_config.max_attempts:
                    logger.error(
                        f"Max retry attempts ({self.retry_config.max_attempts}) exceeded"
                    )
                    break

                # Calculate delay and wait
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt} failed: {error}. Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)

        # All attempts failed
        self.retry_stats["failed_retries"] += 1
        if last_error:
            raise last_error
        else:
            raise Exception("All retry attempts failed")

    async def execute_with_retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an async function with retry logic."""
        last_error = None

        for attempt in range(1, self.retry_config.max_attempts + 1):
            self.retry_stats["total_attempts"] += 1

            # Check circuit breaker
            if self.circuit_breaker and not self.circuit_breaker.can_execute():
                self.retry_stats["circuit_breaker_rejections"] += 1
                raise Exception("Circuit breaker is open - rejecting call")

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Record success
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                if attempt > 1:
                    self.retry_stats["successful_retries"] += 1
                    logger.info(f"Async function succeeded on attempt {attempt}")

                return result

            except Exception as error:
                last_error = error

                # Record failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # Check if error is retryable
                if not self.is_retryable_error(error):
                    logger.warning(f"Non-retryable error encountered: {error}")
                    break

                # Check if we have more attempts
                if attempt >= self.retry_config.max_attempts:
                    logger.error(
                        f"Max retry attempts ({self.retry_config.max_attempts}) exceeded"
                    )
                    break

                # Calculate delay and wait
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Async attempt {attempt} failed: {error}. Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)

        # All attempts failed
        self.retry_stats["failed_retries"] += 1
        if last_error:
            raise last_error
        else:
            raise Exception("All async retry attempts failed")

    def get_stats(self) -> dict[str, Any]:
        """Get retry statistics."""
        stats = self.retry_stats.copy()
        if self.circuit_breaker:
            stats["circuit_breaker"] = self.circuit_breaker.get_stats()
        return stats


def with_retry(
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
):
    """Decorator to add retry logic to functions."""

    def decorator(func: Callable) -> Callable:
        config = retry_config or RetryConfig()
        manager = RetryManager(config, circuit_breaker_config)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return manager.execute_with_retry(func, *args, **kwargs)

        # Attach stats method to wrapper
        wrapper.get_retry_stats = manager.get_stats

        return wrapper

    return decorator


def with_async_retry(
    retry_config: Optional[RetryConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
):
    """Decorator to add retry logic to async functions."""

    def decorator(func: Callable) -> Callable:
        config = retry_config or RetryConfig()
        manager = RetryManager(config, circuit_breaker_config)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.execute_with_retry_async(func, *args, **kwargs)

        # Attach stats method to wrapper
        wrapper.get_retry_stats = manager.get_stats

        return wrapper

    return decorator


class RetryMonitor:
    """Monitor retry attempts and success rates across the pipeline."""

    def __init__(self):
        self.operation_stats: dict[str, dict[str, Any]] = {}
        self.global_stats = {
            "total_operations": 0,
            "operations_with_retries": 0,
            "total_retry_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
        }

    def record_operation(
        self,
        operation_name: str,
        attempts: int,
        success: bool,
        error_type: Optional[str] = None,
    ):
        """Record retry statistics for an operation."""
        if operation_name not in self.operation_stats:
            self.operation_stats[operation_name] = {
                "total_calls": 0,
                "calls_with_retries": 0,
                "total_attempts": 0,
                "successful_retries": 0,
                "failed_retries": 0,
                "error_types": {},
            }

        stats = self.operation_stats[operation_name]
        stats["total_calls"] += 1
        stats["total_attempts"] += attempts

        if attempts > 1:
            stats["calls_with_retries"] += 1
            if success:
                stats["successful_retries"] += 1
            else:
                stats["failed_retries"] += 1

        if error_type:
            if error_type not in stats["error_types"]:
                stats["error_types"][error_type] = 0
            stats["error_types"][error_type] += 1

        # Update global stats
        self.global_stats["total_operations"] += 1
        if attempts > 1:
            self.global_stats["operations_with_retries"] += 1
            self.global_stats["total_retry_attempts"] += attempts - 1
            if success:
                self.global_stats["successful_retries"] += 1
            else:
                self.global_stats["failed_retries"] += 1

    def get_operation_stats(self, operation_name: str) -> Optional[dict[str, Any]]:
        """Get statistics for a specific operation."""
        return self.operation_stats.get(operation_name)

    def get_global_stats(self) -> dict[str, Any]:
        """Get global retry statistics."""
        return self.global_stats.copy()

    def get_summary_report(self) -> dict[str, Any]:
        """Generate a comprehensive retry summary report."""
        total_ops = self.global_stats["total_operations"]
        retry_rate = (
            (self.global_stats["operations_with_retries"] / total_ops * 100)
            if total_ops > 0
            else 0
        )

        successful_retries = self.global_stats["successful_retries"]
        total_retries = (
            self.global_stats["successful_retries"]
            + self.global_stats["failed_retries"]
        )
        retry_success_rate = (
            (successful_retries / total_retries * 100) if total_retries > 0 else 0
        )

        return {
            "summary": {
                "total_operations": total_ops,
                "retry_rate_percent": round(retry_rate, 2),
                "retry_success_rate_percent": round(retry_success_rate, 2),
                "total_retry_attempts": self.global_stats["total_retry_attempts"],
            },
            "global_stats": self.global_stats,
            "operation_breakdown": self.operation_stats,
        }


# Global retry monitor instance
retry_monitor = RetryMonitor()
