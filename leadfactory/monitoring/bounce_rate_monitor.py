"""
Automated Bounce Rate Monitoring Service

This module provides automated monitoring of bounce rates across IP pools and subusers,
with integration to the IP warmup system for automatic intervention when thresholds are exceeded.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from leadfactory.email.sendgrid_warmup import SendGridWarmupScheduler, WarmupStatus
from leadfactory.email.sendgrid_warmup_integration import (
    SendGridWarmupIntegration,
    WarmupIntegrationConfig,
)
from leadfactory.services.bounce_monitor import (
    BounceRateConfig,
    BounceRateMonitor,
    IPSubuserStats,
)
from leadfactory.services.ip_rotation import IPRotationService, RotationReason, IPSubuserStatus
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AutomatedBounceMonitor:
    """
    Automated service that continuously monitors bounce rates and takes action
    when thresholds are exceeded.
    """
    
    def __init__(
        self,
        bounce_monitor: BounceRateMonitor,
        warmup_scheduler: SendGridWarmupScheduler,
        rotation_service: IPRotationService,
        warmup_integration: SendGridWarmupIntegration,
        check_interval_seconds: int = 300,  # 5 minutes
        alert_webhook_url: Optional[str] = None,
    ):
        """
        Initialize the automated bounce monitor.
        
        Args:
            bounce_monitor: Bounce rate monitoring service
            warmup_scheduler: IP warmup scheduler
            rotation_service: IP rotation service
            warmup_integration: Warmup integration service
            check_interval_seconds: How often to check bounce rates
            alert_webhook_url: Optional webhook URL for alerts
        """
        self.bounce_monitor = bounce_monitor
        self.warmup_scheduler = warmup_scheduler
        self.rotation_service = rotation_service
        self.warmup_integration = warmup_integration
        self.check_interval = check_interval_seconds
        self.alert_webhook_url = alert_webhook_url or os.getenv('BOUNCE_ALERT_WEBHOOK_URL')
        
        self._running = False
        self._task = None
        self._last_check_time = {}
        self._alert_history = {}
        
    async def start(self):
        """Start the automated monitoring service."""
        if self._running:
            logger.warning("Automated bounce monitor is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Started automated bounce rate monitoring (interval: {self.check_interval}s)")
        
    async def stop(self):
        """Stop the automated monitoring service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped automated bounce rate monitoring")
        
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_bounce_rates()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in bounce monitoring loop: {e}")
                await asyncio.sleep(30)  # Brief pause on error
                
    async def _check_bounce_rates(self):
        """Check bounce rates for all active IPs and take action if needed."""
        logger.debug("Checking bounce rates...")
        
        # Get all IP/subuser combinations
        stats = await self._get_all_stats()
        
        for ip_subuser_stats in stats:
            ip = ip_subuser_stats.ip_address
            subuser = ip_subuser_stats.subuser
            bounce_rate = ip_subuser_stats.bounce_rate
            
            # Skip if not enough samples
            if ip_subuser_stats.total_sent < self.bounce_monitor.config.minimum_sample_size:
                continue
                
            # Check thresholds
            if bounce_rate >= self.bounce_monitor.config.block_threshold:
                await self._handle_block_threshold(ip, subuser, bounce_rate, ip_subuser_stats)
            elif bounce_rate >= self.bounce_monitor.config.critical_threshold:
                await self._handle_critical_threshold(ip, subuser, bounce_rate, ip_subuser_stats)
            elif bounce_rate >= self.bounce_monitor.config.warning_threshold:
                await self._handle_warning_threshold(ip, subuser, bounce_rate, ip_subuser_stats)
            else:
                # Clear any previous alerts if bounce rate is now healthy
                await self._clear_alerts(ip, subuser)
                
    async def _get_all_stats(self) -> List[IPSubuserStats]:
        """Get stats for all IP/subuser combinations."""
        try:
            # Get from bounce monitor
            all_stats = []
            
            # Get active IPs from rotation service
            active_pools = self.rotation_service.get_all_pools()
            
            for pool in active_pools:
                for ip_subuser in pool.pool:
                    stats = self.bounce_monitor.get_bounce_rate(
                        ip_subuser.ip_address,
                        ip_subuser.subuser
                    )
                    if stats:
                        all_stats.append(stats)
                        
            # Also check IPs in warmup
            warmup_ips = self.warmup_scheduler.get_active_warmup_ips()
            for ip_info in warmup_ips:
                stats = self.bounce_monitor.get_bounce_rate(
                    ip_info['ip_address'],
                    ip_info['subuser']
                )
                if stats:
                    all_stats.append(stats)
                    
            return all_stats
            
        except Exception as e:
            logger.error(f"Error getting IP stats: {e}")
            return []
            
    async def _handle_block_threshold(
        self,
        ip: str,
        subuser: str,
        bounce_rate: float,
        stats: IPSubuserStats
    ):
        """Handle IP that exceeded block threshold."""
        logger.error(
            f"BLOCK threshold exceeded for {ip}/{subuser}: "
            f"{bounce_rate:.2%} (sent: {stats.total_sent}, bounced: {stats.total_bounced})"
        )
        
        # Check if in warmup
        warmup_status = self.warmup_scheduler.get_warmup_status(ip)
        
        if warmup_status and warmup_status.status != WarmupStatus.COMPLETED:
            # Pause warmup immediately
            self.warmup_scheduler.pause_warmup(ip, f"Bounce rate exceeded block threshold: {bounce_rate:.2%}")
            await self._send_alert(
                "critical",
                f"IP Warmup Paused - Block Threshold",
                f"IP {ip} (subuser: {subuser}) warmup paused due to {bounce_rate:.2%} bounce rate"
            )
        else:
            # Find and disable IP in rotation pool
            success = False
            pools = self.rotation_service.get_all_pools()
            
            for pool in pools:
                for ip_subuser in pool.pool:
                    if ip_subuser.ip_address == ip and ip_subuser.subuser == subuser:
                        # Disable the IP
                        ip_subuser.status = IPSubuserStatus.DISABLED
                        ip_subuser.metadata["disabled_reason"] = f"High bounce rate: {bounce_rate:.2%}"
                        ip_subuser.metadata["disabled_at"] = datetime.now().isoformat()
                        success = True
                        
                        # Record in alerting system if available
                        if hasattr(self.rotation_service, 'alerting_service') and self.rotation_service.alerting_service:
                            self.rotation_service.alerting_service.record_ip_disabled(
                                ip, f"High bounce rate: {bounce_rate:.2%}"
                            )
                        break
                if success:
                    break
            
            if success:
                await self._send_alert(
                    "critical",
                    f"IP Blocked - High Bounce Rate",
                    f"IP {ip} (subuser: {subuser}) removed from rotation due to {bounce_rate:.2%} bounce rate"
                )
            else:
                logger.error(f"IP {ip} not found in rotation pools")
                
    async def _handle_critical_threshold(
        self,
        ip: str,
        subuser: str,
        bounce_rate: float,
        stats: IPSubuserStats
    ):
        """Handle IP that exceeded critical threshold."""
        logger.warning(
            f"CRITICAL threshold exceeded for {ip}/{subuser}: "
            f"{bounce_rate:.2%} (sent: {stats.total_sent}, bounced: {stats.total_bounced})"
        )
        
        # Check if in warmup
        warmup_status = self.warmup_scheduler.get_warmup_status(ip)
        
        if warmup_status and warmup_status.status == WarmupStatus.IN_PROGRESS:
            # Slow down warmup progression
            logger.info(f"Slowing warmup progression for {ip} due to critical bounce rate")
            # The warmup scheduler will check bounce rates before advancing stages
        else:
            # Deprioritize in rotation pool by increasing priority number (lower priority)
            pools = self.rotation_service.get_all_pools()
            
            for pool in pools:
                for ip_subuser in pool.pool:
                    if ip_subuser.ip_address == ip and ip_subuser.subuser == subuser:
                        # Increase priority number to deprioritize (higher number = lower priority)
                        ip_subuser.priority = max(10, ip_subuser.priority + 5)
                        ip_subuser.metadata["deprioritized_reason"] = f"Critical bounce rate: {bounce_rate:.2%}"
                        ip_subuser.metadata["deprioritized_at"] = datetime.now().isoformat()
                        logger.info(f"Deprioritized IP {ip} to priority {ip_subuser.priority}")
                        break
            
        await self._send_alert(
            "warning",
            f"Critical Bounce Rate - {ip}",
            f"IP {ip} (subuser: {subuser}) has {bounce_rate:.2%} bounce rate (critical threshold)"
        )
        
    async def _handle_warning_threshold(
        self,
        ip: str,
        subuser: str,
        bounce_rate: float,
        stats: IPSubuserStats
    ):
        """Handle IP that exceeded warning threshold."""
        logger.info(
            f"WARNING threshold exceeded for {ip}/{subuser}: "
            f"{bounce_rate:.2%} (sent: {stats.total_sent}, bounced: {stats.total_bounced})"
        )
        
        # Only alert if this is the first warning or rate increased significantly
        alert_key = f"{ip}:{subuser}"
        last_alert = self._alert_history.get(alert_key, {})
        
        if not last_alert or bounce_rate > last_alert.get('bounce_rate', 0) * 1.2:
            await self._send_alert(
                "info",
                f"Bounce Rate Warning - {ip}",
                f"IP {ip} (subuser: {subuser}) has {bounce_rate:.2%} bounce rate (warning threshold)"
            )
            self._alert_history[alert_key] = {
                'bounce_rate': bounce_rate,
                'timestamp': datetime.now()
            }
            
    async def _clear_alerts(self, ip: str, subuser: str):
        """Clear previous alerts for healthy IP."""
        alert_key = f"{ip}:{subuser}"
        if alert_key in self._alert_history:
            del self._alert_history[alert_key]
            logger.info(f"Cleared alerts for {ip}/{subuser} - bounce rate now healthy")
            
    async def _send_alert(self, severity: str, title: str, message: str):
        """Send alert via webhook or logging."""
        alert_data = {
            "severity": severity,
            "title": title,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "service": "bounce_rate_monitor"
        }
        
        # Always log
        if severity == "critical":
            logger.error(f"ALERT: {title} - {message}")
        elif severity == "warning":
            logger.warning(f"ALERT: {title} - {message}")
        else:
            logger.info(f"ALERT: {title} - {message}")
            
        # Send webhook if configured
        if self.alert_webhook_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.alert_webhook_url,
                        json=alert_data,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status != 200:
                            logger.error(f"Failed to send alert webhook: {response.status}")
            except Exception as e:
                logger.error(f"Error sending alert webhook: {e}")
                
    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status."""
        return {
            "running": self._running,
            "check_interval_seconds": self.check_interval,
            "last_checks": self._last_check_time,
            "active_alerts": len(self._alert_history),
            "alert_history": [
                {
                    "ip_subuser": key,
                    "bounce_rate": data['bounce_rate'],
                    "timestamp": data['timestamp'].isoformat()
                }
                for key, data in self._alert_history.items()
            ]
        }


# Singleton instance
_monitor_instance = None


def get_automated_monitor() -> Optional[AutomatedBounceMonitor]:
    """Get the singleton automated monitor instance."""
    return _monitor_instance


async def start_automated_monitoring(
    check_interval_seconds: int = 300,
    alert_webhook_url: Optional[str] = None
) -> AutomatedBounceMonitor:
    """
    Start automated bounce rate monitoring.
    
    Args:
        check_interval_seconds: How often to check bounce rates
        alert_webhook_url: Optional webhook URL for alerts
        
    Returns:
        The automated monitor instance
    """
    global _monitor_instance
    
    if _monitor_instance and _monitor_instance._running:
        logger.warning("Automated monitoring already running")
        return _monitor_instance
        
    # Initialize required services
    from leadfactory.services.bounce_monitor import BounceRateMonitor, BounceRateConfig
    from leadfactory.services.ip_rotation import IPRotationService, RotationConfig
    
    # Create service instances
    bounce_config = BounceRateConfig()
    bounce_monitor = BounceRateMonitor(config=bounce_config)
    
    rotation_config = RotationConfig()
    rotation_service = IPRotationService(config=rotation_config)
    
    warmup_scheduler = SendGridWarmupScheduler()
    
    integration_config = WarmupIntegrationConfig()
    warmup_integration = SendGridWarmupIntegration(
        warmup_scheduler=warmup_scheduler,
        bounce_monitor=bounce_monitor,
        rotation_service=rotation_service,
        config=integration_config
    )
    
    # Create and start monitor
    _monitor_instance = AutomatedBounceMonitor(
        bounce_monitor=bounce_monitor,
        warmup_scheduler=warmup_scheduler,
        rotation_service=rotation_service,
        warmup_integration=warmup_integration,
        check_interval_seconds=check_interval_seconds,
        alert_webhook_url=alert_webhook_url
    )
    
    await _monitor_instance.start()
    return _monitor_instance


async def stop_automated_monitoring():
    """Stop automated bounce rate monitoring."""
    global _monitor_instance
    
    if _monitor_instance:
        await _monitor_instance.stop()
        _monitor_instance = None