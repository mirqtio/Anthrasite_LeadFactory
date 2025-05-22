#!/usr/bin/env python3
"""
Script to disable old CI workflow files by renaming them.
This ensures only the unified CI workflow is active.
"""

import os
import shutil
from pathlib import Path


def disable_old_workflows():
    """Disable old CI workflow files by renaming them with .disabled extension."""
    # Get the workflows directory
    workflows_dir = Path(__file__).parent.parent / ".github" / "workflows"

    # The only workflow we want to keep active
    active_workflow = "unified-ci.yml"

    # Count of disabled workflows
    disabled_count = 0

    # List all workflow files
    for workflow_file in workflows_dir.glob("*.yml"):
        # Skip the unified workflow
        if workflow_file.name == active_workflow:
            print(f"Keeping active workflow: {workflow_file.name}")
            continue

        # Rename the workflow file to disable it
        disabled_path = workflow_file.with_suffix(".yml.disabled")
        shutil.move(workflow_file, disabled_path)
        print(f"Disabled workflow: {workflow_file.name} -> {disabled_path.name}")
        disabled_count += 1

    print(f"\nDisabled {disabled_count} old workflow files. Only {active_workflow} remains active.")
    print("This ensures there are no conflicting CI workflows running in parallel.")


if __name__ == "__main__":
    disable_old_workflows()
