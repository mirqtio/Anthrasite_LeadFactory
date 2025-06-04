"""
Unit tests for the rate limiting system.

Tests rate limiting functionality, configuration, violation tracking,
and cooldown mechanisms.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from leadfactory.security.rate_limiter import (
    PDFRateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitType,
    get_rate_limiter,
)


class TestRateLimitConfig:
    """Test cases for RateLimitConfig."""

    def test_default_config(self):
        """Test default rate limit configuration."""
        config = RateLimitConfig()

        assert config.per_minute > 0
        assert config.per_hour > 0
        assert config.per_day > 0
        assert config.burst_allowance >= 0
        assert config.cooldown_minutes >= 0

    def test_custom_config(self):
        """Test custom rate limit configuration."""
        config = RateLimitConfig(
            per_minute=10,
            per_hour=100,
            per_day=1000,
            burst_allowance=5,
            cooldown_minutes=30,
        )

        assert config.per_minute == 10
        assert config.per_hour == 100
        assert config.per_day == 1000
        assert config.burst_allowance == 5
        assert config.cooldown_minutes == 30


class TestRateLimiter:
    """Test cases for RateLimiter."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create rate limiter with test configurations
        self.rate_limiter = PDFRateLimiter()

        # Override with test-friendly configurations
        self.rate_limiter.configs[RateLimitType.PDF_GENERATION] = RateLimitConfig(
            per_minute=5,
            per_hour=50,
            per_day=500,
            burst_allowance=2,
            cooldown_minutes=10,
        )

        self.rate_limiter.configs[RateLimitType.PDF_ACCESS] = RateLimitConfig(
            per_minute=10,
            per_hour=100,
            per_day=1000,
            burst_allowance=5,
            cooldown_minutes=5,
        )

    def test_rate_limit_check_success(self):
        """Test successful rate limit check."""
        user_id = "test_user_1"
        operation = RateLimitType.PDF_ACCESS

        # First request should succeed
        result = self.rate_limiter.check_rate_limit(user_id, operation)

        assert result.allowed is True
        assert result.violation is None
        assert result.requests_remaining > 0

    def test_rate_limit_per_minute_exceeded(self):
        """Test rate limit exceeded for per-minute limit."""
        user_id = "test_user_2"
        operation = RateLimitType.PDF_GENERATION
        config = self.rate_limiter.configs[operation]

        # Make requests up to the limit
        for i in range(config.per_minute):
            result = self.rate_limiter.check_rate_limit(user_id, operation)
            assert result.allowed is True

        # Next request should be denied
        result = self.rate_limiter.check_rate_limit(user_id, operation)
        assert result.allowed is False
        assert result.violation is not None
        assert result.violation.limit_type == "per_minute"

    def test_burst_allowance(self):
        """Test burst allowance functionality."""
        user_id = "test_user_3"
        operation = RateLimitType.PDF_GENERATION
        config = self.rate_limiter.configs[operation]

        # Make requests up to limit + burst allowance
        total_allowed = config.per_minute + config.burst_allowance

        for i in range(total_allowed):
            result = self.rate_limiter.check_rate_limit(user_id, operation)
            assert result.allowed is True

        # Next request should be denied
        result = self.rate_limiter.check_rate_limit(user_id, operation)
        assert result.allowed is False

    def test_cooldown_enforcement(self):
        """Test cooldown period enforcement."""
        user_id = "test_user_4"
        operation = RateLimitType.PDF_GENERATION
        config = self.rate_limiter.configs[operation]

        # Exceed the rate limit to trigger cooldown
        for i in range(config.per_minute + config.burst_allowance + 1):
            self.rate_limiter.check_rate_limit(user_id, operation)

        # User should be in cooldown
        result = self.rate_limiter.check_rate_limit(user_id, operation)
        assert result.allowed is False
        assert result.violation.cooldown_until is not None

    def test_different_users_independent_limits(self):
        """Test that different users have independent rate limits."""
        user1 = "test_user_5"
        user2 = "test_user_6"
        operation = RateLimitType.PDF_ACCESS
        config = self.rate_limiter.configs[operation]

        # Exhaust rate limit for user1
        for i in range(config.per_minute + config.burst_allowance):
            result = self.rate_limiter.check_rate_limit(user1, operation)
            assert result.allowed is True

        # user1 should be rate limited
        result = self.rate_limiter.check_rate_limit(user1, operation)
        assert result.allowed is False

        # user2 should still be allowed
        result = self.rate_limiter.check_rate_limit(user2, operation)
        assert result.allowed is True

    def test_different_operations_independent_limits(self):
        """Test that different operations have independent rate limits."""
        user_id = "test_user_7"

        # Exhaust PDF generation limit
        config_gen = self.rate_limiter.configs[RateLimitType.PDF_GENERATION]
        for i in range(config_gen.per_minute + config_gen.burst_allowance):
            result = self.rate_limiter.check_rate_limit(
                user_id, RateLimitType.PDF_GENERATION
            )
            assert result.allowed is True

        # PDF generation should be rate limited
        result = self.rate_limiter.check_rate_limit(
            user_id, RateLimitType.PDF_GENERATION
        )
        assert result.allowed is False

        # PDF access should still be allowed
        result = self.rate_limiter.check_rate_limit(user_id, RateLimitType.PDF_ACCESS)
        assert result.allowed is True

    def test_get_user_stats(self):
        """Test getting user rate limit statistics."""
        user_id = "test_user_8"
        operation = RateLimitType.PDF_ACCESS

        # Make some requests
        for i in range(3):
            self.rate_limiter.check_rate_limit(user_id, operation)

        stats = self.rate_limiter.get_user_stats(user_id)

        assert user_id in stats
        assert operation.value in stats[user_id]
        assert stats[user_id][operation.value]["requests_made"] == 3

    def test_cleanup_expired_records(self):
        """Test cleanup of expired rate limit records."""
        user_id = "test_user_9"
        operation = RateLimitType.PDF_ACCESS

        # Make a request
        self.rate_limiter.check_rate_limit(user_id, operation)

        # Manually set old timestamps to simulate expiry
        if user_id in self.rate_limiter.user_requests:
            if operation.value in self.rate_limiter.user_requests[user_id]:
                old_time = datetime.utcnow() - timedelta(days=2)
                self.rate_limiter.user_requests[user_id][operation.value] = [old_time]

        # Cleanup should remove expired records
        self.rate_limiter.cleanup_expired_records()

        # Check that records are cleaned up
        stats = self.rate_limiter.get_user_stats(user_id)
        if user_id in stats and operation.value in stats[user_id]:
            assert stats[user_id][operation.value]["requests_made"] == 0

    @patch("leadfactory.security.audit_logger.get_audit_logger")
    def test_violation_logging(self, mock_get_logger):
        """Test that rate limit violations are logged."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        user_id = "test_user_10"
        operation = RateLimitType.PDF_GENERATION
        config = self.rate_limiter.configs[operation]

        # Exceed rate limit
        for i in range(config.per_minute + config.burst_allowance + 1):
            self.rate_limiter.check_rate_limit(user_id, operation)

        # Verify that violation was logged
        mock_logger.log_rate_limit_violation.assert_called()

    def test_rate_limit_reset_after_time_window(self):
        """Test that rate limits reset after the time window."""
        user_id = "test_user_11"
        operation = RateLimitType.PDF_ACCESS
        config = self.rate_limiter.configs[operation]

        # Make requests up to the limit
        for i in range(config.per_minute):
            result = self.rate_limiter.check_rate_limit(user_id, operation)
            assert result.allowed is True

        # Should be rate limited now
        result = self.rate_limiter.check_rate_limit(user_id, operation)
        assert result.allowed is False

        # Manually advance time by moving all request timestamps back
        if user_id in self.rate_limiter.user_requests:
            if operation.value in self.rate_limiter.user_requests[user_id]:
                old_time = datetime.utcnow() - timedelta(minutes=2)
                self.rate_limiter.user_requests[user_id][operation.value] = [
                    old_time
                ] * len(self.rate_limiter.user_requests[user_id][operation.value])

        # Should be allowed again after time window
        result = self.rate_limiter.check_rate_limit(user_id, operation)
        assert result.allowed is True

    def test_rate_limit_violation_details(self):
        """Test rate limit violation contains proper details."""
        user_id = "test_user_12"
        operation = RateLimitType.PDF_GENERATION
        config = self.rate_limiter.configs[operation]

        # Exceed rate limit
        for i in range(config.per_minute + config.burst_allowance + 1):
            result = self.rate_limiter.check_rate_limit(user_id, operation)

        # Last result should have violation details
        assert result.violation is not None
        assert result.violation.user_id == user_id
        assert result.violation.operation == operation.value
        assert result.violation.limit_exceeded > 0
        assert result.violation.retry_after is not None


class TestRateLimiterSingleton:
    """Test the singleton pattern for rate limiter."""

    def test_singleton_instance(self):
        """Test that get_rate_limiter returns the same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2
        assert isinstance(limiter1, PDFRateLimiter)
