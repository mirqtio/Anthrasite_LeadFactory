#!/usr/bin/env python3
"""
Script to fix import sorting issues in Python files.
"""

import os
import subprocess
import sys


def fix_imports_in_file(file_path):
    """Fix import sorting in a single file using isort."""
    try:
        subprocess.run(["isort", file_path], check=True)
        print(f"✅ Fixed imports in {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fix imports in {file_path}: {e}")
        return False


def main():
    """Main function to fix imports in all Python files."""
    # Files with import issues from the logs
    problem_files = [
        "utils/raw_data_retention.py",
        "utils/website_scraper.py",
        "utils/llm_logger.py",
        "utils/metrics.py",
    ]

    # Get the project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Fix imports in each file
    success = True
    for rel_path in problem_files:
        file_path = os.path.join(project_root, rel_path)
        if os.path.exists(file_path):
            if not fix_imports_in_file(file_path):
                success = False
        else:
            print(f"⚠️ File not found: {file_path}")
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
