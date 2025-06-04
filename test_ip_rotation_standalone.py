#!/usr/bin/env python3
"""
Standalone test script for IP/Subuser Rotation Logic

This script tests the IP rotation functionality independently of the pytest environment
to verify the core rotation logic works correctly.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

# Add the project root to the path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the services we need to test
from leadfactory.services.bounce_monitor import (
    BounceEvent,
    BounceRateConfig,
    BounceRateMonitor,
    IPSubuserStats,
)
from leadfactory.services.ip_rotation import (
    IPRotationService,
    IPSubuserPool,
    IPSubuserStatus,
    RotationConfig,
    RotationEvent,
    RotationReason,
    create_default_rotation_config,
)
from leadfactory.services.threshold_detector import (
    ThresholdBreach,
    ThresholdConfig,
    ThresholdDetector,
    ThresholdSeverity,
    create_default_threshold_config,
)


def test_ip_pool_management():
    """Test basic IP pool management functionality."""
    print("Testing IP pool management...")

    config = create_default_rotation_config()
    rotation_service = IPRotationService(config)

    # Test adding IP/subuser combinations
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
    rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)

    assert len(rotation_service.ip_pool) == 3, "Should have 3 IP/subuser combinations"

    # Test getting pool entry
    pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
    assert pool_entry is not None, "Should find pool entry"
    assert pool_entry.priority == 5, "Priority should be 5"
    assert pool_entry.status == IPSubuserStatus.ACTIVE, "Should be active"

    # Test removing IP/subuser
    removed = rotation_service.remove_ip_subuser("192.168.1.2", "user2")
    assert removed == True, "Should successfully remove"
    assert len(rotation_service.ip_pool) == 2, "Should have 2 IP/subuser combinations"

    # Test removing non-existent
    removed = rotation_service.remove_ip_subuser("192.168.1.99", "user99")
    assert removed == False, "Should fail to remove non-existent"

    print("✓ IP pool management tests passed")


def test_performance_scoring():
    """Test performance scoring calculation."""
    print("Testing performance scoring...")

    # Create pool entry with some stats
    pool_entry = IPSubuserPool(
        ip_address="192.168.1.1",
        subuser="user1",
        priority=5,
        total_sent=1000,
        total_bounced=50,  # 5% bounce rate
    )

    score = pool_entry.calculate_performance_score()
    expected_base = 1.0 - 0.05  # 95% success rate
    expected_priority_boost = min(0.2, 5 * 0.05)  # Priority boost
    expected_score = min(1.0, expected_base + expected_priority_boost)  # Capped at 1.0

    assert (
        abs(score - expected_score) < 0.01
    ), f"Score should be ~{expected_score}, got {score}"

    # Test new IP/subuser (no stats)
    new_pool_entry = IPSubuserPool(
        ip_address="192.168.1.2", subuser="user2", priority=1
    )

    new_score = new_pool_entry.calculate_performance_score()
    assert new_score == 1.0, "New IP/subuser should get perfect score"

    # Test high bounce rate
    bad_pool_entry = IPSubuserPool(
        ip_address="192.168.1.3",
        subuser="user3",
        priority=1,
        total_sent=1000,
        total_bounced=500,  # 50% bounce rate
    )

    bad_score = bad_pool_entry.calculate_performance_score()
    expected_bad_score = max(0.0, 1.0 - 0.5) + min(
        0.2, 1 * 0.05
    )  # 50% + small priority boost
    assert (
        abs(bad_score - expected_bad_score) < 0.01
    ), f"Bad score should be ~{expected_bad_score}, got {bad_score}"

    print("✓ Performance scoring tests passed")


def test_alternative_selection():
    """Test selection of best alternatives for rotation."""
    print("Testing alternative selection...")

    config = create_default_rotation_config()
    rotation_service = IPRotationService(config)

    # Add multiple IP/subuser combinations with different performance
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
    rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)
    rotation_service.add_ip_subuser("192.168.1.4", "user4", priority=1)

    # Set different performance scores
    rotation_service.ip_pool[0].total_sent = 1000
    rotation_service.ip_pool[0].total_bounced = 100  # 10% bounce rate
    rotation_service.ip_pool[0].calculate_performance_score()

    rotation_service.ip_pool[1].total_sent = 1000
    rotation_service.ip_pool[1].total_bounced = 30  # 3% bounce rate
    rotation_service.ip_pool[1].calculate_performance_score()

    rotation_service.ip_pool[2].total_sent = 1000
    rotation_service.ip_pool[2].total_bounced = 20  # 2% bounce rate
    rotation_service.ip_pool[2].calculate_performance_score()

    # Test getting available alternatives
    alternatives = rotation_service.get_available_alternatives(
        exclude_ip="192.168.1.1", exclude_subuser="user1"
    )

    assert len(alternatives) == 3, "Should have 3 alternatives"

    # Should be sorted by combined score (performance + priority)
    # user3 should be first (high priority + good performance)
    assert alternatives[0].subuser == "user3", "user3 should be first choice"

    # Test selecting best alternative
    best = rotation_service.select_best_alternative("192.168.1.1", "user1")
    assert best is not None, "Should find best alternative"
    assert best.subuser == "user3", "Should select user3 as best"

    print("✓ Alternative selection tests passed")


def test_cooldown_functionality():
    """Test cooldown period functionality."""
    print("Testing cooldown functionality...")

    config = create_default_rotation_config()
    rotation_service = IPRotationService(config)

    # Add IP/subuser
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")

    # Should be available initially
    assert pool_entry.is_available() == True, "Should be available initially"

    # Put in cooldown
    pool_entry.status = IPSubuserStatus.COOLDOWN
    pool_entry.cooldown_until = datetime.now() + timedelta(hours=1)

    # Should not be available during cooldown
    assert pool_entry.is_available() == False, "Should not be available during cooldown"

    # Set cooldown in the past and reset status
    pool_entry.cooldown_until = datetime.now() - timedelta(hours=1)
    pool_entry.status = IPSubuserStatus.ACTIVE  # Reset to active

    # Should be available after cooldown
    assert pool_entry.is_available() == True, "Should be available after cooldown"

    print("✓ Cooldown functionality tests passed")


def test_rotation_execution():
    """Test rotation execution logic."""
    print("Testing rotation execution...")

    config = create_default_rotation_config()
    config.rotation_delay_seconds = 0  # No delay for testing
    rotation_service = IPRotationService(config)

    # Add IP/subuser combinations
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)

    # Execute rotation
    rotation_event = rotation_service.execute_rotation(
        from_ip="192.168.1.1",
        from_subuser="user1",
        to_ip="192.168.1.2",
        to_subuser="user2",
        reason=RotationReason.MANUAL_ROTATION,
    )

    assert rotation_event.success == True, "Rotation should succeed"
    assert rotation_event.from_ip == "192.168.1.1", "From IP should match"
    assert rotation_event.to_ip == "192.168.1.2", "To IP should match"
    assert (
        rotation_event.reason == RotationReason.MANUAL_ROTATION
    ), "Reason should match"

    # Check that from_entry is in cooldown
    from_entry = rotation_service.get_ip_subuser_pool("192.168.1.1", "user1")
    assert (
        from_entry.status == IPSubuserStatus.COOLDOWN
    ), "From entry should be in cooldown"
    assert from_entry.cooldown_until is not None, "Cooldown time should be set"

    # Check rotation history
    assert (
        len(rotation_service.rotation_history) == 1
    ), "Should have 1 rotation in history"

    print("✓ Rotation execution tests passed")


def test_threshold_breach_handling():
    """Test handling of threshold breaches."""
    print("Testing threshold breach handling...")

    # Create services with SQLite for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    try:
        # Create bounce monitor
        bounce_config = BounceRateConfig()
        bounce_monitor = BounceRateMonitor(bounce_config, db_path=db_path)

        # Create threshold detector
        threshold_config = create_default_threshold_config()
        threshold_detector = ThresholdDetector(threshold_config, bounce_monitor)

        # Create rotation service
        rotation_config = create_default_rotation_config()
        rotation_config.rotation_delay_seconds = 0  # No delay for testing
        rotation_service = IPRotationService(
            rotation_config, bounce_monitor, threshold_detector
        )

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
            time_window_hours=24,
        )

        # Handle the breach
        rotation_event = rotation_service.handle_threshold_breach(breach)

        assert rotation_event is not None, "Should execute rotation for breach"
        assert rotation_event.success == True, "Rotation should succeed"
        assert (
            rotation_event.reason == RotationReason.THRESHOLD_BREACH
        ), "Reason should be threshold breach"
        assert rotation_event.breach_details is not None, "Should have breach details"

        print("✓ Threshold breach handling tests passed")

    finally:
        # Clean up temp database
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_rate_limiting():
    """Test rotation rate limiting."""
    print("Testing rate limiting...")

    config = create_default_rotation_config()
    config.max_rotations_per_hour = 2  # Low limit for testing
    config.rotation_delay_seconds = 0  # No delay for testing
    rotation_service = IPRotationService(config)

    # Add IP/subuser combinations
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
    rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)

    # Execute rotations up to the limit
    for i in range(2):
        rotation_event = rotation_service.execute_rotation(
            from_ip="192.168.1.1",
            from_subuser="user1",
            to_ip=f"192.168.1.{i + 2}",
            to_subuser=f"user{i + 2}",
            reason=RotationReason.MANUAL_ROTATION,
        )
        assert rotation_event.success == True, f"Rotation {i + 1} should succeed"

    # Next rotation should fail due to rate limit
    rotation_event = rotation_service.execute_rotation(
        from_ip="192.168.1.1",
        from_subuser="user1",
        to_ip="192.168.1.3",
        to_subuser="user3",
        reason=RotationReason.MANUAL_ROTATION,
    )
    assert rotation_event.success == False, "Should fail due to rate limit"
    assert (
        "rate limit" in rotation_event.error_message.lower()
    ), "Error should mention rate limit"

    print("✓ Rate limiting tests passed")


def test_pool_status():
    """Test pool status reporting."""
    print("Testing pool status reporting...")

    config = create_default_rotation_config()
    rotation_service = IPRotationService(config)

    # Add various IP/subuser combinations
    rotation_service.add_ip_subuser("192.168.1.1", "user1", priority=5)
    rotation_service.add_ip_subuser("192.168.1.2", "user2", priority=3)
    rotation_service.add_ip_subuser("192.168.1.3", "user3", priority=7)

    # Put one in cooldown
    pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.2", "user2")
    pool_entry.status = IPSubuserStatus.COOLDOWN
    pool_entry.cooldown_until = datetime.now() + timedelta(hours=1)

    # Disable one
    pool_entry = rotation_service.get_ip_subuser_pool("192.168.1.3", "user3")
    pool_entry.status = IPSubuserStatus.DISABLED

    status = rotation_service.get_pool_status()

    assert status["total_count"] == 3, "Should have 3 total"
    assert status["active_count"] == 1, "Should have 1 active"
    assert status["cooldown_count"] == 1, "Should have 1 in cooldown"
    assert status["disabled_count"] == 1, "Should have 1 disabled"
    assert status["available_count"] == 1, "Should have 1 available"

    print("✓ Pool status tests passed")


def test_default_configuration():
    """Test default configuration creation."""
    print("Testing default configuration...")

    config = create_default_rotation_config()

    assert config.default_cooldown_hours == 4, "Default cooldown should be 4 hours"
    assert config.max_rotations_per_hour == 10, "Default max rotations should be 10"
    assert config.fallback_enabled == True, "Fallback should be enabled by default"
    assert (
        config.require_minimum_alternatives == 2
    ), "Should require 2 alternatives by default"
    assert (
        config.enable_automatic_rotation == True
    ), "Automatic rotation should be enabled"

    print("✓ Default configuration tests passed")


def run_all_tests():
    """Run all standalone tests."""
    print("Running IP Rotation Service standalone tests...")
    print("=" * 60)

    try:
        test_ip_pool_management()
        test_performance_scoring()
        test_alternative_selection()
        test_cooldown_functionality()
        test_rotation_execution()
        test_threshold_breach_handling()
        test_rate_limiting()
        test_pool_status()
        test_default_configuration()

        print("=" * 60)
        print("✅ All IP rotation tests passed successfully!")
        return True

    except Exception as e:
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
