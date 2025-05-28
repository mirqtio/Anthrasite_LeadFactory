"""
Enhanced logging system for deduplication operations.

This module provides specialized logging capabilities for tracking and monitoring
deduplication processes, including structured logging, performance metrics,
and detailed operation tracking.
"""

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.utils.logging import LogContext, get_logger, setup_logger


class DedupeLogger:
    """Enhanced logger for deduplication operations with structured logging support."""

    def __init__(
        self,
        name: str = "dedupe",
        level: Optional[str] = None,
        log_file: Optional[str] = None,
    ):
        """Initialize the dedupe logger."""
        self.name = name
        self.log_file = log_file
        self.metrics = {}
        self.operation_stack = []
        self.operations = {}  # Track operations for testing

        if log_file:
            # Use setup_logger with file handler for file logging
            self.logger = setup_logger(
                f"leadfactory.dedupe.{name}",
                level=level,
                add_file_handler=True,
                log_file=log_file,
            )
        else:
            # Use regular get_logger for console logging
            self.logger = get_logger(f"leadfactory.dedupe.{name}", level=level)

    def start_operation(self, operation: str, **context) -> str:
        """
        Start tracking a deduplication operation.

        Args:
            operation: Name of the operation (e.g., "merge", "verify", "find_duplicates")
            **context: Additional context data

        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation}_{int(time.time() * 1000)}"
        operation_data = {
            "id": operation_id,
            "operation": operation,
            "start_time": time.time(),
            "context": context,
        }
        self.operation_stack.append(operation_data)
        self.operations[operation_id] = operation_data  # Track for testing

        self.logger.info(
            f"Started {operation} operation",
            extra={
                "operation_id": operation_id,
                "operation_type": operation,
                **context,
            },
        )
        return operation_id

    def end_operation(self, operation_id: str, status: str = "success", **result_data):
        """
        End tracking a deduplication operation.

        Args:
            operation_id: The operation ID returned by start_operation
            status: Operation status (success, failure, partial)
            **result_data: Result data from the operation
        """
        # Find and remove the operation from the stack
        operation_data = None
        for i, op in enumerate(self.operation_stack):
            if op["id"] == operation_id:
                operation_data = self.operation_stack.pop(i)
                break

        if not operation_data:
            self.logger.warning(f"Operation {operation_id} not found in stack")
            return

        duration = time.time() - operation_data["start_time"]

        log_data = {
            "operation_id": operation_id,
            "operation_type": operation_data["operation"],
            "status": status,
            "duration_seconds": round(duration, 3),
            **operation_data["context"],
            **result_data,
        }

        if status == "success":
            self.logger.info(
                f"Completed {operation_data['operation']} operation in {duration:.3f}s",
                extra=log_data,
            )
        else:
            self.logger.error(
                f"Failed {operation_data['operation']} operation after {duration:.3f}s",
                extra=log_data,
            )

        # Update metrics
        self._update_metrics(operation_data["operation"], duration, status)

    def log_duplicate_found(
        self,
        business1_id: int,
        business2_id: int,
        similarity_score: float,
        match_type: str,
        **details,
    ):
        """Log when a duplicate is found."""
        self.logger.info(
            f"Duplicate found: businesses {business1_id} and {business2_id}",
            extra={
                "event_type": "duplicate_found",
                "business1_id": business1_id,
                "business2_id": business2_id,
                "similarity_score": similarity_score,
                "match_type": match_type,
                **details,
            },
        )

    def log_merge_decision(
        self,
        primary_id: int,
        secondary_id: int,
        decision: str,
        confidence: float,
        **details,
    ):
        """Log merge decision details."""
        self.logger.info(
            f"Merge decision: {decision} for {secondary_id} -> {primary_id}",
            extra={
                "event_type": "merge_decision",
                "primary_id": primary_id,
                "secondary_id": secondary_id,
                "decision": decision,
                "confidence": confidence,
                **details,
            },
        )

    def log_conflict(
        self,
        field: str,
        primary_value: Any,
        secondary_value: Any,
        resolution_strategy: str,
        resolved_value: Any,
    ):
        """Log field conflict and resolution."""
        self.logger.warning(
            f"Field conflict resolved: {field}",
            extra={
                "event_type": "field_conflict",
                "field": field,
                "primary_value": str(primary_value)[:100],  # Truncate long values
                "secondary_value": str(secondary_value)[:100],
                "resolution_strategy": resolution_strategy,
                "resolved_value": str(resolved_value)[:100],
            },
        )

    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """Log a performance metric."""
        self.logger.debug(
            f"Performance metric: {metric_name}={value}{unit}",
            extra={
                "event_type": "performance_metric",
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
            },
        )

    def log_batch_progress(
        self, batch_id: str, processed: int, total: int, errors: int = 0, **stats
    ):
        """Log batch processing progress."""
        progress_pct = (processed / total * 100) if total > 0 else 0
        self.logger.info(
            f"Batch {batch_id}: {processed}/{total} ({progress_pct:.1f}%) processed",
            extra={
                "event_type": "batch_progress",
                "batch_id": batch_id,
                "processed": processed,
                "total": total,
                "progress_percentage": progress_pct,
                "errors": errors,
                **stats,
            },
        )

    def log_merge(
        self,
        primary_id: int,
        secondary_id: int,
        confidence: float,
        strategy: str,
        metadata: Dict[str, Any] = None,
    ):
        """Log merge operations with detailed information."""
        self.logger.info(
            "Business merge completed",
            extra={
                "event_type": "business_merge",
                "primary_id": primary_id,
                "secondary_id": secondary_id,
                "confidence": confidence,
                "strategy": strategy,
                "metadata": metadata or {},
            },
        )

    def log_performance_metrics(
        self,
        operation_type: str,
        duration_seconds: float,
        records_processed: int,
        memory_usage_mb: float = None,
    ):
        """Log performance metrics for operations."""
        records_per_second = (
            records_processed / duration_seconds if duration_seconds > 0 else 0
        )
        self.logger.info(
            f"Performance metrics for {operation_type}: {duration_seconds:.2f}s, {records_processed} records",
            extra={
                "event_type": "performance_metrics",
                "operation_type": operation_type,
                "duration_seconds": duration_seconds,
                "records_processed": records_processed,
                "memory_usage_mb": memory_usage_mb,
                "records_per_second": records_per_second,
            },
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics."""
        return {"operations": self.metrics, "timestamp": datetime.utcnow().isoformat()}

    def _update_metrics(self, operation: str, duration: float, status: str):
        """Update internal metrics tracking."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "total_duration": 0,
                "min_duration": float("inf"),
                "max_duration": 0,
            }

        metrics = self.metrics[operation]
        metrics["count"] += 1
        metrics["total_duration"] += duration
        metrics["min_duration"] = min(metrics["min_duration"], duration)
        metrics["max_duration"] = max(metrics["max_duration"], duration)

        if status == "success":
            metrics["success_count"] += 1
        else:
            metrics["failure_count"] += 1


@contextmanager
def dedupe_operation(logger: DedupeLogger, operation: str, **context):
    """
    Context manager for tracking dedupe operations.

    Usage:
        with dedupe_operation(logger, "merge", business1_id=1, business2_id=2) as op_id:
            # Perform operation
            pass
    """
    operation_id = logger.start_operation(operation, **context)
    try:
        yield operation_id
        logger.end_operation(operation_id, status="success")
    except Exception as e:
        logger.end_operation(operation_id, status="error", error=str(e))
        raise


def log_dedupe_performance(logger: DedupeLogger):
    """
    Decorator to log performance of dedupe functions.

    Usage:
        @log_dedupe_performance(logger)
        def my_dedupe_function():
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_seconds = time.time() - start_time
                logger.log_performance_metrics(
                    operation_type=func.__name__,
                    duration_seconds=duration_seconds,
                    records_processed=1,  # Default value
                )
                return result
            except Exception as e:
                duration_seconds = time.time() - start_time
                logger.log_performance_metrics(
                    operation_type=f"{func.__name__}_failed",
                    duration_seconds=duration_seconds,
                    records_processed=0,
                )
                raise

        return wrapper

    return decorator


