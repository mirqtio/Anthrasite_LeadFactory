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


def main():
    """Run Black on all Python files in the project."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.absolute()

    # Change to the project root directory
    os.chdir(project_root)

    # Build the command
    cmd = ["black"]
    cmd.extend(DIRS_TO_FORMAT)

    # Run Black
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print the output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Return the exit code
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
