"""
Unit tests for Stripe payment service.

Tests payment service functionality including checkout session creation,
webhook handling, and payment status management.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leadfactory.services.payment_service import (
    Base,
    Payment,
    PaymentConfig,
    PaymentStatus,
    StripePaymentService,
)


@pytest.fixture
def payment_config():
    """Create test payment configuration."""
    return PaymentConfig(
        stripe_secret_key="sk_test_123",
        stripe_publishable_key="pk_test_123",
        webhook_secret="whsec_test_123",
        currency="usd",
        success_url="https://test.com/success",
        cancel_url="https://test.com/cancel",
    )


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def payment_service(payment_config, test_db):
    """Create payment service with test configuration."""
    with patch("stripe.api_key"), patch(
        "leadfactory.services.payment_service.ReportDeliveryService"
    ):
        service = StripePaymentService(payment_config, "sqlite:///:memory:")
        service.engine = test_db
        service.SessionLocal = sessionmaker(bind=test_db)
        return service


class TestStripePaymentService:
    """Test cases for StripePaymentService."""

    @patch("stripe.PaymentIntent.create")
    @patch("stripe.checkout.Session.create")
    def test_create_checkout_session_success(
        self, mock_session_create, mock_intent_create, payment_service
    ):
        """Test successful checkout session creation."""
        # Mock Stripe responses
        mock_intent_create.return_value = Mock(id="pi_test_123")
        mock_session_create.return_value = Mock(
            id="cs_test_123", url="https://checkout.stripe.com/test"
        )

        # Create checkout session
        result = payment_service.create_checkout_session(
            customer_email="test@example.com",
            customer_name="Test User",
            audit_type="seo",
            amount=9900,
            metadata={"source": "test"},
        )

        # Verify result
        assert result["session_id"] == "cs_test_123"
        assert result["session_url"] == "https://checkout.stripe.com/test"
        assert result["payment_intent_id"] == "pi_test_123"
        assert result["publishable_key"] == "pk_test_123"

        # Verify Stripe calls
        mock_intent_create.assert_called_once()
        mock_session_create.assert_called_once()

        # Verify database record
        with payment_service.SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == "pi_test_123").first()
            assert payment is not None
            assert payment.customer_email == "test@example.com"
            assert payment.amount == 9900
            assert payment.status == PaymentStatus.PENDING.value

    @patch("stripe.PaymentIntent.create")
    def test_create_checkout_session_stripe_error(
        self, mock_intent_create, payment_service
    ):
        """Test checkout session creation with Stripe error."""
        import stripe

        mock_intent_create.side_effect = stripe.error.StripeError("Test error")

        with pytest.raises(stripe.error.StripeError):
            payment_service.create_checkout_session(
                customer_email="test@example.com",
                customer_name="Test User",
                audit_type="seo",
                amount=9900,
            )

    @patch("stripe.Webhook.construct_event")
    def test_handle_webhook_payment_succeeded(
        self, mock_construct_event, payment_service
    ):
        """Test webhook handling for successful payment."""
        # Create test payment record
        with payment_service.SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.PENDING.value,
                audit_type="seo",
            )
            db.add(payment)
            db.commit()

        # Mock webhook event
        mock_construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123"}},
        }

        # Handle webhook
        result = payment_service.handle_webhook("test_payload", "test_signature")

        # Verify result
        assert result["status"] == "success"
        assert result["payment_id"] == "pi_test_123"

        # Verify database update
        with payment_service.SessionLocal() as db:
            updated_payment = (
                db.query(Payment).filter(Payment.id == "pi_test_123").first()
            )
            assert updated_payment.status == PaymentStatus.SUCCEEDED.value
            assert updated_payment.webhook_received is True

    @patch("stripe.Webhook.construct_event")
    def test_handle_webhook_payment_failed(self, mock_construct_event, payment_service):
        """Test webhook handling for failed payment."""
        # Create test payment record
        with payment_service.SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.PENDING.value,
                audit_type="seo",
            )
            db.add(payment)
            db.commit()

        # Mock webhook event
        mock_construct_event.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_test_123"}},
        }

        # Handle webhook
        result = payment_service.handle_webhook("test_payload", "test_signature")

        # Verify result
        assert result["status"] == "failed"
        assert result["payment_id"] == "pi_test_123"

        # Verify database update
        with payment_service.SessionLocal() as db:
            updated_payment = (
                db.query(Payment).filter(Payment.id == "pi_test_123").first()
            )
            assert updated_payment.status == PaymentStatus.FAILED.value
            assert updated_payment.webhook_received is True

    @patch("stripe.Webhook.construct_event")
    def test_handle_webhook_signature_error(
        self, mock_construct_event, payment_service
    ):
        """Test webhook handling with signature verification error."""
        import stripe

        mock_construct_event.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "test_signature"
        )

        with pytest.raises(stripe.error.SignatureVerificationError):
            payment_service.handle_webhook("test_payload", "test_signature")

    def test_get_payment_status_existing(self, payment_service):
        """Test getting payment status for existing payment."""
        # Create test payment record
        with payment_service.SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.SUCCEEDED.value,
                audit_type="seo",
            )
            db.add(payment)
            db.commit()

        # Get payment status
        result = payment_service.get_payment_status("pi_test_123")

        # Verify result
        assert result is not None
        assert result["id"] == "pi_test_123"
        assert result["status"] == PaymentStatus.SUCCEEDED.value
        assert result["customer_email"] == "test@example.com"
        assert result["amount"] == 9900

    def test_get_payment_status_not_found(self, payment_service):
        """Test getting payment status for non-existent payment."""
        result = payment_service.get_payment_status("pi_nonexistent")
        assert result is None

    def test_get_payments_by_email(self, payment_service):
        """Test getting payments by customer email."""
        # Create test payment records
        with payment_service.SessionLocal() as db:
            payment1 = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.SUCCEEDED.value,
                audit_type="seo",
            )
            payment2 = Payment(
                id="pi_test_456",
                stripe_payment_intent_id="pi_test_456",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=14900,
                currency="usd",
                status=PaymentStatus.PENDING.value,
                audit_type="security",
            )
            db.add_all([payment1, payment2])
            db.commit()

        # Get payments by email
        result = payment_service.get_payments_by_email("test@example.com")

        # Verify result
        assert len(result) == 2
        assert result[0]["id"] == "pi_test_123"
        assert result[1]["id"] == "pi_test_456"

    @patch("stripe.Refund.create")
    def test_refund_payment_success(self, mock_refund_create, payment_service):
        """Test successful payment refund."""
        # Create test payment record
        with payment_service.SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.SUCCEEDED.value,
                audit_type="seo",
            )
            db.add(payment)
            db.commit()

        # Mock Stripe refund response
        mock_refund_create.return_value = Mock(id="re_test_123", amount=9900)

        # Refund payment
        result = payment_service.refund_payment("pi_test_123")

        # Verify result
        assert result["status"] == "refunded"
        assert result["refund_id"] == "re_test_123"
        assert result["amount"] == 9900

        # Verify database update
        with payment_service.SessionLocal() as db:
            updated_payment = (
                db.query(Payment).filter(Payment.id == "pi_test_123").first()
            )
            assert updated_payment.status == PaymentStatus.REFUNDED.value

    def test_refund_payment_not_found(self, payment_service):
        """Test refunding non-existent payment."""
        with pytest.raises(ValueError, match="Payment not found"):
            payment_service.refund_payment("pi_nonexistent")

    def test_refund_payment_invalid_status(self, payment_service):
        """Test refunding payment with invalid status."""
        # Create test payment record with pending status
        with payment_service.SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.PENDING.value,
                audit_type="seo",
            )
            db.add(payment)
            db.commit()

        with pytest.raises(ValueError, match="Cannot refund payment with status"):
            payment_service.refund_payment("pi_test_123")


class TestPaymentConfig:
    """Test cases for PaymentConfig."""

    def test_payment_config_creation(self):
        """Test payment configuration creation."""
        config = PaymentConfig(
            stripe_secret_key="sk_test_123",
            stripe_publishable_key="pk_test_123",
            webhook_secret="whsec_test_123",
        )

        assert config.stripe_secret_key == "sk_test_123"
        assert config.stripe_publishable_key == "pk_test_123"
        assert config.webhook_secret == "whsec_test_123"
        assert config.currency == "usd"  # Default value

    def test_payment_config_custom_values(self):
        """Test payment configuration with custom values."""
        config = PaymentConfig(
            stripe_secret_key="sk_test_123",
            stripe_publishable_key="pk_test_123",
            webhook_secret="whsec_test_123",
            currency="eur",
            success_url="https://custom.com/success",
            cancel_url="https://custom.com/cancel",
        )

        assert config.currency == "eur"
        assert config.success_url == "https://custom.com/success"
        assert config.cancel_url == "https://custom.com/cancel"


class TestPaymentModel:
    """Test cases for Payment database model."""

    def test_payment_model_creation(self, test_db):
        """Test payment model creation and persistence."""
        SessionLocal = sessionmaker(bind=test_db)

        with SessionLocal() as db:
            payment = Payment(
                id="pi_test_123",
                stripe_payment_intent_id="pi_test_123",
                customer_email="test@example.com",
                customer_name="Test User",
                amount=9900,
                currency="usd",
                status=PaymentStatus.PENDING.value,
                audit_type="seo",
                metadata='{"source": "test"}',
            )
            db.add(payment)
            db.commit()

            # Retrieve and verify
            retrieved = db.query(Payment).filter(Payment.id == "pi_test_123").first()
            assert retrieved is not None
            assert retrieved.customer_email == "test@example.com"
            assert retrieved.amount == 9900
            assert retrieved.status == PaymentStatus.PENDING.value
