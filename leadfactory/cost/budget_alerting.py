"""
Budget Alerting and Notification System

This module provides comprehensive alerting and notification capabilities for the
budget monitoring system. It supports multiple notification channels including
email, Slack, webhooks, and logging. The system includes rate limiting to prevent
alert storms and template-based messaging for consistent communication.

Features:
- Multi-channel notifications (email, Slack, webhooks, logs)
- Template-based alert messages
- Rate limiting to prevent alert storms
- Alert aggregation and batching
- Configurable alert thresholds and escalation
- Integration with budget configuration system
- Async and sync notification support
"""

import asyncio
import json
import logging
import smtplib
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import urljoin

import requests

from leadfactory.cost.budget_config import AlertLevel, get_budget_config
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationChannel(Enum):
    """Supported notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"
    CONSOLE = "console"


class AlertType(Enum):
    """Types of budget alerts."""

    THRESHOLD_WARNING = "threshold_warning"
    THRESHOLD_CRITICAL = "threshold_critical"
    BUDGET_EXCEEDED = "budget_exceeded"
    THROTTLING_ACTIVATED = "throttling_activated"
    SERVICE_DEGRADED = "service_degraded"
    RATE_LIMIT_HIT = "rate_limit_hit"
    COST_SPIKE = "cost_spike"
    DAILY_SUMMARY = "daily_summary"


@dataclass
class AlertMessage:
    """Represents an alert message."""

    alert_type: AlertType
    severity: AlertLevel
    title: str
    message: str
    service: str
    model: Optional[str] = None
    endpoint: Optional[str] = None
    current_cost: Optional[float] = None
    budget_limit: Optional[float] = None
    utilization_percentage: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert message to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["alert_type"] = self.alert_type.value
        data["severity"] = self.severity.value
        return data


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""

    email_enabled: bool = False
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: List[str] = field(default_factory=list)

    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_username: str = "BudgetGuard"

    webhook_enabled: bool = False
    webhook_urls: List[str] = field(default_factory=list)
    webhook_timeout: int = 10

    log_enabled: bool = True
    console_enabled: bool = False

    # Rate limiting
    rate_limit_window_minutes: int = 15
    max_alerts_per_window: int = 10

    # Alert aggregation
    aggregation_enabled: bool = True
    aggregation_window_minutes: int = 5


class AlertRateLimiter:
    """Rate limiter for alerts to prevent spam."""

    def __init__(self, window_minutes: int = 15, max_alerts: int = 10):
        self.window_minutes = window_minutes
        self.max_alerts = max_alerts
        self.alert_history: Dict[str, List[datetime]] = {}
        self.lock = Lock()

    def should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent based on rate limits."""
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=self.window_minutes)

            # Clean old alerts
            if alert_key in self.alert_history:
                self.alert_history[alert_key] = [
                    timestamp
                    for timestamp in self.alert_history[alert_key]
                    if timestamp > cutoff
                ]
            else:
                self.alert_history[alert_key] = []

            # Check if under limit
            if len(self.alert_history[alert_key]) < self.max_alerts:
                self.alert_history[alert_key].append(now)
                return True

            return False

    def get_alert_count(self, alert_key: str) -> int:
        """Get current alert count for a key."""
        with self.lock:
            return len(self.alert_history.get(alert_key, []))


class AlertAggregator:
    """Aggregates similar alerts to reduce noise."""

    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes
        self.pending_alerts: Dict[str, List[AlertMessage]] = {}
        self.lock = Lock()

    def add_alert(self, alert: AlertMessage) -> Optional[List[AlertMessage]]:
        """Add alert to aggregation. Returns alerts to send if window expired."""
        with self.lock:
            # Create aggregation key
            agg_key = f"{alert.alert_type.value}:{alert.service}:{alert.model or 'all'}"

            if agg_key not in self.pending_alerts:
                self.pending_alerts[agg_key] = []

            self.pending_alerts[agg_key].append(alert)

            # Check if we should flush this group
            oldest_alert = self.pending_alerts[agg_key][0]
            if datetime.now() - oldest_alert.timestamp > timedelta(
                minutes=self.window_minutes
            ):
                alerts_to_send = self.pending_alerts[agg_key].copy()
                del self.pending_alerts[agg_key]
                return alerts_to_send

            return None

    def flush_all(self) -> Dict[str, List[AlertMessage]]:
        """Flush all pending alerts."""
        with self.lock:
            result = self.pending_alerts.copy()
            self.pending_alerts.clear()
            return result


