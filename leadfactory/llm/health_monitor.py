"""
LLM Health Monitoring System

This module provides comprehensive health monitoring for LLM providers,
including periodic health checks, status tracking, alerting, and dashboard data.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from leadfactory.utils.logging import get_logger

from .provider import LLMHealthStatus, LLMProvider

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Overall health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    provider: str
    timestamp: float
    status: HealthStatus
    response_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderMetrics:
    """Metrics for a provider over time."""

    provider: str
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    average_response_time: float = 0.0
    last_successful_check: Optional[float] = None
    last_failed_check: Optional[float] = None
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0
    response_times: List[float] = field(default_factory=list)


@dataclass
class HealthAlert:
    """Health monitoring alert."""

    id: str
    timestamp: float
    provider: str
    severity: AlertSeverity
    message: str
    resolved: bool = False
    resolved_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthConfig:
    """Configuration for health monitoring."""

    check_interval: float = 60.0  # Health check interval in seconds
    timeout: float = 30.0  # Health check timeout
    failure_threshold: int = 3  # Consecutive failures before alert
    recovery_threshold: int = 2  # Consecutive successes to clear alert
    response_time_threshold: float = 10.0  # Response time threshold for degraded status
    enable_alerts: bool = True
    enable_dashboard: bool = True
    max_history_size: int = 1000  # Maximum health check history to keep
    alert_cooldown: float = 300.0  # Minimum time between similar alerts


class HealthMonitor:
    """
    Comprehensive health monitoring for LLM providers.

    This class provides periodic health checks, status tracking,
    alerting, and dashboard data for LLM providers.
    """

    def __init__(self, config: Optional[HealthConfig] = None):
        """
        Initialize the health monitor.

        Args:
            config: Health monitoring configuration
        """
        self.config = config or HealthConfig()
        self.providers: Dict[str, LLMProvider] = {}
        self.health_history: List[HealthCheckResult] = []
        self.provider_metrics: Dict[str, ProviderMetrics] = {}
        self.active_alerts: Dict[str, HealthAlert] = {}
        self.alert_callbacks: List[Callable] = []

        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = None
        self._last_cleanup = time.time()
        self._alert_counter = 0

        logger.info("Health monitor initialized")

    def _get_lock(self):
        """Get or create the async lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """
        Register a provider for health monitoring.

        Args:
            name: Provider name
            provider: Provider instance
        """
        self.providers[name] = provider
        if name not in self.provider_metrics:
            self.provider_metrics[name] = ProviderMetrics(provider=name)

        logger.info(f"Registered provider for health monitoring: {name}")

    def unregister_provider(self, name: str) -> None:
        """
        Unregister a provider from health monitoring.

        Args:
            name: Provider name
        """
        if name in self.providers:
            del self.providers[name]
            logger.info(f"Unregistered provider from health monitoring: {name}")

    async def start_monitoring(self) -> None:
        """Start the health monitoring background task."""
        if self._monitoring_task is not None:
            logger.warning("Health monitoring is already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started health monitoring background task")

    async def stop_monitoring(self) -> None:
        """Stop the health monitoring background task."""
        if self._monitoring_task is not None:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Stopped health monitoring background task")

    async def check_provider_health(self, name: str) -> HealthCheckResult:
        """
        Check the health of a specific provider.

        Args:
            name: Provider name

        Returns:
            Health check result

        Raises:
            ValueError: If provider is not registered
        """
        if name not in self.providers:
            raise ValueError(f"Provider {name} is not registered")

        provider = self.providers[name]
        start_time = time.time()

        try:
            # Perform health check with timeout
            health_status = await asyncio.wait_for(
                provider.check_health(), timeout=self.config.timeout
            )

            response_time = time.time() - start_time

            # Determine overall status
            if health_status.is_healthy:
                if response_time > self.config.response_time_threshold:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.UNHEALTHY

            result = HealthCheckResult(
                provider=name,
                timestamp=time.time(),
                status=status,
                response_time=response_time,
                metadata={
                    "provider_is_healthy": health_status.is_healthy,
                    "provider_message": health_status.error_message,
                    "provider_response_time": health_status.response_time,
                    "provider_consecutive_failures": health_status.consecutive_failures,
                    "provider_last_check": health_status.last_check,
                },
            )

        except asyncio.TimeoutError:
            result = HealthCheckResult(
                provider=name,
                timestamp=time.time(),
                status=HealthStatus.CRITICAL,
                response_time=self.config.timeout,
                error_message=f"Health check timed out after {self.config.timeout}s",
            )

        except Exception as e:
            result = HealthCheckResult(
                provider=name,
                timestamp=time.time(),
                status=HealthStatus.CRITICAL,
                response_time=time.time() - start_time,
                error_message=str(e),
            )

        # Update metrics and history
        await self._update_metrics(result)

        return result

    async def check_all_providers(self) -> Dict[str, HealthCheckResult]:
        """
        Check the health of all registered providers.

        Returns:
            Dictionary mapping provider names to health check results
        """
        results = {}

        # Run health checks concurrently
        tasks = [self.check_provider_health(name) for name in self.providers.keys()]

        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(check_results):
                provider_name = list(self.providers.keys())[i]
                if isinstance(result, Exception):
                    results[provider_name] = HealthCheckResult(
                        provider=provider_name,
                        timestamp=time.time(),
                        status=HealthStatus.CRITICAL,
                        response_time=0.0,
                        error_message=str(result),
                    )
                else:
                    results[provider_name] = result

        return results

    async def get_provider_status(self, name: str) -> Dict[str, Any]:
        """
        Get current status and metrics for a provider.

        Args:
            name: Provider name

        Returns:
            Dictionary with provider status and metrics
        """
        if name not in self.provider_metrics:
            return {"error": f"Provider {name} not found"}

        metrics = self.provider_metrics[name]

        # Get recent health checks
        recent_checks = [
            check for check in self.health_history[-50:] if check.provider == name
        ]

        # Get active alerts
        provider_alerts = [
            alert
            for alert in self.active_alerts.values()
            if alert.provider == name and not alert.resolved
        ]

        return {
            "provider": name,
            "metrics": {
                "total_checks": metrics.total_checks,
                "successful_checks": metrics.successful_checks,
                "failed_checks": metrics.failed_checks,
                "uptime_percentage": metrics.uptime_percentage,
                "average_response_time": metrics.average_response_time,
                "consecutive_failures": metrics.consecutive_failures,
                "last_successful_check": metrics.last_successful_check,
                "last_failed_check": metrics.last_failed_check,
            },
            "recent_checks": len(recent_checks),
            "active_alerts": len(provider_alerts),
            "current_status": (
                recent_checks[-1].status.value if recent_checks else "unknown"
            ),
        }

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for all providers.

        Returns:
            Dictionary with dashboard data
        """
        async with self._get_lock():
            provider_statuses = {}

            for name in self.providers.keys():
                provider_statuses[name] = await self.get_provider_status(name)

            # Overall system health
            all_statuses = [
                status["current_status"]
                for status in provider_statuses.values()
                if "current_status" in status
            ]

            if not all_statuses:
                overall_health = HealthStatus.UNKNOWN
            elif all(status == "healthy" for status in all_statuses):
                overall_health = HealthStatus.HEALTHY
            elif any(status == "critical" for status in all_statuses):
                overall_health = HealthStatus.CRITICAL
            elif any(status == "unhealthy" for status in all_statuses):
                overall_health = HealthStatus.UNHEALTHY
            else:
                overall_health = HealthStatus.DEGRADED

            # Recent alerts
            recent_alerts = sorted(
                self.active_alerts.values(), key=lambda x: x.timestamp, reverse=True
            )[:10]

            return {
                "overall_health": overall_health.value,
                "total_providers": len(self.providers),
                "healthy_providers": sum(
                    1 for status in all_statuses if status == "healthy"
                ),
                "providers": provider_statuses,
                "recent_alerts": [
                    {
                        "id": alert.id,
                        "timestamp": alert.timestamp,
                        "provider": alert.provider,
                        "severity": alert.severity.value,
                        "message": alert.message,
                        "resolved": alert.resolved,
                    }
                    for alert in recent_alerts
                ],
                "total_health_checks": len(self.health_history),
                "monitoring_active": self._monitoring_task is not None,
            }

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Add a callback function for health alerts.

        Args:
            callback: Function to call when alerts are triggered
        """
        self.alert_callbacks.append(callback)

    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Manually resolve an alert.

        Args:
            alert_id: Alert ID to resolve

        Returns:
            True if alert was resolved, False if not found
        """
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = time.time()
            logger.info(f"Manually resolved alert: {alert_id}")
            return True
        return False

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        logger.info("Health monitoring loop started")

        while True:
            try:
                # Check all providers
                await self.check_all_providers()

                # Cleanup old data periodically
                await self._cleanup_old_data()

                # Wait for next check
                await asyncio.sleep(self.config.check_interval)

            except asyncio.CancelledError:
                logger.info("Health monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.config.check_interval)

    async def _update_metrics(self, result: HealthCheckResult) -> None:
        """Update provider metrics with health check result."""
        async with self._get_lock():
            # Add to history
            self.health_history.append(result)

            # Update provider metrics
            metrics = self.provider_metrics[result.provider]
            metrics.total_checks += 1

            if result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                metrics.successful_checks += 1
                metrics.last_successful_check = result.timestamp
                metrics.consecutive_failures = 0
            else:
                metrics.failed_checks += 1
                metrics.last_failed_check = result.timestamp
                metrics.consecutive_failures += 1

            # Update response times
            metrics.response_times.append(result.response_time)
            if len(metrics.response_times) > 100:  # Keep last 100 response times
                metrics.response_times = metrics.response_times[-100:]

            metrics.average_response_time = sum(metrics.response_times) / len(
                metrics.response_times
            )

            # Update uptime percentage
            if metrics.total_checks > 0:
                metrics.uptime_percentage = (
                    metrics.successful_checks / metrics.total_checks
                ) * 100

            # Check for alerts
            await self._check_alerts(result, metrics)

    async def _check_alerts(
        self, result: HealthCheckResult, metrics: ProviderMetrics
    ) -> None:
        """Check if alerts should be triggered based on health check result."""
        if not self.config.enable_alerts:
            return

        provider = result.provider

        # Check for failure threshold
        if (
            metrics.consecutive_failures >= self.config.failure_threshold
            and result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]
        ):

            alert_key = f"{provider}_consecutive_failures"
            if alert_key not in self.active_alerts:
                await self._create_alert(
                    provider=provider,
                    severity=AlertSeverity.ERROR,
                    message=f"Provider {provider} has {metrics.consecutive_failures} consecutive failures",
                    alert_key=alert_key,
                )

        # Check for recovery
        elif metrics.consecutive_failures == 0 and result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
        ]:

            alert_key = f"{provider}_consecutive_failures"
            if alert_key in self.active_alerts:
                await self._resolve_alert(alert_key)

        # Check for slow response times
        if result.response_time > self.config.response_time_threshold * 2:
            alert_key = f"{provider}_slow_response"
            if alert_key not in self.active_alerts:
                await self._create_alert(
                    provider=provider,
                    severity=AlertSeverity.WARNING,
                    message=f"Provider {provider} has slow response time: {result.response_time:.2f}s",
                    alert_key=alert_key,
                )

    async def _create_alert(
        self, provider: str, severity: AlertSeverity, message: str, alert_key: str
    ) -> None:
        """Create a new alert."""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}_{int(time.time())}"

        alert = HealthAlert(
            id=alert_id,
            timestamp=time.time(),
            provider=provider,
            severity=severity,
            message=message,
        )

        self.active_alerts[alert_key] = alert

        logger.warning(f"Health alert created: {message}")

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    async def _resolve_alert(self, alert_key: str) -> None:
        """Resolve an alert."""
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.resolved = True
            alert.resolved_at = time.time()

            logger.info(f"Health alert resolved: {alert.message}")

            # Remove from active alerts
            del self.active_alerts[alert_key]

    async def _cleanup_old_data(self) -> None:
        """Clean up old health check data."""
        now = time.time()

        # Only cleanup once per hour
        if now - self._last_cleanup < 3600:
            return

        async with self._get_lock():
            # Keep only recent health checks
            if len(self.health_history) > self.config.max_history_size:
                self.health_history = self.health_history[
                    -self.config.max_history_size :
                ]

            # Clean up resolved alerts older than 24 hours
            cutoff_time = now - (24 * 3600)
            resolved_alerts = [
                key
                for key, alert in self.active_alerts.items()
                if alert.resolved
                and alert.resolved_at
                and alert.resolved_at < cutoff_time
            ]

            for key in resolved_alerts:
                del self.active_alerts[key]

            if resolved_alerts:
                logger.info(f"Cleaned up {len(resolved_alerts)} old resolved alerts")

            self._last_cleanup = now

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_monitoring()
