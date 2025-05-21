#!/usr/bin/env python3
"""
Script to fix all PEP8 violations in the codebase.
This script:
1. Fixes f-string syntax errors
2. Removes unused variables
3. Applies Black formatting
4. Runs Ruff linter with fixes
"""

import os
import re
import subprocess
from pathlib import Path


def fix_fstring_syntax(file_path):
    """Fix f-string syntax errors in a file."""
    with open(file_path, "r") as f:
        content = f.read()

    # Pattern to match broken f-strings: f"......"
    pattern = r'f"([^"]*)" "(?:\s*f" )?([^"]*)"'
    replacement = r'f"\1\2"'

    # Apply the fix
    fixed_content = re.sub(pattern, replacement, content)

    # Only write if changes were made
    if fixed_content != content:
        print(f"Fixing f-string syntax in {file_path}")
        with open(file_path, "w") as f:
            f.write(fixed_content)
        return True
    return False


def fix_all_files():
    """Fix all Python files in the project."""
    project_root = Path(__file__).parent

    # Find all Python files
    python_files = []
    for root, _, files in os.walk(project_root):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    # Fix f-string syntax errors
    fixed_files = []
    for file_path in python_files:
        if fix_fstring_syntax(file_path):
            fixed_files.append(file_path)

    # Run Black formatter on all Python files
    print("\nRunning Black formatter...")
    subprocess.run(["black", "."], cwd=project_root)

    # Run Ruff linter with fixes
    print("\nRunning Ruff linter with fixes...")
    subprocess.run(["ruff", "check", ".", "--fix"], cwd=project_root)

    print(f"\nFixed f-string syntax in {len(fixed_files)} files.")
    print("All PEP8 violations should now be fixed.")


if __name__ == "__main__":
    fix_all_files()
