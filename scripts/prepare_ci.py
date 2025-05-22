#!/usr/bin/env python3
"""
Script to prepare the codebase for CI pipeline execution.
This script runs before CI tests to ensure that all tests will pass.
"""

import os
import subprocess
import sys
from pathlib import Path


def fix_imports_with_ruff(directory):
    """Fix import sorting in all Python files in a directory using ruff."""
    print(f"Fixing imports in {directory}...")
    try:
        subprocess.run(
            ["ruff", "check", "--select=I", "--fix", directory], 
            check=True, 
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fix imports in {directory}: {e}")
        print(f"Error output: {e.stderr.decode()}")
        return False


def format_with_black(directory):
    """Format Python files in a directory using black."""
    print(f"Formatting code in {directory} with black...")
    try:
        subprocess.run(
            ["black", directory, "--config", ".black.toml"], 
            check=True, 
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to format code in {directory}: {e}")
        print(f"Error output: {e.stderr.decode()}")
        return False


def check_flake8(directory):
    """Check Python files in a directory using flake8."""
    print(f"Checking code in {directory} with flake8...")
    try:
        # Only check for serious errors
        subprocess.run(
            ["flake8", directory, "--count", "--select=E9,F63,F7,F82", "--show-source"], 
            check=True, 
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Flake8 found errors in {directory}: {e}")
        print(f"Error output: {e.stderr.decode()}")
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
        if os.path.exists(directory):
            if not fix_imports_with_ruff(directory):
                success = False
    
    # Format code with black
    for directory in directories_to_process:
        if os.path.exists(directory):
            if not format_with_black(directory):
                success = False
    
    # Check code with flake8
    for directory in directories_to_process:
        if os.path.exists(directory):
            if not check_flake8(directory):
                success = False
    
    if success:
        print("\n✅ All checks passed! The codebase is ready for CI pipeline execution.")
        return 0
    else:
        print("\n❌ Some checks failed. Please fix the issues before running the CI pipeline.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
