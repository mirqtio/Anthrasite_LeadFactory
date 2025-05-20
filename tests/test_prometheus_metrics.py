"""
Tests for Prometheus metrics endpoint and alert rules.
"""
import pytest
import requests
from prometheus_client.parser import text_string_to_metric_families


@pytest.fixture
def metrics_endpoint():
    """Return the URL for the Prometheus metrics endpoint."""
    return "http://localhost:8000/metrics"


def test_metrics_endpoint_available(metrics_endpoint):
    """Test that the metrics endpoint is available and returns 200."""
    response = requests.get(metrics_endpoint, timeout=5)
    assert response.status_code == 200, "Metrics endpoint should return 200"


def test_metrics_include_required_gauges(metrics_endpoint):
    """Test that required gauges are present in the metrics output."""
    response = requests.get(metrics_endpoint, timeout=5)
    metrics = text_string_to_metric_families(response.text)

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
