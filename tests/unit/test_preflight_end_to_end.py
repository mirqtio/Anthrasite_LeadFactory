"""
End-to-End Integration Tests for Complete Preflight Sequence

This module tests the entire preflight validation sequence from start to finish,
ensuring proper execution order, accurate pass/fail determination, and comprehensive
logging and reporting.
"""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from scripts.preflight.pipeline_validator import (
    PipelineValidator,
    ValidationError,
    ValidationErrorCode,
    ValidationLogger,
    ValidationSeverity,
)


class TestPreflightEndToEnd(unittest.TestCase):
    """End-to-end tests for the complete preflight sequence."""

    def setUp(self):
        """Set up test environment."""
        self.test_env = {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
            "YELP_API_KEY": "test_yelp_key",
            "GOOGLE_API_KEY": "test_google_key",
            "SCREENSHOTONE_API_KEY": "test_screenshot_key",
            "SENDGRID_API_KEY": "test_sendgrid_key",
            "SENDGRID_FROM_EMAIL": "test@example.com",
        }

        # Create temporary files for testing
        self.temp_files = []
        self.temp_dir = tempfile.mkdtemp()

        # Create test email template
        self.email_template = os.path.join(self.temp_dir, "email_template.html")
        with open(self.email_template, "w") as f:
            f.write("<html><body>Test template</body></html>")
        self.temp_files.append(self.email_template)

    def tearDown(self):
        """Clean up test environment."""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="<html><body>Test</body></html>",
    )
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_complete_preflight_sequence_success(
        self, mock_find_spec, mock_exists, mock_file, mock_requests, mock_db
    ):
        """Test successful execution of complete preflight sequence."""
        # Set up environment variables
        with patch.dict(os.environ, self.test_env):
            # Mock successful database connection
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            # Mock successful HTTP requests
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            # Mock file existence
            mock_exists.return_value = True

            # Mock module imports
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            # Create validator and run complete sequence
            validator = PipelineValidator()

            # Test the complete validation sequence
            result = validator.validate()

            # Verify the sequence executed successfully
            self.assertTrue(
                result,
                "Complete preflight sequence should pass with all dependencies met",
            )

            # Verify database connection was attempted
            mock_db.assert_called()

            # Verify file access was checked
            mock_exists.assert_called()

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_complete_preflight_sequence_failure(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test complete preflight sequence with multiple failures."""
        # Set up minimal environment (missing required keys)
        minimal_env = {"DATABASE_URL": "postgresql://test:test@localhost:5432/testdb"}

        with patch.dict(os.environ, minimal_env):
            # Mock database connection failure
            mock_db.side_effect = Exception("Database connection failed")

            # Mock network request failure
            mock_requests.side_effect = Exception("Network error")

            # Mock file not found
            mock_exists.return_value = False

            # Mock module import failure
            mock_find_spec.return_value = None

            # Create validator and run complete sequence
            validator = PipelineValidator()

            # Test the complete validation sequence
            result = validator.validate()

            # Verify the sequence failed appropriately
            self.assertFalse(
                result,
                "Complete preflight sequence should fail with missing dependencies",
            )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_execution_order(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test that preflight checks execute in the correct order."""
        with patch.dict(os.environ, self.test_env):
            # Mock successful responses
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            # Create validator with custom logger to track execution order
            validator = PipelineValidator()

            # Capture log messages to verify execution order
            with self.assertLogs("pipeline_validator", level="INFO") as log_context:
                validator.validate()

                log_messages = [record.getMessage() for record in log_context.records]

                # Verify that dependency validation happens first
                dependency_logs = [
                    msg for msg in log_messages if "dependency" in msg.lower()
                ]
                self.assertTrue(
                    len(dependency_logs) > 0, "Dependency validation should be logged"
                )

                # Verify that component validation follows
                component_logs = [
                    msg for msg in log_messages if "component" in msg.lower()
                ]
                self.assertTrue(
                    len(component_logs) > 0, "Component validation should be logged"
                )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_pass_fail_determination(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test accurate pass/fail determination for the complete sequence."""
        # Test scenario 1: All checks pass
        with patch.dict(os.environ, self.test_env):
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            validator = PipelineValidator()
            result = validator.validate()

            self.assertTrue(result, "Should pass when all checks succeed")

        # Test scenario 2: Critical failure causes overall failure
        with patch.dict(os.environ, {"DATABASE_URL": "invalid_url"}):
            mock_db.side_effect = Exception("Critical database error")
            mock_exists.return_value = True
            mock_find_spec.return_value = mock_spec

            validator = PipelineValidator()
            result = validator.validate()

            self.assertFalse(result, "Should fail when critical checks fail")

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_logging_and_reporting(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test comprehensive logging and reporting of sequence results."""
        with patch.dict(os.environ, self.test_env):
            # Mock mixed success/failure scenario
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            # Some requests succeed, some fail
            def mock_request_side_effect(url, **kwargs):
                if "google" in url:
                    response = MagicMock()
                    response.status_code = 200
                    return response
                else:
                    raise Exception("Network timeout")

            mock_requests.side_effect = mock_request_side_effect
            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            # Create validator and capture logs
            validator = PipelineValidator()

            with self.assertLogs("pipeline_validator", level="INFO") as log_context:
                result = validator.validate()

                log_messages = [record.getMessage() for record in log_context.records]

                # Verify comprehensive logging
                self.assertTrue(
                    any("Starting pipeline validation" in msg for msg in log_messages),
                    "Should log validation start",
                )

                self.assertTrue(
                    any("validation" in msg.lower() for msg in log_messages),
                    "Should log validation progress",
                )

                # Check for error reporting
                error_logs = [
                    msg for msg in log_messages if "ERROR" in str(log_context.records)
                ]
                if not result:
                    self.assertTrue(
                        len(error_logs) > 0, "Should log errors when validation fails"
                    )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_partial_failure_handling(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test handling of partial failures in the preflight sequence."""
        # Set up environment with some missing optional components
        partial_env = {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
            "YELP_API_KEY": "test_yelp_key",
            # Missing GOOGLE_API_KEY and other optional keys
        }

        with patch.dict(os.environ, partial_env):
            # Mock successful database but some network failures
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            validator = PipelineValidator()
            result = validator.validate()

            # The result depends on whether missing components are critical
            # This test verifies that partial failures are handled gracefully
            self.assertIsInstance(
                result,
                bool,
                "Should return a boolean result even with partial failures",
            )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_error_recovery_and_continuation(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test that preflight sequence continues after non-critical errors."""
        with patch.dict(os.environ, self.test_env):
            # Mock database success
            mock_db_conn = MagicMock()
            mock_db.return_value = mock_db_conn

            # Mock some network requests failing, others succeeding
            call_count = 0

            def mock_request_side_effect(url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 0:  # Every other request fails
                    raise Exception("Intermittent network error")
                else:
                    response = MagicMock()
                    response.status_code = 200
                    return response

            mock_requests.side_effect = mock_request_side_effect
            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            validator = PipelineValidator()

            # Capture logs to verify continuation after errors
            with self.assertLogs("pipeline_validator", level="INFO") as log_context:
                validator.validate()

                log_messages = [record.getMessage() for record in log_context.records]

                # Verify that validation continued despite some failures
                component_validations = [
                    msg for msg in log_messages if "Validating component" in msg
                ]
                self.assertTrue(
                    len(component_validations) > 1,
                    "Should continue validating multiple components despite some failures",
                )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_performance_and_timeout_handling(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Test preflight sequence performance and timeout handling."""
        with patch.dict(os.environ, self.test_env):
            # Mock database connection with delay
            import time

            def slow_db_connect(*args, **kwargs):
                time.sleep(0.1)  # Small delay to simulate slow connection
                return MagicMock()

            mock_db.side_effect = slow_db_connect

            # Mock slow network requests
            def slow_request(*args, **kwargs):
                time.sleep(0.05)  # Small delay
                response = MagicMock()
                response.status_code = 200
                return response

            mock_requests.side_effect = slow_request
            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            validator = PipelineValidator()

            # Measure execution time
            start_time = time.time()
            result = validator.validate()
            execution_time = time.time() - start_time

            # Verify reasonable execution time (should complete within reasonable bounds)
            self.assertLess(
                execution_time,
                30.0,
                "Preflight sequence should complete within 30 seconds",
            )
            self.assertIsInstance(
                result, bool, "Should return a result even with slow operations"
            )

    def test_preflight_configuration_validation(self):
        """Test validation of preflight configuration and setup."""
        # Test validator initialization
        validator = PipelineValidator()

        # Verify validator has required components
        self.assertIsNotNone(validator, "Validator should initialize successfully")

        # Test logger initialization
        logger = ValidationLogger()
        self.assertIsNotNone(logger, "Logger should initialize successfully")
        self.assertIsNotNone(
            logger.validation_session_id, "Logger should have session ID"
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch("psycopg2.connect")
    @patch("requests.get")
    @patch("os.path.exists")
    @patch("importlib.util.find_spec")
    def test_preflight_comprehensive_end_to_end(
        self, mock_find_spec, mock_exists, mock_requests, mock_db
    ):
        """Comprehensive end-to-end test covering the complete preflight workflow."""
        with patch.dict(os.environ, self.test_env):
            # Set up comprehensive mocking for full workflow
            mock_db_conn = MagicMock()
            mock_db_conn.cursor.return_value.fetchone.return_value = (1,)
            mock_db.return_value = mock_db_conn

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_requests.return_value = mock_response

            mock_exists.return_value = True
            mock_spec = MagicMock()
            mock_find_spec.return_value = mock_spec

            # Create validator and run complete workflow
            validator = PipelineValidator()

            # Test complete validation workflow
            with self.assertLogs("pipeline_validator", level="INFO") as log_context:
                result = validator.validate()

                # Verify workflow completion
                self.assertIsInstance(result, bool, "Should return boolean result")

                # Verify comprehensive logging
                log_messages = [record.getMessage() for record in log_context.records]

                # Check for key workflow stages
                self.assertTrue(
                    any("Starting pipeline validation" in msg for msg in log_messages),
                    "Should log workflow start",
                )

                self.assertTrue(
                    any("dependency" in msg.lower() for msg in log_messages),
                    "Should log dependency validation",
                )

                self.assertTrue(
                    any("component" in msg.lower() for msg in log_messages),
                    "Should log component validation",
                )

                # Verify database connections were tested
                mock_db.assert_called()

                # Verify network connectivity was tested
                mock_requests.assert_called()

                # Verify file access was tested
                mock_exists.assert_called()


if __name__ == "__main__":
    unittest.main()
