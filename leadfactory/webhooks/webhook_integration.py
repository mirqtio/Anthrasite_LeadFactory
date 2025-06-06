#!/usr/bin/env python3
"""
Webhook Integration Layer.

This module integrates the webhook failure handling system with existing
engagement tracking, error handling, and monitoring systems to provide
a unified webhook processing experience.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from leadfactory.monitoring.engagement_analytics import EngagementAnalytics, EventType
from leadfactory.pipeline.error_handling import (
    ErrorCategory,
    ErrorPropagationManager,
    PipelineError,
)
from leadfactory.utils.logging import get_logger
from leadfactory.webhooks.dead_letter_queue import (
    DeadLetterQueueManager,
    DeadLetterReason,
)
from leadfactory.webhooks.webhook_monitor import WebhookMonitor
from leadfactory.webhooks.webhook_retry_manager import WebhookRetryManager
from leadfactory.webhooks.webhook_validator import (
    WebhookEvent,
    WebhookEventType,
    WebhookStatus,
    WebhookValidator,
)

logger = get_logger(__name__)


class WebhookIntegrationService:
    """Service that integrates webhook handling with existing systems."""

    def __init__(
        self,
        engagement_analytics: Optional[EngagementAnalytics] = None,
        error_manager: Optional[ErrorPropagationManager] = None,
        webhook_monitor: Optional[WebhookMonitor] = None,
        retry_manager: Optional[WebhookRetryManager] = None,
        dead_letter_manager: Optional[DeadLetterQueueManager] = None,
    ):
        """Initialize the integration service.

        Args:
            engagement_analytics: Engagement tracking service
            error_manager: Error propagation manager
            webhook_monitor: Webhook health monitor
            retry_manager: Webhook retry manager
            dead_letter_manager: Dead letter queue manager
        """
        self.engagement_analytics = engagement_analytics or EngagementAnalytics()
        self.error_manager = error_manager or ErrorPropagationManager()
        self.webhook_monitor = webhook_monitor or WebhookMonitor()
        self.retry_manager = retry_manager or WebhookRetryManager()
        self.dead_letter_manager = dead_letter_manager or DeadLetterQueueManager()

        # Create the main webhook validator with integrated services
        self.webhook_validator = WebhookValidator(
            error_manager=self.error_manager,
            engagement_analytics=self.engagement_analytics,
        )

        # Register event handlers for different webhook types
        self._register_event_handlers()

        logger.info("Initialized WebhookIntegrationService")

    def _register_event_handlers(self):
        """Register webhook event handlers for different event types."""
        # Email event handlers
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_DELIVERY, self._handle_email_delivery
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_BOUNCE, self._handle_email_bounce
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_OPEN, self._handle_email_open
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_CLICK, self._handle_email_click
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_SPAM, self._handle_email_spam
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.EMAIL_UNSUBSCRIBE, self._handle_email_unsubscribe
        )

        # Payment event handlers
        self.webhook_validator.register_event_handler(
            WebhookEventType.PAYMENT_SUCCESS, self._handle_payment_success
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.PAYMENT_FAILED, self._handle_payment_failed
        )

        # User event handlers
        self.webhook_validator.register_event_handler(
            WebhookEventType.USER_SIGNUP, self._handle_user_signup
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.USER_LOGIN, self._handle_user_login
        )

        # Engagement event handlers
        self.webhook_validator.register_event_handler(
            WebhookEventType.ENGAGEMENT_EVENT, self._handle_engagement_event
        )
        self.webhook_validator.register_event_handler(
            WebhookEventType.FORM_SUBMISSION, self._handle_form_submission
        )

    def process_webhook(
        self,
        webhook_name: str,
        payload: bytes,
        headers: Dict[str, str],
        source_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a webhook with full integration support.

        Args:
            webhook_name: Name of the webhook
            payload: Raw webhook payload
            headers: HTTP headers
            source_ip: Source IP address

        Returns:
            Processing result dictionary
        """
        start_time = datetime.utcnow()
        result = {
            "success": False,
            "event_id": None,
            "status": "failed",
            "message": "",
            "processing_time_ms": 0,
        }

        try:
            # Validate the webhook
            event = self.webhook_validator.validate_webhook(
                webhook_name, payload, headers, source_ip
            )

            result["event_id"] = event.event_id

            # Process the webhook with integrated error handling
            try:
                success = self.webhook_validator.process_webhook(event)

                if success:
                    result["success"] = True
                    result["status"] = "completed"
                    result["message"] = "Webhook processed successfully"

                    # Track successful processing in engagement analytics
                    self._track_webhook_success(event)

                else:
                    result["status"] = "failed"
                    result["message"] = "Webhook processing failed"

                    # Handle failure with retry mechanism
                    self._handle_webhook_failure(event, "Processing failed")

            except Exception as processing_error:
                result["status"] = "failed"
                result["message"] = f"Processing error: {processing_error}"

                # Handle exception with integrated error management
                self._handle_webhook_exception(event, processing_error)

        except Exception as validation_error:
            result["message"] = f"Validation error: {validation_error}"

            # Log validation errors for monitoring
            self._handle_validation_error(webhook_name, validation_error, headers)

        finally:
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result["processing_time_ms"] = round(processing_time, 2)

            # Log the result
            logger.info(
                f"Webhook processing completed: {webhook_name} - {result['status']} "
                f"({result['processing_time_ms']}ms)"
            )

        return result

    def _handle_email_delivery(self, event: WebhookEvent) -> bool:
        """Handle email delivery events."""
        try:
            email = event.payload.get("email")
            message_id = event.payload.get("sg_message_id")

            # Track engagement event
            if email and message_id:
                self.engagement_analytics.track_event(
                    user_id=email,  # Use email as user ID for email events
                    session_id=message_id,  # Use message ID as session
                    event_type=EventType.EMAIL_OPEN.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "message_id": message_id,
                        "delivery_timestamp": event.payload.get("timestamp"),
                    },
                )

            logger.debug(f"Handled email delivery for {email}")
            return True

        except Exception as e:
            logger.error(f"Error handling email delivery: {e}")
            return False

    def _handle_email_bounce(self, event: WebhookEvent) -> bool:
        """Handle email bounce events."""
        try:
            email = event.payload.get("email")
            bounce_type = event.payload.get("type", "unknown")
            reason = event.payload.get("reason", "")

            # Create pipeline error for bounce
            pipeline_error = PipelineError(
                stage="email_delivery",
                operation="send_email",
                error_type="EmailBounce",
                error_message=f"Email bounced: {reason}",
                context={
                    "email": email,
                    "bounce_type": bounce_type,
                    "reason": reason,
                    "webhook_event_id": event.event_id,
                },
            )

            # Record in error manager
            self.error_manager.record_error(pipeline_error)

            # Track negative engagement
            if email:
                self.engagement_analytics.track_event(
                    user_id=email,
                    session_id=event.event_id,
                    event_type="email_bounce",
                    properties={
                        "bounce_type": bounce_type,
                        "reason": reason,
                        "webhook_name": event.webhook_name,
                    },
                )

            logger.debug(f"Handled email bounce for {email}: {bounce_type}")
            return True

        except Exception as e:
            logger.error(f"Error handling email bounce: {e}")
            return False

    def _handle_email_open(self, event: WebhookEvent) -> bool:
        """Handle email open events."""
        try:
            email = event.payload.get("email")
            message_id = event.payload.get("sg_message_id")

            if email:
                self.engagement_analytics.track_event(
                    user_id=email,
                    session_id=message_id or event.event_id,
                    event_type=EventType.EMAIL_OPEN.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "message_id": message_id,
                        "open_timestamp": event.payload.get("timestamp"),
                        "user_agent": event.payload.get("useragent"),
                        "ip": event.payload.get("ip"),
                    },
                )

            logger.debug(f"Handled email open for {email}")
            return True

        except Exception as e:
            logger.error(f"Error handling email open: {e}")
            return False

    def _handle_email_click(self, event: WebhookEvent) -> bool:
        """Handle email click events."""
        try:
            email = event.payload.get("email")
            url = event.payload.get("url")
            message_id = event.payload.get("sg_message_id")

            if email:
                self.engagement_analytics.track_event(
                    user_id=email,
                    session_id=message_id or event.event_id,
                    event_type=EventType.EMAIL_CLICK.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "message_id": message_id,
                        "clicked_url": url,
                        "click_timestamp": event.payload.get("timestamp"),
                        "user_agent": event.payload.get("useragent"),
                        "ip": event.payload.get("ip"),
                    },
                )

            logger.debug(f"Handled email click for {email}: {url}")
            return True

        except Exception as e:
            logger.error(f"Error handling email click: {e}")
            return False

    def _handle_email_spam(self, event: WebhookEvent) -> bool:
        """Handle email spam complaint events."""
        try:
            email = event.payload.get("email")

            # Create critical pipeline error for spam complaints
            pipeline_error = PipelineError(
                stage="email_delivery",
                operation="send_email",
                error_type="SpamComplaint",
                error_message=f"Spam complaint received for {email}",
                context={
                    "email": email,
                    "webhook_event_id": event.event_id,
                },
            )

            self.error_manager.record_error(pipeline_error)

            # Track spam complaint in engagement analytics
            if email:
                self.engagement_analytics.track_event(
                    user_id=email,
                    session_id=event.event_id,
                    event_type="email_spam_complaint",
                    properties={
                        "webhook_name": event.webhook_name,
                        "complaint_timestamp": event.payload.get("timestamp"),
                    },
                )

            logger.warning(f"Handled spam complaint for {email}")
            return True

        except Exception as e:
            logger.error(f"Error handling email spam: {e}")
            return False

    def _handle_email_unsubscribe(self, event: WebhookEvent) -> bool:
        """Handle email unsubscribe events."""
        try:
            email = event.payload.get("email")

            if email:
                self.engagement_analytics.track_event(
                    user_id=email,
                    session_id=event.event_id,
                    event_type="email_unsubscribe",
                    properties={
                        "webhook_name": event.webhook_name,
                        "unsubscribe_timestamp": event.payload.get("timestamp"),
                        "unsubscribe_type": event.payload.get(
                            "event"
                        ),  # unsubscribe vs group_unsubscribe
                    },
                )

            logger.debug(f"Handled email unsubscribe for {email}")
            return True

        except Exception as e:
            logger.error(f"Error handling email unsubscribe: {e}")
            return False

    def _handle_payment_success(self, event: WebhookEvent) -> bool:
        """Handle successful payment events."""
        try:
            payment_id = event.payload.get("payment_id")
            customer_id = event.payload.get("customer_id")
            amount = event.payload.get("amount")

            if customer_id:
                self.engagement_analytics.track_event(
                    user_id=customer_id,
                    session_id=event.event_id,
                    event_type=EventType.PURCHASE.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "payment_id": payment_id,
                        "amount": amount,
                        "currency": event.payload.get("currency", "USD"),
                        "payment_timestamp": event.payload.get("timestamp"),
                    },
                )

            logger.info(f"Handled successful payment: {payment_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling payment success: {e}")
            return False

    def _handle_payment_failed(self, event: WebhookEvent) -> bool:
        """Handle failed payment events."""
        try:
            payment_id = event.payload.get("payment_id")
            customer_id = event.payload.get("customer_id")
            error_message = event.payload.get("error_message", "Payment failed")

            # Create pipeline error for failed payment
            pipeline_error = PipelineError(
                stage="payment_processing",
                operation="process_payment",
                error_type="PaymentFailed",
                error_message=error_message,
                context={
                    "payment_id": payment_id,
                    "customer_id": customer_id,
                    "webhook_event_id": event.event_id,
                },
            )

            self.error_manager.record_error(pipeline_error)

            # Track failed payment attempt
            if customer_id:
                self.engagement_analytics.track_event(
                    user_id=customer_id,
                    session_id=event.event_id,
                    event_type="payment_failed",
                    properties={
                        "webhook_name": event.webhook_name,
                        "payment_id": payment_id,
                        "error_message": error_message,
                        "failure_timestamp": event.payload.get("timestamp"),
                    },
                )

            logger.warning(f"Handled failed payment: {payment_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")
            return False

    def _handle_user_signup(self, event: WebhookEvent) -> bool:
        """Handle user signup events."""
        try:
            user_id = event.payload.get("user_id")
            email = event.payload.get("email")

            if user_id:
                self.engagement_analytics.track_event(
                    user_id=user_id,
                    session_id=event.event_id,
                    event_type=EventType.SIGNUP.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "email": email,
                        "signup_timestamp": event.payload.get("timestamp"),
                        "signup_source": event.payload.get("source"),
                    },
                )

            logger.debug(f"Handled user signup for {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling user signup: {e}")
            return False

    def _handle_user_login(self, event: WebhookEvent) -> bool:
        """Handle user login events."""
        try:
            user_id = event.payload.get("user_id")

            if user_id:
                self.engagement_analytics.track_event(
                    user_id=user_id,
                    session_id=event.event_id,
                    event_type=EventType.LOGIN.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "login_timestamp": event.payload.get("timestamp"),
                        "login_method": event.payload.get("method"),
                        "ip_address": event.source_ip,
                    },
                )

            logger.debug(f"Handled user login for {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling user login: {e}")
            return False

    def _handle_engagement_event(self, event: WebhookEvent) -> bool:
        """Handle generic engagement events."""
        try:
            user_id = event.payload.get("user_id")
            event_type = event.payload.get("event_type")
            session_id = event.payload.get("session_id", event.event_id)

            if user_id and event_type:
                self.engagement_analytics.track_event(
                    user_id=user_id,
                    session_id=session_id,
                    event_type=event_type,
                    properties=event.payload.get("properties", {}),
                    page_url=event.payload.get("page_url"),
                    referrer=event.payload.get("referrer"),
                    user_agent=event.user_agent,
                    ip_address=event.source_ip,
                )

            logger.debug(f"Handled engagement event for {user_id}: {event_type}")
            return True

        except Exception as e:
            logger.error(f"Error handling engagement event: {e}")
            return False

    def _handle_form_submission(self, event: WebhookEvent) -> bool:
        """Handle form submission events."""
        try:
            user_id = event.payload.get("user_id") or event.payload.get("email")
            form_name = event.payload.get("form_name")

            if user_id:
                self.engagement_analytics.track_event(
                    user_id=user_id,
                    session_id=event.event_id,
                    event_type=EventType.FORM_SUBMIT.value,
                    properties={
                        "webhook_name": event.webhook_name,
                        "form_name": form_name,
                        "form_data": event.payload.get("form_data", {}),
                        "submission_timestamp": event.payload.get("timestamp"),
                    },
                    page_url=event.payload.get("page_url"),
                )

            logger.debug(f"Handled form submission for {user_id}: {form_name}")
            return True

        except Exception as e:
            logger.error(f"Error handling form submission: {e}")
            return False

    def _track_webhook_success(self, event: WebhookEvent):
        """Track successful webhook processing in engagement analytics."""
        try:
            # Track as a system event for monitoring
            self.engagement_analytics.track_event(
                user_id="system",
                session_id=event.event_id,
                event_type="webhook_processed",
                properties={
                    "webhook_name": event.webhook_name,
                    "event_type": event.event_type.value,
                    "processing_success": True,
                    "signature_verified": event.signature_verified,
                },
            )
        except Exception as e:
            logger.error(f"Error tracking webhook success: {e}")

    def _handle_webhook_failure(self, event: WebhookEvent, error_message: str):
        """Handle webhook processing failure."""
        try:
            # Schedule retry
            from leadfactory.webhooks.webhook_retry_manager import WebhookPriority

            priority = WebhookPriority.NORMAL
            if event.webhook_name in ["stripe", "paypal"]:
                priority = WebhookPriority.CRITICAL

            self.retry_manager.schedule_retry(
                event_id=event.event_id,
                webhook_name=event.webhook_name,
                retry_attempt=event.retry_count + 1,
                error=error_message,
                priority=priority,
            )

            # Track failure in engagement analytics
            self.engagement_analytics.track_event(
                user_id="system",
                session_id=event.event_id,
                event_type="webhook_failed",
                properties={
                    "webhook_name": event.webhook_name,
                    "event_type": event.event_type.value,
                    "error_message": error_message,
                    "retry_count": event.retry_count,
                },
            )

        except Exception as e:
            logger.error(f"Error handling webhook failure: {e}")

    def _handle_webhook_exception(self, event: WebhookEvent, exception: Exception):
        """Handle webhook processing exception."""
        try:
            # Create pipeline error
            pipeline_error = PipelineError.from_exception(
                exception=exception,
                stage="webhook_processing",
                operation=f"process_{event.webhook_name}",
                context={
                    "event_id": event.event_id,
                    "webhook_name": event.webhook_name,
                    "event_type": event.event_type.value,
                },
            )

            # Record in error manager
            self.error_manager.record_error(pipeline_error)

            # Check if we should move to dead letter queue
            config = self.webhook_validator.webhook_configs.get(event.webhook_name)
            if config and event.retry_count >= config.max_retries:
                # Move to dead letter queue
                self.dead_letter_manager.add_event(
                    webhook_event=event.to_dict(),
                    reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
                    last_error=str(exception),
                )
            else:
                # Schedule retry
                self._handle_webhook_failure(event, str(exception))

        except Exception as e:
            logger.error(f"Error handling webhook exception: {e}")

    def _handle_validation_error(
        self, webhook_name: str, error: Exception, headers: Dict[str, str]
    ):
        """Handle webhook validation error."""
        try:
            # Create pipeline error
            pipeline_error = PipelineError.from_exception(
                exception=error,
                stage="webhook_validation",
                operation=f"validate_{webhook_name}",
                context={
                    "webhook_name": webhook_name,
                    "headers": headers,
                },
            )

            # Record in error manager
            self.error_manager.record_error(pipeline_error)

            # Track validation failure
            self.engagement_analytics.track_event(
                user_id="system",
                session_id=str(datetime.utcnow().timestamp()),
                event_type="webhook_validation_failed",
                properties={
                    "webhook_name": webhook_name,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
            )

        except Exception as e:
            logger.error(f"Error handling validation error: {e}")

    def get_integration_status(self) -> Dict[str, Any]:
        """Get status of all integrated systems.

        Returns:
            Integration status dictionary
        """
        try:
            return {
                "webhook_validator": {
                    "registered_webhooks": len(self.webhook_validator.webhook_configs),
                    "registered_handlers": {
                        event_type.value: len(handlers)
                        for event_type, handlers in self.webhook_validator.event_handlers.items()
                    },
                },
                "webhook_monitor": self.webhook_monitor.get_overall_health(),
                "retry_manager": self.retry_manager.get_queue_stats(),
                "dead_letter_manager": self.dead_letter_manager.get_statistics(),
                "error_manager": self.error_manager.get_error_summary(),
                "engagement_analytics": self.engagement_analytics.get_real_time_metrics(),
            }

        except Exception as e:
            logger.error(f"Error getting integration status: {e}")
            return {"error": str(e)}

    def shutdown(self):
        """Shutdown the integration service."""
        try:
            # Stop monitoring
            self.webhook_monitor.stop_monitoring()

            # Stop retry queue
            self.retry_manager.stop_queue()

            logger.info("WebhookIntegrationService shutdown completed")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Global instance can be created when needed
webhook_integration_service = None


def get_webhook_integration_service():
    """Get or create webhook integration service instance."""
    global webhook_integration_service
    if webhook_integration_service is None:
        webhook_integration_service = WebhookIntegrationService()
    return webhook_integration_service
