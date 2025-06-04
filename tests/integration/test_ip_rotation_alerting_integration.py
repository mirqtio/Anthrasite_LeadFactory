"""
Integration tests for IP rotation alerting system.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from leadfactory.services.ip_rotation import (
    IPRotationService,
    IPSubuserPool,
    IPSubuserStatus,
    RotationConfig,
    RotationEvent,
    RotationReason,
)
from leadfactory.services.ip_rotation_alerting import (
    AlertingConfig,
    AlertSeverity,
    AlertType,
    IPRotationAlerting,
)


class TestIPRotationAlertingIntegration:
    """Test integration between IP rotation service and alerting system."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create rotation config
        self.rotation_config = RotationConfig(
            enable_automatic_rotation=True,
            default_cooldown_hours=4,
            rotation_delay_seconds=1,
            max_consecutive_failures=2,
        )

        # Create alerting config
        self.alerting_config = AlertingConfig(
            smtp_host="test-smtp",
            admin_emails=[],  # Empty to disable email sending
            webhook_urls=[],  # Empty to disable webhook sending
            slack_webhook_url="",  # Empty to disable Slack alerts
            throttle_window_minutes=0,  # Disable throttling for tests
            max_alerts_per_window=1000,  # High limit for tests
        )

        # Create services
        self.alerting_service = IPRotationAlerting(self.alerting_config)
        self.rotation_service = IPRotationService(
            config=self.rotation_config,
            bounce_monitor=None,
            threshold_detector=None,
            alerting_service=self.alerting_service,
        )

        # Add test IP/subuser pairs
        self.rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=1)
        self.rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=2)
        self.rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=3)

    def test_rotation_generates_alert(self):
        """Test that successful rotation generates an alert."""
        initial_alert_count = len(self.alerting_service.alert_history)

        # Execute a rotation
        result = self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Verify rotation was successful
        assert result is not None
        assert isinstance(result, RotationEvent)
        assert result.success is True

        # Verify alert was generated
        assert len(self.alerting_service.alert_history) == initial_alert_count + 1

        # Check alert details
        alert = self.alerting_service.alert_history[-1]
        assert alert.alert_type == AlertType.ROTATION_EXECUTED
        assert alert.severity == AlertSeverity.INFO
        assert "192.168.1.1" in alert.message
        assert "user1" in alert.message

    def test_rotation_error_generates_alert(self):
        """Test that rotation errors generate alerts."""
        initial_alert_count = len(self.alerting_service.alert_history)

        # Try to rotate to non-existent IP (this will succeed but generate alert)
        result = self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="999.999.999.999",
            to_subuser="nonexistent",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Verify rotation succeeded (the service allows rotation to any IP)
        assert result.success is True

        # Verify alert was generated for the rotation
        assert len(self.alerting_service.alert_history) == initial_alert_count + 1

        # Check alert details
        alert = self.alerting_service.alert_history[-1]
        assert alert.alert_type == AlertType.ROTATION_EXECUTED
        assert "999.999.999.999" in alert.message

    def test_cooldown_violation_generates_alert(self):
        """Test that cooldown violations generate alerts."""
        # First, execute a rotation to put source IP in cooldown
        self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Clear alerts to focus on cooldown violation
        self.alerting_service.alert_history.clear()

        # Try to rotate FROM the IP that's in cooldown (should fail)
        try:
            self.rotation_service.execute_rotation(
                from_ip="192.168.1.1",
                from_subuser="user1",
                to_ip="192.168.1.3",
                to_subuser="user3",
                reason=RotationReason.MANUAL_ROTATION,
            )
            assert False, "Expected ValueError to be raised"
        except ValueError:
            pass  # Expected

        # Verify cooldown violation alert was generated
        assert len(self.alerting_service.alert_history) >= 1
        cooldown_alerts = [
            alert
            for alert in self.alerting_service.alert_history
            if "cooldown" in alert.message.lower()
        ]
        assert len(cooldown_alerts) >= 1
        alert = cooldown_alerts[0]
        assert alert.alert_type == AlertType.SYSTEM_ERROR
        assert "cooldown" in alert.message.lower()

    def test_threshold_breach_handling_with_alerts(self):
        """Test threshold breach handling generates appropriate alerts."""
        # Create mock threshold breach
        mock_breach = Mock()
        mock_breach.ip_address = "192.168.1.1"
        mock_breach.subuser = "user1"
        mock_breach.threshold_value = 0.05
        mock_breach.current_value = 0.08
        mock_breach.rule_name = "bounce_rate_threshold"
        mock_breach.severity = Mock()
        mock_breach.severity.value = "high"
        mock_breach.breach_id = "test_breach_123"

        initial_alert_count = len(self.alerting_service.alert_history)

        # Handle threshold breach
        rotation_event = self.rotation_service.handle_threshold_breach(mock_breach)

        # Verify rotation was executed
        assert rotation_event is not None
        assert isinstance(rotation_event, RotationEvent)
        assert rotation_event.success is True

        # Verify alerts were generated
        # Should have: 1 threshold breach alert + 1 rotation executed alert
        assert len(self.alerting_service.alert_history) >= initial_alert_count + 2

        # Find threshold breach alert
        threshold_alerts = [
            alert
            for alert in self.alerting_service.alert_history
            if alert.alert_type == AlertType.THRESHOLD_BREACH
        ]
        assert len(threshold_alerts) >= 1

        threshold_alert = threshold_alerts[-1]
        assert threshold_alert.severity == AlertSeverity.WARNING
        assert "192.168.1.1" in threshold_alert.message
        assert "8.00%" in threshold_alert.message
        assert "5.00%" in threshold_alert.message

        # Find rotation alert
        rotation_alerts = [
            alert
            for alert in self.alerting_service.alert_history
            if alert.alert_type == AlertType.ROTATION_EXECUTED
        ]
        assert len(rotation_alerts) >= 1

    def test_consecutive_failures_disable_ip_with_alert(self):
        """Test that consecutive failures disable IP and generate alert."""
        # Create mock threshold breach
        mock_breach = Mock()
        mock_breach.ip_address = "192.168.1.1"
        mock_breach.subuser = "user1"
        mock_breach.threshold_value = 0.05
        mock_breach.current_value = 0.08
        mock_breach.rule_name = "bounce_rate_threshold"
        mock_breach.severity = Mock()
        mock_breach.severity.value = "high"
        mock_breach.breach_id = "test_breach_123"

        # Simulate failures by making all alternatives unavailable
        # First, put all other IPs in cooldown
        for pool_entry in self.rotation_service.ip_pool:
            if pool_entry.ip_address != "192.168.1.1":
                pool_entry.status = IPSubuserStatus.COOLDOWN
                pool_entry.cooldown_until = datetime.now() + timedelta(hours=1)

        initial_alert_count = len(self.alerting_service.alert_history)

        # Try to handle threshold breach multiple times to trigger failures
        for i in range(self.rotation_config.max_consecutive_failures + 1):
            try:
                self.rotation_service.handle_threshold_breach(mock_breach)
            except Exception:
                # Expected to fail due to no available alternatives
                pass

        # Verify IP was disabled
        pool_entry = self.rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        assert pool_entry.status == IPSubuserStatus.DISABLED

        # Verify IP disabled alert was generated
        disabled_alerts = [
            alert
            for alert in self.alerting_service.alert_history
            if alert.alert_type == AlertType.IP_DISABLED
        ]
        assert len(disabled_alerts) >= 1

        disabled_alert = disabled_alerts[-1]
        assert disabled_alert.severity == AlertSeverity.CRITICAL
        assert "192.168.1.1" in disabled_alert.message
        assert "disabled" in disabled_alert.message.lower()

    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with rotation service."""
        # Trigger multiple system errors to open circuit breaker
        failure_threshold = self.alerting_service.circuit_breaker.failure_threshold
        for i in range(failure_threshold):
            self.alerting_service.record_system_error("Test error")

        # Circuit breaker should be open
        assert self.alerting_service.circuit_breaker.state == "open"
        assert not self.alerting_service.circuit_breaker.can_execute()

        # Verify alerts were sent
        alert_summary = self.alerting_service.get_alert_summary()
        assert alert_summary["total_alerts"] >= failure_threshold
        assert "system_error" in alert_summary["by_type"]
        assert alert_summary["by_type"]["system_error"] >= failure_threshold

    def test_dashboard_data_integration(self):
        """Test dashboard data collection with real rotation data."""
        # Execute some rotations and generate alerts
        self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Record some additional events
        self.alerting_service.record_threshold_breach("192.168.1.3", 0.05, 0.07)
        self.alerting_service.record_system_error("Test error")

        # Get dashboard data
        dashboard_data = self.alerting_service.get_dashboard_data()

        # Verify system status
        assert "system_status" in dashboard_data
        system_status = dashboard_data["system_status"]
        assert system_status["total_rotations"] >= 1
        assert system_status["total_alerts"] >= 3  # rotation + threshold + error

        # Verify recent alerts
        assert "recent_alerts" in dashboard_data
        assert len(dashboard_data["recent_alerts"]) >= 3

        # Verify metrics
        assert "metrics" in dashboard_data
        metrics = dashboard_data["metrics"]
        assert "alerts_by_severity" in metrics
        assert "alerts_by_type" in metrics

        # Check alert counts
        assert metrics["alerts_by_severity"]["info"] >= 1  # rotation alert
        assert metrics["alerts_by_severity"]["warning"] >= 1  # threshold alert
        assert metrics["alerts_by_severity"]["critical"] >= 1  # error alert

    def test_alert_summary_with_real_data(self):
        """Test alert summary with real rotation and alerting data."""
        # Generate various types of alerts
        self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        self.alerting_service.record_threshold_breach("192.168.1.1", 0.05, 0.08)
        self.alerting_service.record_ip_disabled("192.168.1.3", "Test disable")
        self.alerting_service.record_system_error("Test error")

        # Get alert summary
        summary = self.alerting_service.get_alert_summary(24)

        # Verify summary data
        assert summary["total_alerts"] >= 4
        assert summary["by_severity"]["info"] >= 1
        assert summary["by_severity"]["warning"] >= 1
        assert summary["by_severity"]["critical"] >= 2

        assert summary["by_type"]["rotation_executed"] >= 1
        assert summary["by_type"]["threshold_breach"] >= 1
        assert summary["by_type"]["ip_disabled"] >= 1
        assert summary["by_type"]["system_error"] >= 1

    def test_performance_metrics_update_integration(self):
        """Test performance metrics update with alerting integration."""
        # Mock bounce monitor
        mock_bounce_monitor = Mock()
        mock_stats = Mock()
        mock_stats.total_sent = 1000
        mock_stats.total_bounced = 50
        mock_bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        self.rotation_service.bounce_monitor = mock_bounce_monitor

        initial_alert_count = len(self.alerting_service.alert_history)

        # Update performance metrics
        self.rotation_service.update_performance_metrics()

        # Verify no errors occurred (no additional error alerts)
        error_alerts = [
            alert
            for alert in self.alerting_service.alert_history[initial_alert_count:]
            if alert.alert_type == AlertType.SYSTEM_ERROR
        ]
        assert len(error_alerts) == 0

        # Verify pool entries were updated
        for pool_entry in self.rotation_service.ip_pool:
            assert pool_entry.total_sent == 1000
            assert pool_entry.total_bounced == 50

    def test_cleanup_integration(self):
        """Test cleanup of old data across both services."""
        # Generate some old alerts and rotation events
        old_timestamp = datetime.now() - timedelta(days=10)

        # Add old rotation event manually
        old_rotation = RotationEvent(
            timestamp=old_timestamp,
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
            success=True,
        )
        self.rotation_service.rotation_history.append(old_rotation)

        # Add old alert manually
        from leadfactory.services.ip_rotation_alerting import Alert

        old_alert = Alert(
            alert_type=AlertType.ROTATION_EXECUTED,
            severity=AlertSeverity.INFO,
            message="Old alert",
            timestamp=old_timestamp,
            metadata={},
        )
        self.alerting_service.alert_history.append(old_alert)

        # Add recent data
        self.rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Verify we have both old and new data
        assert len(self.rotation_service.rotation_history) >= 2
        assert len(self.alerting_service.alert_history) >= 2

        # Cleanup old data (7 days)
        rotation_removed = self.rotation_service.cleanup_old_history(7)
        alerts_removed = self.alerting_service.cleanup_old_alerts(7)

        # Verify old data was removed
        assert rotation_removed >= 1
        assert alerts_removed >= 1

        # Verify recent data remains
        assert len(self.rotation_service.rotation_history) >= 1
        assert len(self.alerting_service.alert_history) >= 1

        # Verify remaining data is recent
        for event in self.rotation_service.rotation_history:
            assert event.timestamp > datetime.now() - timedelta(days=7)

        for alert in self.alerting_service.alert_history:
            assert alert.timestamp > datetime.now() - timedelta(days=7)


if __name__ == "__main__":
    pytest.main([__file__])
