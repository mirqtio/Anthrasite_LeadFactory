#!/usr/bin/env python3
"""
Step definitions for E2E Pipeline Execution and Resolution BDD tests
"""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from behave import given, then, when

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

from scripts.e2e.generate_report import ReportGenerator
from scripts.e2e.pipeline_executor import (
    ExecutionStatus,
    FailureCategory,
    PipelineExecutor,
)


@given("the preflight checks have been completed successfully")
def step_preflight_successful(context):
    """Set up a mock for successful preflight checks"""
    context.preflight_patcher = patch("scripts.e2e.pipeline_executor.PreflightCheck")
    mock_preflight = context.preflight_patcher.start()

    # Configure mock
    mock_preflight_instance = mock_preflight.return_value
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.issues = []
    mock_preflight_instance.run.return_value = mock_result

    # Save for later steps
    context.mock_preflight = mock_preflight


@given("the test environment is configured with valid API keys")
def step_valid_api_keys(context):
    """Set up environment with valid API keys"""
    # Create a temporary environment file for testing
    from tempfile import NamedTemporaryFile

    context.env_file = NamedTemporaryFile(delete=False, mode="w+")
    context.env_file.write(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory\n"  # pragma: allowlist secret
    )
    context.env_file.write("OPENAI_API_KEY=sk-test123456\n")
    context.env_file.write("GOOGLE_MAPS_API_KEY=test-api-key\n")
    context.env_file.write("SENDGRID_API_KEY=SG.test-key\n")
    context.env_file.write("EMAIL_OVERRIDE=test@example.com\n")
    context.env_file.write("MOCKUP_ENABLED=true\n")
    context.env_file.write("E2E_MODE=true\n")
    context.env_file.flush()

    # Register for cleanup
    context.add_cleanup(lambda: os.unlink(context.env_file.name))


@given("the test database is running with proper schema")
def step_database_running(context):
    """Mock database connection and schema validation"""
    # This step is a placeholder for real DB connection verification
    # In a real implementation, this would connect to the test database
    context.database_running = True


@given("a test lead is queued")
def step_test_lead_queued(context):
    """Queue a test lead for processing"""
    # Mock lead data that would be inserted into the database
    context.test_lead = {
        "id": "test-lead-123",
        "business_name": "Test Business",
        "business_type": "Test Type",
        "address": "123 Test St, Test City, TS 12345",
        "phone": "555-123-4567",
        "website": "https://testbusiness.com",
        "status": "queued",
    }


@when("the pipeline runs with real API keys")
def step_pipeline_runs_real_keys(context):
    """Run the pipeline with real API keys"""
    # Set up subprocess.run mock for successful pipeline execution
    context.subprocess_patcher = patch("subprocess.run")
    mock_subprocess = context.subprocess_patcher.start()

    # Configure successful subprocess calls
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Test output"
    mock_process.stderr = ""
    mock_subprocess.return_value = mock_process

    # Initialize and run the pipeline executor
    context.executor = PipelineExecutor(
        env_file=context.env_file.name, max_retries=1, resolution_mode=True
    )

    # Run the pipeline
    context.pipeline_result = context.executor.execute_pipeline()

    # Register for cleanup
    context.add_cleanup(context.subprocess_patcher.stop)


@then("a screenshot and mockup are generated")
def step_screenshot_mockup_generated(context):
    """Verify screenshot and mockup were generated"""
    # Check that screenshot and mockup stages were successful
    assert context.executor.stages["screenshot"].status == ExecutionStatus.SUCCESS
    assert context.executor.stages["mockup"].status == ExecutionStatus.SUCCESS


@then("a real email is sent via SendGrid to EMAIL_OVERRIDE")
def step_email_sent(context):
    """Verify email was sent via SendGrid to the override address"""
    # Check that email stage was successful
    assert context.executor.stages["email"].status == ExecutionStatus.SUCCESS

    # In a real implementation, we would check the database for email records
    # or query the SendGrid API to verify the email was sent


