"""
Integration tests for external API services.

These tests demonstrate how to use the API test fixtures with both mock and real APIs.
"""

import pytest

from tests.integration.api_test_config import APITestConfig


# Yelp API Tests
@pytest.mark.real_api
def test_yelp_api_business_search(yelp_api, api_metrics_logger):
    """Test searching for businesses using Yelp API."""
    # This test will be skipped unless --use-real-apis is specified
    result = yelp_api.business_search(
        term="plumber", location="New York", limit=3, metrics_logger=api_metrics_logger
    )

    assert "businesses" in result
    assert isinstance(result["businesses"], list)
    assert len(result["businesses"]) <= 3

    if result["businesses"]:
        business = result["businesses"][0]
        assert "id" in business
        assert "name" in business
        assert "categories" in business


def test_yelp_api_mock_business_details(yelp_api):
    """Test getting business details using Yelp API (always uses mock)."""
    # This test always uses the mock API
    result = yelp_api.business_details(business_id="mock-business-1")

    assert "id" in result
    assert result["id"] == "mock-business-1"
    assert "name" in result
    assert "location" in result


# Google Places API Tests
@pytest.mark.real_api
def test_google_places_api_search(google_places_api, api_metrics_logger):
    """Test searching for places using Google Places API."""
    # This test will be skipped unless --use-real-apis is specified
    result = google_places_api.place_search(
        query="HVAC contractors in New York", metrics_logger=api_metrics_logger
    )

    assert "results" in result
    assert "status" in result
    assert result["status"] == "OK"

    if result["results"]:
        place = result["results"][0]
        assert "place_id" in place
        assert "name" in place


def test_google_places_api_mock_details(google_places_api):
    """Test getting place details using Google Places API (always uses mock)."""
    # This test always uses the mock API
    result = google_places_api.place_details(place_id="mock-place-1")

    assert "result" in result
    assert "status" in result
    assert result["status"] == "OK"
    assert result["result"]["place_id"] == "mock-place-1"


# OpenAI API Tests
@pytest.mark.real_api
def test_openai_api_chat_completion(openai_api, api_metrics_logger):
    """Test generating chat completions using OpenAI API."""
    # This test will be skipped unless --use-real-apis is specified
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ]

    result = openai_api.chat_completion(
        messages=messages,
        model="gpt-3.5-turbo",  # Use a less expensive model for testing
        metrics_logger=api_metrics_logger,
    )

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "message" in result["choices"][0]
    assert "content" in result["choices"][0]["message"]
    assert "Paris" in result["choices"][0]["message"]["content"]


def test_openai_api_mock_chat_completion(openai_api):
    """Test generating chat completions using OpenAI API (always uses mock)."""
    # This test always uses the mock API
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ]

    result = openai_api.chat_completion(messages=messages)

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "message" in result["choices"][0]
    assert "content" in result["choices"][0]["message"]


# SendGrid API Tests
@pytest.mark.real_api
def test_sendgrid_api_send_email(sendgrid_api, api_metrics_logger):
    """Test sending emails using SendGrid API."""
    # This test will be skipped unless --use-real-apis is specified
    # Use a test email address to avoid sending real emails
    from_email = "test@example.com"
    to_email = "test@example.com"  # Send to yourself for testing
    subject = "API Integration Test"
    content = "<h1>This is a test email</h1><p>This is a test of the SendGrid API integration.</p>"

    result = sendgrid_api.send_email(
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        content=content,
        metrics_logger=api_metrics_logger,
    )

    assert "status_code" in result
    assert result["status_code"] == 202  # SendGrid returns 202 for successful sends


def test_sendgrid_api_mock_send_email(sendgrid_api):
    """Test sending emails using SendGrid API (always uses mock)."""
    # This test always uses the mock API
    result = sendgrid_api.send_email(
        from_email="test@example.com",
        to_email="test@example.com",
        subject="Test Email",
        content="<p>Test content</p>",
    )

    assert "status_code" in result
    assert result["status_code"] == 202


# ScreenshotOne API Tests
@pytest.mark.real_api
def test_screenshotone_api_take_screenshot(screenshotone_api, api_metrics_logger):
    """Test taking screenshots using ScreenshotOne API."""
    # This test will be skipped unless --use-real-apis is specified
    screenshot = screenshotone_api.take_screenshot(
        url="https://example.com", full_page=True, metrics_logger=api_metrics_logger
    )

    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0
    assert screenshot.startswith(b"\x89PNG")  # PNG signature


def test_screenshotone_api_mock_take_screenshot(screenshotone_api):
    """Test taking screenshots using ScreenshotOne API (always uses mock)."""
    # This test always uses the mock API
    screenshot = screenshotone_api.take_screenshot(url="https://example.com")

    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0


# Test API configuration
def test_api_test_config():
    """Test the API test configuration module."""
    # Check API key detection
    api_keys = APITestConfig.get_api_keys()
    assert isinstance(api_keys, dict)
    assert "yelp" in api_keys
    assert "google" in api_keys
    assert "openai" in api_keys
    assert "sendgrid" in api_keys
    assert "screenshotone" in api_keys

    # Check API usage decision logic
    use_real = APITestConfig.should_use_real_api("yelp")
    assert isinstance(use_real, bool)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
