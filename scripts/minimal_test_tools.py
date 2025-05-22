#!/usr/bin/env python3
"""
Minimal Test Tools Installation

This script installs only the essential dependencies for running tests in CI.
It checks if packages are already installed and has robust error handling.

Usage:
    python scripts/minimal_test_tools.py
"""

import importlib
import logging
import subprocess
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def check_package_installed(package_name):
    """Check if a package is already installed."""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False


def install_package(package):
    """Install a single package with error handling."""
    try:
        logger.info(f"Installing {package}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing {package}: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return False


def main():
    """Main function with error handling."""
    logger.info("Installing essential test dependencies...")

    # Map package names to their import names
    packages = {"pytest-json-report": "pytest_json_report", "pytest-cov": "pytest_cov"}

    # Track installation success
    success_count = 0
    failure_count = 0

    # Install packages if not already installed
    for package, import_name in packages.items():
        if not check_package_installed(import_name):
            if install_package(package):
                success_count += 1
            else:
                failure_count += 1
        else:
            logger.info(f"{package} is already installed")
            success_count += 1

    # Report results
    if failure_count == 0:
        logger.info(
            f"Successfully installed/verified all {success_count} essential dependencies!"
        )
        return 0
    else:
        logger.warning(
            f"Installed/verified {success_count} packages, but {failure_count} failed"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
