#!/usr/bin/env python3
"""
Standalone test for threshold detection system functionality.
"""

import os
import sys
import tempfile
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from leadfactory.services.bounce_monitor import (
    BounceEvent,
    BounceRateConfig,
    BounceRateMonitor,
)
from leadfactory.services.threshold_detector import (
    ThresholdConfig,
    ThresholdDetector,
    ThresholdRule,
    ThresholdSeverity,
    ThresholdType,
    create_default_threshold_config,
)


def test_basic_threshold_detection():
    """Test basic threshold detection functionality."""

    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()

    try:
        # Initialize bounce monitor
        bounce_monitor_config = BounceRateConfig()
        bounce_monitor = BounceRateMonitor(bounce_monitor_config, temp_db.name)

        # Create threshold configuration
        config = ThresholdConfig()
        config.add_rule(
            ThresholdRule(
                name="warning_threshold",
                threshold_value=0.05,
                severity=ThresholdSeverity.LOW,
                minimum_sample_size=10,
            )
        )
        config.add_rule(
            ThresholdRule(
                name="critical_threshold",
                threshold_value=0.10,
                severity=ThresholdSeverity.CRITICAL,
                minimum_sample_size=10,
            )
        )

        # Initialize threshold detector
        detector = ThresholdDetector(config, bounce_monitor)

        # Test data
        ip_address = "192.168.1.1"
        subuser = "test_user"

        # Record sent emails
        for _i in range(20):
            bounce_monitor.record_sent_email(ip_address=ip_address, subuser=subuser)

        # Record bounces (30% bounce rate)
        for _i in range(6):
            bounce_monitor.record_bounce_event(
                BounceEvent(
                    ip_address=ip_address,
                    subuser=subuser,
                    timestamp=datetime.now(),
                    email="test@example.com",
                    bounce_type="hard",
                    reason="Test bounce reason",
                )
            )

        # Check thresholds
        breaches = detector.check_thresholds(ip_address, subuser)

        for _breach in breaches:
            pass

        # Verify expected results
        assert len(breaches) == 2, f"Expected 2 breaches, got {len(breaches)}"

        rule_names = [breach.rule_name for breach in breaches]
        assert "warning_threshold" in rule_names, "Missing warning threshold breach"
        assert "critical_threshold" in rule_names, "Missing critical threshold breach"

    finally:
        # Clean up
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_volume_based_thresholds():
    """Test volume-based threshold detection."""

    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()

    try:
        # Initialize bounce monitor
        bounce_monitor_config = BounceRateConfig()
        bounce_monitor = BounceRateMonitor(bounce_monitor_config, temp_db.name)

        # Create configuration with volume-based rule
        config = ThresholdConfig()
        config.add_rule(
            ThresholdRule(
                name="volume_threshold",
                threshold_value=0.05,  # Default 5%
                severity=ThresholdSeverity.MEDIUM,
                threshold_type=ThresholdType.VOLUME_BASED,
                volume_ranges={
                    "0-50": 0.15,  # 15% threshold for low volume
                    "50-200": 0.08,  # 8% threshold for medium volume
                    "200+": 0.04,  # 4% threshold for high volume
                },
                minimum_sample_size=10,
            )
        )

        detector = ThresholdDetector(config, bounce_monitor)

        # Test scenarios
        scenarios = [
            ("192.168.1.1", "low_vol", 30, 3, False),  # 10% < 15% - no breach
            ("192.168.1.2", "med_vol", 100, 9, True),  # 9% > 8% - breach
            ("192.168.1.3", "high_vol", 300, 15, True),  # 5% > 4% - breach
        ]

        for ip, subuser, sent_count, bounce_count, should_breach in scenarios:

            # Record data
            for _i in range(sent_count):
                bounce_monitor.record_sent_email(ip_address=ip, subuser=subuser)

            for _i in range(bounce_count):
                bounce_monitor.record_bounce_event(
                    BounceEvent(
                        ip_address=ip,
                        subuser=subuser,
                        timestamp=datetime.now(),
                        email="test@example.com",
                        bounce_type="hard",
                        reason="Test bounce reason",
                    )
                )

            # Check thresholds
            breaches = detector.check_thresholds(ip, subuser)
            volume_breaches = [b for b in breaches if b.rule_name == "volume_threshold"]

            bounce_count / sent_count

            if should_breach:
                assert len(volume_breaches) == 1, f"Expected breach for {ip}/{subuser}"
            else:
                assert (
                    len(volume_breaches) == 0
                ), f"Unexpected breach for {ip}/{subuser}"

    finally:
        # Clean up
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_notification_callbacks():
    """Test notification callback functionality."""

    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()

    try:
        # Initialize bounce monitor
        bounce_monitor_config = BounceRateConfig()
        bounce_monitor = BounceRateMonitor(bounce_monitor_config, temp_db.name)

        # Create simple configuration
        config = ThresholdConfig()
        config.add_rule(
            ThresholdRule(
                name="test_threshold",
                threshold_value=0.05,
                severity=ThresholdSeverity.MEDIUM,
                minimum_sample_size=10,
            )
        )

        detector = ThresholdDetector(config, bounce_monitor)

        # Add notification callback
        notifications = []

        def test_callback(breach):
            notifications.append(
                {
                    "rule": breach.rule_name,
                    "ip": breach.ip_address,
                    "subuser": breach.subuser,
                    "value": breach.current_value,
                }
            )

        detector.add_notification_callback(test_callback)

        # Record data that will trigger breach
        ip_address = "192.168.1.1"
        subuser = "test_user"

        for _i in range(20):
            bounce_monitor.record_sent_email(ip_address=ip_address, subuser=subuser)

        for _i in range(2):  # 10% bounce rate
            bounce_monitor.record_bounce_event(
                BounceEvent(
                    ip_address=ip_address,
                    subuser=subuser,
                    timestamp=datetime.now(),
                    email="test@example.com",
                    bounce_type="hard",
                    reason="Test bounce reason",
                )
            )

        # Check thresholds
        breaches = detector.check_thresholds(ip_address, subuser)

        assert len(breaches) == 1, f"Expected 1 breach, got {len(breaches)}"
        assert (
            len(notifications) == 1
        ), f"Expected 1 notification, got {len(notifications)}"

        notification = notifications[0]
        assert notification["rule"] == "test_threshold"
        assert notification["ip"] == ip_address
        assert notification["subuser"] == subuser
        assert notification["value"] == 0.10

    finally:
        # Clean up
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_default_configuration():
    """Test default threshold configuration."""

    config = create_default_threshold_config()

    for _rule in config.rules:
        pass

    # Verify expected rules exist
    rule_names = [rule.name for rule in config.rules]
    expected_rules = [
        "warning_threshold",
        "action_threshold",
        "rotation_threshold",
        "emergency_threshold",
        "volume_based_threshold",
    ]

    for expected_rule in expected_rules:
        assert expected_rule in rule_names, f"Missing expected rule: {expected_rule}"

    # Verify severity distribution
    severities = [rule.severity for rule in config.rules]
    assert ThresholdSeverity.LOW in severities
    assert ThresholdSeverity.MEDIUM in severities
    assert ThresholdSeverity.HIGH in severities
    assert ThresholdSeverity.CRITICAL in severities


def main():
    """Run all threshold detection tests."""

    try:
        test_basic_threshold_detection()
        test_volume_based_thresholds()
        test_notification_callbacks()
        test_default_configuration()

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
