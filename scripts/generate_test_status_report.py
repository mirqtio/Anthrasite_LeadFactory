#!/usr/bin/env python
"""
Generate Test Status Report
--------------------------
This script analyzes the current state of tests in the project and generates
a comprehensive report on test status, coverage, and re-enablement progress.

Usage:
    python generate_test_status_report.py --output docs/test_status_report.md

Features:
- Analyzes all test files in the project
- Categorizes tests by type and status
- Calculates test coverage metrics
- Generates visualizations of test status
- Provides recommendations for next tests to enable
"""

import argparse
import glob
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Union

# Use lowercase versions for Python 3.9 compatibility

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "test_status_report.log")),
    ],
)
logger = logging.getLogger("generate_test_status_report")

# Test categories and their directories
TEST_CATEGORIES = {
    "core_utils": "tests/core_utils",
    "data_processing": "tests/data_processing",
    "api": "tests/api",
    "integration": "tests/integration",
    "ui": "tests/ui",
    "verify": "tests/verify_ci",
}

# Test priorities
TEST_PRIORITIES = ["critical", "high", "medium", "low"]


def ensure_directories():
    """Ensure necessary directories exist."""
    directories = ["logs", "test_results", "docs"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def find_all_test_files():
    """Find all test files in the project."""
    test_files = []

    # Find all pytest files
    for root, _, files in os.walk("tests"):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    # Find all unittest files in ci_tests
    if os.path.exists("ci_tests"):
        for root, _, files in os.walk("ci_tests"):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(os.path.join(root, file))

    return test_files


def categorize_test_file(test_file):
    """Categorize a test file based on its path."""
    for category, directory in TEST_CATEGORIES.items():
        if directory in test_file or category in test_file:
            return category

    # Default to uncategorized
    return "uncategorized"


def analyze_test_importance(test_file):
    """Analyze the importance of a test file based on its content."""
    try:
        with open(test_file) as f:
            content = f.read()

        # Check for priority markers in the file
        if (
            "@pytest.mark.critical" in content
            or "priority: critical" in content.lower()
        ):
            return "critical"
        elif "@pytest.mark.high" in content or "priority: high" in content.lower():
            return "high"
        elif "@pytest.mark.medium" in content or "priority: medium" in content.lower():
            return "medium"
        elif "@pytest.mark.low" in content or "priority: low" in content.lower():
            return "low"

        # Default to medium priority
        return "medium"
    except Exception as e:
        logger.error(f"Error analyzing test importance for {test_file}: {e}")
        return "medium"


def is_test_enabled_in_ci(test_file):
    """Check if a test is enabled in CI."""
    # If it's in ci_tests, it's enabled
    if test_file.startswith("ci_tests/"):
        return True

    # If it's in tests/verify_ci, it's enabled
    if test_file.startswith("tests/verify_ci/"):
        return True

    # Check if there's a corresponding file in ci_tests
    ci_test_file = test_file.replace("tests/", "ci_tests/")
    if os.path.exists(ci_test_file):
        return True

    # Check if it's included in any CI workflow
    for workflow_file in glob.glob(".github/workflows/*.yml"):
        try:
            with open(workflow_file) as f:
                content = f.read()

                # Extract the test file name without path
                test_name = os.path.basename(test_file)

                # Check if the test is mentioned in the workflow
                if test_name in content:
                    return True
        except Exception as e:
            logger.error(f"Error checking workflow file {workflow_file}: {e}")

    return False


def count_test_cases(test_file):
    """Count the number of test cases in a file."""
    try:
        with open(test_file) as f:
            content = f.read()

        # Count pytest test functions
        pytest_tests = len(re.findall(r"def test_\w+\(", content))

        # Count unittest test methods
        unittest_tests = len(re.findall(r"def test_\w+\(self", content))

        return max(pytest_tests, unittest_tests)
    except Exception as e:
        logger.error(f"Error counting test cases in {test_file}: {e}")
        return 0


def analyze_tests():
    """Analyze all tests in the project."""
    logger.info("Analyzing tests...")

    test_files = find_all_test_files()
    logger.info(f"Found {len(test_files)} test files")

    # Initialize test data
    test_data = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(test_files),
        "total_test_cases": 0,
        "enabled_files": 0,
        "enabled_test_cases": 0,
        "categories": {},
        "priorities": {
            priority: {"count": 0, "enabled": 0} for priority in TEST_PRIORITIES
        },
        "tests": {},
    }

    # Analyze each test file
    for test_file in test_files:
        category = categorize_test_file(test_file)
        priority = analyze_test_importance(test_file)
        enabled = is_test_enabled_in_ci(test_file)
        test_cases = count_test_cases(test_file)

        # Initialize category if needed
        if category not in test_data["categories"]:
            test_data["categories"][category] = {
                "count": 0,
                "enabled": 0,
                "test_cases": 0,
                "enabled_test_cases": 0,
            }

        # Update test data
        test_data["categories"][category]["count"] += 1
        test_data["categories"][category]["test_cases"] += test_cases
        test_data["total_test_cases"] += test_cases

        if enabled:
            test_data["enabled_files"] += 1
            test_data["categories"][category]["enabled"] += 1
            test_data["categories"][category]["enabled_test_cases"] += test_cases
            test_data["enabled_test_cases"] += test_cases
            test_data["priorities"][priority]["enabled"] += 1

        test_data["priorities"][priority]["count"] += 1

        # Store test file data
        test_data["tests"][test_file] = {
            "category": category,
            "priority": priority,
            "enabled": enabled,
            "test_cases": test_cases,
        }

    return test_data


