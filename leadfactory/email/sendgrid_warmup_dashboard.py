"""
SendGrid Warmup Dashboard and Metrics

This module provides comprehensive monitoring dashboard and metrics
for the SendGrid dedicated IP warmup system.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Import WarmupStatus from the warmup module
try:
    from leadfactory.email.sendgrid_warmup import WarmupStatus
except ImportError:
    # Fallback enum definition for testing
    from enum import Enum

    class WarmupStatus(Enum):
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        PAUSED = "paused"
        COMPLETED = "completed"


try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from leadfactory.utils.metrics import Counter, Gauge, Histogram, record_metric

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Metrics not available")

# Warmup-specific metrics
if METRICS_AVAILABLE:
    WARMUP_PROGRESS = Gauge(
        "sendgrid_warmup_progress_percent",
        "Warmup progress percentage",
        ["ip_address", "stage"],
    )
    WARMUP_DAILY_SENDS = Counter(
        "sendgrid_warmup_daily_sends_total",
        "Daily sends during warmup",
        ["ip_address", "stage"],
    )
    WARMUP_BOUNCE_RATE = Gauge(
        "sendgrid_warmup_bounce_rate",
        "Current bounce rate during warmup",
        ["ip_address"],
    )
    WARMUP_SPAM_RATE = Gauge(
        "sendgrid_warmup_spam_rate", "Current spam rate during warmup", ["ip_address"]
    )
    WARMUP_STATUS_GAUGE = Gauge(
        "sendgrid_warmup_status",
        "Warmup status (0=not_started, 1=in_progress, 2=paused, 3=completed)",
        ["ip_address"],
    )
    WARMUP_STAGE_DURATION = Histogram(
        "sendgrid_warmup_stage_duration_hours",
        "Duration of warmup stages",
        ["ip_address", "stage"],
    )


class SendGridWarmupDashboard:
    """Dashboard for SendGrid warmup system monitoring."""

    def __init__(self, warmup_scheduler=None, integration_service=None):
        self.warmup_scheduler = warmup_scheduler
        self.integration_service = integration_service
        logger.info("SendGrid warmup dashboard initialized")

    def get_warmup_metrics(self) -> dict[str, Any]:
        """Collect comprehensive warmup metrics for all IPs."""
        try:
            if not self.warmup_scheduler:
                return {"error": "Warmup scheduler not available"}

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "ips": {},
                "summary": {
                    "total_ips": 0,
                    "in_progress": 0,
                    "completed": 0,
                    "paused": 0,
                },
            }

            warmup_ips = self.warmup_scheduler.get_all_warmup_ips()
            metrics["summary"]["total_ips"] = len(warmup_ips)

            for ip_address in warmup_ips:
                progress = self.warmup_scheduler.get_warmup_progress(ip_address)
                if not progress:
                    continue

                # Get current daily limit from scheduler
                daily_limit = self.warmup_scheduler.get_current_daily_limit(ip_address)

                # Calculate progress percentage
                progress_percent = self._calculate_progress_percent(progress)

                # Get current rates from integration service
                rates = {}
                if self.integration_service:
                    try:
                        rates = self.integration_service.get_current_rates(ip_address)
                    except Exception as e:
                        logger.warning(f"Failed to get rates for {ip_address}: {e}")

                ip_metrics = {
                    "status": progress.status.value.lower(),
                    "stage": progress.current_stage,
                    "progress_percent": progress_percent,
                    "daily_sent": progress.daily_sent_count,
                    "daily_limit": daily_limit,
                    "daily_remaining": max(0, daily_limit - progress.daily_sent_count),
                    "utilization_percent": (
                        (progress.daily_sent_count / daily_limit * 100)
                        if daily_limit > 0
                        else 0
                    ),
                    "total_sent": progress.total_sent_count,
                    "bounce_count": progress.bounce_count,
                    "spam_count": progress.spam_complaint_count,
                    "is_paused": progress.is_paused,
                    "pause_reason": progress.pause_reason,
                    "start_date": progress.start_date.isoformat(),
                    "current_date": progress.current_date.isoformat(),
                    "stage_start_date": progress.stage_start_date.isoformat(),
                    "last_updated": (
                        progress.last_updated.isoformat()
                        if progress.last_updated
                        else None
                    ),
                }

                # Add integration rates if available
                if rates:
                    ip_metrics.update(
                        {
                            "bounce_rate": rates.get("bounce_rate", 0.0),
                            "spam_rate": rates.get("spam_rate", 0.0),
                            "deliverability_rate": 1.0
                            - rates.get("bounce_rate", 0.0)
                            - rates.get("spam_rate", 0.0),
                        }
                    )

                metrics["ips"][ip_address] = ip_metrics

                # Update summary counts
                if progress.status == WarmupStatus.IN_PROGRESS:
                    metrics["summary"]["in_progress"] += 1
                elif progress.status == WarmupStatus.COMPLETED:
                    metrics["summary"]["completed"] += 1
                elif progress.status == WarmupStatus.PAUSED:
                    metrics["summary"]["paused"] += 1

            return metrics

        except Exception as e:
            logger.error(f"Error collecting warmup metrics: {e}")
            return {"error": str(e)}

    def _calculate_progress_percent(self, progress) -> float:
        """Calculate warmup progress percentage."""
        if not progress or not hasattr(progress, "current_stage"):
            return 0.0

        total_stages = getattr(progress, "total_stages", 7)
        current_stage = progress.current_stage

        # Base progress from completed stages
        base_progress = ((current_stage - 1) / total_stages) * 100

        # Add progress within current stage based on days
        if hasattr(progress, "stage_start_date") and progress.stage_start_date:
            # Convert date to datetime for comparison
            stage_start_datetime = datetime.combine(
                progress.stage_start_date, datetime.min.time()
            )
            days_in_stage = (datetime.now() - stage_start_datetime).days
            stage_duration = getattr(progress, "stage_duration_days", 2)
            stage_progress = min(days_in_stage / stage_duration, 1.0)
            stage_percent = (stage_progress / total_stages) * 100
            return min(base_progress + stage_percent, 100.0)

        return base_progress

    def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard for warmup monitoring."""
        metrics = self.get_warmup_metrics()

        if "error" in metrics:
            return self._generate_error_page(metrics["error"])

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SendGrid Warmup Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
                .summary-card {{ background: #fff; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .summary-card h3 {{ margin: 0 0 10px 0; color: #333; }}
                .summary-card .value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
                .ip-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }}
                .ip-card {{ background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .ip-header {{ display: flex; justify-content: between; align-items: center; margin-bottom: 15px; }}
                .ip-address {{ font-size: 18px; font-weight: bold; color: #333; }}
                .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
                .status.in-progress {{ background: #e3f2fd; color: #1976d2; }}
                .status.completed {{ background: #e8f5e8; color: #2e7d32; }}
                .status.paused {{ background: #fff3e0; color: #f57c00; }}
                .progress-bar {{ width: 100%; height: 20px; background: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 10px 0; }}
                .progress-fill {{ height: 100%; background: linear-gradient(90deg, #4caf50, #8bc34a); transition: width 0.3s ease; }}
                .metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }}
                .metric {{ text-align: center; }}
                .metric-label {{ font-size: 12px; color: #666; }}
                .metric-value {{ font-size: 16px; font-weight: bold; color: #333; }}
                .alert {{ background: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 10px 0; }}
                .refresh {{ position: fixed; top: 20px; right: 20px; background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; }}
            </style>
            <script>
                function refreshDashboard() {{
                    location.reload();
                }}
                // Auto-refresh every 30 seconds
                setTimeout(refreshDashboard, 30000);
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SendGrid Warmup Dashboard</h1>
                    <p>Last updated: {metrics["timestamp"]}</p>
                </div>

                <div class="summary">
                    <div class="summary-card">
                        <h3>Total IPs</h3>
                        <div class="value">{metrics["summary"]["total_ips"]}</div>
                    </div>
                    <div class="summary-card">
                        <h3>In Progress</h3>
                        <div class="value">{metrics["summary"]["in_progress"]}</div>
                    </div>
                    <div class="summary-card">
                        <h3>Completed</h3>
                        <div class="value">{metrics["summary"]["completed"]}</div>
                    </div>
                    <div class="summary-card">
                        <h3>Paused</h3>
                        <div class="value">{metrics["summary"]["paused"]}</div>
                    </div>
                </div>

                <div class="ip-grid">
        """

        # Add IP cards
        for ip, data in metrics["ips"].items():
            status_class = data["status"].replace("_", "-")
            progress_percent = data["progress_percent"]

            alerts = []
            if data.get("bounce_rate", 0) > 0.05:
                alerts.append(f"High bounce rate: {data['bounce_rate']:.3f}")
            if data.get("spam_rate", 0) > 0.001:
                alerts.append(f"High spam rate: {data['spam_rate']:.3f}")
            if data["is_paused"]:
                alerts.append(f"Paused: {data['pause_reason']}")

            alerts_html = ""
            for alert in alerts:
                alerts_html += f'<div class="alert">{alert}</div>'

            html += f"""
                    <div class="ip-card">
                        <div class="ip-header">
                            <div class="ip-address">{ip}</div>
                            <div class="status {status_class}">{data["status"]}</div>
                        </div>

                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {progress_percent}%"></div>
                        </div>
                        <div style="text-align: center; margin-top: 5px;">
                            Stage {data["stage"]} - {progress_percent:.1f}% Complete
                        </div>

                        {alerts_html}

                        <div class="metrics">
                            <div class="metric">
                                <div class="metric-label">Daily Sent</div>
                                <div class="metric-value">{data["daily_sent"]}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Daily Limit</div>
                                <div class="metric-value">{data["daily_limit"]}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Bounce Rate</div>
                                <div class="metric-value">{data.get("bounce_rate", 0):.3f}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Spam Rate</div>
                                <div class="metric-value">{data.get("spam_rate", 0):.3f}</div>
                            </div>
                        </div>
                    </div>
            """

        html += """
                </div>
            </div>
            <button class="refresh" onclick="refreshDashboard()">Refresh</button>
        </body>
        </html>
        """

        return html

    def _generate_error_page(self, error_message: str) -> str:
        """Generate error page HTML."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Warmup Dashboard Error</title></head>
        <body>
            <h1>Dashboard Error</h1>
            <p>Error: {error_message}</p>
        </body>
        </html>
        """

    def update_prometheus_metrics(self):
        """Update Prometheus metrics with current warmup data."""
        if not METRICS_AVAILABLE or not self.warmup_scheduler:
            return

        try:
            warmup_ips = self.warmup_scheduler.get_all_warmup_ips()

            for ip in warmup_ips:
                progress = self.warmup_scheduler.get_warmup_progress(ip)
                if not progress:
                    continue

                # Update progress metrics
                progress_percent = self._calculate_progress_percent(progress)
                WARMUP_PROGRESS.labels(
                    ip_address=ip, stage=str(progress.current_stage)
                ).set(progress_percent)

                # Update status metric
                status_value = {
                    "not_started": 0,
                    "in_progress": 1,
                    "paused": 2,
                    "completed": 3,
                }.get(progress.status.value.lower(), 0)

                WARMUP_STATUS_GAUGE.labels(ip_address=ip).set(status_value)

                # Update daily sends
                WARMUP_DAILY_SENDS.labels(
                    ip_address=ip, stage=str(progress.current_stage)
                ).inc(
                    0
                )  # Just to ensure the metric exists

                # Update rates if integration service available
                if self.integration_service:
                    try:
                        rates = self.integration_service.get_current_rates(ip)
                        WARMUP_BOUNCE_RATE.labels(ip_address=ip).set(
                            rates.get("bounce_rate", 0)
                        )
                        WARMUP_SPAM_RATE.labels(ip_address=ip).set(
                            rates.get("spam_rate", 0)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to get rates for {ip}: {e}")

        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")

    def get_alert_conditions(self) -> list[dict[str, Any]]:
        """Check for alert conditions in warmup system."""
        alerts = []

        if not self.warmup_scheduler:
            return alerts

        try:
            warmup_ips = self.warmup_scheduler.get_all_warmup_ips()

            for ip in warmup_ips:
                progress = self.warmup_scheduler.get_warmup_progress(ip)
                if not progress:
                    continue

                # Check for paused warmups
                if progress.is_paused:
                    alerts.append(
                        {
                            "severity": "warning",
                            "ip": ip,
                            "message": f"Warmup paused: {progress.pause_reason}",
                            "timestamp": datetime.now(),
                        }
                    )

                # Check for stalled warmups
                if progress.last_updated:
                    hours_since_update = (
                        datetime.now() - progress.last_updated
                    ).total_seconds() / 3600
                    if hours_since_update > 25:  # More than 25 hours
                        alerts.append(
                            {
                                "severity": "critical",
                                "ip": ip,
                                "message": f"Warmup stalled for {hours_since_update:.1f} hours",
                                "timestamp": datetime.now(),
                            }
                        )

                # Check bounce/spam rates if integration available
                if self.integration_service:
                    rates = self.integration_service.get_current_rates(ip)

                    if rates.get("bounce_rate", 0) > 0.05:
                        alerts.append(
                            {
                                "severity": "critical",
                                "ip": ip,
                                "message": f"High bounce rate: {rates['bounce_rate']:.3f}",
                                "timestamp": datetime.now(),
                            }
                        )

                    if rates.get("spam_rate", 0) > 0.001:
                        alerts.append(
                            {
                                "severity": "warning",
                                "ip": ip,
                                "message": f"High spam rate: {rates['spam_rate']:.3f}",
                                "timestamp": datetime.now(),
                            }
                        )

        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
            alerts.append(
                {
                    "severity": "error",
                    "ip": "system",
                    "message": f"Error checking alerts: {e}",
                    "timestamp": datetime.now(),
                }
            )

        return alerts


def create_warmup_dashboard(warmup_scheduler=None, integration_service=None):
    """Convenience function to create warmup dashboard."""
    return SendGridWarmupDashboard(warmup_scheduler, integration_service)
