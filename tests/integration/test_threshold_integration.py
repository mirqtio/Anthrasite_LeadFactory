"""
Integration tests for threshold detection with bounce monitoring.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from leadfactory.services.bounce_monitor import BounceRateMonitor
from leadfactory.services.threshold_detector import (
    ThresholdDetector,
    ThresholdConfig,
    ThresholdRule,
    ThresholdSeverity,
    ThresholdType,
    create_default_threshold_config
)

class TestThresholdBounceIntegration:
    """Integration tests for threshold detection with bounce monitoring."""

    def setup_method(self):
        """Set up test fixtures with temporary database."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Initialize bounce monitor with SQLite
        self.bounce_monitor = BounceRateMonitor(
            db_path=self.temp_db.name,
            default_threshold=0.05,
            sampling_period_hours=24
        )

        # Create threshold configuration
        self.threshold_config = ThresholdConfig()
        self.threshold_config.add_rule(ThresholdRule(
            name="warning_threshold",
            threshold_value=0.05,
            severity=ThresholdSeverity.LOW,
            minimum_sample_size=10  # Lower for testing
        ))
        self.threshold_config.add_rule(ThresholdRule(
            name="critical_threshold",
            threshold_value=0.10,
            severity=ThresholdSeverity.CRITICAL,
            minimum_sample_size=10
        ))

        # Initialize threshold detector
        self.threshold_detector = ThresholdDetector(
            config=self.threshold_config,
            bounce_monitor=self.bounce_monitor
        )

    def teardown_method(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_end_to_end_threshold_detection(self):
        """Test complete flow from recording events to detecting thresholds."""
        ip_address = "192.168.1.1"
        subuser = "test_user"

        # Record some sent emails
        for i in range(20):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Record some bounces (30% bounce rate)
        for i in range(6):
            self.bounce_monitor.record_bounce_event(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Check thresholds
        breaches = self.threshold_detector.check_thresholds(ip_address, subuser)

        # Should have both warning and critical breaches (30% > 10% > 5%)
        assert len(breaches) == 2

        breach_rules = [breach.rule_name for breach in breaches]
        assert "warning_threshold" in breach_rules
        assert "critical_threshold" in breach_rules

        # Verify breach details
        critical_breach = next(b for b in breaches if b.rule_name == "critical_threshold")
        assert critical_breach.current_value == 0.3  # 6/20 = 0.3
        assert critical_breach.threshold_value == 0.10
        assert critical_breach.severity == ThresholdSeverity.CRITICAL

    def test_no_breach_with_low_bounce_rate(self):
        """Test that no breaches are detected with low bounce rates."""
        ip_address = "192.168.1.2"
        subuser = "good_user"

        # Record emails with low bounce rate (2%)
        for i in range(50):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Only 1 bounce out of 50 emails
        self.bounce_monitor.record_bounce_event(
            ip_address=ip_address,
            subuser=subuser,
            timestamp=datetime.now()
        )

        # Check thresholds
        breaches = self.threshold_detector.check_thresholds(ip_address, subuser)

        # Should have no breaches (2% < 5%)
        assert len(breaches) == 0

    def test_insufficient_sample_size(self):
        """Test that thresholds are not checked with insufficient sample size."""
        ip_address = "192.168.1.3"
        subuser = "low_volume_user"

        # Record only a few emails (below minimum sample size)
        for i in range(5):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # High bounce rate but low volume
        for i in range(3):
            self.bounce_monitor.record_bounce_event(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Check thresholds
        breaches = self.threshold_detector.check_thresholds(ip_address, subuser)

        # Should have no breaches due to insufficient sample size
        assert len(breaches) == 0

    def test_multiple_ip_subuser_combinations(self):
        """Test threshold detection across multiple IP/subuser combinations."""
        test_data = [
            ("192.168.1.1", "user1", 20, 1),   # 5% bounce rate - warning only
            ("192.168.1.2", "user2", 30, 4),   # 13.3% bounce rate - both thresholds
            ("192.168.1.3", "user3", 25, 0),   # 0% bounce rate - no breach
        ]

        # Record data for all combinations
        for ip, subuser, sent_count, bounce_count in test_data:
            for i in range(sent_count):
                self.bounce_monitor.record_sent_email(
                    ip_address=ip,
                    subuser=subuser,
                    timestamp=datetime.now()
                )

            for i in range(bounce_count):
                self.bounce_monitor.record_bounce_event(
                    ip_address=ip,
                    subuser=subuser,
                    timestamp=datetime.now()
                )

        # Check all thresholds
        all_breaches = self.threshold_detector.check_all_thresholds()

        # Should have 3 breaches total: 1 from user1, 2 from user2, 0 from user3
        assert len(all_breaches) == 3

        # Group breaches by IP/subuser
        breach_groups = {}
        for breach in all_breaches:
            key = (breach.ip_address, breach.subuser)
            if key not in breach_groups:
                breach_groups[key] = []
            breach_groups[key].append(breach)

        # Verify breach distribution
        assert len(breach_groups[("192.168.1.1", "user1")]) == 1  # Warning only
        assert len(breach_groups[("192.168.1.2", "user2")]) == 2  # Warning + Critical
        assert ("192.168.1.3", "user3") not in breach_groups     # No breaches

    def test_volume_based_threshold_integration(self):
        """Test volume-based thresholds with real bounce monitor data."""
        # Add volume-based threshold rule
        volume_rule = ThresholdRule(
            name="volume_threshold",
            threshold_value=0.05,  # Default 5%
            severity=ThresholdSeverity.MEDIUM,
            threshold_type=ThresholdType.VOLUME_BASED,
            volume_ranges={
                "0-50": 0.15,    # 15% threshold for low volume
                "50-200": 0.08,  # 8% threshold for medium volume
                "200+": 0.04     # 4% threshold for high volume
            },
            minimum_sample_size=10
        )
        self.threshold_config.add_rule(volume_rule)

        test_scenarios = [
            # (ip, subuser, sent_count, bounce_count, expected_breaches)
            ("192.168.1.1", "low_vol", 30, 3, 0),      # 10% < 15% - no breach
            ("192.168.1.2", "med_vol", 100, 9, 1),     # 9% > 8% - breach
            ("192.168.1.3", "high_vol", 300, 15, 1),   # 5% > 4% - breach
        ]

        for ip, subuser, sent_count, bounce_count, expected_breach_count in test_scenarios:
            # Record data
            for i in range(sent_count):
                self.bounce_monitor.record_sent_email(
                    ip_address=ip,
                    subuser=subuser,
                    timestamp=datetime.now()
                )

            for i in range(bounce_count):
                self.bounce_monitor.record_bounce_event(
                    ip_address=ip,
                    subuser=subuser,
                    timestamp=datetime.now()
                )

            # Check thresholds
            breaches = self.threshold_detector.check_thresholds(ip, subuser)

            # Filter for volume-based breaches
            volume_breaches = [b for b in breaches if b.rule_name == "volume_threshold"]

            assert len(volume_breaches) == expected_breach_count, \
                f"Expected {expected_breach_count} volume breaches for {ip}/{subuser}, got {len(volume_breaches)}"

    def test_notification_callback_integration(self):
        """Test notification callbacks with real breach detection."""
        notification_log = []

        def test_callback(breach):
            notification_log.append({
                'ip': breach.ip_address,
                'subuser': breach.subuser,
                'rule': breach.rule_name,
                'severity': breach.severity,
                'value': breach.current_value,
                'time': breach.breach_time
            })

        self.threshold_detector.add_notification_callback(test_callback)

        ip_address = "192.168.1.1"
        subuser = "test_user"

        # Record data that will trigger breaches
        for i in range(20):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        for i in range(3):  # 15% bounce rate
            self.bounce_monitor.record_bounce_event(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Trigger threshold check
        breaches = self.threshold_detector.check_thresholds(ip_address, subuser)

        # Verify notifications were sent
        assert len(notification_log) == len(breaches)
        assert len(notification_log) == 2  # Should have warning and critical

        # Verify notification content
        for notification in notification_log:
            assert notification['ip'] == ip_address
            assert notification['subuser'] == subuser
            assert notification['rule'] in ['warning_threshold', 'critical_threshold']
            assert notification['value'] == 0.15

    def test_breach_history_persistence(self):
        """Test that breach history is maintained across multiple checks."""
        ip_address = "192.168.1.1"
        subuser = "test_user"

        # First batch of data
        for i in range(15):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        for i in range(2):  # 13.3% bounce rate
            self.bounce_monitor.record_bounce_event(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # First check
        breaches1 = self.threshold_detector.check_thresholds(ip_address, subuser)
        assert len(breaches1) == 2
        assert len(self.threshold_detector.breach_history) == 2

        # Add more data (lower overall bounce rate)
        for i in range(35):  # Total: 50 sent
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Second check (should be 4% bounce rate now - no new breaches)
        breaches2 = self.threshold_detector.check_thresholds(ip_address, subuser)
        assert len(breaches2) == 0

        # History should still contain previous breaches
        assert len(self.threshold_detector.breach_history) == 2

        # Verify we can filter history
        recent_breaches = self.threshold_detector.get_breach_history(hours_back=1)
        assert len(recent_breaches) == 2

    def test_default_configuration_integration(self):
        """Test integration with default threshold configuration."""
        # Use default configuration
        default_config = create_default_threshold_config()
        detector = ThresholdDetector(default_config, self.bounce_monitor)

        ip_address = "192.168.1.1"
        subuser = "test_user"

        # Record data with moderate bounce rate (7%)
        for i in range(100):
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        for i in range(7):
            self.bounce_monitor.record_bounce_event(
                ip_address=ip_address,
                subuser=subuser,
                timestamp=datetime.now()
            )

        # Check thresholds with default config
        breaches = detector.check_thresholds(ip_address, subuser)

        # Should trigger warning and action thresholds (7% > 5% and 7% < 8%)
        assert len(breaches) >= 1

        # Verify that default rules are working
        rule_names = [breach.rule_name for breach in breaches]
        assert "warning_threshold" in rule_names

    @patch('leadfactory.services.threshold_detector.logger')
    def test_error_handling_integration(self, mock_logger):
        """Test error handling in integrated threshold detection."""
        # Create a detector with a broken bounce monitor
        broken_monitor = Mock()
        broken_monitor.get_stats.side_effect = Exception("Database error")

        detector = ThresholdDetector(self.threshold_config, broken_monitor)

        # Should handle errors gracefully
        breaches = detector.check_thresholds("192.168.1.1", "test_user")

        # Should return empty list on error
        assert len(breaches) == 0

        # Should log the error (this would be logged by bounce monitor, not detector)
        # But detector should handle the exception gracefully

    def test_concurrent_threshold_checks(self):
        """Test threshold detection with concurrent data updates."""
        import threading
        import time

        ip_address = "192.168.1.1"
        subuser = "concurrent_user"

        # Function to add data concurrently
        def add_data():
            for i in range(10):
                self.bounce_monitor.record_sent_email(
                    ip_address=ip_address,
                    subuser=subuser,
                    timestamp=datetime.now()
                )
                if i < 2:  # Add some bounces
                    self.bounce_monitor.record_bounce_event(
                        ip_address=ip_address,
                        subuser=subuser,
                        timestamp=datetime.now()
                    )
                time.sleep(0.01)  # Small delay to simulate real timing

        # Start concurrent data addition
        thread = threading.Thread(target=add_data)
        thread.start()

        # Check thresholds while data is being added
        all_breaches = []
        for i in range(5):
            breaches = self.threshold_detector.check_thresholds(ip_address, subuser)
            all_breaches.extend(breaches)
            time.sleep(0.02)

        thread.join()

        # Final check after all data is added
        final_breaches = self.threshold_detector.check_thresholds(ip_address, subuser)

        # Should have detected some breaches (20% bounce rate)
        assert len(final_breaches) > 0

        # System should handle concurrent access without errors
        # (SQLite handles this with locking)
