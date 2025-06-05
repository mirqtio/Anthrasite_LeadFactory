"""
Stripe Payment Service for Audit Sales

Handles Stripe checkout integration, payment intents, and webhook processing
for direct-to-SMB audit sales.
"""

import logging
import os
import tempfile
import time
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

# Import financial tracking
from leadfactory.cost.financial_tracking import financial_tracker

# Import purchase metrics tracking
from leadfactory.cost.purchase_metrics import purchase_metrics_tracker

# Import report delivery service
from leadfactory.services.report_delivery import ReportDeliveryService

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
    success_url: str = None
    cancel_url: str = None

    def __post_init__(self):
        """Set default URLs from environment variables."""
        if self.success_url is None:
            self.success_url = os.getenv(
                "STRIPE_SUCCESS_URL", "http://localhost:3000/success"
            )
        if self.cancel_url is None:
            self.cancel_url = os.getenv(
                "STRIPE_CANCEL_URL", "http://localhost:3000/cancel"
            )


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

        # Initialize report delivery service
        self.report_delivery = ReportDeliveryService()

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
            elif event["type"] == "charge.dispute.created":
                return self._handle_chargeback_created(event["data"]["object"])
            elif event["type"] in ["refund.created", "charge.refunded"]:
                return self._handle_refund_created(event["data"]["object"])
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

                # Extract fee information from Stripe charge
                try:
                    # Get the charge details to extract fee information
                    charges = stripe.Charge.list(
                        payment_intent=payment_intent_id, limit=1
                    )

                    if charges.data:
                        charge = charges.data[0]

                        # Extract financial data
                        gross_amount_cents = charge.get("amount", 0)
                        net_amount_cents = charge.get(
                            "amount_captured", gross_amount_cents
                        )

                        # Extract Stripe fees from balance transaction
                        balance_transaction_id = charge.get("balance_transaction")
                        stripe_fee_cents = 0
                        application_fee_cents = 0

                        if balance_transaction_id:
                            try:
                                balance_txn = stripe.BalanceTransaction.retrieve(
                                    balance_transaction_id
                                )
                                stripe_fee_cents = balance_txn.get("fee", 0)
                                net_amount_cents = balance_txn.get(
                                    "net", gross_amount_cents - stripe_fee_cents
                                )

                                # Extract fee details
                                fee_details = balance_txn.get("fee_details", [])
                                for fee_detail in fee_details:
                                    if fee_detail.get("type") == "application_fee":
                                        application_fee_cents += fee_detail.get(
                                            "amount", 0
                                        )

                            except Exception as e:
                                logger.warning(
                                    f"Could not retrieve balance transaction {balance_transaction_id}: {e}"
                                )

                        # Extract tax information (if available)
                        tax_amount_cents = 0
                        if "metadata" in charge and "tax_amount" in charge["metadata"]:
                            try:
                                tax_amount_cents = int(charge["metadata"]["tax_amount"])
                            except (ValueError, TypeError):
                                pass

                        # Record purchase in metrics and financial tracking system
                        purchase_metrics_tracker.record_purchase(
                            stripe_payment_intent_id=payment_intent_id,
                            stripe_charge_id=charge["id"],
                            customer_email=payment.customer_email,
                            customer_name=payment.customer_name,
                            gross_amount_cents=gross_amount_cents,
                            net_amount_cents=net_amount_cents,
                            stripe_fee_cents=stripe_fee_cents,
                            audit_type=payment.audit_type,
                            currency=charge.get("currency", "usd"),
                            metadata={
                                "charge_id": charge["id"],
                                "balance_transaction_id": balance_transaction_id,
                                "payment_method": charge.get(
                                    "payment_method_details", {}
                                ).get("type"),
                                "receipt_url": charge.get("receipt_url"),
                                "stripe_metadata": charge.get("metadata", {}),
                                "application_fee_cents": application_fee_cents,
                                "tax_amount_cents": tax_amount_cents,
                            },
                        )

                        logger.info(
                            f"Recorded financial data for payment {payment_intent_id}: "
                            f"gross=${gross_amount_cents / 100:.2f}, "
                            f"fee=${stripe_fee_cents / 100:.2f}, "
                            f"net=${net_amount_cents / 100:.2f}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error extracting fee information for payment {payment_intent_id}: {e}"
                    )
                    # Continue with payment processing even if fee extraction fails

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

    def _handle_chargeback_created(self, dispute: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chargeback created."""
        charge_id = dispute["charge"]
        payment_intent_id = dispute["payment_intent"]

        logger.info(f"Chargeback created for payment intent: {payment_intent_id}")

        with self.SessionLocal() as db:
            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if payment:
                payment.status = PaymentStatus.FAILED.value
                payment.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Updated payment status to failed: {payment_intent_id}")

                return {
                    "status": "chargeback",
                    "payment_id": payment.id,
                    "customer_email": payment.customer_email,
                }
            else:
                logger.warning(
                    f"Payment record not found for intent: {payment_intent_id}"
                )
                return {"status": "not_found", "payment_intent_id": payment_intent_id}

    def _handle_refund_created(self, refund: Dict[str, Any]) -> Dict[str, Any]:
        """Handle refund created."""
        charge_id = refund["charge"]
        payment_intent_id = refund["payment_intent"]

        logger.info(f"Refund created for payment intent: {payment_intent_id}")

        with self.SessionLocal() as db:
            payment = (
                db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if payment:
                payment.status = PaymentStatus.REFUNDED.value
                payment.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Updated payment status to refunded: {payment_intent_id}")

                # Record refund in financial tracking system
                try:
                    refund_amount_cents = refund.get("amount", 0)
                    reason = refund.get("reason", "requested_by_customer")

                    # Get balance transaction for fee refund information
                    stripe_fee_refund_cents = 0
                    balance_transaction_id = refund.get("balance_transaction")

                    if balance_transaction_id:
                        try:
                            balance_txn = stripe.BalanceTransaction.retrieve(
                                balance_transaction_id
                            )
                            # For refunds, the fee is typically negative (refunded)
                            stripe_fee_refund_cents = abs(balance_txn.get("fee", 0))
                        except Exception as e:
                            logger.warning(
                                f"Could not retrieve refund balance transaction {balance_transaction_id}: {e}"
                            )

                    purchase_metrics_tracker.record_refund(
                        stripe_payment_intent_id=payment_intent_id,
                        stripe_charge_id=charge_id,
                        refund_amount_cents=refund_amount_cents,
                        reason=reason,
                        currency=refund.get("currency", "usd"),
                        metadata={
                            "refund_id": refund["id"],
                            "balance_transaction_id": balance_transaction_id,
                            "refund_status": refund.get("status"),
                            "refund_metadata": refund.get("metadata", {}),
                            "stripe_fee_refund_cents": stripe_fee_refund_cents,
                        },
                    )

                    logger.info(
                        f"Recorded refund financial data for payment {payment_intent_id}: "
                        f"refund=${refund_amount_cents / 100:.2f}, "
                        f"fee_refund=${stripe_fee_refund_cents / 100:.2f}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error recording refund financial data for payment {payment_intent_id}: {e}"
                    )

                return {
                    "status": "refunded",
                    "payment_id": payment.id,
                    "customer_email": payment.customer_email,
                }
            else:
                logger.warning(
                    f"Payment record not found for intent: {payment_intent_id}"
                )
                return {"status": "not_found", "payment_intent_id": payment_intent_id}

    def _trigger_audit_generation(self, payment: Payment) -> None:
        """Trigger audit report generation after successful payment."""
        logger.info(f"Triggering audit generation for payment: {payment.id}")

        try:
            # For now, we'll simulate PDF generation by creating a placeholder
            # In a real implementation, this would call the PDF generation service
            # and get the actual PDF path

            # Generate a report ID based on payment details
            report_id = f"audit_{payment.audit_type}_{payment.id}_{int(datetime.utcnow().timestamp())}"

            # Simulate PDF generation (replace with actual PDF generation service)
            pdf_path = self._generate_audit_pdf(payment, report_id)

            # Use the report delivery service to upload and deliver the report
            delivery_result = self.report_delivery.upload_and_deliver_report(
                pdf_path=pdf_path,
                report_id=report_id,
                user_id=payment.customer_email,  # Using email as user ID for now
                user_email=payment.customer_email,
                purchase_id=payment.stripe_payment_intent_id,
                business_name=payment.customer_name or "Your Business",
                expiry_hours=72,  # 3 days access
            )

            logger.info(
                f"Report delivered successfully for payment {payment.id}: {delivery_result}"
            )

            # Update payment record with delivery information
            with self.SessionLocal() as db:
                db_payment = db.query(Payment).filter(Payment.id == payment.id).first()
                if db_payment:
                    # Store delivery metadata in payment record
                    if not db_payment.payment_metadata:
                        db_payment.payment_metadata = "{}"

                    import json

                    metadata = (
                        json.loads(db_payment.payment_metadata)
                        if db_payment.payment_metadata
                        else {}
                    )
                    metadata.update(
                        {
                            "report_delivered": True,
                            "report_id": report_id,
                            "delivery_status": delivery_result.get("status"),
                            "storage_path": delivery_result.get("storage_path"),
                            "delivered_at": delivery_result.get("delivered_at"),
                            "expires_at": delivery_result.get("expires_at"),
                        }
                    )
                    db_payment.payment_metadata = json.dumps(metadata)

                    db.commit()
                    logger.info(f"Updated payment {payment.id} with delivery metadata")

        except Exception as e:
            logger.error(
                f"Failed to generate and deliver audit report for payment {payment.id}: {e}"
            )
            # Don't raise the exception to avoid disrupting webhook processing
            # The payment is still successful even if report delivery fails

    def _generate_audit_pdf(self, payment: Payment, report_id: str) -> str:
        """
        Generate audit PDF report.

        This is a placeholder implementation. In production, this would:
        1. Call the actual PDF generation service
        2. Generate a comprehensive audit report
        3. Return the path to the generated PDF

        Args:
            payment: Payment record with audit details
            report_id: Unique identifier for the report

        Returns:
            Path to the generated PDF file
        """
        import os

        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        # Create a temporary PDF file
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, f"{report_id}.pdf")

        # Generate a simple PDF report (placeholder)
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter

        # Add content to the PDF
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Audit Report: {payment.audit_type}")

        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Report ID: {report_id}")
        c.drawString(50, height - 100, f"Customer: {payment.customer_name}")
        c.drawString(50, height - 120, f"Email: {payment.customer_email}")
        c.drawString(50, height - 140, f"Business: {payment.customer_name or 'N/A'}")
        c.drawString(
            50,
            height - 160,
            f"Amount Paid: ${payment.amount / 100:.2f} {payment.currency.upper()}",
        )
        c.drawString(
            50,
            height - 180,
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        )

        c.setFont("Helvetica", 10)
        c.drawString(
            50,
            height - 220,
            "This is a placeholder audit report generated for testing purposes.",
        )
        c.drawString(
            50,
            height - 240,
            "In production, this would contain comprehensive audit findings,",
        )
        c.drawString(
            50,
            height - 260,
            "recommendations, and detailed analysis of the business operations.",
        )

        # Add audit sections
        y_pos = height - 300
        sections = [
            "Executive Summary",
            "Financial Analysis",
            "Operational Review",
            "Compliance Assessment",
            "Risk Analysis",
            "Recommendations",
            "Action Plan",
        ]

        c.setFont("Helvetica-Bold", 12)
        for section in sections:
            c.drawString(50, y_pos, f"• {section}")
            y_pos -= 30
            c.setFont("Helvetica", 10)
            c.drawString(
                70, y_pos, "Detailed analysis and findings would appear here..."
            )
            y_pos -= 40
            c.setFont("Helvetica-Bold", 12)

        c.save()

        logger.info(f"Generated placeholder PDF report: {pdf_path}")
        return pdf_path

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
