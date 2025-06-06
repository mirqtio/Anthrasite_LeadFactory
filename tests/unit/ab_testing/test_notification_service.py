"""Unit tests for A/B Test Notification Service."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.ab_testing.notification_service import ABTestNotificationService
from leadfactory.ab_testing.ab_test_manager import ABTestConfig, TestStatus, TestType


class TestABTestNotificationService(unittest.TestCase):
    """Test A/B Test Notification Service functionality."""

    def setUp(self):
        """Set up test environment."""
        self.notification_service = ABTestNotificationService()
        self.notification_service.ab_manager = Mock()
        self.notification_service.report_generator = Mock()
        self.notification_service.stats_engine = Mock()

    def test_check_for_completed_tests_end_date_reached(self):
        """Test detection of tests that reached end date."""
        # Mock test that should be completed
        past_test = ABTestConfig(
            id="test123",
            name="Test Email Subject",
            description="Test description",
            test_type=TestType.EMAIL_SUBJECT,
            status=TestStatus.ACTIVE,
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow() - timedelta(hours=1),  # Past end date
            target_sample_size=1000,
            significance_threshold=0.05,
            minimum_effect_size=0.1,
            variants=[{"name": "A"}, {"name": "B"}],
            metadata={},
            created_at=datetime.utcnow() - timedelta(days=8),
            updated_at=datetime.utcnow() - timedelta(days=1)
        )

        self.notification_service.ab_manager.get_active_tests.return_value = [past_test]
        self.notification_service.ab_manager.stop_test.return_value = True
        self.notification_service.notification_config = {"auto_report_on_completion": False}

        completed = self.notification_service.check_for_completed_tests()

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0], "test123")
        self.notification_service.ab_manager.stop_test.assert_called_once_with("test123")

    def test_check_for_completed_tests_target_reached(self):
        """Test detection of tests that reached target sample size."""
        # Mock test that reached target sample size
        target_reached_test = ABTestConfig(
            id="test456",
            name="Test Pricing",
            description="Test description",
            test_type=TestType.PRICING,
            status=TestStatus.ACTIVE,
            start_date=datetime.utcnow() - timedelta(days=3),
            end_date=datetime.utcnow() + timedelta(days=4),  # Future end date
            target_sample_size=1000,
            significance_threshold=0.05,
            minimum_effect_size=0.1,
            variants=[{"name": "A"}, {"name": "B"}],
            metadata={},
            created_at=datetime.utcnow() - timedelta(days=4),
            updated_at=datetime.utcnow() - timedelta(days=1)
        )

        # Mock test results showing target reached
        test_results = {
            'total_assignments': 1000,  # Reached target
            'variant_results': {}
        }

        self.notification_service.ab_manager.get_active_tests.return_value = [target_reached_test]
        self.notification_service.ab_manager.get_test_results.return_value = test_results
        self.notification_service.ab_manager.stop_test.return_value = True
        self.notification_service.notification_config = {"auto_report_on_completion": False}

        completed = self.notification_service.check_for_completed_tests()

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0], "test456")

    def test_check_for_significant_results(self):
        """Test detection of statistically significant results."""
        # Mock active test
        active_test = ABTestConfig(
            id="test789",
            name="Test CTA Button",
            description="Test description",
            test_type=TestType.CTA_BUTTON,
            status=TestStatus.ACTIVE,
            start_date=datetime.utcnow() - timedelta(days=5),
            end_date=datetime.utcnow() + timedelta(days=2),
            target_sample_size=1000,
            significance_threshold=0.05,
            minimum_effect_size=0.1,
            variants=[{"name": "A"}, {"name": "B"}],
            metadata={},
            created_at=datetime.utcnow() - timedelta(days=6),
            updated_at=datetime.utcnow() - timedelta(days=1)
        )

        # Mock test results with sufficient sample size
        test_results = {
            'total_assignments': 500,  # Sufficient for analysis
            'variant_results': {}
        }

        # Mock significant statistical results
        stats_results = {
            'p_value': 0.02,  # Significant
            'recommended_variant': 'variant_1',
            'effect_size': 0.25
        }

        self.notification_service.ab_manager.get_active_tests.return_value = [active_test]
        self.notification_service.ab_manager.get_test_results.return_value = test_results
        self.notification_service.stats_engine.analyze_test_results.return_value = stats_results
        self.notification_service.notification_config = {"auto_report_on_significance": False}

        significant = self.notification_service.check_for_significant_results()

        self.assertEqual(len(significant), 1)
        self.assertEqual(significant[0]['test_id'], "test789")
        self.assertEqual(significant[0]['p_value'], 0.02)
        self.assertEqual(significant[0]['recommended_variant'], 'variant_1')

    def test_has_minimum_sample_size(self):
        """Test minimum sample size checking."""
        # Mock test with 2 variants
        test = Mock()
        test.variants = [{"name": "A"}, {"name": "B"}]

        # Test with sufficient sample size
        test_results_sufficient = {'total_assignments': 250}  # 125 per variant > 100
        self.notification_service.ab_manager.get_test_results.return_value = test_results_sufficient

        self.assertTrue(self.notification_service._has_minimum_sample_size(test))

        # Test with insufficient sample size
        test_results_insufficient = {'total_assignments': 150}  # 75 per variant < 100
        self.notification_service.ab_manager.get_test_results.return_value = test_results_insufficient

        self.assertFalse(self.notification_service._has_minimum_sample_size(test))

    def test_should_complete_early(self):
        """Test early completion logic."""
        test = Mock()
        test.target_sample_size = 1000

        # Test reaching target
        test_results_target = {'total_assignments': 1000}
        self.notification_service.ab_manager.get_test_results.return_value = test_results_target

        self.assertTrue(self.notification_service._should_complete_early(test))

        # Test not reaching target
        test_results_not_target = {'total_assignments': 800}
        self.notification_service.ab_manager.get_test_results.return_value = test_results_not_target

        self.assertFalse(self.notification_service._should_complete_early(test))

    def test_get_notification_recipients_test_specific(self):
        """Test getting test-specific notification recipients."""
        test_config = Mock()
        test_config.metadata = {
            'notification_recipients': ['test1@example.com', 'test2@example.com']
        }

        self.notification_service.ab_manager.get_test_config.return_value = test_config

        recipients = self.notification_service._get_notification_recipients("test123")

        self.assertEqual(recipients, ['test1@example.com', 'test2@example.com'])

    def test_get_notification_recipients_default(self):
        """Test getting default notification recipients."""
        test_config = Mock()
        test_config.metadata = {}

        self.notification_service.ab_manager.get_test_config.return_value = test_config
        self.notification_service.notification_config = {
            'default_recipients': ['default@example.com']
        }

        recipients = self.notification_service._get_notification_recipients("test123")

        self.assertEqual(recipients, ['default@example.com'])

    def test_send_significance_alert(self):
        """Test sending significance alert email."""
        # Mock the simple email sending method
        self.notification_service._send_simple_email = Mock()

        significant_result = {
            'test_name': 'Email Subject Test',
            'p_value': 0.02,
            'confidence_level': 95.0,
            'recommended_variant': 'variant_1',
            'effect_size': 0.25
        }

        # Mock recipients
        self.notification_service._get_notification_recipients = Mock(
            return_value=['test@example.com']
        )

        self.notification_service._send_significance_alert("test123", significant_result)

        # Should send email
        self.notification_service._send_simple_email.assert_called_once()

        # Check email content
        call_args = self.notification_service._send_simple_email.call_args
        to_email = call_args[0][0]
        subject = call_args[0][1]
        body = call_args[0][2]

        self.assertEqual(to_email, 'test@example.com')
        self.assertIn("Significant Results Detected", subject)
        self.assertIn("0.02", body)  # P-value
        self.assertIn("variant_1", body)  # Recommended variant

    def test_run_periodic_checks(self):
        """Test running periodic checks."""
        # Mock completed tests
        self.notification_service.check_for_completed_tests = Mock(return_value=['test1', 'test2'])

        # Mock significant tests
        self.notification_service.check_for_significant_results = Mock(return_value=[
            {'test_id': 'test3', 'p_value': 0.01}
        ])

        summary = self.notification_service.run_periodic_checks()

        self.assertEqual(summary['completed_tests'], 2)
        self.assertEqual(summary['significant_tests'], 1)
        self.assertIn('timestamp', summary)

    def test_get_notification_status(self):
        """Test getting notification status for a test."""
        test_config = Mock()
        test_config.id = "test123"
        test_config.name = "Test Name"
        test_config.status = TestStatus.ACTIVE
        test_config.significance_threshold = 0.05
        test_config.target_sample_size = 1000

        test_results = {'total_assignments': 600}
        stats_results = {'p_value': 0.08}

        self.notification_service.ab_manager.get_test_config.return_value = test_config
        self.notification_service.ab_manager.get_test_results.return_value = test_results
        self.notification_service.stats_engine.analyze_test_results.return_value = stats_results
        self.notification_service._get_notification_recipients = Mock(return_value=['test@example.com'])
        self.notification_service.notification_config = {
            'auto_report_on_completion': True,
            'auto_report_on_significance': True
        }

        status = self.notification_service.get_notification_status("test123")

        self.assertEqual(status['test_id'], "test123")
        self.assertEqual(status['test_name'], "Test Name")
        self.assertEqual(status['status'], "active")
        self.assertEqual(status['current_p_value'], 0.08)
        self.assertFalse(status['is_significant'])
        self.assertEqual(status['total_participants'], 600)
        self.assertEqual(status['completion_progress'], 0.6)

    def test_schedule_test_completion_check(self):
        """Test scheduling completion check."""
        check_time = datetime.utcnow() + timedelta(days=1)
        recipients = ['test@example.com']

        # Should not raise exception
        self.notification_service.schedule_test_completion_check(
            "test123",
            check_time,
            recipients
        )

    def test_error_handling(self):
        """Test error handling in notification service."""
        # Mock error in ab_manager
        self.notification_service.ab_manager.get_active_tests.side_effect = Exception("Database error")

        # Should handle gracefully
        completed = self.notification_service.check_for_completed_tests()
        self.assertEqual(len(completed), 0)

        significant = self.notification_service.check_for_significant_results()
        self.assertEqual(len(significant), 0)


if __name__ == "__main__":
    unittest.main()
