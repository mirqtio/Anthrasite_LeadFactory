#!/usr/bin/env python3
"""
BDD tests for batch completion tracking and alerting.
"""

import json
import os

# Add project root to path
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest
from behave import given, then, when

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
from bin.batch_completion_monitor import (
    check_and_alert,
)
from utils_legacy.batch_tracker import (
    check_batch_completion,
    record_batch_end,
    record_batch_stage_completion,
    record_batch_start,
)


@pytest.fixture
def batch_tracker_file():
    """Create a temporary batch tracker file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"{}")

    # Set environment variable to use the temp file
    original_file = os.environ.get("BATCH_TRACKER_FILE")
    os.environ["BATCH_TRACKER_FILE"] = temp_file.name

    # Set deadline timezone and hour for testing
    os.environ["BATCH_COMPLETION_DEADLINE_HOUR"] = "5"
    os.environ["BATCH_COMPLETION_TIMEZONE"] = "America/New_York"

    yield temp_file.name

    # Clean up
    os.unlink(temp_file.name)
    if original_file:
        os.environ["BATCH_TRACKER_FILE"] = original_file
    else:
        del os.environ["BATCH_TRACKER_FILE"]


@given("the batch tracker system is initialized")
def step_impl(context):
    """Initialize the batch tracker system with a clean file."""
    context.batch_tracker_file = batch_tracker_file()
    context.original_data = {}
    with open(context.batch_tracker_file, "w") as f:
        json.dump(context.original_data, f)


@when("I record a batch start")
def step_impl(context):
    """Record a batch start."""
    context.result = record_batch_start()
    assert context.result is True


@then("the batch start timestamp should be saved")
def step_impl(context):
    """Verify the batch start timestamp was saved."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "current_batch_start" in data
    # Verify timestamp is in ISO format and recent
    start_time = datetime.fromisoformat(data["current_batch_start"])
    now = datetime.utcnow()
    assert (now - start_time).total_seconds() < 60  # Within the last minute


@then("the batch completion gauge should be reset to 0% for all stages")
def step_impl(context):
    """Verify the batch completion gauge was reset."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "completion_percentage" in data
    assert data["completion_percentage"] == 0.0
    assert "stages" in data
    assert isinstance(data["stages"], dict)


@given("a batch has been started")
def step_impl(context):
    """Start a batch for testing."""
    context.result = record_batch_start()
    assert context.result is True


@when('I record completion of the "{stage}" stage at {percentage:f}%')
def step_impl(context, stage, percentage):
    """Record completion of a specific stage."""
    context.stage = stage
    context.percentage = percentage
    context.result = record_batch_stage_completion(stage, percentage)
    assert context.result is True


@then('the "{stage}" stage completion should be recorded as {percentage:f}%')
def step_impl(context, stage, percentage):
    """Verify the stage completion was recorded correctly."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "stages" in data
    assert stage in data["stages"]
    assert "completion_percentage" in data["stages"][stage]
    assert data["stages"][stage]["completion_percentage"] == percentage


@then('the batch completion gauge should show {percentage:f}% for the "{stage}" stage')
def step_impl(context, percentage, stage):
    """Verify the batch completion gauge shows the correct percentage for a stage."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "stages" in data
    assert stage in data["stages"]
    assert "completion_percentage" in data["stages"][stage]
    assert data["stages"][stage]["completion_percentage"] == percentage


@given("all stages have been completed")
def step_impl(context):
    """Mark all stages as completed."""
    stages = ["scrape", "enrichment", "deduplication", "scoring", "mockup", "email"]
    for i, stage in enumerate(stages):
        percentage = ((i + 1) * 100) / len(stages)
        record_batch_stage_completion(stage, percentage)


@when("I record a batch end")
def step_impl(context):
    """Record a batch end."""
    context.result = record_batch_end()
    assert context.result is True


@then("the batch end timestamp should be saved")
def step_impl(context):
    """Verify the batch end timestamp was saved."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "current_batch_end" in data
    # Verify timestamp is in ISO format and recent
    end_time = datetime.fromisoformat(data["current_batch_end"])
    now = datetime.utcnow()
    assert (now - end_time).total_seconds() < 60  # Within the last minute


