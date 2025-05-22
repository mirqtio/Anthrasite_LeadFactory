#!/usr/bin/env python3
"""
Format specific files that are known to have formatting issues in the CI pipeline.
This script is designed to be run in the CI pipeline to ensure consistent formatting.

This script precisely matches the formatting requirements of the CI pipeline.
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

# Additional files that might need formatting
ADDITIONAL_DIRS = [
    "bin",
    "utils",
    "scripts",
    "tests",
]


def main():
    """Format specific files with known formatting issues."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # First, fix the specific problem files
    print(f"Formatting {len(PROBLEM_FILES)} specific files with known formatting issues...")
    format_problem_files(project_root)

    # Then run a comprehensive check on all Python files
    print("\nRunning comprehensive formatting check on all Python files...")
    check_all_files(project_root)


def format_problem_files(project_root):
    """Format specific files with known formatting issues."""
    for file_path in PROBLEM_FILES:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"Formatting {file_path}...")

            # Apply specific fixes based on the file
            if "raw_data_retention.py" in file_path:
                fix_raw_data_retention(full_path)
            elif "cost_tracker.py" in file_path:
                fix_cost_tracker(full_path)
            elif "website_scraper.py" in file_path:
                fix_website_scraper(full_path)

            # Then run Black with the exact CI configuration
            cmd = ["black", "--config", ".black.toml", full_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout.strip() or "No changes made by Black")
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        else:
            print(f"Warning: File {file_path} does not exist")


def check_all_files(project_root):
    """Run formatting checks on all Python files."""
    # Run Black on all Python files
    for directory in ADDITIONAL_DIRS:
        dir_path = os.path.join(project_root, directory)
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"\nChecking files in {directory}/...")
            cmd = ["black", "--config", ".black.toml", dir_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout.strip() or "No changes made by Black")
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            # Run isort on the directory
            print(f"Running isort on {directory}/...")
            cmd = ["isort", dir_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout.strip() or "No changes made by isort")
            if result.stderr:
                print(result.stderr, file=sys.stderr)


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


def fix_cost_tracker(file_path):
    """Fix specific formatting issues in cost_tracker.py."""
    with open(file_path, "r") as f:
        content = f.read()

    # Fix the percent_used calculations
    content = content.replace(
        '"percent_used": (\n                (daily_cost / DAILY_BUDGET) * 100 if DAILY_BUDGET > 0 else 0\n            ),',
        '"percent_used": (daily_cost / DAILY_BUDGET) * 100 if DAILY_BUDGET > 0 else 0,',
    )

    content = content.replace(
        '"percent_used": (\n                (monthly_cost / MONTHLY_BUDGET) * 100 if MONTHLY_BUDGET > 0 else 0\n            ),',
        '"percent_used": (monthly_cost / MONTHLY_BUDGET) * 100 if MONTHLY_BUDGET > 0 else 0,',
    )

    # Fix the any_threshold_exceeded line
    content = content.replace(
        '"any_threshold_exceeded": daily_threshold_exceeded\n        or monthly_threshold_exceeded,',
        '"any_threshold_exceeded": daily_threshold_exceeded or monthly_threshold_exceeded,',
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed specific formatting issues in {file_path}")


def fix_website_scraper(file_path):
    """Fix specific formatting issues in website_scraper.py."""
    with open(file_path, "r") as f:
        content = f.read()

    # Fix the logger.info statements
    content = content.replace(
        'logger.info(\n            f"Found {len(businesses)} businesses with websites but no HTML stored"\n        )',
        'logger.info(f"Found {len(businesses)} businesses with websites but no HTML stored")',
    )

    content = content.replace(
        'logger.info(\n            f"Finished processing {processed_count} businesses, {success_count} successful"\n        )',
        'logger.info(f"Finished processing {processed_count} businesses, {success_count} successful")',
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed specific formatting issues in {file_path}")


if __name__ == "__main__":
    main()
