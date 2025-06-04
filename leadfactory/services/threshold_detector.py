"""
Threshold Configuration and Detection System for Bounce Rate Monitoring

This module provides configurable threshold detection for bounce rates,
supporting multiple threshold levels, severity classifications, and
notification mechanisms.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# Import logging with fallback
try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class ThresholdSeverity(Enum):
    """Severity levels for threshold violations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThresholdType(Enum):
    """Types of threshold detection."""

    ABSOLUTE = "absolute"  # Fixed percentage (e.g., 5%)
    RELATIVE = "relative"  # Relative increase (e.g., 50% increase from baseline)
    VOLUME_BASED = "volume_based"  # Different thresholds based on email volume
    DOMAIN_BASED = "domain_based"  # Different thresholds based on recipient domains


@dataclass
class ThresholdRule:
    """Configuration for a single threshold rule."""

    name: str
    threshold_value: float
    severity: ThresholdSeverity
    threshold_type: ThresholdType = ThresholdType.ABSOLUTE
    minimum_sample_size: int = 100
    time_window_hours: int = 24
    enabled: bool = True
    description: str = ""

    # Volume-based thresholds
    volume_ranges: Optional[Dict[str, float]] = (
        None  # e.g., {"0-1000": 0.05, "1000-10000": 0.03}
    )

    # Domain-based thresholds
    domain_patterns: Optional[Dict[str, float]] = (
        None  # e.g., {"gmail.com": 0.02, "yahoo.com": 0.03}
    )

    # Notification settings
    notify_on_breach: bool = True
    cooldown_minutes: int = 60  # Minimum time between notifications for same IP/subuser


@dataclass
class ThresholdBreach:
    """Represents a threshold breach event."""

    ip_address: str
    subuser: str
    rule_name: str
    current_value: float
    threshold_value: float
    severity: ThresholdSeverity
    breach_time: datetime
    sample_size: int
    time_window_hours: int
    breach_id: str = field(
        default_factory=lambda: f"breach_{datetime.now().timestamp()}"
    )


@dataclass
class ThresholdConfig:
    """Complete threshold configuration."""

    rules: List[ThresholdRule] = field(default_factory=list)
    global_enabled: bool = True
    default_minimum_sample_size: int = 100
    default_time_window_hours: int = 24
    notification_cooldown_minutes: int = 60

    def add_rule(self, rule: ThresholdRule) -> None:
        """Add a threshold rule to the configuration."""
        self.rules.append(rule)

    def get_rule(self, name: str) -> Optional[ThresholdRule]:
        """Get a threshold rule by name."""
        for rule in self.rules:
            if rule.name == name:
                return rule
        return None

    def get_enabled_rules(self) -> List[ThresholdRule]:
        """Get all enabled threshold rules."""
        if not self.global_enabled:
            return []
        return [rule for rule in self.rules if rule.enabled]


