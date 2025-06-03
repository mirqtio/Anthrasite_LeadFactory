"""
SendGrid Email Throttling System

This module implements an automated throttling system that enforces daily send caps
based on warm-up schedules, implements rate limiting, manages email queues, and
provides monitoring and emergency stop mechanisms for compliance.
"""

import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler, WarmupStatus

# Configure logging
logger = logging.getLogger(__name__)


class ThrottleStatus(Enum):
    """Email throttling status."""

    ACTIVE = "active"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"
    DISABLED = "disabled"


class QueuePriority(Enum):
    """Email queue priority levels."""

    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class ThrottleConfig:
    """Configuration for email throttling."""

    max_sends_per_hour: int = 100
    max_sends_per_minute: int = 10
    burst_limit: int = 5
    burst_window_seconds: int = 60
    queue_size_limit: int = 10000
    emergency_stop_threshold: float = 0.95  # Stop at 95% of daily limit
    rate_distribution_hours: int = 12  # Distribute sends over 12 hours


@dataclass
class EmailBatch:
    """Represents a batch of emails to be sent."""

    batch_id: str
    ip_address: str
    emails: List[Dict[str, Any]]
    priority: QueuePriority
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "batch_id": self.batch_id,
            "ip_address": self.ip_address,
            "emails": self.emails,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": (
                self.scheduled_for.isoformat() if self.scheduled_for else None
            ),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmailBatch":
        """Create from dictionary."""
        return cls(
            batch_id=data["batch_id"],
            ip_address=data["ip_address"],
            emails=data["emails"],
            priority=QueuePriority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            scheduled_for=(
                datetime.fromisoformat(data["scheduled_for"])
                if data["scheduled_for"]
                else None
            ),
            attempts=data["attempts"],
            max_attempts=data["max_attempts"],
        )


