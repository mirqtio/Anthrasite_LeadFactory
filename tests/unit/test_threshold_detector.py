"""
Unit tests for the threshold detection system.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from leadfactory.services.threshold_detector import (
    ThresholdBreach,
    ThresholdConfig,
    ThresholdDetector,
    ThresholdRule,
    ThresholdSeverity,
    ThresholdType,
    create_default_threshold_config,
    log_notification_callback,
)


# Mock IPSubuserStats for testing
@dataclass
class MockIPSubuserStats:
    ip_address: str
    subuser: str
    bounce_rate: float
    total_sent: int
    total_bounces: int
    last_updated: datetime


class TestThresholdRule:
    """Test ThresholdRule dataclass."""

    def test_threshold_rule_creation(self):
        """Test creating a threshold rule."""
        rule = ThresholdRule(
            name="test_rule",
            threshold_value=0.05,
            severity=ThresholdSeverity.MEDIUM,
            threshold_type=ThresholdType.ABSOLUTE,
        )

        assert rule.name == "test_rule"
        assert rule.threshold_value == 0.05
        assert rule.severity == ThresholdSeverity.MEDIUM
        assert rule.threshold_type == ThresholdType.ABSOLUTE
        assert rule.enabled is True
        assert rule.minimum_sample_size == 100

    def test_threshold_rule_with_volume_ranges(self):
        """Test threshold rule with volume-based configuration."""
        volume_ranges = {"0-1000": 0.08, "1000-10000": 0.05, "10000+": 0.03}

        rule = ThresholdRule(
            name="volume_rule",
            threshold_value=0.05,
            severity=ThresholdSeverity.LOW,
            threshold_type=ThresholdType.VOLUME_BASED,
            volume_ranges=volume_ranges,
        )

        assert rule.volume_ranges == volume_ranges
        assert rule.threshold_type == ThresholdType.VOLUME_BASED


class TestThresholdConfig:
    """Test ThresholdConfig class."""

    def test_empty_config(self):
        """Test creating an empty threshold configuration."""
        config = ThresholdConfig()

        assert len(config.rules) == 0
        assert config.global_enabled is True
        assert config.default_minimum_sample_size == 100

    def test_add_rule(self):
        """Test adding a rule to configuration."""
        config = ThresholdConfig()
        rule = ThresholdRule(
            name="test_rule", threshold_value=0.05, severity=ThresholdSeverity.MEDIUM
        )

        config.add_rule(rule)

        assert len(config.rules) == 1
        assert config.rules[0] == rule

    def test_get_rule(self):
        """Test retrieving a rule by name."""
        config = ThresholdConfig()
        rule = ThresholdRule(
            name="test_rule", threshold_value=0.05, severity=ThresholdSeverity.MEDIUM
        )
        config.add_rule(rule)

        retrieved_rule = config.get_rule("test_rule")
        assert retrieved_rule == rule

        missing_rule = config.get_rule("nonexistent")
        assert missing_rule is None

    def test_get_enabled_rules(self):
        """Test getting only enabled rules."""
        config = ThresholdConfig()

        enabled_rule = ThresholdRule(
            name="enabled_rule",
            threshold_value=0.05,
            severity=ThresholdSeverity.MEDIUM,
            enabled=True,
        )

        disabled_rule = ThresholdRule(
            name="disabled_rule",
            threshold_value=0.08,
            severity=ThresholdSeverity.HIGH,
            enabled=False,
        )

        config.add_rule(enabled_rule)
        config.add_rule(disabled_rule)

        enabled_rules = config.get_enabled_rules()
        assert len(enabled_rules) == 1
        assert enabled_rules[0] == enabled_rule

    def test_global_disabled(self):
        """Test that global disable overrides individual rule settings."""
        config = ThresholdConfig(global_enabled=False)

        rule = ThresholdRule(
            name="test_rule",
            threshold_value=0.05,
            severity=ThresholdSeverity.MEDIUM,
            enabled=True,
        )
        config.add_rule(rule)

        enabled_rules = config.get_enabled_rules()
        assert len(enabled_rules) == 0


class TestThresholdDetector:
    """Test ThresholdDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ThresholdConfig()
        self.config.add_rule(
            ThresholdRule(
                name="low_threshold",
                threshold_value=0.05,
                severity=ThresholdSeverity.LOW,
                minimum_sample_size=50,
            )
        )
        self.config.add_rule(
            ThresholdRule(
                name="high_threshold",
                threshold_value=0.10,
                severity=ThresholdSeverity.HIGH,
                minimum_sample_size=100,
            )
        )

        self.mock_bounce_monitor = Mock()
        self.detector = ThresholdDetector(self.config, self.mock_bounce_monitor)

    def test_detector_initialization(self):
        """Test threshold detector initialization."""
        assert self.detector.config == self.config
        assert self.detector.bounce_monitor == self.mock_bounce_monitor
        assert len(self.detector.breach_history) == 0
        assert len(self.detector.notification_callbacks) == 0

    def test_add_notification_callback(self):
        """Test adding notification callbacks."""
        callback = Mock()
        self.detector.add_notification_callback(callback)

        assert len(self.detector.notification_callbacks) == 1
        assert self.detector.notification_callbacks[0] == callback

    def test_check_thresholds_no_stats(self):
        """Test threshold checking when no stats are available."""
        self.mock_bounce_monitor.get_stats.return_value = None

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 0
        self.mock_bounce_monitor.get_stats.assert_called_once_with(
            "192.168.1.1", "test_user"
        )

    def test_check_thresholds_insufficient_sample_size(self):
        """Test threshold checking with insufficient sample size."""
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.08,
            total_sent=25,  # Below minimum sample size
            total_bounces=2,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 0

    def test_check_thresholds_no_breach(self):
        """Test threshold checking when no thresholds are breached."""
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.03,  # Below all thresholds
            total_sent=200,
            total_bounces=6,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 0

    def test_check_thresholds_single_breach(self):
        """Test threshold checking with a single breach."""
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.07,  # Above low threshold, below high
            total_sent=200,
            total_bounces=14,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 1
        breach = breaches[0]
        assert breach.ip_address == "192.168.1.1"
        assert breach.subuser == "test_user"
        assert breach.rule_name == "low_threshold"
        assert breach.current_value == 0.07
        assert breach.threshold_value == 0.05
        assert breach.severity == ThresholdSeverity.LOW

    def test_check_thresholds_multiple_breaches(self):
        """Test threshold checking with multiple breaches."""
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.12,  # Above both thresholds
            total_sent=200,
            total_bounces=24,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 2

        # Should have both low and high threshold breaches
        rule_names = [breach.rule_name for breach in breaches]
        assert "low_threshold" in rule_names
        assert "high_threshold" in rule_names

    def test_check_all_thresholds(self):
        """Test checking thresholds for all IP/subuser combinations."""
        stats_list = [
            MockIPSubuserStats(
                ip_address="192.168.1.1",
                subuser="user1",
                bounce_rate=0.07,
                total_sent=200,
                total_bounces=14,
                last_updated=datetime.now(),
            ),
            MockIPSubuserStats(
                ip_address="192.168.1.2",
                subuser="user2",
                bounce_rate=0.02,
                total_sent=150,
                total_bounces=3,
                last_updated=datetime.now(),
            ),
        ]
        self.mock_bounce_monitor.get_all_stats.return_value = stats_list

        # Mock individual get_stats calls
        def mock_get_stats(ip, subuser):
            for stats in stats_list:
                if stats.ip_address == ip and stats.subuser == subuser:
                    return stats
            return None

        self.mock_bounce_monitor.get_stats.side_effect = mock_get_stats

        all_breaches = self.detector.check_all_thresholds()

        assert len(all_breaches) == 1  # Only first IP should have breach
        assert all_breaches[0].ip_address == "192.168.1.1"

    def test_volume_based_threshold(self):
        """Test volume-based threshold detection."""
        volume_rule = ThresholdRule(
            name="volume_rule",
            threshold_value=0.05,
            severity=ThresholdSeverity.MEDIUM,
            threshold_type=ThresholdType.VOLUME_BASED,
            volume_ranges={"0-1000": 0.08, "1000-10000": 0.05, "10000+": 0.03},
            minimum_sample_size=50,
        )
        self.config.add_rule(volume_rule)

        # Test low volume (should use 0.08 threshold)
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.07,  # Above 0.05 but below 0.08
            total_sent=500,
            total_bounces=35,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        # Should not breach volume-based rule (0.07 < 0.08)
        volume_breaches = [b for b in breaches if b.rule_name == "volume_rule"]
        assert len(volume_breaches) == 0

        # Test high volume (should use 0.03 threshold)
        stats.total_sent = 15000
        stats.bounce_rate = 0.04  # Above 0.03 but below 0.05

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        # Should breach volume-based rule (0.04 > 0.03)
        volume_breaches = [b for b in breaches if b.rule_name == "volume_rule"]
        assert len(volume_breaches) == 1
        assert volume_breaches[0].threshold_value == 0.03

    def test_notification_callback_execution(self):
        """Test that notification callbacks are executed on breach."""
        callback = Mock()
        self.detector.add_notification_callback(callback)

        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.07,
            total_sent=200,
            total_bounces=14,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        breaches = self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(breaches) == 1
        callback.assert_called_once()

        # Verify callback was called with the breach
        call_args = callback.call_args[0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], ThresholdBreach)

    def test_notification_cooldown(self):
        """Test notification cooldown functionality."""
        callback = Mock()
        self.detector.add_notification_callback(callback)

        # Set short cooldown for testing
        self.config.rules[0].cooldown_minutes = 1

        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.07,
            total_sent=200,
            total_bounces=14,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        # First breach should trigger notification
        self.detector.check_thresholds("192.168.1.1", "test_user")
        assert callback.call_count == 1

        # Second breach immediately should not trigger notification (cooldown)
        self.detector.check_thresholds("192.168.1.1", "test_user")
        assert callback.call_count == 1

        # Simulate time passing beyond cooldown
        past_time = datetime.now() - timedelta(minutes=2)
        notification_key = ("192.168.1.1", "test_user", "low_threshold")
        self.detector.last_notification_times[notification_key] = past_time

        # Third breach should trigger notification again
        self.detector.check_thresholds("192.168.1.1", "test_user")
        assert callback.call_count == 2

    def test_breach_history(self):
        """Test breach history tracking."""
        stats = MockIPSubuserStats(
            ip_address="192.168.1.1",
            subuser="test_user",
            bounce_rate=0.07,
            total_sent=200,
            total_bounces=14,
            last_updated=datetime.now(),
        )
        self.mock_bounce_monitor.get_stats.return_value = stats

        # Generate some breaches
        self.detector.check_thresholds("192.168.1.1", "test_user")

        assert len(self.detector.breach_history) == 1

        # Check breach details
        breach = self.detector.breach_history[0]
        assert breach.ip_address == "192.168.1.1"
        assert breach.subuser == "test_user"
        assert breach.rule_name == "low_threshold"

    def test_get_breach_history_filtering(self):
        """Test breach history filtering."""
        # Add some test breaches manually
        breach1 = ThresholdBreach(
            ip_address="192.168.1.1",
            subuser="user1",
            rule_name="low_threshold",
            current_value=0.07,
            threshold_value=0.05,
            severity=ThresholdSeverity.LOW,
            breach_time=datetime.now() - timedelta(hours=2),
            sample_size=200,
            time_window_hours=24,
        )

        breach2 = ThresholdBreach(
            ip_address="192.168.1.2",
            subuser="user2",
            rule_name="high_threshold",
            current_value=0.12,
            threshold_value=0.10,
            severity=ThresholdSeverity.HIGH,
            breach_time=datetime.now() - timedelta(minutes=30),
            sample_size=150,
            time_window_hours=24,
        )

        self.detector.breach_history = [breach1, breach2]

        # Test IP filtering
        ip_filtered = self.detector.get_breach_history(ip_address="192.168.1.1")
        assert len(ip_filtered) == 1
        assert ip_filtered[0] == breach1

        # Test severity filtering
        severity_filtered = self.detector.get_breach_history(
            severity=ThresholdSeverity.HIGH
        )
        assert len(severity_filtered) == 1
        assert severity_filtered[0] == breach2

        # Test time filtering
        time_filtered = self.detector.get_breach_history(hours_back=1)
        assert len(time_filtered) == 1
        assert time_filtered[0] == breach2

    def test_clear_breach_history(self):
        """Test clearing breach history."""
        # Add some test breaches
        old_breach = ThresholdBreach(
            ip_address="192.168.1.1",
            subuser="user1",
            rule_name="low_threshold",
            current_value=0.07,
            threshold_value=0.05,
            severity=ThresholdSeverity.LOW,
            breach_time=datetime.now() - timedelta(hours=25),
            sample_size=200,
            time_window_hours=24,
        )

        recent_breach = ThresholdBreach(
            ip_address="192.168.1.2",
            subuser="user2",
            rule_name="high_threshold",
            current_value=0.12,
            threshold_value=0.10,
            severity=ThresholdSeverity.HIGH,
            breach_time=datetime.now() - timedelta(minutes=30),
            sample_size=150,
            time_window_hours=24,
        )

        self.detector.breach_history = [old_breach, recent_breach]

        # Clear old entries (keep last 24 hours)
        cleared_count = self.detector.clear_breach_history(hours_back=24)

        assert cleared_count == 1
        assert len(self.detector.breach_history) == 1
        assert self.detector.breach_history[0] == recent_breach

        # Clear all
        cleared_count = self.detector.clear_breach_history()
        assert cleared_count == 1
        assert len(self.detector.breach_history) == 0


