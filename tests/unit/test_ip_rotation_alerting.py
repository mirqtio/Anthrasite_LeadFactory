"""
Unit tests for IP rotation alerting system.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.services.ip_rotation_alerting import (
    Alert,
    AlertingConfig,
    CircuitBreaker,
    IPRotationAlerting,
    AlertType,
    AlertSeverity,
)


class TestAlert:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test alert creation with all fields."""
        alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"key": "value"},
            alert_id="test-123",
        )

        assert alert.alert_id == "test-123"
        assert alert.alert_type == AlertType.ROTATION_EXECUTED
        assert alert.severity == AlertSeverity.INFO
        assert alert.message == "Test alert"
        assert alert.metadata == {"key": "value"}

    def test_alert_auto_id_generation(self):
        """Test automatic alert ID generation."""
        timestamp = datetime.now()
        alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Test alert",
            timestamp=timestamp,
            metadata={"key": "value"},
        )

        expected_id = f"rotation_executed_{int(timestamp.timestamp())}"
        assert alert.alert_id == expected_id


class TestAlertingConfig:
    """Test AlertingConfig dataclass."""

    def test_default_config(self):
        """Test default alerting configuration."""
        config = AlertingConfig()

        assert config.smtp_host == "localhost"
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True
        assert config.admin_emails == []
        assert config.webhook_urls == []
        assert config.throttle_window_minutes == 15
        assert config.max_alerts_per_window == 10

    def test_custom_config(self):
        """Test custom alerting configuration."""
        config = AlertingConfig(
            smtp_host="smtp.example.com",
            smtp_port=465,
            admin_emails=["admin@example.com"],
            webhook_urls=["https://example.com/webhook"],
            throttle_window_minutes=10,
            max_alerts_per_window=20,
        )

        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.admin_emails == ["admin@example.com"]
        assert config.webhook_urls == ["https://example.com/webhook"]
        assert config.throttle_window_minutes == 10
        assert config.max_alerts_per_window == 20


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)

        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.can_execute() is True

    def test_record_success(self):
        """Test recording successful operations."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)

        # Record some failures first
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        # Record success should reset failure count
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_record_failure_opens_circuit(self):
        """Test that failures open the circuit breaker."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)

        # Record failures up to threshold
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.can_execute() is True

        # This should open the circuit
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False
        assert cb.last_failure_time is not None

    def test_half_open_state(self):
        """Test circuit breaker half-open state after timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)  # 1 second

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Manually set last failure time to past
        cb.last_failure_time = datetime.now() - timedelta(seconds=2)

        # Should be half-open now
        assert cb.can_execute() is True
        assert cb.state == "half-open"

    def test_reset(self):
        """Test circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=300)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Reset should close the circuit
        cb.record_success()  # This acts as reset
        assert cb.state == "closed"
        assert cb.failure_count == 0


