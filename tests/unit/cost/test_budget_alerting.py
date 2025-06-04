"""
Unit tests for the budget alerting and notification system.

This module tests all components of the budget alerting system including:
- Alert message creation and serialization
- Rate limiting functionality
- Alert aggregation
- Message templates
- Multi-channel notification delivery
- Configuration management
- Error handling and resilience
"""

import asyncio
import json
import smtplib
import time
import unittest
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from leadfactory.cost.budget_alerting import (
    AlertAggregator,
    AlertMessage,
    AlertRateLimiter,
    AlertType,
    BudgetNotificationService,
    MessageTemplates,
    NotificationChannel,
    NotificationConfig,
    get_notification_service,
    reset_notification_service,
    send_budget_alert,
    send_budget_alert_async,
)
from leadfactory.cost.budget_config import AlertLevel


class TestAlertMessage(unittest.TestCase):
    """Test AlertMessage functionality."""

    def test_alert_message_creation(self):
        """Test creating an alert message."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
            model="gpt-4o",
            endpoint="chat",
            current_cost=50.0,
            budget_limit=100.0,
            utilization_percentage=50.0,
        )

        self.assertEqual(alert.alert_type, AlertType.THRESHOLD_WARNING)
        self.assertEqual(alert.severity, AlertLevel.WARNING)
        self.assertEqual(alert.title, "Test Alert")
        self.assertEqual(alert.service, "openai")
        self.assertEqual(alert.model, "gpt-4o")
        self.assertEqual(alert.current_cost, 50.0)
        self.assertEqual(alert.utilization_percentage, 50.0)
        self.assertIsInstance(alert.timestamp, datetime)

    def test_alert_message_to_dict(self):
        """Test converting alert message to dictionary."""
        alert = AlertMessage(
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=AlertLevel.CRITICAL,
            title="Budget Exceeded",
            message="Budget has been exceeded",
            service="openai",
            current_cost=150.0,
            budget_limit=100.0,
        )

        alert_dict = alert.to_dict()

        self.assertEqual(alert_dict["alert_type"], "budget_exceeded")
        self.assertEqual(alert_dict["severity"], "critical")
        self.assertEqual(alert_dict["title"], "Budget Exceeded")
        self.assertEqual(alert_dict["service"], "openai")
        self.assertEqual(alert_dict["current_cost"], 150.0)
        self.assertIn("timestamp", alert_dict)
        self.assertIsInstance(alert_dict["timestamp"], str)


class TestAlertRateLimiter(unittest.TestCase):
    """Test AlertRateLimiter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = AlertRateLimiter(window_minutes=1, max_alerts=3)

    def test_rate_limiter_allows_initial_alerts(self):
        """Test that rate limiter allows initial alerts."""
        alert_key = "test_alert"

        # Should allow first 3 alerts
        for i in range(3):
            self.assertTrue(self.rate_limiter.should_send_alert(alert_key))

        # Should block 4th alert
        self.assertFalse(self.rate_limiter.should_send_alert(alert_key))

    def test_rate_limiter_window_expiry(self):
        """Test that rate limiter resets after window expires."""
        alert_key = "test_alert"

        # Fill up the rate limit
        for i in range(3):
            self.assertTrue(self.rate_limiter.should_send_alert(alert_key))

        # Should be blocked
        self.assertFalse(self.rate_limiter.should_send_alert(alert_key))

        # Simulate time passing (mock the timestamps)
        with patch("leadfactory.cost.budget_alerting.datetime") as mock_datetime:
            # Set current time to 2 minutes later
            future_time = datetime.now() + timedelta(minutes=2)
            mock_datetime.now.return_value = future_time

            # Should allow alerts again
            self.assertTrue(self.rate_limiter.should_send_alert(alert_key))

    def test_rate_limiter_different_keys(self):
        """Test that rate limiter tracks different keys separately."""
        # Should allow alerts for different keys
        self.assertTrue(self.rate_limiter.should_send_alert("key1"))
        self.assertTrue(self.rate_limiter.should_send_alert("key2"))
        self.assertTrue(self.rate_limiter.should_send_alert("key1"))
        self.assertTrue(self.rate_limiter.should_send_alert("key2"))

    def test_get_alert_count(self):
        """Test getting alert count for a key."""
        alert_key = "test_alert"

        self.assertEqual(self.rate_limiter.get_alert_count(alert_key), 0)

        self.rate_limiter.should_send_alert(alert_key)
        self.assertEqual(self.rate_limiter.get_alert_count(alert_key), 1)

        self.rate_limiter.should_send_alert(alert_key)
        self.assertEqual(self.rate_limiter.get_alert_count(alert_key), 2)


