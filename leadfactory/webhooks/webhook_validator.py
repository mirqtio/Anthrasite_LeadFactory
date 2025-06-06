#!/usr/bin/env python3
"""
Enhanced Webhook Validation Service for LeadFactory Pipeline.

This module provides comprehensive webhook validation with robust error handling,
retry mechanisms, and integration with the existing engagement tracking system.

Features:
- Enhanced payload validation with schema validation
- Signature verification for security
- Intelligent retry mechanism with exponential backoff
- Dead letter queue for permanently failed webhooks
- Real-time monitoring and alerting
- Integration with engagement tracking
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

try:
    import jsonschema
    from jsonschema import validate

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None

    # Mock validate function if jsonschema is not available
    def validate(instance, schema):
        pass


from leadfactory.monitoring.alert_manager import AlertManager, AlertSeverity, AlertType
from leadfactory.monitoring.engagement_analytics import EngagementAnalytics
from leadfactory.pipeline.error_handling import (
    ErrorCategory,
    ErrorPropagationManager,
    ErrorSeverity,
    PipelineError,
)
from leadfactory.pipeline.retry_mechanisms import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryConfig,
    RetryManager,
    RetryStrategy,
)
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookEventType(Enum):
    """Types of webhook events."""

    EMAIL_DELIVERY = "email_delivery"
    EMAIL_BOUNCE = "email_bounce"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    EMAIL_SPAM = "email_spam"
    EMAIL_UNSUBSCRIBE = "email_unsubscribe"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    FORM_SUBMISSION = "form_submission"
    ENGAGEMENT_EVENT = "engagement_event"
    SYSTEM_ALERT = "system_alert"
    CUSTOM = "custom"


class WebhookStatus(Enum):
    """Webhook processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"
    REJECTED = "rejected"


class ValidationError(Exception):
    """Webhook validation error."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)


class SignatureVerificationError(Exception):
    """Webhook signature verification error."""

    pass


@dataclass
class WebhookConfig:
    """Webhook configuration."""

    name: str
    endpoint_path: str
    event_types: List[WebhookEventType]
    secret_key: Optional[str] = None
    signature_header: str = "X-Signature"
    signature_algorithm: str = "sha256"
    signature_encoding: str = "base64"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    validation_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True
    rate_limit_per_minute: int = 100


@dataclass
class WebhookEvent:
    """Represents a webhook event."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    webhook_name: str = ""
    event_type: WebhookEventType = WebhookEventType.CUSTOM
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    status: WebhookStatus = WebhookStatus.PENDING
    retry_count: int = 0
    last_error: Optional[str] = None
    processed_at: Optional[datetime] = None
    signature_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "webhook_name": self.webhook_name,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "headers": self.headers,
            "timestamp": self.timestamp.isoformat(),
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
            "signature_verified": self.signature_verified,
        }