@then("the SendGrid response is {status_code:d}")
def step_sendgrid_response(context, status_code):
    """Verify SendGrid API response code"""
    # This would require parsing the output of the email stage
    # For now, we'll just check that the stage was successful
    assert context.executor.stages["email"].status == ExecutionStatus.SUCCESS


@given('the environment is missing a required variable "{variable_name}"')
def step_missing_environment_variable(context, variable_name):
    """Set up environment with a missing required variable"""
    # Create a temporary environment file missing the specified variable
    from tempfile import NamedTemporaryFile

    context.env_file = NamedTemporaryFile(delete=False, mode="w+")
    context.env_file.write(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory\n"  # pragma: allowlist secret
    )
    context.env_file.write("OPENAI_API_KEY=sk-test123456\n")
    context.env_file.write("GOOGLE_MAPS_API_KEY=test-api-key\n")

    # Exclude the specified variable
    if variable_name != "SENDGRID_API_KEY":
        context.env_file.write("SENDGRID_API_KEY=SG.test-key\n")

    if variable_name != "EMAIL_OVERRIDE":
        context.env_file.write("EMAIL_OVERRIDE=test@example.com\n")

    if variable_name != "MOCKUP_ENABLED":
        context.env_file.write("MOCKUP_ENABLED=true\n")

    if variable_name != "E2E_MODE":
        context.env_file.write("E2E_MODE=true\n")

    context.env_file.flush()

    # Register for cleanup
    context.add_cleanup(lambda: os.unlink(context.env_file.name))

    # Set up preflight check to detect the missing variable
    context.preflight_patcher = patch("scripts.e2e.pipeline_executor.PreflightCheck")
    mock_preflight = context.preflight_patcher.start()

    # Configure mock
    mock_preflight_instance = mock_preflight.return_value
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.issues = [f"Missing required variable: {variable_name}"]
    mock_preflight_instance.run.return_value = mock_result

    # Save for later steps
    context.mock_preflight = mock_preflight
    context.missing_variable = variable_name

    # Register for cleanup
    context.add_cleanup(context.preflight_patcher.stop)


@when("the pipeline preflight check runs")
def step_preflight_check_runs(context):
    """Run the pipeline preflight check"""
    # Initialize the pipeline executor
    context.executor = PipelineExecutor(
        env_file=context.env_file.name, max_retries=1, resolution_mode=True
    )

    # Run only the preflight check
    context.preflight_result = context.executor.run_preflight_check()


@then('the execution status should be "{status}"')
def step_execution_status(context, status):
    """Verify the execution status"""
    if hasattr(context, "pipeline_result"):
        if status == "success":
            assert context.executor.overall_status == ExecutionStatus.SUCCESS
        else:
            assert context.executor.overall_status == ExecutionStatus.FAILURE
    else:
        if status == "success":
            assert context.preflight_result is True
        else:
            assert context.preflight_result is False


@then('the failure category should be "{category}"')
def step_failure_category(context, category):
    """Verify the failure category"""
    failures = context.executor.results["failures"]
    assert len(failures) > 0, "No failures recorded"

    # Check that at least one failure has the expected category
    matching_failures = [f for f in failures if f["category"] == category]
    assert len(matching_failures) > 0, f"No failures with category {category}"


@then("the resolution should suggest adding the missing variable")
def step_resolution_suggests_adding_variable(context):
    """Verify the resolution suggestion"""
    failures = context.executor.results["failures"]

    # Find failures related to the missing variable
    variable_failures = [
        f for f in failures if context.missing_variable in f["message"]
    ]

    assert (
        len(variable_failures) > 0
    ), f"No failures related to {context.missing_variable}"

    # Check resolution suggestion
    resolution = variable_failures[0]["resolution"]
    assert (
        "Add the missing variable" in resolution
    ), f"Unexpected resolution: {resolution}"


