#!/usr/bin/env python3
"""Update TaskMaster with completed tasks and add new tasks from codebase review."""

import json
from datetime import datetime

# Read current tasks
with open(".taskmaster/tasks/tasks.json") as f:
    data = json.load(f)

# Update status of completed tasks that are marked as done
for task in data["tasks"]:
    if task["id"] in [31, 32] and task["status"] == "done":
        task["status"] = "completed"

# Get the next task ID
next_id = max(task["id"] for task in data["tasks"]) + 1

# Add new tasks based on codebase review
new_tasks = [
    {
        "id": next_id,
        "title": "Fix Critical Test Coverage Gaps",
        "description": "Add comprehensive tests for storage abstraction layer, CLI commands, and pipeline orchestration services. These are critical components currently without any test coverage.",
        "priority": "critical",
        "status": "pending",
        "complexity": "high",
        "estimated_hours": 40,
        "dependencies": [],
        "subtasks": [
            {
                "id": 1,
                "title": "Add tests for storage abstraction layer",
                "description": "Create comprehensive tests for factory.py, interface.py, postgres_storage.py, and sharded_postgres_storage.py",
                "status": "pending",
                "estimated_hours": 16,
            },
            {
                "id": 2,
                "title": "Add tests for CLI commands",
                "description": "Test admin_commands.py, dev_commands.py, pipeline_commands.py, and purchase_analytics.py",
                "status": "pending",
                "estimated_hours": 12,
            },
            {
                "id": 3,
                "title": "Add tests for pipeline orchestration services",
                "description": "Test all files in pipeline_services/ directory",
                "status": "pending",
                "estimated_hours": 12,
            },
        ],
    },
    {
        "id": next_id + 1,
        "title": "Fix Security Vulnerabilities",
        "description": "Address critical security issues including bare except blocks, missing input validation, hardcoded values, and potential SQL injection risks.",
        "priority": "critical",
        "status": "pending",
        "complexity": "medium",
        "estimated_hours": 24,
        "dependencies": [],
        "subtasks": [
            {
                "id": 1,
                "title": "Replace bare except blocks",
                "description": "Fix 4 files with bare except blocks and add specific exception handling",
                "status": "pending",
                "estimated_hours": 4,
            },
            {
                "id": 2,
                "title": "Add input validation to APIs",
                "description": "Implement comprehensive validation for all API endpoints",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 3,
                "title": "Remove hardcoded values",
                "description": "Move all hardcoded emails, URLs, and credentials to configuration",
                "status": "pending",
                "estimated_hours": 6,
            },
            {
                "id": 4,
                "title": "Audit SQL query construction",
                "description": "Review and fix all dynamic SQL construction for injection risks",
                "status": "pending",
                "estimated_hours": 6,
            },
        ],
    },
    {
        "id": next_id + 2,
        "title": "Complete Code Quality Improvements",
        "description": "Fix all TODO/FIXME comments, replace print statements with logging, remove blocking operations, and add missing type hints.",
        "priority": "high",
        "status": "pending",
        "complexity": "medium",
        "estimated_hours": 32,
        "dependencies": [],
        "subtasks": [
            {
                "id": 1,
                "title": "Complete TODO implementations",
                "description": "Fix 11 files with TODO/FIXME comments",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 2,
                "title": "Replace print statements with logging",
                "description": "Update 15 files using print() to use proper logging",
                "status": "pending",
                "estimated_hours": 6,
            },
            {
                "id": 3,
                "title": "Replace blocking operations with async",
                "description": "Fix 11 files with time.sleep() to use async/await",
                "status": "pending",
                "estimated_hours": 10,
            },
            {
                "id": 4,
                "title": "Add missing type hints",
                "description": "Add type annotations to 140+ files",
                "status": "pending",
                "estimated_hours": 8,
            },
        ],
    },
    {
        "id": next_id + 3,
        "title": "Complete Microservices Migration",
        "description": "Finish the transition from monolithic to microservices architecture, remove duplicate files, and standardize imports.",
        "priority": "high",
        "status": "pending",
        "complexity": "high",
        "estimated_hours": 40,
        "dependencies": [],
        "subtasks": [
            {
                "id": 1,
                "title": "Remove duplicate files",
                "description": "Clean up 15+ duplicate test and configuration files",
                "status": "pending",
                "estimated_hours": 4,
            },
            {
                "id": 2,
                "title": "Standardize imports",
                "description": "Fix import inconsistencies and remove sys.path hacks",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 3,
                "title": "Complete service separation",
                "description": "Separate remaining monolithic code into services",
                "status": "pending",
                "estimated_hours": 20,
            },
            {
                "id": 4,
                "title": "Unify configuration system",
                "description": "Consolidate multiple configuration systems into one",
                "status": "pending",
                "estimated_hours": 8,
            },
        ],
    },
    {
        "id": next_id + 4,
        "title": "Create Comprehensive Documentation",
        "description": "Add missing README files, create API documentation, write installation guides, and document architecture decisions.",
        "priority": "medium",
        "status": "pending",
        "complexity": "medium",
        "estimated_hours": 24,
        "dependencies": [],
        "subtasks": [
            {
                "id": 1,
                "title": "Add README files to key directories",
                "description": "Create README for 8 major directories without documentation",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 2,
                "title": "Create API documentation",
                "description": "Generate OpenAPI/Swagger documentation for all endpoints",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 3,
                "title": "Write installation and quick-start guide",
                "description": "Create comprehensive setup documentation",
                "status": "pending",
                "estimated_hours": 4,
            },
            {
                "id": 4,
                "title": "Document architecture decisions",
                "description": "Create ADRs for key architectural choices",
                "status": "pending",
                "estimated_hours": 4,
            },
        ],
    },
    {
        "id": next_id + 5,
        "title": "Implement Performance Optimizations",
        "description": "Replace synchronous operations with async patterns, optimize database queries, implement streaming for large data exports.",
        "priority": "medium",
        "status": "pending",
        "complexity": "high",
        "estimated_hours": 32,
        "dependencies": [next_id + 2],  # Depends on code quality improvements
        "subtasks": [
            {
                "id": 1,
                "title": "Implement async/await patterns",
                "description": "Convert blocking I/O operations to async",
                "status": "pending",
                "estimated_hours": 12,
            },
            {
                "id": 2,
                "title": "Optimize database queries",
                "description": "Fix N+1 queries and add query optimization",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 3,
                "title": "Implement data streaming",
                "description": "Add streaming for large data exports",
                "status": "pending",
                "estimated_hours": 8,
            },
            {
                "id": 4,
                "title": "Configure connection pooling",
                "description": "Properly configure database connection pools",
                "status": "pending",
                "estimated_hours": 4,
            },
        ],
    },
]

# Add new tasks to the data
data["tasks"].extend(new_tasks)

# Update metadata if it exists
if "metadata" not in data:
    data["metadata"] = {}
data["metadata"]["last_updated"] = datetime.now().isoformat()
data["metadata"]["total_tasks"] = len(data["tasks"])

# Save updated tasks
with open(".taskmaster/tasks/tasks.json", "w") as f:
    json.dump(data, f, indent=2)


# Print summary of new tasks
for task in new_tasks:
    pass
