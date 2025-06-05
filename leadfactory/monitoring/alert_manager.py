"""
Alert Manager for Purchase Metrics
=================================

This module implements alerting for purchase metrics anomalies, threshold violations,
and business critical events. It provides flexible alert configuration and multiple
notification channels.
"""

import json
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import requests

from leadfactory.monitoring.metrics_aggregator import (
    AggregationPeriod,
    MetricsAggregator,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""

    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    TREND = "trend"
    SYSTEM = "system"


@dataclass
class AlertRule:
    """Configuration for an alert rule."""

    name: str
    description: str
    alert_type: AlertType
    severity: AlertSeverity
    metric_name: str
    condition: str  # e.g., "> 100", "< 0.05", "change > 50%"
    threshold_value: Union[float, int]
    comparison_period: Optional[AggregationPeriod] = None
    enabled: bool = True
    cooldown_minutes: int = 60
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate alert rule configuration."""
        if not self.condition or self.threshold_value is None:
            raise ValueError("Alert rule must have condition and threshold_value")


@dataclass
class Alert:
    """An active alert instance."""

    rule_name: str
    severity: AlertSeverity
    message: str
    current_value: Union[float, int]
    threshold_value: Union[float, int]
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class NotificationChannel:
    """Base class for notification channels."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = get_logger(f"{__name__}.{name}")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert notification. Should be implemented by subclasses."""
        raise NotImplementedError

    def test_connection(self) -> bool:
        """Test if notification channel is working."""
        raise NotImplementedError


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            smtp_server = self.config.get("smtp_server")
            smtp_port = self.config.get("smtp_port", 587)
            username = self.config.get("username")
            password = self.config.get("password")
            recipients = self.config.get("recipients", [])

            if not all([smtp_server, username, password, recipients]):
                self.logger.error("Email configuration incomplete")
                return False

            # Create message
            msg = MIMEMultipart()
            msg["From"] = username
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.rule_name}"

            # Email body
            body = f"""
Purchase Metrics Alert

Rule: {alert.rule_name}
Severity: {alert.severity.value.upper()}
Timestamp: {alert.timestamp}

Message: {alert.message}

Current Value: {alert.current_value}
Threshold: {alert.threshold_value}

Metadata:
{json.dumps(alert.metadata, indent=2)}

--
LeadFactory Monitoring System
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

            self.logger.info(f"Sent email alert for {alert.rule_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False

    def test_connection(self) -> bool:
        """Test email connection."""
        try:
            smtp_server = self.config.get("smtp_server")
            smtp_port = self.config.get("smtp_port", 587)
            username = self.config.get("username")
            password = self.config.get("password")

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)

            return True
        except Exception as e:
            self.logger.error(f"Email connection test failed: {e}")
            return False


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel."""

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via Slack webhook."""
        try:
            webhook_url = self.config.get("webhook_url")
            if not webhook_url:
                self.logger.error("Slack webhook URL not configured")
                return False

            # Create Slack message
            color_map = {
                AlertSeverity.LOW: "good",
                AlertSeverity.MEDIUM: "warning",
                AlertSeverity.HIGH: "danger",
                AlertSeverity.CRITICAL: "danger",
            }

            slack_message = {
                "text": f"Purchase Metrics Alert: {alert.rule_name}",
                "attachments": [
                    {
                        "color": color_map.get(alert.severity, "warning"),
                        "fields": [
                            {"title": "Rule", "value": alert.rule_name, "short": True},
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True,
                            },
                            {
                                "title": "Current Value",
                                "value": str(alert.current_value),
                                "short": True,
                            },
                            {
                                "title": "Threshold",
                                "value": str(alert.threshold_value),
                                "short": True,
                            },
                            {
                                "title": "Message",
                                "value": alert.message,
                                "short": False,
                            },
                        ],
                        "footer": "LeadFactory Monitoring",
                        "ts": int(alert.timestamp.timestamp()),
                    }
                ],
            }

            response = requests.post(webhook_url, json=slack_message, timeout=10)
            response.raise_for_status()

            self.logger.info(f"Sent Slack alert for {alert.rule_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Slack webhook connection."""
        try:
            webhook_url = self.config.get("webhook_url")
            test_message = {"text": "LeadFactory monitoring test message"}

            response = requests.post(webhook_url, json=test_message, timeout=10)
            response.raise_for_status()

            return True
        except Exception as e:
            self.logger.error(f"Slack connection test failed: {e}")
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel."""

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        try:
            webhook_url = self.config.get("url")
            headers = self.config.get("headers", {})

            if not webhook_url:
                self.logger.error("Webhook URL not configured")
                return False

            payload = {
                "rule_name": alert.rule_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata,
            }

            response = requests.post(
                webhook_url, json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()

            self.logger.info(f"Sent webhook alert for {alert.rule_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            return False

    def test_connection(self) -> bool:
        """Test webhook connection."""
        try:
            webhook_url = self.config.get("url")
            headers = self.config.get("headers", {})

            test_payload = {"test": True, "timestamp": datetime.now().isoformat()}

            response = requests.post(
                webhook_url, json=test_payload, headers=headers, timeout=10
            )
            response.raise_for_status()

            return True
        except Exception as e:
            self.logger.error(f"Webhook connection test failed: {e}")
            return False


class AlertManager:
    """Purchase metrics alert manager."""

    def __init__(self, metrics_aggregator: Optional[MetricsAggregator] = None):
        """Initialize alert manager.

        Args:
            metrics_aggregator: Optional metrics aggregator instance
        """
        self.metrics_aggregator = metrics_aggregator or MetricsAggregator()
        self.logger = get_logger(f"{__name__}.AlertManager")

        self.alert_rules: dict[str, AlertRule] = {}
        self.notification_channels: dict[str, NotificationChannel] = {}
        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []
        self.last_check_times: dict[str, datetime] = {}

        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default alert rules for purchase metrics."""
        default_rules = [
            AlertRule(
                name="revenue_drop",
                description="Daily revenue dropped significantly",
                alert_type=AlertType.THRESHOLD,
                severity=AlertSeverity.HIGH,
                metric_name="total_revenue_cents",
                condition="< 50000",  # Less than $500 daily revenue
                threshold_value=50000,
                comparison_period=AggregationPeriod.DAILY,
            ),
            AlertRule(
                name="conversion_rate_low",
                description="Conversion rate is below acceptable threshold",
                alert_type=AlertType.THRESHOLD,
                severity=AlertSeverity.MEDIUM,
                metric_name="conversion_rate",
                condition="< 0.02",  # Less than 2% conversion rate
                threshold_value=0.02,
                comparison_period=AggregationPeriod.DAILY,
            ),
            AlertRule(
                name="no_purchases_6h",
                description="No purchases recorded in the last 6 hours",
                alert_type=AlertType.THRESHOLD,
                severity=AlertSeverity.MEDIUM,
                metric_name="total_purchases",
                condition="= 0",
                threshold_value=0,
                comparison_period=AggregationPeriod.HOURLY,
            ),
            AlertRule(
                name="high_refund_rate",
                description="Refund rate is unusually high",
                alert_type=AlertType.THRESHOLD,
                severity=AlertSeverity.HIGH,
                metric_name="refund_rate",
                condition="> 0.1",  # More than 10% refund rate
                threshold_value=0.1,
                comparison_period=AggregationPeriod.DAILY,
            ),
            AlertRule(
                name="stripe_fees_spike",
                description="Stripe fees percentage has spiked",
                alert_type=AlertType.ANOMALY,
                severity=AlertSeverity.LOW,
                metric_name="stripe_fee_percentage",
                condition="> 0.05",  # More than 5% in fees
                threshold_value=0.05,
                comparison_period=AggregationPeriod.DAILY,
            ),
        ]

        for rule in default_rules:
            self.add_alert_rule(rule)

    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule.

        Args:
            rule: Alert rule to add
        """
        self.alert_rules[rule.name] = rule
        self.logger.info(f"Added alert rule: {rule.name}")

    def remove_alert_rule(self, rule_name: str):
        """Remove an alert rule.

        Args:
            rule_name: Name of rule to remove
        """
        if rule_name in self.alert_rules:
            del self.alert_rules[rule_name]
            self.logger.info(f"Removed alert rule: {rule_name}")

    def add_notification_channel(self, channel: NotificationChannel):
        """Add a notification channel.

        Args:
            channel: Notification channel to add
        """
        self.notification_channels[channel.name] = channel
        self.logger.info(f"Added notification channel: {channel.name}")

    def check_alerts(self):
        """Check all alert rules and trigger alerts as needed."""
        self.logger.debug("Checking alert rules...")

        current_time = datetime.now()

        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            # Check cooldown
            last_check = self.last_check_times.get(rule_name)
            if (
                last_check
                and (current_time - last_check).total_seconds()
                < rule.cooldown_minutes * 60
            ):
                continue

            try:
                self._check_rule(rule, current_time)
                self.last_check_times[rule_name] = current_time
            except Exception as e:
                self.logger.error(f"Error checking rule {rule_name}: {e}")

    def _check_rule(self, rule: AlertRule, current_time: datetime):
        """Check a specific alert rule."""
        # Get metrics based on rule's comparison period
        period = rule.comparison_period or AggregationPeriod.HOURLY

        # Get recent metrics
        metrics = self.metrics_aggregator.get_aggregated_metrics(period, limit=24)

        if not metrics:
            self.logger.warning(f"No metrics available for rule {rule.name}")
            return

        latest_metric = metrics[0]  # Most recent

        # Extract metric value
        metric_value = self._extract_metric_value(latest_metric, rule.metric_name)

        if metric_value is None:
            self.logger.warning(
                f"Could not extract metric {rule.metric_name} for rule {rule.name}"
            )
            return

        # Evaluate condition
        alert_triggered = self._evaluate_condition(
            metric_value, rule.condition, rule.threshold_value
        )

        if alert_triggered:
            self._trigger_alert(rule, metric_value, current_time, latest_metric)
        else:
            # Check if we should resolve an existing alert
            self._resolve_alert_if_exists(rule.name)

    def _extract_metric_value(
        self, metric, metric_name: str
    ) -> Optional[Union[float, int]]:
        """Extract metric value from aggregated metric."""
        if metric_name == "total_revenue_cents":
            return metric.total_revenue_cents
        elif metric_name == "total_purchases":
            return metric.total_purchases
        elif metric_name == "conversion_rate":
            return metric.conversion_rate
        elif metric_name == "average_order_value_cents":
            return metric.average_order_value_cents
        elif metric_name == "refund_rate":
            if metric.total_purchases > 0:
                return metric.refund_count / metric.total_purchases
            return 0.0
        elif metric_name == "stripe_fee_percentage":
            if metric.total_revenue_cents > 0:
                return metric.total_stripe_fees_cents / metric.total_revenue_cents
            return 0.0
        else:
            return None

    def _evaluate_condition(
        self,
        current_value: Union[float, int],
        condition: str,
        threshold: Union[float, int],
    ) -> bool:
        """Evaluate if alert condition is met."""
        condition = condition.strip()

        if condition.startswith(">"):
            return current_value > threshold
        elif condition.startswith("<"):
            return current_value < threshold
        elif condition.startswith("="):
            return current_value == threshold
        elif condition.startswith(">="):
            return current_value >= threshold
        elif condition.startswith("<="):
            return current_value <= threshold
        else:
            self.logger.warning(f"Unknown condition: {condition}")
            return False

    def _trigger_alert(
        self,
        rule: AlertRule,
        current_value: Union[float, int],
        timestamp: datetime,
        metric_data: Any,
    ):
        """Trigger an alert for a rule."""
        # Check if alert already exists
        if rule.name in self.active_alerts:
            return

        # Create alert
        alert = Alert(
            rule_name=rule.name,
            severity=rule.severity,
            message=f"{rule.description}. Current value: {current_value}, Threshold: {rule.threshold_value}",
            current_value=current_value,
            threshold_value=rule.threshold_value,
            timestamp=timestamp,
            metadata={
                "metric_name": rule.metric_name,
                "condition": rule.condition,
                "alert_type": rule.alert_type.value,
                "comparison_period": (
                    rule.comparison_period.value if rule.comparison_period else None
                ),
                "tags": rule.tags,
            },
        )

        # Store alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)

        # Send notifications
        self._send_alert_notifications(alert)

        self.logger.warning(f"Alert triggered: {rule.name} - {alert.message}")

    def _resolve_alert_if_exists(self, rule_name: str):
        """Resolve an active alert if it exists."""
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.resolved = True
            alert.resolved_at = datetime.now()

            del self.active_alerts[rule_name]

            self.logger.info(f"Alert resolved: {rule_name}")

    def _send_alert_notifications(self, alert: Alert):
        """Send alert through all configured notification channels."""
        for channel_name, channel in self.notification_channels.items():
            try:
                success = channel.send_alert(alert)
                if success:
                    self.logger.info(f"Alert sent via {channel_name}")
                else:
                    self.logger.error(f"Failed to send alert via {channel_name}")
            except Exception as e:
                self.logger.error(f"Error sending alert via {channel_name}: {e}")

    def get_alert_status(self) -> dict[str, Any]:
        """Get current alert system status.

        Returns:
            Dictionary with alert status information
        """
        return {
            "active_alerts_count": len(self.active_alerts),
            "active_alerts": [
                {
                    "rule_name": alert.rule_name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "current_value": alert.current_value,
                }
                for alert in self.active_alerts.values()
            ],
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "notification_channels": len(self.notification_channels),
            "recent_alerts_24h": len(
                [
                    a
                    for a in self.alert_history
                    if a.timestamp > datetime.now() - timedelta(hours=24)
                ]
            ),
        }

    def test_notifications(self) -> dict[str, bool]:
        """Test all notification channels.

        Returns:
            Dictionary mapping channel names to test results
        """
        results = {}
        for channel_name, channel in self.notification_channels.items():
            try:
                results[channel_name] = channel.test_connection()
            except Exception as e:
                self.logger.error(f"Error testing {channel_name}: {e}")
                results[channel_name] = False

        return results


# Global instance
alert_manager = AlertManager()
