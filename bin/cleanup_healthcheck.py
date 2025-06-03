#!/usr/bin/env python3
"""
Healthcheck script for Task #4: Clean Up Dead Code, Clutter, and Legacy Artifacts.
Verifies that all identified redundant files have been properly removed.
"""

import os
import sys
from pathlib import Path


def check_file_removed(filepath, description):
    """Check if a file has been removed and print the status."""
    return bool(not os.path.exists(filepath))


def check_no_bak_files():
    """Check that no .bak files exist in the codebase."""
    bak_files = []

    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".bak"):
                bak_files.append(os.path.join(root, file))

    if not bak_files:
        return True
    else:
        for file in bak_files:
            pass
        return False


def check_no_print_statements():
    """Verify that no print statements exist in the production code."""
    # This is a simplified check - in a real codebase, you would want to use
    # a proper AST parser to detect print statements in production code

    dirs_to_check = ["leadfactory", "utils"]
    # We'll only check bin/ for scripts that aren't utility scripts
    utility_scripts = [
        "bin/cleanup_healthcheck.py",
        "bin/linting_healthcheck.py",
        "bin/find_commented_code.py",
        "bin/ci_healthcheck.py",
        "bin/cost_tracking.py",
    ]
    print_statements = []

    for dir_path in dirs_to_check:
        if not os.path.exists(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = os.path.join(root, file)
                if file_path in utility_scripts or "/tests/" in file_path:
                    continue

                with open(file_path, encoding="utf-8") as f:
                    try:
                        lines = f.readlines()
                    except UnicodeDecodeError:
                        continue

                for i, line in enumerate(lines):
                    if "print(" in line and not line.strip().startswith("#"):
                        print_statements.append((file_path, i + 1, line.strip()))

    if not print_statements:
        return True
    else:
        for file_path, _line_num, line in print_statements:
            pass
        return False


def check_cleanup_log():
    """Check that the cleanup log exists and is complete."""
    log_path = "cleanup_log.md"

    if not os.path.exists(log_path):
        return False

    with open(log_path) as f:
        content = f.read()

    required_sections = [
        "Redundant Test Files Removed",
        "Patch/Fix Scripts Removed",
        "Backup Files Removed",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    if missing_sections:
        return False

    placeholder_text = "*To be populated during cleanup*"
    return placeholder_text not in content


def main():
    """Run all healthchecks and return exit code based on results."""

    checks = [
        check_file_removed(
            "tests/test_dedupe_new.py", "Redundant test file (test_dedupe_new.py)"
        ),
        check_file_removed(
            "tests/test_mockup 3.py", "Redundant test file (test_mockup 3.py)"
        ),
        check_file_removed(
            "fix_dedupe_simple.py", "Patch script (fix_dedupe_simple.py)"
        ),
        check_file_removed(
            "fix_test_mockup_unit.py", "Patch script (fix_test_mockup_unit.py)"
        ),
        check_no_bak_files(),
        check_no_print_statements(),
        check_cleanup_log(),
    ]

    success = all(checks)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
