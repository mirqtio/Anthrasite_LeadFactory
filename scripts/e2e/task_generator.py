#!/usr/bin/env python3
"""
Task Generator for E2E Pipeline Failures

This module automatically generates tasks based on failure analysis
and patterns detected in the E2E pipeline execution.
"""

import datetime
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.failure_analyzer import FailureAnalyzer


class TaskPriority:
    """Enum-like class for task priorities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus:
    """Enum-like class for task statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    DEFERRED = "deferred"


class TaskType:
    """Enum-like class for task types."""

    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    MAINTENANCE = "maintenance"
    DOCUMENTATION = "documentation"
    INFRASTRUCTURE = "infrastructure"


class TaskGenerator:
    """
    Generates tasks based on pipeline execution failures.
    """

    def __init__(self, tasks_file: Optional[str] = None):
        """
        Initialize the TaskGenerator.

        Args:
            tasks_file: Path to the tasks JSON file
        """
        self.tasks_file = tasks_file or str(project_root / "tasks" / "tasks.json")

        # Set up logger
        self.logger = logging.getLogger("task_generator")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # Formatter
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            console_handler.setFormatter(formatter)

            # Add handler
            self.logger.addHandler(console_handler)

        self.analyzer = FailureAnalyzer()
        self.tasks = self._load_tasks()

    def _load_tasks(self) -> dict[str, Any]:
        """
        Load tasks from the tasks file.

        Returns:
            Dictionary containing tasks data
        """
        if not os.path.exists(self.tasks_file):
            self.logger.warning(f"Tasks file not found: {self.tasks_file}")
            return {"tasks": []}

        try:
            with open(self.tasks_file) as f:
                tasks_data = json.load(f)
                self.logger.info(f"Loaded tasks from {self.tasks_file}")
                return tasks_data
        except (json.JSONDecodeError, OSError) as e:
            self.logger.error(f"Failed to load tasks: {e}")
            return {"tasks": []}

    def _save_tasks(self) -> bool:
        """
        Save tasks to the tasks file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)

            with open(self.tasks_file, "w") as f:
                json.dump(self.tasks, f, indent=2)

            self.logger.info(f"Saved tasks to {self.tasks_file}")
            return True
        except OSError as e:
            self.logger.error(f"Failed to save tasks: {e}")
            return False

    def _get_next_task_id(self) -> int:
        """
        Get the next available task ID.

        Returns:
            Next available task ID
        """
        max_id = 0

        for task in self.tasks.get("tasks", []):
            # Check if it's a numeric task ID
            task_id = task.get("id", "")
            if isinstance(task_id, int):
                max_id = max(max_id, task_id)
            elif isinstance(task_id, str) and task_id.isdigit():
                max_id = max(max_id, int(task_id))
            elif isinstance(task_id, str) and "." in task_id:
                # Handle subtask IDs like "35.3"
                main_id = task_id.split(".")[0]
                if main_id.isdigit():
                    max_id = max(max_id, int(main_id))

        return max_id + 1

    def _get_next_subtask_id(self, parent_id: str) -> str:
        """
        Get the next available subtask ID for a parent task.

        Args:
            parent_id: Parent task ID

        Returns:
            Next available subtask ID
        """
        max_subtask_num = 0

        for task in self.tasks.get("tasks", []):
            task_id = task.get("id", "")
            if isinstance(task_id, str) and task_id.startswith(f"{parent_id}."):
                # Extract subtask number
                subtask_num = task_id.split(".")[1]
                if subtask_num.isdigit():
                    max_subtask_num = max(max_subtask_num, int(subtask_num))

        return f"{parent_id}.{max_subtask_num + 1}"

    def create_task_from_failure(
        self,
        execution_id: str,
        failure: dict[str, Any],
        task_type: str = TaskType.BUG,
        priority: str = TaskPriority.MEDIUM,
    ) -> Optional[str]:
        """
        Create a task from a failure.

        Args:
            execution_id: Execution ID
            failure: Failure dictionary
            task_type: Type of task
            priority: Priority of task

        Returns:
            Task ID if successful, None otherwise
        """
        # Extract information from failure
        stage = failure.get("stage", "unknown")
        category = failure.get("category", "unknown")
        message = failure.get("message", "")

        # Analyze the failure
        matching_patterns, context = self.analyzer.analyze_failure(stage, message)

        # Determine task title and description
        if matching_patterns:
            pattern = matching_patterns[0]
            title = f"Fix {pattern.name} in {stage} stage"

            # Get resolution steps
            resolution_steps = self.analyzer.get_resolution_steps(
                pattern.pattern_id, context
            )
            resolution_steps_text = "\n".join(
                [f"- {step}" for step in resolution_steps]
            )

            description = f"""
