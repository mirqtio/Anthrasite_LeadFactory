#!/usr/bin/env python3
"""
Script to identify commented-out code blocks in the codebase.
"""

import os
import re
import sys
from pathlib import Path

# Define patterns to identify commented code
CODE_PATTERNS = [
    r"^\s*#\s*(def|class|if|for|while|return|import|from|try|except|with|async)",
    r"^\s*#\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=",
    r"^\s*#\s*[a-zA-Z_][a-zA-Z0-9_]*\(.*\)",
    r"^\s*# if\s+False:",
]

# Define directories to search
SEARCH_DIRS = ["leadfactory", "bin", "utils"]

# Define files to exclude
EXCLUDE_FILES = [
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
]


def is_excluded(path):
    """Check if a path should be excluded from analysis."""
    for excluded in EXCLUDE_FILES:
        if excluded in path:
            return True
    return False


def find_commented_code():
    """Find commented code blocks in the codebase."""
    results = []

    for directory in SEARCH_DIRS:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        for root, _, files in os.walk(dir_path):
            root_path = Path(root)
            if is_excluded(str(root_path)):
                continue

            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = root_path / file
                if is_excluded(str(file_path)):
                    continue

                # Process the file
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        lines = f.readlines()
                    except UnicodeDecodeError:
                        print(f"Error reading {file_path} - skipping")
                        continue

                # Look for commented code patterns
                in_comment_block = False
                comment_block_start = 0
                comment_block_lines = []

                for i, line in enumerate(lines):
                    is_comment = line.strip().startswith("#")

                    if is_comment:
                        if not in_comment_block:
                            in_comment_block = True
                            comment_block_start = i
                            comment_block_lines = [line]
                        else:
                            comment_block_lines.append(line)
                    elif in_comment_block:
                        # End of comment block
                        in_comment_block = False

                        # Check if it looks like code
                        for pattern in CODE_PATTERNS:
                            for comment_line in comment_block_lines:
                                if re.search(pattern, comment_line):
                                    results.append(
                                        {
                                            "file": str(file_path),
                                            "start_line": comment_block_start + 1,
                                            "end_line": i,
                                            "content": "".join(comment_block_lines),
                                        }
                                    )
                                    break
                            else:
                                continue
                            break

                # Check for final comment block at EOF
                if in_comment_block:
                    for pattern in CODE_PATTERNS:
                        for comment_line in comment_block_lines:
                            if re.search(pattern, comment_line):
                                results.append(
                                    {
                                        "file": str(file_path),
                                        "start_line": comment_block_start + 1,
                                        "end_line": len(lines),
                                        "content": "".join(comment_block_lines),
                                    }
                                )
                                break
                        else:
                            continue
                        break

    return results


def main():
    """Main function."""
    print("Searching for commented-out code blocks...")
    results = find_commented_code()

    if not results:
        print("No commented-out code blocks found.")
        return 0

    print(f"\nFound {len(results)} potential commented-out code blocks:")
    for i, result in enumerate(results, 1):
        print(
            f"\n{i}. {result['file']} (lines {result['start_line']}-{result['end_line']}):"
        )
        print("-" * 80)
        print(result["content"].strip())
        print("-" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
