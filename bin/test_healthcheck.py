#!/usr/bin/env python3
"""
Healthcheck script for Task #5: Consolidate and Enhance Test Suite.
Verifies that the test suite has been properly consolidated and structured.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_directory_exists(path, description):
    """Check if a directory exists and print the status."""
    if os.path.exists(path) and os.path.isdir(path):
        print(f"✅ {description} exists at {path}")
        return True
    else:
        print(f"❌ ERROR: {description} not found at {path}")
        return False


def check_file_exists(filepath, description):
    """Check if a file exists and print the status."""
    if os.path.exists(filepath):
        print(f"✅ {description} exists at {filepath}")
        return True
    else:
        print(f"❌ ERROR: {description} not found at {filepath}")
        return False


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
            print(f"❌ ERROR: Old test file still exists: {file}")
            all_removed = False
        else:
            print(f"✅ Old test file successfully removed: {file}")

    return all_removed


def check_test_coverage():
    """Check test coverage for the dedupe module."""
    try:
        # Run pytest with coverage for the dedupe module
        print("Running test coverage check for dedupe module...")
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
            print(f"❌ ERROR: Tests failed with exit code {result.returncode}")
            print(f"Test output: {result.stdout}")
            print(f"Test errors: {result.stderr}")
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
            print("❌ ERROR: Could not find coverage information in test output")
            return False

        # Extract coverage percentage
        try:
            coverage_parts = coverage_line.split()
            coverage_percent = float(coverage_parts[-1].rstrip("%"))

            print(f"✅ Test coverage for dedupe module: {coverage_percent:.1f}%")

            # Warn if coverage is low
            if coverage_percent < 70:
                print(
                    f"⚠️ WARNING: Test coverage is below 70% ({coverage_percent:.1f}%)"
                )

            return True
        except (IndexError, ValueError) as e:
            print(f"❌ ERROR: Failed to parse coverage percentage: {e}")
            return False

    except Exception as e:
        print(f"❌ ERROR: Failed to run coverage test: {e}")
        return False


def check_no_skipped_tests():
    """Check that there are no skipped tests in the test suite."""
    try:
        # Run pytest with verbose output to see skipped tests
        print("Checking for skipped tests...")
        result = subprocess.run(
            ["python", "-m", "pytest", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Count skipped tests
        skipped_count = result.stdout.count("SKIPPED")

        if skipped_count > 0:
            print(f"❌ ERROR: Found {skipped_count} skipped tests")

            # Extract skipped test info
            for line in result.stdout.split("\n"):
                if "SKIPPED" in line:
                    print(f"  - {line.strip()}")

            return False
        else:
            print("✅ No skipped tests found")
            return True

    except Exception as e:
        print(f"❌ ERROR: Failed to check for skipped tests: {e}")
        return False


def check_bdd_tests():
    """Check that BDD tests are properly implemented."""
    try:
        # Run pytest-bdd tests
        print("Checking BDD tests...")
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/bdd", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"❌ ERROR: BDD tests failed with exit code {result.returncode}")
            print(f"Test output: {result.stdout}")
            print(f"Test errors: {result.stderr}")
            return False

        # Count passing tests
        passing_count = result.stdout.count("PASSED")

        if passing_count > 0:
            print(f"✅ {passing_count} BDD tests passing")
            return True
        else:
            print("❌ ERROR: No passing BDD tests found")
            return False

    except Exception as e:
        print(f"❌ ERROR: Failed to check BDD tests: {e}")
        return False


def main():
    """Run all healthchecks and return exit code based on results."""
    print("\n=== Test Suite Consolidation Healthcheck ===\n")

    checks = [
        check_test_directory_structure(),
        check_consolidated_test_files(),
        check_old_test_files_removed(),
    ]

    # Optional checks that may fail if dependencies are not installed
    try:
        checks.append(check_test_coverage())
    except Exception as e:
        print(f"⚠️ WARNING: Could not check test coverage: {e}")

    try:
        checks.append(check_no_skipped_tests())
    except Exception as e:
        print(f"⚠️ WARNING: Could not check for skipped tests: {e}")

    try:
        checks.append(check_bdd_tests())
    except Exception as e:
        print(f"⚠️ WARNING: Could not check BDD tests: {e}")

    success = all(checks)

    print("\n=== Healthcheck Summary ===")
    print(f"Total checks: {len(checks)}")
    print(f"Passed: {sum(1 for check in checks if check)}")
    print(f"Failed: {sum(1 for check in checks if not check)}")
    print(f"Status: {'PASSED' if success else 'FAILED'}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
