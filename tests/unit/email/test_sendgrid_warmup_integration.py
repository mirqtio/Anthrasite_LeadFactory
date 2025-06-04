#!/usr/bin/env python3
"""
Unit tests for SendGrid warmup integration module.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from leadfactory.email.sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupProgress,
    WarmupStage,
    WarmupStatus,
)
from leadfactory.email.sendgrid_warmup_integration import (
    IntegrationMode,
    SendGridWarmupIntegration,
    WarmupIntegrationConfig,
    create_warmup_integration,
    setup_integrated_email_system,
)


class TestWarmupIntegrationConfig(unittest.TestCase):
    """Test warmup integration configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WarmupIntegrationConfig()

        self.assertEqual(config.warmup_warning_threshold, 0.08)
        self.assertEqual(config.warmup_critical_threshold, 0.15)
        self.assertEqual(config.warmup_block_threshold, 0.25)
        self.assertTrue(config.auto_add_to_rotation_pool)
        self.assertEqual(config.rotation_pool_priority, 1)
        self.assertEqual(config.cooldown_after_warmup_hours, 2)
        self.assertTrue(config.pause_warmup_on_critical_bounce)
        self.assertTrue(config.require_warmup_completion_for_rotation)
        self.assertEqual(config.minimum_warmup_days_before_rotation, 7)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = WarmupIntegrationConfig(
            warmup_warning_threshold=0.05,
            warmup_critical_threshold=0.10,
            warmup_block_threshold=0.20,
            auto_add_to_rotation_pool=False,
            rotation_pool_priority=2,
            cooldown_after_warmup_hours=4,
            pause_warmup_on_critical_bounce=False,
            require_warmup_completion_for_rotation=False,
            minimum_warmup_days_before_rotation=14,
        )

        self.assertEqual(config.warmup_warning_threshold, 0.05)
        self.assertEqual(config.warmup_critical_threshold, 0.10)
        self.assertEqual(config.warmup_block_threshold, 0.20)
        self.assertFalse(config.auto_add_to_rotation_pool)
        self.assertEqual(config.rotation_pool_priority, 2)
        self.assertEqual(config.cooldown_after_warmup_hours, 4)
        self.assertFalse(config.pause_warmup_on_critical_bounce)
        self.assertFalse(config.require_warmup_completion_for_rotation)
        self.assertEqual(config.minimum_warmup_days_before_rotation, 14)


