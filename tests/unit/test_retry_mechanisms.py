"""
Unit tests for retry mechanisms module.

Tests retry logic, circuit breakers, and monitoring functionality.
"""

import asyncio
import contextlib
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.pipeline.error_handling import (
    ErrorCategory,
    ErrorSeverity,
    PipelineError,
    RetryStrategy,
)
from leadfactory.pipeline.retry_mechanisms import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    RetryConfig,
    RetryManager,
    RetryMonitor,
    retry_monitor,
    with_async_retry,
    with_retry,
)


class TestRetryConfig(unittest.TestCase):
    """Test retry configuration."""

    def test_default_config(self):
        """Test default retry configuration values."""
        config = RetryConfig()

        self.assertEqual(config.max_attempts, 3)
        self.assertEqual(config.base_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertEqual(config.exponential_base, 2.0)
        self.assertTrue(config.jitter)
        self.assertEqual(config.backoff_strategy, RetryStrategy.EXPONENTIAL_BACKOFF)
        self.assertIn(ConnectionError, config.retryable_exceptions)
        self.assertIn(ErrorCategory.NETWORK, config.retryable_categories)

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False,
            backoff_strategy=RetryStrategy.LINEAR_BACKOFF,
        )

        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.base_delay, 2.0)
        self.assertEqual(config.max_delay, 120.0)
        self.assertEqual(config.exponential_base, 3.0)
        self.assertFalse(config.jitter)
        self.assertEqual(config.backoff_strategy, RetryStrategy.LINEAR_BACKOFF)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = CircuitBreakerConfig(
            failure_threshold=3, recovery_timeout=5.0, success_threshold=2, timeout=10.0
        )
        self.circuit_breaker = CircuitBreaker(self.config)

    def test_initial_state(self):
        """Test circuit breaker initial state."""
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)
        self.assertEqual(self.circuit_breaker.success_count, 0)
        self.assertTrue(self.circuit_breaker.can_execute())

    def test_failure_threshold_opens_circuit(self):
        """Test that reaching failure threshold opens the circuit."""
        # Record failures up to threshold
        for i in range(self.config.failure_threshold):
            self.circuit_breaker.record_failure()
            if i < self.config.failure_threshold - 1:
                self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)

        # Circuit should now be open
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
        self.assertFalse(self.circuit_breaker.can_execute())

    def test_success_resets_failure_count(self):
        """Test that successes reduce failure count."""
        # Record some failures
        self.circuit_breaker.record_failure()
        self.circuit_breaker.record_failure()
        self.assertEqual(self.circuit_breaker.failure_count, 2)

        # Record success
        self.circuit_breaker.record_success()
        self.assertEqual(self.circuit_breaker.failure_count, 1)
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)

    def test_half_open_transition(self):
        """Test transition to half-open state after recovery timeout."""
        # Open the circuit
        for _ in range(self.config.failure_threshold):
            self.circuit_breaker.record_failure()
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)

        # Simulate time passage
        self.circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=10)

        # Should allow execution and transition to half-open
        self.assertTrue(self.circuit_breaker.can_execute())
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.HALF_OPEN)

    def test_half_open_to_closed_recovery(self):
        """Test recovery from half-open to closed state."""
        # Set to half-open state
        self.circuit_breaker.state = CircuitBreakerState.HALF_OPEN

        # Record enough successes to close circuit
        for _ in range(self.config.success_threshold):
            self.circuit_breaker.record_success()

        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.failure_count, 0)

    def test_half_open_to_open_on_failure(self):
        """Test that failure in half-open state reopens circuit."""
        # Set to half-open state
        self.circuit_breaker.state = CircuitBreakerState.HALF_OPEN

        # Record failure
        self.circuit_breaker.record_failure()

        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)

    def test_circuit_breaker_stats(self):
        """Test circuit breaker statistics."""
        self.circuit_breaker.record_success()
        self.circuit_breaker.record_failure()

        stats = self.circuit_breaker.get_stats()

        self.assertEqual(stats["state"], CircuitBreakerState.CLOSED.value)
        self.assertEqual(stats["failure_count"], 1)
        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["call_count"], 2)
        self.assertEqual(stats["success_rate"], 0.5)


