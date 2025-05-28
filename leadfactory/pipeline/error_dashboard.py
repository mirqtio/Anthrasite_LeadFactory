"""
Error Dashboard and Visualization System for LeadFactory Pipeline.

This module provides dashboard functionality for visualizing error patterns,
trends, and metrics through web interface and reports.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from leadfactory.pipeline.error_aggregation import (
        AlertLevel,
        ErrorAggregator,
        TimeWindow,
    )
    from leadfactory.utils.logging import get_logger
except ImportError:
    # Fallback for testing environments
    import logging

    def get_logger(name):
        return logging.getLogger(name)

    class TimeWindow:
        LAST_HOUR = "last_hour"
        LAST_24_HOURS = "last_24_hours"
        LAST_7_DAYS = "last_7_days"

    class AlertLevel:
        WARNING = "warning"
        CRITICAL = "critical"


@dataclass
class DashboardConfig:
    """Configuration for error dashboard."""

    refresh_interval_seconds: int = 300  # 5 minutes
    max_error_patterns: int = 10
    max_recent_errors: int = 50
    enable_real_time_alerts: bool = True
    alert_email_recipients: List[str] = None
    dashboard_title: str = "LeadFactory Pipeline Error Dashboard"

    def __post_init__(self):
        if self.alert_email_recipients is None:
            self.alert_email_recipients = []


class ErrorDashboard:
    """Web-based dashboard for error monitoring and visualization."""

    def __init__(
        self, aggregator: ErrorAggregator, config: Optional[DashboardConfig] = None
    ):
        """
        Initialize error dashboard.

        Args:
            aggregator: Error aggregator instance
            config: Dashboard configuration
        """
        self.aggregator = aggregator
        self.config = config or DashboardConfig()
        self.logger = get_logger(__name__)

    def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate comprehensive dashboard data."""
        # Get metrics for different time windows
        metrics_1h = self.aggregator.generate_error_metrics(TimeWindow.LAST_HOUR)
        metrics_24h = self.aggregator.generate_error_metrics(TimeWindow.LAST_24_HOURS)
        metrics_7d = self.aggregator.generate_error_metrics(TimeWindow.LAST_7_DAYS)

        # Check for alerts
        alerts_1h = self.aggregator.check_alert_thresholds(metrics_1h)
        alerts_24h = self.aggregator.check_alert_thresholds(metrics_24h)

        # Get recent errors
        recent_errors = self._get_recent_errors(self.config.max_recent_errors)

        dashboard_data = {
            "generated_at": datetime.now().isoformat(),
            "config": {
                "title": self.config.dashboard_title,
                "refresh_interval": self.config.refresh_interval_seconds,
            },
            "summary": {
                "last_hour": {
                    "total_errors": metrics_1h.total_errors,
                    "error_rate": round(metrics_1h.error_rate_per_hour, 2),
                    "critical_errors": metrics_1h.critical_error_count,
                    "affected_businesses": len(metrics_1h.affected_businesses),
                },
                "last_24_hours": {
                    "total_errors": metrics_24h.total_errors,
                    "error_rate": round(metrics_24h.error_rate_per_hour, 2),
                    "critical_errors": metrics_24h.critical_error_count,
                    "affected_businesses": len(metrics_24h.affected_businesses),
                },
                "last_7_days": {
                    "total_errors": metrics_7d.total_errors,
                    "error_rate": round(metrics_7d.error_rate_per_hour, 2),
                    "critical_errors": metrics_7d.critical_error_count,
                    "affected_businesses": len(metrics_7d.affected_businesses),
                },
            },
            "alerts": {
                "active_alerts": len(alerts_1h) + len(alerts_24h),
                "critical_alerts": len(
                    [
                        a
                        for a in alerts_1h + alerts_24h
                        if a["threshold"]["alert_level"] == "critical"
                    ]
                ),
                "recent_alerts": alerts_1h + alerts_24h,
            },
            "error_breakdown": {
                "by_severity": metrics_24h.errors_by_severity,
                "by_category": metrics_24h.errors_by_category,
                "by_stage": metrics_24h.errors_by_stage,
                "by_operation": metrics_24h.errors_by_operation,
            },
            "top_patterns": [
                pattern.to_dict()
                for pattern in metrics_24h.patterns[: self.config.max_error_patterns]
            ],
            "recent_errors": recent_errors,
            "trends": self._calculate_error_trends(),
            "health_status": self._calculate_health_status(metrics_1h, metrics_24h),
        }

        return dashboard_data

    def _get_recent_errors(self, limit: int) -> List[Dict[str, Any]]:
        """Get recent errors for dashboard display."""
        recent_errors = sorted(
            self.aggregator.error_history, key=lambda e: e.timestamp, reverse=True
        )[:limit]

        return [
            {
                "id": error.id,
                "timestamp": error.timestamp.isoformat(),
                "stage": error.stage,
                "operation": error.operation,
                "error_type": error.error_type,
                "message": (
                    error.error_message[:200] + "..."
                    if len(error.error_message) > 200
                    else error.error_message
                ),
                "severity": (
                    error.severity.value
                    if hasattr(error.severity, "value")
                    else str(error.severity)
                ),
                "category": (
                    error.category.value
                    if hasattr(error.category, "value")
                    else str(error.category)
                ),
                "business_id": error.business_id,
                "recoverable": error.recoverable,
            }
            for error in recent_errors
        ]

    def _calculate_error_trends(self) -> Dict[str, Any]:
        """Calculate error trends for visualization."""
        now = datetime.now()

        # Calculate hourly error counts for the last 24 hours
        hourly_counts = {}
        for i in range(24):
            hour_start = now - timedelta(hours=i + 1)
            hour_end = now - timedelta(hours=i)

            hour_errors = [
                error
                for error in self.aggregator.error_history
                if hour_start <= error.timestamp < hour_end
            ]

            hour_key = hour_start.strftime("%H:00")
            hourly_counts[hour_key] = len(hour_errors)

        # Calculate daily error counts for the last 7 days
        daily_counts = {}
        for i in range(7):
            day_start = now - timedelta(days=i + 1)
            day_end = now - timedelta(days=i)

            day_errors = [
                error
                for error in self.aggregator.error_history
                if day_start <= error.timestamp < day_end
            ]

            day_key = day_start.strftime("%Y-%m-%d")
            daily_counts[day_key] = len(day_errors)

        return {
            "hourly_last_24h": hourly_counts,
            "daily_last_7d": daily_counts,
            "trend_direction": self._calculate_trend_direction(hourly_counts),
        }

    def _calculate_trend_direction(self, hourly_counts: Dict[str, int]) -> str:
        """Calculate overall trend direction."""
        if not hourly_counts:
            return "stable"

        values = list(hourly_counts.values())
        if len(values) < 2:
            return "stable"

        # Compare recent hours with earlier hours
        recent_avg = sum(values[:6]) / 6  # Last 6 hours
        earlier_avg = sum(values[6:12]) / 6  # Previous 6 hours

        if recent_avg > earlier_avg * 1.2:
            return "increasing"
        elif recent_avg < earlier_avg * 0.8:
            return "decreasing"
        else:
            return "stable"

    def _calculate_health_status(self, metrics_1h, metrics_24h) -> Dict[str, Any]:
        """Calculate overall pipeline health status."""
        # Define health criteria
        critical_threshold = 10  # Critical errors in last hour
        warning_threshold = 50  # Total errors in last hour

        status = "healthy"
        issues = []

        if metrics_1h.critical_error_count > 0:
            status = "critical"
            issues.append(
                f"{metrics_1h.critical_error_count} critical errors in last hour"
            )
        elif metrics_1h.total_errors > warning_threshold:
            status = "warning"
            issues.append(
                f"High error volume: {metrics_1h.total_errors} errors in last hour"
            )
        elif metrics_1h.error_rate_per_hour > 25:
            status = "warning"
            issues.append(
                f"High error rate: {metrics_1h.error_rate_per_hour:.1f} errors/hour"
            )

        # Check for increasing error trends
        trends = self._calculate_error_trends()
        if trends["trend_direction"] == "increasing" and status == "healthy":
            status = "warning"
            issues.append("Error rate is increasing")

        return {
            "status": status,
            "issues": issues,
            "last_updated": datetime.now().isoformat(),
        }

    def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard for web display."""
        dashboard_data = self.generate_dashboard_data()

        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .status-card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .status-healthy {{ border-left: 5px solid #27ae60; }}
                .status-warning {{ border-left: 5px solid #f39c12; }}
                .status-critical {{ border-left: 5px solid #e74c3c; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
                .metric-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
                .metric-label {{ color: #7f8c8d; margin-top: 5px; }}
                .alert-item {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 5px 0; border-radius: 4px; }}
                .alert-critical {{ background: #f8d7da; border-color: #f5c6cb; }}
                .error-item {{ background: white; padding: 15px; margin: 5px 0; border-radius: 4px; border-left: 4px solid #3498db; }}
                .error-critical {{ border-left-color: #e74c3c; }}
                .error-high {{ border-left-color: #f39c12; }}
                .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
                .refresh-info {{ text-align: center; color: #7f8c8d; margin-top: 20px; }}
            </style>
            <script>
                setTimeout(function() {{ location.reload(); }}, {refresh_interval}000);
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{title}</h1>
                    <p>Last updated: {generated_at}</p>
                </div>

                <div class="status-card status-{health_status}">
                    <h2>Pipeline Health: {health_status_title}</h2>
                    {health_issues}
                </div>

                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{errors_1h}</div>
                        <div class="metric-label">Errors (Last Hour)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{errors_24h}</div>
                        <div class="metric-label">Errors (Last 24h)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{critical_errors_24h}</div>
                        <div class="metric-label">Critical Errors (24h)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{error_rate_24h}</div>
                        <div class="metric-label">Error Rate (per hour)</div>
                    </div>
                </div>

                {alerts_section}

                {recent_errors_section}

                <div class="refresh-info">
                    Dashboard refreshes every {refresh_interval} seconds
                </div>
            </div>
        </body>
        </html>
        """

        # Format health issues
        health_issues = ""
        if dashboard_data["health_status"]["issues"]:
            health_issues = (
                "<ul>"
                + "".join(
                    f"<li>{issue}</li>"
                    for issue in dashboard_data["health_status"]["issues"]
                )
                + "</ul>"
            )
        else:
            health_issues = "<p>No issues detected</p>"

        # Format alerts section
        alerts_section = ""
        if dashboard_data["alerts"]["recent_alerts"]:
            alerts_section = "<div class='status-card'><h2>Active Alerts</h2>"
            for alert in dashboard_data["alerts"]["recent_alerts"]:
                alert_class = (
                    "alert-critical"
                    if alert["threshold"]["alert_level"] == "critical"
                    else "alert-item"
                )
                alerts_section += f"""
                <div class="{alert_class}">
                    <strong>{alert['threshold']['name']}</strong><br>
                    {alert['threshold']['description']}<br>
                    Current: {alert['current_value']}, Threshold: {alert['threshold']['threshold_value']}
                </div>
                """
            alerts_section += "</div>"

        # Format recent errors section
        recent_errors_section = "<div class='status-card'><h2>Recent Errors</h2>"
        if dashboard_data["recent_errors"]:
            for error in dashboard_data["recent_errors"][:10]:  # Show top 10
                error_class = (
                    f"error-{error['severity']}"
                    if error["severity"] in ["critical", "high"]
                    else "error-item"
                )
                recent_errors_section += f"""
                <div class="{error_class}">
                    <strong>{error['error_type']}</strong> in {error['stage']}<br>
                    {error['message']}<br>
                    <span class="timestamp">{error['timestamp']} | Severity: {error['severity']}</span>
                </div>
                """
        else:
            recent_errors_section += "<p>No recent errors</p>"
        recent_errors_section += "</div>"

        return html_template.format(
            title=dashboard_data["config"]["title"],
            refresh_interval=dashboard_data["config"]["refresh_interval"],
            generated_at=dashboard_data["generated_at"],
            health_status=dashboard_data["health_status"]["status"],
            health_status_title=dashboard_data["health_status"]["status"].title(),
            health_issues=health_issues,
            errors_1h=dashboard_data["summary"]["last_hour"]["total_errors"],
            errors_24h=dashboard_data["summary"]["last_24_hours"]["total_errors"],
            critical_errors_24h=dashboard_data["summary"]["last_24_hours"][
                "critical_errors"
            ],
            error_rate_24h=dashboard_data["summary"]["last_24_hours"]["error_rate"],
            alerts_section=alerts_section,
            recent_errors_section=recent_errors_section,
        )

    def save_dashboard_html(self, filepath: str):
        """Save HTML dashboard to file."""
        html_content = self.generate_html_dashboard()

        with open(filepath, "w") as f:
            f.write(html_content)

        self.logger.info(f"Dashboard saved to {filepath}")

    def export_dashboard_data(self, filepath: str):
        """Export dashboard data to JSON file."""
        dashboard_data = self.generate_dashboard_data()

        with open(filepath, "w") as f:
            json.dump(dashboard_data, f, indent=2, default=str)

        self.logger.info(f"Dashboard data exported to {filepath}")


