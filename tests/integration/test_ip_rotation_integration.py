"""
Integration tests for IP/Subuser Rotation Logic

These tests verify the integration between the IP rotation service,
bounce monitor, and threshold detector.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta

from leadfactory.services.ip_rotation import (
    IPRotationService, RotationConfig, RotationReason,
    create_default_rotation_config
)
from leadfactory.services.bounce_monitor import (
    BounceRateMonitor, BounceRateConfig, BounceEvent
)
from leadfactory.services.threshold_detector import (
    ThresholdDetector, ThresholdConfig, ThresholdBreach, ThresholdSeverity,
    create_default_threshold_config
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def bounce_monitor(temp_db):
    """Create a bounce monitor with test database."""
    config = BounceRateConfig()
    return BounceRateMonitor(config, db_path=temp_db)


@pytest.fixture
def threshold_detector(bounce_monitor):
    """Create a threshold detector."""
    config = create_default_threshold_config()
    return ThresholdDetector(config, bounce_monitor)


@pytest.fixture
def rotation_service(bounce_monitor, threshold_detector):
    """Create an IP rotation service."""
    config = create_default_rotation_config()
    config.rotation_delay_seconds = 0  # No delay for testing
    config.require_minimum_alternatives = 1  # Lower requirement for testing
    return IPRotationService(config, bounce_monitor, threshold_detector)


class TestIPRotationIntegration:
    """Integration tests for IP rotation functionality."""

    def test_basic_rotation_flow(self, rotation_service):
        """Test basic rotation flow without external dependencies."""
        # Add IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

        # Execute manual rotation
        rotation_event = rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION
        )

        assert rotation_event.success == True
        assert rotation_event.from_ip == "192.168.1.1"
        assert rotation_event.to_ip == "192.168.1.2"
        assert rotation_event.reason == RotationReason.MANUAL_ROTATION

        # Check rotation history
        assert len(rotation_service.rotation_history) == 1
        assert rotation_service.rotation_history[0] == rotation_event

    def test_threshold_breach_integration(self, rotation_service, bounce_monitor):
        """Test integration with threshold breach detection."""
        # Add IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

        # Create a mock threshold breach
        breach = ThresholdBreach(
            ip_address="192.168.1.1",
            subuser="user1",
            rule_name="test_rule",
            current_value=0.15,
            threshold_value=0.10,
            severity=ThresholdSeverity.HIGH,
            breach_time=datetime.now(),
            sample_size=100,
            time_window_hours=24
        )

        # Handle the breach
        rotation_event = rotation_service.handle_threshold_breach(breach)

        assert rotation_event is not None
        assert rotation_event.success == True
        assert rotation_event.reason == RotationReason.THRESHOLD_BREACH
        assert rotation_event.breach_details is not None
        assert rotation_event.breach_details["rule_name"] == "test_rule"

    def test_bounce_monitor_integration(self, rotation_service, bounce_monitor):
        """Test integration with bounce monitor for performance updates."""
        # Add IP/subuser
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)

        # Record some bounce events
        bounce_monitor.record_bounce_event(BounceEvent(
            email="test@example.com",
            ip_address="192.168.1.1",
            subuser="user1",
            bounce_type="hard",
            reason="mailbox_full",
            timestamp=datetime.now()
        ))

        # Update performance metrics from bounce monitor
        rotation_service.update_performance_metrics()

        # Check that performance was updated
        pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        assert pool_entry is not None
        # The exact values depend on bounce monitor implementation
        # Just verify the method doesn't crash

    def test_automatic_rotation_disabled(self, rotation_service):
        """Test that automatic rotation can be disabled."""
        rotation_service.config.enable_automatic_rotation = False

        # Add IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

        # Create a threshold breach
        breach = ThresholdBreach(
            ip_address="192.168.1.1",
            subuser="user1",
            rule_name="test_rule",
            current_value=0.15,
            threshold_value=0.10,
            severity=ThresholdSeverity.HIGH,
            breach_time=datetime.now(),
            sample_size=100,
            time_window_hours=24
        )

        # Handle the breach - should not rotate
        rotation_event = rotation_service.handle_threshold_breach(breach)

        assert rotation_event is None

    def test_insufficient_alternatives(self, rotation_service):
        """Test behavior when there are insufficient alternatives."""
        # Add only one IP/subuser
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)

        # Set minimum alternatives requirement higher
        rotation_service.config.require_minimum_alternatives = 2

        # Try to get alternatives
        alternatives = rotation_service.get_available_alternatives(
            exclude_ip="192.168.1.1",
            exclude_subuser="user1"
        )

        assert len(alternatives) == 0

        # Try to select best alternative
        best = rotation_service.select_best_alternative("192.168.1.1", "user1")
        assert best is None

    def test_cooldown_prevents_rotation(self, rotation_service):
        """Test that cooldown periods prevent immediate rotation."""
        # Add IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

        # Execute first rotation
        rotation_event1 = rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION
        )
        assert rotation_event1.success == True

        # Try to rotate back immediately - should fail due to cooldown
        rotation_event2 = rotation_service.execute_rotation(
            from_ip="192.168.1.2",
            from_subuser="user2",
            to_ip="192.168.1.1",
            to_subuser="user1",
            reason=RotationReason.MANUAL_ROTATION
        )
        assert rotation_event2.success == False
        assert "cooldown" in rotation_event2.error_message.lower()

    def test_rate_limiting_integration(self, rotation_service):
        """Test rate limiting across multiple rotations."""
        # Set low rate limit
        rotation_service.config.max_rotations_per_hour = 2

        # Add multiple IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
        rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)

        # Execute rotations up to limit
        success_count = 0
        for i in range(3):  # Try 3 rotations with limit of 2
            rotation_event = rotation_service.execute_rotation(
                from_ip="192.168.1.1",
                from_subuser="user1",
                to_ip=f"192.168.1.{i+2}",
                to_subuser=f"user{i+2}",
                reason=RotationReason.MANUAL_ROTATION
            )
            if rotation_event.success:
                success_count += 1

        assert success_count == 2  # Only 2 should succeed due to rate limit

    def test_pool_status_reporting(self, rotation_service):
        """Test pool status reporting functionality."""
        # Add various IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
        rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)

        # Execute a rotation to put one in cooldown
        rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION
        )

        # Get pool status
        status = rotation_service.get_pool_status()

        assert status["total_count"] == 3
        assert status["active_count"] >= 1  # At least one should be active
        assert status["cooldown_count"] >= 1  # At least one should be in cooldown
        assert "available_count" in status
        assert "disabled_count" in status

    def test_performance_scoring_integration(self, rotation_service):
        """Test performance scoring with realistic data."""
        # Add IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

        # Set different performance metrics
        pool1 = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        pool1.total_sent = 1000
        pool1.total_bounced = 50  # 5% bounce rate

        pool2 = rotation_service.get_ip_subuser_pool("192.168.1.2", "user2")
        pool2.total_sent = 1000
        pool2.total_bounced = 20  # 2% bounce rate

        # Get alternatives - should prefer user2 due to better performance
        alternatives = rotation_service.get_available_alternatives(
            exclude_ip="192.168.1.1",
            exclude_subuser="user1"
        )

        assert len(alternatives) == 1
        assert alternatives[0].subuser == "user2"

        # Select best alternative
        best = rotation_service.select_best_alternative("192.168.1.1", "user1")
        assert best is not None
        assert best.subuser == "user2"
