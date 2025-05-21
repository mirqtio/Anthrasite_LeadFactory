#!/usr/bin/env python3
"""
Script to fix issues in test_mockup_unit.py.
"""


def fix_test_mockup_unit():
    """Fix issues in test_mockup_unit.py."""
    file_path = "tests/test_mockup_unit.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the logger and track_api_cost mocks
    patterns_to_fix = [
        # Fix the first test function
        (
            'patch(\n        "bin.mockup.logger"\n    ):',
            'patch(\n        "bin.mockup.logger"\n    ) as mock_logging:',
        ),
        (
            'patch(\n        "utils.io.track_api_cost"\n    ),',
            'patch(\n        "utils.io.track_api_cost"\n    ) as mock_track,',
        ),
        # Fix the second test function
        ('patch("bin.mockup.logger"):', 'patch("bin.mockup.logger") as mock_logging:'),
        (
            'patch("utils.io.track_api_cost"),',
            'patch("utils.io.track_api_cost") as mock_track,',
        ),
        # Fix the third test function
        ('patch("bin.mockup.logger")', 'patch("bin.mockup.logger") as mock_logging'),
    ]

    fixed_content = content
    for old, new in patterns_to_fix:
        fixed_content = fixed_content.replace(old, new)

    with open(file_path, "w") as f:
        f.write(fixed_content)

    print(f"Fixed mocks in {file_path}")


if __name__ == "__main__":
    fix_test_mockup_unit()
