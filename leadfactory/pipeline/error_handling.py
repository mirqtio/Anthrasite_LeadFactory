"""
Error Propagation and Partial Failure Handling for LeadFactory Pipeline.

This module provides comprehensive error handling mechanisms for pipeline operations,
including error propagation, partial failure handling, retry mechanisms, and error aggregation.
"""

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    NETWORK = "network"
    DATABASE = "database"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_API = "external_api"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"


class RetryStrategy(Enum):
    """Retry strategies for different error types."""

    NONE = "none"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    IMMEDIATE = "immediate"
    CUSTOM = "custom"


@dataclass
class PipelineError:
    """Represents an error that occurred during pipeline processing."""

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    stage: str = ""
    operation: str = ""
    error_type: str = ""
    error_message: str = ""
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.BUSINESS_LOGIC
    retry_strategy: RetryStrategy = RetryStrategy.NONE
    context: Dict[str, Any] = field(default_factory=dict)
    traceback_info: Optional[str] = None
    business_id: Optional[int] = None
    batch_id: Optional[str] = None
    recoverable: bool = True
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "stage": self.stage,
            "operation": self.operation,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "retry_strategy": self.retry_strategy.value,
            "context": self.context,
            "traceback_info": self.traceback_info,
            "business_id": self.business_id,
            "batch_id": self.batch_id,
            "recoverable": self.recoverable,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        stage: str,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        business_id: Optional[int] = None,
        batch_id: Optional[str] = None,
    ) -> "PipelineError":
        """Create PipelineError from an exception."""
        error_type = type(exception).__name__
        error_message = str(exception)

        # Determine severity and category based on exception type
        severity = cls._determine_severity(exception)
        category = cls._determine_category(exception)
        retry_strategy = cls._determine_retry_strategy(exception)

        return cls(
            stage=stage,
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            category=category,
            retry_strategy=retry_strategy,
            context=context or {},
            traceback_info=traceback.format_exc(),
            business_id=business_id,
            batch_id=batch_id,
            recoverable=cls._is_recoverable(exception),
        )

    @staticmethod
    def _determine_severity(exception: Exception) -> ErrorSeverity:
        """Determine error severity based on exception type."""
        critical_errors = (SystemExit, KeyboardInterrupt, MemoryError)
        high_errors = (ConnectionError, TimeoutError, PermissionError)
        medium_errors = (ValueError, TypeError, AttributeError)

        if isinstance(exception, critical_errors):
            return ErrorSeverity.CRITICAL
        elif isinstance(exception, high_errors):
            return ErrorSeverity.HIGH
        elif isinstance(exception, medium_errors):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW

    @staticmethod
    def _determine_category(exception: Exception) -> ErrorCategory:
        """Determine error category based on exception type."""
        if isinstance(exception, (ConnectionError, OSError)):
            return ErrorCategory.NETWORK
        elif isinstance(exception, TimeoutError):
            return ErrorCategory.TIMEOUT
        elif isinstance(exception, (ValueError, TypeError)):
            return ErrorCategory.VALIDATION
        elif isinstance(exception, PermissionError):
            return ErrorCategory.PERMISSION
        else:
            return ErrorCategory.BUSINESS_LOGIC

    @staticmethod
    def _determine_retry_strategy(exception: Exception) -> RetryStrategy:
        """Determine retry strategy based on exception type."""
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return RetryStrategy.EXPONENTIAL_BACKOFF
        elif isinstance(exception, (OSError, PermissionError)):
            return RetryStrategy.LINEAR_BACKOFF
        elif isinstance(exception, (ValueError, TypeError)):
            return RetryStrategy.NONE
        else:
            return RetryStrategy.LINEAR_BACKOFF


