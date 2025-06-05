#!/usr/bin/env python3
"""
Unit tests for SendGrid warm-up scheduler.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

# Import the module under test
from leadfactory.email.sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupConfiguration,
    WarmupProgress,
    WarmupStage,
    WarmupStatus,
    advance_warmup_if_needed,
    check_warmup_limits,
    get_warmup_scheduler,
    record_warmup_emails_sent,
)


class TestWarmupConfiguration(unittest.TestCase):
    """Test WarmupConfiguration class."""

    def test_default_configuration(self):
        """Test default configuration initialization."""
        config = WarmupConfiguration()

        # Check default values
        self.assertEqual(config.max_daily_limit, 110000)
        self.assertEqual(config.bounce_rate_threshold, 0.05)
        self.assertEqual(config.spam_rate_threshold, 0.001)
        self.assertEqual(config.stage_duration_days, 2)
        self.assertEqual(config.total_stages, 7)
        self.assertEqual(config.check_interval_hours, 1)

        # Check stage schedule
        self.assertIsNotNone(config.stage_schedule)
        self.assertEqual(len(config.stage_schedule), 7)

        # Check specific stage limits
        self.assertEqual(config.stage_schedule[1]["daily_limit"], 5000)
        self.assertEqual(config.stage_schedule[2]["daily_limit"], 15000)
        self.assertEqual(config.stage_schedule[3]["daily_limit"], 35000)
        self.assertEqual(config.stage_schedule[4]["daily_limit"], 50000)
        self.assertEqual(config.stage_schedule[5]["daily_limit"], 75000)
        self.assertEqual(config.stage_schedule[6]["daily_limit"], 100000)
        self.assertEqual(config.stage_schedule[7]["daily_limit"], 110000)

    def test_custom_configuration(self):
        """Test custom configuration."""
        custom_schedule = {
            1: {"daily_limit": 1000, "duration_days": 1, "description": "Test stage 1"},
            2: {"daily_limit": 2000, "duration_days": 1, "description": "Test stage 2"},
        }

        config = WarmupConfiguration(
            stage_schedule=custom_schedule,
            max_daily_limit=50000,
            bounce_rate_threshold=0.03,
            spam_rate_threshold=0.002,
            stage_duration_days=1,
            total_stages=2,
            alert_email="test@example.com",
        )

        self.assertEqual(config.stage_schedule, custom_schedule)
        self.assertEqual(config.max_daily_limit, 50000)
        self.assertEqual(config.bounce_rate_threshold, 0.03)
        self.assertEqual(config.spam_rate_threshold, 0.002)
        self.assertEqual(config.stage_duration_days, 1)
        self.assertEqual(config.total_stages, 2)
        self.assertEqual(config.alert_email, "test@example.com")


class TestSendGridWarmupScheduler(unittest.TestCase):
    """Test SendGridWarmupScheduler class."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create scheduler instance
        self.scheduler = SendGridWarmupScheduler(db_path=self.db_path)

        # Test IP address
        self.test_ip = "192.168.1.100"

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_database_initialization(self):
        """Test database table creation."""
        # Check that tables were created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check sendgrid_warmup_progress table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sendgrid_warmup_progress'"
        )
        self.assertIsNotNone(cursor.fetchone())

        # Check sendgrid_warmup_daily_logs table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sendgrid_warmup_daily_logs'"
        )
        self.assertIsNotNone(cursor.fetchone())

        # Check sendgrid_warmup_events table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sendgrid_warmup_events'"
        )
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_start_warmup_success(self):
        """Test successful warm-up start."""
        start_date = date.today()
        result = self.scheduler.start_warmup(self.test_ip, start_date)

        self.assertTrue(result)

        # Verify progress was created
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertIsNotNone(progress)
        self.assertEqual(progress.ip_address, self.test_ip)
        self.assertEqual(progress.status, WarmupStatus.IN_PROGRESS)
        self.assertEqual(progress.current_stage, 1)
        self.assertEqual(progress.start_date, start_date)
        self.assertEqual(progress.daily_sent_count, 0)
        self.assertEqual(progress.total_sent_count, 0)

    def test_start_warmup_already_exists(self):
        """Test starting warm-up when it already exists."""
        # Start initial warm-up
        self.scheduler.start_warmup(self.test_ip)

        # Try to start again
        result = self.scheduler.start_warmup(self.test_ip)
        self.assertFalse(result)

    def test_get_warmup_progress_not_found(self):
        """Test getting progress for non-existent IP."""
        progress = self.scheduler.get_warmup_progress("192.168.1.999")
        self.assertIsNone(progress)

    def test_get_current_daily_limit(self):
        """Test getting current daily limit."""
        # No warm-up started
        limit = self.scheduler.get_current_daily_limit(self.test_ip)
        self.assertEqual(limit, 0)

        # Start warm-up
        self.scheduler.start_warmup(self.test_ip)
        limit = self.scheduler.get_current_daily_limit(self.test_ip)
        self.assertEqual(limit, 5000)  # Stage 1 limit

    def test_can_send_email_no_warmup(self):
        """Test can_send_email with no warm-up process."""
        can_send, reason = self.scheduler.can_send_email(self.test_ip, 100)
        self.assertFalse(can_send)
        self.assertEqual(reason, "IP not in warm-up process")

    def test_can_send_email_within_limit(self):
        """Test can_send_email within daily limit."""
        self.scheduler.start_warmup(self.test_ip)

        can_send, reason = self.scheduler.can_send_email(self.test_ip, 1000)
        self.assertTrue(can_send)
        self.assertEqual(reason, "OK")

    def test_can_send_email_exceeds_limit(self):
        """Test can_send_email exceeding daily limit."""
        self.scheduler.start_warmup(self.test_ip)

        can_send, reason = self.scheduler.can_send_email(self.test_ip, 6000)
        self.assertFalse(can_send)
        self.assertIn("Would exceed daily limit", reason)

    def test_can_send_email_paused(self):
        """Test can_send_email when warm-up is paused."""
        self.scheduler.start_warmup(self.test_ip)
        self.scheduler.pause_warmup(self.test_ip, "Test pause")

        can_send, reason = self.scheduler.can_send_email(self.test_ip, 100)
        self.assertFalse(can_send)
        self.assertIn("paused", reason)

    def test_record_email_sent(self):
        """Test recording sent emails."""
        self.scheduler.start_warmup(self.test_ip)

        result = self.scheduler.record_email_sent(self.test_ip, 100)
        self.assertTrue(result)

        # Check progress was updated
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.daily_sent_count, 100)
        self.assertEqual(progress.total_sent_count, 100)

    def test_record_email_sent_no_warmup(self):
        """Test recording emails when no warm-up exists."""
        result = self.scheduler.record_email_sent(self.test_ip, 100)
        self.assertFalse(result)

    def test_advance_warmup_schedule_same_day(self):
        """Test advancing schedule on same day (no advancement)."""
        self.scheduler.start_warmup(self.test_ip)

        result = self.scheduler.advance_warmup_schedule(self.test_ip)
        self.assertTrue(result)

        # Should still be in stage 1
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.current_stage, 1)

    def test_advance_warmup_schedule_next_stage(self):
        """Test advancing to next stage."""
        # Start warm-up 3 days ago
        start_date = date.today() - timedelta(days=3)
        self.scheduler.start_warmup(self.test_ip, start_date)

        # Manually update stage start date to trigger advancement
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.stage_start_date = start_date
        progress.current_date = date.today() - timedelta(days=1)
        self.scheduler._save_warmup_progress(progress)

        result = self.scheduler.advance_warmup_schedule(self.test_ip)
        self.assertTrue(result)

        # Should advance to stage 2
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.current_stage, 2)
        self.assertEqual(progress.daily_sent_count, 0)  # Reset for new day

    def test_advance_warmup_schedule_completion(self):
        """Test warm-up completion."""
        # Start warm-up and manually set to final stage
        self.scheduler.start_warmup(self.test_ip)
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.current_stage = 7
        progress.stage_start_date = date.today() - timedelta(days=3)
        progress.current_date = date.today() - timedelta(days=1)
        self.scheduler._save_warmup_progress(progress)

        result = self.scheduler.advance_warmup_schedule(self.test_ip)
        self.assertTrue(result)

        # Should be completed
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.status, WarmupStatus.COMPLETED)

    def test_check_safety_thresholds_safe(self):
        """Test safety thresholds within limits."""
        self.scheduler.start_warmup(self.test_ip)
        self.scheduler.record_email_sent(self.test_ip, 1000)

        # Add minimal bounces/spam (within thresholds)
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.bounce_count = 10  # 1% bounce rate
        progress.spam_complaint_count = 0  # 0% spam rate
        self.scheduler._save_warmup_progress(progress)

        result = self.scheduler.check_safety_thresholds(self.test_ip)
        self.assertTrue(result)

    def test_check_safety_thresholds_bounce_exceeded(self):
        """Test safety thresholds with bounce rate exceeded."""
        self.scheduler.start_warmup(self.test_ip)
        self.scheduler.record_email_sent(self.test_ip, 1000)

        # Add high bounce rate (exceeds 5% threshold)
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.bounce_count = 60  # 6% bounce rate
        self.scheduler._save_warmup_progress(progress)

        result = self.scheduler.check_safety_thresholds(self.test_ip)
        self.assertFalse(result)

        # Should be paused
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertTrue(progress.is_paused)
        self.assertIn("Bounce rate", progress.pause_reason)

    def test_check_safety_thresholds_spam_exceeded(self):
        """Test safety thresholds with spam rate exceeded."""
        self.scheduler.start_warmup(self.test_ip)
        self.scheduler.record_email_sent(self.test_ip, 1000)

        # Add high spam rate (exceeds 0.1% threshold)
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.spam_complaint_count = 2  # 0.2% spam rate
        self.scheduler._save_warmup_progress(progress)

        result = self.scheduler.check_safety_thresholds(self.test_ip)
        self.assertFalse(result)

        # Should be paused
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertTrue(progress.is_paused)
        self.assertIn("Spam rate", progress.pause_reason)

    def test_pause_and_resume_warmup(self):
        """Test pausing and resuming warm-up."""
        self.scheduler.start_warmup(self.test_ip)

        # Pause
        result = self.scheduler.pause_warmup(self.test_ip, "Manual pause")
        self.assertTrue(result)

        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertTrue(progress.is_paused)
        self.assertEqual(progress.pause_reason, "Manual pause")

        # Resume
        result = self.scheduler.resume_warmup(self.test_ip)
        self.assertTrue(result)

        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertFalse(progress.is_paused)
        self.assertIsNone(progress.pause_reason)

    def test_get_warmup_status_summary(self):
        """Test getting status summary."""
        self.scheduler.start_warmup(self.test_ip)
        self.scheduler.record_email_sent(self.test_ip, 500)

        summary = self.scheduler.get_warmup_status_summary(self.test_ip)

        self.assertEqual(summary["ip_address"], self.test_ip)
        self.assertEqual(summary["status"], "in_progress")
        self.assertEqual(summary["current_stage"], 1)
        self.assertEqual(summary["daily_limit"], 5000)
        self.assertEqual(summary["daily_sent"], 500)
        self.assertEqual(summary["daily_remaining"], 4500)
        self.assertEqual(summary["total_sent"], 500)
        self.assertEqual(summary["bounce_count"], 0)
        self.assertEqual(summary["spam_complaint_count"], 0)
        self.assertFalse(summary["is_paused"])

    def test_get_warmup_status_summary_not_found(self):
        """Test getting status summary for non-existent IP."""
        summary = self.scheduler.get_warmup_status_summary("192.168.1.999")
        self.assertIn("error", summary)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Test IP address
        self.test_ip = "192.168.1.100"

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_get_warmup_scheduler(self):
        """Test get_warmup_scheduler function."""
        scheduler = get_warmup_scheduler(self.db_path)
        self.assertIsInstance(scheduler, SendGridWarmupScheduler)
        self.assertEqual(scheduler.db_path, self.db_path)

    def test_check_warmup_limits(self):
        """Test check_warmup_limits function."""
        # Initialize scheduler and start warm-up
        scheduler = SendGridWarmupScheduler(db_path=self.db_path)
        scheduler.start_warmup(self.test_ip)

        # Test function
        can_send, reason = check_warmup_limits(self.test_ip, 1000, self.db_path)
        self.assertTrue(can_send)
        self.assertEqual(reason, "OK")

    def test_record_warmup_emails_sent(self):
        """Test record_warmup_emails_sent function."""
        # Initialize scheduler and start warm-up
        scheduler = SendGridWarmupScheduler(db_path=self.db_path)
        scheduler.start_warmup(self.test_ip)

        # Test function
        result = record_warmup_emails_sent(self.test_ip, 100, self.db_path)
        self.assertTrue(result)

        # Verify it was recorded
        progress = scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.total_sent_count, 100)

    def test_advance_warmup_if_needed(self):
        """Test advance_warmup_if_needed function."""
        # Initialize scheduler and start warm-up
        scheduler = SendGridWarmupScheduler(db_path=self.db_path)
        scheduler.start_warmup(self.test_ip)

        # Test function
        result = advance_warmup_if_needed(self.test_ip, self.db_path)
        self.assertTrue(result)


