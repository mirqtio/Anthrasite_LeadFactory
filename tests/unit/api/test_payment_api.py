"""
Unit tests for Payment API endpoints.

Tests FastAPI payment endpoints including checkout session creation,
webhook handling, and payment status retrieval.
"""

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from leadfactory.api.payment_api import get_payment_service
from leadfactory.app import app
from leadfactory.services.payment_service import PaymentStatus


@pytest.fixture
def mock_payment_service():
    """Mock payment service."""
    return Mock()


@pytest.fixture
def client(mock_payment_service):
    """Create test client with mocked payment service."""
    app.dependency_overrides[get_payment_service] = lambda: mock_payment_service
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPaymentAPI:
    """Test cases for payment API endpoints."""

    def test_create_checkout_session_success(self, client, mock_payment_service):
        """Test successful checkout session creation."""
        # Setup mock
        mock_payment_service.create_checkout_session.return_value = {
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/test",
            "payment_intent_id": "pi_test_123",
            "publishable_key": "pk_test_123",
        }

        # Make request
        response = client.post(
            "/api/v1/payments/checkout",
            json={
                "customer_email": "test@example.com",
                "customer_name": "Test User",
                "audit_type": "seo",
                "amount": 9900,
                "metadata": {"source": "test"},
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "cs_test_123"
        assert data["session_url"] == "https://checkout.stripe.com/test"
        assert data["payment_intent_id"] == "pi_test_123"
        assert data["publishable_key"] == "pk_test_123"

        # Verify service call
        mock_payment_service.create_checkout_session.assert_called_once_with(
            customer_email="test@example.com",
            customer_name="Test User",
            audit_type="seo",
            amount=9900,
            metadata={"source": "test"},
        )

    def test_create_checkout_session_invalid_audit_type(
        self, client, mock_payment_service
    ):
        """Test checkout session creation with invalid audit type."""
        response = client.post(
            "/api/v1/payments/checkout",
            json={
                "customer_email": "test@example.com",
                "customer_name": "Test User",
                "audit_type": "invalid_type",
                "amount": 9900,
            },
        )

        assert response.status_code == 400
        assert "Invalid audit type" in response.json()["detail"]

    def test_create_checkout_session_invalid_amount(self, client, mock_payment_service):
        """Test checkout session creation with invalid amount."""
        # Test amount too low
        response = client.post(
            "/api/v1/payments/checkout",
            json={
                "customer_email": "test@example.com",
                "customer_name": "Test User",
                "audit_type": "seo",
                "amount": 500,  # Below $10 minimum
            },
        )

        assert response.status_code == 400
        assert "Amount must be between" in response.json()["detail"]

        # Test amount too high
        response = client.post(
            "/api/v1/payments/checkout",
            json={
                "customer_email": "test@example.com",
                "customer_name": "Test User",
                "audit_type": "seo",
                "amount": 1500000,  # Above $10,000 maximum
            },
        )

        assert response.status_code == 400
        assert "Amount must be between" in response.json()["detail"]

    def test_create_checkout_session_service_error(self, client, mock_payment_service):
        """Test checkout session creation with service error."""
        mock_payment_service.create_checkout_session.side_effect = Exception(
            "Service error"
        )

        response = client.post(
            "/api/v1/payments/checkout",
            json={
                "customer_email": "test@example.com",
                "customer_name": "Test User",
                "audit_type": "seo",
                "amount": 9900,
            },
        )

        assert response.status_code == 500
        assert "Failed to create checkout session" in response.json()["detail"]

    def test_handle_stripe_webhook_success(self, client, mock_payment_service):
        """Test successful webhook handling."""
        response = client.post(
            "/api/v1/payments/webhook",
            data="test_payload",
            headers={"stripe-signature": "test_signature"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_handle_stripe_webhook_missing_signature(
        self, client, mock_payment_service
    ):
        """Test webhook handling with missing signature."""
        response = client.post("/api/v1/payments/webhook", data="test_payload")

        assert response.status_code == 400
        assert "Missing Stripe signature" in response.json()["detail"]

    def test_get_payment_status_success(self, client, mock_payment_service):
        """Test successful payment status retrieval."""
        mock_payment_service.get_payment_status.return_value = {
            "id": "pi_test_123",
            "status": PaymentStatus.SUCCEEDED.value,
            "customer_email": "test@example.com",
            "customer_name": "Test User",
            "amount": 9900,
            "currency": "usd",
            "audit_type": "seo",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        response = client.get("/api/v1/payments/status/pi_test_123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pi_test_123"
        assert data["status"] == PaymentStatus.SUCCEEDED.value
        assert data["customer_email"] == "test@example.com"

    def test_get_payment_status_not_found(self, client, mock_payment_service):
        """Test payment status retrieval for non-existent payment."""
        mock_payment_service.get_payment_status.return_value = None

        response = client.get("/api/v1/payments/status/pi_nonexistent")

        assert response.status_code == 404
        assert "Payment not found" in response.json()["detail"]

    def test_get_customer_payments_success(self, client, mock_payment_service):
        """Test successful customer payments retrieval."""
        mock_payment_service.get_payments_by_email.return_value = [
            {
                "id": "pi_test_123",
                "status": PaymentStatus.SUCCEEDED.value,
                "amount": 9900,
                "currency": "usd",
                "audit_type": "seo",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        ]

        response = client.get("/api/v1/payments/customer/test@example.com")

        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        assert len(data["payments"]) == 1
        assert data["payments"][0]["id"] == "pi_test_123"

    def test_refund_payment_success(self, client, mock_payment_service):
        """Test successful payment refund."""
        mock_payment_service.refund_payment.return_value = {
            "status": "refunded",
            "refund_id": "re_test_123",
            "amount": 9900,
            "payment_id": "pi_test_123",
        }

        response = client.post(
            "/api/v1/payments/refund/pi_test_123", json={"amount": 9900}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "refunded"
        assert data["refund_id"] == "re_test_123"

    def test_refund_payment_invalid_payment(self, client, mock_payment_service):
        """Test refund for invalid payment."""
        mock_payment_service.refund_payment.side_effect = ValueError(
            "Payment not found"
        )

        response = client.post("/api/v1/payments/refund/pi_nonexistent", json={})

        assert response.status_code == 400
        assert "Payment not found" in response.json()["detail"]

    def test_health_check(self, client):
        """Test payment API health check."""
        response = client.get("/api/v1/payments/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "payment_api"
        assert "timestamp" in data

    def test_get_pricing(self, client):
        """Test pricing information endpoint."""
        response = client.get("/api/v1/payments/pricing")

        assert response.status_code == 200
        data = response.json()
        assert "pricing" in data

        pricing = data["pricing"]
        assert "seo" in pricing
        assert "security" in pricing
        assert "performance" in pricing
        assert "accessibility" in pricing
        assert "comprehensive" in pricing

        # Verify SEO pricing structure
        seo_pricing = pricing["seo"]
        assert seo_pricing["name"] == "SEO Audit"
        assert seo_pricing["price"] == 9900
        assert seo_pricing["currency"] == "usd"
        assert "description" in seo_pricing
