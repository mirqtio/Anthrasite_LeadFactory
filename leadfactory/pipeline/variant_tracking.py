"""
Variant Tracking System for A/B Testing.

This module provides functionality for tracking variant performance metrics,
events, and analytics throughout the pipeline execution.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Types of trackable events."""

    VARIANT_ASSIGNED = "variant_assigned"
    PIPELINE_STARTED = "pipeline_started"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    EMAIL_SENT = "email_sent"
    EMAIL_DELIVERED = "email_delivered"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_BOUNCED = "email_bounced"
    EMAIL_UNSUBSCRIBED = "email_unsubscribed"
    CONVERSION = "conversion"
    CUSTOM_EVENT = "custom_event"


@dataclass
class TrackingEvent:
    """Represents a tracking event."""

    id: str = field(default_factory=lambda: str(uuid4()))
    variant_id: str = ""
    business_id: int = 0
    event_type: EventType = EventType.CUSTOM_EVENT
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    stage: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "variant_id": self.variant_id,
            "business_id": self.business_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "properties": self.properties,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackingEvent":
        """Create from dictionary for deserialization."""
        return cls(
            id=data["id"],
            variant_id=data["variant_id"],
            business_id=data["business_id"],
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            stage=data.get("stage"),
            properties=data.get("properties", {}),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
        )


@dataclass
class VariantMetrics:
    """Aggregated metrics for a variant."""

    variant_id: str
    variant_name: str = ""
    total_assignments: int = 0
    pipeline_starts: int = 0
    pipeline_completions: int = 0
    pipeline_failures: int = 0
    emails_sent: int = 0
    emails_delivered: int = 0
    emails_opened: int = 0
    emails_clicked: int = 0
    emails_bounced: int = 0
    emails_unsubscribed: int = 0
    conversions: int = 0
    total_cost_cents: float = 0.0
    avg_processing_time_seconds: float = 0.0

    @property
    def pipeline_success_rate(self) -> float:
        """Calculate pipeline success rate."""
        if self.pipeline_starts == 0:
            return 0.0
        return self.pipeline_completions / self.pipeline_starts

    @property
    def email_delivery_rate(self) -> float:
        """Calculate email delivery rate."""
        if self.emails_sent == 0:
            return 0.0
        return self.emails_delivered / self.emails_sent

    @property
    def email_open_rate(self) -> float:
        """Calculate email open rate."""
        if self.emails_delivered == 0:
            return 0.0
        return self.emails_opened / self.emails_delivered

    @property
    def email_click_rate(self) -> float:
        """Calculate email click rate."""
        if self.emails_delivered == 0:
            return 0.0
        return self.emails_clicked / self.emails_delivered

    @property
    def email_bounce_rate(self) -> float:
        """Calculate email bounce rate."""
        if self.emails_sent == 0:
            return 0.0
        return self.emails_bounced / self.emails_sent

    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        if self.emails_delivered == 0:
            return 0.0
        return self.conversions / self.emails_delivered

    @property
    def cost_per_conversion(self) -> float:
        """Calculate cost per conversion."""
        if self.conversions == 0:
            return 0.0
        return self.total_cost_cents / self.conversions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "total_assignments": self.total_assignments,
            "pipeline_starts": self.pipeline_starts,
            "pipeline_completions": self.pipeline_completions,
            "pipeline_failures": self.pipeline_failures,
            "emails_sent": self.emails_sent,
            "emails_delivered": self.emails_delivered,
            "emails_opened": self.emails_opened,
            "emails_clicked": self.emails_clicked,
            "emails_bounced": self.emails_bounced,
            "emails_unsubscribed": self.emails_unsubscribed,
            "conversions": self.conversions,
            "total_cost_cents": self.total_cost_cents,
            "avg_processing_time_seconds": self.avg_processing_time_seconds,
            "pipeline_success_rate": self.pipeline_success_rate,
            "email_delivery_rate": self.email_delivery_rate,
            "email_open_rate": self.email_open_rate,
            "email_click_rate": self.email_click_rate,
            "email_bounce_rate": self.email_bounce_rate,
            "conversion_rate": self.conversion_rate,
            "cost_per_conversion": self.cost_per_conversion,
        }