@then("the batch completion gauge should show 100% for all stages")
def step_impl(context):
    """Verify the batch completion gauge shows 100% for all stages."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    assert "completion_percentage" in data
    assert data["completion_percentage"] == 100.0


@given("the batch has been completed today")
def step_impl(context):
    """Mark the batch as completed today."""
    record_batch_end()


@given("the batch has not been completed")
def step_impl(context):
    """Ensure the batch is not marked as completed."""
    with open(context.batch_tracker_file) as f:
        data = json.load(f)

    if "current_batch_end" in data:
        del data["current_batch_end"]

    with open(context.batch_tracker_file, "w") as f:
        json.dump(data, f)


@given("the time is after the completion deadline")
def step_impl(context):
    """Set the current time to be after the completion deadline."""
    # Mock datetime.now to return a time after the deadline
    context.mock_now_patcher = patch("utils_legacy.batch_tracker.datetime")
    context.mock_now = context.mock_now_patcher.start()

    # Set to 6 AM EST (after the 5 AM deadline)
    mock_now = datetime.utcnow().replace(
        hour=11, minute=0, second=0
    )  # 6 AM EST = 11 AM UTC
    context.mock_now.utcnow.return_value = mock_now
    context.mock_now.fromisoformat.side_effect = datetime.fromisoformat


@when("I check batch completion status")
def step_impl(context):
    """Check batch completion status."""
    context.completed, context.reason = check_batch_completion()


@then("the system should report the batch as completed on time")
def step_impl(context):
    """Verify the system reports the batch as completed on time."""
    assert context.completed is True
    assert "completed" in context.reason.lower()


@then("no alert should be triggered")
def step_impl(context):
    """Verify no alert is triggered."""
    with patch("bin.batch_completion_monitor.send_alert_email") as mock_send_alert:
        check_and_alert()
        mock_send_alert.assert_not_called()


@then("the system should report the batch as not completed on time")
def step_impl(context):
    """Verify the system reports the batch as not completed on time."""
    assert context.completed is False
    assert (
        "not completed" in context.reason.lower()
        or "deadline" in context.reason.lower()
    )


@then("an alert should be triggered")
def step_impl(context):
    """Verify an alert is triggered."""
    with patch("bin.batch_completion_monitor.send_alert_email") as mock_send_alert:
        check_and_alert()
        mock_send_alert.assert_called_once()


@given("a batch has not been completed on time")
def step_impl(context):
    """Set up a scenario where a batch has not been completed on time."""
    # Start a batch but don't complete it
    record_batch_start()

    # Set the time to after the deadline
    context.mock_now_patcher = patch("utils_legacy.batch_tracker.datetime")
    context.mock_now = context.mock_now_patcher.start()

    # Set to 6 AM EST (after the 5 AM deadline)
    mock_now = datetime.utcnow().replace(
        hour=11, minute=0, second=0
    )  # 6 AM EST = 11 AM UTC
    context.mock_now.utcnow.return_value = mock_now
    context.mock_now.fromisoformat.side_effect = datetime.fromisoformat


@when("the batch completion monitor runs")
def step_impl(context):
    """Simulate the batch completion monitor running."""
    context.mock_send_alert = patch(
        "bin.batch_completion_monitor.send_alert_email"
    ).start()
    context.mock_send_alert.return_value = True

    check_and_alert()


@then("an alert email should be sent")
def step_impl(context):
    """Verify an alert email is sent."""
    context.mock_send_alert.assert_called_once()
    subject = context.mock_send_alert.call_args[0][0]
    assert "ALERT" in subject
    assert "Batch Completion" in subject


@then("the alert should contain batch status information")
def step_impl(context):
    """Verify the alert contains batch status information."""
    message = context.mock_send_alert.call_args[0][1]
    assert "Batch Completion Alert" in message
    assert "Status: FAILED" in message
    assert "Batch Details:" in message
    assert "Stage Completion:" in message


def teardown_function():
    """Clean up after tests."""
    # Stop any running patchers
    for patcher in [
        getattr(pytest, "mock_now_patcher", None),
        getattr(pytest, "mock_send_alert_patcher", None),
    ]:
        if patcher and patcher.is_active:
            patcher.stop()
