"""
IP/Subuser Rotation Logic for Bounce Threshold Management

This module implements the core rotation logic to automatically switch traffic
to alternative IPs/subusers when bounce thresholds are exceeded.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Import logging with fallback
try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

# Import alerting system
try:
    from leadfactory.services.ip_rotation_alerting import (
        AlertSeverity,
        AlertType,
        IPRotationAlerting,
    )
except ImportError:
    logger.warning("IP rotation alerting not available")
    AlertSeverity = None
    AlertType = None
    IPRotationAlerting = None


class RotationReason(Enum):
    """Reasons for IP/subuser rotation."""

    THRESHOLD_BREACH = "threshold_breach"
    MANUAL_ROTATION = "manual_rotation"
    SCHEDULED_ROTATION = "scheduled_rotation"
    PERFORMANCE_DEGRADATION = "performance_degradation"


class IPSubuserStatus(Enum):
    """Status of an IP/subuser combination."""

    ACTIVE = "active"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


@dataclass
class IPSubuserPool:
    """Represents an IP/subuser combination in the rotation pool."""

    ip_address: str
    subuser: str
    status: IPSubuserStatus = IPSubuserStatus.ACTIVE
    priority: int = 1  # Higher number = higher priority
    last_used: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    total_sent: int = 0
    total_bounced: int = 0
    performance_score: float = 1.0  # 0.0 to 1.0, higher is better
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """Check if this IP/subuser is available for use."""
        if self.status != IPSubuserStatus.ACTIVE:
            return False

        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False

        return True

    def calculate_performance_score(self) -> float:
        """Calculate performance score based on bounce rate and other factors."""
        if self.total_sent == 0:
            return 1.0  # New IP/subuser gets benefit of the doubt

        bounce_rate = self.total_bounced / self.total_sent
        base_score = max(0.0, 1.0 - bounce_rate)

        # Apply priority boost
        priority_boost = min(0.2, self.priority * 0.05)

        # Apply recency penalty (prefer recently used IPs less)
        recency_penalty = 0.0
        if self.last_used:
            hours_since_use = (datetime.now() - self.last_used).total_seconds() / 3600
            if hours_since_use < 1:
                recency_penalty = 0.1  # Small penalty for very recent use

        self.performance_score = min(1.0, base_score + priority_boost - recency_penalty)
        return self.performance_score


@dataclass
class RotationEvent:
    """Represents a rotation event."""

    from_ip: str
    from_subuser: str
    to_ip: str
    to_subuser: str
    reason: RotationReason
    timestamp: datetime = field(default_factory=datetime.now)
    breach_details: Optional[Dict[str, Any]] = None
    success: bool = False
    error_message: Optional[str] = None
    event_id: str = field(default_factory=lambda: f"rotation_{int(time.time())}")


@dataclass
class RotationConfig:
    """Configuration for IP/subuser rotation."""

    default_cooldown_hours: int = 4
    max_rotations_per_hour: int = 10
    fallback_enabled: bool = True
    require_minimum_alternatives: int = 2
    performance_weight: float = 0.7  # Weight for performance vs priority
    enable_automatic_rotation: bool = True
    rotation_delay_seconds: int = 30  # Delay before executing rotation
    max_consecutive_failures: int = 3


class IPRotationService:
    """
    Service for managing IP/subuser rotation based on bounce thresholds.

    This service maintains a pool of available IPs/subusers and automatically
    rotates traffic when thresholds are exceeded.
    """

    def __init__(
        self,
        config: RotationConfig,
        bounce_monitor=None,
        threshold_detector=None,
        alerting_service: IPRotationAlerting = None,
    ):
        """
        Initialize the IP rotation service.

        Args:
            config: Rotation configuration
            bounce_monitor: BounceRateMonitor instance
            threshold_detector: ThresholdDetector instance
            alerting_service: IPRotationAlerting instance
        """
        self.config = config
        self.bounce_monitor = bounce_monitor
        self.threshold_detector = threshold_detector
        self.ip_pool: List[IPSubuserPool] = []
        self.rotation_history: List[RotationEvent] = []
        self.active_rotations: Dict[Tuple[str, str], datetime] = (
            {}
        )  # Track ongoing rotations
        self.consecutive_failures: Dict[Tuple[str, str], int] = {}
        self.alerting_service = alerting_service

        logger.info("IP rotation service initialized")

    def add_ip_subuser(
        self,
        ip_address: str,
        subuser: str,
        priority: int = 1,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Add an IP/subuser combination to the rotation pool.

        Args:
            ip_address: IP address
            subuser: Subuser identifier
            priority: Priority level (higher = more preferred)
            tags: Optional tags for categorization
            metadata: Optional metadata
        """
        # Check if already exists
        existing = self.get_ip_subuser_pool(ip_address, subuser)
        if existing:
            logger.warning(f"IP/subuser {ip_address}/{subuser} already exists in pool")
            return

        pool_entry = IPSubuserPool(
            ip_address=ip_address,
            subuser=subuser,
            priority=priority,
            tags=tags or [],
            metadata=metadata or {},
        )

        self.ip_pool.append(pool_entry)
        logger.info(
            f"Added IP/subuser {ip_address}/{subuser} to rotation pool with priority {priority}"
        )

    def remove_ip_subuser(self, ip_address: str, subuser: str) -> bool:
        """
        Remove an IP/subuser combination from the rotation pool.

        Args:
            ip_address: IP address
            subuser: Subuser identifier

        Returns:
            True if removed, False if not found
        """
        for i, pool_entry in enumerate(self.ip_pool):
            if pool_entry.ip_address == ip_address and pool_entry.subuser == subuser:
                del self.ip_pool[i]
                logger.info(
                    f"Removed IP/subuser {ip_address}/{subuser} from rotation pool"
                )
                return True

        logger.warning(f"IP/subuser {ip_address}/{subuser} not found in pool")
        return False

    def get_ip_subuser_pool(
        self, ip_address: str, subuser: str
    ) -> Optional[IPSubuserPool]:
        """Get pool entry for specific IP/subuser combination."""
        for pool_entry in self.ip_pool:
            if pool_entry.ip_address == ip_address and pool_entry.subuser == subuser:
                return pool_entry
        return None

    def update_performance_metrics(self) -> None:
        """Update performance metrics for all IP/subuser combinations."""
        if not self.bounce_monitor:
            logger.warning("No bounce monitor available for performance updates")
            return

        for pool_entry in self.ip_pool:
            try:
                stats = self.bounce_monitor.get_ip_subuser_stats(
                    pool_entry.ip_address, pool_entry.subuser
                )
                if stats:
                    pool_entry.total_sent = stats.total_sent
                    pool_entry.total_bounced = stats.total_bounced
                    pool_entry.calculate_performance_score()

                    logger.debug(
                        f"Updated metrics for {pool_entry.ip_address}/{pool_entry.subuser}: "
                        f"score={pool_entry.performance_score:.3f}"
                    )
            except Exception as e:
                logger.error(
                    f"Error updating metrics for {pool_entry.ip_address}/{pool_entry.subuser}: {e}"
                )

    def get_available_alternatives(
        self,
        exclude_ip: str = None,
        exclude_subuser: str = None,
        min_performance_score: float = 0.0,
    ) -> List[IPSubuserPool]:
        """
        Get available IP/subuser alternatives for rotation.

        Args:
            exclude_ip: IP to exclude from results
            exclude_subuser: Subuser to exclude from results
            min_performance_score: Minimum performance score required

        Returns:
            List of available IP/subuser combinations sorted by preference
        """
        available = []

        for pool_entry in self.ip_pool:
            # Skip if not available
            if not pool_entry.is_available():
                continue

            # Skip if excluded
            if (
                exclude_ip
                and pool_entry.ip_address == exclude_ip
                and exclude_subuser
                and pool_entry.subuser == exclude_subuser
            ):
                continue

            # Skip if performance too low
            if pool_entry.performance_score < min_performance_score:
                continue

            available.append(pool_entry)

        # Sort by combined score (performance + priority)
        def sort_key(entry):
            performance_weight = self.config.performance_weight
            priority_weight = 1.0 - performance_weight

            # Normalize priority (assume max priority is 10)
            normalized_priority = min(1.0, entry.priority / 10.0)

            combined_score = (
                performance_weight * entry.performance_score
                + priority_weight * normalized_priority
            )

            return combined_score

        available.sort(key=sort_key, reverse=True)

        logger.debug(f"Found {len(available)} available alternatives")
        return available

    def select_best_alternative(
        self, current_ip: str, current_subuser: str
    ) -> Optional[IPSubuserPool]:
        """
        Select the best alternative IP/subuser for rotation.

        Args:
            current_ip: Current IP address
            current_subuser: Current subuser

        Returns:
            Best alternative or None if no suitable alternative found
        """
        alternatives = self.get_available_alternatives(
            exclude_ip=current_ip, exclude_subuser=current_subuser
        )

        if not alternatives:
            logger.warning(
                f"No alternatives available for {current_ip}/{current_subuser}"
            )
            return None

        if len(alternatives) < self.config.require_minimum_alternatives:
            logger.warning(
                f"Only {len(alternatives)} alternatives available, "
                f"minimum required: {self.config.require_minimum_alternatives}"
            )
            if not self.config.fallback_enabled:
                return None

        best_alternative = alternatives[0]
        logger.info(
            f"Selected best alternative: {best_alternative.ip_address}/{best_alternative.subuser} "
            f"(score: {best_alternative.performance_score:.3f})"
        )

        return best_alternative

    def execute_rotation(
        self,
        from_ip: str,
        from_subuser: str,
        to_ip: str,
        to_subuser: str,
        reason: RotationReason,
        breach_details: Dict[str, Any] = None,
    ) -> RotationEvent:
        """
        Execute a rotation from one IP/subuser to another.

        Args:
            from_ip: Source IP address
            from_subuser: Source subuser
            to_ip: Target IP address
            to_subuser: Target subuser
            reason: Reason for rotation
            breach_details: Optional breach details

        Returns:
            RotationEvent with execution results
        """
        rotation_event = RotationEvent(
            from_ip=from_ip,
            from_subuser=from_subuser,
            to_ip=to_ip,
            to_subuser=to_subuser,
            reason=reason,
            breach_details=breach_details,
        )

        try:
            # Check rate limiting
            if not self._check_rotation_rate_limit():
                raise Exception("Rotation rate limit exceeded")

            # Check if source IP/subuser is in cooldown
            from_entry = self.get_ip_subuser_pool(from_ip, from_subuser)
            if from_entry and from_entry.status == IPSubuserStatus.COOLDOWN:
                error_msg = f"Source IP/subuser {from_ip}/{from_subuser} is in cooldown until {from_entry.cooldown_until}"
                logger.warning(error_msg)
                if self.alerting_service:
                    self.alerting_service.record_system_error(
                        error_msg,
                        {
                            "source_ip": from_ip,
                            "source_subuser": from_subuser,
                            "cooldown_until": str(from_entry.cooldown_until),
                        },
                    )
                raise ValueError(error_msg)

            # Check if target IP/subuser is available
            to_entry = self.get_ip_subuser_pool(to_ip, to_subuser)
            if to_entry and not to_entry.is_available():
                raise Exception(
                    f"Target IP/subuser {to_ip}/{to_subuser} is not available (status: {to_entry.status}, cooldown: {to_entry.cooldown_until})"
                )

            # Mark rotation as in progress
            rotation_key = (from_ip, from_subuser)
            self.active_rotations[rotation_key] = datetime.now()

            # Add delay if configured
            if self.config.rotation_delay_seconds > 0:
                logger.info(
                    f"Waiting {self.config.rotation_delay_seconds} seconds before rotation"
                )
                time.sleep(self.config.rotation_delay_seconds)

            # Check if target is available (not in cooldown)
            target_entry = None
            for pool_entry in self.ip_pool:
                if pool_entry.ip_address == to_ip and pool_entry.subuser == to_subuser:
                    target_entry = pool_entry
                    break

            if target_entry and target_entry.status == IPSubuserStatus.COOLDOWN:
                error_msg = f"Target IP/subuser {to_ip}/{to_subuser} is in cooldown until {target_entry.cooldown_until}"
                logger.warning(error_msg)
                if self.alerting_service:
                    self.alerting_service.record_system_error(
                        error_msg,
                        {
                            "target_ip": to_ip,
                            "target_subuser": to_subuser,
                            "cooldown_until": str(target_entry.cooldown_until),
                        },
                    )
                raise ValueError(error_msg)

            logger.info(
                f"Executing rotation: {from_ip}/{from_subuser} -> {to_ip}/{to_subuser} "
                f"(reason: {reason.value})"
            )

            # Record the rotation event
            rotation_event = RotationEvent(
                timestamp=datetime.now(),
                from_ip=from_ip,
                from_subuser=from_subuser,
                to_ip=to_ip,
                to_subuser=to_subuser,
                reason=reason,
                success=True,
            )

            self.rotation_history.append(rotation_event)

            # Update last used timestamp for target
            for pool_entry in self.ip_pool:
                if pool_entry.ip_address == to_ip and pool_entry.subuser == to_subuser:
                    pool_entry.last_used = datetime.now()
                    break

            # Apply cooldown to source IP/subuser
            self._apply_cooldown(from_ip, from_subuser)

            # Track the rotation
            self.active_rotations[(from_ip, from_subuser)] = datetime.now()

            # Record successful rotation in alerting system
            if self.alerting_service:
                self.alerting_service.record_rotation(
                    f"{from_ip}/{from_subuser}", f"{to_ip}/{to_subuser}", reason.value
                )

            rotation_event.success = True
            logger.info(
                f"Successfully rotated from {from_ip}/{from_subuser} to {to_ip}/{to_subuser}"
            )

            # Reset consecutive failures
            self.consecutive_failures.pop(rotation_key, None)

        except ValueError as e:
            # Re-raise ValueError for cooldown violations and other validation errors
            rotation_event.success = False
            rotation_event.error_message = str(e)
            logger.error(f"Failed to execute rotation: {e}")

            # Track consecutive failures
            rotation_key = (from_ip, from_subuser)
            self.consecutive_failures[rotation_key] = (
                self.consecutive_failures.get(rotation_key, 0) + 1
            )

            # Record error in alerting system
            if self.alerting_service:
                self.alerting_service.record_system_error(
                    f"Rotation failed: {from_ip}/{from_subuser} -> {to_ip}/{to_subuser}: {str(e)}",
                    {
                        "from_ip": from_ip,
                        "from_subuser": from_subuser,
                        "to_ip": to_ip,
                        "to_subuser": to_subuser,
                        "reason": reason.value,
                        "error": str(e),
                    },
                )

            # Remove from active rotations before re-raising
            rotation_key = (from_ip, from_subuser)
            self.active_rotations.pop(rotation_key, None)

            raise e  # Re-raise the ValueError

        except Exception as e:
            rotation_event.success = False
            rotation_event.error_message = str(e)
            logger.error(f"Failed to execute rotation: {e}")

            # Track consecutive failures
            rotation_key = (from_ip, from_subuser)
            self.consecutive_failures[rotation_key] = (
                self.consecutive_failures.get(rotation_key, 0) + 1
            )

            # Record error in alerting system
            if self.alerting_service:
                self.alerting_service.record_system_error(
                    f"Rotation failed: {from_ip}/{from_subuser} -> {to_ip}/{to_subuser}: {str(e)}",
                    {
                        "from_ip": from_ip,
                        "from_subuser": from_subuser,
                        "to_ip": to_ip,
                        "to_subuser": to_subuser,
                        "reason": reason.value,
                        "error": str(e),
                    },
                )

        finally:
            # Remove from active rotations
            rotation_key = (from_ip, from_subuser)
            self.active_rotations.pop(rotation_key, None)

        return rotation_event

    def handle_threshold_breach(self, breach) -> Optional[RotationEvent]:
        """
        Handle a threshold breach by executing rotation if appropriate.

        Args:
            breach: ThresholdBreach object

        Returns:
            RotationEvent if rotation was executed, None otherwise
        """
        if not self.config.enable_automatic_rotation:
            logger.info("Automatic rotation disabled, skipping breach handling")
            return None

        current_ip = breach.ip_address
        current_subuser = breach.subuser

        # Record threshold breach in alerting system
        if self.alerting_service:
            self.alerting_service.record_threshold_breach(
                current_ip, breach.threshold_value, breach.current_value
            )

        # Check if already rotating
        rotation_key = (current_ip, current_subuser)
        if rotation_key in self.active_rotations:
            logger.info(
                f"Rotation already in progress for {current_ip}/{current_subuser}"
            )
            return None

        # Check consecutive failures
        failures = self.consecutive_failures.get(rotation_key, 0)
        if failures >= self.config.max_consecutive_failures:
            logger.warning(
                f"Max consecutive failures reached for {current_ip}/{current_subuser}, "
                f"disabling automatic rotation"
            )
            pool_entry = self.get_ip_subuser_pool(current_ip, current_subuser)
            if pool_entry:
                pool_entry.status = IPSubuserStatus.DISABLED

                # Record IP disabling in alerting system
                if self.alerting_service:
                    self.alerting_service.record_ip_disabled(
                        current_ip, f"Max consecutive failures reached ({failures})"
                    )
            return None

        # Find best alternative
        alternative = self.select_best_alternative(current_ip, current_subuser)
        if not alternative:
            logger.warning(
                f"No suitable alternative found for {current_ip}/{current_subuser}"
            )
            # Increment consecutive failures
            self.consecutive_failures[rotation_key] = (
                self.consecutive_failures.get(rotation_key, 0) + 1
            )
            return None

        # Execute rotation
        breach_details = {
            "rule_name": breach.rule_name,
            "current_value": breach.current_value,
            "threshold_value": breach.threshold_value,
            "severity": breach.severity.value,
            "breach_id": breach.breach_id,
        }

        return self.execute_rotation(
            from_ip=current_ip,
            from_subuser=current_subuser,
            to_ip=alternative.ip_address,
            to_subuser=alternative.subuser,
            reason=RotationReason.THRESHOLD_BREACH,
            breach_details=breach_details,
        )

    def _check_rotation_rate_limit(self) -> bool:
        """Check if rotation rate limit is exceeded."""
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_rotations = [
            event
            for event in self.rotation_history
            if event.timestamp > cutoff_time and event.success
        ]

        return len(recent_rotations) < self.config.max_rotations_per_hour

    def get_rotation_history(self, hours_back: int = 24) -> List[RotationEvent]:
        """Get rotation history for the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        return [
            event for event in self.rotation_history if event.timestamp > cutoff_time
        ]

    def get_pool_status(self) -> Dict[str, Any]:
        """Get current status of the IP/subuser pool."""
        total_count = len(self.ip_pool)
        active_count = len(
            [p for p in self.ip_pool if p.status == IPSubuserStatus.ACTIVE]
        )
        cooldown_count = len(
            [p for p in self.ip_pool if p.status == IPSubuserStatus.COOLDOWN]
        )
        disabled_count = len(
            [p for p in self.ip_pool if p.status == IPSubuserStatus.DISABLED]
        )

        available_count = len([p for p in self.ip_pool if p.is_available()])

        return {
            "total_count": total_count,
            "active_count": active_count,
            "cooldown_count": cooldown_count,
            "disabled_count": disabled_count,
            "available_count": available_count,
            "active_rotations": len(self.active_rotations),
            "recent_rotations": len(self.get_rotation_history(hours_back=1)),
        }

    def cleanup_old_history(self, days_to_keep: int = 7) -> int:
        """Clean up old rotation history."""
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        original_count = len(self.rotation_history)

        self.rotation_history = [
            event for event in self.rotation_history if event.timestamp > cutoff_time
        ]

        removed_count = original_count - len(self.rotation_history)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old rotation events")

        return removed_count

    def _apply_cooldown(self, ip_address: str, subuser: str) -> None:
        """Apply cooldown to an IP/subuser combination."""
        for pool_entry in self.ip_pool:
            if pool_entry.ip_address == ip_address and pool_entry.subuser == subuser:
                pool_entry.status = IPSubuserStatus.COOLDOWN
                pool_entry.cooldown_until = datetime.now() + timedelta(
                    hours=self.config.default_cooldown_hours
                )
                logger.info(
                    f"Applied cooldown to {ip_address}/{subuser} until {pool_entry.cooldown_until}"
                )
                break


def create_default_rotation_config() -> RotationConfig:
    """Create a default rotation configuration."""
    return RotationConfig(
        default_cooldown_hours=4,
        max_rotations_per_hour=10,
        fallback_enabled=True,
        require_minimum_alternatives=2,
        performance_weight=0.7,
        enable_automatic_rotation=True,
        rotation_delay_seconds=30,
        max_consecutive_failures=3,
    )
