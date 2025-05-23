#!/usr/bin/env python3
"""
Install Test Tools

This script installs the necessary dependencies for the test status tracker
and other test-related tools.

Usage:
    python scripts/install_test_tools.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    print("Installing test tools dependencies...")

    # Required packages
    packages = ["matplotlib", "numpy", "pytest-json-report", "pytest-cov"]

    # Install packages
    try:
        subprocess.run([sys.executable, "-m", "pip", "install"] + packages, check=True)
        print("Successfully installed test tools dependencies!")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return 1

    # Make test status tracker executable
    tracker_path = Path(__file__).parent / "test_status_tracker.py"
    if tracker_path.exists():
        try:
            tracker_path.chmod(0o755)
            print(f"Made {tracker_path} executable")
        except Exception as e:
            print(f"Error making {tracker_path} executable: {e}")

    print("\nTest tools are ready to use!")
    print("Example commands:")
    print("  python scripts/test_status_tracker.py --categorize --report")
    print(
        "  python scripts/test_status_tracker.py --run-tests --test-pattern='test_database*' --report"
    )
    print("  python scripts/test_status_tracker.py --visualize")

    return 0


if __name__ == "__main__":
    sys.exit(main())
