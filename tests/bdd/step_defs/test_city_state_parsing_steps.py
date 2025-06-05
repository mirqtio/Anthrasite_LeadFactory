"""Step definitions for city and state parsing BDD tests."""

from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from leadfactory.pipeline.scrape import (
    parse_city_state_from_address,
    process_yelp_business,
    process_google_place
)

# Load scenarios
scenarios('../features/city_state_parsing.feature')


@pytest.fixture
def scraping_context():
    """Context for scraping tests."""
    return {
        'parsed_city': None,
        'parsed_state': None,
        'business_data': {},
        'mock_storage': None
    }


@given("the LeadFactory pipeline is configured")
def configure_pipeline():
    """Configure the pipeline for testing."""
    pass  # No specific configuration needed for these tests


@given(parsers.parse('a Yelp business with display address "{address}"'))
def setup_yelp_business(scraping_context, address):
    """Set up a Yelp business with display address."""
    # Extract ZIP from address
    import re
    zip_match = re.search(r'\b(\d{5})\b', address)
    zip_code = zip_match.group(1) if zip_match else ""

    # Split address into lines for Yelp format
    parts = address.rsplit(', ', 2)  # Split from right to get city, state zip
    if len(parts) >= 3:
        street = parts[0]
        city_state_zip = parts[1] + ', ' + parts[2]
        display_address = [street, city_state_zip]
    else:
        display_address = [address]

    scraping_context['business_data'] = {
        "id": "test-business-123",
        "name": "Test Business",
        "location": {
            "display_address": display_address,
            "zip_code": zip_code
        }
    }


@given(parsers.parse('a Google Place with formatted address "{address}"'))
def setup_google_place(scraping_context, address):
    """Set up a Google Place with formatted address."""
    # Extract ZIP from address
    import re
    zip_match = re.search(r'\b(\d{5})\b', address)
    zip_code = zip_match.group(1) if zip_match else ""

    scraping_context['business_data'] = {
        "place_id": "test-place-123",
        "name": "Test Place",
        "formatted_address": address,
        "address_components": [
            {
                "long_name": zip_code,
                "types": ["postal_code"]
            }
        ] if zip_code else []
    }


@given(parsers.parse('a business address "{address}"'))
def setup_business_address(scraping_context, address):
    """Set up a business address for parsing."""
    scraping_context['business_data'] = {
        'address': address
    }


@given("a business with no address information")
def setup_empty_address(scraping_context):
    """Set up a business with no address."""
    scraping_context['business_data'] = {
        'address': ''
    }


@when("the business is processed through the scraping pipeline")
def process_business_scraping(scraping_context):
    """Process the business through scraping pipeline."""
    # Create mock storage
    mock_storage = Mock()
    mock_storage.create_business = Mock(return_value=123)
    mock_storage.get_business_by_source_id = Mock(return_value=None)
    mock_storage.get_business_by_website = Mock(return_value=None)
    mock_storage.get_business_by_phone = Mock(return_value=None)
    mock_storage.get_business_by_name_and_zip = Mock(return_value=None)

    scraping_context['mock_storage'] = mock_storage

    with patch('leadfactory.pipeline.scrape.get_storage_instance', return_value=mock_storage):
        with patch('leadfactory.pipeline.scrape.should_store_json', return_value=False):
            business_data = scraping_context['business_data']

            if 'location' in business_data:  # Yelp business
                process_yelp_business(business_data, "test_category")
            else:  # Google place
                # Mock Google API
                mock_google_api = Mock()
                # Return some details so it doesn't return early
                mock_google_api.get_place_details = Mock(return_value=(
                    {"formatted_phone_number": "+1 650-253-0000"},
                    None
                ))
                process_google_place(business_data, "test_category", mock_google_api)


@when("the place is processed through the scraping pipeline")
def process_place_scraping(scraping_context):
    """Process the Google place through scraping pipeline."""
    process_business_scraping(scraping_context)


@when("the address is parsed")
def parse_address(scraping_context):
    """Parse the address."""
    address = scraping_context['business_data'].get('address', '')
    city, state = parse_city_state_from_address(address)
    scraping_context['parsed_city'] = city
    scraping_context['parsed_state'] = state


@when("the business is processed")
def process_empty_business(scraping_context):
    """Process business with empty address."""
    parse_address(scraping_context)


@then(parsers.parse('the business should have city "{expected_city}"'))
def verify_business_city(scraping_context, expected_city):
    """Verify the business has the expected city."""
    if scraping_context['mock_storage'] and scraping_context['mock_storage'].create_business.called:
        # Check the mock call arguments
        call_args = scraping_context['mock_storage'].create_business.call_args
        # Debug output
        print(f"DEBUG: create_business called with args: {call_args}")

        # The create_business signature is:
        # create_business(name, address, city, state, zip_code, category, ...)
        # So city is at index 2
        if call_args[0]:  # Positional arguments
            assert len(call_args[0]) >= 3, f"Not enough args: {call_args[0]}"
            actual_city = call_args[0][2]
            assert actual_city == expected_city, f"Expected city '{expected_city}', got '{actual_city}'"
        else:  # Keyword arguments
            assert 'city' in call_args[1]
            assert call_args[1]['city'] == expected_city
    else:
        assert scraping_context['parsed_city'] == expected_city


@then(parsers.parse('the business should have state "{expected_state}"'))
def verify_business_state(scraping_context, expected_state):
    """Verify the business has the expected state."""
    if scraping_context['mock_storage'] and scraping_context['mock_storage'].create_business.called:
        # Check the mock call arguments
        call_args = scraping_context['mock_storage'].create_business.call_args

        # The create_business signature is:
        # create_business(name, address, city, state, zip_code, category, ...)
        # So state is at index 3
        if call_args[0]:  # Positional arguments
            assert len(call_args[0]) >= 4, f"Not enough args: {call_args[0]}"
            actual_state = call_args[0][3]
            assert actual_state == expected_state, f"Expected state '{expected_state}', got '{actual_state}'"
        else:  # Keyword arguments
            assert 'state' in call_args[1]
            assert call_args[1]['state'] == expected_state
    else:
        assert scraping_context['parsed_state'] == expected_state


@then(parsers.parse('the city should be "{expected_city}"'))
def verify_parsed_city(scraping_context, expected_city):
    """Verify the parsed city."""
    assert scraping_context['parsed_city'] == expected_city


@then(parsers.parse('the state should be "{expected_state}"'))
def verify_parsed_state(scraping_context, expected_state):
    """Verify the parsed state."""
    assert scraping_context['parsed_state'] == expected_state


@then("the business should have empty city")
def verify_empty_city(scraping_context):
    """Verify the business has empty city."""
    assert scraping_context['parsed_city'] == ""


@then("the business should have empty state")
def verify_empty_state(scraping_context):
    """Verify the business has empty state."""
    assert scraping_context['parsed_state'] == ""
