#!/usr/bin/env python3
"""
Unit tests for webhook validator.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from leadfactory.webhooks.webhook_validator import (
    WebhookValidator,
    WebhookEvent,
    WebhookEventType,
    WebhookStatus,
    WebhookConfig,
    ValidationError,
    SignatureVerificationError,
)


class TestWebhookValidator:
    """Test cases for WebhookValidator."""

    def setup_method(self):
        """Setup test dependencies."""
        self.mock_storage = Mock()
        self.mock_error_manager = Mock()
        self.mock_alert_manager = Mock()
        self.mock_engagement_analytics = Mock()

        with patch('leadfactory.webhooks.webhook_validator.get_storage_instance', return_value=self.mock_storage):
            self.validator = WebhookValidator(
                error_manager=self.mock_error_manager,
                alert_manager=self.mock_alert_manager,
                engagement_analytics=self.mock_engagement_analytics,
            )

    def test_webhook_validator_initialization(self):
        """Test webhook validator initialization."""
        assert self.validator.storage == self.mock_storage
        assert self.validator.error_manager == self.mock_error_manager
        assert self.validator.alert_manager == self.mock_alert_manager
        assert self.validator.engagement_analytics == self.mock_engagement_analytics

        # Check default configs are loaded
        assert "sendgrid" in self.validator.webhook_configs
        assert "stripe" in self.validator.webhook_configs
        assert "engagement" in self.validator.webhook_configs

    def test_register_webhook_config(self):
        """Test registering webhook configuration."""
        config = WebhookConfig(
            name="test_webhook",
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.CUSTOM],
            secret_key="test_secret",
        )

        self.validator.register_webhook(config)

        assert "test_webhook" in self.validator.webhook_configs
        assert self.validator.webhook_configs["test_webhook"] == config

    def test_register_event_handler(self):
        """Test registering event handler."""
        def mock_handler(event):
            return True

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        assert WebhookEventType.EMAIL_DELIVERY in self.validator.event_handlers
        assert mock_handler in self.validator.event_handlers[WebhookEventType.EMAIL_DELIVERY]

    def test_validate_webhook_success(self):
        """Test successful webhook validation."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
            "sg_event_id": "test_event_id",
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        event = self.validator.validate_webhook(webhook_name, payload, headers)

        assert isinstance(event, WebhookEvent)
        assert event.webhook_name == webhook_name
        assert event.payload["email"] == "test@example.com"
        assert event.event_type == WebhookEventType.EMAIL_DELIVERY

    def test_validate_webhook_unknown_webhook(self):
        """Test validation with unknown webhook."""
        payload = b'{"test": "data"}'
        headers = {}

        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_webhook("unknown_webhook", payload, headers)

        assert "Unknown webhook" in str(exc_info.value)

    def test_validate_webhook_disabled_webhook(self):
        """Test validation with disabled webhook."""
        config = WebhookConfig(
            name="disabled_webhook",
            endpoint_path="/webhooks/disabled",
            event_types=[WebhookEventType.CUSTOM],
            enabled=False,
        )
        self.validator.register_webhook(config)

        payload = b'{"test": "data"}'
        headers = {}

        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_webhook("disabled_webhook", payload, headers)

        assert "disabled" in str(exc_info.value)

    def test_validate_webhook_invalid_json(self):
        """Test validation with invalid JSON payload."""
        payload = b'invalid json'
        headers = {}

        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_webhook("sendgrid", payload, headers)

        assert "Invalid JSON payload" in str(exc_info.value)

    def test_validate_webhook_rate_limit_exceeded(self):
        """Test validation with rate limit exceeded."""
        webhook_name = "sendgrid"
        config = self.validator.webhook_configs[webhook_name]
        config.rate_limit_per_minute = 1

        payload = json.dumps({"test": "data"}).encode('utf-8')
        headers = {}

        # First request should pass
        event1 = self.validator.validate_webhook(webhook_name, payload, headers)
        assert event1.webhook_name == webhook_name

        # Second request should fail due to rate limit
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_webhook(webhook_name, payload, headers)

        assert "Rate limit exceeded" in str(exc_info.value)

    def test_signature_verification_success(self):
        """Test successful signature verification."""
        webhook_name = "test_webhook"
        secret_key = "test_secret"

        config = WebhookConfig(
            name=webhook_name,
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.EMAIL_DELIVERY],
            secret_key=secret_key,
            signature_algorithm="sha256",
            signature_encoding="hex",
        )
        self.validator.register_webhook(config)

        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')

        # Generate valid signature
        import hmac
        import hashlib
        signature = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        headers = {"X-Signature": f"sha256={signature}"}

        event = self.validator.validate_webhook(webhook_name, payload, headers)
        assert event.signature_verified is True

    def test_signature_verification_failure(self):
        """Test signature verification failure."""
        webhook_name = "test_webhook"
        secret_key = "test_secret"

        config = WebhookConfig(
            name=webhook_name,
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.EMAIL_DELIVERY],
            secret_key=secret_key,
        )
        self.validator.register_webhook(config)

        payload = json.dumps({"test": "data"}).encode('utf-8')
        headers = {"X-Signature": "invalid_signature"}

        with pytest.raises(SignatureVerificationError) as exc_info:
            self.validator.validate_webhook(webhook_name, payload, headers)

        assert "Invalid signature" in str(exc_info.value)

    def test_signature_verification_missing_header(self):
        """Test signature verification with missing header."""
        webhook_name = "test_webhook"

        config = WebhookConfig(
            name=webhook_name,
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.EMAIL_DELIVERY],
            secret_key="test_secret",
        )
        self.validator.register_webhook(config)

        payload = json.dumps({"test": "data"}).encode('utf-8')
        headers = {}

        with pytest.raises(SignatureVerificationError) as exc_info:
            self.validator.validate_webhook(webhook_name, payload, headers)

        assert "Missing signature header" in str(exc_info.value)

    def test_determine_event_type_sendgrid(self):
        """Test event type determination for SendGrid webhooks."""
        test_cases = [
            ("delivered", WebhookEventType.EMAIL_DELIVERY),
            ("bounce", WebhookEventType.EMAIL_BOUNCE),
            ("dropped", WebhookEventType.EMAIL_BOUNCE),
            ("open", WebhookEventType.EMAIL_OPEN),
            ("click", WebhookEventType.EMAIL_CLICK),
            ("spamreport", WebhookEventType.EMAIL_SPAM),
            ("unsubscribe", WebhookEventType.EMAIL_UNSUBSCRIBE),
        ]

        config = self.validator.webhook_configs["sendgrid"]

        for event_name, expected_type in test_cases:
            payload = {"event": event_name}
            result = self.validator._determine_event_type(payload, config)
            assert result == expected_type

    def test_determine_event_type_stripe(self):
        """Test event type determination for Stripe webhooks."""
        config = self.validator.webhook_configs["stripe"]

        # Payment success
        payload = {"event": "payment_intent.succeeded"}
        result = self.validator._determine_event_type(payload, config)
        assert result == WebhookEventType.PAYMENT_SUCCESS

        # Payment failure
        payload = {"event": "payment_intent.payment_failed"}
        result = self.validator._determine_event_type(payload, config)
        assert result == WebhookEventType.PAYMENT_FAILED

    def test_schema_validation_success(self):
        """Test successful schema validation."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={
                "email": "test@example.com",
                "event": "delivered",
                "timestamp": 1234567890,
            },
        )

        # Should not raise an exception
        self.validator._validate_payload_schema(event)

    def test_schema_validation_failure(self):
        """Test schema validation failure."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={
                "email": "invalid_email",  # Invalid email format
                "event": "delivered",
                # Missing required timestamp
            },
        )

        with pytest.raises(ValidationError) as exc_info:
            self.validator._validate_payload_schema(event)

        assert "Schema validation failed" in str(exc_info.value)

    def test_custom_validation_email_bounce(self):
        """Test custom validation for email bounce events."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_BOUNCE,
            payload={
                "email": "test@example.com",
                "event": "bounce",
                "timestamp": 1234567890,
                "reason": "User unknown",
                "type": "hard",
            },
        )

        config = self.validator.webhook_configs["sendgrid"]

        # Should not raise an exception
        self.validator._custom_validation(event, config)

    def test_custom_validation_invalid_email(self):
        """Test custom validation with invalid email."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={
                "email": "invalid_email_format",
                "event": "delivered",
                "timestamp": 1234567890,
            },
        )

        config = self.validator.webhook_configs["sendgrid"]

        with pytest.raises(ValidationError) as exc_info:
            self.validator._custom_validation(event, config)

        assert "Invalid email format" in str(exc_info.value)

    def test_custom_validation_negative_amount(self):
        """Test custom validation with negative payment amount."""
        event = WebhookEvent(
            webhook_name="stripe",
            event_type=WebhookEventType.PAYMENT_SUCCESS,
            payload={
                "payment_id": "pay_123",
                "amount": -100,  # Negative amount
                "currency": "USD",
                "customer_id": "cust_123",
            },
        )

        config = self.validator.webhook_configs["stripe"]

        with pytest.raises(ValidationError) as exc_info:
            self.validator._custom_validation(event, config)

        assert "Amount cannot be negative" in str(exc_info.value)

    def test_process_webhook_success(self):
        """Test successful webhook processing."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={
                "email": "test@example.com",
                "event": "delivered",
                "timestamp": 1234567890,
            },
        )

        # Mock successful handler
        def mock_handler(event):
            return True

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        # Mock storage methods
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True

        result = self.validator.process_webhook(event)

        assert result is True
        assert event.status == WebhookStatus.COMPLETED
        assert event.processed_at is not None

        # Verify storage calls
        self.mock_storage.store_webhook_event.assert_called_once()
        self.mock_storage.update_webhook_event.assert_called_once()

    def test_process_webhook_handler_failure(self):
        """Test webhook processing with handler failure."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={"test": "data"},
        )

        # Mock failing handler
        def mock_handler(event):
            return False

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        # Mock storage methods
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True

        result = self.validator.process_webhook(event)

        assert result is False
        assert event.status == WebhookStatus.FAILED

    def test_process_webhook_handler_exception(self):
        """Test webhook processing with handler exception."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={"test": "data"},
        )

        # Mock handler that raises exception
        def mock_handler(event):
            raise Exception("Handler failed")

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        # Mock storage methods
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True

        # Mock retry manager
        mock_retry_manager = Mock()
        mock_retry_manager.execute_with_retry.side_effect = Exception("Handler failed")
        self.validator.retry_managers["sendgrid"] = mock_retry_manager

        result = self.validator.process_webhook(event)

        assert result is False
        # Status could be FAILED or RETRYING depending on retry manager configuration
        assert event.status in [WebhookStatus.FAILED, WebhookStatus.RETRYING]
        assert "Handler failed" in event.last_error

    def test_process_webhook_max_retries_exceeded(self):
        """Test webhook processing when max retries exceeded."""
        event = WebhookEvent(
            webhook_name="sendgrid",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={"test": "data"},
            retry_count=5,  # Exceeds max retries
        )

        # Mock handler that raises exception
        def mock_handler(event):
            raise Exception("Handler failed")

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        # Mock storage methods
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True
        self.mock_storage.store_dead_letter_webhook.return_value = True

        # Mock retry manager
        mock_retry_manager = Mock()
        mock_retry_manager.execute_with_retry.side_effect = Exception("Handler failed")
        self.validator.retry_managers["sendgrid"] = mock_retry_manager

        result = self.validator.process_webhook(event)

        assert result is False
        assert event.status == WebhookStatus.DEAD_LETTER

        # Verify dead letter storage was called
        self.mock_storage.store_dead_letter_webhook.assert_called_once()

    def test_get_webhook_stats(self):
        """Test getting webhook statistics."""
        webhook_name = "sendgrid"
        expected_stats = {
            "total_events": 100,
            "successful_events": 95,
            "failed_events": 5,
        }

        self.mock_storage.get_webhook_stats.return_value = expected_stats

        stats = self.validator.get_webhook_stats(webhook_name)

        assert stats == expected_stats
        self.mock_storage.get_webhook_stats.assert_called_once_with(webhook_name)

    def test_get_dead_letter_events(self):
        """Test getting dead letter events."""
        expected_events = [
            {"event_id": "1", "webhook_name": "sendgrid"},
            {"event_id": "2", "webhook_name": "stripe"},
        ]

        self.mock_storage.get_dead_letter_webhooks.return_value = expected_events

        events = self.validator.get_dead_letter_events(limit=50)

        assert events == expected_events
        self.mock_storage.get_dead_letter_webhooks.assert_called_once_with(50)

    def test_retry_dead_letter_event_success(self):
        """Test successful retry of dead letter event."""
        event_id = "test_event_id"
        dead_letter_data = {
            "event_id": event_id,
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"email": "test@example.com"},
            "headers": {},
            "timestamp": datetime.utcnow().isoformat(),
            "status": "dead_letter",
            "retry_count": 3,
            "last_error": "Previous error",
        }

        # Mock storage methods
        self.mock_storage.get_dead_letter_webhook.return_value = dead_letter_data
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True
        self.mock_storage.remove_dead_letter_webhook.return_value = True

        # Mock successful handler
        def mock_handler(event):
            return True

        self.validator.register_event_handler(WebhookEventType.EMAIL_DELIVERY, mock_handler)

        # Mock the process_webhook method to return success
        with patch.object(self.validator, 'process_webhook', return_value=True):
            result = self.validator.retry_dead_letter_event(event_id)

        assert result is True
        self.mock_storage.remove_dead_letter_webhook.assert_called_once_with(event_id)

    def test_retry_dead_letter_event_not_found(self):
        """Test retry of non-existent dead letter event."""
        event_id = "nonexistent_event"

        self.mock_storage.get_dead_letter_webhook.return_value = None

        result = self.validator.retry_dead_letter_event(event_id)

        assert result is False

    def test_is_valid_email(self):
        """Test email validation."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "123@test-domain.org",
        ]

        invalid_emails = [
            "invalid_email",
            "@domain.com",
            "user@",
            "user..name@domain.com",
        ]

        for email in valid_emails:
            assert self.validator._is_valid_email(email) is True

        for email in invalid_emails:
            assert self.validator._is_valid_email(email) is False


