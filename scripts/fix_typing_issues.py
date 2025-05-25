#!/usr/bin/env python3
"""
Fix typing issues in Python files for Python 3.9 compatibility.
This script updates deprecated typing imports and replaces Dict, List, and Tuple
with their lowercase equivalents.
"""
import os
import re
from pathlib import Path


def process_file(file_path):
    """Process a single Python file to fix typing issues."""
    print(f"Processing {file_path}")
    with open(file_path) as f:
        content = f.read()

    # Fix typing imports
    content = re.sub(
        r"from typing import (.*?)(.*?)(.*?)(.*?)\n",
        # Use lowercase versions for Python 3.9 compatibility
        # Use lowercase versions for Python 3.9 compatibility
        lambda m: f"from typing import {m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}\n# Use lowercase versions for Python 3.9 compatibility\n",
        # Use lowercase versions for Python 3.9 compatibility
        content,
    )

    # Replace Dict, List, Tuple with lowercase versions in type annotations
    content = re.sub(r"Dict\[", "dict[", content)
    content = re.sub(r"List\[", "list[", content)
    content = re.sub(r"Tuple\[", "tuple[", content)

    # Update docstrings
    content = re.sub(r"tuple of", "tuple of", content)
    content = re.sub(r"list of", "list of", content)
    content = re.sub(r"dict of", "dict of", content)

    # Write back to file
    with open(file_path, "w") as f:
        f.write(content)


def main():
    """Main function to process all Python files."""
    project_root = Path(__file__).resolve().parent.parent
    # Target specific directories only
    target_dirs = [
        project_root / "bin",
        project_root / "utils",
        project_root / "scripts",
        project_root / "tests",
    ]

    # Skip these directories
    skip_dirs = ["venv", ".git", "__pycache__", ".pytest_cache"]

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue

        for root, dirs, files in os.walk(target_dir):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                if (
                    file.endswith(".py")
                    and not file.endswith("_backup.py")
                    and ".tmp" not in file
                ):
                    file_path = os.path.join(root, file)
                    process_file(file_path)


if __name__ == "__main__":
    main()
