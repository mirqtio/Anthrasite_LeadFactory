#!/usr/bin/env python3
"""
Minimal Test Status Tracker

This script provides essential test tracking functionality without visualization
dependencies. It focuses on running tests and recording their status with robust
error handling.

Usage:
    python scripts/minimal_test_tracker.py [--run-tests] [--test-pattern=<pattern>] [--report]
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Constants
TEST_DIR = project_root / "tests"
STATUS_FILE = project_root / "test_results" / "test_status.json"
REPORT_FILE = project_root / "test_results" / "test_report.txt"

# Test status enum
STATUS_DISABLED = "disabled"
STATUS_FAILING = "failing"
STATUS_PASSING = "passing"
STATUS_SKIPPED = "skipped"


class MinimalTestTracker:
    """Minimal test tracker with essential functionality."""

    def __init__(self):
        """Initialize with error handling."""
        self.tests = {}
        self.load_status()

    def load_status(self):
        """Load existing test status from file with error handling."""
        try:
            if STATUS_FILE.exists():
                with open(STATUS_FILE) as f:
                    self.tests = json.load(f)
                logger.info(f"Loaded test status from {STATUS_FILE}")
            else:
                self.discover_tests()
        except Exception as e:
            logger.error(f"Error loading test status: {e}")
            self.discover_tests()

    def save_status(self):
        """Save current test status to file with error handling."""
        try:
            # Ensure directory exists
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

            with open(STATUS_FILE, "w") as f:
                json.dump(self.tests, f, indent=2)
            logger.info(f"Saved test status to {STATUS_FILE}")
        except Exception as e:
            logger.error(f"Error saving test status: {e}")

    def discover_tests(self):
        """Discover all tests in the test directory with error handling."""
        logger.info("Discovering tests...")

        try:
            # Find all test files
            test_files = list(TEST_DIR.glob("test_*.py"))
            test_files.extend(TEST_DIR.glob("**/test_*.py"))

            # Extract test functions from files
            for test_file in test_files:
                try:
                    rel_path = test_file.relative_to(project_root)
                    with open(test_file) as f:
                        content = f.read()

                    # Find test functions (def test_*)
                    test_funcs = re.findall(r"def\s+(test_\w+)\s*\(", content)

                    # Add each test to our dictionary
                    for func in test_funcs:
                        test_id = f"{rel_path}::{func}"
                        if test_id not in self.tests:
                            self.tests[test_id] = {
                                "file": str(rel_path),
                                "function": func,
                                "status": STATUS_DISABLED,  # All tests are initially disabled in CI
                                "last_run": None,
                                "error_message": None,
                            }
                except Exception as e:
                    logger.error(f"Error processing test file {test_file}: {e}")

            logger.info(f"Discovered {len(self.tests)} tests")
            self.save_status()
        except Exception as e:
            logger.error(f"Error discovering tests: {e}")

    def run_tests(self, test_pattern=None, ci_mode=False):
        """Run tests and update their status with error handling."""
        logger.info(f"Running tests with pattern: {test_pattern or 'all'}")

        try:
            # Create test results directory
            os.makedirs(project_root / "test_results", exist_ok=True)

            # Build pytest command
            pytest_cmd = ["pytest"]

            # Add JSON report if available
            try:
                import pytest_json_report

                pytest_cmd.extend(["--json-report", "--json-report-file=test_results/report.json"])
            except ImportError:
                logger.warning("pytest-json-report not available, will use exit code only")

            # Add coverage if available
            try:
                import pytest_cov

                pytest_cmd.extend(["--cov=bin", "--cov=utils", "--cov-report=term"])
            except ImportError:
                logger.warning("pytest-cov not available, skipping coverage")

            # Add test pattern if provided
            if test_pattern:
                pytest_cmd.append(test_pattern)

            # Add CI-specific options
            if ci_mode:
                pytest_cmd.extend(["-v", "--tb=native"])

            # Run pytest
            logger.info(f"Running command: {' '.join(pytest_cmd)}")
            start_time = time.time()

            result = subprocess.run(pytest_cmd, cwd=project_root, capture_output=True, text=True)

            duration = time.time() - start_time

            # Process results
            report_path = project_root / "test_results" / "report.json"
            if report_path.exists():
                try:
                    with open(report_path) as f:
                        report = json.load(f)

                    # Update test status based on report
                    for test_id, test_info in report.get("tests", {}).items():
                        if test_id in self.tests:
                            if test_info.get("outcome") == "passed":
                                self.tests[test_id]["status"] = STATUS_PASSING
                            elif test_info.get("outcome") == "skipped":
                                self.tests[test_id]["status"] = STATUS_SKIPPED
                            else:
                                self.tests[test_id]["status"] = STATUS_FAILING
                                self.tests[test_id]["error_message"] = test_info.get("call", {}).get("longrepr", "")

                            self.tests[test_id]["last_run"] = datetime.now().isoformat()
                except Exception as e:
                    logger.error(f"Error processing test report: {e}")
            else:
                logger.warning("No JSON report found, using exit code only")
                # If no report, use exit code to determine overall success/failure
                if result.returncode == 0:
                    logger.info("All tests passed based on exit code")
                else:
                    logger.warning(f"Some tests failed (exit code {result.returncode})")

            # Save updated status
            self.save_status()

            logger.info(f"Test run complete. Exit code: {result.returncode}")
            logger.info(f"Duration: {duration:.2f} seconds")

            # Save stdout/stderr for debugging
            stdout_path = project_root / "test_results" / "pytest_stdout.txt"
            stderr_path = project_root / "test_results" / "pytest_stderr.txt"

            try:
                with open(stdout_path, "w") as f:
                    f.write(result.stdout)
                with open(stderr_path, "w") as f:
                    f.write(result.stderr)
            except Exception as e:
                logger.error(f"Error saving pytest output: {e}")

            return result.returncode
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return 1

    def generate_report(self, output_file=None):
        """Generate a simple report of test status with error handling."""
        try:
            # Count tests by status
            status_counts = defaultdict(int)
            for test_info in self.tests.values():
                status_counts[test_info["status"]] += 1

            # Generate report
            report_lines = [
                "===== TEST STATUS REPORT =====",
                f"Generated: {datetime.now().isoformat()}",
                f"Total tests: {len(self.tests)}",
                f"Passing: {status_counts[STATUS_PASSING]}",
                f"Failing: {status_counts[STATUS_FAILING]}",
                f"Skipped: {status_counts[STATUS_SKIPPED]}",
                f"Disabled: {status_counts[STATUS_DISABLED]}",
                "",
                "===== FAILING TESTS =====",
            ]

            # Add failing tests with error messages
            failing_tests = [
                (test_id, test_info)
                for test_id, test_info in self.tests.items()
                if test_info["status"] == STATUS_FAILING
            ]

            if failing_tests:
                for test_id, test_info in failing_tests:
                    report_lines.append(f"- {test_id}")
                    error_msg = test_info.get("error_message", "")
                    if error_msg:
                        # Add first line of error message
                        first_line = error_msg.split("\n")[0] if error_msg else ""
                        report_lines.append(f"  Error: {first_line}")
            else:
                report_lines.append("No failing tests!")

            # Write report
            report_text = "\n".join(report_lines)

            output_path = Path(output_file) if output_file else REPORT_FILE

            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                f.write(report_text)

            logger.info(f"Report generated: {output_path}")

            return report_text
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Error generating report: {e}"


def main():
    """Main function with error handling."""
    try:
        parser = argparse.ArgumentParser(description="Minimal Test Status Tracker")
        parser.add_argument("--run-tests", action="store_true", help="Run tests and record their status")
        parser.add_argument(
            "--test-pattern",
            type=str,
            help="Pattern to filter tests (e.g., 'test_database*')",
        )
        parser.add_argument(
            "--ci-mode",
            action="store_true",
            help="Run in CI mode with specific settings",
        )
        parser.add_argument("--report", action="store_true", help="Generate a status report")
        parser.add_argument("--output", type=str, help="Output file for the report")

        args = parser.parse_args()

        tracker = MinimalTestTracker()

        if args.run_tests:
            tracker.run_tests(test_pattern=args.test_pattern, ci_mode=args.ci_mode)

        if args.report or (not args.run_tests):
            tracker.generate_report(output_file=args.output)

        return 0
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
