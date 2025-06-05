"""
Unit tests for the email queue pipeline module.

Tests the email generation and sending logic without external dependencies.
"""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, call, mock_open, patch

import pytest

from leadfactory.pipeline.email_queue import (
    SendGridEmailSender,
    add_unsubscribe,
    apply_template_replacements,
    generate_email_content,
    generate_standard_email_content,
    get_businesses_for_email,
    is_email_unsubscribed,
    is_valid_email,
    load_email_template,
    log_email_sent,
    process_business_email,
    save_email_record,
    send_business_email,
)


class TestEmailValidation:
    """Test email validation functions."""

    def test_is_valid_email_valid(self):
        """Test valid email addresses."""
        assert is_valid_email("test@example.com") is True
        assert is_valid_email("john.doe@company.co.uk") is True
        assert is_valid_email("user+tag@domain.com") is True
        assert is_valid_email("123@example.com") is True

    def test_is_valid_email_invalid(self):
        """Test invalid email addresses."""
        assert is_valid_email("") is False
        assert is_valid_email("notanemail") is False
        assert is_valid_email("@example.com") is False
        assert is_valid_email("test@") is False
        assert is_valid_email("test @example.com") is False
        assert is_valid_email("test@example") is False


class TestSendGridEmailSender:
    """Test SendGrid email sender."""

    @pytest.fixture
    def sender(self):
        """Create a SendGrid email sender instance."""
        return SendGridEmailSender(
            api_key="test-api-key",
            from_email="test@example.com",
            from_name="Test Sender",
            ip_pool="primary",
            subuser="test-user"
        )

    @patch('leadfactory.pipeline.email_queue.requests.post')
    def test_send_email_success(self, mock_post, sender):
        """Test successful email sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "test-message-id"}
        mock_post.return_value = mock_response

        # Send email
        message_id = sender.send_email(
            to_email="recipient@example.com",
            to_name="Test Recipient",
            subject="Test Subject",
            html_content="<p>Test content</p>"
        )

        assert message_id == "test-message-id"
        mock_post.assert_called_once()

        # Verify payload
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["personalizations"][0]["to"][0]["email"] == "recipient@example.com"
        assert payload["personalizations"][0]["subject"] == "Test Subject"
        assert payload["from"]["email"] == "test@example.com"

    @patch('leadfactory.pipeline.email_queue.requests.post')
    def test_send_email_failure(self, mock_post, sender):
        """Test failed email sending."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        # Send email
        message_id = sender.send_email(
            to_email="recipient@example.com",
            to_name="Test Recipient",
            subject="Test Subject",
            html_content="<p>Test content</p>"
        )

        assert message_id is None

    def test_send_email_dry_run(self, sender):
        """Test email sending in dry run mode."""
        message_id = sender.send_email(
            to_email="recipient@example.com",
            to_name="Test Recipient",
            subject="Test Subject",
            html_content="<p>Test content</p>",
            is_dry_run=True
        )

        assert message_id.startswith("dry-run-")

    def test_send_email_no_api_key(self):
        """Test email sending without API key."""
        sender = SendGridEmailSender(
            api_key=None,
            from_email="test@example.com",
            from_name="Test Sender"
        )

        message_id = sender.send_email(
            to_email="recipient@example.com",
            to_name="Test Recipient",
            subject="Test Subject",
            html_content="<p>Test content</p>"
        )

        assert message_id is None

    @patch('leadfactory.pipeline.email_queue.requests.get')
    def test_get_bounce_rate(self, mock_get, sender):
        """Test getting bounce rate."""
        # Mock response with bounce data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "stats": [{
                    "metrics": {
                        "requests": 100,
                        "bounces": 2
                    }
                }]
            }
        ]
        mock_get.return_value = mock_response

        bounce_rate = sender.get_bounce_rate(days=7)
        assert bounce_rate == 0.02  # 2%

    @patch('leadfactory.pipeline.email_queue.requests.get')
    def test_get_spam_rate(self, mock_get, sender):
        """Test getting spam complaint rate."""
        # Mock response with spam data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "stats": [{
                    "metrics": {
                        "requests": 1000,
                        "spam_reports": 1
                    }
                }]
            }
        ]
        mock_get.return_value = mock_response

        spam_rate = sender.get_spam_rate(days=7)
        assert spam_rate == 0.001  # 0.1%

    @patch('leadfactory.pipeline.email_queue.requests.get')
    def test_get_daily_sent_count(self, mock_get, sender):
        """Test getting daily sent count."""
        # Mock response with daily count
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "stats": [{
                    "metrics": {
                        "requests": 50
                    }
                }]
            }
        ]
        mock_get.return_value = mock_response

        count = sender.get_daily_sent_count()
        assert count == 50


