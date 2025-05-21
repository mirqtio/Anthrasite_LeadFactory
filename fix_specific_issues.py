#!/usr/bin/env python3
"""
Script to fix specific PEP8 issues in the codebase.
"""

import re
from pathlib import Path


def fix_unused_variables():
    """Add noqa comments to unused variables that are needed for test structure."""
    files_to_fix = {
        "tests/test_dedupe_simple.py": [
            (
                r"real_conn = conn",
                r"real_conn = conn  # noqa: F841 - kept for clarity in test structure",
            )
        ],
        "tests/test_dedupe_unit.py": [
            (
                r"with patch\(\"bin.dedupe.DatabaseConnection\"\) as mock_db_conn:",
                r"with patch(\"bin.dedupe.DatabaseConnection\") as mock_db_conn:  # noqa: F841",
            )
        ],
        "tests/test_mockup.py": [
            (
                r"model_used = \"primary\"",
                r"model_used = \"primary\"  # noqa: F841 - for future reference",
            )
        ],
    }

    for file_path, patterns in files_to_fix.items():
        full_path = Path(__file__).parent / file_path
        if not full_path.exists():
            print(f"Warning: {file_path} does not exist")
            continue

        with open(full_path, "r") as f:
            content = f.read()

        modified = False
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True

        if modified:
            print(f"Fixing unused variables in {file_path}")
            with open(full_path, "w") as f:
                f.write(content)


def fix_undefined_names():
    """Fix undefined names in test files."""
    # Add missing imports or fix variable names
    fixes = {
        "tests/test_mockup_unit.py": [
            # Add missing imports at the top of the file
            (
                r"import pytest\n",
                r"import pytest\nfrom unittest.mock import ANY, patch, MagicMock\n",
            ),
            # Fix undefined names
            (r"mock_logger\.warning", r"mock_logging.warning"),
            (r"mock_logger\.error", r"mock_logging.error"),
            (r"mock_track_cost\.assert_not_called", r"mock_track.assert_not_called"),
        ],
        "tests/test_score.py": [
            # Add missing import for scenarios
            (
                r"from pytest_bdd import given, when, then\n",
                r"from pytest_bdd import given, when, then, scenarios\n",
            )
        ],
    }

    for file_path, patterns in fixes.items():
        full_path = Path(__file__).parent / file_path
        if not full_path.exists():
            print(f"Warning: {file_path} does not exist")
            continue

        with open(full_path, "r") as f:
            content = f.read()

        modified = False
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True

        if modified:
            print(f"Fixing undefined names in {file_path}")
            with open(full_path, "w") as f:
                f.write(content)


if __name__ == "__main__":
    fix_unused_variables()
    fix_undefined_names()
    print(
        "Specific issues fixed. Now run Black and Ruff again to ensure consistent formatting."
    )
