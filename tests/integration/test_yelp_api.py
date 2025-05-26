"""
Integration tests for Yelp Fusion API.

These tests verify that the Yelp API integration works correctly.
They will run with mocks by default, but can use the real API when --use-real-apis is specified.
"""

import os
import pytest
from unittest.mock import patch

from tests.integration.api_test_config import APITestConfig


@pytest.mark.parametrize("location", ["New York, NY", "Seattle, WA", "Carmel, IN"])
def test_yelp_business_search_locations(yelp_api, api_metrics_logger, location):
    """Test that Yelp business search works with different locations."""
    result = yelp_api.business_search(
        term="plumber",
        location=location,
        limit=3,
        metrics_logger=api_metrics_logger
    )

    assert "businesses" in result
    assert "total" in result
    assert isinstance(result["businesses"], list)

    if result["businesses"]:
        business = result["businesses"][0]
        assert "id" in business
        assert "name" in business
        assert "location" in business, f"Business {business['name']} has no location data"
        assert "categories" in business, f"Business {business['name']} has no categories"


@pytest.mark.parametrize("term", ["plumber", "hvac", "veterinarian"])
def test_yelp_business_search_categories(yelp_api, api_metrics_logger, term):
    """Test that Yelp business search works with different categories."""
    result = yelp_api.business_search(
        term=term,
        location="New York, NY",
        limit=3,
        metrics_logger=api_metrics_logger
    )

    assert "businesses" in result
    assert isinstance(result["businesses"], list)

    # Verify category filtering works
    if result["businesses"] and APITestConfig.should_use_real_api("yelp"):
        # Only verify category filtering with real API
        categories_found = False
        for business in result["businesses"]:
            for category in business.get("categories", []):
                if term.lower() in category["title"].lower():
                    categories_found = True
                    break
            if categories_found:
                break

        assert categories_found, f"No businesses found with category related to '{term}'"


def test_yelp_business_details(yelp_api, api_metrics_logger):
    """Test retrieving details for a specific business."""
    # For real API, we need to get a business ID first
    if APITestConfig.should_use_real_api("yelp"):
        # First get a business ID from search
        search_result = yelp_api.business_search(
            term="plumber",
            location="New York, NY",
            limit=1,
            metrics_logger=api_metrics_logger
        )

        assert "businesses" in search_result
        assert len(search_result["businesses"]) > 0
        business_id = search_result["businesses"][0]["id"]
    else:
        # Use mock business ID
        business_id = "mock-business-1"

    # Now get business details
    result = yelp_api.business_details(
        business_id=business_id,
        metrics_logger=api_metrics_logger
    )

    assert "id" in result
    assert result["id"] == business_id
    assert "name" in result
    assert "location" in result
    assert "categories" in result

    # Detailed information that should be present
    if APITestConfig.should_use_real_api("yelp"):
        # These fields might not be present for all businesses, so only check with real API
        assert "rating" in result
        assert "phone" in result
        assert "url" in result


@pytest.mark.real_api
def test_yelp_api_error_handling(yelp_api):
    """Test that the Yelp API client handles errors correctly."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("yelp"):
        pytest.skip("Test requires real API connection")

    # Test with invalid API key
    with patch.dict(os.environ, {"YELP_API_KEY": "invalid_key"}):
        # Create a new client with invalid key
        from tests.integration.api_fixtures import yelp_api as yelp_api_fixture
        invalid_yelp_api = yelp_api_fixture(None)

        # Test error handling
        with pytest.raises(Exception) as excinfo:
            invalid_yelp_api.business_search(term="test", location="test")

        assert any(code in str(excinfo.value) for code in ["401", "403", "Unauthorized", "Forbidden"])


def test_yelp_api_limit_parameter(yelp_api, api_metrics_logger):
    """Test that the limit parameter works correctly."""
    for limit in [1, 2, 5]:
        result = yelp_api.business_search(
            term="plumber",
            location="New York, NY",
            limit=limit,
            metrics_logger=api_metrics_logger
        )

        assert "businesses" in result
        assert len(result["businesses"]) <= limit, f"Expected at most {limit} results, got {len(result['businesses'])}"


@pytest.mark.real_api
def test_yelp_api_rate_limit_handling(yelp_api, api_metrics_logger):
    """Test that the API client handles rate limits correctly."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("yelp"):
        pytest.skip("Test requires real API connection")

    # Make multiple requests in quick succession to potentially hit rate limits
    for _ in range(5):
        result = yelp_api.business_search(
            term="plumber",
            location="New York, NY",
            limit=1,
            metrics_logger=api_metrics_logger
        )

        assert "businesses" in result

    # If we got here without exceptions, rate limiting is handled correctly
