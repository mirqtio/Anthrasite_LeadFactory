"""
Error Aggregation and Reporting System for LeadFactory Pipeline.

This module provides comprehensive error aggregation, analysis, and reporting
capabilities for monitoring pipeline health and identifying patterns.
"""

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from leadfactory.pipeline.error_handling import (
        BatchResult,
        ErrorCategory,
        ErrorSeverity,
        PipelineError,
    )
    from leadfactory.utils.logging import get_logger
except ImportError:
    # Fallback for testing environments
    from enum import Enum

    class ErrorSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    class ErrorCategory(Enum):
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

    def get_logger(name):
        return logging.getLogger(name)


class AlertLevel(Enum):
    """Alert levels for error thresholds."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class TimeWindow(Enum):
    """Time windows for error aggregation."""

    LAST_HOUR = "last_hour"
    LAST_6_HOURS = "last_6_hours"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


@dataclass
class ErrorPattern:
    """Represents a pattern of errors for analysis."""

    pattern_id: str
    error_type: str
    stage: str
    operation: str
    category: ErrorCategory
    severity: ErrorSeverity
    frequency: int = 0
    first_occurrence: Optional[datetime] = None
    last_occurrence: Optional[datetime] = None
    affected_businesses: Set[int] = field(default_factory=set)
    common_context: Dict[str, Any] = field(default_factory=dict)
    sample_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error pattern to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "error_type": self.error_type,
            "stage": self.stage,
            "operation": self.operation,
            "category": (
                self.category.value
                if hasattr(self.category, "value")
                else str(self.category)
            ),
            "severity": (
                self.severity.value
                if hasattr(self.severity, "value")
                else str(self.severity)
            ),
            "frequency": self.frequency,
            "first_occurrence": (
                self.first_occurrence.isoformat() if self.first_occurrence else None
            ),
            "last_occurrence": (
                self.last_occurrence.isoformat() if self.last_occurrence else None
            ),
            "affected_businesses": list(self.affected_businesses),
            "common_context": self.common_context,
            "sample_errors": self.sample_errors[:5],  # Limit to 5 samples
        }


@dataclass
class ErrorMetrics:
    """Aggregated error metrics for reporting."""

    time_window: TimeWindow
    start_time: datetime
    end_time: datetime
    total_errors: int = 0
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_stage: Dict[str, int] = field(default_factory=dict)
    errors_by_operation: Dict[str, int] = field(default_factory=dict)
    error_rate_per_hour: float = 0.0
    most_common_errors: List[Tuple[str, int]] = field(default_factory=list)
    affected_businesses: Set[int] = field(default_factory=set)
    critical_error_count: int = 0
    recoverable_error_count: int = 0
    patterns: List[ErrorPattern] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "time_window": self.time_window.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_errors": self.total_errors,
            "errors_by_severity": self.errors_by_severity,
            "errors_by_category": self.errors_by_category,
            "errors_by_stage": self.errors_by_stage,
            "errors_by_operation": self.errors_by_operation,
            "error_rate_per_hour": self.error_rate_per_hour,
            "most_common_errors": self.most_common_errors,
            "affected_businesses": list(self.affected_businesses),
            "critical_error_count": self.critical_error_count,
            "recoverable_error_count": self.recoverable_error_count,
            "patterns": [pattern.to_dict() for pattern in self.patterns],
        }


@dataclass
class AlertThreshold:
    """Defines thresholds for error alerting."""

    name: str
    description: str
    metric_type: str  # 'error_rate', 'error_count', 'critical_errors', etc.
    threshold_value: float
    time_window: TimeWindow
    alert_level: AlertLevel
    conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert threshold to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "metric_type": self.metric_type,
            "threshold_value": self.threshold_value,
            "time_window": self.time_window.value,
            "alert_level": self.alert_level.value,
            "conditions": self.conditions,
        }


class ErrorAggregator:
    """Aggregates and analyzes pipeline errors for reporting and alerting."""

    def __init__(
        self, max_error_history: int = 10000, pattern_detection_enabled: bool = True
    ):
        """
        Initialize error aggregator.

        Args:
            max_error_history: Maximum number of errors to keep in memory
            pattern_detection_enabled: Whether to detect error patterns
        """
        self.max_error_history = max_error_history
        self.pattern_detection_enabled = pattern_detection_enabled
        self.error_history: List[PipelineError] = []
        self.batch_history: List[BatchResult] = []
        self.alert_thresholds: List[AlertThreshold] = []
        self.logger = get_logger(__name__)

        # Initialize default alert thresholds
        self._initialize_default_thresholds()

    def _initialize_default_thresholds(self):
        """Initialize default alert thresholds."""
        default_thresholds = [
            AlertThreshold(
                name="High Error Rate",
                description="Error rate exceeds 10% in the last hour",
                metric_type="error_rate",
                threshold_value=0.10,
                time_window=TimeWindow.LAST_HOUR,
                alert_level=AlertLevel.WARNING,
            ),
            AlertThreshold(
                name="Critical Error Rate",
                description="Error rate exceeds 25% in the last hour",
                metric_type="error_rate",
                threshold_value=0.25,
                time_window=TimeWindow.LAST_HOUR,
                alert_level=AlertLevel.CRITICAL,
            ),
            AlertThreshold(
                name="Critical Errors Present",
                description="Critical errors detected in the last hour",
                metric_type="critical_errors",
                threshold_value=1,
                time_window=TimeWindow.LAST_HOUR,
                alert_level=AlertLevel.CRITICAL,
            ),
            AlertThreshold(
                name="High Volume Errors",
                description="More than 100 errors in the last hour",
                metric_type="error_count",
                threshold_value=100,
                time_window=TimeWindow.LAST_HOUR,
                alert_level=AlertLevel.WARNING,
            ),
        ]

        self.alert_thresholds.extend(default_thresholds)

    def add_error(self, error: PipelineError):
        """Add an error to the aggregation system."""
        self.error_history.append(error)

        # Maintain max history size
        if len(self.error_history) > self.max_error_history:
            self.error_history = self.error_history[-self.max_error_history :]

        self.logger.debug(f"Added error to aggregation: {error.id}")

    def add_batch_result(self, batch_result: BatchResult):
        """Add a batch result to the aggregation system."""
        self.batch_history.append(batch_result)

        # Add individual errors from the batch
        for error in batch_result.errors:
            self.add_error(error)

        # Maintain max history size
        if len(self.batch_history) > self.max_error_history:
            self.batch_history = self.batch_history[-self.max_error_history :]

        self.logger.debug(f"Added batch result to aggregation: {batch_result.batch_id}")

    def get_time_window_bounds(
        self, time_window: TimeWindow
    ) -> Tuple[datetime, datetime]:
        """Get start and end times for a time window."""
        end_time = datetime.now()

        if time_window == TimeWindow.LAST_HOUR:
            start_time = end_time - timedelta(hours=1)
        elif time_window == TimeWindow.LAST_6_HOURS:
            start_time = end_time - timedelta(hours=6)
        elif time_window == TimeWindow.LAST_24_HOURS:
            start_time = end_time - timedelta(hours=24)
        elif time_window == TimeWindow.LAST_7_DAYS:
            start_time = end_time - timedelta(days=7)
        elif time_window == TimeWindow.LAST_30_DAYS:
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(hours=24)  # Default to 24 hours

        return start_time, end_time

    def filter_errors_by_time(self, time_window: TimeWindow) -> List[PipelineError]:
        """Filter errors by time window."""
        start_time, end_time = self.get_time_window_bounds(time_window)

        filtered_errors = [
            error
            for error in self.error_history
            if start_time <= error.timestamp <= end_time
        ]

        return filtered_errors

    def generate_error_metrics(
        self, time_window: TimeWindow = TimeWindow.LAST_24_HOURS
    ) -> ErrorMetrics:
        """Generate comprehensive error metrics for the specified time window."""
        start_time, end_time = self.get_time_window_bounds(time_window)
        errors = self.filter_errors_by_time(time_window)

        metrics = ErrorMetrics(
            time_window=time_window,
            start_time=start_time,
            end_time=end_time,
            total_errors=len(errors),
        )

        if not errors:
            return metrics

        # Calculate error rate per hour
        time_diff_hours = (end_time - start_time).total_seconds() / 3600
        metrics.error_rate_per_hour = (
            len(errors) / time_diff_hours if time_diff_hours > 0 else 0
        )

        # Aggregate by severity
        severity_counter = Counter()
        for error in errors:
            severity = (
                error.severity.value
                if hasattr(error.severity, "value")
                else str(error.severity)
            )
            severity_counter[severity] += 1
        metrics.errors_by_severity = dict(severity_counter)

        # Aggregate by category
        category_counter = Counter()
        for error in errors:
            category = (
                error.category.value
                if hasattr(error.category, "value")
                else str(error.category)
            )
            category_counter[category] += 1
        metrics.errors_by_category = dict(category_counter)

        # Aggregate by stage
        stage_counter = Counter(error.stage for error in errors)
        metrics.errors_by_stage = dict(stage_counter)

        # Aggregate by operation
        operation_counter = Counter(error.operation for error in errors)
        metrics.errors_by_operation = dict(operation_counter)

        # Most common error types
        error_type_counter = Counter(error.error_type for error in errors)
        metrics.most_common_errors = error_type_counter.most_common(10)

        # Affected businesses
        metrics.affected_businesses = {
            error.business_id for error in errors if error.business_id is not None
        }

        # Critical and recoverable error counts
        metrics.critical_error_count = sum(
            1
            for error in errors
            if (
                error.severity == ErrorSeverity.CRITICAL
                or str(error.severity) == "critical"
            )
        )
        metrics.recoverable_error_count = sum(
            1 for error in errors if error.recoverable
        )

        # Generate error patterns if enabled
        if self.pattern_detection_enabled:
            metrics.patterns = self.detect_error_patterns(errors)

        return metrics

    def detect_error_patterns(self, errors: List[PipelineError]) -> List[ErrorPattern]:
        """Detect patterns in the error data."""
        patterns = {}

        for error in errors:
            # Create pattern key based on error characteristics
            pattern_key = (
                error.error_type,
                error.stage,
                error.operation,
                str(error.category),
                str(error.severity),
            )

            if pattern_key not in patterns:
                pattern_id = f"pattern_{len(patterns) + 1}"
                patterns[pattern_key] = ErrorPattern(
                    pattern_id=pattern_id,
                    error_type=error.error_type,
                    stage=error.stage,
                    operation=error.operation,
                    category=error.category,
                    severity=error.severity,
                    first_occurrence=error.timestamp,
                    last_occurrence=error.timestamp,
                )

            pattern = patterns[pattern_key]
            pattern.frequency += 1
            pattern.last_occurrence = max(pattern.last_occurrence, error.timestamp)

            if error.business_id:
                pattern.affected_businesses.add(error.business_id)

            # Add sample error message
            if len(pattern.sample_errors) < 5:
                pattern.sample_errors.append(error.error_message)

            # Update common context (simplified - could be more sophisticated)
            for key, value in error.context.items():
                if key in pattern.common_context:
                    if pattern.common_context[key] != value:
                        pattern.common_context[key] = "[VARIES]"
                else:
                    pattern.common_context[key] = value

        # Sort patterns by frequency
        sorted_patterns = sorted(
            patterns.values(), key=lambda p: p.frequency, reverse=True
        )

        return sorted_patterns

    def check_alert_thresholds(self, metrics: ErrorMetrics) -> List[Dict[str, Any]]:
        """Check if any alert thresholds are exceeded."""
        triggered_alerts = []

        for threshold in self.alert_thresholds:
            if threshold.time_window != metrics.time_window:
                continue

            alert_triggered = False
            current_value = None

            if threshold.metric_type == "error_rate":
                current_value = metrics.error_rate_per_hour
                alert_triggered = current_value > threshold.threshold_value
            elif threshold.metric_type == "error_count":
                current_value = metrics.total_errors
                alert_triggered = current_value > threshold.threshold_value
            elif threshold.metric_type == "critical_errors":
                current_value = metrics.critical_error_count
                alert_triggered = current_value >= threshold.threshold_value

            if alert_triggered:
                alert = {
                    "threshold": threshold.to_dict(),
                    "current_value": current_value,
                    "triggered_at": datetime.now().isoformat(),
                    "metrics_summary": {
                        "total_errors": metrics.total_errors,
                        "error_rate_per_hour": metrics.error_rate_per_hour,
                        "critical_errors": metrics.critical_error_count,
                    },
                }
                triggered_alerts.append(alert)

                self.logger.warning(
                    f"Alert threshold exceeded: {threshold.name} "
                    f"(current: {current_value}, threshold: {threshold.threshold_value})"
                )

        return triggered_alerts

    def generate_error_report(
        self,
        time_window: TimeWindow = TimeWindow.LAST_24_HOURS,
        include_patterns: bool = True,
        include_alerts: bool = True,
    ) -> Dict[str, Any]:
        """Generate a comprehensive error report."""
        metrics = self.generate_error_metrics(time_window)

        report = {
            "report_generated_at": datetime.now().isoformat(),
            "metrics": metrics.to_dict(),
        }

        if include_alerts:
            triggered_alerts = self.check_alert_thresholds(metrics)
            report["alerts"] = triggered_alerts
            report["alert_summary"] = {
                "total_alerts": len(triggered_alerts),
                "critical_alerts": len(
                    [
                        a
                        for a in triggered_alerts
                        if a["threshold"]["alert_level"] == "critical"
                    ]
                ),
                "warning_alerts": len(
                    [
                        a
                        for a in triggered_alerts
                        if a["threshold"]["alert_level"] == "warning"
                    ]
                ),
            }

        # Add recommendations based on patterns
        if include_patterns and metrics.patterns:
            report["recommendations"] = self._generate_recommendations(metrics)

        return report

    def _generate_recommendations(self, metrics: ErrorMetrics) -> List[Dict[str, Any]]:
        """Generate recommendations based on error patterns."""
        recommendations = []

        # Check for high-frequency patterns
        for pattern in metrics.patterns[:5]:  # Top 5 patterns
            if pattern.frequency > 10:  # Threshold for frequent errors
                recommendation = {
                    "type": "pattern_analysis",
                    "priority": (
                        "high"
                        if pattern.severity == ErrorSeverity.CRITICAL
                        else "medium"
                    ),
                    "pattern_id": pattern.pattern_id,
                    "description": f"Frequent {pattern.error_type} errors in {pattern.stage}",
                    "frequency": pattern.frequency,
                    "suggested_actions": [
                        f"Investigate {pattern.stage} stage for {pattern.error_type} issues",
                        f"Review {pattern.operation} operation implementation",
                        "Consider adding retry logic if not present",
                        "Check for resource constraints or external dependencies",
                    ],
                }
                recommendations.append(recommendation)

        # Check for critical error trends
        if metrics.critical_error_count > 0:
            recommendations.append(
                {
                    "type": "critical_errors",
                    "priority": "critical",
                    "description": f"{metrics.critical_error_count} critical errors detected",
                    "suggested_actions": [
                        "Immediately investigate critical errors",
                        "Consider stopping affected pipeline stages",
                        "Review system resources and dependencies",
                        "Implement additional monitoring for critical paths",
                    ],
                }
            )

        # Check for high error rates
        if metrics.error_rate_per_hour > 50:  # Threshold for high error rate
            recommendations.append(
                {
                    "type": "high_error_rate",
                    "priority": "high",
                    "description": f"High error rate: {metrics.error_rate_per_hour:.2f} errors/hour",
                    "suggested_actions": [
                        "Review pipeline configuration and thresholds",
                        "Check external API status and rate limits",
                        "Consider implementing circuit breakers",
                        "Review data quality and validation rules",
                    ],
                }
            )

        return recommendations

    def add_custom_threshold(self, threshold: AlertThreshold):
        """Add a custom alert threshold."""
        self.alert_thresholds.append(threshold)
        self.logger.info(f"Added custom alert threshold: {threshold.name}")

    def export_metrics_to_json(
        self, filepath: str, time_window: TimeWindow = TimeWindow.LAST_24_HOURS
    ):
        """Export error metrics to JSON file."""
        report = self.generate_error_report(time_window)

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Error metrics exported to {filepath}")

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a summary of errors for the specified time period."""
        # Convert hours to appropriate time window
        if hours <= 1:
            time_window = TimeWindow.LAST_HOUR
        elif hours <= 6:
            time_window = TimeWindow.LAST_6_HOURS
        elif hours <= 24:
            time_window = TimeWindow.LAST_24_HOURS
        elif hours <= 168:  # 7 days
            time_window = TimeWindow.LAST_7_DAYS
        else:
            time_window = TimeWindow.LAST_30_DAYS

        metrics = self.generate_error_metrics(time_window)

        return {
            "time_period_hours": hours,
            "total_errors": metrics.total_errors,
            "error_rate_per_hour": metrics.error_rate_per_hour,
            "critical_errors": metrics.critical_error_count,
            "affected_businesses": len(metrics.affected_businesses),
            "top_error_types": metrics.most_common_errors[:5],
            "errors_by_stage": metrics.errors_by_stage,
            "errors_by_severity": metrics.errors_by_severity,
        }
