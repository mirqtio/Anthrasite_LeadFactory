#!/usr/bin/env python3
"""
Clean up tasks.json by removing auto-generated maintenance tasks
and keeping only essential project tasks.
"""

import json
import os
from datetime import datetime


def clean_tasks():
    # Read the current tasks.json
    with open("tasks/tasks.json") as f:
        data = json.load(f)

    len(data["tasks"])

    # Filter out auto-generated maintenance tasks
    cleaned_tasks = []
    for task in data["tasks"]:
        # Skip auto-generated maintenance tasks
        if task.get("source", {}).get("type") == "maintenance":
            continue

        # Skip tasks with titles that indicate they're auto-generated fixes
        skip_patterns = [
            "Fix failing test:",
            "Fix lint error:",
            "Fix type error:",
            "Improve reliability of",
            "Fix timeout in",
            "Investigate and fix",
            "Address performance issue",
        ]

        if any(pattern in task.get("title", "") for pattern in skip_patterns):
            continue

        # Keep this task
        cleaned_tasks.append(task)

    # Update the data with cleaned tasks
    data["tasks"] = cleaned_tasks

    # Backup the original
    backup_path = f'tasks/tasks.json.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    os.rename("tasks/tasks.json", backup_path)

    # Write the cleaned version
    with open("tasks/tasks.json", "w") as f:
        json.dump(data, f, indent=2)

    # Remove old task files
    for i in range(1, 274):
        task_file = f"tasks/task_{i}.txt"
        if os.path.exists(task_file):
            os.remove(task_file)

    return len(cleaned_tasks)


if __name__ == "__main__":
    clean_tasks()