Failure detected during E2E pipeline execution in the {stage} stage.

**Failure Category**: {category}
**Pattern Detected**: {pattern.name}
**Error Message**: {message}

**Execution ID**: {execution_id}
**Timestamp**: {datetime.datetime.now().isoformat()}

**Suggested Resolution Steps**:
{resolution_steps_text}

**Additional Context**:
{pattern.description}
"""
        else:
            title = f"Fix {category} failure in {stage} stage"
            description = f"""
Failure detected during E2E pipeline execution in the {stage} stage.

**Failure Category**: {category}
**Error Message**: {message}

**Execution ID**: {execution_id}
**Timestamp**: {datetime.datetime.now().isoformat()}

This issue requires investigation as no known pattern was detected.
"""

        # Create the task
        task_id = str(self._get_next_task_id())

        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": TaskStatus.PENDING,
            "priority": priority,
            "type": task_type,
            "created_at": datetime.datetime.now().isoformat(),
            "source": {
                "type": "e2e_pipeline",
                "execution_id": execution_id,
                "stage": stage,
                "category": category,
            },
            "dependencies": [],
        }

        # Add to tasks
        self.tasks.setdefault("tasks", []).append(task)

        # Save tasks
        if self._save_tasks():
            self.logger.info(f"Created task {task_id}: {title}")
            return task_id
        else:
            self.logger.error(f"Failed to create task for failure in {stage}")
            return None

    def create_tasks_from_execution(self, execution_id: str) -> list[str]:
        """
        Create tasks from an execution.

        Args:
            execution_id: Execution ID

        Returns:
            List of created task IDs
        """
        # Get execution data from tracker
        from scripts.e2e.execution_logger import ExecutionTracker

        tracker = ExecutionTracker()
        execution = tracker.get_execution(execution_id)

        if not execution:
            self.logger.error(f"Execution not found: {execution_id}")
            return []

        # Get failures
        failures = execution.get("failures", [])

        if not failures:
            self.logger.info(f"No failures found in execution {execution_id}")
            return []

        # Create a task for each failure
        task_ids = []

        for failure in failures:
            # Determine priority based on stage and category
            stage = failure.get("stage", "unknown")
            failure.get("category", "unknown")

            # Critical priority for preflight failures
            if stage == "preflight":
                priority = TaskPriority.HIGH
            # High priority for data processing failures
            elif stage in ["scrape", "mockup", "personalize"] or stage in [
                "render",
                "email",
            ]:
                priority = TaskPriority.MEDIUM
            else:
                priority = TaskPriority.LOW

            # Create the task
            task_id = self.create_task_from_failure(
                execution_id=execution_id, failure=failure, priority=priority
            )

            if task_id:
                task_ids.append(task_id)

        return task_ids

    def generate_task_files(self) -> bool:
        """
        Generate individual task files from the tasks.json file.

        Returns:
            True if successful, False otherwise
        """
        # Check if dev.js exists
        dev_script = project_root / "scripts" / "dev.js"

        if not os.path.exists(dev_script):
            self.logger.error(f"dev.js script not found: {dev_script}")
            return False

        try:
            # Run dev.js generate command
            import subprocess

            result = subprocess.run(
                ["node", str(dev_script), "generate"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.logger.info("Successfully generated task files")
                return True
            else:
                self.logger.error(f"Failed to generate task files: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error running task generation: {e}")
            return False

    def create_maintenance_task(
        self, title: str, description: str, priority: str = TaskPriority.MEDIUM
    ) -> Optional[str]:
        """
        Create a maintenance task.

        Args:
            title: Task title
            description: Task description
            priority: Task priority

        Returns:
            Task ID if successful, None otherwise
        """
        # Create the task
        task_id = str(self._get_next_task_id())

        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "status": TaskStatus.PENDING,
            "priority": priority,
            "type": TaskType.MAINTENANCE,
            "created_at": datetime.datetime.now().isoformat(),
            "source": {"type": "maintenance", "creator": "task_generator"},
            "dependencies": [],
        }

        # Add to tasks
        self.tasks.setdefault("tasks", []).append(task)

        # Save tasks
        if self._save_tasks():
            self.logger.info(f"Created maintenance task {task_id}: {title}")
            return task_id
        else:
            self.logger.error(f"Failed to create maintenance task: {title}")
            return None

    def create_optimization_task_from_analysis(self) -> Optional[str]:
        """
        Create an optimization task based on execution history analysis.

        Returns:
            Task ID if successful, None otherwise
        """
        # Analyze execution history
        analysis = self.analyzer.analyze_execution_history(30)

        if not analysis:
            self.logger.error("Failed to analyze execution history")
            return None

        # Get recurring patterns
        recurring_patterns = analysis.get("recurring_patterns", [])

        if not recurring_patterns:
            self.logger.info("No recurring failure patterns found")
            return None

        # Find the most frequent pattern
        most_frequent = max(
            recurring_patterns, key=lambda p: p.get("occurrences", 0), default=None
        )

        if not most_frequent:
            return None

        # Create an optimization task
        pattern_name = most_frequent.get("name", "Unknown Pattern")
        stage = most_frequent.get("stage", "unknown")
        category = most_frequent.get("category", "unknown")
        occurrences = most_frequent.get("occurrences", 0)

        title = f"Optimize {stage} stage to prevent recurring {pattern_name} failures"

        description = f"""
