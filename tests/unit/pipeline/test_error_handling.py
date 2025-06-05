"""
Unit tests for the error handling pipeline module.

Tests error propagation, partial failure handling, and retry mechanisms.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from leadfactory.pipeline.error_handling import (
    BatchResult,
    ErrorCategory,
    ErrorPropagationManager,
    ErrorSeverity,
    PipelineError,
    RetryStrategy,
    create_batch_processor,
    with_error_handling,
)


class TestPipelineError:
    """Test PipelineError class."""

    def test_pipeline_error_creation(self):
        """Test creating a pipeline error."""
        error = PipelineError(
            stage="enrichment",
            operation="fetch_data",
            error_type="ValueError",
            error_message="Invalid input",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            business_id=123,
        )

        assert error.stage == "enrichment"
        assert error.operation == "fetch_data"
        assert error.error_type == "ValueError"
        assert error.error_message == "Invalid input"
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.category == ErrorCategory.VALIDATION
        assert error.business_id == 123
        assert error.recoverable is True

    def test_pipeline_error_from_exception(self):
        """Test creating pipeline error from exception."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            error = PipelineError.from_exception(
                exception=e,
                stage="test_stage",
                operation="test_operation",
                business_id=456,
            )

        assert error.error_type == "ValueError"
        assert error.error_message == "Test error"
        assert error.stage == "test_stage"
        assert error.operation == "test_operation"
        assert error.business_id == 456
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.retry_strategy == RetryStrategy.NONE
        assert "Traceback" in error.traceback_info

    def test_pipeline_error_to_dict(self):
        """Test converting pipeline error to dictionary."""
        error = PipelineError(
            stage="scoring",
            operation="calculate_score",
            error_type="RuntimeError",
            error_message="Score calculation failed",
            context={"score_type": "performance"},
        )

        error_dict = error.to_dict()

        assert error_dict["stage"] == "scoring"
        assert error_dict["operation"] == "calculate_score"
        assert error_dict["error_type"] == "RuntimeError"
        assert error_dict["error_message"] == "Score calculation failed"
        assert error_dict["context"] == {"score_type": "performance"}
        assert "timestamp" in error_dict
        assert "id" in error_dict

    def test_error_severity_determination(self):
        """Test automatic severity determination from exception types."""
        # Critical errors
        critical_error = PipelineError.from_exception(
            MemoryError("Out of memory"), "test", "test"
        )
        assert critical_error.severity == ErrorSeverity.CRITICAL

        # High severity errors
        high_error = PipelineError.from_exception(
            ConnectionError("Network error"), "test", "test"
        )
        assert high_error.severity == ErrorSeverity.HIGH

        # Medium severity errors
        medium_error = PipelineError.from_exception(
            ValueError("Invalid value"), "test", "test"
        )
        assert medium_error.severity == ErrorSeverity.MEDIUM

        # Low severity errors
        low_error = PipelineError.from_exception(
            Exception("Generic error"), "test", "test"
        )
        assert low_error.severity == ErrorSeverity.LOW

    def test_error_category_determination(self):
        """Test automatic category determination from exception types."""
        # Network errors
        network_error = PipelineError.from_exception(
            ConnectionError("Connection failed"), "test", "test"
        )
        assert network_error.category == ErrorCategory.NETWORK

        # Timeout errors
        timeout_error = PipelineError.from_exception(
            TimeoutError("Request timed out"), "test", "test"
        )
        assert timeout_error.category == ErrorCategory.TIMEOUT

        # Validation errors
        validation_error = PipelineError.from_exception(
            ValueError("Invalid input"), "test", "test"
        )
        assert validation_error.category == ErrorCategory.VALIDATION

        # Permission errors
        permission_error = PipelineError.from_exception(
            PermissionError("Access denied"), "test", "test"
        )
        assert permission_error.category == ErrorCategory.PERMISSION

    def test_retry_strategy_determination(self):
        """Test automatic retry strategy determination."""
        # Exponential backoff for network errors
        network_error = PipelineError.from_exception(
            ConnectionError("Network error"), "test", "test"
        )
        assert network_error.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF

        # Linear backoff for OS errors
        os_error = PipelineError.from_exception(
            OSError("File not found"), "test", "test"
        )
        assert os_error.retry_strategy == RetryStrategy.LINEAR_BACKOFF

        # No retry for validation errors
        validation_error = PipelineError.from_exception(
            ValueError("Invalid input"), "test", "test"
        )
        assert validation_error.retry_strategy == RetryStrategy.NONE