class TestEmailTemplateProcessing:
    """Test email template processing functions."""

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_load_email_template_success(self, mock_storage):
        """Test loading email template successfully."""
        mock_storage.read_text.return_value = "<html>{{business_name}}</html>"

        template = load_email_template()
        assert "{{business_name}}" in template
        mock_storage.read_text.assert_called_once()

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_load_email_template_failure(self, mock_storage):
        """Test loading email template with fallback."""
        mock_storage.read_text.side_effect = Exception("File not found")

        template = load_email_template()
        assert "Anthrasite Web Services" in template  # Fallback template

    def test_apply_template_replacements(self):
        """Test applying template replacements."""
        template = "Hello {{contact_name}} from {{business_name}}!"
        business = {
            "name": "Test Business",
            "contact_name": "John Doe",
            "email": "john@example.com"
        }

        result = apply_template_replacements(template, business)
        assert "Hello John Doe from Test Business!" == result
        assert "{{" not in result  # No placeholders left

    def test_apply_template_replacements_with_html_escaping(self):
        """Test template replacements with HTML escaping."""
        template = "Business: {{business_name}}"
        business = {"name": "Joe's <Pizza> & Pasta"}

        result = apply_template_replacements(template, business)
        assert "Joe&#x27;s &lt;Pizza&gt; &amp; Pasta" in result

    def test_generate_standard_email_content(self):
        """Test standard email content generation."""
        template = "<html>{{business_name}} {{contact_name}}</html>"
        business = {
            "id": 1,
            "name": "Test Business",
            "contact_name": "John Doe",
            "website": "example.com",
            "email": "john@example.com"
        }

        subject, html, text = generate_standard_email_content(business, template)

        assert subject == "Free Website Mockup for Test Business"
        assert "Test Business" in html
        assert "John Doe" in html
        assert "Test Business" in text
        assert "John Doe" in text

    @pytest.mark.asyncio
    async def test_generate_email_content_with_ai_enabled(self):
        """Test email content generation with AI enabled."""
        template = "<html>{{business_name}}</html>"
        business = {"id": 1, "name": "Test Business"}

        with patch.dict(os.environ, {"USE_AI_EMAIL_CONTENT": "true"}):
            with patch('leadfactory.email.ai_content_generator.email_content_personalizer') as mock_ai:
                # Mock AI response (including business name placeholder)
                mock_ai.personalize_email_content = AsyncMock(
                    return_value=("AI Subject", "<p>AI Content for {{business_name}}</p>", "AI Text")
                )

                subject, html, text = await generate_email_content(business, template)

                assert subject == "AI Subject"
                assert "Test Business" in html  # Template replacements still applied
                assert text == "AI Text"

    @pytest.mark.asyncio
    async def test_generate_email_content_ai_fallback(self):
        """Test email content generation when AI fails."""
        template = "<html>{{business_name}}</html>"
        business = {"id": 1, "name": "Test Business"}

        with patch.dict(os.environ, {"USE_AI_EMAIL_CONTENT": "true"}):
            with patch('leadfactory.email.ai_content_generator.email_content_personalizer') as mock_ai:
                # Mock AI failure
                mock_ai.personalize_email_content = AsyncMock(
                    side_effect=Exception("AI service unavailable")
                )

                subject, html, text = await generate_email_content(business, template)

                # Should fall back to standard generation
                assert "Free Website Mockup" in subject
                assert "Test Business" in html


