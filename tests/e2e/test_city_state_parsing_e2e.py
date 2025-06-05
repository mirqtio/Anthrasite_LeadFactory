"""End-to-end test for city/state parsing functionality."""

from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.scrape import process_yelp_business, process_google_place


class TestCityStateParsingE2E:
    """End-to-end tests for city and state parsing."""

    @patch('leadfactory.pipeline.scrape.get_storage_instance')
    @patch('leadfactory.pipeline.scrape.should_store_json', return_value=False)
    def test_yelp_scraping_with_city_state(self, mock_should_store, mock_get_storage):
        """Test end-to-end Yelp scraping with city/state parsing."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.create_business = Mock(return_value=123)
        mock_storage.get_business_by_source_id = Mock(return_value=None)
        mock_storage.get_business_by_website = Mock(return_value=None)
        mock_storage.get_business_by_phone = Mock(return_value=None)
        mock_storage.get_business_by_name_and_zip = Mock(return_value=None)
        mock_get_storage.return_value = mock_storage

        # Create Yelp business data
        yelp_business = {
            "id": "golden-gate-bridge-sf",
            "name": "Golden Gate Bridge Vista Point",
            "location": {
                "display_address": [
                    "Golden Gate Bridge",
                    "San Francisco, CA 94129"
                ],
                "zip_code": "94129"
            },
            "display_phone": "+1-415-921-5858",
            "url": "https://www.yelp.com/biz/golden-gate-bridge-vista-point"
        }

        # Process the business
        business_id = process_yelp_business(yelp_business, "landmarks")

        # Verify business was created
        assert business_id == 123

        # Check the create_business call
        mock_storage.create_business.assert_called_once()
        call_args = mock_storage.create_business.call_args[0]

        # Verify city and state were parsed correctly
        assert call_args[0] == "Golden Gate Bridge Vista Point"  # name
        assert call_args[1] == "Golden Gate Bridge, San Francisco, CA 94129"  # address
        assert call_args[2] == "San Francisco"  # city
        assert call_args[3] == "CA"  # state
        assert call_args[4] == "94129"  # zip

    @patch('leadfactory.pipeline.scrape.get_storage_instance')
    @patch('leadfactory.pipeline.scrape.should_store_json', return_value=False)
    def test_google_scraping_with_city_state(self, mock_should_store, mock_get_storage):
        """Test end-to-end Google Places scraping with city/state parsing."""
        # Mock storage
        mock_storage = Mock()
        mock_storage.create_business = Mock(return_value=456)
        mock_storage.get_business_by_source_id = Mock(return_value=None)
        mock_storage.get_business_by_website = Mock(return_value=None)
        mock_storage.get_business_by_phone = Mock(return_value=None)
        mock_storage.get_business_by_name_and_zip = Mock(return_value=None)
        mock_get_storage.return_value = mock_storage

        # Mock Google Places API
        mock_google_api = Mock()
        mock_google_api.get_place_details = Mock(return_value=(
            {
                "formatted_phone_number": "(408) 961-1560",
                "website": "https://www.apple.com/retail/applepark/"
            },
            None
        ))

        # Create Google place data
        google_place = {
            "place_id": "ChIJVVVVVYx3j4AR-UJRcnfw3HI",
            "name": "Apple Park Visitor Center",
            "formatted_address": "10600 N Tantau Ave, Cupertino, CA 95014, USA",
            "address_components": [
                {
                    "long_name": "95014",
                    "types": ["postal_code"]
                }
            ]
        }

        # Process the place
        business_id = process_google_place(google_place, "technology", mock_google_api)

        # Verify business was created
        assert business_id == 456

        # Check the create_business call
        mock_storage.create_business.assert_called_once()
        call_args = mock_storage.create_business.call_args[0]

        # Verify city and state were parsed correctly
        assert call_args[0] == "Apple Park Visitor Center"  # name
        assert call_args[1] == "10600 N Tantau Ave, Cupertino, CA 95014, USA"  # address
        assert call_args[2] == "Cupertino"  # city
        assert call_args[3] == "CA"  # state
        assert call_args[4] == "95014"  # zip

    @patch('leadfactory.pipeline.scrape.get_storage_instance')
    def test_various_city_formats(self, mock_get_storage):
        """Test parsing various city name formats."""
        # Mock storage
        mock_storage = Mock()
        created_businesses = []

        def capture_business(*args):
            created_businesses.append({
                'name': args[0],
                'address': args[1],
                'city': args[2],
                'state': args[3],
                'zip': args[4]
            })
            return len(created_businesses)

        mock_storage.create_business = Mock(side_effect=capture_business)
        mock_storage.get_business_by_source_id = Mock(return_value=None)
        mock_storage.get_business_by_website = Mock(return_value=None)
        mock_storage.get_business_by_phone = Mock(return_value=None)
        mock_storage.get_business_by_name_and_zip = Mock(return_value=None)
        mock_get_storage.return_value = mock_storage

        # Test data with various city formats
        test_businesses = [
            {
                "name": "Hyphenated City Business",
                "display_address": ["123 Main St", "Winston-Salem, NC 27101"],
                "zip_code": "27101"
            },
            {
                "name": "Multi-Word City Business",
                "display_address": ["456 Broadway", "New York City, NY 10001"],
                "zip_code": "10001"
            },
            {
                "name": "Saint City Business",
                "display_address": ["789 Market St", "St. Louis, MO 63101"],
                "zip_code": "63101"
            },
            {
                "name": "Los/Las City Business",
                "display_address": ["321 Sunset Blvd", "Los Angeles, CA 90028"],
                "zip_code": "90028"
            }
        ]

        # Process each business
        with patch('leadfactory.pipeline.scrape.should_store_json', return_value=False):
            from leadfactory.pipeline.scrape import process_yelp_business

            for biz_data in test_businesses:
                yelp_business = {
                    "id": f"test-{biz_data['name'].lower().replace(' ', '-')}",
                    "name": biz_data["name"],
                    "location": {
                        "display_address": biz_data["display_address"],
                        "zip_code": biz_data["zip_code"]
                    }
                }
                process_yelp_business(yelp_business, "test_category")

        # Verify all businesses were parsed correctly
        assert len(created_businesses) == 4

        # Check each business
        assert created_businesses[0]['city'] == "Winston-Salem"
        assert created_businesses[0]['state'] == "NC"

        assert created_businesses[1]['city'] == "New York City"
        assert created_businesses[1]['state'] == "NY"

        assert created_businesses[2]['city'] == "St. Louis"
        assert created_businesses[2]['state'] == "MO"

        assert created_businesses[3]['city'] == "Los Angeles"
        assert created_businesses[3]['state'] == "CA"
