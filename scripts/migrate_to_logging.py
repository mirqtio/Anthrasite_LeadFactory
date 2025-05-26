#!/usr/bin/env python
"""
Print to Logger Migration Script for Anthrasite LeadFactory

This script identifies print() statements in the codebase and generates a report of
suggested replacements with the unified logging system. It doesn't automatically
modify files but provides guidance for manual migration.

CAUTION: This script identifies potential changes only. All replacements should be
manually reviewed to ensure correct log levels and context are applied.
"""

import os
import re
import ast
import argparse
from typing import Dict, List, Tuple, Optional
from pathlib import Path


def find_import_logging(file_content: str) -> bool:
    """Check if the file already imports logging."""
    return (
        re.search(r"(import\s+logging|from\s+logging\s+import)", file_content)
        is not None
    )


def find_import_our_logging(file_content: str) -> bool:
    """Check if the file already imports our custom logging module."""
    return (
        re.search(r"from\s+leadfactory\.utils\.logging\s+import", file_content)
        is not None
    )


def should_skip_file(file_path: str) -> bool:
    """Determine if a file should be skipped."""
    # Skip tests, backup files, and scripts
    if (
        "/tests/" in file_path
        or "backup_" in file_path
        or "/scripts/" in file_path
        or "test_" in file_path
    ):
        return True
    return False


def analyze_print_statement(node, context: Optional[str] = None) -> Tuple[str, str]:
    """
    Analyze a print statement to determine the appropriate log level and format.

    Returns:
        Tuple of (log_level, suggested_replacement)
    """
    # Default to info level
    log_level = "info"

    # Check if this looks like an error message
    message = ""
    if len(node.args) > 0 and isinstance(node.args[0], ast.Constant):
        message = str(node.args[0].value)
    elif len(node.args) > 0 and isinstance(node.args[0], ast.JoinedStr):
        # Handle f-strings
        parts = []
        for value in node.args[0].values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
        message = "".join(parts)

    # Determine log level from message content
    lower_message = message.lower()
    if any(
        keyword in lower_message for keyword in ["error", "failed", "exception", "❌"]
    ):
        log_level = "error"
    elif any(keyword in lower_message for keyword in ["warning", "warn", "⚠️"]):
        log_level = "warning"
    elif any(keyword in lower_message for keyword in ["debug", "detailed"]):
        log_level = "debug"

    # Create suggested replacement with logger
    if context:
        context_str = f", extra={context}"
    else:
        context_str = ""

    return (
        log_level,
        f"logger.{log_level}({', '.join(ast.unparse(arg) for arg in node.args)}{context_str})",
    )


def scan_file(file_path: str) -> List[Dict]:
    """
    Scan a file for print statements and suggest logger replacements.

    Returns:
        List of dictionaries containing info about each print statement found
    """
    results = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        # Track if the file already uses our logging
        uses_logging = find_import_logging(content)
        uses_our_logging = find_import_our_logging(content)

        # Find all print statements
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                # Get line number
                line_num = getattr(node, "lineno", 0)

                # Get original line content
                file_lines = content.splitlines()
                if 0 < line_num <= len(file_lines):
                    original_line = file_lines[line_num - 1]
                else:
                    original_line = "Unknown"

                # Analyze print statement
                log_level, suggested_replacement = analyze_print_statement(node)

                results.append(
                    {
                        "file_path": file_path,
                        "line_num": line_num,
                        "original_line": original_line,
                        "log_level": log_level,
                        "suggested_replacement": suggested_replacement,
                        "uses_logging": uses_logging,
                        "uses_our_logging": uses_our_logging,
                    }
                )

    except Exception as e:
        print(f"Error analyzing {file_path}: {str(e)}")

    return results


def scan_directory(directory: str, extensions: List[str] = None) -> List[Dict]:
    """
    Recursively scan a directory for Python files with print statements.

    Args:
        directory: Directory to scan
        extensions: List of file extensions to include (default: ['.py'])

    Returns:
        List of dictionaries containing information about each print statement found
    """
    if extensions is None:
        extensions = [".py"]

    results = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)

                if should_skip_file(file_path):
                    continue

                file_results = scan_file(file_path)
                results.extend(file_results)

    return results


def generate_report(results: List[Dict]) -> str:
    """
    Generate a human-readable report of suggested logger replacements.

    Args:
        results: List of dictionaries containing print statement information

    Returns:
        Formatted report as a string
    """
    if not results:
        return "No print statements found."

    report = "Print to Logger Migration Report\n"
    report += "=============================\n\n"
    report += f"Found {len(results)} print statements to replace.\n\n"

    # Group by file
    files = {}
    for result in results:
        file_path = result["file_path"]
        if file_path not in files:
            files[file_path] = []
        files[file_path].append(result)

    # Generate report for each file
    for file_path, file_results in files.items():
        report += f"File: {file_path}\n"
        report += "-" * 80 + "\n"

        # Check if the file already imports logging
        if file_results[0]["uses_our_logging"]:
            report += "* Already imports leadfactory.utils.logging\n"
        elif file_results[0]["uses_logging"]:
            report += "* Already imports logging (needs to be replaced with leadfactory.utils.logging)\n"
        else:
            report += (
                "* Needs import: from leadfactory.utils.logging import get_logger\n"
            )
            report += "* Needs to add: logger = get_logger(__name__)\n"

        report += "\n"

        # List each print statement
        for result in file_results:
            report += f"Line {result['line_num']}: {result['original_line'].strip()}\n"
            report += f"  Replace with: {result['suggested_replacement']}\n"
            report += f"  Log level: {result['log_level']}\n\n"

        report += "\n"

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Migrate print statements to unified logging system"
    )
    parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--output", "-o", help="Output file for report (default: print to console)"
    )
    parser.add_argument(
        "--extensions",
        "-e",
        default=".py",
        help="File extensions to scan, comma-separated (default: .py)",
    )

    args = parser.parse_args()

    directory = args.directory
    extensions = args.extensions.split(",")

    print(f"Scanning directory: {directory}")
    print(f"File extensions: {extensions}")

    results = scan_directory(directory, extensions)
    report = generate_report(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print("\n" + report)

    print(f"Found {len(results)} print statements to replace.")


if __name__ == "__main__":
    main()
