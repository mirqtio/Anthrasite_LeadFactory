"""
Unit tests for address parsing functionality in scrape.py
"""
import pytest
from leadfactory.pipeline.scrape import parse_city_state_from_address, _get_state_abbreviation


class TestAddressParsing:
    """Test cases for the parse_city_state_from_address function."""

    def test_standard_address_with_zip(self):
        """Test standard US address format with ZIP code."""
        city, state = parse_city_state_from_address("123 Main St, New York, NY 10001")
        assert city == "New York"
        assert state == "NY"

    def test_address_with_full_state_name(self):
        """Test address with full state name."""
        city, state = parse_city_state_from_address("789 Pine Rd, Chicago, Illinois 60601")
        assert city == "Chicago"
        assert state == "IL"

    def test_address_no_comma_before_state(self):
        """Test address without comma before state."""
        city, state = parse_city_state_from_address("123 Main St, Seattle WA 98101")
        assert city == "Seattle"
        assert state == "WA"

    def test_address_no_zip(self):
        """Test address without ZIP code."""
        city, state = parse_city_state_from_address("456 Oak Ave, Miami, FL")
        assert city == "Miami"
        assert state == "FL"

    def test_city_state_only(self):
        """Test simple city, state format."""
        city, state = parse_city_state_from_address("New York, NY")
        assert city == "New York"
        assert state == "NY"

    def test_complex_city_name(self):
        """Test city names with multiple words."""
        city, state = parse_city_state_from_address("123 Main St, San Francisco, CA 94102")
        assert city == "San Francisco"
        assert state == "CA"

        city, state = parse_city_state_from_address("456 Oak Ave, Las Vegas, Nevada 89101")
        assert city == "Las Vegas"
        assert state == "NV"

    def test_empty_or_invalid_address(self):
        """Test edge cases with empty or invalid addresses."""
        city, state = parse_city_state_from_address("")
        assert city == ""
        assert state == ""

        city, state = parse_city_state_from_address("123 Main St")
        assert city == ""
        assert state == ""

        city, state = parse_city_state_from_address(None)
        assert city == ""
        assert state == ""

    def test_address_with_multiple_commas(self):
        """Test addresses with multiple comma-separated parts."""
        city, state = parse_city_state_from_address("123 Main St, Suite 100, Portland, OR 97201")
        assert city == "Portland"
        assert state == "OR"


class TestStateAbbreviation:
    """Test cases for the _get_state_abbreviation helper function."""

    def test_common_state_names(self):
        """Test conversion of common state names to abbreviations."""
        assert _get_state_abbreviation("California") == "CA"
        assert _get_state_abbreviation("california") == "CA"
        assert _get_state_abbreviation("New York") == "NY"
        assert _get_state_abbreviation("texas") == "TX"
        assert _get_state_abbreviation("Florida") == "FL"

    def test_already_abbreviated(self):
        """Test states that are already abbreviated."""
        assert _get_state_abbreviation("CA") == "CA"
        assert _get_state_abbreviation("NY") == "NY"

    def test_unknown_state(self):
        """Test unknown state names."""
        result = _get_state_abbreviation("Unknown State")
        assert result == "UN"  # First 2 characters uppercase

    def test_edge_cases(self):
        """Test edge cases for state abbreviation."""
        assert _get_state_abbreviation("") == ""
        assert _get_state_abbreviation("A") == "A"


class TestAddressParsingIntegration:
    """Integration tests for address parsing in realistic scenarios."""

    @pytest.mark.parametrize("address,expected_city,expected_state", [
        # Real-world Yelp address formats
        ("1600 Amphitheatre Pkwy, Mountain View, CA 94043", "Mountain View", "CA"),
        ("350 5th Ave, New York, NY 10118", "New York", "NY"),
        ("1 Infinite Loop, Cupertino, CA 95014", "Cupertino", "CA"),

        # Real-world Google Places address formats
        ("233 S Wacker Dr, Chicago, IL 60606", "Chicago", "IL"),
        ("1901 Thornridge Cir, Shiloh, Hawaii 81063", "Shiloh", "HI"),

        # Edge cases that might come from APIs
        ("Downtown, Seattle, WA", "Seattle", "WA"),
        ("Main Street, Boston, Massachusetts", "Boston", "MA"),
    ])
    def test_realistic_address_formats(self, address, expected_city, expected_state):
        """Test parsing of realistic address formats from external APIs."""
        city, state = parse_city_state_from_address(address)
        assert city == expected_city
        assert state == expected_state

    def test_international_addresses_graceful_failure(self):
        """Test that international addresses fail gracefully."""
        # These should not parse successfully (return empty strings)
        city, state = parse_city_state_from_address("123 Queen St, Toronto, ON M5H 2M9")
        assert city == ""
        assert state == ""

        city, state = parse_city_state_from_address("10 Downing Street, London, UK")
        assert city == ""
        assert state == ""

        city, state = parse_city_state_from_address("123 Main St, Vancouver, BC")
        assert city == ""
        assert state == ""
