#!/usr/bin/env python3
"""
Webhook Health Monitoring and Alerting System.

This module provides real-time monitoring, health checks, and alerting
for webhook processing performance and reliability.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from leadfactory.monitoring.alert_manager import Alert, AlertManager, AlertSeverity
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class MetricType(Enum):
    """Types of webhook metrics."""

    SUCCESS_RATE = "success_rate"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RETRY_RATE = "retry_rate"
    DEAD_LETTER_RATE = "dead_letter_rate"
    CIRCUIT_BREAKER_TRIPS = "circuit_breaker_trips"


@dataclass
class WebhookHealthMetric:
    """Individual webhook health metric."""

    metric_id: str = field(default_factory=lambda: str(uuid4()))
    webhook_name: str = ""
    metric_type: MetricType = MetricType.SUCCESS_RATE
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    time_window_minutes: int = 5
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "metric_id": self.metric_id,
            "webhook_name": self.webhook_name,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "time_window_minutes": self.time_window_minutes,
            "details": self.details,
        }


@dataclass
class WebhookHealthCheck:
    """Health check configuration for a webhook."""

    webhook_name: str
    enabled: bool = True
    check_interval_minutes: int = 5
    success_rate_threshold: float = 0.95  # 95%
    response_time_threshold_ms: float = 1000.0  # 1 second
    error_rate_threshold: float = 0.05  # 5%
    dead_letter_threshold: float = 0.01  # 1%
    throughput_min_per_minute: Optional[float] = None
    consecutive_failures_alert: int = 3
    last_check: Optional[datetime] = None
    current_status: HealthStatus = HealthStatus.HEALTHY
    consecutive_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "webhook_name": self.webhook_name,
            "enabled": self.enabled,
            "check_interval_minutes": self.check_interval_minutes,
            "success_rate_threshold": self.success_rate_threshold,
            "response_time_threshold_ms": self.response_time_threshold_ms,
            "error_rate_threshold": self.error_rate_threshold,
            "dead_letter_threshold": self.dead_letter_threshold,
            "throughput_min_per_minute": self.throughput_min_per_minute,
            "consecutive_failures_alert": self.consecutive_failures_alert,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "current_status": self.current_status.value,
            "consecutive_failures": self.consecutive_failures,
        }


class WebhookMonitor:
    """Real-time webhook health monitoring and alerting."""

    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """Initialize webhook monitor.

        Args:
            alert_manager: Alert manager for notifications
        """
        self.storage = get_storage_instance()
        self.alert_manager = alert_manager or AlertManager()

        # Health checks configuration
        self.health_checks: Dict[str, WebhookHealthCheck] = {}
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Metrics storage (in-memory cache for recent metrics)
        self.metrics_cache: Dict[str, List[WebhookHealthMetric]] = {}
        self.cache_max_age_minutes = 60
        self.cache_max_items_per_webhook = 100

        # Setup default health checks
        self._setup_default_health_checks()

        logger.info("Initialized WebhookMonitor")

    def _setup_default_health_checks(self):
        """Setup default health checks for common webhooks."""
        default_configs = [
            # Critical payment webhooks
            WebhookHealthCheck(
                webhook_name="stripe",
                success_rate_threshold=0.99,  # 99% for payments
                response_time_threshold_ms=500.0,  # 500ms for payments
                error_rate_threshold=0.01,  # 1% error rate
                dead_letter_threshold=0.005,  # 0.5% dead letter rate
                consecutive_failures_alert=2,  # Alert after 2 failures
            ),
            WebhookHealthCheck(
                webhook_name="paypal",
                success_rate_threshold=0.99,
                response_time_threshold_ms=500.0,
                error_rate_threshold=0.01,
                dead_letter_threshold=0.005,
                consecutive_failures_alert=2,
            ),
            # Email service webhooks
            WebhookHealthCheck(
                webhook_name="sendgrid",
                success_rate_threshold=0.95,  # 95% for email
                response_time_threshold_ms=1000.0,  # 1s for email
                error_rate_threshold=0.05,  # 5% error rate
                dead_letter_threshold=0.02,  # 2% dead letter rate
                consecutive_failures_alert=3,
            ),
            WebhookHealthCheck(
                webhook_name="mailgun",
                success_rate_threshold=0.95,
                response_time_threshold_ms=1000.0,
                error_rate_threshold=0.05,
                dead_letter_threshold=0.02,
                consecutive_failures_alert=3,
            ),
            # Engagement tracking webhook
            WebhookHealthCheck(
                webhook_name="engagement",
                success_rate_threshold=0.90,  # 90% for analytics
                response_time_threshold_ms=2000.0,  # 2s for analytics
                error_rate_threshold=0.10,  # 10% error rate
                dead_letter_threshold=0.05,  # 5% dead letter rate
                consecutive_failures_alert=5,
            ),
        ]

        for config in default_configs:
            self.register_health_check(config)

    def register_health_check(self, health_check: WebhookHealthCheck):
        """Register a health check configuration.

        Args:
            health_check: Health check configuration
        """
        self.health_checks[health_check.webhook_name] = health_check
        logger.info(f"Registered health check for webhook: {health_check.webhook_name}")

    def start_monitoring(self):
        """Start the monitoring loop."""
        if self.monitoring_active:
            logger.warning("Monitoring is already active")
            return

        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started webhook health monitoring")

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("Stopped webhook health monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        try:
            while self.monitoring_active:
                # Check each registered webhook
                for webhook_name, health_check in self.health_checks.items():
                    if not health_check.enabled:
                        continue

                    # Check if it's time for a health check
                    if self._should_run_health_check(health_check):
                        try:
                            await self._perform_health_check(health_check)
                        except Exception as e:
                            logger.error(
                                f"Error in health check for {webhook_name}: {e}"
                            )

                # Clean up old metrics from cache
                self._cleanup_metrics_cache()

                # Wait before next iteration
                await asyncio.sleep(60)  # Check every minute

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")

    def _should_run_health_check(self, health_check: WebhookHealthCheck) -> bool:
        """Determine if health check should run."""
        if not health_check.last_check:
            return True

        time_since_last_check = datetime.utcnow() - health_check.last_check
        return time_since_last_check.total_seconds() >= (
            health_check.check_interval_minutes * 60
        )

    async def _perform_health_check(self, health_check: WebhookHealthCheck):
        """Perform health check for a webhook."""
        webhook_name = health_check.webhook_name
        logger.debug(f"Performing health check for webhook: {webhook_name}")

        try:
            # Calculate metrics for the time window
            time_window_minutes = health_check.check_interval_minutes
            metrics = await self._calculate_webhook_metrics(
                webhook_name, time_window_minutes
            )

            # Store metrics
            self._store_metrics(webhook_name, metrics)

            # Evaluate health status
            old_status = health_check.current_status
            new_status = self._evaluate_health_status(health_check, metrics)

            # Update health check
            health_check.last_check = datetime.utcnow()
            health_check.current_status = new_status

            # Track consecutive failures
            if new_status in [HealthStatus.CRITICAL, HealthStatus.DOWN]:
                health_check.consecutive_failures += 1
            else:
                health_check.consecutive_failures = 0

            # Check if we need to send alerts
            if old_status != new_status or self._should_alert_consecutive_failures(
                health_check
            ):
                await self._send_health_alert(health_check, metrics, old_status)

            # Update in storage
            self.storage.update_webhook_health_check(
                webhook_name, health_check.to_dict()
            )

            logger.debug(
                f"Health check completed for {webhook_name}: {new_status.value} "
                f"(consecutive failures: {health_check.consecutive_failures})"
            )

        except Exception as e:
            logger.error(f"Error performing health check for {webhook_name}: {e}")
            # Mark as down if we can't perform health check
            health_check.current_status = HealthStatus.DOWN
            health_check.consecutive_failures += 1

    async def _calculate_webhook_metrics(
        self, webhook_name: str, time_window_minutes: int
    ) -> List[WebhookHealthMetric]:
        """Calculate health metrics for a webhook."""
        metrics = []
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_window_minutes)

        try:
            # Get webhook events in time window
            events = self.storage.get_webhook_events(
                webhook_name=webhook_name,
                start_time=start_time,
                end_time=end_time,
            )

            if not events:
                # No events in time window - this might be normal or concerning
                metrics.append(
                    WebhookHealthMetric(
                        webhook_name=webhook_name,
                        metric_type=MetricType.THROUGHPUT,
                        value=0.0,
                        time_window_minutes=time_window_minutes,
                        details={"total_events": 0},
                    )
                )
                return metrics

            total_events = len(events)
            successful_events = len(
                [e for e in events if e.get("status") == "completed"]
            )
            failed_events = len([e for e in events if e.get("status") == "failed"])
            retry_events = len([e for e in events if e.get("retry_count", 0) > 0])
            dead_letter_events = len(
                [e for e in events if e.get("status") == "dead_letter"]
            )

            # Calculate success rate
            success_rate = successful_events / total_events if total_events > 0 else 0.0
            metrics.append(
                WebhookHealthMetric(
                    webhook_name=webhook_name,
                    metric_type=MetricType.SUCCESS_RATE,
                    value=success_rate,
                    time_window_minutes=time_window_minutes,
                    details={
                        "successful_events": successful_events,
                        "total_events": total_events,
                    },
                )
            )

            # Calculate error rate
            error_rate = failed_events / total_events if total_events > 0 else 0.0
            metrics.append(
                WebhookHealthMetric(
                    webhook_name=webhook_name,
                    metric_type=MetricType.ERROR_RATE,
                    value=error_rate,
                    time_window_minutes=time_window_minutes,
                    details={
                        "failed_events": failed_events,
                        "total_events": total_events,
                    },
                )
            )

            # Calculate retry rate
            retry_rate = retry_events / total_events if total_events > 0 else 0.0
            metrics.append(
                WebhookHealthMetric(
                    webhook_name=webhook_name,
                    metric_type=MetricType.RETRY_RATE,
                    value=retry_rate,
                    time_window_minutes=time_window_minutes,
                    details={
                        "retry_events": retry_events,
                        "total_events": total_events,
                    },
                )
            )

            # Calculate dead letter rate
            dead_letter_rate = (
                dead_letter_events / total_events if total_events > 0 else 0.0
            )
            metrics.append(
                WebhookHealthMetric(
                    webhook_name=webhook_name,
                    metric_type=MetricType.DEAD_LETTER_RATE,
                    value=dead_letter_rate,
                    time_window_minutes=time_window_minutes,
                    details={
                        "dead_letter_events": dead_letter_events,
                        "total_events": total_events,
                    },
                )
            )

            # Calculate throughput (events per minute)
            throughput = total_events / time_window_minutes
            metrics.append(
                WebhookHealthMetric(
                    webhook_name=webhook_name,
                    metric_type=MetricType.THROUGHPUT,
                    value=throughput,
                    time_window_minutes=time_window_minutes,
                    details={"total_events": total_events},
                )
            )

            # Calculate average response time (if available)
            processing_times = []
            for event in events:
                if event.get("processed_at") and event.get("timestamp"):
                    try:
                        start = datetime.fromisoformat(event["timestamp"])
                        end = datetime.fromisoformat(event["processed_at"])
                        processing_time = (
                            end - start
                        ).total_seconds() * 1000  # Convert to ms
                        processing_times.append(processing_time)
                    except (ValueError, TypeError):
                        continue

            if processing_times:
                avg_response_time = sum(processing_times) / len(processing_times)
                metrics.append(
                    WebhookHealthMetric(
                        webhook_name=webhook_name,
                        metric_type=MetricType.RESPONSE_TIME,
                        value=avg_response_time,
                        time_window_minutes=time_window_minutes,
                        details={
                            "avg_response_time_ms": avg_response_time,
                            "min_response_time_ms": min(processing_times),
                            "max_response_time_ms": max(processing_times),
                            "sample_size": len(processing_times),
                        },
                    )
                )

            return metrics

        except Exception as e:
            logger.error(f"Error calculating metrics for {webhook_name}: {e}")
            return []

    def _store_metrics(self, webhook_name: str, metrics: List[WebhookHealthMetric]):
        """Store metrics in cache and persistent storage."""
        try:
            # Store in cache
            if webhook_name not in self.metrics_cache:
                self.metrics_cache[webhook_name] = []

            self.metrics_cache[webhook_name].extend(metrics)

            # Limit cache size
            if len(self.metrics_cache[webhook_name]) > self.cache_max_items_per_webhook:
                self.metrics_cache[webhook_name] = self.metrics_cache[webhook_name][
                    -self.cache_max_items_per_webhook :
                ]

            # Store in persistent storage
            for metric in metrics:
                self.storage.store_webhook_metric(metric.to_dict())

        except Exception as e:
            logger.error(f"Error storing metrics for {webhook_name}: {e}")

    def _evaluate_health_status(
        self, health_check: WebhookHealthCheck, metrics: List[WebhookHealthMetric]
    ) -> HealthStatus:
        """Evaluate health status based on metrics and thresholds."""
        try:
            # Convert metrics to lookup dictionary
            metric_lookup = {metric.metric_type: metric for metric in metrics}

            # Check critical thresholds first
            critical_issues = []
            warning_issues = []

            # Check success rate
            success_metric = metric_lookup.get(MetricType.SUCCESS_RATE)
            if (
                success_metric
                and success_metric.value < health_check.success_rate_threshold
            ):
                if success_metric.value < (
                    health_check.success_rate_threshold - 0.1
                ):  # 10% below threshold
                    critical_issues.append(f"Success rate: {success_metric.value:.2%}")
                else:
                    warning_issues.append(f"Success rate: {success_metric.value:.2%}")

            # Check error rate
            error_metric = metric_lookup.get(MetricType.ERROR_RATE)
            if error_metric and error_metric.value > health_check.error_rate_threshold:
                if error_metric.value > (
                    health_check.error_rate_threshold * 2
                ):  # Double the threshold
                    critical_issues.append(f"Error rate: {error_metric.value:.2%}")
                else:
                    warning_issues.append(f"Error rate: {error_metric.value:.2%}")

            # Check dead letter rate
            dl_metric = metric_lookup.get(MetricType.DEAD_LETTER_RATE)
            if dl_metric and dl_metric.value > health_check.dead_letter_threshold:
                if dl_metric.value > (health_check.dead_letter_threshold * 2):
                    critical_issues.append(f"Dead letter rate: {dl_metric.value:.2%}")
                else:
                    warning_issues.append(f"Dead letter rate: {dl_metric.value:.2%}")

            # Check response time
            response_metric = metric_lookup.get(MetricType.RESPONSE_TIME)
            if (
                response_metric
                and response_metric.value > health_check.response_time_threshold_ms
            ):
                if response_metric.value > (
                    health_check.response_time_threshold_ms * 2
                ):
                    critical_issues.append(
                        f"Response time: {response_metric.value:.0f}ms"
                    )
                else:
                    warning_issues.append(
                        f"Response time: {response_metric.value:.0f}ms"
                    )

            # Check minimum throughput (if configured)
            throughput_metric = metric_lookup.get(MetricType.THROUGHPUT)
            if (
                health_check.throughput_min_per_minute
                and throughput_metric
                and throughput_metric.value < health_check.throughput_min_per_minute
            ):
                warning_issues.append(
                    f"Low throughput: {throughput_metric.value:.1f} events/min"
                )

            # Determine overall status
            if critical_issues:
                return HealthStatus.CRITICAL
            elif warning_issues:
                return HealthStatus.WARNING
            else:
                return HealthStatus.HEALTHY

        except Exception as e:
            logger.error(f"Error evaluating health status: {e}")
            return HealthStatus.DOWN

    def _should_alert_consecutive_failures(
        self, health_check: WebhookHealthCheck
    ) -> bool:
        """Check if we should alert due to consecutive failures."""
        return (
            health_check.consecutive_failures >= health_check.consecutive_failures_alert
            and health_check.consecutive_failures
            % health_check.consecutive_failures_alert
            == 0
        )

    async def _send_health_alert(
        self,
        health_check: WebhookHealthCheck,
        metrics: List[WebhookHealthMetric],
        old_status: HealthStatus,
    ):
        """Send health alert for status change or consecutive failures."""
        try:
            webhook_name = health_check.webhook_name
            new_status = health_check.current_status

            # Determine alert severity
            if new_status == HealthStatus.CRITICAL:
                severity = AlertSeverity.CRITICAL
            elif new_status == HealthStatus.DOWN:
                severity = AlertSeverity.CRITICAL
            elif new_status == HealthStatus.WARNING:
                severity = AlertSeverity.MEDIUM
            else:
                severity = AlertSeverity.LOW

            # Build alert message
            if old_status != new_status:
                message = (
                    f"Webhook {webhook_name} health status changed from "
                    f"{old_status.value} to {new_status.value}"
                )
            else:
                message = (
                    f"Webhook {webhook_name} has {health_check.consecutive_failures} "
                    f"consecutive health check failures"
                )

            # Add metric details
            metric_details = {}
            for metric in metrics:
                metric_details[metric.metric_type.value] = {
                    "value": metric.value,
                    "details": metric.details,
                }

            # Create alert
            alert = Alert(
                rule_name=f"webhook_health_{webhook_name}",
                severity=severity,
                message=message,
                current_value=health_check.consecutive_failures,
                threshold_value=health_check.consecutive_failures_alert,
                timestamp=datetime.utcnow(),
                metadata={
                    "webhook_name": webhook_name,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "consecutive_failures": health_check.consecutive_failures,
                    "metrics": metric_details,
                },
            )

            # Send alert
            self.alert_manager._send_alert_notifications(alert)

            logger.warning(f"Sent health alert for webhook {webhook_name}: {message}")

        except Exception as e:
            logger.error(f"Error sending health alert: {e}")

    def _cleanup_metrics_cache(self):
        """Clean up old metrics from cache."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(
                minutes=self.cache_max_age_minutes
            )

            for webhook_name in list(self.metrics_cache.keys()):
                # Filter out old metrics
                self.metrics_cache[webhook_name] = [
                    metric
                    for metric in self.metrics_cache[webhook_name]
                    if metric.timestamp > cutoff_time
                ]

                # Remove empty entries
                if not self.metrics_cache[webhook_name]:
                    del self.metrics_cache[webhook_name]

        except Exception as e:
            logger.error(f"Error cleaning up metrics cache: {e}")

    def get_webhook_health(self, webhook_name: str) -> Optional[Dict[str, Any]]:
        """Get current health status for a webhook.

        Args:
            webhook_name: Name of the webhook

        Returns:
            Health status dictionary or None if not found
        """
        try:
            health_check = self.health_checks.get(webhook_name)
            if not health_check:
                return None

            # Get recent metrics from cache
            recent_metrics = self.metrics_cache.get(webhook_name, [])

            # Convert metrics to dictionary format
            metrics_data = {}
            for metric in recent_metrics[-10:]:  # Last 10 metrics
                metric_type = metric.metric_type.value
                if metric_type not in metrics_data:
                    metrics_data[metric_type] = []
                metrics_data[metric_type].append(
                    {
                        "value": metric.value,
                        "timestamp": metric.timestamp.isoformat(),
                        "details": metric.details,
                    }
                )

            return {
                "webhook_name": webhook_name,
                "status": health_check.current_status.value,
                "last_check": (
                    health_check.last_check.isoformat()
                    if health_check.last_check
                    else None
                ),
                "consecutive_failures": health_check.consecutive_failures,
                "thresholds": {
                    "success_rate": health_check.success_rate_threshold,
                    "error_rate": health_check.error_rate_threshold,
                    "response_time_ms": health_check.response_time_threshold_ms,
                    "dead_letter_rate": health_check.dead_letter_threshold,
                },
                "recent_metrics": metrics_data,
            }

        except Exception as e:
            logger.error(f"Error getting webhook health for {webhook_name}: {e}")
            return None

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall health status across all webhooks.

        Returns:
            Overall health status dictionary
        """
        try:
            health_data = {
                "overall_status": HealthStatus.HEALTHY.value,
                "total_webhooks": len(self.health_checks),
                "webhooks_by_status": {},
                "webhooks": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

            worst_status = HealthStatus.HEALTHY
            status_counts = {status.value: 0 for status in HealthStatus}

            for webhook_name, health_check in self.health_checks.items():
                if not health_check.enabled:
                    continue

                current_status = health_check.current_status
                status_counts[current_status.value] += 1

                # Track worst status
                if current_status.value == HealthStatus.DOWN.value:
                    worst_status = HealthStatus.DOWN
                elif (
                    current_status.value == HealthStatus.CRITICAL.value
                    and worst_status != HealthStatus.DOWN
                ):
                    worst_status = HealthStatus.CRITICAL
                elif (
                    current_status.value == HealthStatus.WARNING.value
                    and worst_status == HealthStatus.HEALTHY
                ):
                    worst_status = HealthStatus.WARNING

                # Get individual webhook health
                webhook_health = self.get_webhook_health(webhook_name)
                if webhook_health:
                    health_data["webhooks"][webhook_name] = webhook_health

            health_data["overall_status"] = worst_status.value
            health_data["webhooks_by_status"] = status_counts

            return health_data

        except Exception as e:
            logger.error(f"Error getting overall health: {e}")
            return {"error": str(e)}

    def update_health_check(self, webhook_name: str, **kwargs) -> bool:
        """Update health check configuration.

        Args:
            webhook_name: Name of the webhook
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        try:
            health_check = self.health_checks.get(webhook_name)
            if not health_check:
                logger.error(f"Health check not found for webhook: {webhook_name}")
                return False

            # Update fields
            for field, value in kwargs.items():
                if hasattr(health_check, field):
                    setattr(health_check, field, value)
                else:
                    logger.warning(f"Unknown health check field: {field}")

            # Update in storage
            self.storage.update_webhook_health_check(
                webhook_name, health_check.to_dict()
            )

            logger.info(f"Updated health check for webhook: {webhook_name}")
            return True

        except Exception as e:
            logger.error(f"Error updating health check for {webhook_name}: {e}")
            return False

    def get_metrics_history(
        self,
        webhook_name: str,
        metric_type: MetricType,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get historical metrics for a webhook.

        Args:
            webhook_name: Name of the webhook
            metric_type: Type of metric to retrieve
            hours: Number of hours of history to retrieve

        Returns:
            List of historical metrics
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            # Get from storage
            metrics = self.storage.get_webhook_metrics(
                webhook_name=webhook_name,
                metric_type=metric_type.value,
                start_time=start_time,
                end_time=end_time,
            )

            return [
                {
                    "value": metric["value"],
                    "timestamp": metric["timestamp"],
                    "details": metric.get("details", {}),
                }
                for metric in metrics
            ]

        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return []
