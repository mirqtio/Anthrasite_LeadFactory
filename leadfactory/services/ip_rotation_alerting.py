"""
IP Rotation Alerting and Monitoring System

This module provides comprehensive alerting, monitoring, and dashboard capabilities
for the IP rotation system. It includes real-time notifications, metrics collection,
and visualization components.
"""

import asyncio
import json
import logging
import smtplib
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import requests

# Import logging with fallback
try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(Enum):
    """Types of alerts."""

    ROTATION_EXECUTED = "rotation_executed"
    THRESHOLD_BREACH = "threshold_breach"
    IP_DISABLED = "ip_disabled"
    POOL_EXHAUSTED = "pool_exhausted"
    SYSTEM_ERROR = "system_error"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    PERFORMANCE_DEGRADATION = "performance_degradation"


@dataclass
class Alert:
    """Represents an alert event."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    metadata: dict[str, Any]
    alert_id: str = ""

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = f"{self.alert_type.value}_{int(self.timestamp.timestamp())}"


@dataclass
class AlertingConfig:
    """Configuration for the alerting system."""

    # Email settings
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    admin_emails: list[str] = None

    # Webhook settings
    webhook_urls: list[str] = None
    webhook_timeout: int = 10

    # Slack settings
    slack_webhook_url: str = ""
    slack_channel: str = "#alerts"

    # Alert throttling
    throttle_window_minutes: int = 15
    max_alerts_per_window: int = 10

    # Severity thresholds
    email_severity_threshold: AlertSeverity = AlertSeverity.WARNING
    webhook_severity_threshold: AlertSeverity = AlertSeverity.CRITICAL

    def __post_init__(self):
        if self.admin_emails is None:
            self.admin_emails = []
        if self.webhook_urls is None:
            self.webhook_urls = []


class CircuitBreaker:
    """Circuit breaker for emergency situations."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.critical(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Check if operations can be executed."""
        if self.state == "closed":
            return True

        if self.state == "open":
            if (
                self.last_failure_time
                and datetime.now() - self.last_failure_time
                > timedelta(seconds=self.recovery_timeout)
            ):
                self.state = "half-open"
                logger.info("Circuit breaker moved to half-open state")
                return True
            return False

        # half-open state
        return True

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "can_execute": self.can_execute(),
        }


