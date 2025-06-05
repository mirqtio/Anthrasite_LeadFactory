"""
GPU Alerting System for LeadFactory.

Monitors GPU infrastructure and sends alerts for critical events.
"""

import asyncio
import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class GPUAlertManager:
    """
    Manages alerts for GPU auto-scaling system.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize the alert manager.

        Args:
            config: Configuration dictionary for alerting
        """
        self.config = config or {}
        self.alert_history: list[dict[str, Any]] = []
        self.alert_cooldowns: dict[str, datetime] = {}

        # Alert thresholds
        self.thresholds = {
            "budget_warning": 0.8,  # 80% of daily budget
            "budget_critical": 0.95,  # 95% of daily budget
            "queue_size_warning": 1500,  # Queue approaching threshold
            "queue_size_critical": 2500,  # Queue well above threshold
            "instance_failure_threshold": 3,  # Failed instances in 1 hour
            "cost_spike_threshold": 2.0,  # 200% of normal hourly cost
        }

        # Cooldown periods (in minutes)
        self.cooldown_periods = {
            "budget_warning": 60,
            "budget_critical": 30,
            "queue_size_warning": 30,
            "queue_size_critical": 15,
            "instance_failure": 30,
            "cost_spike": 45,
        }

    def check_budget_alerts(
        self, current_spend: float, daily_budget: float
    ) -> list[dict[str, Any]]:
        """
        Check for budget-related alerts.

        Args:
            current_spend: Current daily spend
            daily_budget: Daily budget limit

        Returns:
            List of alert dictionaries
        """
        alerts = []
        spend_ratio = current_spend / daily_budget if daily_budget > 0 else 0

        # Critical budget alert
        if spend_ratio >= self.thresholds["budget_critical"]:
            if self._should_send_alert("budget_critical"):
                alerts.append(
                    {
                        "type": "budget_critical",
                        "severity": "critical",
                        "message": f"GPU budget critical: ${current_spend:.2f} / ${daily_budget:.2f} ({spend_ratio:.1%})",
                        "details": {
                            "current_spend": current_spend,
                            "daily_budget": daily_budget,
                            "spend_ratio": spend_ratio,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        # Warning budget alert
        elif spend_ratio >= self.thresholds["budget_warning"]:
            if self._should_send_alert("budget_warning"):
                alerts.append(
                    {
                        "type": "budget_warning",
                        "severity": "warning",
                        "message": f"GPU budget warning: ${current_spend:.2f} / ${daily_budget:.2f} ({spend_ratio:.1%})",
                        "details": {
                            "current_spend": current_spend,
                            "daily_budget": daily_budget,
                            "spend_ratio": spend_ratio,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return alerts

    def check_queue_alerts(self, queue_metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Check for queue-related alerts.

        Args:
            queue_metrics: Queue metrics dictionary

        Returns:
            List of alert dictionaries
        """
        alerts = []
        pending_tasks = queue_metrics.get("pending", 0)

        # Critical queue size alert
        if pending_tasks >= self.thresholds["queue_size_critical"]:
            if self._should_send_alert("queue_size_critical"):
                alerts.append(
                    {
                        "type": "queue_size_critical",
                        "severity": "critical",
                        "message": f"GPU queue critical: {pending_tasks} pending tasks (threshold: 2000)",
                        "details": {
                            "pending_tasks": pending_tasks,
                            "processing_tasks": queue_metrics.get("processing", 0),
                            "eta_minutes": queue_metrics.get("eta", 0) / 60,
                            "growth_rate": queue_metrics.get("growth_rate", 0),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        # Warning queue size alert
        elif pending_tasks >= self.thresholds["queue_size_warning"]:
            if self._should_send_alert("queue_size_warning"):
                alerts.append(
                    {
                        "type": "queue_size_warning",
                        "severity": "warning",
                        "message": f"GPU queue warning: {pending_tasks} pending tasks approaching threshold",
                        "details": {
                            "pending_tasks": pending_tasks,
                            "processing_tasks": queue_metrics.get("processing", 0),
                            "eta_minutes": queue_metrics.get("eta", 0) / 60,
                            "growth_rate": queue_metrics.get("growth_rate", 0),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return alerts

    def check_instance_alerts(
        self, gpu_manager_status: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Check for instance-related alerts.

        Args:
            gpu_manager_status: GPU manager status dictionary

        Returns:
            List of alert dictionaries
        """
        alerts = []
        instances = gpu_manager_status.get("instances", {})

        # Check for failed instances
        failed_instances = [
            instance_id
            for instance_id, instance_data in instances.items()
            if instance_data.get("status") == "failed"
        ]

        if len(failed_instances) >= self.thresholds["instance_failure_threshold"]:
            if self._should_send_alert("instance_failure"):
                alerts.append(
                    {
                        "type": "instance_failure",
                        "severity": "critical",
                        "message": f"Multiple GPU instances failed: {len(failed_instances)} instances",
                        "details": {
                            "failed_instances": failed_instances,
                            "total_instances": len(instances),
                            "active_instances": gpu_manager_status.get(
                                "active_instances", 0
                            ),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return alerts

    def check_cost_alerts(
        self, current_hourly_cost: float, average_hourly_cost: float
    ) -> list[dict[str, Any]]:
        """
        Check for cost spike alerts.

        Args:
            current_hourly_cost: Current hourly cost
            average_hourly_cost: Average hourly cost over last 24h

        Returns:
            List of alert dictionaries
        """
        alerts = []

        if average_hourly_cost > 0:
            cost_ratio = current_hourly_cost / average_hourly_cost

            if cost_ratio >= self.thresholds["cost_spike_threshold"]:
                if self._should_send_alert("cost_spike"):
                    alerts.append(
                        {
                            "type": "cost_spike",
                            "severity": "warning",
                            "message": f"GPU cost spike detected: ${current_hourly_cost:.2f}/hour ({cost_ratio:.1f}x normal)",
                            "details": {
                                "current_hourly_cost": current_hourly_cost,
                                "average_hourly_cost": average_hourly_cost,
                                "cost_ratio": cost_ratio,
                            },
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

        return alerts

    def _should_send_alert(self, alert_type: str) -> bool:
        """
        Check if an alert should be sent based on cooldown periods.

        Args:
            alert_type: Type of alert to check

        Returns:
            True if alert should be sent, False otherwise
        """
        if alert_type not in self.alert_cooldowns:
            return True

        last_sent = self.alert_cooldowns[alert_type]
        cooldown_minutes = self.cooldown_periods.get(alert_type, 60)
        cooldown_period = timedelta(minutes=cooldown_minutes)

        return datetime.utcnow() - last_sent >= cooldown_period

    async def send_alert(self, alert: dict[str, Any]) -> bool:
        """
        Send an alert via configured channels.

        Args:
            alert: Alert dictionary

        Returns:
            True if alert was sent successfully, False otherwise
        """
        try:
            # Record that we're sending this alert
            self.alert_cooldowns[alert["type"]] = datetime.utcnow()
            self.alert_history.append(alert)

            # Keep only last 100 alerts in history
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]

            # Send via configured channels
            success = True

            # Log alert
            logger.warning(
                f"GPU Alert [{alert['severity'].upper()}]: {alert['message']}"
            )

            # Send email if configured
            if self.config.get("email_alerts"):
                email_success = await self._send_email_alert(alert)
                success = success and email_success

            # Send Slack if configured
            if self.config.get("slack_webhook"):
                slack_success = await self._send_slack_alert(alert)
                success = success and slack_success

            return success

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    async def _send_email_alert(self, alert: dict[str, Any]) -> bool:
        """Send alert via email."""
        try:
            email_config = self.config.get("email_alerts", {})

            if not email_config.get("enabled", False):
                return True

            # Create email content
            subject = f"GPU Alert: {alert['type'].replace('_', ' ').title()}"

            f"""
GPU Alert Notification

Type: {alert["type"]}
Severity: {alert["severity"].upper()}
Time: {alert["timestamp"]}

Message: {alert["message"]}

Details:
{json.dumps(alert["details"], indent=2)}

---
LeadFactory GPU Auto-Scaling System
"""

            # Send email (simplified - would need proper SMTP configuration)
            logger.info(f"Would send email alert: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    async def _send_slack_alert(self, alert: dict[str, Any]) -> bool:
        """Send alert via Slack webhook."""
        try:
            # Would implement Slack webhook integration here
            logger.info(f"Would send Slack alert: {alert['type']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def get_alert_summary(self, hours: int = 24) -> dict[str, Any]:
        """
        Get summary of alerts from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Alert summary dictionary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        recent_alerts = [
            alert
            for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00"))
            >= cutoff_time
        ]

        # Count alerts by type and severity
        alert_counts = {}
        severity_counts = {"critical": 0, "warning": 0, "info": 0}

        for alert in recent_alerts:
            alert_type = alert["type"]
            severity = alert["severity"]

            alert_counts[alert_type] = alert_counts.get(alert_type, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "period_hours": hours,
            "total_alerts": len(recent_alerts),
            "alert_counts": alert_counts,
            "severity_counts": severity_counts,
            "recent_alerts": recent_alerts[-10:],  # Last 10 alerts
            "generated_at": datetime.utcnow().isoformat(),
        }


# Global alert manager instance
gpu_alert_manager = GPUAlertManager()


async def check_all_gpu_alerts(gpu_manager) -> list[dict[str, Any]]:
    """
    Check all GPU-related alerts and send notifications.

    Args:
        gpu_manager: GPU manager instance

    Returns:
        List of alerts that were generated
    """
    all_alerts = []

    try:
        # Get current status
        status = gpu_manager.get_status()
        queue_metrics = gpu_manager.queue_metrics
        cost_tracking = gpu_manager.cost_tracking

        # Check budget alerts
        budget_alerts = gpu_alert_manager.check_budget_alerts(
            cost_tracking["current_spend"], cost_tracking["daily_budget"]
        )
        all_alerts.extend(budget_alerts)

        # Check queue alerts
        queue_alerts = gpu_alert_manager.check_queue_alerts(
            {
                "pending": queue_metrics.pending_tasks,
                "processing": queue_metrics.processing_tasks,
                "eta": queue_metrics.estimated_completion_time,
                "growth_rate": queue_metrics.queue_growth_rate,
            }
        )
        all_alerts.extend(queue_alerts)

        # Check instance alerts
        instance_alerts = gpu_alert_manager.check_instance_alerts(status)
        all_alerts.extend(instance_alerts)

        # Send all alerts
        for alert in all_alerts:
            await gpu_alert_manager.send_alert(alert)

        if all_alerts:
            logger.info(f"Generated {len(all_alerts)} GPU alerts")

        return all_alerts

    except Exception as e:
        logger.error(f"Error checking GPU alerts: {e}")
        return []


__all__ = ["GPUAlertManager", "gpu_alert_manager", "check_all_gpu_alerts"]
