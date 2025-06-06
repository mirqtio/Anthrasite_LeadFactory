"""Integration tests for complete A/B testing workflow."""

import unittest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.ab_testing.ab_test_manager import ABTestManager, TestType, TestStatus
from leadfactory.ab_testing.report_generator import ABTestReportGenerator
from leadfactory.ab_testing.notification_service import ABTestNotificationService
from leadfactory.ab_testing.statistical_engine import StatisticalEngine


class TestABTestingWorkflow(unittest.TestCase):
    """Integration tests for complete A/B testing workflow."""

    def setUp(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ab.db")

        # Initialize services with test database
        self.ab_manager = ABTestManager(db_path=self.db_path)
        self.stats_engine = StatisticalEngine()
        self.notification_service = ABTestNotificationService()
        self.notification_service.ab_manager = self.ab_manager
        self.notification_service.stats_engine = self.stats_engine

        # Mock email services to avoid sending real emails
        self.notification_service.notification_config = {
            "auto_report_on_completion": False,
            "auto_report_on_significance": False,
            "default_recipients": ["test@example.com"]
        }

    def tearDown(self):
        """Clean up test environment."""
        try:
            os.remove(self.db_path)
            os.rmdir(self.temp_dir)
        except (OSError, FileNotFoundError):
            pass

    def test_complete_ab_test_lifecycle(self):
        """Test complete A/B test lifecycle from creation to completion."""
        # Step 1: Create test
        test_id = self.ab_manager.create_test(
            name="Email Subject Test",
            description="Testing different email subjects for better open rates",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[
                {
                    "name": "Control",
                    "subject": "Your monthly report is ready",
                    "weight": 0.5
                },
                {
                    "name": "Treatment",
                    "subject": "🚀 Your amazing monthly insights inside!",
                    "weight": 0.5
                }
            ],
            target_sample_size=1000,
            significance_threshold=0.05,
            end_date=datetime.utcnow() + timedelta(days=7)
        )

        self.assertIsNotNone(test_id)

        # Step 2: Start test
        success = self.ab_manager.start_test(test_id)
        self.assertTrue(success)

        # Verify test is active
        test_config = self.ab_manager.get_test_config(test_id)
        self.assertEqual(test_config.status, TestStatus.ACTIVE)

        # Step 3: Simulate user assignments and conversions
        # Assign users to variants
        user_assignments = {}
        for user_id in range(100):  # Simulate 100 users
            variant = self.ab_manager.assign_user_to_variant(f"user_{user_id}", test_id)
            user_assignments[f"user_{user_id}"] = variant

        # Record conversions (treatment performs better)
        conversion_count = 0
        for user_id, variant in user_assignments.items():
            # Treatment has 30% open rate, control has 25%
            if variant == "variant_0":  # Control
                if conversion_count % 4 == 0:  # 25% rate
                    self.ab_manager.record_conversion(
                        test_id, user_id, "email_open", metadata={"variant": "control"}
                    )
            else:  # Treatment
                if conversion_count % 10 < 3:  # 30% rate
                    self.ab_manager.record_conversion(
                        test_id, user_id, "email_open", metadata={"variant": "treatment"}
                    )
            conversion_count += 1

        # Step 4: Get test results
        test_results = self.ab_manager.get_test_results(test_id)

        # Verify results structure
        self.assertEqual(test_results['test_id'], test_id)
        self.assertEqual(test_results['total_assignments'], 100)
        self.assertIn('variant_results', test_results)
        self.assertEqual(len(test_results['variant_results']), 2)

        # Step 5: Run statistical analysis
        stats_results = self.stats_engine.analyze_test_results(test_results)

        # Verify statistical analysis
        self.assertIn('p_value', stats_results)
        self.assertIn('effect_size', stats_results)
        self.assertIn('statistical_power', stats_results)

        # Step 6: Check notification service functionality
        # Simulate test with insufficient sample for significance
        status = self.notification_service.get_notification_status(test_id)

        self.assertEqual(status['test_id'], test_id)
        self.assertEqual(status['total_participants'], 100)
        self.assertFalse(status['is_significant'])  # Small sample unlikely to be significant

        # Step 7: Complete test manually
        success = self.ab_manager.stop_test(test_id)
        self.assertTrue(success)

        # Verify test is completed
        test_config = self.ab_manager.get_test_config(test_id)
        self.assertEqual(test_config.status, TestStatus.COMPLETED)

    def test_statistical_significance_detection(self):
        """Test detection of statistical significance with larger sample."""
        # Create test with larger sample size
        test_id = self.ab_manager.create_test(
            name="CTA Button Test",
            description="Testing button colors",
            test_type=TestType.CTA_BUTTON,
            variants=[
                {"name": "Blue Button", "color": "blue", "weight": 0.5},
                {"name": "Red Button", "color": "red", "weight": 0.5}
            ],
            target_sample_size=2000,
            significance_threshold=0.05
        )

        self.ab_manager.start_test(test_id)

        # Simulate larger sample with clear difference
        for user_id in range(500):  # 500 users per variant
            # Assign to control (blue)
            self.ab_manager.assign_user_to_variant(f"user_blue_{user_id}", test_id)
            # Assign to treatment (red)
            self.ab_manager.assign_user_to_variant(f"user_red_{user_id}", test_id)

            # Record conversions with significant difference
            # Blue button: 20% conversion rate
            if user_id % 5 == 0:
                self.ab_manager.record_conversion(
                    test_id, f"user_blue_{user_id}", "click"
                )

            # Red button: 30% conversion rate (significant improvement)
            if user_id % 10 < 3:
                self.ab_manager.record_conversion(
                    test_id, f"user_red_{user_id}", "click"
                )

        # Check for significance
        test_results = self.ab_manager.get_test_results(test_id)
        stats_results = self.stats_engine.analyze_test_results(test_results)

        # With clear difference and sufficient sample, should detect significance
        self.assertLess(stats_results.get('p_value', 1.0), 0.05)
        self.assertGreater(abs(stats_results.get('effect_size', 0.0)), 0.2)

    def test_automatic_completion_detection(self):
        """Test automatic completion detection."""
        # Create test with past end date
        past_date = datetime.utcnow() - timedelta(hours=1)
        test_id = self.ab_manager.create_test(
            name="Past End Date Test",
            description="Test that should auto-complete",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[
                {"name": "A", "subject": "Subject A"},
                {"name": "B", "subject": "Subject B"}
            ],
            end_date=past_date
        )

        self.ab_manager.start_test(test_id)

        # Check for completion
        completed_tests = self.notification_service.check_for_completed_tests()

        self.assertIn(test_id, completed_tests)

        # Verify test was stopped
        test_config = self.ab_manager.get_test_config(test_id)
        self.assertEqual(test_config.status, TestStatus.COMPLETED)

    def test_target_sample_size_completion(self):
        """Test completion when target sample size is reached."""
        test_id = self.ab_manager.create_test(
            name="Target Size Test",
            description="Test that completes when target reached",
            test_type=TestType.PRICING,
            variants=[
                {"name": "Price A", "price": 9.99},
                {"name": "Price B", "price": 14.99}
            ],
            target_sample_size=50,  # Small target for testing
            end_date=datetime.utcnow() + timedelta(days=30)  # Future date
        )

        self.ab_manager.start_test(test_id)

        # Assign enough users to reach target
        for user_id in range(50):
            self.ab_manager.assign_user_to_variant(f"user_{user_id}", test_id)

        # Check for completion
        completed_tests = self.notification_service.check_for_completed_tests()

        self.assertIn(test_id, completed_tests)

    @patch('leadfactory.ab_testing.report_generator.SimpleDocTemplate')
    def test_report_generation_integration(self, mock_doc):
        """Test report generation integration."""
        # Mock PDF generation
        mock_doc_instance = Mock()
        mock_doc.return_value = mock_doc_instance

        # Create and complete a test
        test_id = self.ab_manager.create_test(
            name="Report Test",
            description="Test for report generation",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[
                {"name": "Subject A", "subject": "Original"},
                {"name": "Subject B", "subject": "New"}
            ],
            target_sample_size=100
        )

        self.ab_manager.start_test(test_id)

        # Add some data
        for user_id in range(20):
            variant = self.ab_manager.assign_user_to_variant(f"user_{user_id}", test_id)
            if user_id % 3 == 0:  # Some conversions
                self.ab_manager.record_conversion(test_id, f"user_{user_id}", "email_open")

        self.ab_manager.stop_test(test_id)

        # Initialize report generator with mocked dependencies
        report_generator = ABTestReportGenerator()
        report_generator.ab_manager = self.ab_manager
        report_generator.stats_engine = self.stats_engine
        report_generator._send_report_email_simple = Mock()

        # Generate report
        with patch('io.BytesIO') as mock_buffer:
            mock_buffer.return_value.getvalue.return_value = b"fake pdf"

            pdf_bytes = report_generator.generate_test_end_report(test_id, auto_email=False)

            self.assertEqual(pdf_bytes, b"fake pdf")
            mock_doc_instance.build.assert_called_once()

    def test_multiple_tests_management(self):
        """Test managing multiple concurrent tests."""
        # Create multiple tests
        test_ids = []
        for i in range(3):
            test_id = self.ab_manager.create_test(
                name=f"Test {i+1}",
                description=f"Test description {i+1}",
                test_type=TestType.EMAIL_SUBJECT,
                variants=[
                    {"name": "A", "subject": f"Subject A{i}"},
                    {"name": "B", "subject": f"Subject B{i}"}
                ],
                target_sample_size=100
            )
            self.ab_manager.start_test(test_id)
            test_ids.append(test_id)

        # Get all active tests
        active_tests = self.ab_manager.get_active_tests()
        self.assertEqual(len(active_tests), 3)

        # Assign users to each test
        for test_id in test_ids:
            for user_id in range(10):
                self.ab_manager.assign_user_to_variant(f"{test_id}_user_{user_id}", test_id)

        # Verify each test has assignments
        for test_id in test_ids:
            results = self.ab_manager.get_test_results(test_id)
            self.assertEqual(results['total_assignments'], 10)

        # Stop one test
        self.ab_manager.stop_test(test_ids[0])

        # Verify active count decreased
        active_tests = self.ab_manager.get_active_tests()
        self.assertEqual(len(active_tests), 2)

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Test invalid test ID
        with self.assertRaises(ValueError):
            self.ab_manager.start_test("invalid_test_id")

        # Test assignment to non-existent test
        with self.assertRaises(ValueError):
            self.ab_manager.assign_user_to_variant("user123", "invalid_test_id")

        # Test recording conversion for unassigned user
        test_id = self.ab_manager.create_test(
            name="Error Test",
            description="Test error handling",
            test_type=TestType.EMAIL_SUBJECT,
            variants=[{"name": "A", "subject": "Subject A"}, {"name": "B", "subject": "Subject B"}]
        )
        self.ab_manager.start_test(test_id)

        with self.assertRaises(ValueError):
            self.ab_manager.record_conversion(test_id, "unassigned_user", "email_open")

        # Test notification service with invalid test
        status = self.notification_service.get_notification_status("invalid_test")
        self.assertIn('error', status)


if __name__ == "__main__":
    unittest.main()
