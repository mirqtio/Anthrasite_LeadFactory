#!/usr/bin/env python3
import json


def analyze_task_complexity():
    # Read the tasks
    with open(".taskmaster/tasks/tasks.json") as f:
        data = json.load(f)

    # Filter for our new tasks (IDs 41-60)
    new_tasks = [t for t in data["tasks"] if 41 <= t["id"] <= 60]

    # Define complexity factors
    complexity_scores = {}

    for task in new_tasks:
        score = 0
        reasons = []

        # Check for API integrations
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["api", "integration", "webhook", "external"]
        ):
            score += 3
            reasons.append("External API integration")

        # Check for infrastructure changes
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["infrastructure", "backup", "migration", "database"]
        ):
            score += 3
            reasons.append("Infrastructure changes")

        # Check for compliance/security
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["compliance", "security", "can-spam", "legal"]
        ):
            score += 2
            reasons.append("Compliance/Security requirements")

        # Check for AI/ML components
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["gpt", "ai", "machine learning", "personalization"]
        ):
            score += 3
            reasons.append("AI/ML components")

        # Check for financial/cost tracking
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["cost", "spend", "financial", "profit", "buffer"]
        ):
            score += 2
            reasons.append("Financial tracking")

        # Check for email deliverability
        if any(
            word in task["title"].lower() or word in task["details"].lower()
            for word in ["bounce", "warm-up", "deliverability", "ip pool"]
        ):
            score += 4
            reasons.append("Email deliverability complexity")

        # Check for multi-system coordination
        if len(task.get("dependencies", [])) > 0:
            score += 1
            reasons.append("Has dependencies")

        complexity_scores[task["id"]] = {
            "title": task["title"],
            "score": score,
            "reasons": reasons,
            "priority": task["priority"],
        }

    # Sort by complexity score
    sorted_tasks = sorted(
        complexity_scores.items(), key=lambda x: x[1]["score"], reverse=True
    )

    high_complexity = []
    for task_id, info in sorted_tasks:
        if info["score"] >= 5:
            high_complexity.append((task_id, info))

    for task_id, info in sorted_tasks:
        if 3 <= info["score"] < 5:
            pass

    for task_id, info in high_complexity:
        if info["priority"] == "high":
            pass


if __name__ == "__main__":
    analyze_task_complexity()