class ErrorReportGenerator:
    """Generates comprehensive error reports for stakeholders."""

    def __init__(self, aggregator: ErrorAggregator):
        """Initialize report generator."""
        self.aggregator = aggregator
        self.logger = get_logger(__name__)

    def generate_executive_summary(
        self, time_window: TimeWindow = TimeWindow.LAST_24_HOURS
    ) -> Dict[str, Any]:
        """Generate executive summary of error status."""
        metrics = self.aggregator.generate_error_metrics(time_window)

        # Calculate key performance indicators
        total_operations = max(
            metrics.total_errors * 10, 1000
        )  # Estimate total operations
        success_rate = max(
            0, (total_operations - metrics.total_errors) / total_operations * 100
        )

        return {
            "report_type": "executive_summary",
            "time_period": time_window.value,
            "generated_at": datetime.now().isoformat(),
            "key_metrics": {
                "total_errors": metrics.total_errors,
                "critical_errors": metrics.critical_error_count,
                "success_rate_percent": round(success_rate, 2),
                "error_rate_per_hour": round(metrics.error_rate_per_hour, 2),
                "affected_businesses": len(metrics.affected_businesses),
            },
            "status_summary": self._get_status_summary(metrics),
            "top_issues": self._get_top_issues(metrics),
            "recommendations": self._get_executive_recommendations(metrics),
        }

    def _get_status_summary(self, metrics) -> str:
        """Get high-level status summary."""
        if metrics.critical_error_count > 0:
            return f"CRITICAL: {metrics.critical_error_count} critical errors require immediate attention"
        elif metrics.total_errors > 100:
            return (
                f"WARNING: High error volume ({metrics.total_errors} errors) detected"
            )
        elif metrics.error_rate_per_hour > 25:
            return (
                f"WARNING: Elevated error rate ({metrics.error_rate_per_hour:.1f}/hour)"
            )
        else:
            return "HEALTHY: Pipeline operating within normal parameters"

    def _get_top_issues(self, metrics) -> List[Dict[str, Any]]:
        """Get top issues for executive attention."""
        issues = []

        # Critical errors
        if metrics.critical_error_count > 0:
            issues.append(
                {
                    "priority": "critical",
                    "description": f"{metrics.critical_error_count} critical errors",
                    "impact": "Pipeline reliability compromised",
                }
            )

        # High error volume
        if metrics.total_errors > 100:
            issues.append(
                {
                    "priority": "high",
                    "description": f"High error volume: {metrics.total_errors} errors",
                    "impact": "Potential service degradation",
                }
            )

        # Top error patterns
        for pattern in metrics.patterns[:3]:
            if pattern.frequency > 10:
                issues.append(
                    {
                        "priority": "medium",
                        "description": f"Recurring {pattern.error_type} in {pattern.stage}",
                        "impact": f"Affects {len(pattern.affected_businesses)} businesses",
                    }
                )

        return issues

    def _get_executive_recommendations(self, metrics) -> List[str]:
        """Get executive-level recommendations."""
        recommendations = []

        if metrics.critical_error_count > 0:
            recommendations.append(
                "Immediate investigation of critical errors required"
            )
            recommendations.append(
                "Consider implementing emergency response procedures"
            )

        if metrics.total_errors > 100:
            recommendations.append("Review pipeline capacity and scaling requirements")
            recommendations.append("Implement additional monitoring and alerting")

        if len(metrics.patterns) > 5:
            recommendations.append("Prioritize fixing recurring error patterns")
            recommendations.append("Invest in improved error handling and retry logic")

        if not recommendations:
            recommendations.append("Continue monitoring current performance levels")
            recommendations.append("Consider proactive improvements to error handling")

        return recommendations
