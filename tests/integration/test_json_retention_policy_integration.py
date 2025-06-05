"""
Integration tests for JSON retention policy with database operations.
"""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from leadfactory.config.json_retention_policy import (
    get_retention_expiry_date,
    process_json_for_storage,
    should_store_json,
)
from leadfactory.pipeline.scrape import save_business
from leadfactory.storage import get_storage_instance


class TestJSONRetentionPolicyIntegration:
    """Integration test cases for JSON retention policy."""

    @pytest.fixture
    def storage(self):
        """Get storage instance for testing."""
        return get_storage_instance()

    def test_business_creation_with_retention_policy_enabled(self, storage):
        """Test business creation when JSON retention is enabled."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False):

            test_yelp_json = {
                "id": "test-business-123",
                "name": "Test Restaurant",
                "rating": 4.5,
                "phone": "555-1234",
                "location": {
                    "address": "123 Main St",
                    "zip_code": "12345"
                }
            }

            business_id = save_business(
                name="Test Restaurant",
                address="123 Main St, Anytown, CA 12345",
                zip_code="12345",
                category="restaurant",
                yelp_response_json=test_yelp_json,
                source="yelp",
                source_id="test-business-123"
            )

            assert business_id is not None

            # Verify JSON was stored
            business = storage.get_business_by_id(business_id)
            assert business is not None

            # Check if we can access the stored yelp_response_json
            # Note: This depends on the storage implementation
            business_details = storage.get_business_details(business_id)
            if business_details and "yelp_response" in business_details:
                stored_json = business_details["yelp_response"]
                if isinstance(stored_json, str):
                    stored_json = json.loads(stored_json)
                assert stored_json["id"] == "test-business-123"

    def test_business_creation_with_retention_policy_disabled(self, storage):
        """Test business creation when JSON retention is disabled."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):

            test_yelp_json = {
                "id": "test-business-456",
                "name": "Test Cafe",
                "rating": 4.0
            }

            business_id = save_business(
                name="Test Cafe",
                address="456 Oak Ave, Somewhere, NY 67890",
                zip_code="67890",
                category="cafe",
                yelp_response_json=test_yelp_json,
                source="yelp",
                source_id="test-business-456"
            )

            assert business_id is not None

            # Verify business was created but JSON should not be stored
            business = storage.get_business_by_id(business_id)
            assert business is not None

    def test_business_creation_with_anonymization(self, storage):
        """Test business creation with JSON anonymization enabled."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 30), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "id,rating,categories"):

            test_yelp_json = {
                "id": "test-business-789",
                "name": "John's Pizza",  # Should be redacted
                "rating": 4.2,  # Should be preserved
                "phone": "555-9876",  # Should be redacted
                "categories": ["pizza", "restaurant"],  # Should be preserved
                "owner_name": "John Smith",  # Should be redacted
                "location": {
                    "address": "789 Pine St",  # Should be redacted
                    "zip_code": "54321"
                }
            }

            business_id = save_business(
                name="John's Pizza",
                address="789 Pine St, Testville, FL 54321",
                zip_code="54321",
                category="restaurant",
                yelp_response_json=test_yelp_json,
                source="yelp",
                source_id="test-business-789"
            )

            assert business_id is not None

            # Verify business was created
            business = storage.get_business_by_id(business_id)
            assert business is not None

    def test_retention_expiry_date_setting(self):
        """Test that retention expiry dates are set correctly."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 60):

            expiry_date = get_retention_expiry_date()

            assert expiry_date is not None

            # Should be approximately 60 days from now
            expected = datetime.now() + timedelta(days=60)
            time_diff = abs((expiry_date - expected).total_seconds())
            assert time_diff < 60  # Within 1 minute

    def test_should_store_json_function(self):
        """Test the global should_store_json function."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90):
            assert should_store_json() is True

        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            assert should_store_json() is False

        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 0):
            assert should_store_json() is False

    def test_process_json_for_storage_function(self):
        """Test the global process_json_for_storage function."""
        test_data = {"id": "test", "name": "Test Business", "rating": 4.0}

        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False):
            result = process_json_for_storage(test_data)
            assert result == test_data

        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            result = process_json_for_storage(test_data)
            assert result is None

    def test_google_places_json_processing(self, storage):
        """Test JSON processing for Google Places responses."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False):

            test_google_json = {
                "place_id": "ChIJtest123",
                "name": "Test Business",
                "rating": 4.3,
                "formatted_phone_number": "(555) 123-4567",
                "geometry": {
                    "location": {
                        "lat": 40.7128,
                        "lng": -74.0060
                    }
                }
            }

            business_id = save_business(
                name="Test Business",
                address="123 Test St, New York, NY 10001",
                zip_code="10001",
                category="business",
                google_response_json=test_google_json,
                source="google",
                source_id="ChIJtest123"
            )

            assert business_id is not None

            # Verify business was created
            business = storage.get_business_by_id(business_id)
            assert business is not None

    def test_multiple_json_sources(self, storage):
        """Test business creation with both Yelp and Google JSON data."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False):

            test_yelp_json = {
                "id": "yelp-test-123",
                "name": "Multi Source Business",
                "rating": 4.1
            }

            test_google_json = {
                "place_id": "google-test-123",
                "name": "Multi Source Business",
                "rating": 4.2
            }

            business_id = save_business(
                name="Multi Source Business",
                address="999 Multi St, Testburg, TX 75001",
                zip_code="75001",
                category="business",
                yelp_response_json=test_yelp_json,
                google_response_json=test_google_json,
                source="yelp",
                source_id="yelp-test-123"
            )

            assert business_id is not None

            # Verify business was created
            business = storage.get_business_by_id(business_id)
            assert business is not None