class TestRetryManager(unittest.TestCase):
    """Test retry manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.retry_config = RetryConfig(max_attempts=3, base_delay=0.1)
        self.circuit_config = CircuitBreakerConfig(failure_threshold=2)
        self.retry_manager = RetryManager(self.retry_config, self.circuit_config)

    def test_retryable_error_detection(self):
        """Test detection of retryable errors."""
        # Test with retryable exception
        self.assertTrue(
            self.retry_manager.is_retryable_error(ConnectionError("Network error"))
        )
        self.assertTrue(self.retry_manager.is_retryable_error(TimeoutError("Timeout")))

        # Test with non-retryable exception
        self.assertFalse(
            self.retry_manager.is_retryable_error(ValueError("Invalid value"))
        )

        # Test with PipelineError
        retryable_error = PipelineError(
            category=ErrorCategory.NETWORK,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        self.assertTrue(self.retry_manager.is_retryable_error(retryable_error))

        non_retryable_error = PipelineError(
            category=ErrorCategory.VALIDATION, retry_strategy=RetryStrategy.NONE
        )
        self.assertFalse(self.retry_manager.is_retryable_error(non_retryable_error))

    def test_delay_calculation(self):
        """Test retry delay calculation."""
        # Test exponential backoff
        self.retry_manager.retry_config.jitter = (
            False  # Disable jitter for predictable tests
        )

        delay1 = self.retry_manager.calculate_delay(1)
        delay2 = self.retry_manager.calculate_delay(2)
        delay3 = self.retry_manager.calculate_delay(3)

        self.assertEqual(delay1, 0.1)  # base_delay * 2^0
        self.assertEqual(delay2, 0.2)  # base_delay * 2^1
        self.assertEqual(delay3, 0.4)  # base_delay * 2^2

        # Test linear backoff
        self.retry_manager.retry_config.backoff_strategy = RetryStrategy.LINEAR_BACKOFF

        delay1 = self.retry_manager.calculate_delay(1)
        delay2 = self.retry_manager.calculate_delay(2)
        delay3 = self.retry_manager.calculate_delay(3)

        self.assertEqual(delay1, 0.1)  # base_delay * 1
        self.assertEqual(delay2, 0.2)  # base_delay * 2
        self.assertEqual(delay3, 0.3)  # base_delay * 3

    def test_successful_execution_no_retry(self):
        """Test successful execution without retries."""
        mock_func = Mock(return_value="success")

        result = self.retry_manager.execute_with_retry(
            mock_func, "arg1", kwarg1="value1"
        )

        self.assertEqual(result, "success")
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        self.assertEqual(self.retry_manager.retry_stats["total_attempts"], 1)
        self.assertEqual(self.retry_manager.retry_stats["successful_retries"], 0)

    def test_retry_on_transient_failure(self):
        """Test retry behavior on transient failures."""
        mock_func = Mock(side_effect=[ConnectionError("Network error"), "success"])

        result = self.retry_manager.execute_with_retry(mock_func)

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)
        self.assertEqual(self.retry_manager.retry_stats["total_attempts"], 2)
        self.assertEqual(self.retry_manager.retry_stats["successful_retries"], 1)

    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        mock_func = Mock(side_effect=ConnectionError("Persistent network error"))

        with self.assertRaises(ConnectionError):
            self.retry_manager.execute_with_retry(mock_func)

        self.assertEqual(mock_func.call_count, 3)  # max_attempts
        self.assertEqual(self.retry_manager.retry_stats["total_attempts"], 3)
        self.assertEqual(self.retry_manager.retry_stats["failed_retries"], 1)

    def test_non_retryable_error_no_retry(self):
        """Test that non-retryable errors are not retried."""
        mock_func = Mock(side_effect=ValueError("Invalid input"))

        with self.assertRaises(ValueError):
            self.retry_manager.execute_with_retry(mock_func)

        self.assertEqual(mock_func.call_count, 1)  # No retries
        self.assertEqual(self.retry_manager.retry_stats["total_attempts"], 1)
        self.assertEqual(self.retry_manager.retry_stats["failed_retries"], 1)

    def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker."""
        mock_func = Mock(side_effect=ConnectionError("Network error"))

        # Trigger circuit breaker opening
        for _ in range(2):  # failure_threshold = 2
            with contextlib.suppress(ConnectionError):
                self.retry_manager.execute_with_retry(mock_func)

        # Circuit should be open, next call should be rejected
        with self.assertRaises(Exception) as context:
            self.retry_manager.execute_with_retry(mock_func)

        self.assertIn("Circuit breaker is open", str(context.exception))
        self.assertGreater(
            self.retry_manager.retry_stats["circuit_breaker_rejections"], 0
        )

    @patch("time.sleep")
    def test_retry_timing(self, mock_sleep):
        """Test that retry delays are applied correctly."""
        mock_func = Mock(side_effect=[ConnectionError("Error"), "success"])

        self.retry_manager.execute_with_retry(mock_func)

        # Should have slept once between retries
        mock_sleep.assert_called_once()
        self.assertGreater(mock_sleep.call_args[0][0], 0)  # Delay should be > 0


class TestAsyncRetryManager(unittest.TestCase):
    """Test async retry functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
        self.retry_manager = RetryManager(self.retry_config)

    async def test_async_successful_execution(self):
        """Test successful async execution without retries."""

        async def mock_async_func():
            return "async_success"

        result = await self.retry_manager.execute_with_retry_async(mock_async_func)
        self.assertEqual(result, "async_success")

    async def test_async_retry_on_failure(self):
        """Test async retry behavior on failures."""
        call_count = 0

        async def mock_async_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            return "async_success"

        result = await self.retry_manager.execute_with_retry_async(mock_async_func)

        self.assertEqual(result, "async_success")
        self.assertEqual(call_count, 2)
        self.assertEqual(self.retry_manager.retry_stats["successful_retries"], 1)


class TestRetryDecorators(unittest.TestCase):
    """Test retry decorators."""

    def test_sync_retry_decorator(self):
        """Test synchronous retry decorator."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, base_delay=0.01))
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            return "decorated_success"

        result = test_func()

        self.assertEqual(result, "decorated_success")
        self.assertEqual(call_count, 2)

        # Check stats are available
        stats = test_func.get_retry_stats()
        self.assertIn("successful_retries", stats)

    async def test_async_retry_decorator(self):
        """Test asynchronous retry decorator."""
        call_count = 0

        @with_async_retry(RetryConfig(max_attempts=3, base_delay=0.01))
        async def test_async_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            return "async_decorated_success"

        result = await test_async_func()

        self.assertEqual(result, "async_decorated_success")
        self.assertEqual(call_count, 2)

        # Check stats are available
        stats = test_async_func.get_retry_stats()
        self.assertIn("successful_retries", stats)


