"""
Purchase Monitoring and Dashboard
================================

This module provides comprehensive monitoring and dashboard functionality for purchase metrics,
integrating with the existing financial tracking, metrics aggregation, and alerting systems.
It serves as the main interface for real-time purchase monitoring and analytics.
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.cost.financial_tracking import TransactionType, financial_tracker
from leadfactory.cost.purchase_metrics import purchase_metrics_tracker
from leadfactory.monitoring.alert_manager import AlertSeverity, alert_manager
from leadfactory.monitoring.metrics_aggregator import (
    AggregatedMetric,
    AggregationPeriod,
    metrics_aggregator,
)
from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import PURCHASES_TOTAL, REVENUE_TOTAL, record_metric

logger = get_logger(__name__)


class MonitoringPeriod(Enum):
    """Monitoring time periods."""

    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class PurchaseKPI:
    """Key Performance Indicator for purchase metrics."""

    name: str
    value: Union[int, float]
    unit: str
    change_percentage: Optional[float] = None
    trend: Optional[str] = None  # "up", "down", "stable"
    target: Optional[Union[int, float]] = None


@dataclass
class DashboardData:
    """Dashboard data structure containing all purchase monitoring information."""

    timestamp: datetime
    period: MonitoringPeriod
    kpis: List[PurchaseKPI]
    revenue_breakdown: Dict[str, Any]
    conversion_metrics: Dict[str, Any]
    alert_summary: Dict[str, Any]
    recent_transactions: List[Dict[str, Any]]
    performance_trends: Dict[str, List[Dict[str, Any]]]


class PurchaseMonitor:
    """Comprehensive purchase monitoring and dashboard system."""

    def __init__(
        self,
        update_interval_seconds: int = 300,  # 5 minutes
        enable_realtime_alerts: bool = True,
    ):
        """Initialize purchase monitor.

        Args:
            update_interval_seconds: How often to update metrics and check alerts
            enable_realtime_alerts: Whether to enable real-time alerting
        """
        self.update_interval = update_interval_seconds
        self.enable_realtime_alerts = enable_realtime_alerts
        self.logger = get_logger(f"{__name__}.PurchaseMonitor")

        # Component references
        self.metrics_tracker = purchase_metrics_tracker
        self.financial_tracker = financial_tracker
        self.metrics_aggregator = metrics_aggregator
        self.alert_manager = alert_manager

        # Monitoring state
        self.is_running = False
        self.last_update = None
        self._monitoring_task = None

        self.logger.info("Purchase monitor initialized")

    async def start_monitoring(self):
        """Start the continuous monitoring process."""
        if self.is_running:
            self.logger.warning("Purchase monitoring is already running")
            return

        self.is_running = True
        self.logger.info(
            f"Starting purchase monitoring (update interval: {self.update_interval}s)"
        )

        # Start the monitoring loop
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop the continuous monitoring process."""
        if not self.is_running:
            return

        self.is_running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Purchase monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop that runs continuously."""
        while self.is_running:
            try:
                # Update aggregated metrics
                await self._update_metrics()

                # Check alerts
                if self.enable_realtime_alerts:
                    self.alert_manager.check_alerts()

                # Update last update timestamp
                self.last_update = datetime.now()

                # Wait for next interval
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _update_metrics(self):
        """Update aggregated metrics for all time periods."""
        try:
            # Aggregate metrics for different periods
            for period in [AggregationPeriod.HOURLY, AggregationPeriod.DAILY]:
                metrics = self.metrics_aggregator.aggregate_metrics(period)
                if metrics:
                    self.metrics_aggregator.store_aggregated_metrics(metrics)

            self.logger.debug("Metrics updated successfully")

        except Exception as e:
            self.logger.error(f"Failed to update metrics: {e}")

    def get_dashboard_data(
        self, period: MonitoringPeriod = MonitoringPeriod.DAILY, lookback_days: int = 30
    ) -> DashboardData:
        """Get comprehensive dashboard data for purchase monitoring.

        Args:
            period: Time period for aggregation
            lookback_days: How many days to look back for trends

        Returns:
            Complete dashboard data
        """
        try:
            timestamp = datetime.now()

            # Map monitoring period to aggregation period
            agg_period_map = {
                MonitoringPeriod.HOURLY: AggregationPeriod.HOURLY,
                MonitoringPeriod.DAILY: AggregationPeriod.DAILY,
                MonitoringPeriod.WEEKLY: AggregationPeriod.WEEKLY,
                MonitoringPeriod.MONTHLY: AggregationPeriod.MONTHLY,
            }

            agg_period = agg_period_map.get(period, AggregationPeriod.DAILY)

            # Get KPIs
            kpis = self._calculate_kpis(agg_period, lookback_days)

            # Get revenue breakdown
            revenue_breakdown = self._get_revenue_breakdown(agg_period)

            # Get conversion metrics
            conversion_metrics = self._get_conversion_metrics()

            # Get alert summary
            alert_summary = self.alert_manager.get_alert_status()

            # Get recent transactions
            recent_transactions = self._get_recent_transactions()

            # Get performance trends
            performance_trends = self._get_performance_trends(agg_period, lookback_days)

            dashboard_data = DashboardData(
                timestamp=timestamp,
                period=period,
                kpis=kpis,
                revenue_breakdown=revenue_breakdown,
                conversion_metrics=conversion_metrics,
                alert_summary=alert_summary,
                recent_transactions=recent_transactions,
                performance_trends=performance_trends,
            )

            self.logger.debug(f"Generated dashboard data for {period.value}")
            return dashboard_data

        except Exception as e:
            self.logger.error(f"Failed to generate dashboard data: {e}")
            # Return minimal dashboard data in case of error
            return DashboardData(
                timestamp=datetime.now(),
                period=period,
                kpis=[],
                revenue_breakdown={},
                conversion_metrics={},
                alert_summary={"error": str(e)},
                recent_transactions=[],
                performance_trends={},
            )

    def _calculate_kpis(
        self, period: AggregationPeriod, lookback_days: int
    ) -> List[PurchaseKPI]:
        """Calculate key performance indicators."""
        kpis = []

        try:
            # Get recent metrics for comparison
            current_metrics = self.metrics_aggregator.get_aggregated_metrics(
                period, limit=lookback_days
            )

            if not current_metrics:
                return kpis

            latest = current_metrics[0]
            previous = current_metrics[1] if len(current_metrics) > 1 else None

            # Total Revenue KPI
            revenue_change = None
            if previous and previous.total_revenue_cents > 0:
                revenue_change = (
                    (latest.total_revenue_cents - previous.total_revenue_cents)
                    / previous.total_revenue_cents
                ) * 100

            kpis.append(
                PurchaseKPI(
                    name="Total Revenue",
                    value=latest.total_revenue_cents / 100,  # Convert to dollars
                    unit="USD",
                    change_percentage=revenue_change,
                    trend=(
                        "up"
                        if revenue_change and revenue_change > 0
                        else "down" if revenue_change else "stable"
                    ),
                )
            )

            # Total Purchases KPI
            purchases_change = None
            if previous and previous.total_purchases > 0:
                purchases_change = (
                    (latest.total_purchases - previous.total_purchases)
                    / previous.total_purchases
                ) * 100

            kpis.append(
                PurchaseKPI(
                    name="Total Purchases",
                    value=latest.total_purchases,
                    unit="purchases",
                    change_percentage=purchases_change,
                    trend=(
                        "up"
                        if purchases_change and purchases_change > 0
                        else "down" if purchases_change else "stable"
                    ),
                )
            )

            # Average Order Value KPI
            aov_change = None
            if previous and previous.average_order_value_cents > 0:
                aov_change = (
                    (
                        latest.average_order_value_cents
                        - previous.average_order_value_cents
                    )
                    / previous.average_order_value_cents
                ) * 100

            kpis.append(
                PurchaseKPI(
                    name="Average Order Value",
                    value=latest.average_order_value_cents / 100,  # Convert to dollars
                    unit="USD",
                    change_percentage=aov_change,
                    trend=(
                        "up"
                        if aov_change and aov_change > 0
                        else "down" if aov_change else "stable"
                    ),
                )
            )

            # Conversion Rate KPI
            conversion_change = None
            if previous and previous.conversion_rate > 0:
                conversion_change = (
                    (latest.conversion_rate - previous.conversion_rate)
                    / previous.conversion_rate
                ) * 100

            kpis.append(
                PurchaseKPI(
                    name="Conversion Rate",
                    value=latest.conversion_rate * 100,  # Convert to percentage
                    unit="%",
                    change_percentage=conversion_change,
                    trend=(
                        "up"
                        if conversion_change and conversion_change > 0
                        else "down" if conversion_change else "stable"
                    ),
                    target=2.0,  # 2% target conversion rate
                )
            )

            # Stripe Fee Percentage KPI
            fee_percentage = 0
            if latest.total_revenue_cents > 0:
                fee_percentage = (
                    latest.total_stripe_fees_cents / latest.total_revenue_cents
                ) * 100

            kpis.append(
                PurchaseKPI(
                    name="Stripe Fee Rate",
                    value=fee_percentage,
                    unit="%",
                    target=3.0,  # Target to keep fees under 3%
                )
            )

        except Exception as e:
            self.logger.error(f"Failed to calculate KPIs: {e}")

        return kpis

    def _get_revenue_breakdown(self, period: AggregationPeriod) -> Dict[str, Any]:
        """Get revenue breakdown by audit type and other dimensions."""
        try:
            metrics = self.metrics_aggregator.get_aggregated_metrics(period, limit=30)

            breakdown = {
                "by_audit_type": {},
                "total_revenue_cents": 0,
                "total_stripe_fees_cents": 0,
                "net_revenue_cents": 0,
            }

            for metric in metrics:
                breakdown["total_revenue_cents"] += metric.total_revenue_cents
                breakdown["total_stripe_fees_cents"] += metric.total_stripe_fees_cents

                # Aggregate by audit type
                for audit_type, data in metric.audit_type_breakdown.items():
                    if audit_type not in breakdown["by_audit_type"]:
                        breakdown["by_audit_type"][audit_type] = {
                            "revenue_cents": 0,
                            "purchases": 0,
                        }

                    breakdown["by_audit_type"][audit_type]["revenue_cents"] += data[
                        "revenue_cents"
                    ]
                    breakdown["by_audit_type"][audit_type]["purchases"] += data[
                        "purchases"
                    ]

            breakdown["net_revenue_cents"] = (
                breakdown["total_revenue_cents"] - breakdown["total_stripe_fees_cents"]
            )

            return breakdown

        except Exception as e:
            self.logger.error(f"Failed to get revenue breakdown: {e}")
            return {}

    def _get_conversion_metrics(self) -> Dict[str, Any]:
        """Get conversion funnel metrics."""
        try:
            # Get conversion metrics from purchase tracker
            conversion_data = self.metrics_tracker.get_conversion_metrics()

            return {
                "conversion_funnel": conversion_data,
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get conversion metrics: {e}")
            return {}

    def _get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transactions for display."""
        try:
            # Get recent transactions from financial tracker
            summary = self.financial_tracker.get_transaction_summary(
                limit=limit, transaction_type=TransactionType.PAYMENT
            )

            return summary.get("transactions", [])

        except Exception as e:
            self.logger.error(f"Failed to get recent transactions: {e}")
            return []

    def _get_performance_trends(
        self, period: AggregationPeriod, lookback_days: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get performance trends over time."""
        try:
            metrics = self.metrics_aggregator.get_aggregated_metrics(
                period, limit=lookback_days
            )

            trends = {
                "revenue_trend": [],
                "purchases_trend": [],
                "conversion_trend": [],
                "aov_trend": [],
            }

            for metric in reversed(metrics):  # Reverse to get chronological order
                timestamp = metric.timestamp.isoformat()

                trends["revenue_trend"].append(
                    {"timestamp": timestamp, "value": metric.total_revenue_cents / 100}
                )

                trends["purchases_trend"].append(
                    {"timestamp": timestamp, "value": metric.total_purchases}
                )

                trends["conversion_trend"].append(
                    {"timestamp": timestamp, "value": metric.conversion_rate * 100}
                )

                trends["aov_trend"].append(
                    {
                        "timestamp": timestamp,
                        "value": metric.average_order_value_cents / 100,
                    }
                )

            return trends

        except Exception as e:
            self.logger.error(f"Failed to get performance trends: {e}")
            return {}

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring system status.

        Returns:
            Status information about the monitoring system
        """
        return {
            "is_running": self.is_running,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "update_interval_seconds": self.update_interval,
            "realtime_alerts_enabled": self.enable_realtime_alerts,
            "alert_manager_status": self.alert_manager.get_alert_status(),
            "metrics_summary": self.metrics_aggregator.get_metrics_summary(),
        }

    def trigger_manual_update(self):
        """Manually trigger metrics update and alert check."""
        try:
            # Update metrics synchronously
            for period in [AggregationPeriod.HOURLY, AggregationPeriod.DAILY]:
                metrics = self.metrics_aggregator.aggregate_metrics(period)
                if metrics:
                    self.metrics_aggregator.store_aggregated_metrics(metrics)

            # Check alerts
            self.alert_manager.check_alerts()

            self.last_update = datetime.now()
            self.logger.info("Manual update completed successfully")

        except Exception as e:
            self.logger.error(f"Manual update failed: {e}")
            raise

    def export_dashboard_data(
        self,
        period: MonitoringPeriod = MonitoringPeriod.DAILY,
        format_type: str = "json",
    ) -> str:
        """Export dashboard data in specified format.

        Args:
            period: Time period for data
            format_type: Export format ('json', 'csv')

        Returns:
            Exported data as string
        """
        dashboard_data = self.get_dashboard_data(period)

        if format_type.lower() == "json":
            # Convert dashboard_data to dict for JSON serialization
            data_dict = {
                "timestamp": dashboard_data.timestamp.isoformat(),
                "period": dashboard_data.period.value,
                "kpis": [
                    {
                        "name": kpi.name,
                        "value": kpi.value,
                        "unit": kpi.unit,
                        "change_percentage": kpi.change_percentage,
                        "trend": kpi.trend,
                        "target": kpi.target,
                    }
                    for kpi in dashboard_data.kpis
                ],
                "revenue_breakdown": dashboard_data.revenue_breakdown,
                "conversion_metrics": dashboard_data.conversion_metrics,
                "alert_summary": dashboard_data.alert_summary,
                "recent_transactions": dashboard_data.recent_transactions,
                "performance_trends": dashboard_data.performance_trends,
            }

            return json.dumps(data_dict, indent=2, default=str)

        elif format_type.lower() == "csv":
            # Simple CSV export of KPIs
            csv_lines = ["Name,Value,Unit,Change %,Trend,Target"]
            for kpi in dashboard_data.kpis:
                csv_lines.append(
                    f"{kpi.name},{kpi.value},{kpi.unit},"
                    f"{kpi.change_percentage or ''},"
                    f"{kpi.trend or ''},"
                    f"{kpi.target or ''}"
                )
            return "\n".join(csv_lines)

        else:
            raise ValueError(f"Unsupported export format: {format_type}")


# Global instance
purchase_monitor = PurchaseMonitor()
