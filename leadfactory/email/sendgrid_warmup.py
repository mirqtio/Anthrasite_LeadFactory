#!/usr/bin/env python3
"""
SendGrid Dedicated IP Warm-up Scheduler

This module provides a comprehensive system for managing SendGrid dedicated IP warm-up
schedules with progressive send caps, safety monitoring, and automated advancement.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Try to import project modules, fall back to basic implementations
try:
    from leadfactory.utils.logging_config import get_logger
except ImportError:
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


class WarmupStatus(Enum):
    """Warm-up process status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class WarmupStage(Enum):
    """Warm-up stages with progressive send limits."""

    STAGE_1 = 1  # 5,000 emails/day
    STAGE_2 = 2  # 15,000 emails/day
    STAGE_3 = 3  # 35,000 emails/day
    STAGE_4 = 4  # 50,000 emails/day
    STAGE_5 = 5  # 75,000 emails/day
    STAGE_6 = 6  # 100,000 emails/day
    STAGE_7 = 7  # 110,000 emails/day


@dataclass
class WarmupConfiguration:
    """Configuration for warm-up schedule and safety thresholds."""

    # Stage schedule with daily limits and durations
    stage_schedule: dict[int, dict[str, Any]] = None

    # Safety thresholds
    bounce_rate_threshold: float = 0.05  # 5% bounce rate threshold
    spam_rate_threshold: float = 0.001  # 0.1% spam rate threshold

    # Timing configuration
    stage_duration_days: int = 2  # Days per stage
    total_stages: int = 7  # Total number of stages
    check_interval_hours: int = 1  # How often to check thresholds

    # Limits
    max_daily_limit: int = 110000  # Maximum daily send limit

    # Alerting
    alert_email: Optional[str] = None

    def __post_init__(self):
        """Initialize default stage schedule if not provided."""
        if self.stage_schedule is None:
            self.stage_schedule = {
                1: {
                    "daily_limit": 5000,
                    "duration_days": 2,
                    "description": "Initial warm-up stage",
                },
                2: {
                    "daily_limit": 15000,
                    "duration_days": 2,
                    "description": "Low volume stage",
                },
                3: {
                    "daily_limit": 35000,
                    "duration_days": 2,
                    "description": "Medium volume stage",
                },
                4: {
                    "daily_limit": 50000,
                    "duration_days": 2,
                    "description": "Medium-high volume stage",
                },
                5: {
                    "daily_limit": 75000,
                    "duration_days": 2,
                    "description": "High volume stage",
                },
                6: {
                    "daily_limit": 100000,
                    "duration_days": 2,
                    "description": "Near-max volume stage",
                },
                7: {
                    "daily_limit": 110000,
                    "duration_days": 2,
                    "description": "Maximum volume stage",
                },
            }


