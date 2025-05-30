#!/usr/bin/env python3
"""
Healthcheck script for Task #3: Establish Linting, Formatting, and Type Checking Baseline.
Verifies that all required configuration files and reports exist.
"""

import configparser
import json
import os
import sys
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a file exists and print the status."""
    return bool(os.path.exists(filepath))


def check_ruff_config():
    """Verify that .ruff.toml contains the required rules."""
    try:
        with open(".ruff.toml") as f:
            content = f.read()

        # Check for required rules
        required_rules = ["F401", "F841", "B002"]
        missing = []

        for rule in required_rules:
            if rule not in content:
                missing.append(rule)

        return bool(not missing)
    except Exception:
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
                return False

        # Check Python version
        if config.has_option("mypy", "python_version"):
            if config.get("mypy", "python_version") != "3.10":
                return False
        else:
            return False

        return True
    except Exception:
        return False


def check_bandit_report():
    """Verify that bandit-report.json exists and is valid JSON."""
    try:
        with open("bandit-report.json") as f:
            report = json.load(f)

        return bool("results" in report and "metrics" in report)
    except FileNotFoundError:
        return False
    except json.JSONDecodeError:
        return False
    except Exception:
        return False


def check_lint_debt_md():
    """Verify that lint_debt.md exists and contains required sections."""
    try:
        with open("lint_debt.md") as f:
            content = f.read()

        required_sections = ["Type Ignores", "Lint Suppressions", "Future Improvements"]
        return all(section in content for section in required_sections)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def check_ci_workflow():
    """Verify that the CI workflow includes linting steps."""
    try:
        workflow_path = ".github/workflows/ci.yml"
        if not os.path.exists(workflow_path):
            return False

        with open(workflow_path) as f:
            content = f.read()

        required_tools = ["black", "ruff", "bandit", "pytest"]
        missing_tools = []

        for tool in required_tools:
            if tool not in content:
                missing_tools.append(tool)

        return not missing_tools
    except Exception:
        return False


def main():
    """Run all healthchecks and return exit code based on results."""

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

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
