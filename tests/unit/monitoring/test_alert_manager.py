"""
Tests for Alert Manager System
==============================

Tests for the purchase metrics alert manager and notification system.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.monitoring.alert_manager import (
    AlertManager,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertType,
    EmailNotificationChannel,
    SlackNotificationChannel,
    WebhookNotificationChannel
)
from leadfactory.monitoring.metrics_aggregator import (
    MetricsAggregator,
    AggregatedMetric,
    AggregationPeriod
)


class TestAlertManager:
    """Test alert manager functionality."""

    @pytest.fixture
    def mock_metrics_aggregator(self):
        """Mock metrics aggregator."""
        mock = Mock(spec=MetricsAggregator)

        # Create mock aggregated metric
        mock_metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=5,
            total_revenue_cents=25000,  # $250
            total_stripe_fees_cents=750,
            average_order_value_cents=5000,
            conversion_rate=0.01,  # 1%
            refund_count=2,
            refund_amount_cents=10000,
            audit_type_breakdown={},
            geographic_breakdown={}
        )

        mock.get_aggregated_metrics.return_value = [mock_metric]
        return mock

    @pytest.fixture
    def alert_manager(self, mock_metrics_aggregator):
        """Create alert manager with mocked dependencies."""
        return AlertManager(metrics_aggregator=mock_metrics_aggregator)

    def test_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert len(alert_manager.alert_rules) > 0  # Default rules should be loaded
        assert len(alert_manager.notification_channels) == 0  # No channels by default
        assert len(alert_manager.active_alerts) == 0
        assert len(alert_manager.alert_history) == 0

    def test_default_alert_rules(self, alert_manager):
        """Test default alert rules are created."""
        rule_names = list(alert_manager.alert_rules.keys())

        expected_rules = [
            "revenue_drop",
            "conversion_rate_low",
            "no_purchases_6h",
            "high_refund_rate",
            "stripe_fees_spike"
        ]

        for rule_name in expected_rules:
            assert rule_name in rule_names

    def test_add_alert_rule(self, alert_manager):
        """Test adding custom alert rule."""
        custom_rule = AlertRule(
            name="custom_test_rule",
            description="Test rule",
            alert_type=AlertType.THRESHOLD,
            severity=AlertSeverity.MEDIUM,
            metric_name="total_purchases",
            condition="> 100",
            threshold_value=100
        )

        alert_manager.add_alert_rule(custom_rule)

        assert "custom_test_rule" in alert_manager.alert_rules
        assert alert_manager.alert_rules["custom_test_rule"].description == "Test rule"

    def test_remove_alert_rule(self, alert_manager):
        """Test removing alert rule."""
        # Add a rule first
        test_rule = AlertRule(
            name="to_be_removed",
            description="Will be removed",
            alert_type=AlertType.THRESHOLD,
            severity=AlertSeverity.LOW,
            metric_name="total_purchases",
            condition="> 0",
            threshold_value=0
        )

        alert_manager.add_alert_rule(test_rule)
        assert "to_be_removed" in alert_manager.alert_rules

        # Remove the rule
        alert_manager.remove_alert_rule("to_be_removed")
        assert "to_be_removed" not in alert_manager.alert_rules

    def test_check_alerts_triggers_alert(self, alert_manager, mock_metrics_aggregator):
        """Test that check_alerts triggers alerts when conditions are met."""
        # Create a metric that should trigger the revenue_drop alert
        low_revenue_metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=1,
            total_revenue_cents=30000,  # $300 - below $500 threshold
            total_stripe_fees_cents=900,
            average_order_value_cents=30000,
            conversion_rate=0.005,
            refund_count=0,
            refund_amount_cents=0,
            audit_type_breakdown={},
            geographic_breakdown={}
        )

        mock_metrics_aggregator.get_aggregated_metrics.return_value = [low_revenue_metric]

        # Check alerts
        alert_manager.check_alerts()

        # Should have triggered revenue_drop alert
        assert len(alert_manager.active_alerts) > 0
        assert "revenue_drop" in alert_manager.active_alerts

    def test_check_alerts_no_trigger(self, alert_manager, mock_metrics_aggregator):
        """Test that check_alerts doesn't trigger when conditions aren't met."""
        # Create a metric that should NOT trigger alerts
        good_metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=20,
            total_revenue_cents=100000,  # $1000 - above $500 threshold
            total_stripe_fees_cents=3000,
            average_order_value_cents=5000,
            conversion_rate=0.05,  # 5% - above 2% threshold
            refund_count=1,
            refund_amount_cents=5000,
            audit_type_breakdown={},
            geographic_breakdown={}
        )

        mock_metrics_aggregator.get_aggregated_metrics.return_value = [good_metric]

        # Check alerts
        alert_manager.check_alerts()

        # Should not have triggered any alerts
        assert len(alert_manager.active_alerts) == 0

    def test_alert_cooldown(self, alert_manager, mock_metrics_aggregator):
        """Test alert cooldown prevents duplicate alerts."""
        # Create metric that triggers alert
        low_revenue_metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=1,
            total_revenue_cents=30000,
            total_stripe_fees_cents=900,
            average_order_value_cents=30000,
            conversion_rate=0.005,
            refund_count=0,
            refund_amount_cents=0,
            audit_type_breakdown={},
            geographic_breakdown={}
        )

        mock_metrics_aggregator.get_aggregated_metrics.return_value = [low_revenue_metric]

        # First check should trigger alert
        alert_manager.check_alerts()
        assert len(alert_manager.active_alerts) == 1
        first_alert_count = len(alert_manager.alert_history)

        # Immediate second check should not trigger due to cooldown
        alert_manager.check_alerts()
        assert len(alert_manager.alert_history) == first_alert_count  # No new alerts

    def test_evaluate_condition(self, alert_manager):
        """Test condition evaluation logic."""
        # Test different condition types
        assert alert_manager._evaluate_condition(10, "> 5", 5) == True
        assert alert_manager._evaluate_condition(3, "> 5", 5) == False

        assert alert_manager._evaluate_condition(3, "< 5", 5) == True
        assert alert_manager._evaluate_condition(7, "< 5", 5) == False

        assert alert_manager._evaluate_condition(5, "= 5", 5) == True
        assert alert_manager._evaluate_condition(4, "= 5", 5) == False

        assert alert_manager._evaluate_condition(5, ">= 5", 5) == True
        assert alert_manager._evaluate_condition(4, ">= 5", 5) == False

        assert alert_manager._evaluate_condition(5, "<= 5", 5) == True
        assert alert_manager._evaluate_condition(6, "<= 5", 5) == False

    def test_extract_metric_value(self, alert_manager):
        """Test metric value extraction."""
        metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=10,
            total_revenue_cents=50000,
            total_stripe_fees_cents=1500,
            average_order_value_cents=5000,
            conversion_rate=0.025,
            refund_count=2,
            refund_amount_cents=1000,
            audit_type_breakdown={},
            geographic_breakdown={}
        )

        # Test different metric extractions
        assert alert_manager._extract_metric_value(metric, "total_revenue_cents") == 50000
        assert alert_manager._extract_metric_value(metric, "total_purchases") == 10
        assert alert_manager._extract_metric_value(metric, "conversion_rate") == 0.025
        assert alert_manager._extract_metric_value(metric, "average_order_value_cents") == 5000

        # Test calculated metrics
        refund_rate = alert_manager._extract_metric_value(metric, "refund_rate")
        assert refund_rate == 0.2  # 2 refunds / 10 purchases

        stripe_fee_percentage = alert_manager._extract_metric_value(metric, "stripe_fee_percentage")
        assert stripe_fee_percentage == 0.03  # 1500 / 50000

        # Test unknown metric
        assert alert_manager._extract_metric_value(metric, "unknown_metric") is None

    def test_get_alert_status(self, alert_manager):
        """Test alert status retrieval."""
        status = alert_manager.get_alert_status()

        assert "active_alerts_count" in status
        assert "active_alerts" in status
        assert "total_rules" in status
        assert "enabled_rules" in status
        assert "notification_channels" in status
        assert "recent_alerts_24h" in status

        # Verify initial values
        assert status["active_alerts_count"] == 0
        assert status["total_rules"] == len(alert_manager.alert_rules)
        assert status["enabled_rules"] == len([r for r in alert_manager.alert_rules.values() if r.enabled])


class TestAlertRule:
    """Test alert rule functionality."""

    def test_alert_rule_creation(self):
        """Test alert rule creation and validation."""
        rule = AlertRule(
            name="test_rule",
            description="Test description",
            alert_type=AlertType.THRESHOLD,
            severity=AlertSeverity.HIGH,
            metric_name="test_metric",
            condition="> 100",
            threshold_value=100,
            comparison_period=AggregationPeriod.DAILY,
            enabled=True,
            cooldown_minutes=30,
            tags=["test", "monitoring"]
        )

        assert rule.name == "test_rule"
        assert rule.severity == AlertSeverity.HIGH
        assert rule.threshold_value == 100
        assert rule.enabled == True
        assert rule.cooldown_minutes == 30
        assert "test" in rule.tags

    def test_alert_rule_validation(self):
        """Test alert rule validation."""
        # Should raise error for missing condition
        with pytest.raises(ValueError):
            AlertRule(
                name="invalid_rule",
                description="Invalid",
                alert_type=AlertType.THRESHOLD,
                severity=AlertSeverity.LOW,
                metric_name="test",
                condition="",  # Empty condition
                threshold_value=0
            )


class TestAlert:
    """Test alert data structure."""

    def test_alert_creation(self):
        """Test alert creation."""
        timestamp = datetime.now()

        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.CRITICAL,
            message="Test alert message",
            current_value=50,
            threshold_value=100,
            timestamp=timestamp,
            metadata={"test": "value"},
            resolved=False
        )

        assert alert.rule_name == "test_rule"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.message == "Test alert message"
        assert alert.current_value == 50
        assert alert.threshold_value == 100
        assert alert.timestamp == timestamp
        assert alert.metadata["test"] == "value"
        assert alert.resolved == False
        assert alert.resolved_at is None


class TestEmailNotificationChannel:
    """Test email notification channel."""

    def test_email_channel_creation(self):
        """Test email notification channel creation."""
        config = {
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'test@example.com',
            'password': 'password',
            'recipients': ['admin@example.com']
        }

        channel = EmailNotificationChannel("email", config)

        assert channel.name == "email"
        assert channel.config == config

    @patch('smtplib.SMTP')
    def test_email_send_alert(self, mock_smtp):
        """Test email alert sending."""
        config = {
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'test@example.com',
            'password': 'password',
            'recipients': ['admin@example.com']
        }

        channel = EmailNotificationChannel("email", config)

        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.HIGH,
            message="Test message",
            current_value=10,
            threshold_value=20,
            timestamp=datetime.now()
        )

        # Mock SMTP connection
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = channel.send_alert(alert)

        assert result == True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@example.com', 'password')
        mock_server.send_message.assert_called_once()

    def test_email_send_alert_missing_config(self):
        """Test email alert with missing configuration."""
        config = {
            'smtp_server': 'smtp.example.com',
            # Missing required fields
        }

        channel = EmailNotificationChannel("email", config)

        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.HIGH,
            message="Test message",
            current_value=10,
            threshold_value=20,
            timestamp=datetime.now()
        )

        result = channel.send_alert(alert)
        assert result == False


class TestSlackNotificationChannel:
    """Test Slack notification channel."""

    def test_slack_channel_creation(self):
        """Test Slack notification channel creation."""
        config = {'webhook_url': 'https://hooks.slack.com/webhook'}

        channel = SlackNotificationChannel("slack", config)

        assert channel.name == "slack"
        assert channel.config == config

    @patch('requests.post')
    def test_slack_send_alert(self, mock_post):
        """Test Slack alert sending."""
        config = {'webhook_url': 'https://hooks.slack.com/webhook'}

        channel = SlackNotificationChannel("slack", config)

        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.CRITICAL,
            message="Test message",
            current_value=5,
            threshold_value=10,
            timestamp=datetime.now()
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = channel.send_alert(alert)

        assert result == True
        mock_post.assert_called_once()

        # Verify request payload
        call_args = mock_post.call_args
        assert call_args[1]['json']['text'] == "Purchase Metrics Alert: test_alert"
        assert len(call_args[1]['json']['attachments']) == 1

    def test_slack_send_alert_missing_webhook(self):
        """Test Slack alert with missing webhook URL."""
        config = {}  # Missing webhook_url

        channel = SlackNotificationChannel("slack", config)

        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.HIGH,
            message="Test message",
            current_value=10,
            threshold_value=20,
            timestamp=datetime.now()
        )

        result = channel.send_alert(alert)
        assert result == False


class TestWebhookNotificationChannel:
    """Test webhook notification channel."""

    @patch('requests.post')
    def test_webhook_send_alert(self, mock_post):
        """Test webhook alert sending."""
        config = {
            'url': 'https://example.com/webhook',
            'headers': {'Authorization': 'Bearer token'}
        }

        channel = WebhookNotificationChannel("webhook", config)

        alert = Alert(
            rule_name="test_alert",
            severity=AlertSeverity.MEDIUM,
            message="Test message",
            current_value=15,
            threshold_value=20,
            timestamp=datetime.now()
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = channel.send_alert(alert)

        assert result == True
        mock_post.assert_called_once()

        # Verify request details
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://example.com/webhook'
        assert 'Authorization' in call_args[1]['headers']
        assert call_args[1]['json']['rule_name'] == "test_alert"


@pytest.mark.integration
class TestAlertManagerIntegration:
    """Integration tests for alert manager."""

    def test_full_alert_workflow(self):
        """Test complete alert workflow with notification channels."""
        # Create temporary metrics aggregator
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            metrics_aggregator = MetricsAggregator(db_path=db_path)
            alert_manager = AlertManager(metrics_aggregator=metrics_aggregator)

            # Add a mock notification channel
            mock_channel = Mock()
            mock_channel.name = "test_channel"
            mock_channel.send_alert.return_value = True

            alert_manager.add_notification_channel(mock_channel)

            # Add test data that should trigger an alert
            metrics_aggregator.record_purchase(
                stripe_payment_intent_id="pi_test",
                stripe_charge_id="ch_test",
                customer_email="test@example.com",
                customer_name="Test Customer",
                gross_amount_cents=100,  # Very low amount
                net_amount_cents=90,
                stripe_fee_cents=10,
                audit_type="basic"
            )

            # Aggregate metrics
            metrics = metrics_aggregator.aggregate_metrics(AggregationPeriod.DAILY)
            metrics_aggregator.store_aggregated_metrics(metrics)

            # Check alerts - should trigger revenue_drop alert
            alert_manager.check_alerts()

            # Verify alert was triggered and notification sent
            assert len(alert_manager.active_alerts) > 0
            mock_channel.send_alert.assert_called()

        finally:
            os.unlink(db_path)
