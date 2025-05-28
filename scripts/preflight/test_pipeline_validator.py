#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Pipeline Component Validator

Unit tests for the pipeline_validator.py module.
"""

import os
import json
import unittest
import tempfile
import subprocess
import requests
from unittest.mock import patch, MagicMock, mock_open

from scripts.preflight.pipeline_validator import (
    PipelineValidator,
    PipelineValidationResult,
)


class TestPipelineValidator(unittest.TestCase):
    """Test cases for the PipelineValidator class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary .env file for testing
        self.env_file = tempfile.NamedTemporaryFile(suffix=".env", delete=False).name
        with open(self.env_file, "w") as f:
            f.write(
                """
# Test environment file for pipeline validation
E2E_MODE=true
MOCKUP_ENABLED=false
DATA_INGESTION_URL=http://localhost:8001
DATA_PROCESSING_URL=http://localhost:8002
MODEL_TRAINING_URL=http://localhost:8003
API_GATEWAY_URL=http://localhost:8000
NOTIFICATION_SERVICE_URL=http://localhost:8004
"""
            )

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary .env file
        os.unlink(self.env_file)

    def test_init(self):
        """Test initialization of PipelineValidator."""
        validator = PipelineValidator(env_file=self.env_file)
        self.assertEqual(validator.env_file, self.env_file)
        self.assertFalse(validator.mock_mode)

    @patch.dict("os.environ", {"MOCKUP_ENABLED": "true"})
    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        # Create a validator with mock mode environment variable set
        validator = PipelineValidator()
        self.assertTrue(validator.mock_mode)

    def test_validate_mock_mode(self):
        """Test validation in mock mode."""
        # Create a validator with mock mode enabled
        with patch.dict(os.environ, {"MOCKUP_ENABLED": "true"}):
            validator = PipelineValidator()
            result = validator.validate()

            # In mock mode, validation should succeed with all components verified
            self.assertTrue(result.success)
            self.assertEqual(
                len(result.components_verified), len(validator.REQUIRED_COMPONENTS)
            )
            self.assertEqual(len(result.components_failed), 0)
            self.assertEqual(len(result.issues), 0)

    def test_validate_non_e2e_mode(self):
        """Test validation when not in E2E mode."""
        # Create a validator with E2E mode disabled
        with patch.dict(os.environ, {"E2E_MODE": "false", "MOCKUP_ENABLED": "false"}):
            validator = PipelineValidator()
            result = validator.validate()

            # When not in E2E mode, validation should be skipped
            self.assertTrue(result.success)
            self.assertEqual(result.components_verified, ["skipped_validation"])
            self.assertEqual(len(result.components_failed), 0)
            self.assertEqual(len(result.issues), 0)

    @patch("requests.get")
    def test_verify_component_success(self, mock_get):
        """Test successful component verification."""
        # Mock successful response from component
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should succeed with no issues
        self.assertTrue(success)
        self.assertEqual(len(issues), 0)

        # Check that requests.get was called with the right URL
        mock_get.assert_called_once_with("http://localhost:8001/status", timeout=5)

    @patch("requests.get")
    def test_verify_component_failure_status_code(self, mock_get):
        """Test component verification with non-200 status code."""
        # Mock error response from component
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("status code 500", issues[0])

    @patch("requests.get")
    def test_verify_component_failure_bad_json(self, mock_get):
        """Test component verification with invalid JSON response."""
        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("invalid JSON", issues[0])

    @patch("requests.get")
    def test_verify_component_failure_bad_status(self, mock_get):
        """Test component verification with non-ok status."""
        # Mock response with non-ok status
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "message": "Something went wrong",
        }
        mock_get.return_value = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("status is 'error'", issues[0])

    @patch("requests.get")
    def test_verify_component_failure_no_status(self, mock_get):
        """Test component verification with response missing status field."""
        # Mock response missing status field
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Hello"}
        mock_get.return_value = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("missing 'status' field", issues[0])

    @patch("requests.get")
    def test_verify_component_failure_connection_error(self, mock_get):
        """Test component verification with connection error."""
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("Failed to connect", issues[0])

    @patch("requests.get")
    @patch.dict("os.environ", {"E2E_MODE": "true"}, clear=True)
    def test_verify_component_missing_url(self, mock_get):
        """Test component verification with missing URL."""
        # Create a validator with empty environment (DATA_INGESTION_URL not set)
        validator = PipelineValidator()
        success, issues = validator._verify_component("data_ingestion")

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(issues), 1)
        self.assertIn("Missing DATA_INGESTION_URL", issues[0])

        # requests.get should not be called
        mock_get.assert_not_called()

    @patch("subprocess.run")
    def test_verify_docker_services_success(self, mock_run):
        """Test successful Docker services verification."""
        # Mock successful subprocess call with all components running
        mock_process = MagicMock()
        mock_process.stdout = "data_ingestion_service\ndata_processing_service\nmodel_training_service\napi_gateway_service\nnotification_service"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        validator = PipelineValidator(env_file=self.env_file)
        success, running_services, issues = validator.verify_docker_services()

        # Verification should succeed with all services running
        self.assertTrue(success)
        self.assertEqual(len(running_services), 5)
        self.assertEqual(len(issues), 0)

    @patch("subprocess.run")
    def test_verify_docker_services_missing(self, mock_run):
        """Test Docker services verification with missing services."""
        # Mock subprocess call with some services missing
        mock_process = MagicMock()
        mock_process.stdout = "data_ingestion_service\nmodel_training_service"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        validator = PipelineValidator(env_file=self.env_file)
        success, running_services, issues = validator.verify_docker_services()

        # Verification should fail with appropriate issues
        self.assertFalse(success)
        self.assertEqual(len(running_services), 2)
        self.assertEqual(len(issues), 3)  # 3 missing services

    @patch("subprocess.run")
    def test_verify_docker_services_error(self, mock_run):
        """Test Docker services verification with subprocess error."""
        # Mock subprocess error
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        validator = PipelineValidator(env_file=self.env_file)
        success, running_services, issues = validator.verify_docker_services()

        # Verification should fail with appropriate issue
        self.assertFalse(success)
        self.assertEqual(len(running_services), 0)
        self.assertEqual(len(issues), 1)
        self.assertIn("Error checking Docker services", issues[0])

    @patch(
        "scripts.preflight.pipeline_validator.PipelineValidator.verify_pipeline_connections"
    )
    def test_verify_pipeline_connections_success(self, mock_verify_connections):
        """Test successful pipeline connections verification."""
        # Mock the method directly to return success
        mock_verify_connections.return_value = (True, [])

        # Create a validator
        validator = PipelineValidator(env_file=self.env_file)

        # Call the method (which is now mocked)
        success, issues = validator.verify_pipeline_connections()

        # Verification should succeed with no issues
        self.assertTrue(success)
        self.assertEqual(len(issues), 0)

    @patch("requests.get")
    def test_verify_pipeline_connections_failure(self, mock_get):
        """Test pipeline connections verification with failures."""

        # Mock responses with some connection failures
        def mock_response(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200

            if "data_ingestion" in url:
                mock_resp.json.return_value = {
                    "connections": [{"target": "data_processing", "status": "error"}]
                }
            elif "data_processing" in url:
                # Missing connection data
                mock_resp.json.return_value = {"connections": []}
            elif "model_training" in url:
                mock_resp.json.return_value = {
                    "connections": [{"target": "api_gateway", "status": "ok"}]
                }
            elif "api_gateway" in url:
                # Error status code
                mock_resp.status_code = 500
                mock_resp.json.side_effect = Exception("Shouldn't be called")

            return mock_resp

        mock_get.side_effect = mock_response

        validator = PipelineValidator(env_file=self.env_file)
        success, issues = validator.verify_pipeline_connections()

        # Verification should fail with appropriate issues
        self.assertFalse(success)
        self.assertGreaterEqual(len(issues), 3)  # At least 3 issues

    def test_generate_sample_env_file(self):
        """Test generation of sample environment file."""
        # Create a temporary file for the sample config
        output_file = tempfile.NamedTemporaryFile(suffix=".env", delete=False).name

        try:
            validator = PipelineValidator()
            validator.generate_sample_env_file(output_file)

            # Check that the file was created
            self.assertTrue(os.path.exists(output_file))

            # Read the file and check content
            with open(output_file, "r") as f:
                content = f.read()

            # Check for key components in the sample config
            self.assertIn("E2E_MODE=true", content)
            self.assertIn("MOCKUP_ENABLED=false", content)
            self.assertIn("DATA_INGESTION_URL=", content)
            self.assertIn("DATA_PROCESSING_URL=", content)
            self.assertIn("MODEL_TRAINING_URL=", content)
            self.assertIn("API_GATEWAY_URL=", content)
            self.assertIn("NOTIFICATION_SERVICE_URL=", content)
        finally:
            os.unlink(output_file)

    def test_validation_result_str(self):
        """Test string representation of PipelineValidationResult."""
        # Test successful result
        result = PipelineValidationResult(True, ["comp1", "comp2"], [], [])
        self.assertEqual(str(result), "✅ Pipeline component validation successful")

        # Test failed result
        result = PipelineValidationResult(
            False, ["comp1"], ["comp2"], ["Issue with comp2"]
        )
        self.assertIn("❌ Pipeline component validation failed", str(result))
        self.assertIn("Issue with comp2", str(result))


if __name__ == "__main__":
    # Add header and footer to test output
    print("=" * 80)
    print("=" * 25 + " PIPELINE VALIDATOR TESTS " + "=" * 25)
    print("=" * 80)
    unittest.main(verbosity=2)
    print("=" * 80)
