"""
Simple tests for the email queue functionality.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the function to test
from bin.email_queue import process_business_email


def test_process_business_email_dry_run_mode():
    """Test that process_business_email works correctly in dry run mode."""
    # Mock all dependencies
    with patch('bin.email_queue.get_businesses_for_email') as mock_get_businesses, \
         patch('bin.email_queue.load_email_template') as mock_load_template, \
         patch('bin.email_queue.generate_email_content') as mock_generate_content, \
         patch('bin.email_queue.save_email_record') as mock_save_email, \
         patch('bin.email_queue.log_cost') as mock_log_cost, \
         patch('bin.email_queue.logger') as mock_logger, \
         patch('bin.email_queue.os.getenv') as mock_getenv, \
         patch('bin.email_queue.SendGridEmailSender') as mock_sender:
        
        # Configure mocks
        mock_get_businesses.return_value = [{
            'id': 1,
            'name': 'Test Business',
            'email': 'test@example.com',
            'mockup_generated': 1,
            'mockup_data': '{"improvements": [{"title": "Test Improvement"}]}'
        }]
        mock_load_template.return_value = "<html>{{business_name}}</html>"
        mock_generate_content.return_value = ("Test Subject", "<html>Test Content</html>", "Test Content")
        mock_save_email.return_value = True
        mock_getenv.return_value = "test_api_key"
        
        # Call the function with dry_run=True
        result = process_business_email(1, dry_run=True)
        
        # Assert the result is True
        assert result is True
        
        # Verify that log_cost was not called in dry run mode
        mock_log_cost.assert_not_called()
        
        # Verify that the email was not sent in dry run mode
        mock_sender.return_value.send_email.assert_not_called()



