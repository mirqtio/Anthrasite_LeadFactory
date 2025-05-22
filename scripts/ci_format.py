#!/usr/bin/env python3
"""
Format specific files that are known to have formatting issues in the CI pipeline.
This script is designed to be run in the CI pipeline to ensure consistent formatting.
"""

import os
import subprocess
import sys
from pathlib import Path

# Files with known formatting issues
PROBLEM_FILES = [
    "utils/raw_data_retention.py",
    "utils/cost_tracker.py",
    "utils/website_scraper.py",
]


def main():
    """Format specific files with known formatting issues."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    print(
        f"Formatting {len(PROBLEM_FILES)} specific files with known formatting issues..."
    )

    # Format each problem file individually
    for file_path in PROBLEM_FILES:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"Formatting {file_path}...")

            # First, fix the HTML_STORAGE_DIR constant in raw_data_retention.py
            if "raw_data_retention.py" in file_path:
                fix_raw_data_retention(full_path)

            # Then run Black on the file
            cmd = ["black", full_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        else:
            print(f"Warning: File {file_path} does not exist")


def fix_raw_data_retention(file_path):
    """Fix specific formatting issues in raw_data_retention.py."""
    with open(file_path, "r") as f:
        content = f.read()

    # Fix the HTML_STORAGE_DIR constant
    content = content.replace(
        'HTML_STORAGE_DIR = os.path.join(\n    os.path.dirname(os.path.dirname(__file__)), "data", "html_storage"\n)',
        'HTML_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "html_storage")',
    )

    # Fix the compression_ratio calculation
    content = content.replace(
        "compression_ratio = (\n        (original_size - compressed_size) / original_size if original_size > 0 else 0\n    )",
        "compression_ratio = (original_size - compressed_size) / original_size if original_size > 0 else 0",
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed specific formatting issues in {file_path}")


if __name__ == "__main__":
    main()