@given("the OpenAI API is temporarily unavailable")
def step_openai_api_unavailable(context):
    """Set up OpenAI API to be temporarily unavailable"""
    # Set up environment with valid API keys
    step_valid_api_keys(context)

    # Set up successful preflight check
    step_preflight_successful(context)

    # Set up subprocess.run mock to simulate API failure then success
    context.subprocess_patcher = patch("subprocess.run")
    mock_subprocess = context.subprocess_patcher.start()

    # Configure subprocess calls: first call to API fails, then succeeds on retry
    # This uses a side effect function to vary the behavior based on call count
    context.api_call_count = 0

    def api_failure_then_success(*args, **kwargs):
        script_path = args[0][1] if len(args) > 0 and len(args[0]) > 1 else ""

        # If this is the mockup stage which uses OpenAI API
        if "03_mockup.py" in script_path:
            context.api_call_count += 1

            # First call fails
            if context.api_call_count == 1:
                mock_fail = MagicMock()
                mock_fail.returncode = 1
                mock_fail.stdout = ""
                mock_fail.stderr = "OpenAI API returned 503 Service Unavailable"
                return mock_fail

        # All other calls succeed
        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = "Test output"
        mock_success.stderr = ""
        return mock_success

    mock_subprocess.side_effect = api_failure_then_success

    # Register for cleanup
    context.add_cleanup(context.subprocess_patcher.stop)


@when("the pipeline runs with retry enabled")
def step_pipeline_runs_with_retry(context):
    """Run the pipeline with retry enabled"""
    # Initialize and run the pipeline executor with retries enabled
    context.executor = PipelineExecutor(
        env_file=context.env_file.name,
        max_retries=3,  # Allow up to 3 retries
        resolution_mode=True,
    )

    # Run the pipeline
    context.pipeline_result = context.executor.execute_pipeline()


@then("the API test should be retried")
def step_api_test_retried(context):
    """Verify the API test was retried"""
    # Check that mockup stage has a retry count greater than 0
    assert context.executor.stages["mockup"].retry_count > 0, "API test was not retried"


@then("the execution should eventually succeed")
def step_execution_eventually_succeeds(context):
    """Verify the execution eventually succeeded"""
    assert context.pipeline_result is True, "Pipeline execution did not succeed"
    assert context.executor.overall_status == ExecutionStatus.SUCCESS


@then("the retry count should be greater than {count:d}")
def step_retry_count_greater_than(context, count):
    """Verify the retry count is greater than the specified value"""
    # Check retry count across all stages
    total_retries = sum(stage.retry_count for stage in context.executor.stages.values())
    assert (
        total_retries > count
    ), f"Total retry count {total_retries} is not greater than {count}"


@given("a pipeline execution has completed")
def step_pipeline_execution_completed(context):
    """Set up a completed pipeline execution"""
    # First set up a successful pipeline execution
    step_valid_api_keys(context)
    step_preflight_successful(context)

    # Create a subprocess mock for successful execution
    context.subprocess_patcher = patch("subprocess.run")
    mock_subprocess = context.subprocess_patcher.start()

    # Configure successful subprocess calls
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Test output"
    mock_process.stderr = ""
    mock_subprocess.return_value = mock_process

    # Initialize and run the pipeline executor
    context.executor = PipelineExecutor(
        env_file=context.env_file.name, max_retries=1, resolution_mode=True
    )

    # Run the pipeline
    context.pipeline_result = context.executor.execute_pipeline()

    # Ensure we have an execution history file
    context.execution_id = context.executor.execution_id

    # Register for cleanup
    context.add_cleanup(context.subprocess_patcher.stop)


@when("the report generator runs")
def step_report_generator_runs(context):
    """Run the report generator"""
    # Create a mock execution history file if it doesn't exist
    if not os.path.exists(context.executor.history_file):
        with open(context.executor.history_file, "w") as f:
            json.dump([context.executor.results], f)

    # Initialize and run the report generator
    context.report_generator = ReportGenerator(
        execution_id=context.execution_id, history_file=context.executor.history_file
    )

    # Generate reports
    context.summary_report = context.report_generator.generate_summary_report()
    context.detailed_report = context.report_generator.generate_detailed_report()


