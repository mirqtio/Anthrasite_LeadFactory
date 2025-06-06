"""Unit tests for ScreenshotOne retry logic enhancements."""

import time
import unittest
from unittest.mock import Mock, patch

import requests

from leadfactory.pipeline.screenshot import _capture_with_screenshotone_retry


class TestScreenshotOneRetry(unittest.TestCase):
    """Test ScreenshotOne retry logic with exponential backoff."""

    def setUp(self):
        """Set up test environment."""
        self.api_url = "https://api.screenshotone.com/take"
        self.params = {
            "access_key": "test_key",
            "url": "https://example.com",
            "device_scale_factor": 1,
            "format": "png",
            "viewport_width": 1280,
            "viewport_height": 800,
            "full_page": False,
            "timeout": 30,
        }
        self.screenshot_path = "/tmp/test_screenshot.png"
        self.website = "https://example.com"

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    @patch("builtins.open", create=True)
    def test_successful_capture_first_attempt(self, mock_open, mock_cost_cap, mock_get, mock_sleep):
        """Test successful screenshot capture on first attempt."""
        # Mock successful response
        mock_response = Mock()
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'x' * 2000  # Valid PNG content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__ = Mock(return_value=mock_file)
        mock_open.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website
        )

        self.assertTrue(result)
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()  # No retries needed
        mock_file.write.assert_called_once_with(mock_response.content)

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    @patch("builtins.open", create=True)
    def test_successful_capture_after_retries(self, mock_open, mock_cost_cap, mock_get, mock_sleep):
        """Test successful screenshot capture after timeout retries."""
        # Mock timeout on first two attempts, success on third
        mock_response = Mock()
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'x' * 2000  # Valid PNG content
        mock_response.raise_for_status = Mock()

        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.Timeout("Timeout 2"),
            mock_response
        ]

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__ = Mock(return_value=mock_file)
        mock_open.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website
        )

        self.assertTrue(result)
        self.assertEqual(mock_get.call_count, 3)
        # Check exponential backoff: sleep(1), sleep(2)
        expected_sleep_calls = [unittest.mock.call(1), unittest.mock.call(2)]
        mock_sleep.assert_has_calls(expected_sleep_calls)
        mock_file.write.assert_called_once_with(mock_response.content)

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    def test_failure_after_max_retries(self, mock_cost_cap, mock_get, mock_sleep):
        """Test failure after maximum retry attempts."""
        # Mock all attempts failing with timeout
        mock_get.side_effect = requests.exceptions.Timeout("Persistent timeout")

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website, max_retries=3
        )

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 3)
        # Should have 2 sleep calls for retries: sleep(1), sleep(2)
        expected_sleep_calls = [unittest.mock.call(1), unittest.mock.call(2)]
        mock_sleep.assert_has_calls(expected_sleep_calls)

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    def test_client_error_no_retry(self, mock_cost_cap, mock_get, mock_sleep):
        """Test that client errors (4xx) don't trigger retries."""
        # Mock 4xx client error
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError("Not Found")
        http_error.response = mock_response
        mock_get.side_effect = http_error

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website
        )

        self.assertFalse(result)
        mock_get.assert_called_once()  # Only one attempt, no retries
        mock_sleep.assert_not_called()

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    def test_server_error_with_retry(self, mock_cost_cap, mock_get, mock_sleep):
        """Test that server errors (5xx) trigger retries."""
        # Mock 5xx server error on all attempts
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError("Internal Server Error")
        http_error.response = mock_response
        mock_get.side_effect = http_error

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website, max_retries=2
        )

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 2)  # Should retry once
        mock_sleep.assert_called_once_with(1)  # One retry delay

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    def test_invalid_response_validation(self, mock_cost_cap, mock_get, mock_sleep):
        """Test response validation with invalid content."""
        # Mock response with invalid content
        mock_response = Mock()
        mock_response.content = b'not a valid png'  # Invalid PNG content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website, max_retries=2
        )

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 2)  # Should retry once due to validation error
        mock_sleep.assert_called_once_with(1)

    @patch("leadfactory.pipeline.screenshot.time.sleep")
    @patch("requests.get")
    @patch("leadfactory.cost.service_cost_decorators.enforce_service_cost_cap")
    def test_small_response_validation(self, mock_cost_cap, mock_get, mock_sleep):
        """Test response validation with too small content."""
        # Mock response with content too small to be valid
        mock_response = Mock()
        mock_response.content = b'\x89PNG\r\n\x1a\n' + b'x' * 500  # Too small
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock cost cap context manager
        mock_cost_cap.return_value.__enter__ = Mock()
        mock_cost_cap.return_value.__exit__ = Mock()

        result = _capture_with_screenshotone_retry(
            self.api_url, self.params, self.screenshot_path, self.website, max_retries=2
        )

        self.assertFalse(result)
        self.assertEqual(mock_get.call_count, 2)  # Should retry once due to size validation
        mock_sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
