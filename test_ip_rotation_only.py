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
        print("Testing imports...")
        from leadfactory.services.ip_rotation import IPRotationService

        print("✓ IPRotationService imported successfully")

        from leadfactory.services.bounce_monitor import BounceRateMonitor

        print("✓ BounceRateMonitor imported successfully")

        from leadfactory.services.threshold_detector import ThresholdDetector

        print("✓ ThresholdDetector imported successfully")

        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def run_specific_tests():
    """Run only our new IP rotation tests."""
    print("=" * 60)
    print("RUNNING IP ROTATION TESTS ONLY")
    print("=" * 60)

    # Test files we want to run
    test_files = [
        "tests/unit/test_ip_rotation_unit.py",
        "tests/e2e/test_ip_rotation_e2e.py",
        "tests/integration/test_ip_rotation_integration.py",
    ]

    results = {}

    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"⚠️  Test file {test_file} does not exist, skipping...")
            continue

        print(f"\n--- Running {test_file} ---")

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
            print(f"✓ {test_file} PASSED")
        else:
            print(f"✗ {test_file} FAILED")

    return results


def run_bdd_test():
    """Run BDD test for IP rotation."""
    print("=" * 60)
    print("RUNNING BDD TEST")
    print("=" * 60)

    # Set PYTHONPATH for behave
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    cmd = [sys.executable, "-m", "behave", "tests/features/ip_rotation.feature", "-v"]

    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode == 0


def main():
    """Run focused IP rotation test suite."""
    print("IP Rotation Testing Suite")
    print(f"Project root: {project_root}")
    print(f"Python version: {sys.version}")

    # Test imports first
    if not test_imports():
        print("❌ Import test failed - cannot proceed with tests")
        return 1

    # Run specific tests
    test_results = run_specific_tests()

    # Run BDD test
    try:
        bdd_result = run_bdd_test()
        test_results["BDD"] = bdd_result
    except Exception as e:
        print(f"BDD test failed with error: {e}")
        test_results["BDD"] = False

    # Print summary
    print("\n" + "=" * 60)
    print("IP ROTATION TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in test_results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{test_name:40} : {status}")

    all_passed = all(test_results.values())
    overall_status = "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"
    print(f"\nOVERALL: {overall_status}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
