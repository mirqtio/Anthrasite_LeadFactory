#!/usr/bin/env python3
"""
Unit tests for the Bounce Rate Monitoring System.

Tests the BounceRateMonitor class and its functionality for tracking
bounce rates per IP/subuser combination.
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the module under test
from leadfactory.services.bounce_monitor import (
    BounceEvent,
    BounceRateConfig,
    BounceRateMonitor,
    CalculationMethod,
    IPSubuserStats,
    SamplingPeriod,
)


class TestBounceRateConfig:
    """Test BounceRateConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BounceRateConfig()

        assert config.sampling_period == SamplingPeriod.HOURLY
        assert config.calculation_method == CalculationMethod.ROLLING_AVERAGE
        assert config.rolling_window_hours == 24
        assert config.minimum_sample_size == 10
        assert config.warning_threshold == 0.05
        assert config.critical_threshold == 0.10
        assert config.block_threshold == 0.15
        assert config.exponential_decay_factor == 0.9

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BounceRateConfig(
            sampling_period=SamplingPeriod.DAILY,
            calculation_method=CalculationMethod.POINT_IN_TIME,
            rolling_window_hours=48,
            minimum_sample_size=20,
            warning_threshold=0.03,
            critical_threshold=0.08,
            block_threshold=0.12,
        )

        assert config.sampling_period == SamplingPeriod.DAILY
        assert config.calculation_method == CalculationMethod.POINT_IN_TIME
        assert config.rolling_window_hours == 48
        assert config.minimum_sample_size == 20
        assert config.warning_threshold == 0.03
        assert config.critical_threshold == 0.08
        assert config.block_threshold == 0.12


