"""
Tests for budget audit functionality.
"""

from utils.cost_tracker import (check_budget_thresholds, get_daily_cost,
                                get_monthly_cost, is_scaling_gate_active)


def test_daily_cost_tracking():
    """Test daily cost tracking functionality."""
    cost = get_daily_cost()
    assert isinstance(cost, float), "Daily cost should be a float"
    assert cost >= 0, "Cost should not be negative"


def test_monthly_cost_tracking():
    """Test monthly cost tracking functionality."""
    cost = get_monthly_cost()
    assert isinstance(cost, float), "Monthly cost should be a float"
    assert cost >= 0, "Cost should not be negative"


def test_budget_thresholds():
    """Test budget threshold checks."""
    thresholds = check_budget_thresholds()

    # Check top-level keys
    required_top_keys = [
        "daily",
        "monthly",
        "any_threshold_exceeded",
        "any_budget_exceeded",
    ]
    for key in required_top_keys:
        assert key in thresholds, f"Missing top-level key in thresholds: {key}"

    # Check daily section keys
    required_daily_keys = [
        "cost",
        "budget",
        "threshold",
        "threshold_exceeded",
        "budget_exceeded",
        "percent_used",
    ]
    for key in required_daily_keys:
        assert key in thresholds["daily"], f"Missing key in daily thresholds: {key}"

    # Check monthly section keys
    required_monthly_keys = [
        "cost",
        "budget",
        "threshold",
        "threshold_exceeded",
        "budget_exceeded",
        "percent_used",
    ]
    for key in required_monthly_keys:
        assert key in thresholds["monthly"], f"Missing key in monthly thresholds: {key}"


def test_scaling_gate():
    """Test scaling gate status check."""
    status, _ = is_scaling_gate_active()
    assert isinstance(status, bool), "Scaling gate status should be boolean"


# Add more tests as needed for specific budget scenarios