class ThresholdDetector:
    """
    Threshold detection service that monitors bounce rates and detects violations.
    """

    def __init__(self, config: ThresholdConfig, bounce_monitor=None):
        """
        Initialize threshold detector.

        Args:
            config: Threshold configuration
            bounce_monitor: BounceRateMonitor instance for getting stats
        """
        self.config = config
        self.bounce_monitor = bounce_monitor
        self.breach_history: List[ThresholdBreach] = []
        self.notification_callbacks: List[Callable[[ThresholdBreach], None]] = []
        self.last_notification_times: Dict[Tuple[str, str, str], datetime] = (
            {}
        )  # (ip, subuser, rule) -> time

        logger.info(f"Threshold detector initialized with {len(config.rules)} rules")

    def add_notification_callback(
        self, callback: Callable[[ThresholdBreach], None]
    ) -> None:
        """Add a callback function to be called when thresholds are breached."""
        self.notification_callbacks.append(callback)

    def check_thresholds(self, ip_address: str, subuser: str) -> List[ThresholdBreach]:
        """
        Check all enabled threshold rules for a specific IP/subuser combination.

        Args:
            ip_address: IP address to check
            subuser: Subuser to check

        Returns:
            List of threshold breaches detected
        """
        breaches = []

        if not self.bounce_monitor:
            logger.warning("No bounce monitor configured, cannot check thresholds")
            return breaches

        # Get current stats
        stats = self.bounce_monitor.get_stats(ip_address, subuser)
        if not stats:
            logger.debug(f"No stats available for {ip_address}/{subuser}")
            return breaches

        # Check each enabled rule
        for rule in self.config.get_enabled_rules():
            breach = self._check_single_rule(rule, stats)
            if breach:
                breaches.append(breach)
                self._handle_breach(breach)

        return breaches

    def check_all_thresholds(self) -> List[ThresholdBreach]:
        """
        Check thresholds for all IP/subuser combinations.

        Returns:
            List of all threshold breaches detected
        """
        all_breaches = []

        if not self.bounce_monitor:
            logger.warning("No bounce monitor configured, cannot check thresholds")
            return all_breaches

        # Get all stats
        all_stats = self.bounce_monitor.get_all_stats()

        for stats in all_stats:
            breaches = self.check_thresholds(stats.ip_address, stats.subuser)
            all_breaches.extend(breaches)

        return all_breaches

    def _check_single_rule(
        self, rule: ThresholdRule, stats
    ) -> Optional[ThresholdBreach]:
        """
        Check a single threshold rule against IP/subuser stats.

        Args:
            rule: Threshold rule to check
            stats: IPSubuserStats object

        Returns:
            ThresholdBreach if rule is violated, None otherwise
        """
        # Check minimum sample size
        if stats.total_sent < rule.minimum_sample_size:
            logger.debug(
                f"Insufficient sample size for {stats.ip_address}/{stats.subuser}: "
                f"{stats.total_sent} < {rule.minimum_sample_size}"
            )
            return None

        # Get threshold value based on rule type
        threshold_value = self._get_threshold_value(rule, stats)
        if threshold_value is None:
            return None

        # Check if current bounce rate exceeds threshold
        current_value = stats.bounce_rate

        if rule.threshold_type == ThresholdType.RELATIVE:
            # For relative thresholds, we need a baseline (could be historical average)
            # For now, we'll use a simple implementation
            baseline = self._get_baseline_bounce_rate(stats.ip_address, stats.subuser)
            if baseline is None:
                logger.debug(
                    f"No baseline available for relative threshold check: {stats.ip_address}/{stats.subuser}"
                )
                return None

            relative_increase = (
                (current_value - baseline) / baseline if baseline > 0 else float("inf")
            )
            if relative_increase >= threshold_value:
                return ThresholdBreach(
                    ip_address=stats.ip_address,
                    subuser=stats.subuser,
                    rule_name=rule.name,
                    current_value=relative_increase,
                    threshold_value=threshold_value,
                    severity=rule.severity,
                    breach_time=datetime.now(),
                    sample_size=stats.total_sent,
                    time_window_hours=rule.time_window_hours,
                )
        else:
            # Absolute threshold check
            if current_value >= threshold_value:
                return ThresholdBreach(
                    ip_address=stats.ip_address,
                    subuser=stats.subuser,
                    rule_name=rule.name,
                    current_value=current_value,
                    threshold_value=threshold_value,
                    severity=rule.severity,
                    breach_time=datetime.now(),
                    sample_size=stats.total_sent,
                    time_window_hours=rule.time_window_hours,
                )

        return None

    def _get_threshold_value(self, rule: ThresholdRule, stats) -> Optional[float]:
        """
        Get the appropriate threshold value based on rule type and context.

        Args:
            rule: Threshold rule
            stats: IPSubuserStats object

        Returns:
            Threshold value or None if not applicable
        """
        if rule.threshold_type == ThresholdType.ABSOLUTE:
            return rule.threshold_value

        elif rule.threshold_type == ThresholdType.VOLUME_BASED:
            if not rule.volume_ranges:
                return rule.threshold_value

            # Find appropriate volume range
            volume = stats.total_sent
            for range_key, threshold in rule.volume_ranges.items():
                if "-" in range_key:
                    min_vol, max_vol = map(int, range_key.split("-"))
                    if min_vol <= volume <= max_vol:
                        return threshold
                elif range_key.endswith("+"):
                    min_vol = int(range_key[:-1])
                    if volume >= min_vol:
                        return threshold

            return rule.threshold_value  # Default fallback

        elif rule.threshold_type == ThresholdType.DOMAIN_BASED:
            if not rule.domain_patterns:
                return rule.threshold_value

            # For domain-based thresholds, we'd need to analyze the recipient domains
            # This would require additional data that's not currently tracked
            # For now, return the default threshold
            return rule.threshold_value

        elif rule.threshold_type == ThresholdType.RELATIVE:
            return rule.threshold_value

        return rule.threshold_value

    def _get_baseline_bounce_rate(
        self, ip_address: str, subuser: str
    ) -> Optional[float]:
        """
        Get baseline bounce rate for relative threshold calculations.

        This could be implemented as:
        - Historical average over a longer period
        - Industry benchmark
        - Account-specific baseline

        For now, returns a simple default baseline.
        """
        # TODO: Implement proper baseline calculation
        return 0.02  # 2% baseline

    def _handle_breach(self, breach: ThresholdBreach) -> None:
        """
        Handle a threshold breach by logging and notifying.

        Args:
            breach: ThresholdBreach object
        """
        # Add to breach history
        self.breach_history.append(breach)

        # Log the breach
        logger.warning(
            f"Threshold breach detected: {breach.rule_name} for {breach.ip_address}/{breach.subuser} "
            f"(current: {breach.current_value:.4f}, threshold: {breach.threshold_value:.4f}, "
            f"severity: {breach.severity.value})"
        )

        # Check notification cooldown
        notification_key = (breach.ip_address, breach.subuser, breach.rule_name)
        last_notification = self.last_notification_times.get(notification_key)

        if last_notification:
            rule = self.config.get_rule(breach.rule_name)
            cooldown_minutes = (
                rule.cooldown_minutes
                if rule
                else self.config.notification_cooldown_minutes
            )

            if datetime.now() - last_notification < timedelta(minutes=cooldown_minutes):
                logger.debug(f"Notification cooldown active for {notification_key}")
                return

        # Send notifications
        for callback in self.notification_callbacks:
            try:
                callback(breach)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")

        # Update last notification time
        self.last_notification_times[notification_key] = datetime.now()

    def get_breach_history(
        self,
        ip_address: Optional[str] = None,
        subuser: Optional[str] = None,
        severity: Optional[ThresholdSeverity] = None,
        hours_back: Optional[int] = None,
    ) -> List[ThresholdBreach]:
        """
        Get breach history with optional filtering.

        Args:
            ip_address: Filter by IP address
            subuser: Filter by subuser
            severity: Filter by severity level
            hours_back: Only return breaches from last N hours

        Returns:
            Filtered list of threshold breaches
        """
        filtered_breaches = self.breach_history.copy()

        if ip_address:
            filtered_breaches = [
                b for b in filtered_breaches if b.ip_address == ip_address
            ]

        if subuser:
            filtered_breaches = [b for b in filtered_breaches if b.subuser == subuser]

        if severity:
            filtered_breaches = [b for b in filtered_breaches if b.severity == severity]

        if hours_back:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            filtered_breaches = [
                b for b in filtered_breaches if b.breach_time >= cutoff_time
            ]

        return filtered_breaches

    def get_current_violations(self) -> List[ThresholdBreach]:
        """
        Get current threshold violations (recent breaches that may still be active).

        Returns:
            List of recent threshold breaches
        """
        # Return breaches from the last hour as "current"
        return self.get_breach_history(hours_back=1)

    def clear_breach_history(self, hours_back: Optional[int] = None) -> int:
        """
        Clear breach history, optionally keeping recent entries.

        Args:
            hours_back: If specified, only clear entries older than N hours

        Returns:
            Number of entries cleared
        """
        if hours_back is None:
            count = len(self.breach_history)
            self.breach_history.clear()
            return count

        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        original_count = len(self.breach_history)
        self.breach_history = [
            b for b in self.breach_history if b.breach_time >= cutoff_time
        ]
        cleared_count = original_count - len(self.breach_history)

        logger.info(
            f"Cleared {cleared_count} breach history entries older than {hours_back} hours"
        )
        return cleared_count