class TestIPSubuserStats:
    """Test IPSubuserStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = IPSubuserStats(ip_address="192.168.1.1", subuser="test")

        assert stats.ip_address == "192.168.1.1"
        assert stats.subuser == "test"
        assert stats.total_sent == 0
        assert stats.total_bounced == 0
        assert stats.hard_bounces == 0
        assert stats.soft_bounces == 0
        assert stats.block_bounces == 0
        assert stats.bounce_rate == 0.0
        assert stats.status == "active"
        assert isinstance(stats.last_updated, datetime)

    def test_calculate_bounce_rate_zero_sent(self):
        """Test bounce rate calculation with zero emails sent."""
        stats = IPSubuserStats(ip_address="192.168.1.1", subuser="test")

        bounce_rate = stats.calculate_bounce_rate()

        assert bounce_rate == 0.0
        assert stats.bounce_rate == 0.0

    def test_calculate_bounce_rate_with_bounces(self):
        """Test bounce rate calculation with bounces."""
        stats = IPSubuserStats(
            ip_address="192.168.1.1", subuser="test", total_sent=100, total_bounced=5
        )

        bounce_rate = stats.calculate_bounce_rate()

        assert bounce_rate == 0.05
        assert stats.bounce_rate == 0.05

    def test_calculate_bounce_rate_high_bounces(self):
        """Test bounce rate calculation with high bounce count."""
        stats = IPSubuserStats(
            ip_address="192.168.1.1", subuser="test", total_sent=50, total_bounced=10
        )

        bounce_rate = stats.calculate_bounce_rate()

        assert bounce_rate == 0.20
        assert stats.bounce_rate == 0.20


class TestBounceEvent:
    """Test BounceEvent dataclass."""

    def test_bounce_event_creation(self):
        """Test creating a bounce event."""
        timestamp = datetime.now()
        event = BounceEvent(
            email="test@example.com",
            ip_address="192.168.1.1",
            subuser="marketing",
            bounce_type="hard",
            reason="Invalid email",
            timestamp=timestamp,
            message_id="msg123",
        )

        assert event.email == "test@example.com"
        assert event.ip_address == "192.168.1.1"
        assert event.subuser == "marketing"
        assert event.bounce_type == "hard"
        assert event.reason == "Invalid email"
        assert event.timestamp == timestamp
        assert event.message_id == "msg123"


class TestBounceRateMonitor:
    """Test BounceRateMonitor class."""

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
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15,
            minimum_sample_size=5,
        )

    @pytest.fixture
    def monitor(self, config, temp_db):
        """Create a BounceRateMonitor instance for testing."""
        return BounceRateMonitor(config=config, db_path=temp_db)

    def test_monitor_initialization(self, monitor, config):
        """Test monitor initialization."""
        assert monitor.config == config
        assert monitor._stats_cache == {}
        assert isinstance(monitor._last_cache_update, datetime)
        assert monitor._cache_ttl_seconds == 300

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_initialize_tables(self, mock_db_conn, config):
        """Test database table initialization."""
        mock_db = Mock()
        mock_db_conn.return_value.__enter__.return_value = mock_db

        BounceRateMonitor(config=config)

        # Verify tables were created
        assert mock_db.execute.call_count >= 3  # At least 3 SQL statements
        mock_db.commit.assert_called()

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_record_bounce_event(self, mock_db_conn, monitor):
        """Test recording a bounce event."""
        mock_db = Mock()
        mock_db_conn.return_value.__enter__.return_value = mock_db

        bounce_event = BounceEvent(
            email="test@example.com",
            ip_address="192.168.1.1",
            subuser="marketing",
            bounce_type="hard",
            reason="Invalid email",
            timestamp=datetime.now(),
        )

        monitor.record_bounce_event(bounce_event)

        # Verify event was inserted
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_record_sent_email(self, mock_db_conn, monitor):
        """Test recording a sent email."""
        mock_db = Mock()
        mock_db_conn.return_value.__enter__.return_value = mock_db

        monitor.record_sent_email("192.168.1.1", "marketing", "test@example.com")

        # Verify database was updated
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_get_bounce_rate_no_data(self, mock_db_conn, monitor):
        """Test getting bounce rate when no data exists."""
        mock_db = Mock()
        mock_db.fetchone.return_value = None
        mock_db_conn.return_value.__enter__.return_value = mock_db

        bounce_rate = monitor.get_bounce_rate("192.168.1.1", "marketing")

        assert bounce_rate == 0.0

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_get_ip_subuser_stats(self, mock_db_conn, monitor):
        """Test getting IP/subuser statistics."""
        mock_db = Mock()
        mock_db.fetchone.return_value = (
            "192.168.1.1",
            "marketing",
            100,
            5,
            3,
            2,
            0,
            0.05,
            "active",
            "2023-01-01T12:00:00",
        )
        mock_db_conn.return_value.__enter__.return_value = mock_db

        stats = monitor.get_ip_subuser_stats("192.168.1.1", "marketing")

        assert stats is not None
        assert stats.ip_address == "192.168.1.1"
        assert stats.subuser == "marketing"
        assert stats.total_sent == 100
        assert stats.total_bounced == 5
        assert stats.hard_bounces == 3
        assert stats.soft_bounces == 2
        assert stats.block_bounces == 0
        assert stats.bounce_rate == 0.05
        assert stats.status == "active"

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_get_all_stats(self, mock_db_conn, monitor):
        """Test getting all statistics."""
        mock_db = Mock()
        mock_db.fetchall.return_value = [
            (
                "192.168.1.1",
                "marketing",
                100,
                5,
                3,
                2,
                0,
                0.05,
                "active",
                "2023-01-01T12:00:00",
            ),
            (
                "192.168.1.2",
                "sales",
                50,
                8,
                5,
                3,
                0,
                0.16,
                "blocked",
                "2023-01-01T12:00:00",
            ),
        ]
        mock_db_conn.return_value.__enter__.return_value = mock_db

        all_stats = monitor.get_all_stats()

        assert len(all_stats) == 2
        assert all_stats[0].ip_address == "192.168.1.1"
        assert all_stats[0].subuser == "marketing"
        assert all_stats[1].ip_address == "192.168.1.2"
        assert all_stats[1].subuser == "sales"

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_get_threshold_violations(self, mock_db_conn, monitor):
        """Test getting threshold violations."""
        mock_db = Mock()
        mock_db.fetchall.return_value = [
            (
                "192.168.1.2",
                "sales",
                50,
                8,
                5,
                3,
                0,
                0.16,
                "blocked",
                "2023-01-01T12:00:00",
            )
        ]
        mock_db_conn.return_value.__enter__.return_value = mock_db

        violations = monitor.get_threshold_violations()

        assert len(violations) == 1
        assert violations[0].ip_address == "192.168.1.2"
        assert violations[0].bounce_rate == 0.16

    def test_check_thresholds(self, monitor):
        """Test checking thresholds against all stats."""
        # Mock get_all_stats to return test data
        test_stats = [
            IPSubuserStats(
                "192.168.1.1",
                "marketing",
                100,
                3,
                2,
                1,
                0,
                bounce_rate=0.03,
                status="active",
            ),
            IPSubuserStats(
                "192.168.1.2",
                "sales",
                100,
                7,
                4,
                3,
                0,
                bounce_rate=0.07,
                status="warning",
            ),
            IPSubuserStats(
                "192.168.1.3",
                "support",
                100,
                12,
                8,
                4,
                0,
                bounce_rate=0.12,
                status="critical",
            ),
            IPSubuserStats(
                "192.168.1.4",
                "test",
                100,
                18,
                12,
                6,
                0,
                bounce_rate=0.18,
                status="blocked",
            ),
            IPSubuserStats(
                "192.168.1.5",
                "small",
                3,
                1,
                1,
                0,
                0,
                bounce_rate=0.33,
                status="blocked",
            ),  # Below minimum sample size
        ]

        with patch.object(monitor, "get_all_stats", return_value=test_stats):
            violations = monitor.check_thresholds()

        assert len(violations["warning"]) == 1
        assert violations["warning"][0].ip_address == "192.168.1.2"

        assert len(violations["critical"]) == 1
        assert violations["critical"][0].ip_address == "192.168.1.3"

        assert len(violations["blocked"]) == 1
        assert violations["blocked"][0].ip_address == "192.168.1.4"

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_reset_stats(self, mock_db_conn, monitor):
        """Test resetting statistics for an IP/subuser."""
        mock_db = Mock()
        mock_db_conn.return_value.__enter__.return_value = mock_db

        # Add item to cache first
        cache_key = ("192.168.1.1", "marketing")
        monitor._stats_cache[cache_key] = IPSubuserStats("192.168.1.1", "marketing")

        monitor.reset_stats("192.168.1.1", "marketing")

        # Verify database was updated
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

        # Verify cache was cleared
        assert cache_key not in monitor._stats_cache

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_cleanup_old_events(self, mock_db_conn, monitor):
        """Test cleaning up old bounce events."""
        mock_db = Mock()
        mock_db.rowcount = 15
        mock_db_conn.return_value.__enter__.return_value = mock_db

        deleted_count = monitor.cleanup_old_events(days_to_keep=30)

        assert deleted_count == 15
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_update_ip_subuser_stats_new_entry(self, mock_db_conn, monitor):
        """Test updating stats for a new IP/subuser combination."""
        mock_db = Mock()
        # First query returns None (no existing stats)
        # Second query returns bounce counts
        # Third query is the upsert
        mock_db.fetchone.side_effect = [None]
        mock_db.fetchall.return_value = [("hard", 2), ("soft", 1)]
        mock_db_conn.return_value.__enter__.return_value = mock_db

        monitor._update_ip_subuser_stats("192.168.1.1", "marketing", sent_count=10)

        # Verify database operations
        assert mock_db.execute.call_count >= 3
        mock_db.commit.assert_called()

    @patch("leadfactory.services.bounce_monitor.DatabaseConnection")
    def test_update_ip_subuser_stats_existing_entry(self, mock_db_conn, monitor):
        """Test updating stats for an existing IP/subuser combination."""
        mock_db = Mock()
        # First query returns existing stats
        mock_db.fetchone.return_value = (90, 4, 2, 2, 0)
        # Second query returns new bounce counts
        mock_db.fetchall.return_value = [("hard", 3), ("soft", 2)]
        mock_db_conn.return_value.__enter__.return_value = mock_db

        monitor._update_ip_subuser_stats("192.168.1.1", "marketing", sent_count=10)

        # Verify database operations
        assert mock_db.execute.call_count >= 3
        mock_db.commit.assert_called()

    def test_cache_functionality(self, monitor):
        """Test that caching works correctly."""
        # Create a mock stats object
        test_stats = IPSubuserStats("192.168.1.1", "marketing", 100, 5)
        cache_key = ("192.168.1.1", "marketing")

        # Add to cache
        monitor._stats_cache[cache_key] = test_stats
        monitor._last_cache_update = datetime.now()

        # Should return cached version
        with patch(
            "leadfactory.services.bounce_monitor.DatabaseConnection"
        ) as mock_db_conn:
            result = monitor.get_ip_subuser_stats("192.168.1.1", "marketing")

            # Database should not be called
            mock_db_conn.assert_not_called()
            assert result == test_stats

    def test_cache_expiry(self, monitor):
        """Test that cache expires correctly."""
        # Create a mock stats object
        test_stats = IPSubuserStats("192.168.1.1", "marketing", 100, 5)
        cache_key = ("192.168.1.1", "marketing")

        # Add to cache with old timestamp
        monitor._stats_cache[cache_key] = test_stats
        monitor._last_cache_update = datetime.now() - timedelta(
            seconds=400
        )  # Older than TTL

        # Mock database response
        with patch(
            "leadfactory.services.bounce_monitor.DatabaseConnection"
        ) as mock_db_conn:
            mock_db = Mock()
            mock_db.fetchone.return_value = (
                "192.168.1.1",
                "marketing",
                100,
                5,
                3,
                2,
                0,
                0.05,
                "active",
                "2023-01-01T12:00:00",
            )
            mock_db_conn.return_value.__enter__.return_value = mock_db

            result = monitor.get_ip_subuser_stats("192.168.1.1", "marketing")

            # Database should be called due to cache expiry
            mock_db_conn.assert_called()
            assert result is not None


class TestIntegrationScenarios:
    """Integration tests for realistic bounce monitoring scenarios."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def monitor(self, temp_db):
        """Create a real monitor instance for integration testing."""
        config = BounceRateConfig(
            warning_threshold=0.05,
            critical_threshold=0.10,
            block_threshold=0.15,
            minimum_sample_size=5,
        )
        return BounceRateMonitor(config=config, db_path=temp_db)

    def test_realistic_bounce_scenario(self, monitor):
        """Test a realistic bounce monitoring scenario."""
        ip_address = "192.168.1.100"
        subuser = "marketing"

        # Record some sent emails
        for i in range(20):
            monitor.record_sent_email(ip_address, subuser, f"user{i}@example.com")

        # Record some bounce events
        for i in range(3):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Invalid email address",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        # Check bounce rate (should be 3/20 = 0.15 = 15%)
        bounce_rate = monitor.get_bounce_rate(ip_address, subuser)
        assert bounce_rate == 0.15

        # Check threshold violations
        violations = monitor.check_thresholds()
        assert len(violations["blocked"]) == 1
        assert violations["blocked"][0].ip_address == ip_address

    def test_multiple_ip_subuser_combinations(self, monitor):
        """Test monitoring multiple IP/subuser combinations."""
        combinations = [
            ("192.168.1.100", "marketing"),
            ("192.168.1.101", "sales"),
            ("192.168.1.102", "support"),
        ]

        # Set up different bounce rates for each combination
        for i, (ip, subuser) in enumerate(combinations):
            # Send emails
            for j in range(10):
                monitor.record_sent_email(ip, subuser, f"user{j}@example.com")

            # Create different bounce counts
            bounce_count = i + 1  # 1, 2, 3 bounces respectively
            for j in range(bounce_count):
                bounce_event = BounceEvent(
                    email=f"user{j}@example.com",
                    ip_address=ip,
                    subuser=subuser,
                    bounce_type="hard",
                    reason="Invalid email address",
                    timestamp=datetime.now(),
                )
                monitor.record_bounce_event(bounce_event)

        # Check all stats
        all_stats = monitor.get_all_stats()
        assert len(all_stats) == 3

        # Verify bounce rates
        assert monitor.get_bounce_rate("192.168.1.100", "marketing") == 0.1  # 1/10
        assert monitor.get_bounce_rate("192.168.1.101", "sales") == 0.2  # 2/10
        assert monitor.get_bounce_rate("192.168.1.102", "support") == 0.3  # 3/10

    def test_threshold_status_updates(self, monitor):
        """Test that status is updated correctly based on thresholds."""
        ip_address = "192.168.1.100"
        subuser = "test"

        # Start with low bounce rate (below warning)
        for i in range(100):
            monitor.record_sent_email(ip_address, subuser, f"user{i}@example.com")

        # Add 2 bounces (2% bounce rate - below warning threshold of 5%)
        for i in range(2):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Invalid email address",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.status == "active"

        # Add more bounces to reach warning threshold (6% total)
        for i in range(2, 6):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Invalid email address",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.status == "warning"

        # Add more bounces to reach critical threshold (11% total)
        for i in range(6, 11):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Invalid email address",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.status == "critical"

        # Add more bounces to reach block threshold (16% total)
        for i in range(11, 16):
            bounce_event = BounceEvent(
                email=f"user{i}@example.com",
                ip_address=ip_address,
                subuser=subuser,
                bounce_type="hard",
                reason="Invalid email address",
                timestamp=datetime.now(),
            )
            monitor.record_bounce_event(bounce_event)

        stats = monitor.get_ip_subuser_stats(ip_address, subuser)
        assert stats.status == "blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
