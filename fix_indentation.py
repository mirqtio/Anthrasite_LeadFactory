#!/usr/bin/env python3
"""
Script to fix indentation issues in test_email.py
"""

import re


def fix_indentation(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    # Fix indentation for cursor.execute statements
    content = re.sub(r"(\s+)cursor\.execute\(", r"    cursor.execute(", content)

    # Ensure consistent indentation for SQL statements
    content = re.sub(r"    cursor\.execute\(\"\"\"\n\s+", r'    cursor.execute("""\n    ', content)

    with open(file_path, "w") as file:
        file.write(content)

    print(f"Fixed indentation in {file_path}")


if __name__ == "__main__":
    fix_indentation("tests/test_email.py")
