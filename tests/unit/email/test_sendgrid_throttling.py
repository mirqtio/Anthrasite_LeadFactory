"""
Unit tests for SendGrid throttling system.

Tests cover throttling configuration, rate limiting, queue management,
metrics tracking, and integration with warm-up schedules.
"""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from leadfactory.email.sendgrid_throttling import (
    EmailBatch,
    QueuePriority,
    SendGridThrottler,
    SendMetrics,
    ThrottleConfig,
    ThrottleStatus,
    check_send_capacity,
    create_email_batch,
    get_throttler,
)
from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler, WarmupStatus


class TestThrottleConfig(unittest.TestCase):
    """Test throttle configuration."""

    def test_throttle_config_creation(self):
        """Test creating throttle configuration."""
        config = ThrottleConfig(
            max_sends_per_hour=200,
            max_sends_per_minute=20,
            burst_limit=10,
        )

        self.assertEqual(config.max_sends_per_hour, 200)
        self.assertEqual(config.max_sends_per_minute, 20)
        self.assertEqual(config.burst_limit, 10)
        self.assertEqual(config.burst_window_seconds, 60)
        self.assertEqual(config.queue_size_limit, 10000)
        self.assertEqual(config.emergency_stop_threshold, 0.95)

    def test_throttle_config_defaults(self):
        """Test default throttle configuration values."""
        config = ThrottleConfig()

        self.assertEqual(config.max_sends_per_hour, 100)
        self.assertEqual(config.max_sends_per_minute, 10)
        self.assertEqual(config.burst_limit, 5)
        self.assertEqual(config.emergency_stop_threshold, 0.95)


class TestEmailBatch(unittest.TestCase):
    """Test email batch data class."""

    def test_email_batch_creation(self):
        """Test creating email batch."""
        emails = [
            {"to": "test1@example.com", "subject": "Test 1"},
            {"to": "test2@example.com", "subject": "Test 2"},
        ]

        batch = EmailBatch(
            batch_id="batch-123",
            ip_address="192.168.1.1",
            emails=emails,
            priority=QueuePriority.HIGH,
            created_at=datetime.now(),
        )

        self.assertEqual(batch.batch_id, "batch-123")
        self.assertEqual(batch.ip_address, "192.168.1.1")
        self.assertEqual(len(batch.emails), 2)
        self.assertEqual(batch.priority, QueuePriority.HIGH)
        self.assertEqual(batch.attempts, 0)
        self.assertEqual(batch.max_attempts, 3)

    def test_email_batch_to_dict(self):
        """Test converting email batch to dictionary."""
        created_at = datetime.now()
        emails = [{"to": "test@example.com", "subject": "Test"}]

        batch = EmailBatch(
            batch_id="batch-456",
            ip_address="192.168.1.2",
            emails=emails,
            priority=QueuePriority.NORMAL,
            created_at=created_at,
        )

        batch_dict = batch.to_dict()

        self.assertEqual(batch_dict["batch_id"], "batch-456")
        self.assertEqual(batch_dict["ip_address"], "192.168.1.2")
        self.assertEqual(batch_dict["emails"], emails)
        self.assertEqual(batch_dict["priority"], QueuePriority.NORMAL.value)
        self.assertEqual(batch_dict["created_at"], created_at.isoformat())

    def test_email_batch_from_dict(self):
        """Test creating email batch from dictionary."""
        created_at = datetime.now()
        emails = [{"to": "test@example.com", "subject": "Test"}]

        batch_dict = {
            "batch_id": "batch-789",
            "ip_address": "192.168.1.3",
            "emails": emails,
            "priority": QueuePriority.LOW.value,
            "created_at": created_at.isoformat(),
            "scheduled_for": None,
            "attempts": 1,
            "max_attempts": 5,
        }

        batch = EmailBatch.from_dict(batch_dict)

        self.assertEqual(batch.batch_id, "batch-789")
        self.assertEqual(batch.ip_address, "192.168.1.3")
        self.assertEqual(batch.emails, emails)
        self.assertEqual(batch.priority, QueuePriority.LOW)
        self.assertEqual(batch.created_at, created_at)
        self.assertEqual(batch.attempts, 1)
        self.assertEqual(batch.max_attempts, 5)


