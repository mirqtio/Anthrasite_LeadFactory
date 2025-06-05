"""
Tests for Purchase Monitoring System
===================================

Tests for the comprehensive purchase monitoring and dashboard functionality.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.monitoring.metrics_aggregator import (
    AggregatedMetric,
    AggregationPeriod,
)
from leadfactory.monitoring.purchase_monitoring import (
    DashboardData,
    MonitoringPeriod,
    PurchaseKPI,
    PurchaseMonitor,
)


class TestPurchaseMonitor:
    """Test purchase monitoring functionality."""

    @pytest.fixture
    def mock_metrics_tracker(self):
        """Mock metrics tracker."""
        mock = Mock()
        mock.get_purchase_analytics_summary.return_value = {
            "timestamp": datetime.now().isoformat(),
            "daily_metrics": {"total_revenue_cents": 10000},
            "monthly_metrics": {"total_revenue_cents": 50000},
        }
        return mock

    @pytest.fixture
    def mock_financial_tracker(self):
        """Mock financial tracker."""
        mock = Mock()
        mock.get_transaction_summary.return_value = {
            "transactions": [
                {
                    "transaction_id": "txn_123",
                    "gross_amount_cents": 5000,
                    "audit_type": "basic",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }
        return mock

    @pytest.fixture
    def mock_metrics_aggregator(self):
        """Mock metrics aggregator."""
        mock = Mock()

        # Create mock aggregated metrics
        mock_metric = AggregatedMetric(
            period=AggregationPeriod.DAILY,
            timestamp=datetime.now(),
            total_purchases=10,
            total_revenue_cents=50000,
            total_stripe_fees_cents=1500,
            average_order_value_cents=5000,
            conversion_rate=0.025,
            refund_count=1,
            refund_amount_cents=500,
            audit_type_breakdown={"basic": {"purchases": 10, "revenue_cents": 50000}},
            geographic_breakdown={},
        )

        mock.get_aggregated_metrics.return_value = [mock_metric]
        mock.aggregate_metrics.return_value = [mock_metric]
        mock.get_metrics_summary.return_value = {
            "raw_metrics_count": 100,
            "aggregated_metrics_count": 10,
            "conversion_events_count": 50,
        }
        return mock

    @pytest.fixture
    def mock_alert_manager(self):
        """Mock alert manager."""
        mock = Mock()
        mock.get_alert_status.return_value = {
            "active_alerts_count": 0,
            "active_alerts": [],
            "total_rules": 5,
            "enabled_rules": 5,
            "notification_channels": 2,
            "recent_alerts_24h": 0,
        }
        return mock

    @pytest.fixture
    def purchase_monitor(
        self,
        mock_metrics_tracker,
        mock_financial_tracker,
        mock_metrics_aggregator,
        mock_alert_manager,
    ):
        """Create purchase monitor with mocked dependencies."""
        monitor = PurchaseMonitor(update_interval_seconds=60)
        monitor.metrics_tracker = mock_metrics_tracker
        monitor.financial_tracker = mock_financial_tracker
        monitor.metrics_aggregator = mock_metrics_aggregator
        monitor.alert_manager = mock_alert_manager
        return monitor

    def test_initialization(self):
        """Test purchase monitor initialization."""
        monitor = PurchaseMonitor(
            update_interval_seconds=300, enable_realtime_alerts=True
        )

        assert monitor.update_interval == 300
        assert monitor.enable_realtime_alerts
        assert not monitor.is_running
        assert monitor.last_update is None

    def test_get_dashboard_data(self, purchase_monitor):
        """Test dashboard data generation."""
        dashboard_data = purchase_monitor.get_dashboard_data(
            MonitoringPeriod.DAILY, lookback_days=30
        )

        assert isinstance(dashboard_data, DashboardData)
        assert dashboard_data.period == MonitoringPeriod.DAILY
        assert len(dashboard_data.kpis) > 0
        assert isinstance(dashboard_data.revenue_breakdown, dict)
        assert isinstance(dashboard_data.alert_summary, dict)

    def test_calculate_kpis(self, purchase_monitor):
        """Test KPI calculation."""
        dashboard_data = purchase_monitor.get_dashboard_data(MonitoringPeriod.DAILY)

        # Verify KPIs are calculated
        kpi_names = [kpi.name for kpi in dashboard_data.kpis]
        expected_kpis = [
            "Total Revenue",
            "Total Purchases",
            "Average Order Value",
            "Conversion Rate",
            "Stripe Fee Rate",
        ]

        for expected_kpi in expected_kpis:
            assert expected_kpi in kpi_names

        # Check KPI structure
        for kpi in dashboard_data.kpis:
            assert isinstance(kpi, PurchaseKPI)
            assert kpi.name is not None
            assert kpi.value is not None
            assert kpi.unit is not None

    def test_revenue_breakdown(self, purchase_monitor):
        """Test revenue breakdown calculation."""
        dashboard_data = purchase_monitor.get_dashboard_data(MonitoringPeriod.DAILY)
        breakdown = dashboard_data.revenue_breakdown

        assert "total_revenue_cents" in breakdown
        assert "total_stripe_fees_cents" in breakdown
        assert "net_revenue_cents" in breakdown
        assert "by_audit_type" in breakdown

        # Verify audit type breakdown
        by_audit_type = breakdown["by_audit_type"]
        assert "basic" in by_audit_type
        assert "revenue_cents" in by_audit_type["basic"]
        assert "purchases" in by_audit_type["basic"]

    def test_export_dashboard_data_json(self, purchase_monitor):
        """Test JSON export of dashboard data."""
        exported_data = purchase_monitor.export_dashboard_data(
            MonitoringPeriod.DAILY, "json"
        )

        assert isinstance(exported_data, str)

        # Should be valid JSON
        import json

        parsed_data = json.loads(exported_data)
        assert "timestamp" in parsed_data
        assert "period" in parsed_data
        assert "kpis" in parsed_data

    def test_export_dashboard_data_csv(self, purchase_monitor):
        """Test CSV export of dashboard data."""
        exported_data = purchase_monitor.export_dashboard_data(
            MonitoringPeriod.DAILY, "csv"
        )

        assert isinstance(exported_data, str)
        assert "Name,Value,Unit,Change %,Trend,Target" in exported_data
        lines = exported_data.split("\n")
        assert len(lines) > 1  # Header plus at least one data row

    def test_export_unsupported_format(self, purchase_monitor):
        """Test export with unsupported format raises error."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            purchase_monitor.export_dashboard_data(MonitoringPeriod.DAILY, "xml")

    def test_get_monitoring_status(self, purchase_monitor):
        """Test monitoring status retrieval."""
        status = purchase_monitor.get_monitoring_status()

        assert "is_running" in status
        assert "last_update" in status
        assert "update_interval_seconds" in status
        assert "realtime_alerts_enabled" in status
        assert "alert_manager_status" in status
        assert "metrics_summary" in status

        assert not status["is_running"]  # Not started yet
        assert status["update_interval_seconds"] == 60

    def test_trigger_manual_update(self, purchase_monitor):
        """Test manual update trigger."""
        # Should not raise an error
        purchase_monitor.trigger_manual_update()

        # Verify update timestamp is set
        assert purchase_monitor.last_update is not None

        # Verify mocked methods were called
        purchase_monitor.metrics_aggregator.aggregate_metrics.assert_called()
        purchase_monitor.metrics_aggregator.store_aggregated_metrics.assert_called()
        purchase_monitor.alert_manager.check_alerts.assert_called()

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, purchase_monitor):
        """Test starting and stopping the monitoring process."""
        # Start monitoring
        await purchase_monitor.start_monitoring()
        assert purchase_monitor.is_running

        # Stop monitoring
        await purchase_monitor.stop_monitoring()
        assert not purchase_monitor.is_running

    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, purchase_monitor):
        """Test monitoring loop handles errors gracefully."""
        # Mock an error in metrics aggregation
        purchase_monitor.metrics_aggregator.aggregate_metrics.side_effect = Exception(
            "Test error"
        )

        # Start monitoring for a short time
        await purchase_monitor.start_monitoring()

        # Wait a bit for the loop to run
        await asyncio.sleep(0.1)

        # Stop monitoring
        await purchase_monitor.stop_monitoring()

        # Should still be able to stop without error
        assert not purchase_monitor.is_running


