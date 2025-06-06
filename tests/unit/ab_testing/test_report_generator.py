"""Unit tests for A/B Test Report Generator."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from leadfactory.ab_testing.report_generator import ABTestReportGenerator
from leadfactory.ab_testing.ab_test_manager import ABTestConfig, TestStatus, TestType


class TestABTestReportGenerator(unittest.TestCase):
    """Test A/B Test Report Generator functionality."""

    def setUp(self):
        """Set up test environment."""
        self.report_generator = ABTestReportGenerator()
        self.report_generator.ab_manager = Mock()
        self.report_generator.stats_engine = Mock()

    def test_generate_test_end_report_success(self):
        """Test successful report generation."""
        # Mock test results
        test_config = ABTestConfig(
            id="test123",
            name="Email Subject Test",
            description="Testing different email subjects",
            test_type=TestType.EMAIL_SUBJECT,
            status=TestStatus.COMPLETED,
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
            target_sample_size=1000,
            significance_threshold=0.05,
            minimum_effect_size=0.1,
            variants=[
                {"name": "Subject A", "subject": "Original subject", "weight": 0.5},
                {"name": "Subject B", "subject": "New subject", "weight": 0.5}
            ],
            metadata={},
            created_at=datetime.utcnow() - timedelta(days=8),
            updated_at=datetime.utcnow()
        )

        test_results = {
            'test_id': 'test123',
            'test_config': test_config,
            'variant_results': {
                'variant_0': {
                    'assignments': 500,
                    'conversion_rates': {
                        'email_open': {'rate': 0.25, 'count': 125}
                    }
                },
                'variant_1': {
                    'assignments': 500,
                    'conversion_rates': {
                        'email_open': {'rate': 0.30, 'count': 150}
                    }
                }
            },
            'total_assignments': 1000
        }

        stats_results = {
            'p_value': 0.03,
            'effect_size': 0.2,
            'statistical_power': 0.85,
            'recommended_variant': 'variant_1',
            'significance_threshold': 0.05,
            'confidence_intervals': {
                'variant_0': (0.22, 0.28),
                'variant_1': (0.27, 0.33)
            }
        }

        self.report_generator.ab_manager.get_test_results.return_value = test_results
        self.report_generator.stats_engine.analyze_test_results.return_value = stats_results

        # Generate report
        pdf_bytes = self.report_generator.generate_test_end_report("test123", auto_email=False)

        # Verify
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)  # Should be a substantial PDF
        self.report_generator.ab_manager.get_test_results.assert_called_once_with("test123")
        self.report_generator.stats_engine.analyze_test_results.assert_called_once()

    def test_format_duration(self):
        """Test duration formatting."""
        start_date = datetime(2023, 1, 1, 10, 0, 0)
        end_date = datetime(2023, 1, 3, 14, 30, 0)

        duration = self.report_generator._format_duration(start_date, end_date)
        self.assertEqual(duration, "2 days, 4 hours")

        # Test hours only
        end_date_hours = datetime(2023, 1, 1, 15, 30, 0)
        duration_hours = self.report_generator._format_duration(start_date, end_date_hours)
        self.assertEqual(duration_hours, "5 hours")

    def test_interpret_p_value(self):
        """Test p-value interpretation."""
        # Significant
        interpretation = self.report_generator._interpret_p_value(0.02, 0.05)
        self.assertEqual(interpretation, "Significant (< 0.05)")

        # Marginally significant
        interpretation = self.report_generator._interpret_p_value(0.08, 0.05)
        self.assertEqual(interpretation, "Marginally significant")

        # Not significant
        interpretation = self.report_generator._interpret_p_value(0.15, 0.05)
        self.assertEqual(interpretation, "Not significant")

    def test_interpret_effect_size(self):
        """Test effect size interpretation."""
        # Small effect
        self.assertEqual(self.report_generator._interpret_effect_size(0.1), "Small effect")

        # Medium effect
        self.assertEqual(self.report_generator._interpret_effect_size(0.3), "Medium effect")

        # Large effect
        self.assertEqual(self.report_generator._interpret_effect_size(0.6), "Large effect")

    def test_interpret_power(self):
        """Test statistical power interpretation."""
        # Adequate power
        self.assertEqual(self.report_generator._interpret_power(0.85), "Adequate power")

        # Moderate power
        self.assertEqual(self.report_generator._interpret_power(0.7), "Moderate power")

        # Low power
        self.assertEqual(self.report_generator._interpret_power(0.5), "Low power")

    def test_get_variant_name(self):
        """Test variant name extraction."""
        test_config = Mock()
        test_config.variants = [
            {"name": "Control"},
            {"name": "Treatment A"}
        ]

        # Valid variant
        name = self.report_generator._get_variant_name("variant_0", test_config)
        self.assertEqual(name, "Control")

        # Invalid variant ID
        name = self.report_generator._get_variant_name("invalid_id", test_config)
        self.assertEqual(name, "invalid_id")

    def test_generate_insights(self):
        """Test insight generation."""
        test_config = Mock()
        test_config.target_sample_size = 1000

        test_results = {
            'test_config': test_config,
            'total_assignments': 1200,
            'variant_results': {
                'variant_0': {
                    'conversion_rates': {
                        'email_open': {'rate': 0.20}
                    }
                },
                'variant_1': {
                    'conversion_rates': {
                        'email_open': {'rate': 0.25}
                    }
                }
            }
        }

        stats_results = {
            'p_value': 0.02,
            'significance_threshold': 0.05,
            'recommended_variant': 'variant_1',
            'effect_size': 0.3
        }

        insights = self.report_generator._generate_insights(test_results, stats_results)

        # Should contain multiple insights
        self.assertGreater(len(insights), 0)

        # Should mention clear winner
        self.assertTrue(any("Clear Winner" in insight for insight in insights))

    def test_send_report_email(self):
        """Test email sending functionality."""
        # Mock the simple email sending method
        self.report_generator._send_report_email_simple = Mock()

        pdf_bytes = b"fake pdf content"
        recipient_emails = ["test@example.com", "test2@example.com"]
        stats_results = {
            'p_value': 0.02,
            'significance_threshold': 0.05
        }

        self.report_generator._send_report_email(
            "test123",
            pdf_bytes,
            recipient_emails,
            stats_results
        )

        # Should send emails to all recipients
        self.assertEqual(self.report_generator._send_report_email_simple.call_count, 2)

        # Check subject line for significant results
        call_args = self.report_generator._send_report_email_simple.call_args_list[0]
        subject = call_args[0][1]
        self.assertIn("Significant Results", subject)

    def test_error_handling(self):
        """Test error handling in report generation."""
        # Mock error in ab_manager
        self.report_generator.ab_manager.get_test_results.side_effect = Exception("Database error")

        with self.assertRaises(Exception):
            self.report_generator.generate_test_end_report("test123")


if __name__ == "__main__":
    unittest.main()