class TestSendMetrics(unittest.TestCase):
    """Test send metrics data class."""

    def test_send_metrics_creation(self):
        """Test creating send metrics."""
        test_date = date.today()

        metrics = SendMetrics(
            date=test_date,
            ip_address="192.168.1.1",
            total_sent=100,
            total_queued=50,
            total_failed=5,
        )

        self.assertEqual(metrics.date, test_date)
        self.assertEqual(metrics.ip_address, "192.168.1.1")
        self.assertEqual(metrics.total_sent, 100)
        self.assertEqual(metrics.total_queued, 50)
        self.assertEqual(metrics.total_failed, 5)
        self.assertEqual(metrics.hourly_counts, {})

    def test_send_metrics_to_dict(self):
        """Test converting send metrics to dictionary."""
        test_date = date.today()
        last_send = datetime.now()
        hourly_counts = {9: 10, 10: 15, 11: 20}

        metrics = SendMetrics(
            date=test_date,
            ip_address="192.168.1.2",
            total_sent=45,
            hourly_counts=hourly_counts,
            last_send_time=last_send,
        )

        metrics_dict = metrics.to_dict()

        self.assertEqual(metrics_dict["date"], test_date.isoformat())
        self.assertEqual(metrics_dict["ip_address"], "192.168.1.2")
        self.assertEqual(metrics_dict["total_sent"], 45)
        self.assertEqual(metrics_dict["hourly_counts"], hourly_counts)
        self.assertEqual(metrics_dict["last_send_time"], last_send.isoformat())

    def test_send_metrics_from_dict(self):
        """Test creating send metrics from dictionary."""
        test_date = date.today()
        last_send = datetime.now()
        hourly_counts = {9: 10, 10: 15}

        metrics_dict = {
            "date": test_date.isoformat(),
            "ip_address": "192.168.1.3",
            "total_sent": 75,
            "total_queued": 25,
            "total_failed": 3,
            "hourly_counts": hourly_counts,
            "last_send_time": last_send.isoformat(),
        }

        metrics = SendMetrics.from_dict(metrics_dict)

        self.assertEqual(metrics.date, test_date)
        self.assertEqual(metrics.ip_address, "192.168.1.3")
        self.assertEqual(metrics.total_sent, 75)
        self.assertEqual(metrics.total_queued, 25)
        self.assertEqual(metrics.total_failed, 3)
        self.assertEqual(metrics.hourly_counts, hourly_counts)
        self.assertEqual(metrics.last_send_time, last_send)


