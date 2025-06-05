"""
Purchase Metrics Dashboard
=========================

This module provides a web-based dashboard for monitoring purchase metrics,
conversion funnels, and business analytics for the LeadFactory audit system.
"""

import contextlib
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request

from leadfactory.monitoring.alert_manager import alert_manager
from leadfactory.monitoring.conversion_tracking import (
    ConversionChannel,
    conversion_tracker,
)
from leadfactory.monitoring.purchase_monitoring import (
    MonitoringPeriod,
    purchase_monitor,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class PurchaseMetricsDashboard:
    """Web-based dashboard for purchase metrics monitoring."""

    def __init__(
        self, host: str = "127.0.0.1", port: int = 5000, debug: bool = False
    ):  # nosec B104
        """Initialize the dashboard.

        Args:
            host: Host to bind the web server to
            port: Port to bind the web server to
            debug: Enable Flask debug mode
        """
        self.host = host
        self.port = port
        self.debug = debug
        self.logger = get_logger(f"{__name__}.PurchaseMetricsDashboard")

        # Initialize Flask app
        self.app = Flask(
            __name__,
            template_folder=self._get_template_folder(),
            static_folder=self._get_static_folder(),
        )

        # Configure Flask app
        self.app.config["SECRET_KEY"] = os.environ.get(
            "FLASK_SECRET_KEY", "dev-secret-key"
        )

        # Register routes
        self._register_routes()

        self.logger.info(f"Dashboard initialized (host={host}, port={port})")

    def _get_template_folder(self) -> str:
        """Get templates folder path."""
        return os.path.join(os.path.dirname(__file__), "templates")

    def _get_static_folder(self) -> str:
        """Get static files folder path."""
        return os.path.join(os.path.dirname(__file__), "static")

    def _register_routes(self):
        """Register Flask routes for the dashboard."""

        @self.app.route("/")
        def dashboard_home():
            """Main dashboard page."""
            return render_template("dashboard.html")

        @self.app.route("/api/dashboard-data")
        def api_dashboard_data():
            """API endpoint for dashboard data."""
            try:
                period_str = request.args.get("period", "daily")
                lookback_days = int(request.args.get("lookback_days", 30))

                # Map string to enum
                period_map = {
                    "hourly": MonitoringPeriod.HOURLY,
                    "daily": MonitoringPeriod.DAILY,
                    "weekly": MonitoringPeriod.WEEKLY,
                    "monthly": MonitoringPeriod.MONTHLY,
                }

                period = period_map.get(period_str, MonitoringPeriod.DAILY)

                # Get dashboard data
                dashboard_data = purchase_monitor.get_dashboard_data(
                    period, lookback_days
                )

                # Convert to JSON-serializable format
                data = {
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

                return jsonify(data)

            except Exception as e:
                self.logger.error(f"Error generating dashboard data: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/conversion-funnel")
        def api_conversion_funnel():
            """API endpoint for conversion funnel analysis."""
            try:
                days_back = int(request.args.get("days_back", 30))
                audit_type = request.args.get("audit_type")
                channel_str = request.args.get("channel")

                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)

                channel = None
                if channel_str:
                    with contextlib.suppress(ValueError):
                        channel = ConversionChannel(channel_str)

                funnel = conversion_tracker.analyze_funnel(
                    start_date, end_date, audit_type, channel
                )

                return jsonify(
                    {
                        "period_start": funnel.period_start.isoformat(),
                        "period_end": funnel.period_end.isoformat(),
                        "audit_type": funnel.audit_type,
                        "channel": funnel.channel.value if funnel.channel else None,
                        "funnel_steps": funnel.funnel_steps,
                        "conversion_rates": funnel.conversion_rates,
                        "drop_off_points": funnel.drop_off_points,
                        "total_revenue_cents": funnel.total_revenue_cents,
                        "average_time_to_conversion": funnel.average_time_to_conversion,
                    }
                )

            except Exception as e:
                self.logger.error(f"Error generating funnel analysis: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/attribution-analysis")
        def api_attribution_analysis():
            """API endpoint for marketing attribution analysis."""
            try:
                days_back = int(request.args.get("days_back", 30))
                attribution_model = request.args.get("model", "last_click")

                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)

                attribution = conversion_tracker.analyze_attribution(
                    start_date, end_date, attribution_model
                )

                return jsonify(
                    {
                        "period_start": attribution.period_start.isoformat(),
                        "period_end": attribution.period_end.isoformat(),
                        "channel_performance": attribution.channel_performance,
                        "top_converting_channels": attribution.top_converting_channels,
                        "revenue_attribution": attribution.revenue_attribution,
                        "conversion_paths": attribution.conversion_paths,
                    }
                )

            except Exception as e:
                self.logger.error(f"Error generating attribution analysis: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/alerts")
        def api_alerts():
            """API endpoint for current alerts."""
            try:
                alert_status = alert_manager.get_alert_status()
                return jsonify(alert_status)

            except Exception as e:
                self.logger.error(f"Error getting alert status: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/monitoring-status")
        def api_monitoring_status():
            """API endpoint for monitoring system status."""
            try:
                status = purchase_monitor.get_monitoring_status()
                return jsonify(status)

            except Exception as e:
                self.logger.error(f"Error getting monitoring status: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/export/<format_type>")
        def api_export_data(format_type):
            """API endpoint for exporting dashboard data."""
            try:
                period_str = request.args.get("period", "daily")
                period_map = {
                    "hourly": MonitoringPeriod.HOURLY,
                    "daily": MonitoringPeriod.DAILY,
                    "weekly": MonitoringPeriod.WEEKLY,
                    "monthly": MonitoringPeriod.MONTHLY,
                }

                period = period_map.get(period_str, MonitoringPeriod.DAILY)

                exported_data = purchase_monitor.export_dashboard_data(
                    period, format_type
                )

                if format_type.lower() == "json":
                    return Response(
                        exported_data,
                        mimetype="application/json",
                        headers={
                            "Content-Disposition": f"attachment; filename=dashboard_data_{period_str}.json"
                        },
                    )
                elif format_type.lower() == "csv":
                    return Response(
                        exported_data,
                        mimetype="text/csv",
                        headers={
                            "Content-Disposition": f"attachment; filename=dashboard_data_{period_str}.csv"
                        },
                    )
                else:
                    return jsonify({"error": f"Unsupported format: {format_type}"}), 400

            except Exception as e:
                self.logger.error(f"Error exporting data: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/trigger-update", methods=["POST"])
        def api_trigger_update():
            """API endpoint to manually trigger metrics update."""
            try:
                purchase_monitor.trigger_manual_update()
                return jsonify(
                    {"success": True, "message": "Update triggered successfully"}
                )

            except Exception as e:
                self.logger.error(f"Error triggering update: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({"error": "Not found"}), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({"error": "Internal server error"}), 500

    def run(self):
        """Run the dashboard web server."""
        try:
            self.logger.info(f"Starting dashboard server on {self.host}:{self.port}")
            self.app.run(host=self.host, port=self.port, debug=self.debug)
        except Exception as e:
            self.logger.error(f"Error starting dashboard server: {e}")
            raise

    def create_wsgi_app(self):
        """Create WSGI application for production deployment."""
        return self.app


def create_dashboard_templates():
    """Create basic HTML templates for the dashboard."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    os.makedirs(template_dir, exist_ok=True)

    # Main dashboard template
    dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Purchase Metrics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 2em; font-weight: bold; color: #2563eb; }
        .metric-change { font-size: 0.9em; margin-top: 5px; }
        .metric-change.positive { color: #059669; }
        .metric-change.negative { color: #dc2626; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .alert-banner { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .controls { display: flex; gap: 10px; margin-bottom: 20px; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-primary { background: #2563eb; color: white; }
        .btn-secondary { background: #6b7280; color: white; }
        select { padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; }
        .loading { text-align: center; padding: 40px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Purchase Metrics Dashboard</h1>
            <p>Real-time monitoring of audit report sales and conversion metrics</p>
        </div>

        <div id="alert-container"></div>

        <div class="controls">
            <select id="period-selector">
                <option value="hourly">Hourly</option>
                <option value="daily" selected>Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
            </select>
            <button class="btn btn-primary" onclick="refreshData()">Refresh</button>
            <button class="btn btn-secondary" onclick="exportData('json')">Export JSON</button>
            <button class="btn btn-secondary" onclick="exportData('csv')">Export CSV</button>
        </div>

        <div id="metrics-container" class="metrics-grid">
            <div class="loading">Loading metrics...</div>
        </div>

        <div class="chart-container">
            <h3>Revenue Trend</h3>
            <canvas id="revenueChart" width="400" height="200"></canvas>
        </div>

        <div class="chart-container">
            <h3>Conversion Funnel</h3>
            <canvas id="funnelChart" width="400" height="200"></canvas>
        </div>
    </div>

    <script>
        let revenueChart, funnelChart;

        async function loadDashboardData() {
            try {
                const period = document.getElementById('period-selector').value;
                const response = await fetch(`/api/dashboard-data?period=${period}`);
                const data = await response.json();

                if (data.error) {
                    throw new Error(data.error);
                }

                updateMetrics(data.kpis);
                updateRevenueChart(data.performance_trends.revenue_trend || []);
                updateAlerts(data.alert_summary);

                // Load funnel data
                const funnelResponse = await fetch('/api/conversion-funnel');
                const funnelData = await funnelResponse.json();
                updateFunnelChart(funnelData.funnel_steps || []);

            } catch (error) {
                console.error('Error loading dashboard data:', error);
                document.getElementById('metrics-container').innerHTML =
                    `<div style="color: red;">Error loading data: ${error.message}</div>`;
            }
        }

        function updateMetrics(kpis) {
            const container = document.getElementById('metrics-container');
            container.innerHTML = '';

            kpis.forEach(kpi => {
                const card = document.createElement('div');
                card.className = 'metric-card';

                const changeClass = kpi.change_percentage > 0 ? 'positive' :
                                   kpi.change_percentage < 0 ? 'negative' : '';
                const changeText = kpi.change_percentage ?
                    `${kpi.change_percentage > 0 ? '+' : ''}${kpi.change_percentage.toFixed(1)}%` : '';

                card.innerHTML = `
                    <h4>${kpi.name}</h4>
                    <div class="metric-value">${kpi.value.toLocaleString()} ${kpi.unit}</div>
                    ${changeText ? `<div class="metric-change ${changeClass}">${changeText}</div>` : ''}
                    ${kpi.target ? `<div style="font-size: 0.8em; color: #6b7280;">Target: ${kpi.target} ${kpi.unit}</div>` : ''}
                `;

                container.appendChild(card);
            });
        }

        function updateRevenueChart(data) {
            const ctx = document.getElementById('revenueChart').getContext('2d');

            if (revenueChart) {
                revenueChart.destroy();
            }

            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => new Date(d.timestamp).toLocaleDateString()),
                    datasets: [{
                        label: 'Revenue ($)',
                        data: data.map(d => d.value),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        }

        function updateFunnelChart(steps) {
            const ctx = document.getElementById('funnelChart').getContext('2d');

            if (funnelChart) {
                funnelChart.destroy();
            }

            funnelChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: steps.map(s => s.step.replace(/_/g, ' ').toUpperCase()),
                    datasets: [{
                        label: 'Users',
                        data: steps.map(s => s.count),
                        backgroundColor: '#059669',
                        borderColor: '#047857',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }

        function updateAlerts(alertSummary) {
            const container = document.getElementById('alert-container');

            if (alertSummary.active_alerts_count > 0) {
                container.innerHTML = `
                    <div class="alert-banner">
                        <strong>Active Alerts:</strong> ${alertSummary.active_alerts_count} alerts require attention
                    </div>
                `;
            } else {
                container.innerHTML = '';
            }
        }

        function refreshData() {
            loadDashboardData();
        }

        function exportData(format) {
            const period = document.getElementById('period-selector').value;
            window.open(`/api/export/${format}?period=${period}`, '_blank');
        }

        // Auto-refresh every 5 minutes
        setInterval(loadDashboardData, 5 * 60 * 1000);

        // Initial load
        document.addEventListener('DOMContentLoaded', loadDashboardData);

        // Period change handler
        document.getElementById('period-selector').addEventListener('change', loadDashboardData);
    </script>
</body>
</html>
    """

    with open(os.path.join(template_dir, "dashboard.html"), "w") as f:
        f.write(dashboard_html)


# Global instance
dashboard = PurchaseMetricsDashboard()

# Create templates if they don't exist
create_dashboard_templates()


def run_dashboard(
    host: str = "127.0.0.1", port: int = 5000, debug: bool = False
):  # nosec B104
    """Run the dashboard server.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        debug: Enable debug mode
    """
    dashboard_instance = PurchaseMetricsDashboard(host, port, debug)
    dashboard_instance.run()


if __name__ == "__main__":
    run_dashboard(debug=True)
