"""
Integration tests for Google Places API.

These tests verify that the Google Places API integration works correctly.
They will run with mocks by default, but can use the real API when --use-real-apis is specified.
"""

import os
from unittest.mock import patch

import pytest

from tests.integration.api_test_config import APITestConfig


@pytest.mark.parametrize(
    "query",
    [
        "HVAC contractors in New York",
        "Plumbers in Seattle",
        "Veterinarians in Carmel Indiana",
    ],
)
def test_google_places_search_queries(google_places_api, api_metrics_logger, query):
    """Test that Google Places search works with different queries."""
    result = google_places_api.place_search(
        query=query, metrics_logger=api_metrics_logger
    )

    assert "results" in result
    assert "status" in result
    assert result["status"] == "OK"
    assert isinstance(result["results"], list)

    if result["results"]:
        place = result["results"][0]
        assert "place_id" in place
        assert "name" in place
        assert "formatted_address" in place


def test_google_places_details(google_places_api, api_metrics_logger):
    """Test retrieving details for a specific place."""
    # For real API, we need to get a place ID first
    if APITestConfig.should_use_real_api("google"):
        # First get a place ID from search
        search_result = google_places_api.place_search(
            query="HVAC contractors in New York", metrics_logger=api_metrics_logger
        )

        assert "results" in search_result
        assert search_result["status"] == "OK"
        assert len(search_result["results"]) > 0
        place_id = search_result["results"][0]["place_id"]
    else:
        # Use mock place ID
        place_id = "mock-place-1"

    # Now get place details
    result = google_places_api.place_details(
        place_id=place_id, metrics_logger=api_metrics_logger
    )

    assert "result" in result
    assert "status" in result
    assert result["status"] == "OK"

    place = result["result"]
    assert "place_id" in place
    assert place["place_id"] == place_id
    assert "name" in place
    assert "formatted_address" in place


@pytest.mark.real_api
def test_google_places_api_invalid_place_id(google_places_api, api_metrics_logger):
    """Test error handling for an invalid place ID."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("google"):
        pytest.skip("Test requires real API connection")

    result = google_places_api.place_details(
        place_id="invalid_place_id_that_does_not_exist",
        metrics_logger=api_metrics_logger,
    )

    assert "status" in result
    assert result["status"] in ["NOT_FOUND", "INVALID_REQUEST"]


@pytest.mark.real_api
def test_google_places_api_error_handling(google_places_api):
    """Test that the Google Places API client handles errors correctly."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("google"):
        pytest.skip("Test requires real API connection")

    # Test with invalid API key
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "invalid_key"}):
        # Create a new client with invalid key
        from tests.integration.api_fixtures import (
            google_places_api as google_api_fixture,
        )

        invalid_google_api = google_api_fixture(None)

        # Test error handling
        result = invalid_google_api.place_search(query="HVAC contractors")

        # Google Places API returns a response with an error status instead of raising an exception
        assert "status" in result
        assert result["status"] in ["REQUEST_DENIED", "INVALID_REQUEST"]


def test_google_places_api_with_location_bias(google_places_api, api_metrics_logger):
    """Test that the Google Places search works with location bias."""
    query = "Plumbers"

    # Without location bias
    result1 = google_places_api.place_search(
        query=query, metrics_logger=api_metrics_logger
    )

    # With location bias for New York
    result2 = google_places_api.place_search(
        query=f"{query} in New York", metrics_logger=api_metrics_logger
    )

    assert "results" in result1
    assert "results" in result2
    assert result1["status"] == "OK"
    assert result2["status"] == "OK"

    # If using real API, results should be different due to location bias
    if (
        APITestConfig.should_use_real_api("google")
        and result1["results"]
        and result2["results"]
    ):
        place_ids_1 = {place["place_id"] for place in result1["results"]}
        place_ids_2 = {place["place_id"] for place in result2["results"]}

        # There should be some difference in the results
        assert place_ids_1 != place_ids_2, "Location bias did not affect search results"


@pytest.mark.real_api
def test_google_places_api_rate_limit_handling(google_places_api, api_metrics_logger):
    """Test that the API client handles rate limits correctly."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("google"):
        pytest.skip("Test requires real API connection")

    # Make multiple requests in quick succession to potentially hit rate limits
    for i in range(5):
        result = google_places_api.place_search(
            query=f"HVAC contractors in New York query {i}",  # Vary query to avoid caching
            metrics_logger=api_metrics_logger,
        )

        assert "results" in result
        assert "status" in result

        # If we hit a rate limit, the API will return OVER_QUERY_LIMIT
        if result["status"] == "OVER_QUERY_LIMIT":
            pytest.skip("Rate limit reached, which is expected behavior")
        else:
            assert result["status"] == "OK"

    # If we got here without rate limit issues, that's also fine
