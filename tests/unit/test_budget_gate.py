"""
Unit tests for the budget_gate module.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from leadfactory.cost import budget_gate


@pytest.fixture
def mock_db():
    """Create an in-memory SQLite database for testing."""
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

    # Insert test data for api_costs
    # Past month costs
    past_month = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 1000, 0.05, ?, 'verification')
        """,
        (past_month,)
    )

    # Current month costs
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 2000, 0.10, ?, 'mockup')
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

    # Insert budget settings
    cursor.execute(
        """
        INSERT INTO budget_settings (monthly_budget, daily_budget, warning_threshold, pause_threshold, current_status)
        VALUES (50.0, 5.0, 0.8, 0.95, 'active')
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.mark.skip(reason="Function get_current_month_costs not yet implemented")
def test_get_current_month_costs(mock_db):
    """Test retrieving current month's API costs."""
    # Call the function
    costs = budget_gate.get_current_month_costs(mock_db)

    # Verify the result
    assert costs == 0.15  # 0.10 + 0.05 for current month


@pytest.mark.skip(reason="Function get_current_day_costs not yet implemented")
def test_get_current_day_costs(mock_db):
    """Test retrieving current day's API costs."""
    # Call the function
    costs = budget_gate.get_current_day_costs(mock_db)

    # Verify the result
    assert costs == 0.15  # 0.10 + 0.05 for current day


def test_get_budget_settings(mock_db):
    """Test retrieving budget settings."""
    # Call the function
    settings = budget_gate.get_budget_settings(mock_db)

    # Verify the result
    assert settings["monthly_budget"] == 50.0
    assert settings["daily_budget"] == 5.0
    assert settings["warning_threshold"] == 0.8
    assert settings["pause_threshold"] == 0.95
    assert settings["current_status"] == "active"


def test_check_budget_status_active(mock_db):
    """Test checking budget status when within limits."""
    # Call the function
    status = budget_gate.check_budget_status(mock_db)

    # Verify the result
    assert status["status"] == "active"
    assert status["monthly_budget_used"] == 0.15 / 50.0  # 0.3%
    assert status["daily_budget_used"] == 0.15 / 5.0  # 3%


def test_check_budget_status_warning(mock_db):
    """Test checking budget status when reaching warning threshold."""
    # Add costs to reach warning threshold
    cursor = mock_db.cursor()
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add costs to reach 80% of daily budget (4.0 out of 5.0)
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 78000, 3.85, ?, 'large_operation')
        """,
        (current_date,)
    )
    mock_db.commit()

    # Call the function
    status = budget_gate.check_budget_status(mock_db)

    # Verify the result
    assert status["status"] == "warning"
    assert status["daily_budget_used"] >= 0.8  # At least 80% of daily budget


def test_check_budget_status_paused(mock_db):
    """Test checking budget status when reaching pause threshold."""
    # Add costs to reach pause threshold
    cursor = mock_db.cursor()
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add costs to reach 95% of daily budget (4.75 out of 5.0)
    cursor.execute(
        """
        INSERT INTO api_costs (model, tokens, cost, timestamp, purpose)
        VALUES ('gpt-4', 92000, 4.6, ?, 'large_operation')
        """,
        (current_date,)
    )
    mock_db.commit()

    # Call the function
    status = budget_gate.check_budget_status(mock_db)

    # Verify the result
    assert status["status"] == "paused"
    assert status["daily_budget_used"] >= 0.95  # At least 95% of daily budget


def test_update_budget_settings(mock_db):
    """Test updating budget settings."""
    # Call the function
    new_settings = {
        "monthly_budget": 100.0,
        "daily_budget": 10.0,
        "warning_threshold": 0.7,
        "pause_threshold": 0.9
    }

    result = budget_gate.update_budget_settings(mock_db, new_settings)

    # Verify the result
    assert result is True

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT monthly_budget, daily_budget, warning_threshold, pause_threshold FROM budget_settings")
    settings = cursor.fetchone()

    assert settings[0] == 100.0
    assert settings[1] == 10.0
    assert settings[2] == 0.7
    assert settings[3] == 0.9


def test_reset_budget_status(mock_db):
    """Test resetting budget status to active."""
    # First set status to paused
    cursor = mock_db.cursor()
    cursor.execute("UPDATE budget_settings SET current_status = 'paused'")
    mock_db.commit()

    # Call the function
    result = budget_gate.reset_budget_status(mock_db)

    # Verify the result
    assert result is True

    # Verify database was updated
    cursor.execute("SELECT current_status FROM budget_settings")
    status = cursor.fetchone()[0]

    assert status == "active"


def test_can_proceed_with_operation(mock_db):
    """Test checking if an operation can proceed based on budget status."""
    # Test with active status
    result = budget_gate.can_proceed_with_operation(mock_db, estimated_cost=0.1)
    assert result is True

    # Test with warning status but acceptable cost
    cursor = mock_db.cursor()
    cursor.execute("UPDATE budget_settings SET current_status = 'warning'")
    mock_db.commit()

    result = budget_gate.can_proceed_with_operation(mock_db, estimated_cost=0.1)
    assert result is True

    # Test with warning status and high cost
    result = budget_gate.can_proceed_with_operation(mock_db, estimated_cost=2.0)
    assert result is False

    # Test with paused status
    cursor.execute("UPDATE budget_settings SET current_status = 'paused'")
    mock_db.commit()

    result = budget_gate.can_proceed_with_operation(mock_db, estimated_cost=0.1)
    assert result is False


def test_log_api_cost(mock_db):
    """Test logging new API costs."""
    # Call the function
    result = budget_gate.log_api_cost(mock_db, model="gpt-4", tokens=3000, cost=0.15, purpose="test", business_id=1)

    # Verify the result
    assert result is True

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT model, tokens, cost, purpose, business_id FROM api_costs WHERE purpose = 'test'")
    cost_entry = cursor.fetchone()

    assert cost_entry[0] == "gpt-4"
    assert cost_entry[1] == 3000
    assert cost_entry[2] == 0.15
    assert cost_entry[3] == "test"
    assert cost_entry[4] == 1


def test_get_cost_summary(mock_db):
    """Test getting a summary of API costs by model and purpose."""
    # Call the function
    summary = budget_gate.get_cost_summary(mock_db)

    # Verify the result
    assert "by_model" in summary
    assert "by_purpose" in summary
    assert "gpt-4" in summary["by_model"]
    assert "gpt-3.5-turbo" in summary["by_model"]
    assert "mockup" in summary["by_purpose"]
    assert "email" in summary["by_purpose"]

    # Verify totals
    assert summary["total"] == 0.15
    assert summary["by_model"]["gpt-4"] == 0.10
    assert summary["by_model"]["gpt-3.5-turbo"] == 0.05
    assert summary["by_purpose"]["mockup"] == 0.10
    assert summary["by_purpose"]["email"] == 0.05


if __name__ == "__main__":
    pytest.main(["-v", __file__])
