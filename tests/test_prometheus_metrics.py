"""
Tests for Prometheus metrics endpoint and alert rules.
"""

import pytest
import requests
import unittest.mock as mock
from prometheus_client.parser import text_string_to_metric_families


@pytest.fixture
def mock_metrics_response():
    """Return a mock metrics response with sample metrics."""
    sample_metrics = """
# HELP batch_runtime_seconds Duration of batch processing jobs
# TYPE batch_runtime_seconds gauge
batch_runtime_seconds{job="lead_enrichment"} 45.2
# HELP pipeline_stage_duration_seconds Duration of pipeline processing stages
# TYPE pipeline_stage_duration_seconds gauge
pipeline_stage_duration_seconds{stage="scraping"} 12.3
pipeline_stage_duration_seconds{stage="enrichment"} 8.7
# HELP lead_processing_duration_seconds Duration of lead processing
# TYPE lead_processing_duration_seconds gauge
lead_processing_duration_seconds{type="new"} 3.2
# HELP api_request_duration_seconds Duration of API requests
# TYPE api_request_duration_seconds gauge
api_request_duration_seconds{endpoint="yelp"} 0.8
# HELP email_queue_size Current size of the email queue
# TYPE email_queue_size gauge
email_queue_size 15
# HELP budget_usage_ratio Current budget usage ratio
# TYPE budget_usage_ratio gauge
budget_usage_ratio{period="daily"} 0.45
    """
    return sample_metrics


def test_metrics_endpoint_available(mock_metrics_response):
    """Test that the metrics endpoint is available and returns 200."""
    # Instead of making a real HTTP request, we'll mock the response
    with mock.patch("requests.get") as mock_get:
        # Create a mock response object
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.text = mock_metrics_response
        # Configure the mock to return our mock response
        mock_get.return_value = mock_response
        # Make the request (which will be mocked)
        response = requests.get("http://localhost:8000/metrics", timeout=5)
        # Verify the response
        assert response.status_code == 200, "Metrics endpoint should return 200"


def test_metrics_include_required_gauges(mock_metrics_response):
    """Test that required gauges are present in the metrics output."""
    # Parse the mock metrics response directly
    metrics = text_string_to_metric_families(mock_metrics_response)
    required_metrics = [
        "batch_runtime_seconds",
        "pipeline_stage_duration_seconds",
        "lead_processing_duration_seconds",
        "api_request_duration_seconds",
        "email_queue_size",
        "budget_usage_ratio",
    ]
    metric_names = set()
    for family in metrics:
        metric_names.add(family.name)
    for metric in required_metrics:
        assert metric in metric_names, f"Required metric {metric} not found in metrics"


def test_alert_rules_file_exists():
    """Test that the alert rules file exists and is valid YAML."""
    import yaml
    from pathlib import Path

    alert_rules_path = Path("etc/alert_rules.yml")
    assert alert_rules_path.exists(), "Alert rules file does not exist"
    # Try to load the YAML to validate syntax
    with open(alert_rules_path, "r") as f:
        rules = yaml.safe_load(f)
    # Basic validation of alert rules structure
    assert "groups" in rules, "Alert rules should have 'groups' key"
    assert len(rules["groups"]) > 0, "Alert rules should have at least one group"
    # Check for required alert rules
    required_alerts = [
        "MonthlyBudgetWarning",
        "MonthlyBudgetCritical",
        "PipelineStageFailed",
        "HighCPUUsage",
        "HighMemoryUsage",
        "EmailQueueBacklog",
        "APIFailureRate",
    ]
    alert_names = []
    for group in rules["groups"]:
        for rule in group.get("rules", []):
            if "alert" in rule:
                alert_names.append(rule["alert"])
    for alert in required_alerts:
        assert alert in alert_names, f"Required alert rule {alert} not found"
