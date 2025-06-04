"""
Integration tests for ScreenshotOne API.

These tests verify that the ScreenshotOne API integration works correctly.
They will run with mocks by default, but can use the real API when --use-real-apis is specified.
"""

import os
from unittest.mock import patch

import pytest

from tests.integration.api_test_config import APITestConfig


def test_screenshotone_basic_screenshot(screenshotone_api, api_metrics_logger):
    """Test basic screenshot functionality."""
    url = "https://example.com"

    screenshot = screenshotone_api.take_screenshot(
        url=url, metrics_logger=api_metrics_logger
    )

    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0

    # Check if it's a valid PNG image (starts with PNG signature)
    assert screenshot.startswith(b"\x89PNG"), "Screenshot data is not a valid PNG"


@pytest.mark.parametrize(
    "url",
    [
        "https://google.com",
        "https://github.com",
        "https://wikipedia.org",
        "https://python.org",
    ],
)
def test_screenshotone_different_websites(screenshotone_api, api_metrics_logger, url):
    """Test taking screenshots of different websites."""
    # Skip some real API tests to avoid excessive API usage
    if (
        APITestConfig.should_use_real_api("screenshotone")
        and url != "https://example.com"
    ):
        if os.environ.get("TEST_ALL_SCREENSHOTS") != "1":
            pytest.skip(
                "Skipping to avoid excessive API usage. Set TEST_ALL_SCREENSHOTS=1 to run all."
            )

    screenshot = screenshotone_api.take_screenshot(
        url=url, metrics_logger=api_metrics_logger
    )

    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0
    assert screenshot.startswith(b"\x89PNG"), "Screenshot data is not a valid PNG"


def test_screenshotone_options(screenshotone_api, api_metrics_logger):
    """Test screenshot options like dimensions and format."""
    url = "https://example.com"

    # Test different dimensions
    for width, height in [(800, 600), (1024, 768), (1280, 1024)]:
        screenshot = screenshotone_api.take_screenshot(
            url=url, width=width, height=height, metrics_logger=api_metrics_logger
        )

        assert isinstance(screenshot, bytes)
        assert len(screenshot) > 0
        assert screenshot.startswith(b"\x89PNG"), "Screenshot data is not a valid PNG"


def test_screenshotone_full_page(screenshotone_api, api_metrics_logger):
    """Test full page screenshot option."""
    url = "https://example.com"

    screenshot = screenshotone_api.take_screenshot(
        url=url, full_page=True, metrics_logger=api_metrics_logger
    )

    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0
    assert screenshot.startswith(b"\x89PNG"), "Screenshot data is not a valid PNG"


@pytest.mark.real_api
def test_screenshotone_api_error_handling(screenshotone_api):
    """Test error handling in the ScreenshotOne API client."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("screenshotone"):
        pytest.skip("Test requires real API connection")

    # Test with invalid API key
    with patch.dict(os.environ, {"SCREENSHOTONE_API_KEY": "invalid_key"}):
        # Create a new client with invalid key
        from tests.integration.api_fixtures import (
            screenshotone_api as screenshotone_api_fixture,
        )

        invalid_screenshotone_api = screenshotone_api_fixture(None)

        # Test error handling
        with pytest.raises(Exception) as excinfo:
            invalid_screenshotone_api.take_screenshot(url="https://example.com")

        assert any(
            term in str(excinfo.value).lower()
            for term in ["authentication", "api key", "invalid", "unauthorized"]
        )


@pytest.mark.real_api
def test_screenshotone_api_invalid_url(screenshotone_api):
    """Test error handling for invalid URLs."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("screenshotone"):
        pytest.skip("Test requires real API connection")

    # Test with invalid URL format
    with pytest.raises(Exception) as excinfo:
        screenshotone_api.take_screenshot(url="invalid-url")

    assert any(
        term in str(excinfo.value).lower() for term in ["url", "invalid", "format"]
    )


def test_screenshotone_api_metrics_tracking(screenshotone_api, api_metrics_logger):
    """Test that API metrics tracking works correctly."""
    # Clear previous metrics
    api_metrics_logger.metrics = []

    # Take screenshot
    screenshotone_api.take_screenshot(
        url="https://example.com", metrics_logger=api_metrics_logger
    )

    # Check that metrics were logged
    assert len(api_metrics_logger.metrics) > 0
    metric = api_metrics_logger.metrics[0]
    assert metric["api"] == "screenshotone"
    assert metric["endpoint"] == "take_screenshot"
    assert metric["latency"] > 0


@pytest.mark.real_api
def test_screenshotone_save_screenshot(screenshotone_api, api_metrics_logger, tmpdir):
    """Test saving screenshots to disk."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("screenshotone"):
        pytest.skip("Test requires real API connection")

    url = "https://example.com"

    # Take screenshot
    screenshot = screenshotone_api.take_screenshot(
        url=url, metrics_logger=api_metrics_logger
    )

    # Save to disk
    output_path = tmpdir.join("test_screenshot.png")
    with open(output_path, "wb") as f:
        f.write(screenshot)

    # Verify file was saved correctly
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0

    # Clean up
    os.remove(output_path)