class VariantTracker:
    """Tracks variant events and metrics."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or ":memory:"
        self._init_database()

    def _init_database(self):
        """Initialize the tracking database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS variant_events (
                        id TEXT PRIMARY KEY,
                        variant_id TEXT NOT NULL,
                        business_id INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        stage TEXT,
                        properties TEXT,
                        session_id TEXT,
                        user_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_variant_events_variant_id
                    ON variant_events(variant_id)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_variant_events_business_id
                    ON variant_events(business_id)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_variant_events_timestamp
                    ON variant_events(timestamp)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_variant_events_event_type
                    ON variant_events(event_type)
                """
                )

                conn.commit()
                logger.info("Variant tracking database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize tracking database: {e}")
            raise

    def track_event(self, event: TrackingEvent) -> bool:
        """Track a variant event."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO variant_events
                    (id, variant_id, business_id, event_type, timestamp, stage, properties, session_id, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.id,
                        event.variant_id,
                        event.business_id,
                        event.event_type.value,
                        event.timestamp,
                        event.stage,
                        json.dumps(event.properties),
                        event.session_id,
                        event.user_id,
                    ),
                )
                conn.commit()

            logger.debug(
                f"Tracked event: {event.event_type.value} for variant {event.variant_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return False

    def track_variant_assignment(
        self,
        variant_id: str,
        business_id: int,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track variant assignment."""
        event = TrackingEvent(
            variant_id=variant_id,
            business_id=business_id,
            event_type=EventType.VARIANT_ASSIGNED,
            session_id=session_id,
            user_id=user_id,
            properties=properties or {},
        )
        return self.track_event(event)

    def track_pipeline_start(
        self,
        variant_id: str,
        business_id: int,
        session_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track pipeline start."""
        event = TrackingEvent(
            variant_id=variant_id,
            business_id=business_id,
            event_type=EventType.PIPELINE_STARTED,
            session_id=session_id,
            properties=properties or {},
        )
        return self.track_event(event)

    def track_stage_completion(
        self,
        variant_id: str,
        business_id: int,
        stage: str,
        duration_seconds: Optional[float] = None,
        cost_cents: Optional[float] = None,
        session_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track stage completion."""
        event_properties = properties or {}
        if duration_seconds is not None:
            event_properties["duration_seconds"] = duration_seconds
        if cost_cents is not None:
            event_properties["cost_cents"] = cost_cents

        event = TrackingEvent(
            variant_id=variant_id,
            business_id=business_id,
            event_type=EventType.STAGE_COMPLETED,
            stage=stage,
            session_id=session_id,
            properties=event_properties,
        )
        return self.track_event(event)

    def track_email_event(
        self,
        variant_id: str,
        business_id: int,
        event_type: EventType,
        email_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track email-related events."""
        if event_type not in [
            EventType.EMAIL_SENT,
            EventType.EMAIL_DELIVERED,
            EventType.EMAIL_OPENED,
            EventType.EMAIL_CLICKED,
            EventType.EMAIL_BOUNCED,
            EventType.EMAIL_UNSUBSCRIBED,
        ]:
            raise ValueError(f"Invalid email event type: {event_type}")

        event_properties = properties or {}
        if email_id:
            event_properties["email_id"] = email_id

        event = TrackingEvent(
            variant_id=variant_id,
            business_id=business_id,
            event_type=event_type,
            properties=event_properties,
        )
        return self.track_event(event)

    def track_conversion(
        self,
        variant_id: str,
        business_id: int,
        conversion_value: Optional[float] = None,
        conversion_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track conversion event."""
        event_properties = properties or {}
        if conversion_value is not None:
            event_properties["conversion_value"] = conversion_value
        if conversion_type:
            event_properties["conversion_type"] = conversion_type

        event = TrackingEvent(
            variant_id=variant_id,
            business_id=business_id,
            event_type=EventType.CONVERSION,
            properties=event_properties,
        )
        return self.track_event(event)

    def get_events(
        self,
        variant_id: Optional[str] = None,
        business_id: Optional[int] = None,
        event_type: Optional[EventType] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TrackingEvent]:
        """Get events with optional filtering."""
        try:
            query = "SELECT * FROM variant_events WHERE 1=1"
            params = []

            if variant_id:
                query += " AND variant_id = ?"
                params.append(variant_id)

            if business_id:
                query += " AND business_id = ?"
                params.append(business_id)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

            events = []
            for row in rows:
                event = TrackingEvent(
                    id=row["id"],
                    variant_id=row["variant_id"],
                    business_id=row["business_id"],
                    event_type=EventType(row["event_type"]),
                    timestamp=row["timestamp"],
                    stage=row["stage"],
                    properties=(
                        json.loads(row["properties"]) if row["properties"] else {}
                    ),
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                )
                events.append(event)

            return events

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def get_variant_metrics(
        self,
        variant_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> VariantMetrics:
        """Get aggregated metrics for a variant."""
        try:
            # Build time filter
            time_filter = ""
            params = [variant_id]

            if start_time:
                time_filter += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                time_filter += " AND timestamp <= ?"
                params.append(end_time)

            with sqlite3.connect(self.db_path) as conn:
                # Get event counts
                cursor = conn.execute(
                    f"""
                    SELECT event_type, COUNT(*) as count
                    FROM variant_events
                    WHERE variant_id = ? {time_filter}
                    GROUP BY event_type
                """,
                    params,
                )

                event_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get cost and timing data
                cursor = conn.execute(
                    f"""
                    SELECT
                        AVG(CAST(JSON_EXTRACT(properties, '$.duration_seconds') AS REAL)) as avg_duration,
                        SUM(CAST(JSON_EXTRACT(properties, '$.cost_cents') AS REAL)) as total_cost
                    FROM variant_events
                    WHERE variant_id = ? {time_filter}
                    AND event_type = 'stage_completed'
                    AND JSON_EXTRACT(properties, '$.duration_seconds') IS NOT NULL
                """,
                    params,
                )

                timing_row = cursor.fetchone()
                avg_duration = timing_row[0] if timing_row[0] else 0.0
                total_cost = timing_row[1] if timing_row[1] else 0.0

            metrics = VariantMetrics(
                variant_id=variant_id,
                total_assignments=event_counts.get(EventType.VARIANT_ASSIGNED.value, 0),
                pipeline_starts=event_counts.get(EventType.PIPELINE_STARTED.value, 0),
                pipeline_completions=event_counts.get(
                    EventType.PIPELINE_COMPLETED.value, 0
                ),
                pipeline_failures=event_counts.get(EventType.PIPELINE_FAILED.value, 0),
                emails_sent=event_counts.get(EventType.EMAIL_SENT.value, 0),
                emails_delivered=event_counts.get(EventType.EMAIL_DELIVERED.value, 0),
                emails_opened=event_counts.get(EventType.EMAIL_OPENED.value, 0),
                emails_clicked=event_counts.get(EventType.EMAIL_CLICKED.value, 0),
                emails_bounced=event_counts.get(EventType.EMAIL_BOUNCED.value, 0),
                emails_unsubscribed=event_counts.get(
                    EventType.EMAIL_UNSUBSCRIBED.value, 0
                ),
                conversions=event_counts.get(EventType.CONVERSION.value, 0),
                total_cost_cents=total_cost,
                avg_processing_time_seconds=avg_duration,
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to get variant metrics: {e}")
            return VariantMetrics(variant_id=variant_id)

    def get_all_variant_metrics(
        self, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> List[VariantMetrics]:
        """Get metrics for all variants."""
        try:
            # Get all variant IDs
            time_filter = ""
            params = []

            if start_time:
                time_filter += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                time_filter += " AND timestamp <= ?"
                params.append(end_time)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"""
                    SELECT DISTINCT variant_id
                    FROM variant_events
                    WHERE 1=1 {time_filter}
                """,
                    params,
                )

                variant_ids = [row[0] for row in cursor.fetchall()]

            # Get metrics for each variant
            all_metrics = []
            for variant_id in variant_ids:
                metrics = self.get_variant_metrics(variant_id, start_time, end_time)
                all_metrics.append(metrics)

            return all_metrics

        except Exception as e:
            logger.error(f"Failed to get all variant metrics: {e}")
            return []

    def clear_events(
        self, variant_id: Optional[str] = None, before_time: Optional[str] = None
    ) -> bool:
        """Clear events with optional filtering."""
        try:
            query = "DELETE FROM variant_events WHERE 1=1"
            params = []

            if variant_id:
                query += " AND variant_id = ?"
                params.append(variant_id)

            if before_time:
                query += " AND timestamp < ?"
                params.append(before_time)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                deleted_count = cursor.rowcount
                conn.commit()

            logger.info(f"Cleared {deleted_count} tracking events")
            return True

        except Exception as e:
            logger.error(f"Failed to clear events: {e}")
            return False

    def clear_old_events(self, cutoff_date: datetime) -> int:
        """Clear events older than the cutoff date."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM variant_events
                    WHERE timestamp < ?
                """,
                    (cutoff_date.isoformat(),),
                )
                conn.commit()
                return cursor.rowcount

        except Exception as e:
            logger.error(f"Failed to clear old events: {e}")
            return 0

    def close(self):
        """Close the tracker (placeholder for cleanup if needed)."""
        # SQLite connections are automatically closed when using context managers
        # This method exists for test compatibility
        pass


# Global tracker instance
_global_tracker = VariantTracker()


def get_variant_tracker() -> VariantTracker:
    """Get the global variant tracker."""
    return _global_tracker


def track_variant_assignment(
    variant_id: str, business_id: int, properties: Dict[str, Any] = None
) -> bool:
    """Convenience function to track variant assignment."""
    return get_variant_tracker().track_variant_assignment(
        variant_id, business_id, properties=properties
    )


def track_pipeline_start(
    variant_id: str, business_id: int, properties: Dict[str, Any] = None
) -> bool:
    """Convenience function to track pipeline start."""
    return get_variant_tracker().track_pipeline_start(
        variant_id, business_id, properties=properties
    )


def track_stage_completion(
    variant_id: str, business_id: int, stage: str, properties: Dict[str, Any] = None
) -> bool:
    """Convenience function to track stage completion."""
    return get_variant_tracker().track_stage_completion(
        variant_id, business_id, stage, properties=properties
    )


def track_email_sent(
    variant_id: str, business_id: int, properties: Dict[str, Any] = None
) -> bool:
    """Convenience function to track email sent."""
    return get_variant_tracker().track_email_event(
        variant_id, business_id, EventType.EMAIL_SENT, properties=properties
    )


def track_conversion(
    variant_id: str, business_id: int, properties: Dict[str, Any] = None
) -> bool:
    """Convenience function to track conversion."""
    return get_variant_tracker().track_conversion(
        variant_id, business_id, properties=properties
    )