Optimization task created based on execution history analysis.

**Recurring Failure Pattern**: {pattern_name}
**Stage**: {stage}
**Category**: {category}
**Occurrences**: {occurrences} in the last 30 executions

**Recommended Actions**:
{os.linesep.join([f"- {step}" for step in most_frequent.get("resolution_steps", [])])}

This optimization will improve the reliability of the E2E pipeline by addressing
a frequently occurring failure pattern.
"""

        # Create the task
        return self.create_maintenance_task(
            title=title,
            description=description,
            priority=TaskPriority.HIGH if occurrences > 5 else TaskPriority.MEDIUM,
        )

    def create_improvement_task_from_reliability(self) -> Optional[str]:
        """
        Create an improvement task based on stage reliability analysis.

        Returns:
            Task ID if successful, None otherwise
        """
        # Analyze execution history
        analysis = self.analyzer.analyze_execution_history(30)

        if not analysis:
            self.logger.error("Failed to analyze execution history")
            return None

        # Get stage reliability
        stage_reliability = analysis.get("stage_reliability", {})

        if not stage_reliability:
            self.logger.info("No stage reliability data found")
            return None

        # Find the least reliable stage with at least 5 runs
        least_reliable_stage = None
        lowest_reliability = 100.0

        for stage_name, data in stage_reliability.items():
            runs = data.get("runs", 0)
            reliability = data.get("reliability", 100.0)

            if runs >= 5 and reliability < lowest_reliability:
                lowest_reliability = reliability
                least_reliable_stage = stage_name

        if not least_reliable_stage or lowest_reliability > 80.0:
            # Only create tasks for stages with < 80% reliability
            return None

        # Create an improvement task
        title = f"Improve reliability of {least_reliable_stage} stage ({lowest_reliability:.1f}% success rate)"

        description = f"""
Improvement task created based on stage reliability analysis.

**Stage**: {least_reliable_stage}
**Current Reliability**: {lowest_reliability:.1f}%
**Success/Total**: {stage_reliability[least_reliable_stage].get("successes", 0)}/{stage_reliability[least_reliable_stage].get("runs", 0)}

**Recommended Actions**:
- Review recent failures in this stage
- Identify common patterns or root causes
- Implement error handling improvements
- Add additional logging for debugging
- Consider refactoring critical components

This improvement will enhance the overall reliability of the E2E pipeline by
addressing issues in the least reliable stage.
"""

        # Create the task
        return self.create_maintenance_task(
            title=title,
            description=description,
            priority=(
                TaskPriority.HIGH if lowest_reliability < 50.0 else TaskPriority.MEDIUM
            ),
        )


def main():
    """Main entry point for the task generator."""
    import argparse

    parser = argparse.ArgumentParser(description="E2E Pipeline Task Generator")
    parser.add_argument(
        "--execution-id", help="Generate tasks from a specific execution ID"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Create optimization tasks from history analysis",
    )
    parser.add_argument(
        "--generate-files", action="store_true", help="Generate individual task files"
    )

    args = parser.parse_args()

    generator = TaskGenerator()

    if args.execution_id:
        task_ids = generator.create_tasks_from_execution(args.execution_id)

        if task_ids:
            for _task_id in task_ids:
                pass
        else:
            pass

    if args.analyze:
        # Create optimization task
        optimization_task_id = generator.create_optimization_task_from_analysis()

        if optimization_task_id:
            pass

        # Create reliability improvement task
        improvement_task_id = generator.create_improvement_task_from_reliability()

        if improvement_task_id:
            pass

    if args.generate_files:
        success = generator.generate_task_files()

        if success:
            pass
        else:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
