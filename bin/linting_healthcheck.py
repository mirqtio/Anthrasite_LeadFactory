#!/usr/bin/env python3
"""
Healthcheck script for Task #3: Establish Linting, Formatting, and Type Checking Baseline.
Verifies that all required configuration files and reports exist.
"""

import os
import sys
import json
import configparser
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a file exists and print the status."""
    if os.path.exists(filepath):
        print(f"✅ {description} exists at {filepath}")
        return True
    else:
        print(f"❌ ERROR: {description} not found at {filepath}")
        return False


def check_ruff_config():
    """Verify that .ruff.toml contains the required rules."""
    try:
        with open(".ruff.toml", "r") as f:
            content = f.read()

        # Check for required rules
        required_rules = ["F401", "F841", "B002"]
        missing = []

        for rule in required_rules:
            if rule not in content:
                missing.append(rule)

        if not missing:
            print("✅ Ruff configuration contains required rules")
            return True
        else:
            print(
                f"❌ ERROR: Ruff configuration is missing rules: {', '.join(missing)}"
            )
            return False
    except Exception as e:
        print(f"❌ ERROR: Failed to check Ruff configuration: {e}")
        return False


def check_mypy_config():
    """Verify that mypy.ini contains the required settings."""
    try:
        config = configparser.ConfigParser()
        config.read("mypy.ini")

        # Check for required sections and settings
        required_sections = ["mypy", "mypy-utils.*", "mypy-bin.*", "mypy-tests.*"]
        for section in required_sections:
            if section not in config.sections() and section != "mypy":
                print(f"❌ ERROR: MyPy configuration is missing section: {section}")
                return False

        # Check Python version
        if config.has_option("mypy", "python_version"):
            if config.get("mypy", "python_version") != "3.10":
                print(f"❌ ERROR: MyPy configuration has incorrect Python version")
                return False
        else:
            print(f"❌ ERROR: MyPy configuration is missing python_version setting")
            return False

        print("✅ MyPy configuration contains required settings")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to check MyPy configuration: {e}")
        return False


def check_bandit_report():
    """Verify that bandit-report.json exists and is valid JSON."""
    try:
        with open("bandit-report.json", "r") as f:
            report = json.load(f)

        if "results" in report and "metrics" in report:
            print("✅ Bandit report exists and is valid")
            return True
        else:
            print("❌ ERROR: Bandit report is missing required sections")
            return False
    except FileNotFoundError:
        print("❌ ERROR: Bandit report not found")
        return False
    except json.JSONDecodeError:
        print("❌ ERROR: Bandit report is not valid JSON")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to check Bandit report: {e}")
        return False


def check_lint_debt_md():
    """Verify that lint_debt.md exists and contains required sections."""
    try:
        with open("lint_debt.md", "r") as f:
            content = f.read()

        required_sections = ["Type Ignores", "Lint Suppressions", "Future Improvements"]
        for section in required_sections:
            if section not in content:
                print(f"❌ ERROR: lint_debt.md is missing section: {section}")
                return False

        print("✅ lint_debt.md exists and contains required sections")
        return True
    except FileNotFoundError:
        print("❌ ERROR: lint_debt.md not found")
        return False
    except Exception as e:
        print(f"❌ ERROR: Failed to check lint_debt.md: {e}")
        return False


def check_ci_workflow():
    """Verify that the CI workflow includes linting steps."""
    try:
        workflow_path = ".github/workflows/ci.yml"
        if not os.path.exists(workflow_path):
            print(f"❌ ERROR: CI workflow not found at {workflow_path}")
            return False

        with open(workflow_path, "r") as f:
            content = f.read()

        required_tools = ["black", "ruff", "bandit", "pytest"]
        missing_tools = []

        for tool in required_tools:
            if tool not in content:
                missing_tools.append(tool)

        if missing_tools:
            print(
                f"❌ ERROR: CI workflow is missing steps for: {', '.join(missing_tools)}"
            )
            return False

        print("✅ CI workflow includes required linting steps")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to check CI workflow: {e}")
        return False


def main():
    """Run all healthchecks and return exit code based on results."""
    print("\n=== Linting, Formatting, and Type Checking Healthcheck ===\n")

    checks = [
        check_file_exists(".ruff.toml", "Ruff configuration"),
        check_file_exists("mypy.ini", "MyPy configuration"),
        check_file_exists("bandit-report.json", "Bandit report"),
        check_file_exists("lint_debt.md", "Lint debt documentation"),
        check_ruff_config(),
        check_mypy_config(),
        check_bandit_report(),
        check_lint_debt_md(),
        check_ci_workflow(),
    ]

    success = all(checks)

    print("\n=== Healthcheck Summary ===")
    print(f"Total checks: {len(checks)}")
    print(f"Passed: {sum(checks)}")
    print(f"Failed: {len(checks) - sum(checks)}")
    print(f"Status: {'PASSED' if success else 'FAILED'}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