class TestBusinessEmailProcessing:
    """Test business email processing functions."""

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_get_businesses_for_email(self, mock_storage):
        """Test getting businesses for email."""
        # Mock storage response
        mock_storage.get_businesses_for_email.return_value = [
            {"id": 1, "name": "Business 1", "score": 80},
            {"id": 2, "name": "Business 2", "score": 40},  # Below threshold
            {"id": 3, "name": "Business 3", "score": 70}
        ]

        with patch('leadfactory.pipeline.score.meets_audit_threshold') as mock_threshold:
            mock_threshold.side_effect = lambda score: score >= 60

            businesses = get_businesses_for_email(limit=10)

            assert len(businesses) == 2  # Only businesses above threshold
            assert businesses[0]["id"] == 1
            assert businesses[1]["id"] == 3

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_is_email_unsubscribed_true(self, mock_storage):
        """Test checking unsubscribed email."""
        mock_storage.is_email_unsubscribed.return_value = True

        assert is_email_unsubscribed("test@example.com") is True

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_is_email_unsubscribed_table_missing(self, mock_storage):
        """Test unsubscribe check when table doesn't exist."""
        mock_storage.is_email_unsubscribed.side_effect = Exception("Table 'unsubscribes' does not exist")

        assert is_email_unsubscribed("test@example.com") is False

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_add_unsubscribe(self, mock_storage):
        """Test adding unsubscribe."""
        mock_storage.add_unsubscribe.return_value = True

        result = add_unsubscribe(
            "test@example.com",
            reason="User request",
            ip_address="127.0.0.1"
        )

        assert result is True
        mock_storage.add_unsubscribe.assert_called_once()

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_log_email_sent(self, mock_storage):
        """Test logging sent email."""
        mock_storage.log_email_sent.return_value = True

        result = log_email_sent(
            business_id=1,
            recipient_email="test@example.com",
            recipient_name="Test User",
            subject="Test Subject",
            message_id="msg-123",
            status="sent"
        )

        assert result is True

    @patch('leadfactory.pipeline.email_queue.storage')
    def test_save_email_record(self, mock_storage):
        """Test saving email record."""
        mock_storage.save_email_record.return_value = True

        result = save_email_record(
            business_id=1,
            to_email="test@example.com",
            to_name="Test User",
            subject="Test Subject",
            message_id="msg-123",
            status="sent"
        )

        assert result is True


