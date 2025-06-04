"""
Unit tests for SendGrid warmup dashboard and monitoring.
"""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from leadfactory.email.sendgrid_warmup import WarmupProgress, WarmupStatus
from leadfactory.email.sendgrid_warmup_dashboard import (
    SendGridWarmupDashboard,
    create_warmup_dashboard,
)


class TestSendGridWarmupDashboard(unittest.TestCase):
    """Test SendGrid warmup dashboard functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_scheduler = Mock()
        self.mock_integration = Mock()
        self.dashboard = SendGridWarmupDashboard(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration,
        )

    def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        dashboard = SendGridWarmupDashboard()
        self.assertIsNone(dashboard.warmup_scheduler)
        self.assertIsNone(dashboard.integration_service)

        dashboard_with_services = SendGridWarmupDashboard(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration,
        )
        self.assertEqual(dashboard_with_services.warmup_scheduler, self.mock_scheduler)
        self.assertEqual(
            dashboard_with_services.integration_service, self.mock_integration
        )

    def test_get_warmup_metrics_no_scheduler(self):
        """Test metrics collection without scheduler."""
        dashboard = SendGridWarmupDashboard()
        metrics = dashboard.get_warmup_metrics()
        self.assertIn("error", metrics)
        self.assertEqual(metrics["error"], "Warmup scheduler not available")

    def test_get_warmup_metrics_success(self):
        """Test successful metrics collection."""
        # Mock warmup IPs and progress
        test_ips = ["192.168.1.1", "192.168.1.2"]
        self.mock_scheduler.get_all_warmup_ips.return_value = test_ips

        # Create mock progress objects
        progress1 = WarmupProgress(
            ip_address="192.168.1.1",
            status=WarmupStatus.IN_PROGRESS,
            current_stage=3,
            start_date=date.today() - timedelta(days=5),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            daily_sent_count=150,
            total_sent_count=750,
            last_updated=datetime.now(),
        )
        progress2 = WarmupProgress(
            ip_address="192.168.1.2",
            status=WarmupStatus.COMPLETED,
            current_stage=7,
            start_date=date.today() - timedelta(days=14),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            daily_sent_count=500,
            total_sent_count=5000,
            last_updated=datetime.now(),
        )

        self.mock_scheduler.get_warmup_progress.side_effect = [progress1, progress2]

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.side_effect = [200, 1000]

        # Mock integration service rates
        self.mock_integration.get_current_rates.side_effect = [
            {"bounce_rate": 0.02, "spam_rate": 0.001},
            {"bounce_rate": 0.01, "spam_rate": 0.0005},
        ]

        metrics = self.dashboard.get_warmup_metrics()

        # Verify structure
        self.assertIn("timestamp", metrics)
        self.assertIn("ips", metrics)
        self.assertIn("summary", metrics)

        # Verify summary counts
        summary = metrics["summary"]
        self.assertEqual(summary["total_ips"], 2)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["paused"], 0)

        # Verify IP metrics
        ip1_metrics = metrics["ips"]["192.168.1.1"]
        self.assertEqual(ip1_metrics["status"], "in_progress")
        self.assertEqual(ip1_metrics["stage"], 3)
        self.assertEqual(ip1_metrics["daily_sent"], 150)
        self.assertEqual(ip1_metrics["daily_limit"], 200)
        self.assertEqual(ip1_metrics["daily_remaining"], 50)
        self.assertEqual(ip1_metrics["bounce_rate"], 0.02)

        ip2_metrics = metrics["ips"]["192.168.1.2"]
        self.assertEqual(ip2_metrics["status"], "completed")
        self.assertEqual(ip2_metrics["stage"], 7)
        self.assertEqual(ip2_metrics["daily_sent"], 500)
        self.assertEqual(ip2_metrics["daily_limit"], 1000)

    def test_calculate_progress_percent(self):
        """Test progress percentage calculation."""
        # Test basic progress calculation
        progress = Mock()
        progress.current_stage = 3
        progress.total_stages = 7
        progress.stage_start_date = None

        percent = self.dashboard._calculate_progress_percent(progress)
        expected = ((3 - 1) / 7) * 100  # 28.57%
        self.assertAlmostEqual(percent, expected, places=1)

        # Test with stage progress
        progress.stage_start_date = datetime.now() - timedelta(days=1)
        progress.stage_duration_days = 2

        percent = self.dashboard._calculate_progress_percent(progress)
        # Should be base progress + 50% of one stage
        stage_percent = (0.5 / 7) * 100
        expected = ((3 - 1) / 7) * 100 + stage_percent
        self.assertAlmostEqual(percent, expected, places=1)

    def test_generate_html_dashboard_error(self):
        """Test HTML generation with error."""
        dashboard = SendGridWarmupDashboard()
        html = dashboard.generate_html_dashboard()
        self.assertIn("Dashboard Error", html)
        self.assertIn("Warmup scheduler not available", html)

    def test_generate_html_dashboard_success(self):
        """Test successful HTML dashboard generation."""
        # Setup mock data
        test_ips = ["192.168.1.1"]
        self.mock_scheduler.get_all_warmup_ips.return_value = test_ips

        progress = WarmupProgress(
            ip_address="192.168.1.1",
            status=WarmupStatus.IN_PROGRESS,
            current_stage=2,
            start_date=date.today() - timedelta(days=3),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            daily_sent_count=100,
            total_sent_count=300,
            last_updated=datetime.now(),
        )
        self.mock_scheduler.get_warmup_progress.return_value = progress

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.return_value = 200

        self.mock_integration.get_current_rates.return_value = {
            "bounce_rate": 0.03,
            "spam_rate": 0.001,
        }

        html = self.dashboard.generate_html_dashboard()

        # Verify HTML structure
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("SendGrid Warmup Dashboard", html)
        self.assertIn("192.168.1.1", html)
        self.assertIn("Stage 2", html)
        self.assertIn("100", html)  # daily sent

    def test_generate_html_dashboard_with_alerts(self):
        """Test HTML generation with alert conditions."""
        test_ips = ["192.168.1.1"]
        self.mock_scheduler.get_all_warmup_ips.return_value = test_ips

        progress = WarmupProgress(
            ip_address="192.168.1.1",
            status=WarmupStatus.PAUSED,
            current_stage=2,
            start_date=date.today() - timedelta(days=3),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            daily_sent_count=100,
            total_sent_count=300,
            is_paused=True,
            pause_reason="High bounce rate",
            last_updated=datetime.now(),
        )
        self.mock_scheduler.get_warmup_progress.return_value = progress

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.return_value = 200

        # High bounce rate to trigger alert
        self.mock_integration.get_current_rates.return_value = {
            "bounce_rate": 0.08,
            "spam_rate": 0.002,
        }

        html = self.dashboard.generate_html_dashboard()

        # Verify alerts are shown
        self.assertIn("High bounce rate", html)
        self.assertIn("High spam rate", html)
        self.assertIn("Paused: High bounce rate", html)
        self.assertIn("status paused", html)

    @patch("leadfactory.email.sendgrid_warmup_dashboard.METRICS_AVAILABLE", True)
    @patch("leadfactory.email.sendgrid_warmup_dashboard.WARMUP_PROGRESS")
    @patch("leadfactory.email.sendgrid_warmup_dashboard.WARMUP_STATUS_GAUGE")
    def test_update_prometheus_metrics(self, mock_status_gauge, mock_progress):
        """Test Prometheus metrics updates."""
        test_ips = ["192.168.1.1"]
        self.mock_scheduler.get_all_warmup_ips.return_value = test_ips

        progress = WarmupProgress(
            ip_address="192.168.1.1",
            status=WarmupStatus.IN_PROGRESS,
            current_stage=3,
            start_date=date.today() - timedelta(days=5),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            daily_sent_count=150,
            total_sent_count=750,
            last_updated=datetime.now(),
        )
        self.mock_scheduler.get_warmup_progress.return_value = progress

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.return_value = 200

        self.mock_integration.get_current_rates.return_value = {
            "bounce_rate": 0.02,
            "spam_rate": 0.001,
        }

        # Mock the labels method chain
        mock_progress_labels = Mock()
        mock_progress.labels.return_value = mock_progress_labels

        mock_status_labels = Mock()
        mock_status_gauge.labels.return_value = mock_status_labels

        self.dashboard.update_prometheus_metrics()

        # Verify metrics were called
        mock_progress.labels.assert_called()
        mock_status_gauge.labels.assert_called()

    def test_get_alert_conditions_no_scheduler(self):
        """Test alert conditions without scheduler."""
        dashboard = SendGridWarmupDashboard()
        alerts = dashboard.get_alert_conditions()
        self.assertEqual(alerts, [])

    def test_get_alert_conditions_with_issues(self):
        """Test alert detection with various issues."""
        test_ips = ["192.168.1.1", "192.168.1.2"]
        self.mock_scheduler.get_all_warmup_ips.return_value = test_ips

        # IP 1: Paused warmup
        progress1 = WarmupProgress(
            ip_address="192.168.1.1",
            status=WarmupStatus.PAUSED,
            current_stage=2,
            start_date=date.today() - timedelta(days=3),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            is_paused=True,
            pause_reason="High bounce rate",
            last_updated=datetime.now(),
        )

        # IP 2: Stalled warmup (old last_updated)
        progress2 = WarmupProgress(
            ip_address="192.168.1.2",
            status=WarmupStatus.IN_PROGRESS,
            current_stage=3,
            start_date=date.today() - timedelta(days=5),
            current_date=date.today(),
            stage_start_date=date.today() - timedelta(days=1),
            last_updated=datetime.now() - timedelta(hours=30),
        )

        self.mock_scheduler.get_warmup_progress.side_effect = [progress1, progress2]

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.side_effect = [200, 1000]

        # High rates for IP 1
        self.mock_integration.get_current_rates.side_effect = [
            {"bounce_rate": 0.08, "spam_rate": 0.002},
            {"bounce_rate": 0.01, "spam_rate": 0.0005},
        ]

        alerts = self.dashboard.get_alert_conditions()

        # Should have multiple alerts
        self.assertGreater(len(alerts), 0)

        # Check for paused alert
        paused_alerts = [a for a in alerts if "paused" in a["message"].lower()]
        self.assertGreater(len(paused_alerts), 0)

        # Check for stalled alert
        stalled_alerts = [a for a in alerts if "stalled" in a["message"].lower()]
        self.assertGreater(len(stalled_alerts), 0)

        # Check for high bounce rate alert
        bounce_alerts = [a for a in alerts if "bounce rate" in a["message"].lower()]
        self.assertGreater(len(bounce_alerts), 0)

    def test_create_warmup_dashboard_convenience(self):
        """Test convenience function for creating dashboard."""
        dashboard = create_warmup_dashboard(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration,
        )

        self.assertIsInstance(dashboard, SendGridWarmupDashboard)
        self.assertEqual(dashboard.warmup_scheduler, self.mock_scheduler)
        self.assertEqual(dashboard.integration_service, self.mock_integration)

    def test_get_warmup_metrics_exception_handling(self):
        """Test exception handling in metrics collection."""
        self.mock_scheduler.get_all_warmup_ips.side_effect = Exception("Database error")

        metrics = self.dashboard.get_warmup_metrics()
        self.assertIn("error", metrics)
        self.assertIn("Database error", metrics["error"])

    def test_update_prometheus_metrics_exception_handling(self):
        """Test exception handling in Prometheus metrics update."""
        self.mock_scheduler.get_all_warmup_ips.side_effect = Exception(
            "Connection error"
        )

        # Should not raise exception
        self.dashboard.update_prometheus_metrics()

    def test_get_alert_conditions_exception_handling(self):
        """Test exception handling in alert condition checking."""
        self.mock_scheduler.get_all_warmup_ips.side_effect = Exception("Service error")

        alerts = self.dashboard.get_alert_conditions()

        # Should return error alert
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "error")
        self.assertIn("Service error", alerts[0]["message"])


if __name__ == "__main__":
    unittest.main()
