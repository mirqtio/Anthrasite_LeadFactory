#!/usr/bin/env python3
"""
Import Refactoring Script for LeadFactory.

This script processes Python files in the codebase and updates import statements
to match the new package structure.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Import replacement mapping
IMPORT_MAPPING = [
    # Pipeline modules
    (
        r"from leadfactory.pipeline import scrape",
        "from leadfactory.pipeline import scrape",
    ),
    (r"from bin\.scrape import (.+)", r"from leadfactory.pipeline.scrape import \1"),
    (
        r"from leadfactory.pipeline import enrich",
        "from leadfactory.pipeline import enrich",
    ),
    (r"from bin\.enrich import (.+)", r"from leadfactory.pipeline.enrich import \1"),
    (
        r"from leadfactory.pipeline import dedupe",
        "from leadfactory.pipeline import dedupe",
    ),
    (r"from bin\.dedupe import (.+)", r"from leadfactory.pipeline.dedupe import \1"),
    (
        r"from leadfactory.pipeline import score",
        "from leadfactory.pipeline import score",
    ),
    (r"from bin\.score import (.+)", r"from leadfactory.pipeline.score import \1"),
    (
        r"from leadfactory.pipeline import email_queue",
        "from leadfactory.pipeline import email_queue",
    ),
    (
        r"from bin\.email_queue import (.+)",
        r"from leadfactory.pipeline.email_queue import \1",
    ),
    (
        r"from leadfactory.pipeline import mockup",
        "from leadfactory.pipeline import mockup",
    ),
    (r"from bin\.mockup import (.+)", r"from leadfactory.pipeline.mockup import \1"),
    # Utility modules
    (r"from bin\.utils import (.+)", r"from leadfactory.utils import \1"),
    (
        r"from bin\.utils\.string_utils import (.+)",
        r"from leadfactory.utils.string_utils import \1",
    ),
    (r"from bin\.metrics import metrics", r"from leadfactory.utils import metrics"),
    (
        r"from leadfactory.utils import batch_completion_monitor",
        r"from leadfactory.utils import batch_completion_monitor",
    ),
    (
        r"from bin\.batch_completion_monitor import (.+)",
        r"from leadfactory.utils.batch_completion_monitor import \1",
    ),
    # Cost tracking modules
    (
        r"from leadfactory.cost import budget_gate",
        r"from leadfactory.cost import budget_gate",
    ),
    (
        r"from bin\.budget_gate import (.+)",
        r"from leadfactory.cost.budget_gate import \1",
    ),
    (
        r"from bin\.cost_tracking import cost_tracker",
        r"from leadfactory.cost.cost_tracking import cost_tracker",
    ),
    (
        r"from leadfactory.cost import budget_audit",
        r"from leadfactory.cost import budget_audit",
    ),
    # Configuration
    (
        r"^load_dotenv\(\)",
        r"from leadfactory.config import load_config\n\nload_config()",
    ),
    (
        r"from leadfactory.config import load_config",
        r"from leadfactory.config import load_config",
    ),
]


def process_file(
    file_path: Path, dry_run: bool = True
) -> tuple[int, list[tuple[str, str]]]:
    """Process a single Python file to update imports.

    Args:
        file_path: Path to the Python file
        dry_run: If True, don't modify the file, just show changes

    Returns:
        Tuple of (number of changes, list of (old_line, new_line) changes)
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return 0, []

    original_content = content
    changes = []

    for pattern, replacement in IMPORT_MAPPING:
        # Store original content for comparison
        old_content = content

        # Apply the replacement
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        # If content changed, find the specific lines that changed
        if old_content != content:
            old_lines = old_content.splitlines()
            new_lines = content.splitlines()

            # Use difflib to find differences
            import difflib

            differ = difflib.Differ()
            diff = list(differ.compare(old_lines, new_lines))

            for line in diff:
                if line.startswith("- "):
                    old_line = line[2:]
                    for next_line in diff:
                        if (
                            next_line.startswith("+ ")
                            and re.sub(pattern, replacement, old_line) == next_line[2:]
                        ):
                            changes.append((old_line, next_line[2:]))
                            break

    if not dry_run and content != original_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    return len(changes), changes


def process_directory(
    directory: Path,
    extensions: list[str] = None,
    dry_run: bool = True,
    exclude_dirs: list[str] = None,
) -> dict[str, list[tuple[str, str]]]:
    """Process Python files in a directory to update imports.

    Args:
        directory: Directory to process
        extensions: File extensions to process
        dry_run: If True, don't modify files, just show changes
        exclude_dirs: Directories to exclude

    Returns:
        Dictionary mapping file paths to lists of (old_line, new_line) changes
    """
    if exclude_dirs is None:
        exclude_dirs = ["__pycache__", ".git", "venv", "env", ".env"]
    if extensions is None:
        extensions = [".py"]
    changes_by_file = {}

    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = Path(root) / file
                num_changes, changes = process_file(file_path, dry_run)

                if num_changes > 0:
                    changes_by_file[str(file_path)] = changes

    return changes_by_file


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(description="Update imports in Python files")
    parser.add_argument(
        "--directory", "-d", type=str, default=".", help="Directory to process"
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Don't modify files, just show changes",
    )

    args = parser.parse_args()

    changes_by_file = process_directory(Path(args.directory), dry_run=args.dry_run)

    sum(len(changes) for changes in changes_by_file.values())

    if args.dry_run:
        for _file_path, changes in sorted(changes_by_file.items()):
            for _old_line, _new_line in changes:
                pass
    else:
        pass


if __name__ == "__main__":
    main()