def create_default_threshold_config() -> ThresholdConfig:
    """
    Create a default threshold configuration with common rules.

    Returns:
        ThresholdConfig with default rules
    """
    config = ThresholdConfig()

    # Low severity - warning level (2% for Task 21 requirements)
    config.add_rule(
        ThresholdRule(
            name="warning_threshold",
            threshold_value=0.02,  # 2% - Task 21 requirement
            severity=ThresholdSeverity.LOW,
            threshold_type=ThresholdType.ABSOLUTE,
            minimum_sample_size=10,  # Lower for testing
            time_window_hours=24,
            description="2% bounce rate threshold as per Task 21",
        )
    )

    # Medium severity - action required
    config.add_rule(
        ThresholdRule(
            name="action_threshold",
            threshold_value=0.08,  # 8%
            severity=ThresholdSeverity.MEDIUM,
            threshold_type=ThresholdType.ABSOLUTE,
            minimum_sample_size=100,
            time_window_hours=24,
            description="Action required bounce rate threshold",
        )
    )

    # High severity - immediate rotation
    config.add_rule(
        ThresholdRule(
            name="rotation_threshold",
            threshold_value=0.12,  # 12%
            severity=ThresholdSeverity.HIGH,
            threshold_type=ThresholdType.ABSOLUTE,
            minimum_sample_size=100,
            time_window_hours=12,
            description="Immediate rotation required threshold",
        )
    )

    # Critical severity - emergency stop
    config.add_rule(
        ThresholdRule(
            name="emergency_threshold",
            threshold_value=0.20,  # 20%
            severity=ThresholdSeverity.CRITICAL,
            threshold_type=ThresholdType.ABSOLUTE,
            minimum_sample_size=50,
            time_window_hours=6,
            description="Emergency stop threshold",
        )
    )

    # Volume-based threshold example
    config.add_rule(
        ThresholdRule(
            name="volume_based_threshold",
            threshold_value=0.05,  # Default 5%
            severity=ThresholdSeverity.MEDIUM,
            threshold_type=ThresholdType.VOLUME_BASED,
            volume_ranges={
                "0-1000": 0.08,  # Higher threshold for low volume
                "1000-10000": 0.05,  # Standard threshold
                "10000+": 0.03,  # Lower threshold for high volume
            },
            description="Volume-based bounce rate threshold",
        )
    )

    return config


# Example notification callbacks
def log_notification_callback(breach: ThresholdBreach) -> None:
    """Simple logging notification callback."""
    logger.error(
        f"THRESHOLD BREACH: {breach.severity.value.upper()} - "
        f"{breach.ip_address}/{breach.subuser} exceeded {breach.rule_name} "
        f"({breach.current_value:.2%} > {breach.threshold_value:.2%})"
    )


def email_notification_callback(breach: ThresholdBreach) -> None:
    """Email notification callback (placeholder implementation)."""
    # TODO: Implement actual email notification
    logger.info(f"Would send email notification for breach: {breach.breach_id}")


def webhook_notification_callback(breach: ThresholdBreach) -> None:
    """Webhook notification callback (placeholder implementation)."""
    # TODO: Implement actual webhook notification
    logger.info(f"Would send webhook notification for breach: {breach.breach_id}")