class TestSendBusinessEmail:
    """Test send_business_email function."""

    @pytest.fixture
    def mock_sender(self):
        """Create a mock email sender."""
        sender = MagicMock()
        sender.send_email.return_value = "test-message-id"
        return sender

    @pytest.fixture
    def business(self):
        """Create test business data."""
        return {
            "id": 1,
            "name": "Test Business",
            "email": "business@example.com"
        }

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.storage')
    async def test_send_business_email_success(self, mock_storage, mock_sender, business):
        """Test successful business email sending."""
        # Mock storage methods
        mock_storage.get_business_asset.side_effect = lambda bid, atype: {
            "file_path": f"/tmp/{atype}.png"
        }
        mock_storage.save_email_record.return_value = True

        # Mock unsubscribe check
        with patch('leadfactory.pipeline.email_queue.is_email_unsubscribed', return_value=False):
            # Mock file existence
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b"fake image data")):
                    with patch('leadfactory.pipeline.email_queue.generate_email_content', new_callable=AsyncMock) as mock_gen:
                        mock_gen.return_value = ("Subject", "<p>HTML</p>", "Text")

                        result = await send_business_email(
                            business, mock_sender, "<html>Template</html>"
                        )

                        assert result is True
                        mock_sender.send_email.assert_called_once()
                        mock_storage.save_email_record.assert_called_once()

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.storage')
    async def test_send_business_email_no_mockup(self, mock_storage, mock_sender, business):
        """Test email sending fails without mockup."""
        # Mock no mockup found
        mock_storage.get_business_asset.return_value = None

        with patch('leadfactory.pipeline.email_queue.is_email_unsubscribed', return_value=False):
            with patch('leadfactory.pipeline.email_queue.generate_email_content', new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = ("Subject", "<p>HTML</p>", "Text")

                with pytest.raises(Exception, match="Email delivery requires real mockup"):
                    await send_business_email(
                        business, mock_sender, "<html>Template</html>"
                    )

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.storage')
    async def test_send_business_email_unsubscribed(self, mock_storage, mock_sender, business):
        """Test email not sent to unsubscribed address."""
        with patch('leadfactory.pipeline.email_queue.is_email_unsubscribed', return_value=True):
            result = await send_business_email(
                business, mock_sender, "<html>Template</html>"
            )

            assert result is False
            mock_sender.send_email.assert_not_called()

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.storage')
    async def test_send_business_email_dry_run(self, mock_storage, mock_sender, business):
        """Test email sending in dry run mode."""
        mock_storage.save_email_record.return_value = True

        with patch('leadfactory.pipeline.email_queue.is_email_unsubscribed', return_value=False):
            with patch('leadfactory.pipeline.email_queue.generate_email_content', new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = ("Subject", "<p>HTML</p>", "Text")

                result = await send_business_email(
                    business, mock_sender, "<html>Template</html>", is_dry_run=True
                )

                assert result is True
                mock_sender.send_email.assert_not_called()  # Not actually sent
                mock_storage.save_email_record.assert_called_once()  # Still recorded

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.storage')
    async def test_send_business_email_with_override(self, mock_storage, mock_sender, business):
        """Test email override functionality."""
        mock_storage.get_business_asset.return_value = {"file_path": "/tmp/mockup.png"}
        mock_storage.save_email_record.return_value = True

        with patch('leadfactory.pipeline.email_queue.is_email_unsubscribed', return_value=False):
            with patch.dict(os.environ, {"EMAIL_OVERRIDE": "override@example.com"}):
                with patch('os.path.exists', return_value=True):
                    with patch('builtins.open', mock_open(read_data=b"fake image")):
                        with patch('leadfactory.pipeline.email_queue.generate_email_content', new_callable=AsyncMock) as mock_gen:
                            mock_gen.return_value = ("Subject", "<p>HTML</p>", "Text")

                            result = await send_business_email(
                                business, mock_sender, "<html>Template</html>"
                            )

                            assert result is True
                            # Check email was sent to override address
                            call_args = mock_sender.send_email.call_args
                            assert call_args.kwargs["to_email"] == "override@example.com"


class TestProcessBusinessEmail:
    """Test process_business_email function."""

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.get_businesses_for_email')
    @patch('leadfactory.pipeline.email_queue.load_email_template')
    @patch('leadfactory.pipeline.email_queue.send_business_email')
    @patch('leadfactory.pipeline.email_queue.load_sendgrid_config')
    async def test_process_business_email_success(
        self, mock_load_config, mock_send, mock_template, mock_get_businesses
    ):
        """Test processing a business email successfully."""
        # Set up mocks
        mock_get_businesses.return_value = [
            {"id": 1, "name": "Test Business", "email": "test@example.com"}
        ]
        mock_template.return_value = "<html>Template</html>"
        mock_send.return_value = True

        # Mock SendGrid config
        with patch('leadfactory.pipeline.email_queue.SENDGRID_API_KEY', 'test-key'):
            with patch('leadfactory.pipeline.email_queue.SENDGRID_FROM_EMAIL', 'from@example.com'):
                with patch('leadfactory.pipeline.email_queue.SENDGRID_FROM_NAME', 'Sender'):
                    result = await process_business_email(1)

                    assert result is True
                    mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.get_businesses_for_email')
    @patch('leadfactory.pipeline.email_queue.load_sendgrid_config')
    async def test_process_business_email_not_found(
        self, mock_load_config, mock_get_businesses
    ):
        """Test processing when business not found."""
        mock_get_businesses.return_value = []

        result = await process_business_email(999)
        assert result is False

    @pytest.mark.asyncio
    @patch('leadfactory.pipeline.email_queue.get_businesses_for_email')
    @patch('leadfactory.pipeline.email_queue.load_email_template')
    @patch('leadfactory.pipeline.email_queue.load_sendgrid_config')
    async def test_process_business_email_no_template(
        self, mock_load_config, mock_template, mock_get_businesses
    ):
        """Test processing when template loading fails."""
        mock_get_businesses.return_value = [{"id": 1, "name": "Test"}]
        mock_template.return_value = None

        result = await process_business_email(1)
        assert result is False