@dataclass
class SendMetrics:
    """Metrics for email sending."""

    date: date
    ip_address: str
    total_sent: int = 0
    total_queued: int = 0
    total_failed: int = 0
    hourly_counts: Dict[int, int] = None  # Hour -> count mapping
    last_send_time: Optional[datetime] = None

    def __post_init__(self):
        if self.hourly_counts is None:
            self.hourly_counts = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "date": self.date.isoformat(),
            "ip_address": self.ip_address,
            "total_sent": self.total_sent,
            "total_queued": self.total_queued,
            "total_failed": self.total_failed,
            "hourly_counts": self.hourly_counts,
            "last_send_time": (
                self.last_send_time.isoformat() if self.last_send_time else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SendMetrics":
        """Create from dictionary."""
        # Convert string keys back to integers for hourly_counts
        hourly_counts = data.get("hourly_counts", {})
        if hourly_counts:
            hourly_counts = {int(k): v for k, v in hourly_counts.items()}

        return cls(
            date=date.fromisoformat(data["date"]),
            ip_address=data["ip_address"],
            total_sent=data["total_sent"],
            total_queued=data["total_queued"],
            total_failed=data["total_failed"],
            hourly_counts=hourly_counts,
            last_send_time=(
                datetime.fromisoformat(data["last_send_time"])
                if data.get("last_send_time")
                else None
            ),
        )


class SendGridThrottler:
    """
    SendGrid email throttling system with warm-up integration.

    Manages email sending rates based on warm-up schedules, implements
    queue management, rate limiting, and compliance monitoring.
    """

    def __init__(
        self,
        db_path: str = "sendgrid_throttling.db",
        config: Optional[ThrottleConfig] = None,
        warmup_scheduler: Optional[SendGridWarmupScheduler] = None,
    ):
        """
        Initialize the throttling system.

        Args:
            db_path: Path to SQLite database for persistence
            config: Throttling configuration
            warmup_scheduler: Optional warm-up scheduler for integration
        """
        self.db_path = Path(db_path)
        self.config = config or ThrottleConfig()
        self.warmup_scheduler = warmup_scheduler
        self.status = ThrottleStatus.ACTIVE

        # Thread-safe queues for different priorities
        self.queues = {
            QueuePriority.HIGH: Queue(),
            QueuePriority.NORMAL: Queue(),
            QueuePriority.LOW: Queue(),
        }

        # Rate limiting tracking
        self.rate_limiter_lock = threading.Lock()
        self.recent_sends = []  # List of recent send timestamps

        # Initialize database
        self._init_database()

        logger.info(
            f"SendGrid throttler initialized with config: {asdict(self.config)}"
        )

    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_database(self):
        """Initialize SQLite database tables."""
        with self._get_db_connection() as conn:
            # Email batches queue table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS email_batches (
                    batch_id TEXT PRIMARY KEY,
                    ip_address TEXT NOT NULL,
                    emails TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    scheduled_for TEXT,
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'queued'
                )
            """
            )

            # Send metrics table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS send_metrics (
                    date TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    total_sent INTEGER DEFAULT 0,
                    total_queued INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0,
                    hourly_counts TEXT,
                    last_send_time TEXT,
                    PRIMARY KEY (date, ip_address)
                )
            """
            )

            # Throttle events table for audit logging
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS throttle_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ip_address TEXT,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batches_ip_status ON email_batches(ip_address, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batches_scheduled ON email_batches(scheduled_for)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_date ON send_metrics(date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON throttle_events(timestamp)"
            )

            conn.commit()

    def _log_event(
        self,
        event_type: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log throttling events for audit trail."""
        try:
            with self._get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO throttle_events (timestamp, event_type, ip_address, details) VALUES (?, ?, ?, ?)",
                    (
                        datetime.now().isoformat(),
                        event_type,
                        ip_address,
                        json.dumps(details) if details else None,
                    ),
                )
                conn.commit()

            logger.info(
                f"Throttle Event: {event_type} for {ip_address or 'system'}: {details or {}}"
            )
        except Exception as e:
            logger.error(f"Failed to log throttle event: {e}")

    def get_daily_limit(
        self, ip_address: str, target_date: Optional[date] = None
    ) -> int:
        """
        Get daily send limit for an IP based on warm-up schedule.

        Args:
            ip_address: IP address to check
            target_date: Date to check (defaults to today)

        Returns:
            Daily send limit for the IP
        """
        if target_date is None:
            target_date = date.today()

        # If we have a warm-up scheduler, get limit from there
        if self.warmup_scheduler:
            try:
                progress = self.warmup_scheduler.get_warmup_progress(ip_address)
                if progress and progress.status == WarmupStatus.IN_PROGRESS:
                    return self.warmup_scheduler.get_current_daily_limit(ip_address)
                elif progress and progress.status == WarmupStatus.COMPLETED:
                    # Post warm-up limit (could be configured)
                    return 110000  # Full capacity after warm-up
            except Exception as e:
                logger.warning(f"Failed to get warm-up limit for {ip_address}: {e}")

        # Default conservative limit if no warm-up info
        return 100

    def get_current_metrics(
        self, ip_address: str, target_date: Optional[date] = None
    ) -> SendMetrics:
        """
        Get current send metrics for an IP.

        Args:
            ip_address: IP address to check
            target_date: Date to check (defaults to today)

        Returns:
            Current send metrics
        """
        if target_date is None:
            target_date = date.today()

        try:
            with self._get_db_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM send_metrics WHERE date = ? AND ip_address = ?",
                    (target_date.isoformat(), ip_address),
                ).fetchone()

                if row:
                    data = dict(row)
                    data["hourly_counts"] = (
                        json.loads(data["hourly_counts"])
                        if data["hourly_counts"]
                        else {}
                    )
                    return SendMetrics.from_dict(data)
                else:
                    # Create new metrics record
                    metrics = SendMetrics(date=target_date, ip_address=ip_address)
                    self._store_metrics(metrics)
                    return metrics
        except Exception as e:
            logger.error(f"Failed to get metrics for {ip_address}: {e}")
            return SendMetrics(date=target_date, ip_address=ip_address)

    def _store_metrics(self, metrics: SendMetrics):
        """Store send metrics to database."""
        try:
            with self._get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO send_metrics
                    (date, ip_address, total_sent, total_queued, total_failed, hourly_counts, last_send_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metrics.date.isoformat(),
                        metrics.ip_address,
                        metrics.total_sent,
                        metrics.total_queued,
                        metrics.total_failed,
                        json.dumps(metrics.hourly_counts),
                        (
                            metrics.last_send_time.isoformat()
                            if metrics.last_send_time
                            else None
                        ),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")

    def can_send_now(self, ip_address: str, email_count: int = 1) -> Tuple[bool, str]:
        """
        Check if emails can be sent now based on throttling rules.

        Args:
            ip_address: IP address to check
            email_count: Number of emails to send

        Returns:
            Tuple of (can_send, reason)
        """
        if self.status == ThrottleStatus.EMERGENCY_STOP:
            return False, "Emergency stop activated"

        if self.status == ThrottleStatus.PAUSED:
            return False, "Throttling paused"

        if self.status == ThrottleStatus.DISABLED:
            return True, "Throttling disabled"

        # Check daily limit
        daily_limit = self.get_daily_limit(ip_address)
        current_metrics = self.get_current_metrics(ip_address)

        if current_metrics.total_sent + email_count > daily_limit:
            return (
                False,
                f"Daily limit exceeded ({current_metrics.total_sent}/{daily_limit})",
            )

        # Check emergency stop threshold
        if (
            current_metrics.total_sent + email_count
        ) / daily_limit >= self.config.emergency_stop_threshold:
            self.emergency_stop(ip_address, "Approaching daily limit")
            return False, "Emergency stop triggered - approaching daily limit"

        # Check rate limiting
        with self.rate_limiter_lock:
            now = datetime.now()

            # Clean old timestamps
            cutoff = now - timedelta(seconds=self.config.burst_window_seconds)
            self.recent_sends = [ts for ts in self.recent_sends if ts > cutoff]

            # Check burst limit
            if len(self.recent_sends) + email_count > self.config.burst_limit:
                return (
                    False,
                    f"Burst limit exceeded ({len(self.recent_sends)}/{self.config.burst_limit})",
                )

            # Check hourly limit
            current_hour = now.hour
            hourly_count = current_metrics.hourly_counts.get(current_hour, 0)
            if hourly_count + email_count > self.config.max_sends_per_hour:
                return (
                    False,
                    f"Hourly limit exceeded ({hourly_count}/{self.config.max_sends_per_hour})",
                )

        return True, "OK"

    def queue_email_batch(self, batch: EmailBatch) -> bool:
        """
        Queue an email batch for sending.

        Args:
            batch: Email batch to queue

        Returns:
            True if queued successfully
        """
        try:
            # Check queue size limit
            total_queued = sum(q.qsize() for q in self.queues.values())
            if total_queued >= self.config.queue_size_limit:
                self._log_event(
                    "queue_full", batch.ip_address, {"batch_id": batch.batch_id}
                )
                return False

            # Store batch in database
            with self._get_db_connection() as conn:
                batch_data = batch.to_dict()
                conn.execute(
                    """
                    INSERT INTO email_batches
                    (batch_id, ip_address, emails, priority, created_at, scheduled_for, attempts, max_attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        batch.batch_id,
                        batch.ip_address,
                        json.dumps(batch.emails),
                        batch.priority.value,
                        batch.created_at.isoformat(),
                        (
                            batch.scheduled_for.isoformat()
                            if batch.scheduled_for
                            else None
                        ),
                        batch.attempts,
                        batch.max_attempts,
                    ),
                )
                conn.commit()

            # Add to in-memory queue
            self.queues[batch.priority].put(batch)

            # Update metrics
            metrics = self.get_current_metrics(batch.ip_address)
            metrics.total_queued += len(batch.emails)
            self._store_metrics(metrics)

            self._log_event(
                "batch_queued",
                batch.ip_address,
                {
                    "batch_id": batch.batch_id,
                    "email_count": len(batch.emails),
                    "priority": batch.priority.name,
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to queue batch {batch.batch_id}: {e}")
            return False

    def get_next_batch(self, ip_address: Optional[str] = None) -> Optional[EmailBatch]:
        """
        Get the next email batch to send, respecting priority and throttling.

        Args:
            ip_address: Optional IP address filter

        Returns:
            Next batch to send or None
        """
        # Check queues in priority order
        for priority in [QueuePriority.HIGH, QueuePriority.NORMAL, QueuePriority.LOW]:
            try:
                while not self.queues[priority].empty():
                    batch = self.queues[priority].get_nowait()

                    # Filter by IP if specified
                    if ip_address and batch.ip_address != ip_address:
                        # Put back in queue
                        self.queues[priority].put(batch)
                        continue

                    # Check if scheduled for future
                    if batch.scheduled_for and datetime.now() < batch.scheduled_for:
                        # Put back in queue
                        self.queues[priority].put(batch)
                        continue

                    # Check if can send now
                    can_send, reason = self.can_send_now(
                        batch.ip_address, len(batch.emails)
                    )
                    if can_send:
                        return batch
                    else:
                        # Put back in queue if temporary issue
                        if "limit exceeded" in reason.lower():
                            self.queues[priority].put(batch)
                        else:
                            logger.warning(f"Dropping batch {batch.batch_id}: {reason}")
                        continue

            except Empty:
                continue

        return None

    def record_send_success(self, batch: EmailBatch, sent_count: int):
        """
        Record successful email sends.

        Args:
            batch: Email batch that was sent
            sent_count: Number of emails successfully sent
        """
        try:
            now = datetime.now()

            # Update rate limiter
            with self.rate_limiter_lock:
                self.recent_sends.extend([now] * sent_count)

            # Update metrics
            metrics = self.get_current_metrics(batch.ip_address)
            metrics.total_sent += sent_count
            metrics.total_queued -= len(batch.emails)
            metrics.last_send_time = now

            # Update hourly counts
            current_hour = now.hour
            metrics.hourly_counts[current_hour] = (
                metrics.hourly_counts.get(current_hour, 0) + sent_count
            )

            self._store_metrics(metrics)

            # Remove batch from database
            with self._get_db_connection() as conn:
                conn.execute(
                    "DELETE FROM email_batches WHERE batch_id = ?", (batch.batch_id,)
                )
                conn.commit()

            self._log_event(
                "send_success",
                batch.ip_address,
                {
                    "batch_id": batch.batch_id,
                    "sent_count": sent_count,
                    "total_sent_today": metrics.total_sent,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to record send success for batch {batch.batch_id}: {e}"
            )

    def record_send_failure(self, batch: EmailBatch, error: str):
        """
        Record failed email sends.

        Args:
            batch: Email batch that failed
            error: Error message
        """
        try:
            batch.attempts += 1

            # Update metrics
            metrics = self.get_current_metrics(batch.ip_address)
            metrics.total_failed += len(batch.emails)
            metrics.total_queued -= len(batch.emails)
            self._store_metrics(metrics)

            if batch.attempts < batch.max_attempts:
                # Retry later
                batch.scheduled_for = datetime.now() + timedelta(
                    minutes=5 * batch.attempts
                )
                self.queue_email_batch(batch)
            else:
                # Remove from database
                with self._get_db_connection() as conn:
                    conn.execute(
                        "DELETE FROM email_batches WHERE batch_id = ?",
                        (batch.batch_id,),
                    )
                    conn.commit()

            self._log_event(
                "send_failure",
                batch.ip_address,
                {
                    "batch_id": batch.batch_id,
                    "error": error,
                    "attempts": batch.attempts,
                    "max_attempts": batch.max_attempts,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to record send failure for batch {batch.batch_id}: {e}"
            )

    def emergency_stop(
        self, ip_address: Optional[str] = None, reason: str = "Manual stop"
    ):
        """
        Trigger emergency stop for throttling.

        Args:
            ip_address: Optional IP address to stop (None for all)
            reason: Reason for emergency stop
        """
        self.status = ThrottleStatus.EMERGENCY_STOP

        self._log_event(
            "emergency_stop",
            ip_address,
            {
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            },
        )

        logger.critical(
            f"Emergency stop activated for {ip_address or 'all IPs'}: {reason}"
        )

    def pause_throttling(self, reason: str = "Manual pause"):
        """Pause throttling system."""
        self.status = ThrottleStatus.PAUSED
        self._log_event("throttling_paused", None, {"reason": reason})
        logger.warning(f"Throttling paused: {reason}")

    def resume_throttling(self, reason: str = "Manual resume"):
        """Resume throttling system."""
        self.status = ThrottleStatus.ACTIVE
        self._log_event("throttling_resumed", None, {"reason": reason})
        logger.info(f"Throttling resumed: {reason}")

    def get_throttle_status(self) -> Dict[str, Any]:
        """Get current throttling system status."""
        total_queued = sum(q.qsize() for q in self.queues.values())

        return {
            "status": self.status.value,
            "total_queued": total_queued,
            "queue_breakdown": {
                priority.name: self.queues[priority].qsize()
                for priority in QueuePriority
            },
            "config": asdict(self.config),
        }

    def get_ip_status_summary(self, ip_address: str) -> Dict[str, Any]:
        """Get comprehensive status summary for an IP."""
        daily_limit = self.get_daily_limit(ip_address)
        metrics = self.get_current_metrics(ip_address)
        can_send, reason = self.can_send_now(ip_address)

        return {
            "ip_address": ip_address,
            "daily_limit": daily_limit,
            "total_sent": metrics.total_sent,
            "total_queued": metrics.total_queued,
            "total_failed": metrics.total_failed,
            "utilization": metrics.total_sent / daily_limit if daily_limit > 0 else 0,
            "can_send": can_send,
            "send_status": reason,
            "hourly_breakdown": metrics.hourly_counts,
            "last_send_time": (
                metrics.last_send_time.isoformat() if metrics.last_send_time else None
            ),
        }


# Convenience functions
def get_throttler(
    db_path: str = "sendgrid_throttling.db",
    config: Optional[ThrottleConfig] = None,
    warmup_scheduler: Optional[SendGridWarmupScheduler] = None,
) -> SendGridThrottler:
    """Get a configured SendGrid throttler instance."""
    return SendGridThrottler(
        db_path=db_path, config=config, warmup_scheduler=warmup_scheduler
    )


def create_email_batch(
    batch_id: str,
    ip_address: str,
    emails: List[Dict[str, Any]],
    priority: QueuePriority = QueuePriority.NORMAL,
) -> EmailBatch:
    """Create an email batch for queuing."""
    return EmailBatch(
        batch_id=batch_id,
        ip_address=ip_address,
        emails=emails,
        priority=priority,
        created_at=datetime.now(),
    )


def check_send_capacity(
    ip_address: str, email_count: int = 1, throttler: Optional[SendGridThrottler] = None
) -> Tuple[bool, str]:
    """Check if emails can be sent for an IP address."""
    if throttler is None:
        throttler = get_throttler()

    return throttler.can_send_now(ip_address, email_count)
