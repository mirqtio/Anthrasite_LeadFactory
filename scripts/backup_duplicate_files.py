#!/usr/bin/env python3
"""
Backup Duplicate Files Script

This script identifies and moves duplicate Python files (those ending with " 2.py")
to a backup directory. It preserves the original directory structure in the backup.

Usage:
    python scripts/backup_duplicate_files.py

This script follows the task-master workflow and is part of the Python 3.9 compatibility task.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def main():
    """Main function to find and move duplicate files."""
    # Define paths
    repo_root = Path(__file__).parent.parent
    backup_root = (
        repo_root
        / "backup_files"
        / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    print(f"Repository root: {repo_root}")
    print(f"Backup directory: {backup_root}")

    # Create backup directory with timestamp
    backup_root.mkdir(parents=True, exist_ok=True)

    # Find all duplicate files
    duplicate_files = []
    for root, _, files in os.walk(repo_root):
        root_path = Path(root)
        if ".git" in root_path.parts or "backup_files" in root_path.parts:
            continue

        for file in files:
            if file.endswith(" 2.py"):
                duplicate_files.append(root_path / file)

    print(f"Found {len(duplicate_files)} duplicate files to back up.")

    # Move each file to the backup directory, preserving structure
    for file_path in duplicate_files:
        rel_path = file_path.relative_to(repo_root)
        backup_path = backup_root / rel_path

        # Create parent directories if needed
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file
        try:
            shutil.move(file_path, backup_path)
            print(f"Moved: {rel_path} → {backup_path.relative_to(repo_root)}")
        except Exception as e:
            print(f"Error moving {rel_path}: {e}")

    print("\nBackup complete.")
    print(f"All duplicate files have been moved to: {backup_root}")
    print("To restore files if needed, copy them back from the backup directory.")


if __name__ == "__main__":
    main()