class TestAlertAggregator(unittest.TestCase):
    """Test AlertAggregator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.aggregator = AlertAggregator(window_minutes=1)

    def test_aggregator_collects_similar_alerts(self):
        """Test that aggregator collects similar alerts."""
        alert1 = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Alert 1",
            message="Message 1",
            service="openai",
            model="gpt-4o",
        )

        alert2 = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Alert 2",
            message="Message 2",
            service="openai",
            model="gpt-4o",
        )

        # First alert should be collected
        result1 = self.aggregator.add_alert(alert1)
        self.assertIsNone(result1)

        # Second alert should also be collected
        result2 = self.aggregator.add_alert(alert2)
        self.assertIsNone(result2)

    def test_aggregator_flushes_after_window(self):
        """Test that aggregator flushes alerts after window expires."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        # Add alert
        result1 = self.aggregator.add_alert(alert)
        self.assertIsNone(result1)

        # Mock time passing
        with patch("leadfactory.cost.budget_alerting.datetime") as mock_datetime:
            future_time = datetime.now() + timedelta(minutes=2)
            mock_datetime.now.return_value = future_time

            # Add another alert - should trigger flush
            alert2 = AlertMessage(
                alert_type=AlertType.THRESHOLD_WARNING,
                severity=AlertLevel.WARNING,
                title="Test Alert 2",
                message="Test message 2",
                service="openai",
            )

            result2 = self.aggregator.add_alert(alert2)
            self.assertIsNotNone(result2)
            self.assertEqual(
                len(result2), 2
            )  # Should return both alerts (first + second)

    def test_aggregator_flush_all(self):
        """Test flushing all pending alerts."""
        alert1 = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Alert 1",
            message="Message 1",
            service="openai",
        )

        alert2 = AlertMessage(
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=AlertLevel.CRITICAL,
            title="Alert 2",
            message="Message 2",
            service="semrush",
        )

        self.aggregator.add_alert(alert1)
        self.aggregator.add_alert(alert2)

        flushed = self.aggregator.flush_all()

        self.assertEqual(len(flushed), 2)  # Two different aggregation keys
        self.assertTrue(
            any("threshold_warning:openai:all" in key for key in flushed.keys())
        )
        self.assertTrue(
            any("budget_exceeded:semrush:all" in key for key in flushed.keys())
        )


class TestMessageTemplates(unittest.TestCase):
    """Test MessageTemplates functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.templates = MessageTemplates()

    def test_threshold_warning_template(self):
        """Test threshold warning message template."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Warning",
            message="Test warning",
            service="openai",
            model="gpt-4o",
            current_cost=80.0,
            budget_limit=100.0,
            utilization_percentage=80.0,
        )

        template = self.templates.threshold_warning(alert)

        self.assertIn("subject", template)
        self.assertIn("text", template)
        self.assertIn("html", template)
        self.assertIn("80.0%", template["subject"])
        self.assertIn("openai", template["text"])
        self.assertIn("$80.00", template["text"])
        self.assertIn("<table>", template["html"])

    def test_budget_exceeded_template(self):
        """Test budget exceeded message template."""
        alert = AlertMessage(
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=AlertLevel.CRITICAL,
            title="Budget Exceeded",
            message="Budget exceeded",
            service="openai",
            model="gpt-4o",
            current_cost=120.0,
            budget_limit=100.0,
            utilization_percentage=120.0,
        )

        template = self.templates.budget_exceeded(alert)

        self.assertIn("CRITICAL", template["subject"])
        self.assertIn("IMMEDIATE ACTION", template["text"])
        self.assertIn("$20.00", template["text"])  # Overage
        self.assertIn("color: red", template["html"])

    def test_throttling_activated_template(self):
        """Test throttling activation message template."""
        alert = AlertMessage(
            alert_type=AlertType.THROTTLING_ACTIVATED,
            severity=AlertLevel.WARNING,
            title="Throttling Active",
            message="Throttling has been activated",
            service="openai",
            model="gpt-4o",
        )

        template = self.templates.throttling_activated(alert)

        self.assertIn("Throttling Activated", template["subject"])
        self.assertIn("throttling has been activated", template["text"].lower())
        self.assertIn("openai", template["text"])


class TestNotificationConfig(unittest.TestCase):
    """Test NotificationConfig functionality."""

    def test_notification_config_defaults(self):
        """Test notification config default values."""
        config = NotificationConfig()

        self.assertFalse(config.email_enabled)
        self.assertFalse(config.slack_enabled)
        self.assertFalse(config.webhook_enabled)
        self.assertTrue(config.log_enabled)
        self.assertFalse(config.console_enabled)
        self.assertEqual(config.rate_limit_window_minutes, 15)
        self.assertEqual(config.max_alerts_per_window, 10)

    def test_notification_config_custom_values(self):
        """Test notification config with custom values."""
        config = NotificationConfig(
            email_enabled=True,
            email_smtp_host="smtp.example.com",
            email_to=["admin@example.com"],
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/test",
            rate_limit_window_minutes=30,
            max_alerts_per_window=5,
        )

        self.assertTrue(config.email_enabled)
        self.assertEqual(config.email_smtp_host, "smtp.example.com")
        self.assertEqual(config.email_to, ["admin@example.com"])
        self.assertTrue(config.slack_enabled)
        self.assertEqual(config.slack_webhook_url, "https://hooks.slack.com/test")
        self.assertEqual(config.rate_limit_window_minutes, 30)
        self.assertEqual(config.max_alerts_per_window, 5)