class TestSendGridThrottler(unittest.TestCase):
    """Test SendGrid throttler functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_throttling.db"
        self.config = ThrottleConfig(
            max_sends_per_hour=100,
            burst_limit=5,
            emergency_stop_threshold=0.9,
        )
        self.throttler = SendGridThrottler(
            db_path=str(self.db_path),
            config=self.config,
        )

    def test_throttler_initialization(self):
        """Test throttler initialization."""
        self.assertEqual(self.throttler.db_path, self.db_path)
        self.assertEqual(self.throttler.config, self.config)
        self.assertEqual(self.throttler.status, ThrottleStatus.ACTIVE)
        self.assertTrue(self.db_path.exists())

    def test_database_initialization(self):
        """Test database table creation."""
        # Check that tables exist by querying them
        with self.throttler._get_db_connection() as conn:
            # Check email_batches table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='email_batches'"
            )
            self.assertIsNotNone(cursor.fetchone())

            # Check send_metrics table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='send_metrics'"
            )
            self.assertIsNotNone(cursor.fetchone())

            # Check throttle_events table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='throttle_events'"
            )
            self.assertIsNotNone(cursor.fetchone())

    def test_get_daily_limit_default(self):
        """Test getting daily limit without warm-up scheduler."""
        limit = self.throttler.get_daily_limit("192.168.1.1")
        self.assertEqual(limit, 100)  # Default conservative limit

    def test_get_daily_limit_with_warmup(self):
        """Test getting daily limit with warm-up scheduler."""
        # Mock warm-up scheduler
        mock_scheduler = Mock(spec=SendGridWarmupScheduler)
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        mock_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock the correct method name
        mock_scheduler.get_current_daily_limit.return_value = 500

        self.throttler.warmup_scheduler = mock_scheduler

        limit = self.throttler.get_daily_limit("192.168.1.1")
        self.assertEqual(limit, 500)

    def test_get_current_metrics_new_ip(self):
        """Test getting metrics for new IP."""
        metrics = self.throttler.get_current_metrics("192.168.1.1")

        self.assertEqual(metrics.ip_address, "192.168.1.1")
        self.assertEqual(metrics.date, date.today())
        self.assertEqual(metrics.total_sent, 0)
        self.assertEqual(metrics.total_queued, 0)
        self.assertEqual(metrics.total_failed, 0)

    def test_store_and_retrieve_metrics(self):
        """Test storing and retrieving metrics."""
        test_date = date.today()
        metrics = SendMetrics(
            date=test_date,
            ip_address="192.168.1.1",
            total_sent=50,
            total_queued=25,
            total_failed=2,
            hourly_counts={9: 10, 10: 15, 11: 25},
            last_send_time=datetime.now(),
        )

        self.throttler._store_metrics(metrics)

        # Retrieve and verify
        retrieved = self.throttler.get_current_metrics("192.168.1.1", test_date)
        self.assertEqual(retrieved.total_sent, 50)
        self.assertEqual(retrieved.total_queued, 25)
        self.assertEqual(retrieved.total_failed, 2)
        self.assertEqual(retrieved.hourly_counts, {9: 10, 10: 15, 11: 25})

    def test_can_send_now_success(self):
        """Test successful send capacity check."""
        can_send, reason = self.throttler.can_send_now("192.168.1.1", 1)
        self.assertTrue(can_send)
        self.assertEqual(reason, "OK")

    def test_can_send_now_emergency_stop(self):
        """Test send capacity check with emergency stop."""
        self.throttler.emergency_stop("192.168.1.1", "Test stop")

        can_send, reason = self.throttler.can_send_now("192.168.1.1", 1)
        self.assertFalse(can_send)
        self.assertEqual(reason, "Emergency stop activated")

    def test_can_send_now_paused(self):
        """Test send capacity check when paused."""
        self.throttler.pause_throttling("Test pause")

        can_send, reason = self.throttler.can_send_now("192.168.1.1", 1)
        self.assertFalse(can_send)
        self.assertEqual(reason, "Throttling paused")

    def test_can_send_now_disabled(self):
        """Test send capacity check when disabled."""
        self.throttler.status = ThrottleStatus.DISABLED

        can_send, reason = self.throttler.can_send_now("192.168.1.1", 1)
        self.assertTrue(can_send)
        self.assertEqual(reason, "Throttling disabled")

    @patch("leadfactory.email.sendgrid_throttling.SendGridThrottler.get_daily_limit")
    def test_can_send_now_daily_limit_exceeded(self, mock_get_limit):
        """Test send capacity check with daily limit exceeded."""
        mock_get_limit.return_value = 100

        # Set current metrics to near limit
        metrics = SendMetrics(
            date=date.today(),
            ip_address="192.168.1.1",
            total_sent=99,
        )
        self.throttler._store_metrics(metrics)

        can_send, reason = self.throttler.can_send_now("192.168.1.1", 2)
        self.assertFalse(can_send)
        self.assertIn("Daily limit exceeded", reason)

    def test_queue_email_batch_success(self):
        """Test successful email batch queuing."""
        emails = [{"to": "test@example.com", "subject": "Test"}]
        batch = EmailBatch(
            batch_id="test-batch-1",
            ip_address="192.168.1.1",
            emails=emails,
            priority=QueuePriority.NORMAL,
            created_at=datetime.now(),
        )

        success = self.throttler.queue_email_batch(batch)
        self.assertTrue(success)

        # Check queue
        self.assertEqual(self.throttler.queues[QueuePriority.NORMAL].qsize(), 1)

        # Check database
        with self.throttler._get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM email_batches WHERE batch_id = ?", ("test-batch-1",)
            ).fetchone()
            self.assertIsNotNone(row)

    def test_get_next_batch_priority_order(self):
        """Test getting next batch respects priority order."""
        # Queue batches with different priorities
        high_batch = create_email_batch(
            "high-batch",
            "192.168.1.1",
            [{"to": "test@example.com"}],
            QueuePriority.HIGH,
        )
        normal_batch = create_email_batch(
            "normal-batch",
            "192.168.1.1",
            [{"to": "test@example.com"}],
            QueuePriority.NORMAL,
        )
        low_batch = create_email_batch(
            "low-batch", "192.168.1.1", [{"to": "test@example.com"}], QueuePriority.LOW
        )

        # Queue in reverse priority order
        self.throttler.queue_email_batch(low_batch)
        self.throttler.queue_email_batch(normal_batch)
        self.throttler.queue_email_batch(high_batch)

        # Should get high priority first
        next_batch = self.throttler.get_next_batch()
        self.assertEqual(next_batch.batch_id, "high-batch")

    def test_record_send_success(self):
        """Test recording successful sends."""
        emails = [{"to": "test@example.com", "subject": "Test"}]
        batch = EmailBatch(
            batch_id="success-batch",
            ip_address="192.168.1.1",
            emails=emails,
            priority=QueuePriority.NORMAL,
            created_at=datetime.now(),
        )

        # Queue and then record success
        self.throttler.queue_email_batch(batch)
        self.throttler.record_send_success(batch, 1)

        # Check metrics updated
        metrics = self.throttler.get_current_metrics("192.168.1.1")
        self.assertEqual(metrics.total_sent, 1)
        self.assertIsNotNone(metrics.last_send_time)

    def test_record_send_failure(self):
        """Test recording send failures."""
        emails = [{"to": "test@example.com", "subject": "Test"}]
        batch = EmailBatch(
            batch_id="failure-batch",
            ip_address="192.168.1.1",
            emails=emails,
            priority=QueuePriority.NORMAL,
            created_at=datetime.now(),
        )

        # Queue and then record failure
        self.throttler.queue_email_batch(batch)
        self.throttler.record_send_failure(batch, "Test error")

        # Check metrics updated
        metrics = self.throttler.get_current_metrics("192.168.1.1")
        self.assertEqual(metrics.total_failed, 1)

    def test_emergency_stop(self):
        """Test emergency stop functionality."""
        self.throttler.emergency_stop("192.168.1.1", "Test emergency")

        self.assertEqual(self.throttler.status, ThrottleStatus.EMERGENCY_STOP)

        # Should not be able to send
        can_send, reason = self.throttler.can_send_now("192.168.1.1")
        self.assertFalse(can_send)
        self.assertEqual(reason, "Emergency stop activated")

    def test_pause_and_resume(self):
        """Test pause and resume functionality."""
        # Pause
        self.throttler.pause_throttling("Test pause")
        self.assertEqual(self.throttler.status, ThrottleStatus.PAUSED)

        can_send, reason = self.throttler.can_send_now("192.168.1.1")
        self.assertFalse(can_send)
        self.assertEqual(reason, "Throttling paused")

        # Resume
        self.throttler.resume_throttling("Test resume")
        self.assertEqual(self.throttler.status, ThrottleStatus.ACTIVE)

        can_send, reason = self.throttler.can_send_now("192.168.1.1")
        self.assertTrue(can_send)

    def test_get_throttle_status(self):
        """Test getting throttle status."""
        # Queue some batches
        batch1 = create_email_batch(
            "batch1", "192.168.1.1", [{"to": "test1@example.com"}], QueuePriority.HIGH
        )
        batch2 = create_email_batch(
            "batch2", "192.168.1.1", [{"to": "test2@example.com"}], QueuePriority.NORMAL
        )

        self.throttler.queue_email_batch(batch1)
        self.throttler.queue_email_batch(batch2)

        status = self.throttler.get_throttle_status()

        self.assertEqual(status["status"], ThrottleStatus.ACTIVE.value)
        self.assertEqual(status["total_queued"], 2)
        self.assertEqual(status["queue_breakdown"]["HIGH"], 1)
        self.assertEqual(status["queue_breakdown"]["NORMAL"], 1)
        self.assertEqual(status["queue_breakdown"]["LOW"], 0)

    def test_get_ip_status_summary(self):
        """Test getting IP status summary."""
        # Set up some metrics
        metrics = SendMetrics(
            date=date.today(),
            ip_address="192.168.1.1",
            total_sent=50,
            total_queued=10,
            total_failed=2,
            hourly_counts={9: 20, 10: 30},
            last_send_time=datetime.now(),
        )
        self.throttler._store_metrics(metrics)

        summary = self.throttler.get_ip_status_summary("192.168.1.1")

        self.assertEqual(summary["ip_address"], "192.168.1.1")
        self.assertEqual(summary["total_sent"], 50)
        self.assertEqual(summary["total_queued"], 10)
        self.assertEqual(summary["total_failed"], 2)
        self.assertEqual(summary["hourly_breakdown"], {9: 20, 10: 30})
        self.assertTrue(summary["can_send"])


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_convenience.db"

    def test_get_throttler(self):
        """Test getting throttler instance."""
        config = ThrottleConfig(max_sends_per_hour=200)
        throttler = get_throttler(str(self.db_path), config)

        self.assertIsInstance(throttler, SendGridThrottler)
        self.assertEqual(throttler.config.max_sends_per_hour, 200)

    def test_create_email_batch(self):
        """Test creating email batch."""
        emails = [{"to": "test@example.com", "subject": "Test"}]
        batch = create_email_batch(
            "test-batch", "192.168.1.1", emails, QueuePriority.HIGH
        )

        self.assertEqual(batch.batch_id, "test-batch")
        self.assertEqual(batch.ip_address, "192.168.1.1")
        self.assertEqual(batch.emails, emails)
        self.assertEqual(batch.priority, QueuePriority.HIGH)

    def test_check_send_capacity(self):
        """Test checking send capacity."""
        throttler = get_throttler(str(self.db_path))

        can_send, reason = check_send_capacity("192.168.1.1", 1, throttler)
        self.assertTrue(can_send)
        self.assertEqual(reason, "OK")

    def test_check_send_capacity_default_throttler(self):
        """Test checking send capacity with default throttler."""
        with patch("leadfactory.email.sendgrid_throttling.get_throttler") as mock_get:
            mock_throttler = Mock()
            mock_throttler.can_send_now.return_value = (True, "OK")
            mock_get.return_value = mock_throttler

            can_send, reason = check_send_capacity("192.168.1.1", 1)
            self.assertTrue(can_send)
            self.assertEqual(reason, "OK")


if __name__ == "__main__":
    unittest.main()
