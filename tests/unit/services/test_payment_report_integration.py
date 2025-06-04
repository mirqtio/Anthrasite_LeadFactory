"""
Integration tests for Stripe payment service with report delivery.

Tests the complete flow from successful payment webhook to report delivery.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import stripe

from leadfactory.services.payment_service import (
    Payment,
    PaymentConfig,
    PaymentStatus,
    StripePaymentService,
)


class TestPaymentReportIntegration:
    """Test cases for payment service with report delivery integration."""

    @pytest.fixture
    def payment_config(self):
        """Create test payment configuration."""
        return PaymentConfig(
            stripe_secret_key="sk_test_123",
            stripe_publishable_key="pk_test_123",
            webhook_secret="whsec_test_123",
        )

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch(
            "leadfactory.services.payment_service.sessionmaker"
        ) as mock_sessionmaker:
            mock_session = Mock()
            mock_sessionmaker.return_value = Mock(return_value=mock_session)
            yield mock_session

    @pytest.fixture
    def mock_report_delivery(self):
        """Mock report delivery service."""
        with patch(
            "leadfactory.services.payment_service.ReportDeliveryService"
        ) as mock:
            delivery_instance = Mock()
            mock.return_value = delivery_instance
            yield delivery_instance

    @pytest.fixture
    def mock_stripe(self):
        """Mock Stripe API calls."""
        with patch("leadfactory.services.payment_service.stripe") as mock_stripe:
            # Keep the real error classes
            mock_stripe.error = stripe.error
            yield mock_stripe

    @pytest.fixture
    def payment_service(self, payment_config, mock_db_session, mock_report_delivery):
        """Create payment service with mocked dependencies."""
        with (
            patch("leadfactory.services.payment_service.create_engine"),
            patch("leadfactory.services.payment_service.Base"),
        ):
            service = StripePaymentService(payment_config, "sqlite:///:memory:")
            mock_session_local = Mock()
            mock_session_local.return_value.__enter__ = Mock(
                return_value=mock_db_session
            )
            mock_session_local.return_value.__exit__ = Mock(return_value=None)
            service.SessionLocal = mock_session_local
            return service

    @pytest.fixture
    def sample_payment(self):
        """Create sample payment record."""
        payment = Mock(spec=Payment)
        payment.id = "payment-123"
        payment.stripe_payment_intent_id = "pi_test_123"
        payment.customer_email = "test@example.com"
        payment.customer_name = "Test Customer"
        payment.business_name = "Test Business LLC"
        payment.amount = 9900  # $99.00
        payment.currency = "usd"
        payment.audit_type = "financial"
        payment.status = PaymentStatus.PENDING.value
        payment.payment_metadata = "{}"
        return payment

    def test_successful_payment_triggers_report_delivery(
        self,
        payment_service,
        mock_db_session,
        mock_report_delivery,
        mock_stripe,
        sample_payment,
    ):
        """Test that successful payment webhook triggers report delivery."""
        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            sample_payment
        )

        # Setup Stripe mocks
        mock_stripe.Charge.list.return_value.data = [
            {
                "id": "ch_test_123",
                "amount": 9900,
                "amount_captured": 9900,
                "balance_transaction": "txn_test_123",
                "currency": "usd",
                "metadata": {},
                "receipt_url": "https://pay.stripe.com/receipts/test",
            }
        ]

        mock_stripe.BalanceTransaction.retrieve.return_value = {
            "fee": 317,  # $3.17 Stripe fee
            "net": 9583,
            "fee_details": [],
        }

        # Setup report delivery mock
        mock_report_delivery.upload_and_deliver_report.return_value = {
            "status": "delivered",
            "report_id": "audit_financial_payment-123_1234567890",
            "storage_path": "reports/test@example.com/audit_financial_payment-123_1234567890.pdf",
            "secure_token": "jwt-token-123",
            "signed_url": "https://supabase.co/storage/signed-url",
            "expires_at": "2023-06-04T12:00:00Z",
            "email_sent": True,
            "delivered_at": "2023-06-01T12:00:00Z",
        }

        # Mock financial tracker
        with patch(
            "leadfactory.services.payment_service.financial_tracker"
        ) as mock_tracker:
            # Execute webhook handling
            payment_intent_data = {
                "id": "pi_test_123",
                "amount": 9900,
                "currency": "usd",
                "status": "succeeded",
            }

            result = payment_service._handle_payment_succeeded(payment_intent_data)

        # Verify payment status was updated
        assert sample_payment.status == PaymentStatus.SUCCEEDED.value
        assert sample_payment.webhook_received is True
        mock_db_session.commit.assert_called()

        # Verify financial tracking was called
        mock_tracker.record_stripe_payment.assert_called_once()

        # Verify report delivery was triggered
        mock_report_delivery.upload_and_deliver_report.assert_called_once()
        delivery_call = mock_report_delivery.upload_and_deliver_report.call_args

        # Check delivery arguments
        assert delivery_call[1]["user_id"] == "test@example.com"
        assert delivery_call[1]["user_email"] == "test@example.com"
        assert delivery_call[1]["purchase_id"] == "pi_test_123"
        assert delivery_call[1]["business_name"] == "Test Customer"
        assert delivery_call[1]["expiry_hours"] == 72

        # Verify report ID format
        report_id = delivery_call[1]["report_id"]
        assert report_id.startswith("audit_financial_payment-123_")

        # Verify PDF path was provided
        pdf_path = delivery_call[1]["pdf_path"]
        assert pdf_path.endswith(".pdf")
        assert "audit_financial_payment-123_" in pdf_path

        # Verify payment metadata was updated with delivery info
        updated_metadata = json.loads(sample_payment.payment_metadata)
        assert updated_metadata["report_delivered"] is True
        delivery_call = mock_report_delivery.upload_and_deliver_report.call_args
        expected_report_id = delivery_call[1]["report_id"]
        assert updated_metadata["report_id"] == expected_report_id
        assert updated_metadata["delivery_status"] == "delivered"
        assert (
            updated_metadata["storage_path"]
            == "reports/test@example.com/audit_financial_payment-123_1234567890.pdf"
        )

        # Verify webhook response
        assert result["status"] == "success"
        assert result["customer_email"] == "test@example.com"

    def test_payment_success_with_report_delivery_failure(
        self,
        payment_service,
        mock_db_session,
        mock_report_delivery,
        mock_stripe,
        sample_payment,
    ):
        """Test that payment success continues even if report delivery fails."""
        # Setup database mock
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            sample_payment
        )

        # Setup Stripe mocks
        mock_stripe.Charge.list.return_value.data = [
            {"id": "ch_test_123", "amount": 9900, "balance_transaction": "txn_test_123"}
        ]
        mock_stripe.BalanceTransaction.retrieve.return_value = {"fee": 317, "net": 9583}

        # Setup report delivery to fail
        mock_report_delivery.upload_and_deliver_report.side_effect = Exception(
            "Report delivery failed"
        )

        # Mock financial tracker
        with patch("leadfactory.services.payment_service.financial_tracker"):
            # Execute webhook handling
            payment_intent_data = {
                "id": "pi_test_123",
                "amount": 9900,
                "currency": "usd",
                "status": "succeeded",
            }

            result = payment_service._handle_payment_succeeded(payment_intent_data)

        # Verify payment was still marked as successful
        assert sample_payment.status == PaymentStatus.SUCCEEDED.value
        assert sample_payment.webhook_received is True
        mock_db_session.commit.assert_called()

        # Verify webhook response indicates success (payment processing succeeded)
        assert result["status"] == "success"
        assert result["customer_email"] == "test@example.com"

        # Verify report delivery was attempted
        mock_report_delivery.upload_and_deliver_report.assert_called_once()

    def test_pdf_generation_creates_valid_file(self, payment_service, sample_payment):
        """Test that PDF generation creates a valid file."""
        import os
        import tempfile

        # Execute PDF generation
        report_id = "test_report_123"
        pdf_path = payment_service._generate_audit_pdf(sample_payment, report_id)

        # Verify file was created
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith(".pdf")
        assert report_id in pdf_path

        # Verify file has content
        file_size = os.path.getsize(pdf_path)
        assert file_size > 0

        # Verify it's a PDF file (basic check)
        with open(pdf_path, "rb") as f:
            header = f.read(4)
            assert header == b"%PDF"

        # Cleanup
        os.unlink(pdf_path)

    def test_pdf_generation_includes_payment_details(
        self, payment_service, sample_payment
    ):
        """Test that generated PDF includes payment details."""
        import os

        # Execute PDF generation
        report_id = "test_report_456"
        pdf_path = payment_service._generate_audit_pdf(sample_payment, report_id)

        # Read PDF content (basic text extraction would require additional libraries)
        # For now, just verify the file was created with reasonable size
        file_size = os.path.getsize(pdf_path)
        assert file_size > 1000  # Should be reasonably sized with content

        # Cleanup
        os.unlink(pdf_path)

    def test_webhook_signature_verification_failure(self, payment_service, mock_stripe):
        """Test handling of webhook signature verification failure."""
        # Setup Stripe to raise signature verification error
        mock_stripe.Webhook.construct_event.side_effect = (
            stripe.error.SignatureVerificationError("Invalid signature", "sig_header")
        )

        # Execute and expect exception
        with pytest.raises(stripe.error.SignatureVerificationError):
            payment_service.handle_webhook("payload", "invalid_signature")

    def test_payment_not_found_for_webhook(
        self, payment_service, mock_db_session, mock_stripe
    ):
        """Test handling when payment record is not found for webhook."""
        # Setup database mock to return no payment
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Setup Stripe webhook mock
        mock_stripe.Webhook.construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_nonexistent_123",
                    "amount": 9900,
                    "currency": "usd",
                }
            },
        }

        # Execute webhook handling
        result = payment_service.handle_webhook("payload", "signature")

        # Verify response indicates payment not found
        assert result["status"] == "not_found"
        assert result["payment_intent_id"] == "pi_nonexistent_123"

    def test_multiple_audit_types_generate_different_reports(
        self, payment_service, mock_db_session, mock_report_delivery, mock_stripe
    ):
        """Test that different audit types generate appropriately named reports."""
        audit_types = ["financial", "operational", "compliance", "security"]

        for audit_type in audit_types:
            # Create payment for this audit type
            payment = Mock(spec=Payment)
            payment.id = f"payment-{audit_type}"
            payment.stripe_payment_intent_id = f"pi_{audit_type}_123"
            payment.customer_email = "test@example.com"
            payment.customer_name = "Test Customer"
            payment.amount = 9900
            payment.currency = "usd"
            payment.audit_type = audit_type
            payment.status = PaymentStatus.PENDING.value
            payment.payment_metadata = "{}"

            # Setup mocks
            mock_db_session.query.return_value.filter.return_value.first.return_value = payment
            mock_stripe.Charge.list.return_value.data = [
                {"id": "ch_test", "amount": 9900, "balance_transaction": "txn_test"}
            ]
            mock_stripe.BalanceTransaction.retrieve.return_value = {
                "fee": 317,
                "net": 9583,
            }
            mock_report_delivery.upload_and_deliver_report.return_value = {
                "status": "delivered"
            }

            # Mock financial tracker
            with patch("leadfactory.services.payment_service.financial_tracker"):
                # Execute
                payment_intent_data = {"id": f"pi_{audit_type}_123", "amount": 9900}
                payment_service._handle_payment_succeeded(payment_intent_data)

            # Verify report delivery was called with correct audit type in report ID
            delivery_call = mock_report_delivery.upload_and_deliver_report.call_args
            report_id = delivery_call[1]["report_id"]
            assert f"audit_{audit_type}_payment-{audit_type}_" in report_id

            # Reset mock for next iteration
            mock_report_delivery.reset_mock()

    def test_business_name_fallback_in_delivery(
        self, payment_service, mock_db_session, mock_report_delivery, mock_stripe
    ):
        """Test business name fallback when business_name is None."""
        # Create payment without business name
        payment = Mock(spec=Payment)
        payment.id = "payment-123"
        payment.stripe_payment_intent_id = "pi_test_123"
        payment.customer_email = "test@example.com"
        payment.customer_name = "Test Customer"
        payment.business_name = None  # No business name
        payment.amount = 9900
        payment.currency = "usd"
        payment.audit_type = "financial"
        payment.status = PaymentStatus.PENDING.value
        payment.payment_metadata = "{}"

        # Setup mocks
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            payment
        )
        mock_stripe.Charge.list.return_value.data = [
            {"id": "ch_test", "amount": 9900, "balance_transaction": "txn_test"}
        ]
        mock_stripe.BalanceTransaction.retrieve.return_value = {"fee": 317, "net": 9583}
        mock_report_delivery.upload_and_deliver_report.return_value = {
            "status": "delivered"
        }

        # Mock financial tracker
        with patch("leadfactory.services.payment_service.financial_tracker"):
            # Execute
            payment_intent_data = {"id": "pi_test_123", "amount": 9900}
            payment_service._handle_payment_succeeded(payment_intent_data)

        # Verify business name fallback was used
        delivery_call = mock_report_delivery.upload_and_deliver_report.call_args
        business_name = delivery_call[1]["business_name"]
        assert business_name == "Test Customer"  # Falls back to customer_name
