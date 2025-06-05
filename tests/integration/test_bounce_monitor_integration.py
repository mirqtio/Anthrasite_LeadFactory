#!/usr/bin/env python3
"""
Integration tests for the Bounce Rate Monitoring System.

Tests integration with SendGrid webhook handling and real database operations.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the modules under test
from leadfactory.services.bounce_monitor import (
    BounceEvent,
    BounceRateConfig,
    BounceRateMonitor,
    CalculationMethod,
    SamplingPeriod,
)


class TestBounceMonitorIntegration:
    """Integration tests for bounce rate monitoring with real database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return BounceRateConfig(
            sampling_period=SamplingPeriod.HOURLY,
            calculation_method=CalculationMethod.ROLLING_AVERAGE,
            rolling_window_hours=24,
            minimum_sample_size=5,
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15,
        )

    @pytest.fixture
    def monitor(self, config, temp_db):
        """Create a BounceRateMonitor instance for testing."""
        return BounceRateMonitor(config=config, db_path=temp_db)

    def test_database_table_creation(self, monitor):
        """Test that database tables are created correctly."""
        # Tables should be created during initialization
        # This is a basic smoke test to ensure no exceptions are raised
        assert monitor is not None

        # Try to query the tables to verify they exist
        try:
            with monitor.DatabaseConnection(monitor.db_path) as db:
                # Test bounce_rate_stats table
                db.execute("SELECT COUNT(*) FROM bounce_rate_stats")
                count = db.fetchone()[0]
                assert count == 0  # Should be empty initially

                # Test bounce_events_tracking table
                db.execute("SELECT COUNT(*) FROM bounce_events_tracking")
                count = db.fetchone()[0]
                assert count == 0  # Should be empty initially

        except Exception as e:
            pytest.fail(f"Database tables not created properly: {e}")

    def test_end_to_end_bounce_tracking(self, monitor):
        """Test complete bounce tracking workflow."""
        ip_address = "192.168.1.100"
        subuser = "marketing_campaign"

        # Step 1: Record sent emails
        sent_emails = []
        for i in range(50):
            email = f"user{i}@example.com"
            sent_emails.append(email)
            monitor.record_sent_email(ip_address, subuser, email, f"msg_{i}")

        # Step 2: Simulate bounce events for some emails
        bounce_emails = sent_emails[:8]  # 8 bounces out of 50 = 16% bounce rate

        for i, email in enumerate(bounce_emails):
            bounce_type = "hard" if i < 5 else "soft"  # 5 hard, 3 soft
            bounce_event = BounceEvent(
                email=email,
                ip_address=ip_address,
                subuser=subuser,
                bounce_type=bounce_type,
                reason=f"Bounce reason {i}",
                timestamp=datetime.now(),
                message_id=f"msg_{i}",
            )
            monitor.record_bounce_event(bounce_event)

        # Step 3: Verify statistics
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats is not None
        assert stats.ip_address == ip_address
        assert stats.subuser == subuser
        assert stats.total_sent == 50
        assert stats.total_bounced == 8
        assert stats.hard_bounces == 5
        assert stats.soft_bounces == 3
        assert stats.bounce_rate == 0.16  # 8/50
        assert stats.status == "blocked"  # Above 15% threshold

        # Step 4: Verify threshold violations
        violations = monitor.check_thresholds()
        assert len(violations["blocked"]) == 1
        assert violations["blocked"][0].ip_address == ip_address
        assert violations["blocked"][0].subuser == subuser

    def test_multiple_ip_subuser_monitoring(self, monitor):
        """Test monitoring multiple IP/subuser combinations simultaneously."""
        test_combinations = [
            ("192.168.1.100", "marketing", 100, 3),  # 3% bounce rate - active
            ("192.168.1.101", "sales", 100, 7),  # 7% bounce rate - warning
            ("192.168.1.102", "support", 100, 12),  # 12% bounce rate - critical
            ("192.168.1.103", "newsletter", 100, 18),  # 18% bounce rate - blocked
        ]

        # Set up data for each combination
        for ip, subuser, sent_count, bounce_count in test_combinations:
            # Record sent emails
            for i in range(sent_count):
                monitor.record_sent_email(ip, subuser, f"user{i}@{subuser}.com")

            # Record bounce events
            for i in range(bounce_count):
                bounce_event = BounceEvent(
                    email=f"user{i}@{subuser}.com",
                    ip_address=ip,
                    subuser=subuser,
                    bounce_type="hard",
                    reason="Invalid email address",
                    timestamp=datetime.now(),
                )
                monitor.record_bounce_event(bounce_event)

        # Verify all statistics
        all_stats = monitor.get_all_stats()
        assert len(all_stats) == 4

        # Check individual bounce rates
        assert monitor.get_bounce_rate("192.168.1.100", "marketing") == 0.03
        assert monitor.get_bounce_rate("192.168.1.101", "sales") == 0.07
        assert monitor.get_bounce_rate("192.168.1.102", "support") == 0.12
        assert monitor.get_bounce_rate("192.168.1.103", "newsletter") == 0.18

        # Check threshold violations
        violations = monitor.check_thresholds()
        assert len(violations["warning"]) == 1
        assert len(violations["critical"]) == 1
        assert len(violations["blocked"]) == 1

        assert violations["warning"][0].subuser == "sales"
        assert violations["critical"][0].subuser == "support"
        assert violations["blocked"][0].subuser == "newsletter"

    def test_time_window_filtering(self, monitor):
        """Test that time window filtering works correctly."""
        ip_address = "192.168.1.100"
        subuser = "test_campaign"

        # Record emails sent now
        for i in range(20):
            monitor.record_sent_email(ip_address, subuser, f"recent{i}@example.com")

        # Record recent bounce events (within window)
        recent_bounces = 2
        for i in range(recent_bounces):
            bounce_event = BounceEvent(
                email=f"recent{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Recent bounce",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        # Record old bounce events (outside window)
        old_timestamp = datetime.now() - timedelta(hours=48)  # Outside 24-hour window
        old_bounces = 5
        for i in range(old_bounces):
            bounce_event = BounceEvent(
                email=f"old{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Old bounce",
                timestamp=old_timestamp,
            )
            monitor.record_bounce_event(bounce_event)

        # Verify that only recent bounces are counted
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.total_bounced == recent_bounces  # Should only count recent bounces
        assert stats.bounce_rate == recent_bounces / 20  # 2/20 = 0.10

    def test_bounce_type_categorization(self, monitor):
        """Test that different bounce types are categorized correctly."""
        ip_address = "192.168.1.100"
        subuser = "categorization_test"

        # Record sent emails
        for i in range(30):
            monitor.record_sent_email(ip_address, subuser, f"user{i}@example.com")

        # Record different types of bounces
        bounce_types = [("hard", 5), ("soft", 3), ("block", 2)]

        bounce_index = 0
        for bounce_type, count in bounce_types:
            for i in range(count):
                bounce_event = BounceEvent(
                    email=f"user{bounce_index}@example.com",
                    ip_address=ip_address,
                    subuser=subuser,
                    bounce_type=bounce_type,
                    reason=f"{bounce_type} bounce reason",
                    timestamp=datetime.now(),
                )
                monitor.record_bounce_event(bounce_event)
                bounce_index += 1

        # Verify categorization
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.hard_bounces == 5
        assert stats.soft_bounces == 3
        assert stats.block_bounces == 2
        assert stats.total_bounced == 10
        assert stats.bounce_rate == 10 / 30  # 33.3%

    def test_stats_reset_functionality(self, monitor):
        """Test resetting statistics for an IP/subuser combination."""
        ip_address = "192.168.1.100"
        subuser = "reset_test"

        # Set up initial data
        for i in range(20):
            monitor.record_sent_email(ip_address, subuser, f"user{i}@example.com")

        for i in range(5):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Initial bounce",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        # Verify initial stats
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.total_sent == 20
        assert stats.total_bounced == 5
        assert stats.bounce_rate == 0.25

        # Reset stats
        monitor.reset_stats(ip_address, subuser)

        # Verify stats are reset
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.total_sent == 0
        assert stats.total_bounced == 0
        assert stats.bounce_rate == 0.0
        assert stats.status == "active"

    def test_cleanup_old_events(self, monitor):
        """Test cleaning up old bounce events."""
        ip_address = "192.168.1.100"
        subuser = "cleanup_test"

        # Record recent events
        recent_timestamp = datetime.now()
        for i in range(5):
            bounce_event = BounceEvent(
                email=f"recent{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Recent bounce",
                timestamp=recent_timestamp,
            )
            monitor.record_bounce_event(bounce_event)

        # Record old events
        old_timestamp = datetime.now() - timedelta(days=35)
        for i in range(10):
            bounce_event = BounceEvent(
                email=f"old{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Old bounce",
                timestamp=old_timestamp,
            )
            monitor.record_bounce_event(bounce_event)

        # Verify all events are recorded
        with monitor.DatabaseConnection(monitor.db_path) as db:
            db.execute("SELECT COUNT(*) FROM bounce_events_tracking")
            total_events = db.fetchone()[0]
            assert total_events == 15

        # Clean up old events (keep 30 days)
        deleted_count = monitor.cleanup_old_events(days_to_keep=30)
        assert deleted_count == 10

        # Verify only recent events remain
        with monitor.DatabaseConnection(monitor.db_path) as db:
            db.execute("SELECT COUNT(*) FROM bounce_events_tracking")
            remaining_events = db.fetchone()[0]
            assert remaining_events == 5

    def test_concurrent_operations(self, monitor):
        """Test handling concurrent operations on the same IP/subuser."""
        ip_address = "192.168.1.100"
        subuser = "concurrent_test"

        # Simulate concurrent sent email recordings
        for i in range(10):
            monitor.record_sent_email(ip_address, subuser, f"batch1_{i}@example.com")
            monitor.record_sent_email(ip_address, subuser, f"batch2_{i}@example.com")

        # Simulate concurrent bounce event recordings
        for i in range(5):
            bounce_event1 = BounceEvent(
                email=f"batch1_{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Concurrent bounce 1",
                timestamp=datetime.now(),
            )
            bounce_event2 = BounceEvent(
                email=f"batch2_{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="soft",
                reason="Concurrent bounce 2",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event1)
            monitor.record_bounce_event(bounce_event2)

        # Verify final statistics are consistent
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.total_sent == 20
        assert stats.total_bounced == 10
        assert stats.hard_bounces == 5
        assert stats.soft_bounces == 5
        assert stats.bounce_rate == 0.5

    def test_edge_cases(self, monitor):
        """Test edge cases and error conditions."""
        ip_address = "192.168.1.100"
        subuser = "edge_case_test"

        # Test with zero emails sent
        bounce_rate = monitor.get_bounce_rate(ip_address, subuser)
        assert bounce_rate == 0.0

        # Test with non-existent IP/subuser
        stats = monitor.get_ip_subuser_stats("999.999.999.999", "nonexistent")
        assert stats is None

        # Test with minimum sample size threshold
        # Send emails below minimum sample size
        for i in range(3):  # Below minimum of 5
            monitor.record_sent_email(ip_address, subuser, f"user{i}@example.com")

        # Add bounces
        for i in range(2):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Below minimum sample",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        # Should not appear in threshold violations due to minimum sample size
        violations = monitor.check_thresholds()
        assert all(len(v) == 0 for v in violations.values())

    def test_performance_with_large_dataset(self, monitor):
        """Test performance with a larger dataset."""
        ip_addresses = [f"192.168.1.{i}" for i in range(100, 110)]  # 10 IPs
        subusers = ["marketing", "sales", "support"]  # 3 subusers

        # Generate data for all combinations
        for ip in ip_addresses:
            for subuser in subusers:
                # Record sent emails
                for i in range(50):
                    monitor.record_sent_email(ip, subuser, f"user{i}@{subuser}.com")

                # Record some bounces (varying rates)
                bounce_count = hash(f"{ip}{subuser}") % 10  # Pseudo-random bounce count
                for i in range(bounce_count):
                    bounce_event = BounceEvent(
                        email=f"user{i}@{subuser}.com",
                        ip_address=ip,
                        subuser=subuser,
                        bounce_type="hard",
                        reason="Performance test bounce",
                        timestamp=datetime.now(),
                    )
                    monitor.record_bounce_event(bounce_event)

        # Test that operations complete in reasonable time
        import time

        start_time = time.time()
        all_stats = monitor.get_all_stats()
        query_time = time.time() - start_time

        # Should have stats for all combinations
        assert len(all_stats) == 30  # 10 IPs * 3 subusers

        # Query should complete quickly (less than 1 second for this dataset)
        assert query_time < 1.0

        # Test threshold checking performance
        start_time = time.time()
        monitor.check_thresholds()
        threshold_check_time = time.time() - start_time

        assert threshold_check_time < 1.0


class TestSendGridWebhookIntegration:
    """Test integration with SendGrid webhook processing."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def monitor(self, temp_db):
        """Create a BounceRateMonitor instance for testing."""
        config = BounceRateConfig(
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15,
            minimum_sample_size=5,
        )
        return BounceRateMonitor(config=config, db_path=temp_db)

    def test_sendgrid_bounce_webhook_simulation(self, monitor):
        """Test processing SendGrid-style bounce webhook events."""
        # Simulate SendGrid webhook payload for bounce events
        sendgrid_bounce_events = [
            {
                "email": "bounce1@example.com",
                "timestamp": int(datetime.now().timestamp()),
                "event": "bounce",
                "reason": "550 5.1.1 The email account that you tried to reach does not exist.",
                "status": "5.1.1",
                "type": "bounce",
                "sg_message_id": "msg1",
                "ip": "192.168.1.100",
                "subuser": "marketing",
            },
            {
                "email": "bounce2@example.com",
                "timestamp": int(datetime.now().timestamp()),
                "event": "bounce",
                "reason": "452 4.2.2 The email account that you tried to reach is over quota.",
                "status": "4.2.2",
                "type": "bounce",
                "sg_message_id": "msg2",
                "ip": "192.168.1.100",
                "subuser": "marketing",
            },
            {
                "email": "blocked@example.com",
                "timestamp": int(datetime.now().timestamp()),
                "event": "blocked",
                "reason": "Bounced Address",
                "status": "blocked",
                "type": "blocked",
                "sg_message_id": "msg3",
                "ip": "192.168.1.100",
                "subuser": "marketing",
            },
        ]

        # Process webhook events
        for event_data in sendgrid_bounce_events:
            # Determine bounce type based on status code
            if event_data["event"] == "blocked":
                bounce_type = "block"
            elif event_data["status"].startswith("5"):
                bounce_type = "hard"
            elif event_data["status"].startswith("4"):
                bounce_type = "soft"
            else:
                bounce_type = "hard"  # Default

            bounce_event = BounceEvent(
                email=event_data["email"],
                ip_address=event_data["ip"],
                subuser=event_data["subuser"],
                bounce_type=bounce_type,
                reason=event_data["reason"],
                timestamp=datetime.fromtimestamp(event_data["timestamp"]),
                message_id=event_data["sg_message_id"],
            )

            monitor.record_bounce_event(bounce_event)

        # Record some sent emails for the same IP/subuser
        for i in range(20):
            monitor.record_sent_email(
                "192.168.1.100", "marketing", f"user{i}@example.com"
            )

        # Verify processing
        stats = monitor.get_ip_subuser_stats("192.168.1.100", "marketing")
        assert stats.total_bounced == 3
        assert stats.hard_bounces == 1  # 5.1.1 status
        assert stats.soft_bounces == 1  # 4.2.2 status
        assert stats.block_bounces == 1  # blocked event
        assert stats.bounce_rate == 3 / 20  # 15%

    def test_webhook_batch_processing(self, monitor):
        """Test processing batches of webhook events efficiently."""
        ip_address = "192.168.1.100"
        subuser = "batch_test"

        # Simulate a batch of 100 sent emails
        for i in range(100):
            monitor.record_sent_email(ip_address, subuser, f"batch{i}@example.com")

        # Simulate a batch of bounce events
        bounce_events = []
        for i in range(15):  # 15% bounce rate
            bounce_event = BounceEvent(
                email=f"batch{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard" if i % 2 == 0 else "soft",
                reason=f"Batch bounce reason {i}",
                timestamp=datetime.now(),
                message_id=f"batch_msg_{i}",
            )
            bounce_events.append(bounce_event)

        # Process all bounce events
        for bounce_event in bounce_events:
            monitor.record_bounce_event(bounce_event)

        # Verify batch processing results
        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.total_sent == 100
        assert stats.total_bounced == 15
        assert stats.bounce_rate == 0.15
        assert stats.status == "blocked"  # Above 15% threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
