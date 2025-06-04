#!/usr/bin/env python3
"""
Task 21: IP Pool Switching Integration Module

This module ties together all the components needed for automatic IP pool switching
on bounce threshold, providing a unified interface for the complete functionality.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Import core components
try:
    from leadfactory.services.bounce_monitor import BounceRateConfig, BounceRateMonitor
    from leadfactory.services.ip_pool_manager import IPPoolManager
    from leadfactory.services.ip_rotation import (
        IPRotationService,
        create_default_rotation_config,
    )
    from leadfactory.services.ip_rotation_alerting import (
        AlertingConfig,
        IPRotationAlerting,
    )
    from leadfactory.services.threshold_detector import (
        ThresholdDetector,
        create_default_threshold_config,
    )
except ImportError as e:
    logging.error(f"Failed to import required components: {e}")
    raise

# Import logging with fallback
try:
    from leadfactory.utils.logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class IPPoolSwitchingService:
    """
    Main service that integrates all Task 21 components for automatic IP pool switching.

    This service:
    1. Monitors bounce rates per IP/subuser combination
    2. Detects when 2% bounce threshold is exceeded
    3. Automatically switches to backup IP pools
    4. Integrates with SendGrid API for pool management
    5. Provides alerting for critical events
    """

    def __init__(
        self,
        bounce_config: BounceRateConfig = None,
        alerting_config: AlertingConfig = None,
        db_path: str = None,
    ):
        """
        Initialize the IP pool switching service.

        Args:
            bounce_config: Configuration for bounce rate monitoring
            alerting_config: Configuration for alerting system
            db_path: Database path (SQLite for testing, None for PostgreSQL)
        """
        self.db_path = db_path

        # Set up bounce rate monitoring (2% threshold as per Task 21)
        self.bounce_config = bounce_config or BounceRateConfig(
            warning_threshold=0.02,  # 2% threshold requirement
            critical_threshold=0.05,  # 5% critical threshold
            block_threshold=0.10,  # 10% block threshold
            minimum_sample_size=50,  # Minimum emails before triggering
            rolling_window_hours=24,  # 24-hour rolling window
        )

        # Initialize components
        self.bounce_monitor = BounceRateMonitor(self.bounce_config, db_path=db_path)
        self.threshold_detector = ThresholdDetector(
            create_default_threshold_config(), bounce_monitor=self.bounce_monitor
        )
        self.alerting_service = IPRotationAlerting(alerting_config)
        self.rotation_service = IPRotationService(
            create_default_rotation_config(),
            bounce_monitor=self.bounce_monitor,
            threshold_detector=self.threshold_detector,
            alerting_service=self.alerting_service,
        )
        self.ip_pool_manager = IPPoolManager()

        # Set up threshold breach handling
        self.threshold_detector.add_notification_callback(self._handle_threshold_breach)

        # Service state
        self.running = False
        self.monitoring_task = None

        logger.info("IP Pool Switching Service initialized with 2% bounce threshold")

    async def start(self):
        """Start the IP pool switching service."""
        if self.running:
            logger.warning("IP Pool Switching Service already running")
            return

        self.running = True

        # Initialize IP pool configurations
        await self._initialize_ip_pools()

        # Start monitoring tasks
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("IP Pool Switching Service started")

    async def stop(self):
        """Stop the IP pool switching service."""
        self.running = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        # Stop IP pool manager if running
        if self.ip_pool_manager.running:
            await self.ip_pool_manager.stop_monitoring()

        logger.info("IP Pool Switching Service stopped")

    async def _initialize_ip_pools(self):
        """Initialize IP pool configurations for rotation."""
        # Add IP/subuser combinations to rotation pool
        # These would be configured based on your SendGrid setup

        # Primary pools (high priority)
        self.rotation_service.add_ip_subuser(
            ip_address="198.51.100.1",
            subuser="primary_marketing",
            priority=10,
            tags=["primary", "marketing"],
        )

        self.rotation_service.add_ip_subuser(
            ip_address="198.51.100.2",
            subuser="primary_sales",
            priority=10,
            tags=["primary", "sales"],
        )

        # Backup pools (medium priority)
        self.rotation_service.add_ip_subuser(
            ip_address="203.0.113.1",
            subuser="backup_marketing",
            priority=5,
            tags=["backup", "marketing"],
        )

        self.rotation_service.add_ip_subuser(
            ip_address="203.0.113.2",
            subuser="backup_sales",
            priority=5,
            tags=["backup", "sales"],
        )

        # Emergency pools (low priority)
        self.rotation_service.add_ip_subuser(
            ip_address="192.0.2.1",
            subuser="emergency_all",
            priority=1,
            tags=["emergency", "all"],
        )

        logger.info("IP pools initialized for rotation")

    async def _monitoring_loop(self):
        """Main monitoring loop for bounce rates and threshold detection."""
        while self.running:
            try:
                # Check thresholds for all IP/subuser combinations
                breaches = self.threshold_detector.check_all_thresholds()

                if breaches:
                    logger.info(f"Found {len(breaches)} threshold breaches")
                    for breach in breaches:
                        await self._handle_threshold_breach(breach)

                # Update performance metrics
                self.rotation_service.update_performance_metrics()

                # Clean up old data periodically
                if datetime.now().minute == 0:  # Once per hour
                    self._cleanup_old_data()

                # Sleep before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    def _handle_threshold_breach(self, breach):
        """Handle threshold breach by triggering rotation."""
        try:
            # Let the rotation service handle the breach
            rotation_event = self.rotation_service.handle_threshold_breach(breach)

            if rotation_event and rotation_event.success:
                logger.info(
                    f"Successfully rotated {rotation_event.from_ip}/{rotation_event.from_subuser} "
                    f"to {rotation_event.to_ip}/{rotation_event.to_subuser} "
                    f"due to threshold breach"
                )
            elif rotation_event and not rotation_event.success:
                logger.error(
                    f"Failed to rotate due to threshold breach: {rotation_event.error_message}"
                )

        except Exception as e:
            logger.error(f"Error handling threshold breach: {e}")

    def _cleanup_old_data(self):
        """Clean up old monitoring data."""
        try:
            # Clean up bounce monitor data
            if hasattr(self.bounce_monitor, "cleanup_old_events"):
                deleted_events = self.bounce_monitor.cleanup_old_events(days_to_keep=30)
                if deleted_events > 0:
                    logger.info(f"Cleaned up {deleted_events} old bounce events")

            # Clean up rotation history
            deleted_rotations = self.rotation_service.cleanup_old_history(
                days_to_keep=7
            )
            if deleted_rotations > 0:
                logger.info(f"Cleaned up {deleted_rotations} old rotation events")

            # Clean up alerts
            deleted_alerts = self.alerting_service.cleanup_old_alerts(days=7)
            if deleted_alerts > 0:
                logger.info(f"Cleaned up {deleted_alerts} old alerts")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def record_bounce_event(
        self,
        email: str,
        ip_address: str,
        subuser: str,
        bounce_type: str,
        reason: str,
        message_id: str = None,
    ):
        """
        Record a bounce event for monitoring.

        Args:
            email: Email address that bounced
            ip_address: IP address used to send
            subuser: Subuser identifier
            bounce_type: Type of bounce (hard, soft, spam)
            reason: Reason for bounce
            message_id: Optional message ID
        """
        try:
            from leadfactory.services.bounce_monitor import BounceEvent

            bounce_event = BounceEvent(
                email=email,
                ip_address=ip_address,
                subuser=subuser,
                bounce_type=bounce_type,
                reason=reason,
                timestamp=datetime.now(),
                message_id=message_id,
            )

            self.bounce_monitor.record_bounce_event(bounce_event)

            # Check if this specific IP/subuser should be checked immediately
            breaches = self.threshold_detector.check_thresholds(ip_address, subuser)
            if breaches:
                for breach in breaches:
                    await self._handle_threshold_breach(breach)

        except Exception as e:
            logger.error(f"Error recording bounce event: {e}")

    async def record_sent_email(
        self, ip_address: str, subuser: str, email: str = None, message_id: str = None
    ):
        """
        Record a sent email for bounce rate calculation.

        Args:
            ip_address: IP address used to send
            subuser: Subuser identifier
            email: Email address (optional)
            message_id: Message ID (optional)
        """
        try:
            self.bounce_monitor.record_sent_email(
                ip_address=ip_address,
                subuser=subuser,
                email=email,
                message_id=message_id,
            )
        except Exception as e:
            logger.error(f"Error recording sent email: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the IP pool switching service."""
        try:
            bounce_stats = self.bounce_monitor.get_all_stats()
            pool_status = self.rotation_service.get_pool_status()
            ip_pool_status = self.ip_pool_manager.get_status()
            alert_summary = self.alerting_service.get_alert_summary(hours=24)

            # Get recent threshold violations
            violations = self.threshold_detector.get_current_violations()

            return {
                "service_running": self.running,
                "bounce_monitoring": {
                    "total_ip_subuser_combinations": len(bounce_stats),
                    "threshold_violations": len(violations),
                    "warning_threshold": self.bounce_config.warning_threshold,
                    "critical_threshold": self.bounce_config.critical_threshold,
                },
                "rotation_pool": pool_status,
                "ip_pool_manager": ip_pool_status,
                "alerts": alert_summary,
                "recent_violations": [
                    {
                        "ip_address": v.ip_address,
                        "subuser": v.subuser,
                        "bounce_rate": v.current_value,
                        "threshold": v.threshold_value,
                        "severity": v.severity.value,
                        "rule": v.rule_name,
                    }
                    for v in violations[:10]  # Last 10 violations
                ],
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"error": str(e), "service_running": self.running}

    def get_bounce_rate(self, ip_address: str, subuser: str) -> float:
        """Get current bounce rate for an IP/subuser combination."""
        return self.bounce_monitor.get_bounce_rate(ip_address, subuser)

    def get_available_alternatives(
        self, exclude_ip: str = None, exclude_subuser: str = None
    ) -> List[Dict[str, Any]]:
        """Get available IP/subuser alternatives for rotation."""
        try:
            alternatives = self.rotation_service.get_available_alternatives(
                exclude_ip=exclude_ip, exclude_subuser=exclude_subuser
            )

            return [
                {
                    "ip_address": alt.ip_address,
                    "subuser": alt.subuser,
                    "status": alt.status.value,
                    "priority": alt.priority,
                    "performance_score": alt.performance_score,
                    "total_sent": alt.total_sent,
                    "total_bounced": alt.total_bounced,
                    "last_used": alt.last_used.isoformat() if alt.last_used else None,
                    "tags": alt.tags,
                }
                for alt in alternatives
            ]
        except Exception as e:
            logger.error(f"Error getting alternatives: {e}")
            return []

    async def force_rotation(
        self, from_ip: str, from_subuser: str, to_ip: str = None, to_subuser: str = None
    ) -> Dict[str, Any]:
        """
        Force a manual rotation between IP/subuser combinations.

        Args:
            from_ip: Source IP address
            from_subuser: Source subuser
            to_ip: Target IP address (auto-selected if None)
            to_subuser: Target subuser (auto-selected if None)

        Returns:
            Dictionary with rotation results
        """
        try:
            from leadfactory.services.ip_rotation import RotationReason

            # Auto-select target if not specified
            if not to_ip or not to_subuser:
                alternative = self.rotation_service.select_best_alternative(
                    from_ip, from_subuser
                )
                if not alternative:
                    return {
                        "success": False,
                        "error": "No suitable alternative found",
                        "from_ip": from_ip,
                        "from_subuser": from_subuser,
                    }
                to_ip = alternative.ip_address
                to_subuser = alternative.subuser

            # Execute rotation
            rotation_event = self.rotation_service.execute_rotation(
                from_ip=from_ip,
                from_subuser=from_subuser,
                to_ip=to_ip,
                to_subuser=to_subuser,
                reason=RotationReason.MANUAL_ROTATION,
            )

            return {
                "success": rotation_event.success,
                "error": rotation_event.error_message,
                "from_ip": from_ip,
                "from_subuser": from_subuser,
                "to_ip": to_ip,
                "to_subuser": to_subuser,
                "event_id": rotation_event.event_id,
                "timestamp": rotation_event.timestamp.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error during forced rotation: {e}")
            return {
                "success": False,
                "error": str(e),
                "from_ip": from_ip,
                "from_subuser": from_subuser,
            }


# Global service instance (singleton pattern)
_ip_pool_switching_service = None


def get_ip_pool_switching_service(
    bounce_config: BounceRateConfig = None,
    alerting_config: AlertingConfig = None,
    db_path: str = None,
) -> IPPoolSwitchingService:
    """Get or create the global IP pool switching service instance."""
    global _ip_pool_switching_service

    if _ip_pool_switching_service is None:
        _ip_pool_switching_service = IPPoolSwitchingService(
            bounce_config=bounce_config,
            alerting_config=alerting_config,
            db_path=db_path,
        )

    return _ip_pool_switching_service


async def start_ip_pool_switching():
    """Start the IP pool switching service."""
    service = get_ip_pool_switching_service()
    await service.start()


async def stop_ip_pool_switching():
    """Stop the IP pool switching service."""
    service = get_ip_pool_switching_service()
    await service.stop()


# Example usage and testing functions
async def example_usage():
    """Example usage of the IP pool switching service."""
    # Initialize service with 2% bounce threshold
    service = get_ip_pool_switching_service()

    # Start monitoring
    await service.start()

    try:
        # Simulate sending emails
        await service.record_sent_email("198.51.100.1", "primary_marketing")
        await service.record_sent_email("198.51.100.1", "primary_marketing")
        await service.record_sent_email("198.51.100.1", "primary_marketing")

        # Simulate a bounce event (this might trigger rotation if rate exceeds 2%)
        await service.record_bounce_event(
            email="bounce@example.com",
            ip_address="198.51.100.1",
            subuser="primary_marketing",
            bounce_type="hard",
            reason="User unknown",
            message_id="msg_001",
        )

        # Check status
        status = service.get_status()
        print(f"Service Status: {status}")

        # Get alternatives
        alternatives = service.get_available_alternatives(
            exclude_ip="198.51.100.1", exclude_subuser="primary_marketing"
        )
        print(f"Available alternatives: {len(alternatives)}")

        # Force a manual rotation if needed
        rotation_result = await service.force_rotation(
            from_ip="198.51.100.1", from_subuser="primary_marketing"
        )
        print(f"Manual rotation result: {rotation_result}")

    finally:
        # Stop service
        await service.stop()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