class TestDashboardIntegration:
    """Test dashboard integration functionality."""

    def test_dashboard_data_serialization(self):
        """Test dashboard data can be serialized properly."""
        # Create sample dashboard data
        kpis = [
            PurchaseKPI(
                name="Test KPI",
                value=100.0,
                unit="USD",
                change_percentage=10.5,
                trend="up",
                target=150.0,
            )
        ]

        dashboard_data = DashboardData(
            timestamp=datetime.now(),
            period=MonitoringPeriod.DAILY,
            kpis=kpis,
            revenue_breakdown={"total_revenue_cents": 10000},
            conversion_metrics={"conversion_rate": 0.025},
            alert_summary={"active_alerts_count": 0},
            recent_transactions=[],
            performance_trends={},
        )

        # Should be able to access all fields
        assert dashboard_data.period == MonitoringPeriod.DAILY
        assert len(dashboard_data.kpis) == 1
        assert dashboard_data.kpis[0].name == "Test KPI"
        assert dashboard_data.revenue_breakdown["total_revenue_cents"] == 10000

    def test_kpi_calculation_edge_cases(self):
        """Test KPI calculation with edge cases."""
        # Test KPI with no change percentage
        kpi = PurchaseKPI(
            name="Stable KPI", value=50.0, unit="%", change_percentage=None, trend=None
        )

        assert kpi.change_percentage is None
        assert kpi.trend is None

        # Test KPI with target
        kpi_with_target = PurchaseKPI(
            name="Target KPI", value=80.0, unit="%", target=100.0
        )

        assert kpi_with_target.target == 100.0


class TestMonitoringPeriods:
    """Test monitoring period functionality."""

    def test_monitoring_period_enum(self):
        """Test monitoring period enum values."""
        periods = list(MonitoringPeriod)
        expected_periods = [
            MonitoringPeriod.REALTIME,
            MonitoringPeriod.HOURLY,
            MonitoringPeriod.DAILY,
            MonitoringPeriod.WEEKLY,
            MonitoringPeriod.MONTHLY,
        ]

        for period in expected_periods:
            assert period in periods

        # Test string values
        assert MonitoringPeriod.DAILY.value == "daily"
        assert MonitoringPeriod.WEEKLY.value == "weekly"


@pytest.mark.integration
class TestPurchaseMonitoringIntegration:
    """Integration tests for purchase monitoring system."""

    def test_end_to_end_monitoring_flow(self):
        """Test complete monitoring flow."""
        # This would require actual database and metrics setup
        # For now, we'll just test that components can be instantiated together
        monitor = PurchaseMonitor()

        # Should be able to get status without errors
        status = monitor.get_monitoring_status()
        assert isinstance(status, dict)

        # Should be able to trigger manual update
        try:
            monitor.trigger_manual_update()
            # If no exception, test passes
        except Exception as e:
            # Some failures are expected without proper setup
            assert "Failed to update metrics" in str(e) or "database" in str(e).lower()