class TestSendGridWarmupIntegration(unittest.TestCase):
    """Test SendGrid warmup integration service."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.warmup_db = Path(self.temp_dir) / "test_warmup.db"

        # Create mock warmup scheduler
        self.warmup_scheduler = Mock(spec=SendGridWarmupScheduler)

        # Create mock bounce monitor
        self.bounce_monitor = Mock()
        self.bounce_monitor.get_ip_subuser_stats.return_value = None
        self.bounce_monitor.check_thresholds.return_value = {}

        # Create mock rotation service
        self.rotation_service = Mock()
        self.rotation_service.get_pool_status.return_value = []

        # Create integration config
        self.config = WarmupIntegrationConfig()

        # Create integration instance
        self.integration = SendGridWarmupIntegration(
            warmup_scheduler=self.warmup_scheduler,
            bounce_monitor=self.bounce_monitor,
            rotation_service=self.rotation_service,
            config=self.config,
        )

    def test_integration_initialization(self):
        """Test integration service initialization."""
        self.assertEqual(self.integration.warmup_scheduler, self.warmup_scheduler)
        self.assertEqual(self.integration.bounce_monitor, self.bounce_monitor)
        self.assertEqual(self.integration.rotation_service, self.rotation_service)
        self.assertEqual(self.integration.config, self.config)
        self.assertEqual(len(self.integration.monitored_ips), 0)
        self.assertEqual(len(self.integration.integration_events), 0)

    def test_get_integration_mode_integrated(self):
        """Test integration mode detection with all services."""
        mode = self.integration._get_integration_mode()
        self.assertEqual(mode, IntegrationMode.INTEGRATED)

    def test_get_integration_mode_rotation_only(self):
        """Test integration mode detection with bounce monitor only."""
        integration = SendGridWarmupIntegration(
            warmup_scheduler=self.warmup_scheduler,
            bounce_monitor=self.bounce_monitor,
            rotation_service=None,
        )
        mode = integration._get_integration_mode()
        self.assertEqual(mode, IntegrationMode.ROTATION_ONLY)

    def test_get_integration_mode_warmup_only(self):
        """Test integration mode detection with warmup only."""
        integration = SendGridWarmupIntegration(
            warmup_scheduler=self.warmup_scheduler,
            bounce_monitor=None,
            rotation_service=None,
        )
        mode = integration._get_integration_mode()
        self.assertEqual(mode, IntegrationMode.WARMUP_ONLY)

    def test_start_ip_warmup_with_monitoring_success(self):
        """Test successful IP warmup start with monitoring."""
        ip_address = "192.168.1.1"
        self.warmup_scheduler.start_warmup.return_value = True

        result = self.integration.start_ip_warmup_with_monitoring(ip_address)

        self.assertTrue(result)
        self.warmup_scheduler.start_warmup.assert_called_once_with(ip_address)
        self.assertIn(ip_address, self.integration.monitored_ips)
        self.assertEqual(len(self.integration.integration_events), 1)

        event = self.integration.integration_events[0]
        self.assertEqual(event["event_type"], "warmup_started")
        self.assertEqual(event["ip_address"], ip_address)

    def test_start_ip_warmup_with_monitoring_failure(self):
        """Test failed IP warmup start."""
        ip_address = "192.168.1.1"
        self.warmup_scheduler.start_warmup.return_value = False

        result = self.integration.start_ip_warmup_with_monitoring(ip_address)

        self.assertFalse(result)
        self.warmup_scheduler.start_warmup.assert_called_once_with(ip_address)
        self.assertNotIn(ip_address, self.integration.monitored_ips)
        self.assertEqual(len(self.integration.integration_events), 0)

    def test_check_warmup_bounce_thresholds_no_warmup(self):
        """Test bounce threshold check for IP not in warmup."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock no warmup progress
        self.warmup_scheduler.get_warmup_progress.return_value = None

        # Mock bounce monitor stats
        mock_stats = Mock()
        mock_stats.ip_address = ip_address
        mock_stats.subuser = subuser
        mock_stats.bounce_rate = 0.05
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats
        self.bounce_monitor.check_thresholds.return_value = {}

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(
            ip_address, subuser
        )

        self.assertTrue(is_safe)
        self.assertIsNone(reason)

    def test_check_warmup_bounce_thresholds_in_warmup_safe(self):
        """Test bounce threshold check for IP in warmup - safe levels."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock bounce monitor stats - safe bounce rate
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.05  # Below warning threshold
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(
            ip_address, subuser
        )

        self.assertTrue(is_safe)
        self.assertIsNone(reason)

    def test_check_warmup_bounce_thresholds_in_warmup_warning(self):
        """Test bounce threshold check for IP in warmup - warning level."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock bounce monitor stats - warning level
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.10  # Above warning, below critical
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(
            ip_address, subuser
        )

        self.assertTrue(is_safe)
        self.assertIsNone(reason)

    def test_check_warmup_bounce_thresholds_in_warmup_critical(self):
        """Test bounce threshold check for IP in warmup - critical level."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock bounce monitor stats - critical level
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.18  # Above critical, below block
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(
            ip_address, subuser
        )

        self.assertFalse(is_safe)
        self.assertIn("critical threshold exceeded", reason)

    def test_check_warmup_bounce_thresholds_in_warmup_block(self):
        """Test bounce threshold check for IP in warmup - block level."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock bounce monitor stats - block level
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.30  # Above block threshold
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        is_safe, reason = self.integration.check_warmup_bounce_thresholds(
            ip_address, subuser
        )

        self.assertFalse(is_safe)
        self.assertIn("block threshold exceeded", reason)
        # Should pause warmup
        self.warmup_scheduler.pause_warmup.assert_called_once_with(
            ip_address, "Warmup block threshold exceeded: 0.300"
        )

    def test_handle_warmup_completion_success(self):
        """Test successful warmup completion handling."""
        ip_address = "192.168.1.1"

        # Mock completed warmup
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.COMPLETED
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        result = self.integration.handle_warmup_completion(ip_address)

        self.assertTrue(result)
        self.rotation_service.add_ip_subuser.assert_called_once()

        # Check event logging
        self.assertEqual(len(self.integration.integration_events), 1)
        event = self.integration.integration_events[0]
        self.assertEqual(event["event_type"], "warmup_completed")
        self.assertEqual(event["ip_address"], ip_address)

    def test_handle_warmup_completion_not_completed(self):
        """Test warmup completion handling when warmup not actually completed."""
        ip_address = "192.168.1.1"

        # Mock warmup not completed
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        result = self.integration.handle_warmup_completion(ip_address)

        self.assertFalse(result)
        self.rotation_service.add_ip_subuser.assert_not_called()

    def test_get_rotation_candidates_with_warmup_requirement(self):
        """Test getting rotation candidates with warmup completion requirement."""
        # Mock rotation service pool status
        mock_entry1 = Mock()
        mock_entry1.ip_address = "192.168.1.1"
        mock_entry1.status = Mock()
        mock_entry1.status.ACTIVE = "active"
        mock_entry1.status = "active"

        mock_entry2 = Mock()
        mock_entry2.ip_address = "192.168.1.2"
        mock_entry2.status = "active"

        # Mock the enum comparison
        with patch(
            "leadfactory.email.sendgrid_warmup_integration.IPSubuserStatus"
        ) as mock_status:
            mock_status.ACTIVE = "active"
            self.rotation_service.get_pool_status.return_value = [
                mock_entry1,
                mock_entry2,
            ]

            # Mock warmup progress - first IP completed, second in progress
            def mock_get_progress(ip):
                if ip == "192.168.1.1":
                    progress = Mock()
                    progress.status = WarmupStatus.COMPLETED
                    return progress
                elif ip == "192.168.1.2":
                    progress = Mock()
                    progress.status = WarmupStatus.IN_PROGRESS
                    return progress
                return None

            self.warmup_scheduler.get_warmup_progress.side_effect = mock_get_progress

            candidates = self.integration.get_rotation_candidates(
                require_warmup_complete=True
            )

            # Only the completed warmup IP should be returned
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0], "192.168.1.1")

    def test_should_rotate_ip_in_warmup(self):
        """Test rotation decision for IP in warmup."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock safe bounce thresholds
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.05
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        should_rotate, reason = self.integration.should_rotate_ip(ip_address, subuser)

        self.assertFalse(should_rotate)
        self.assertIn("warmup", reason.lower())

    def test_should_rotate_ip_warmup_threshold_breach(self):
        """Test rotation decision for IP in warmup with threshold breach."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock warmup in progress
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.IN_PROGRESS
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock high bounce rate
        mock_stats = Mock()
        mock_stats.bounce_rate = 0.30  # Above block threshold
        self.bounce_monitor.get_ip_subuser_stats.return_value = mock_stats

        should_rotate, reason = self.integration.should_rotate_ip(ip_address, subuser)

        self.assertTrue(should_rotate)
        self.assertIn("threshold breach", reason.lower())

    def test_should_rotate_ip_completed_warmup_safe(self):
        """Test rotation decision for IP with completed warmup - safe."""
        ip_address = "192.168.1.1"
        subuser = "default"

        # Mock completed warmup
        mock_progress = Mock()
        mock_progress.status = WarmupStatus.COMPLETED
        self.warmup_scheduler.get_warmup_progress.return_value = mock_progress

        # Mock safe bounce thresholds
        self.bounce_monitor.check_thresholds.return_value = {}

        should_rotate, reason = self.integration.should_rotate_ip(ip_address, subuser)

        self.assertFalse(should_rotate)
        self.assertIn("no rotation needed", reason.lower())

    def test_get_integration_status(self):
        """Test getting integration status."""
        # Add some monitored IPs
        self.integration.monitored_ips["192.168.1.1"] = datetime.now()
        self.integration.monitored_ips["192.168.1.2"] = datetime.now()

        # Mock warmup progress
        def mock_get_progress(ip):
            if ip == "192.168.1.1":
                progress = Mock()
                progress.status = WarmupStatus.IN_PROGRESS
                return progress
            elif ip == "192.168.1.2":
                progress = Mock()
                progress.status = WarmupStatus.COMPLETED
                return progress
            return None

        self.warmup_scheduler.get_warmup_progress.side_effect = mock_get_progress

        status = self.integration.get_integration_status()

        self.assertEqual(status["integration_mode"], "integrated")
        self.assertEqual(status["monitored_ips"], 2)
        self.assertEqual(len(status["warmup_in_progress"]), 1)
        self.assertEqual(len(status["warmup_completed"]), 1)
        self.assertTrue(status["bounce_monitoring_enabled"])
        self.assertTrue(status["rotation_service_enabled"])


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def test_create_warmup_integration(self):
        """Test creating warmup integration."""
        warmup_scheduler = Mock(spec=SendGridWarmupScheduler)
        bounce_monitor = Mock()
        rotation_service = Mock()
        config = WarmupIntegrationConfig()

        integration = create_warmup_integration(
            warmup_scheduler=warmup_scheduler,
            bounce_monitor=bounce_monitor,
            rotation_service=rotation_service,
            config=config,
        )

        self.assertIsInstance(integration, SendGridWarmupIntegration)
        self.assertEqual(integration.warmup_scheduler, warmup_scheduler)
        self.assertEqual(integration.bounce_monitor, bounce_monitor)
        self.assertEqual(integration.rotation_service, rotation_service)
        self.assertEqual(integration.config, config)

    @patch("leadfactory.email.sendgrid_warmup_integration.ROTATION_AVAILABLE", True)
    @patch("leadfactory.email.sendgrid_warmup_integration.SendGridWarmupScheduler")
    @patch("leadfactory.email.sendgrid_warmup_integration.BounceRateMonitor")
    @patch("leadfactory.email.sendgrid_warmup_integration.IPRotationService")
    @patch("leadfactory.email.sendgrid_warmup_integration.BounceRateConfig")
    @patch("leadfactory.email.sendgrid_warmup_integration.RotationConfig")
    def test_setup_integrated_email_system(
        self,
        mock_rotation_config,
        mock_bounce_config,
        mock_rotation_service,
        mock_bounce_monitor,
        mock_warmup_scheduler,
    ):
        """Test setting up integrated email system."""
        warmup_db_path = "/tmp/warmup.db"
        bounce_db_path = "/tmp/bounce.db"

        integration = setup_integrated_email_system(
            warmup_db_path=warmup_db_path,
            bounce_db_path=bounce_db_path,
        )

        self.assertIsInstance(integration, SendGridWarmupIntegration)
        mock_warmup_scheduler.assert_called_once_with(db_path=warmup_db_path)
        mock_bounce_monitor.assert_called_once()
        mock_rotation_service.assert_called_once()


if __name__ == "__main__":
    unittest.main()