class TestBudgetNotificationService(unittest.TestCase):
    """Test BudgetNotificationService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = NotificationConfig(
            log_enabled=True,
            console_enabled=False,
            email_enabled=False,
            slack_enabled=False,
            webhook_enabled=False,
            aggregation_enabled=False,  # Disable for simpler testing
        )
        self.service = BudgetNotificationService(self.config)

    def test_service_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service.config)
        self.assertIsNotNone(self.service.rate_limiter)
        self.assertIsNotNone(self.service.templates)

    @patch("leadfactory.cost.budget_alerting.logger")
    def test_send_log_alert(self, mock_logger):
        """Test sending alert to logger."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        result = self.service._send_log_alert(alert)

        self.assertTrue(result)
        mock_logger.log.assert_called_once()

    def test_send_console_alert(self):
        """Test sending alert to console."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        with patch("builtins.print") as mock_print:
            result = self.service._send_console_alert(alert)

            self.assertTrue(result)
            self.assertEqual(mock_print.call_count, 2)  # Title and message

    @patch("leadfactory.cost.budget_alerting.smtplib.SMTP")
    def test_send_email_alert_success(self, mock_smtp_class):
        """Test successful email alert sending."""
        # Configure email
        self.service.config.email_enabled = True
        self.service.config.email_smtp_host = "smtp.example.com"
        self.service.config.email_username = "user@example.com"
        self.service.config.email_password = "password"
        self.service.config.email_from = "alerts@example.com"
        self.service.config.email_to = ["admin@example.com"]

        # Mock SMTP
        mock_smtp = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
            current_cost=50.0,
            budget_limit=100.0,
            utilization_percentage=50.0,
        )

        result = self.service._send_email_alert(alert)

        self.assertTrue(result)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user@example.com", "password")
        mock_smtp.send_message.assert_called_once()

    def test_send_email_alert_incomplete_config(self):
        """Test email alert with incomplete configuration."""
        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        result = self.service._send_email_alert(alert)

        self.assertFalse(result)  # Should fail due to incomplete config

    @patch("leadfactory.cost.budget_alerting.requests.post")
    def test_send_slack_alert_success(self, mock_post):
        """Test successful Slack alert sending."""
        self.service.config.slack_webhook_url = "https://hooks.slack.com/test"
        self.service.config.slack_channel = "#alerts"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        alert = AlertMessage(
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=AlertLevel.CRITICAL,
            title="Budget Exceeded",
            message="Budget has been exceeded",
            service="openai",
            current_cost=120.0,
            budget_limit=100.0,
        )

        result = self.service._send_slack_alert(alert)

        self.assertTrue(result)
        mock_post.assert_called_once()

        # Check payload structure
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["channel"], "#alerts")
        self.assertEqual(len(payload["attachments"]), 1)
        self.assertEqual(payload["attachments"][0]["color"], "danger")

    @patch("leadfactory.cost.budget_alerting.requests.post")
    def test_send_webhook_alert_success(self, mock_post):
        """Test successful webhook alert sending."""
        self.service.config.webhook_urls = ["https://example.com/webhook"]

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        alert = AlertMessage(
            alert_type=AlertType.THROTTLING_ACTIVATED,
            severity=AlertLevel.WARNING,
            title="Throttling Active",
            message="Throttling activated",
            service="openai",
        )

        result = self.service._send_webhook_alert(alert)

        self.assertTrue(result)
        mock_post.assert_called_once()

        # Check payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["alert_type"], "throttling_activated")
        self.assertEqual(payload["service"], "openai")

    @patch("leadfactory.cost.budget_alerting.requests.post")
    def test_send_webhook_alert_failure(self, mock_post):
        """Test webhook alert failure handling."""
        self.service.config.webhook_urls = ["https://example.com/webhook"]

        mock_post.side_effect = requests.RequestException("Network error")

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        result = self.service._send_webhook_alert(alert)

        self.assertFalse(result)

    def test_send_alert_with_rate_limiting(self):
        """Test alert sending with rate limiting."""
        # Set up tight rate limiting
        self.service.rate_limiter = AlertRateLimiter(window_minutes=60, max_alerts=1)

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        # First alert should succeed
        result1 = self.service.send_alert(alert)
        self.assertTrue(result1)

        # Second alert should be rate limited
        result2 = self.service.send_alert(alert)
        self.assertFalse(result2)

    def test_send_alert_with_aggregation(self):
        """Test alert sending with aggregation."""
        # Enable aggregation
        self.service.config.aggregation_enabled = True
        self.service.aggregator = AlertAggregator(window_minutes=60)  # Long window

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        # Alert should be aggregated, not sent immediately
        with patch.object(self.service, "_send_single_alert") as mock_send:
            result = self.service.send_alert(alert)

            self.assertTrue(result)
            mock_send.assert_not_called()  # Should not send immediately

    def test_flush_pending_alerts(self):
        """Test flushing pending aggregated alerts."""
        # Enable aggregation
        self.service.config.aggregation_enabled = True
        self.service.aggregator = AlertAggregator(window_minutes=60)

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        # Add alert to aggregation
        self.service.send_alert(alert)

        # Flush should send aggregated alert
        with patch.object(self.service, "_send_single_alert") as mock_send:
            mock_send.return_value = True
            result = self.service.flush_pending_alerts()

            self.assertTrue(result)
            mock_send.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "BUDGET_ALERT_EMAIL_ENABLED": "true",
            "BUDGET_ALERT_SMTP_HOST": "smtp.test.com",
            "BUDGET_ALERT_EMAIL_TO": "admin@test.com,user@test.com",
        },
    )
    def test_load_config_from_environment(self):
        """Test loading configuration from environment variables."""
        service = BudgetNotificationService()

        self.assertTrue(service.config.email_enabled)
        self.assertEqual(service.config.email_smtp_host, "smtp.test.com")
        self.assertEqual(service.config.email_to, ["admin@test.com", "user@test.com"])


class TestAsyncFunctionality(unittest.TestCase):
    """Test async functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = NotificationConfig(log_enabled=True)
        self.service = BudgetNotificationService(self.config)

    @patch.object(BudgetNotificationService, "send_alert")
    def test_send_alert_async(self, mock_send_alert):
        """Test async alert sending."""
        mock_send_alert.return_value = True

        alert = AlertMessage(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
        )

        async def test_async():
            result = await self.service.send_alert_async(alert)
            return result

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(test_async())
            self.assertTrue(result)
            mock_send_alert.assert_called_once_with(alert)
        finally:
            loop.close()