class TestWarmupIntegration(unittest.TestCase):
    """Integration tests for warm-up system."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create scheduler instance
        self.scheduler = SendGridWarmupScheduler(db_path=self.db_path)

        # Test IP address
        self.test_ip = "192.168.1.100"

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_complete_warmup_cycle(self):
        """Test complete warm-up cycle simulation."""
        # Start warm-up
        self.scheduler.start_warmup(self.test_ip)

        # Simulate progression through all stages
        current_date = date.today()

        # Simulate 14 days total (7 stages × 2 days each)
        for _day in range(14):
            # Update current date in the scheduler's context
            progress = self.scheduler.get_warmup_progress(self.test_ip)

            # Get current stage config
            stage_config = self.scheduler.config.stage_schedule.get(
                progress.current_stage, {}
            )
            daily_limit = stage_config.get("daily_limit", 0)

            # Send emails up to daily limit for current stage
            if daily_limit > 0:
                emails_to_send = min(daily_limit, 1000)  # Send in batches
                for batch in range(0, emails_to_send, 100):
                    batch_size = min(100, emails_to_send - batch)
                    can_send, reason = self.scheduler.can_send_email(
                        self.test_ip, batch_size
                    )
                    if can_send:
                        self.scheduler.record_email_sent(self.test_ip, batch_size)

            # Advance to next day
            current_date += timedelta(days=1)
            self.scheduler.advance_warmup_schedule(self.test_ip, current_date)

        # After completing all days, advance one more time to ensure completion
        self.scheduler.advance_warmup_schedule(self.test_ip, current_date)

        # Check final status
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertEqual(progress.status, WarmupStatus.COMPLETED)
        self.assertGreater(progress.total_sent_count, 0)

    def test_warmup_with_safety_pause(self):
        """Test warm-up with safety threshold pause."""
        # Start warm-up
        self.scheduler.start_warmup(self.test_ip)

        # Send some emails
        self.scheduler.record_email_sent(self.test_ip, 1000)

        # Simulate high bounce rate
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        progress.bounce_count = 60  # 6% bounce rate (exceeds 5% threshold)
        self.scheduler._save_warmup_progress(progress)

        # Check safety thresholds
        result = self.scheduler.check_safety_thresholds(self.test_ip)
        self.assertFalse(result)

        # Should be paused
        progress = self.scheduler.get_warmup_progress(self.test_ip)
        self.assertTrue(progress.is_paused)

        # Should not be able to send emails
        can_send, reason = self.scheduler.can_send_email(self.test_ip, 100)
        self.assertFalse(can_send)
        self.assertIn("paused", reason)

        # Resume and should be able to send again
        self.scheduler.resume_warmup(self.test_ip)
        can_send, reason = self.scheduler.can_send_email(self.test_ip, 100)
        self.assertTrue(can_send)


if __name__ == "__main__":
    unittest.main()
