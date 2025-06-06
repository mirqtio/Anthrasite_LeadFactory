#!/usr/bin/env python3
"""
Dead Letter Queue Management for Failed Webhooks.

This module provides comprehensive management of permanently failed webhooks,
including classification, analytics, manual intervention, and automated cleanup.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from leadfactory.monitoring.alert_manager import Alert, AlertManager, AlertSeverity
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class DeadLetterReason(Enum):
    """Reasons for moving events to dead letter queue."""

    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    INVALID_PAYLOAD = "invalid_payload"
    SIGNATURE_VERIFICATION_FAILED = "signature_verification_failed"
    WEBHOOK_DISABLED = "webhook_disabled"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    HANDLER_NOT_FOUND = "handler_not_found"
    PERMANENT_FAILURE = "permanent_failure"
    MANUAL_MOVE = "manual_move"


class DeadLetterStatus(Enum):
    """Status of dead letter events."""

    ACTIVE = "active"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
    REPROCESSING = "reprocessing"


class DeadLetterCategory(Enum):
    """Categories for organizing dead letter events."""

    CRITICAL = "critical"  # Payment, security events
    IMPORTANT = "important"  # User actions, notifications
    NORMAL = "normal"  # Email events, analytics
    LOW = "low"  # Logging, metrics


@dataclass
class DeadLetterEvent:
    """Represents an event in the dead letter queue."""

    id: str = field(default_factory=lambda: str(uuid4()))
    original_event_id: str = ""
    webhook_name: str = ""
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    original_timestamp: datetime = field(default_factory=datetime.utcnow)
    dead_letter_timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: DeadLetterReason = DeadLetterReason.MAX_RETRIES_EXCEEDED
    status: DeadLetterStatus = DeadLetterStatus.ACTIVE
    category: DeadLetterCategory = DeadLetterCategory.NORMAL
    retry_attempts: int = 0
    last_error: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    investigation_started: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "original_event_id": self.original_event_id,
            "webhook_name": self.webhook_name,
            "event_type": self.event_type,
            "payload": self.payload,
            "headers": self.headers,
            "original_timestamp": self.original_timestamp.isoformat(),
            "dead_letter_timestamp": self.dead_letter_timestamp.isoformat(),
            "reason": self.reason.value,
            "status": self.status.value,
            "category": self.category.value,
            "retry_attempts": self.retry_attempts,
            "last_error": self.last_error,
            "tags": list(self.tags),
            "notes": self.notes,
            "assigned_to": self.assigned_to,
            "investigation_started": (
                self.investigation_started.isoformat()
                if self.investigation_started
                else None
            ),
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_webhook_event(
        cls,
        webhook_event: Dict[str, Any],
        reason: DeadLetterReason,
        last_error: Optional[str] = None,
    ) -> "DeadLetterEvent":
        """Create dead letter event from webhook event."""
        # Determine category based on webhook type and event type
        category = cls._determine_category(
            webhook_event.get("webhook_name", ""),
            webhook_event.get("event_type", ""),
        )

        return cls(
            original_event_id=webhook_event.get("event_id", ""),
            webhook_name=webhook_event.get("webhook_name", ""),
            event_type=webhook_event.get("event_type", ""),
            payload=webhook_event.get("payload", {}),
            headers=webhook_event.get("headers", {}),
            original_timestamp=datetime.fromisoformat(
                webhook_event.get("timestamp", datetime.utcnow().isoformat())
            ),
            reason=reason,
            category=category,
            retry_attempts=webhook_event.get("retry_count", 0),
            last_error=last_error,
        )

    @staticmethod
    def _determine_category(webhook_name: str, event_type: str) -> DeadLetterCategory:
        """Determine category based on webhook and event type."""
        # Critical: Payment and security events
        if (
            webhook_name in ["stripe", "paypal", "square"]
            or "payment" in event_type.lower()
        ):
            return DeadLetterCategory.CRITICAL

        if "security" in webhook_name.lower() or "auth" in webhook_name.lower():
            return DeadLetterCategory.CRITICAL

        # Important: User actions and notifications
        if event_type in ["user_signup", "user_login", "form_submission"]:
            return DeadLetterCategory.IMPORTANT

        if webhook_name in ["sendgrid", "mailgun"] and "bounce" in event_type.lower():
            return DeadLetterCategory.IMPORTANT

        # Low: Analytics and logging
        if webhook_name in ["analytics", "logs", "metrics"]:
            return DeadLetterCategory.LOW

        # Default to normal
        return DeadLetterCategory.NORMAL


class DeadLetterQueueManager:
    """Manages the dead letter queue for failed webhooks."""

    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """Initialize dead letter queue manager.

        Args:
            alert_manager: Alert manager for notifications
        """
        self.storage = get_storage_instance()
        self.alert_manager = alert_manager or AlertManager()

        # Configuration
        self.auto_archive_days = 30  # Archive events older than 30 days
        self.max_reprocess_attempts = 3
        self.alert_thresholds = {
            DeadLetterCategory.CRITICAL: 1,  # Alert on any critical event
            DeadLetterCategory.IMPORTANT: 5,  # Alert on 5+ important events
            DeadLetterCategory.NORMAL: 20,  # Alert on 20+ normal events
            DeadLetterCategory.LOW: 100,  # Alert on 100+ low priority events
        }

        logger.info("Initialized DeadLetterQueueManager")

    def add_event(
        self,
        webhook_event: Dict[str, Any],
        reason: DeadLetterReason,
        last_error: Optional[str] = None,
        tags: Optional[Set[str]] = None,
    ) -> str:
        """Add an event to the dead letter queue.

        Args:
            webhook_event: Original webhook event data
            reason: Reason for moving to dead letter queue
            last_error: Last error message
            tags: Optional tags for categorization

        Returns:
            Dead letter event ID
        """
        try:
            # Create dead letter event
            dl_event = DeadLetterEvent.from_webhook_event(
                webhook_event, reason, last_error
            )

            if tags:
                dl_event.tags.update(tags)

            # Add contextual tags
            dl_event.tags.add(f"webhook:{dl_event.webhook_name}")
            dl_event.tags.add(f"reason:{reason.value}")
            dl_event.tags.add(f"category:{dl_event.category.value}")

            # Store in database
            self.storage.store_dead_letter_event(dl_event.to_dict())

            # Check alert thresholds
            self._check_alert_thresholds(dl_event.category)

            # Log the event
            logger.warning(
                f"Added event to dead letter queue: {dl_event.id} "
                f"(reason: {reason.value}, category: {dl_event.category.value})"
            )

            return dl_event.id

        except Exception as e:
            logger.error(f"Error adding event to dead letter queue: {e}")
            return ""

    def get_events(
        self,
        status: Optional[DeadLetterStatus] = None,
        category: Optional[DeadLetterCategory] = None,
        webhook_name: Optional[str] = None,
        reason: Optional[DeadLetterReason] = None,
        assigned_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DeadLetterEvent]:
        """Get dead letter events with filtering.

        Args:
            status: Filter by status
            category: Filter by category
            webhook_name: Filter by webhook name
            reason: Filter by reason
            assigned_to: Filter by assignee
            limit: Maximum number of events to return
            offset: Offset for pagination

        Returns:
            List of dead letter events
        """
        try:
            # Build filter criteria
            filters = {}
            if status:
                filters["status"] = status.value
            if category:
                filters["category"] = category.value
            if webhook_name:
                filters["webhook_name"] = webhook_name
            if reason:
                filters["reason"] = reason.value
            if assigned_to:
                filters["assigned_to"] = assigned_to

            # Get events from storage
            event_data_list = self.storage.get_dead_letter_events(
                filters=filters, limit=limit, offset=offset
            )

            # Convert to DeadLetterEvent objects
            events = []
            for event_data in event_data_list:
                # Convert string fields back to enums
                event_data["reason"] = DeadLetterReason(event_data["reason"])
                event_data["status"] = DeadLetterStatus(event_data["status"])
                event_data["category"] = DeadLetterCategory(event_data["category"])

                # Convert timestamp strings back to datetime
                if isinstance(event_data["original_timestamp"], str):
                    event_data["original_timestamp"] = datetime.fromisoformat(
                        event_data["original_timestamp"]
                    )
                if isinstance(event_data["dead_letter_timestamp"], str):
                    event_data["dead_letter_timestamp"] = datetime.fromisoformat(
                        event_data["dead_letter_timestamp"]
                    )
                if event_data["investigation_started"]:
                    event_data["investigation_started"] = datetime.fromisoformat(
                        event_data["investigation_started"]
                    )

                # Convert tags list back to set
                event_data["tags"] = set(event_data.get("tags", []))

                events.append(DeadLetterEvent(**event_data))

            return events

        except Exception as e:
            logger.error(f"Error getting dead letter events: {e}")
            return []

    def get_event(self, event_id: str) -> Optional[DeadLetterEvent]:
        """Get a specific dead letter event.

        Args:
            event_id: Dead letter event ID

        Returns:
            Dead letter event or None if not found
        """
        events = self.get_events()
        for event in events:
            if event.id == event_id:
                return event
        return None

    def update_event_status(
        self,
        event_id: str,
        status: DeadLetterStatus,
        notes: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> bool:
        """Update the status of a dead letter event.

        Args:
            event_id: Dead letter event ID
            status: New status
            notes: Optional notes
            assigned_to: Optional assignee

        Returns:
            True if updated successfully
        """
        try:
            update_data = {"status": status.value}

            if notes:
                update_data["notes"] = notes

            if assigned_to:
                update_data["assigned_to"] = assigned_to

            if status == DeadLetterStatus.INVESTIGATING:
                update_data["investigation_started"] = datetime.utcnow().isoformat()

            success = self.storage.update_dead_letter_event(event_id, update_data)

            if success:
                logger.info(
                    f"Updated dead letter event {event_id} status to {status.value}"
                )

            return success

        except Exception as e:
            logger.error(f"Error updating dead letter event status: {e}")
            return False

    def reprocess_event(self, event_id: str, force: bool = False) -> bool:
        """Attempt to reprocess a dead letter event.

        Args:
            event_id: Dead letter event ID
            force: Force reprocessing even if max attempts exceeded

        Returns:
            True if reprocessing was initiated successfully
        """
        try:
            # Get the event
            event = self.get_event(event_id)
            if not event:
                logger.error(f"Dead letter event not found: {event_id}")
                return False

            # Check if we can reprocess
            if not force and event.retry_attempts >= self.max_reprocess_attempts:
                logger.warning(
                    f"Event {event_id} has exceeded max reprocess attempts "
                    f"({self.max_reprocess_attempts})"
                )
                return False

            # Update status to reprocessing
            self.update_event_status(event_id, DeadLetterStatus.REPROCESSING)

            # Import here to avoid circular imports
            from leadfactory.webhooks.webhook_validator import (
                WebhookEvent,
                WebhookStatus,
            )

            # Create new webhook event from dead letter data
            webhook_event = WebhookEvent(
                event_id=str(uuid4()),  # New event ID
                webhook_name=event.webhook_name,
                payload=event.payload,
                headers=event.headers,
                timestamp=datetime.utcnow(),  # Current timestamp
                status=WebhookStatus.PENDING,
                retry_count=0,  # Reset retry count
            )

            # Process the event
            from leadfactory.webhooks.webhook_validator import WebhookValidator

            validator = WebhookValidator()
            success = validator.process_webhook(webhook_event)

            if success:
                # Mark as resolved
                self.update_event_status(
                    event_id,
                    DeadLetterStatus.RESOLVED,
                    notes=f"Successfully reprocessed at {datetime.utcnow().isoformat()}",
                )
                logger.info(f"Successfully reprocessed dead letter event {event_id}")
            else:
                # Increment retry attempts
                self.storage.update_dead_letter_event(
                    event_id, {"retry_attempts": event.retry_attempts + 1}
                )
                # Reset status to active
                self.update_event_status(
                    event_id,
                    DeadLetterStatus.ACTIVE,
                    notes=f"Reprocessing failed at {datetime.utcnow().isoformat()}",
                )
                logger.error(f"Failed to reprocess dead letter event {event_id}")

            return success

        except Exception as e:
            logger.error(f"Error reprocessing dead letter event {event_id}: {e}")
            return False

    def bulk_reprocess(
        self,
        filters: Optional[Dict[str, Any]] = None,
        max_events: int = 10,
    ) -> Dict[str, int]:
        """Bulk reprocess dead letter events.

        Args:
            filters: Optional filters for selecting events
            max_events: Maximum number of events to reprocess

        Returns:
            Dictionary with success/failure counts
        """
        try:
            # Get events to reprocess
            status_filter = filters.get("status") if filters else None
            category_filter = filters.get("category") if filters else None
            webhook_filter = filters.get("webhook_name") if filters else None

            events = self.get_events(
                status=status_filter,
                category=category_filter,
                webhook_name=webhook_filter,
                limit=max_events,
            )

            # Filter to only active events if no status specified
            if not status_filter:
                events = [e for e in events if e.status == DeadLetterStatus.ACTIVE]

            results = {"successful": 0, "failed": 0, "skipped": 0}

            for event in events:
                try:
                    if event.retry_attempts >= self.max_reprocess_attempts:
                        results["skipped"] += 1
                        continue

                    success = self.reprocess_event(event.id)
                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1

                except Exception as e:
                    logger.error(f"Error in bulk reprocess for event {event.id}: {e}")
                    results["failed"] += 1

            logger.info(
                f"Bulk reprocess completed: {results['successful']} successful, "
                f"{results['failed']} failed, {results['skipped']} skipped"
            )

            return results

        except Exception as e:
            logger.error(f"Error in bulk reprocess: {e}")
            return {"successful": 0, "failed": 0, "skipped": 0}

    def archive_old_events(self, days: Optional[int] = None) -> int:
        """Archive old dead letter events.

        Args:
            days: Number of days old to archive (default from config)

        Returns:
            Number of events archived
        """
        try:
            archive_days = days or self.auto_archive_days
            cutoff_date = datetime.utcnow() - timedelta(days=archive_days)

            # Get old resolved events
            events = self.get_events(status=DeadLetterStatus.RESOLVED, limit=1000)
            old_events = [e for e in events if e.dead_letter_timestamp < cutoff_date]

            archived_count = 0
            for event in old_events:
                try:
                    success = self.update_event_status(
                        event.id,
                        DeadLetterStatus.ARCHIVED,
                        notes=f"Auto-archived after {archive_days} days",
                    )
                    if success:
                        archived_count += 1
                except Exception as e:
                    logger.error(f"Error archiving event {event.id}: {e}")

            if archived_count > 0:
                logger.info(f"Archived {archived_count} old dead letter events")

            return archived_count

        except Exception as e:
            logger.error(f"Error archiving old events: {e}")
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get dead letter queue statistics.

        Returns:
            Statistics dictionary
        """
        try:
            stats = {
                "total_events": 0,
                "by_status": {},
                "by_category": {},
                "by_reason": {},
                "by_webhook": {},
                "oldest_event": None,
                "newest_event": None,
                "events_last_24h": 0,
                "events_last_7d": 0,
            }

            # Get all events (this might need pagination for large datasets)
            all_events = self.get_events(limit=10000)
            stats["total_events"] = len(all_events)

            if not all_events:
                return stats

            # Calculate distributions
            for event in all_events:
                # By status
                status = event.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                # By category
                category = event.category.value
                stats["by_category"][category] = (
                    stats["by_category"].get(category, 0) + 1
                )

                # By reason
                reason = event.reason.value
                stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1

                # By webhook
                webhook = event.webhook_name
                stats["by_webhook"][webhook] = stats["by_webhook"].get(webhook, 0) + 1

            # Calculate time-based stats
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            stats["events_last_24h"] = len(
                [e for e in all_events if e.dead_letter_timestamp > day_ago]
            )
            stats["events_last_7d"] = len(
                [e for e in all_events if e.dead_letter_timestamp > week_ago]
            )

            # Oldest and newest events
            sorted_events = sorted(all_events, key=lambda x: x.dead_letter_timestamp)
            stats["oldest_event"] = sorted_events[0].dead_letter_timestamp.isoformat()
            stats["newest_event"] = sorted_events[-1].dead_letter_timestamp.isoformat()

            return stats

        except Exception as e:
            logger.error(f"Error getting dead letter statistics: {e}")
            return {}

    def _check_alert_thresholds(self, category: DeadLetterCategory):
        """Check if alert thresholds are exceeded for a category."""
        try:
            threshold = self.alert_thresholds.get(category, 999999)

            # Get active events count for this category
            active_events = self.get_events(
                status=DeadLetterStatus.ACTIVE,
                category=category,
                limit=threshold + 1,
            )

            if len(active_events) >= threshold:
                # Trigger alert
                alert = Alert(
                    rule_name=f"dead_letter_threshold_{category.value}",
                    severity=(
                        AlertSeverity.HIGH
                        if category == DeadLetterCategory.CRITICAL
                        else AlertSeverity.MEDIUM
                    ),
                    message=f"Dead letter queue threshold exceeded for {category.value} events",
                    current_value=len(active_events),
                    threshold_value=threshold,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "category": category.value,
                        "threshold": threshold,
                        "active_events": len(active_events),
                    },
                )

                self.alert_manager._send_alert_notifications(alert)
                logger.warning(
                    f"Alert triggered for dead letter threshold: {category.value}"
                )

        except Exception as e:
            logger.error(f"Error checking alert thresholds: {e}")

    def cleanup_old_events(self, days: int = 90) -> int:
        """Delete very old archived events to free up storage.

        Args:
            days: Number of days old to delete

        Returns:
            Number of events deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get old archived events
            events = self.get_events(status=DeadLetterStatus.ARCHIVED, limit=1000)
            old_events = [e for e in events if e.dead_letter_timestamp < cutoff_date]

            deleted_count = 0
            for event in old_events:
                try:
                    success = self.storage.delete_dead_letter_event(event.id)
                    if success:
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting event {event.id}: {e}")

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old archived dead letter events")

            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")
            return 0
