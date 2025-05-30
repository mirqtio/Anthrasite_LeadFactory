#!/usr/bin/env python3
"""
Healthcheck script for Task #5: Consolidate and Enhance Test Suite.
Verifies that the test suite has been properly consolidated and structured.
"""

import contextlib
import os
import subprocess
import sys
from pathlib import Path


def check_directory_exists(path, description):
    """Check if a directory exists and print the status."""
    return bool(os.path.exists(path) and os.path.isdir(path))


def check_file_exists(filepath, description):
    """Check if a file exists and print the status."""
    return bool(os.path.exists(filepath))


def check_test_directory_structure():
    """Check that the test directory structure is as expected."""
    # Define the expected directory structure
    expected_dirs = [
        ("tests/unit", "Unit tests directory"),
        ("tests/integration", "Integration tests directory"),
        ("tests/bdd", "BDD tests directory"),
        ("tests/bdd/features", "BDD features directory"),
        ("tests/bdd/step_defs", "BDD step definitions directory"),
        ("tests/utils", "Test utilities directory"),
    ]

    # Check each directory
    results = []
    for path, description in expected_dirs:
        results.append(check_directory_exists(path, description))

    return all(results)


def check_consolidated_test_files():
    """Check that the test files have been consolidated properly."""
    # Define the expected consolidated test files
    expected_files = [
        ("tests/unit/test_dedupe.py", "Consolidated unit tests for dedupe module"),
        (
            "tests/bdd/step_defs/test_dedupe_steps.py",
            "BDD step definitions for dedupe module",
        ),
        (
            "tests/bdd/features/deduplication.feature",
            "BDD feature file for deduplication",
        ),
        (
            "tests/integration/test_pipeline_stages.py",
            "Integration tests for pipeline stages",
        ),
        ("tests/utils/test_io.py", "Utility tests for IO functions"),
        ("tests/conftest.py", "Shared test fixtures"),
    ]

    # Check each file
    results = []
    for path, description in expected_files:
        results.append(check_file_exists(path, description))

    return all(results)


def check_old_test_files_removed():
    """Check that the old test files have been removed."""
    # Define the old test files that should be removed
    old_files = [
        "tests/test_dedupe_new.py",
        "tests/test_dedupe_fixed.py",
        "tests/test_dedupe_simple.py",
        "tests/test_dedupe_unit.py",
        "tests/test_mockup 3.py",
    ]

    # Check that each file is gone
    all_removed = True
    for file in old_files:
        if os.path.exists(file):
            all_removed = False
        else:
            pass

    return all_removed


def check_test_coverage():
    """Check test coverage for the dedupe module."""
    try:
        # Run pytest with coverage for the dedupe module
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/unit/test_dedupe.py",
                "--cov=bin.dedupe",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False

        # Check coverage from output
        coverage_line = next(
            (
                line
                for line in result.stdout.split("\n")
                if "TOTAL" in line and "%" in line
            ),
            None,
        )

        if not coverage_line:
            return False

        # Extract coverage percentage
        try:
            coverage_parts = coverage_line.split()
            coverage_percent = float(coverage_parts[-1].rstrip("%"))

            # Warn if coverage is low
            if coverage_percent < 70:
                pass

            return True
        except (IndexError, ValueError):
            return False

    except Exception:
        return False


def check_no_skipped_tests():
    """Check that there are no skipped tests in the test suite."""
    try:
        # Run pytest with verbose output to see skipped tests
        result = subprocess.run(
            ["python", "-m", "pytest", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Count skipped tests
        skipped_count = result.stdout.count("SKIPPED")

        if skipped_count > 0:

            # Extract skipped test info
            for line in result.stdout.split("\n"):
                if "SKIPPED" in line:
                    pass

            return False
        else:
            return True

    except Exception:
        return False


def check_bdd_tests():
    """Check that BDD tests are properly implemented."""
    try:
        # Run pytest-bdd tests
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/bdd", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False

        # Count passing tests
        passing_count = result.stdout.count("PASSED")

        return passing_count > 0

    except Exception:
        return False


def main():
    """Run all healthchecks and return exit code based on results."""

    checks = [
        check_test_directory_structure(),
        check_consolidated_test_files(),
        check_old_test_files_removed(),
    ]

    # Optional checks that may fail if dependencies are not installed
    with contextlib.suppress(Exception):
        checks.append(check_test_coverage())

    with contextlib.suppress(Exception):
        checks.append(check_no_skipped_tests())

    with contextlib.suppress(Exception):
        checks.append(check_bdd_tests())

    success = all(checks)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
