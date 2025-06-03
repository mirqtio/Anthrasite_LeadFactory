#!/usr/bin/env python3
"""
Bounce Rate Monitoring System for IP/Subuser Rotation

This module implements a comprehensive bounce rate monitoring system that tracks
bounce rates per IP/subuser combination to enable automated rotation when
thresholds are exceeded.
"""

import logging

# Import database connection with fallback
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


@contextmanager
def SQLiteDatabaseConnection(db_path: str = None):
    """SQLite database connection for testing"""
    conn = None
    try:
        conn = sqlite3.connect(db_path or ":memory:")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()


try:
    from leadfactory.utils.e2e_db_connector import db_connection as PostgreSQLConnection

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    PostgreSQLConnection = None

# Import logging with fallback
try:
    from leadfactory.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class SamplingPeriod(Enum):
    """Sampling periods for bounce rate calculation."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class CalculationMethod(Enum):
    """Methods for calculating bounce rates."""

    ROLLING_AVERAGE = "rolling_average"
    POINT_IN_TIME = "point_in_time"
    EXPONENTIAL_WEIGHTED = "exponential_weighted"


@dataclass
class BounceRateConfig:
    """Configuration for bounce rate monitoring."""

    sampling_period: SamplingPeriod = SamplingPeriod.HOURLY
    calculation_method: CalculationMethod = CalculationMethod.ROLLING_AVERAGE
    rolling_window_hours: int = 24
    minimum_sample_size: int = 10
    warning_threshold: float = 0.05  # 5%
    critical_threshold: float = 0.10  # 10%
    block_threshold: float = 0.15  # 15%
    exponential_decay_factor: float = 0.9


@dataclass
class IPSubuserStats:
    """Statistics for an IP/subuser combination."""

    ip_address: str
    subuser: str
    total_sent: int = 0
    total_bounced: int = 0
    hard_bounces: int = 0
    soft_bounces: int = 0
    block_bounces: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    bounce_rate: float = 0.0
    status: str = "active"  # active, warning, critical, blocked

    def calculate_bounce_rate(self) -> float:
        """Calculate current bounce rate."""
        if self.total_sent == 0:
            return 0.0
        self.bounce_rate = self.total_bounced / self.total_sent
        return self.bounce_rate


@dataclass
class BounceEvent:
    """Represents a bounce event with IP/subuser tracking."""

    email: str
    ip_address: str
    subuser: str
    bounce_type: str  # hard, soft, block
    reason: str
    timestamp: datetime
    message_id: Optional[str] = None


class BounceRateMonitor:
    """
    Monitors bounce rates per IP/subuser combination.

    This service continuously tracks bounce rates for each IP/subuser
    combination and provides real-time statistics and threshold monitoring.
    """

    def __init__(self, config: BounceRateConfig, db_path: str = None):
        """
        Initialize the bounce rate monitor.

        Args:
            config: Configuration for bounce rate monitoring
            db_path: Database path (for SQLite fallback, ignored for PostgreSQL)
        """
        self.config = config
        self.db_path = db_path
        self.cache = {}
        self.cache_ttl = {}
        self._initialize_tables()

    def _initialize_tables(self):
        """Initialize database tables for bounce rate monitoring."""
        try:
            # Check if we're using PostgreSQL or SQLite
            if self.db_path:
                # SQLite mode (testing)
                with SQLiteDatabaseConnection(self.db_path) as db:
                    self._create_sqlite_tables(db)
            else:
                # PostgreSQL mode (production)
                with PostgreSQLConnection() as db:
                    self._create_postgres_tables(db)
        except Exception as e:
            logger.error(f"Error initializing bounce rate monitoring tables: {e}")
            raise

    def _create_sqlite_tables(self, db):
        """Create SQLite tables for bounce rate monitoring."""
        # Create bounce rate statistics table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bounce_rate_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                subuser TEXT NOT NULL,
                total_sent INTEGER DEFAULT 0,
                total_bounced INTEGER DEFAULT 0,
                hard_bounces INTEGER DEFAULT 0,
                soft_bounces INTEGER DEFAULT 0,
                block_bounces INTEGER DEFAULT 0,
                bounce_rate REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ip_address, subuser)
            )
        """
        )

        # Create bounce events tracking table
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS bounce_events_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                subuser TEXT NOT NULL,
                bounce_type TEXT NOT NULL,
                reason TEXT,
                message_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE
            )
        """
        )

        # Create index for performance
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bounce_events_ip_subuser_timestamp
            ON bounce_events_tracking(ip_address, subuser, timestamp)
        """
        )

        db.commit()

    def _create_postgres_tables(self, db):
        """Create PostgreSQL tables for bounce rate monitoring."""
        cursor = db.cursor()

        # Create bounce rate statistics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bounce_rate_stats (
                id SERIAL PRIMARY KEY,
                ip_address VARCHAR(45) NOT NULL,
                subuser VARCHAR(255) NOT NULL,
                total_sent INTEGER DEFAULT 0,
                total_bounced INTEGER DEFAULT 0,
                hard_bounces INTEGER DEFAULT 0,
                soft_bounces INTEGER DEFAULT 0,
                block_bounces INTEGER DEFAULT 0,
                bounce_rate DOUBLE PRECISION DEFAULT 0.0,
                status VARCHAR(50) DEFAULT 'active',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ip_address, subuser)
            )
        """
        )

        # Create bounce events tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bounce_events_tracking (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                subuser VARCHAR(255) NOT NULL,
                bounce_type VARCHAR(50) NOT NULL,
                reason TEXT,
                message_id VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE
            )
        """
        )

        # Create index for performance
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bounce_events_ip_subuser_timestamp
            ON bounce_events_tracking(ip_address, subuser, timestamp)
        """
        )

        db.commit()

    def record_bounce_event(self, bounce_event: BounceEvent) -> None:
        """
        Record a bounce event for monitoring.

        Args:
            bounce_event: The bounce event to record
        """
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    self._record_bounce_sqlite(db, bounce_event)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    self._record_bounce_postgres(db, bounce_event)
        except Exception as e:
            logger.error(f"Error recording bounce event: {e}")
            raise

    def _record_bounce_sqlite(self, db, bounce_event: BounceEvent):
        """Record bounce event in SQLite database."""
        # Insert bounce event
        db.execute(
            """
            INSERT INTO bounce_events_tracking
            (email, ip_address, subuser, bounce_type, reason, message_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                bounce_event.email,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                bounce_event.reason,
                bounce_event.message_id,
            ),
        )

        # Update or create stats record
        db.execute(
            """
            INSERT OR REPLACE INTO bounce_rate_stats
            (ip_address, subuser, total_sent, total_bounced, hard_bounces,
             soft_bounces, block_bounces, bounce_rate, status, last_updated)
            VALUES (
                ?, ?,
                COALESCE((SELECT total_sent FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0),
                COALESCE((SELECT total_bounced FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0) + 1,
                COALESCE((SELECT hard_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0) +
                    CASE WHEN ? = 'hard' THEN 1 ELSE 0 END,
                COALESCE((SELECT soft_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0) +
                    CASE WHEN ? = 'soft' THEN 1 ELSE 0 END,
                COALESCE((SELECT block_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0) +
                    CASE WHEN ? = 'block' THEN 1 ELSE 0 END,
                0.0,
                'active',
                ?
            )
        """,
            (
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                datetime.now().isoformat(),
            ),
        )

        db.commit()

    def _record_bounce_postgres(self, db, bounce_event: BounceEvent):
        """Record bounce event in PostgreSQL database."""
        cursor = db.cursor()

        # Insert bounce event
        cursor.execute(
            """
            INSERT INTO bounce_events_tracking
            (email, ip_address, subuser, bounce_type, reason, message_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            (
                bounce_event.email,
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                bounce_event.reason,
                bounce_event.message_id,
            ),
        )

        # Update or create stats record using UPSERT
        cursor.execute(
            """
            INSERT INTO bounce_rate_stats
            (ip_address, subuser, total_sent, total_bounced, hard_bounces,
             soft_bounces, block_bounces, bounce_rate, status, last_updated)
            VALUES (%s, %s, 0, 1,
                CASE WHEN %s = 'hard' THEN 1 ELSE 0 END,
                CASE WHEN %s = 'soft' THEN 1 ELSE 0 END,
                CASE WHEN %s = 'block' THEN 1 ELSE 0 END,
                0.0, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT (ip_address, subuser) DO UPDATE SET
                total_bounced = bounce_rate_stats.total_bounced + 1,
                hard_bounces = bounce_rate_stats.hard_bounces + CASE WHEN %s = 'hard' THEN 1 ELSE 0 END,
                soft_bounces = bounce_rate_stats.soft_bounces + CASE WHEN %s = 'soft' THEN 1 ELSE 0 END,
                block_bounces = bounce_rate_stats.block_bounces + CASE WHEN %s = 'block' THEN 1 ELSE 0 END,
                last_updated = CURRENT_TIMESTAMP
        """,
            (
                bounce_event.ip_address,
                bounce_event.subuser,
                bounce_event.bounce_type,
                bounce_event.bounce_type,
                bounce_event.bounce_type,
                bounce_event.bounce_type,
                bounce_event.bounce_type,
                bounce_event.bounce_type,
            ),
        )

        db.commit()

    def record_sent_email(
        self,
        ip_address: str,
        subuser: str,
        email: str = None,
        message_id: Optional[str] = None,
    ) -> None:
        """
        Record a sent email for bounce rate calculation.

        Args:
            ip_address: IP address used to send the email
            subuser: Subuser identifier
            email: Email address (optional for counting)
            message_id: Message ID for tracking (optional)
        """
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    self._record_sent_sqlite(db, ip_address, subuser)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    self._record_sent_postgres(db, ip_address, subuser)
        except Exception as e:
            logger.error(f"Error recording sent email: {e}")
            raise

    def _record_sent_sqlite(self, db, ip_address: str, subuser: str):
        """Record sent email in SQLite database."""
        # Update or create stats record
        db.execute(
            """
            INSERT OR REPLACE INTO bounce_rate_stats
            (ip_address, subuser, total_sent, total_bounced, hard_bounces, soft_bounces, block_bounces, bounce_rate, last_updated)
            VALUES (
                ?, ?,
                COALESCE((SELECT total_sent FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0) + 1,
                COALESCE((SELECT total_bounced FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0),
                COALESCE((SELECT hard_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0),
                COALESCE((SELECT soft_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0),
                COALESCE((SELECT block_bounces FROM bounce_rate_stats WHERE ip_address = ? AND subuser = ?), 0),
                0.0,
                CURRENT_TIMESTAMP
            )
        """,
            (
                ip_address,
                subuser,
                ip_address,
                subuser,
                ip_address,
                subuser,
                ip_address,
                subuser,
                ip_address,
                subuser,
                ip_address,
                subuser,
            ),
        )
        db.commit()

    def _record_sent_postgres(self, db, ip_address: str, subuser: str):
        """Record sent email in PostgreSQL database."""
        cursor = db.cursor()

        # Update or create stats record using UPSERT
        cursor.execute(
            """
            INSERT INTO bounce_rate_stats
            (ip_address, subuser, total_sent, total_bounced, hard_bounces, soft_bounces, block_bounces, bounce_rate, last_updated)
            VALUES (%s, %s, 1, 0, 0, 0, 0, 0.0, CURRENT_TIMESTAMP)
            ON CONFLICT (ip_address, subuser) DO UPDATE SET
                total_sent = bounce_rate_stats.total_sent + 1,
                last_updated = CURRENT_TIMESTAMP
        """,
            (ip_address, subuser),
        )

        db.commit()

    def _update_ip_subuser_stats(
        self, ip_address: str, subuser: str, sent_count: int = 0
    ) -> None:
        """
        Update statistics for an IP/subuser combination.

        Args:
            ip_address: IP address
            subuser: Subuser
            sent_count: Number of emails sent (if any)
        """
        try:
            with SQLiteDatabaseConnection(self.db_path) as db:
                # Get current stats
                db.execute(
                    """
                    SELECT total_sent, total_bounced, hard_bounces, soft_bounces, block_bounces
                    FROM bounce_rate_stats
                    WHERE ip_address = ? AND subuser = ?
                """,
                    (ip_address, subuser),
                )

                result = db.fetchone()
                if result:
                    (
                        total_sent,
                        total_bounced,
                        hard_bounces,
                        soft_bounces,
                        block_bounces,
                    ) = result
                else:
                    total_sent = total_bounced = hard_bounces = soft_bounces = (
                        block_bounces
                    ) = 0

                # Calculate new bounce counts from recent events
                cutoff_time = datetime.now() - timedelta(
                    hours=self.config.rolling_window_hours
                )
                db.execute(
                    """
                    SELECT bounce_type, COUNT(*)
                    FROM bounce_events_tracking
                    WHERE ip_address = ? AND subuser = ? AND timestamp > ?
                    GROUP BY bounce_type
                """,
                    (ip_address, subuser, cutoff_time),
                )

                bounce_counts = dict(db.fetchall())
                new_hard_bounces = bounce_counts.get("hard", 0)
                new_soft_bounces = bounce_counts.get("soft", 0)
                new_block_bounces = bounce_counts.get("block", 0)
                new_total_bounced = (
                    new_hard_bounces + new_soft_bounces + new_block_bounces
                )

                # Update sent count
                new_total_sent = total_sent + sent_count

                # Calculate bounce rate
                bounce_rate = (
                    new_total_bounced / new_total_sent if new_total_sent > 0 else 0.0
                )

                # Determine status based on thresholds
                if bounce_rate >= self.config.block_threshold:
                    status = "blocked"
                elif bounce_rate >= self.config.critical_threshold:
                    status = "critical"
                elif bounce_rate >= self.config.warning_threshold:
                    status = "warning"
                else:
                    status = "active"

                # Upsert statistics
                db.execute(
                    """
                    INSERT OR REPLACE INTO bounce_rate_stats
                    (ip_address, subuser, total_sent, total_bounced, hard_bounces,
                     soft_bounces, block_bounces, bounce_rate, status, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        ip_address,
                        subuser,
                        new_total_sent,
                        new_total_bounced,
                        new_hard_bounces,
                        new_soft_bounces,
                        new_block_bounces,
                        bounce_rate,
                        status,
                        datetime.now(),
                    ),
                )

                db.commit()

                # Update cache
                cache_key = (ip_address, subuser)
                self.cache[cache_key] = IPSubuserStats(
                    ip_address=ip_address,
                    subuser=subuser,
                    total_sent=new_total_sent,
                    total_bounced=new_total_bounced,
                    hard_bounces=new_hard_bounces,
                    soft_bounces=new_soft_bounces,
                    block_bounces=new_block_bounces,
                    bounce_rate=bounce_rate,
                    status=status,
                    last_updated=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Error updating IP/subuser stats: {e}")
            raise

    def get_bounce_rate(self, ip_address: str, subuser: str) -> float:
        """
        Get current bounce rate for an IP/subuser combination.

        Args:
            ip_address: IP address
            subuser: Subuser

        Returns:
            Current bounce rate as a float (0.0 to 1.0)
        """
        stats = self.get_ip_subuser_stats(ip_address, subuser)
        return stats.bounce_rate if stats else 0.0

    def get_ip_subuser_stats(
        self, ip_address: str, subuser: str
    ) -> Optional[IPSubuserStats]:
        """
        Get statistics for an IP/subuser combination.

        Args:
            ip_address: IP address
            subuser: Subuser

        Returns:
            IPSubuserStats object or None if not found
        """
        cache_key = (ip_address, subuser)

        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Fetch from database
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    return self._get_stats_sqlite(db, ip_address, subuser, cache_key)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    return self._get_stats_postgres(db, ip_address, subuser, cache_key)
        except Exception as e:
            logger.error(f"Error fetching IP/subuser stats: {e}")
            return None

    def get_all_stats(self) -> List[IPSubuserStats]:
        """
        Get statistics for all IP/subuser combinations.

        Returns:
            List of IPSubuserStats objects
        """
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    return self._get_all_stats_sqlite(db)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    return self._get_all_stats_postgres(db)
        except Exception as e:
            logger.error(f"Error fetching all stats: {e}")
            return []

    def get_threshold_violations(self) -> List[IPSubuserStats]:
        """
        Get all IP/subuser combinations that exceed warning thresholds.

        Returns:
            List of IPSubuserStats objects with threshold violations
        """
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    return self._get_threshold_violations_sqlite(db)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    return self._get_threshold_violations_postgres(db)
        except Exception as e:
            logger.error(f"Error fetching threshold violations: {e}")
            return []

    def check_thresholds(self) -> Dict[str, List[IPSubuserStats]]:
        """
        Check all IP/subuser combinations against thresholds.

        Returns:
            Dictionary with threshold levels as keys and lists of violating stats as values
        """
        violations = {"warning": [], "critical": [], "blocked": []}

        all_stats = self.get_all_stats()

        for stats in all_stats:
            if stats.total_sent < self.config.minimum_sample_size:
                continue

            if stats.bounce_rate >= self.config.block_threshold:
                violations["blocked"].append(stats)
            elif stats.bounce_rate >= self.config.critical_threshold:
                violations["critical"].append(stats)
            elif stats.bounce_rate >= self.config.warning_threshold:
                violations["warning"].append(stats)

        return violations

    def reset_stats(self, ip_address: str, subuser: str) -> None:
        """
        Reset statistics for an IP/subuser combination.

        Args:
            ip_address: IP address
            subuser: Subuser
        """
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    self._reset_stats_sqlite(db, ip_address, subuser)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    self._reset_stats_postgres(db, ip_address, subuser)
        except Exception as e:
            logger.error(f"Error resetting stats: {e}")
            raise

    def cleanup_old_events(self, days_to_keep: int = 30) -> int:
        """
        Clean up old bounce events to prevent database bloat.

        Args:
            days_to_keep: Number of days of events to keep

        Returns:
            Number of events deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    return self._cleanup_old_events_sqlite(db, cutoff_date)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    return self._cleanup_old_events_postgres(db, cutoff_date)
        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")
            return 0

    def get_stats(self, ip_address: str, subuser: str) -> IPSubuserStats:
        """
        Get current statistics for an IP/subuser combination.

        Args:
            ip_address: IP address to get stats for
            subuser: Subuser to get stats for

        Returns:
            Current statistics for the IP/subuser combination
        """
        cache_key = (ip_address, subuser)

        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Fetch from database
        try:
            if self.db_path:
                # SQLite mode
                with SQLiteDatabaseConnection(self.db_path) as db:
                    return self._get_stats_sqlite(db, ip_address, subuser, cache_key)
            else:
                # PostgreSQL mode
                with PostgreSQLConnection() as db:
                    return self._get_stats_postgres(db, ip_address, subuser, cache_key)
        except Exception as e:
            logger.error(f"Error getting stats for {ip_address}/{subuser}: {e}")
            # Return default stats on error
            return IPSubuserStats(
                ip_address=ip_address,
                subuser=subuser,
                total_sent=0,
                total_bounced=0,
                hard_bounces=0,
                soft_bounces=0,
                block_bounces=0,
                bounce_rate=0.0,
                status="unknown",
            )

    def _get_stats_sqlite(self, db, ip_address: str, subuser: str, cache_key):
        """Get stats from SQLite database."""
        cursor = db.execute(
            """
            SELECT total_sent, total_bounced, hard_bounces, soft_bounces, block_bounces, status
            FROM bounce_rate_stats
            WHERE ip_address = ? AND subuser = ?
        """,
            (ip_address, subuser),
        )

        row = cursor.fetchone()
        if row:
            (
                total_sent,
                total_bounced,
                hard_bounces,
                soft_bounces,
                block_bounces,
                status,
            ) = row
            bounce_rate = (total_bounced / total_sent) if total_sent > 0 else 0.0

            stats = IPSubuserStats(
                ip_address=ip_address,
                subuser=subuser,
                total_sent=total_sent,
                total_bounced=total_bounced,
                hard_bounces=hard_bounces,
                soft_bounces=soft_bounces,
                block_bounces=block_bounces,
                bounce_rate=bounce_rate,
                status=status,
            )

            # Update cache
            self.cache[cache_key] = stats
            return stats

        # Return default stats if no record found
        return IPSubuserStats(
            ip_address=ip_address,
            subuser=subuser,
            total_sent=0,
            total_bounced=0,
            hard_bounces=0,
            soft_bounces=0,
            block_bounces=0,
            bounce_rate=0.0,
            status="active",
        )

    def _get_stats_postgres(self, db, ip_address: str, subuser: str, cache_key):
        """Get stats from PostgreSQL database."""
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT total_sent, total_bounced, hard_bounces, soft_bounces, block_bounces, status
            FROM bounce_rate_stats
            WHERE ip_address = %s AND subuser = %s
        """,
            (ip_address, subuser),
        )

        row = cursor.fetchone()
        if row:
            (
                total_sent,
                total_bounced,
                hard_bounces,
                soft_bounces,
                block_bounces,
                status,
            ) = row
            bounce_rate = (total_bounced / total_sent) if total_sent > 0 else 0.0

            stats = IPSubuserStats(
                ip_address=ip_address,
                subuser=subuser,
                total_sent=total_sent,
                total_bounced=total_bounced,
                hard_bounces=hard_bounces,
                soft_bounces=soft_bounces,
                block_bounces=block_bounces,
                bounce_rate=bounce_rate,
                status=status,
            )

            # Update cache
            self.cache[cache_key] = stats
            return stats

        # Return default stats if no record found
        return IPSubuserStats(
            ip_address=ip_address,
            subuser=subuser,
            total_sent=0,
            total_bounced=0,
            hard_bounces=0,
            soft_bounces=0,
            block_bounces=0,
            bounce_rate=0.0,
            status="active",
        )

    def _get_all_stats_sqlite(self, db):
        """Get all stats from SQLite database."""
        cursor = db.execute(
            """
            SELECT ip_address, subuser, total_sent, total_bounced, hard_bounces,
                   soft_bounces, block_bounces, bounce_rate, status, last_updated
            FROM bounce_rate_stats
            ORDER BY bounce_rate DESC, total_sent DESC
        """
        )

        results = cursor.fetchall()
        stats_list = []

        for result in results:
            stats = IPSubuserStats(
                ip_address=result[0],
                subuser=result[1],
                total_sent=result[2],
                total_bounced=result[3],
                hard_bounces=result[4],
                soft_bounces=result[5],
                block_bounces=result[6],
                bounce_rate=result[7],
                status=result[8],
                last_updated=(
                    datetime.fromisoformat(result[9]) if result[9] else datetime.now()
                ),
            )
            stats_list.append(stats)

        return stats_list

    def _get_all_stats_postgres(self, db):
        """Get all stats from PostgreSQL database."""
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT ip_address, subuser, total_sent, total_bounced, hard_bounces,
                   soft_bounces, block_bounces, bounce_rate, status, last_updated
            FROM bounce_rate_stats
            ORDER BY bounce_rate DESC, total_sent DESC
        """
        )

        results = cursor.fetchall()
        stats_list = []

        for result in results:
            stats = IPSubuserStats(
                ip_address=result[0],
                subuser=result[1],
                total_sent=result[2],
                total_bounced=result[3],
                hard_bounces=result[4],
                soft_bounces=result[5],
                block_bounces=result[6],
                bounce_rate=result[7],
                status=result[8],
                last_updated=result[9] if result[9] else datetime.now(),
            )
            stats_list.append(stats)

        return stats_list

    def _get_threshold_violations_sqlite(self, db):
        """Get threshold violations from SQLite database."""
        cursor = db.execute(
            """
            SELECT ip_address, subuser, total_sent, total_bounced, hard_bounces,
                   soft_bounces, block_bounces, bounce_rate, status, last_updated
            FROM bounce_rate_stats
            WHERE bounce_rate >= ? AND total_sent >= ?
            ORDER BY bounce_rate DESC
        """,
            (self.config.warning_threshold, self.config.minimum_sample_size),
        )

        results = cursor.fetchall()
        violations = []

        for result in results:
            stats = IPSubuserStats(
                ip_address=result[0],
                subuser=result[1],
                total_sent=result[2],
                total_bounced=result[3],
                hard_bounces=result[4],
                soft_bounces=result[5],
                block_bounces=result[6],
                bounce_rate=result[7],
                status=result[8],
                last_updated=(
                    datetime.fromisoformat(result[9]) if result[9] else datetime.now()
                ),
            )
            violations.append(stats)

        return violations

    def _get_threshold_violations_postgres(self, db):
        """Get threshold violations from PostgreSQL database."""
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT ip_address, subuser, total_sent, total_bounced, hard_bounces,
                   soft_bounces, block_bounces, bounce_rate, status, last_updated
            FROM bounce_rate_stats
            WHERE bounce_rate >= %s AND total_sent >= %s
            ORDER BY bounce_rate DESC
        """,
            (self.config.warning_threshold, self.config.minimum_sample_size),
        )

        results = cursor.fetchall()
        violations = []

        for result in results:
            stats = IPSubuserStats(
                ip_address=result[0],
                subuser=result[1],
                total_sent=result[2],
                total_bounced=result[3],
                hard_bounces=result[4],
                soft_bounces=result[5],
                block_bounces=result[6],
                bounce_rate=result[7],
                status=result[8],
                last_updated=result[9] if result[9] else datetime.now(),
            )
            violations.append(stats)

        return violations

    def _reset_stats_sqlite(self, db, ip_address: str, subuser: str):
        """Reset stats in SQLite database."""
        db.execute(
            """
            UPDATE bounce_rate_stats
            SET total_sent = 0, total_bounced = 0, hard_bounces = 0,
                soft_bounces = 0, block_bounces = 0, bounce_rate = 0.0,
                status = 'active', last_updated = ?
            WHERE ip_address = ? AND subuser = ?
        """,
            (datetime.now().isoformat(), ip_address, subuser),
        )

        db.commit()

        # Clear from cache
        cache_key = (ip_address, subuser)
        if cache_key in self.cache:
            del self.cache[cache_key]

        logger.info(f"Reset stats for {ip_address}/{subuser}")

    def _reset_stats_postgres(self, db, ip_address: str, subuser: str):
        """Reset stats in PostgreSQL database."""
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE bounce_rate_stats
            SET total_sent = 0, total_bounced = 0, hard_bounces = 0,
                soft_bounces = 0, block_bounces = 0, bounce_rate = 0.0,
                status = 'active', last_updated = CURRENT_TIMESTAMP
            WHERE ip_address = %s AND subuser = %s
        """,
            (ip_address, subuser),
        )

        db.commit()

        # Clear from cache
        cache_key = (ip_address, subuser)
        if cache_key in self.cache:
            del self.cache[cache_key]

        logger.info(f"Reset stats for {ip_address}/{subuser}")

    def _cleanup_old_events_sqlite(self, db, cutoff_date):
        """Cleanup old events in SQLite database."""
        cursor = db.execute(
            """
            DELETE FROM bounce_events_tracking
            WHERE timestamp < ?
        """,
            (cutoff_date.isoformat(),),
        )

        deleted_count = cursor.rowcount
        db.commit()

        logger.info(f"Cleaned up {deleted_count} old bounce events")
        return deleted_count

    def _cleanup_old_events_postgres(self, db, cutoff_date):
        """Cleanup old events in PostgreSQL database."""
        cursor = db.cursor()
        cursor.execute(
            """
            DELETE FROM bounce_events_tracking
            WHERE timestamp < %s
        """,
            (cutoff_date,),
        )

        deleted_count = cursor.rowcount
        db.commit()

        logger.info(f"Cleaned up {deleted_count} old bounce events")
        return deleted_count


def create_bounce_monitor_tables(db_path: Optional[str] = None) -> None:
    """
    Create database tables for bounce rate monitoring.

    Args:
        db_path: Path to the database file
    """
    monitor = BounceRateMonitor(BounceRateConfig(), db_path=db_path)
    logger.info("Bounce rate monitoring tables created successfully")


if __name__ == "__main__":
    # Example usage
    config = BounceRateConfig(
        sampling_period=SamplingPeriod.HOURLY,
        calculation_method=CalculationMethod.ROLLING_AVERAGE,
        rolling_window_hours=24,
        warning_threshold=0.05,
        critical_threshold=0.10,
        block_threshold=0.15,
    )

    monitor = BounceRateMonitor(config)

    # Example: Record a bounce event
    bounce_event = BounceEvent(
        email="test@example.com",
        ip_address="192.168.1.100",
        subuser="marketing",
        bounce_type="hard",
        reason="Invalid email address",
        timestamp=datetime.now(),
    )

    monitor.record_bounce_event(bounce_event)

    # Check bounce rate
    bounce_rate = monitor.get_bounce_rate("192.168.1.100", "marketing")
    print(f"Bounce rate: {bounce_rate:.2%}")

    # Check threshold violations
    violations = monitor.check_thresholds()
    print(f"Threshold violations: {violations}")
