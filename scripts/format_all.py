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


def main():
    """Run Black on all Python files in the project."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # Find all Python files
    python_files = []
    for dir_to_format in DIRS_TO_FORMAT:
        python_files.extend(find_python_files(dir_to_format))

    # Remove duplicates
    python_files = list(set(python_files))
    python_files.sort()  # Sort for consistent output

    # Print summary

    # Build the command
    cmd = ["black"]
    cmd.extend(python_files)

    # Run Black
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print the output
    if result.stderr:
        pass

    # Return the exit code
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
