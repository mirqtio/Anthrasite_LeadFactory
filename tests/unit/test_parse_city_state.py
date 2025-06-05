"""Test parsing and storing city/state for businesses."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bin.scrape import process_yelp_business, process_google_place


class TestParseCityState:
    """Test parsing city and state from business addresses."""

    @pytest.fixture
    def mock_save_business(self):
        """Mock save_business function."""
        with patch('bin.scrape.save_business') as mock:
            mock.return_value = 123
            yield mock

    @pytest.fixture
    def yelp_business_data(self):
        """Sample Yelp business data."""
        return {
            "id": "test-business-123",
            "name": "Test Business LLC",
            "phone": "+14155551234",
            "url": "https://www.yelp.com/biz/test-business",
            "location": {
                "address1": "123 Main Street",
                "address2": "Suite 100",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94105",
                "country": "US"
            }
        }

    @pytest.fixture
    def google_place_data(self):
        """Sample Google Places data."""
        return {
            "place_id": "ChIJtest123",
            "name": "Google Test Business",
            "formatted_address": "456 Market St, San Francisco, CA 94105, USA",
            "formatted_phone_number": "(415) 555-5678",
            "website": "https://testbusiness.com",
            "address_components": [
                {
                    "long_name": "456",
                    "short_name": "456",
                    "types": ["street_number"]
                },
                {
                    "long_name": "Market Street",
                    "short_name": "Market St",
                    "types": ["route"]
                },
                {
                    "long_name": "San Francisco",
                    "short_name": "San Francisco",
                    "types": ["locality", "political"]
                },
                {
                    "long_name": "San Francisco County",
                    "short_name": "San Francisco County",
                    "types": ["administrative_area_level_2", "political"]
                },
                {
                    "long_name": "California",
                    "short_name": "CA",
                    "types": ["administrative_area_level_1", "political"]
                },
                {
                    "long_name": "United States",
                    "short_name": "US",
                    "types": ["country", "political"]
                },
                {
                    "long_name": "94105",
                    "short_name": "94105",
                    "types": ["postal_code"]
                }
            ]
        }

    def test_process_yelp_business_extracts_city_state(self, mock_save_business, yelp_business_data):
        """Test that process_yelp_business correctly extracts city and state."""
        # Process the business
        result = process_yelp_business(yelp_business_data, "Restaurant")
        
        # Should return the business ID
        assert result == 123
        
        # Check that save_business was called with correct parameters
        mock_save_business.assert_called_once()
        call_args = mock_save_business.call_args[1]
        
        # Verify city and state were extracted
        assert call_args["name"] == "Test Business LLC"
        assert call_args["address"] == "123 Main Street, Suite 100"
        assert call_args["city"] == "San Francisco"
        assert call_args["state"] == "CA"
        assert call_args["zip_code"] == "94105"
        assert call_args["source"] == "yelp"
        assert call_args["source_id"] == "test-business-123"

    def test_process_yelp_business_handles_missing_address2(self, mock_save_business):
        """Test handling of business without address2."""
        business_data = {
            "id": "test-456",
            "name": "Simple Business",
            "location": {
                "address1": "789 Oak Ave",
                "city": "Los Angeles",
                "state": "CA",
                "zip_code": "90001"
            }
        }
        
        result = process_yelp_business(business_data, "Service")
        
        assert result == 123
        call_args = mock_save_business.call_args[1]
        assert call_args["address"] == "789 Oak Ave"  # No Suite/address2
        assert call_args["city"] == "Los Angeles"
        assert call_args["state"] == "CA"

    @patch('bin.scrape.GooglePlacesAPI')
    def test_process_google_place_extracts_city_state(self, mock_google_api_class, mock_save_business, google_place_data):
        """Test that process_google_place correctly extracts city and state from components."""
        # Mock the API
        mock_api = Mock()
        mock_api.get_place_details.return_value = (google_place_data, None)
        mock_google_api_class.return_value = mock_api
        
        # Process the place
        place = {"place_id": "ChIJtest123", "name": "Google Test Business"}
        result = process_google_place(place, "Restaurant", mock_api)
        
        # Should return the business ID
        assert result == 123
        
        # Check that save_business was called with correct parameters
        mock_save_business.assert_called_once()
        call_args = mock_save_business.call_args[1]
        
        # Verify city and state were extracted from address components
        assert call_args["name"] == "Google Test Business"
        assert call_args["address"] == "456 Market Street"
        assert call_args["city"] == "San Francisco"
        assert call_args["state"] == "CA"
        assert call_args["zip_code"] == "94105"
        assert call_args["source"] == "google"
        assert call_args["source_id"] == "ChIJtest123"

    @patch('bin.scrape.GooglePlacesAPI')
    def test_process_google_place_fallback_to_formatted_address(self, mock_google_api_class, mock_save_business):
        """Test fallback when address components are missing."""
        # Mock place data without address components
        place_data = {
            "place_id": "ChIJtest789",
            "name": "Fallback Business",
            "formatted_address": "1000 Broadway, New York, NY 10001, USA",
            "address_components": []  # Empty components
        }
        
        mock_api = Mock()
        mock_api.get_place_details.return_value = (place_data, None)
        mock_google_api_class.return_value = mock_api
        
        place = {"place_id": "ChIJtest789"}
        result = process_google_place(place, "Store", mock_api)
        
        assert result == 123
        call_args = mock_save_business.call_args[1]
        
        # Should use formatted address as fallback
        assert call_args["address"] == "1000 Broadway, New York, NY 10001, USA"
        assert call_args["city"] == ""  # Not extracted
        assert call_args["state"] == ""  # Not extracted

    def test_process_yelp_business_handles_missing_location_fields(self, mock_save_business):
        """Test handling of missing city/state in Yelp data."""
        business_data = {
            "id": "incomplete-123",
            "name": "Incomplete Business",
            "location": {
                "address1": "Unknown Street",
                # Missing city, state, zip
            }
        }
        
        result = process_yelp_business(business_data, "Unknown")
        
        assert result == 123
        call_args = mock_save_business.call_args[1]
        assert call_args["address"] == "Unknown Street"
        assert call_args["city"] == ""
        assert call_args["state"] == ""
        assert call_args["zip_code"] == ""

    @patch('bin.scrape.extract_email_from_website')
    def test_city_state_preserved_through_pipeline(self, mock_extract_email, mock_save_business, yelp_business_data):
        """Test that city/state data flows through the entire processing pipeline."""
        mock_extract_email.return_value = "info@testbusiness.com"
        
        result = process_yelp_business(yelp_business_data, "Restaurant")
        
        assert result == 123
        
        # Verify complete data preservation
        call_args = mock_save_business.call_args[1]
        assert call_args["city"] == "San Francisco"
        assert call_args["state"] == "CA"
        assert call_args["email"] == "info@testbusiness.com"