class WebhookValidator:
    """Enhanced webhook validation service."""

    def __init__(
        self,
        error_manager: Optional[ErrorPropagationManager] = None,
        alert_manager: Optional[AlertManager] = None,
        engagement_analytics: Optional[EngagementAnalytics] = None,
    ):
        """Initialize webhook validator.

        Args:
            error_manager: Error propagation manager
            alert_manager: Alert manager for notifications
            engagement_analytics: Engagement tracking service
        """
        self.storage = get_storage_instance()
        self.error_manager = error_manager or ErrorPropagationManager()
        self.alert_manager = alert_manager or AlertManager()
        self.engagement_analytics = engagement_analytics or EngagementAnalytics()

        self.webhook_configs: Dict[str, WebhookConfig] = {}
        self.event_handlers: Dict[WebhookEventType, List[Callable]] = {}
        self.retry_managers: Dict[str, RetryManager] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Rate limiting
        self.rate_limits: Dict[str, List[datetime]] = {}

        # Webhook schemas
        self._setup_default_schemas()
        self._setup_default_configs()

        logger.info("Initialized WebhookValidator")

    def _setup_default_schemas(self):
        """Setup default validation schemas for different webhook types."""
        self.default_schemas = {
            WebhookEventType.EMAIL_DELIVERY: {
                "type": "object",
                "required": ["email", "event", "timestamp"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "event": {"type": "string"},
                    "timestamp": {"type": "integer"},
                    "message_id": {"type": "string"},
                    "sg_event_id": {"type": "string"},
                },
            },
            WebhookEventType.EMAIL_BOUNCE: {
                "type": "object",
                "required": ["email", "event", "timestamp", "reason"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "event": {"type": "string"},
                    "timestamp": {"type": "integer"},
                    "reason": {"type": "string"},
                    "bounce_type": {
                        "type": "string",
                        "enum": ["hard", "soft", "block"],
                    },
                    "status": {"type": "string"},
                },
            },
            WebhookEventType.PAYMENT_SUCCESS: {
                "type": "object",
                "required": ["payment_id", "amount", "currency", "customer_id"],
                "properties": {
                    "payment_id": {"type": "string"},
                    "amount": {"type": "number", "minimum": 0},
                    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                    "customer_id": {"type": "string"},
                    "timestamp": {"type": "integer"},
                },
            },
            WebhookEventType.ENGAGEMENT_EVENT: {
                "type": "object",
                "required": ["user_id", "event_type", "timestamp"],
                "properties": {
                    "user_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "timestamp": {"type": "integer"},
                    "session_id": {"type": "string"},
                    "properties": {"type": "object"},
                    "page_url": {"type": "string", "format": "uri"},
                },
            },
        }

    def _setup_default_configs(self):
        """Setup default webhook configurations."""
        # SendGrid webhook config
        self.register_webhook(
            WebhookConfig(
                name="sendgrid",
                endpoint_path="/webhooks/sendgrid",
                event_types=[
                    WebhookEventType.EMAIL_DELIVERY,
                    WebhookEventType.EMAIL_BOUNCE,
                    WebhookEventType.EMAIL_OPEN,
                    WebhookEventType.EMAIL_CLICK,
                    WebhookEventType.EMAIL_SPAM,
                    WebhookEventType.EMAIL_UNSUBSCRIBE,
                ],
                signature_header="X-Twilio-Email-Event-Webhook-Signature",
                timeout_seconds=30,
                max_retries=3,
            )
        )

        # Stripe webhook config
        self.register_webhook(
            WebhookConfig(
                name="stripe",
                endpoint_path="/webhooks/stripe",
                event_types=[
                    WebhookEventType.PAYMENT_SUCCESS,
                    WebhookEventType.PAYMENT_FAILED,
                ],
                signature_header="Stripe-Signature",
                signature_algorithm="sha256",
                timeout_seconds=30,
                max_retries=5,
            )
        )

        # Engagement tracking webhook config
        self.register_webhook(
            WebhookConfig(
                name="engagement",
                endpoint_path="/webhooks/engagement",
                event_types=[WebhookEventType.ENGAGEMENT_EVENT],
                timeout_seconds=15,
                max_retries=2,
            )
        )

    def register_webhook(self, config: WebhookConfig):
        """Register a webhook configuration.

        Args:
            config: Webhook configuration
        """
        self.webhook_configs[config.name] = config

        # Setup retry manager for this webhook
        retry_config = RetryConfig(
            max_attempts=config.max_retries,
            base_delay=config.retry_delay_seconds,
            backoff_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )

        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            timeout=config.timeout_seconds,
        )

        self.retry_managers[config.name] = RetryManager(
            retry_config, circuit_breaker_config
        )

        logger.info(f"Registered webhook config: {config.name}")

    def register_event_handler(
        self, event_type: WebhookEventType, handler: Callable[[WebhookEvent], bool]
    ):
        """Register an event handler for a specific webhook event type.

        Args:
            event_type: Type of webhook event
            handler: Handler function that processes the event
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event type: {event_type.value}")

    def validate_webhook(
        self,
        webhook_name: str,
        payload: bytes,
        headers: Dict[str, str],
        source_ip: Optional[str] = None,
    ) -> WebhookEvent:
        """Validate an incoming webhook.

        Args:
            webhook_name: Name of the webhook configuration
            payload: Raw webhook payload
            headers: HTTP headers
            source_ip: Source IP address

        Returns:
            Validated webhook event

        Raises:
            ValidationError: If validation fails
            SignatureVerificationError: If signature verification fails
        """
        try:
            # Get webhook config
            config = self.webhook_configs.get(webhook_name)
            if not config:
                raise ValidationError(f"Unknown webhook: {webhook_name}")

            if not config.enabled:
                raise ValidationError(f"Webhook {webhook_name} is disabled")

            # Check rate limiting
            if not self._check_rate_limit(webhook_name, config):
                raise ValidationError(f"Rate limit exceeded for webhook {webhook_name}")

            # Parse payload
            try:
                payload_data = json.loads(payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise ValidationError(f"Invalid JSON payload: {e}")

            # Create webhook event
            event = WebhookEvent(
                webhook_name=webhook_name,
                payload=payload_data,
                headers=headers,
                source_ip=source_ip,
                user_agent=headers.get("User-Agent"),
            )

            # Verify signature if secret key is provided
            if config.secret_key:
                signature = headers.get(config.signature_header)
                if not signature:
                    raise SignatureVerificationError(
                        f"Missing signature header: {config.signature_header}"
                    )

                if not self._verify_signature(
                    payload, signature, config.secret_key, config
                ):
                    raise SignatureVerificationError("Invalid signature")

                event.signature_verified = True

            # Determine event type
            event.event_type = self._determine_event_type(payload_data, config)

            # Validate payload schema
            self._validate_payload_schema(event)

            # Additional custom validation
            self._custom_validation(event, config)

            logger.debug(f"Validated webhook event: {event.event_id}")
            return event

        except (ValidationError, SignatureVerificationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating webhook: {e}")
            raise ValidationError(f"Validation failed: {e}")

    def _check_rate_limit(self, webhook_name: str, config: WebhookConfig) -> bool:
        """Check if webhook is within rate limits."""
        current_time = datetime.utcnow()
        minute_ago = current_time - timedelta(minutes=1)

        # Get recent requests for this webhook
        if webhook_name not in self.rate_limits:
            self.rate_limits[webhook_name] = []

        # Remove old entries
        self.rate_limits[webhook_name] = [
            timestamp
            for timestamp in self.rate_limits[webhook_name]
            if timestamp > minute_ago
        ]

        # Check if under limit
        if len(self.rate_limits[webhook_name]) >= config.rate_limit_per_minute:
            logger.warning(
                f"Rate limit exceeded for webhook {webhook_name}: "
                f"{len(self.rate_limits[webhook_name])} requests in last minute"
            )
            return False

        # Add current request
        self.rate_limits[webhook_name].append(current_time)
        return True

    def _verify_signature(
        self, payload: bytes, signature: str, secret: str, config: WebhookConfig
    ) -> bool:
        """Verify webhook signature."""
        try:
            # Handle different signature formats
            if config.signature_algorithm == "sha256":
                if config.signature_encoding == "hex":
                    expected_signature = hmac.new(
                        secret.encode("utf-8"), payload, hashlib.sha256
                    ).hexdigest()
                    # Handle prefixed signatures (e.g., "sha256=...")
                    if "=" in signature:
                        signature = signature.split("=", 1)[1]
                else:  # base64
                    expected_signature = base64.b64encode(
                        hmac.new(
                            secret.encode("utf-8"), payload, hashlib.sha256
                        ).digest()
                    ).decode("utf-8")
            else:
                logger.warning(
                    f"Unsupported signature algorithm: {config.signature_algorithm}"
                )
                return False

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def _determine_event_type(
        self, payload: Dict[str, Any], config: WebhookConfig
    ) -> WebhookEventType:
        """Determine the event type from payload."""
        # Try to determine from payload event field
        event_field = payload.get("event", "").lower()

        # SendGrid event mapping
        if config.name == "sendgrid":
            sendgrid_mapping = {
                "delivered": WebhookEventType.EMAIL_DELIVERY,
                "bounce": WebhookEventType.EMAIL_BOUNCE,
                "dropped": WebhookEventType.EMAIL_BOUNCE,
                "open": WebhookEventType.EMAIL_OPEN,
                "click": WebhookEventType.EMAIL_CLICK,
                "spamreport": WebhookEventType.EMAIL_SPAM,
                "unsubscribe": WebhookEventType.EMAIL_UNSUBSCRIBE,
                "group_unsubscribe": WebhookEventType.EMAIL_UNSUBSCRIBE,
            }
            return sendgrid_mapping.get(event_field, WebhookEventType.CUSTOM)

        # Stripe event mapping
        elif config.name == "stripe":
            if "payment_intent" in event_field and "succeeded" in event_field:
                return WebhookEventType.PAYMENT_SUCCESS
            elif "payment_intent" in event_field and "payment_failed" in event_field:
                return WebhookEventType.PAYMENT_FAILED

        # Engagement tracking
        elif config.name == "engagement":
            return WebhookEventType.ENGAGEMENT_EVENT

        # Default to first configured event type
        return config.event_types[0] if config.event_types else WebhookEventType.CUSTOM

    def _validate_payload_schema(self, event: WebhookEvent):
        """Validate payload against schema."""
        try:
            # Get schema for event type
            schema = self.default_schemas.get(event.event_type)
            config = self.webhook_configs.get(event.webhook_name)

            # Use custom schema if provided
            if config and config.validation_schema:
                schema = config.validation_schema

            if schema:
                validate(instance=event.payload, schema=schema)
                logger.debug(f"Schema validation passed for event {event.event_id}")
            else:
                logger.debug(
                    f"No schema validation for event type {event.event_type.value}"
                )

        except Exception as e:
            if HAS_JSONSCHEMA and hasattr(e, "message"):
                logger.error(f"Schema validation failed: {e.message}")
                raise ValidationError(
                    f"Schema validation failed: {e.message}",
                    field=getattr(e, "path", None),
                )
            else:
                logger.error(f"Schema validation failed: {e}")
                raise ValidationError(f"Schema validation failed: {e}")

    def _custom_validation(self, event: WebhookEvent, config: WebhookConfig):
        """Perform custom validation based on webhook type."""
        try:
            # Email validation
            if event.event_type in [
                WebhookEventType.EMAIL_DELIVERY,
                WebhookEventType.EMAIL_BOUNCE,
                WebhookEventType.EMAIL_OPEN,
                WebhookEventType.EMAIL_CLICK,
            ]:
                email = event.payload.get("email")
                if email and not self._is_valid_email(email):
                    raise ValidationError(
                        f"Invalid email format: {email}", field="email"
                    )

            # Payment validation
            elif event.event_type in [
                WebhookEventType.PAYMENT_SUCCESS,
                WebhookEventType.PAYMENT_FAILED,
            ]:
                amount = event.payload.get("amount")
                if amount is not None and amount < 0:
                    raise ValidationError("Amount cannot be negative", field="amount")

            # Engagement event validation
            elif event.event_type == WebhookEventType.ENGAGEMENT_EVENT:
                user_id = event.payload.get("user_id")
                if not user_id:
                    raise ValidationError("User ID is required", field="user_id")

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Custom validation error: {e}")
            raise ValidationError(f"Custom validation failed: {e}")

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        # More strict email validation that rejects consecutive dots
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            return False

        # Check for consecutive dots
        if ".." in email:
            return False

        # Check for leading/trailing dots in local part
        local_part = email.split("@")[0]
        if local_part.startswith(".") or local_part.endswith("."):
            return False

        return True

    def process_webhook(self, event: WebhookEvent) -> bool:
        """Process a validated webhook event with retry logic.

        Args:
            event: Validated webhook event

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # Store event
            event.status = WebhookStatus.PROCESSING
            self.storage.store_webhook_event(event.to_dict())

            # Get retry manager for this webhook
            retry_manager = self.retry_managers.get(event.webhook_name)
            if not retry_manager:
                logger.warning(f"No retry manager for webhook {event.webhook_name}")
                return self._process_event_handlers(event)

            # Process with retry logic
            def process_with_retry():
                return self._process_event_handlers(event)

            try:
                success = retry_manager.execute_with_retry(process_with_retry)
                if success:
                    event.status = WebhookStatus.COMPLETED
                    event.processed_at = datetime.utcnow()
                    logger.info(
                        f"Successfully processed webhook event {event.event_id}"
                    )
                else:
                    event.status = WebhookStatus.FAILED
                    logger.error(f"Failed to process webhook event {event.event_id}")

                # Update event in storage
                self.storage.update_webhook_event(event.event_id, event.to_dict())
                return success

            except Exception as e:
                event.status = WebhookStatus.FAILED
                event.last_error = str(e)
                event.retry_count += 1

                # Check if we should move to dead letter queue
                config = self.webhook_configs.get(event.webhook_name)
                if config and event.retry_count >= config.max_retries:
                    event.status = WebhookStatus.DEAD_LETTER
                    self._move_to_dead_letter_queue(event)
                    logger.error(
                        f"Moved webhook event {event.event_id} to dead letter queue after "
                        f"{event.retry_count} retries"
                    )
                else:
                    event.status = WebhookStatus.RETRYING
                    logger.warning(
                        f"Webhook event {event.event_id} failed, will retry "
                        f"(attempt {event.retry_count})"
                    )

                # Record error
                pipeline_error = PipelineError.from_exception(
                    exception=e,
                    stage="webhook_processing",
                    operation=f"process_{event.webhook_name}",
                    context={
                        "event_id": event.event_id,
                        "webhook_name": event.webhook_name,
                        "event_type": event.event_type.value,
                        "retry_count": event.retry_count,
                    },
                )
                self.error_manager.record_error(pipeline_error)

                # Update event in storage
                self.storage.update_webhook_event(event.event_id, event.to_dict())

                # Trigger alerts if critical
                if event.status == WebhookStatus.DEAD_LETTER:
                    self._trigger_dead_letter_alert(event)

                return False

        except Exception as e:
            logger.error(
                f"Unexpected error processing webhook event {event.event_id}: {e}"
            )
            return False

    def _process_event_handlers(self, event: WebhookEvent) -> bool:
        """Process event through registered handlers."""
        try:
            handlers = self.event_handlers.get(event.event_type, [])

            if not handlers:
                logger.warning(
                    f"No handlers registered for event type {event.event_type.value}"
                )
                return True  # Consider successful if no handlers

            success_count = 0
            for handler in handlers:
                try:
                    result = handler(event)
                    if result:
                        success_count += 1
                    else:
                        logger.warning(
                            f"Handler returned False for event {event.event_id}"
                        )
                except Exception as e:
                    logger.error(f"Handler failed for event {event.event_id}: {e}")

            # Consider successful if at least one handler succeeded
            return success_count > 0

        except Exception as e:
            logger.error(f"Error processing event handlers: {e}")
            return False

    def _move_to_dead_letter_queue(self, event: WebhookEvent):
        """Move event to dead letter queue."""
        try:
            dead_letter_data = {
                **event.to_dict(),
                "dead_letter_timestamp": datetime.utcnow().isoformat(),
                "reason": "Max retries exceeded",
            }

            self.storage.store_dead_letter_webhook(dead_letter_data)
            logger.info(f"Moved event {event.event_id} to dead letter queue")

        except Exception as e:
            logger.error(f"Error moving event to dead letter queue: {e}")

    def _trigger_dead_letter_alert(self, event: WebhookEvent):
        """Trigger alert for dead letter queue event."""
        try:
            from leadfactory.monitoring.alert_manager import Alert

            alert = Alert(
                rule_name="webhook_dead_letter",
                severity=AlertSeverity.HIGH,
                message=f"Webhook event {event.event_id} moved to dead letter queue",
                current_value=event.retry_count,
                threshold_value=self.webhook_configs[event.webhook_name].max_retries,
                timestamp=datetime.utcnow(),
                metadata={
                    "event_id": event.event_id,
                    "webhook_name": event.webhook_name,
                    "event_type": event.event_type.value,
                    "last_error": event.last_error,
                },
            )

            # Send alert through notification channels
            self.alert_manager._send_alert_notifications(alert)

        except Exception as e:
            logger.error(f"Error triggering dead letter alert: {e}")

    def get_webhook_stats(self, webhook_name: Optional[str] = None) -> Dict[str, Any]:
        """Get webhook processing statistics.

        Args:
            webhook_name: Optional webhook name to filter by

        Returns:
            Statistics dictionary
        """
        try:
            # Get stats from storage
            stats = self.storage.get_webhook_stats(webhook_name)

            # Add retry manager stats
            if webhook_name and webhook_name in self.retry_managers:
                retry_stats = self.retry_managers[webhook_name].get_stats()
                stats["retry_stats"] = retry_stats

            return stats

        except Exception as e:
            logger.error(f"Error getting webhook stats: {e}")
            return {}

    def get_dead_letter_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events from dead letter queue.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of dead letter events
        """
        try:
            return self.storage.get_dead_letter_webhooks(limit)
        except Exception as e:
            logger.error(f"Error getting dead letter events: {e}")
            return []

    def retry_dead_letter_event(self, event_id: str) -> bool:
        """Retry a dead letter event.

        Args:
            event_id: Event ID to retry

        Returns:
            True if retry was initiated successfully
        """
        try:
            # Get dead letter event
            dead_letter_event = self.storage.get_dead_letter_webhook(event_id)
            if not dead_letter_event:
                logger.error(f"Dead letter event not found: {event_id}")
                return False

            # Convert back to WebhookEvent
            event_data = dead_letter_event.copy()
            event_data.pop("dead_letter_timestamp", None)
            event_data.pop("reason", None)

            # Reset status and retry count
            event_data["status"] = WebhookStatus.PENDING.value
            event_data["retry_count"] = 0
            event_data["last_error"] = None

            # Convert timestamp strings back to datetime
            if isinstance(event_data["timestamp"], str):
                event_data["timestamp"] = datetime.fromisoformat(
                    event_data["timestamp"]
                )

            # Create new WebhookEvent
            event = WebhookEvent(**event_data)

            # Process the event
            success = self.process_webhook(event)

            if success:
                # Remove from dead letter queue
                self.storage.remove_dead_letter_webhook(event_id)
                logger.info(f"Successfully retried dead letter event {event_id}")
            else:
                logger.error(f"Failed to retry dead letter event {event_id}")

            return success

        except Exception as e:
            logger.error(f"Error retrying dead letter event {event_id}: {e}")
            return False