class TestWebhookEvent:
    """Test cases for WebhookEvent."""

    def test_webhook_event_creation(self):
        """Test webhook event creation."""
        event = WebhookEvent(
            webhook_name="test_webhook",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={"test": "data"},
            headers={"Content-Type": "application/json"},
        )

        assert event.webhook_name == "test_webhook"
        assert event.event_type == WebhookEventType.EMAIL_DELIVERY
        assert event.payload == {"test": "data"}
        assert event.headers == {"Content-Type": "application/json"}
        assert event.status == WebhookStatus.PENDING
        assert event.retry_count == 0

    def test_webhook_event_to_dict(self):
        """Test webhook event serialization."""
        event = WebhookEvent(
            webhook_name="test_webhook",
            event_type=WebhookEventType.EMAIL_DELIVERY,
            payload={"test": "data"},
        )

        event_dict = event.to_dict()

        assert event_dict["webhook_name"] == "test_webhook"
        assert event_dict["event_type"] == "email_delivery"
        assert event_dict["payload"] == {"test": "data"}
        assert event_dict["status"] == "pending"
        assert "timestamp" in event_dict
        assert "event_id" in event_dict


class TestWebhookConfig:
    """Test cases for WebhookConfig."""

    def test_webhook_config_creation(self):
        """Test webhook config creation."""
        config = WebhookConfig(
            name="test_webhook",
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.EMAIL_DELIVERY, WebhookEventType.EMAIL_BOUNCE],
            secret_key="test_secret",
            timeout_seconds=30,
            max_retries=5,
        )

        assert config.name == "test_webhook"
        assert config.endpoint_path == "/webhooks/test"
        assert WebhookEventType.EMAIL_DELIVERY in config.event_types
        assert WebhookEventType.EMAIL_BOUNCE in config.event_types
        assert config.secret_key == "test_secret"
        assert config.timeout_seconds == 30
        assert config.max_retries == 5
        assert config.enabled is True  # Default value
