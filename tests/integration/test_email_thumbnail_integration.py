"""
Integration tests for email thumbnail functionality.
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from leadfactory.email.service import EmailReportService, ReportDeliveryRequest
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.pipeline.screenshot_local import capture_screenshot_sync, is_playwright_available


class TestEmailThumbnailIntegration:
    """Integration test cases for email thumbnail functionality."""

    def test_email_template_rendering_with_thumbnail(self):
        """Test that email templates render correctly with thumbnail."""
        # Create a test thumbnail file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake png data")
            thumbnail_path = tmp_file.name

        try:
            personalization = EmailPersonalization(
                user_name="Test User",
                user_email="test@example.com",
                report_title="Website Audit Report",
                report_link="https://example.com/report",
                agency_cta_link="https://example.com/cta",
                company_name="Test Company",
                website_url="https://example.com",
                website_thumbnail_path=thumbnail_path,
                purchase_date=datetime.now(),
                expiry_date=datetime.now()
            )

            engine = EmailTemplateEngine()

            # Test report delivery template
            template = engine.create_report_delivery_email(personalization)

            assert template.name == "report_delivery"
            assert "Test User" in template.html_content
            assert "Website Audit Report" in template.html_content

            # Check if the thumbnail context is properly set
            # The actual CID reference should be in the template
            assert "cid:website-thumbnail.png" in template.html_content

        finally:
            if os.path.exists(thumbnail_path):
                os.unlink(thumbnail_path)

    def test_email_template_rendering_without_thumbnail(self):
        """Test that email templates render correctly without thumbnail."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Website Audit Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            company_name="Test Company",
            website_url="https://example.com",
            website_thumbnail_path=None,
            purchase_date=datetime.now(),
            expiry_date=datetime.now()
        )

        engine = EmailTemplateEngine()

        # Test report delivery template
        template = engine.create_report_delivery_email(personalization)

        assert template.name == "report_delivery"
        assert "Test User" in template.html_content
        assert "Website Audit Report" in template.html_content
