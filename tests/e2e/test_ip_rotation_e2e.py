"""
End-to-end tests for IP/Subuser Rotation System

These tests verify the complete IP rotation workflow from bounce detection
through rotation decision and execution, following BDD principles.
"""

import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta

from leadfactory.services.ip_rotation import (
    IPRotationService, RotationConfig, RotationReason,
    create_default_rotation_config
)
from leadfactory.services.bounce_monitor import (
    BounceRateMonitor, BounceRateConfig, BounceEvent
)
from leadfactory.services.threshold_detector import (
    ThresholdDetector, ThresholdConfig, ThresholdRule, ThresholdSeverity
)


class TestIPRotationE2E:
    """End-to-end tests for IP rotation system."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def bounce_config(self):
        """Create bounce rate configuration for testing."""
        return BounceRateConfig(
            rolling_window_hours=1,
            minimum_sample_size=5,
            warning_threshold=0.05,
            critical_threshold=0.10
        )

    @pytest.fixture
    def threshold_config(self):
        """Create threshold detection configuration."""
        return ThresholdConfig(
            rules=[
                ThresholdRule(
                    name="warning_threshold",
                    bounce_rate_threshold=0.05,
                    min_volume=10,
                    severity=ThresholdSeverity.WARNING
                ),
                ThresholdRule(
                    name="critical_threshold",
                    bounce_rate_threshold=0.10,
                    min_volume=10,
                    severity=ThresholdSeverity.CRITICAL
                )
            ],
            notification_cooldown_minutes=30
        )

    @pytest.fixture
    def rotation_config(self):
        """Create rotation configuration for testing."""
        return RotationConfig(
            default_cooldown_hours=1,
            max_rotations_per_hour=10,
            fallback_enabled=True,
            require_minimum_alternatives=1
        )

    @pytest.fixture
    def integrated_system(self, temp_db, bounce_config, threshold_config, rotation_config):
        """Create fully integrated IP rotation system."""
        # Initialize bounce monitor
        bounce_monitor = BounceRateMonitor(bounce_config, temp_db)

        # Initialize threshold detector
        threshold_detector = ThresholdDetector(threshold_config, bounce_monitor)

        # Initialize rotation service
        rotation_service = IPRotationService(rotation_config, bounce_monitor, threshold_detector)

        # Add some test IP/subuser combinations
        rotation_service.add_ip_subuser("192.168.1.1", "primary", priority=1)
        rotation_service.add_ip_subuser("192.168.1.2", "secondary", priority=2)
        rotation_service.add_ip_subuser("192.168.1.3", "tertiary", priority=3)

        return {
            'bounce_monitor': bounce_monitor,
            'threshold_detector': threshold_detector,
            'rotation_service': rotation_service
        }

    def test_complete_rotation_workflow_on_high_bounce_rate(self, integrated_system):
        """
        Test complete workflow: high bounce rate triggers threshold breach,
        which triggers IP rotation.

        Given: A system with multiple IP/subuser combinations
        When: One IP experiences high bounce rate above threshold
        Then: The system should automatically rotate to a different IP
        And: The original IP should be put in cooldown
        And: Future emails should use the new IP
        """
        bounce_monitor = integrated_system['bounce_monitor']
        threshold_detector = integrated_system['threshold_detector']
        rotation_service = integrated_system['rotation_service']

        # Given: Record normal email activity for primary IP
        primary_ip = "192.168.1.1"
        primary_subuser = "primary"

        # Record sent emails
        for i in range(50):
            bounce_monitor.record_sent_email(
                ip=primary_ip,
                subuser=primary_subuser,
                recipient=f"test{i}@example.com",
                timestamp=datetime.utcnow()
            )

        # When: Record high bounce rate (20% bounce rate)
        for i in range(10):
            bounce_monitor.record_bounce_event(
                ip=primary_ip,
                subuser=primary_subuser,
                recipient=f"test{i}@example.com",
                bounce_type="hard",
                timestamp=datetime.utcnow()
            )

        # Check that bounce rate is high
        bounce_rate = bounce_monitor.get_bounce_rate(primary_ip, primary_subuser)
        assert bounce_rate == 0.20  # 10 bounces out of 50 emails

        # Check threshold breach detection
        breaches = threshold_detector.check_thresholds(primary_ip, primary_subuser)
        assert len(breaches) > 0
        assert any(breach.severity == ThresholdSeverity.CRITICAL for breach in breaches)

        # Then: Perform rotation
        rotation_result = rotation_service.rotate_ip(
            primary_ip,
            primary_subuser,
            RotationReason.HIGH_BOUNCE_RATE
        )

        # Verify rotation occurred
        assert rotation_result is not None
        assert rotation_result.from_ip == primary_ip
        assert rotation_result.from_subuser == primary_subuser
        assert rotation_result.to_ip in ["192.168.1.2", "192.168.1.3"]
        assert rotation_result.reason == RotationReason.HIGH_BOUNCE_RATE

        # And: Verify original IP is in cooldown
        original_pool = rotation_service.get_ip_subuser_pool(primary_ip, primary_subuser)
        assert not original_pool.is_available()

        # And: Verify new IP is available and different
        new_ip = rotation_service.get_next_available_ip()
        assert new_ip is not None
        assert new_ip.ip != primary_ip

    def test_rotation_respects_priority_order(self, integrated_system):
        """
        Test that rotation selects IPs in priority order.

        Given: Multiple available IPs with different priorities
        When: Rotation is needed
        Then: The highest priority (lowest number) available IP should be selected
        """
        rotation_service = integrated_system['rotation_service']

        # Given: Disable highest priority IP to force rotation
        primary_pool = rotation_service.get_ip_subuser_pool("192.168.1.1", "primary")
        primary_pool.disable()

        # When: Get next available IP
        next_ip = rotation_service.get_next_available_ip()

        # Then: Should get second highest priority IP
        assert next_ip is not None
        assert next_ip.ip == "192.168.1.2"
        assert next_ip.subuser == "secondary"
        assert next_ip.priority == 2

    def test_rotation_handles_no_available_alternatives(self, integrated_system):
        """
        Test system behavior when no alternative IPs are available.

        Given: Only one IP/subuser combination
        When: That IP needs rotation
        Then: Rotation should fail gracefully
        And: Original IP should remain active
        """
        rotation_service = integrated_system['rotation_service']

        # Given: Disable all but one IP
        rotation_service.get_ip_subuser_pool("192.168.1.2", "secondary").disable()
        rotation_service.get_ip_subuser_pool("192.168.1.3", "tertiary").disable()

        # When: Try to rotate the only remaining IP
        result = rotation_service.rotate_ip(
            "192.168.1.1",
            "primary",
            RotationReason.HIGH_BOUNCE_RATE
        )

        # Then: Rotation should fail
        assert result is None

        # And: Original IP should remain active
        original_pool = rotation_service.get_ip_subuser_pool("192.168.1.1", "primary")
        assert original_pool.is_available()

    def test_cooldown_period_prevents_immediate_reuse(self, integrated_system):
        """
        Test that IPs in cooldown cannot be immediately reused.

        Given: An IP that has been rotated and is in cooldown
        When: Checking for available IPs
        Then: The cooldown IP should not be available
        And: Only non-cooldown IPs should be returned
        """
        rotation_service = integrated_system['rotation_service']

        # Given: Rotate an IP (puts it in cooldown)
        rotation_service.rotate_ip(
            "192.168.1.1",
            "primary",
            RotationReason.HIGH_BOUNCE_RATE
        )

        # When: Check available IPs
        available_ips = [
            pool for pool in rotation_service.ip_pool
            if pool.is_available()
        ]

        # Then: Cooldown IP should not be available
        cooldown_ips = [pool.ip for pool in available_ips if pool.ip == "192.168.1.1"]
        assert len(cooldown_ips) == 0

        # And: Other IPs should still be available
        assert len(available_ips) >= 1
        assert all(pool.ip != "192.168.1.1" for pool in available_ips)

    def test_rate_limiting_prevents_excessive_rotations(self, integrated_system):
        """
        Test that rate limiting prevents too many rotations in a short period.

        Given: A system with rate limiting configured
        When: Multiple rotation attempts are made rapidly
        Then: Only the allowed number should succeed
        And: Subsequent attempts should be blocked
        """
        rotation_service = integrated_system['rotation_service']

        # Given: Configure aggressive rate limiting for testing
        rotation_service.config.max_rotations_per_hour = 2

        successful_rotations = 0

        # When: Attempt multiple rotations rapidly
        for i in range(5):
            # Add a new IP for each rotation attempt
            test_ip = f"192.168.2.{i}"
            rotation_service.add_ip_subuser(test_ip, f"test_user_{i}", priority=10+i)

            result = rotation_service.rotate_ip(
                test_ip,
                f"test_user_{i}",
                RotationReason.MANUAL
            )

            if result is not None:
                successful_rotations += 1

        # Then: Only allowed number should succeed
        assert successful_rotations <= 2

    def test_statistics_tracking_accuracy(self, integrated_system):
        """
        Test that rotation statistics are accurately tracked.

        Given: A system with some rotation activity
        When: Statistics are requested
        Then: All metrics should be accurate and consistent
        """
        rotation_service = integrated_system['rotation_service']

        # Given: Perform some rotations
        rotation_service.rotate_ip("192.168.1.1", "primary", RotationReason.HIGH_BOUNCE_RATE)
        rotation_service.rotate_ip("192.168.1.2", "secondary", RotationReason.MANUAL)

        # When: Get statistics
        stats = rotation_service.get_rotation_statistics()

        # Then: Statistics should be accurate
        assert stats['total_rotations'] == 2
        assert stats['cooldown_ips'] == 2  # Both rotated IPs should be in cooldown
        assert stats['active_ips'] == 1   # Only tertiary should be active
        assert stats['disabled_ips'] == 0

        # Verify consistency
        total_ips = stats['active_ips'] + stats['cooldown_ips'] + stats['disabled_ips']
        assert total_ips == len(rotation_service.ip_pool)


if __name__ == "__main__":
    pytest.main([__file__])