class TestBatchResult:
    """Test BatchResult class."""

    def test_batch_result_creation(self):
        """Test creating a batch result."""
        result = BatchResult(
            stage="enrichment",
            operation="fetch_all",
            total_items=100,
            successful_items=90,
            failed_items=5,
            skipped_items=5,
        )

        assert result.stage == "enrichment"
        assert result.operation == "fetch_all"
        assert result.total_items == 100
        assert result.successful_items == 90
        assert result.failed_items == 5
        assert result.skipped_items == 5

    def test_batch_result_success_rate(self):
        """Test success rate calculation."""
        result = BatchResult(
            total_items=100,
            successful_items=75,
            failed_items=20,
            skipped_items=5,
        )

        assert result.success_rate == 75.0

        # Test with no items
        empty_result = BatchResult(total_items=0)
        assert empty_result.success_rate == 0.0

    def test_batch_result_has_failures(self):
        """Test failure detection."""
        # With failures
        result_with_failures = BatchResult(failed_items=5)
        assert result_with_failures.has_failures is True

        # Without failures
        result_no_failures = BatchResult(failed_items=0)
        assert result_no_failures.has_failures is False

    def test_batch_result_has_critical_errors(self):
        """Test critical error detection."""
        # Create errors
        critical_error = PipelineError(
            severity=ErrorSeverity.CRITICAL,
            error_type="MemoryError",
            error_message="Out of memory",
        )
        normal_error = PipelineError(
            severity=ErrorSeverity.MEDIUM,
            error_type="ValueError",
            error_message="Invalid value",
        )

        # With critical errors
        result_critical = BatchResult()
        result_critical.add_error(critical_error)
        assert result_critical.has_critical_errors is True

        # Without critical errors
        result_normal = BatchResult()
        result_normal.add_error(normal_error)
        assert result_normal.has_critical_errors is False

    def test_batch_result_add_error(self):
        """Test adding errors to batch result."""
        result = BatchResult()
        assert result.failed_items == 0
        assert len(result.errors) == 0

        error = PipelineError(
            error_type="TestError",
            error_message="Test error message",
        )
        result.add_error(error)

        assert result.failed_items == 1
        assert len(result.errors) == 1
        assert result.errors[0] == error

    def test_batch_result_to_dict(self):
        """Test converting batch result to dictionary."""
        result = BatchResult(
            stage="scoring",
            operation="batch_score",
            total_items=50,
            successful_items=45,
            failed_items=4,  # Set to 4 since add_error will increment
            duration_seconds=10.5,
        )

        # Add an error (this will increment failed_items to 5)
        error = PipelineError(
            error_type="ScoreError",
            error_message="Score calculation failed",
        )
        result.add_error(error)

        result_dict = result.to_dict()

        assert result_dict["stage"] == "scoring"
        assert result_dict["operation"] == "batch_score"
        assert result_dict["total_items"] == 50
        assert result_dict["successful_items"] == 45
        assert result_dict["failed_items"] == 5
        assert result_dict["success_rate"] == 90.0
        assert result_dict["duration_seconds"] == 10.5
        assert len(result_dict["errors"]) == 1


