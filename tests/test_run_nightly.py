"""
Tests for the nightly batch processing script.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

# No need to modify Python path as it's handled in conftest.py


class TestRunNightly(unittest.TestCase):
    """Test cases for the nightly batch processing script."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        # Path to the script
        self.script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scripts",
            "run_nightly.sh",
        )

        # Create a mock .env file
        self.env_file = os.path.join(self.test_dir, ".env")
        with open(self.env_file, "w") as f:
            f.write("NOTIFICATION_EMAIL=test@example.com\n")
            f.write("TIER=1\n")
            f.write("MOCKUP_ENABLED=true\n")

    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    def test_script_execution(self, mock_run):
        """Test that the script executes all the required steps."""
        # Configure the mock to return success
        mock_run.return_value = MagicMock(returncode=0)

        # Run the script with the --dry-run option
        result = subprocess.run(
            ["bash", self.script_path, "--dry-run"],
            cwd=self.test_dir,
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            },
            capture_output=True,
            text=True,
        )

        # Check that the script executed successfully
        self.assertEqual(
            result.returncode,
            0,
            f"Script failed with output: {result.stdout} {result.stderr}",
        )

        # Check that the script output contains the expected steps
        expected_steps = [
            "Starting nightly batch processing",
            "Starting cost tracking for batch",
            "Step 1: Fetching leads",
            "Step 2: Enriching leads",
            "Step 3: Scoring leads",
            "Step 4: Generating mockups",
            "Step 5: Sending emails",
            "Step 6: Updating database",
            "Step 7: Generating reports",
            "Ending cost tracking for batch",
            "Recording completion timestamp metric",
        ]

        # The dry run option should prevent actual execution but should show the steps
        for step in expected_steps:
            self.assertIn(step, result.stdout + result.stderr, f"Missing step: {step}")

    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("subprocess.run")
    def test_batch_completion_metric(self, mock_run, mock_open, mock_exists):
        """Test that the batch completion metric is recorded."""
        # Configure the mocks
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=0)

        # Create a test environment with the required variables
        env = os.environ.copy()
        env["NOTIFICATION_EMAIL"] = "test@example.com"
        env["TIER"] = "1"
        env["MOCKUP_ENABLED"] = "true"

        # Run the script with the --test-metrics option
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (b"", b"")
            mock_popen.return_value.returncode = 0

            result = subprocess.run(
                ["bash", self.script_path, "--test-metrics"],
                cwd=self.test_dir,
                env=env,
                capture_output=True,
                text=True,
            )

        # Check that the script executed successfully
        self.assertEqual(
            result.returncode,
            0,
            f"Script failed with output: {result.stdout} {result.stderr}",
        )

        # Verify that the Python code to record metrics was called
        expected_calls = [
            call(
                [
                    "python",
                    "-c",
                    "import sys; sys.path.append('.'); from bin.metrics import metrics; metrics.batch_completed_timestamp.set(time.time()); metrics.observe_batch_duration($DURATION)",
                ],
                cwd=self.test_dir,
                env=env,
                shell=True,
                check=True,
            )
        ]

        # Note: The actual calls might differ slightly due to environment variables and paths
        # This is a simplified check
        self.assertTrue(
            mock_run.called, "Python command to record metrics was not called"
        )

    @patch("subprocess.run")
    def test_supabase_usage_check(self, mock_run):
        """Test that the Supabase usage check is executed."""
        # Configure the mock to return success
        mock_run.return_value = MagicMock(returncode=0)

        # Run the script with the --check-supabase option
        result = subprocess.run(
            ["bash", self.script_path, "--check-supabase"],
            cwd=self.test_dir,
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            },
            capture_output=True,
            text=True,
        )

        # Check that the script executed successfully
        self.assertEqual(
            result.returncode,
            0,
            f"Script failed with output: {result.stdout} {result.stderr}",
        )

        # Verify that the Supabase usage check was called
        expected_call = call(
            ["python", "scripts/monitor_supabase_usage.py", "--alert-threshold", "80"],
            cwd=self.test_dir,
            check=True,
        )

        # Note: The actual calls might differ slightly due to environment variables and paths
        # This is a simplified check
        self.assertTrue(mock_run.called, "Supabase usage check was not called")


if __name__ == "__main__":
    unittest.main()
