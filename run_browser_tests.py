#!/usr/bin/env python3
"""
Browser test runner for LeadFactory UI components.

This script runs browser-based BDD tests using Playwright and pytest-bdd.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import playwright
        import pytest
        from pytest_bdd import scenario

        print("✓ All required dependencies are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please run: pip install playwright pytest pytest-bdd")
        return False


def install_browsers():
    """Install Playwright browsers if needed."""
    print("Checking browser installation...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✓ Browsers are ready")
            return True
        else:
            print(f"✗ Browser installation failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error installing browsers: {e}")
        return False


def run_browser_tests(test_path=None, headless=True, verbose=False):
    """Run browser-based BDD tests."""
    # Set up environment variables
    env = os.environ.copy()
    env["HEADLESS"] = "true" if headless else "false"
    env["BROWSER_TEST_MODE"] = "True"

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Add test path
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("tests/browser/")

    # Add pytest options
    cmd.extend(["-v" if verbose else "-q", "--tb=short", "--color=yes", "--no-header"])

    # Add BDD-specific options
    cmd.extend(
        [
            "--gherkin-terminal-reporter",
            "--cucumberjson=test_results/browser_test_results.json",
        ]
    )

    print(f"Running command: {' '.join(cmd)}")
    print(f"Headless mode: {headless}")
    print("-" * 50)

    # Create results directory
    os.makedirs("test_results", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)

    # Run tests
    try:
        result = subprocess.run(cmd, env=env)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n✗ Tests interrupted by user")
        return False
    except Exception as e:
        print(f"✗ Error running tests: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run browser-based BDD tests")
    parser.add_argument(
        "--test", "-t", help="Specific test file or directory to run", default=None
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run tests in headed mode (visible browser)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only check dependencies and install browsers",
    )

    args = parser.parse_args()

    print("LeadFactory Browser Test Runner")
    print("=" * 50)

    # Check dependencies
    if not check_dependencies():
        return 1

    # Install browsers
    if not install_browsers():
        return 1

    if args.setup_only:
        print("✓ Setup complete")
        return 0

    # Run tests
    success = run_browser_tests(
        test_path=args.test, headless=not args.headed, verbose=args.verbose
    )

    if success:
        print("\n✓ All browser tests passed!")
        return 0
    else:
        print("\n✗ Some browser tests failed")
        print("Check test_results/ for detailed results")
        print("Check screenshots/ for failure screenshots")
        return 1


if __name__ == "__main__":
    sys.exit(main())
