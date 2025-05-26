"""
BDD step definitions for the API cost monitoring functionality feature.
"""

import os
import sys
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import scenarios, given, when, then, parsers

# Import shared steps to ensure 'the database is initialized' step is available
from tests.bdd.step_defs.shared_steps import initialize_database

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Import the modules being tested
from leadfactory.cost import budget_gate

# Load the scenarios from the feature file
scenarios('../features/pipeline_stages.feature')


@pytest.fixture
def cost_db_conn():
    """Fixture for an in-memory test database for API cost tests."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create api_costs table
    cursor.execute(
        """
        CREATE TABLE api_costs (
            id INTEGER PRIMARY KEY,
            model TEXT NOT NULL,
            tokens INTEGER NOT NULL,
            cost REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            purpose TEXT,
            business_id INTEGER
        )
        """
    )

    # Create budget_settings table
    cursor.execute(
        """
        CREATE TABLE budget_settings (
            id INTEGER PRIMARY KEY,
            monthly_budget REAL NOT NULL,
            daily_budget REAL NOT NULL,
            warning_threshold REAL NOT NULL,
            pause_threshold REAL NOT NULL,
            current_status TEXT DEFAULT 'active',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def api_costs_logged(cost_db_conn):
    """Set up API costs logged for various operations."""
    cursor = cost_db_conn.cursor()

    # Insert budget settings
    cursor.execute(
        """
        INSERT INTO budget_settings (monthly_budget, daily_budget, warning_threshold, pause_threshold)
        VALUES (100.0, 10.0, 0.8, 0.95)
        """
    )

    # Insert API costs
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Different models
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 2000, 0.10, ?, 'verification')
        """,
        (current_date,)
    )

    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-3.5-turbo', 5000, 0.05, ?, 'email')
        """,
        (current_date,)
    )

    # Different purposes
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 3000, 0.15, ?, 'mockup')
        """,
        (current_date,)
    )

    cost_db_conn.commit()
    return {"db_conn": cost_db_conn}


# Given step implementation
@given("API costs have been logged for various operations")
def costs_have_been_logged(api_costs_logged):
    """API costs have been logged for various operations."""
    return api_costs_logged


# When step implementation
@when("I check the budget status")
def check_budget_status(api_costs_logged):
    """Check the budget status."""
    db_conn = api_costs_logged["db_conn"]

    # Get current costs
    monthly_costs = budget_gate.get_current_month_costs(db_conn)
    daily_costs = budget_gate.get_current_day_costs(db_conn)

    # Get budget status
    status = budget_gate.check_budget_status(db_conn)

    # Get cost summary
    summary = budget_gate.get_cost_summary(db_conn)

    api_costs_logged.update({
        'monthly_costs': monthly_costs,
        'daily_costs': daily_costs,
        'budget_status': status,
        'cost_summary': summary
    })

    return api_costs_logged


# Then step implementations
@then("I should see the total cost for the current month")
def check_monthly_cost(api_costs_logged):
    """Check that total cost for current month is available."""
    monthly_costs = api_costs_logged['monthly_costs']

    assert monthly_costs is not None, "Monthly costs should not be None"
    assert monthly_costs > 0, "Monthly costs should be greater than 0"
    assert monthly_costs == 0.30, f"Monthly costs should be 0.30, got {monthly_costs}"  # 0.10 + 0.05 + 0.15


@then("I should see the cost breakdown by model")
def check_cost_by_model(api_costs_logged):
    """Check that cost breakdown by model is available."""
    cost_summary = api_costs_logged['cost_summary']
    by_model = cost_summary['by_model']

    assert by_model is not None, "Cost breakdown by model should not be None"
    assert "gpt-4" in by_model, "Cost breakdown should include gpt-4"
    assert "gpt-3.5-turbo" in by_model, "Cost breakdown should include gpt-3.5-turbo"
    assert by_model["gpt-4"] == 0.25, f"GPT-4 cost should be 0.25, got {by_model['gpt-4']}"  # 0.10 + 0.15
    assert by_model["gpt-3.5-turbo"] == 0.05, f"GPT-3.5-turbo cost should be 0.05, got {by_model['gpt-3.5-turbo']}"


@then("I should see the cost breakdown by purpose")
def check_cost_by_purpose(api_costs_logged):
    """Check that cost breakdown by purpose is available."""
    cost_summary = api_costs_logged['cost_summary']
    by_purpose = cost_summary['by_purpose']

    assert by_purpose is not None, "Cost breakdown by purpose should not be None"
    assert "verification" in by_purpose, "Cost breakdown should include verification"
    assert "email" in by_purpose, "Cost breakdown should include email"
    assert "mockup" in by_purpose, "Cost breakdown should include mockup"
    assert by_purpose["verification"] == 0.10, f"Verification cost should be 0.10, got {by_purpose['verification']}"
    assert by_purpose["email"] == 0.05, f"Email cost should be 0.05, got {by_purpose['email']}"
    assert by_purpose["mockup"] == 0.15, f"Mockup cost should be 0.15, got {by_purpose['mockup']}"


@then("I should know if we're within budget limits")
def check_budget_limits(api_costs_logged):
    """Check that budget status indicates if we're within limits."""
    status = api_costs_logged['budget_status']

    assert status is not None, "Budget status should not be None"
    assert "status" in status, "Budget status should include status field"
    assert status["status"] in ["active", "warning", "paused"], f"Status should be one of active, warning, paused, got {status['status']}"
    assert "monthly_budget_used" in status, "Budget status should include monthly_budget_used"
    assert "daily_budget_used" in status, "Budget status should include daily_budget_used"

    # With our test data we should be well under budget
    assert status["monthly_budget_used"] < 0.5, f"Monthly budget used should be less than 50%, got {status['monthly_budget_used'] * 100}%"
    assert status["daily_budget_used"] < 0.5, f"Daily budget used should be less than 50%, got {status['daily_budget_used'] * 100}%"
