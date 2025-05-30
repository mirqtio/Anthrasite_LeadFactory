#!/usr/bin/env python3
"""
Test Script for API Tester

This script tests the functionality of the ApiTester module,
ensuring it correctly validates API connectivity with proper
authentication while handling various error conditions.
"""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the API tester
from scripts.preflight.api_tester import ApiTester, ApiTestResult

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_env_file(content):
    """Create a temporary environment file with the given content"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".env")
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


class TestApiTester(unittest.TestCase):
    """Test cases for the ApiTester class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a test environment file
        env_content = """
# API keys for testing
OPENAI_API_KEY=sk-test123456789
GOOGLE_MAPS_API_KEY=AIzaTest123456
SENDGRID_API_KEY=SG.testkey123456.testkeysecondpart789012345678901234567890
MOCKUP_ENABLED=false
"""
        self.env_file = create_test_env_file(env_content)

        # Create a mock-enabled environment file
        mock_env_content = """
# API keys for testing with mock mode
OPENAI_API_KEY=sk-test123456789
GOOGLE_MAPS_API_KEY=AIzaTest123456
SENDGRID_API_KEY=SG.testkey123456.testkeysecondpart789012345678901234567890
MOCKUP_ENABLED=true
"""
        self.mock_env_file = create_test_env_file(mock_env_content)

    def tearDown(self):
        """Clean up test fixtures"""
        os.unlink(self.env_file)
        os.unlink(self.mock_env_file)

    @patch("requests.get")
    def test_openai_api_success(self, mock_get):
        """Test successful OpenAI API connection"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "gpt-4", "object": "model"}]}
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_openai_api()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIn("gpt-4", str(result.response_data))

        # Verify the correct URL and headers were used
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], tester.OPENAI_TEST_URL)
        self.assertIn("Authorization", kwargs["headers"])
        self.assertIn("Bearer", kwargs["headers"]["Authorization"])

    @patch("requests.get")
    def test_openai_api_failure(self, mock_get):
        """Test failed OpenAI API connection"""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_openai_api()

        # Check result
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 401)
        self.assertIn("Invalid API key", str(result.issues))

    @patch("requests.get")
    def test_google_maps_api_success(self, mock_get):
        """Test successful Google Maps API connection"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{"geometry": {"location": {"lat": 37.4224, "lng": -122.0842}}}],
        }
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_google_maps_api()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.response_data["status"], "OK")

        # Verify the correct URL and parameters were used
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], tester.GOOGLE_MAPS_GEOCODE_URL)
        self.assertIn("key", kwargs["params"])

    @patch("requests.get")
    def test_google_maps_api_failure(self, mock_get):
        """Test failed Google Maps API connection"""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 200  # Google returns 200 even for API errors
        mock_response.json.return_value = {
            "status": "REQUEST_DENIED",
            "error_message": "API key invalid",
        }
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_google_maps_api()

        # Check result
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertIn("REQUEST_DENIED", str(result.issues))

    @patch("requests.get")
    def test_sendgrid_api_success(self, mock_get):
        """Test successful SendGrid API connection"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"templates": []}
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_sendgrid_api()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)

        # Verify the correct URL and headers were used
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn("api.sendgrid.com", args[0])
        self.assertIn("Authorization", kwargs["headers"])
        self.assertIn("Bearer", kwargs["headers"]["Authorization"])

    @patch("requests.get")
    def test_sendgrid_api_failure(self, mock_get):
        """Test failed SendGrid API connection"""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"message": "Unauthorized"}]}
        mock_get.return_value = mock_response

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_sendgrid_api()

        # Check result
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 401)
        self.assertIn("Unauthorized", str(result.issues))

    @patch("requests.get")
    def test_mock_mode(self, mock_get):
        """Test API tests in mock mode"""
        # This test verifies that no API calls are made in mock mode

        # Create tester with mock env file
        tester = ApiTester(env_file=self.mock_env_file)

        # Run all API tests
        openai_result = tester.test_openai_api()
        maps_result = tester.test_google_maps_api()
        sendgrid_result = tester.test_sendgrid_api()
        all_result = tester.test_all_apis()

        # Check results
        self.assertTrue(openai_result.success)
        self.assertTrue(maps_result.success)
        self.assertTrue(sendgrid_result.success)
        self.assertTrue(all_result.success)

        # Verify no API calls were made
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_all_apis_success(self, mock_get):
        """Test successful connection to all APIs"""

        # Mock successful responses for all APIs
        def side_effect(*args, **kwargs):
            url = args[0]
            mock_response = MagicMock()

            if "openai.com" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": [{"id": "gpt-4", "object": "model"}]
                }
            elif "maps.googleapis.com" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "status": "OK",
                    "results": [
                        {"geometry": {"location": {"lat": 37.4224, "lng": -122.0842}}}
                    ],
                }
            elif "sendgrid.com" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {"templates": []}

            return mock_response

        mock_get.side_effect = side_effect

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_all_apis()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(len(result.issues), 0)

        # Verify all APIs were called
        self.assertEqual(mock_get.call_count, 3)

    @patch("requests.get")
    def test_all_apis_partial_failure(self, mock_get):
        """Test partial failure when testing all APIs"""

        # Mock responses with one failure
        def side_effect(*args, **kwargs):
            url = args[0]
            mock_response = MagicMock()

            if "openai.com" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": [{"id": "gpt-4", "object": "model"}]
                }
            elif "maps.googleapis.com" in url:
                mock_response.status_code = 400
                mock_response.json.return_value = {"status": "INVALID_REQUEST"}
            elif "sendgrid.com" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {"templates": []}

            return mock_response

        mock_get.side_effect = side_effect

        # Create tester and run test
        tester = ApiTester(env_file=self.env_file)
        result = tester.test_all_apis()

        # Check result
        self.assertFalse(result.success)
        self.assertTrue(len(result.issues) > 0)
        self.assertIn("Google Maps API", result.message)

        # Verify all APIs were called
        self.assertEqual(mock_get.call_count, 3)


def main():
    """Run all tests"""

    # Run tests
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


if __name__ == "__main__":
    main()
