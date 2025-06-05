"""
Conversion Tracking and Analytics
================================

This module provides comprehensive conversion tracking and analytics for the LeadFactory
audit business model. It tracks the complete customer journey from initial page view
to purchase completion and provides detailed funnel analysis.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import CONVERSION_FUNNEL, record_metric

logger = get_logger(__name__)


class ConversionEventType(Enum):
    """Types of conversion events tracked."""

    PAGE_VIEW = "page_view"
    AUDIT_TYPE_SELECTION = "audit_type_selection"
    FORM_START = "form_start"
    FORM_SUBMIT = "form_submit"
    PAYMENT_INTENT_CREATED = "payment_intent_created"
    PAYMENT_PROCESSING = "payment_processing"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    REPORT_DOWNLOAD = "report_download"


class ConversionChannel(Enum):
    """Marketing channels for attribution."""

    DIRECT = "direct"
    ORGANIC_SEARCH = "organic_search"
    PAID_SEARCH = "paid_search"
    SOCIAL_MEDIA = "social_media"
    EMAIL_MARKETING = "email_marketing"
    REFERRAL = "referral"
    UNKNOWN = "unknown"


@dataclass
class ConversionEvent:
    """Individual conversion event."""

    event_id: str
    session_id: str
    user_id: Optional[str]
    event_type: ConversionEventType
    timestamp: datetime
    audit_type: Optional[str]
    revenue_cents: Optional[int]
    properties: dict[str, Any]
    channel: ConversionChannel
    referrer: Optional[str]
    user_agent: Optional[str]


@dataclass
class ConversionFunnel:
    """Conversion funnel analysis."""

    period_start: datetime
    period_end: datetime
    audit_type: Optional[str]
    channel: Optional[ConversionChannel]
    funnel_steps: list[dict[str, Any]]
    conversion_rates: dict[str, float]
    drop_off_points: list[dict[str, Any]]
    total_revenue_cents: int
    average_time_to_conversion: Optional[float]


@dataclass
class AttributionReport:
    """Attribution analysis report."""

    period_start: datetime
    period_end: datetime
    channel_performance: dict[str, dict[str, Any]]
    top_converting_channels: list[dict[str, Any]]
    revenue_attribution: dict[str, int]
    conversion_paths: list[dict[str, Any]]


class ConversionTracker:
    """Comprehensive conversion tracking and analytics system."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize conversion tracker.

        Args:
            db_path: Path to SQLite database for conversion tracking
        """
        self.db_path = db_path or "conversion_tracking.db"
        self.logger = get_logger(f"{__name__}.ConversionTracker")
        self._init_database()

    def _init_database(self):
        """Initialize database schema for conversion tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversion_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    audit_type TEXT,
                    revenue_cents INTEGER,
                    properties TEXT,
                    channel TEXT NOT NULL,
                    referrer TEXT,
                    user_agent TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversion_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    first_event_timestamp DATETIME NOT NULL,
                    last_event_timestamp DATETIME NOT NULL,
                    conversion_completed BOOLEAN DEFAULT FALSE,
                    revenue_cents INTEGER DEFAULT 0,
                    audit_type TEXT,
                    attribution_channel TEXT,
                    attribution_referrer TEXT,
                    event_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversion_attribution (
                    attribution_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    attribution_weight REAL NOT NULL,
                    revenue_attribution_cents INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversion_sessions(session_id),
                    FOREIGN KEY (event_id) REFERENCES conversion_events(event_id)
                );

                CREATE INDEX IF NOT EXISTS idx_events_session ON conversion_events(session_id);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON conversion_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_type ON conversion_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_channel ON conversion_events(channel);
                CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON conversion_sessions(first_event_timestamp);
                CREATE INDEX IF NOT EXISTS idx_sessions_conversion ON conversion_sessions(conversion_completed);
                CREATE INDEX IF NOT EXISTS idx_attribution_session ON conversion_attribution(session_id);
            """
            )

        self.logger.info(f"Conversion tracking database initialized at {self.db_path}")

    def track_event(
        self,
        session_id: str,
        event_type: ConversionEventType,
        audit_type: Optional[str] = None,
        revenue_cents: Optional[int] = None,
        properties: Optional[dict[str, Any]] = None,
        channel: ConversionChannel = ConversionChannel.UNKNOWN,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Track a conversion event.

        Args:
            session_id: Unique session identifier
            event_type: Type of conversion event
            audit_type: Type of audit (if applicable)
            revenue_cents: Revenue amount in cents (for purchase events)
            properties: Additional event properties
            channel: Marketing channel
            referrer: Referrer URL
            user_agent: User agent string
            user_id: User identifier (if known)

        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now()

        event = ConversionEvent(
            event_id=event_id,
            session_id=session_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=timestamp,
            audit_type=audit_type,
            revenue_cents=revenue_cents,
            properties=properties or {},
            channel=channel,
            referrer=referrer,
            user_agent=user_agent,
        )

        with sqlite3.connect(self.db_path) as conn:
            # Insert event
            conn.execute(
                """
                INSERT INTO conversion_events (
                    event_id, session_id, user_id, event_type, timestamp,
                    audit_type, revenue_cents, properties, channel,
                    referrer, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.session_id,
                    event.user_id,
                    event.event_type.value,
                    event.timestamp,
                    event.audit_type,
                    event.revenue_cents,
                    json.dumps(event.properties),
                    event.channel.value,
                    event.referrer,
                    event.user_agent,
                ),
            )

            # Update or create session
            self._update_session(conn, event)

        # Update Prometheus metrics
        record_metric(
            CONVERSION_FUNNEL,
            1,
            stage=event_type.value,
            audit_type=audit_type or "unknown",
            channel=channel.value,
        )

        self.logger.debug(
            f"Tracked conversion event: {event_type.value} for session {session_id}"
        )
        return event_id

    def _update_session(self, conn: sqlite3.Connection, event: ConversionEvent):
        """Update session information with new event."""
        # Check if session exists
        cursor = conn.execute(
            "SELECT session_id, first_event_timestamp, event_count FROM conversion_sessions WHERE session_id = ?",
            (event.session_id,),
        )
        session_row = cursor.fetchone()

        if session_row:
            # Update existing session
            conn.execute(
                """
                UPDATE conversion_sessions
                SET last_event_timestamp = ?,
                    event_count = event_count + 1,
                    updated_at = ?,
                    conversion_completed = CASE
                        WHEN ? = 'payment_success' THEN TRUE
                        ELSE conversion_completed
                    END,
                    revenue_cents = CASE
                        WHEN ? IS NOT NULL THEN revenue_cents + ?
                        ELSE revenue_cents
                    END,
                    audit_type = COALESCE(?, audit_type)
                WHERE session_id = ?
            """,
                (
                    event.timestamp,
                    event.timestamp,
                    event.event_type.value,
                    event.revenue_cents,
                    event.revenue_cents or 0,
                    event.audit_type,
                    event.session_id,
                ),
            )
        else:
            # Create new session
            conn.execute(
                """
                INSERT INTO conversion_sessions (
                    session_id, user_id, first_event_timestamp, last_event_timestamp,
                    conversion_completed, revenue_cents, audit_type,
                    attribution_channel, attribution_referrer, event_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
                (
                    event.session_id,
                    event.user_id,
                    event.timestamp,
                    event.timestamp,
                    event.event_type == ConversionEventType.PAYMENT_SUCCESS,
                    event.revenue_cents or 0,
                    event.audit_type,
                    event.channel.value,
                    event.referrer,
                ),
            )

    def analyze_funnel(
        self,
        start_date: datetime,
        end_date: datetime,
        audit_type: Optional[str] = None,
        channel: Optional[ConversionChannel] = None,
    ) -> ConversionFunnel:
        """Analyze conversion funnel for a specific period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            audit_type: Filter by audit type
            channel: Filter by marketing channel

        Returns:
            Conversion funnel analysis
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Build filter conditions
            conditions = ["timestamp BETWEEN ? AND ?"]
            params = [start_date, end_date]

            if audit_type:
                conditions.append("audit_type = ?")
                params.append(audit_type)

            if channel:
                conditions.append("channel = ?")
                params.append(channel.value)

            where_clause = " AND ".join(conditions)

            # Get funnel step counts
            cursor = conn.execute(
                f"""
                SELECT event_type, COUNT(*) as count, COUNT(DISTINCT session_id) as unique_sessions
                FROM conversion_events
                WHERE {where_clause}
                GROUP BY event_type
                ORDER BY COUNT(*) DESC
            """,
                params,
            )

            step_counts = {
                row["event_type"]: {
                    "count": row["count"],
                    "unique_sessions": row["unique_sessions"],
                }
                for row in cursor
            }

            # Define funnel steps in order
            funnel_steps_order = [
                ConversionEventType.PAGE_VIEW.value,
                ConversionEventType.AUDIT_TYPE_SELECTION.value,
                ConversionEventType.FORM_START.value,
                ConversionEventType.FORM_SUBMIT.value,
                ConversionEventType.PAYMENT_INTENT_CREATED.value,
                ConversionEventType.PAYMENT_SUCCESS.value,
            ]

            # Build funnel analysis
            funnel_steps = []
            conversion_rates = {}
            previous_count = None

            for step in funnel_steps_order:
                step_data = step_counts.get(step, {"count": 0, "unique_sessions": 0})
                step_count = step_data["unique_sessions"]

                conversion_rate = None
                if previous_count is not None and previous_count > 0:
                    conversion_rate = (step_count / previous_count) * 100

                funnel_steps.append(
                    {
                        "step": step,
                        "count": step_count,
                        "conversion_rate": conversion_rate,
                    }
                )

                if conversion_rate is not None:
                    conversion_rates[
                        f"{funnel_steps_order[len(funnel_steps) - 2]}_to_{step}"
                    ] = conversion_rate

                previous_count = step_count

            # Calculate drop-off points
            drop_off_points = []
            for i in range(len(funnel_steps) - 1):
                current_step = funnel_steps[i]
                next_step = funnel_steps[i + 1]

                if current_step["count"] > 0:
                    drop_off_rate = (
                        (current_step["count"] - next_step["count"])
                        / current_step["count"]
                    ) * 100
                    if drop_off_rate > 50:  # Flag high drop-off points
                        drop_off_points.append(
                            {
                                "from_step": current_step["step"],
                                "to_step": next_step["step"],
                                "drop_off_rate": drop_off_rate,
                                "users_lost": current_step["count"]
                                - next_step["count"],
                            }
                        )

            # Calculate total revenue
            cursor = conn.execute(
                f"""
                SELECT SUM(revenue_cents) as total_revenue
                FROM conversion_events
                WHERE {where_clause} AND revenue_cents IS NOT NULL
            """,
                params,
            )
            total_revenue_cents = cursor.fetchone()["total_revenue"] or 0

            # Calculate average time to conversion
            cursor = conn.execute(
                f"""
                SELECT AVG(
                    JULIANDAY(last_event_timestamp) - JULIANDAY(first_event_timestamp)
                ) * 24 * 60 as avg_minutes
                FROM conversion_sessions
                WHERE first_event_timestamp BETWEEN ? AND ?
                AND conversion_completed = TRUE
                {f"AND audit_type = '{audit_type}'" if audit_type else ""}
                {f"AND attribution_channel = '{channel.value}'" if channel else ""}
            """,
                [start_date, end_date],
            )

            avg_time_result = cursor.fetchone()
            avg_time_to_conversion = (
                avg_time_result["avg_minutes"] if avg_time_result else None
            )

            return ConversionFunnel(
                period_start=start_date,
                period_end=end_date,
                audit_type=audit_type,
                channel=channel,
                funnel_steps=funnel_steps,
                conversion_rates=conversion_rates,
                drop_off_points=drop_off_points,
                total_revenue_cents=total_revenue_cents,
                average_time_to_conversion=avg_time_to_conversion,
            )

    def analyze_attribution(
        self,
        start_date: datetime,
        end_date: datetime,
        attribution_model: str = "last_click",
    ) -> AttributionReport:
        """Analyze marketing attribution for conversions.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            attribution_model: Attribution model ('last_click', 'first_click', 'linear')

        Returns:
            Attribution analysis report
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get converted sessions in period
            cursor = conn.execute(
                """
                SELECT session_id, attribution_channel, attribution_referrer, revenue_cents
                FROM conversion_sessions
                WHERE first_event_timestamp BETWEEN ? AND ?
                AND conversion_completed = TRUE
            """,
                (start_date, end_date),
            )

            converted_sessions = list(cursor.fetchall())

            # Analyze channel performance
            channel_performance = {}
            revenue_attribution = {}

            for session in converted_sessions:
                channel = session["attribution_channel"]
                revenue = session["revenue_cents"] or 0

                if channel not in channel_performance:
                    channel_performance[channel] = {
                        "conversions": 0,
                        "revenue_cents": 0,
                        "sessions": 0,
                    }

                channel_performance[channel]["conversions"] += 1
                channel_performance[channel]["revenue_cents"] += revenue

                revenue_attribution[channel] = (
                    revenue_attribution.get(channel, 0) + revenue
                )

            # Calculate conversion rates by channel
            cursor = conn.execute(
                """
                SELECT attribution_channel, COUNT(*) as total_sessions
                FROM conversion_sessions
                WHERE first_event_timestamp BETWEEN ? AND ?
                GROUP BY attribution_channel
            """,
                (start_date, end_date),
            )

            for row in cursor:
                channel = row["attribution_channel"]
                if channel in channel_performance:
                    channel_performance[channel]["sessions"] = row["total_sessions"]
                    channel_performance[channel]["conversion_rate"] = (
                        channel_performance[channel]["conversions"]
                        / row["total_sessions"]
                    ) * 100

            # Sort channels by performance
            top_converting_channels = sorted(
                [
                    {
                        "channel": channel,
                        "conversions": data["conversions"],
                        "revenue_cents": data["revenue_cents"],
                        "conversion_rate": data.get("conversion_rate", 0),
                    }
                    for channel, data in channel_performance.items()
                ],
                key=lambda x: x["revenue_cents"],
                reverse=True,
            )

            # Analyze conversion paths (simplified)
            conversion_paths = []
            for session in converted_sessions[:10]:  # Limit for performance
                cursor = conn.execute(
                    """
                    SELECT event_type, channel, timestamp
                    FROM conversion_events
                    WHERE session_id = ?
                    ORDER BY timestamp
                """,
                    (session["session_id"],),
                )

                events = list(cursor.fetchall())
                if events:
                    conversion_paths.append(
                        {
                            "session_id": session["session_id"],
                            "revenue_cents": session["revenue_cents"],
                            "path_length": len(events),
                            "events": [
                                {
                                    "event_type": event["event_type"],
                                    "channel": event["channel"],
                                    "timestamp": event["timestamp"],
                                }
                                for event in events
                            ],
                        }
                    )

            return AttributionReport(
                period_start=start_date,
                period_end=end_date,
                channel_performance=channel_performance,
                top_converting_channels=top_converting_channels,
                revenue_attribution=revenue_attribution,
                conversion_paths=conversion_paths,
            )

    def get_conversion_summary(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Get overall conversion summary for a period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            Conversion summary data
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Overall metrics
            cursor = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(DISTINCT CASE WHEN conversion_completed THEN session_id END) as converted_sessions,
                    SUM(revenue_cents) as total_revenue_cents,
                    AVG(revenue_cents) as avg_revenue_per_conversion_cents
                FROM conversion_sessions
                WHERE first_event_timestamp BETWEEN ? AND ?
            """,
                (start_date, end_date),
            )

            summary_row = cursor.fetchone()

            total_sessions = summary_row["total_sessions"] or 0
            converted_sessions = summary_row["converted_sessions"] or 0
            total_revenue_cents = summary_row["total_revenue_cents"] or 0
            avg_revenue_per_conversion = (
                summary_row["avg_revenue_per_conversion_cents"] or 0
            )

            overall_conversion_rate = (
                (converted_sessions / total_sessions * 100) if total_sessions > 0 else 0
            )

            # Event type breakdown
            cursor = conn.execute(
                """
                SELECT event_type, COUNT(*) as count
                FROM conversion_events
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY event_type
                ORDER BY count DESC
            """,
                (start_date, end_date),
            )

            event_breakdown = {row["event_type"]: row["count"] for row in cursor}

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "overall_metrics": {
                    "total_sessions": total_sessions,
                    "converted_sessions": converted_sessions,
                    "overall_conversion_rate": overall_conversion_rate,
                    "total_revenue_cents": total_revenue_cents,
                    "average_revenue_per_conversion_cents": avg_revenue_per_conversion,
                },
                "event_breakdown": event_breakdown,
            }

    def cleanup_old_data(self, retention_days: int = 90):
        """Clean up old conversion tracking data.

        Args:
            retention_days: Number of days to retain data
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        with sqlite3.connect(self.db_path) as conn:
            # Delete old events
            cursor = conn.execute(
                """
                DELETE FROM conversion_events
                WHERE timestamp < ?
            """,
                (cutoff_date,),
            )
            events_deleted = cursor.rowcount

            # Delete old sessions
            cursor = conn.execute(
                """
                DELETE FROM conversion_sessions
                WHERE first_event_timestamp < ?
            """,
                (cutoff_date,),
            )
            sessions_deleted = cursor.rowcount

            # Delete orphaned attribution records
            cursor = conn.execute(
                """
                DELETE FROM conversion_attribution
                WHERE session_id NOT IN (SELECT session_id FROM conversion_sessions)
            """
            )
            attribution_deleted = cursor.rowcount

        self.logger.info(
            f"Cleanup completed: {events_deleted} events, {sessions_deleted} sessions, "
            f"{attribution_deleted} attribution records deleted"
        )


# Global instance
conversion_tracker = ConversionTracker()
