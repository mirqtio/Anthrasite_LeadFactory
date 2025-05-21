#!/usr/bin/env python3
"""
Script to fix long lines in the codebase.
This script specifically addresses:
1. Long f-strings by breaking them into multiple lines
2. Long docstrings by reformatting them
3. Long SQL queries by breaking them into multiple lines
"""

from pathlib import Path


def fix_long_lines_in_file(file_path, max_length=88):
    """Fix lines that exceed the maximum length in a file."""
    print(f"Fixing long lines in {file_path}...")

    with open(file_path, "r") as file:
        lines = file.readlines()

    fixed_lines = []
    for line in lines:
        if len(line.rstrip()) <= max_length:
            fixed_lines.append(line)
            continue

        # Check if this is an f-string
        if 'f"' in line or "f'" in line:
            # Try to break the f-string at a good point
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Find a good breaking point
            break_point = max_length - 10
            while break_point > 0 and line[break_point] not in [
                " ",
                ",",
                ".",
                ":",
                "+",
            ]:
                break_point -= 1

            if break_point > 0:
                first_part = line[:break_point].rstrip()
                second_part = indent_str + "    " + line[break_point:].lstrip()

                # If the line ends with a string concatenation, handle it properly
                if first_part.endswith('"') and not first_part.endswith('\\"'):
                    first_part = first_part + " +"

                fixed_lines.append(first_part + "\n")

                # If the second part is still too long, we'll process it in the next iteration
                if len(second_part.rstrip()) > max_length:
                    lines.append(second_part)
                else:
                    fixed_lines.append(second_part)
            else:
                # If no good breaking point found, just append the original line
                fixed_lines.append(line)

        # Check if this is a long SQL query
        elif (
            "SELECT" in line or "INSERT" in line or "UPDATE" in line or "CREATE" in line
        ):
            # Break SQL queries at logical points
            for token in [
                " FROM ",
                " WHERE ",
                " GROUP BY ",
                " ORDER BY ",
                " VALUES ",
                " SET ",
            ]:
                if token in line:
                    parts = line.split(token, 1)
                    indent = len(line) - len(line.lstrip())
                    indent_str = " " * indent

                    fixed_lines.append(parts[0] + "\n")
                    fixed_lines.append(indent_str + token.lstrip() + parts[1])
                    break
            else:
                # If no SQL tokens found, just append the original line
                fixed_lines.append(line)

        # Check if this is a long docstring
        elif line.strip().startswith('"""') or line.strip().startswith("'''"):
            # Just append the original line for now
            # Docstrings are complex to format automatically
            fixed_lines.append(line)

        else:
            # For other long lines, try to break at a logical point
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Find a good breaking point
            break_point = max_length - 10
            while break_point > 0 and line[break_point] not in [
                " ",
                ",",
                ".",
                ":",
                "+",
            ]:
                break_point -= 1

            if break_point > 0:
                first_part = line[:break_point].rstrip()
                second_part = indent_str + "    " + line[break_point:].lstrip()

                fixed_lines.append(first_part + "\n")
                fixed_lines.append(second_part)
            else:
                # If no good breaking point found, just append the original line
                fixed_lines.append(line)

    with open(file_path, "w") as file:
        file.writelines(fixed_lines)

    return True


def fix_specific_files():
    """Fix specific files with known long line issues."""
    project_root = Path("/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory")

    # Files with known long line issues
    files_to_fix = [
        project_root / "utils/cost_tracker.py",
        project_root / "utils/io.py",
        project_root / "utils/logging_config.py",
        project_root / "utils/metrics.py",
    ]

    for file_path in files_to_fix:
        fix_long_lines_in_file(file_path)

    print("Long line fixes applied to specific files.")


if __name__ == "__main__":
    fix_specific_files()
