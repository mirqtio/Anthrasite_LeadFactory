#!/usr/bin/env python3
"""
Focused test runner for IP rotation tests only.
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that we can import the required modules."""
    try:
        from leadfactory.services.bounce_monitor import BounceRateMonitor
        from leadfactory.services.ip_rotation import IPRotationService
        from leadfactory.services.threshold_detector import ThresholdDetector

        return True
    except ImportError:
        return False


def run_specific_tests():
    """Run only our new IP rotation tests."""

    # Test files we want to run
    test_files = [
        "tests/unit/test_ip_rotation_unit.py",
        "tests/e2e/test_ip_rotation_e2e.py",
        "tests/integration/test_ip_rotation_integration.py",
    ]

    results = {}

    for test_file in test_files:
        if not Path(test_file).exists():
            continue

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_file,
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
        ]

        result = subprocess.run(cmd, cwd=project_root)
        results[test_file] = result.returncode == 0

        if result.returncode == 0:
            pass
        else:
            pass

    return results


def run_bdd_test():
    """Run BDD test for IP rotation."""

    # Set PYTHONPATH for behave
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    cmd = [sys.executable, "-m", "behave", "tests/features/ip_rotation.feature", "-v"]

    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode == 0


def main():
    """Run focused IP rotation test suite."""

    # Test imports first
    if not test_imports():
        return 1

    # Run specific tests
    test_results = run_specific_tests()

    # Run BDD test
    try:
        bdd_result = run_bdd_test()
        test_results["BDD"] = bdd_result
    except Exception:
        test_results["BDD"] = False

    # Print summary

    for _test_name, _passed in test_results.items():
        pass

    all_passed = all(test_results.values())

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
