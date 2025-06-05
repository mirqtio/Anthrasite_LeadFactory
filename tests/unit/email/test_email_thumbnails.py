"""
Unit tests for email website thumbnail functionality.
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.email.service import EmailReportService, ReportDeliveryRequest
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine


class TestEmailThumbnails:
    """Test cases for email website thumbnail integration."""

    @pytest.fixture
    def email_service(self):
        """Create an EmailReportService instance for testing."""
        with patch("leadfactory.email.service.EmailDeliveryService"), \
             patch("leadfactory.email.service.SecureLinkGenerator"), \
             patch("leadfactory.email.service.EmailTemplateEngine") as mock_template_engine, \
             patch("leadfactory.email.service.EmailWorkflowEngine"), \
             patch("leadfactory.email.service.EmailABTest"):

            # Mock async generate_ai_content method
            async def mock_generate_ai_content(personalization):
                return personalization

            service = EmailReportService()
            service.template_engine.generate_ai_content = mock_generate_ai_content

            return service

    @pytest.fixture
    def sample_report_request(self):
        """Create a sample report delivery request."""
        return ReportDeliveryRequest(
            user_id="user123",
            user_email="test@example.com",
            user_name="Test User",
            report_id="report456",
            report_title="Website Audit Report",
            purchase_id="purchase789",
            company_name="Test Company",
            website_url="https://example.com",
            business_id=123
        )

    def test_email_personalization_with_thumbnail_fields(self):
        """Test EmailPersonalization includes thumbnail fields."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            website_url="https://example.com",
            website_thumbnail_path="/path/to/thumbnail.png",
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        assert personalization.website_url == "https://example.com"
        assert personalization.website_thumbnail_path == "/path/to/thumbnail.png"

    def test_template_engine_thumbnail_context(self):
        """Test template engine includes thumbnail availability context."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake png data")
            thumbnail_path = tmp_file.name

        try:
            personalization = EmailPersonalization(
                user_name="Test User",
                user_email="test@example.com",
                report_title="Test Report",
                report_link="https://example.com/report",
                agency_cta_link="https://example.com/cta",
                website_thumbnail_path=thumbnail_path,
                purchase_date=datetime.now(),
                expiry_date=datetime.now()
            )

            engine = EmailTemplateEngine()

            # Mock template loading to avoid file system dependencies
            with patch.object(engine.env, 'get_template') as mock_get_template:
                mock_template = Mock()
                mock_template.render.return_value = "<html>Test content</html>"
                mock_get_template.return_value = mock_template

                # Mock subject extraction and text template to avoid double call
                with patch.object(engine, '_extract_subject', return_value="Test Subject"), \
                     patch.object(engine, '_html_to_text', return_value="Test text"):
                    result = engine.render_template("test_template", personalization)

                # Verify template was called with thumbnail context (may be called twice for HTML and text)
                assert mock_template.render.call_count >= 1
                call_args = mock_template.render.call_args[1]

                assert "website_thumbnail_available" in call_args
                assert call_args["website_thumbnail_available"] is True
                assert call_args["user"] == personalization

        finally:
            if os.path.exists(thumbnail_path):
                os.unlink(thumbnail_path)

    def test_template_engine_no_thumbnail_context(self):
        """Test template engine handles missing thumbnail gracefully."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            website_thumbnail_path=None,
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        engine = EmailTemplateEngine()

        with patch.object(engine.env, 'get_template') as mock_get_template:
            mock_template = Mock()
            mock_template.render.return_value = "<html>Test content</html>"
            mock_get_template.return_value = mock_template

            with patch.object(engine, '_extract_subject', return_value="Test Subject"):
                result = engine.render_template("test_template", personalization)

            call_args = mock_template.render.call_args[1]
            assert "website_thumbnail_available" in call_args
            assert call_args["website_thumbnail_available"] is False

    def test_template_engine_nonexistent_thumbnail(self):
        """Test template engine handles nonexistent thumbnail file."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            website_thumbnail_path="/nonexistent/path.png",
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        engine = EmailTemplateEngine()

        with patch.object(engine.env, 'get_template') as mock_get_template:
            mock_template = Mock()
            mock_template.render.return_value = "<html>Test content</html>"
            mock_get_template.return_value = mock_template

            with patch.object(engine, '_extract_subject', return_value="Test Subject"):
                result = engine.render_template("test_template", personalization)

            call_args = mock_template.render.call_args[1]
            assert "website_thumbnail_available" in call_args
            assert call_args["website_thumbnail_available"] is False

    @pytest.mark.asyncio
    @patch("leadfactory.email.service.get_storage")
    @patch("leadfactory.email.service.generate_business_screenshot")
    async def test_deliver_report_with_existing_screenshot(
        self, mock_generate_screenshot, mock_get_storage, email_service, sample_report_request
    ):
        """Test report delivery with existing screenshot."""
        # Mock storage to return existing screenshot
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake png data")
            screenshot_path = tmp_file.name

        try:
            mock_storage.get_business_asset.return_value = {
                "file_path": screenshot_path
            }

            # Mock other dependencies
            email_service.link_generator.generate_secure_link.return_value = "https://example.com/report"
            email_service.link_generator.generate_download_link.return_value = "https://example.com/download"
            email_service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

            email_service.ab_test.generate_email_with_variant.return_value = (
                "variant1",
                {
                    "subject": "Test Subject",
                    "html_content": "<html>Test</html>",
                    "template_name": "report_delivery"
                }
            )

            # Mock async methods using AsyncMock
            from unittest.mock import AsyncMock
            email_service.delivery_service.send_email = AsyncMock(return_value="email123")
            email_service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

            result = await email_service.deliver_report(sample_report_request)

            assert result.success is True
            assert result.email_id == "email123"

            # Verify screenshot generation was not called since screenshot exists
            mock_generate_screenshot.assert_not_called()

            # Verify email service was called with correct personalization
            email_service.delivery_service.send_email.assert_called_once()
            call_args = email_service.delivery_service.send_email.call_args
            personalization = call_args[0][1]  # Second argument is personalization

            assert personalization.website_url == "https://example.com"
            assert personalization.website_thumbnail_path == screenshot_path

        finally:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)

    @pytest.mark.asyncio
    @patch("leadfactory.email.service.get_storage")
    @patch("leadfactory.email.service.generate_business_screenshot")
    async def test_deliver_report_generate_new_screenshot(
        self, mock_generate_screenshot, mock_get_storage, email_service, sample_report_request
    ):
        """Test report delivery generates new screenshot when none exists."""
        # Mock storage to return no existing screenshot initially
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake png data")
            screenshot_path = tmp_file.name

        try:
            # First call returns None, second call returns new screenshot
            mock_storage.get_business_asset.side_effect = [
                None,  # No existing screenshot
                {"file_path": screenshot_path}  # Screenshot after generation
            ]

            mock_generate_screenshot.return_value = True

            # Mock other dependencies
            email_service.link_generator.generate_secure_link.return_value = "https://example.com/report"
            email_service.link_generator.generate_download_link.return_value = "https://example.com/download"
            email_service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

            email_service.ab_test.generate_email_with_variant.return_value = (
                "variant1",
                {
                    "subject": "Test Subject",
                    "html_content": "<html>Test</html>",
                    "template_name": "report_delivery"
                }
            )

            # Mock async methods using AsyncMock
            from unittest.mock import AsyncMock
            email_service.delivery_service.send_email = AsyncMock(return_value="email123")
            email_service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

            result = await email_service.deliver_report(sample_report_request)

            assert result.success is True

            # Verify screenshot generation was called
            mock_generate_screenshot.assert_called_once()
            call_args = mock_generate_screenshot.call_args[0][0]
            assert call_args["id"] == 123
            assert call_args["name"] == "Test Company"
            assert call_args["website"] == "https://example.com"

        finally:
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)

    @pytest.mark.asyncio
    @patch("leadfactory.email.service.get_storage")
    @patch("leadfactory.email.service.generate_business_screenshot")
    async def test_deliver_report_screenshot_generation_fails(
        self, mock_generate_screenshot, mock_get_storage, email_service, sample_report_request
    ):
        """Test report delivery handles screenshot generation failure gracefully."""
        # Mock storage to return no existing screenshot
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_business_asset.return_value = None

        # Mock screenshot generation failure
        mock_generate_screenshot.return_value = False

        # Mock other dependencies
        email_service.link_generator.generate_secure_link.return_value = "https://example.com/report"
        email_service.link_generator.generate_download_link.return_value = "https://example.com/download"
        email_service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

        email_service.ab_test.generate_email_with_variant.return_value = (
            "variant1",
            {
                "subject": "Test Subject",
                "html_content": "<html>Test</html>",
                "template_name": "report_delivery"
            }
        )

        # Mock async methods using Mock with side_effect
        async def mock_send_email(*args, **kwargs):
            return "email123"

        async def mock_start_workflow(*args, **kwargs):
            return "workflow456"

        email_service.delivery_service.send_email = Mock(side_effect=mock_send_email)
        email_service.workflow_engine.start_workflow = Mock(side_effect=mock_start_workflow)

        result = await email_service.deliver_report(sample_report_request)

        # Email should still be sent successfully even if screenshot fails
        assert result.success is True

        # Verify email service was called with no thumbnail path
        email_service.delivery_service.send_email.assert_called_once()
        call_args = email_service.delivery_service.send_email.call_args
        personalization = call_args[0][1]

        assert personalization.website_url == "https://example.com"
        assert personalization.website_thumbnail_path is None

    @pytest.mark.asyncio
    async def test_deliver_report_no_business_info(self, email_service):
        """Test report delivery without business information."""
        request = ReportDeliveryRequest(
            user_id="user123",
            user_email="test@example.com",
            user_name="Test User",
            report_id="report456",
            report_title="Website Audit Report",
            purchase_id="purchase789"
            # No business_id or website_url
        )

        # Mock dependencies
        email_service.link_generator.generate_secure_link.return_value = "https://example.com/report"
        email_service.link_generator.generate_download_link.return_value = "https://example.com/download"
        email_service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

        email_service.ab_test.generate_email_with_variant.return_value = (
            "variant1",
            {
                "subject": "Test Subject",
                "html_content": "<html>Test</html>",
                "template_name": "report_delivery"
            }
        )

        # Mock async methods using Mock with side_effect
        async def mock_send_email(*args, **kwargs):
            return "email123"

        async def mock_start_workflow(*args, **kwargs):
            return "workflow456"

        email_service.delivery_service.send_email = Mock(side_effect=mock_send_email)
        email_service.workflow_engine.start_workflow = Mock(side_effect=mock_start_workflow)

        result = await email_service.deliver_report(request)

        assert result.success is True

        # Verify email service was called with no website info
        email_service.delivery_service.send_email.assert_called_once()
        call_args = email_service.delivery_service.send_email.call_args
        personalization = call_args[0][1]

        assert personalization.website_url is None
        assert personalization.website_thumbnail_path is None

    @pytest.mark.asyncio
    @patch("leadfactory.email.service.get_storage")
    async def test_deliver_report_storage_error(
        self, mock_get_storage, email_service, sample_report_request
    ):
        """Test report delivery handles storage errors gracefully."""
        # Mock storage to raise an exception
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.get_business_asset.side_effect = Exception("Storage error")

        # Mock other dependencies
        email_service.link_generator.generate_secure_link.return_value = "https://example.com/report"
        email_service.link_generator.generate_download_link.return_value = "https://example.com/download"
        email_service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

        email_service.ab_test.generate_email_with_variant.return_value = (
            "variant1",
            {
                "subject": "Test Subject",
                "html_content": "<html>Test</html>",
                "template_name": "report_delivery"
            }
        )

        # Mock async methods using Mock with side_effect
        async def mock_send_email(*args, **kwargs):
            return "email123"

        async def mock_start_workflow(*args, **kwargs):
            return "workflow456"

        email_service.delivery_service.send_email = Mock(side_effect=mock_send_email)
        email_service.workflow_engine.start_workflow = Mock(side_effect=mock_start_workflow)

        result = await email_service.deliver_report(sample_report_request)

        # Email should still be sent successfully despite storage error
        assert result.success is True

        # Verify email service was called with no thumbnail path
        email_service.delivery_service.send_email.assert_called_once()
        call_args = email_service.delivery_service.send_email.call_args
        personalization = call_args[0][1]

        assert personalization.website_url == "https://example.com"
        assert personalization.website_thumbnail_path is None


class TestEmailDeliveryThumbnails:
    """Test cases for email delivery service thumbnail handling."""

    @pytest.fixture
    def delivery_service(self):
        """Create an EmailDeliveryService instance for testing."""
        with patch("leadfactory.email.delivery.sendgrid.SendGridAPIClient"):
            from leadfactory.email.delivery import EmailDeliveryService
            return EmailDeliveryService(api_key="test_key")

    def test_prepare_sendgrid_email_with_thumbnail(self, delivery_service):
        """Test SendGrid email preparation includes thumbnail attachment."""
        from leadfactory.email.templates import EmailTemplate, EmailPersonalization

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake png data")
            thumbnail_path = tmp_file.name

        try:
            template = EmailTemplate(
                name="test_template",
                subject="Test Subject",
                html_content="<html><img src='cid:website-thumbnail.png'></html>"
            )

            personalization = EmailPersonalization(
                user_name="Test User",
                user_email="test@example.com",
                report_title="Test Report",
                report_link="https://example.com/report",
                agency_cta_link="https://example.com/cta",
                website_thumbnail_path=thumbnail_path,
                purchase_date=datetime.now(),
                expiry_date=datetime.now()
            )

            # Mock the SendGrid Mail creation to avoid Email type issues
            with patch('leadfactory.email.delivery.Mail') as mock_mail_class, \
                 patch('leadfactory.email.delivery.Email') as mock_email_class, \
                 patch('leadfactory.email.delivery.Content') as mock_content_class:

                mock_mail = Mock()
                mock_mail.attachments = []
                mock_mail_class.return_value = mock_mail

                mail = delivery_service._prepare_sendgrid_email(template, personalization, "email123")

                # Verify attachment was added
                assert mock_mail.add_attachment.called
                call_args = mock_mail.add_attachment.call_args[0][0]
                assert call_args.filename == "website-thumbnail.png"
                assert call_args.type == "image/png"
                # Check that disposition and content_id are set (they are objects not strings)
                assert hasattr(call_args, 'disposition')
                assert hasattr(call_args, 'content_id')
                # Verify the attachment has content
                assert hasattr(call_args, 'content')
                assert call_args.content is not None

        finally:
            if os.path.exists(thumbnail_path):
                os.unlink(thumbnail_path)

    def test_prepare_sendgrid_email_no_thumbnail(self, delivery_service):
        """Test SendGrid email preparation without thumbnail."""
        from leadfactory.email.templates import EmailTemplate, EmailPersonalization

        template = EmailTemplate(
            name="test_template",
            subject="Test Subject",
            html_content="<html>Test content</html>"
        )

        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            website_thumbnail_path=None,
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        with patch('leadfactory.email.delivery.Mail') as mock_mail_class, \
             patch('leadfactory.email.delivery.Email') as mock_email_class, \
             patch('leadfactory.email.delivery.Content') as mock_content_class:

            mock_mail = Mock()
            mock_mail.attachments = []
            mock_mail_class.return_value = mock_mail

            mail = delivery_service._prepare_sendgrid_email(template, personalization, "email123")

            # Verify no attachment was added
            assert not mock_mail.add_attachment.called

    def test_prepare_sendgrid_email_missing_thumbnail_file(self, delivery_service):
        """Test SendGrid email preparation with missing thumbnail file."""
        from leadfactory.email.templates import EmailTemplate, EmailPersonalization

        template = EmailTemplate(
            name="test_template",
            subject="Test Subject",
            html_content="<html><img src='cid:website-thumbnail.png'></html>"
        )

        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            website_thumbnail_path="/nonexistent/path.png",
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        with patch('leadfactory.email.delivery.Mail') as mock_mail_class, \
             patch('leadfactory.email.delivery.Email') as mock_email_class, \
             patch('leadfactory.email.delivery.Content') as mock_content_class:

            mock_mail = Mock()
            mock_mail.attachments = []
            mock_mail_class.return_value = mock_mail

            # Should not raise an exception, should handle gracefully
            mail = delivery_service._prepare_sendgrid_email(template, personalization, "email123")

            # Verify no attachment was added due to missing file
            assert not mock_mail.add_attachment.called
