#!/usr/bin/env python3
"""
CI workflow healthcheck script for Task #1.
Validates that the GitHub Actions workflow file exists and contains all required components.
"""

import os
import sys

import yaml


def check_github_actions_workflow():
    """Verify the GitHub Actions workflow file exists and is valid."""
    workflow_path = ".github/workflows/ci.yml"

    # Check file exists
    if not os.path.exists(workflow_path):
        return False

    # Load and validate YAML
    try:
        with open(workflow_path) as file:
            content = file.read()
            workflow = yaml.safe_load(content)
    except Exception:
        return False

    # Check required components
    # First, check simple top-level components
    if workflow.get("name") != "CI":
        return False

    # Check push and pull request triggers - handle both quoted and unquoted 'on' key
    on_key = "on"
    if on_key not in workflow and '"on"' in workflow:
        on_key = '"on"'

    if on_key not in workflow:
        return False

    on_section = workflow[on_key]

    if "push" not in on_section:
        return False

    push_branches = on_section.get("push", {}).get("branches", [])
    if "main" not in push_branches:
        return False

    if "pull_request" not in on_section:
        return False

    pr_branches = on_section.get("pull_request", {}).get("branches", [])
    if "main" not in pr_branches:
        return False

    # Check job configuration
    if "test" not in workflow.get("jobs", {}):
        return False

    if workflow.get("jobs", {}).get("test", {}).get("runs-on") != "ubuntu-latest":
        return False

    # Component validation is now handled above

    # Check for required steps
    steps = workflow.get("jobs", {}).get("test", {}).get("steps", [])
    required_steps = [
        ("actions/checkout@v3", "Checkout repository"),
        ("actions/setup-python@v4", "Set up Python 3.10"),
        ("pip install", "Install dependencies"),
        ("black --check", "Lint with Black"),
        ("ruff check", "Lint with Ruff"),
        ("bandit -r", "Security scan with Bandit"),
        ("pytest --cov", "Test with pytest"),
        ("actions/upload-artifact@v3", "Upload reports"),
    ]

    for step_content, _description in required_steps:
        if not any(step_content in str(step) for step in steps):
            return False

    # Check for badges in README.md
    try:
        with open("README.md") as file:
            readme_content = file.read()
            if "![CI]" not in readme_content and "![ci]" not in readme_content.lower():
                return False
    except Exception:
        return False

    return True


if __name__ == "__main__":
    success = check_github_actions_workflow()
    sys.exit(0 if success else 1)
