#!/usr/bin/env python3
"""
Script to prepare the codebase for CI pipeline execution.
This script runs before CI tests to ensure that all tests will pass.
"""

import os
import subprocess
import sys


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
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Directories to process (excluding tests)
    directories_to_process = [
        os.path.join(project_root, "utils"),
        os.path.join(project_root, "bin"),
        os.path.join(project_root, "scripts"),
    ]

    success = True

    # Fix imports with ruff
    for directory in directories_to_process:
        if os.path.exists(directory) and not fix_imports_with_ruff(directory):
            success = False

    # Format code with black
    for directory in directories_to_process:
        if os.path.exists(directory) and not format_with_black(directory):
            success = False

    # Check code with flake8
    for directory in directories_to_process:
        if os.path.exists(directory) and not check_flake8(directory):
            success = False

    if success:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