class MessageTemplates:
    """Templates for alert messages."""

    @staticmethod
    def threshold_warning(alert: AlertMessage) -> Dict[str, str]:
        """Template for threshold warning alerts."""
        utilization = alert.utilization_percentage or 0
        return {
            "subject": f"Budget Warning: {alert.service} at {utilization:.1f}% utilization",
            "text": f"""
Budget Warning Alert

Service: {alert.service}
Model: {alert.model or 'All models'}
Current Utilization: {utilization:.1f}%
Current Cost: ${alert.current_cost:.2f}
Budget Limit: ${alert.budget_limit:.2f}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

This is a warning that your budget utilization is approaching the configured threshold.
Please monitor your usage to avoid service disruption.
            """.strip(),
            "html": f"""
<h2>Budget Warning Alert</h2>
<table>
    <tr><td><strong>Service:</strong></td><td>{alert.service}</td></tr>
    <tr><td><strong>Model:</strong></td><td>{alert.model or 'All models'}</td></tr>
    <tr><td><strong>Current Utilization:</strong></td><td>{utilization:.1f}%</td></tr>
    <tr><td><strong>Current Cost:</strong></td><td>${alert.current_cost:.2f}</td></tr>
    <tr><td><strong>Budget Limit:</strong></td><td>${alert.budget_limit:.2f}</td></tr>
    <tr><td><strong>Timestamp:</strong></td><td>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
</table>
<p>This is a warning that your budget utilization is approaching the configured threshold.</p>
<p>Please monitor your usage to avoid service disruption.</p>
            """.strip(),
        }

    @staticmethod
    def budget_exceeded(alert: AlertMessage) -> Dict[str, str]:
        """Template for budget exceeded alerts."""
        utilization = alert.utilization_percentage or 0
        return {
            "subject": f"CRITICAL: Budget Exceeded for {alert.service}",
            "text": f"""
CRITICAL BUDGET ALERT

Service: {alert.service}
Model: {alert.model or 'All models'}
Current Utilization: {utilization:.1f}%
Current Cost: ${alert.current_cost:.2f}
Budget Limit: ${alert.budget_limit:.2f}
Overage: ${(alert.current_cost or 0) - (alert.budget_limit or 0):.2f}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

IMMEDIATE ACTION REQUIRED: Your budget has been exceeded.
Services may be throttled or blocked to prevent further overage.
            """.strip(),
            "html": f"""
<h2 style="color: red;">CRITICAL BUDGET ALERT</h2>
<table>
    <tr><td><strong>Service:</strong></td><td>{alert.service}</td></tr>
    <tr><td><strong>Model:</strong></td><td>{alert.model or 'All models'}</td></tr>
    <tr><td><strong>Current Utilization:</strong></td><td style="color: red;">{utilization:.1f}%</td></tr>
    <tr><td><strong>Current Cost:</strong></td><td style="color: red;">${alert.current_cost:.2f}</td></tr>
    <tr><td><strong>Budget Limit:</strong></td><td>${alert.budget_limit:.2f}</td></tr>
    <tr><td><strong>Overage:</strong></td><td style="color: red;">${(alert.current_cost or 0) - (alert.budget_limit or 0):.2f}</td></tr>
    <tr><td><strong>Timestamp:</strong></td><td>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
</table>
<p style="color: red;"><strong>IMMEDIATE ACTION REQUIRED:</strong> Your budget has been exceeded.</p>
<p>Services may be throttled or blocked to prevent further overage.</p>
            """.strip(),
        }

    @staticmethod
    def throttling_activated(alert: AlertMessage) -> Dict[str, str]:
        """Template for throttling activation alerts."""
        return {
            "subject": f"Throttling Activated: {alert.service}",
            "text": f"""
Throttling Activation Alert

Service: {alert.service}
Model: {alert.model or 'All models'}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Throttling has been activated for this service due to budget constraints.
Requests may be delayed, rejected, or downgraded to maintain budget compliance.

Details: {alert.message}
            """.strip(),
            "html": f"""
<h2>Throttling Activation Alert</h2>
<table>
    <tr><td><strong>Service:</strong></td><td>{alert.service}</td></tr>
    <tr><td><strong>Model:</strong></td><td>{alert.model or 'All models'}</td></tr>
    <tr><td><strong>Timestamp:</strong></td><td>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
</table>
<p>Throttling has been activated for this service due to budget constraints.</p>
<p>Requests may be delayed, rejected, or downgraded to maintain budget compliance.</p>
<p><strong>Details:</strong> {alert.message}</p>
            """.strip(),
        }


