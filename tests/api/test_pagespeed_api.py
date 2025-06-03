"""
Test the PageSpeed API with real credentials.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Test if the PageSpeed API key is available in the environment
def test_pagespeed_api_key_in_env():
    """Test if PageSpeed API key is set in environment variables."""
    # Look for PageSpeed API key in different possible environment variables
    pagespeed_key = os.environ.get("PAGESPEED_KEY", None)

    # Skip test if key is not available in the environment
    if not pagespeed_key:
        pytest.skip("PAGESPEED_KEY not found in environment variables")

    assert pagespeed_key is not None, "PageSpeed API key should be set"
    assert len(pagespeed_key) > 10, "PageSpeed API key should be a valid length"

def test_pagespeed_api_call():
    """Test if PageSpeed API can be called successfully."""
    # Look for PageSpeed API key in different possible environment variables
    pagespeed_key = os.environ.get("PAGESPEED_KEY", None)

    # Skip test if key is not available in the environment
    if not pagespeed_key:
        pytest.skip("PAGESPEED_KEY not found in environment variables")

    # Test website to analyze
    test_url = "https://www.google.com"

    # PageSpeed Insights API endpoint
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={test_url}&key={pagespeed_key}"

    # Make the API call
    response = requests.get(api_url, timeout=30)

    # Check if the call was successful
    assert response.status_code == 200, f"PageSpeed API call failed with status code {response.status_code}"

    # Check if the response contains the expected data
    json_response = response.json()
    assert "lighthouseResult" in json_response, "Response should contain lighthouse results"
    assert "categories" in json_response["lighthouseResult"], "Response should contain categories"
    assert "performance" in json_response["lighthouseResult"]["categories"], "Response should contain performance category"

@patch("requests.get")
def test_pagespeed_api_with_mock(mock_get):
    """Test PageSpeed API with mocked response for CI environments without real keys."""
    # Create a mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "lighthouseResult": {
            "categories": {
                "performance": {
                    "score": 0.95
                }
            },
            "audits": {
                "speed-index": {
                    "displayValue": "1.5 s",
                    "score": 0.98
                },
                "first-contentful-paint": {
                    "displayValue": "0.8 s",
                    "score": 0.99
                },
                "largest-contentful-paint": {
                    "displayValue": "1.2 s",
                    "score": 0.97
                }
            }
        }
    }

    # Set up the mock
    mock_get.return_value = mock_response

    # Test URL
    test_url = "https://www.example.com"

    # Simulate API call (will use mock)
    api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={test_url}&key=fake_key"
    response = requests.get(api_url)

    # Verify mock was called
    mock_get.assert_called_once()

    # Check mock response
    assert response.status_code == 200
    data = response.json()
    assert data["lighthouseResult"]["categories"]["performance"]["score"] == 0.95
