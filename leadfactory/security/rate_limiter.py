"""
Rate limiting system for PDF report operations.

This module provides configurable rate limiting to prevent abuse
and ensure fair usage of PDF generation and access operations.
"""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple

from leadfactory.security.audit_logger import get_audit_logger

logger = get_audit_logger()


class RateLimitType(Enum):
    """Types of rate limits."""

    PDF_GENERATION = "pdf_generation"
    PDF_ACCESS = "pdf_access"
    PDF_DOWNLOAD = "pdf_download"
    TOKEN_GENERATION = "token_generation"
    SESSION_CREATION = "session_creation"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 10
    requests_per_hour: int = 100
    requests_per_day: int = 1000
    burst_allowance: int = 5
    cooldown_period_seconds: int = 60


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(
        self,
        allowed: bool,
        remaining_requests: int = 0,
        reset_time: Optional[datetime] = None,
        retry_after_seconds: Optional[int] = None,
    ):
        self.allowed = allowed
        self.remaining_requests = remaining_requests
        self.reset_time = reset_time
        self.retry_after_seconds = retry_after_seconds


class PDFRateLimiter:
    """Rate limiter specifically designed for PDF operations."""

    def __init__(self):
        """Initialize the PDF rate limiter."""
        self._configs = self._initialize_default_configs()
        self._user_requests: Dict[str, Dict[RateLimitType, deque]] = defaultdict(
            lambda: defaultdict(deque)
        )
        self._user_violations: Dict[str, Dict[RateLimitType, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._lock = threading.RLock()

    def _initialize_default_configs(self) -> Dict[RateLimitType, RateLimitConfig]:
        """Initialize default rate limit configurations."""
        return {
            RateLimitType.PDF_GENERATION: RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=50,
                requests_per_day=200,
                burst_allowance=2,
                cooldown_period_seconds=120,
            ),
            RateLimitType.PDF_ACCESS: RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=200,
                requests_per_day=1000,
                burst_allowance=10,
                cooldown_period_seconds=30,
            ),
            RateLimitType.PDF_DOWNLOAD: RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                requests_per_day=500,
                burst_allowance=5,
                cooldown_period_seconds=60,
            ),
            RateLimitType.TOKEN_GENERATION: RateLimitConfig(
                requests_per_minute=3,
                requests_per_hour=30,
                requests_per_day=100,
                burst_allowance=1,
                cooldown_period_seconds=300,
            ),
            RateLimitType.SESSION_CREATION: RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=20,
                requests_per_day=50,
                burst_allowance=2,
                cooldown_period_seconds=180,
            ),
        }

    def check_rate_limit(
        self,
        user_id: str,
        operation_type: RateLimitType,
        ip_address: Optional[str] = None,
    ) -> RateLimitResult:
        """
        Check if a request is within rate limits.

        Args:
            user_id: ID of the user making the request
            operation_type: Type of operation being performed
            ip_address: IP address of the request (optional)

        Returns:
            RateLimitResult indicating if request is allowed
        """
        with self._lock:
            config = self._configs.get(operation_type)
            if not config:
                return RateLimitResult(allowed=True)

            now = datetime.utcnow()
            user_requests = self._user_requests[user_id][operation_type]

            # Clean up old requests
            self._cleanup_old_requests(user_requests, now)

            # Check different time windows
            minute_count = self._count_requests_in_window(user_requests, now, minutes=1)
            hour_count = self._count_requests_in_window(user_requests, now, hours=1)
            day_count = self._count_requests_in_window(user_requests, now, hours=24)

            # Check limits
            if minute_count >= config.requests_per_minute:
                self._log_rate_limit_violation(
                    user_id,
                    operation_type,
                    "per_minute",
                    minute_count,
                    config.requests_per_minute,
                    ip_address,
                )
                return RateLimitResult(
                    allowed=False, remaining_requests=0, retry_after_seconds=60
                )

            if hour_count >= config.requests_per_hour:
                self._log_rate_limit_violation(
                    user_id,
                    operation_type,
                    "per_hour",
                    hour_count,
                    config.requests_per_hour,
                    ip_address,
                )
                return RateLimitResult(
                    allowed=False, remaining_requests=0, retry_after_seconds=3600
                )

            if day_count >= config.requests_per_day:
                self._log_rate_limit_violation(
                    user_id,
                    operation_type,
                    "per_day",
                    day_count,
                    config.requests_per_day,
                    ip_address,
                )
                return RateLimitResult(
                    allowed=False, remaining_requests=0, retry_after_seconds=86400
                )

            # Check burst allowance
            recent_requests = self._count_requests_in_window(
                user_requests, now, seconds=10
            )
            if recent_requests >= config.burst_allowance:
                self._log_rate_limit_violation(
                    user_id,
                    operation_type,
                    "burst",
                    recent_requests,
                    config.burst_allowance,
                    ip_address,
                )
                return RateLimitResult(
                    allowed=False,
                    remaining_requests=0,
                    retry_after_seconds=config.cooldown_period_seconds,
                )

            # Request is allowed - record it
            user_requests.append(now)

            # Calculate remaining requests
            remaining_minute = max(0, config.requests_per_minute - minute_count - 1)
            remaining_hour = max(0, config.requests_per_hour - hour_count - 1)
            remaining_day = max(0, config.requests_per_day - day_count - 1)

            return RateLimitResult(
                allowed=True,
                remaining_requests=min(remaining_minute, remaining_hour, remaining_day),
                reset_time=now + timedelta(minutes=1),
            )

    def _cleanup_old_requests(self, user_requests: deque, now: datetime):
        """Remove requests older than 24 hours."""
        cutoff = now - timedelta(hours=24)
        while user_requests and user_requests[0] < cutoff:
            user_requests.popleft()

    def _count_requests_in_window(
        self,
        user_requests: deque,
        now: datetime,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
    ) -> int:
        """Count requests within a time window."""
        window_start = now - timedelta(seconds=seconds, minutes=minutes, hours=hours)
        count = 0
        for request_time in reversed(user_requests):
            if request_time >= window_start:
                count += 1
            else:
                break
        return count

    def _log_rate_limit_violation(
        self,
        user_id: str,
        operation_type: RateLimitType,
        limit_type: str,
        current_count: int,
        limit_value: int,
        ip_address: Optional[str],
    ):
        """Log rate limit violation."""
        self._user_violations[user_id][operation_type] += 1

        logger.log_rate_limit_exceeded(
            user_id=user_id,
            operation=operation_type.value,
            limit_type=limit_type,
            current_count=current_count,
            limit_value=limit_value,
            ip_address=ip_address,
            additional_data={
                "total_violations": self._user_violations[user_id][operation_type]
            },
        )

    def get_user_stats(self, user_id: str) -> Dict:
        """Get rate limiting statistics for a user."""
        with self._lock:
            stats = {}
            for operation_type in RateLimitType:
                user_requests = self._user_requests[user_id][operation_type]
                now = datetime.utcnow()

                stats[operation_type.value] = {
                    "requests_last_minute": self._count_requests_in_window(
                        user_requests, now, minutes=1
                    ),
                    "requests_last_hour": self._count_requests_in_window(
                        user_requests, now, hours=1
                    ),
                    "requests_last_day": self._count_requests_in_window(
                        user_requests, now, hours=24
                    ),
                    "total_violations": self._user_violations[user_id][operation_type],
                    "config": {
                        "per_minute": self._configs[operation_type].requests_per_minute,
                        "per_hour": self._configs[operation_type].requests_per_hour,
                        "per_day": self._configs[operation_type].requests_per_day,
                    },
                }

            return stats

    def reset_user_limits(
        self, user_id: str, operation_type: Optional[RateLimitType] = None
    ):
        """Reset rate limits for a user."""
        with self._lock:
            if operation_type:
                self._user_requests[user_id][operation_type].clear()
                self._user_violations[user_id][operation_type] = 0
            else:
                self._user_requests[user_id].clear()
                self._user_violations[user_id].clear()

    def update_config(self, operation_type: RateLimitType, config: RateLimitConfig):
        """Update rate limit configuration for an operation type."""
        with self._lock:
            self._configs[operation_type] = config

    def is_user_blocked(self, user_id: str, operation_type: RateLimitType) -> bool:
        """Check if a user is currently blocked due to rate limiting."""
        result = self.check_rate_limit(user_id, operation_type)
        return not result.allowed


# Global rate limiter instance
_rate_limiter: Optional[PDFRateLimiter] = None


def get_rate_limiter() -> PDFRateLimiter:
    """Get the global PDF rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = PDFRateLimiter()
    return _rate_limiter
