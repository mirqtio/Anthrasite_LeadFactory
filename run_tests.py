#!/usr/bin/env python3
"""
Test runner for LeadFactory IP/Subuser Rotation System

This script properly sets up the Python path and runs all tests
for the comprehensive testing suite.
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_unit_tests():
    """Run unit tests using pytest."""

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/test_ip_rotation_unit.py",
        "-v",
        "--tb=short",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_integration_tests():
    """Run integration tests using pytest."""

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_ip_rotation_integration.py",
        "-v",
        "--tb=short",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_e2e_tests():
    """Run end-to-end tests using pytest."""

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/e2e/test_ip_rotation_e2e.py",
        "-v",
        "--tb=short",
    ]

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_bdd_tests():
    """Run BDD tests using behave."""

    # Set PYTHONPATH for behave
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    cmd = [sys.executable, "-m", "behave", "tests/features/ip_rotation.feature", "-v"]

    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode == 0


def run_all_existing_tests():
    """Run all existing project tests to ensure no regressions."""

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--ignore=tests/e2e/test_ip_rotation_e2e.py",  # Skip our new e2e test to avoid duplicates
    ]

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def main():
    """Run comprehensive test suite."""

    results = {}

    # Run each test suite
    try:
        results["unit"] = run_unit_tests()
    except Exception:
        results["unit"] = False

    try:
        results["integration"] = run_integration_tests()
    except Exception:
        results["integration"] = False

    try:
        results["e2e"] = run_e2e_tests()
    except Exception:
        results["e2e"] = False

    try:
        results["bdd"] = run_bdd_tests()
    except Exception:
        results["bdd"] = False

    try:
        results["existing"] = run_all_existing_tests()
    except Exception:
        results["existing"] = False

    # Print summary

    for _test_type, _passed in results.items():
        pass

    all_passed = all(results.values())

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
