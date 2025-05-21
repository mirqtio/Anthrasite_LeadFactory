#!/usr/bin/env python3
"""
Script to fix common PEP8 violations in the codebase.
This script specifically addresses:
1. Line length violations (E501)
2. Trailing whitespace (W291)
3. Blank lines containing whitespace (W293)
"""

import re
from pathlib import Path


def fix_trailing_whitespace(file_path):
    """Fix trailing whitespace in a file."""
    with open(file_path, "r") as file:
        lines = file.readlines()

    fixed_lines = [line.rstrip() + "\n" for line in lines]

    with open(file_path, "w") as file:
        file.writelines(fixed_lines)

    return True


def fix_long_lines(file_path, max_length=88):
    """Fix lines that exceed the maximum length."""
    with open(file_path, "r") as file:
        content = file.read()

    # Fix long f-strings by breaking them into multiple lines
    pattern = r'(f"[^"]{' + str(max_length) + r',}?")'

    def split_fstring(match):
        fstring = match.group(1)
        if len(fstring) <= max_length:
            return fstring

        # Find a good breaking point
        break_point = max_length - 10
        while break_point > 0 and fstring[break_point] not in [" ", ",", "."]:
            break_point -= 1

        if break_point <= 0:
            # If no good breaking point found, just return the original
            return fstring

        first_part = fstring[:break_point]
        second_part = 'f"' + fstring[break_point:]

        # Replace the closing and opening quotes
        first_part = first_part + '"'

        return first_part + ' "\n                ' + second_part

    content = re.sub(pattern, split_fstring, content)

    # Fix SQL queries with trailing whitespace
    content = re.sub(r"(\s+)$", "", content, flags=re.MULTILINE)

    with open(file_path, "w") as file:
        file.write(content)

    return True


def main():
    """Main function to fix PEP8 violations."""
    project_root = Path("/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory")

    # Directories to process
    directories = [
        project_root / "bin",
        project_root / "tests",
        project_root / "utils",
    ]

    # Process all Python files in the directories
    for directory in directories:
        for file_path in directory.glob("**/*.py"):
            print(f"Fixing PEP8 violations in {file_path}...")
            fix_trailing_whitespace(file_path)
            fix_long_lines(file_path)

    print("PEP8 fixes applied. Run static analysis tools again to verify.")


if __name__ == "__main__":
    main()
