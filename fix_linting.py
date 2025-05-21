#!/usr/bin/env python3
"""
Script to fix common linting issues in the codebase.
This script specifically addresses:
1. Unused variable assignments in test files
2. Function redefinition issues
3. Import order problems
"""

import os
import re


def fix_unused_variables(file_path):
    """Fix unused variable assignments in test files."""
    with open(file_path, "r") as file:
        content = file.read()

    # Fix mock_track_cost and mock_logger unused variables
    content = re.sub(
        r'\) as mock_track_cost, patch\(\s*"bin\.mockup\.logger"\s*\) as mock_logger:',
        '), patch(\n        "bin.mockup.logger"\n    ):',
        content,
    )

    # Fix model_used unused variable in test_mockup.py
    content = re.sub(
        r'mockup_data = self\.fallback\.generate_mockup\(business_id\)\s*\n\s*model_used = "fallback"',
        'mockup_data = self.fallback.generate_mockup(business_id)\n                    # Track which model was used for the mockup\n                    self.logger.info("Using fallback model for mockup generation")',
        content,
    )

    # Fix unused mock_logger in test_email_simple.py and test_process_business_email.py
    content = re.sub(r"\) as mock_logger, patch\(", "), patch(", content)

    # Fix unused mock_sendgrid in test_process_business_email.py
    content = re.sub(r"\) as mock_sendgrid:", "):", content)

    # Fix unused mocks variable in test_scraper.py
    content = re.sub(
        r"# Store the mocks for assertions\s*\n\s*mocks = \{[^}]+\}",
        "# Store references to mocks if needed for debugging\n        # (Currently not used in assertions)",
        content,
    )

    with open(file_path, "w") as file:
        file.write(content)

    return True


def fix_function_redefinitions(file_path):
    """Fix function redefinition issues."""
    with open(file_path, "r") as file:
        content = file.read()

    # Fix mockup_api_unavailable redefinition in test_mockup.py
    if "test_mockup.py" in file_path:
        content = re.sub(
            r'@given\("the mockup generation API is unavailable"\)\s*\ndef mockup_api_unavailable\(mock_gpt4o_client, mock_claude_client, caplog\):',
            '@given("the mockup generation API is unavailable")\ndef mockup_api_unavailable_step(mock_gpt4o_client, mock_claude_client, caplog):',
            content,
        )

    # Fix existing_businesses redefinition in test_scraper.py
    if "test_scraper.py" in file_path:
        content = re.sub(
            r'@given\("some businesses already exist in the database"\)\s*\ndef existing_businesses\(temp_db\):',
            '@given("some businesses already exist in the database")\ndef existing_businesses_step(temp_db):',
            content,
        )

    with open(file_path, "w") as file:
        file.write(content)

    return True


def fix_import_order(file_path):
    """Fix import order problems."""
    with open(file_path, "r") as file:
        content = file.read()

    # Fix imports not at top of file in test_scraper.py
    if "test_scraper.py" in file_path:
        # This is a complex fix that would require proper parsing
        # For now, we'll just add a comment to indicate the issue
        content = re.sub(
            r"# Import the module to test\s*\nfrom bin\.scrape import",
            "# TODO: Fix import order issue - imports should be at the top of the file\n# Import the module to test\nfrom bin.scrape import",
            content,
        )

    with open(file_path, "w") as file:
        file.write(content)

    return True


def main():
    """Main function to fix linting issues."""
    project_root = "/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory"
    test_files = [
        os.path.join(project_root, "tests/test_mockup.py"),
        os.path.join(project_root, "tests/test_mockup_unit.py"),
        os.path.join(project_root, "tests/test_email_simple.py"),
        os.path.join(project_root, "tests/test_process_business_email.py"),
        os.path.join(project_root, "tests/test_scraper.py"),
    ]

    for file_path in test_files:
        print(f"Fixing linting issues in {file_path}...")
        fix_unused_variables(file_path)
        fix_function_redefinitions(file_path)
        fix_import_order(file_path)

    print("Linting fixes applied. Run static analysis tools again to verify.")


if __name__ == "__main__":
    main()
