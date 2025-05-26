#!/usr/bin/env python3
"""
Script to update all task and subtask statuses in the Phase 0 plan to 'completed'.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict


def update_statuses(file_path):
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Read the JSON file
    try:
        with Path(file_path).open("r") as f:
            data: dict[str, Any] = json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: File not found at {file_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {file_path}")
        return

    # Update status for all main tasks
    for task in data.get("tasks", []):
        task["status"] = "completed"

        # Update status for all subtasks
        for subtask in task.get("subtasks", []):
            subtask["status"] = "completed"

    # Write the updated data back to the file
    try:
        with Path(file_path).open("w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        logging.error(f"Error: Could not write to file {file_path}")
        return

    logging.info(f"Successfully updated all task statuses in {file_path}")


if __name__ == "__main__":
    file_path = "tasks/leadfactory_phase0_plan.json"
    update_statuses(file_path)
