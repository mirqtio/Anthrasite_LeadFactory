#!/usr/bin/env python3
"""
BDD tests for cost metrics tracking and alerting.
"""

import os
import json
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock
from behave import given, when, then, step
import pytest

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
from utils.cost_metrics import (
    ensure_cost_tracker_file,
    get_cost_data,
    save_cost_data,
    get_lead_count,
    get_total_monthly_cost,
    calculate_cost_per_lead,
    track_gpu_usage,
    check_gpu_cost_threshold,
    check_cost_per_lead_threshold,
    update_cost_metrics_at_batch_end,
)


@pytest.fixture
def cost_tracker_file():
    """Create a temporary cost tracker file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"{}")

    # Set environment variable to use the temp file
    original_file = os.environ.get("COST_TRACKER_FILE")
    os.environ["COST_TRACKER_FILE"] = temp_file.name

    yield temp_file.name

    # Clean up
    os.unlink(temp_file.name)
    if original_file:
        os.environ["COST_TRACKER_FILE"] = original_file
    else:
        del os.environ["COST_TRACKER_FILE"]


@pytest.fixture
def mock_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
        pass

    # Set environment variable to use the temp database
    original_db = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = temp_file.name

    # Create test database
    conn = sqlite3.connect(temp_file.name)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE businesses (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
    conn.commit()
    conn.close()

    yield temp_file.name

    # Clean up
    os.unlink(temp_file.name)
    if original_db:
        os.environ["DATABASE_URL"] = original_db
    else:
        del os.environ["DATABASE_URL"]


@given("the cost metrics system is initialized")
def step_impl(context):
    """Initialize the cost metrics system with a clean file."""
    context.cost_tracker_file = cost_tracker_file()
    context.mock_database = mock_database()
    ensure_cost_tracker_file()


@given("there are {count:d} leads in the database")
def step_impl(context, count):
    """Add leads to the database."""
    context.lead_count = count

    # Connect to database
    conn = sqlite3.connect(context.mock_database)
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM businesses")

    # Add test leads
    for i in range(count):
        cursor.execute(
            "INSERT INTO businesses (name, email) VALUES (?, ?)",
            (f"Business {i}", f"business{i}@example.com")
        )

    conn.commit()
    conn.close()

    # Verify lead count
    assert get_lead_count() == count


@given("the total monthly cost is ${cost:f}")
def step_impl(context, cost):
    """Set the total monthly cost."""
    context.monthly_cost = cost

    # Get current data
    data = get_cost_data()

    # Update monthly costs
    data["monthly_costs"] = {"total": cost}

    # Save updated data
    save_cost_data(data)

    # Verify total monthly cost
    assert get_total_monthly_cost() == cost


@when("I calculate the cost per lead")
def step_impl(context):
    """Calculate the cost per lead."""
    context.cost_per_lead = calculate_cost_per_lead()


@then("the cost per lead should be ${cost:f}")
def step_impl(context, cost):
    """Verify the cost per lead."""
    assert context.cost_per_lead == cost

    # Also verify it was saved in the cost data
    data = get_cost_data()
    assert data["cost_per_lead"] == cost


@then("the cost per lead metric should be updated")
def step_impl(context):
    """Verify the cost per lead metric was updated."""
    with patch("utils.batch_metrics.record_cost_per_lead") as mock_record:
        calculate_cost_per_lead()
        mock_record.assert_called_once()


@given("the cost per lead is ${cost:f}")
def step_impl(context, cost):
    """Set the cost per lead."""
    context.cost_per_lead = cost

    # Get current data
    data = get_cost_data()

    # Update cost per lead
    data["cost_per_lead"] = cost

    # Save updated data
    save_cost_data(data)


@when("I check the cost per lead threshold of ${threshold:f}")
def step_impl(context, threshold):
    """Check the cost per lead threshold."""
    context.exceeded, context.reason = check_cost_per_lead_threshold(threshold)


@then("the system should report the cost per lead is within threshold")
def step_impl(context):
    """Verify the system reports the cost per lead is within threshold."""
    assert context.exceeded is False
    assert "within threshold" in context.reason.lower()


@then("the system should report the cost per lead exceeds threshold")
def step_impl(context):
    """Verify the system reports the cost per lead exceeds threshold."""
    assert context.exceeded is True
    assert "exceeds threshold" in context.reason.lower()


@given("the GPU_BURST flag is enabled")
def step_impl(context):
    """Enable the GPU_BURST flag."""
    os.environ["GPU_BURST"] = "1"


@given("the GPU_BURST flag is disabled")
def step_impl(context):
    """Disable the GPU_BURST flag."""
    if "GPU_BURST" in os.environ:
        del os.environ["GPU_BURST"]


@when("I track GPU usage with cost ${cost:f}")
def step_impl(context, cost):
    """Track GPU usage with the specified cost."""
    with patch("utils.batch_metrics.increment_gpu_cost") as mock_increment:
        context.tracked = track_gpu_usage(cost)
        context.mock_increment = mock_increment


@then("the GPU cost should be incremented by ${cost:f}")
def step_impl(context, cost):
    """Verify the GPU cost was incremented."""
    assert context.tracked is True

    # Verify the cost was saved in the cost data
    data = get_cost_data()
    assert data["gpu_costs"]["total"] == cost
    assert data["gpu_costs"]["daily"] == cost
    assert data["gpu_costs"]["monthly"] == cost


@then("the GPU cost should not be incremented")
def step_impl(context):
    """Verify the GPU cost was not incremented."""
    assert context.tracked is False

    # Verify the cost was not saved in the cost data
    data = get_cost_data()
    assert data["gpu_costs"]["total"] == 0
    assert data["gpu_costs"]["daily"] == 0
    assert data["gpu_costs"]["monthly"] == 0


@then("the GPU cost metric should be updated")
def step_impl(context):
    """Verify the GPU cost metric was updated."""
    context.mock_increment.assert_called_once()


@then("the GPU cost metric should not be updated")
def step_impl(context):
    """Verify the GPU cost metric was not updated."""
    context.mock_increment.assert_not_called()


@given("the daily GPU cost is ${cost:f}")
def step_impl(context, cost):
    """Set the daily GPU cost."""
    context.daily_gpu_cost = cost

    # Get current data
    data = get_cost_data()

    # Update GPU costs
    if "gpu_costs" not in data:
        data["gpu_costs"] = {"total": 0.0, "daily": 0.0, "monthly": 0.0}

    data["gpu_costs"]["daily"] = cost

    # Save updated data
    save_cost_data(data)


@given("the monthly GPU cost is ${cost:f}")
def step_impl(context, cost):
    """Set the monthly GPU cost."""
    context.monthly_gpu_cost = cost

    # Get current data
    data = get_cost_data()

    # Update GPU costs
    if "gpu_costs" not in data:
        data["gpu_costs"] = {"total": 0.0, "daily": 0.0, "monthly": 0.0}

    data["gpu_costs"]["monthly"] = cost

    # Save updated data
    save_cost_data(data)


@when("I check the GPU cost thresholds of ${daily:f} daily and ${monthly:f} monthly")
def step_impl(context, daily, monthly):
    """Check the GPU cost thresholds."""
    context.exceeded, context.reason = check_gpu_cost_threshold(daily, monthly)


@then("the system should report the GPU cost is within thresholds")
def step_impl(context):
    """Verify the system reports the GPU cost is within thresholds."""
    assert context.exceeded is False
    assert "within threshold" in context.reason.lower()


@then("the system should report the GPU cost exceeds daily threshold")
def step_impl(context):
    """Verify the system reports the GPU cost exceeds daily threshold."""
    assert context.exceeded is True
    assert "daily gpu cost" in context.reason.lower()
    assert "exceeds threshold" in context.reason.lower()


@then("the system should report the GPU cost exceeds monthly threshold")
def step_impl(context):
    """Verify the system reports the GPU cost exceeds monthly threshold."""
    assert context.exceeded is True
    assert "monthly gpu cost" in context.reason.lower()
    assert "exceeds threshold" in context.reason.lower()


@when("I update cost metrics at batch end")
def step_impl(context):
    """Update cost metrics at batch end."""
    with patch("utils.batch_metrics.record_cost_per_lead") as mock_record:
        context.results = update_cost_metrics_at_batch_end()
        context.mock_record = mock_record


@then("the system should report all cost metrics")
def step_impl(context):
    """Verify the system reports all cost metrics."""
    assert "cost_per_lead" in context.results
    assert "cost_per_lead_threshold_exceeded" in context.results
    assert "gpu_cost_daily" in context.results
    assert "gpu_cost_monthly" in context.results
    assert "gpu_cost_total" in context.results
    assert "gpu_cost_threshold_exceeded" in context.results
    assert "total_monthly_cost" in context.results
    assert "monthly_budget" in context.results
    assert "budget_utilization" in context.results

    # Verify the cost per lead metric was updated
    context.mock_record.assert_called_once()


def teardown_function():
    """Clean up after tests."""
    # Reset environment variables
    for var in ["COST_TRACKER_FILE", "DATABASE_URL", "GPU_BURST"]:
        if var in os.environ:
            del os.environ[var]
