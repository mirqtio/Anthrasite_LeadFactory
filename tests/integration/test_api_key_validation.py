"""Integration tests for API key validation functionality."""

import os
import unittest
from unittest.mock import patch

import pytest

from leadfactory.pipeline.scrape import validate_api_keys, scrape_businesses


class TestAPIKeyValidation(unittest.TestCase):
    """Test API key validation functionality."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment
        self.original_yelp_key = os.environ.get("YELP_KEY")
        self.original_google_key = os.environ.get("GOOGLE_KEY")

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        if self.original_yelp_key is not None:
            os.environ["YELP_KEY"] = self.original_yelp_key
        elif "YELP_KEY" in os.environ:
            del os.environ["YELP_KEY"]

        if self.original_google_key is not None:
            os.environ["GOOGLE_KEY"] = self.original_google_key
        elif "GOOGLE_KEY" in os.environ:
            del os.environ["GOOGLE_KEY"]

    def test_validate_api_keys_both_present(self):
        """Test validation passes when both API keys are present."""
        os.environ["YELP_KEY"] = "test_yelp_key"
        os.environ["GOOGLE_KEY"] = "test_google_key"

        is_valid, error_message = validate_api_keys()

        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")

    def test_validate_api_keys_yelp_missing(self):
        """Test validation fails when Yelp key is missing."""
        if "YELP_KEY" in os.environ:
            del os.environ["YELP_KEY"]
        os.environ["GOOGLE_KEY"] = "test_google_key"

        is_valid, error_message = validate_api_keys()

        self.assertFalse(is_valid)
        self.assertIn("ENV001", error_message)
        self.assertIn("YELP_KEY", error_message)
        self.assertIn("environment variables", error_message)

    def test_validate_api_keys_google_missing(self):
        """Test validation fails when Google key is missing."""
        os.environ["YELP_KEY"] = "test_yelp_key"
        if "GOOGLE_KEY" in os.environ:
            del os.environ["GOOGLE_KEY"]

        is_valid, error_message = validate_api_keys()

        self.assertFalse(is_valid)
        self.assertIn("ENV001", error_message)
        self.assertIn("GOOGLE_KEY", error_message)
        self.assertIn("environment variables", error_message)

    def test_validate_api_keys_both_missing(self):
        """Test validation fails when both keys are missing."""
        if "YELP_KEY" in os.environ:
            del os.environ["YELP_KEY"]
        if "GOOGLE_KEY" in os.environ:
            del os.environ["GOOGLE_KEY"]

        is_valid, error_message = validate_api_keys()

        self.assertFalse(is_valid)
        self.assertIn("ENV001", error_message)
        self.assertIn("YELP_KEY", error_message)
        self.assertIn("GOOGLE_KEY", error_message)

    def test_validate_api_keys_empty_strings(self):
        """Test validation fails when keys are empty strings."""
        os.environ["YELP_KEY"] = ""
        os.environ["GOOGLE_KEY"] = "   "  # Whitespace only

        is_valid, error_message = validate_api_keys()

        self.assertFalse(is_valid)
        self.assertIn("ENV001", error_message)
        self.assertIn("YELP_KEY", error_message)
        self.assertIn("GOOGLE_KEY", error_message)

    def test_scrape_businesses_blocks_on_missing_keys(self):
        """Test that scrape_businesses raises ValueError when API keys are missing."""
        if "YELP_KEY" in os.environ:
            del os.environ["YELP_KEY"]
        if "GOOGLE_KEY" in os.environ:
            del os.environ["GOOGLE_KEY"]

        vertical = {"name": "restaurants", "yelp_alias": "restaurants", "google_alias": "restaurant"}

        with self.assertRaises(ValueError) as context:
            scrape_businesses("10002", vertical, limit=5)

        self.assertIn("ENV001", str(context.exception))
        self.assertIn("YELP_KEY", str(context.exception))
        self.assertIn("GOOGLE_KEY", str(context.exception))

    @patch("leadfactory.pipeline.scrape.YelpAPI")
    @patch("leadfactory.pipeline.scrape.GooglePlacesAPI")
    @patch("leadfactory.pipeline.scrape.get_zip_coordinates")
    def test_scrape_businesses_proceeds_with_valid_keys(self, mock_coordinates, mock_google_api, mock_yelp_api):
        """Test that scrape_businesses proceeds when API keys are valid."""
        os.environ["YELP_KEY"] = "test_yelp_key"
        os.environ["GOOGLE_KEY"] = "test_google_key"

        # Mock coordinates
        mock_coordinates.return_value = "40.7128,-74.0060"

        # Mock API responses
        mock_yelp_instance = mock_yelp_api.return_value
        mock_yelp_instance.search_businesses.return_value = ([], None)

        mock_google_instance = mock_google_api.return_value
        mock_google_instance.search_places.return_value = ([], None)

        vertical = {"name": "restaurants", "yelp_alias": "restaurants", "google_alias": "restaurant"}

        # Should not raise any exception
        try:
            yelp_count, google_count = scrape_businesses("10002", vertical, limit=5)
            # Expect 0 businesses scraped due to mocked empty responses
            self.assertEqual(yelp_count, 0)
            self.assertEqual(google_count, 0)
        except ValueError:
            self.fail("scrape_businesses raised ValueError unexpectedly with valid API keys")


if __name__ == "__main__":
    unittest.main()
