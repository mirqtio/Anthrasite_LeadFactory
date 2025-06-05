"""Unit tests for email thumbnail embedding functionality."""

import base64
import os
import tempfile
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.pipeline.email_queue import generate_email_content, send_business_email


class TestEmailThumbnail:
    """Test email thumbnail embedding functionality."""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for asset retrieval."""
        storage = Mock()
        # Mock screenshot asset
        storage.get_business_asset.side_effect = lambda business_id, asset_type: {
            "screenshot": {"file_path": "/tmp/screenshot.png"},
            "mockup": {"file_path": "/tmp/mockup.png"}
        }.get(asset_type)
        return storage

    @pytest.fixture
    def test_business(self):
        """Test business data."""
        return {
            "id": 123,
            "name": "Test Business",
            "email": "test@business.com",
            "website": "https://testbusiness.com",
            "category": "Restaurant"
        }

    @pytest.fixture
    def mock_email_sender(self):
        """Mock email sender."""
        sender = Mock()
        sender.send_email.return_value = "msg-123456"
        return sender

    def test_thumbnail_attachment_created(self, test_business, mock_storage, mock_email_sender):
        """Test that thumbnail is added as inline attachment."""
        # Create temporary files for screenshot and mockup
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as screenshot:
            screenshot.write(b"SCREENSHOT_PNG_DATA")
            screenshot_path = screenshot.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
            mockup.write(b"MOCKUP_PNG_DATA")
            mockup_path = mockup.name

        try:
            # Update mock to return actual file paths
            mock_storage.get_business_asset.side_effect = lambda business_id, asset_type: {
                "screenshot": {"file_path": screenshot_path},
                "mockup": {"file_path": mockup_path}
            }.get(asset_type)

            with patch("leadfactory.pipeline.email_queue.get_storage", return_value=mock_storage):
                with patch("leadfactory.pipeline.email_queue.generate_email_content") as mock_generate:
                    mock_generate.return_value = ("Subject", "<html>content</html>", "text content")

                    with patch("leadfactory.pipeline.email_queue.SendGridEmailSender", return_value=mock_email_sender):
                        # Send email
                        result = send_business_email(test_business, is_dry_run=False)

                        assert result is True

                        # Verify send_email was called with attachments
                        mock_email_sender.send_email.assert_called_once()
                        call_args = mock_email_sender.send_email.call_args[1]

                        # Check attachments
                        attachments = call_args.get("attachments", [])
                        assert len(attachments) == 2

                        # Find screenshot attachment
                        screenshot_attachment = next(
                            (a for a in attachments if a["content_id"] == "website-thumbnail.png"),
                            None
                        )
                        assert screenshot_attachment is not None
                        assert screenshot_attachment["filename"] == "website-thumbnail.png"
                        assert screenshot_attachment["type"] == "image/png"
                        assert screenshot_attachment["disposition"] == "inline"

                        # Verify content is base64 encoded
                        decoded = base64.b64decode(screenshot_attachment["content"])
                        assert decoded == b"SCREENSHOT_PNG_DATA"

        finally:
            # Clean up temp files
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
            if os.path.exists(mockup_path):
                os.unlink(mockup_path)

    def test_email_sends_without_thumbnail(self, test_business, mock_storage, mock_email_sender):
        """Test that email still sends if thumbnail is not available."""
        # Create only mockup file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
            mockup.write(b"MOCKUP_PNG_DATA")
            mockup_path = mockup.name

        try:
            # Mock storage to return no screenshot
            mock_storage.get_business_asset.side_effect = lambda business_id, asset_type: {
                "screenshot": None,
                "mockup": {"file_path": mockup_path}
            }.get(asset_type)

            with patch("leadfactory.pipeline.email_queue.get_storage", return_value=mock_storage):
                with patch("leadfactory.pipeline.email_queue.generate_email_content") as mock_generate:
                    mock_generate.return_value = ("Subject", "<html>content</html>", "text content")

                    with patch("leadfactory.pipeline.email_queue.SendGridEmailSender", return_value=mock_email_sender):
                        # Send email
                        result = send_business_email(test_business, is_dry_run=False)

                        assert result is True

                        # Verify only mockup attachment
                        call_args = mock_email_sender.send_email.call_args[1]
                        attachments = call_args.get("attachments", [])
                        assert len(attachments) == 1
                        assert attachments[0]["content_id"] == "website-mockup.png"

        finally:
            if os.path.exists(mockup_path):
                os.unlink(mockup_path)

    def test_thumbnail_file_not_exists(self, test_business, mock_storage, mock_email_sender):
        """Test handling when thumbnail file doesn't exist on disk."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
            mockup.write(b"MOCKUP_PNG_DATA")
            mockup_path = mockup.name

        try:
            # Mock storage to return non-existent screenshot path
            mock_storage.get_business_asset.side_effect = lambda business_id, asset_type: {
                "screenshot": {"file_path": "/tmp/non_existent_screenshot.png"},
                "mockup": {"file_path": mockup_path}
            }.get(asset_type)

            with patch("leadfactory.pipeline.email_queue.get_storage", return_value=mock_storage):
                with patch("leadfactory.pipeline.email_queue.generate_email_content") as mock_generate:
                    mock_generate.return_value = ("Subject", "<html>content</html>", "text content")

                    with patch("leadfactory.pipeline.email_queue.SendGridEmailSender", return_value=mock_email_sender):
                        # Send email - should succeed without thumbnail
                        result = send_business_email(test_business, is_dry_run=False)

                        assert result is True

                        # Verify only mockup attachment
                        call_args = mock_email_sender.send_email.call_args[1]
                        attachments = call_args.get("attachments", [])
                        assert len(attachments) == 1

        finally:
            if os.path.exists(mockup_path):
                os.unlink(mockup_path)

    def test_both_attachments_order(self, test_business, mock_storage, mock_email_sender):
        """Test that both attachments are added in correct order."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as screenshot:
            screenshot.write(b"SCREENSHOT_DATA")
            screenshot_path = screenshot.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as mockup:
            mockup.write(b"MOCKUP_DATA")
            mockup_path = mockup.name

        try:
            mock_storage.get_business_asset.side_effect = lambda business_id, asset_type: {
                "screenshot": {"file_path": screenshot_path},
                "mockup": {"file_path": mockup_path}
            }.get(asset_type)

            with patch("leadfactory.pipeline.email_queue.get_storage", return_value=mock_storage):
                with patch("leadfactory.pipeline.email_queue.generate_email_content") as mock_generate:
                    mock_generate.return_value = ("Subject", "<html>content</html>", "text content")

                    with patch("leadfactory.pipeline.email_queue.SendGridEmailSender", return_value=mock_email_sender):
                        result = send_business_email(test_business, is_dry_run=False)

                        assert result is True

                        call_args = mock_email_sender.send_email.call_args[1]
                        attachments = call_args.get("attachments", [])

                        # Verify order: screenshot first, then mockup
                        assert len(attachments) == 2
                        assert attachments[0]["content_id"] == "website-thumbnail.png"
                        assert attachments[1]["content_id"] == "website-mockup.png"

        finally:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
            if os.path.exists(mockup_path):
                os.unlink(mockup_path)
