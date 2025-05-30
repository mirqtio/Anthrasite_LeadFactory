#!/usr/bin/env python3
"""
Script to fix Python 3.9 compatibility issues with type annotations and other Python 3.9-specific issues.

This script systematically addresses known Python 3.9 compatibility issues, including:
- Type annotation syntax differences from Python 3.10+
- Missing typing imports
- Unsupported function parameters like zip(strict=False)
- Variable type annotation issues
- Path handling with pathlib vs os.path
- Common function signature mismatches

Usage:
    python3 fix_python39_compatibility.py <directory>
"""

import ast
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from re import Match, Pattern
from typing import (
    # Use lowercase versions for Python 3.9 compatibility
    Any,
    Dict,
    Final,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

# Type annotation patterns to find and replace
TYPE_ANNOTATION_PATTERNS = [
    # Union type using pipe operator (Union[X, Y] -> Union[X, Y])
    (r"(\w+)\s*\|\s*(\w+)(?!\])", r"Union[\1, \2]"),
    # Optional type using pipe operator (Union[X, None] -> Optional[X])
    (r"(\w+)\s*\|\s*None(?!\])", r"Optional[\1]"),
    # Multi-union types (Union[X, Y] | Z -> Union[X, Y, Z])
    (r"(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)(?!\])", r"Union[\1, \2, \3]"),
    # Complex Union types with nested structures
    (
        r"(Union[List, Dict]|Union[Tuple, Set])\[([^]]+)\]\s*\|\s*None(?!\])",
        r"Optional[\1[\2]]",
    ),
    # Unions with nested types
    (
        r"(Union[List, Dict]|Union[Tuple, Set])\[([^]]+)\]\s*\|\s*(Union[List, Dict]|Union[Tuple, Set])\[([^]]+)\](?!\])",
        r"Union[\1[\2], \3[\4]]",
    ),
    # Return type annotations using list[str] -> list[str]
    (r"\) -> list\[(\w+)\]:", r") -> list[\1]:"),
    # Return type annotations using dict[str, any] -> dict[str, Any]
    (r"\) -> dict\[(\w+), (\w+)\]:", r") -> dict[\1, \2]:"),
    # Variable annotations using list[str] -> list[str]
    (r": list\[(\w+)\] = \[", r": list[\1] = ["),
    # Variable annotations using dict[str, any] -> dict[str, Any]
    (r": dict\[(\w+), (\w+)\] = \{", r": dict[\1, \2] = {"),
]


# Additional compatibility patterns for fixing other Python 3.9 issues
CODE_PATTERNS = [
    # Remove strict=False from zip() calls
    (r"zip\(([^,]+), ([^,]+), strict=False\)", r"zip(\1, \2)"),
    # Fix missing variable annotations for dictionaries
    (
        r"(\s+)([a-zA-Z][a-zA-Z0-9_]*) = \{\}\s+# Dictionary of ([^\n]+)",
        r"\1\2: dict[str, Any] = {}  # Dictionary of \3",
    ),
    # Fix missing variable annotations for lists
    (
        r"(\s+)([a-zA-Z][a-zA-Z0-9_]*) = \[\]\s+# list of ([^\n]+)",
        r"\1\2: list[\3] = []  # list of \3",
    ),
    # Fix missing type annotations for variables with default values
    (
        r"(\s+)([a-zA-Z][a-zA-Z0-9_]*) = (None|\[\]|\{\}|set\(\))\s+# ([^\n]+) with no type",
        r"\1\2: Optional[Any] = \3  # \4 with type annotation",
    ),
]


def add_imports_if_needed(content: str) -> str:
    """Add typing imports if they are needed based on our replacements."""
    needed_imports = set()

    # Check which typing imports are needed
    if "Union[" in content:
        needed_imports.add("Union")
    if "Optional[" in content:
        needed_imports.add("Optional")
    if "list[" in content:
        needed_imports.add("List")
    if "dict[" in content:
        needed_imports.add("Dict")
    if "tuple[" in content:
        needed_imports.add("Tuple")
    if "Set[" in content:
        needed_imports.add("Set")
    if "Any" in content:
        needed_imports.add("Any")
    if "Iterator[" in content:
        needed_imports.add("Iterator")
    if "Final[" in content:
        needed_imports.add("Final")

    # If no imports needed, return original content
    if not needed_imports:
        return content

    # Try to parse the content to check if it's valid Python
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If the file has syntax errors, don't modify imports
        return content

    # Check for existing typing imports
    existing_imports = set()
    import_line = None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            import_line = (
                node.lineno - 1
            )  # Line numbers are 1-indexed, lists are 0-indexed
            for name in node.names:
                existing_imports.add(name.name)

    # Determine which imports need to be added
    missing_imports = needed_imports - existing_imports
    if not missing_imports:
        return content

    # Convert content to lines for easier manipulation
    lines = content.splitlines()

    # If we found an existing typing import, modify it
    if import_line is not None:
        # Update existing import line
        current_import = lines[import_line]

        # Handle different import formats
        if "import " in current_import and "typing import" in current_import:
            # Case: from typing import X, Y, Z
            # Use lowercase versions for Python 3.9 compatibility
            # Find the position to insert new imports
            items_str = ", ".join(sorted(existing_imports.union(missing_imports)))
            new_import = f"from typing import {items_str}"
            # Use lowercase versions for Python 3.9 compatibility
            lines[import_line] = new_import
        else:
            # For other formats, just add a new import line
            new_import = f"from typing import {', '.join(sorted(missing_imports))}"
            # Use lowercase versions for Python 3.9 compatibility
            lines.insert(import_line + 1, new_import)
    else:
        # No existing typing import, find a good place to add it
        # Try to insert after any other imports
        insert_position = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_position = i + 1

        # Add the new import line
        new_import = f"from typing import {', '.join(sorted(missing_imports))}"
        # Use lowercase versions for Python 3.9 compatibility
        lines.insert(insert_position, new_import)

    return "\n".join(lines)


def fix_unsupported_kwargs(content: str) -> str:
    """Fix unsupported keyword arguments in functions like zip(strict=False)"""
    # Specific pattern for the strict=False parameter in zip
    pattern = r"zip\(([^,]+),\s*([^)]+),\s*strict=False\)"
    replacement = r"zip(\1, \2)"
    return re.sub(pattern, replacement, content)


def fix_function_signature_mismatches(content: str, file_path: str) -> str:
    """Fix known function signature mismatches between modules"""
    # Only apply to specific files with known issues
    if "budget_audit.py" in file_path:
        # Remove period parameter from get_cost_breakdown_by_service
        content = re.sub(
            r"get_cost_breakdown_by_service\(period=([^)]+)\)",
            r"get_cost_breakdown_by_service()",
            content,
        )
        # Remove period parameter from get_cost_breakdown_by_operation
        content = re.sub(
            r"get_cost_breakdown_by_operation\(([^,]+), period=([^)]+)\)",
            r"get_cost_breakdown_by_operation(\1)",
            content,
        )
        # Remove limit parameter from get_scaling_gate_history
        content = re.sub(
            r"get_scaling_gate_history\(limit=([^)]+)\)",
            r"get_scaling_gate_history()",
            content,
        )
        # Remove period parameter from export_cost_report
        content = re.sub(
            r"export_cost_report\(([^,]+), period=([^)]+)\)",
            r"export_cost_report(\1)",
            content,
        )

    return content


def fix_variable_annotations(content: str) -> str:
    """Add proper type annotations to variables"""
    # Add typing for data dictionaries
    content = re.sub(
        r"(\s+)data = json\.load\(f\)",
        r"\1data: dict[str, Any] = json.load(f)",
        content,
    )

    # Add typing for empty lists that will have appends
    content = re.sub(
        r"(\s+)(\w+) = \[\](\s+)\2\.append", r"\1\2: list[Any] = []\3\2.append", content
    )

    # Fix variable shadowing with appropriate renaming
    content = re.sub(
        r'(\s+)data = \{([^}]+)\}(\s+)(\s+)data\["(\w+)"\]',
        r'\1gate_data: dict[str, Any] = {\2}\3\4gate_data["\5"]',
        content,
    )

    return content


def fix_file(file_path: str) -> bool:
    """
    Fix Python 3.9 compatibility issues in a single file.
    Returns True if file was modified, False otherwise.
    """
    # Skip non-Python files
    if not file_path.endswith(".py"):
        return False

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    # Store original content for comparison
    original_content = content

    # Apply type annotation patterns
    for pattern, replacement in TYPE_ANNOTATION_PATTERNS:
        content = re.sub(pattern, replacement, content)

    # Apply code patterns
    for pattern, replacement in CODE_PATTERNS:
        content = re.sub(pattern, replacement, content)

    # Apply specific fixes
    content = fix_unsupported_kwargs(content)
    content = fix_function_signature_mismatches(content, file_path)
    content = fix_variable_annotations(content)

    # Add imports if needed
    content = add_imports_if_needed(content)

    # Only write the file if changes were made
    if content != original_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False
    return False


def process_directory(directory: str) -> tuple[int, int]:
    """
    Process all Python files in the given directory recursively.
    Returns a tuple of (files_processed, files_modified).
    """
    files_processed = 0
    files_modified = 0

    # Directories to skip
    skip_dirs = ["venv", ".venv", "__pycache__", ".git", "tests", ".cursor", "archive"]

    for root, dirs, files in os.walk(directory):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                files_processed += 1
                if fix_file(file_path):
                    files_modified += 1

    return files_processed, files_modified


def create_non_automatable_issues_list(directory: str) -> None:
    """
    Create a list of non-automatable Python 3.9 compatibility issues
    that need manual attention.
    """
    non_automatable_issues = [
        "# Python 3.9 Compatibility Issues Requiring Manual Attention\n",
        "The following issues cannot be automated and require manual fixes:\n\n",
        "1. Function signature mismatches between utils/cost_tracker.py and bin/budget_audit.py that are too complex for regex\n",
        "2. Complex type annotation issues that require context-aware parsing\n",
        "3. Inconsistent variable naming patterns that can't be safely automated\n",
        "4. Missing library stubs (install via pip: types-requests, types-pytz, etc.)\n",
        "5. Import cycles that need manual restructuring\n\n",
        "Files with potential issues:\n",
    ]

    # Scan for files with known difficult patterns
    difficult_patterns = [
        r"def\s+get_logger\s*\([^)]*\)\s*->\s*\w+:",  # Multiple different get_logger signatures
        r"Unexpected\s+keyword\s+argument",  # Keyword argument mismatches
        r"Statement\s+is\s+unreachable",  # Unreachable code
        r"Incompatible\s+types\s+in\s+assignment",  # Type mismatches
    ]

    # list of files with suspected issues
    issue_files = set()

    # Walk the directory and look for files with potential issues
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                        for pattern in difficult_patterns:
                            if re.search(pattern, content):
                                issue_files.add(file_path)
                                break
                except Exception:
                    pass

    # Add the files to the list
    for file_path in sorted(issue_files):
        non_automatable_issues.append(f"- {file_path}\n")

    # Write the list to a file
    issues_file = os.path.join(directory, "python39_non_automatable_issues.md")
    with open(issues_file, "w", encoding="utf-8") as f:
        f.writelines(non_automatable_issues)


def main():
    if len(sys.argv) < 2:
        return 1

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        return 1

    files_processed, files_modified = process_directory(directory)

    # Create list of non-automatable issues
    create_non_automatable_issues_list(directory)

    return 0


if __name__ == "__main__":
    sys.exit(main())
