"""Integration tests for email thumbnail embedding."""

import base64
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.email_queue import send_business_email
from leadfactory.storage.factory import get_storage
from leadfactory.utils.e2e_db_connector import db_connection


class TestEmailThumbnailIntegration:
    """Integration tests for email thumbnail functionality."""

    @pytest.fixture
    def setup_test_business(self):
        """Set up test business with assets."""
        with db_connection() as conn:
            cursor = conn.cursor()

            # Clean up any existing test data
            cursor.execute("DELETE FROM assets WHERE business_id = 9999")
            cursor.execute("DELETE FROM businesses WHERE id = 9999")

            # Insert test business
            cursor.execute("""
                INSERT INTO businesses (id, name, email, website, address, city, state, zip, vertical_id)
                VALUES (9999, 'Thumbnail Test Business', 'test@thumbnail.com',
                        'https://thumbnail-test.com', '123 Test St', 'Test City', 'TC', '99999',
                        (SELECT id FROM verticals LIMIT 1))
            """)

            # Create temp files for assets
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as screenshot:
                screenshot.write(b"TEST_SCREENSHOT_DATA")
                screenshot_path = screenshot.name

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
                mockup.write(b"TEST_MOCKUP_DATA")
                mockup_path = mockup.name

            # Insert asset records
            cursor.execute("""
                INSERT INTO assets (business_id, asset_type, file_path, url)
                VALUES
                (9999, 'screenshot', %s, 'https://example.com/screenshot.png'),
                (9999, 'mockup', %s, 'https://example.com/mockup.png')
            """, (screenshot_path, mockup_path))

            conn.commit()

            yield {
                "business_id": 9999,
                "screenshot_path": screenshot_path,
                "mockup_path": mockup_path
            }

            # Cleanup
            cursor.execute("DELETE FROM assets WHERE business_id = 9999")
            cursor.execute("DELETE FROM businesses WHERE id = 9999")
            conn.commit()

            # Clean up temp files
            for path in [screenshot_path, mockup_path]:
                if os.path.exists(path):
                    os.unlink(path)

    def test_email_with_thumbnail_from_database(self, setup_test_business):
        """Test sending email with thumbnail retrieved from database."""
        storage = get_storage()
        business = storage.get_business_by_id(setup_test_business["business_id"])

        assert business is not None

        # Mock email sender
        with patch("leadfactory.pipeline.email_queue.SendGridEmailSender") as mock_sender_class:
            mock_sender = Mock()
            mock_sender.send_email.return_value = "msg-123456"
            mock_sender_class.return_value = mock_sender

            # Send email
            result = send_business_email(business, is_dry_run=False)

            assert result is True

            # Verify attachments
            call_args = mock_sender.send_email.call_args[1]
            attachments = call_args.get("attachments", [])

            # Should have both thumbnail and mockup
            assert len(attachments) == 2

            # Verify thumbnail
            thumbnail = next((a for a in attachments if a["content_id"] == "website-thumbnail.png"), None)
            assert thumbnail is not None
            assert thumbnail["disposition"] == "inline"
            assert base64.b64decode(thumbnail["content"]) == b"TEST_SCREENSHOT_DATA"

            # Verify mockup
            mockup = next((a for a in attachments if a["content_id"] == "website-mockup.png"), None)
            assert mockup is not None
            assert base64.b64decode(mockup["content"]) == b"TEST_MOCKUP_DATA"

    def test_email_template_rendering_with_thumbnail(self):
        """Test that email template properly includes thumbnail reference."""
        from leadfactory.pipeline.email_queue import generate_email_content

        business = {
            "name": "Test Business",
            "website": "https://testbusiness.com",
            "category": "Restaurant",
            "email": "test@business.com"
        }

        # Load template
        template_path = os.path.join(
            os.path.dirname(__file__),
            "../../etc/email_template.html"
        )

        with open(template_path) as f:
            template_content = f.read()

        # Generate email content
        subject, html_content, text_content = generate_email_content(business, template_content)

        # Verify thumbnail reference in HTML
        assert "cid:website-thumbnail.png" in html_content
        assert "Current Website:" in html_content
        assert "cid:website-mockup.png" in html_content

    def test_full_email_flow_with_assets(self, setup_test_business):
        """Test complete email flow with both screenshot and mockup."""
        storage = get_storage()

        # Get business with assets
        business = storage.get_business_by_id(setup_test_business["business_id"])

        # Verify assets exist
        screenshot_asset = storage.get_business_asset(business["id"], "screenshot")
        mockup_asset = storage.get_business_asset(business["id"], "mockup")

        assert screenshot_asset is not None
        assert mockup_asset is not None
        assert os.path.exists(screenshot_asset["file_path"])
        assert os.path.exists(mockup_asset["file_path"])

        # Mock SendGrid
        with patch("leadfactory.pipeline.email_queue.SendGridEmailSender") as mock_sender_class:
            mock_sender = Mock()
            mock_sender.send_email.return_value = "msg-test-123"
            mock_sender_class.return_value = mock_sender

            # Send email
            result = send_business_email(business, is_dry_run=False)

            assert result is True

            # Verify email was sent with correct parameters
            mock_sender.send_email.assert_called_once()

            call_kwargs = mock_sender.send_email.call_args[1]
            assert call_kwargs["to_email"] == "test@thumbnail.com"
            assert call_kwargs["to_name"] == "Thumbnail Test Business"
            assert len(call_kwargs["attachments"]) == 2

    def test_email_without_screenshot_asset(self):
        """Test email sending when business has no screenshot asset."""
        with db_connection() as conn:
            cursor = conn.cursor()

            # Create business without screenshot
            cursor.execute("""
                INSERT INTO businesses (id, name, email, website, address, city, state, zip, vertical_id)
                VALUES (9998, 'No Screenshot Business', 'noshot@test.com',
                        'https://noshot.com', '456 Test Ave', 'Test Town', 'TT', '88888',
                        (SELECT id FROM verticals LIMIT 1))
            """)

            # Create only mockup asset
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
                mockup.write(b"MOCKUP_ONLY_DATA")
                mockup_path = mockup.name

            cursor.execute("""
                INSERT INTO assets (business_id, asset_type, file_path, url)
                VALUES (9998, 'mockup', %s, 'https://example.com/mockup.png')
            """, (mockup_path,))

            conn.commit()

            try:
                storage = get_storage()
                business = storage.get_business_by_id(9998)

                with patch("leadfactory.pipeline.email_queue.SendGridEmailSender") as mock_sender_class:
                    mock_sender = Mock()
                    mock_sender.send_email.return_value = "msg-no-thumb"
                    mock_sender_class.return_value = mock_sender

                    # Should still send successfully
                    result = send_business_email(business, is_dry_run=False)
                    assert result is True

                    # Verify only mockup attachment
                    call_args = mock_sender.send_email.call_args[1]
                    attachments = call_args.get("attachments", [])
                    assert len(attachments) == 1
                    assert attachments[0]["content_id"] == "website-mockup.png"

            finally:
                # Cleanup
                cursor.execute("DELETE FROM assets WHERE business_id = 9998")
                cursor.execute("DELETE FROM businesses WHERE id = 9998")
                conn.commit()

                if os.path.exists(mockup_path):
                    os.unlink(mockup_path)
