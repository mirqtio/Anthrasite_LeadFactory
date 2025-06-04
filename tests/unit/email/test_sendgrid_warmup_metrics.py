"""
Unit tests for SendGrid warmup metrics collection and reporting.
"""

import unittest
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock

from leadfactory.email.sendgrid_warmup_metrics import (
    SendGridWarmupMetricsCollector, create_warmup_metrics_collector, record_warmup_event
)
from leadfactory.email.sendgrid_warmup import WarmupStatus, WarmupProgress


class TestSendGridWarmupMetricsCollector(unittest.TestCase):
    """Test SendGrid warmup metrics collector functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_scheduler = Mock()
        self.mock_integration = Mock()
        self.collector = SendGridWarmupMetricsCollector(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration
        )

    def test_collector_initialization(self):
        """Test metrics collector initialization."""
        collector = SendGridWarmupMetricsCollector()
        self.assertIsNone(collector.warmup_scheduler)
        self.assertIsNone(collector.integration_service)

        collector_with_services = SendGridWarmupMetricsCollector(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration
        )
        self.assertEqual(collector_with_services.warmup_scheduler, self.mock_scheduler)
        self.assertEqual(collector_with_services.integration_service, self.mock_integration)

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_STARTED')
    def test_record_warmup_started(self, mock_metric):
        """Test recording warmup start events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_warmup_started("192.168.1.1")

        mock_metric.labels.assert_called_once_with(ip_address="192.168.1.1")
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_COMPLETED')
    def test_record_warmup_completed(self, mock_metric):
        """Test recording warmup completion events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_warmup_completed("192.168.1.1", 14)

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            duration_days="14"
        )
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_PAUSED')
    def test_record_warmup_paused(self, mock_metric):
        """Test recording warmup pause events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_warmup_paused("192.168.1.1", "High bounce rate")

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            reason="High bounce rate"
        )
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_RESUMED')
    def test_record_warmup_resumed(self, mock_metric):
        """Test recording warmup resume events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_warmup_resumed("192.168.1.1")

        mock_metric.labels.assert_called_once_with(ip_address="192.168.1.1")
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_STAGE_ADVANCED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_STAGE_COMPLETION_TIME')
    def test_record_stage_advancement(self, mock_time_metric, mock_stage_metric):
        """Test recording stage advancement with timing."""
        mock_stage_labels = Mock()
        mock_stage_metric.labels.return_value = mock_stage_labels

        mock_time_labels = Mock()
        mock_time_metric.labels.return_value = mock_time_labels

        self.collector.record_stage_advancement("192.168.1.1", 2, 3, 86400.0)

        # Check stage advancement metric
        mock_stage_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            from_stage="2",
            to_stage="3"
        )
        mock_stage_labels.inc.assert_called_once()

        # Check timing metric
        mock_time_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            stage="2"
        )
        mock_time_labels.observe.assert_called_once_with(86400.0)

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_EMAILS_SENT')
    def test_record_email_sent(self, mock_metric):
        """Test recording email sent during warmup."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_email_sent("192.168.1.1", 3, "success")

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            stage="3",
            status="success"
        )
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_DAILY_LIMIT_UTILIZATION')
    def test_update_daily_limit_utilization(self, mock_metric):
        """Test updating daily limit utilization gauge."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.update_daily_limit_utilization("192.168.1.1", 3, 150, 300)

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            stage="3"
        )
        mock_labels.set.assert_called_once_with(50.0)  # 150/300 * 100

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_DELIVERABILITY_RATE')
    def test_update_deliverability_rate(self, mock_metric):
        """Test updating deliverability rate gauge."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.update_deliverability_rate("192.168.1.1", 3, 0.95)

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            stage="3"
        )
        mock_labels.set.assert_called_once_with(0.95)

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_REPUTATION_SCORE')
    def test_update_reputation_score(self, mock_metric):
        """Test updating IP reputation score gauge."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.update_reputation_score("192.168.1.1", 85.5)

        mock_metric.labels.assert_called_once_with(ip_address="192.168.1.1")
        mock_labels.set.assert_called_once_with(85.5)

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_THRESHOLD_BREACHES')
    def test_record_threshold_breach(self, mock_metric):
        """Test recording threshold breach events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_threshold_breach("192.168.1.1", "bounce_rate", "critical")

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            threshold_type="bounce_rate",
            severity="critical"
        )
        mock_labels.inc.assert_called_once()

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_INTEGRATION_EVENTS')
    def test_record_integration_event(self, mock_metric):
        """Test recording integration events."""
        mock_labels = Mock()
        mock_metric.labels.return_value = mock_labels

        self.collector.record_integration_event("192.168.1.1", "rotation_triggered", "ip_rotation")

        mock_metric.labels.assert_called_once_with(
            ip_address="192.168.1.1",
            event_type="rotation_triggered",
            system="ip_rotation"
        )
        mock_labels.inc.assert_called_once()

    def test_collect_all_metrics_no_scheduler(self):
        """Test metrics collection without scheduler."""
        collector = SendGridWarmupMetricsCollector()
        metrics = collector.collect_all_metrics()
        self.assertIn("error", metrics)
        self.assertEqual(metrics["error"], "Warmup scheduler not available")

    def test_collect_all_metrics_success(self):
        """Test successful comprehensive metrics collection."""
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
            last_updated=datetime.now()
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
            last_updated=datetime.now()
        )

        self.mock_scheduler.get_warmup_progress.side_effect = [progress1, progress2]

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.side_effect = [200, 1000]

        # Mock integration service rates
        self.mock_integration.get_current_rates.side_effect = [
            {"bounce_rate": 0.02, "spam_rate": 0.001},
            {"bounce_rate": 0.01, "spam_rate": 0.0005}
        ]

        metrics = self.collector.collect_all_metrics()

        # Verify structure
        self.assertIn("timestamp", metrics)
        self.assertIn("warmup_metrics", metrics)
        self.assertIn("system_health", metrics)

        # Verify system health
        health = metrics["system_health"]
        self.assertEqual(health["total_ips"], 2)
        self.assertEqual(health["active_warmups"], 1)
        self.assertEqual(health["completed_warmups"], 1)
        self.assertEqual(health["paused_warmups"], 0)

        # Verify IP metrics
        ip1_metrics = metrics["warmup_metrics"]["192.168.1.1"]
        self.assertEqual(ip1_metrics["status"], "in_progress")
        self.assertEqual(ip1_metrics["stage"], 3)
        self.assertEqual(ip1_metrics["daily_sent"], 150)
        self.assertEqual(ip1_metrics["daily_limit"], 200)
        self.assertEqual(ip1_metrics["bounce_rate"], 0.02)

        ip2_metrics = metrics["warmup_metrics"]["192.168.1.2"]
        self.assertEqual(ip2_metrics["status"], "completed")
        self.assertEqual(ip2_metrics["stage"], 7)
        self.assertEqual(ip2_metrics["daily_sent"], 500)
        self.assertEqual(ip2_metrics["daily_limit"], 1000)

    def test_collect_all_metrics_integration_error(self):
        """Test metrics collection with integration service error."""
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
            last_updated=datetime.now()
        )
        self.mock_scheduler.get_warmup_progress.return_value = progress

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.return_value = 200

        # Integration service raises exception
        self.mock_integration.get_current_rates.side_effect = Exception("API error")

        metrics = self.collector.collect_all_metrics()

        # Should still collect basic metrics
        self.assertIn("warmup_metrics", metrics)
        self.assertIn("192.168.1.1", metrics["warmup_metrics"])

        # Should not have integration metrics
        ip_metrics = metrics["warmup_metrics"]["192.168.1.1"]
        self.assertNotIn("bounce_rate", ip_metrics)
        self.assertNotIn("spam_rate", ip_metrics)

    def test_generate_metrics_report(self):
        """Test formatted metrics report generation."""
        # Setup mock data
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
            last_updated=datetime.now()
        )
        self.mock_scheduler.get_warmup_progress.return_value = progress

        # Mock daily limits
        self.mock_scheduler.get_current_daily_limit.return_value = 200

        self.mock_integration.get_current_rates.return_value = {
            "bounce_rate": 0.02, "spam_rate": 0.001
        }

        report = self.collector.generate_metrics_report()

        # Verify report content
        self.assertIn("SendGrid Warmup Metrics Report", report)
        self.assertIn("System Health:", report)
        self.assertIn("Total IPs: 1", report)
        self.assertIn("Active Warmups: 1", report)
        self.assertIn("IP Details:", report)
        self.assertIn("192.168.1.1:", report)
        self.assertIn("Status: in_progress", report)
        self.assertIn("Stage: 3", report)
        self.assertIn("Daily Usage: 150", report)
        self.assertIn("Bounce Rate: 0.020", report)
        self.assertIn("Spam Rate: 0.001", report)

    def test_generate_metrics_report_error(self):
        """Test metrics report generation with error."""
        collector = SendGridWarmupMetricsCollector()
        report = collector.generate_metrics_report()
        self.assertIn("Error generating metrics report", report)

    def test_create_warmup_metrics_collector_convenience(self):
        """Test convenience function for creating metrics collector."""
        collector = create_warmup_metrics_collector(
            warmup_scheduler=self.mock_scheduler,
            integration_service=self.mock_integration
        )

        self.assertIsInstance(collector, SendGridWarmupMetricsCollector)
        self.assertEqual(collector.warmup_scheduler, self.mock_scheduler)
        self.assertEqual(collector.integration_service, self.mock_integration)

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', True)
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_STARTED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_COMPLETED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_PAUSED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_RESUMED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_STAGE_ADVANCED')
    @patch('leadfactory.email.sendgrid_warmup_metrics.WARMUP_THRESHOLD_BREACHES')
    def test_record_warmup_event_convenience(self, mock_threshold, mock_stage, mock_resumed,
                                           mock_paused, mock_completed, mock_started):
        """Test convenience function for recording warmup events."""
        # Mock labels for all metrics
        for mock_metric in [mock_started, mock_completed, mock_paused, mock_resumed,
                           mock_stage, mock_threshold]:
            mock_labels = Mock()
            mock_metric.labels.return_value = mock_labels

        # Test different event types
        record_warmup_event("started", "192.168.1.1")
        mock_started.labels.assert_called_with(ip_address="192.168.1.1")

        record_warmup_event("completed", "192.168.1.1", duration_days=14)
        mock_completed.labels.assert_called_with(ip_address="192.168.1.1", duration_days="14")

        record_warmup_event("paused", "192.168.1.1", reason="High bounce rate")
        mock_paused.labels.assert_called_with(ip_address="192.168.1.1", reason="High bounce rate")

        record_warmup_event("resumed", "192.168.1.1")
        mock_resumed.labels.assert_called_with(ip_address="192.168.1.1")

        record_warmup_event("stage_advanced", "192.168.1.1", from_stage=2, to_stage=3)
        mock_stage.labels.assert_called_with(ip_address="192.168.1.1", from_stage="2", to_stage="3")

        record_warmup_event("threshold_breach", "192.168.1.1",
                           threshold_type="bounce_rate", severity="critical")
        mock_threshold.labels.assert_called_with(
            ip_address="192.168.1.1", threshold_type="bounce_rate", severity="critical"
        )

    @patch('leadfactory.email.sendgrid_warmup_metrics.METRICS_AVAILABLE', False)
    def test_record_warmup_event_no_metrics(self):
        """Test convenience function when metrics not available."""
        # Should not raise exception
        record_warmup_event("started", "192.168.1.1")

    def test_collect_all_metrics_exception_handling(self):
        """Test exception handling in metrics collection."""
        self.mock_scheduler.get_all_warmup_ips.side_effect = Exception("Database error")

        metrics = self.collector.collect_all_metrics()
        self.assertIn("error", metrics)
        self.assertIn("Database error", metrics["error"])


if __name__ == "__main__":
    unittest.main()