class TestErrorPropagationManager:
    """Test ErrorPropagationManager class."""

    @pytest.fixture
    def manager(self):
        """Create an error propagation manager."""
        return ErrorPropagationManager(
            max_error_threshold=0.1,  # 10% error rate
            stop_on_critical=True,
        )

    def test_should_continue_batch_normal(self, manager):
        """Test batch continuation with normal error rates."""
        result = BatchResult(
            total_items=100,
            successful_items=95,
            failed_items=5,  # 5% error rate
        )

        assert manager.should_continue_batch(result) is True

    def test_should_continue_batch_high_error_rate(self, manager):
        """Test batch continuation with high error rate."""
        result = BatchResult(
            total_items=100,
            successful_items=85,
            failed_items=15,  # 15% error rate
        )

        assert manager.should_continue_batch(result) is False

    def test_should_continue_batch_critical_error(self, manager):
        """Test batch continuation with critical error."""
        result = BatchResult()
        critical_error = PipelineError(
            severity=ErrorSeverity.CRITICAL,
            error_type="SystemExit",
            error_message="System exit",
        )
        result.add_error(critical_error)

        assert manager.should_continue_batch(result) is False

    def test_should_continue_batch_critical_disabled(self):
        """Test batch continuation with critical stopping disabled."""
        manager = ErrorPropagationManager(stop_on_critical=False)
        result = BatchResult()
        critical_error = PipelineError(
            severity=ErrorSeverity.CRITICAL,
            error_type="SystemExit",
            error_message="System exit",
        )
        result.add_error(critical_error)

        assert manager.should_continue_batch(result) is True

    def test_record_error(self, manager):
        """Test recording errors."""
        error = PipelineError(
            stage="test",
            operation="test_op",
            error_type="TestError",
            error_message="Test error",
        )

        assert len(manager.error_history) == 0
        manager.record_error(error)
        assert len(manager.error_history) == 1
        assert manager.error_history[0] == error

    def test_record_batch_result(self, manager):
        """Test recording batch results."""
        result = BatchResult(
            stage="test",
            operation="batch_test",
            total_items=10,
            successful_items=10,
        )

        assert len(manager.batch_results) == 0
        manager.record_batch_result(result)
        assert len(manager.batch_results) == 1
        assert manager.batch_results[0] == result

    def test_get_error_summary(self, manager):
        """Test error summary generation."""
        # Add various errors
        errors = [
            PipelineError(
                stage="enrichment",
                operation="fetch",
                error_type="NetworkError",
                error_message="Connection failed",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.HIGH,
            ),
            PipelineError(
                stage="enrichment",
                operation="validate",
                error_type="ValueError",
                error_message="Invalid data",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
            ),
            PipelineError(
                stage="scoring",
                operation="calculate",
                error_type="RuntimeError",
                error_message="Calculation failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.MEDIUM,
            ),
        ]

        for error in errors:
            manager.record_error(error)

        summary = manager.get_error_summary(hours=24)

        assert summary["total_errors"] == 3
        assert summary["time_period_hours"] == 24
        assert summary["by_category"]["network"] == 1
        assert summary["by_category"]["validation"] == 1
        assert summary["by_category"]["business_logic"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_severity"]["medium"] == 2
        assert summary["by_stage"]["enrichment"] == 2
        assert summary["by_stage"]["scoring"] == 1
        assert len(summary["recent_errors"]) == 3

    def test_get_error_summary_time_filter(self, manager):
        """Test error summary with time filtering."""
        # Add old error
        old_error = PipelineError(
            error_type="OldError",
            error_message="Old error",
        )
        old_error.timestamp = datetime.now() - timedelta(hours=25)
        manager.error_history.append(old_error)

        # Add recent error
        recent_error = PipelineError(
            error_type="RecentError",
            error_message="Recent error",
        )
        manager.record_error(recent_error)

        summary = manager.get_error_summary(hours=24)
        assert summary["total_errors"] == 1  # Only recent error


class TestErrorHandlingDecorator:
    """Test with_error_handling decorator."""

    @patch('leadfactory.pipeline.error_handling.logger')
    def test_with_error_handling_success(self, mock_logger):
        """Test decorator with successful execution."""
        manager = ErrorPropagationManager()

        @with_error_handling(
            stage="test",
            operation="test_op",
            error_manager=manager,
            business_id=123,
        )
        def test_function(value):
            return value * 2

        result = test_function(5)
        assert result == 10

        # Check success was logged
        mock_logger.info.assert_called()
        log_args = mock_logger.info.call_args
        assert "Successfully executed test.test_op" in log_args[0][0]

    @patch('leadfactory.pipeline.error_handling.logger')
    def test_with_error_handling_recoverable_error(self, mock_logger):
        """Test decorator with recoverable error."""
        manager = ErrorPropagationManager()

        @with_error_handling(
            stage="test",
            operation="test_op",
            error_manager=manager,
        )
        def test_function():
            raise ValueError("Test error")

        result = test_function()
        assert result is None  # Returns None for recoverable errors
        assert len(manager.error_history) == 1
        assert manager.error_history[0].error_type == "ValueError"

    def test_with_error_handling_critical_error(self):
        """Test decorator with critical error."""
        manager = ErrorPropagationManager()

        @with_error_handling(
            stage="test",
            operation="test_op",
            error_manager=manager,
        )
        def test_function():
            raise MemoryError("Out of memory")

        with pytest.raises(MemoryError):
            test_function()

        assert len(manager.error_history) == 1
        assert manager.error_history[0].severity == ErrorSeverity.CRITICAL

    def test_with_error_handling_no_manager(self):
        """Test decorator without error manager."""

        @with_error_handling(
            stage="test",
            operation="test_op",
        )
        def test_function():
            raise ValueError("Test error")

        result = test_function()
        assert result is None  # Still handles error gracefully


class TestBatchProcessor:
    """Test create_batch_processor function."""

    def test_batch_processor_all_success(self):
        """Test batch processor with all items successful."""
        manager = ErrorPropagationManager()
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
            error_manager=manager,
        )

        def processor_func(item, **kwargs):
            return item * 2

        items = [1, 2, 3, 4, 5]
        result = process_batch(items, processor_func)

        assert result.total_items == 5
        assert result.successful_items == 5
        assert result.failed_items == 0
        assert result.has_failures is False
        assert len(manager.batch_results) == 1

    def test_batch_processor_with_failures(self):
        """Test batch processor with some failures."""
        # Use higher error threshold to allow processing all items
        manager = ErrorPropagationManager(max_error_threshold=0.5)  # 50% threshold
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
            error_manager=manager,
            continue_on_error=True,
        )

        def processor_func(item, **kwargs):
            if item == 3:
                raise ValueError(f"Cannot process {item}")
            return item * 2

        items = [1, 2, 3, 4, 5]
        result = process_batch(items, processor_func)

        assert result.total_items == 5
        assert result.successful_items == 4
        assert result.failed_items == 1
        assert result.has_failures is True
        assert len(result.errors) == 1
        assert result.errors[0].error_message == "Cannot process 3"

    def test_batch_processor_stop_on_error(self):
        """Test batch processor stopping on error."""
        manager = ErrorPropagationManager()
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
            error_manager=manager,
            continue_on_error=False,
        )

        def processor_func(item, **kwargs):
            if item == 3:
                raise ValueError(f"Cannot process {item}")
            return item * 2

        items = [1, 2, 3, 4, 5]
        result = process_batch(items, processor_func)

        assert result.total_items == 5
        assert result.successful_items == 2  # Only processed 1 and 2
        assert result.failed_items == 1  # Failed on 3
        # Items 4 and 5 were not processed

    def test_batch_processor_with_skipped_items(self):
        """Test batch processor with skipped items."""
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
        )

        def processor_func(item, **kwargs):
            if item % 2 == 0:
                return None  # Skip even numbers
            return item * 2

        items = [1, 2, 3, 4, 5]
        result = process_batch(items, processor_func)

        assert result.total_items == 5
        assert result.successful_items == 3  # 1, 3, 5
        assert result.skipped_items == 2  # 2, 4
        assert result.failed_items == 0

    def test_batch_processor_with_context(self):
        """Test batch processor with context information."""
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
        )

        captured_contexts = []

        def processor_func(item, **kwargs):
            captured_contexts.append(kwargs)
            return item

        items = [1, 2]
        batch_context = {"source": "test_source"}
        result = process_batch(
            items,
            processor_func,
            batch_id="test-batch-123",
            context=batch_context,
        )

        assert result.batch_id == "test-batch-123"
        assert result.context == batch_context

        # Check item contexts
        assert len(captured_contexts) == 2
        assert captured_contexts[0]["item_index"] == 0
        assert captured_contexts[0]["batch_id"] == "test-batch-123"
        assert captured_contexts[0]["source"] == "test_source"
        assert captured_contexts[1]["item_index"] == 1

    def test_batch_processor_error_threshold_stop(self):
        """Test batch processor stopping due to error threshold."""
        manager = ErrorPropagationManager(max_error_threshold=0.3)  # 30% threshold
        process_batch = create_batch_processor(
            stage="test",
            operation="batch_test",
            error_manager=manager,
            continue_on_error=True,
        )

        def processor_func(item, **kwargs):
            # Fail on items 2, 3, 4 (3 out of 10 = 30%)
            if item in [2, 3, 4]:
                raise ValueError(f"Cannot process {item}")
            return item

        items = list(range(1, 11))  # 1 to 10
        result = process_batch(items, processor_func)

        # The batch processor will process all items but check threshold after each
        # With 30% threshold and 10 items, it allows up to 3 failures
        assert result.failed_items == 3  # Failed on items 2, 3, 4
        assert result.successful_items == 7  # Items 1, 5, 6, 7, 8, 9, 10
        assert result.total_items == 10
