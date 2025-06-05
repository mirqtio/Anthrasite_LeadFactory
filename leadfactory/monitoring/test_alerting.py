"""
Test Alerting and Notification System.

Implements intelligent alerting for test failures, degradation patterns,
and early warning systems for CI pipeline health issues.
Part of Task 14: CI Pipeline Test Monitoring and Governance Framework.
"""

import asyncio
import json
import logging
import smtplib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MimeBase
from email.mime.multipart import MimeMultipart
from email.mime.text import MimeText
from typing import Any, Callable, Dict, List, Optional

from .test_monitoring import TestMetrics, TestSuiteMetrics, metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Defines an alert rule for test monitoring."""

    rule_id: str
    name: str
    description: str
    condition: str  # "pass_rate_below", "flakiness_above", "trend_degrading", etc.
    threshold: float
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True
    cooldown_minutes: int = 60  # Minimum time between similar alerts
    notification_channels: list[str] = None  # ["email", "slack", "webhook"]

    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["email"]


@dataclass
class Alert:
    """Represents a triggered alert."""

    alert_id: str
    rule_id: str
    test_id: str
    test_name: str
    test_suite: str
    severity: str
    message: str
    details: dict[str, Any]
    triggered_at: datetime
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class NotificationChannel:
    """Base configuration for notification channels."""

    channel_type: str
    config: dict[str, Any]
    enabled: bool = True


class AlertManager:
    """Manages test alerts and notifications."""

    def __init__(self, config_file: str = "alert_config.json"):
        self.config_file = config_file
        self.alert_rules: dict[str, AlertRule] = {}
        self.notification_channels: dict[str, NotificationChannel] = {}
        self.active_alerts: list[Alert] = []
        self.alert_history: list[Alert] = []
        self.last_alert_times: dict[str, datetime] = {}
        self._lock = threading.Lock()

        self._load_configuration()
        self._setup_default_rules()
        self._setup_default_channels()

    def _load_configuration(self):
        """Load alert configuration from file."""
        try:
            with open(self.config_file) as f:
                config = json.load(f)

                # Load alert rules
                for rule_data in config.get("alert_rules", []):
                    rule = AlertRule(**rule_data)
                    self.alert_rules[rule.rule_id] = rule

                # Load notification channels
                for channel_data in config.get("notification_channels", []):
                    channel = NotificationChannel(**channel_data)
                    self.notification_channels[channel.channel_type] = channel

                logger.info(
                    f"Loaded {len(self.alert_rules)} alert rules and {len(self.notification_channels)} notification channels"
                )

        except FileNotFoundError:
            logger.info("No alert configuration file found, using defaults")
        except Exception as e:
            logger.error(f"Error loading alert configuration: {e}")

    def _setup_default_rules(self):
        """Setup default alert rules if none exist."""
        if not self.alert_rules:
            default_rules = [
                AlertRule(
                    rule_id="low_pass_rate_critical",
                    name="Critical Pass Rate Drop",
                    description="Test pass rate below 50%",
                    condition="pass_rate_below",
                    threshold=0.5,
                    severity="critical",
                    cooldown_minutes=30,
                ),
                AlertRule(
                    rule_id="low_pass_rate_warning",
                    name="Low Pass Rate Warning",
                    description="Test pass rate below 80%",
                    condition="pass_rate_below",
                    threshold=0.8,
                    severity="medium",
                    cooldown_minutes=120,
                ),
                AlertRule(
                    rule_id="high_flakiness",
                    name="High Test Flakiness",
                    description="Test showing flaky behavior",
                    condition="flakiness_above",
                    threshold=0.3,
                    severity="medium",
                    cooldown_minutes=180,
                ),
                AlertRule(
                    rule_id="degrading_trend",
                    name="Degrading Test Trend",
                    description="Test performance is degrading over time",
                    condition="trend_degrading",
                    threshold=0.0,  # No numeric threshold for trend
                    severity="medium",
                    cooldown_minutes=240,
                ),
                AlertRule(
                    rule_id="test_failure_spike",
                    name="Test Failure Spike",
                    description="Multiple tests failing in same suite",
                    condition="suite_failure_spike",
                    threshold=0.3,  # 30% of tests in suite failing
                    severity="high",
                    cooldown_minutes=60,
                ),
                AlertRule(
                    rule_id="reliability_grade_f",
                    name="Test Grade F",
                    description="Test has reliability grade F",
                    condition="reliability_grade_f",
                    threshold=0.0,
                    severity="high",
                    cooldown_minutes=360,
                ),
                AlertRule(
                    rule_id="new_test_instability",
                    name="New Test Instability",
                    description="Recently added test showing instability",
                    condition="new_test_unstable",
                    threshold=0.7,  # Pass rate below 70% for new test
                    severity="medium",
                    cooldown_minutes=120,
                ),
            ]

            for rule in default_rules:
                self.alert_rules[rule.rule_id] = rule

            logger.info(f"Setup {len(default_rules)} default alert rules")

    def _setup_default_channels(self):
        """Setup default notification channels if none exist."""
        if not self.notification_channels:
            # Email channel (requires configuration)
            self.notification_channels["email"] = NotificationChannel(
                channel_type="email",
                config={
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",  # To be configured
                    "password": "",  # To be configured
                    "from_email": "",
                    "to_emails": [],
                },
                enabled=False,  # Disabled until configured
            )

            # Webhook channel for Slack/Teams/etc
            self.notification_channels["webhook"] = NotificationChannel(
                channel_type="webhook",
                config={
                    "url": "",  # To be configured
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                },
                enabled=False,  # Disabled until configured
            )

            # Log channel (always enabled)
            self.notification_channels["log"] = NotificationChannel(
                channel_type="log", config={"log_level": "WARNING"}, enabled=True
            )

    def evaluate_test_alerts(self, test_metrics: TestMetrics):
        """Evaluate a test against all alert rules."""
        alerts_triggered = []

        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue

            # Check cooldown period
            cooldown_key = f"{rule.rule_id}:{test_metrics.test_id}"
            last_alert_time = self.last_alert_times.get(cooldown_key)
            if last_alert_time:
                time_since_last = datetime.now() - last_alert_time
                if time_since_last.total_seconds() < rule.cooldown_minutes * 60:
                    continue

            # Evaluate rule condition
            triggered = self._evaluate_rule_condition(rule, test_metrics)

            if triggered:
                alert = self._create_alert(rule, test_metrics)
                alerts_triggered.append(alert)
                self.last_alert_times[cooldown_key] = datetime.now()

        return alerts_triggered

    def _evaluate_rule_condition(
        self, rule: AlertRule, test_metrics: TestMetrics
    ) -> bool:
        """Evaluate if a rule condition is met."""
        condition = rule.condition
        threshold = rule.threshold

        if condition == "pass_rate_below":
            return test_metrics.pass_rate < threshold

        elif condition == "flakiness_above":
            return test_metrics.flakiness_score > threshold

        elif condition == "trend_degrading":
            return test_metrics.trend == "degrading"

        elif condition == "reliability_grade_f":
            return test_metrics.reliability_grade == "F"

        elif condition == "new_test_unstable":
            # Consider test "new" if it has fewer than 20 executions
            return (
                test_metrics.execution_count < 20 and test_metrics.pass_rate < threshold
            )

        elif condition == "suite_failure_spike":
            # This requires suite-level evaluation
            suite_metrics = metrics_collector.get_suite_metrics(test_metrics.test_suite)
            return suite_metrics.pass_rate < threshold

        return False

    def _create_alert(self, rule: AlertRule, test_metrics: TestMetrics) -> Alert:
        """Create an alert from a rule and test metrics."""
        alert_id = f"{rule.rule_id}_{test_metrics.test_id}_{int(time.time())}"

        # Create detailed message
        message = self._format_alert_message(rule, test_metrics)

        # Prepare details dictionary
        details = {
            "rule_name": rule.name,
            "rule_description": rule.description,
            "test_metrics": asdict(test_metrics),
            "threshold": rule.threshold,
            "actual_value": self._get_metric_value(rule.condition, test_metrics),
        }

        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            test_id=test_metrics.test_id,
            test_name=test_metrics.test_name,
            test_suite=test_metrics.test_suite,
            severity=rule.severity,
            message=message,
            details=details,
            triggered_at=datetime.now(),
        )

        return alert

    def _get_metric_value(self, condition: str, test_metrics: TestMetrics) -> Any:
        """Get the actual metric value for a condition."""
        if condition == "pass_rate_below":
            return test_metrics.pass_rate
        elif condition == "flakiness_above":
            return test_metrics.flakiness_score
        elif condition == "trend_degrading":
            return test_metrics.trend
        elif condition == "reliability_grade_f":
            return test_metrics.reliability_grade
        elif condition == "new_test_unstable":
            return test_metrics.pass_rate
        elif condition == "suite_failure_spike":
            suite_metrics = metrics_collector.get_suite_metrics(test_metrics.test_suite)
            return suite_metrics.pass_rate
        return None

    def _format_alert_message(self, rule: AlertRule, test_metrics: TestMetrics) -> str:
        """Format a human-readable alert message."""
        severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🚨", "critical": "🔥"}

        emoji = severity_emoji.get(rule.severity, "⚠️")

        if rule.condition == "pass_rate_below":
            return (
                f"{emoji} {rule.name}: Test '{test_metrics.test_name}' in suite "
                f"'{test_metrics.test_suite}' has pass rate {test_metrics.pass_rate:.1%} "
                f"(below threshold {rule.threshold:.1%})"
            )

        elif rule.condition == "flakiness_above":
            return (
                f"{emoji} {rule.name}: Test '{test_metrics.test_name}' in suite "
                f"'{test_metrics.test_suite}' has flakiness score {test_metrics.flakiness_score:.1%} "
                f"(above threshold {rule.threshold:.1%})"
            )

        elif rule.condition == "trend_degrading":
            return (
                f"{emoji} {rule.name}: Test '{test_metrics.test_name}' in suite "
                f"'{test_metrics.test_suite}' is showing degrading performance trend"
            )

        elif rule.condition == "reliability_grade_f":
            return (
                f"{emoji} {rule.name}: Test '{test_metrics.test_name}' in suite "
                f"'{test_metrics.test_suite}' has reliability grade F"
            )

        elif rule.condition == "new_test_unstable":
            return (
                f"{emoji} {rule.name}: New test '{test_metrics.test_name}' in suite "
                f"'{test_metrics.test_suite}' showing instability "
                f"(pass rate: {test_metrics.pass_rate:.1%})"
            )

        elif rule.condition == "suite_failure_spike":
            suite_metrics = metrics_collector.get_suite_metrics(test_metrics.test_suite)
            return (
                f"{emoji} {rule.name}: Test suite '{test_metrics.test_suite}' "
                f"experiencing failure spike (pass rate: {suite_metrics.pass_rate:.1%})"
            )

        return f"{emoji} {rule.name}: {rule.description}"

    def process_alert(self, alert: Alert):
        """Process and send notifications for an alert."""
        with self._lock:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)

        logger.warning(f"Alert triggered: {alert.message}")

        # Get notification channels for the rule
        rule = self.alert_rules.get(alert.rule_id)
        if not rule:
            return

        # Send notifications
        for channel_type in rule.notification_channels:
            channel = self.notification_channels.get(channel_type)
            if channel and channel.enabled:
                try:
                    self._send_notification(channel, alert)
                except Exception as e:
                    logger.error(f"Failed to send notification via {channel_type}: {e}")

    def _send_notification(self, channel: NotificationChannel, alert: Alert):
        """Send notification via specified channel."""
        if channel.channel_type == "email":
            self._send_email_notification(channel, alert)
        elif channel.channel_type == "webhook":
            self._send_webhook_notification(channel, alert)
        elif channel.channel_type == "log":
            self._send_log_notification(channel, alert)

    def _send_email_notification(self, channel: NotificationChannel, alert: Alert):
        """Send email notification."""
        config = channel.config

        if not config.get("username") or not config.get("to_emails"):
            logger.warning("Email notification not configured properly")
            return

        msg = MimeMultipart()
        msg["From"] = config["from_email"] or config["username"]
        msg["To"] = ", ".join(config["to_emails"])
        msg["Subject"] = f"Test Alert: {alert.severity.upper()} - {alert.test_name}"

        # Create HTML body
        html_body = f"""
        <html>
        <body>
            <h2>Test Monitoring Alert</h2>
            <p><strong>Severity:</strong> {alert.severity.upper()}</p>
            <p><strong>Test:</strong> {alert.test_name}</p>
            <p><strong>Suite:</strong> {alert.test_suite}</p>
            <p><strong>Message:</strong> {alert.message}</p>
            <p><strong>Time:</strong> {alert.triggered_at}</p>

            <h3>Test Details</h3>
            <ul>
                <li><strong>Pass Rate:</strong> {alert.details["test_metrics"]["pass_rate"]:.1%}</li>
                <li><strong>Flakiness Score:</strong> {alert.details["test_metrics"]["flakiness_score"]:.1%}</li>
                <li><strong>Reliability Grade:</strong> {alert.details["test_metrics"]["reliability_grade"]}</li>
                <li><strong>Trend:</strong> {alert.details["test_metrics"]["trend"]}</li>
                <li><strong>Execution Count:</strong> {alert.details["test_metrics"]["execution_count"]}</li>
            </ul>

            <p><em>This alert was generated by the CI Pipeline Test Monitoring system.</em></p>
        </body>
        </html>
        """

        msg.attach(MimeText(html_body, "html"))

        # Send email
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["username"], config["password"])
        server.send_message(msg)
        server.quit()

        logger.info(f"Email alert sent for {alert.test_name}")

    def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert):
        """Send webhook notification (Slack, Teams, etc.)."""
        import requests

        config = channel.config
        url = config.get("url")

        if not url:
            logger.warning("Webhook URL not configured")
            return

        # Prepare webhook payload
        payload = {
            "text": alert.message,
            "alert_id": alert.alert_id,
            "severity": alert.severity,
            "test_name": alert.test_name,
            "test_suite": alert.test_suite,
            "timestamp": alert.triggered_at.isoformat(),
            "details": alert.details,
        }

        headers = config.get("headers", {})
        method = config.get("method", "POST")

        response = requests.request(method, url, json=payload, headers=headers)
        response.raise_for_status()

        logger.info(f"Webhook alert sent for {alert.test_name}")

    def _send_log_notification(self, channel: NotificationChannel, alert: Alert):
        """Send log notification."""
        config = channel.config
        log_level = config.get("log_level", "WARNING")

        log_message = f"TEST ALERT [{alert.severity.upper()}]: {alert.message}"

        if log_level == "ERROR":
            logger.error(log_message)
        elif log_level == "WARNING":
            logger.warning(log_message)
        elif log_level == "INFO":
            logger.info(log_message)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system"):
        """Acknowledge an alert."""
        with self._lock:
            for alert in self.active_alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                    break

    def resolve_alert(self, alert_id: str, resolved_by: str = "system"):
        """Resolve an alert."""
        with self._lock:
            for i, alert in enumerate(self.active_alerts):
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    self.active_alerts.pop(i)
                    logger.info(f"Alert {alert_id} resolved by {resolved_by}")
                    break

    def get_active_alerts(self, severity: Optional[str] = None) -> list[Alert]:
        """Get list of active alerts, optionally filtered by severity."""
        with self._lock:
            alerts = self.active_alerts.copy()

        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]

        return sorted(alerts, key=lambda x: x.triggered_at, reverse=True)

    def get_alert_summary(self) -> dict[str, Any]:
        """Get summary of alert status."""
        with self._lock:
            active_alerts = self.active_alerts.copy()
            recent_history = [
                a
                for a in self.alert_history
                if a.triggered_at > datetime.now() - timedelta(hours=24)
            ]

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for alert in active_alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        return {
            "active_alerts_count": len(active_alerts),
            "alerts_last_24h": len(recent_history),
            "severity_breakdown": severity_counts,
            "most_recent_alert": (
                active_alerts[-1].triggered_at.isoformat() if active_alerts else None
            ),
            "rules_enabled": len([r for r in self.alert_rules.values() if r.enabled]),
        }

    def run_monitoring_loop(self, check_interval: int = 300):
        """Run continuous monitoring loop."""
        logger.info(
            f"Starting alert monitoring loop (check interval: {check_interval}s)"
        )

        while True:
            try:
                # Get all problematic tests
                problematic_tests = metrics_collector.get_problematic_tests()

                # Evaluate alerts for each test
                for test_metrics in problematic_tests:
                    alerts = self.evaluate_test_alerts(test_metrics)

                    for alert in alerts:
                        self.process_alert(alert)

                # Check for suite-level alerts
                self._check_suite_alerts()

                # Clean up old resolved alerts
                self._cleanup_old_alerts()

                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Shorter sleep on error

    def _check_suite_alerts(self):
        """Check for suite-level alert conditions."""
        # Get all suites and check for failure spikes
        summary = metrics_collector.get_dashboard_summary()

        for suite_info in summary.get("suite_statistics", []):
            suite_name = suite_info["suite_name"]
            pass_rate = suite_info["pass_rate"]

            # Check if suite pass rate triggers any rules
            fake_test_metrics = TestMetrics(
                test_id=f"suite_{suite_name}",
                test_name=f"Suite {suite_name}",
                test_suite=suite_name,
                pass_rate=pass_rate,
                avg_duration=0.0,
                flakiness_score=0.0,
                execution_count=suite_info["test_count"],
                last_execution=datetime.now(),
                trend="stable",
                reliability_grade="A",
            )

            # Only check suite-specific rules
            suite_rules = [
                r
                for r in self.alert_rules.values()
                if r.condition == "suite_failure_spike"
            ]

            for rule in suite_rules:
                if self._evaluate_rule_condition(rule, fake_test_metrics):
                    alert = self._create_alert(rule, fake_test_metrics)
                    self.process_alert(alert)

    def _cleanup_old_alerts(self):
        """Clean up old resolved alerts from history."""
        cutoff_time = datetime.now() - timedelta(days=30)

        with self._lock:
            self.alert_history = [
                alert
                for alert in self.alert_history
                if alert.triggered_at > cutoff_time or not alert.resolved
            ]


# Global alert manager instance
alert_manager = AlertManager()


def start_alert_monitoring(check_interval: int = 300):
    """Start the alert monitoring in a background thread."""

    def monitoring_thread():
        alert_manager.run_monitoring_loop(check_interval)

    thread = threading.Thread(target=monitoring_thread, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    # Example usage
    logger.info("Test Alerting System initialized")

    # Start monitoring
    start_alert_monitoring(check_interval=60)  # Check every minute for testing

    # Keep the script running
    try:
        while True:
            time.sleep(60)
            summary = alert_manager.get_alert_summary()
            logger.info(f"Alert summary: {summary}")
    except KeyboardInterrupt:
        logger.info("Alert monitoring stopped")