class DedupeLogAnalyzer:
    """Analyzer for dedupe logs to extract insights and patterns."""

    def __init__(self, log_file: Optional[str] = None):
        """Initialize the log analyzer."""
        self.log_file = log_file
        self.logs = []
        if log_file:
            self.load_logs()

    def load_logs(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """Load and parse dedupe logs within the specified time range."""
        if not self.log_file or not os.path.exists(self.log_file):
            return []

        import json

        logs = []
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            log_entry = json.loads(line)
                            # Filter by time range if specified
                            if start_time or end_time:
                                log_time = datetime.fromisoformat(
                                    log_entry.get("timestamp", "").replace(
                                        "Z", "+00:00"
                                    )
                                )
                                if start_time and log_time < start_time:
                                    continue
                                if end_time and log_time > end_time:
                                    continue
                            logs.append(log_entry)
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            pass

        self.logs = logs
        return logs

    def analyze_merge_patterns(self) -> Dict[str, Any]:
        """Analyze merge patterns from logs."""
        merge_logs = [
            log for log in self.logs if log.get("event_type") == "business_merge"
        ]

        if not merge_logs:
            return {"message": "No merge logs found"}

        total_merges = len(merge_logs)
        successful_merges = sum(
            1 for log in merge_logs if log.get("status") == "success"
        )
        failed_merges = sum(1 for log in merge_logs if log.get("status") == "failure")

        return {
            "total_merges": total_merges,
            "successful_merges": successful_merges,
            "failed_merges": failed_merges,
            "success_rate": (
                round(successful_merges / total_merges * 100, 2)
                if total_merges > 0
                else 0
            ),
            "average_confidence": (
                round(
                    sum(log.get("confidence", 0) for log in merge_logs) / total_merges,
                    2,
                )
                if total_merges > 0
                else 0
            ),
        }

    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze performance metrics from logs."""
        perf_logs = [
            log for log in self.logs if log.get("event_type") == "performance_metric"
        ]

        if not perf_logs:
            return {"message": "No performance metrics found"}

        metrics = {}
        for log in perf_logs:
            metric_name = log.get("metric_name")
            value = log.get("value", 0)

            if metric_name not in metrics:
                metrics[metric_name] = {
                    "count": 0,
                    "total": 0,
                    "min": float("inf"),
                    "max": 0,
                }

            metrics[metric_name]["count"] += 1
            metrics[metric_name]["total"] += value
            metrics[metric_name]["min"] = min(metrics[metric_name]["min"], value)
            metrics[metric_name]["max"] = max(metrics[metric_name]["max"], value)

        # Calculate averages
        for metric in metrics.values():
            metric["average"] = (
                metric["total"] / metric["count"] if metric["count"] > 0 else 0
            )

        return metrics

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get a summary of all operations from logs."""
        operation_logs = [log for log in self.logs if log.get("operation_type")]

        if not operation_logs:
            return {"message": "No operation logs found"}

        operations = {}
        for log in operation_logs:
            op_type = log.get("operation_type")
            if op_type not in operations:
                operations[op_type] = {
                    "count": 0,
                    "total_duration": 0,
                    "avg_duration": 0,
                }

            operations[op_type]["count"] += 1
            duration = log.get("duration_seconds", 0)
            operations[op_type]["total_duration"] += duration
            operations[op_type]["avg_duration"] = (
                operations[op_type]["total_duration"] / operations[op_type]["count"]
            )

        return operations

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive dedupe analysis report."""
        return {
            "summary": {
                "total_logs_analyzed": len(self.logs),
                "time_range": {
                    "start": (
                        min(log.get("timestamp", "") for log in self.logs)
                        if self.logs
                        else None
                    ),
                    "end": (
                        max(log.get("timestamp", "") for log in self.logs)
                        if self.logs
                        else None
                    ),
                },
            },
            "merge_analysis": self.analyze_merge_patterns(),
            "performance_analysis": self.analyze_performance(),
            "operation_summary": self.get_operation_summary(),
            "generated_at": datetime.utcnow().isoformat(),
        }


# Create a default dedupe logger instance
dedupe_logger = DedupeLogger()
