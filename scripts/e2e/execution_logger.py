#!/usr/bin/env python3
"""
E2E Pipeline Execution Logger

This module provides comprehensive logging and tracking capabilities for the E2E pipeline,
capturing execution details, failures, and resolutions in structured formats.
"""

import os
import sys
import json
import logging
import datetime
import traceback
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))


class ExecutionLogHandler:
    """
    Handles structured logging of pipeline execution details, with support for
    different log formats and destinations.
    """

    def __init__(self, execution_id: str, log_dir: Optional[str] = None):
        """
        Initialize the ExecutionLogHandler.

        Args:
            execution_id: Unique identifier for the execution being logged
            log_dir: Directory to store logs (defaults to project_root/logs/e2e)
        """
        self.execution_id = execution_id
        self.log_dir = Path(log_dir) if log_dir else Path(project_root) / "logs" / "e2e"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / f"execution_{execution_id}.log"
        self.json_log_file = self.log_dir / f"execution_{execution_id}.json"

        # Initialize execution data structure
        self.execution_data = {
            "execution_id": execution_id,
            "start_time": datetime.datetime.now().isoformat(),
            "end_time": None,
            "duration": None,
            "status": "pending",
            "stages": {},
            "logs": [],
            "failures": [],
            "resolution_attempts": [],
        }

        # Set up logger
        self._setup_logger()

        # Write initial JSON log
        self._write_json_log()

        # Log execution start
        self.logger.info(f"Starting execution {execution_id}")
        self.add_log_entry("info", f"Starting execution {execution_id}")

    def _setup_logger(self):
        """Set up the logger for this execution."""
        self.logger = logging.getLogger(f"execution_{self.execution_id}")
        self.logger.setLevel(logging.DEBUG)

        # Clear any existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()

        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _write_json_log(self):
        """Write the current execution data to the JSON log file."""
        try:
            with open(self.json_log_file, "w") as f:
                json.dump(self.execution_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to write JSON log: {e}")

    def add_log_entry(
        self, level: str, message: str, data: Optional[Dict[str, Any]] = None
    ):
        """
        Add a structured log entry to the execution data.

        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message
            data: Additional structured data for the log entry
        """
        timestamp = datetime.datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "data": data or {},
        }

        self.execution_data["logs"].append(log_entry)
        self._write_json_log()

    def log_stage_start(self, stage_name: str, stage_display_name: str):
        """
        Log the start of a pipeline stage.

        Args:
            stage_name: Internal name of the stage
            stage_display_name: Display name of the stage
        """
        timestamp = datetime.datetime.now().isoformat()

        if stage_name not in self.execution_data["stages"]:
            self.execution_data["stages"][stage_name] = {
                "name": stage_display_name,
                "start_time": timestamp,
                "end_time": None,
                "duration": None,
                "status": "running",
                "retry_count": 0,
                "logs": [],
            }
        else:
            self.execution_data["stages"][stage_name]["start_time"] = timestamp
            self.execution_data["stages"][stage_name]["status"] = "running"

        self.logger.info(f"Stage started: {stage_display_name}")
        self.add_log_entry(
            "info", f"Stage started: {stage_display_name}", {"stage": stage_name}
        )

    def log_stage_end(
        self,
        stage_name: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        Log the end of a pipeline stage.

        Args:
            stage_name: Internal name of the stage
            status: Final status of the stage (success, failure, skipped)
            output: Stage output (if any)
            error: Stage error (if any)
        """
        timestamp = datetime.datetime.now().isoformat()

        if stage_name not in self.execution_data["stages"]:
            self.logger.warning(f"Logging end for unknown stage: {stage_name}")
            return

        stage_data = self.execution_data["stages"][stage_name]
        stage_data["end_time"] = timestamp
        stage_data["status"] = status

        # Calculate duration
        if stage_data["start_time"]:
            start_time = datetime.datetime.fromisoformat(stage_data["start_time"])
            end_time = datetime.datetime.fromisoformat(timestamp)
            duration = (end_time - start_time).total_seconds()
            stage_data["duration"] = duration

        # Add output and error if provided
        if output:
            stage_data["output"] = output

        if error:
            stage_data["error"] = error

        # Log appropriate message
        stage_display_name = stage_data["name"]
        if status == "success":
            self.logger.info(
                f"Stage completed: {stage_display_name} ✅ ({stage_data['duration']:.2f}s)"
            )
            self.add_log_entry(
                "info",
                f"Stage completed: {stage_display_name}",
                {
                    "stage": stage_name,
                    "duration": stage_data["duration"],
                    "status": status,
                },
            )
        elif status == "failure":
            self.logger.error(
                f"Stage failed: {stage_display_name} ❌ ({stage_data['duration']:.2f}s)"
            )
            self.add_log_entry(
                "error",
                f"Stage failed: {stage_display_name}",
                {
                    "stage": stage_name,
                    "duration": stage_data["duration"],
                    "status": status,
                    "error": error,
                },
            )
        else:
            self.logger.info(f"Stage {status}: {stage_display_name}")
            self.add_log_entry(
                "info",
                f"Stage {status}: {stage_display_name}",
                {"stage": stage_name, "status": status},
            )

        self._write_json_log()

    def log_stage_retry(
        self, stage_name: str, retry_count: int, reason: Optional[str] = None
    ):
        """
        Log a stage retry attempt.

        Args:
            stage_name: Internal name of the stage
            retry_count: Current retry count
            reason: Reason for the retry
        """
        if stage_name not in self.execution_data["stages"]:
            self.logger.warning(f"Logging retry for unknown stage: {stage_name}")
            return

        stage_data = self.execution_data["stages"][stage_name]
        stage_data["retry_count"] = retry_count

        stage_display_name = stage_data["name"]
        message = f"Retrying stage: {stage_display_name} (attempt {retry_count})"
        if reason:
            message += f" - Reason: {reason}"

        self.logger.info(message)
        self.add_log_entry(
            "info",
            message,
            {"stage": stage_name, "retry_count": retry_count, "reason": reason},
        )

    def log_failure(
        self,
        stage_name: str,
        category: str,
        message: str,
        resolution: Optional[str] = None,
    ):
        """
        Log a pipeline failure.

        Args:
            stage_name: Internal name of the stage where failure occurred
            category: Failure category
            message: Failure message
            resolution: Suggested resolution
        """
        timestamp = datetime.datetime.now().isoformat()

        failure_data = {
            "timestamp": timestamp,
            "stage": stage_name,
            "category": category,
            "message": message,
            "resolution": resolution or "No resolution available",
        }

        if stage_name in self.execution_data["stages"]:
            stage_display_name = self.execution_data["stages"][stage_name]["name"]
        else:
            stage_display_name = stage_name

        self.execution_data["failures"].append(failure_data)

        self.logger.error(f"Failure in {stage_display_name}: {category} - {message}")
        if resolution:
            self.logger.info(f"Suggested resolution: {resolution}")

        self.add_log_entry("error", f"Failure in {stage_display_name}", failure_data)
        self._write_json_log()

    def log_resolution_attempt(
        self, stage_name: str, issue: str, resolution: str, success: bool, result: str
    ):
        """
        Log a resolution attempt for a failure.

        Args:
            stage_name: Internal name of the stage where resolution was attempted
            issue: Issue being resolved
            resolution: Resolution action taken
            success: Whether the resolution was successful
            result: Result of the resolution attempt
        """
        timestamp = datetime.datetime.now().isoformat()

        resolution_data = {
            "timestamp": timestamp,
            "stage": stage_name,
            "issue": issue,
            "resolution": resolution,
            "success": success,
            "result": result,
        }

        if stage_name in self.execution_data["stages"]:
            stage_display_name = self.execution_data["stages"][stage_name]["name"]
        else:
            stage_display_name = stage_name

        self.execution_data["resolution_attempts"].append(resolution_data)

        status_icon = "✅" if success else "❌"
        self.logger.info(
            f"Resolution attempt for {stage_display_name}: {status_icon} {result}"
        )

        self.add_log_entry(
            "info", f"Resolution attempt for {stage_display_name}", resolution_data
        )
        self._write_json_log()

    def log_execution_end(self, status: str):
        """
        Log the end of the pipeline execution.

        Args:
            status: Final status of the execution (success, failure, partial_success)
        """
        timestamp = datetime.datetime.now().isoformat()
        self.execution_data["end_time"] = timestamp
        self.execution_data["status"] = status

        # Calculate duration
        if self.execution_data["start_time"]:
            start_time = datetime.datetime.fromisoformat(
                self.execution_data["start_time"]
            )
            end_time = datetime.datetime.fromisoformat(timestamp)
            duration = (end_time - start_time).total_seconds()
            self.execution_data["duration"] = duration

        # Log appropriate message
        status_icon = "✅" if status == "success" else "❌"
        self.logger.info(
            f"Execution {self.execution_id} completed with status: {status} {status_icon}"
        )
        if self.execution_data["duration"]:
            self.logger.info(
                f"Total duration: {self.execution_data['duration']:.2f} seconds"
            )

        if status != "success":
            num_failures = len(self.execution_data["failures"])
            self.logger.info(f"Total failures: {num_failures}")

        self.add_log_entry(
            "info",
            f"Execution completed with status: {status}",
            {
                "status": status,
                "duration": self.execution_data["duration"],
                "failures": len(self.execution_data["failures"]),
            },
        )

        self._write_json_log()

    def get_execution_data(self) -> Dict[str, Any]:
        """
        Get a copy of the current execution data.

        Returns:
            The current execution data dictionary
        """
        return self.execution_data.copy()


class ExecutionTracker:
    """
    Tracks and stores execution history, providing search and analysis capabilities
    across multiple pipeline executions.
    """

    def __init__(self, history_file: Optional[str] = None):
        """
        Initialize the ExecutionTracker.

        Args:
            history_file: Path to the execution history JSON file
        """
        self.history_file = (
            Path(history_file)
            if history_file
            else Path(project_root) / "scripts" / "e2e" / "execution_history.json"
        )
        self.history_data = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load execution history from the history file."""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Failed to load execution history: {e}")
            return []

    def _save_history(self):
        """Save the current history data to the history file."""
        try:
            # Create directory if it doesn't exist
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.history_file, "w") as f:
                json.dump(self.history_data, f, indent=2)
        except OSError as e:
            logging.error(f"Failed to save execution history: {e}")

    def add_execution(self, execution_data: Dict[str, Any]):
        """
        Add an execution to the history.

        Args:
            execution_data: Execution data to add
        """
        # Check if this execution is already in the history
        existing_index = None
        for i, existing in enumerate(self.history_data):
            if existing.get("execution_id") == execution_data.get("execution_id"):
                existing_index = i
                break

        # Update or append
        if existing_index is not None:
            self.history_data[existing_index] = execution_data
        else:
            self.history_data.append(execution_data)

        # Keep only the last 100 executions
        if len(self.history_data) > 100:
            self.history_data = self.history_data[-100:]

        # Save to file
        self._save_history()

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific execution by ID.

        Args:
            execution_id: Execution ID to retrieve

        Returns:
            The execution data if found, None otherwise
        """
        for execution in self.history_data:
            if execution.get("execution_id") == execution_id:
                return execution

        return None

    def get_recent_executions(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent executions.

        Args:
            count: Number of recent executions to retrieve

        Returns:
            List of recent execution data
        """
        return (
            self.history_data[-count:]
            if len(self.history_data) >= count
            else self.history_data
        )

    def search_executions(
        self,
        status: Optional[str] = None,
        stage_name: Optional[str] = None,
        failure_category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for executions matching the given criteria.

        Args:
            status: Filter by execution status
            stage_name: Filter by stage name
            failure_category: Filter by failure category
            date_from: Filter by start date (ISO format)
            date_to: Filter by end date (ISO format)

        Returns:
            List of matching execution data
        """
        results = []

        for execution in self.history_data:
            # Filter by status
            if status and execution.get("status") != status:
                continue

            # Filter by date range
            if date_from or date_to:
                start_time = execution.get("start_time")
                if not start_time:
                    continue

                if date_from and start_time < date_from:
                    continue

                if date_to and start_time > date_to:
                    continue

            # Filter by stage name
            if stage_name:
                stages = execution.get("stages", {})
                if stage_name not in stages:
                    continue

            # Filter by failure category
            if failure_category:
                failures = execution.get("failures", [])
                if not any(
                    failure.get("category") == failure_category for failure in failures
                ):
                    continue

            results.append(execution)

        return results

    def get_success_rate(self, recent_count: Optional[int] = None) -> float:
        """
        Calculate the success rate of recent executions.

        Args:
            recent_count: Number of recent executions to consider (None for all)

        Returns:
            Success rate as a percentage
        """
        if recent_count is not None:
            executions = self.get_recent_executions(recent_count)
        else:
            executions = self.history_data

        if not executions:
            return 0.0

        success_count = sum(
            1 for execution in executions if execution.get("status") == "success"
        )
        return (success_count / len(executions)) * 100

    def get_stage_reliability(
        self, stage_name: str, recent_count: Optional[int] = None
    ) -> Dict[str, Union[float, int]]:
        """
        Calculate the reliability of a specific stage.

        Args:
            stage_name: Name of the stage to analyze
            recent_count: Number of recent executions to consider (None for all)

        Returns:
            Dictionary with reliability metrics
        """
        if recent_count is not None:
            executions = self.get_recent_executions(recent_count)
        else:
            executions = self.history_data

        if not executions:
            return {
                "success_rate": 0.0,
                "total_runs": 0,
                "success_count": 0,
                "failure_count": 0,
                "retry_rate": 0.0,
                "avg_duration": 0.0,
            }

        total_runs = 0
        success_count = 0
        failure_count = 0
        retry_count = 0
        durations = []

        for execution in executions:
            stages = execution.get("stages", {})
            if stage_name not in stages:
                continue

            stage_data = stages[stage_name]
            total_runs += 1

            if stage_data.get("status") == "success":
                success_count += 1
            elif stage_data.get("status") == "failure":
                failure_count += 1

            retry_count += stage_data.get("retry_count", 0)

            if stage_data.get("duration") is not None:
                durations.append(stage_data["duration"])

        if total_runs == 0:
            return {
                "success_rate": 0.0,
                "total_runs": 0,
                "success_count": 0,
                "failure_count": 0,
                "retry_rate": 0.0,
                "avg_duration": 0.0,
            }

        success_rate = (success_count / total_runs) * 100
        retry_rate = retry_count / total_runs
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "success_rate": success_rate,
            "total_runs": total_runs,
            "success_count": success_count,
            "failure_count": failure_count,
            "retry_rate": retry_rate,
            "avg_duration": avg_duration,
        }

    def get_common_failures(self, recent_count: Optional[int] = None) -> Dict[str, int]:
        """
        Get the most common failure categories.

        Args:
            recent_count: Number of recent executions to consider (None for all)

        Returns:
            Dictionary mapping failure categories to counts
        """
        if recent_count is not None:
            executions = self.get_recent_executions(recent_count)
        else:
            executions = self.history_data

        failure_counts = {}

        for execution in executions:
            failures = execution.get("failures", [])
            for failure in failures:
                category = failure.get("category", "unknown")
                failure_counts[category] = failure_counts.get(category, 0) + 1

        return failure_counts


def configure_error_logging(log_dir: Optional[str] = None):
    """
    Configure global exception logging to capture unhandled exceptions.

    Args:
        log_dir: Directory to store error logs
    """
    log_dir_path = Path(log_dir) if log_dir else Path(project_root) / "logs" / "e2e"
    log_dir_path.mkdir(parents=True, exist_ok=True)

    error_log_file = log_dir_path / "unhandled_exceptions.log"

    # Set up error logger
    error_logger = logging.getLogger("error_logger")
    error_logger.setLevel(logging.ERROR)

    # Clear any existing handlers
    if error_logger.handlers:
        error_logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(error_log_file)
    file_handler.setLevel(logging.ERROR)

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    # Add handler
    error_logger.addHandler(file_handler)

    # Set up global exception handler
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions by logging them."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupt (ctrl+c)
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_logger.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    # Install the exception handler
    sys.excepthook = handle_exception
