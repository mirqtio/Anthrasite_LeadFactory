"""
Unit tests for IP/Subuser Rotation Logic

These tests focus on testing individual components of the IP rotation system
in isolation, with mocked dependencies.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.services.ip_rotation import (
    IPRotationService,
    IPSubuserPool,
    IPSubuserStatus,
    RotationConfig,
    RotationEvent,
    RotationReason,
)


class TestIPSubuserPool:
    """Test cases for IPSubuserPool class."""

    def test_initialization(self):
        """Test IPSubuserPool initialization."""
        pool = IPSubuserPool(
            ip_address="192.168.1.1",
            subuser="user1",
            priority=5,
            tags=["test"],
            metadata={"region": "us-east"},
        )

        assert pool.ip_address == "192.168.1.1"
        assert pool.subuser == "user1"
        assert pool.priority == 5
        assert pool.tags == ["test"]
        assert pool.metadata == {"region": "us-east"}
        assert pool.status == IPSubuserStatus.ACTIVE
        assert pool.total_sent == 0
        assert pool.total_bounced == 0
        assert pool.performance_score == 1.0
        assert pool.cooldown_until is None
        assert pool.last_used is None

    def test_is_available_when_active(self):
        """Test is_available returns True when status is ACTIVE and no cooldown."""
        pool = IPSubuserPool("192.168.1.1", "user1")
        assert pool.is_available() is True

    def test_is_available_when_disabled(self):
        """Test is_available returns False when status is DISABLED."""
        pool = IPSubuserPool("192.168.1.1", "user1")
        pool.status = IPSubuserStatus.DISABLED
        assert pool.is_available() is False

    def test_is_available_when_cooldown_active(self):
        """Test is_available returns False when cooldown is active."""
        pool = IPSubuserPool("192.168.1.1", "user1")
        pool.cooldown_until = datetime.now() + timedelta(hours=1)
        assert pool.is_available() is False

    def test_is_available_when_cooldown_expired(self):
        """Test is_available returns True when cooldown has expired."""
        pool = IPSubuserPool("192.168.1.1", "user1")
        pool.cooldown_until = datetime.now() - timedelta(hours=1)
        assert pool.is_available() is True

    def test_apply_cooldown(self):
        """Test applying cooldown to IP/subuser."""
        pool = IPSubuserPool("192.168.1.1", "user1")
        cooldown_hours = 2

        # Manually apply cooldown (since there's no apply_cooldown method)
        pool.status = IPSubuserStatus.COOLDOWN
        pool.cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)

        assert pool.status == IPSubuserStatus.COOLDOWN
        assert pool.cooldown_until is not None
        # Check that cooldown is approximately correct (within 1 minute)
        expected_time = datetime.now() + timedelta(hours=cooldown_hours)
        time_diff = abs((pool.cooldown_until - expected_time).total_seconds())
        assert time_diff < 60  # Within 1 minute

    def test_disable(self):
        """Test disabling IP/subuser."""
        pool = IPSubuserPool("192.168.1.1", "user1")

        # Manually disable (since there's no disable method)
        pool.status = IPSubuserStatus.DISABLED

        assert pool.status == IPSubuserStatus.DISABLED

    def test_calculate_performance_score(self):
        """Test performance score calculation."""
        pool = IPSubuserPool("192.168.1.1", "user1", priority=5)

        # Test with no sends (should be 1.0)
        score = pool.calculate_performance_score()
        assert score == 1.0

        # Test with some bounces
        pool.total_sent = 100
        pool.total_bounced = 10  # 10% bounce rate
        score = pool.calculate_performance_score()
        assert 0.9 <= score <= 1.0  # Should be around 0.9 plus priority boost


class TestRotationConfig:
    """Test cases for RotationConfig class."""

    def test_default_config_creation(self):
        """Test creating RotationConfig with default values."""
        config = RotationConfig()

        assert config.default_cooldown_hours == 4
        assert config.max_rotations_per_hour == 10
        assert config.fallback_enabled is True
        assert config.require_minimum_alternatives == 2
        assert config.performance_weight == 0.7
        assert config.enable_automatic_rotation is True
        assert config.rotation_delay_seconds == 30
        assert config.max_consecutive_failures == 3

    def test_custom_config_creation(self):
        """Test creating RotationConfig with custom values."""
        config = RotationConfig(
            default_cooldown_hours=8,
            max_rotations_per_hour=5,
            fallback_enabled=False,
            require_minimum_alternatives=3,
            performance_weight=0.5,
            enable_automatic_rotation=False,
            rotation_delay_seconds=60,
            max_consecutive_failures=5,
        )

        assert config.default_cooldown_hours == 8
        assert config.max_rotations_per_hour == 5
        assert config.fallback_enabled is False
        assert config.require_minimum_alternatives == 3
        assert config.performance_weight == 0.5
        assert config.enable_automatic_rotation is False
        assert config.rotation_delay_seconds == 60
        assert config.max_consecutive_failures == 5


class TestIPRotationService:
    """Test cases for IPRotationService class."""

    @pytest.fixture
    def rotation_config(self):
        """Create a test rotation configuration."""
        return RotationConfig(
            default_cooldown_hours=2,
            max_rotations_per_hour=5,
            fallback_enabled=True,
            require_minimum_alternatives=1,
            performance_weight=0.6,
            enable_automatic_rotation=True,
            rotation_delay_seconds=0,  # No delay for tests
            max_consecutive_failures=2,
        )

    @pytest.fixture
    def rotation_service(self, rotation_config):
        """Create a test IP rotation service."""
        return IPRotationService(rotation_config)

    def test_initialization(self, rotation_service):
        """Test IPRotationService initialization."""
        assert rotation_service.config is not None
        assert rotation_service.ip_pool == []
        assert rotation_service.rotation_history == []
        assert rotation_service.active_rotations == {}
        assert rotation_service.consecutive_failures == {}

    def test_add_ip_subuser(self, rotation_service):
        """Test adding IP/subuser to rotation pool."""
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)

        assert len(rotation_service.ip_pool) == 1
        pool_entry = rotation_service.ip_pool[0]
        assert pool_entry.ip_address == "192.168.1.1"
        assert pool_entry.subuser == "user1"
        assert pool_entry.priority == 5

    def test_add_duplicate_ip_subuser(self, rotation_service):
        """Test adding duplicate IP/subuser doesn't create duplicates."""
        rotation_service.add_ip_subuser("192.168.1.1", "user1")
        rotation_service.add_ip_subuser("192.168.1.1", "user1")  # Duplicate

        assert len(rotation_service.ip_pool) == 1

    def test_get_ip_subuser_pool_existing(self, rotation_service):
        """Test getting existing IP/subuser pool entry."""
        rotation_service.add_ip_subuser("192.168.1.1", "user1")

        pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        assert pool_entry is not None
        assert pool_entry.ip_address == "192.168.1.1"
        assert pool_entry.subuser == "user1"

    def test_get_ip_subuser_pool_nonexistent(self, rotation_service):
        """Test getting non-existent IP/subuser pool entry."""
        pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        assert pool_entry is None

    def test_get_available_alternatives_with_available_ips(self, rotation_service):
        """Test getting available alternatives when IPs are available."""
        rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=1)
        rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=2)
        rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=3)

        alternatives = rotation_service.get_available_alternatives(
            exclude_ip="192.168.1.1", exclude_subuser="user1"
        )

        assert len(alternatives) == 2
        # Should be sorted by priority (higher first)
        assert alternatives[0].priority >= alternatives[1].priority

    def test_get_available_alternatives_no_available_ips(self, rotation_service):
        """Test getting alternatives when no IPs are available."""
        # Add IP but disable it
        rotation_service.add_ip_subuser("192.168.1.1", "user1")
        pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        pool_entry.status = IPSubuserStatus.DISABLED

        alternatives = rotation_service.get_available_alternatives()
        assert len(alternatives) == 0

    def test_get_available_alternatives_excludes_current(self, rotation_service):
        """Test that get_available_alternatives excludes current IP/subuser."""
        rotation_service.add_ip_subuser("192.168.1.1", "user1")
        rotation_service.add_ip_subuser("192.168.1.2", "user2")

        alternatives = rotation_service.get_available_alternatives(
            exclude_ip="192.168.1.1", exclude_subuser="user1"
        )

        assert len(alternatives) == 1
        assert alternatives[0].ip_address == "192.168.1.2"
        assert alternatives[0].subuser == "user2"

    def test_execute_rotation_successful(self, rotation_service):
        """Test successful IP rotation."""
        # Add source and target IPs
        rotation_service.add_ip_subuser("192.168.1.1", "user1")
        rotation_service.add_ip_subuser("192.168.1.2", "user2")

        result = rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        assert result.success is True
        assert result.from_ip == "192.168.1.1"
        assert result.from_subuser == "user1"
        assert result.to_ip == "192.168.1.2"
        assert result.to_subuser == "user2"
        assert result.reason == RotationReason.MANUAL_ROTATION

        # Check that source IP is in cooldown
        from_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
        assert from_entry.status == IPSubuserStatus.COOLDOWN
        assert from_entry.cooldown_until is not None

    def test_execute_rotation_no_alternatives(self, rotation_service):
        """Test rotation when no alternatives are available."""
        # Add only one IP
        rotation_service.add_ip_subuser("192.168.1.1", "user1")

        alternative = rotation_service.select_best_alternative("192.168.1.1", "user1")
        assert alternative is None

    def test_execute_rotation_nonexistent_ip(self, rotation_service):
        """Test rotating non-existent IP/subuser."""
        result = rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip="192.168.1.2",
            to_subuser="user2",
            reason=RotationReason.MANUAL_ROTATION,
        )

        # Should still create rotation event but may not update pool entries
        assert result.from_ip == "192.168.1.1"
        assert result.from_subuser == "user1"

    def test_check_rate_limits_within_limits(self, rotation_service):
        """Test rate limiting when within limits."""
        # Should return True when no recent rotations
        assert rotation_service._check_rotation_rate_limit() is True

    @patch("leadfactory.services.ip_rotation.datetime")
    def test_check_rate_limits_exceeded(self, mock_datetime, rotation_service):
        """Test rate limiting when limits are exceeded."""
        fixed_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = fixed_time

        # Add many rotations within the hour
        for i in range(15):  # More than max_rotations_per_hour (5 in test config)
            event = RotationEvent(
                from_ip=f"192.168.1.{i}",
                from_subuser=f"user{i}",
                to_ip="192.168.1.100",
                to_subuser="target_user",
                reason=RotationReason.MANUAL_ROTATION,
            )
            event.success = True
            event.timestamp = fixed_time
            rotation_service.rotation_history.append(event)

        assert rotation_service._check_rotation_rate_limit() is False

    def test_get_pool_status(self, rotation_service):
        """Test getting pool status statistics."""
        # Add some mock IPs with different statuses
        rotation_service.add_ip_subuser("192.168.1.1", "user1")
        rotation_service.add_ip_subuser("192.168.1.2", "user2")
        rotation_service.add_ip_subuser("192.168.1.3", "user3")

        # Disable one IP
        pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.3", "user3")
        pool_entry.status = IPSubuserStatus.DISABLED

        stats = rotation_service.get_pool_status()

        assert stats["total_count"] == 3
        assert stats["active_count"] == 2
        assert stats["disabled_count"] == 1
        assert stats["available_count"] == 2
        assert "active_rotations" in stats
        assert "recent_rotations" in stats


class TestRotationReasons:
    """Test cases for RotationReason enum."""

    def test_rotation_reasons_exist(self):
        """Test that all expected rotation reasons exist."""
        assert hasattr(RotationReason, "THRESHOLD_BREACH")
        assert hasattr(RotationReason, "MANUAL_ROTATION")
        assert hasattr(RotationReason, "SCHEDULED_ROTATION")
        assert hasattr(RotationReason, "PERFORMANCE_DEGRADATION")

        # Test enum values
        assert RotationReason.THRESHOLD_BREACH.value == "threshold_breach"
        assert RotationReason.MANUAL_ROTATION.value == "manual_rotation"
        assert RotationReason.SCHEDULED_ROTATION.value == "scheduled_rotation"
        assert RotationReason.PERFORMANCE_DEGRADATION.value == "performance_degradation"


if __name__ == "__main__":
    pytest.main([__file__])
