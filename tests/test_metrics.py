"""
Tests for the metrics module.
"""

from unittest.mock import patch

import pytest

# Check if fastapi is available
fastapi_available = False
try:
    from fastapi.testclient import TestClient

    from utils.metrics import app, update_metrics

    # Create test client
    client = TestClient(app)
    fastapi_available = True
except ImportError:
    # Skip tests if fastapi is not available
    pytest.skip(
        "fastapi not installed, skipping metrics tests", allow_module_level=True
    )


@pytest.fixture
def mock_cost_data():
    return {"openai": 10.5, "sendgrid": 2.3}


@pytest.fixture
def mock_budget_data():
    return {
        "daily_cost": 12.8,
        "daily_budget": 50.0,
        "monthly_cost": 120.5,
        "monthly_budget": 1000.0,
        "daily_alert": False,
        "monthly_alert": False,
    }


def test_metrics_endpoint(mock_cost_data, mock_budget_data):
    """Test the /metrics endpoint."""
    with (
        patch("utils.metrics.get_cost_breakdown_by_service") as mock_get_costs,
        patch("utils.metrics.check_budget_thresholds") as mock_budget,
        patch("utils.metrics.is_scaling_gate_active") as mock_gate,
    ):
        # Setup mocks
        mock_get_costs.return_value = mock_cost_data
        mock_budget.return_value = mock_budget_data
        mock_gate.return_value = (False, "Below threshold")
        # Make request
        response = client.get("/metrics")
        # Assert response
        assert response.status_code == 200
        assert (
            response.headers["Content-Type"]
            == "text/plain; version=0.0.4; charset=utf-8"
        )
        # Check if metrics are in the response
        metrics = response.text
        assert "lead_factory_daily_cost" in metrics
        assert "lead_factory_monthly_cost" in metrics
        assert "lead_factory_budget_utilization" in metrics
        assert "lead_factory_scaling_gate_active" in metrics


def test_health_endpoint():
    """Test the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_scaling_gate_status():
    """Test the /scaling-gate/status endpoint."""
    with patch("utils.metrics.is_scaling_gate_active") as mock_gate:
        mock_gate.return_value = (True, "Test reason")
        response = client.get("/scaling-gate/status")
        assert response.status_code == 200
        data = response.json()
        assert data["scaling_gate_active"] is True
        assert data["reason"] == "Test reason"
        assert "timestamp" in data


def test_daily_costs_endpoint(mock_cost_data):
    """Test the /costs/daily endpoint."""
    with patch("utils.metrics.get_cost_breakdown_by_service") as mock_get_costs:
        mock_get_costs.return_value = mock_cost_data
        response = client.get("/costs/daily")
        assert response.status_code == 200
        assert response.json() == mock_cost_data


def test_monthly_costs_endpoint(mock_cost_data):
    """Test the /costs/monthly endpoint."""
    with patch("utils.metrics.get_cost_breakdown_by_service") as mock_get_costs:
        mock_get_costs.return_value = mock_cost_data
        response = client.get("/costs/monthly")
        assert response.status_code == 200
        assert response.json() == mock_cost_data


def test_http_metrics():
    """Test that HTTP metrics are recorded."""
    # Make a request to ensure metrics are generated
    response = client.get("/health")
    assert response.status_code == 200
    # Check metrics
    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.text
    # Check for HTTP metrics in the response
    # We don't need to check exact values, just that the metrics exist
    assert "http_requests_total" in metrics_text, "HTTP requests metric not found"
    assert (
        "http_request_duration_seconds" in metrics_text
    ), "HTTP duration metric not found"


def test_update_metrics(mock_cost_data, mock_budget_data):
    """Test the update_metrics function."""
    with (
        patch("utils.metrics.get_cost_breakdown_by_service") as mock_get_costs,
        patch("utils.metrics.check_budget_thresholds") as mock_budget,
        patch("utils.metrics.is_scaling_gate_active") as mock_gate,
    ):
        # Setup mocks
        mock_get_costs.return_value = mock_cost_data
        mock_budget.return_value = mock_budget_data
        mock_gate.return_value = (False, "Below threshold")
        # Call the function
        update_metrics()
        # Verify the mocks were called
        assert mock_get_costs.call_count == 2  # Called once for daily, once for monthly
        mock_budget.assert_called_once()
        mock_gate.assert_called_once()
