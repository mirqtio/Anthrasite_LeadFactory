#!/usr/bin/env python3
"""
Unit tests for the E2E Pipeline Execution and Resolution Loop
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.pipeline_executor import (
    ExecutionStatus,
    FailureCategory,
    PipelineExecutor,
    PipelineStage,
)


class TestPipelineExecutor(unittest.TestCase):
    """Test cases for the PipelineExecutor class"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary files for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create mock environment file
        self.env_file = self.temp_path / ".env.e2e.test"
        with open(self.env_file, "w") as f:
            f.write(
                "DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory\n"  # pragma: allowlist secret
            )
            f.write("OPENAI_API_KEY=sk-test123456\n")
            f.write("GOOGLE_MAPS_API_KEY=test-api-key\n")
            f.write("SENDGRID_API_KEY=SG.test-key\n")
            f.write("EMAIL_OVERRIDE=test@example.com\n")
            f.write("MOCKUP_ENABLED=true\n")
            f.write("E2E_MODE=true\n")

        # Create mock known issues file
        self.known_issues_file = self.temp_path / "known_issues.json"
        known_issues = {
            "environment_issues": {
                "missing_api_key": {
                    "pattern": "Missing required variable: (?P<key>.+)",
                    "resolution": "Add the missing variable to your .env.e2e file",
                    "category": FailureCategory.ENVIRONMENT,
                }
            }
        }
        with open(self.known_issues_file, "w") as f:
            json.dump(known_issues, f)

        # Create mock history file
        self.history_file = self.temp_path / "execution_history.json"
        history = []
        with open(self.history_file, "w") as f:
            json.dump(history, f)

        # Create mock pipeline executor with patched file paths
        with patch("scripts.e2e.pipeline_executor.project_root", self.temp_path):
            self.executor = PipelineExecutor(
                env_file=str(self.env_file), max_retries=1, resolution_mode=True
            )

            # Override file paths with our test paths
            self.executor.known_issues_file = self.known_issues_file
            self.executor.history_file = self.history_file

    def tearDown(self):
        """Clean up after tests"""
        self.temp_dir.cleanup()

    @patch("scripts.e2e.pipeline_executor.PreflightCheck")
    def test_run_preflight_check_success(self, mock_preflight):
        """Test successful preflight check"""
        # Configure mock
        mock_preflight_instance = mock_preflight.return_value
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.issues = []
        mock_preflight_instance.run.return_value = mock_result

        # Run preflight check
        result = self.executor.run_preflight_check()

        # Assertions
        self.assertTrue(result)
        self.assertEqual(
            self.executor.stages["preflight"].status, ExecutionStatus.SUCCESS
        )

        # Verify mock was called correctly
        mock_preflight.assert_called_once_with(env_file=str(self.env_file))
        mock_preflight_instance.run.assert_called_once()

    @patch("scripts.e2e.pipeline_executor.PreflightCheck")
    def test_run_preflight_check_failure(self, mock_preflight):
        """Test failed preflight check"""
        # Configure mock
        mock_preflight_instance = mock_preflight.return_value
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.issues = ["Missing required variable: TEST_VAR"]
        mock_preflight_instance.run.return_value = mock_result

        # Run preflight check
        result = self.executor.run_preflight_check()

        # Assertions
        self.assertFalse(result)
        self.assertEqual(
            self.executor.stages["preflight"].status, ExecutionStatus.FAILURE
        )
        self.assertEqual(len(self.executor.results["failures"]), 1)
        self.assertEqual(
            self.executor.results["failures"][0]["category"],
            FailureCategory.ENVIRONMENT,
        )

        # Verify mock was called correctly
        mock_preflight.assert_called_once_with(env_file=str(self.env_file))
        mock_preflight_instance.run.assert_called_once()

    @patch("subprocess.run")
    @patch("scripts.e2e.pipeline_executor.PipelineExecutor.run_preflight_check")
    def test_execute_pipeline_preflight_failure(
        self, mock_preflight, mock_subprocess_run
    ):
        """Test pipeline execution aborted due to preflight failure"""
        # Configure mocks
        mock_preflight.return_value = False

        # Run pipeline
        result = self.executor.execute_pipeline()

        # Assertions
        self.assertFalse(result)
        self.assertEqual(self.executor.overall_status, ExecutionStatus.FAILURE)

        # Verify preflight was called but subprocess.run was not
        mock_preflight.assert_called_once()
        mock_subprocess_run.assert_not_called()

    @patch("subprocess.run")
    @patch("scripts.e2e.pipeline_executor.PipelineExecutor.run_preflight_check")
    def test_execute_pipeline_success(self, mock_preflight, mock_subprocess_run):
        """Test successful pipeline execution"""
        # Configure mocks
        mock_preflight.return_value = True

        # Configure subprocess.run to return success for all stages
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Test output"
        mock_process.stderr = ""
        mock_subprocess_run.return_value = mock_process

        # Run pipeline
        result = self.executor.execute_pipeline()

        # Assertions
        self.assertTrue(result)
        self.assertEqual(self.executor.overall_status, ExecutionStatus.SUCCESS)

        # Verify preflight was called and subprocess.run was called for each stage (except preflight)
        mock_preflight.assert_called_once()
        self.assertEqual(
            mock_subprocess_run.call_count, len(self.executor.stages) - 1
        )  # Minus preflight

        # Check all stages succeeded
        for stage_name, stage in self.executor.stages.items():
            if stage_name != "preflight":  # Preflight was mocked separately
                self.assertEqual(stage.status, ExecutionStatus.SUCCESS)

    @patch("subprocess.run")
    @patch("scripts.e2e.pipeline_executor.PipelineExecutor.run_preflight_check")
    def test_execute_pipeline_stage_failure(self, mock_preflight, mock_subprocess_run):
        """Test pipeline execution with stage failure"""
        # Configure mocks
        mock_preflight.return_value = True

        # Make one stage fail
        def mock_subprocess_side_effect(*args, **kwargs):
            stage_script = args[0][1]
            mock_process = MagicMock()

            # Make the scrape stage fail
            if "01_scrape.py" in stage_script:
                mock_process.returncode = 1
                mock_process.stdout = ""
                mock_process.stderr = "Test error"
            else:
                mock_process.returncode = 0
                mock_process.stdout = "Test output"
                mock_process.stderr = ""

            return mock_process

        mock_subprocess_run.side_effect = mock_subprocess_side_effect

        # Run pipeline
        result = self.executor.execute_pipeline()

        # Assertions
        self.assertFalse(result)
        self.assertEqual(self.executor.overall_status, ExecutionStatus.FAILURE)

        # Verify preflight was called
        mock_preflight.assert_called_once()

        # Check the scrape stage failed
        self.assertEqual(self.executor.stages["scrape"].status, ExecutionStatus.FAILURE)

        # Check dependent stages were skipped
        self.assertEqual(
            self.executor.stages["screenshot"].status, ExecutionStatus.SKIPPED
        )
        self.assertEqual(self.executor.stages["mockup"].status, ExecutionStatus.SKIPPED)

    def test_categorize_failure(self):
        """Test failure categorization"""
        # Test known issue matching
        error_message = "Missing required variable: TEST_API_KEY"
        failure_info = self.executor._categorize_failure("preflight", error_message)

        self.assertEqual(failure_info["category"], FailureCategory.ENVIRONMENT)
        self.assertEqual(failure_info["stage"], "preflight")
        self.assertEqual(failure_info["issue_type"], "environment_issues")
        self.assertEqual(failure_info["issue_name"], "missing_api_key")

        # Test heuristic categorization
        error_message = "API key validation failed"
        failure_info = self.executor._categorize_failure("api_test", error_message)

        self.assertEqual(failure_info["category"], FailureCategory.API)
        self.assertEqual(failure_info["stage"], "api_test")

        error_message = "Database connection failed"
        failure_info = self.executor._categorize_failure("db_test", error_message)

        self.assertEqual(failure_info["category"], FailureCategory.DATABASE)
        self.assertEqual(failure_info["stage"], "db_test")

        # Test unknown error
        error_message = "Some random error"
        failure_info = self.executor._categorize_failure("unknown", error_message)

        self.assertEqual(failure_info["category"], FailureCategory.UNKNOWN)
        self.assertEqual(failure_info["stage"], "unknown")

    @patch("scripts.e2e.pipeline_executor.PipelineExecutor._resolve_environment_issue")
    def test_attempt_resolution(self, mock_resolve):
        """Test resolution attempt"""
        # Configure mock
        mock_resolve.return_value = True

        # Create test failure
        failure = {
            "stage": "preflight",
            "category": FailureCategory.ENVIRONMENT,
            "message": "Missing required variable: TEST_API_KEY",
            "resolution": "Add the missing variable to your .env.e2e file",
            "timestamp": "2023-01-01T00:00:00",
        }

        # Attempt resolution
        result = self.executor._attempt_resolution([failure])

        # Assertions
        self.assertTrue(result)
        self.assertEqual(len(self.executor.results["resolution_attempts"]), 1)
        self.assertTrue(self.executor.results["resolution_attempts"][0]["success"])

        # Verify mock was called correctly
        mock_resolve.assert_called_once_with(failure)

        # Test with resolution failure
        mock_resolve.reset_mock()
        mock_resolve.return_value = False

        # Reset results
        self.executor.results["resolution_attempts"] = []

        # Attempt resolution
        result = self.executor._attempt_resolution([failure])

        # Assertions
        self.assertFalse(result)
        self.assertEqual(len(self.executor.results["resolution_attempts"]), 1)
        self.assertFalse(self.executor.results["resolution_attempts"][0]["success"])


if __name__ == "__main__":
    unittest.main()
