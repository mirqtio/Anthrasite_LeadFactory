#!/usr/bin/env python3
"""
Applies all QA fixes to the tasks.json file.
"""

import json
from pathlib import Path


def apply_qa_fixes():
    # Path to tasks.json
    tasks_path = Path("/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory/tasks/tasks.json")

    # Load the tasks
    with open(tasks_path, "r") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])

    # Task ID mapping for reference
    task_id_map = {}
    for task in tasks:
        if "title" in task:
            task_id_map[task["title"]] = task.get("id")

    # 1. Add repo skeleton task if not exists
    if "Initialize Repository Skeleton" not in [t.get("title", "") for t in tasks]:
        tasks.insert(
            0,
            {
                "id": 0,
                "title": "Initialize Repository Skeleton",
                "description": "Create the initial directory structure and stub files",
                "details": "Create the initial directory structure (bin/, utils/, etc/, tests/, db/) and stub files including __init__.py files, requirements.txt, and .env.example.",
                "testStrategy": "Verify all directories and files are created with correct permissions.",
                "priority": "high",
                "dependencies": [],
                "status": "done",
                "parallelizable": False,
                "touches": [
                    "bin/",
                    "utils/",
                    "etc/",
                    "tests/",
                    "db/",
                    "requirements.txt",
                    ".env.example",
                ],
                "tests": ["F RepoSkeleton"],
            },
        )
        # Update IDs of other tasks
        for task in tasks[1:]:
            if "id" in task:
                task["id"] += 1

    # 2. Fix schema_init task
    for task in tasks:
        if task.get("title") == "Initialize Database Schema and Seed Helpers":
            task["parallelizable"] = False
            if "tests" in task and "F Seed" in task["tests"]:
                task["tests"] = ["F SeedHelpers" if t == "F Seed" else t for t in task["tests"]]

        # 3. Add tests to prometheus_exporter
        elif task.get("title") == "Implement Prometheus Exporter":
            if "tests" not in task or not task["tests"]:
                task["tests"] = ["F MetricsEndpoint"]

            # Add alert rules subtask if not exists
            if "subtasks" not in task:
                task["subtasks"] = []

            if not any(st.get("title") == "Create Alert Rules" for st in task["subtasks"]):
                task["subtasks"].append(
                    {
                        "id": len(task["subtasks"]) + 1,
                        "title": "Create Alert Rules",
                        "description": "Define and export Prometheus alert rules for monitoring",
                        "status": "done",
                        "parallelizable": True,
                        "parentTaskId": task["id"],
                        "touches": ["etc/alert_rules.yml"],
                        "tests": ["F AlertRules"],
                    }
                )

        # 4. Update CI workflow task
        elif "CI" in task.get("title", "") and "workflow" in task.get("title", "").lower():
            if "touches" in task and ".github/workflows/ci.yml" in task["touches"]:
                if "requirements.txt" not in task["touches"]:
                    task["touches"].append("requirements.txt")

        # 5. Update rsync_fallback task
        elif "RSYNC" in task.get("title", "") and "Fallback" in task.get("title", ""):
            task["parallelizable"] = False

        # 6. Update budget_audit task
        elif "Budget" in task.get("title", "") and "Audit" in task.get("title", ""):
            if "tests" not in task or not task["tests"]:
                task["tests"] = ["F BudgetChecks"]

            # Add test_budget.py to touches if not present
            if "touches" not in task:
                task["touches"] = []

            if "tests/test_budget.py" not in task["touches"]:
                task["touches"].append("tests/test_budget.py")

        # 7. Add conftest.py to relevant tasks' touches
        if "touches" in task and "tests/" in str(task["touches"]):
            if "tests/conftest.py" not in task["touches"]:
                task["touches"].append("tests/conftest.py")

    # 8. Add Prometheus metrics test file
    metrics_test_file = Path("tests/test_prometheus_metrics.py")
    if not metrics_test_file.exists():
        test_content = '''"""Tests for Prometheus metrics endpoint and alert rules."""
import pytest
import requests
from prometheus_client.parser import text_string_to_metric_families

@pytest.fixture
def metrics_endpoint():
    """Return the URL for the Prometheus metrics endpoint."""
    return "http://localhost:8000/metrics"

def test_metrics_endpoint_available(metrics_endpoint):
    """Test that the metrics endpoint is available and returns 200."""
    response = requests.get(metrics_endpoint, timeout=5)
    assert response.status_code == 200, "Metrics endpoint should return 200"

def test_metrics_include_required_gauges(metrics_endpoint):
    """Test that required gauges are present in the metrics output."""
    response = requests.get(metrics_endpoint, timeout=5)
    metrics = text_string_to_metric_families(response.text)
    
    required_metrics = [
        'batch_runtime_seconds',
        'pipeline_stage_duration_seconds',
        'lead_processing_duration_seconds',
        'api_request_duration_seconds',
        'email_queue_size',
        'budget_usage_ratio'
    ]
    
    metric_names = set()
    for family in metrics:
        metric_names.add(family.name)
    
    for metric in required_metrics:
        assert metric in metric_names, f"Required metric {metric} not found in metrics"

def test_alert_rules_file_exists():
    """Test that the alert rules file exists and is valid YAML."""
    import yaml
    from pathlib import Path
    
    alert_rules_path = Path("etc/alert_rules.yml")
    assert alert_rules_path.exists(), "Alert rules file does not exist"
    
    # Try to load the YAML to validate syntax
    with open(alert_rules_path, 'r') as f:
        rules = yaml.safe_load(f)
    
    # Basic validation of alert rules structure
    assert 'groups' in rules, "Alert rules should have 'groups' key"
    assert len(rules['groups']) > 0, "Alert rules should have at least one group"
    
    # Check for required alert rules
    required_alerts = [
        'MonthlyBudgetWarning',
        'MonthlyBudgetCritical',
        'PipelineStageFailed',
        'HighCPUUsage',
        'HighMemoryUsage',
        'EmailQueueBacklog',
        'APIFailureRate'
    ]
    
    alert_names = []
    for group in rules['groups']:
        for rule in group.get('rules', []):
            if 'alert' in rule:
                alert_names.append(rule['alert'])
    
    for alert in required_alerts:
        assert alert in alert_names, f"Required alert rule {alert} not found"
'''
        with open(metrics_test_file, "w") as f:
            f.write(test_content)

    # 9. Add top-level metadata if missing
    if "id" not in data:
        data["id"] = "leadfactory_phase0_plan"
    if "title" not in data:
        data["title"] = "Anthrasite Lead-Factory Phase 0 Execution Plan"
    if "description" not in data:
        data["description"] = (
            "Complete implementation plan for the Anthrasite Lead-Factory pipeline as specified in v1.3 of the specification document."
        )

    # Save the updated tasks back to the file
    with open(tasks_path, "w") as f:
        json.dump(data, f, indent=2)

    print("Successfully applied all QA fixes to tasks.json")


if __name__ == "__main__":
    apply_qa_fixes()
