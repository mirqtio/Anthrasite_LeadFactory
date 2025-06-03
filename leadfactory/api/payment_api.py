"""
Payment API endpoints for Stripe checkout integration.

Provides REST API endpoints for creating checkout sessions, handling webhooks,
and managing payment status for audit sales.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from leadfactory.services.payment_service import (
    StripePaymentService,
    create_payment_service,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    """Request model for creating checkout session."""

    customer_email: EmailStr
    customer_name: str
    audit_type: str
    amount: int  # Amount in cents
    metadata: Optional[Dict[str, Any]] = None


class PaymentStatusResponse(BaseModel):
    """Response model for payment status."""

    id: str
    status: str
    customer_email: str
    customer_name: Optional[str]
    amount: int
    currency: str
    audit_type: str
    created_at: str
    updated_at: str


class CheckoutResponse(BaseModel):
    """Response model for checkout session creation."""

    session_id: str
    session_url: str
    payment_intent_id: str
    publishable_key: str


class RefundRequest(BaseModel):
    """Request model for payment refund."""

    amount: Optional[int] = None  # If None, refunds full amount


def get_payment_service() -> StripePaymentService:
    """Dependency to get payment service instance."""
    return create_payment_service()


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    payment_service: StripePaymentService = Depends(get_payment_service),
):
    """Create a Stripe checkout session for audit purchase."""
    try:
        logger.info(f"Creating checkout session for {request.customer_email}")

        # Validate audit type
        valid_audit_types = [
            "seo",
            "security",
            "performance",
            "accessibility",
            "comprehensive",
        ]
        if request.audit_type.lower() not in valid_audit_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audit type. Must be one of: {', '.join(valid_audit_types)}",
            )

        # Validate amount (minimum $10, maximum $10,000)
        if request.amount < 1000 or request.amount > 1000000:
            raise HTTPException(
                status_code=400, detail="Amount must be between $10.00 and $10,000.00"
            )

        result = payment_service.create_checkout_session(
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            audit_type=request.audit_type.lower(),
            amount=request.amount,
            metadata=request.metadata,
        )

        return CheckoutResponse(**result)

    except HTTPException:
        raise  # Re-raise HTTPException to preserve status code
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    payment_service: StripePaymentService = Depends(get_payment_service),
):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing Stripe signature")

        # Process webhook in background to respond quickly
        background_tasks.add_task(
            process_webhook, payment_service, payload.decode(), signature
        )

        return JSONResponse(content={"status": "received"}, status_code=200)

    except HTTPException:
        raise  # Re-raise HTTPException to preserve status code
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")


async def process_webhook(
    payment_service: StripePaymentService, payload: str, signature: str
):
    """Process webhook in background."""
    try:
        result = payment_service.handle_webhook(payload, signature)
        logger.info(f"Webhook processed: {result}")
    except Exception as e:
        logger.error(f"Background webhook processing failed: {str(e)}")


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: str,
    payment_service: StripePaymentService = Depends(get_payment_service),
):
    """Get payment status by ID."""
    try:
        payment = payment_service.get_payment_status(payment_id)

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        return PaymentStatusResponse(**payment)

    except HTTPException:
        raise  # Re-raise HTTPException to preserve status code
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get payment status")


@router.get("/customer/{email}")
async def get_customer_payments(
    email: str, payment_service: StripePaymentService = Depends(get_payment_service)
):
    """Get all payments for a customer email."""
    try:
        payments = payment_service.get_payments_by_email(email)
        return {"payments": payments}

    except Exception as e:
        logger.error(f"Error getting customer payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get customer payments")


@router.post("/refund/{payment_id}")
async def refund_payment(
    payment_id: str,
    request: RefundRequest,
    payment_service: StripePaymentService = Depends(get_payment_service),
):
    """Refund a payment."""
    try:
        result = payment_service.refund_payment(payment_id, request.amount)
        return result

    except HTTPException:
        raise  # Re-raise HTTPException to preserve status code
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error refunding payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refund payment")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "payment_api",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Pricing configuration endpoint
@router.get("/pricing")
async def get_pricing():
    """Get audit pricing information."""
    return {
        "pricing": {
            "seo": {
                "name": "SEO Audit",
                "description": "Comprehensive SEO analysis and recommendations",
                "price": 9900,  # $99.00
                "currency": "usd",
            },
            "security": {
                "name": "Security Audit",
                "description": "Website security vulnerability assessment",
                "price": 14900,  # $149.00
                "currency": "usd",
            },
            "performance": {
                "name": "Performance Audit",
                "description": "Website speed and performance optimization",
                "price": 7900,  # $79.00
                "currency": "usd",
            },
            "accessibility": {
                "name": "Accessibility Audit",
                "description": "WCAG compliance and accessibility assessment",
                "price": 8900,  # $89.00
                "currency": "usd",
            },
            "comprehensive": {
                "name": "Comprehensive Audit",
                "description": "Complete website audit covering all areas",
                "price": 24900,  # $249.00
                "currency": "usd",
            },
        }
    }


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    payment_service: StripePaymentService = Depends(get_payment_service),
):
    """Get payment status by Stripe session ID."""
    try:
        logger.info(f"Getting session status for {session_id}")

        # Get session details from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get payment record from database if available
        payment = None
        if session.payment_intent:
            try:
                payment_data = payment_service.get_payment_status(
                    session.payment_intent
                )
                if payment_data:
                    payment = {
                        "id": payment_data["id"],
                        "stripe_payment_id": payment_data["stripe_payment_intent_id"],
                        "customer_email": payment_data["customer_email"],
                        "customer_name": payment_data["customer_name"],
                        "amount": payment_data["amount"],
                        "currency": payment_data["currency"],
                        "status": payment_data["status"],
                        "audit_type": payment_data["audit_type"],
                        "created_at": payment_data["created_at"],
                        "updated_at": payment_data["updated_at"],
                    }
            except Exception as e:
                logger.warning(f"Could not retrieve payment record: {e}")

        return {
            "session_id": session_id,
            "session_status": session.payment_status,
            "payment_intent_id": session.payment_intent,
            "customer_email": session.customer_email,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "payment": payment,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error getting session status: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
