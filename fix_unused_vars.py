#!/usr/bin/env python3
"""
Script to fix unused variables warnings in test_mockup_unit.py.
"""


def fix_unused_vars():
    """Add noqa comments to unused variables."""
    file_path = "tests/test_mockup_unit.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    for line in lines:
        if ") as mock_track," in line:
            line = line.replace(") as mock_track,", ") as mock_track,  # noqa: F841")
        elif ") as mock_logging:" in line:
            line = line.replace(") as mock_logging:", ") as mock_logging:  # noqa: F841")
        fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print(f"Fixed unused variables in {file_path}")


if __name__ == "__main__":
    fix_unused_vars()
