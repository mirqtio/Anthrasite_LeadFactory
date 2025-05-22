#!/usr/bin/env python3
"""
Fix Import Issues

This script fixes common import issues in Python files, including:
- Sorting imports using ruff
- Adding necessary sys.path modifications
- Fixing import order conflicts
- Adding noqa comments for necessary imports after sys.path modification

Usage:
    python scripts/fix_import_issues.py [--files=<file1,file2,...>]
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Files that need special handling
SPECIAL_FILES = [
    "bin/enrich.py",
    "bin/dedupe.py",
    "bin/dedupe_new.py",
    "bin/scraper.py",
    "bin/score.py",
    "bin/email_queue.py",
    "utils/raw_data_retention.py",
    "utils/website_scraper.py",
    "utils/llm_logger.py",
    "utils/metrics.py",
]

def run_command(cmd, cwd=None):
    """Run a command and return its output."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd or project_root, 
            check=True, 
            capture_output=True, 
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {cmd}: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return None

def fix_imports_with_ruff(files=None):
    """Fix imports using ruff."""
    print("Fixing imports with ruff...")
    
    cmd = ["ruff", "check", "--select", "I", "--fix"]
    if files:
        cmd.extend(files)
    else:
        cmd.append(".")
    
    result = run_command(cmd)
    if result is not None:
        print("Ruff import sorting complete.")
    else:
        print("Ruff import sorting failed.")

def fix_special_files():
    """Fix special files that need custom import handling."""
    print("Fixing special files with custom import handling...")
    
    for file_path in SPECIAL_FILES:
        abs_path = project_root / file_path
        if not abs_path.exists():
            print(f"Skipping {file_path} - file not found")
            continue
        
        print(f"Processing {file_path}...")
        
        # Read file content
        with open(abs_path, "r") as f:
            content = f.read()
        
        # Fix sys.path modifications
        if "sys.path.insert" in content or "sys.path.append" in content:
            # Add isort directives if not present
            if "# isort: skip" not in content and "# isort:skip" not in content:
                lines = content.split("\n")
                new_lines = []
                
                # Find where sys.path is modified
                sys_path_indices = []
                for i, line in enumerate(lines):
                    if "sys.path.insert" in line or "sys.path.append" in line:
                        sys_path_indices.append(i)
                
                # Add isort directives and noqa comments
                for i, line in enumerate(lines):
                    if i in sys_path_indices:
                        # Add isort skip directive before sys.path modification
                        if i > 0 and "# isort: skip" not in lines[i-1] and "# isort:skip" not in lines[i-1]:
                            new_lines.append("# isort: skip")
                        
                        # Add the sys.path line
                        new_lines.append(line)
                        
                        # Find the next import after sys.path modification
                        for j in range(i+1, len(lines)):
                            if lines[j].startswith("import ") or lines[j].startswith("from "):
                                if "# noqa" not in lines[j]:
                                    new_lines.append(lines[j] + "  # noqa")
                                else:
                                    new_lines.append(lines[j])
                                break
                            else:
                                new_lines.append(lines[j])
                    elif i-1 in sys_path_indices and (line.startswith("import ") or line.startswith("from ")):
                        # Skip imports that were already handled
                        continue
                    else:
                        new_lines.append(line)
                
                content = "\n".join(new_lines)
        
        # Write updated content
        with open(abs_path, "w") as f:
            f.write(content)
        
        print(f"Fixed {file_path}")

def fix_test_files():
    """Fix test files that need special handling."""
    print("Fixing test files...")
    
    test_files = list((project_root / "tests").glob("test_*.py"))
    test_files.extend((project_root / "tests").glob("**/test_*.py"))
    
    for file_path in test_files:
        rel_path = file_path.relative_to(project_root)
        print(f"Processing {rel_path}...")
        
        # Read file content
        with open(file_path, "r") as f:
            content = f.read()
        
        # Fix sys.path modifications
        if "sys.path.insert" in content:
            # Add isort directives if not present
            if "# isort: skip" not in content and "# isort:skip" not in content:
                lines = content.split("\n")
                new_lines = []
                
                # Find where sys.path is modified
                sys_path_indices = []
                for i, line in enumerate(lines):
                    if "sys.path.insert" in line:
                        sys_path_indices.append(i)
                
                # Add isort directives and noqa comments
                for i, line in enumerate(lines):
                    if i in sys_path_indices:
                        # Add isort skip directive before sys.path modification
                        if i > 0 and "# isort: skip" not in lines[i-1] and "# isort:skip" not in lines[i-1]:
                            new_lines.append("# isort: skip")
                        
                        # Add the sys.path line
                        new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                content = "\n".join(new_lines)
        
        # Write updated content
        with open(file_path, "w") as f:
            f.write(content)
        
        print(f"Fixed {rel_path}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Fix import issues in Python files")
    parser.add_argument("--files", type=str, help="Comma-separated list of files to process")
    
    args = parser.parse_args()
    
    # Get list of files to process
    files = None
    if args.files:
        files = args.files.split(",")
    
    # Fix imports with ruff
    fix_imports_with_ruff(files)
    
    # Fix special files
    fix_special_files()
    
    # Fix test files
    fix_test_files()
    
    print("\nImport issues fixed successfully!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