@dataclass
class BatchResult:
    """Represents the result of a batch operation."""

    batch_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    stage: str = ""
    operation: str = ""
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    errors: List[PipelineError] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def __post_init__(self):
        """Post-initialization to handle any setup."""
        if isinstance(self.errors, list) and len(self.errors) == 0:
            self.errors = []

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.successful_items / self.total_items) * 100

    @property
    def has_failures(self) -> bool:
        """Check if batch has any failures."""
        return self.failed_items > 0

    @property
    def has_critical_errors(self) -> bool:
        """Check if batch has any critical errors."""
        return any(error.severity == ErrorSeverity.CRITICAL for error in self.errors)

    def add_error(self, error: PipelineError) -> None:
        """Add an error to the batch result."""
        self.errors.append(error)
        self.failed_items += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert batch result to dictionary for serialization."""
        return {
            "batch_id": self.batch_id,
            "timestamp": self.timestamp.isoformat(),
            "stage": self.stage,
            "operation": self.operation,
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "success_rate": self.success_rate,
            "errors": [error.to_dict() for error in self.errors],
            "context": self.context,
            "duration_seconds": self.duration_seconds,
        }


class ErrorPropagationManager:
    """Manages error propagation and partial failure handling across pipeline stages."""

    def __init__(self, max_error_threshold: float = 0.1, stop_on_critical: bool = True):
        """
        Initialize error propagation manager.

        Args:
            max_error_threshold: Maximum error rate (0.0-1.0) before stopping batch
            stop_on_critical: Whether to stop processing on critical errors
        """
        self.max_error_threshold = max_error_threshold
        self.stop_on_critical = stop_on_critical
        self.error_history: List[PipelineError] = []
        self.batch_results: List[BatchResult] = []

    def should_continue_batch(self, batch_result: BatchResult) -> bool:
        """
        Determine if batch processing should continue based on error rates.

        Args:
            batch_result: Current batch result

        Returns:
            True if processing should continue, False otherwise
        """
        # Stop on critical errors if configured
        if self.stop_on_critical and batch_result.has_critical_errors:
            logger.error(
                f"Stopping batch {batch_result.batch_id} due to critical errors",
                extra={"batch_id": batch_result.batch_id, "critical_errors": True},
            )
            return False

        # Check error threshold
        if batch_result.total_items > 0:
            error_rate = batch_result.failed_items / batch_result.total_items
            if error_rate > self.max_error_threshold:
                logger.warning(
                    f"Stopping batch {batch_result.batch_id} due to high error rate: {error_rate:.2%}",
                    extra={
                        "batch_id": batch_result.batch_id,
                        "error_rate": error_rate,
                        "threshold": self.max_error_threshold,
                    },
                )
                return False

        return True

    def record_error(self, error: PipelineError) -> None:
        """Record an error in the error history."""
        self.error_history.append(error)
        logger.error(
            f"Pipeline error in {error.stage}.{error.operation}: {error.error_message}",
            extra=error.to_dict(),
        )

    def record_batch_result(self, batch_result: BatchResult) -> None:
        """Record a batch result."""
        self.batch_results.append(batch_result)
        logger.info(
            f"Batch {batch_result.batch_id} completed: {batch_result.successful_items}/{batch_result.total_items} successful",
            extra=batch_result.to_dict(),
        )

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get error summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with error statistics
        """
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        recent_errors = [
            error
            for error in self.error_history
            if error.timestamp.timestamp() > cutoff_time
        ]

        # Group errors by category and severity
        by_category = {}
        by_severity = {}
        by_stage = {}

        for error in recent_errors:
            # By category
            category = error.category.value
            by_category[category] = by_category.get(category, 0) + 1

            # By severity
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # By stage
            stage = error.stage
            by_stage[stage] = by_stage.get(stage, 0) + 1

        return {
            "total_errors": len(recent_errors),
            "time_period_hours": hours,
            "by_category": by_category,
            "by_severity": by_severity,
            "by_stage": by_stage,
            "recent_errors": [
                error.to_dict() for error in recent_errors[-10:]
            ],  # Last 10 errors
        }


