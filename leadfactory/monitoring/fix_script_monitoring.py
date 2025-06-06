"""
Fix Script Monitoring and Reporting System.

This module provides comprehensive monitoring and reporting for manual fix script
effectiveness and performance. Part of Feature 8: Fallback & Retry.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from leadfactory.pipeline.manual_fix_scripts import (
    FixExecution,
    FixResult,
    manual_fix_orchestrator,
)
from leadfactory.storage import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FixScriptMetrics:
    """Metrics for a specific fix script."""

    script_id: str
    description: str
    time_period_hours: int
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    partial_success_executions: int = 0
    manual_intervention_required: int = 0
    not_applicable_executions: int = 0
    average_duration_seconds: float = 0.0
    success_rate_percent: float = 0.0
    effectiveness_score: float = 0.0  # Weighted score considering result types
    most_common_errors: List[str] = field(default_factory=list)
    most_common_changes: List[str] = field(default_factory=list)
    business_impact: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FixScriptAlert:
    """Alert for fix script issues."""

    alert_id: str
    script_id: str
    alert_type: (
        str  # 'low_success_rate', 'high_failure_rate', 'performance_degradation'
    )
    severity: str  # 'warning', 'critical'
    description: str
    threshold_value: float
    current_value: float
    timestamp: datetime = field(default_factory=datetime.now)
    actions_recommended: List[str] = field(default_factory=list)


class FixScriptMonitor:
    """Monitors fix script performance and generates reports."""

    def __init__(self):
        self.storage = get_storage()
        self.alert_thresholds = {
            "success_rate_warning": 70.0,  # Warn if success rate < 70%
            "success_rate_critical": 50.0,  # Critical if success rate < 50%
            "failure_rate_warning": 30.0,  # Warn if failure rate > 30%
            "failure_rate_critical": 50.0,  # Critical if failure rate > 50%
            "avg_duration_warning": 30.0,  # Warn if avg duration > 30 seconds
            "avg_duration_critical": 60.0,  # Critical if avg duration > 60 seconds
        }

    def generate_script_metrics(
        self, script_id: str, hours: int = 24
    ) -> FixScriptMetrics:
        """Generate comprehensive metrics for a specific fix script."""
        # Get fix script from orchestrator
        fix_script = None
        for script in manual_fix_orchestrator.fix_scripts:
            if script.fix_id == script_id:
                fix_script = script
                break

        if not fix_script:
            raise ValueError(f"Fix script {script_id} not found")

        # Filter executions by time period
        cutoff_time = datetime.now() - timedelta(hours=hours)
        executions = [
            ex for ex in fix_script.execution_history if ex.timestamp >= cutoff_time
        ]

        metrics = FixScriptMetrics(
            script_id=script_id,
            description=fix_script.description,
            time_period_hours=hours,
            total_executions=len(executions),
        )

        if not executions:
            return metrics

        # Calculate execution results
        result_counts = {result: 0 for result in FixResult}
        total_duration = 0.0
        error_types = {}
        change_types = {}
        affected_businesses = set()

        for execution in executions:
            result_counts[execution.result] += 1
            total_duration += execution.duration_seconds

            # Track error types from execution errors
            for error in execution.errors_encountered:
                error_type = error.split(":")[0] if ":" in error else error
                error_types[error_type] = error_types.get(error_type, 0) + 1

            # Track change types
            for change in execution.changes_made:
                change_type = change.split(" ")[0] if " " in change else change
                change_types[change_type] = change_types.get(change_type, 0) + 1

            # Track affected businesses
            if execution.business_id:
                affected_businesses.add(execution.business_id)

        # Populate metrics
        metrics.successful_executions = result_counts[FixResult.SUCCESS]
        metrics.failed_executions = result_counts[FixResult.FAILED]
        metrics.partial_success_executions = result_counts[FixResult.PARTIAL_SUCCESS]
        metrics.manual_intervention_required = result_counts[
            FixResult.REQUIRES_MANUAL_INTERVENTION
        ]
        metrics.not_applicable_executions = result_counts[FixResult.NOT_APPLICABLE]

        metrics.average_duration_seconds = total_duration / len(executions)

        # Calculate success rate (excluding not applicable)
        applicable_executions = (
            metrics.total_executions - metrics.not_applicable_executions
        )
        if applicable_executions > 0:
            metrics.success_rate_percent = (
                metrics.successful_executions / applicable_executions
            ) * 100

        # Calculate effectiveness score (weighted)
        effectiveness_points = (
            metrics.successful_executions * 1.0
            + metrics.partial_success_executions * 0.5
            + metrics.manual_intervention_required * 0.2
            + metrics.failed_executions * 0.0
        )
        metrics.effectiveness_score = (
            (effectiveness_points / applicable_executions * 100)
            if applicable_executions > 0
            else 0
        )

        # Top error and change types
        metrics.most_common_errors = [
            error
            for error, count in sorted(
                error_types.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]
        metrics.most_common_changes = [
            change
            for change, count in sorted(
                change_types.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        # Business impact
        metrics.business_impact = {
            "affected_businesses_count": len(affected_businesses),
            "avg_executions_per_business": (
                len(executions) / len(affected_businesses) if affected_businesses else 0
            ),
            "affected_business_ids": list(affected_businesses)[
                :10
            ],  # Limit to first 10
        }

        return metrics

    def generate_all_script_metrics(
        self, hours: int = 24
    ) -> Dict[str, FixScriptMetrics]:
        """Generate metrics for all fix scripts."""
        all_metrics = {}

        for script in manual_fix_orchestrator.fix_scripts:
            try:
                metrics = self.generate_script_metrics(script.fix_id, hours)
                all_metrics[script.fix_id] = metrics
            except Exception as e:
                logger.error(f"Failed to generate metrics for {script.fix_id}: {e}")

        return all_metrics

    def check_fix_script_alerts(
        self, metrics: FixScriptMetrics
    ) -> List[FixScriptAlert]:
        """Check fix script metrics against alert thresholds."""
        alerts = []

        # Success rate alerts
        if metrics.total_executions >= 5:  # Only alert if we have sufficient data
            if (
                metrics.success_rate_percent
                < self.alert_thresholds["success_rate_critical"]
            ):
                alerts.append(
                    FixScriptAlert(
                        alert_id=f"{metrics.script_id}_success_rate_critical",
                        script_id=metrics.script_id,
                        alert_type="low_success_rate",
                        severity="critical",
                        description=f"Critical: {metrics.script_id} success rate is {metrics.success_rate_percent:.1f}%",
                        threshold_value=self.alert_thresholds["success_rate_critical"],
                        current_value=metrics.success_rate_percent,
                        actions_recommended=[
                            "Review fix script logic for common failure patterns",
                            "Check if error conditions have changed",
                            "Consider updating fix script implementation",
                            "Investigate high-frequency error types",
                        ],
                    )
                )
            elif (
                metrics.success_rate_percent
                < self.alert_thresholds["success_rate_warning"]
            ):
                alerts.append(
                    FixScriptAlert(
                        alert_id=f"{metrics.script_id}_success_rate_warning",
                        script_id=metrics.script_id,
                        alert_type="low_success_rate",
                        severity="warning",
                        description=f"Warning: {metrics.script_id} success rate is {metrics.success_rate_percent:.1f}%",
                        threshold_value=self.alert_thresholds["success_rate_warning"],
                        current_value=metrics.success_rate_percent,
                        actions_recommended=[
                            "Monitor success rate trend",
                            "Review recent failure reasons",
                            "Consider script improvements",
                        ],
                    )
                )

        # Failure rate alerts
        failure_rate = (
            (metrics.failed_executions / metrics.total_executions * 100)
            if metrics.total_executions > 0
            else 0
        )
        if failure_rate > self.alert_thresholds["failure_rate_critical"]:
            alerts.append(
                FixScriptAlert(
                    alert_id=f"{metrics.script_id}_failure_rate_critical",
                    script_id=metrics.script_id,
                    alert_type="high_failure_rate",
                    severity="critical",
                    description=f"Critical: {metrics.script_id} failure rate is {failure_rate:.1f}%",
                    threshold_value=self.alert_thresholds["failure_rate_critical"],
                    current_value=failure_rate,
                    actions_recommended=[
                        "Immediately investigate script failures",
                        "Check for environmental changes",
                        "Consider disabling script until fixed",
                        "Review error logs for patterns",
                    ],
                )
            )
        elif failure_rate > self.alert_thresholds["failure_rate_warning"]:
            alerts.append(
                FixScriptAlert(
                    alert_id=f"{metrics.script_id}_failure_rate_warning",
                    script_id=metrics.script_id,
                    alert_type="high_failure_rate",
                    severity="warning",
                    description=f"Warning: {metrics.script_id} failure rate is {failure_rate:.1f}%",
                    threshold_value=self.alert_thresholds["failure_rate_warning"],
                    current_value=failure_rate,
                    actions_recommended=[
                        "Monitor failure rate trend",
                        "Review common failure reasons",
                        "Plan script improvements",
                    ],
                )
            )

        # Performance alerts
        if (
            metrics.average_duration_seconds
            > self.alert_thresholds["avg_duration_critical"]
        ):
            alerts.append(
                FixScriptAlert(
                    alert_id=f"{metrics.script_id}_performance_critical",
                    script_id=metrics.script_id,
                    alert_type="performance_degradation",
                    severity="critical",
                    description=f"Critical: {metrics.script_id} average duration is {metrics.average_duration_seconds:.1f}s",
                    threshold_value=self.alert_thresholds["avg_duration_critical"],
                    current_value=metrics.average_duration_seconds,
                    actions_recommended=[
                        "Investigate performance bottlenecks",
                        "Optimize script logic",
                        "Check for resource constraints",
                        "Consider script timeout adjustments",
                    ],
                )
            )
        elif (
            metrics.average_duration_seconds
            > self.alert_thresholds["avg_duration_warning"]
        ):
            alerts.append(
                FixScriptAlert(
                    alert_id=f"{metrics.script_id}_performance_warning",
                    script_id=metrics.script_id,
                    alert_type="performance_degradation",
                    severity="warning",
                    description=f"Warning: {metrics.script_id} average duration is {metrics.average_duration_seconds:.1f}s",
                    threshold_value=self.alert_thresholds["avg_duration_warning"],
                    current_value=metrics.average_duration_seconds,
                    actions_recommended=[
                        "Monitor performance trend",
                        "Review script efficiency",
                        "Consider optimization opportunities",
                    ],
                )
            )

        return alerts

    def generate_monitoring_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive monitoring report for all fix scripts."""
        # Get metrics for all scripts
        all_metrics = self.generate_all_script_metrics(hours)

        # Check alerts for all scripts
        all_alerts = []
        for metrics in all_metrics.values():
            alerts = self.check_fix_script_alerts(metrics)
            all_alerts.extend(alerts)

        # Calculate overall statistics
        total_executions = sum(m.total_executions for m in all_metrics.values())
        total_successful = sum(m.successful_executions for m in all_metrics.values())
        total_failed = sum(m.failed_executions for m in all_metrics.values())

        overall_success_rate = (
            (total_successful / total_executions * 100) if total_executions > 0 else 0
        )

        # Top performing and problematic scripts
        scripts_by_effectiveness = sorted(
            all_metrics.values(), key=lambda m: m.effectiveness_score, reverse=True
        )

        report = {
            "report_timestamp": datetime.now().isoformat(),
            "time_period_hours": hours,
            "overall_statistics": {
                "total_scripts": len(all_metrics),
                "total_executions": total_executions,
                "overall_success_rate": round(overall_success_rate, 2),
                "total_successful": total_successful,
                "total_failed": total_failed,
                "active_alerts": len(all_alerts),
                "critical_alerts": len(
                    [a for a in all_alerts if a.severity == "critical"]
                ),
            },
            "script_metrics": {
                script_id: asdict(metrics) for script_id, metrics in all_metrics.items()
            },
            "active_alerts": [asdict(alert) for alert in all_alerts],
            "top_performing_scripts": [
                {
                    "script_id": m.script_id,
                    "effectiveness_score": m.effectiveness_score,
                    "success_rate": m.success_rate_percent,
                    "total_executions": m.total_executions,
                }
                for m in scripts_by_effectiveness[:3]
            ],
            "problematic_scripts": [
                {
                    "script_id": m.script_id,
                    "effectiveness_score": m.effectiveness_score,
                    "success_rate": m.success_rate_percent,
                    "total_executions": m.total_executions,
                    "issues": [
                        a.description for a in all_alerts if a.script_id == m.script_id
                    ],
                }
                for m in scripts_by_effectiveness[-3:]
                if m.total_executions > 0
            ],
            "recommendations": self._generate_recommendations(all_metrics, all_alerts),
        }

        return report

    def _generate_recommendations(
        self, all_metrics: Dict[str, FixScriptMetrics], all_alerts: List[FixScriptAlert]
    ) -> List[str]:
        """Generate recommendations based on metrics and alerts."""
        recommendations = []

        # Check for scripts with no recent activity
        inactive_scripts = [m for m in all_metrics.values() if m.total_executions == 0]
        if inactive_scripts:
            recommendations.append(
                f"Consider reviewing {len(inactive_scripts)} fix scripts with no recent activity - "
                f"they may need updates or could be removed if no longer applicable"
            )

        # Check for scripts with high manual intervention rates
        high_manual_scripts = [
            m
            for m in all_metrics.values()
            if m.total_executions > 5
            and m.manual_intervention_required / m.total_executions > 0.3
        ]
        if high_manual_scripts:
            recommendations.append(
                f"Review {len(high_manual_scripts)} scripts with high manual intervention rates - "
                f"consider enhancing automation capabilities"
            )

        # Check for critical alerts
        critical_alerts = [a for a in all_alerts if a.severity == "critical"]
        if critical_alerts:
            recommendations.append(
                f"Immediately address {len(critical_alerts)} critical fix script alerts to maintain system reliability"
            )

        # Check overall performance
        total_executions = sum(m.total_executions for m in all_metrics.values())
        if total_executions > 0:
            overall_effectiveness = (
                sum(
                    m.effectiveness_score * m.total_executions
                    for m in all_metrics.values()
                )
                / total_executions
            )

            if overall_effectiveness < 60:
                recommendations.append(
                    f"Overall fix script effectiveness is {overall_effectiveness:.1f}% - "
                    f"consider comprehensive review of fix script implementations"
                )

        # Check for trending issues
        if len(all_alerts) > 5:
            recommendations.append(
                "High number of fix script alerts detected - consider systematic review of error patterns and fix logic"
            )

        return recommendations

    def export_monitoring_report(self, filepath: str, hours: int = 24):
        """Export monitoring report to JSON file."""
        report = self.generate_monitoring_report(hours)

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Fix script monitoring report exported to {filepath}")

    def get_script_trend_data(self, script_id: str, days: int = 7) -> Dict[str, Any]:
        """Get trend data for a specific script over multiple days."""
        # Get fix script
        fix_script = None
        for script in manual_fix_orchestrator.fix_scripts:
            if script.fix_id == script_id:
                fix_script = script
                break

        if not fix_script:
            raise ValueError(f"Fix script {script_id} not found")

        # Calculate daily metrics
        daily_metrics = []
        for day in range(days):
            start_time = datetime.now() - timedelta(days=day + 1)
            end_time = datetime.now() - timedelta(days=day)

            day_executions = [
                ex
                for ex in fix_script.execution_history
                if start_time <= ex.timestamp < end_time
            ]

            if day_executions:
                successful = sum(
                    1 for ex in day_executions if ex.result == FixResult.SUCCESS
                )
                total = len(day_executions)
                success_rate = (successful / total * 100) if total > 0 else 0
                avg_duration = sum(ex.duration_seconds for ex in day_executions) / total
            else:
                success_rate = 0
                avg_duration = 0
                total = 0

            daily_metrics.append(
                {
                    "date": start_time.strftime("%Y-%m-%d"),
                    "total_executions": total,
                    "success_rate": round(success_rate, 2),
                    "average_duration": round(avg_duration, 2),
                }
            )

        # Reverse to get chronological order
        daily_metrics.reverse()

        return {
            "script_id": script_id,
            "period_days": days,
            "daily_metrics": daily_metrics,
            "trend_analysis": {
                "success_rate_trend": self._calculate_trend(
                    [m["success_rate"] for m in daily_metrics]
                ),
                "duration_trend": self._calculate_trend(
                    [m["average_duration"] for m in daily_metrics]
                ),
                "execution_count_trend": self._calculate_trend(
                    [m["total_executions"] for m in daily_metrics]
                ),
            },
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a series of values."""
        if len(values) < 2:
            return "insufficient_data"

        # Simple linear trend calculation
        non_zero_values = [v for v in values if v > 0]
        if len(non_zero_values) < 2:
            return "stable"

        first_half_avg = sum(non_zero_values[: len(non_zero_values) // 2]) / (
            len(non_zero_values) // 2
        )
        second_half_avg = sum(non_zero_values[len(non_zero_values) // 2 :]) / (
            len(non_zero_values) - len(non_zero_values) // 2
        )

        change_percent = (
            ((second_half_avg - first_half_avg) / first_half_avg * 100)
            if first_half_avg > 0
            else 0
        )

        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"


# Global monitor instance
fix_script_monitor = FixScriptMonitor()
