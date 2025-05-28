#!/usr/bin/env python3
"""
Test Runner for E2E Pipeline Execution and Resolution Loop

This script executes the pipeline in a test mode to validate the implementation.
"""

import os
import sys
import argparse
import datetime
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.pipeline_executor import PipelineExecutor
from scripts.e2e.execution_logger import ExecutionTracker


def setup_test_env():
    """Set up a test environment for the pipeline execution."""
    # Create test log directory
    log_dir = project_root / "logs" / "e2e" / "test"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create test data directory
    test_data_dir = project_root / "test_data" / "e2e"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # Return paths
    return {"log_dir": str(log_dir), "test_data_dir": str(test_data_dir)}


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Test Runner for E2E Pipeline Execution"
    )
    parser.add_argument("--env", default=".env.e2e", help="Path to environment file")
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Maximum number of retries for failed stages",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (simulate stage execution)",
    )
    parser.add_argument(
        "--fail-stage", help="Simulate failure in specified stage (requires --mock)"
    )

    args = parser.parse_args()

    # Set up test environment
    paths = setup_test_env()
    print(f"Set up test environment:")
    print(f"- Log directory: {paths['log_dir']}")
    print(f"- Test data directory: {paths['test_data_dir']}")

    # Create a timestamp for this test run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Test run ID: {timestamp}")

    # Execute the pipeline
    print("\n=== Starting Pipeline Execution ===\n")

    if args.mock:
        # In mock mode, we'll patch subprocess.run to simulate execution
        import unittest.mock as mock

        def mock_subprocess_run(*args, **kwargs):
            """Mock subprocess.run to simulate stage execution."""
            script_path = args[0][1] if len(args) > 0 and len(args[0]) > 1 else ""
            stage_name = (
                script_path.split("/")[-1].replace(".py", "")
                if script_path
                else "unknown"
            )

            # If this is the stage that should fail
            if args.fail_stage and args.fail_stage in script_path:
                result = mock.MagicMock()
                result.returncode = 1
                result.stdout = f"Mock output for {stage_name}"
                result.stderr = f"Mock error for {stage_name}: Simulated failure"
                print(f"[MOCK] Simulating failure in stage: {stage_name}")
                return result

            # Otherwise succeed
            result = mock.MagicMock()
            result.returncode = 0
            result.stdout = f"Mock output for {stage_name}"
            result.stderr = ""
            print(f"[MOCK] Simulating success in stage: {stage_name}")
            return result

        # Apply the mock
        with mock.patch("subprocess.run", side_effect=mock_subprocess_run):
            executor = PipelineExecutor(
                env_file=args.env, max_retries=args.retries, resolution_mode=True
            )
            success = executor.execute_pipeline()
    else:
        # Run the actual pipeline
        executor = PipelineExecutor(
            env_file=args.env, max_retries=args.retries, resolution_mode=True
        )
        success = executor.execute_pipeline()

    # Print execution summary
    print("\n=== Pipeline Execution Summary ===\n")
    print(f"Execution ID: {executor.execution_id}")
    print(f"Status: {'Success' if success else 'Failure'}")

    if executor.start_time and executor.end_time:
        duration = (executor.end_time - executor.start_time).total_seconds()
        print(f"Duration: {duration:.2f} seconds")

    # Print stage results
    print("\nStage Results:")
    for stage_name, stage in executor.stages.items():
        status_icon = (
            "✅"
            if stage.status == "success"
            else "❌" if stage.status == "failure" else "⏩"
        )
        print(f"- {status_icon} {stage.name}: {stage.status}")
        if stage.retry_count > 0:
            print(f"  Retries: {stage.retry_count}")

    # Print failure summary
    if executor.results["failures"]:
        print("\nFailures:")
        for failure in executor.results["failures"]:
            print(f"- Stage: {failure['stage']}")
            print(f"  Category: {failure['category']}")
            print(f"  Message: {failure['message']}")
            print(f"  Resolution: {failure['resolution']}")

    # Print resolution attempts
    if executor.results["resolution_attempts"]:
        print("\nResolution Attempts:")
        for attempt in executor.results["resolution_attempts"]:
            status_icon = "✅" if attempt["success"] else "❌"
            print(f"- {status_icon} Stage: {attempt['stage']}")
            print(f"  Issue: {attempt['issue']}")
            print(f"  Resolution: {attempt['resolution']}")
            print(f"  Result: {attempt['result']}")

    # Get history and check if this execution was recorded
    tracker = ExecutionTracker()
    execution = tracker.get_execution(executor.execution_id)

    if execution:
        print("\nExecution successfully recorded in history.")
    else:
        print("\nWARNING: Execution not found in history!")

    # Print path to the execution summary markdown file
    summary_file = project_root / "e2e_summary.md"
    if summary_file.exists():
        print(f"\nExecution summary saved to: {summary_file}")

    # Return exit code based on success
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