class TestIPRotationAlerting:
    """Test IPRotationAlerting class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AlertingConfig(
            smtp_host="localhost",
            smtp_port=587,
            smtp_use_tls=True,
            admin_emails=["admin@example.com"],
            throttle_window_minutes=1,
            max_alerts_per_window=10,
        )
        self.alerting = IPRotationAlerting(self.config)

    def test_initialization(self):
        """Test alerting system initialization."""
        assert self.alerting.config == self.config
        assert len(self.alerting.alert_history) == 0
        assert isinstance(self.alerting.circuit_breaker, CircuitBreaker)
        assert "total_rotations" in self.alerting.metrics

    @patch("smtplib.SMTP")
    def test_send_email_alert(self, mock_smtp):
        """Test sending email alerts."""
        # Configure mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"key": "value"},
            alert_id="test-123",
        )

        # Call the method - it doesn't return anything
        self.alerting._send_email_alert(alert)

        # Verify SMTP was called
        mock_smtp.assert_called_once_with(
            self.alerting.config.smtp_host, self.alerting.config.smtp_port
        )
        mock_server.starttls.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("requests.post")
    def test_send_webhook_alert(self, mock_post):
        """Test sending webhook alerts."""
        # Configure webhook URLs in the config
        self.alerting.config.webhook_urls = ["https://example.com/webhook"]

        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"key": "value"},
            alert_id="test-123",
        )

        # Call the method - it doesn't return anything
        self.alerting._send_webhook_alerts(alert)

        # Verify the webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["alert_id"] == "test-123"
        assert call_args[1]["json"]["message"] == "Test alert"

    def test_send_alert(self):
        """Test sending alerts through the main interface."""
        initial_count = len(self.alerting.alert_history)

        result = self.alerting.send_alert(
            AlertType.ROTATION_EXECUTED,
            AlertSeverity.INFO,
            "Test rotation alert",
            metadata={"from_ip": "192.168.1.1", "to_ip": "192.168.1.2"},
        )

        assert result is True
        assert len(self.alerting.alert_history) == initial_count + 1

        # Check the alert was stored
        alert = self.alerting.alert_history[-1]
        assert alert.alert_type == AlertType.ROTATION_EXECUTED
        assert alert.severity == AlertSeverity.INFO
        assert alert.message == "Test rotation alert"
        assert alert.metadata["from_ip"] == "192.168.1.1"

    def test_record_rotation(self):
        """Test recording rotation events."""
        initial_count = len(self.alerting.alert_history)

        self.alerting.record_rotation("192.168.1.1", "192.168.1.2", "manual")

        assert len(self.alerting.alert_history) == initial_count + 1
        alert = self.alerting.alert_history[-1]
        assert alert.alert_type == AlertType.ROTATION_EXECUTED
        assert alert.severity == AlertSeverity.INFO
        assert "192.168.1.1" in alert.message
        assert "192.168.1.2" in alert.message

    def test_record_threshold_breach(self):
        """Test recording threshold breach events."""
        initial_count = len(self.alerting.alert_history)

        self.alerting.record_threshold_breach("192.168.1.1", 0.05, 0.08)

        assert len(self.alerting.alert_history) == initial_count + 1
        alert = self.alerting.alert_history[-1]
        assert alert.alert_type == AlertType.THRESHOLD_BREACH
        assert alert.severity == AlertSeverity.WARNING
        assert "192.168.1.1" in alert.message
        assert "8.00%" in alert.message

    def test_record_ip_disabled(self):
        """Test recording IP disabled events."""
        initial_count = len(self.alerting.alert_history)

        self.alerting.record_ip_disabled("192.168.1.1", "Too many failures")

        assert len(self.alerting.alert_history) == initial_count + 1
        alert = self.alerting.alert_history[-1]
        assert alert.alert_type == AlertType.IP_DISABLED
        assert alert.severity == AlertSeverity.CRITICAL
        assert "192.168.1.1" in alert.message

    def test_record_system_error(self):
        """Test recording system error events."""
        initial_count = len(self.alerting.alert_history)

        self.alerting.record_system_error("Database connection failed")

        assert len(self.alerting.alert_history) == initial_count + 1
        alert = self.alerting.alert_history[-1]
        assert alert.alert_type == AlertType.SYSTEM_ERROR
        assert alert.severity == AlertSeverity.CRITICAL
        assert "Database connection failed" in alert.message

    def test_get_alert_summary(self):
        """Test getting alert summary."""
        # Add some test alerts
        now = datetime.now()
        for i in range(3):
            alert = Alert(
                alert_type=AlertType.ROTATION_EXECUTED,
                severity=AlertSeverity.INFO,
                message=f"Test alert {i}",
                timestamp=now - timedelta(hours=i),
                metadata={"key": "value"},
                alert_id=f"test-{i}",
            )
            self.alerting.alert_history.append(alert)

        summary = self.alerting.get_alert_summary(24)

        assert summary["total_alerts"] == 3
        assert summary["by_severity"]["info"] == 3
        assert summary["by_type"]["rotation_executed"] == 3
        assert summary["time_period_hours"] == 24

    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        # Add some test data
        alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"key": "value"},
            alert_id="test-1",
        )
        self.alerting.alert_history.append(alert)

        dashboard_data = self.alerting.get_dashboard_data()

        assert "system_status" in dashboard_data
        assert "recent_alerts" in dashboard_data
        assert "metrics" in dashboard_data
        assert "circuit_breaker_status" in dashboard_data
        assert "alert_counts" in dashboard_data

        # Check system status
        system_status = dashboard_data["system_status"]
        assert "total_alerts" in system_status
        assert "health" in system_status
        assert "last_rotation" in system_status
        assert "total_rotations" in system_status

    def test_cleanup_old_alerts(self):
        """Test cleaning up old alerts."""
        # Add old and new alerts
        old_alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Old alert",
            timestamp=datetime.now() - timedelta(days=8),
            metadata={"key": "value"},
            alert_id="old",
        )
        new_alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="New alert",
            timestamp=datetime.now(),
            metadata={"key": "value"},
            alert_id="new",
        )

        self.alerting.alert_history.extend([old_alert, new_alert])
        assert len(self.alerting.alert_history) == 2

        # Call cleanup - it doesn't return the count
        self.alerting.cleanup_old_alerts(7)

        # Verify only the new alert remains
        assert len(self.alerting.alert_history) == 1
        assert self.alerting.alert_history[0].alert_id == "new"


if __name__ == "__main__":
    pytest.main([__file__])
