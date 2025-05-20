"""
Tests for budget audit functionality.
"""

from utils.cost_tracker import (
    get_daily_cost,
    get_monthly_cost,
    check_budget_thresholds,
    is_scaling_gate_active,
)


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
    required_keys = [
        "daily_cost",
        "monthly_cost",
        "daily_percentage",
        "monthly_percentage",
        "daily_alert",
        "monthly_alert",
    ]
    for key in required_keys:
        assert key in thresholds, f"Missing key in thresholds: {key}"


def test_scaling_gate():
    """Test scaling gate status check."""
    status, _ = is_scaling_gate_active()
    assert isinstance(status, bool), "Scaling gate status should be boolean"


# Add more tests as needed for specific budget scenarios
