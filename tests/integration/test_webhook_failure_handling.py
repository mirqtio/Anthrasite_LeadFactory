#!/usr/bin/env python3
"""
Integration tests for webhook failure handling system.
"""

import json
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.webhooks.webhook_integration import WebhookIntegrationService
from leadfactory.webhooks.webhook_validator import WebhookEventType, WebhookStatus
from leadfactory.webhooks.dead_letter_queue import DeadLetterReason, DeadLetterStatus
from leadfactory.webhooks.webhook_retry_manager import WebhookPriority


class TestWebhookFailureHandlingIntegration:
    """Integration tests for webhook failure handling."""

    def setup_method(self):
        """Setup test dependencies."""
        self.mock_storage = Mock()
        self.mock_engagement_analytics = Mock()
        self.mock_error_manager = Mock()

        # Patch storage and analytics dependencies
        self.storage_patcher = patch(
            'leadfactory.webhooks.webhook_validator.get_storage_instance',
            return_value=self.mock_storage
        )
        self.analytics_patcher = patch(
            'leadfactory.webhooks.webhook_integration.EngagementAnalytics',
            return_value=self.mock_engagement_analytics
        )
        self.error_patcher = patch(
            'leadfactory.webhooks.webhook_integration.ErrorPropagationManager',
            return_value=self.mock_error_manager
        )

        self.storage_patcher.start()
        self.analytics_patcher.start()
        self.error_patcher.start()

        # Initialize integration service
        self.integration_service = WebhookIntegrationService()

        # Setup mock storage responses
        self.mock_storage.store_webhook_event.return_value = True
        self.mock_storage.update_webhook_event.return_value = True
        self.mock_storage.store_engagement_event.return_value = True
        self.mock_storage.update_user_session.return_value = True
        self.mock_storage.get_user_session.return_value = None

    def teardown_method(self):
        """Cleanup test dependencies."""
        self.storage_patcher.stop()
        self.analytics_patcher.stop()
        self.error_patcher.stop()

        # Shutdown integration service
        self.integration_service.shutdown()

    def test_successful_sendgrid_email_delivery_webhook(self):
        """Test successful processing of SendGrid email delivery webhook."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
            "sg_event_id": "test_event_123",
            "sg_message_id": "test_message_456",
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers, "192.168.1.1"
        )

        # Should succeed
        assert result["success"] is True
        assert result["status"] == "completed"
        assert result["event_id"] is not None

        # Verify engagement tracking was called
        self.mock_engagement_analytics.track_event.assert_called()

        # Verify webhook event was stored
        self.mock_storage.store_webhook_event.assert_called()
        self.mock_storage.update_webhook_event.assert_called()

    def test_sendgrid_email_bounce_webhook_error_handling(self):
        """Test SendGrid bounce webhook creates proper error records."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "bounced@example.com",
            "event": "bounce",
            "timestamp": 1234567890,
            "reason": "550 5.1.1 User unknown",
            "type": "hard",
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers
        )

        # Should succeed in processing the bounce event
        assert result["success"] is True
        assert result["status"] == "completed"

        # Verify error was recorded
        self.mock_error_manager.record_error.assert_called()

        # Verify bounce tracking in engagement analytics
        self.mock_engagement_analytics.track_event.assert_called()

    def test_stripe_payment_success_webhook(self):
        """Test successful Stripe payment webhook processing."""
        webhook_name = "stripe"
        payload = json.dumps({
            "payment_id": "pay_1234567890",
            "customer_id": "cust_test123",
            "amount": 2999,  # $29.99
            "currency": "USD",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers
        )

        # Should succeed
        assert result["success"] is True
        assert result["status"] == "completed"

        # Verify purchase event was tracked
        self.mock_engagement_analytics.track_event.assert_called()

        # Check that purchase event was tracked correctly
        call_args = self.mock_engagement_analytics.track_event.call_args
        assert call_args[1]["event_type"] == "purchase"
        assert call_args[1]["properties"]["amount"] == 2999

    def test_webhook_validation_failure(self):
        """Test webhook validation failure handling."""
        webhook_name = "sendgrid"
        payload = b'invalid json payload'
        headers = {"Content-Type": "application/json"}

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers
        )

        # Should fail
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "Validation error" in result["message"]

        # Verify error tracking
        self.mock_engagement_analytics.track_event.assert_called()
        call_args = self.mock_engagement_analytics.track_event.call_args
        assert call_args[1]["event_type"] == "webhook_validation_failed"

    def test_webhook_handler_exception_retry_scheduling(self):
        """Test that handler exceptions trigger retry scheduling."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        # Mock handler that raises exception
        def failing_handler(event):
            raise Exception("Handler processing failed")

        # Replace the email delivery handler with failing one
        self.integration_service.webhook_validator.event_handlers[WebhookEventType.EMAIL_DELIVERY] = [failing_handler]

        # Mock retry manager
        with patch.object(self.integration_service.retry_manager, 'schedule_retry', return_value=True) as mock_schedule:
            result = self.integration_service.process_webhook(
                webhook_name, payload, headers
            )

        # Should fail but not crash
        assert result["success"] is False
        assert result["status"] == "failed"

        # Verify retry was scheduled
        mock_schedule.assert_called_once()

    def test_webhook_max_retries_dead_letter_queue(self):
        """Test webhook moved to dead letter queue after max retries."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        # Mock failing handler
        def failing_handler(event):
            return False

        self.integration_service.webhook_validator.event_handlers[WebhookEventType.EMAIL_DELIVERY] = [failing_handler]

        # Mock dead letter manager
        with patch.object(self.integration_service.dead_letter_manager, 'add_event', return_value="dl_event_123") as mock_add_dl:
            # Simulate event that has already exceeded max retries
            with patch.object(self.integration_service.webhook_validator, 'validate_webhook') as mock_validate:
                mock_event = Mock()
                mock_event.event_id = "test_event_123"
                mock_event.webhook_name = webhook_name
                mock_event.retry_count = 5  # Exceeds max retries
                mock_event.to_dict.return_value = {"event_id": "test_event_123"}
                mock_validate.return_value = mock_event

                result = self.integration_service.process_webhook(
                    webhook_name, payload, headers
                )

        # Should fail
        assert result["success"] is False

        # Verify event was added to dead letter queue
        mock_add_dl.assert_called_once()

    def test_webhook_circuit_breaker_behavior(self):
        """Test webhook circuit breaker prevents further processing."""
        webhook_name = "sendgrid"

        # Get the circuit breaker for this webhook
        circuit_breaker = self.integration_service.retry_manager.webhook_circuit_breakers.get(webhook_name)
        if circuit_breaker:
            # Manually trip the circuit breaker
            circuit_breaker.state = circuit_breaker.state.__class__.OPEN

        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        # Mock schedule_retry to check circuit breaker behavior
        with patch.object(self.integration_service.retry_manager, 'schedule_retry', return_value=False) as mock_schedule:
            result = self.integration_service.process_webhook(
                webhook_name, payload, headers
            )

        # Should still process the initial webhook
        assert result["event_id"] is not None

    @pytest.mark.asyncio
    async def test_retry_queue_processing(self):
        """Test retry queue processes items correctly."""
        # Add a retry item to the queue
        retry_manager = self.integration_service.retry_manager

        # Mock storage for retry queue
        self.mock_storage.store_webhook_retry_item.return_value = True
        self.mock_storage.get_webhook_event.return_value = {
            "event_id": "retry_event_123",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"email": "test@example.com", "event": "delivered"},
            "headers": {},
            "timestamp": datetime.utcnow().isoformat(),
            "status": "failed",
            "retry_count": 1,
        }

        # Schedule a retry
        success = retry_manager.schedule_retry(
            event_id="retry_event_123",
            webhook_name="sendgrid",
            retry_attempt=1,
            error="Initial processing failed",
        )

        assert success is True
        assert len(retry_manager.retry_queue) == 1

        # Mock successful processing on retry
        with patch.object(retry_manager, '_process_retry_item', return_value=True) as mock_process:
            # Process ready items
            await retry_manager._process_ready_items()

        # Item should have been processed
        mock_process.assert_called_once()

    def test_engagement_event_webhook_tracking(self):
        """Test engagement event webhook is properly tracked."""
        webhook_name = "engagement"
        payload = json.dumps({
            "user_id": "user_123",
            "event_type": "page_view",
            "timestamp": 1234567890,
            "session_id": "session_456",
            "properties": {
                "page_url": "https://example.com/page",
                "referrer": "https://google.com",
            },
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers
        )

        assert result["success"] is True
        assert result["status"] == "completed"

        # Verify engagement tracking was called with correct parameters
        self.mock_engagement_analytics.track_event.assert_called()
        call_args = self.mock_engagement_analytics.track_event.call_args
        assert call_args[1]["user_id"] == "user_123"
        assert call_args[1]["event_type"] == "page_view"
        assert call_args[1]["session_id"] == "session_456"

    def test_webhook_health_monitoring_integration(self):
        """Test webhook health monitoring tracks metrics."""
        webhook_monitor = self.integration_service.webhook_monitor

        # Mock storage for metrics
        self.mock_storage.get_webhook_events.return_value = [
            {
                "event_id": "event_1",
                "webhook_name": "sendgrid",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "processed_at": (datetime.utcnow() + timedelta(seconds=1)).isoformat(),
                "retry_count": 0,
            },
            {
                "event_id": "event_2",
                "webhook_name": "sendgrid",
                "status": "failed",
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": 1,
            },
        ]

        # Get health status
        health_status = webhook_monitor.get_webhook_health("sendgrid")

        assert health_status is not None
        assert health_status["webhook_name"] == "sendgrid"
        assert "status" in health_status
        assert "thresholds" in health_status

    def test_dead_letter_queue_management(self):
        """Test dead letter queue management operations."""
        dead_letter_manager = self.integration_service.dead_letter_manager

        # Mock adding an event to dead letter queue
        webhook_event = {
            "event_id": "failed_event_123",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"email": "test@example.com"},
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 3,
        }

        # Mock storage
        self.mock_storage.store_dead_letter_event.return_value = True

        dl_event_id = dead_letter_manager.add_event(
            webhook_event=webhook_event,
            reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
            last_error="Processing failed after 3 attempts",
        )

        assert dl_event_id != ""
        self.mock_storage.store_dead_letter_event.assert_called_once()

    def test_webhook_admin_api_integration(self):
        """Test webhook admin API endpoints work with integration service."""
        from leadfactory.api.webhook_admin_api import webhook_admin_bp
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(webhook_admin_bp)

        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/api/webhooks/admin/health')
            assert response.status_code == 200

            health_data = json.loads(response.data)
            assert "overall_status" in health_data
            assert "total_webhooks" in health_data

            # Test webhook stats endpoint
            response = client.get('/api/webhooks/admin/webhooks/sendgrid/stats')
            assert response.status_code == 200

            # Test retry queue stats endpoint
            response = client.get('/api/webhooks/admin/retry/queue')
            assert response.status_code == 200

    def test_signature_verification_integration(self):
        """Test signature verification works end-to-end."""
        webhook_name = "test_webhook_with_secret"
        secret_key = "test_secret_key_123"

        # Register webhook with secret
        from leadfactory.webhooks.webhook_validator import WebhookConfig
        config = WebhookConfig(
            name=webhook_name,
            endpoint_path="/webhooks/test",
            event_types=[WebhookEventType.CUSTOM],
            secret_key=secret_key,
            signature_header="X-Test-Signature",
            signature_algorithm="sha256",
            signature_encoding="hex",
        )

        self.integration_service.webhook_validator.register_webhook(config)

        payload = json.dumps({"test": "data"}).encode('utf-8')

        # Generate valid signature
        import hmac
        import hashlib
        signature = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Test-Signature": f"sha256={signature}",
        }

        result = self.integration_service.process_webhook(
            webhook_name, payload, headers
        )

        assert result["success"] is True
        assert result["status"] == "completed"

    def test_rate_limiting_integration(self):
        """Test rate limiting prevents excessive webhook processing."""
        webhook_name = "sendgrid"
        config = self.integration_service.webhook_validator.webhook_configs[webhook_name]
        config.rate_limit_per_minute = 2  # Very low limit for testing

        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        # First two requests should succeed
        result1 = self.integration_service.process_webhook(webhook_name, payload, headers)
        result2 = self.integration_service.process_webhook(webhook_name, payload, headers)

        assert result1["success"] is True
        assert result2["success"] is True

        # Third request should fail due to rate limiting
        result3 = self.integration_service.process_webhook(webhook_name, payload, headers)

        assert result3["success"] is False
        assert "Rate limit exceeded" in result3["message"]

    def test_integration_service_status(self):
        """Test integration service provides comprehensive status."""
        status = self.integration_service.get_integration_status()

        assert "webhook_validator" in status
        assert "webhook_monitor" in status
        assert "retry_manager" in status
        assert "dead_letter_manager" in status
        assert "error_manager" in status
        assert "engagement_analytics" in status

        # Check webhook validator status
        validator_status = status["webhook_validator"]
        assert "registered_webhooks" in validator_status
        assert "registered_handlers" in validator_status

    def test_end_to_end_webhook_failure_recovery(self):
        """Test complete failure and recovery cycle."""
        webhook_name = "sendgrid"
        payload = json.dumps({
            "email": "test@example.com",
            "event": "delivered",
            "timestamp": 1234567890,
        }).encode('utf-8')
        headers = {"Content-Type": "application/json"}

        # Step 1: Initial webhook fails
        def failing_handler(event):
            raise Exception("Temporary failure")

        self.integration_service.webhook_validator.event_handlers[WebhookEventType.EMAIL_DELIVERY] = [failing_handler]

        with patch.object(self.integration_service.retry_manager, 'schedule_retry', return_value=True):
            result1 = self.integration_service.process_webhook(webhook_name, payload, headers)

        assert result1["success"] is False

        # Step 2: Replace with working handler
        def working_handler(event):
            return True

        self.integration_service.webhook_validator.event_handlers[WebhookEventType.EMAIL_DELIVERY] = [working_handler]

        # Step 3: Retry should succeed
        result2 = self.integration_service.process_webhook(webhook_name, payload, headers)

        assert result2["success"] is True
        assert result2["status"] == "completed"
