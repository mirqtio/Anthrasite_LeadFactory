"""
Tests for email delivery service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from leadfactory.email.delivery import (
    EmailDeliveryService,
    EmailStatus,
    EmailEvent,
    EmailDeliveryRecord
)
from leadfactory.email.templates import EmailTemplate, EmailPersonalization


class TestEmailDeliveryService:
    """Test suite for EmailDeliveryService."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('leadfactory.email.delivery.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(SENDGRID_API_KEY="test-api-key")

            with patch('leadfactory.email.delivery.sendgrid.SendGridAPIClient'):
                with patch('leadfactory.email.delivery.get_storage_instance'):
                    self.service = EmailDeliveryService()
                    self.service.storage = AsyncMock()

    @pytest.fixture
    def sample_template(self):
        """Sample email template for testing."""
        return EmailTemplate(
            name="test_template",
            subject="Test Subject",
            html_content="<h1>Test Email</h1>",
            text_content="Test Email"
        )

    @pytest.fixture
    def sample_personalization(self):
        """Sample email personalization for testing."""
        return EmailPersonalization(
            user_name="John Doe",
            user_email="john@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/agency",
            purchase_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=7)
        )

    @pytest.mark.asyncio
    async def test_send_email_success(self, sample_template, sample_personalization):
        """Test successful email sending."""
        # Mock SendGrid response
        mock_response = MagicMock()
        mock_response.status_code = 202
        self.service.client.send.return_value = mock_response

        email_id = await self.service.send_email(
            sample_template,
            sample_personalization
        )

        assert email_id is not None
        assert len(email_id) == 36  # UUID length

        # Verify storage calls
        assert self.service.storage.execute_query.call_count == 2  # Initial + update

    @pytest.mark.asyncio
    async def test_send_email_failure(self, sample_template, sample_personalization):
        """Test email sending failure."""
        # Mock SendGrid error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.body = "Bad Request"
        self.service.client.send.return_value = mock_response

        with pytest.raises(Exception, match="SendGrid API error"):
            await self.service.send_email(
                sample_template,
                sample_personalization
            )

    @pytest.mark.asyncio
    async def test_handle_webhook_event_delivered(self):
        """Test handling delivered webhook event."""
        event_data = {
            "event": "delivered",
            "email_id": "test-email-id",
            "timestamp": 1640995200,  # 2022-01-01 00:00:00
            "useragent": "Test Agent",
            "ip": "192.168.1.1"
        }

        await self.service.handle_webhook_event(event_data)

        # Verify event storage
        self.service.storage.execute_query.assert_called()

        # Check that delivery status was updated
        calls = self.service.storage.execute_query.call_args_list
        assert len(calls) >= 2  # Event + status update

    @pytest.mark.asyncio
    async def test_handle_webhook_event_opened(self):
        """Test handling opened webhook event."""
        event_data = {
            "event": "open",
            "email_id": "test-email-id",
            "timestamp": 1640995200,
            "useragent": "Test Agent",
            "ip": "192.168.1.1"
        }

        await self.service.handle_webhook_event(event_data)

        # Verify storage calls
        assert self.service.storage.execute_query.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_webhook_event_clicked(self):
        """Test handling clicked webhook event."""
        event_data = {
            "event": "click",
            "email_id": "test-email-id",
            "timestamp": 1640995200,
            "url": "https://example.com/clicked-link",
            "useragent": "Test Agent",
            "ip": "192.168.1.1"
        }

        await self.service.handle_webhook_event(event_data)

        # Verify storage calls
        assert self.service.storage.execute_query.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_webhook_event_bounced(self):
        """Test handling bounced webhook event."""
        event_data = {
            "event": "bounce",
            "email_id": "test-email-id",
            "timestamp": 1640995200,
            "reason": "Invalid email address"
        }

        await self.service.handle_webhook_event(event_data)

        # Verify storage calls
        assert self.service.storage.execute_query.call_count >= 2

    @pytest.mark.asyncio
    async def test_handle_webhook_event_no_email_id(self):
        """Test handling webhook event without email ID."""
        event_data = {
            "event": "delivered",
            "timestamp": 1640995200
        }

        await self.service.handle_webhook_event(event_data)

        # Should not make storage calls
        self.service.storage.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_delivery_stats_basic(self):
        """Test getting basic delivery statistics."""
        mock_result = {
            "total_sent": 100,
            "delivered": 95,
            "opened": 60,
            "clicked": 25,
            "bounced": 3,
            "failed": 2
        }
        self.service.storage.fetch_one.return_value = mock_result

        stats = await self.service.get_delivery_stats()

        assert stats["total_sent"] == 100
        assert stats["delivery_rate"] == 0.95
        assert stats["open_rate"] == 0.60
        assert stats["click_rate"] == 0.25
        assert stats["bounce_rate"] == 0.03

    @pytest.mark.asyncio
    async def test_get_delivery_stats_with_filters(self):
        """Test getting delivery statistics with filters."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        template_name = "report_delivery"

        mock_result = {
            "total_sent": 50,
            "delivered": 48,
            "opened": 30,
            "clicked": 15,
            "bounced": 1,
            "failed": 1
        }
        self.service.storage.fetch_one.return_value = mock_result

        stats = await self.service.get_delivery_stats(
            start_date=start_date,
            end_date=end_date,
            template_name=template_name
        )

        assert stats["total_sent"] == 50

        # Verify query was called with filters
        self.service.storage.fetch_one.assert_called_once()
        call_args = self.service.storage.fetch_one.call_args
        assert start_date in call_args[0]
        assert end_date in call_args[0]
        assert template_name in call_args[0]

    @pytest.mark.asyncio
    async def test_get_delivery_stats_no_data(self):
        """Test getting delivery statistics with no data."""
        self.service.storage.fetch_one.return_value = None

        stats = await self.service.get_delivery_stats()

        assert stats["total_sent"] == 0
        assert stats["delivery_rate"] == 0
        assert stats["open_rate"] == 0
        assert stats["click_rate"] == 0

    @pytest.mark.asyncio
    async def test_retry_failed_emails(self):
        """Test retrying failed emails."""
        mock_failed_emails = [
            {
                "email_id": "failed-1",
                "user_id": "user1",
                "template_name": "test",
                "subject": "Test",
                "metadata": "{}"
            },
            {
                "email_id": "failed-2",
                "user_id": "user2",
                "template_name": "test",
                "subject": "Test",
                "metadata": "{}"
            }
        ]
        self.service.storage.fetch_all.return_value = mock_failed_emails

        retry_count = await self.service.retry_failed_emails()

        assert retry_count == 2

        # Verify retry count was incremented for each email
        assert self.service.storage.execute_query.call_count == 2

    def test_prepare_sendgrid_email(self, sample_template, sample_personalization):
        """Test SendGrid email preparation."""
        email_id = str(uuid4())

        mail = self.service._prepare_sendgrid_email(
            sample_template,
            sample_personalization,
            email_id
        )

        assert mail.from_email.email == "reports@anthrasite.com"
        assert mail.personalizations[0].tos[0]["email"] == "john@example.com"
        assert mail.subject.subject == "Test Subject"

        # Check tracking settings
        assert mail.tracking_settings.click_tracking.enable is True
        assert mail.tracking_settings.open_tracking.enable is True

    def test_email_delivery_record_model(self):
        """Test EmailDeliveryRecord model."""
        record = EmailDeliveryRecord(
            email_id="test-id",
            user_id="user-123",
            email_address="test@example.com",
            template_name="test_template",
            subject="Test Subject"
        )

        assert record.status == EmailStatus.QUEUED
        assert record.retry_count == 0
        assert record.max_retries == 3
        assert record.metadata == {}

    def test_email_event_model(self):
        """Test EmailEvent model."""
        event = EmailEvent(
            email_id="test-id",
            event_type="click",
            timestamp=datetime.utcnow(),
            url="https://example.com/link"
        )

        assert event.email_id == "test-id"
        assert event.event_type == "click"
        assert event.url == "https://example.com/link"
        assert event.metadata == {}

    def test_email_status_enum(self):
        """Test EmailStatus enum values."""
        assert EmailStatus.QUEUED == "queued"
        assert EmailStatus.SENT == "sent"
        assert EmailStatus.DELIVERED == "delivered"
        assert EmailStatus.OPENED == "opened"
        assert EmailStatus.CLICKED == "clicked"
        assert EmailStatus.BOUNCED == "bounced"
        assert EmailStatus.FAILED == "failed"

    @patch('leadfactory.email.delivery.get_email_delivery_service')
    def test_get_email_delivery_service_function(self, mock_factory):
        """Test the factory function."""
        mock_service = MagicMock()
        mock_factory.return_value = mock_service

        from leadfactory.email.delivery import get_email_delivery_service
        service = get_email_delivery_service()

        assert service == mock_service