class TestDefaultConfiguration:
    """Test default configuration creation."""

    def test_create_default_config(self):
        """Test creating default threshold configuration."""
        config = create_default_threshold_config()

        assert len(config.rules) == 5  # Should have 5 default rules
        assert config.global_enabled is True

        # Check that all severity levels are represented
        severities = [rule.severity for rule in config.rules]
        assert ThresholdSeverity.LOW in severities
        assert ThresholdSeverity.MEDIUM in severities
        assert ThresholdSeverity.HIGH in severities
        assert ThresholdSeverity.CRITICAL in severities

        # Check that volume-based rule exists
        volume_rules = [
            rule
            for rule in config.rules
            if rule.threshold_type == ThresholdType.VOLUME_BASED
        ]
        assert len(volume_rules) == 1
        assert volume_rules[0].volume_ranges is not None


class TestNotificationCallbacks:
    """Test notification callback functions."""

    def test_log_notification_callback(self):
        """Test the log notification callback."""
        breach = ThresholdBreach(
            ip_address="192.168.1.1",
            subuser="test_user",
            rule_name="test_rule",
            current_value=0.07,
            threshold_value=0.05,
            severity=ThresholdSeverity.MEDIUM,
            breach_time=datetime.now(),
            sample_size=200,
            time_window_hours=24,
        )

        # This should not raise an exception
        with patch("leadfactory.services.threshold_detector.logger") as mock_logger:
            log_notification_callback(breach)
            mock_logger.error.assert_called_once()
