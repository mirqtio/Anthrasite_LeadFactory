"""
Automatic IP Pool Switching on Bounce Threshold.

Monitors email bounce rates and automatically switches IP pools
to maintain deliverability when bounce thresholds are exceeded.
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail

    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


logger = logging.getLogger(__name__)


class IPPoolStatus(Enum):
    """IP pool status states."""

    ACTIVE = "active"
    WARNING = "warning"
    QUARANTINED = "quarantined"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


@dataclass
class IPPool:
    """Represents an IP pool configuration."""

    pool_id: str
    pool_name: str
    ip_addresses: List[str]
    status: IPPoolStatus
    bounce_rate: float = 0.0
    spam_rate: float = 0.0
    delivery_rate: float = 1.0
    daily_volume: int = 0
    max_daily_volume: int = 50000
    reputation_score: float = 1.0
    last_health_check: Optional[datetime] = None
    quarantine_until: Optional[datetime] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class BounceEvent:
    """Represents a bounce event."""

    email: str
    bounce_type: str  # "soft", "hard", "spam"
    reason: str
    timestamp: datetime
    ip_pool_id: str
    message_id: str


@dataclass
class DeliveryMetrics:
    """Delivery metrics for an IP pool."""

    total_sent: int
    total_delivered: int
    total_bounced: int
    total_spam_reports: int
    bounce_rate: float
    spam_rate: float
    delivery_rate: float
    reputation_score: float


class IPPoolManager:
    """
    Manages automatic IP pool switching based on bounce thresholds.

    Monitors email delivery metrics and automatically switches to
    backup IP pools when bounce rates exceed configured thresholds.
    """

    def __init__(self, config_file: str = "etc/ip_pool_config.yml"):
        """Initialize IP pool manager."""
        self.config_file = config_file
        self.ip_pools: Dict[str, IPPool] = {}
        self.bounce_events: List[BounceEvent] = []
        self.current_pool_id: Optional[str] = None
        self.backup_pools: List[str] = []

        # Thresholds and configuration
        self.thresholds = {
            "bounce_rate_warning": 0.02,  # 2% bounce rate warning
            "bounce_rate_critical": 0.05,  # 5% bounce rate critical
            "spam_rate_warning": 0.001,  # 0.1% spam rate warning
            "spam_rate_critical": 0.005,  # 0.5% spam rate critical
            "reputation_threshold": 0.8,  # Minimum reputation score
            "volume_threshold": 0.9,  # 90% of daily volume
            "quarantine_hours": 24,  # Hours to quarantine problematic pools
        }

        self.monitoring_interval = 60  # Check every minute
        self.running = False

        # Initialize SendGrid client
        self.sendgrid_client = None
        self._initialize_sendgrid()

        # Load initial configuration
        self._load_ip_pools()

    def _initialize_sendgrid(self):
        """Initialize SendGrid client for IP pool management."""
        if SENDGRID_AVAILABLE:
            try:
                import os

                api_key = os.getenv("SENDGRID_API_KEY")
                if api_key:
                    self.sendgrid_client = sendgrid.SendGridAPIClient(api_key)
                    logger.info("SendGrid client initialized")
                else:
                    logger.warning("SENDGRID_API_KEY not found")
            except Exception as e:
                logger.error(f"Failed to initialize SendGrid client: {e}")

    def _load_ip_pools(self):
        """Load IP pool configurations."""
        # In a real implementation, this would load from configuration file
        # For now, we'll create some example pools

        self.ip_pools = {
            "primary": IPPool(
                pool_id="primary",
                pool_name="Primary IP Pool",
                ip_addresses=["198.51.100.1", "198.51.100.2"],
                status=IPPoolStatus.ACTIVE,
                max_daily_volume=100000,
            ),
            "backup": IPPool(
                pool_id="backup",
                pool_name="Backup IP Pool",
                ip_addresses=["203.0.113.1", "203.0.113.2"],
                status=IPPoolStatus.ACTIVE,
                max_daily_volume=50000,
            ),
            "emergency": IPPool(
                pool_id="emergency",
                pool_name="Emergency IP Pool",
                ip_addresses=["192.0.2.1"],
                status=IPPoolStatus.ACTIVE,
                max_daily_volume=25000,
            ),
        }

        # Set primary pool as current
        self.current_pool_id = "primary"
        self.backup_pools = ["backup", "emergency"]

        logger.info(f"Loaded {len(self.ip_pools)} IP pools")

    async def start_monitoring(self):
        """Start IP pool monitoring."""
        self.running = True
        logger.info("IP Pool Manager monitoring started")

        while self.running:
            try:
                # Check pool health
                await self._check_pool_health()

                # Process recent bounce events
                await self._process_bounce_events()

                # Evaluate switching needs
                await self._evaluate_pool_switching()

                # Update pool metrics
                await self._update_pool_metrics()

                # Clean up old data
                await self._cleanup_old_data()

                # Log status
                await self._log_pool_status()

                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Error in IP pool monitoring: {e}")
                await asyncio.sleep(self.monitoring_interval)

    async def stop_monitoring(self):
        """Stop IP pool monitoring."""
        self.running = False
        logger.info("IP Pool Manager monitoring stopped")

    async def _check_pool_health(self):
        """Check health of all IP pools."""
        for pool_id, pool in self.ip_pools.items():
            if pool.status in [IPPoolStatus.QUARANTINED, IPPoolStatus.DISABLED]:
                # Check if quarantine period has ended
                if pool.quarantine_until and datetime.utcnow() > pool.quarantine_until:
                    await self._restore_pool(pool_id)
                continue

            # Check bounce rate threshold
            if pool.bounce_rate > self.thresholds["bounce_rate_critical"]:
                await self._quarantine_pool(pool_id, "High bounce rate")
            elif pool.bounce_rate > self.thresholds["bounce_rate_warning"]:
                pool.status = IPPoolStatus.WARNING
                logger.warning(
                    f"Pool {pool_id} bounce rate warning: {pool.bounce_rate:.3f}"
                )

            # Check spam rate threshold
            if pool.spam_rate > self.thresholds["spam_rate_critical"]:
                await self._quarantine_pool(pool_id, "High spam rate")
            elif pool.spam_rate > self.thresholds["spam_rate_warning"]:
                pool.status = IPPoolStatus.WARNING
                logger.warning(
                    f"Pool {pool_id} spam rate warning: {pool.spam_rate:.3f}"
                )

            # Check reputation score
            if pool.reputation_score < self.thresholds["reputation_threshold"]:
                await self._quarantine_pool(pool_id, "Low reputation score")

            # Check daily volume
            if (
                pool.daily_volume
                > pool.max_daily_volume * self.thresholds["volume_threshold"]
            ):
                pool.status = IPPoolStatus.WARNING
                logger.warning(
                    f"Pool {pool_id} approaching volume limit: {pool.daily_volume}/{pool.max_daily_volume}"
                )

            pool.last_health_check = datetime.utcnow()

    async def _process_bounce_events(self):
        """Process recent bounce events to update pool metrics."""
        # Group bounce events by pool and time window
        now = datetime.utcnow()
        window_start = now - timedelta(hours=1)  # 1-hour window

        recent_bounces = [
            event for event in self.bounce_events if event.timestamp > window_start
        ]

        # Calculate metrics per pool
        pool_metrics = {}
        for event in recent_bounces:
            pool_id = event.ip_pool_id
            if pool_id not in pool_metrics:
                pool_metrics[pool_id] = {
                    "total_bounces": 0,
                    "hard_bounces": 0,
                    "soft_bounces": 0,
                    "spam_reports": 0,
                }

            pool_metrics[pool_id]["total_bounces"] += 1

            if event.bounce_type == "hard":
                pool_metrics[pool_id]["hard_bounces"] += 1
            elif event.bounce_type == "soft":
                pool_metrics[pool_id]["soft_bounces"] += 1
            elif event.bounce_type == "spam":
                pool_metrics[pool_id]["spam_reports"] += 1

        # Update pool bounce rates
        for pool_id, metrics in pool_metrics.items():
            if pool_id in self.ip_pools:
                pool = self.ip_pools[pool_id]

                # Calculate rates (assuming we track sent volume)
                if pool.daily_volume > 0:
                    pool.bounce_rate = metrics["total_bounces"] / pool.daily_volume
                    pool.spam_rate = metrics["spam_reports"] / pool.daily_volume
                    pool.delivery_rate = 1.0 - pool.bounce_rate

    async def _evaluate_pool_switching(self):
        """Evaluate if current pool should be switched."""
        if not self.current_pool_id:
            await self._select_best_pool()
            return

        current_pool = self.ip_pools.get(self.current_pool_id)
        if not current_pool:
            await self._select_best_pool()
            return

        # Check if current pool needs to be switched
        should_switch = (
            current_pool.status == IPPoolStatus.QUARANTINED
            or current_pool.status == IPPoolStatus.DISABLED
            or current_pool.bounce_rate > self.thresholds["bounce_rate_critical"]
            or current_pool.spam_rate > self.thresholds["spam_rate_critical"]
            or current_pool.daily_volume >= current_pool.max_daily_volume
        )

        if should_switch:
            await self._switch_to_backup_pool()

    async def _switch_to_backup_pool(self):
        """Switch to the best available backup pool."""
        current_pool_id = self.current_pool_id
        best_pool_id = await self._select_best_pool()

        if best_pool_id and best_pool_id != current_pool_id:
            # Perform the switch
            old_pool = self.ip_pools.get(current_pool_id)
            new_pool = self.ip_pools[best_pool_id]

            self.current_pool_id = best_pool_id

            # Update SendGrid configuration
            await self._update_sendgrid_pool(best_pool_id)

            logger.warning(
                f"Switched IP pool from {current_pool_id} to {best_pool_id}. "
                f"Reason: Pool {current_pool_id} status={old_pool.status if old_pool else 'unknown'}, "
                f"bounce_rate={old_pool.bounce_rate if old_pool else 0:.3f}"
            )

            # Send alert
            await self._send_pool_switch_alert(current_pool_id, best_pool_id)
        else:
            logger.error("No suitable backup pool available!")
            await self._send_critical_alert("No backup pools available")

    async def _select_best_pool(self) -> Optional[str]:
        """Select the best available IP pool."""
        available_pools = [
            (pool_id, pool)
            for pool_id, pool in self.ip_pools.items()
            if pool.status == IPPoolStatus.ACTIVE
            and pool.daily_volume < pool.max_daily_volume
        ]

        if not available_pools:
            # No active pools, try warning status pools
            available_pools = [
                (pool_id, pool)
                for pool_id, pool in self.ip_pools.items()
                if pool.status == IPPoolStatus.WARNING
                and pool.daily_volume < pool.max_daily_volume
            ]

        if not available_pools:
            return None

        # Score pools based on multiple factors
        pool_scores = []
        for pool_id, pool in available_pools:
            score = (
                pool.reputation_score * 0.4
                + (1.0 - pool.bounce_rate) * 0.3
                + (1.0 - pool.spam_rate) * 0.2
                + (1.0 - pool.daily_volume / pool.max_daily_volume) * 0.1
            )
            pool_scores.append((pool_id, score))

        # Select pool with highest score
        best_pool = max(pool_scores, key=lambda x: x[1])
        return best_pool[0]

    async def _quarantine_pool(self, pool_id: str, reason: str):
        """Quarantine a problematic IP pool."""
        if pool_id not in self.ip_pools:
            return

        pool = self.ip_pools[pool_id]
        pool.status = IPPoolStatus.QUARANTINED
        pool.quarantine_until = datetime.utcnow() + timedelta(
            hours=self.thresholds["quarantine_hours"]
        )

        logger.error(f"Quarantined IP pool {pool_id}: {reason}")

        # If this was the current pool, switch immediately
        if self.current_pool_id == pool_id:
            await self._switch_to_backup_pool()

        # Send alert
        await self._send_quarantine_alert(pool_id, reason)

    async def _restore_pool(self, pool_id: str):
        """Restore a quarantined pool."""
        if pool_id not in self.ip_pools:
            return

        pool = self.ip_pools[pool_id]
        pool.status = IPPoolStatus.ACTIVE
        pool.quarantine_until = None

        # Reset metrics
        pool.bounce_rate = 0.0
        pool.spam_rate = 0.0
        pool.reputation_score = 1.0

        logger.info(f"Restored IP pool {pool_id} from quarantine")
        await self._send_restoration_alert(pool_id)

    async def _update_sendgrid_pool(self, pool_id: str):
        """Update SendGrid to use specified IP pool."""
        if not self.sendgrid_client:
            logger.warning("SendGrid client not available")
            return

        try:
            # In a real implementation, this would use SendGrid API to switch pools
            # For now, we'll just log the action
            pool = self.ip_pools[pool_id]
            logger.info(f"Updated SendGrid to use IP pool: {pool.pool_name}")

            # Example SendGrid API call (commented out):
            # response = self.sendgrid_client.client.ips.pools._(pool_id).put(
            #     request_body={"name": pool.pool_name}
            # )

        except Exception as e:
            logger.error(f"Failed to update SendGrid pool configuration: {e}")

    async def _update_pool_metrics(self):
        """Update pool metrics from SendGrid API."""
        if not self.sendgrid_client:
            return

        try:
            # Fetch delivery statistics from SendGrid
            # This would use actual SendGrid stats API
            for pool_id, pool in self.ip_pools.items():
                # Mock metrics update
                pool.daily_volume = pool.daily_volume + 100  # Simulate volume growth

                # Calculate reputation score based on metrics
                pool.reputation_score = max(
                    0.0, min(1.0, 1.0 - (pool.bounce_rate * 5) - (pool.spam_rate * 10))
                )

        except Exception as e:
            logger.error(f"Failed to update pool metrics: {e}")

    async def _cleanup_old_data(self):
        """Clean up old bounce events and metrics."""
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Keep 7 days

        self.bounce_events = [
            event for event in self.bounce_events if event.timestamp > cutoff_time
        ]

    async def _log_pool_status(self):
        """Log current pool status."""
        current_pool = self.ip_pools.get(self.current_pool_id)
        if current_pool:
            logger.info(
                f"Current IP Pool: {current_pool.pool_name} "
                f"(bounce: {current_pool.bounce_rate:.3f}, "
                f"spam: {current_pool.spam_rate:.3f}, "
                f"volume: {current_pool.daily_volume}/{current_pool.max_daily_volume})"
            )

    async def _send_pool_switch_alert(self, old_pool_id: str, new_pool_id: str):
        """Send alert about pool switch."""
        old_pool = self.ip_pools.get(old_pool_id)
        new_pool = self.ip_pools.get(new_pool_id)

        message = (
            f"ALERT: IP Pool switched from {old_pool.pool_name if old_pool else old_pool_id} "
            f"to {new_pool.pool_name if new_pool else new_pool_id}"
        )

        await self._send_alert(message, "pool_switch")

    async def _send_quarantine_alert(self, pool_id: str, reason: str):
        """Send alert about pool quarantine."""
        pool = self.ip_pools.get(pool_id)
        message = f"CRITICAL: IP Pool {pool.pool_name if pool else pool_id} quarantined - {reason}"
        await self._send_alert(message, "quarantine")

    async def _send_restoration_alert(self, pool_id: str):
        """Send alert about pool restoration."""
        pool = self.ip_pools.get(pool_id)
        message = f"INFO: IP Pool {pool.pool_name if pool else pool_id} restored from quarantine"
        await self._send_alert(message, "restoration")

    async def _send_critical_alert(self, message: str):
        """Send critical system alert."""
        await self._send_alert(f"CRITICAL: {message}", "critical")

    async def _send_alert(self, message: str, alert_type: str):
        """Send alert via configured channels."""
        # In a real implementation, this would send to Slack, email, etc.
        logger.warning(f"ALERT [{alert_type.upper()}]: {message}")

        # Could integrate with monitoring systems here
        # await slack_webhook.send(message)
        # await email_service.send_alert(message)

    async def record_bounce_event(
        self,
        email: str,
        bounce_type: str,
        reason: str,
        message_id: str,
        ip_pool_id: Optional[str] = None,
    ):
        """Record a bounce event for monitoring."""
        bounce_event = BounceEvent(
            email=email,
            bounce_type=bounce_type,
            reason=reason,
            timestamp=datetime.utcnow(),
            ip_pool_id=ip_pool_id or self.current_pool_id or "unknown",
            message_id=message_id,
        )

        self.bounce_events.append(bounce_event)

        logger.debug(f"Recorded bounce event: {email} ({bounce_type}) - {reason}")

    def get_current_pool(self) -> Optional[IPPool]:
        """Get current active IP pool."""
        if self.current_pool_id:
            return self.ip_pools.get(self.current_pool_id)
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of IP pool manager."""
        current_pool = self.get_current_pool()

        return {
            "running": self.running,
            "current_pool": {
                "id": self.current_pool_id,
                "name": current_pool.pool_name if current_pool else None,
                "status": current_pool.status.value if current_pool else None,
                "bounce_rate": current_pool.bounce_rate if current_pool else 0.0,
                "spam_rate": current_pool.spam_rate if current_pool else 0.0,
                "daily_volume": current_pool.daily_volume if current_pool else 0,
            },
            "total_pools": len(self.ip_pools),
            "active_pools": len(
                [p for p in self.ip_pools.values() if p.status == IPPoolStatus.ACTIVE]
            ),
            "quarantined_pools": len(
                [
                    p
                    for p in self.ip_pools.values()
                    if p.status == IPPoolStatus.QUARANTINED
                ]
            ),
            "recent_bounces": len(
                [
                    e
                    for e in self.bounce_events
                    if e.timestamp > datetime.utcnow() - timedelta(hours=1)
                ]
            ),
            "thresholds": self.thresholds,
        }

    def get_pool_details(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about all pools."""
        return {
            pool_id: {
                "name": pool.pool_name,
                "status": pool.status.value,
                "ip_addresses": pool.ip_addresses,
                "bounce_rate": pool.bounce_rate,
                "spam_rate": pool.spam_rate,
                "delivery_rate": pool.delivery_rate,
                "daily_volume": pool.daily_volume,
                "max_daily_volume": pool.max_daily_volume,
                "reputation_score": pool.reputation_score,
                "last_health_check": (
                    pool.last_health_check.isoformat()
                    if pool.last_health_check
                    else None
                ),
                "quarantine_until": (
                    pool.quarantine_until.isoformat() if pool.quarantine_until else None
                ),
            }
            for pool_id, pool in self.ip_pools.items()
        }


# Global instance
ip_pool_manager = IPPoolManager()


async def main():
    """Example usage of IP pool manager."""
    try:
        # Start monitoring
        monitoring_task = asyncio.create_task(ip_pool_manager.start_monitoring())

        # Simulate some bounce events
        await asyncio.sleep(5)

        await ip_pool_manager.record_bounce_event(
            "test@example.com", "hard", "User unknown", "msg_123", "primary"
        )

        # Let it run for a bit
        await asyncio.sleep(30)

        # Print status
        status = ip_pool_manager.get_status()
        print(f"IP Pool Manager Status: {json.dumps(status, indent=2)}")

        monitoring_task.cancel()

    except KeyboardInterrupt:
        await ip_pool_manager.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