class BudgetNotificationService:
    """Main notification service for budget alerts."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize the notification service."""
        self.config = config or NotificationConfig()
        self.rate_limiter = AlertRateLimiter(
            window_minutes=self.config.rate_limit_window_minutes,
            max_alerts=self.config.max_alerts_per_window,
        )
        self.aggregator = (
            AlertAggregator(window_minutes=self.config.aggregation_window_minutes)
            if self.config.aggregation_enabled
            else None
        )
        self.templates = MessageTemplates()

        # Load configuration from environment if available
        self._load_config_from_environment()

    def _load_config_from_environment(self):
        """Load configuration from environment variables."""
        import os

        # Email configuration
        if os.getenv("BUDGET_ALERT_EMAIL_ENABLED", "").lower() == "true":
            self.config.email_enabled = True
            self.config.email_smtp_host = os.getenv("BUDGET_ALERT_SMTP_HOST")
            self.config.email_smtp_port = int(
                os.getenv("BUDGET_ALERT_SMTP_PORT", "587")
            )
            self.config.email_username = os.getenv("BUDGET_ALERT_EMAIL_USERNAME")
            self.config.email_password = os.getenv("BUDGET_ALERT_EMAIL_PASSWORD")
            self.config.email_from = os.getenv("BUDGET_ALERT_EMAIL_FROM")
            email_to = os.getenv("BUDGET_ALERT_EMAIL_TO", "")
            if email_to:
                self.config.email_to = [email.strip() for email in email_to.split(",")]

        # Slack configuration
        if os.getenv("BUDGET_ALERT_SLACK_ENABLED", "").lower() == "true":
            self.config.slack_enabled = True
            self.config.slack_webhook_url = os.getenv("BUDGET_ALERT_SLACK_WEBHOOK_URL")
            self.config.slack_channel = os.getenv("BUDGET_ALERT_SLACK_CHANNEL")
            self.config.slack_username = os.getenv(
                "BUDGET_ALERT_SLACK_USERNAME", "BudgetGuard"
            )

        # Webhook configuration
        if os.getenv("BUDGET_ALERT_WEBHOOK_ENABLED", "").lower() == "true":
            self.config.webhook_enabled = True
            webhook_urls = os.getenv("BUDGET_ALERT_WEBHOOK_URLS", "")
            if webhook_urls:
                self.config.webhook_urls = [
                    url.strip() for url in webhook_urls.split(",")
                ]

    def send_alert(self, alert: AlertMessage) -> bool:
        """Send an alert through configured channels."""
        try:
            # Check rate limiting
            alert_key = (
                f"{alert.alert_type.value}:{alert.service}:{alert.model or 'all'}"
            )
            if not self.rate_limiter.should_send_alert(alert_key):
                logger.warning(f"Alert rate limited: {alert_key}")
                return False

            # Handle aggregation
            if self.aggregator:
                aggregated_alerts = self.aggregator.add_alert(alert)
                if aggregated_alerts:
                    return self._send_aggregated_alerts(aggregated_alerts)
                else:
                    # Alert is being aggregated, don't send yet
                    return True
            else:
                return self._send_single_alert(alert)

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def _send_single_alert(self, alert: AlertMessage) -> bool:
        """Send a single alert through all configured channels."""
        success = True

        if self.config.log_enabled:
            success &= self._send_log_alert(alert)

        if self.config.console_enabled:
            success &= self._send_console_alert(alert)

        if self.config.email_enabled:
            success &= self._send_email_alert(alert)

        if self.config.slack_enabled:
            success &= self._send_slack_alert(alert)

        if self.config.webhook_enabled:
            success &= self._send_webhook_alert(alert)

        return success

    def _send_aggregated_alerts(self, alerts: List[AlertMessage]) -> bool:
        """Send aggregated alerts."""
        if not alerts:
            return True

        # Create summary alert
        first_alert = alerts[0]
        summary_alert = AlertMessage(
            alert_type=first_alert.alert_type,
            severity=max(alert.severity for alert in alerts),
            title=f"Aggregated Alert: {len(alerts)} {first_alert.alert_type.value} alerts",
            message=f"Multiple {first_alert.alert_type.value} alerts occurred:\n"
            + "\n".join(
                f"- {alert.service}/{alert.model or 'all'}: {alert.message}"
                for alert in alerts
            ),
            service=first_alert.service,
            model=first_alert.model,
            endpoint=first_alert.endpoint,
            metadata={
                "aggregated_count": len(alerts),
                "alerts": [alert.to_dict() for alert in alerts],
            },
        )

        return self._send_single_alert(summary_alert)

    def _send_log_alert(self, alert: AlertMessage) -> bool:
        """Send alert to logger."""
        try:
            log_level = {
                AlertLevel.WARNING: logging.WARNING,
                AlertLevel.CRITICAL: logging.ERROR,
            }.get(alert.severity, logging.WARNING)

            logger.log(log_level, f"Budget Alert: {alert.title} - {alert.message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send log alert: {e}")
            return False

    def _send_console_alert(self, alert: AlertMessage) -> bool:
        """Send alert to console."""
        try:
            print(
                f"[{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {alert.severity.value.upper()}: {alert.title}"
            )
            print(f"  {alert.message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send console alert: {e}")
            return False

    def _send_email_alert(self, alert: AlertMessage) -> bool:
        """Send alert via email."""
        try:
            if not all(
                [
                    self.config.email_smtp_host,
                    self.config.email_username,
                    self.config.email_password,
                    self.config.email_from,
                    self.config.email_to,
                ]
            ):
                logger.warning("Email configuration incomplete, skipping email alert")
                return False

            # Get message template
            template_func = getattr(self.templates, alert.alert_type.value, None)
            if template_func:
                template = template_func(alert)
            else:
                template = {
                    "subject": alert.title,
                    "text": alert.message,
                    "html": f"<p>{alert.message}</p>",
                }

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = template["subject"]
            msg["From"] = self.config.email_from
            msg["To"] = ", ".join(self.config.email_to)

            # Add text and HTML parts
            text_part = MIMEText(template["text"], "plain")
            html_part = MIMEText(template["html"], "html")
            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(
                self.config.email_smtp_host, self.config.email_smtp_port
            ) as server:
                server.starttls()
                server.login(self.config.email_username, self.config.email_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {alert.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _send_slack_alert(self, alert: AlertMessage) -> bool:
        """Send alert to Slack."""
        try:
            if not self.config.slack_webhook_url:
                logger.warning("Slack webhook URL not configured, skipping Slack alert")
                return False

            # Create Slack message
            color = {AlertLevel.WARNING: "warning", AlertLevel.CRITICAL: "danger"}.get(
                alert.severity, "good"
            )

            payload = {
                "username": self.config.slack_username,
                "channel": self.config.slack_channel,
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.message,
                        "fields": [
                            {"title": "Service", "value": alert.service, "short": True},
                            {
                                "title": "Model",
                                "value": alert.model or "All",
                                "short": True,
                            },
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Timestamp",
                                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True,
                            },
                        ],
                    }
                ],
            }

            if alert.current_cost is not None and alert.budget_limit is not None:
                payload["attachments"][0]["fields"].extend(
                    [
                        {
                            "title": "Current Cost",
                            "value": f"${alert.current_cost:.2f}",
                            "short": True,
                        },
                        {
                            "title": "Budget Limit",
                            "value": f"${alert.budget_limit:.2f}",
                            "short": True,
                        },
                    ]
                )

            response = requests.post(
                self.config.slack_webhook_url, json=payload, timeout=10
            )
            response.raise_for_status()

            logger.info(f"Slack alert sent: {alert.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _send_webhook_alert(self, alert: AlertMessage) -> bool:
        """Send alert to configured webhooks."""
        success = True

        for webhook_url in self.config.webhook_urls:
            try:
                payload = alert.to_dict()
                response = requests.post(
                    webhook_url, json=payload, timeout=self.config.webhook_timeout
                )
                response.raise_for_status()
                logger.info(f"Webhook alert sent to {webhook_url}: {alert.title}")

            except Exception as e:
                logger.error(f"Failed to send webhook alert to {webhook_url}: {e}")
                success = False

        return success

    async def send_alert_async(self, alert: AlertMessage) -> bool:
        """Send alert asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_alert, alert)

    def flush_pending_alerts(self) -> bool:
        """Flush all pending aggregated alerts."""
        if not self.aggregator:
            return True

        pending_alerts = self.aggregator.flush_all()
        success = True

        for alert_group in pending_alerts.values():
            if alert_group:
                success &= self._send_aggregated_alerts(alert_group)

        return success


# Global notification service instance
_notification_service: Optional[BudgetNotificationService] = None


def get_notification_service() -> BudgetNotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = BudgetNotificationService()
    return _notification_service


def reset_notification_service():
    """Reset the global notification service (for testing)."""
    global _notification_service
    _notification_service = None


def send_budget_alert(
    alert_type: AlertType,
    severity: AlertLevel,
    title: str,
    message: str,
    service: str,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    current_cost: Optional[float] = None,
    budget_limit: Optional[float] = None,
    utilization_percentage: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Convenience function to send a budget alert."""
    alert = AlertMessage(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        service=service,
        model=model,
        endpoint=endpoint,
        current_cost=current_cost,
        budget_limit=budget_limit,
        utilization_percentage=utilization_percentage,
        metadata=metadata or {},
    )

    return get_notification_service().send_alert(alert)


async def send_budget_alert_async(
    alert_type: AlertType,
    severity: AlertLevel,
    title: str,
    message: str,
    service: str,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    current_cost: Optional[float] = None,
    budget_limit: Optional[float] = None,
    utilization_percentage: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Convenience function to send a budget alert asynchronously."""
    alert = AlertMessage(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        service=service,
        model=model,
        endpoint=endpoint,
        current_cost=current_cost,
        budget_limit=budget_limit,
        utilization_percentage=utilization_percentage,
        metadata=metadata or {},
    )

    return await get_notification_service().send_alert_async(alert)