class IPRotationAlerting:
    """Comprehensive alerting system for IP rotation."""

    def __init__(self, config: AlertingConfig = None):
        self.config = config or AlertingConfig()
        self.alert_history: list[Alert] = []
        self.alert_counts: dict[str, int] = {}
        self.last_alert_window = datetime.now()
        self.circuit_breaker = CircuitBreaker()

        # Metrics storage
        self.metrics = {
            "total_rotations": 0,
            "total_alerts": 0,
            "alerts_by_type": {},
            "alerts_by_severity": {},
            "last_rotation_time": None,
            "system_health": "healthy",
        }

        logger.info("IP rotation alerting system initialized")

    def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        metadata: dict[str, Any] = None,
    ) -> bool:
        """Send an alert through configured channels."""
        if metadata is None:
            metadata = {}

        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata,
        )

        # Check throttling
        if not self._should_send_alert(alert):
            logger.debug(f"Alert throttled: {alert.alert_id}")
            return False

        self.alert_history.append(alert)
        self._update_metrics(alert)

        # Send through configured channels
        success = True
        try:
            if severity.value in [
                s.value
                for s in [
                    AlertSeverity.WARNING,
                    AlertSeverity.CRITICAL,
                    AlertSeverity.EMERGENCY,
                ]
            ]:
                if self.config.admin_emails and severity.value in [
                    s.value for s in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
                ]:
                    self._send_email_alert(alert)

                if self.config.webhook_urls and severity.value in [
                    s.value for s in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
                ]:
                    self._send_webhook_alerts(alert)

                if self.config.slack_webhook_url:
                    self._send_slack_alert(alert)

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            success = False

        logger.info(
            f"Alert sent: {alert.alert_type.value} - {alert.severity.value} - {message}"
        )
        return success

    def _should_send_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent based on throttling rules."""
        now = datetime.now()

        # Reset window if needed
        if now - self.last_alert_window > timedelta(
            minutes=self.config.throttle_window_minutes
        ):
            self.alert_counts.clear()
            self.last_alert_window = now

        # Check throttling
        alert_key = f"{alert.alert_type.value}_{alert.severity.value}"
        current_count = self.alert_counts.get(alert_key, 0)

        if current_count >= self.config.max_alerts_per_window:
            return False

        self.alert_counts[alert_key] = current_count + 1
        return True

    def _update_metrics(self, alert: Alert):
        """Update internal metrics."""
        self.metrics["total_alerts"] += 1

        # Update by type
        alert_type = alert.alert_type.value
        self.metrics["alerts_by_type"][alert_type] = (
            self.metrics["alerts_by_type"].get(alert_type, 0) + 1
        )

        # Update by severity
        severity = alert.severity.value
        self.metrics["alerts_by_severity"][severity] = (
            self.metrics["alerts_by_severity"].get(severity, 0) + 1
        )

        # Update system health
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            self.metrics["system_health"] = "degraded"
        elif alert.severity == AlertSeverity.WARNING:
            self.metrics["system_health"] = "warning"

    def _send_email_alert(self, alert: Alert):
        """Send email alert."""
        if not self.config.admin_emails:
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_username
            msg["To"] = ", ".join(self.config.admin_emails)
            msg["Subject"] = (
                f"[{alert.severity.value.upper()}] IP Rotation Alert: {alert.alert_type.value}"
            )

            body = f"""
            Alert Details:
            - Type: {alert.alert_type.value}
            - Severity: {alert.severity.value}
            - Time: {alert.timestamp.isoformat()}
            - Message: {alert.message}

            Metadata:
            {json.dumps(alert.metadata, indent=2)}

            Alert ID: {alert.alert_id}
            """

            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            if self.config.smtp_use_tls:
                server.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)

            server.send_message(msg)
            server.quit()

            logger.debug(f"Email alert sent for {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def _send_webhook_alerts(self, alert: Alert):
        """Send webhook alerts."""
        payload = {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type.value,
            "severity": alert.severity.value,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata,
        }

        for webhook_url in self.config.webhook_urls:
            try:
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=self.config.webhook_timeout,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.debug(f"Webhook alert sent to {webhook_url}")

            except Exception as e:
                logger.error(f"Failed to send webhook alert to {webhook_url}: {e}")

    def _send_slack_alert(self, alert: Alert):
        """Send Slack alert."""
        if not self.config.slack_webhook_url:
            return

        # Color coding by severity
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9500",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#8b0000",
        }

        payload = {
            "channel": self.config.slack_channel,
            "username": "IP Rotation Monitor",
            "icon_emoji": ":warning:",
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#36a64f"),
                    "title": f"{alert.severity.value.upper()}: {alert.alert_type.value}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Alert ID", "value": alert.alert_id, "short": True},
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.isoformat(),
                            "short": True,
                        },
                    ],
                    "footer": "IP Rotation System",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ],
        }

        try:
            response = requests.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=self.config.webhook_timeout,
            )
            response.raise_for_status()
            logger.debug("Slack alert sent")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def record_rotation(self, from_ip: str, to_ip: str, reason: str):
        """Record a rotation event."""
        self.metrics["total_rotations"] += 1
        self.metrics["last_rotation_time"] = datetime.now().isoformat()

        self.send_alert(
            AlertType.ROTATION_EXECUTED,
            AlertSeverity.INFO,
            f"IP rotation executed: {from_ip} -> {to_ip}",
            metadata={"from_ip": from_ip, "to_ip": to_ip, "reason": reason},
        )

    def record_threshold_breach(self, ip_address: str, threshold: float, actual: float):
        """Record a threshold breach."""
        self.send_alert(
            AlertType.THRESHOLD_BREACH,
            AlertSeverity.WARNING,
            f"Bounce threshold breached for {ip_address}: {actual:.2%} > {threshold:.2%}",
            metadata={
                "ip_address": ip_address,
                "threshold": threshold,
                "actual_rate": actual,
            },
        )

    def record_ip_disabled(self, ip_address: str, reason: str):
        """Record an IP being disabled."""
        self.send_alert(
            AlertType.IP_DISABLED,
            AlertSeverity.CRITICAL,
            f"IP {ip_address} has been disabled: {reason}",
            metadata={"ip_address": ip_address, "reason": reason},
        )

    def record_pool_exhausted(self):
        """Record pool exhaustion."""
        self.send_alert(
            AlertType.POOL_EXHAUSTED,
            AlertSeverity.EMERGENCY,
            "No available IPs in rotation pool",
            metadata={},
        )

    def record_system_error(self, error: str, context: dict[str, Any] = None):
        """Record a system error."""
        self.circuit_breaker.record_failure()

        self.send_alert(
            AlertType.SYSTEM_ERROR,
            AlertSeverity.CRITICAL,
            f"System error: {error}",
            metadata={"error": error, "context": context or {}},
        )

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for dashboard visualization."""
        recent_alerts = [
            asdict(alert) for alert in self.alert_history[-50:]  # Last 50 alerts
        ]

        return {
            "metrics": self.metrics,
            "recent_alerts": recent_alerts,
            "circuit_breaker_status": self.circuit_breaker.get_status(),
            "alert_counts": self.alert_counts,
            "system_status": {
                "health": self.metrics["system_health"],
                "last_rotation": self.metrics["last_rotation_time"],
                "total_rotations": self.metrics["total_rotations"],
                "total_alerts": self.metrics["total_alerts"],
            },
        }

    def cleanup_old_alerts(self, days: int = 7) -> int:
        """Clean up old alerts."""
        cutoff_time = datetime.now() - timedelta(days=days)
        original_count = len(self.alert_history)

        self.alert_history = [
            alert for alert in self.alert_history if alert.timestamp > cutoff_time
        ]

        removed_count = original_count - len(self.alert_history)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old alerts")

        return removed_count

    def get_alert_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get alert summary for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [
            alert for alert in self.alert_history if alert.timestamp > cutoff_time
        ]

        summary = {
            "total_alerts": len(recent_alerts),
            "by_severity": {},
            "by_type": {},
            "time_period_hours": hours,
        }

        for alert in recent_alerts:
            # Count by severity
            severity = alert.severity.value
            summary["by_severity"][severity] = (
                summary["by_severity"].get(severity, 0) + 1
            )

            # Count by type
            alert_type = alert.alert_type.value
            summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1

        return summary
