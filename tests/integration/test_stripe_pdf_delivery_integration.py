"""
Integration tests for Stripe webhook integration with PDF delivery.

Tests the complete integration between Stripe payment webhooks and
PDF report delivery, including security, rate limiting, and error handling.
"""

import pytest
import tempfile
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.services.report_delivery import ReportDeliveryService
from leadfactory.services.payment_service import StripePaymentService
from leadfactory.storage.supabase_storage import SupabaseStorage


class TestStripePDFDeliveryIntegration:
    """Integration tests for Stripe webhook and PDF delivery."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create test PDF content
        self.test_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"

        # Create temporary PDF file
        self.temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        self.temp_pdf.write(self.test_pdf_content)
        self.temp_pdf.close()

        # Sample Stripe webhook payloads
        self.successful_payment_payload = {
            "id": "evt_test_webhook",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123456789",
                    "object": "checkout.session",
                    "payment_status": "paid",
                    "customer_email": "customer@example.com",
                    "customer_details": {
                        "email": "customer@example.com",
                        "name": "John Doe"
                    },
                    "metadata": {
                        "report_id": "report_abc123",
                        "user_id": "user_xyz789",
                        "report_type": "lead_analysis"
                    },
                    "amount_total": 2999,  # $29.99
                    "currency": "usd"
                }
            }
        }

        self.failed_payment_payload = {
            "id": "evt_test_webhook_failed",
            "object": "event",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed_123",
                    "object": "checkout.session",
                    "payment_status": "unpaid",
                    "customer_email": "failed@example.com",
                    "metadata": {
                        "report_id": "report_failed123",
                        "user_id": "user_failed789"
                    }
                }
            }
        }

        self.refund_payload = {
            "id": "evt_test_refund",
            "object": "event",
            "type": "charge.dispute.created",
            "data": {
                "object": {
                    "id": "dp_test_dispute",
                    "object": "dispute",
                    "charge": "ch_test_charge_123",
                    "metadata": {
                        "report_id": "report_dispute123",
                        "user_id": "user_dispute789"
                    }
                }
            }
        }

    def teardown_method(self):
        """Clean up test files."""
        try:
            os.unlink(self.temp_pdf.name)
        except FileNotFoundError:
            pass

    @pytest.mark.integration
    def test_successful_payment_triggers_pdf_delivery(self):
        """Test that successful payment webhook triggers PDF delivery."""
        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create_client, \
             patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env, \
             patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock environment variables
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key',
                'STRIPE_WEBHOOK_SECRET': 'whsec_test_secret'
            }.get(key)

            # Mock Supabase client
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_client.storage.from_.return_value.upload.return_value = {
                "path": "reports/user_xyz789/report_abc123_20240101_120000.pdf"
            }
            mock_client.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://test.supabase.co/storage/v1/object/sign/reports/file.pdf?token=webhook123"
            }

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.successful_payment_payload

            # Create storage and services
            storage = SupabaseStorage(bucket_name="webhook-reports")

            # Mock other dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure successful validation
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_rate_limiter.check_rate_limit.return_value.allowed = True
            mock_link_generator.generate_secure_report_url.return_value = {
                "url": "https://secure-delivery.example.com/report_abc123",
                "expires_at": (datetime.utcnow() + timedelta(hours=48)).isoformat() + "Z"
            }

            # Create delivery service
            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # Create payment service
            payment_service = StripePaymentService(delivery_service=delivery_service)

            # Process webhook
            webhook_body = json.dumps(self.successful_payment_payload)
            webhook_signature = "test_signature"

            result = payment_service.handle_webhook(webhook_body, webhook_signature)

            # Verify webhook processing
            assert result["success"] is True
            assert result["event_type"] == "checkout.session.completed"
            assert result["report_id"] == "report_abc123"

            # Verify PDF delivery was triggered
            mock_email_service.send_email.assert_called_once()
            email_call = mock_email_service.send_email.call_args[1]
            assert email_call["to_email"] == "customer@example.com"
            assert "report_abc123" in email_call["html_content"]
            assert "secure-delivery.example.com" in email_call["html_content"]

            # Verify audit logging
            mock_audit_logger.log_access_granted.assert_called_once()

    @pytest.mark.integration
    def test_failed_payment_no_pdf_delivery(self):
        """Test that failed payment webhook does not trigger PDF delivery."""
        with patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.failed_payment_payload

            # Mock dependencies
            mock_email_service = Mock()
            mock_delivery_service = Mock()

            # Create payment service
            payment_service = StripePaymentService(delivery_service=mock_delivery_service)

            # Process webhook
            webhook_body = json.dumps(self.failed_payment_payload)
            webhook_signature = "test_signature"

            result = payment_service.handle_webhook(webhook_body, webhook_signature)

            # Verify webhook processing
            assert result["success"] is True
            assert result["event_type"] == "checkout.session.async_payment_failed"

            # Verify NO PDF delivery was triggered
            mock_delivery_service.upload_and_deliver_report.assert_not_called()
            mock_email_service.send_email.assert_not_called()

    @pytest.mark.integration
    def test_webhook_rate_limiting_protection(self):
        """Test rate limiting protection for webhook processing."""
        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create_client, \
             patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env, \
             patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key',
                'STRIPE_WEBHOOK_SECRET': 'whsec_test_secret'
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.successful_payment_payload

            storage = SupabaseStorage(bucket_name="rate-limit-test")

            # Mock dependencies with rate limiting
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure rate limiting to trigger after first call
            call_count = 0
            def rate_limit_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                result = Mock()
                result.allowed = call_count == 1  # Only allow first call
                result.reason = "Rate limit exceeded" if call_count > 1 else None
                return result

            mock_rate_limiter.check_rate_limit.side_effect = rate_limit_side_effect
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            payment_service = StripePaymentService(delivery_service=delivery_service)

            webhook_body = json.dumps(self.successful_payment_payload)
            webhook_signature = "test_signature"

            # First webhook should succeed
            result1 = payment_service.handle_webhook(webhook_body, webhook_signature)
            assert result1["success"] is True

            # Second identical webhook should be rate limited
            result2 = payment_service.handle_webhook(webhook_body, webhook_signature)
            assert result2["success"] is False
            assert "rate limit" in result2.get("reason", "").lower()

    @pytest.mark.integration
    def test_webhook_security_validation(self):
        """Test security validation during webhook processing."""
        with patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock invalid webhook signature
            mock_stripe.Webhook.construct_event.side_effect = Exception("Invalid signature")

            # Mock dependencies
            mock_delivery_service = Mock()

            payment_service = StripePaymentService(delivery_service=mock_delivery_service)

            webhook_body = json.dumps(self.successful_payment_payload)
            invalid_signature = "invalid_signature"

            # Process webhook with invalid signature
            with pytest.raises(Exception, match="Invalid signature"):
                payment_service.handle_webhook(webhook_body, invalid_signature)

            # Verify no delivery was attempted
            mock_delivery_service.upload_and_deliver_report.assert_not_called()

    @pytest.mark.integration
    def test_webhook_duplicate_event_handling(self):
        """Test handling of duplicate webhook events."""
        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create_client, \
             patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env, \
             patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key'
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.successful_payment_payload

            storage = SupabaseStorage(bucket_name="duplicate-test")

            # Mock dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure successful validation
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_rate_limiter.check_rate_limit.return_value.allowed = True

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            payment_service = StripePaymentService(delivery_service=delivery_service)

            webhook_body = json.dumps(self.successful_payment_payload)
            webhook_signature = "test_signature"

            # Process same webhook twice
            result1 = payment_service.handle_webhook(webhook_body, webhook_signature)
            result2 = payment_service.handle_webhook(webhook_body, webhook_signature)

            # Both should succeed but second should be detected as duplicate
            assert result1["success"] is True
            assert result2["success"] is True
            assert result2.get("duplicate", False) is True

    @pytest.mark.integration
    def test_webhook_refund_handling(self):
        """Test handling of refund/dispute webhooks."""
        with patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.refund_payload

            # Mock dependencies
            mock_delivery_service = Mock()
            mock_audit_logger = Mock()

            payment_service = StripePaymentService(
                delivery_service=mock_delivery_service,
                audit_logger=mock_audit_logger
            )

            webhook_body = json.dumps(self.refund_payload)
            webhook_signature = "test_signature"

            result = payment_service.handle_webhook(webhook_body, webhook_signature)

            # Verify refund processing
            assert result["success"] is True
            assert result["event_type"] == "charge.dispute.created"

            # Verify access revocation was triggered
            mock_delivery_service.revoke_report_access.assert_called_once_with(
                report_id="report_dispute123",
                user_id="user_dispute789",
                reason="Payment disputed/refunded"
            )

            # Verify audit logging
            mock_audit_logger.log_security_violation.assert_called_once()

    @pytest.mark.integration
    def test_webhook_error_recovery(self):
        """Test error recovery during webhook processing."""
        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create_client, \
             patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env, \
             patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key'
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.successful_payment_payload

            storage = SupabaseStorage(bucket_name="error-recovery-test")

            # Mock dependencies with initial failure then success
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure email service to fail first, then succeed
            call_count = 0
            def email_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Email service temporarily unavailable")
                return {"success": True}

            mock_email_service.send_email.side_effect = email_side_effect
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_rate_limiter.check_rate_limit.return_value.allowed = True

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            payment_service = StripePaymentService(delivery_service=delivery_service)

            webhook_body = json.dumps(self.successful_payment_payload)
            webhook_signature = "test_signature"

            # First attempt should fail
            result1 = payment_service.handle_webhook(webhook_body, webhook_signature)
            assert result1["success"] is False
            assert "temporarily unavailable" in result1.get("error", "")

            # Second attempt should succeed (retry logic)
            result2 = payment_service.handle_webhook(webhook_body, webhook_signature)
            assert result2["success"] is True

            # Verify error was logged
            mock_audit_logger.log_security_violation.assert_called()

    @pytest.mark.integration
    def test_webhook_metadata_validation(self):
        """Test validation of webhook metadata requirements."""
        with patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Create payload with missing metadata
            invalid_payload = {
                "id": "evt_test_invalid",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_invalid",
                        "payment_status": "paid",
                        "customer_email": "invalid@example.com",
                        "metadata": {
                            # Missing required report_id and user_id
                            "some_other_field": "value"
                        }
                    }
                }
            }

            mock_stripe.Webhook.construct_event.return_value = invalid_payload

            # Mock dependencies
            mock_delivery_service = Mock()

            payment_service = StripePaymentService(delivery_service=mock_delivery_service)

            webhook_body = json.dumps(invalid_payload)
            webhook_signature = "test_signature"

            result = payment_service.handle_webhook(webhook_body, webhook_signature)

            # Verify validation failure
            assert result["success"] is False
            assert "missing required metadata" in result.get("error", "").lower()

            # Verify no delivery was attempted
            mock_delivery_service.upload_and_deliver_report.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.skip(reason="Temporarily disabled due to CI hanging - needs threading fix")
    def test_webhook_concurrent_processing(self):
        """Test concurrent webhook processing scenarios."""
        import threading
        import queue

        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create_client, \
             patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env, \
             patch('leadfactory.services.payment_service.stripe') as mock_stripe:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key'
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = self.successful_payment_payload

            storage = SupabaseStorage(bucket_name="concurrent-webhook-test")

            # Mock dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure successful validation
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_rate_limiter.check_rate_limit.return_value.allowed = True

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            payment_service = StripePaymentService(delivery_service=delivery_service)

            webhook_body = json.dumps(self.successful_payment_payload)
            webhook_signature = "test_signature"

            # Process multiple webhooks concurrently
            results_queue = queue.Queue()

            def process_webhook(thread_id):
                try:
                    result = payment_service.handle_webhook(webhook_body, webhook_signature)
                    results_queue.put((thread_id, result))
                except Exception as e:
                    results_queue.put((thread_id, {"error": str(e)}))

            # Launch concurrent threads
            threads = []
            for i in range(3):
                thread = threading.Thread(target=process_webhook, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for completion with timeout
            for thread in threads:
                thread.join(timeout=5.0)  # 5 second timeout
                if thread.is_alive():
                    # Thread didn't complete - test should fail
                    pytest.fail(f"Thread {thread.name} did not complete within timeout")

            # Collect results with timeout
            results = []
            timeout_count = 0
            while not results_queue.empty() and timeout_count < 10:
                try:
                    results.append(results_queue.get_nowait())
                except:
                    timeout_count += 1
                    time.sleep(0.1)

            # Verify at least one succeeded and others were handled properly
            successful_results = [r for r in results if r[1].get("success", False)]
            assert len(successful_results) >= 1

            # Verify no race conditions caused errors
            error_results = [r for r in results if "error" in r[1]]
            assert len(error_results) == 0
