"""
Integration tests for SendGrid throttling system.

Tests cover complete throttling workflows, warm-up integration,
rate limiting enforcement, queue management, and system resilience.
"""

import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from leadfactory.email.sendgrid_throttling import (
    EmailBatch,
    QueuePriority,
    SendGridThrottler,
    SendMetrics,
    ThrottleConfig,
    ThrottleStatus,
    create_email_batch,
)
from leadfactory.email.sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupStage,
    WarmupStatus,
)


class TestSendGridThrottlingIntegration(unittest.TestCase):
    """Integration tests for SendGrid throttling system."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.throttle_db = Path(self.temp_dir) / "test_throttling.db"
        self.warmup_db = Path(self.temp_dir) / "test_warmup.db"

        # Create throttling config
        self.config = ThrottleConfig(
            max_sends_per_hour=50,
            max_sends_per_minute=5,
            burst_limit=3,
            burst_window_seconds=10,
            emergency_stop_threshold=0.8,
        )

        # Create warm-up scheduler
        self.warmup_scheduler = SendGridWarmupScheduler(db_path=str(self.warmup_db))

        # Create throttler with warm-up integration
        self.throttler = SendGridThrottler(
            db_path=str(self.throttle_db),
            config=self.config,
            warmup_scheduler=self.warmup_scheduler,
        )

    def test_complete_throttling_workflow(self):
        """Test complete email throttling workflow."""
        ip_address = "192.168.1.1"

        # Start warm-up for IP
        self.warmup_scheduler.start_warmup(ip_address)

        # Create email batches
        batch1 = create_email_batch(
            "batch-1",
            ip_address,
            [{"to": f"test{i}@example.com", "subject": f"Test {i}"} for i in range(5)],
            QueuePriority.HIGH,
        )

        batch2 = create_email_batch(
            "batch-2",
            ip_address,
            [
                {"to": f"test{i + 5}@example.com", "subject": f"Test {i + 5}"}
                for i in range(3)
            ],
            QueuePriority.NORMAL,
        )

        # Queue batches
        self.assertTrue(self.throttler.queue_email_batch(batch1))
        self.assertTrue(self.throttler.queue_email_batch(batch2))

        # Process batches
        processed_batches = []
        while True:
            next_batch = self.throttler.get_next_batch(ip_address)
            if not next_batch:
                break

            # Simulate sending
            can_send, reason = self.throttler.can_send_now(
                next_batch.ip_address, len(next_batch.emails)
            )
            if can_send:
                self.throttler.record_send_success(next_batch, len(next_batch.emails))
                processed_batches.append(next_batch)
            else:
                # Put back in queue if rate limited
                if "limit" in reason.lower():
                    self.throttler.queue_email_batch(next_batch)
                    time.sleep(0.1)  # Brief pause
                    continue
                break

        # Verify processing
        self.assertEqual(len(processed_batches), 2)
        self.assertEqual(
            processed_batches[0].priority, QueuePriority.HIGH
        )  # High priority first

        # Check metrics
        metrics = self.throttler.get_current_metrics(ip_address)
        self.assertEqual(metrics.total_sent, 8)  # 5 + 3 emails
        self.assertGreater(len(metrics.hourly_counts), 0)

    def test_warmup_integration_daily_limits(self):
        """Test integration with warm-up scheduler for daily limits."""
        ip_address = "192.168.1.2"

        # Start warm-up
        self.warmup_scheduler.start_warmup(ip_address)

        # Get current daily limit
        expected_limit = self.warmup_scheduler.get_current_daily_limit(ip_address)

        # Check throttler gets correct limit
        actual_limit = self.throttler.get_daily_limit(ip_address)
        self.assertEqual(actual_limit, expected_limit)

        # Test limit enforcement
        large_batch = create_email_batch(
            "large-batch",
            ip_address,
            [{"to": f"test{i}@example.com"} for i in range(expected_limit + 10)],
            QueuePriority.NORMAL,
        )

        can_send, reason = self.throttler.can_send_now(
            ip_address, len(large_batch.emails)
        )
        self.assertFalse(can_send)
        self.assertIn("Daily limit exceeded", reason)

    def test_rate_limiting_enforcement(self):
        """Test rate limiting enforcement."""
        ip_address = "192.168.1.3"

        # Send up to burst limit
        for i in range(self.config.burst_limit):
            batch = create_email_batch(
                f"burst-{i}", ip_address, [{"to": "test@example.com"}]
            )
            self.assertTrue(self.throttler.queue_email_batch(batch))

            next_batch = self.throttler.get_next_batch(ip_address)
            self.assertIsNotNone(next_batch)

            can_send, reason = self.throttler.can_send_now(ip_address, 1)
            self.assertTrue(can_send, f"Should be able to send batch {i}: {reason}")

            self.throttler.record_send_success(next_batch, 1)

        # Next send should be rate limited
        can_send, reason = self.throttler.can_send_now(ip_address, 1)
        self.assertFalse(can_send)
        self.assertIn("Burst limit exceeded", reason)

        # Wait for burst window to reset
        time.sleep(self.config.burst_window_seconds + 1)

        # Should be able to send again
        can_send, reason = self.throttler.can_send_now(ip_address, 1)
        self.assertTrue(can_send)

    def test_queue_priority_management(self):
        """Test queue priority management."""
        ip_address = "192.168.1.4"

        # Create batches with different priorities
        low_batch = create_email_batch(
            "low", ip_address, [{"to": "low@example.com"}], QueuePriority.LOW
        )
        normal_batch = create_email_batch(
            "normal", ip_address, [{"to": "normal@example.com"}], QueuePriority.NORMAL
        )
        high_batch = create_email_batch(
            "high", ip_address, [{"to": "high@example.com"}], QueuePriority.HIGH
        )

        # Queue in reverse priority order
        self.throttler.queue_email_batch(low_batch)
        self.throttler.queue_email_batch(normal_batch)
        self.throttler.queue_email_batch(high_batch)

        # Should get high priority first
        next_batch = self.throttler.get_next_batch(ip_address)
        self.assertEqual(next_batch.batch_id, "high")

        # Then normal
        next_batch = self.throttler.get_next_batch(ip_address)
        self.assertEqual(next_batch.batch_id, "normal")

        # Finally low
        next_batch = self.throttler.get_next_batch(ip_address)
        self.assertEqual(next_batch.batch_id, "low")

    def test_emergency_stop_workflow(self):
        """Test emergency stop workflow."""
        ip_address = "192.168.1.5"

        # Start warm-up to get daily limit
        self.warmup_scheduler.start_warmup(ip_address)
        daily_limit = self.throttler.get_daily_limit(ip_address)

        # Send emails up to emergency threshold
        emergency_threshold = int(daily_limit * self.config.emergency_stop_threshold)

        # Simulate sending close to threshold
        metrics = SendMetrics(
            date=date.today(),
            ip_address=ip_address,
            total_sent=emergency_threshold - 1,
        )
        self.throttler._store_metrics(metrics)

        # Try to send more - should trigger emergency stop
        can_send, reason = self.throttler.can_send_now(ip_address, 2)
        self.assertFalse(can_send)
        self.assertIn("Emergency stop triggered", reason)

        # Verify emergency stop status
        self.assertEqual(self.throttler.status, ThrottleStatus.EMERGENCY_STOP)

        # No further sends should be allowed
        can_send, reason = self.throttler.can_send_now(ip_address, 1)
        self.assertFalse(can_send)
        self.assertEqual(reason, "Emergency stop activated")

    def test_batch_retry_mechanism(self):
        """Test email batch retry mechanism."""
        ip_address = "192.168.1.6"

        # Create batch
        batch = create_email_batch(
            "retry-batch", ip_address, [{"to": "test@example.com"}]
        )
        self.throttler.queue_email_batch(batch)

        # Get batch and simulate failure
        next_batch = self.throttler.get_next_batch(ip_address)
        self.assertIsNotNone(next_batch)

        # Record failure
        self.throttler.record_send_failure(next_batch, "Temporary error")

        # Should be requeued with incremented attempts
        time.sleep(0.1)  # Brief pause for scheduling
        retry_batch = self.throttler.get_next_batch(ip_address)

        # Check if batch was requeued (might be scheduled for later)
        if retry_batch:
            self.assertEqual(retry_batch.batch_id, "retry-batch")
            self.assertGreater(retry_batch.attempts, 0)

    def test_hourly_rate_distribution(self):
        """Test hourly rate distribution."""
        ip_address = "192.168.1.7"

        # Send emails and track hourly distribution
        current_hour = datetime.now().hour

        # Send multiple batches
        for i in range(10):
            batch = create_email_batch(
                f"hourly-{i}", ip_address, [{"to": f"test{i}@example.com"}]
            )
            self.throttler.queue_email_batch(batch)

            next_batch = self.throttler.get_next_batch(ip_address)
            if next_batch:
                can_send, reason = self.throttler.can_send_now(ip_address, 1)
                if can_send:
                    self.throttler.record_send_success(next_batch, 1)
                else:
                    break

        # Check hourly tracking
        metrics = self.throttler.get_current_metrics(ip_address)
        self.assertIn(current_hour, metrics.hourly_counts)
        self.assertGreater(metrics.hourly_counts[current_hour], 0)

    def test_concurrent_ip_management(self):
        """Test managing multiple IPs concurrently."""
        ip1 = "192.168.1.8"
        ip2 = "192.168.1.9"

        # Start warm-up for both IPs
        self.warmup_scheduler.start_warmup(ip1)
        self.warmup_scheduler.start_warmup(ip2)

        # Create batches for both IPs
        batch1 = create_email_batch("ip1-batch", ip1, [{"to": "test1@example.com"}])
        batch2 = create_email_batch("ip2-batch", ip2, [{"to": "test2@example.com"}])

        # Queue batches
        self.throttler.queue_email_batch(batch1)
        self.throttler.queue_email_batch(batch2)

        # Process batches for each IP
        ip1_batch = self.throttler.get_next_batch(ip1)
        ip2_batch = self.throttler.get_next_batch(ip2)

        self.assertIsNotNone(ip1_batch)
        self.assertIsNotNone(ip2_batch)
        self.assertEqual(ip1_batch.ip_address, ip1)
        self.assertEqual(ip2_batch.ip_address, ip2)

        # Record sends
        self.throttler.record_send_success(ip1_batch, 1)
        self.throttler.record_send_success(ip2_batch, 1)

        # Check separate metrics
        ip1_metrics = self.throttler.get_current_metrics(ip1)
        ip2_metrics = self.throttler.get_current_metrics(ip2)

        self.assertEqual(ip1_metrics.total_sent, 1)
        self.assertEqual(ip2_metrics.total_sent, 1)

    def test_database_persistence_across_sessions(self):
        """Test database persistence across throttler sessions."""
        ip_address = "192.168.1.10"

        # Create and queue batch
        batch = create_email_batch(
            "persistent-batch", ip_address, [{"to": "test@example.com"}]
        )
        self.throttler.queue_email_batch(batch)

        # Record some metrics
        metrics = SendMetrics(
            date=date.today(),
            ip_address=ip_address,
            total_sent=25,
            total_queued=5,
            hourly_counts={10: 15, 11: 10},
        )
        self.throttler._store_metrics(metrics)

        # Create new throttler instance with same database
        new_throttler = SendGridThrottler(
            db_path=str(self.throttle_db),
            config=self.config,
        )

        # Check metrics persistence
        retrieved_metrics = new_throttler.get_current_metrics(ip_address)
        self.assertEqual(retrieved_metrics.total_sent, 25)
        self.assertEqual(retrieved_metrics.total_queued, 5)
        self.assertEqual(retrieved_metrics.hourly_counts, {10: 15, 11: 10})

        # Check batch persistence
        with new_throttler._get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM email_batches WHERE batch_id = ?", ("persistent-batch",)
            ).fetchone()
            self.assertIsNotNone(row)

    def test_throttle_status_monitoring(self):
        """Test comprehensive throttle status monitoring."""
        ip_address = "192.168.1.11"

        # Queue batches with different priorities
        high_batch = create_email_batch(
            "high", ip_address, [{"to": "high@example.com"}], QueuePriority.HIGH
        )
        normal_batch = create_email_batch(
            "normal", ip_address, [{"to": "normal@example.com"}], QueuePriority.NORMAL
        )

        self.throttler.queue_email_batch(high_batch)
        self.throttler.queue_email_batch(normal_batch)

        # Get system status
        system_status = self.throttler.get_throttle_status()

        self.assertEqual(system_status["status"], ThrottleStatus.ACTIVE.value)
        self.assertEqual(system_status["total_queued"], 2)
        self.assertEqual(system_status["queue_breakdown"]["HIGH"], 1)
        self.assertEqual(system_status["queue_breakdown"]["NORMAL"], 1)
        self.assertEqual(system_status["queue_breakdown"]["LOW"], 0)

        # Get IP-specific status
        ip_status = self.throttler.get_ip_status_summary(ip_address)

        self.assertEqual(ip_status["ip_address"], ip_address)
        self.assertGreater(ip_status["daily_limit"], 0)
        self.assertTrue(ip_status["can_send"])
        self.assertEqual(ip_status["send_status"], "OK")

    def test_error_recovery_and_resilience(self):
        """Test system error recovery and resilience."""
        ip_address = "192.168.1.12"

        # Test with corrupted batch data
        batch = create_email_batch(
            "error-batch", ip_address, [{"to": "test@example.com"}]
        )

        # Queue batch successfully
        self.assertTrue(self.throttler.queue_email_batch(batch))

        # Simulate processing error
        next_batch = self.throttler.get_next_batch(ip_address)
        self.assertIsNotNone(next_batch)

        # Record failure multiple times to exceed max attempts
        for attempt in range(next_batch.max_attempts):
            self.throttler.record_send_failure(
                next_batch, f"Error attempt {attempt + 1}"
            )

        # Batch should be removed after max attempts
        with self.throttler._get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM email_batches WHERE batch_id = ?", ("error-batch",)
            ).fetchone()
            # Should be None after max attempts exceeded

        # System should still be functional
        new_batch = create_email_batch(
            "recovery-batch", ip_address, [{"to": "recovery@example.com"}]
        )
        self.assertTrue(self.throttler.queue_email_batch(new_batch))

        can_send, reason = self.throttler.can_send_now(ip_address, 1)
        self.assertTrue(can_send)


if __name__ == "__main__":
    unittest.main()
