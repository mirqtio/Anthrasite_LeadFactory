"""
Stripe Payment Service for Audit Sales

Handles Stripe checkout integration, payment intents, and webhook processing
for direct-to-SMB audit sales.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import stripe
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Configure logging
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()


class PaymentStatus(Enum):
    """Payment status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


@dataclass
class PaymentConfig:
    """Configuration for payment service."""

    stripe_secret_key: str
    stripe_publishable_key: str
    webhook_secret: str
    currency: str = "usd"
    success_url: str = "https://yourdomain.com/success"
    cancel_url: str = "https://yourdomain.com/cancel"


class Payment(Base):
    """Payment record model."""

    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    stripe_payment_intent_id = Column(String, unique=True, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_name = Column(String)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String, default="usd")
    status = Column(String, nullable=False)
    audit_type = Column(String, nullable=False)
    payment_metadata = Column(Text)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    stripe_session_id = Column(String)
    webhook_received = Column(Boolean, default=False)


class StripePaymentService:
    """Service for handling Stripe payments and audit sales."""

    def __init__(self, config: PaymentConfig, database_url: str):
        """Initialize the payment service."""
        self.config = config
        stripe.api_key = config.stripe_secret_key

        # Database setup
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        logger.info("Stripe payment service initialized")

    def create_checkout_session(
        self,
        customer_email: str,
        customer_name: str,
        audit_type: str,
        amount: int,  # Amount in cents
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session for audit purchase."""
        try:
            # Create payment intent first
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=self.config.currency,
                metadata={
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                    "audit_type": audit_type,
                    **(metadata or {}),
                },
            )

            # Create checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": self.config.currency,
                            "product_data": {
                                "name": f"{audit_type.title()} Audit Report",
                                "description": f"Professional {audit_type} audit report for your business",
                            },
                            "unit_amount": amount,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=self.config.success_url
                + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=self.config.cancel_url,
                customer_email=customer_email,
                payment_intent_data={
                    "metadata": {
                        "customer_email": customer_email,
                        "customer_name": customer_name,
                        "audit_type": audit_type,
                        **(metadata or {}),
                    }
                },
            )

            # Store payment record
            with self.SessionLocal() as db:
                payment = Payment(
                    id=payment_intent.id,
                    stripe_payment_intent_id=payment_intent.id,
                    stripe_session_id=session.id,
                    customer_email=customer_email,
                    customer_name=customer_name,
                    amount=amount,
                    currency=self.config.currency,
                    status=PaymentStatus.PENDING.value,
                    audit_type=audit_type,
                    payment_metadata=str(metadata) if metadata else None,
                )
                db.add(payment)
                db.commit()

            logger.info(f"Created checkout session for {customer_email}: {session.id}")

            return {
                "session_id": session.id,
                "session_url": session.url,
                "payment_intent_id": payment_intent.id,
                "publishable_key": self.config.stripe_publishable_key,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise

    def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.config.webhook_secret
            )

            logger.info(f"Received webhook event: {event['type']}")

            if event["type"] == "payment_intent.succeeded":
                return self._handle_payment_succeeded(event["data"]["object"])
            elif event["type"] == "payment_intent.payment_failed":
                return self._handle_payment_failed(event["data"]["object"])
            elif event["type"] == "checkout.session.completed":
                return self._handle_checkout_completed(event["data"]["object"])
            else:
                logger.info(f"Unhandled webhook event type: {event['type']}")
                return {"status": "ignored", "event_type": event["type"]}

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            raise

    def _handle_payment_succeeded(
        self, payment_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle successful payment."""
        payment_intent_id = payment_intent["id"]

        with self.SessionLocal() as db:
            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if payment:
                payment.status = PaymentStatus.SUCCEEDED.value
                payment.webhook_received = True
                payment.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Payment succeeded: {payment_intent_id}")

                # Trigger audit report generation
                self._trigger_audit_generation(payment)

                return {
                    "status": "success",
                    "payment_id": payment.id,
                    "customer_email": payment.customer_email,
                }
            else:
                logger.warning(
                    f"Payment record not found for intent: {payment_intent_id}"
                )
                return {"status": "not_found", "payment_intent_id": payment_intent_id}

    def _handle_payment_failed(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment."""
        payment_intent_id = payment_intent["id"]

        with self.SessionLocal() as db:
            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if payment:
                payment.status = PaymentStatus.FAILED.value
                payment.webhook_received = True
                payment.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Payment failed: {payment_intent_id}")

                return {
                    "status": "failed",
                    "payment_id": payment.id,
                    "customer_email": payment.customer_email,
                }
            else:
                logger.warning(
                    f"Payment record not found for intent: {payment_intent_id}"
                )
                return {"status": "not_found", "payment_intent_id": payment_intent_id}

    def _handle_checkout_completed(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completed checkout session."""
        session_id = session["id"]
        payment_intent_id = session.get("payment_intent")

        logger.info(f"Checkout session completed: {session_id}")

        if payment_intent_id:
            with self.SessionLocal() as db:
                payment = (
                    db.query(Payment)
                    .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                    .first()
                )

                if payment:
                    payment.status = PaymentStatus.PROCESSING.value
                    payment.updated_at = datetime.utcnow()
                    db.commit()

        return {"status": "completed", "session_id": session_id}

    def _trigger_audit_generation(self, payment: Payment) -> None:
        """Trigger audit report generation after successful payment."""
        # This will be implemented when we create the PDF generation service
        logger.info(f"Triggering audit generation for payment: {payment.id}")
        # TODO: Integrate with PDF generation service

    def get_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment status by ID."""
        with self.SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()

            if payment:
                return {
                    "id": payment.id,
                    "status": payment.status,
                    "customer_email": payment.customer_email,
                    "customer_name": payment.customer_name,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "audit_type": payment.audit_type,
                    "created_at": payment.created_at.isoformat(),
                    "updated_at": payment.updated_at.isoformat(),
                }
            return None

    def get_payments_by_email(self, email: str) -> list[Dict[str, Any]]:
        """Get all payments for a customer email."""
        with self.SessionLocal() as db:
            payments = db.query(Payment).filter(Payment.customer_email == email).all()

            return [
                {
                    "id": payment.id,
                    "status": payment.status,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "audit_type": payment.audit_type,
                    "created_at": payment.created_at.isoformat(),
                    "updated_at": payment.updated_at.isoformat(),
                }
                for payment in payments
            ]

    def refund_payment(
        self, payment_id: str, amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """Refund a payment."""
        with self.SessionLocal() as db:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()

            if not payment:
                raise ValueError(f"Payment not found: {payment_id}")

            if payment.status != PaymentStatus.SUCCEEDED.value:
                raise ValueError(f"Cannot refund payment with status: {payment.status}")

            try:
                refund = stripe.Refund.create(
                    payment_intent=payment.stripe_payment_intent_id,
                    amount=amount,  # If None, refunds full amount
                )

                payment.status = PaymentStatus.REFUNDED.value
                payment.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Refunded payment: {payment_id}")

                return {
                    "status": "refunded",
                    "refund_id": refund.id,
                    "amount": refund.amount,
                    "payment_id": payment_id,
                }

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error refunding payment: {str(e)}")
                raise


def create_payment_service() -> StripePaymentService:
    """Factory function to create payment service with environment configuration."""
    config = PaymentConfig(
        stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
        webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        currency=os.getenv("STRIPE_CURRENCY", "usd"),
        success_url=os.getenv("STRIPE_SUCCESS_URL", "https://yourdomain.com/success"),
        cancel_url=os.getenv("STRIPE_CANCEL_URL", "https://yourdomain.com/cancel"),
    )

    database_url = os.getenv("DATABASE_URL", "sqlite:///./payments.db")

    return StripePaymentService(config, database_url)
