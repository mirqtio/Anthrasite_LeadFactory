"""
Unit tests for the process_business_email function in the email_queue module.
"""

import os
import sys
import pytest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the function to test
from bin.email_queue import process_business_email


def test_process_business_email_dry_run():
    """Test that process_business_email returns True in dry run mode."""
    # Mock all dependencies
    with patch(
        "bin.email_queue.get_businesses_for_email"
    ) as mock_get_businesses, patch(
        "bin.email_queue.load_email_template"
    ) as mock_load_template, patch(
        "bin.email_queue.generate_email_content"
    ) as mock_generate_content, patch(
        "bin.email_queue.save_email_record"
    ) as mock_save_email, patch(
        "bin.email_queue.log_cost"
    ) as mock_log_cost, patch(
        "bin.email_queue.logger"
    ), patch(
        "bin.email_queue.os.getenv"
    ) as mock_getenv:
        # Configure mocks
        mock_get_businesses.return_value = [
            {
                "id": 1,
                "name": "Test Business",
                "email": "test@example.com",
                "mockup_generated": 1,
                "mockup_data": '{"improvements": [{"title": "Test Improvement"}]}',
            }
        ]
        mock_load_template.return_value = "<html>{{business_name}}</html>"
        mock_generate_content.return_value = (
            "Test Subject",
            "<html>Test Content</html>",
            "Test Content",
        )
        mock_save_email.return_value = True
        mock_getenv.return_value = "test_api_key"
        # Call the function with dry_run=True
        result = process_business_email(1, dry_run=True)
        # Assert the result is True
        assert result is True
        # Verify that log_cost was not called in dry run mode
        mock_log_cost.assert_not_called()


def test_process_business_email_normal_mode():
    """Test that process_business_email returns True in normal mode."""
    # Mock all dependencies
    with patch(
        "bin.email_queue.get_businesses_for_email"
    ) as mock_get_businesses, patch(
        "bin.email_queue.load_email_template"
    ) as mock_load_template, patch(
        "bin.email_queue.generate_email_content"
    ) as mock_generate_content, patch(
        "bin.email_queue.save_email_record"
    ) as mock_save_email, patch(
        "bin.email_queue.log_cost"
    ) as mock_log_cost, patch(
        "bin.email_queue.logger"
    ), patch(
        "bin.email_queue.os.getenv"
    ) as mock_getenv, patch(
        "bin.email_queue.send_business_email"
    ) as mock_send_email, patch(
        "bin.email_queue.SendGridEmailSender"
    ):
        # Configure mocks
        mock_get_businesses.return_value = [
            {
                "id": 1,
                "name": "Test Business",
                "email": "test@example.com",
                "mockup_generated": 1,
                "mockup_data": '{"improvements": [{"title": "Test Improvement"}]}',
            }
        ]
        mock_load_template.return_value = "<html>{{business_name}}</html>"
        mock_generate_content.return_value = (
            "Test Subject",
            "<html>Test Content</html>",
            "Test Content",
        )
        mock_save_email.return_value = True
        mock_getenv.return_value = "test_api_key"
        mock_send_email.return_value = True
        # Call the function with dry_run=False
        result = process_business_email(1, dry_run=False)
        # Assert the result is True
        assert result is True
        # Verify that log_cost was called in normal mode
        assert mock_log_cost.called


def test_process_business_email_handles_errors_in_dry_run():
    """Test that process_business_email handles errors gracefully in dry run mode."""
    # Mock all dependencies
    with patch(
        "bin.email_queue.get_businesses_for_email"
    ) as mock_get_businesses, patch(
        "bin.email_queue.load_email_template"
    ) as mock_load_template, patch(
        "bin.email_queue.generate_email_content"
    ) as mock_generate_content, patch(
        "bin.email_queue.save_email_record"
    ) as mock_save_email, patch(
        "bin.email_queue.log_cost"
    ) as mock_log_cost, patch(
        "bin.email_queue.logger"
    ), patch(
        "bin.email_queue.os.getenv"
    ) as mock_getenv:
        # Configure mocks to raise exceptions
        mock_get_businesses.side_effect = Exception("Database error")
        mock_load_template.side_effect = Exception("Template error")
        mock_generate_content.side_effect = Exception("Content generation error")
        mock_save_email.side_effect = Exception("Save record error")
        mock_getenv.return_value = None  # No API key
        # Call the function with dry_run=True
        result = process_business_email(1, dry_run=True)
        # Assert the result is True even with errors
        assert result is True
        # Verify that log_cost was not called in dry run mode
        mock_log_cost.assert_not_called()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
