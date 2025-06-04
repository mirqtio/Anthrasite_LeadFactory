#!/usr/bin/env python3
"""
Integration tests for SendGrid warmup integration with bounce monitoring and IP rotation.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from leadfactory.email.sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupConfiguration,
    WarmupStatus,
)
from leadfactory.email.sendgrid_warmup_integration import (
    SendGridWarmupIntegration,
    WarmupIntegrationConfig,
    setup_integrated_email_system,
)


class TestSendGridWarmupIntegrationReal(unittest.TestCase):
    """Integration tests with real warmup scheduler."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.warmup_db = Path(self.temp_dir) / "test_warmup.db"
        self.bounce_db = Path(self.temp_dir) / "test_bounce.db"

        # Create real warmup scheduler
        warmup_config = WarmupConfiguration()
        self.warmup_scheduler = SendGridWarmupScheduler(
            config=warmup_config,
            db_path=str(self.warmup_db),
        )

        # Create mock bounce monitor and rotation service
        self.bounce_monitor = Mock()
        self.bounce_monitor.get_ip_subuser_stats.return_value = None
        self.bounce_monitor.check_thresholds.return_value = {}

        self.rotation_service = Mock()
        self.rotation_service.get_pool_status.return_value = []

        # Create integration config
        self.config = WarmupIntegrationConfig(
            warmup_warning_threshold=0.05,
            warmup_critical_threshold=0.10,
            warmup_block_threshold=0.20,
        )

        # Create integration instance
        self.integration = SendGridWarmupIntegration(
            warmup_scheduler=self.warmup_scheduler,
            bounce_monitor=self.bounce_monitor,
            rotation_service=self.rotation_service,
            config=self.config,
        )

    def test_full_warmup_lifecycle_with_integration(self):
        """Test complete warmup lifecycle with integration monitoring."""
        ip_address = "192.168.1.100"

        # Start warmup with monitoring
        result = self.integration.start_ip_warmup_with_monitoring(ip_address)
        self.assertTrue(result)

        # Verify warmup started
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        self.assertIsNotNone(progress)
        self.assertEqual(progress.status, WarmupStatus.IN_PROGRESS)

        # Verify IP is being monitored
        self.assertIn(ip_address, self.integration.monitored_ips)

        # Check initial bounce thresholds (should be safe)
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.03  # Safe level
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(ip_address)
        self.assertTrue(is_safe)
        self.assertIsNone(reason)

        # Simulate high bounce rate
        mock_stats.bounce_rate = 0.25  # Above block threshold
        is_safe, reason = self.integration.check_warmup_bounce_thresholds(ip_address)
        self.assertFalse(is_safe)
        self.assertIn("block threshold", reason)

        # Verify warmup was paused due to high bounce rate
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        self.assertEqual(progress.status, WarmupStatus.PAUSED)

        # Resume warmup
        self.warmup_scheduler.resume_warmup(ip_address)
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        self.assertEqual(progress.status, WarmupStatus.IN_PROGRESS)

        # Complete warmup manually for testing
        # Simulate advancing through all stages to completion
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        if progress:
            # Manually set to completed status for testing
            progress.status = WarmupStatus.COMPLETED
            progress.current_stage = self.warmup_scheduler.config.total_stages
            self.warmup_scheduler._save_warmup_progress(progress)

        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        self.assertEqual(progress.status, WarmupStatus.COMPLETED)

        # Handle warmup completion
        result = self.integration.handle_warmup_completion(ip_address)
        self.assertTrue(result)

        # Verify IP was added to rotation pool
        self.rotation_service.add_ip_subuser.assert_called_once()
        call_args = self.rotation_service.add_ip_subuser.call_args
        self.assertEqual(call_args[1]["ip_address"], ip_address)
        self.assertEqual(call_args[1]["subuser"], "default")
        self.assertIn("warmed-up", call_args[1]["tags"])

    def test_warmup_integration_with_rotation_decisions(self):
        """Test integration affecting rotation decisions."""
        ip1 = "192.168.1.101"
        ip2 = "192.168.1.102"

        # Start warmup for IP1
        self.integration.start_ip_warmup_with_monitoring(ip1)

        # Complete warmup for IP2 (simulate already completed)
        self.warmup_scheduler.start_warmup(ip2)
        # Simulate completion
        progress = self.warmup_scheduler.get_warmup_progress(ip2)
        if progress:
            progress.status = WarmupStatus.COMPLETED
            progress.current_stage = self.warmup_scheduler.config.total_stages
            self.warmup_scheduler._save_warmup_progress(progress)

        # Mock rotation pool with both IPs
        mock_entry1 = Mock()
        mock_entry1.ip_address = ip1
        mock_entry1.status = "active"

        mock_entry2 = Mock()
        mock_entry2.ip_address = ip2
        mock_entry2.status = "active"

        with patch('leadfactory.email.sendgrid_warmup_integration.IPSubuserStatus') as mock_status:
            mock_status.ACTIVE = "active"
            self.rotation_service.get_pool_status.return_value = [mock_entry1, mock_entry2]

            # Get rotation candidates requiring completed warmup
            candidates = self.integration.get_rotation_candidates(
                require_warmup_complete=True
            )

            # Only IP2 should be available (completed warmup)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0], ip2)

        # Test rotation decision for IP in warmup
        should_rotate, reason = self.integration.should_rotate_ip(ip1)
        self.assertFalse(should_rotate)
        self.assertIn("warmup", reason.lower())

        # Test rotation decision for completed warmup IP
        should_rotate, reason = self.integration.should_rotate_ip(ip2)
        self.assertFalse(should_rotate)
        self.assertIn("no rotation needed", reason.lower())

    def test_integration_status_reporting(self):
        """Test integration status reporting."""
        ip1 = "192.168.1.103"
        ip2 = "192.168.1.104"

        # Start warmup for IP1
        self.integration.start_ip_warmup_with_monitoring(ip1)

        # Complete warmup for IP2
        self.warmup_scheduler.start_warmup(ip2)
        # Simulate completion
        progress = self.warmup_scheduler.get_warmup_progress(ip2)
        if progress:
            progress.status = WarmupStatus.COMPLETED
            progress.current_stage = self.warmup_scheduler.config.total_stages
            self.warmup_scheduler._save_warmup_progress(progress)
        self.integration.monitored_ips[ip2] = datetime.now()

        # Get integration status
        status = self.integration.get_integration_status()

        self.assertEqual(status["integration_mode"], "integrated")
        self.assertEqual(status["monitored_ips"], 2)
        self.assertEqual(len(status["warmup_in_progress"]), 1)
        self.assertEqual(len(status["warmup_completed"]), 1)
        self.assertIn(ip1, status["warmup_in_progress"])
        self.assertIn(ip2, status["warmup_completed"])
        self.assertTrue(status["bounce_monitoring_enabled"])
        self.assertTrue(status["rotation_service_enabled"])

    def test_warmup_bounce_threshold_escalation(self):
        """Test bounce threshold escalation during warmup."""
        ip_address = "192.168.1.105"

        # Start warmup
        self.integration.start_ip_warmup_with_monitoring(ip_address)

        # Mock bounce stats
        mock_stats = Mock()
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        # Test warning level (should be safe but logged)
        mock_stats.bounce_rate = 0.07  # Above warning threshold
        is_safe, reason = self.integration.check_warmup_bounce_thresholds(ip_address)
        self.assertTrue(is_safe)
        self.assertIsNone(reason)

        # Test critical level
        mock_stats.bounce_rate = 0.12  # Above critical threshold
        is_safe, reason = self.integration.check_warmup_bounce_thresholds(ip_address)
        self.assertFalse(is_safe)
        self.assertIn("critical", reason.lower())

        # Test block level (should pause warmup)
        mock_stats.bounce_rate = 0.22  # Above block threshold
        is_safe, reason = self.integration.check_warmup_bounce_thresholds(ip_address)
        self.assertFalse(is_safe)
        self.assertIn("block", reason.lower())

        # Verify warmup was paused
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        self.assertEqual(progress.status, WarmupStatus.PAUSED)