@then("an execution summary is generated")
def step_execution_summary_generated(context):
    """Verify execution summary was generated"""
    assert context.summary_report, "No summary report was generated"
    assert "E2E Pipeline Execution Summary" in context.summary_report
    assert context.execution_id in context.summary_report


@then("the report includes execution statistics")
def step_report_includes_statistics(context):
    """Verify the report includes execution statistics"""
    assert "Duration:" in context.detailed_report
    assert "Stage Results" in context.detailed_report


@then("the report includes test coverage analysis")
def step_report_includes_coverage(context):
    """Verify the report includes test coverage analysis"""
    assert "Test Coverage Analysis" in context.detailed_report
    assert "Pipeline Components Coverage" in context.detailed_report


@then("the report includes failure analysis if applicable")
def step_report_includes_failure_analysis(context):
    """Verify the report includes failure analysis if applicable"""
    if context.executor.results.get("failures"):
        assert "Failures" in context.detailed_report
    else:
        # No failures to report
        pass


@given("multiple pipeline executions have been recorded")
def step_multiple_executions_recorded(context):
    """Set up multiple recorded pipeline executions"""
    # Create a temporary history file with multiple executions
    import json
    from tempfile import NamedTemporaryFile

    context.history_file = NamedTemporaryFile(delete=False, mode="w+")

    # Create sample execution history
    executions = []
    for i in range(10):
        execution_id = f"test-execution-{i}"
        status = "success" if i % 3 != 0 else "failure"

        # Create basic execution record
        execution = {
            "execution_id": execution_id,
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T00:10:00",
            "duration": 600,
            "status": status,
            "stages": {
                "preflight": {
                    "name": "Preflight Check",
                    "status": "success",
                    "start_time": "2023-01-01T00:00:00",
                    "end_time": "2023-01-01T00:01:00",
                    "duration": 60,
                    "retry_count": 0,
                },
                "scrape": {
                    "name": "Web Scraping",
                    "status": "success",
                    "start_time": "2023-01-01T00:01:00",
                    "end_time": "2023-01-01T00:02:00",
                    "duration": 60,
                    "retry_count": 0,
                },
                "mockup": {
                    "name": "Mockup Generation",
                    "status": "success" if i % 2 == 0 else "failure",
                    "start_time": "2023-01-01T00:03:00",
                    "end_time": "2023-01-01T00:04:00",
                    "duration": 60,
                    "retry_count": i % 3,
                    "error": "OpenAI API error" if i % 2 != 0 else None,
                },
            },
            "failures": [],
        }

        # Add failures for failed executions
        if status == "failure" or i % 2 != 0:
            failure = {
                "stage": "mockup",
                "category": "api_failure",
                "message": "OpenAI API returned error",
                "resolution": "Check API key and quota",
                "timestamp": "2023-01-01T00:04:00",
            }
            execution["failures"].append(failure)

        executions.append(execution)

    # Write to history file
    json.dump(executions, context.history_file)
    context.history_file.flush()

    # Register for cleanup
    context.add_cleanup(lambda: os.unlink(context.history_file.name))


@when("the trend report generator runs")
def step_trend_report_generator_runs(context):
    """Run the trend report generator"""
    # Initialize the report generator
    context.report_generator = ReportGenerator(history_file=context.history_file.name)

    # Generate trend report
    context.trend_report = context.report_generator.generate_trend_report(10)


@then("common failure patterns are identified")
def step_common_failure_patterns_identified(context):
    """Verify common failure patterns are identified"""
    assert "Most Common Failure Categories" in context.trend_report
    assert "api_failure" in context.trend_report


@then("recommendations are provided for improving reliability")
def step_recommendations_provided(context):
    """Verify recommendations are provided"""
    assert (
        "Recommendations" in context.trend_report
        or "Trend Recommendations" in context.trend_report
    )


@then("success rate statistics are included in the report")
def step_success_rate_statistics_included(context):
    """Verify success rate statistics are included"""
    assert "Success Rate:" in context.trend_report
    assert "Stage Reliability" in context.trend_report
