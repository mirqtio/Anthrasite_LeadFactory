#!/usr/bin/env python3
"""
Unit tests for the E2E Pipeline Report Generator
"""
import os
import json
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open

import pytest

from scripts.e2e.report_generator import (
    ReportGenerator,
    MetricsCalculator,
    ResultValidator,
    ReportType,
    OutputFormat
)


class TestReportGenerator(unittest.TestCase):
    """Tests for the ReportGenerator class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.report_generator = ReportGenerator(output_dir=self.temp_dir)

        # Mock dependencies
        self.report_generator.tracker = MagicMock()
        self.report_generator.validator = MagicMock()
        self.report_generator.metrics = MagicMock()
        self.report_generator.analyzer = MagicMock()

    def tearDown(self):
        """Clean up test fixtures"""
        # Clean up temp files
        for file in os.listdir(self.temp_dir):
            os.unlink(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def test_generate_report_executive_summary_html(self):
        """Test generating an executive summary report in HTML format"""
        # Set up mock data
        self.report_generator.tracker.get_recent_executions.return_value = [
            {
                "execution_id": "test-123",
                "status": "success",
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration": 120,
                "stages": {
                    "stage1": {"status": "success", "duration": 60},
                    "stage2": {"status": "success", "duration": 60}
                },
                "failures": []
            }
        ]
        self.report_generator.metrics.calculate_success_rate.return_value = 100.0
        self.report_generator.metrics.calculate_average_duration.return_value = 120
        self.report_generator.validator.validate_execution.return_value = {
            "test_coverage": {"status": "passed"},
            "performance": {"status": "passed"},
            "outputs": {"status": "passed"}
        }

        # Call the method under test
        report_path = self.report_generator.generate_report(
            report_type=ReportType.EXECUTIVE_SUMMARY,
            output_format=OutputFormat.HTML
        )

        # Assert report file was created
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.endswith(".html"))

        # Read report content and verify structure
        with open(report_path, "r") as f:
            content = f.read()
            self.assertIn("<html", content)
            self.assertIn("Executive Summary", content)
            self.assertIn("100.0%", content)  # Success rate
            self.assertIn("120", content)  # Duration

    def test_generate_report_technical_detail_json(self):
        """Test generating a technical detail report in JSON format"""
        # Set up mock data
        mock_execution = {
            "execution_id": "test-123",
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration": 120,
            "stages": {
                "stage1": {
                    "status": "success",
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration": 60,
                    "retry_count": 0,
                    "error": None
                }
            },
            "failures": []
        }
        self.report_generator.tracker.get_execution.return_value = mock_execution
        self.report_generator.validator.validate_execution.return_value = {
            "test_coverage": {"status": "passed"},
            "performance": {"status": "passed"},
            "outputs": {"status": "passed"}
        }

        # Call the method under test
        report_path = self.report_generator.generate_report(
            report_type=ReportType.TECHNICAL_DETAIL,
            output_format=OutputFormat.JSON,
            execution_id="test-123"
        )

        # Assert report file was created
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.endswith(".json"))

        # Verify JSON structure
        with open(report_path, "r") as f:
            report_data = json.load(f)
            self.assertEqual(report_data["execution_id"], "test-123")
            self.assertEqual(report_data["execution_status"], "success")
            self.assertIn("validation_results", report_data)
            self.assertIn("stage_details", report_data)

    def test_generate_report_trend_analysis_markdown(self):
        """Test generating a trend analysis report in Markdown format"""
        # Set up mock data
        self.report_generator.tracker.get_recent_executions.return_value = [
            {
                "execution_id": f"test-{i}",
                "status": "success",
                "start_time": datetime.now().isoformat(),
                "duration": 120,
                "failures": []
            } for i in range(10)
        ]
        self.report_generator.metrics.calculate_success_rate.return_value = 90.0
        self.report_generator.metrics.calculate_stage_success_rates.return_value = {
            "stage1": 100.0, "stage2": 80.0
        }
        self.report_generator.metrics.calculate_average_duration.return_value = 120
        self.report_generator.metrics.calculate_stage_average_durations.return_value = {
            "stage1": 60, "stage2": 60
        }
        self.report_generator.metrics.calculate_failure_counts.return_value = {
            "network": 1, "timeout": 1
        }
        self.report_generator.metrics.calculate_retry_rates.return_value = {
            "stage1": 0.0, "stage2": 0.2
        }
        self.report_generator.analyzer.analyze_execution_history.return_value = {
            "recurring_patterns": ["pattern1", "pattern2"],
            "stage_reliability": {"stage1": "high", "stage2": "medium"}
        }

        # Call the method under test
        report_path = self.report_generator.generate_report(
            report_type=ReportType.TREND_ANALYSIS,
            output_format=OutputFormat.MARKDOWN,
            num_executions=10
        )

        # Assert report file was created
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.endswith(".md"))

        # Verify Markdown structure
        with open(report_path, "r") as f:
            content = f.read()
            self.assertIn("# E2E Pipeline Trend Analysis", content)
            self.assertIn("90.0%", content)  # Success rate
            self.assertIn("pattern1", content)  # Recurring pattern
            self.assertIn("stage1", content)  # Stage name
            self.assertIn("stage2", content)  # Stage name

    def test_generate_report_issue_report_html(self):
        """Test generating an issue report in HTML format"""
        # Set up mock data
        mock_execution = {
            "execution_id": "test-123",
            "status": "failed",
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration": 120,
            "stages": {
                "stage1": {"status": "success", "duration": 60},
                "stage2": {"status": "failed", "duration": 60, "error": "Test error"}
            },
            "failures": [
                {
                    "stage": "stage2",
                    "message": "Test error",
                    "category": "test",
                    "resolution": ""
                }
            ],
            "resolution_attempts": []
        }
        self.report_generator.tracker.get_execution.return_value = mock_execution

        # Mock the pattern matching
        mock_pattern = MagicMock()
        mock_pattern.pattern_id = "pattern-123"
        mock_pattern.name = "Test Pattern"
        mock_pattern.description = "Test pattern description"
        mock_pattern.auto_resolvable = True
        mock_pattern.resolution_steps = ["Step 1", "Step 2"]

        self.report_generator.analyzer.analyze_failure.return_value = ([mock_pattern], {})

        # Call the method under test
        report_path = self.report_generator.generate_report(
            report_type=ReportType.ISSUE_REPORT,
            output_format=OutputFormat.HTML,
            execution_id="test-123"
        )

        # Assert report file was created
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.endswith(".html"))

        # Verify HTML structure
        with open(report_path, "r") as f:
            content = f.read()
            self.assertIn("<html", content)
            self.assertIn("Issue Report", content)
            self.assertIn("Test error", content)  # Error message
            self.assertIn("Test Pattern", content)  # Pattern name
            self.assertIn("Step 1", content)  # Resolution step

    def test_generate_report_test_coverage_csv(self):
        """Test generating a test coverage report in CSV format"""
        # Set up mock data
        self.report_generator.validator.validate_test_coverage.return_value = {
            "status": "passed",
            "details": {
                "required_stages_coverage": 100.0,
                "critical_stages_coverage": 100.0,
                "missing_stages": []
            }
        }
        self.report_generator.metrics.calculate_stage_success_rates.return_value = {
            "stage1": 100.0, "stage2": 90.0
        }
        self.report_generator.validator.requirements.get.return_value = {
            "required_stages": ["stage1", "stage2"],
            "critical_stages": ["stage1"]
        }

        # Call the method under test
        report_path = self.report_generator.generate_report(
            report_type=ReportType.TEST_COVERAGE,
            output_format=OutputFormat.CSV
        )

        # Assert report file was created
        self.assertTrue(os.path.exists(report_path))
        self.assertTrue(report_path.endswith(".csv"))

        # Verify CSV structure
        with open(report_path, "r") as f:
            content = f.read()
            self.assertIn("status,passed", content)
            self.assertIn("required_stages_coverage,100.0", content)
            self.assertIn("stage1,100.0", content)
            self.assertIn("stage2,90.0", content)

    def test_generate_report_performance_metrics_console(self):
        """Test generating a performance metrics report in console format"""
        # Set up mock data
        self.report_generator.tracker.get_recent_executions.return_value = [
            {
                "execution_id": f"test-{i}",
                "status": "success",
                "start_time": datetime.now().isoformat(),
                "duration": 120,
                "failures": []
            } for i in range(10)
        ]
        self.report_generator.metrics.calculate_average_duration.return_value = 120
        self.report_generator.metrics.calculate_stage_average_durations.return_value = {
            "stage1": 60, "stage2": 60
        }
        self.report_generator.validator.requirements.get.return_value = {
            "max_duration_seconds": {
                "stage1": 100,
                "stage2": 100,
                "total": 200
            }
        }

        # Call the method under test
        with patch("sys.stdout") as mock_stdout:
            report_path = self.report_generator.generate_report(
                report_type=ReportType.PERFORMANCE_METRICS,
                output_format=OutputFormat.CONSOLE
            )

            # Assert report was printed to console
            mock_stdout.write.assert_called()

            # Assert no file was created
            self.assertIsNone(report_path)

    def test_distribute_report_email(self):
        """Test distributing a report via email"""
        # Create a test report file
        report_path = os.path.join(self.temp_dir, "test_report.html")
        with open(report_path, "w") as f:
            f.write("<html><body>Test Report</body></html>")

        # Mock the email distribution method
        with patch.object(self.report_generator, "_distribute_via_email") as mock_email:
            mock_email.return_value = True

            # Call the method under test
            result = self.report_generator.distribute_report(
                report_path=report_path,
                distribution_channel="email",
                recipients=["test@example.com"]
            )

            # Assert the distribution was successful
            self.assertTrue(result)
            mock_email.assert_called_once_with(report_path, ["test@example.com"])

    def test_distribute_report_slack(self):
        """Test distributing a report via Slack"""
        # Create a test report file
        report_path = os.path.join(self.temp_dir, "test_report.html")
        with open(report_path, "w") as f:
            f.write("<html><body>Test Report</body></html>")

        # Mock the Slack distribution method
        with patch.object(self.report_generator, "_distribute_via_slack") as mock_slack:
            mock_slack.return_value = True

            # Call the method under test
            result = self.report_generator.distribute_report(
                report_path=report_path,
                distribution_channel="slack",
                recipients=["#test-channel"]
            )

            # Assert the distribution was successful
            self.assertTrue(result)
            mock_slack.assert_called_once_with(report_path, ["#test-channel"])

    def test_distribute_report_unsupported_channel(self):
        """Test distributing a report via an unsupported channel"""
        # Create a test report file
        report_path = os.path.join(self.temp_dir, "test_report.html")
        with open(report_path, "w") as f:
            f.write("<html><body>Test Report</body></html>")

        # Call the method under test
        with patch("scripts.e2e.report_generator.logger") as mock_logger:
            result = self.report_generator.distribute_report(
                report_path=report_path,
                distribution_channel="unsupported",
                recipients=["test@example.com"]
            )

            # Assert the distribution failed
            self.assertFalse(result)
            mock_logger.error.assert_called_once()


class TestMetricsCalculator(unittest.TestCase):
    """Tests for the MetricsCalculator class"""

    def setUp(self):
        """Set up test fixtures"""
        self.metrics_calculator = MetricsCalculator()
        self.metrics_calculator.tracker = MagicMock()

    def test_calculate_success_rate(self):
        """Test calculating success rate"""
        # Set up mock data
        self.metrics_calculator.tracker.get_recent_executions.return_value = [
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
            {"status": "success"}
        ]

        # Call the method under test
        success_rate = self.metrics_calculator.calculate_success_rate()

        # Assert the success rate is correct
        self.assertEqual(success_rate, 75.0)

    def test_calculate_stage_success_rates(self):
        """Test calculating stage success rates"""
        # Set up mock data
        self.metrics_calculator.tracker.get_recent_executions.return_value = [
            {
                "stages": {
                    "stage1": {"status": "success"},
                    "stage2": {"status": "success"}
                }
            },
            {
                "stages": {
                    "stage1": {"status": "success"},
                    "stage2": {"status": "failed"}
                }
            }
        ]

        # Call the method under test
        stage_success_rates = self.metrics_calculator.calculate_stage_success_rates()

        # Assert the stage success rates are correct
        self.assertEqual(stage_success_rates["stage1"], 100.0)
        self.assertEqual(stage_success_rates["stage2"], 50.0)

    def test_calculate_average_duration(self):
        """Test calculating average duration"""
        # Set up mock data
        self.metrics_calculator.tracker.get_recent_executions.return_value = [
            {"duration": 100},
            {"duration": 200},
            {"duration": 300}
        ]

        # Call the method under test
        avg_duration = self.metrics_calculator.calculate_average_duration()

        # Assert the average duration is correct
        self.assertEqual(avg_duration, 200.0)

    def test_calculate_failure_counts(self):
        """Test calculating failure counts"""
        # Set up mock data
        self.metrics_calculator.tracker.get_recent_executions.return_value = [
            {
                "failures": [
                    {"category": "network"},
                    {"category": "timeout"}
                ]
            },
            {
                "failures": [
                    {"category": "network"}
                ]
            }
        ]

        # Call the method under test
        failure_counts = self.metrics_calculator.calculate_failure_counts()

        # Assert the failure counts are correct
        self.assertEqual(failure_counts["network"], 2)
        self.assertEqual(failure_counts["timeout"], 1)


class TestResultValidator(unittest.TestCase):
    """Tests for the ResultValidator class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the requirements file loading
        with patch("builtins.open", mock_open(read_data=json.dumps({
            "test_coverage": {
                "required_stages": ["stage1", "stage2"],
                "critical_stages": ["stage1"]
            },
            "performance": {
                "max_duration_seconds": {
                    "stage1": 100,
                    "stage2": 100,
                    "total": 200
                }
            },
            "outputs": {
                "required_files": ["output1.txt", "output2.txt"]
            }
        }))):
            self.validator = ResultValidator()
            self.validator.tracker = MagicMock()

    def test_validate_test_coverage(self):
        """Test validating test coverage"""
        # Set up mock data
        mock_execution = {
            "stages": {
                "stage1": {"status": "success"},
                "stage2": {"status": "success"}
            }
        }
        self.validator.tracker.get_execution.return_value = mock_execution
        self.validator.tracker.get_recent_executions.return_value = [mock_execution]

        # Call the method under test
        results = self.validator.validate_test_coverage()

        # Assert the validation results are correct
        self.assertTrue(results["valid"])
        self.assertEqual(results["message"], "Test coverage validation completed")
        self.assertEqual(results["success_rate"], 100.0)
        self.assertEqual(results["missing_stages"], [])
        self.assertEqual(results["critical_failures"], [])

    def test_validate_performance(self):
        """Test validating performance"""
        # Set up mock data
        mock_execution = {
            "duration": 150,
            "stages": {
                "stage1": {"duration": 70},
                "stage2": {"duration": 80}
            }
        }
        self.validator.tracker.get_execution.return_value = mock_execution
        self.validator.tracker.get_recent_executions.return_value = [mock_execution]

        # Call the method under test
        results = self.validator.validate_performance()

        # Assert the validation results are correct
        self.assertTrue(results["valid"])
        self.assertEqual(results["message"], "Performance validation completed")
        self.assertEqual(results["performance_issues"], [])

    def test_validate_outputs(self):
        """Test validating outputs"""
        # Set up mock data
        mock_execution = {
            "outputs": {
                "files": ["output1.txt", "output2.txt"]
            }
        }
        self.validator.tracker.get_execution.return_value = mock_execution

        # Mock os.path.exists to return True for required files
        with patch("os.path.exists", return_value=True):
            # Call the method under test
            results = self.validator.validate_outputs()

            # Assert the validation results are correct
            self.assertTrue(results["valid"])
            self.assertEqual(results["message"], "Output validation completed")
            self.assertEqual(results["missing_outputs"], [])

    def test_validate_execution(self):
        """Test validating the entire execution"""
        # Mock the individual validation methods
        with patch.object(self.validator, "validate_test_coverage") as mock_coverage, \
             patch.object(self.validator, "validate_performance") as mock_performance, \
             patch.object(self.validator, "validate_outputs") as mock_outputs:

            mock_coverage.return_value = {"valid": True, "message": "Test coverage validation completed"}
            mock_performance.return_value = {"valid": True, "message": "Performance validation completed"}
            mock_outputs.return_value = {"valid": True, "message": "Output validation completed"}

            # Call the method under test
            results = self.validator.validate_execution()

            # Assert the validation results are correct
            self.assertTrue(results["valid"])
            self.assertEqual(results["message"], "Execution validation completed")
            self.assertIn("validations", results)
            self.assertTrue(results["validations"]["test_coverage"]["valid"])
            self.assertTrue(results["validations"]["performance"]["valid"])
            self.assertTrue(results["validations"]["outputs"]["valid"])


if __name__ == "__main__":
    pytest.main()
