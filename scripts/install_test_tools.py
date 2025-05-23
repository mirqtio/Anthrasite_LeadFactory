#!/usr/bin/env python3
"""
Install Test Tools

This script installs the necessary dependencies for the test status tracker
and other test-related tools.

Usage:
    python scripts/install_test_tools.py
"""

import contextlib
import subprocess
import sys
from pathlib import Path


def main():

    # Required packages
    packages = ["matplotlib", "numpy", "pytest-json-report", "pytest-cov"]

    # Install packages
    try:
        subprocess.run([sys.executable, "-m", "pip", "install"] + packages, check=True)
    except subprocess.CalledProcessError:
        return 1

    # Make test status tracker executable
    tracker_path = Path(__file__).parent / "test_status_tracker.py"
    if tracker_path.exists():
        with contextlib.suppress(Exception):
            tracker_path.chmod(0o755)

    return 0


if __name__ == "__main__":
    sys.exit(main())
