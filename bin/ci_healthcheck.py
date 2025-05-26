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
        print(f"❌ ERROR: {workflow_path} does not exist")
        return False

    # Load and validate YAML
    try:
        with open(workflow_path, "r") as file:
            content = file.read()
            print(f"\nWorkflow file content:\n{content}")
            workflow = yaml.safe_load(content)
            print(f"\nParsed YAML structure:\n{workflow}")
    except Exception as e:
        print(f"❌ ERROR: Failed to parse {workflow_path}: {e}")
        return False

    # Check required components
    # First, check simple top-level components
    if workflow.get("name") != "CI":
        print("❌ ERROR: Workflow name should be 'CI'")
        return False

    # Check push and pull request triggers - handle both quoted and unquoted 'on' key
    on_key = "on"
    if on_key not in workflow and '"on"' in workflow:
        on_key = '"on"'

    if on_key not in workflow:
        print("❌ ERROR: Missing on trigger section")
        return False

    on_section = workflow[on_key]

    if "push" not in on_section:
        print("❌ ERROR: Missing trigger for push events")
        return False

    push_branches = on_section.get("push", {}).get("branches", [])
    if "main" not in push_branches:
        print("❌ ERROR: Should trigger on push to main branch")
        return False

    if "pull_request" not in on_section:
        print("❌ ERROR: Missing trigger for pull request events")
        return False

    pr_branches = on_section.get("pull_request", {}).get("branches", [])
    if "main" not in pr_branches:
        print("❌ ERROR: Should trigger on pull requests to main branch")
        return False

    # Check job configuration
    if "test" not in workflow.get("jobs", {}):
        print("❌ ERROR: Missing 'test' job")
        return False

    if workflow.get("jobs", {}).get("test", {}).get("runs-on") != "ubuntu-latest":
        print("❌ ERROR: 'test' job should run on ubuntu-latest")
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

    for step_content, description in required_steps:
        if not any(step_content in str(step) for step in steps):
            print(f"❌ ERROR: Missing step: {description} ({step_content})")
            return False

    # Check for badges in README.md
    try:
        with open("README.md", "r") as file:
            readme_content = file.read()
            if "![CI]" not in readme_content and "![ci]" not in readme_content.lower():
                print("❌ ERROR: CI status badge not found in README.md")
                return False
    except Exception as e:
        print(f"❌ ERROR: Failed to check README.md: {e}")
        return False

    print(
        "✅ SUCCESS: GitHub Actions workflow file is valid and contains all required components"
    )
    print("✅ SUCCESS: CI status badge is present in README.md")
    return True


if __name__ == "__main__":
    success = check_github_actions_workflow()
    sys.exit(0 if success else 1)
