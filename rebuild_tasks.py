#!/usr/bin/env python3
"""
Script to rebuild tasks.json from individual task files
"""
import json
import os
import re
from pathlib import Path


def parse_task_file(filepath):
    """Parse a task file and return task data"""
    with open(filepath, "r") as f:
        content = f.read()

    # Extract task ID from filename
    task_id = int(re.search(r"task_(\d+)\.txt", filepath.name).group(1))

    # Parse header fields
    lines = content.split("\n")
    task_data = {
        "id": task_id,
        "title": "",
        "status": "pending",
        "dependencies": [],
        "priority": "medium",
        "description": "",
        "details": "",
        "test_strategy": "",
        "subtasks": [],
    }

    # Parse header
    details_started = False
    test_strategy_started = False
    current_section = None

    for line in lines:
        line = line.strip()

        if line.startswith("# Title:"):
            task_data["title"] = line.replace("# Title:", "").strip()
        elif line.startswith("# Status:"):
            task_data["status"] = line.replace("# Status:", "").strip()
        elif line.startswith("# Dependencies:"):
            deps_str = line.replace("# Dependencies:", "").strip()
            if deps_str and deps_str.lower() != "none":
                task_data["dependencies"] = [
                    int(d.strip()) for d in deps_str.split(",") if d.strip().isdigit()
                ]
        elif line.startswith("# Priority:"):
            task_data["priority"] = line.replace("# Priority:", "").strip()
        elif line.startswith("# Description:"):
            task_data["description"] = line.replace("# Description:", "").strip()
        elif line.startswith("# Details:"):
            details_started = True
            current_section = "details"
            continue
        elif line.startswith("# Test Strategy:"):
            test_strategy_started = True
            current_section = "test_strategy"
            continue
        elif details_started and current_section == "details":
            if line.startswith("# Test Strategy:"):
                current_section = "test_strategy"
                continue
            if line and not line.startswith("#"):
                if task_data["details"]:
                    task_data["details"] += "\n" + line
                else:
                    task_data["details"] = line
        elif current_section == "test_strategy":
            if line and not line.startswith("#"):
                if task_data["test_strategy"]:
                    task_data["test_strategy"] += "\n" + line
                else:
                    task_data["test_strategy"] = line

    return task_data


def main():
    """Rebuild tasks.json from individual task files"""
    tasks_dir = Path(
        "/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/tasks"
    )

    # Find all task files
    task_files = sorted([f for f in tasks_dir.glob("task_*.txt")])

    tasks = []
    for task_file in task_files:
        try:
            task_data = parse_task_file(task_file)
            tasks.append(task_data)
            print(f"Parsed task {task_data['id']}: {task_data['title']}")
        except Exception as e:
            print(f"Error parsing {task_file}: {e}")

    # Sort by ID
    tasks.sort(key=lambda x: x["id"])

    # Create the full tasks.json structure
    tasks_json = {"tasks": tasks}

    # Backup existing tasks.json
    existing_tasks_json = tasks_dir / "tasks.json"
    if existing_tasks_json.exists():
        backup_path = tasks_dir / "tasks.json.old_backup"
        existing_tasks_json.rename(backup_path)
        print(f"Backed up existing tasks.json to {backup_path}")

    # Write new tasks.json
    with open(existing_tasks_json, "w") as f:
        json.dump(tasks_json, f, indent=2)

    print(f"Successfully rebuilt tasks.json with {len(tasks)} tasks")


if __name__ == "__main__":
    main()
