"""
End-to-end tests for PDF storage and delivery functionality.

Tests the complete workflow from PDF upload through secure URL generation,
Stripe webhook integration, and final delivery to users.
"""

import contextlib
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.security.access_control import PDFOperation, UserRole
from leadfactory.security.rate_limiter import RateLimitType
from leadfactory.services.report_delivery import ReportDeliveryService
from leadfactory.storage.supabase_storage import SupabaseStorage


class TestPDFStorageDeliveryE2E:
    """End-to-end tests for complete PDF storage and delivery workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create test PDF content
        self.test_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        self.large_pdf_content = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024)  # 10MB PDF
        self.invalid_pdf_content = b"This is not a PDF file"

        # Create temporary files
        self.temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.temp_pdf.write(self.test_pdf_content)
        self.temp_pdf.close()

        self.large_temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.large_temp_pdf.write(self.large_pdf_content)
        self.large_temp_pdf.close()

        self.invalid_temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.invalid_temp_pdf.write(self.invalid_pdf_content)
        self.invalid_temp_pdf.close()

    def teardown_method(self):
        """Clean up test files."""
        for temp_file in [self.temp_pdf, self.large_temp_pdf, self.invalid_temp_pdf]:
            with contextlib.suppress(FileNotFoundError):
                Path(temp_file.name).unlink()

    @pytest.mark.e2e
    def test_complete_pdf_upload_and_delivery_workflow(self):
        """Test complete workflow from upload to secure delivery."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment variables
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            # Mock Supabase client
            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock successful upload
            mock_client.storage.from_.return_value.upload.return_value = {
                "path": "reports/user123/report456_20240101_120000.pdf"
            }

            # Mock signed URL generation
            mock_client.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://test.supabase.co/storage/v1/object/sign/reports/file.pdf?token=abc123"
            }

            # Create storage instance
            storage = SupabaseStorage(bucket_name="test-reports")

            # Mock other dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure mocks for successful workflow
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_rate_limiter.check_rate_limit.return_value.allowed = True
            mock_link_generator.generate_secure_report_url.return_value = {
                "url": "https://secure-link.example.com/report123",
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
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

            # Execute complete workflow
            result = delivery_service.upload_and_deliver_report(
                pdf_path=self.temp_pdf.name,
                report_id="report456",
                user_id="user123",
                user_email="test@example.com",
                purchase_id="purchase789"
            )

            # Verify workflow completion
            assert result["success"] is True
            assert "storage_path" in result
            assert "secure_url" in result
            assert "expires_at" in result

            # Verify all components were called
            mock_secure_validator.validate_access.assert_called_once()
            mock_access_control.check_permission.assert_called_once()
            mock_rate_limiter.check_rate_limit.assert_called_once()
            mock_email_service.send_email.assert_called_once()
            mock_audit_logger.log_access_granted.assert_called_once()

    @pytest.mark.e2e
    def test_stripe_webhook_pdf_delivery_integration(self):
        """Test PDF delivery triggered by Stripe webhook."""
        # Mock Stripe webhook payload
        stripe_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "payment_status": "paid",
                    "customer_email": "customer@example.com",
                    "metadata": {
                        "report_id": "report789",
                        "user_id": "user456"
                    }
                }
            }
        }

        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env, \
             patch("leadfactory.services.payment_service.stripe") as mock_stripe:

            # Mock environment and Supabase
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_client.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://test.supabase.co/storage/v1/object/sign/reports/file.pdf?token=webhook123"
            }

            # Mock Stripe webhook verification
            mock_stripe.Webhook.construct_event.return_value = stripe_payload

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
            mock_link_generator.generate_secure_report_url.return_value = {
                "url": "https://secure-webhook-link.example.com/report789",
                "expires_at": (datetime.utcnow() + timedelta(hours=48)).isoformat() + "Z"
            }

            # Create services
            storage = SupabaseStorage(bucket_name="webhook-reports")
            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # Simulate webhook processing
            result = delivery_service.process_payment_webhook(stripe_payload)

            # Verify webhook processing
            assert result["success"] is True
            assert result["report_id"] == "report789"
            assert result["user_id"] == "user456"
            assert "secure_url" in result

            # Verify email delivery was triggered
            mock_email_service.send_email.assert_called_once()
            email_call_args = mock_email_service.send_email.call_args[1]
            assert email_call_args["to_email"] == "customer@example.com"
            assert "secure-webhook-link.example.com" in email_call_args["html_content"]

    @pytest.mark.e2e
    def test_url_expiration_validation(self):
        """Test URL expiration validation in end-to-end workflow."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Test expired URL
            expired_time = datetime.utcnow() - timedelta(hours=1)
            mock_client.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://test.supabase.co/storage/v1/object/sign/reports/expired.pdf?token=expired123"
            }

            storage = SupabaseStorage(bucket_name="expiry-test")

            # Generate URL with past expiration
            with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
                mock_datetime.utcnow.return_value = expired_time

                url_result = storage.generate_secure_report_url(
                    "test-report.pdf",
                    expires_in_hours=1
                )

                # Verify expiration timestamp is in the past
                expires_at = datetime.fromisoformat(url_result["expires_at"].replace("Z", ""))
                assert expires_at < datetime.utcnow()

            # Test URL validation with expired timestamp
            mock_secure_validator = Mock()
            mock_secure_validator.validate_access.return_value.is_valid = False
            mock_secure_validator.validate_access.return_value.reason = "URL expired"

            # Mock other dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # Attempt to access expired URL
            access_result = delivery_service.validate_and_get_report_access(
                report_id="expired-report",
                user_id="user123",
                access_token="expired123"
            )

            # Verify access denied for expired URL
            assert access_result["success"] is False
            assert "expired" in access_result["reason"].lower()

    @pytest.mark.e2e
    def test_large_file_handling_workflow(self):
        """Test complete workflow with large PDF files."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Mock large file upload with chunked handling
            mock_client.storage.from_.return_value.upload.return_value = {
                "path": "reports/large/large_report_20240101_120000.pdf"
            }

            storage = SupabaseStorage(bucket_name="large-files")

            # Test large file upload
            result = storage.upload_pdf_report(
                pdf_path=self.large_temp_pdf.name,
                report_id="large_report",
                user_id="user_large",
                purchase_id="purchase_large"
            )

            # Verify large file was handled
            assert result["storage_path"] == "reports/large/large_report_20240101_120000.pdf"
            assert result["size_bytes"] == len(self.large_pdf_content)
            assert result["content_type"] == "application/pdf"

            # Verify upload was called with correct parameters
            upload_call = mock_client.storage.from_.return_value.upload.call_args
            assert upload_call is not None

    @pytest.mark.e2e
    def test_invalid_pdf_handling_workflow(self):
        """Test workflow behavior with invalid PDF files."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            storage = SupabaseStorage(bucket_name="validation-test")

            # Mock dependencies with validation
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure validation to reject invalid PDF
            mock_secure_validator.validate_access.return_value.is_valid = False
            mock_secure_validator.validate_access.return_value.reason = "Invalid PDF format"

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # Attempt to upload invalid PDF
            with pytest.raises(ValueError, match="Invalid PDF"):
                delivery_service.upload_and_deliver_report(
                    pdf_path=self.invalid_temp_pdf.name,
                    report_id="invalid_report",
                    user_id="user_invalid",
                    user_email="invalid@example.com",
                    purchase_id="purchase_invalid"
                )

            # Verify audit logging for invalid file
            mock_audit_logger.log_security_violation.assert_called_once()

    @pytest.mark.e2e
    @pytest.mark.skip(reason="Temporarily disabled due to CI hanging - needs threading fix")
    def test_concurrent_access_handling(self):
        """Test system behavior under concurrent access scenarios."""
        import queue
        import threading

        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_client.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://test.supabase.co/storage/v1/object/sign/reports/concurrent.pdf?token=concurrent123"
            }

            storage = SupabaseStorage(bucket_name="concurrent-test")

            # Mock dependencies
            mock_email_service = Mock()
            mock_link_generator = Mock()
            mock_secure_validator = Mock()
            mock_access_control = Mock()
            mock_rate_limiter = Mock()
            mock_audit_logger = Mock()

            # Configure rate limiting for concurrent access
            call_count = 0
            def rate_limit_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                result = Mock()
                result.allowed = call_count <= 3  # Allow first 3 calls
                result.reason = "Rate limit exceeded" if call_count > 3 else None
                return result

            mock_rate_limiter.check_rate_limit.side_effect = rate_limit_side_effect
            mock_secure_validator.validate_access.return_value.is_valid = True
            mock_access_control.check_permission.return_value = True
            mock_link_generator.generate_secure_report_url.return_value = {
                "url": "https://concurrent-link.example.com/report",
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
            }

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # Create concurrent access requests
            results_queue = queue.Queue()

            def access_report(thread_id):
                try:
                    result = delivery_service.validate_and_get_report_access(
                        report_id=f"concurrent_report_{thread_id}",
                        user_id=f"user_{thread_id}",
                        access_token=f"token_{thread_id}"
                    )
                    results_queue.put((thread_id, result))
                except Exception as e:
                    results_queue.put((thread_id, {"error": str(e)}))

            # Launch concurrent threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=access_report, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete with timeout
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
                except Exception:
                    timeout_count += 1
                    time.sleep(0.1)

            # Verify rate limiting behavior
            successful_requests = [r for r in results if r[1].get("success", False)]
            rate_limited_requests = [r for r in results if not r[1].get("success", False)]

            assert len(successful_requests) <= 3  # Rate limit should kick in
            assert len(rate_limited_requests) >= 2  # Some requests should be rate limited

    @pytest.mark.e2e
    def test_error_recovery_and_resilience(self):
        """Test system resilience and error recovery mechanisms."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create_client, \
             patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:

            # Mock environment
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key"
            }.get(key)

            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Simulate storage failure then recovery
            call_count = 0
            def upload_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Storage temporarily unavailable")
                return {"path": "reports/recovered/report_recovered.pdf"}

            mock_client.storage.from_.return_value.upload.side_effect = upload_side_effect

            storage = SupabaseStorage(bucket_name="resilience-test")

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
            mock_link_generator.generate_secure_report_url.return_value = {
                "url": "https://recovered-link.example.com/report",
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
            }

            delivery_service = ReportDeliveryService(
                storage=storage,
                email_service=mock_email_service,
                link_generator=mock_link_generator,
                secure_validator=mock_secure_validator,
                access_control=mock_access_control,
                rate_limiter=mock_rate_limiter,
                audit_logger=mock_audit_logger
            )

            # First attempt should fail
            with pytest.raises(Exception, match="Storage temporarily unavailable"):
                delivery_service.upload_and_deliver_report(
                    pdf_path=self.temp_pdf.name,
                    report_id="resilience_report",
                    user_id="user_resilience",
                    user_email="resilience@example.com",
                    purchase_id="purchase_resilience"
                )

            # Second attempt should succeed (simulating retry logic)
            result = delivery_service.upload_and_deliver_report(
                pdf_path=self.temp_pdf.name,
                report_id="resilience_report",
                user_id="user_resilience",
                user_email="resilience@example.com",
                purchase_id="purchase_resilience"
            )

            # Verify recovery
            assert result["success"] is True
            assert "recovered" in result["storage_path"]

            # Verify error was logged
            mock_audit_logger.log_security_violation.assert_called()
