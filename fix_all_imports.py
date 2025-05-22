#!/usr/bin/env python3
"""
Script to fix import sorting issues in all Python files using ruff.
This is a more robust alternative to isort that's faster and more consistent.
"""

import os
import subprocess
import sys
from pathlib import Path


def fix_imports_in_file(file_path):
    """Fix import sorting in a single file using ruff."""
    try:
        subprocess.run(["ruff", "check", "--select=I", "--fix", file_path], check=True)
        print(f"✅ Fixed imports in {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fix imports in {file_path}: {e}")
        return False


def find_python_files(directory, exclude_dirs=None):
    """Find all Python files in a directory recursively."""
    if exclude_dirs is None:
        exclude_dirs = [
            "venv", ".venv", "env", ".env", ".git", ".github", 
            ".mypy_cache", ".pytest_cache", "__pycache__", 
            "build", "dist", "node_modules", "tasks", ".ruff_cache"
        ]
    
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    return python_files


def main():
    """Main function to fix imports in all Python files."""
    # Get the project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Directories to process
    directories_to_process = [
        os.path.join(project_root, "bin"),
        os.path.join(project_root, "scripts"),
        os.path.join(project_root, "utils"),
    ]
    
    # Find all Python files in the directories
    python_files = []
    for directory in directories_to_process:
        if os.path.exists(directory):
            python_files.extend(find_python_files(directory))
    
    if not python_files:
        print("No Python files found to process.")
        return 0
    
    print(f"Found {len(python_files)} Python files to process.")
    
    # Fix imports in each file
    success_count = 0
    for file_path in python_files:
        if fix_imports_in_file(file_path):
            success_count += 1
    
    print(f"\nSummary: Fixed imports in {success_count}/{len(python_files)} files.")
    
    return 0 if success_count == len(python_files) else 1


if __name__ == "__main__":
    sys.exit(main())
