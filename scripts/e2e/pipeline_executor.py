#!/usr/bin/env python3
"""
E2E Pipeline Execution and Resolution Loop

This module implements a continuous execution and resolution loop for the E2E pipeline
that automatically identifies, logs, and assists in resolving failures, creating a
self-improving system that maintains pipeline reliability.
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.execution_logger import (
    ExecutionLogHandler,
    ExecutionTracker,
    configure_error_logging,
)
from scripts.e2e.failure_analyzer import FailureAnalyzer
from scripts.e2e.task_generator import TaskGenerator
from scripts.preflight.preflight_check import PreflightCheck

# Configure logging
log_dir = Path(project_root) / "logs" / "e2e"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = (
    log_dir
    / f"pipeline_executor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Configure error logging
configure_error_logging(str(log_dir))


class ExecutionStatus:
    """Status codes for pipeline execution steps"""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    PARTIAL = "partial_success"
    PENDING = "pending"


class PipelineStage:
    """Pipeline stage definition"""

    def __init__(self, name: str, script_path: str, depends_on: list[str] = None):
        self.name = name
        self.script_path = script_path
        self.depends_on = depends_on or []
        self.status = ExecutionStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.duration = None
        self.output = ""
        self.error = ""
        self.retry_count = 0


class FailureCategory:
    """Categories of pipeline failures"""

    ENVIRONMENT = "environment_issue"
    API = "api_failure"
    DATABASE = "database_issue"
    RESOURCE = "resource_limitation"
    CODE = "code_bug"
    DATA = "data_issue"
    NETWORK = "network_issue"
    PERMISSION = "permission_issue"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown_error"


class PipelineExecutor:
    """
    Manages the execution of the E2E pipeline with automatic failure detection,
    resolution suggestions, and retry mechanisms.
    """

    def __init__(
        self,
        env_file: str = ".env.e2e",
        max_retries: int = 3,
        resolution_mode: bool = False,
        auto_task_generation: bool = True,
    ):
        """
        Initialize the pipeline executor.

        Args:
            env_file: Path to the environment file
            max_retries: Maximum number of retries for failed stages
            resolution_mode: Whether to attempt automatic resolution of failures
            auto_task_generation: Whether to automatically generate tasks for failures
        """
        self.env_file = env_file
        self.max_retries = max_retries
        self.resolution_mode = resolution_mode
        self.auto_task_generation = auto_task_generation

        # Set up logger and tracker
        self.execution_id = f"exec_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.logger = ExecutionLogHandler(self.execution_id)
        self.tracker = ExecutionTracker()

        # Set up failure analyzer and task generator
        self.analyzer = FailureAnalyzer()
        self.task_generator = TaskGenerator()

        # Initialize pipeline state
        self.start_time = None
        self.end_time = None
        self.stages = {}
        self.current_stage = None
        self.results = {
            "status": "pending",
            "failures": [],
            "resolution_attempts": [],
            "generated_tasks": [],
            "stages": {},  # Add this to store stage results
        }

        # Load known issues
        self.known_issues_file = project_root / "scripts" / "e2e" / "known_issues.json"
        self.known_issues = self._load_known_issues()

    def _load_known_issues(self) -> dict[str, dict[str, Any]]:
        """Load known issues from the registry file."""
        if not self.known_issues_file.exists():
            # Create default known issues file if it doesn't exist
            default_issues = {
                "environment_issues": {
                    "missing_api_key": {
                        "pattern": "Missing required variable: (?P<key>.+)",
                        "resolution": "Add the missing variable to your .env.e2e file",
                        "category": FailureCategory.ENVIRONMENT,
                    },
                    "invalid_api_key": {
                        "pattern": "(?P<key>.+) has invalid format: '(?P<value>.+)'",
                        "resolution": "Update the API key with a valid format",
                        "category": FailureCategory.ENVIRONMENT,
                    },
                },
                "api_issues": {
                    "api_timeout": {
                        "pattern": "Timeout connecting to (?P<api>.+) API",
                        "resolution": "Check your internet connection or API endpoint status",
                        "category": FailureCategory.NETWORK,
                    },
                    "api_unauthorized": {
                        "pattern": "(?P<api>.+) API returned 401 Unauthorized",
                        "resolution": "Verify your API key is correct and not expired",
                        "category": FailureCategory.API,
                    },
                },
                "database_issues": {
                    "connection_error": {
                        "pattern": "Could not connect to database: (?P<error>.+)",
                        "resolution": "Verify your DATABASE_URL and ensure the database is running",
                        "category": FailureCategory.DATABASE,
                    },
                    "schema_error": {
                        "pattern": "Table '(?P<table>.+)' does not exist",
                        "resolution": "Run database migrations to create the required tables",
                        "category": FailureCategory.DATABASE,
                    },
                },
            }

            with open(self.known_issues_file, "w") as f:
                json.dump(default_issues, f, indent=2)

            return default_issues

        try:
            with open(self.known_issues_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.error(f"Failed to load known issues from {self.known_issues_file}")
            return {}

    def execute_pipeline(self) -> bool:
        """
        Execute the pipeline stages.

        Returns:
            bool: True if all stages succeeded, False otherwise
        """
        self.start_time = datetime.datetime.now()
        # ExecutionLogHandler logs the start in its constructor

        logger.info(f"Starting pipeline execution {self.execution_id}")
        logger.info(f"Using environment file: {self.env_file}")

        # Run preflight check
        preflight_success = self.run_preflight_check()

        if not preflight_success:
            logger.error("Preflight check failed, aborting pipeline")
            self.end_time = datetime.datetime.now()
            self.results["status"] = "failure"
            self.logger.log_execution_end("failure")
            self.tracker.add_execution(self.logger.get_execution_data())

            # Generate tasks for preflight failures if enabled
            if self.auto_task_generation and self.results["failures"]:
                self._generate_tasks_for_failures()

            return False

        # Run pipeline stages
        overall_success = True

        for stage_name, stage_config in self._get_pipeline_stages().items():
            stage_success = self._execute_stage(stage_name, stage_config)

            if not stage_success:
                overall_success = False

                # Attempt resolution if enabled
                if self.resolution_mode and self.results["failures"]:
                    logger.info("Attempting to resolve failures...")
                    resolved = self._attempt_resolution(self.results["failures"])

                    if resolved:
                        logger.info(
                            "Successfully resolved failures, retrying failed stages"
                        )

                        # Retry failed stages
                        retry_success = self._retry_failed_stages()

                        if retry_success:
                            logger.info("Successfully recovered from failures")
                            overall_success = True
                        else:
                            logger.error("Failed to recover from failures")
                    else:
                        logger.error("Failed to resolve failures")

        # Record final status
        if overall_success:
            logger.info("Pipeline execution completed successfully")
            self.results["status"] = "success"
            self.logger.log_execution_end("success")
        else:
            logger.error("Pipeline execution failed")
            self.results["status"] = "failure"
            self.logger.log_execution_end("failure")

            # Generate tasks for failures if enabled
            if self.auto_task_generation and self.results["failures"]:
                self._generate_tasks_for_failures()

        # Record execution time
        self.end_time = datetime.datetime.now()

        # Save execution data
        self.tracker.add_execution(self.logger.get_execution_data())

        # If this is the 10th execution, analyze for recurring patterns and create optimization tasks
        executions_count = len(self.tracker.get_recent_executions(10))
        if executions_count % 10 == 0 and self.auto_task_generation:
            self._generate_optimization_tasks()

        return overall_success

    def _get_pipeline_stages(self) -> dict[str, dict[str, str]]:
        """Get the pipeline stages configuration."""
        stages = {
            "preflight": {
                "name": "Preflight Check",
                "script_path": "scripts/preflight/preflight_check.py",
                "depends_on": [],
            },
            "scrape": {
                "name": "Web Scraping",
                "script_path": "scripts/pipeline/01_scrape.py",
                "depends_on": ["preflight"],
            },
            "screenshot": {
                "name": "Screenshot Generation",
                "script_path": "scripts/pipeline/02_screenshot.py",
                "depends_on": ["scrape"],
            },
            "mockup": {
                "name": "Mockup Generation",
                "script_path": "scripts/pipeline/03_mockup.py",
                "depends_on": ["screenshot"],
            },
            "personalize": {
                "name": "Email Personalization",
                "script_path": "scripts/pipeline/04_personalize.py",
                "depends_on": ["mockup"],
            },
            "render": {
                "name": "Email Rendering",
                "script_path": "scripts/pipeline/05_render.py",
                "depends_on": ["personalize"],
            },
            "email": {
                "name": "Email Delivery",
                "script_path": "scripts/pipeline/06_email_queue.py",
                "depends_on": ["render"],
            },
            "report": {
                "name": "Result Reporting",
                "script_path": "scripts/e2e/generate_report.py",
                "depends_on": ["email"],
            },
        }

        return stages

    def run_preflight_check(self) -> bool:
        """
        Run the preflight check to validate the environment before pipeline execution.

        Returns:
            bool: True if preflight check passed, False otherwise
        """
        logger.info("Running preflight check...")

        # Get the preflight stage
        stage_name = "preflight"
        stage_config = self._get_pipeline_stages()[stage_name]

        # Log stage start
        self.logger.log_stage_start(stage_name, stage_config["name"])

        # Run preflight check
        preflight = PreflightCheck(env_file=self.env_file)
        result = preflight.run()

        # Record end time
        datetime.datetime.now()

        if result.success:
            # Record success
            self.results["status"] = "success"
            logger.info("Preflight check passed")
            self.logger.log_stage_end(stage_name, "success")

            return True
        else:
            # Record failure
            self.results["status"] = "failure"
            logger.error(f"Preflight check failed: {result.issues}")
            self.logger.log_stage_end(
                stage_name, "failure", error="; ".join(result.issues)
            )

            # Categorize and record the failures
            failures = []
            for issue in result.issues:
                failure_info = self._categorize_failure(stage_name, issue)
                failures.append(failure_info)

                # Log the failure
                self.logger.log_failure(
                    stage_name,
                    failure_info["category"],
                    failure_info["message"],
                    failure_info["resolution"],
                )

            self.results["failures"].extend(failures)

            # Attempt to resolve failures if resolution mode is enabled
            if self.resolution_mode:
                self._attempt_resolution(failures)

            return False

    def _execute_stage(self, stage_name: str, stage_config: dict[str, str]) -> bool:
        """
        Execute a single pipeline stage with retry logic.

        Args:
            stage_name: Name of the stage
            stage_config: Stage configuration

        Returns:
            bool: True if stage executed successfully, False otherwise
        """
        max_attempts = self.max_retries + 1  # Initial attempt + retries
        attempt = 0
        stage_success = False

        while attempt < max_attempts and not stage_success:
            attempt += 1
            if attempt > 1:
                retry_message = f"Retry {attempt - 1}/{self.max_retries} for stage {stage_config['name']}"
                logger.info(retry_message)

                # Log the retry attempt
                self.logger.log_stage_retry(
                    stage_name, attempt - 1, reason="Previous attempt failed"
                )
            else:
                # Log stage start (first attempt)
                self.logger.log_stage_start(stage_name, stage_config["name"])

            # Execute the stage
            start_time = datetime.datetime.now()

            try:
                # Run the stage script
                result = subprocess.run(
                    [sys.executable, stage_config["script_path"]],
                    env=os.environ.copy(),
                    capture_output=True,
                    text=True,
                    check=False,
                )

                output = result.stdout
                error = result.stderr

                if result.returncode == 0:
                    stage_success = True
                    success_message = (
                        f"Stage {stage_config['name']} completed successfully"
                    )
                    logger.info(success_message)

                    # Log stage success
                    self.logger.log_stage_end(stage_name, "success", output=output)
                else:
                    error_message = f"Stage {stage_config['name']} failed with exit code {result.returncode}"
                    logger.error(error_message)
                    logger.error(f"Error: {error}")

                    # Log stage failure
                    self.logger.log_stage_end(stage_name, "failure", error=error)

                    # Categorize and record the failure
                    failure_info = self._categorize_failure(stage_name, error)
                    self.results["failures"].append(failure_info)

                    # Log the failure with comprehensive information
                    self.logger.log_failure(
                        stage_name,
                        failure_info["category"],
                        failure_info["message"],
                        failure_info["resolution"],
                    )

                    # Attempt automatic resolution if enabled
                    if self.resolution_mode and attempt < max_attempts:
                        resolution_success = self._attempt_resolution([failure_info])
                        if not resolution_success:
                            # If resolution failed and we've tried multiple times, break the retry loop
                            if attempt >= max_attempts // 2:
                                give_up_message = f"Giving up on stage {stage_config['name']} after {attempt} attempts"
                                logger.warning(give_up_message)
                                break
            except Exception as e:
                error_message = f"Exception executing stage {stage_config['name']}: {e}"
                logger.exception(error_message)

                # Log stage exception
                self.logger.log_stage_end(stage_name, "failure", error=str(e))

                # Categorize and record the failure
                failure_info = {
                    "stage": stage_name,
                    "category": FailureCategory.UNKNOWN,
                    "message": str(e),
                    "resolution": "Investigate the unexpected exception",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "attempt": attempt,
                }
                self.results["failures"].append(failure_info)

                # Log the failure
                self.logger.log_failure(
                    stage_name,
                    FailureCategory.UNKNOWN,
                    str(e),
                    "Investigate the unexpected exception",
                )
            finally:
                end_time = datetime.datetime.now()
                duration = (end_time - start_time).total_seconds()

                # Record stage results
                self.results["stages"][stage_name] = {
                    "name": stage_config["name"],
                    "status": "success" if stage_success else "failure",
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration": duration,
                    "retry_count": attempt - 1 if not stage_success else 0,
                    "error": error if not stage_success else None,
                }

        return stage_success

    def _categorize_failure(
        self, stage_name: str, error_message: str
    ) -> dict[str, str]:
        """
        Categorize a failure based on the error message and known issues.

        Args:
            stage_name: Name of the stage where the failure occurred
            error_message: Error message from the failed stage

        Returns:
            Dict with failure category, message, and resolution suggestion
        """
        import re

        # Initialize with default unknown error
        failure_info = {
            "stage": stage_name,
            "category": FailureCategory.UNKNOWN,
            "message": error_message,
            "resolution": "Investigate the error message for more details",
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # Check against known issues
        for issue_type, issues in self.known_issues.items():
            for issue_name, issue_info in issues.items():
                pattern = issue_info["pattern"]
                match = re.search(pattern, error_message)

                if match:
                    failure_info["category"] = issue_info["category"]
                    failure_info["issue_type"] = issue_type
                    failure_info["issue_name"] = issue_name

                    # Format resolution with matched groups
                    resolution = issue_info["resolution"]
                    for name, value in match.groupdict().items():
                        resolution = resolution.replace(f"{{{name}}}", value)

                    failure_info["resolution"] = resolution
                    return failure_info

        # Heuristic categorization if no known issue matched
        if "api key" in error_message.lower() or "apikey" in error_message.lower():
            failure_info["category"] = FailureCategory.API
            failure_info["resolution"] = "Verify your API keys in the .env.e2e file"
        elif (
            "database" in error_message.lower()
            or "db" in error_message.lower()
            or "sql" in error_message.lower()
        ):
            failure_info["category"] = FailureCategory.DATABASE
            failure_info["resolution"] = "Check database connection and schema"
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            failure_info["category"] = FailureCategory.TIMEOUT
            failure_info["resolution"] = (
                "Increase timeout settings or check network connectivity"
            )
        elif (
            "permission" in error_message.lower()
            or "access denied" in error_message.lower()
        ):
            failure_info["category"] = FailureCategory.PERMISSION
            failure_info["resolution"] = "Check file/resource permissions"
        elif (
            "network" in error_message.lower() or "connection" in error_message.lower()
        ):
            failure_info["category"] = FailureCategory.NETWORK
            failure_info["resolution"] = (
                "Verify network connectivity to required services"
            )

        return failure_info

    def _attempt_resolution(self, failures: list[dict[str, str]]) -> bool:
        """
        Attempt to automatically resolve failures.

        Args:
            failures: List of failure dictionaries

        Returns:
            bool: True if all failures were resolved, False otherwise
        """
        if not failures:
            return True

        all_resolved = True

        for failure in failures:
            stage = failure["stage"]
            category = failure["category"]
            resolution = failure["resolution"]

            attempt_message = (
                f"Attempting to resolve {category} failure in {stage}: {resolution}"
            )
            logger.info(attempt_message)
            self.logger.add_log_entry("info", attempt_message)

            resolution_attempt = {
                "stage": stage,
                "issue": failure["message"],
                "category": category,
                "resolution": resolution,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": False,
                "result": "Not implemented",
            }

            # Implement resolution strategies based on failure category
            if category == FailureCategory.ENVIRONMENT:
                resolved = self._resolve_environment_issue(failure)
                resolution_attempt["success"] = resolved
                resolution_attempt["result"] = (
                    "Environment variable updated"
                    if resolved
                    else "Failed to update environment variable"
                )
            elif category == FailureCategory.DATABASE:
                resolved = self._resolve_database_issue(failure)
                resolution_attempt["success"] = resolved
                resolution_attempt["result"] = (
                    "Database issue resolved"
                    if resolved
                    else "Failed to resolve database issue"
                )
            else:
                # No automatic resolution available
                resolved = False
                resolution_attempt["result"] = (
                    "No automatic resolution available for this category"
                )

            self.results["resolution_attempts"].append(resolution_attempt)

            # Log the resolution attempt with the comprehensive logger
            self.logger.log_resolution_attempt(
                stage,
                failure["message"],
                resolution,
                resolved,
                resolution_attempt["result"],
            )

            if not resolved:
                all_resolved = False
                failure_message = f"Failed to resolve {category} issue in {stage}"
                logger.warning(failure_message)
            else:
                success_message = f"Successfully resolved {category} issue in {stage}"
                logger.info(success_message)

        return all_resolved

    def _resolve_environment_issue(self, failure: dict[str, str]) -> bool:
        """
        Attempt to resolve environment-related issues.

        Args:
            failure: Failure dictionary

        Returns:
            bool: True if the issue was resolved, False otherwise
        """
        # Not implementing actual environment modification for safety
        # This would be where you could update .env.e2e file or set environment variables

        logger.info("Environment issue resolution would be implemented here")
        logger.info(f"Would attempt to fix: {failure['message']}")

        # Log detailed resolution steps
        self.logger.add_log_entry(
            "info",
            "Environment issue resolution attempt",
            {
                "failure": failure,
                "resolution_steps": [
                    "Identify the missing or invalid environment variable",
                    "Check for common misconfigurations",
                    "Update the .env.e2e file with correct values",
                ],
                "actual_implementation": "Mock implementation only, not actually modifying environment",
            },
        )

        # For now, just return False to indicate we can't automatically resolve
        return False

    def _resolve_database_issue(self, failure: dict[str, str]) -> bool:
        """
        Attempt to resolve database-related issues.

        Args:
            failure: Failure dictionary

        Returns:
            bool: True if the issue was resolved, False otherwise
        """
        # Not implementing actual database modifications for safety
        # This would be where you could run migrations, create tables, etc.

        logger.info("Database issue resolution would be implemented here")
        logger.info(f"Would attempt to fix: {failure['message']}")

        # Log detailed resolution steps
        self.logger.add_log_entry(
            "info",
            "Database issue resolution attempt",
            {
                "failure": failure,
                "resolution_steps": [
                    "Check database connection and credentials",
                    "Verify database server is running",
                    "Run database migrations if tables are missing",
                    "Seed sample data if required data is missing",
                ],
                "actual_implementation": "Mock implementation only, not actually modifying database",
            },
        )

        # For now, just return False to indicate we can't automatically resolve
        return False

    def _generate_tasks_for_failures(self) -> None:
        """
        Generate tasks for the failures encountered during pipeline execution.
        """
        if not self.results["failures"]:
            return

        logger.info(f"Generating tasks for {len(self.results['failures'])} failures")
        self.logger.add_log_entry(
            "info",
            "Generating tasks for failures",
            {"failure_count": len(self.results["failures"])},
        )

        task_ids = []

        for failure in self.results["failures"]:
            # Create a task for the failure
            task_id = self.task_generator.create_task_from_failure(
                execution_id=self.execution_id, failure=failure
            )

            if task_id:
                task_ids.append(task_id)
                self.logger.add_log_entry(
                    "info",
                    "Created task for failure",
                    {
                        "task_id": task_id,
                        "stage": failure["stage"],
                        "category": failure["category"],
                    },
                )

        # Store the generated task IDs
        self.results["generated_tasks"] = task_ids

        # Generate individual task files
        if task_ids:
            self.task_generator.generate_task_files()
            logger.info(f"Generated {len(task_ids)} tasks for failures")

    def _generate_optimization_tasks(self) -> None:
        """
        Generate optimization tasks based on execution history analysis.
        """
        logger.info("Analyzing execution history for recurring patterns")
        self.logger.add_log_entry(
            "info", "Analyzing execution history for optimization opportunities"
        )

        # Create optimization task based on recurring patterns
        optimization_task_id = (
            self.task_generator.create_optimization_task_from_analysis()
        )

        if optimization_task_id:
            self.results["generated_tasks"].append(optimization_task_id)
            self.logger.add_log_entry(
                "info", "Created optimization task", {"task_id": optimization_task_id}
            )

        # Create reliability improvement task
        improvement_task_id = (
            self.task_generator.create_improvement_task_from_reliability()
        )

        if improvement_task_id:
            self.results["generated_tasks"].append(improvement_task_id)
            self.logger.add_log_entry(
                "info",
                "Created reliability improvement task",
                {"task_id": improvement_task_id},
            )

        # Generate individual task files
        if optimization_task_id or improvement_task_id:
            self.task_generator.generate_task_files()
            logger.info("Generated optimization tasks based on execution history")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="E2E Pipeline Execution and Resolution Loop"
    )
    parser.add_argument("--env", default=".env.e2e", help="Path to environment file")
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Maximum number of retries for failed stages",
    )
    parser.add_argument(
        "--no-resolution",
        action="store_true",
        help="Disable automatic resolution attempts",
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run in continuous mode with interval"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Interval in seconds for continuous mode",
    )

    args = parser.parse_args()

    if args.continuous:
        logger.info(f"Starting continuous execution with {args.interval}s interval")

        try:
            while True:
                executor = PipelineExecutor(
                    env_file=args.env,
                    max_retries=args.retries,
                    resolution_mode=not args.no_resolution,
                )
                executor.execute_pipeline()

                logger.info(
                    f"Sleeping for {args.interval} seconds until next execution"
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Continuous execution stopped by user")
    else:
        executor = PipelineExecutor(
            env_file=args.env,
            max_retries=args.retries,
            resolution_mode=not args.no_resolution,
        )
        success = executor.execute_pipeline()

        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
