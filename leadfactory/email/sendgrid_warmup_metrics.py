"""
SendGrid Warmup Metrics Integration

This module extends the main metrics system with SendGrid warmup-specific metrics
and provides integration with the existing Prometheus metrics infrastructure.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    from leadfactory.utils.metrics import (
        METRICS_AVAILABLE,
        Counter,
        Gauge,
        Histogram,
        record_metric,
    )
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Metrics system not available")

# Extended warmup metrics for integration with main metrics system
if METRICS_AVAILABLE:
    # Warmup lifecycle metrics
    WARMUP_STARTED = Counter(
        "sendgrid_warmup_started_total",
        "Total number of warmups started",
        ["ip_address"],
    )

    WARMUP_COMPLETED = Counter(
        "sendgrid_warmup_completed_total",
        "Total number of warmups completed",
        ["ip_address", "duration_days"],
    )

    WARMUP_PAUSED = Counter(
        "sendgrid_warmup_paused_total",
        "Total number of warmup pauses",
        ["ip_address", "reason"],
    )

    WARMUP_RESUMED = Counter(
        "sendgrid_warmup_resumed_total",
        "Total number of warmup resumes",
        ["ip_address"],
    )

    # Stage progression metrics
    WARMUP_STAGE_ADVANCED = Counter(
        "sendgrid_warmup_stage_advanced_total",
        "Total stage advancements",
        ["ip_address", "from_stage", "to_stage"],
    )

    WARMUP_STAGE_COMPLETION_TIME = Histogram(
        "sendgrid_warmup_stage_completion_seconds",
        "Time to complete warmup stages",
        ["ip_address", "stage"],
        buckets=[3600, 7200, 14400, 28800, 43200, 86400, 172800, 259200],  # 1h to 3d
    )

    # Email sending metrics during warmup
    WARMUP_EMAILS_SENT = Counter(
        "sendgrid_warmup_emails_sent_total",
        "Emails sent during warmup",
        ["ip_address", "stage", "status"],
    )

    WARMUP_DAILY_LIMIT_UTILIZATION = Gauge(
        "sendgrid_warmup_daily_limit_utilization_percent",
        "Percentage of daily limit used",
        ["ip_address", "stage"],
    )

    # Quality metrics during warmup
    WARMUP_DELIVERABILITY_RATE = Gauge(
        "sendgrid_warmup_deliverability_rate",
        "Deliverability rate during warmup",
        ["ip_address", "stage"],
    )

    WARMUP_REPUTATION_SCORE = Gauge(
        "sendgrid_warmup_reputation_score",
        "IP reputation score during warmup",
        ["ip_address"],
    )

    # Threshold breach metrics
    WARMUP_THRESHOLD_BREACHES = Counter(
        "sendgrid_warmup_threshold_breaches_total",
        "Threshold breaches during warmup",
        ["ip_address", "threshold_type", "severity"],
    )

    # Integration metrics
    WARMUP_INTEGRATION_EVENTS = Counter(
        "sendgrid_warmup_integration_events_total",
        "Integration events between warmup and other systems",
        ["ip_address", "event_type", "system"],
    )


class SendGridWarmupMetricsCollector:
    """Collects and reports warmup metrics to the main metrics system."""

    def __init__(self, warmup_scheduler=None, integration_service=None):
        self.warmup_scheduler = warmup_scheduler
        self.integration_service = integration_service
        logger.info("SendGrid warmup metrics collector initialized")

    def record_warmup_started(self, ip_address: str):
        """Record warmup start event."""
        if METRICS_AVAILABLE:
            WARMUP_STARTED.labels(ip_address=ip_address).inc()
        logger.info(f"Recorded warmup start for IP {ip_address}")

    def record_warmup_completed(self, ip_address: str, duration_days: int):
        """Record warmup completion event."""
        if METRICS_AVAILABLE:
            WARMUP_COMPLETED.labels(
                ip_address=ip_address, duration_days=str(duration_days)
            ).inc()
        logger.info(
            f"Recorded warmup completion for IP {ip_address} after {duration_days} days"
        )

    def record_warmup_paused(self, ip_address: str, reason: str):
        """Record warmup pause event."""
        if METRICS_AVAILABLE:
            WARMUP_PAUSED.labels(ip_address=ip_address, reason=reason).inc()
        logger.info(f"Recorded warmup pause for IP {ip_address}: {reason}")

    def record_warmup_resumed(self, ip_address: str):
        """Record warmup resume event."""
        if METRICS_AVAILABLE:
            WARMUP_RESUMED.labels(ip_address=ip_address).inc()
        logger.info(f"Recorded warmup resume for IP {ip_address}")

    def record_stage_advancement(
        self, ip_address: str, from_stage: int, to_stage: int, duration_seconds: float
    ):
        """Record stage advancement with timing."""
        if METRICS_AVAILABLE:
            WARMUP_STAGE_ADVANCED.labels(
                ip_address=ip_address,
                from_stage=str(from_stage),
                to_stage=str(to_stage),
            ).inc()

            WARMUP_STAGE_COMPLETION_TIME.labels(
                ip_address=ip_address, stage=str(from_stage)
            ).observe(duration_seconds)

        logger.info(
            f"Recorded stage advancement for IP {ip_address}: {from_stage} -> {to_stage}"
        )

    def record_email_sent(self, ip_address: str, stage: int, status: str = "success"):
        """Record email sent during warmup."""
        if METRICS_AVAILABLE:
            WARMUP_EMAILS_SENT.labels(
                ip_address=ip_address, stage=str(stage), status=status
            ).inc()

    def update_daily_limit_utilization(
        self, ip_address: str, stage: int, sent: int, limit: int
    ):
        """Update daily limit utilization gauge."""
        if METRICS_AVAILABLE and limit > 0:
            utilization = (sent / limit) * 100
            WARMUP_DAILY_LIMIT_UTILIZATION.labels(
                ip_address=ip_address, stage=str(stage)
            ).set(utilization)

    def update_deliverability_rate(self, ip_address: str, stage: int, rate: float):
        """Update deliverability rate gauge."""
        if METRICS_AVAILABLE:
            WARMUP_DELIVERABILITY_RATE.labels(
                ip_address=ip_address, stage=str(stage)
            ).set(rate)

    def update_reputation_score(self, ip_address: str, score: float):
        """Update IP reputation score gauge."""
        if METRICS_AVAILABLE:
            WARMUP_REPUTATION_SCORE.labels(ip_address=ip_address).set(score)

    def record_threshold_breach(
        self, ip_address: str, threshold_type: str, severity: str
    ):
        """Record threshold breach event."""
        if METRICS_AVAILABLE:
            WARMUP_THRESHOLD_BREACHES.labels(
                ip_address=ip_address, threshold_type=threshold_type, severity=severity
            ).inc()
        logger.warning(
            f"Recorded threshold breach for IP {ip_address}: {threshold_type} ({severity})"
        )

    def record_integration_event(self, ip_address: str, event_type: str, system: str):
        """Record integration event with other systems."""
        if METRICS_AVAILABLE:
            WARMUP_INTEGRATION_EVENTS.labels(
                ip_address=ip_address, event_type=event_type, system=system
            ).inc()
        logger.info(
            f"Recorded integration event for IP {ip_address}: {event_type} with {system}"
        )

    def collect_all_metrics(self) -> dict[str, Any]:
        """Collect comprehensive warmup metrics for monitoring and reporting."""
        try:
            if not self.warmup_scheduler:
                return {"error": "Warmup scheduler not available"}

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "warmup_metrics": {},
                "system_health": {
                    "total_ips": 0,
                    "active_warmups": 0,
                    "completed_warmups": 0,
                    "paused_warmups": 0,
                    "avg_stage": 0.0,
                    "total_emails_sent": 0,
                },
            }

            warmup_ips = self.warmup_scheduler.get_all_warmup_ips()
            metrics["system_health"]["total_ips"] = len(warmup_ips)

            total_stage = 0
            total_emails = 0

            for ip_address in warmup_ips:
                progress = self.warmup_scheduler.get_warmup_progress(ip_address)
                if not progress:
                    continue

                # Get current daily limit from scheduler
                daily_limit = self.warmup_scheduler.get_current_daily_limit(ip_address)

                # Calculate utilization percentage
                utilization_percent = (
                    (progress.daily_sent_count / daily_limit * 100)
                    if daily_limit > 0
                    else 0
                )

                ip_metrics = {
                    "status": progress.status.value.lower(),
                    "stage": progress.current_stage,
                    "daily_sent": progress.daily_sent_count,
                    "daily_limit": daily_limit,
                    "utilization_percent": utilization_percent,
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

                # Add integration service metrics if available
                if self.integration_service:
                    try:
                        rates = self.integration_service.get_current_rates(ip_address)
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
                    except Exception:
                        # Integration service error - continue without rates
                        pass

                metrics["warmup_metrics"][ip_address] = ip_metrics

                # Update system health counters
                total_stage += progress.current_stage
                total_emails += progress.total_sent_count

                if progress.status == WarmupStatus.IN_PROGRESS:
                    metrics["system_health"]["active_warmups"] += 1
                elif progress.status == WarmupStatus.COMPLETED:
                    metrics["system_health"]["completed_warmups"] += 1
                elif progress.status == WarmupStatus.PAUSED:
                    metrics["system_health"]["paused_warmups"] += 1

            # Calculate averages
            if warmup_ips:
                metrics["system_health"]["avg_stage"] = total_stage / len(warmup_ips)
            metrics["system_health"]["total_emails_sent"] = total_emails

            return metrics

        except Exception as e:
            return {"error": str(e)}

    def generate_metrics_report(self) -> str:
        """Generate a formatted metrics report."""
        metrics = self.collect_all_metrics()

        if "error" in metrics:
            return f"Error generating metrics report: {metrics['error']}"

        report = []
        report.append("=== SendGrid Warmup Metrics Report ===")
        report.append(f"Generated: {metrics['timestamp']}")
        report.append("")

        # System health summary
        health = metrics["system_health"]
        report.append("System Health:")
        report.append(f"  Total IPs: {health['total_ips']}")
        report.append(f"  Active Warmups: {health['active_warmups']}")
        report.append(f"  Completed Warmups: {health['completed_warmups']}")
        report.append(f"  Paused Warmups: {health['paused_warmups']}")
        report.append(f"  Average Utilization: {health['avg_stage']:.1f}%")
        report.append("")

        # Individual IP metrics
        report.append("IP Details:")
        for ip, data in metrics["warmup_metrics"].items():
            report.append(f"  {ip}:")
            report.append(f"    Status: {data['status']}")
            report.append(f"    Stage: {data['stage']}")
            report.append(
                f"    Daily Usage: {data['daily_sent']}/{data['daily_limit']} ({data['utilization_percent']:.1f}%)"
            )

            if "bounce_rate" in data:
                report.append(f"    Bounce Rate: {data['bounce_rate']:.3f}")
            if "spam_rate" in data:
                report.append(f"    Spam Rate: {data['spam_rate']:.3f}")
            if "deliverability_rate" in data:
                report.append(f"    Deliverability: {data['deliverability_rate']:.3f}")

            if data["is_paused"]:
                report.append("    PAUSED")

            report.append("")

        return "\n".join(report)


# Convenience functions
def create_warmup_metrics_collector(warmup_scheduler=None, integration_service=None):
    """Create warmup metrics collector instance."""
    return SendGridWarmupMetricsCollector(warmup_scheduler, integration_service)


def record_warmup_event(event_type: str, ip_address: str, **kwargs):
    """Convenience function to record warmup events."""
    if not METRICS_AVAILABLE:
        return

    try:
        if event_type == "started":
            WARMUP_STARTED.labels(ip_address=ip_address).inc()
        elif event_type == "completed":
            duration = kwargs.get("duration_days", "unknown")
            WARMUP_COMPLETED.labels(
                ip_address=ip_address, duration_days=str(duration)
            ).inc()
        elif event_type == "paused":
            reason = kwargs.get("reason", "unknown")
            WARMUP_PAUSED.labels(ip_address=ip_address, reason=reason).inc()
        elif event_type == "resumed":
            WARMUP_RESUMED.labels(ip_address=ip_address).inc()
        elif event_type == "stage_advanced":
            from_stage = kwargs.get("from_stage", "unknown")
            to_stage = kwargs.get("to_stage", "unknown")
            WARMUP_STAGE_ADVANCED.labels(
                ip_address=ip_address,
                from_stage=str(from_stage),
                to_stage=str(to_stage),
            ).inc()
        elif event_type == "threshold_breach":
            threshold_type = kwargs.get("threshold_type", "unknown")
            severity = kwargs.get("severity", "unknown")
            WARMUP_THRESHOLD_BREACHES.labels(
                ip_address=ip_address, threshold_type=threshold_type, severity=severity
            ).inc()

    except Exception as e:
        logger.error(
            f"Error recording warmup event {event_type} for IP {ip_address}: {e}"
        )
