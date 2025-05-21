#!/usr/bin/env python3
"""
Script to properly fix the test_mockup_unit.py file.
"""


def fix_test_mockup_unit():
    """Fix the broken syntax in test_mockup_unit.py."""
    # First, let's restore the original file from git
    import subprocess

    subprocess.run(["git", "checkout", "--", "tests/test_mockup_unit.py"])

    # Now let's fix the file properly
    file_path = "tests/test_mockup_unit.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the undefined names by adding proper mock variables
    content = content.replace(
        'patch(\n        "bin.mockup.logger"\n    ):',
        'patch(\n        "bin.mockup.logger"\n    ) as mock_logging:',
    )

    content = content.replace(
        'patch(\n        "utils.io.track_api_cost"\n    ),',
        'patch(\n        "utils.io.track_api_cost"\n    ) as mock_track,',
    )

    with open(file_path, "w") as f:
        f.write(content)

    print("Fixed test_mockup_unit.py")


if __name__ == "__main__":
    fix_test_mockup_unit()