def with_error_handling(
    stage: str,
    operation: str,
    error_manager: Optional[ErrorPropagationManager] = None,
    business_id: Optional[int] = None,
    batch_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
):
    """
    Decorator for adding comprehensive error handling to pipeline functions.

    Args:
        stage: Pipeline stage name
        operation: Operation name
        error_manager: Error propagation manager instance
        business_id: Business ID for context
        batch_id: Batch ID for context
        context: Additional context information
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                # Log successful execution
                duration = time.time() - start_time
                logger.info(
                    f"Successfully executed {stage}.{operation}",
                    extra={
                        "stage": stage,
                        "operation": operation,
                        "duration_seconds": duration,
                        "business_id": business_id,
                        "batch_id": batch_id,
                        "outcome": "success",
                    },
                )

                return result

            except Exception as e:
                # Create pipeline error
                pipeline_error = PipelineError.from_exception(
                    exception=e,
                    stage=stage,
                    operation=operation,
                    context=context,
                    business_id=business_id,
                    batch_id=batch_id,
                )

                # Record error if manager provided
                if error_manager:
                    error_manager.record_error(pipeline_error)

                # Log error with full context
                duration = time.time() - start_time
                logger.error(
                    f"Error in {stage}.{operation}: {str(e)}",
                    extra={
                        **pipeline_error.to_dict(),
                        "duration_seconds": duration,
                        "outcome": "failure",
                    },
                )

                # Re-raise if not recoverable or critical
                if (
                    not pipeline_error.recoverable
                    or pipeline_error.severity == ErrorSeverity.CRITICAL
                ):
                    raise

                # Return None for recoverable errors to allow partial processing
                return None

        return wrapper

    return decorator


def create_batch_processor(
    stage: str,
    operation: str,
    error_manager: Optional[ErrorPropagationManager] = None,
    continue_on_error: bool = True,
):
    """
    Create a batch processor with error handling and partial failure support.

    Args:
        stage: Pipeline stage name
        operation: Operation name
        error_manager: Error propagation manager instance
        continue_on_error: Whether to continue processing after individual item failures

    Returns:
        Batch processor function
    """

    def process_batch(
        items: List[Any],
        processor_func: Callable,
        batch_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BatchResult:
        """
        Process a batch of items with error handling.

        Args:
            items: List of items to process
            processor_func: Function to process each item
            batch_id: Optional batch ID
            context: Additional context

        Returns:
            BatchResult with processing statistics and errors
        """
        batch_id = batch_id or str(uuid4())
        start_time = time.time()

        batch_result = BatchResult(
            batch_id=batch_id,
            stage=stage,
            operation=operation,
            total_items=len(items),
            context=context or {},
        )

        logger.info(
            f"Starting batch processing: {len(items)} items in {stage}.{operation}",
            extra={
                "batch_id": batch_id,
                "stage": stage,
                "operation": operation,
                "total_items": len(items),
            },
        )

        for i, item in enumerate(items):
            try:
                # Add item context
                item_context = {
                    "item_index": i,
                    "batch_id": batch_id,
                    **(context or {}),
                }

                # Process item with error handling
                result = processor_func(item, **item_context)

                if result is not None:
                    batch_result.successful_items += 1
                else:
                    batch_result.skipped_items += 1

            except Exception as e:
                # Create error for this item
                pipeline_error = PipelineError.from_exception(
                    exception=e,
                    stage=stage,
                    operation=operation,
                    context={
                        "item_index": i,
                        "batch_id": batch_id,
                        "item": str(item)[:100],
                    },
                    batch_id=batch_id,
                )

                batch_result.add_error(pipeline_error)

                # Record error if manager provided
                if error_manager:
                    error_manager.record_error(pipeline_error)

                # Check if we should continue processing
                if not continue_on_error or (
                    error_manager
                    and not error_manager.should_continue_batch(batch_result)
                ):
                    logger.warning(
                        f"Stopping batch processing due to error policy",
                        extra={"batch_id": batch_id, "items_processed": i + 1},
                    )
                    break

        # Finalize batch result
        batch_result.duration_seconds = time.time() - start_time

        # Record batch result if manager provided
        if error_manager:
            error_manager.record_batch_result(batch_result)

        logger.info(
            f"Batch processing completed: {batch_result.successful_items}/{batch_result.total_items} successful",
            extra=batch_result.to_dict(),
        )

        return batch_result

    return process_batch
