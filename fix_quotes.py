#!/usr/bin/env python3
"""
Script to fix escaped quotes in test_mockup.py.
"""


def fix_escaped_quotes():
    """Fix escaped quotes in test_mockup.py."""
    file_path = "tests/test_mockup.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    for line in lines:
        if '\\"primary\\"' in line:
            line = line.replace('\\"primary\\"', '"primary"')
        fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print(f"Fixed escaped quotes in {file_path}")


if __name__ == "__main__":
    fix_escaped_quotes()
