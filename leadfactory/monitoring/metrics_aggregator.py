"""
Metrics Aggregation and Storage
==============================

This module implements time-based aggregation for purchase metrics and provides
efficient storage solutions for both raw and aggregated data with appropriate
retention policies.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.cost.purchase_metrics import purchase_metrics_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AggregationPeriod(Enum):
    """Time periods for metrics aggregation."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class AggregatedMetric:
    """Aggregated purchase metric data point."""

    period: AggregationPeriod
    timestamp: datetime
    total_purchases: int
    total_revenue_cents: int
    total_stripe_fees_cents: int
    average_order_value_cents: int
    conversion_rate: float
    refund_count: int
    refund_amount_cents: int
    audit_type_breakdown: Dict[str, Dict[str, Union[int, float]]]
    geographic_breakdown: Dict[str, Dict[str, Union[int, float]]]


class MetricsAggregator:
    """Purchase metrics aggregation and storage system."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize metrics aggregator.

        Args:
            db_path: Path to SQLite database for metrics storage
        """
        self.db_path = db_path or "purchase_metrics.db"
        self.logger = get_logger(f"{__name__}.MetricsAggregator")
        self._init_database()

    def _init_database(self):
        """Initialize database schema for metrics storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS purchase_metrics_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    stripe_payment_intent_id TEXT NOT NULL,
                    stripe_charge_id TEXT,
                    customer_email TEXT,
                    customer_name TEXT,
                    gross_amount_cents INTEGER NOT NULL,
                    net_amount_cents INTEGER NOT NULL,
                    stripe_fee_cents INTEGER NOT NULL,
                    audit_type TEXT NOT NULL,
                    currency TEXT DEFAULT 'usd',
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS purchase_metrics_aggregated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    total_purchases INTEGER NOT NULL,
                    total_revenue_cents INTEGER NOT NULL,
                    total_stripe_fees_cents INTEGER NOT NULL,
                    average_order_value_cents INTEGER NOT NULL,
                    conversion_rate REAL NOT NULL DEFAULT 0.0,
                    refund_count INTEGER NOT NULL DEFAULT 0,
                    refund_amount_cents INTEGER NOT NULL DEFAULT 0,
                    audit_type_breakdown TEXT,
                    geographic_breakdown TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(period, timestamp)
                );

                CREATE TABLE IF NOT EXISTS conversion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    session_id TEXT,
                    customer_email TEXT,
                    audit_type TEXT,
                    referrer TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON purchase_metrics_raw(timestamp);
                CREATE INDEX IF NOT EXISTS idx_raw_audit_type ON purchase_metrics_raw(audit_type);
                CREATE INDEX IF NOT EXISTS idx_aggregated_period ON purchase_metrics_aggregated(period, timestamp);
                CREATE INDEX IF NOT EXISTS idx_conversion_timestamp ON conversion_events(timestamp);
            """
            )

        self.logger.info(f"Metrics database initialized at {self.db_path}")

    def record_purchase(
        self,
        stripe_payment_intent_id: str,
        stripe_charge_id: Optional[str],
        customer_email: str,
        customer_name: Optional[str],
        gross_amount_cents: int,
        net_amount_cents: int,
        stripe_fee_cents: int,
        audit_type: str,
        currency: str = "usd",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a raw purchase metric.

        Args:
            stripe_payment_intent_id: Stripe payment intent ID
            stripe_charge_id: Stripe charge ID
            customer_email: Customer email address
            customer_name: Customer name
            gross_amount_cents: Gross purchase amount in cents
            net_amount_cents: Net amount after fees in cents
            stripe_fee_cents: Stripe processing fee in cents
            audit_type: Type of audit purchased
            currency: Currency code (default: usd)
            metadata: Additional metadata

        Returns:
            Record ID as string
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO purchase_metrics_raw (
                    stripe_payment_intent_id, stripe_charge_id, customer_email,
                    customer_name, gross_amount_cents, net_amount_cents,
                    stripe_fee_cents, audit_type, currency, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    stripe_payment_intent_id,
                    stripe_charge_id,
                    customer_email,
                    customer_name,
                    gross_amount_cents,
                    net_amount_cents,
                    stripe_fee_cents,
                    audit_type,
                    currency,
                    json.dumps(metadata) if metadata else None,
                ),
            )

            record_id = str(cursor.lastrowid)

        self.logger.info(f"Recorded purchase metric: {record_id}")
        return record_id

    def record_conversion_event(
        self,
        event_type: str,
        session_id: Optional[str] = None,
        customer_email: Optional[str] = None,
        audit_type: Optional[str] = None,
        referrer: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a conversion funnel event.

        Args:
            event_type: Type of event (e.g., 'page_view', 'form_start', 'purchase')
            session_id: Session identifier
            customer_email: Customer email (if known)
            audit_type: Type of audit being viewed/purchased
            referrer: Referrer source
            metadata: Additional event metadata
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversion_events (
                    event_type, session_id, customer_email, audit_type, referrer, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    event_type,
                    session_id,
                    customer_email,
                    audit_type,
                    referrer,
                    json.dumps(metadata) if metadata else None,
                ),
            )

        self.logger.debug(f"Recorded conversion event: {event_type}")

    def aggregate_metrics(
        self,
        period: AggregationPeriod,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AggregatedMetric]:
        """Aggregate purchase metrics for a specific time period.

        Args:
            period: Aggregation period (hourly, daily, weekly, monthly)
            start_time: Start of aggregation window (default: 30 days ago)
            end_time: End of aggregation window (default: now)

        Returns:
            List of aggregated metrics
        """
        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        if not end_time:
            end_time = datetime.now()

        self.logger.info(
            f"Aggregating {period.value} metrics from {start_time} to {end_time}"
        )

        # Define period grouping SQL
        period_formats = {
            AggregationPeriod.HOURLY: "strftime('%Y-%m-%d %H:00:00', timestamp)",
            AggregationPeriod.DAILY: "strftime('%Y-%m-%d', timestamp)",
            AggregationPeriod.WEEKLY: "strftime('%Y-%W', timestamp)",
            AggregationPeriod.MONTHLY: "strftime('%Y-%m', timestamp)",
        }

        period_format = period_formats[period]

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Aggregate main metrics
            cursor = conn.execute(
                f"""
                SELECT
                    {period_format} as period_key,
                    COUNT(*) as total_purchases,
                    SUM(gross_amount_cents) as total_revenue_cents,
                    SUM(stripe_fee_cents) as total_stripe_fees_cents,
                    AVG(gross_amount_cents) as average_order_value_cents,
                    audit_type,
                    currency
                FROM purchase_metrics_raw
                WHERE timestamp BETWEEN ? AND ?
                GROUP BY period_key, audit_type, currency
                ORDER BY period_key DESC
            """,
                (start_time, end_time),
            )

            # Process results
            period_data = {}

            for row in cursor:
                period_key = row["period_key"]
                if period_key not in period_data:
                    period_data[period_key] = {
                        "total_purchases": 0,
                        "total_revenue_cents": 0,
                        "total_stripe_fees_cents": 0,
                        "average_order_value_cents": 0,
                        "audit_type_breakdown": {},
                        "geographic_breakdown": {},
                    }

                # Aggregate totals
                period_data[period_key]["total_purchases"] += row["total_purchases"]
                period_data[period_key]["total_revenue_cents"] += (
                    row["total_revenue_cents"] or 0
                )
                period_data[period_key]["total_stripe_fees_cents"] += (
                    row["total_stripe_fees_cents"] or 0
                )

                # Store audit type breakdown
                audit_type = row["audit_type"]
                if audit_type not in period_data[period_key]["audit_type_breakdown"]:
                    period_data[period_key]["audit_type_breakdown"][audit_type] = {
                        "purchases": 0,
                        "revenue_cents": 0,
                    }

                period_data[period_key]["audit_type_breakdown"][audit_type][
                    "purchases"
                ] += row["total_purchases"]
                period_data[period_key]["audit_type_breakdown"][audit_type][
                    "revenue_cents"
                ] += (row["total_revenue_cents"] or 0)

            # Calculate conversion rates
            self._add_conversion_rates(
                conn, period_data, period_format, start_time, end_time
            )

            # Convert to AggregatedMetric objects
            aggregated_metrics = []
            for period_key, data in period_data.items():
                # Parse timestamp based on period type
                if period == AggregationPeriod.HOURLY:
                    timestamp = datetime.strptime(period_key, "%Y-%m-%d %H:%M:%S")
                elif period == AggregationPeriod.DAILY:
                    timestamp = datetime.strptime(period_key, "%Y-%m-%d")
                elif period == AggregationPeriod.WEEKLY:
                    year, week = period_key.split("-")
                    timestamp = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
                elif period == AggregationPeriod.MONTHLY:
                    timestamp = datetime.strptime(period_key, "%Y-%m")

                # Calculate average order value
                avg_order_value = 0
                if data["total_purchases"] > 0:
                    avg_order_value = (
                        data["total_revenue_cents"] // data["total_purchases"]
                    )

                metric = AggregatedMetric(
                    period=period,
                    timestamp=timestamp,
                    total_purchases=data["total_purchases"],
                    total_revenue_cents=data["total_revenue_cents"],
                    total_stripe_fees_cents=data["total_stripe_fees_cents"],
                    average_order_value_cents=avg_order_value,
                    conversion_rate=data.get("conversion_rate", 0.0),
                    refund_count=data.get("refund_count", 0),
                    refund_amount_cents=data.get("refund_amount_cents", 0),
                    audit_type_breakdown=data["audit_type_breakdown"],
                    geographic_breakdown=data["geographic_breakdown"],
                )

                aggregated_metrics.append(metric)

        self.logger.info(f"Generated {len(aggregated_metrics)} aggregated metrics")
        return aggregated_metrics

    def _add_conversion_rates(
        self,
        conn: sqlite3.Connection,
        period_data: Dict[str, Any],
        period_format: str,
        start_time: datetime,
        end_time: datetime,
    ):
        """Calculate and add conversion rates to period data."""
        # Get conversion funnel data
        cursor = conn.execute(
            f"""
            SELECT
                {period_format} as period_key,
                event_type,
                COUNT(*) as event_count
            FROM conversion_events
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY period_key, event_type
        """,
            (start_time, end_time),
        )

        # Calculate conversion rates for each period
        for row in cursor:
            period_key = row["period_key"]
            if period_key in period_data:
                if "conversion_events" not in period_data[period_key]:
                    period_data[period_key]["conversion_events"] = {}

                period_data[period_key]["conversion_events"][row["event_type"]] = row[
                    "event_count"
                ]

        # Calculate conversion rates
        for period_key, data in period_data.items():
            events = data.get("conversion_events", {})
            page_views = events.get("page_view", 0)
            purchases = data["total_purchases"]

            if page_views > 0:
                data["conversion_rate"] = purchases / page_views
            else:
                data["conversion_rate"] = 0.0

    def store_aggregated_metrics(self, metrics: List[AggregatedMetric]):
        """Store aggregated metrics in the database.

        Args:
            metrics: List of aggregated metrics to store
        """
        with sqlite3.connect(self.db_path) as conn:
            for metric in metrics:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO purchase_metrics_aggregated (
                            period, timestamp, total_purchases, total_revenue_cents,
                            total_stripe_fees_cents, average_order_value_cents,
                            conversion_rate, refund_count, refund_amount_cents,
                            audit_type_breakdown, geographic_breakdown
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            metric.period.value,
                            metric.timestamp,
                            metric.total_purchases,
                            metric.total_revenue_cents,
                            metric.total_stripe_fees_cents,
                            metric.average_order_value_cents,
                            metric.conversion_rate,
                            metric.refund_count,
                            metric.refund_amount_cents,
                            json.dumps(metric.audit_type_breakdown),
                            json.dumps(metric.geographic_breakdown),
                        ),
                    )
                except Exception as e:
                    self.logger.error(f"Failed to store aggregated metric: {e}")

        self.logger.info(f"Stored {len(metrics)} aggregated metrics")

    def get_aggregated_metrics(
        self, period: AggregationPeriod, limit: int = 100
    ) -> List[AggregatedMetric]:
        """Retrieve stored aggregated metrics.

        Args:
            period: Aggregation period to retrieve
            limit: Maximum number of records to return

        Returns:
            List of aggregated metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT * FROM purchase_metrics_aggregated
                WHERE period = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (period.value, limit),
            )

            metrics = []
            for row in cursor:
                metric = AggregatedMetric(
                    period=AggregationPeriod(row["period"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    total_purchases=row["total_purchases"],
                    total_revenue_cents=row["total_revenue_cents"],
                    total_stripe_fees_cents=row["total_stripe_fees_cents"],
                    average_order_value_cents=row["average_order_value_cents"],
                    conversion_rate=row["conversion_rate"],
                    refund_count=row["refund_count"],
                    refund_amount_cents=row["refund_amount_cents"],
                    audit_type_breakdown=(
                        json.loads(row["audit_type_breakdown"])
                        if row["audit_type_breakdown"]
                        else {}
                    ),
                    geographic_breakdown=(
                        json.loads(row["geographic_breakdown"])
                        if row["geographic_breakdown"]
                        else {}
                    ),
                )
                metrics.append(metric)

        return metrics

    def cleanup_old_data(self, retention_days: int = 90):
        """Clean up old raw metrics data based on retention policy.

        Args:
            retention_days: Number of days to retain raw data
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        with sqlite3.connect(self.db_path) as conn:
            # Delete old raw metrics
            cursor = conn.execute(
                """
                DELETE FROM purchase_metrics_raw
                WHERE timestamp < ?
            """,
                (cutoff_date,),
            )

            deleted_count = cursor.rowcount

            # Delete old conversion events
            cursor = conn.execute(
                """
                DELETE FROM conversion_events
                WHERE timestamp < ?
            """,
                (cutoff_date,),
            )

            deleted_events = cursor.rowcount

        self.logger.info(
            f"Cleaned up {deleted_count} old purchase records and {deleted_events} conversion events"
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics storage status.

        Returns:
            Dictionary with metrics summary
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get record counts
            raw_count = conn.execute(
                "SELECT COUNT(*) as count FROM purchase_metrics_raw"
            ).fetchone()["count"]
            aggregated_count = conn.execute(
                "SELECT COUNT(*) as count FROM purchase_metrics_aggregated"
            ).fetchone()["count"]
            events_count = conn.execute(
                "SELECT COUNT(*) as count FROM conversion_events"
            ).fetchone()["count"]

            # Get date ranges
            earliest_raw = conn.execute(
                "SELECT MIN(timestamp) as earliest FROM purchase_metrics_raw"
            ).fetchone()["earliest"]
            latest_raw = conn.execute(
                "SELECT MAX(timestamp) as latest FROM purchase_metrics_raw"
            ).fetchone()["latest"]

            return {
                "raw_metrics_count": raw_count,
                "aggregated_metrics_count": aggregated_count,
                "conversion_events_count": events_count,
                "earliest_data": earliest_raw,
                "latest_data": latest_raw,
                "database_path": self.db_path,
            }


# Global instance
metrics_aggregator = MetricsAggregator()