def generate_ascii_bar(value, max_value, width=20):
    """Generate an ASCII bar chart."""
    if max_value == 0:
        return "[" + " " * width + "] 0%"

    percentage = value / max_value * 100
    filled_width = int(width * value / max_value)
    bar = (
        "[" + "#" * filled_width + " " * (width - filled_width) + f"] {percentage:.1f}%"
    )
    return bar


def generate_recommendations(test_data):
    """Generate recommendations for next tests to enable."""
    recommendations = []

    # Find high-priority tests that aren't enabled yet
    for test_file, test_info in test_data["tests"].items():
        if not test_info["enabled"] and test_info["priority"] in ["critical", "high"]:
            recommendations.append(
                {
                    "file": test_file,
                    "category": test_info["category"],
                    "priority": test_info["priority"],
                    "test_cases": test_info["test_cases"],
                }
            )

    # Sort by priority and then by number of test cases
    recommendations.sort(
        key=lambda x: (TEST_PRIORITIES.index(x["priority"]), -x["test_cases"])
    )

    return recommendations[:5]  # Return top 5 recommendations


def generate_markdown_report(test_data, output_file):
    """Generate a markdown report of test status."""
    logger.info(f"Generating markdown report to {output_file}")

    with open(output_file, "w") as f:
        f.write("# Test Status Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall progress
        f.write("## Overall Progress\n\n")
        f.write(
            f"- Test Files: {test_data['enabled_files']}/{test_data['total_files']} ({test_data['enabled_files'] / test_data['total_files'] * 100:.1f}% if test_data['total_files'] > 0 else 0)\n"
        )
        f.write(
            f"- Test Cases: {test_data['enabled_test_cases']}/{test_data['total_test_cases']} ({test_data['enabled_test_cases'] / test_data['total_test_cases'] * 100:.1f}% if test_data['total_test_cases'] > 0 else 0)\n\n"
        )

        # ASCII bar chart for overall progress
        f.write("```\n")
        f.write(
            f"Files:  {generate_ascii_bar(test_data['enabled_files'], test_data['total_files'])}\n"
        )
        f.write(
            f"Cases:  {generate_ascii_bar(test_data['enabled_test_cases'], test_data['total_test_cases'])}\n"
        )
        f.write("```\n\n")

        # Category progress
        f.write("## Category Progress\n\n")
        f.write(
            "| Union[Category, Enabled] Union[Files, Total] Union[Files, Enabled] Union[Cases, Total] Union[Cases, Progress] |\n"
        )
        f.write(
            "|----------|--------------|-------------|---------------|-------------|----------|\n"
        )

        for category, cat_data in sorted(test_data["categories"].items()):
            if cat_data["count"] > 0:
                progress = (
                    cat_data["enabled"] / cat_data["count"] * 100
                    if cat_data["count"] > 0
                    else 0
                )
                f.write(
                    f"| {category} | {cat_data['enabled']} | {cat_data['count']} | {cat_data['enabled_test_cases']} | {cat_data['test_cases']} | {progress:.1f}% |\n"
                )

        f.write("\n")

        # Priority progress
        f.write("## Priority Progress\n\n")
        f.write("| Union[Priority, Enabled] | Union[Total, Progress] |\n")
        f.write("|----------|---------|-------|----------|\n")

        for priority in TEST_PRIORITIES:
            priority_data = test_data["priorities"][priority]
            progress = (
                priority_data["enabled"] / priority_data["count"] * 100
                if priority_data["count"] > 0
                else 0
            )
            f.write(
                f"| {priority} | {priority_data['enabled']} | {priority_data['count']} | {progress:.1f}% |\n"
            )

        f.write("\n")

        # Recommendations
        f.write("## Recommendations\n\n")
        f.write("The following tests are recommended for enabling next:\n\n")

        recommendations = generate_recommendations(test_data)
        if recommendations:
            f.write("| Union[File, Category] | Union[Priority, Test] Cases |\n")
            f.write("|------|----------|----------|------------|\n")

            for rec in recommendations:
                f.write(
                    f"| {rec['file']} | {rec['category']} | {rec['priority']} | {rec['test_cases']} |\n"
                )
        else:
            f.write("No recommendations available.\n")

        f.write("\n")

        # Next steps
        f.write("## Next Steps\n\n")
        f.write("To enable the recommended tests, follow these steps:\n\n")
        f.write(
            "1. Use the test conversion tool to convert pytest tests to unittest:\n"
        )
        f.write("   ```bash\n")
        if recommendations:
            f.write(
                f"   python scripts/generate_ci_tests.py --source-dir {os.path.dirname(recommendations[0]['file'])} --target-dir ci_tests/{os.path.basename(os.path.dirname(recommendations[0]['file']))}\n"
            )
        else:
            f.write(
                "   python scripts/generate_ci_tests.py --source-dir tests/core_utils --target-dir ci_tests/core_utils\n"
            )
        f.write("   ```\n\n")

        f.write(
            "2. Use the test enablement tool to enable tests by category and priority:\n"
        )
        f.write("   ```bash\n")
        if recommendations and recommendations[0]["category"] != "uncategorized":
            f.write(
                f"   python scripts/enable_ci_tests.py --category {recommendations[0]['category']} --priority {recommendations[0]['priority']}\n"
            )
        else:
            f.write(
                "   python scripts/enable_ci_tests.py --category core_utils --priority high\n"
            )
        f.write("   ```\n\n")

        f.write("3. Update the CI workflow to include the newly converted tests:\n")
        f.write("   ```bash\n")
        f.write("   git add ci_tests/ .github/workflows/\n")
        f.write('   git commit -m "Enable additional tests in CI workflow"\n')
        f.write("   git push\n")
        f.write("   ```\n\n")

        f.write("4. Monitor the CI workflow results and adjust as needed.\n\n")

        # Detailed test status
        f.write("## Detailed Test Status\n\n")
        f.write("| Union[File, Category] | Union[Priority, Enabled] | Test Cases |\n")
        f.write("|------|----------|----------|---------|------------|\n")

        for test_file, test_info in sorted(test_data["tests"].items()):
            enabled = "✅" if test_info["enabled"] else "❌"
            f.write(
                f"| {test_file} | {test_info['category']} | {test_info['priority']} | {enabled} | {test_info['test_cases']} |\n"
            )

    logger.info(f"Markdown report generated successfully to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate Test Status Report")
    parser.add_argument(
        "--output",
        type=str,
        default="docs/test_status_report.md",
        help="Output file for the report",
    )
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        # Analyze tests
        test_data = analyze_tests()

        # Generate markdown report
        generate_markdown_report(test_data, args.output)

        # Save test data as JSON
        json_output = os.path.join("test_results", "test_status.json")
        with open(json_output, "w") as f:
            json.dump(test_data, f, indent=2)
        logger.info(f"Test data saved to {json_output}")

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
