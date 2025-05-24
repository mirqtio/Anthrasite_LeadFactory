#!/usr/bin/env python3
"""
Script to fix Python 3.9 compatibility issues with type annotations.

This script focuses on safely converting Python 3.10+ type annotations to be
compatible with Python 3.9, without introducing syntax errors.

Usage:
    python3 fix_python39_compatibility.py <directory>
"""

import ast
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Patterns to find and replace
PATTERNS = [
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
]


def add_imports_if_needed(content: str) -> str:
    """Add typing imports if they are needed based on our replacements."""
    needed_imports = set()

    # Check which typing imports are needed
    if "Union[" in content:
        needed_imports.add("Union")
    if "Optional[" in content:
        needed_imports.add("Optional")
    if "List[" in content:
        needed_imports.add("List")
    if "Dict[" in content:
        needed_imports.add("Dict")
    if "Tuple[" in content:
        needed_imports.add("Tuple")
    if "Set[" in content:
        needed_imports.add("Set")
    if "Any" in content:
        needed_imports.add("Any")

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
            # Find the position to insert new imports
            items_str = ", ".join(sorted(existing_imports.union(missing_imports)))
            new_import = f"from typing import {items_str}"
            lines[import_line] = new_import
        else:
            # For other formats, just add a new import line
            new_import = f"from typing import {', '.join(sorted(missing_imports))}"
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
        lines.insert(insert_position, new_import)

    return "\n".join(lines)


def fix_file(file_path: str) -> bool:
    """
    Fix Python 3.9 compatibility issues in a single file.
    Returns True if file was modified, False otherwise.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Skip empty files
        if not content.strip():
            return False

        # Make a copy of the original content
        original_content = content

        # Apply each pattern replacement
        for pattern, replacement in PATTERNS:
            content = re.sub(pattern, replacement, content)

        # If changes were made, ensure typing imports are present
        if content != original_content:
            content = add_imports_if_needed(content)

            # Only write the file if we actually changed something
            if content != original_content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def process_directory(directory: str) -> Tuple[int, int]:
    """
    Process all Python files in the given directory recursively.
    Returns a tuple of (files_processed, files_modified).
    """
    files_processed = 0
    files_modified = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                files_processed += 1

                if fix_file(file_path):
                    files_modified += 1
                    print(f"Fixed: {file_path}")

    return files_processed, files_modified


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)

    print(f"Processing directory: {directory}")
    files_processed, files_modified = process_directory(directory)

    print("\nSummary:")
    print(f"Files processed: {files_processed}")
    print(f"Files modified: {files_modified}")


if __name__ == "__main__":
    main()
