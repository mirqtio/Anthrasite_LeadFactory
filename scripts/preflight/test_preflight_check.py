#!/usr/bin/env python3
"""
Test E2E Preflight Check System

Unit tests for the preflight_check.py module.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from scripts.preflight.api_tester import ApiTestResult
from scripts.preflight.config_validator import ValidationResult
from scripts.preflight.db_verifier import DbVerificationResult
from scripts.preflight.pipeline_validator import PipelineValidationResult
from scripts.preflight.preflight_check import PreflightCheck, PreflightCheckResult


class TestPreflightCheckResult(unittest.TestCase):
    """Test cases for the PreflightCheckResult class."""

    def test_init(self):
        """Test initialization of PreflightCheckResult."""
        result = PreflightCheckResult()
        self.assertIsNone(result.config_validation)
        self.assertIsNone(result.api_tests)
        self.assertIsNone(result.db_verification)
        self.assertIsNone(result.pipeline_validation)
        self.assertIsNotNone(result.start_time)
        self.assertIsNone(result.end_time)
        self.assertFalse(result.success)
        self.assertEqual(len(result.issues), 0)

    def test_complete(self):
        """Test completing a PreflightCheckResult."""
        result = PreflightCheckResult()
        issues = ["Issue 1", "Issue 2"]
        result.complete(False, issues)

        self.assertIsNotNone(result.end_time)
        self.assertFalse(result.success)
        self.assertEqual(result.issues, issues)

    def test_duration(self):
        """Test duration calculation of PreflightCheckResult."""
        result = PreflightCheckResult()

        # Set start time to 10 seconds ago
        result.start_time = datetime.now() - timedelta(seconds=10)

        # Test duration with no end time
        duration = result.duration()
        self.assertGreaterEqual(duration, 10.0)

        # Test duration with end time
        result.end_time = result.start_time + timedelta(seconds=5)
        duration = result.duration()
        self.assertAlmostEqual(duration, 5.0, delta=0.1)

    def test_str_success(self):
        """Test string representation of successful PreflightCheckResult."""
        result = PreflightCheckResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.complete(True, [])

        str_repr = str(result)
        self.assertIn("PASSED", str_repr)
        self.assertNotIn("FAILED", str_repr)

    def test_str_failure(self):
        """Test string representation of failed PreflightCheckResult."""
        result = PreflightCheckResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.complete(False, ["Issue 1", "Issue 2"])

        str_repr = str(result)
        self.assertIn("FAILED", str_repr)
        self.assertIn("Issue 1", str_repr)
        self.assertIn("Issue 2", str_repr)


class TestPreflightCheck(unittest.TestCase):
    """Test cases for the PreflightCheck class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary .env file for testing
        self.env_file = tempfile.NamedTemporaryFile(suffix=".env", delete=False).name
        with open(self.env_file, "w") as f:
            f.write(
                """
# Test environment file for preflight check
E2E_MODE=true
MOCKUP_ENABLED=false
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret
OPENAI_API_KEY=sk-test-key
GOOGLE_MAPS_API_KEY=test-maps-key
SENDGRID_API_KEY=test-sendgrid-key
DATA_INGESTION_URL=http://localhost:8001
DATA_PROCESSING_URL=http://localhost:8002
MODEL_TRAINING_URL=http://localhost:8003
API_GATEWAY_URL=http://localhost:8000
NOTIFICATION_SERVICE_URL=http://localhost:8004
"""
            )

        # Create a temporary log file
        self.log_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary files
        os.unlink(self.env_file)
        os.unlink(self.log_file)

    def test_init(self):
        """Test initialization of PreflightCheck."""
        check = PreflightCheck(env_file=self.env_file, log_file=self.log_file)
        self.assertEqual(check.env_file, self.env_file)
        self.assertEqual(check.log_file, self.log_file)
        self.assertIsNotNone(check.config_validator)
        self.assertIsNotNone(check.api_tester)
        self.assertIsNotNone(check.db_verifier)
        self.assertIsNotNone(check.pipeline_validator)
        self.assertIsNotNone(check.result)

    @patch("scripts.preflight.config_validator.ConfigValidator.validate")
    @patch("scripts.preflight.api_tester.ApiTester.test_all_apis")
    @patch("scripts.preflight.db_verifier.DbVerifier.verify_database")
    @patch("scripts.preflight.pipeline_validator.PipelineValidator.validate")
    def test_run_success(
        self,
        mock_pipeline_validate,
        mock_db_verify,
        mock_api_test,
        mock_config_validate,
    ):
        """Test successful preflight check run."""
        # Mock successful responses from all components
        mock_config_validate.return_value = ValidationResult(True, [])

        # API test results
        api_results = {
            "openai": ApiTestResult(True, "OpenAI API test successful", None),
            "google_maps": ApiTestResult(True, "Google Maps API test successful", None),
            "sendgrid": ApiTestResult(True, "SendGrid API test successful", None),
        }
        mock_api_test.return_value = api_results

        # DB verification result
        mock_db_verify.return_value = DbVerificationResult(True, [])

        # Pipeline validation result
        mock_pipeline_validate.return_value = PipelineValidationResult(
            True, ["comp1", "comp2"], [], []
        )

        # Run preflight check
        check = PreflightCheck(env_file=self.env_file, log_file=self.log_file)
        result = check.run()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(len(result.issues), 0)
        self.assertIsNotNone(result.end_time)

        # Verify all components were called
        mock_config_validate.assert_called_once()
        mock_api_test.assert_called_once()
        mock_db_verify.assert_called_once()
        mock_pipeline_validate.assert_called_once()

    @patch("scripts.preflight.config_validator.ConfigValidator.validate")
    @patch("scripts.preflight.api_tester.ApiTester.test_all_apis")
    @patch("scripts.preflight.db_verifier.DbVerifier.verify_database")
    @patch("scripts.preflight.pipeline_validator.PipelineValidator.validate")
    def test_run_failure(
        self,
        mock_pipeline_validate,
        mock_db_verify,
        mock_api_test,
        mock_config_validate,
    ):
        """Test failed preflight check run."""
        # Mock responses with some failures
        mock_config_validate.return_value = ValidationResult(
            False, ["Missing required variable"]
        )

        # API test results with one failure
        api_results = {
            "openai": ApiTestResult(True, "OpenAI API test successful", None),
            "google_maps": ApiTestResult(
                False, "Google Maps API test failed", "Invalid API key"
            ),
            "sendgrid": ApiTestResult(True, "SendGrid API test successful", None),
        }
        mock_api_test.return_value = api_results

        # DB verification result
        mock_db_verify.return_value = DbVerificationResult(True, [])

        # Pipeline validation result
        mock_pipeline_validate.return_value = PipelineValidationResult(
            False, ["comp1"], ["comp2"], ["Component comp2 not found"]
        )

        # Run preflight check
        check = PreflightCheck(env_file=self.env_file, log_file=self.log_file)
        result = check.run()

        # Check result
        self.assertFalse(result.success)
        self.assertGreater(len(result.issues), 0)
        self.assertIsNotNone(result.end_time)

        # Verify that the issues contain expected failures
        # Exact issue text may vary, so check for key fragments instead
        self.assertTrue(
            any(
                "google_maps" in issue and "Invalid API key" in issue
                for issue in result.issues
            )
        )
        self.assertTrue(
            any("comp2" in issue and "not found" in issue for issue in result.issues)
        )

        # Verify all components were called
        mock_config_validate.assert_called_once()
        mock_api_test.assert_called_once()
        mock_db_verify.assert_called_once()
        mock_pipeline_validate.assert_called_once()

    def test_generate_report(self):
        """Test report generation."""
        # Create a mock preflight check with mock results
        check = PreflightCheck(env_file=self.env_file, log_file=self.log_file)

        # Mock result data
        check.result.start_time = datetime.now() - timedelta(seconds=10)
        check.result.end_time = datetime.now()
        check.result.success = False
        check.result.issues = ["Issue 1", "Issue 2"]

        # Mock component results
        check.result.config_validation = ValidationResult(False, ["Missing variable"])

        api_results = {
            "openai": ApiTestResult(True, "OpenAI API test successful", None),
            "google_maps": ApiTestResult(
                False, "Google Maps API test failed", "Invalid API key"
            ),
        }
        check.result.api_tests = api_results

        check.result.db_verification = DbVerificationResult(True, [])

        check.result.pipeline_validation = PipelineValidationResult(
            False, ["comp1"], ["comp2"], ["Component comp2 not found"]
        )

        # Generate report
        report_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False).name
        try:
            check.generate_report(report_file)

            # Check that the report file was created
            self.assertTrue(os.path.exists(report_file))

            # Read the file and check content
            with open(report_file) as f:
                content = f.read()

            # Check for key components in the report
            self.assertIn("E2E Preflight Check Report", content)
            self.assertIn("Configuration Validation", content)
            self.assertIn("API Connectivity Tests", content)
            self.assertIn("Database Verification", content)
            self.assertIn("Pipeline Component Validation", content)
            self.assertIn("FAILED", content)
            # Check for the issues from the mocked components
            self.assertIn("Issue 1", content)
            self.assertIn("Issue 2", content)
            self.assertIn("google_maps", content)
            self.assertIn("comp2", content)
        finally:
            os.unlink(report_file)

    def test_generate_report_before_run(self):
        """Test report generation before preflight check run."""
        check = PreflightCheck(env_file=self.env_file, log_file=self.log_file)

        # Generate report without running preflight check
        report_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False).name
        try:
            # This should log a warning and not create a report
            check.generate_report(report_file)

            # Check that the report file was not created
            self.assertFalse(os.path.getsize(report_file) > 0)
        finally:
            os.unlink(report_file)


if __name__ == "__main__":
    # Add header and footer to test output
    unittest.main(verbosity=2)
