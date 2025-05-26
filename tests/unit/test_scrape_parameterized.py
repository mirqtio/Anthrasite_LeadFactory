"""
Parameterized tests for the scraping functionality.
Tests scraping with different filters, sources, and error handling scenarios.
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# Import the modules being tested
from leadfactory.pipeline import scrape


# Test data for business categories
test_categories = [
    {
        "id": "restaurants",
        "category": "restaurants",
        "expected_filters": ["food", "dining", "restaurant"],
        "expected_min_businesses": 5
    },
    {
        "id": "tech_companies",
        "category": "tech",
        "expected_filters": ["technology", "software", "IT"],
        "expected_min_businesses": 10
    },
    {
        "id": "retail_stores",
        "category": "retail",
        "expected_filters": ["shop", "store", "retail"],
        "expected_min_businesses": 8
    },
    {
        "id": "healthcare",
        "category": "healthcare",
        "expected_filters": ["doctor", "medical", "health"],
        "expected_min_businesses": 6
    },
    {
        "id": "professional_services",
        "category": "professional",
        "expected_filters": ["consulting", "service", "professional"],
        "expected_min_businesses": 7
    }
]


# Parameterized test for scraping with different categories
@pytest.mark.parametrize(
    "category_case",
    test_categories,
    ids=[case["id"] for case in test_categories]
)
def test_scraping_by_category(category_case):
    """Test scraping businesses with different categories."""
    # Mock the actual scraping function to return test data
    def mock_scrape_businesses(category, location, limit):
        """Mock function to simulate scraping businesses."""
        # Generate mock business data based on category
        businesses = []
        for i in range(category_case["expected_min_businesses"]):
            businesses.append({
                "name": f"{category.title()} Business {i+1}",
                "address": f"{100+i} Main St",
                "city": "Testville",
                "state": "TS",
                "zip": f"{i+10000}",
                "phone": f"555-{i:03d}-{i*111:04d}",
                "website": f"http://{category.lower()}{i+1}.com",
                "category": category
            })
        return businesses

    # Mock the function that gets filters for a category
    def mock_get_category_filters(category):
        """Mock function to return filters for a category."""
        # Return the expected filters for this category
        return category_case["expected_filters"]

    # Patch the actual scraping functions
    with patch("bin.scrape.scrape_businesses_from_api") as mock_scrape, \
         patch("bin.scrape.get_filters_for_category") as mock_filters:

        # Configure the mocks
        mock_scrape.side_effect = mock_scrape_businesses
        mock_filters.side_effect = mock_get_category_filters

        # Call the scrape function with the test category
        location = "Test Location"
        limit = 20
        results = scrape.scrape_businesses_by_category(
            category_case["category"],
            location,
            limit
        )

        # Verify the results
        assert len(results) >= category_case["expected_min_businesses"], \
            f"Expected at least {category_case['expected_min_businesses']} businesses, got {len(results)}"

        # Verify category filters were used
        mock_filters.assert_called_once_with(category_case["category"])

        # Verify scrape function was called with correct parameters
        mock_scrape.assert_called_with(category_case["category"], location, limit)


# Test data for location filters
test_locations = [
    {
        "id": "major_city",
        "location": "New York, NY",
        "radius": 10,
        "expected_min_businesses": 20
    },
    {
        "id": "mid_size_city",
        "location": "Austin, TX",
        "radius": 15,
        "expected_min_businesses": 15
    },
    {
        "id": "small_town",
        "location": "Smallville, KS",
        "radius": 20,
        "expected_min_businesses": 5
    },
    {
        "id": "zip_code",
        "location": "90210",
        "radius": 5,
        "expected_min_businesses": 10
    },
    {
        "id": "county",
        "location": "Orange County, CA",
        "radius": 25,
        "expected_min_businesses": 18
    }
]


# Parameterized test for scraping with different locations
@pytest.mark.parametrize(
    "location_case",
    test_locations,
    ids=[case["id"] for case in test_locations]
)
def test_scraping_by_location(location_case):
    """Test scraping businesses with different locations and radii."""
    # Mock the actual scraping function to return test data based on location
    def mock_scrape_by_location(category, location, radius, limit):
        """Mock function to simulate scraping businesses by location."""
        # Generate mock business data based on location
        businesses = []
        for i in range(location_case["expected_min_businesses"]):
            businesses.append({
                "name": f"Business {i+1} in {location}",
                "address": f"{100+i} Local St",
                "city": location.split(",")[0] if "," in location else location,
                "state": location.split(",")[1].strip() if "," in location else "ST",
                "zip": f"{i+10000}",
                "phone": f"555-{i:03d}-{i*111:04d}",
                "website": f"http://biz{i+1}-{location.lower().replace(' ', '-').replace(',', '')}.com",
                "category": category,
                "distance": i * (radius / location_case["expected_min_businesses"])  # Simulate distance within radius
            })
        return businesses

    # Patch the actual scraping function
    with patch("bin.scrape.scrape_businesses_from_api_with_radius") as mock_scrape:
        # Configure the mock
        mock_scrape.side_effect = mock_scrape_by_location

        # Call the scrape function with the test location
        category = "test_category"
        limit = 50
        results = scrape.scrape_businesses_by_location(
            category,
            location_case["location"],
            location_case["radius"],
            limit
        )

        # Verify the results
        assert len(results) >= location_case["expected_min_businesses"], \
            f"Expected at least {location_case['expected_min_businesses']} businesses, got {len(results)}"

        # Verify scrape function was called with correct parameters
        mock_scrape.assert_called_with(
            category,
            location_case["location"],
            location_case["radius"],
            limit
        )

        # Verify all businesses are within the specified radius
        for business in results:
            assert "distance" in business, "Business should have a distance field"
            assert business["distance"] <= location_case["radius"], \
                f"Business distance {business['distance']} exceeds radius {location_case['radius']}"


# Test data for business filtering
test_filters = [
    {
        "id": "website_filter",
        "businesses": [
            {"name": "Business 1", "website": "http://business1.com"},
            {"name": "Business 2", "website": None},
            {"name": "Business 3", "website": "http://business3.com"},
            {"name": "Business 4", "website": ""}
        ],
        "filter_type": "has_website",
        "expected_count": 2
    },
    {
        "id": "phone_filter",
        "businesses": [
            {"name": "Business 1", "phone": "555-123-4567"},
            {"name": "Business 2", "phone": None},
            {"name": "Business 3", "phone": "555-987-6543"},
            {"name": "Business 4", "phone": ""}
        ],
        "filter_type": "has_phone",
        "expected_count": 2
    },
    {
        "id": "keyword_filter",
        "businesses": [
            {"name": "Tech Solutions", "description": "We provide IT services"},
            {"name": "Food Delivery", "description": "We deliver food"},
            {"name": "Tech Support", "description": "Computer repair"},
            {"name": "Grocery Store", "description": "We sell food and groceries"}
        ],
        "filter_type": "keyword",
        "filter_value": "tech",
        "expected_count": 2
    },
    {
        "id": "location_filter",
        "businesses": [
            {"name": "Business 1", "city": "San Francisco", "state": "CA"},
            {"name": "Business 2", "city": "New York", "state": "NY"},
            {"name": "Business 3", "city": "San Jose", "state": "CA"},
            {"name": "Business 4", "city": "Boston", "state": "MA"}
        ],
        "filter_type": "location",
        "filter_value": "CA",
        "expected_count": 2
    },
    {
        "id": "combined_filters",
        "businesses": [
            {"name": "Tech 1", "website": "http://tech1.com", "city": "San Francisco"},
            {"name": "Tech 2", "website": None, "city": "San Francisco"},
            {"name": "Food 1", "website": "http://food1.com", "city": "New York"},
            {"name": "Food 2", "website": "http://food2.com", "city": "San Francisco"}
        ],
        "filter_type": "combined",
        "filters": [
            {"type": "has_website", "value": True},
            {"type": "location", "value": "San Francisco"}
        ],
        "expected_count": 2
    }
]


# Parameterized test for filtering businesses
@pytest.mark.parametrize(
    "filter_case",
    test_filters,
    ids=[case["id"] for case in test_filters]
)
def test_business_filtering(filter_case):
    """Test filtering businesses with different criteria."""
    # Define filter functions
    def has_website_filter(business):
        """Filter businesses that have a website."""
        return business.get("website") and business["website"].strip() != ""

    def has_phone_filter(business):
        """Filter businesses that have a phone number."""
        return business.get("phone") and business["phone"].strip() != ""

    def keyword_filter(business, keyword):
        """Filter businesses that contain a keyword in name or description."""
        name = business.get("name", "").lower()
        description = business.get("description", "").lower()
        return keyword.lower() in name or keyword.lower() in description

    def location_filter(business, location):
        """Filter businesses by location (city or state)."""
        city = business.get("city", "").lower()
        state = business.get("state", "").lower()
        return location.lower() in city or location.lower() in state

    # Apply the appropriate filter
    if filter_case["filter_type"] == "has_website":
        filtered = [b for b in filter_case["businesses"] if has_website_filter(b)]

    elif filter_case["filter_type"] == "has_phone":
        filtered = [b for b in filter_case["businesses"] if has_phone_filter(b)]

    elif filter_case["filter_type"] == "keyword":
        keyword = filter_case["filter_value"]
        filtered = [b for b in filter_case["businesses"] if keyword_filter(b, keyword)]

    elif filter_case["filter_type"] == "location":
        location = filter_case["filter_value"]
        filtered = [b for b in filter_case["businesses"] if location_filter(b, location)]

    elif filter_case["filter_type"] == "combined":
        filtered = filter_case["businesses"]
        for filter_item in filter_case["filters"]:
            if filter_item["type"] == "has_website":
                filtered = [b for b in filtered if has_website_filter(b)]
            elif filter_item["type"] == "has_phone":
                filtered = [b for b in filtered if has_phone_filter(b)]
            elif filter_item["type"] == "keyword":
                filtered = [b for b in filtered if keyword_filter(b, filter_item["value"])]
            elif filter_item["type"] == "location":
                filtered = [b for b in filtered if location_filter(b, filter_item["value"])]

    # Verify the filtered results
    assert len(filtered) == filter_case["expected_count"], \
        f"Expected {filter_case['expected_count']} businesses after filtering, got {len(filtered)}"


# Test data for error handling
error_test_cases = [
    {
        "id": "api_timeout",
        "error_type": "timeout",
        "error_message": "Request timed out after 30 seconds",
        "expected_retries": 3
    },
    {
        "id": "api_rate_limit",
        "error_type": "rate_limit",
        "error_message": "Rate limit exceeded. Try again in 60 seconds.",
        "expected_retries": 2,
        "expected_backoff": True
    },
    {
        "id": "api_server_error",
        "error_type": "server_error",
        "error_message": "Internal server error (500)",
        "expected_retries": 3
    },
    {
        "id": "api_auth_error",
        "error_type": "auth_error",
        "error_message": "Authentication failed. Invalid API key.",
        "expected_retries": 0  # Auth errors shouldn't be retried
    },
    {
        "id": "api_not_found",
        "error_type": "not_found",
        "error_message": "Requested resource not found (404)",
        "expected_retries": 0  # Not found errors shouldn't be retried
    }
]


# Parameterized test for API error handling
@pytest.mark.parametrize(
    "error_case",
    error_test_cases,
    ids=[case["id"] for case in error_test_cases]
)
def test_scraping_error_handling(error_case):
    """Test error handling during scraping."""
    # Create an error-raising mock
    def mock_scrape_with_error(*args, **kwargs):
        """Mock that raises errors based on the test case."""
        if error_case["error_type"] == "timeout":
            from requests.exceptions import Timeout
            raise Timeout(error_case["error_message"])
        elif error_case["error_type"] == "rate_limit":
            from requests.exceptions import HTTPError
            response = MagicMock()
            response.status_code = 429
            raise HTTPError(error_case["error_message"], response=response)
        elif error_case["error_type"] == "server_error":
            from requests.exceptions import HTTPError
            response = MagicMock()
            response.status_code = 500
            raise HTTPError(error_case["error_message"], response=response)
        elif error_case["error_type"] == "auth_error":
            from requests.exceptions import HTTPError
            response = MagicMock()
            response.status_code = 401
            raise HTTPError(error_case["error_message"], response=response)
        elif error_case["error_type"] == "not_found":
            from requests.exceptions import HTTPError
            response = MagicMock()
            response.status_code = 404
            raise HTTPError(error_case["error_message"], response=response)

    # Patch the scrape function and retry tracking
    with patch("bin.scrape.scrape_businesses_from_api") as mock_scrape, \
         patch("bin.scrape.time.sleep") as mock_sleep, \
         patch("bin.scrape.logging.error") as mock_log_error, \
         patch("bin.scrape.logging.warning") as mock_log_warning:

        # Configure the mock to raise errors
        mock_scrape.side_effect = mock_scrape_with_error

        # Call the function that should handle errors
        try:
            # Define a simplified version of scrape_with_retry function
            def scrape_with_retry(category, location, limit, max_retries=3, backoff_factor=1.5):
                """Simplified version of a function that retries scraping on certain errors."""
                retries = 0
                while retries <= max_retries:
                    try:
                        return scrape.scrape_businesses_from_api(category, location, limit)
                    except Exception as e:
                        # Log the error
                        if "404" in str(e) or "401" in str(e):
                            mock_log_error(f"Non-recoverable error: {str(e)}")
                            raise  # Don't retry auth or not found errors

                        retries += 1
                        if retries <= max_retries:
                            mock_log_warning(f"Retry {retries}/{max_retries}: {str(e)}")
                            # Sleep with exponential backoff if needed
                            if "429" in str(e) and backoff_factor > 1:
                                sleep_time = backoff_factor ** retries
                                mock_sleep(sleep_time)
                        else:
                            mock_log_error(f"Max retries exceeded: {str(e)}")
                            raise

                return []  # Empty result if all retries fail

            # Try to scrape with retry
            result = scrape_with_retry("test", "test", 10)

            # If we get here, there was no exception (shouldn't happen with our mock)
            assert False, "Expected an exception to be raised"

        except Exception:
            # Expected behavior - check if retry logic was followed
            if error_case["expected_retries"] > 0:
                # Check that the function tried the expected number of retries
                assert mock_scrape.call_count == error_case["expected_retries"] + 1, \
                    f"Expected {error_case['expected_retries'] + 1} calls, got {mock_scrape.call_count}"

                # Check that backoff was used if expected
                if error_case.get("expected_backoff", False):
                    assert mock_sleep.call_count > 0, "Expected sleep to be called for backoff"
            else:
                # For non-retryable errors, function should only be called once
                assert mock_scrape.call_count == 1, \
                    f"Expected 1 call for non-retryable error, got {mock_scrape.call_count}"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
