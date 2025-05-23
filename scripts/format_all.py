#!/usr/bin/env python3
"""
Format all Python files in the project using Black.
"""

import os
import subprocess
import sys
from pathlib import Path

# Directories to format
DIRS_TO_FORMAT = [
    "bin",
    "utils",
    "scripts",
    "tests",
]

# Directories to exclude
EXCLUDE_DIRS = [
    "venv",
    ".venv",
    "env",
    ".env",
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "tasks",
    ".ruff_cache",
]


def find_python_files(base_dir):
    """Find all Python files in the given directory."""
    python_files = []
    for root, dirs, files in os.walk(base_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        # Add Python files
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    return python_files


def format_specific_files():
    """Format specific files that are known to have formatting issues."""
    problem_files = [
        "utils/raw_data_retention.py",
        "utils/cost_tracker.py",
        "utils/website_scraper.py",
    ]

    print(f"Formatting {len(problem_files)} specific files with known formatting issues...")

    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # Format each problem file individually
    for file_path in problem_files:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"Formatting {file_path}...")
            cmd = ["black", full_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        else:
            print(f"Warning: File {file_path} does not exist")


def main():
    """Run Black on all Python files in the project."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # First, format specific problem files
    format_specific_files()

    # Then format all Python files
    python_files = []
    for dir_to_format in DIRS_TO_FORMAT:
        python_files.extend(find_python_files(dir_to_format))

    # Remove duplicates
    python_files = list(set(python_files))
    python_files.sort()  # Sort for consistent output

    # Print summary
    print(f"Found {len(python_files)} Python files to format")

    # Build the command
    cmd = ["black"]
    cmd.extend(python_files)

    # Run Black
    print(f"Running Black on {len(python_files)} files...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print the output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Return the exit code
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
