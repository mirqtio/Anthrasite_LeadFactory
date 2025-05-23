#!/usr/bin/env python3
"""
Script to prepare the codebase for CI pipeline execution.
This script runs before CI tests to ensure that all tests will pass.
"""

import subprocess
import sys
from pathlib import Path


def fix_imports_with_ruff(directory):
    """Fix import sorting in all Python files in a directory using ruff."""
    try:
        subprocess.run(
            ["ruff", "check", "--select=I", "--fix", directory],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def format_with_black(directory):
    """Format Python files in a directory using black."""
    try:
        subprocess.run(
            ["black", directory, "--config", ".black.toml"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_flake8(directory):
    """Check Python files in a directory using flake8."""
    try:
        # Only check for serious errors
        subprocess.run(
            ["flake8", directory, "--count", "--select=E9,F63,F7,F82", "--show-source"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main function to prepare the codebase for CI pipeline execution."""
    # Get the project root directory
    project_root = Path(__file__).resolve().parent.parent

    # Directories to process (excluding tests)
    directories_to_process = [
        project_root / "utils",
        project_root / "bin",
        project_root / "scripts",
    ]

    success = True

    # Fix imports with ruff
    for directory in directories_to_process:
        if Path(directory).exists() and not fix_imports_with_ruff(str(directory)):
            success = False

    # Format code with black
    for directory in directories_to_process:
        if Path(directory).exists() and not format_with_black(str(directory)):
            success = False

    # Check code with flake8
    for directory in directories_to_process:
        if Path(directory).exists() and not check_flake8(str(directory)):
            success = False

    if success:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
