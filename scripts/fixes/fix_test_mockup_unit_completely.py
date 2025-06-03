#!/usr/bin/env python3
"""
Script to completely fix the test_mockup_unit.py file.
"""


def fix_test_mockup_unit():
    """Fix all issues in test_mockup_unit.py."""
    # First, let's restore the original file from git
    import subprocess

    subprocess.run(["git", "checkout", "--", "tests/test_mockup_unit.py"])

    file_path = "tests/test_mockup_unit.py"

    with open(file_path) as f:
        lines = f.readlines()

    # Fix the duplicate imports
    fixed_lines = []
    import_fixed = False

    for line in lines:
        # Skip the duplicate import line
        if (
            "from unittest.mock import patch, MagicMock, ANY" in line
            and not import_fixed
        ):
            import_fixed = True
            continue

        # Fix the undefined mock_logging and mock_track variables
        if "), patch(" in line and "utils.io.track_api_cost" in line:
            fixed_lines.append(line.replace("), patch(", ") as mock_track, patch("))
        elif "), patch(" in line and "bin.mockup.logger" in line:
            fixed_lines.append(line.replace("), patch(", ") as mock_logging, patch("))
        elif "):" in line and "bin.mockup.logger" in line:
            fixed_lines.append(line.replace("):", ") as mock_logging:"))
        else:
            fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)


if __name__ == "__main__":
    fix_test_mockup_unit()