class TestGlobalFunctions(unittest.TestCase):
    """Test global convenience functions."""

    def setUp(self):
        """Set up test fixtures."""
        reset_notification_service()

    def tearDown(self):
        """Clean up after tests."""
        reset_notification_service()

    def test_get_notification_service_singleton(self):
        """Test that get_notification_service returns a singleton."""
        service1 = get_notification_service()
        service2 = get_notification_service()

        self.assertIs(service1, service2)

    def test_reset_notification_service(self):
        """Test resetting the global notification service."""
        service1 = get_notification_service()
        reset_notification_service()
        service2 = get_notification_service()

        self.assertIsNot(service1, service2)

    @patch.object(BudgetNotificationService, "send_alert")
    def test_send_budget_alert_convenience(self, mock_send_alert):
        """Test the convenience function for sending budget alerts."""
        mock_send_alert.return_value = True

        result = send_budget_alert(
            alert_type=AlertType.THRESHOLD_WARNING,
            severity=AlertLevel.WARNING,
            title="Test Alert",
            message="Test message",
            service="openai",
            model="gpt-4o",
            current_cost=50.0,
            budget_limit=100.0,
        )

        self.assertTrue(result)
        mock_send_alert.assert_called_once()

        # Check the alert message passed to send_alert
        call_args = mock_send_alert.call_args[0]
        alert = call_args[0]
        self.assertEqual(alert.alert_type, AlertType.THRESHOLD_WARNING)
        self.assertEqual(alert.service, "openai")
        self.assertEqual(alert.model, "gpt-4o")
        self.assertEqual(alert.current_cost, 50.0)

    @patch.object(BudgetNotificationService, "send_alert_async")
    def test_send_budget_alert_async_convenience(self, mock_send_alert_async):
        """Test the async convenience function for sending budget alerts."""
        mock_send_alert_async.return_value = asyncio.Future()
        mock_send_alert_async.return_value.set_result(True)

        async def test_async():
            result = await send_budget_alert_async(
                alert_type=AlertType.BUDGET_EXCEEDED,
                severity=AlertLevel.CRITICAL,
                title="Budget Exceeded",
                message="Budget exceeded",
                service="openai",
            )
            return result

        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(test_async())
            self.assertTrue(result)
            mock_send_alert_async.assert_called_once()
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
