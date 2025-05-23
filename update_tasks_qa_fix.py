#!/usr/bin/env python3
"""
Script to apply QA fixes to tasks.json based on review feedback.
"""

import json
import logging
from pathlib import Path

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def update_tasks():
    # Path to tasks.json
    tasks_path = Path("/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/tasks/tasks.json")

    # Load the tasks
    with tasks_path.open("r") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])

    # Task ID mapping for reference
    task_id_map = {}
    for task in tasks:
        if "title" in task:
            task_id = task.get("id", task["title"])
            task_id_map[task["title"]] = task_id

    # 1. Update schema_init task
    for task in tasks:
        # 1.1 Update schema_init parallelizable and test ID
        if task.get("title") == "Initialize Database Schema and Seed Helpers":
            task["parallelizable"] = False
            if "tests" in task and "F Seed" in task["tests"]:
                task["tests"] = ["F SeedHelpers" if t == "F Seed" else t for t in task["tests"]]

        # 2. Add tests to prometheus_exporter
        elif task.get("title") == "Implement Prometheus Exporter":
            if "tests" not in task or not task["tests"]:
                task["tests"] = ["F MetricsEndpoint"]

        # 3. Update CI workflow task
        elif "CI" in task.get("title", "") and "workflow" in task.get("title", "").lower():
            if (
                "touches" in task
                and ".github/workflows/ci.yml" in task["touches"]
                and "requirements.txt" not in task["touches"]
            ):
                task["touches"].append("requirements.txt")

        # 4. Update rsync_fallback task
        elif "RSYNC" in task.get("title", "") and "Fallback" in task.get("title", ""):
            task["parallelizable"] = False

        # 5. Update budget_audit task
        elif "Budget" in task.get("title", "") and "Audit" in task.get("title", ""):
            if "tests" not in task or not task["tests"]:
                task["tests"] = ["F BudgetChecks"]

    # 6. Add prometheus_alerts as a subtask to prometheus_exporter
    prometheus_task = next((t for t in tasks if "Prometheus" in t.get("title", "")), None)
    if prometheus_task:
        if "subtasks" not in prometheus_task:
            prometheus_task["subtasks"] = []

        # Check if prometheus_alerts already exists
        if not any(t.get("title") == "Create Prometheus Alert Rules" for t in prometheus_task["subtasks"]):
            prometheus_task["subtasks"].append(
                {
                    "id": len(prometheus_task["subtasks"]) + 1,
                    "title": "Create Prometheus Alert Rules",
                    "description": ("Define and export Prometheus alert rules for monitoring"),
                    "status": "completed",
                    "parallelizable": True,
                    "parentTaskId": prometheus_task["id"],
                    "touches": ["etc/alert_rules.yml"],
                    "tests": ["F AlertRules"],
                }
            )

    # Save the updated tasks back to the data structure
    data["tasks"] = tasks

    # Write the updated data back to the file
    with tasks_path.open("w") as f:
        json.dump(data, f, indent=2)

    logger.info("Successfully updated tasks.json with QA fixes.")


if __name__ == "__main__":
    update_tasks()