@dataclass
class WarmupProgress:
    """Tracks warm-up progress for a specific IP address."""

    ip_address: str
    status: WarmupStatus
    current_stage: int
    start_date: date
    current_date: date
    stage_start_date: date

    # Send counts
    daily_sent_count: int = 0
    total_sent_count: int = 0

    # Safety monitoring
    bounce_count: int = 0
    spam_complaint_count: int = 0

    # Pause management
    is_paused: bool = False
    pause_reason: Optional[str] = None
    pause_timestamp: Optional[datetime] = None

    # Metadata
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SendGridWarmupScheduler:
    """
    SendGrid dedicated IP warm-up scheduler with progressive send caps.

    Manages a 14-day warm-up process with 7 stages of increasing daily send limits,
    safety monitoring for bounce and spam rates, and automated progression.
    """

    def __init__(
        self,
        config: Optional[WarmupConfiguration] = None,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the warm-up scheduler.

        Args:
            config: Warm-up configuration (uses default if None)
            db_path: Path to SQLite database (uses environment variable or default if None)
        """
        self.config = config or WarmupConfiguration()
        self.db_path = db_path or os.getenv("DATABASE_PATH", "warmup_scheduler.db")
        self.logger = get_logger(__name__)

        # Initialize database
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize SQLite database with required tables."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Create warmup progress table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sendgrid_warmup_progress (
                        ip_address TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        current_stage INTEGER NOT NULL,
                        start_date TEXT NOT NULL,
                        current_date TEXT NOT NULL,
                        stage_start_date TEXT NOT NULL,
                        daily_sent_count INTEGER DEFAULT 0,
                        total_sent_count INTEGER DEFAULT 0,
                        bounce_count INTEGER DEFAULT 0,
                        spam_complaint_count INTEGER DEFAULT 0,
                        is_paused BOOLEAN DEFAULT FALSE,
                        pause_reason TEXT,
                        pause_timestamp TEXT,
                        last_updated TEXT,
                        created_at TEXT,
                        config_json TEXT
                    )
                """
                )

                # Create daily logs table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sendgrid_warmup_daily_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        log_date TEXT NOT NULL,
                        stage INTEGER NOT NULL,
                        emails_sent INTEGER DEFAULT 0,
                        daily_limit INTEGER NOT NULL,
                        bounce_count INTEGER DEFAULT 0,
                        spam_complaint_count INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(ip_address, log_date)
                    )
                """
                )

                # Create events/audit table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sendgrid_warmup_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        event_data TEXT,
                        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Create indexes
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_warmup_events_ip_timestamp ON sendgrid_warmup_events(ip_address, timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_warmup_daily_logs_ip_date ON sendgrid_warmup_daily_logs(ip_address, log_date)"
                )

                conn.commit()
                self.logger.info("Warm-up database initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize warm-up database: {e}")
            raise

    @contextmanager
    def _get_db_connection(self):
        """Get SQLite database connection."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def start_warmup(self, ip_address: str, start_date: Optional[date] = None) -> bool:
        """
        Start warm-up process for an IP address.

        Args:
            ip_address: IP address to warm up
            start_date: Start date (uses today if None)

        Returns:
            True if warm-up started successfully, False if already exists
        """
        start_date = start_date or date.today()

        # Check if warm-up already exists
        existing_progress = self.get_warmup_progress(ip_address)
        if existing_progress is not None:
            self.logger.warning(f"Warm-up already exists for IP {ip_address}")
            return False

        # Create new warm-up progress
        progress = WarmupProgress(
            ip_address=ip_address,
            status=WarmupStatus.IN_PROGRESS,
            current_stage=1,
            start_date=start_date,
            current_date=start_date,
            stage_start_date=start_date,
            created_at=datetime.now(),
        )

        # Save to database
        self._save_warmup_progress(progress)

        # Log event
        self._log_event(
            ip_address,
            "warmup_started",
            {"start_date": start_date.isoformat(), "initial_stage": 1},
        )

        self.logger.info(f"Started warm-up for IP {ip_address} on {start_date}")
        return True

    def get_warmup_progress(self, ip_address: str) -> Optional[WarmupProgress]:
        """
        Get current warm-up progress for an IP address.

        Args:
            ip_address: IP address to check

        Returns:
            WarmupProgress object or None if not found
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM sendgrid_warmup_progress WHERE ip_address = ?
                """,
                    (ip_address,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to WarmupProgress object
                columns = [desc[0] for desc in cursor.description]
                data = dict(zip(columns, row))

                # Convert date strings back to date objects
                data["start_date"] = date.fromisoformat(data["start_date"])
                data["current_date"] = date.fromisoformat(data["current_date"])
                data["stage_start_date"] = date.fromisoformat(data["stage_start_date"])

                # Convert datetime strings
                if data["last_updated"]:
                    data["last_updated"] = datetime.fromisoformat(data["last_updated"])
                if data["created_at"]:
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                if data["pause_timestamp"]:
                    data["pause_timestamp"] = datetime.fromisoformat(
                        data["pause_timestamp"]
                    )

                # Convert status to enum
                data["status"] = WarmupStatus(data["status"])

                # Remove config_json from data
                data.pop("config_json", None)

                return WarmupProgress(**data)

        except Exception as e:
            self.logger.error(f"Failed to get warm-up progress for {ip_address}: {e}")
            return None

    def get_current_daily_limit(self, ip_address: str) -> int:
        """
        Get current daily send limit for an IP address.

        Args:
            ip_address: IP address to check

        Returns:
            Current daily limit or 0 if not in warm-up
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress or progress.status != WarmupStatus.IN_PROGRESS:
            return 0

        stage_config = self.config.stage_schedule.get(progress.current_stage, {})
        return stage_config.get("daily_limit", 0)

    def can_send_email(self, ip_address: str, email_count: int) -> tuple[bool, str]:
        """
        Check if sending emails is allowed under current warm-up limits.

        Args:
            ip_address: IP address to check
            email_count: Number of emails to send

        Returns:
            Tuple of (can_send: bool, reason: str)
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress:
            return False, "IP not in warm-up process"

        if progress.status != WarmupStatus.IN_PROGRESS:
            return False, f"Warm-up status is {progress.status.value}"

        if progress.is_paused:
            return False, f"Warm-up is paused: {progress.pause_reason}"

        daily_limit = self.get_current_daily_limit(ip_address)
        if progress.daily_sent_count + email_count > daily_limit:
            return (
                False,
                f"Would exceed daily limit ({progress.daily_sent_count + email_count} > {daily_limit})",
            )

        return True, "OK"

    def record_email_sent(self, ip_address: str, email_count: int) -> bool:
        """
        Record that emails were sent and update counters.

        Args:
            ip_address: IP address that sent emails
            email_count: Number of emails sent

        Returns:
            True if recorded successfully
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress:
            self.logger.warning(
                f"Cannot record emails for IP {ip_address} - not in warm-up"
            )
            return False

        # Update counters
        progress.daily_sent_count += email_count
        progress.total_sent_count += email_count
        progress.last_updated = datetime.now()

        # Save progress
        self._save_warmup_progress(progress)

        # Update daily log
        self._update_daily_log(
            ip_address, progress.current_date, progress.current_stage, email_count
        )

        # Log event
        self._log_event(
            ip_address,
            "emails_sent",
            {
                "count": email_count,
                "daily_total": progress.daily_sent_count,
                "overall_total": progress.total_sent_count,
            },
        )

        return True

    def advance_warmup_schedule(
        self, ip_address: str, current_date: Optional[date] = None
    ) -> bool:
        """
        Check and advance warm-up schedule if needed.

        Args:
            ip_address: IP address to advance
            current_date: Current date to use (defaults to today)

        Returns:
            True if check completed successfully
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress or progress.status != WarmupStatus.IN_PROGRESS:
            return True

        # Use provided current_date or fall back to today
        if current_date is None:
            current_date = date.today()

        stage_config = self.config.stage_schedule.get(progress.current_stage, {})
        stage_duration = stage_config.get(
            "duration_days", self.config.stage_duration_days
        )

        # Check if we need to advance to next day
        if current_date > progress.current_date:
            # Reset daily counter for new day
            progress.daily_sent_count = 0
            progress.current_date = current_date

            # Check if we need to advance stage
            days_in_stage = (current_date - progress.stage_start_date).days
            if days_in_stage >= stage_duration:
                if progress.current_stage < self.config.total_stages:
                    # Advance to next stage
                    progress.current_stage += 1
                    progress.stage_start_date = current_date

                    self._log_event(
                        ip_address,
                        "stage_advanced",
                        {
                            "new_stage": progress.current_stage,
                            "new_daily_limit": self.config.stage_schedule.get(
                                progress.current_stage, {}
                            ).get("daily_limit", 0),
                        },
                    )

                    self.logger.info(
                        f"Advanced IP {ip_address} to stage {progress.current_stage}"
                    )
                else:
                    # Warm-up completed
                    progress.status = WarmupStatus.COMPLETED

                    self._log_event(
                        ip_address,
                        "warmup_completed",
                        {
                            "total_emails_sent": progress.total_sent_count,
                            "completion_date": current_date.isoformat(),
                        },
                    )

                    self.logger.info(f"Completed warm-up for IP {ip_address}")

            # Save updated progress
            self._save_warmup_progress(progress)

        return True

    def check_safety_thresholds(self, ip_address: str) -> bool:
        """
        Check bounce and spam rates against safety thresholds.

        Args:
            ip_address: IP address to check

        Returns:
            True if within thresholds, False if thresholds exceeded (and paused)
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress or progress.total_sent_count == 0:
            return True

        bounce_rate = progress.bounce_count / progress.total_sent_count
        spam_rate = progress.spam_complaint_count / progress.total_sent_count

        # Check bounce rate threshold
        if bounce_rate > self.config.bounce_rate_threshold:
            reason = f"Bounce rate {bounce_rate:.3f} exceeds threshold {self.config.bounce_rate_threshold:.3f}"
            self.pause_warmup(ip_address, reason)
            return False

        # Check spam rate threshold
        if spam_rate > self.config.spam_rate_threshold:
            reason = f"Spam rate {spam_rate:.3f} exceeds threshold {self.config.spam_rate_threshold:.3f}"
            self.pause_warmup(ip_address, reason)
            return False

        return True

    def pause_warmup(self, ip_address: str, reason: str) -> bool:
        """
        Pause warm-up process for an IP address.

        Args:
            ip_address: IP address to pause
            reason: Reason for pausing

        Returns:
            True if paused successfully
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress:
            return False

        progress.status = WarmupStatus.PAUSED
        progress.is_paused = True
        progress.pause_reason = reason
        progress.pause_timestamp = datetime.now()
        progress.last_updated = datetime.now()

        self._save_warmup_progress(progress)

        self._log_event(
            ip_address,
            "warmup_paused",
            {"reason": reason, "stage": progress.current_stage},
        )

        self.logger.warning(f"Paused warm-up for IP {ip_address}: {reason}")
        return True

    def resume_warmup(self, ip_address: str) -> bool:
        """
        Resume paused warm-up process for an IP address.

        Args:
            ip_address: IP address to resume

        Returns:
            True if resumed successfully
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress or not progress.is_paused:
            return False

        progress.status = WarmupStatus.IN_PROGRESS
        progress.is_paused = False
        progress.pause_reason = None
        progress.pause_timestamp = None
        progress.last_updated = datetime.now()

        self._save_warmup_progress(progress)

        self._log_event(ip_address, "warmup_resumed", {"stage": progress.current_stage})

        self.logger.info(f"Resumed warm-up for IP {ip_address}")
        return True

    def get_warmup_status_summary(self, ip_address: str) -> dict[str, Any]:
        """
        Get comprehensive status summary for an IP address.

        Args:
            ip_address: IP address to summarize

        Returns:
            Dictionary with status information
        """
        progress = self.get_warmup_progress(ip_address)
        if not progress:
            return {"error": f"No warm-up found for IP {ip_address}"}

        daily_limit = self.get_current_daily_limit(ip_address)

        return {
            "ip_address": ip_address,
            "status": progress.status.value,
            "current_stage": progress.current_stage,
            "start_date": progress.start_date.isoformat(),
            "current_date": progress.current_date.isoformat(),
            "stage_start_date": progress.stage_start_date.isoformat(),
            "daily_limit": daily_limit,
            "daily_sent": progress.daily_sent_count,
            "daily_remaining": max(0, daily_limit - progress.daily_sent_count),
            "total_sent": progress.total_sent_count,
            "bounce_count": progress.bounce_count,
            "spam_complaint_count": progress.spam_complaint_count,
            "bounce_rate": progress.bounce_count / max(1, progress.total_sent_count),
            "spam_rate": progress.spam_complaint_count
            / max(1, progress.total_sent_count),
            "is_paused": progress.is_paused,
            "pause_reason": progress.pause_reason,
            "last_updated": (
                progress.last_updated.isoformat() if progress.last_updated else None
            ),
        }

    def _save_warmup_progress(self, progress: WarmupProgress) -> None:
        """Save warm-up progress to database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Convert to dictionary and handle special fields
                data = asdict(progress)
                data["start_date"] = progress.start_date.isoformat()
                data["current_date"] = progress.current_date.isoformat()
                data["stage_start_date"] = progress.stage_start_date.isoformat()
                data["status"] = progress.status.value

                if progress.last_updated:
                    data["last_updated"] = progress.last_updated.isoformat()
                if progress.created_at:
                    data["created_at"] = progress.created_at.isoformat()
                if progress.pause_timestamp:
                    data["pause_timestamp"] = progress.pause_timestamp.isoformat()

                # Add config as JSON
                data["config_json"] = json.dumps(asdict(self.config))

                # Use INSERT OR REPLACE
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO sendgrid_warmup_progress
                    (ip_address, status, current_stage, start_date, current_date, stage_start_date,
                     daily_sent_count, total_sent_count, bounce_count, spam_complaint_count,
                     is_paused, pause_reason, pause_timestamp, last_updated, created_at, config_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["ip_address"],
                        data["status"],
                        data["current_stage"],
                        data["start_date"],
                        data["current_date"],
                        data["stage_start_date"],
                        data["daily_sent_count"],
                        data["total_sent_count"],
                        data["bounce_count"],
                        data["spam_complaint_count"],
                        data["is_paused"],
                        data["pause_reason"],
                        data["pause_timestamp"],
                        data["last_updated"],
                        data["created_at"],
                        data["config_json"],
                    ),
                )

                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save warm-up progress: {e}")
            raise

    def _log_event(
        self, ip_address: str, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Log an event to the audit trail."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO sendgrid_warmup_events (ip_address, event_type, event_data)
                    VALUES (?, ?, ?)
                """,
                    (ip_address, event_type, json.dumps(event_data)),
                )
                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")

    def _update_daily_log(
        self, ip_address: str, log_date: date, stage: int, emails_sent: int
    ) -> None:
        """Update daily log entry."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                daily_limit = self.config.stage_schedule.get(stage, {}).get(
                    "daily_limit", 0
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO sendgrid_warmup_daily_logs
                    (ip_address, log_date, stage, emails_sent, daily_limit)
                    VALUES (?, ?, ?, COALESCE((SELECT emails_sent FROM sendgrid_warmup_daily_logs
                                             WHERE ip_address = ? AND log_date = ?), 0) + ?, ?)
                """,
                    (
                        ip_address,
                        log_date.isoformat(),
                        stage,
                        ip_address,
                        log_date.isoformat(),
                        emails_sent,
                        daily_limit,
                    ),
                )

                conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to update daily log: {e}")


# Convenience functions for easy integration


def get_warmup_scheduler(db_path: Optional[str] = None) -> SendGridWarmupScheduler:
    """Get a SendGrid warm-up scheduler instance."""
    return SendGridWarmupScheduler(db_path=db_path)


def check_warmup_limits(
    ip_address: str, email_count: int, db_path: Optional[str] = None
) -> tuple[bool, str]:
    """
    Check if sending emails is allowed under warm-up limits.

    Args:
        ip_address: IP address to check
        email_count: Number of emails to send
        db_path: Database path (optional)

    Returns:
        Tuple of (can_send: bool, reason: str)
    """
    scheduler = get_warmup_scheduler(db_path)
    return scheduler.can_send_email(ip_address, email_count)


def record_warmup_emails_sent(
    ip_address: str, email_count: int, db_path: Optional[str] = None
) -> bool:
    """
    Record that emails were sent for warm-up tracking.

    Args:
        ip_address: IP address that sent emails
        email_count: Number of emails sent
        db_path: Database path (optional)

    Returns:
        True if recorded successfully
    """
    scheduler = get_warmup_scheduler(db_path)
    return scheduler.record_email_sent(ip_address, email_count)


def advance_warmup_if_needed(ip_address: str, db_path: Optional[str] = None) -> bool:
    """
    Check and advance warm-up schedule if needed.

    Args:
        ip_address: IP address to check
        db_path: Database path (optional)

    Returns:
        True if check completed successfully
    """
    scheduler = get_warmup_scheduler(db_path)
    return scheduler.advance_warmup_schedule(ip_address)
