"""
Unit tests for the scrape module.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from leadfactory.pipeline import scrape


@pytest.fixture
def mock_scrape_api():
    """Mock for scraping API responses."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "Test Business 1",
                    "address": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip": "12345",
                    "phone": "555-123-4567",
                    "website": "http://test1.com",
                },
                {
                    "name": "Test Business 2",
                    "address": "456 Oak St",
                    "city": "Somewhere",
                    "state": "NY",
                    "zip": "67890",
                    "phone": "555-987-6543",
                    "website": "http://test2.com",
                },
            ]
        }
        mock_get.return_value = mock_response
        yield mock_get


def test_scrape_businesses(mock_scrape_api):
    """Test scraping businesses from the API."""
    # Call the function with test parameters
    businesses = scrape.scrape_businesses(source="test", limit=10)

    # Assert API was called correctly
    mock_scrape_api.assert_called_once()

    # Verify the returned data
    assert len(businesses) == 2
    assert businesses[0]["name"] == "Test Business 1"
    assert businesses[0]["address"] == "123 Main St"
    assert businesses[1]["name"] == "Test Business 2"
    assert businesses[1]["website"] == "http://test2.com"


def test_scrape_with_filters(mock_scrape_api):
    """Test scraping businesses with filters."""

    # Set up mock to return different data based on parameters
    def mock_get_side_effect(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Check if location filter was applied
        if "location=CA" in args[0]:
            mock_response.json.return_value = {
                "results": [
                    {
                        "name": "Test Business 1",
                        "address": "123 Main St",
                        "city": "Anytown",
                        "state": "CA",
                        "zip": "12345",
                    }
                ]
            }
        else:
            mock_response.json.return_value = {"results": []}

        return mock_response

    mock_scrape_api.side_effect = mock_get_side_effect

    # Test with location filter
    businesses = scrape.scrape_businesses(source="test", location="CA", limit=10)

    # Verify the filtered results
    assert len(businesses) == 1
    assert businesses[0]["state"] == "CA"


def test_scrape_error_handling(mock_scrape_api):
    """Test error handling during scraping."""
    # Configure mock to return an error
    mock_scrape_api.return_value.status_code = 500
    mock_scrape_api.return_value.json.side_effect = Exception("API Error")

    # Call the function and check error handling
    with pytest.raises(Exception) as exc_info:
        scrape.scrape_businesses(source="test", limit=10)

    assert "API Error" in str(exc_info.value)


def test_transform_scraped_data():
    """Test transforming scraped raw data to business objects."""
    # Sample raw data
    raw_data = [
        {
            "business_name": "Test Business",
            "street_address": "123 Main St",
            "locality": "Anytown",
            "region": "CA",
            "postal_code": "12345",
            "telephone": "555-123-4567",
            "web_url": "http://test.com",
        }
    ]

    # Transform the data
    businesses = scrape.transform_scraped_data(raw_data)

    # Verify transformation
    assert len(businesses) == 1
    assert businesses[0]["name"] == "Test Business"
    assert businesses[0]["address"] == "123 Main St"
    assert businesses[0]["city"] == "Anytown"
    assert businesses[0]["state"] == "CA"
    assert businesses[0]["zip"] == "12345"
    assert businesses[0]["phone"] == "555-123-4567"
    assert businesses[0]["website"] == "http://test.com"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
