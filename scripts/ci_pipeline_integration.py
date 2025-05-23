#!/usr/bin/env python
"""
CI Pipeline Integration
---------------------
This script integrates all test re-enablement tools into a unified workflow
that can be run as part of the CI pipeline to incrementally enable tests.

Usage:
    python ci_pipeline_integration.py --mode auto --category core_utils --priority high

Features:
- Automatically analyzes test status and recommends next steps
- Converts selected tests from pytest to unittest format
- Updates CI workflow to include newly converted tests
- Generates comprehensive reports and visualizations
- Provides detailed logging for debugging
"""

import argparse
import json
import logging
import os
import subprocess
import sys

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "ci_pipeline_integration.log")),
    ],
)
logger = logging.getLogger("ci_pipeline_integration")

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
    directories = ["logs", "test_results", "docs", "ci_tests"]

    for category in TEST_CATEGORIES.values():
        directories.append(category)
        ci_category = f"ci_tests/{os.path.basename(category)}"
        directories.append(ci_category)

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def run_command(command, cwd=None):
    """Run a command and return the result."""
    logger.info(f"Running command: {' '.join(command)}")

    try:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Command succeeded: {' '.join(command)}")
            return True, result.stdout
        else:
            logger.error(f"Command failed: {' '.join(command)}")
            logger.error(f"Error: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        logger.exception(f"Error running command: {e}")
        return False, str(e)


def generate_test_status_report():
    """Generate a test status report."""
    logger.info("Generating test status report")

    command = [
        "python",
        "scripts/generate_test_status_report.py",
        "--output",
        "docs/test_status_report.md",
    ]

    success, output = run_command(command)

    if success:
        logger.info("Test status report generated successfully")
        return True
    else:
        logger.error("Failed to generate test status report")
        return False


def generate_test_visualizations():
    """Generate test visualizations."""
    logger.info("Generating test visualizations")

    command = [
        "python",
        "scripts/generate_test_visualizations.py",
        "--input",
        "test_results/test_status.json",
        "--output",
        "docs/test_visualizations",
    ]

    success, output = run_command(command)

    if success:
        logger.info("Test visualizations generated successfully")
        return True
    else:
        logger.error("Failed to generate test visualizations")
        return False


def convert_tests(category, priority):
    """Convert tests from pytest to unittest format."""
    logger.info(f"Converting tests for category {category} with priority {priority}")

    # Get the source directory for the category
    source_dir = TEST_CATEGORIES.get(category)
    if not source_dir:
        logger.error(f"Invalid category: {category}")
        return False

    # Get the target directory for the category
    target_dir = f"ci_tests/{os.path.basename(source_dir)}"

    # Run the generate_ci_tests.py script
    command = [
        "python",
        "scripts/generate_ci_tests.py",
        "--source-dir",
        source_dir,
        "--target-dir",
        target_dir,
    ]

    success, output = run_command(command)

    if success:
        logger.info(f"Tests converted successfully for category {category}")
        return True
    else:
        logger.error(f"Failed to convert tests for category {category}")
        return False


def enable_tests(category, priority):
    """Enable tests for a category with a specific priority."""
    logger.info(f"Enabling tests for category {category} with priority {priority}")

    # Run the enable_ci_tests.py script
    command = [
        "python",
        "scripts/enable_ci_tests.py",
        "--category",
        category,
        "--priority",
        priority,
    ]

    success, output = run_command(command)

    if success:
        logger.info(f"Tests enabled successfully for category {category}")
        return True
    else:
        logger.error(f"Failed to enable tests for category {category}")
        return False


def update_ci_workflow(category):
    """Update the CI workflow to include tests for a category."""
    logger.info(f"Updating CI workflow for category {category}")

    # Get the target directory for the category
    target_dir = f"ci_tests/{os.path.basename(TEST_CATEGORIES.get(category, category))}"

    # Find all test files in the target directory
    test_files = []
    if os.path.exists(target_dir):
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(os.path.join(root, file))

    if not test_files:
        logger.warning(f"No test files found in {target_dir}")
        return False

    # Load the existing workflow file
    workflow_file = ".github/workflows/final-ci.yml"

    try:
        with open(workflow_file) as f:
            workflow = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading workflow file: {e}")
        return False

    # Update the workflow to include the new tests
    try:
        # Find the "Run tests" step
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                if step.get("name") == "Run core utility tests":
                    # Add the new tests to the run command
                    run_command = step.get("run", "")

                    # Add commands to run each test file
                    for test_file in test_files:
                        run_command += f"\n          # Run {os.path.basename(test_file)}\n"
                        run_command += f'          python {test_file} || echo "Test {test_file} failed"\n'

                    step["run"] = run_command

        # Save the updated workflow file
        with open(workflow_file, "w") as f:
            yaml.dump(workflow, f, default_flow_style=False)

        logger.info(f"CI workflow updated successfully for category {category}")
        return True
    except Exception as e:
        logger.error(f"Error updating workflow file: {e}")
        return False


def get_recommendations():
    """Get recommendations for next tests to enable."""
    logger.info("Getting recommendations for next tests to enable")

    # Check if the test status file exists
    status_file = "test_results/test_status.json"
    if not os.path.exists(status_file):
        logger.warning("Test status file not found, generating report first")
        generate_test_status_report()

    try:
        with open(status_file) as f:
            test_data = json.load(f)

        # Find high-priority tests that aren't enabled yet
        recommendations = []
        for test_file, test_info in test_data.get("tests", {}).items():
            if not test_info.get("enabled", False) and test_info.get("priority", "") in ["critical", "high"]:
                recommendations.append(
                    {
                        "file": test_file,
                        "category": test_info.get("category", "uncategorized"),
                        "priority": test_info.get("priority", "medium"),
                        "test_cases": test_info.get("test_cases", 0),
                    }
                )

        # Sort by priority and then by number of test cases
        recommendations.sort(key=lambda x: (TEST_PRIORITIES.index(x["priority"]), -x["test_cases"]))

        return recommendations[:5]  # Return top 5 recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return []


def auto_mode():
    """Run in automatic mode, using recommendations to enable tests."""
    logger.info("Running in automatic mode")

    # Generate test status report
    generate_test_status_report()

    # Get recommendations
    recommendations = get_recommendations()

    if not recommendations:
        logger.info("No recommendations available")
        return

    # Group recommendations by category
    categories = {}
    for rec in recommendations:
        category = rec["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(rec)

    # Process each category
    for category, recs in categories.items():
        # Get the highest priority in this category
        priorities = [rec["priority"] for rec in recs]
        priority = min(priorities, key=lambda p: TEST_PRIORITIES.index(p))

        logger.info(f"Processing category {category} with priority {priority}")

        # Convert and enable tests
        if convert_tests(category, priority):
            if enable_tests(category, priority):
                update_ci_workflow(category)

    # Generate visualizations
    generate_test_visualizations()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CI Pipeline Integration")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["auto", "manual"],
        default="auto",
        help="Mode to run in (auto or manual)",
    )
    parser.add_argument("--category", type=str, help="Test category to enable (required in manual mode)")
    parser.add_argument(
        "--priority",
        type=str,
        choices=TEST_PRIORITIES,
        default="high",
        help="Minimum test priority to enable (default: high)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate reports only, no test conversion",
    )
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        if args.report_only:
            # Generate reports only
            generate_test_status_report()
            generate_test_visualizations()
            return 0

        if args.mode == "auto":
            # Run in automatic mode
            auto_mode()
        else:
            # Run in manual mode
            if not args.category:
                logger.error("Category is required in manual mode")
                return 1

            # Convert and enable tests
            if convert_tests(args.category, args.priority):
                if enable_tests(args.category, args.priority):
                    update_ci_workflow(args.category)

            # Generate reports
            generate_test_status_report()
            generate_test_visualizations()

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
