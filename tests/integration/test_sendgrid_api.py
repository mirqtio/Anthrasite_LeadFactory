"""
Integration tests for SendGrid API.

These tests verify that the SendGrid API integration works correctly.
They will run with mocks by default, but can use the real API when --use-real-apis is specified.
"""

import os
import uuid
from unittest.mock import patch

import pytest

from tests.integration.api_test_config import APITestConfig


def test_sendgrid_send_email_basic(sendgrid_api, api_metrics_logger):
    """Test basic email sending functionality."""
    # Generate a unique subject for testing
    test_id = str(uuid.uuid4())[:8]
    subject = f"Test Email {test_id}"

    # Use test email address (when using real API, always send to yourself)
    from_email = "test@example.com"
    to_email = "test@example.com"
    if APITestConfig.should_use_real_api("sendgrid"):
        # For real API, use a real email that you control
        # Use the same email for from_email and to_email to avoid sending to others
        api_key = os.environ.get("SENDGRID_API_KEY", "")
        if "@" in api_key:  # Some people store email in API key var
            to_email = from_email = api_key
        else:
            # Try to get email from environment
            test_email = os.environ.get("TEST_EMAIL")
            if test_email and "@" in test_email:
                to_email = from_email = test_email

    content = f"""
    <h1>Test Email from API Integration Test</h1>
    <p>This is a test email sent from the API integration tests.</p>
    <p>Test ID: {test_id}</p>
    """

    result = sendgrid_api.send_email(
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        content=content,
        metrics_logger=api_metrics_logger,
    )

    assert "status_code" in result

    # Check status code
    if APITestConfig.should_use_real_api("sendgrid"):
        assert result["status_code"] == 202, (
            f"Expected status code 202, got: {result['status_code']}"
        )
    else:
        assert result["status_code"] == 202, "Mock API should return status code 202"


def test_sendgrid_email_with_different_content(sendgrid_api, api_metrics_logger):
    """Test sending emails with different content."""
    content_types = [
        ("<h1>HTML Email</h1><p>This is an <strong>HTML</strong> email.</p>", "HTML"),
        ("<p>Simple email with a <a href='https://example.com'>link</a>.</p>", "Link"),
        ("<h1>Email with List</h1><ul><li>Item 1</li><li>Item 2</li></ul>", "List"),
    ]

    for content, content_type in content_types:
        # Generate a unique subject for testing
        test_id = str(uuid.uuid4())[:8]
        subject = f"Test {content_type} Email {test_id}"

        result = sendgrid_api.send_email(
            from_email="test@example.com",
            to_email="test@example.com",
            subject=subject,
            content=content,
            metrics_logger=api_metrics_logger,
        )

        assert "status_code" in result
        assert result["status_code"] == 202, f"Failed to send {content_type} email"


@pytest.mark.real_api
def test_sendgrid_api_error_handling(sendgrid_api):
    """Test error handling in the SendGrid API client."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("sendgrid"):
        pytest.skip("Test requires real API connection")

    # Test with invalid API key
    with patch.dict(os.environ, {"SENDGRID_API_KEY": "invalid_key"}):
        # Create a new client with invalid key
        from tests.integration.api_fixtures import sendgrid_api as sendgrid_api_fixture

        invalid_sendgrid_api = sendgrid_api_fixture(None)

        # Test error handling
        with pytest.raises(Exception) as excinfo:
            invalid_sendgrid_api.send_email(
                from_email="test@example.com",
                to_email="test@example.com",
                subject="Test Error Handling",
                content="<p>Test content</p>",
            )

        assert any(
            term in str(excinfo.value).lower()
            for term in ["authentication", "api key", "invalid", "unauthorized"]
        )


@pytest.mark.real_api
def test_sendgrid_api_invalid_email(sendgrid_api):
    """Test error handling for invalid email addresses."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("sendgrid"):
        pytest.skip("Test requires real API connection")

    # Test with invalid email format
    with pytest.raises(Exception) as excinfo:
        sendgrid_api.send_email(
            from_email="invalid-email",  # Invalid email format
            to_email="test@example.com",
            subject="Test Invalid Email",
            content="<p>Test content</p>",
        )

    assert any(
        term in str(excinfo.value).lower() for term in ["email", "invalid", "format"]
    )


def test_sendgrid_api_metrics_tracking(sendgrid_api, api_metrics_logger):
    """Test that API metrics tracking works correctly."""
    # Clear previous metrics
    api_metrics_logger.metrics = []

    # Send test email
    sendgrid_api.send_email(
        from_email="test@example.com",
        to_email="test@example.com",
        subject="Test Metrics Tracking",
        content="<p>Test content for metrics tracking</p>",
        metrics_logger=api_metrics_logger,
    )

    # Check that metrics were logged
    assert len(api_metrics_logger.metrics) > 0
    metric = api_metrics_logger.metrics[0]
    assert metric["api"] == "sendgrid"
    assert metric["endpoint"] == "send_email"
    assert metric["latency"] > 0