class TestIntegrationSetup(unittest.TestCase):
    """Test integration setup functions."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.warmup_db = Path(self.temp_dir) / "test_warmup.db"
        self.bounce_db = Path(self.temp_dir) / "test_bounce.db"

    def test_setup_integrated_email_system_warmup_only(self):
        """Test setting up email system with warmup only."""
        # Mock rotation components as unavailable
        with patch('leadfactory.email.sendgrid_warmup_integration.ROTATION_AVAILABLE', False):
            integration = setup_integrated_email_system(
                warmup_db_path=str(self.warmup_db),
                bounce_db_path=str(self.bounce_db),
            )

            self.assertIsInstance(integration, SendGridWarmupIntegration)
            self.assertIsNotNone(integration.warmup_scheduler)
            self.assertIsNone(integration.bounce_monitor)
            self.assertIsNone(integration.rotation_service)

    @patch('leadfactory.email.sendgrid_warmup_integration.ROTATION_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_integration.BounceRateMonitor')
    @patch('leadfactory.email.sendgrid_warmup_integration.IPRotationService')
    @patch('leadfactory.email.sendgrid_warmup_integration.BounceRateConfig')
    @patch('leadfactory.email.sendgrid_warmup_integration.RotationConfig')
    def test_setup_integrated_email_system_full(
        self,
        mock_rotation_config,
        mock_bounce_config,
        mock_rotation_service,
        mock_bounce_monitor,
    ):
        """Test setting up full integrated email system."""
        integration = setup_integrated_email_system(
            warmup_db_path=str(self.warmup_db),
            bounce_db_path=str(self.bounce_db),
        )

        self.assertIsInstance(integration, SendGridWarmupIntegration)
        self.assertIsNotNone(integration.warmup_scheduler)

        # Verify bounce monitor and rotation service were created
        mock_bounce_monitor.assert_called_once()
        mock_rotation_service.assert_called_once()

    def test_integration_event_logging(self):
        """Test integration event logging."""
        warmup_config = WarmupConfiguration()
        warmup_scheduler = SendGridWarmupScheduler(
            config=warmup_config,
            db_path=str(self.warmup_db),
        )

        integration = SendGridWarmupIntegration(
            warmup_scheduler=warmup_scheduler,
        )

        ip_address = "192.168.1.106"

        # Start warmup (should log event)
        integration.start_ip_warmup_with_monitoring(ip_address, enable_bounce_monitoring=False)

        # Check event was logged
        self.assertEqual(len(integration.integration_events), 1)
        event = integration.integration_events[0]
        self.assertEqual(event["event_type"], "warmup_started")
        self.assertEqual(event["ip_address"], ip_address)
        self.assertIn("timestamp", event)
        self.assertIn("details", event)

        # Complete warmup (should log another event)
        # Simulate completion
        progress = warmup_scheduler.get_warmup_progress(ip_address)
        if progress:
            progress.status = WarmupStatus.COMPLETED
            progress.current_stage = warmup_scheduler.config.total_stages
            warmup_scheduler._save_warmup_progress(progress)
        integration.handle_warmup_completion(ip_address)

        # Check completion event was logged
        self.assertEqual(len(integration.integration_events), 2)
        event = integration.integration_events[1]
        self.assertEqual(event["event_type"], "warmup_completed")
        self.assertEqual(event["ip_address"], ip_address)


if __name__ == "__main__":
    unittest.main()
