#!/usr/bin/env python3
"""
Script to properly add noqa comments to unused variables in test_mockup_unit.py.
"""


def fix_unused_vars():
    """Add noqa comments to unused variables."""
    file_path = "tests/test_mockup_unit.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix unused variables with proper noqa comments
    content = content.replace(") as mock_track, patch(", ") as mock_track,  # noqa: F841\n    patch(")

    content = content.replace(") as mock_logging:", ") as mock_logging:  # noqa: F841")

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed unused variables in {file_path}")


if __name__ == "__main__":
    fix_unused_vars()
