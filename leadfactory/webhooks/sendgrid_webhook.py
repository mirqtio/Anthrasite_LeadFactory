#!/usr/bin/env python3
"""
SendGrid webhook handler for processing bounce events and other email events.

This module handles incoming webhooks from SendGrid to process bounce events,
spam complaints, unsubscribes, and other email delivery events.
"""

import base64
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Import database connection with fallback
try:
    from leadfactory.utils.e2e_db_connector import db_connection as DatabaseConnection
except ImportError:
    # Fallback for testing
    class DatabaseConnection:
        def __init__(self, db_path=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def execute(self, *args, **kwargs):
            pass

        def fetchall(self):
            return []

        def fetchone(self):
            return None

        def commit(self):
            pass


# Import logging with fallback
try:
    from leadfactory.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class EventType(Enum):
    """SendGrid webhook event types."""

    BOUNCE = "bounce"
    DROPPED = "dropped"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    DEFERRED = "deferred"
    SPAM_REPORT = "spamreport"
    UNSUBSCRIBE = "unsubscribe"
    GROUP_UNSUBSCRIBE = "group_unsubscribe"
    OPEN = "open"
    CLICK = "click"


class BounceType(Enum):
    """Types of email bounces."""

    HARD = "hard"
    SOFT = "soft"
    BLOCK = "block"


@dataclass
class BounceEvent:
    """Represents a bounce event from SendGrid."""

    email: str
    event: str
    timestamp: int
    bounce_type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    message_id: Optional[str] = None
    sg_event_id: Optional[str] = None
    sg_message_id: Optional[str] = None

    @classmethod
    def from_webhook_data(cls, data: Dict[str, Any]) -> "BounceEvent":
        """Create a BounceEvent from webhook data."""
        return cls(
            email=data.get("email", ""),
            event=data.get("event", ""),
            timestamp=data.get("timestamp", 0),
            bounce_type=data.get("type"),
            reason=data.get("reason"),
            status=data.get("status"),
            message_id=data.get("message_id"),
            sg_event_id=data.get("sg_event_id"),
            sg_message_id=data.get("sg_message_id"),
        )


class SendGridWebhookHandler:
    """Handles SendGrid webhook events."""

    def __init__(
        self, webhook_secret: Optional[str] = None, db_path: Optional[str] = None
    ):
        """Initialize the webhook handler.

        Args:
            webhook_secret: Secret for verifying webhook signatures
            db_path: Path to the database file
        """
        self.webhook_secret = webhook_secret
        self.db_path = db_path
        self.bounce_thresholds = {
            "warning": 0.05,  # 5% bounce rate warning
            "critical": 0.10,  # 10% bounce rate critical
            "block": 0.15,  # 15% bounce rate blocks sending
        }
        self.spam_thresholds = {
            "warning": 0.001,  # 0.1% spam rate warning
            "critical": 0.005,  # 0.5% spam rate critical
            "block": 0.01,  # 1% spam rate blocks sending
        }

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify the webhook signature from SendGrid.

        Args:
            payload: Raw webhook payload
            signature: Signature from SendGrid headers

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning(
                "No webhook secret configured, skipping signature verification"
            )
            return True

        try:
            # SendGrid uses HMAC-SHA256 with base64 encoding
            expected_signature = base64.b64encode(
                hmac.new(
                    self.webhook_secret.encode("utf-8"), payload, hashlib.sha256
                ).digest()
            ).decode("utf-8")

            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    def process_webhook_events(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process a list of webhook events.

        Args:
            events: List of webhook event dictionaries

        Returns:
            Dictionary with counts of processed events by type
        """
        event_counts = {}

        for event_data in events:
            try:
                event_type = event_data.get("event")
                if not event_type:
                    logger.warning("Event missing 'event' field, skipping")
                    continue

                # Count events by type
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

                # Process specific event types
                if event_type in [EventType.BOUNCE.value, EventType.DROPPED.value]:
                    self._process_bounce_event(event_data)
                elif event_type == EventType.SPAM_REPORT.value:
                    self._process_spam_event(event_data)
                elif event_type in [
                    EventType.UNSUBSCRIBE.value,
                    EventType.GROUP_UNSUBSCRIBE.value,
                ]:
                    self._process_unsubscribe_event(event_data)
                elif event_type == EventType.DELIVERED.value:
                    self._process_delivered_event(event_data)
                else:
                    logger.debug(
                        f"Processed {event_type} event for {event_data.get('email')}"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing webhook event: {e}",
                    extra={"event_data": event_data},
                )
                continue

        return event_counts

    def _process_bounce_event(self, event_data: Dict[str, Any]) -> None:
        """Process a bounce or dropped event.

        Args:
            event_data: Bounce event data from webhook
        """
        bounce_event = BounceEvent.from_webhook_data(event_data)

        logger.info(
            f"Processing bounce event for {bounce_event.email}: "
            f"type={bounce_event.bounce_type}, reason={bounce_event.reason}"
        )

        # Store bounce event in database
        self._store_bounce_event(bounce_event)

        # Update email status based on bounce type
        if bounce_event.bounce_type == BounceType.HARD.value:
            self._mark_email_permanently_bounced(bounce_event.email)
        elif bounce_event.bounce_type == BounceType.BLOCK.value:
            self._mark_email_blocked(bounce_event.email)
        else:
            # Soft bounce - increment retry count
            self._increment_soft_bounce_count(bounce_event.email)

        # Check if bounce rate thresholds are exceeded
        self._check_bounce_rate_thresholds()

    def _process_spam_event(self, event_data: Dict[str, Any]) -> None:
        """Process a spam complaint event.

        Args:
            event_data: Spam event data from webhook
        """
        email = event_data.get("email")
        logger.info(f"Processing spam complaint for {email}")

        # Store spam event and mark email as complained
        self._store_spam_event(event_data)
        self._mark_email_spam_complaint(email)

        # Check if spam rate thresholds are exceeded
        self._check_spam_rate_thresholds()

    def _process_unsubscribe_event(self, event_data: Dict[str, Any]) -> None:
        """Process an unsubscribe event.

        Args:
            event_data: Unsubscribe event data from webhook
        """
        email = event_data.get("email")
        logger.info(f"Processing unsubscribe for {email}")

        # Store unsubscribe event
        self._store_unsubscribe_event(event_data)
        self._mark_email_unsubscribed(email)

    def _process_delivered_event(self, event_data: Dict[str, Any]) -> None:
        """Process a delivered event.

        Args:
            event_data: Delivered event data from webhook
        """
        email = event_data.get("email")
        message_id = event_data.get("sg_message_id")

        # Update email status to delivered
        self._mark_email_delivered(email, message_id)

    def _store_bounce_event(self, bounce_event: BounceEvent) -> None:
        """Store bounce event in database.

        Args:
            bounce_event: BounceEvent object to store
        """
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    INSERT OR REPLACE INTO email_bounces
                    (email, event_type, bounce_type, reason, status, message_id,
                     sg_event_id, sg_message_id, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        bounce_event.email,
                        bounce_event.event,
                        bounce_event.bounce_type,
                        bounce_event.reason,
                        bounce_event.status,
                        bounce_event.message_id,
                        bounce_event.sg_event_id,
                        bounce_event.sg_message_id,
                        bounce_event.timestamp,
                        datetime.now().isoformat(),
                    ),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error storing bounce event: {e}")

    def _store_spam_event(self, event_data: Dict[str, Any]) -> None:
        """Store spam complaint event in database."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    INSERT OR REPLACE INTO email_spam_reports
                    (email, sg_event_id, sg_message_id, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        event_data.get("email"),
                        event_data.get("sg_event_id"),
                        event_data.get("sg_message_id"),
                        event_data.get("timestamp"),
                        datetime.now().isoformat(),
                    ),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error storing spam event: {e}")

    def _store_unsubscribe_event(self, event_data: Dict[str, Any]) -> None:
        """Store unsubscribe event in database."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    INSERT OR REPLACE INTO email_unsubscribes
                    (email, sg_event_id, sg_message_id, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        event_data.get("email"),
                        event_data.get("sg_event_id"),
                        event_data.get("sg_message_id"),
                        event_data.get("timestamp"),
                        datetime.now().isoformat(),
                    ),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error storing unsubscribe event: {e}")

    def _mark_email_permanently_bounced(self, email: str) -> None:
        """Mark an email as permanently bounced."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET status = 'hard_bounced', updated_at = ?
                    WHERE recipient_email = ?
                """,
                    (datetime.now().isoformat(), email),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking email as hard bounced: {e}")

    def _mark_email_blocked(self, email: str) -> None:
        """Mark an email as blocked."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET status = 'blocked', updated_at = ?
                    WHERE recipient_email = ?
                """,
                    (datetime.now().isoformat(), email),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking email as blocked: {e}")

    def _increment_soft_bounce_count(self, email: str) -> None:
        """Increment soft bounce count for an email."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET soft_bounce_count = COALESCE(soft_bounce_count, 0) + 1,
                        updated_at = ?
                    WHERE recipient_email = ?
                """,
                    (datetime.now().isoformat(), email),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error incrementing soft bounce count: {e}")

    def _mark_email_spam_complaint(self, email: str) -> None:
        """Mark an email as having a spam complaint."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET status = 'spam_complaint', updated_at = ?
                    WHERE recipient_email = ?
                """,
                    (datetime.now().isoformat(), email),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking email spam complaint: {e}")

    def _mark_email_unsubscribed(self, email: str) -> None:
        """Mark an email as unsubscribed."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET status = 'unsubscribed', updated_at = ?
                    WHERE recipient_email = ?
                """,
                    (datetime.now().isoformat(), email),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking email as unsubscribed: {e}")

    def _mark_email_delivered(self, email: str, message_id: Optional[str]) -> None:
        """Mark an email as delivered."""
        try:
            with DatabaseConnection(self.db_path) as db:
                db.execute(
                    """
                    UPDATE email_queue
                    SET status = 'delivered', delivered_at = ?, updated_at = ?
                    WHERE recipient_email = ? AND message_id = ?
                """,
                    (
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        email,
                        message_id,
                    ),
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking email as delivered: {e}")

    def _check_bounce_rate_thresholds(self) -> None:
        """Check if bounce rate thresholds are exceeded and take action."""
        try:
            # Calculate current bounce rate (last 24 hours)
            bounce_rate = self._calculate_recent_bounce_rate(hours=24)

            if bounce_rate >= self.bounce_thresholds["block"]:
                logger.critical(
                    f"Bounce rate {bounce_rate:.2%} exceeds block threshold "
                    f"{self.bounce_thresholds['block']:.2%} - blocking email sending"
                )
                self._trigger_email_sending_block("High bounce rate")
            elif bounce_rate >= self.bounce_thresholds["critical"]:
                logger.error(
                    f"Bounce rate {bounce_rate:.2%} exceeds critical threshold "
                    f"{self.bounce_thresholds['critical']:.2%}"
                )
                self._trigger_critical_alert("High bounce rate", bounce_rate)
            elif bounce_rate >= self.bounce_thresholds["warning"]:
                logger.warning(
                    f"Bounce rate {bounce_rate:.2%} exceeds warning threshold "
                    f"{self.bounce_thresholds['warning']:.2%}"
                )
                self._trigger_warning_alert("Elevated bounce rate", bounce_rate)
        except Exception as e:
            logger.error(f"Error checking bounce rate thresholds: {e}")

    def _check_spam_rate_thresholds(self) -> None:
        """Check if spam rate thresholds are exceeded and take action."""
        try:
            # Calculate current spam rate (last 24 hours)
            spam_rate = self._calculate_recent_spam_rate(hours=24)

            if spam_rate >= self.spam_thresholds["block"]:
                logger.critical(
                    f"Spam rate {spam_rate:.3%} exceeds block threshold "
                    f"{self.spam_thresholds['block']:.3%} - blocking email sending"
                )
                self._trigger_email_sending_block("High spam rate")
            elif spam_rate >= self.spam_thresholds["critical"]:
                logger.error(
                    f"Spam rate {spam_rate:.3%} exceeds critical threshold "
                    f"{self.spam_thresholds['critical']:.3%}"
                )
                self._trigger_critical_alert("High spam rate", spam_rate)
            elif spam_rate >= self.spam_thresholds["warning"]:
                logger.warning(
                    f"Spam rate {spam_rate:.3%} exceeds warning threshold "
                    f"{self.spam_thresholds['warning']:.3%}"
                )
                self._trigger_warning_alert("Elevated spam rate", spam_rate)
        except Exception as e:
            logger.error(f"Error checking spam rate thresholds: {e}")

    def _calculate_recent_bounce_rate(self, hours: int = 24) -> float:
        """Calculate bounce rate for recent time period."""
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            with DatabaseConnection(self.db_path) as db:
                # Get total emails sent in time period
                db.execute(
                    """
                    SELECT COUNT(*) FROM email_queue
                    WHERE created_at > ? AND status != 'pending'
                """,
                    (datetime.fromtimestamp(cutoff_time).isoformat(),),
                )
                total_sent = db.fetchone()[0] or 0

                # Get bounce count in time period
                db.execute(
                    """
                    SELECT COUNT(*) FROM email_bounces
                    WHERE timestamp > ?
                """,
                    (cutoff_time,),
                )
                bounce_count = db.fetchone()[0] or 0

                return bounce_count / total_sent if total_sent > 0 else 0.0
        except Exception as e:
            logger.error(f"Error calculating bounce rate: {e}")
            return 0.0

    def _calculate_recent_spam_rate(self, hours: int = 24) -> float:
        """Calculate spam rate for recent time period."""
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            with DatabaseConnection(self.db_path) as db:
                # Get total emails sent in time period
                db.execute(
                    """
                    SELECT COUNT(*) FROM email_queue
                    WHERE created_at > ? AND status != 'pending'
                """,
                    (datetime.fromtimestamp(cutoff_time).isoformat(),),
                )
                total_sent = db.fetchone()[0] or 0

                # Get spam complaint count in time period
                db.execute(
                    """
                    SELECT COUNT(*) FROM email_spam_reports
                    WHERE timestamp > ?
                """,
                    (cutoff_time,),
                )
                spam_count = db.fetchone()[0] or 0

                return spam_count / total_sent if total_sent > 0 else 0.0
        except Exception as e:
            logger.error(f"Error calculating spam rate: {e}")
            return 0.0

    def _trigger_email_sending_block(self, reason: str) -> None:
        """Trigger a block on email sending."""
        logger.critical(f"BLOCKING EMAIL SENDING: {reason}")
        # In a real implementation, this would set a flag in the database
        # or configuration system to prevent further email sending

    def _trigger_critical_alert(self, alert_type: str, rate: float) -> None:
        """Trigger a critical alert."""
        logger.error(f"CRITICAL ALERT: {alert_type} - Rate: {rate:.3%}")
        # In a real implementation, this would send alerts to administrators

    def _trigger_warning_alert(self, alert_type: str, rate: float) -> None:
        """Trigger a warning alert."""
        logger.warning(f"WARNING ALERT: {alert_type} - Rate: {rate:.3%}")
        # In a real implementation, this would send warnings to administrators


def create_webhook_tables(db_path: Optional[str] = None) -> None:
    """Create database tables for webhook event storage.

    Args:
        db_path: Path to the database file
    """
    try:
        with DatabaseConnection(db_path) as db:
            # Create bounce events table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS email_bounces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    bounce_type TEXT,
                    reason TEXT,
                    status TEXT,
                    message_id TEXT,
                    sg_event_id TEXT,
                    sg_message_id TEXT,
                    timestamp INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(email, sg_event_id)
                )
            """
            )

            # Create spam reports table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS email_spam_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    sg_event_id TEXT,
                    sg_message_id TEXT,
                    timestamp INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(email, sg_event_id)
                )
            """
            )

            # Create unsubscribes table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS email_unsubscribes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    sg_event_id TEXT,
                    sg_message_id TEXT,
                    timestamp INTEGER,
                    created_at TEXT NOT NULL,
                    UNIQUE(email, sg_event_id)
                )
            """
            )

            # Add columns to email_queue if they don't exist
            try:
                db.execute(
                    "ALTER TABLE email_queue ADD COLUMN soft_bounce_count INTEGER DEFAULT 0"
                )
            except:
                pass  # Column already exists

            try:
                db.execute("ALTER TABLE email_queue ADD COLUMN delivered_at TEXT")
            except:
                pass  # Column already exists

            db.commit()
            logger.info("Webhook database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating webhook tables: {e}")
