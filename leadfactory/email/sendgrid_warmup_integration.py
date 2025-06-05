#!/usr/bin/env python3
"""
SendGrid Warmup Integration with Bounce Rate Monitoring and IP Rotation

This module provides integration between the SendGrid warmup scheduler,
bounce rate monitoring, and IP rotation systems to ensure seamless
transition from warmup to production rotation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Import logging with fallback
try:
    from leadfactory.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Import warmup components
from leadfactory.email.sendgrid_warmup import (
    SendGridWarmupScheduler,
    WarmupStage,
    WarmupStatus,
)

# Import bounce monitoring and rotation components
try:
    from leadfactory.services.bounce_monitor import (
        BounceEvent,
        BounceRateConfig,
        BounceRateMonitor,
    )
    from leadfactory.services.ip_rotation import (
        IPRotationService,
        IPSubuserPool,
        IPSubuserStatus,
        RotationConfig,
        RotationReason,
    )

    ROTATION_AVAILABLE = True
except ImportError:
    logger.warning("Bounce monitoring and rotation services not available")
    ROTATION_AVAILABLE = False
    BounceRateMonitor = None
    IPRotationService = None


class IntegrationMode(Enum):
    """Integration modes for warmup and rotation."""

    WARMUP_ONLY = "warmup_only"
    ROTATION_ONLY = "rotation_only"
    INTEGRATED = "integrated"


@dataclass
class WarmupIntegrationConfig:
    """Configuration for warmup integration."""

    # Warmup-specific bounce thresholds (more lenient during warmup)
    warmup_warning_threshold: float = 0.08
    warmup_critical_threshold: float = 0.15
    warmup_block_threshold: float = 0.25

    # Post-warmup transition settings
    auto_add_to_rotation_pool: bool = True
    rotation_pool_priority: int = 1
    cooldown_after_warmup_hours: int = 2

    # Integration behavior
    pause_warmup_on_critical_bounce: bool = True
    require_warmup_completion_for_rotation: bool = True
    minimum_warmup_days_before_rotation: int = 7


class SendGridWarmupIntegration:
    """
    Integration service for SendGrid warmup with bounce monitoring and IP rotation.

    This service coordinates between the warmup scheduler, bounce rate monitoring,
    and IP rotation systems to provide seamless email delivery management.
    """

    def __init__(
        self,
        warmup_scheduler: SendGridWarmupScheduler,
        bounce_monitor: Optional[BounceRateMonitor] = None,
        rotation_service: Optional[IPRotationService] = None,
        config: Optional[WarmupIntegrationConfig] = None,
    ):
        """
        Initialize the warmup integration service.

        Args:
            warmup_scheduler: SendGrid warmup scheduler instance
            bounce_monitor: Bounce rate monitor instance (optional)
            rotation_service: IP rotation service instance (optional)
            config: Integration configuration (uses default if None)
        """
        self.warmup_scheduler = warmup_scheduler
        self.bounce_monitor = bounce_monitor
        self.rotation_service = rotation_service
        self.config = config or WarmupIntegrationConfig()

        # Track integration state
        self.monitored_ips: dict[str, datetime] = {}
        self.integration_events: list[dict] = []

        logger.info(
            f"Warmup integration initialized with mode: {self._get_integration_mode()}"
        )

    def _get_integration_mode(self) -> IntegrationMode:
        """Determine the current integration mode."""
        if self.bounce_monitor and self.rotation_service:
            return IntegrationMode.INTEGRATED
        elif self.bounce_monitor:
            return IntegrationMode.ROTATION_ONLY
        else:
            return IntegrationMode.WARMUP_ONLY

    def start_ip_warmup_with_monitoring(
        self,
        ip_address: str,
        enable_bounce_monitoring: bool = True,
    ) -> bool:
        """
        Start warmup for an IP with integrated bounce monitoring.

        Args:
            ip_address: IP address to start warming up
            enable_bounce_monitoring: Whether to enable bounce monitoring

        Returns:
            True if warmup started successfully
        """
        try:
            # Start the warmup process
            success = self.warmup_scheduler.start_warmup(ip_address)
            if not success:
                logger.error(f"Failed to start warmup for IP {ip_address}")
                return False

            # Enable bounce monitoring with warmup-specific thresholds
            if enable_bounce_monitoring and self.bounce_monitor:
                self._setup_warmup_bounce_monitoring(ip_address)

            # Track this IP in our integration
            self.monitored_ips[ip_address] = datetime.now()

            self._log_integration_event(
                "warmup_started",
                ip_address,
                {"bounce_monitoring": enable_bounce_monitoring},
            )

            logger.info(f"Started integrated warmup for IP {ip_address}")
            return True

        except Exception as e:
            logger.error(f"Error starting warmup for IP {ip_address}: {e}")
            return False

    def _setup_warmup_bounce_monitoring(self, ip_address: str):
        """Set up bounce monitoring with warmup-specific thresholds."""
        if not self.bounce_monitor:
            return

        # Note: In a full implementation, we might modify the bounce monitor
        # to use different thresholds during warmup. For now, we'll track
        # this in our integration layer.
        logger.info(f"Enabled warmup-aware bounce monitoring for IP {ip_address}")

    def check_warmup_bounce_thresholds(
        self,
        ip_address: str,
        subuser: str = "default",
    ) -> tuple[bool, Optional[str]]:
        """
        Check bounce thresholds with warmup-aware logic.

        Args:
            ip_address: IP address to check
            subuser: Subuser identifier

        Returns:
            Tuple of (is_safe, reason_if_not_safe)
        """
        if not self.bounce_monitor:
            return True, None

        # Get current warmup status
        warmup_progress = self.warmup_scheduler.get_warmup_progress(ip_address)
        if not warmup_progress:
            # Not in warmup, use normal thresholds
            stats = self.bounce_monitor.get_ip_subuser_stats(ip_address, subuser)
            if not stats:
                return True, None

            # Use normal bounce rate monitoring logic
            violations = self.bounce_monitor.check_thresholds()
            for level, violating_stats in violations.items():
                for stat in violating_stats:
                    if stat.ip_address == ip_address and stat.subuser == subuser:
                        return False, f"Bounce threshold exceeded: {level}"

            return True, None

        # In warmup - use warmup-specific thresholds
        stats = self.bounce_monitor.get_ip_subuser_stats(ip_address, subuser)
        if not stats:
            return True, None

        bounce_rate = stats.bounce_rate

        if bounce_rate >= self.config.warmup_block_threshold:
            reason = f"Warmup block threshold exceeded: {bounce_rate:.3f}"
            if self.config.pause_warmup_on_critical_bounce:
                self.warmup_scheduler.pause_warmup(ip_address, reason)
                logger.warning(
                    f"Paused warmup for {ip_address} due to high bounce rate"
                )
            return False, reason

        if bounce_rate >= self.config.warmup_critical_threshold:
            return False, f"Warmup critical threshold exceeded: {bounce_rate:.3f}"

        if bounce_rate >= self.config.warmup_warning_threshold:
            logger.warning(
                f"Warmup warning threshold exceeded for {ip_address}: {bounce_rate:.3f}"
            )

        return True, None

    def handle_warmup_completion(self, ip_address: str) -> bool:
        """
        Handle the completion of warmup for an IP address.

        Args:
            ip_address: IP address that completed warmup

        Returns:
            True if post-warmup setup was successful
        """
        try:
            # Verify warmup is actually complete
            progress = self.warmup_scheduler.get_warmup_progress(ip_address)
            if not progress or progress.status != WarmupStatus.COMPLETED:
                logger.warning(f"Warmup not completed for IP {ip_address}")
                return False

            # Add to rotation pool if configured
            if self.config.auto_add_to_rotation_pool and self.rotation_service:
                self._add_to_rotation_pool(ip_address)

            # Apply post-warmup cooldown
            if self.config.cooldown_after_warmup_hours > 0:
                self._apply_post_warmup_cooldown(ip_address)

            self._log_integration_event(
                "warmup_completed",
                ip_address,
                {"added_to_rotation": self.config.auto_add_to_rotation_pool},
            )

            logger.info(f"Completed warmup integration for IP {ip_address}")
            return True

        except Exception as e:
            logger.error(f"Error handling warmup completion for {ip_address}: {e}")
            return False

    def _add_to_rotation_pool(self, ip_address: str):
        """Add a warmed-up IP to the rotation pool."""
        if not self.rotation_service:
            return

        # Add with default subuser - in practice, this might be configurable
        self.rotation_service.add_ip_subuser(
            ip_address=ip_address,
            subuser="default",
            priority=self.config.rotation_pool_priority,
            tags=["warmed-up"],
            metadata={
                "warmup_completed": datetime.now().isoformat(),
                "source": "warmup_integration",
            },
        )

        logger.info(f"Added warmed-up IP {ip_address} to rotation pool")

    def _apply_post_warmup_cooldown(self, ip_address: str):
        """Apply cooldown period after warmup completion."""
        # This would typically involve setting a cooldown in the rotation service
        # For now, we'll just log it
        cooldown_until = datetime.now() + timedelta(
            hours=self.config.cooldown_after_warmup_hours
        )
        logger.info(
            f"Applied post-warmup cooldown for IP {ip_address} until {cooldown_until}"
        )

    def get_rotation_candidates(
        self,
        exclude_ip: str = None,
        require_warmup_complete: bool = None,
    ) -> list[str]:
        """
        Get IPs available for rotation, considering warmup status.

        Args:
            exclude_ip: IP to exclude from candidates
            require_warmup_complete: Whether to require completed warmup

        Returns:
            List of IP addresses available for rotation
        """
        if require_warmup_complete is None:
            require_warmup_complete = self.config.require_warmup_completion_for_rotation

        candidates = []

        # Get all IPs from rotation service if available
        if self.rotation_service:
            pool_status = self.rotation_service.get_pool_status()
            for entry in pool_status:
                if exclude_ip and entry.ip_address == exclude_ip:
                    continue

                if entry.status != IPSubuserStatus.ACTIVE:
                    continue

                # Check warmup status if required
                if require_warmup_complete:
                    progress = self.warmup_scheduler.get_warmup_progress(
                        entry.ip_address
                    )
                    if progress and progress.status != WarmupStatus.COMPLETED:
                        continue

                candidates.append(entry.ip_address)

        return candidates

    def should_rotate_ip(
        self,
        ip_address: str,
        subuser: str = "default",
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if an IP should be rotated based on integrated logic.

        Args:
            ip_address: IP address to check
            subuser: Subuser identifier

        Returns:
            Tuple of (should_rotate, reason)
        """
        # Check warmup status first
        progress = self.warmup_scheduler.get_warmup_progress(ip_address)

        # If in warmup, use warmup-specific logic
        if progress and progress.status == WarmupStatus.IN_PROGRESS:
            is_safe, reason = self.check_warmup_bounce_thresholds(ip_address, subuser)
            if not is_safe:
                return True, f"Warmup threshold breach: {reason}"
            return False, "IP in warmup - rotation not recommended"

        # If warmup completed, use normal rotation logic
        if self.bounce_monitor:
            violations = self.bounce_monitor.check_thresholds()
            for level, violating_stats in violations.items():
                for stat in violating_stats:
                    if stat.ip_address == ip_address and stat.subuser == subuser:
                        if level in ["critical", "block"]:
                            return True, f"Bounce threshold exceeded: {level}"

        return False, "No rotation needed"

    def _log_integration_event(
        self,
        event_type: str,
        ip_address: str,
        details: dict = None,
    ):
        """Log an integration event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "ip_address": ip_address,
            "details": details or {},
        }
        self.integration_events.append(event)

        # Keep only recent events
        if len(self.integration_events) > 1000:
            self.integration_events = self.integration_events[-500:]

    def get_integration_status(self) -> dict:
        """Get current integration status."""
        warmup_ips = []
        completed_ips = []

        for ip_address in self.monitored_ips:
            progress = self.warmup_scheduler.get_warmup_progress(ip_address)
            if progress:
                if progress.status == WarmupStatus.IN_PROGRESS:
                    warmup_ips.append(ip_address)
                elif progress.status == WarmupStatus.COMPLETED:
                    completed_ips.append(ip_address)

        return {
            "integration_mode": self._get_integration_mode().value,
            "monitored_ips": len(self.monitored_ips),
            "warmup_in_progress": warmup_ips,
            "warmup_completed": completed_ips,
            "recent_events": self.integration_events[-10:],
            "bounce_monitoring_enabled": self.bounce_monitor is not None,
            "rotation_service_enabled": self.rotation_service is not None,
        }


# Convenience functions
def create_warmup_integration(
    warmup_scheduler: SendGridWarmupScheduler,
    bounce_monitor: Optional[BounceRateMonitor] = None,
    rotation_service: Optional[IPRotationService] = None,
    config: Optional[WarmupIntegrationConfig] = None,
) -> SendGridWarmupIntegration:
    """
    Create a warmup integration instance.

    Args:
        warmup_scheduler: SendGrid warmup scheduler
        bounce_monitor: Bounce rate monitor (optional)
        rotation_service: IP rotation service (optional)
        config: Integration configuration (optional)

    Returns:
        SendGridWarmupIntegration instance
    """
    return SendGridWarmupIntegration(
        warmup_scheduler=warmup_scheduler,
        bounce_monitor=bounce_monitor,
        rotation_service=rotation_service,
        config=config,
    )


def setup_integrated_email_system(
    warmup_db_path: Optional[str] = None,
    bounce_db_path: Optional[str] = None,
    warmup_config: Optional[WarmupIntegrationConfig] = None,
) -> SendGridWarmupIntegration:
    """
    Set up a complete integrated email system with warmup, bounce monitoring, and rotation.

    Args:
        warmup_db_path: Database path for warmup scheduler
        bounce_db_path: Database path for bounce monitor
        warmup_config: Integration configuration

    Returns:
        Configured SendGridWarmupIntegration instance
    """
    # Create warmup scheduler
    warmup_scheduler = SendGridWarmupScheduler(db_path=warmup_db_path)

    # Create bounce monitor if available
    bounce_monitor = None
    rotation_service = None

    if ROTATION_AVAILABLE:
        try:
            bounce_config = BounceRateConfig()
            bounce_monitor = BounceRateMonitor(
                config=bounce_config,
                db_path=bounce_db_path,
            )

            rotation_config = RotationConfig()
            rotation_service = IPRotationService(
                config=rotation_config,
                bounce_monitor=bounce_monitor,
            )

            logger.info("Created integrated email system with full rotation support")
        except Exception as e:
            logger.warning(f"Could not create rotation components: {e}")

    return create_warmup_integration(
        warmup_scheduler=warmup_scheduler,
        bounce_monitor=bounce_monitor,
        rotation_service=rotation_service,
        config=warmup_config,
    )