class TestRetryMonitor(unittest.TestCase):
    """Test retry monitoring functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.monitor = RetryMonitor()

    def test_record_operation_success(self):
        """Test recording successful operation."""
        self.monitor.record_operation("test_op", attempts=1, success=True)

        stats = self.monitor.get_operation_stats("test_op")
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["calls_with_retries"], 0)
        self.assertEqual(stats["successful_retries"], 0)

        global_stats = self.monitor.get_global_stats()
        self.assertEqual(global_stats["total_operations"], 1)
        self.assertEqual(global_stats["operations_with_retries"], 0)

    def test_record_operation_with_retries(self):
        """Test recording operation with retries."""
        self.monitor.record_operation(
            "test_op", attempts=3, success=True, error_type="ConnectionError"
        )

        stats = self.monitor.get_operation_stats("test_op")
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["calls_with_retries"], 1)
        self.assertEqual(stats["successful_retries"], 1)
        self.assertEqual(stats["error_types"]["ConnectionError"], 1)

        global_stats = self.monitor.get_global_stats()
        self.assertEqual(global_stats["total_operations"], 1)
        self.assertEqual(global_stats["operations_with_retries"], 1)
        self.assertEqual(global_stats["total_retry_attempts"], 2)  # attempts - 1
        self.assertEqual(global_stats["successful_retries"], 1)

    def test_record_operation_failed_retries(self):
        """Test recording operation with failed retries."""
        self.monitor.record_operation(
            "test_op", attempts=3, success=False, error_type="TimeoutError"
        )

        stats = self.monitor.get_operation_stats("test_op")
        self.assertEqual(stats["failed_retries"], 1)

        global_stats = self.monitor.get_global_stats()
        self.assertEqual(global_stats["failed_retries"], 1)

    def test_summary_report(self):
        """Test generation of summary report."""
        # Record various operations
        self.monitor.record_operation("op1", attempts=1, success=True)
        self.monitor.record_operation(
            "op2", attempts=3, success=True, error_type="ConnectionError"
        )
        self.monitor.record_operation(
            "op3", attempts=3, success=False, error_type="TimeoutError"
        )

        report = self.monitor.get_summary_report()

        self.assertEqual(report["summary"]["total_operations"], 3)
        self.assertEqual(report["summary"]["retry_rate_percent"], 66.67)  # 2/3 * 100
        self.assertEqual(
            report["summary"]["retry_success_rate_percent"], 50.0
        )  # 1/2 * 100
        self.assertEqual(report["summary"]["total_retry_attempts"], 4)  # (3-1) + (3-1)

        self.assertIn("global_stats", report)
        self.assertIn("operation_breakdown", report)


class TestRetryIntegration(unittest.TestCase):
    """Test integration scenarios."""

    def test_pipeline_error_integration(self):
        """Test integration with PipelineError objects."""
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01)
        manager = RetryManager(retry_config)

        # Create a retryable PipelineError
        error = PipelineError(
            stage="test_stage",
            operation="test_operation",
            error_type="ConnectionError",
            error_message="Network timeout",
            category=ErrorCategory.NETWORK,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            recoverable=True,
        )

        self.assertTrue(manager.is_retryable_error(error))

        # Create a non-retryable PipelineError
        error_non_retryable = PipelineError(
            stage="test_stage",
            operation="test_operation",
            error_type="ValidationError",
            error_message="Invalid data",
            category=ErrorCategory.VALIDATION,
            retry_strategy=RetryStrategy.NONE,
            recoverable=False,
        )

        self.assertFalse(manager.is_retryable_error(error_non_retryable))

    def test_global_retry_monitor(self):
        """Test global retry monitor instance."""
        # Test that global instance exists and works
        retry_monitor.record_operation("global_test", attempts=2, success=True)

        stats = retry_monitor.get_operation_stats("global_test")
        self.assertIsNotNone(stats)
        self.assertEqual(stats["total_calls"], 1)


if __name__ == "__main__":
    # Run async tests
    async def run_async_tests():
        test_instance = TestAsyncRetryManager()
        test_instance.setUp()
        await test_instance.test_async_successful_execution()
        await test_instance.test_async_retry_on_failure()

        decorator_test = TestRetryDecorators()
        await decorator_test.test_async_retry_decorator()

    # Run sync tests
    unittest.main(verbosity=2, exit=False)

    # Run async tests
    asyncio.run(run_async_tests())
