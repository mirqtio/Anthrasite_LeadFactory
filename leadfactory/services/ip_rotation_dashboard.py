"""
IP Rotation Dashboard and Visualization

This module provides dashboard components and visualization utilities
for monitoring IP rotation system status, metrics, and performance.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Import logging with fallback
try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class IPRotationDashboard:
    """Dashboard for IP rotation system visualization and monitoring."""

    def __init__(self, rotation_service=None, alerting_service=None):
        self.rotation_service = rotation_service
        self.alerting_service = alerting_service
        logger.info("IP rotation dashboard initialized")

    def generate_html_dashboard(self) -> str:
        """Generate a complete HTML dashboard."""
        if not self.rotation_service or not self.alerting_service:
            return self._generate_error_page("Services not available")

        try:
            # Collect all data
            pool_status = self.rotation_service.get_pool_status()
            dashboard_data = self.alerting_service.get_dashboard_data()
            alert_summary = self.alerting_service.get_alert_summary(24)

            # Generate HTML
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>IP Rotation System Dashboard</title>
                <style>
                    {self._get_dashboard_css()}
                </style>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            </head>
            <body>
                <div class="dashboard">
                    <header class="dashboard-header">
                        <h1>IP Rotation System Dashboard</h1>
                        <div class="last-updated">
                            Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                        </div>
                    </header>

                    {self._generate_status_cards(pool_status, dashboard_data)}
                    {self._generate_pool_table(pool_status)}
                    {self._generate_alerts_section(dashboard_data, alert_summary)}
                    {self._generate_charts_section(dashboard_data)}
                    {self._generate_circuit_breaker_section(dashboard_data)}
                </div>

                <script>
                    {self._get_dashboard_javascript(dashboard_data)}
                </script>
            </body>
            </html>
            """

            return html

        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            return self._generate_error_page(f"Error generating dashboard: {str(e)}")

    def _generate_error_page(self, error_message: str) -> str:
        """Generate an error page."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 50px; }}
                .error {{ color: red; padding: 20px; border: 1px solid red; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Dashboard Error</h2>
                <p>{error_message}</p>
            </div>
        </body>
        </html>
        """

    def _get_dashboard_css(self) -> str:
        """Get CSS styles for the dashboard."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }

        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .dashboard-header h1 {
            font-size: 2.5em;
            margin: 0;
        }

        .last-updated {
            font-size: 0.9em;
            opacity: 0.9;
        }

        .status-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .status-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
            transition: transform 0.2s;
        }

        .status-card:hover {
            transform: translateY(-2px);
        }

        .status-card h3 {
            color: #666;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .status-card .value {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .status-card.healthy .value { color: #28a745; }
        .status-card.warning .value { color: #ffc107; }
        .status-card.critical .value { color: #dc3545; }

        .section {
            background: white;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }

        .section-header {
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #dee2e6;
        }

        .section-header h2 {
            margin: 0;
            color: #495057;
        }

        .section-content {
            padding: 20px;
        }

        .pool-table {
            width: 100%;
            border-collapse: collapse;
        }

        .pool-table th,
        .pool-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }

        .pool-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }

        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
        }

        .status-active { background: #d4edda; color: #155724; }
        .status-cooldown { background: #fff3cd; color: #856404; }
        .status-disabled { background: #f8d7da; color: #721c24; }
        .status-maintenance { background: #d1ecf1; color: #0c5460; }

        .performance-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }

        .performance-fill {
            height: 100%;
            background: linear-gradient(90deg, #dc3545 0%, #ffc107 50%, #28a745 100%);
            transition: width 0.3s;
        }

        .alerts-list {
            max-height: 400px;
            overflow-y: auto;
        }

        .alert-item {
            padding: 15px;
            border-left: 4px solid;
            margin-bottom: 10px;
            background: #f8f9fa;
        }

        .alert-item.info { border-left-color: #17a2b8; }
        .alert-item.warning { border-left-color: #ffc107; }
        .alert-item.critical { border-left-color: #dc3545; }
        .alert-item.emergency { border-left-color: #6f42c1; }

        .alert-time {
            font-size: 0.8em;
            color: #666;
            margin-bottom: 5px;
        }

        .chart-container {
            position: relative;
            height: 300px;
            margin: 20px 0;
        }

        .charts-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }

        .circuit-breaker {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .circuit-status {
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .circuit-closed { background: #d4edda; color: #155724; }
        .circuit-open { background: #f8d7da; color: #721c24; }
        .circuit-half-open { background: #fff3cd; color: #856404; }

        @media (max-width: 768px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }

            .dashboard-header {
                flex-direction: column;
                text-align: center;
                gap: 10px;
            }
        }
        """

    def _generate_status_cards(
        self, pool_status: List[Dict], dashboard_data: Dict
    ) -> str:
        """Generate status cards section."""
        total_ips = len(pool_status)
        active_ips = sum(1 for ip in pool_status if ip["status"] == "active")
        disabled_ips = sum(1 for ip in pool_status if ip["status"] == "disabled")
        cooldown_ips = sum(1 for ip in pool_status if ip["status"] == "cooldown")

        system_health = dashboard_data["system_status"]["health"]
        total_rotations = dashboard_data["system_status"]["total_rotations"]
        total_alerts = dashboard_data["system_status"]["total_alerts"]

        health_class = (
            "healthy"
            if system_health == "healthy"
            else "warning" if system_health == "warning" else "critical"
        )

        return f"""
        <div class="status-cards">
            <div class="status-card">
                <h3>Total IPs</h3>
                <div class="value">{total_ips}</div>
            </div>
            <div class="status-card">
                <h3>Active IPs</h3>
                <div class="value" style="color: #28a745;">{active_ips}</div>
            </div>
            <div class="status-card">
                <h3>Disabled IPs</h3>
                <div class="value" style="color: #dc3545;">{disabled_ips}</div>
            </div>
            <div class="status-card">
                <h3>Cooldown IPs</h3>
                <div class="value" style="color: #ffc107;">{cooldown_ips}</div>
            </div>
            <div class="status-card {health_class}">
                <h3>System Health</h3>
                <div class="value">{system_health.title()}</div>
            </div>
            <div class="status-card">
                <h3>Total Rotations</h3>
                <div class="value">{total_rotations}</div>
            </div>
            <div class="status-card">
                <h3>Total Alerts</h3>
                <div class="value">{total_alerts}</div>
            </div>
        </div>
        """

    def _generate_pool_table(self, pool_status: List[Dict]) -> str:
        """Generate IP pool status table."""
        if not pool_status:
            return """
            <div class="section">
                <div class="section-header">
                    <h2>IP Pool Status</h2>
                </div>
                <div class="section-content">
                    <p>No IPs in the pool.</p>
                </div>
            </div>
            """

        rows = ""
        for ip_info in pool_status:
            performance_width = int(ip_info["performance_score"] * 100)
            status_class = f"status-{ip_info['status']}"

            rows += f"""
            <tr>
                <td>{ip_info['ip_address']}</td>
                <td>{ip_info['subuser']}</td>
                <td><span class="status-badge {status_class}">{ip_info['status']}</span></td>
                <td>{ip_info['priority']}</td>
                <td>
                    <div class="performance-bar">
                        <div class="performance-fill" style="width: {performance_width}%"></div>
                    </div>
                    {ip_info['performance_score']:.3f}
                </td>
                <td>{ip_info['total_sent']:,}</td>
                <td>{ip_info['total_bounced']:,}</td>
                <td>{ip_info['bounce_rate']:.2%}</td>
                <td>{ip_info['cooldown_until'] or 'N/A'}</td>
                <td>{ip_info['last_used'] or 'Never'}</td>
            </tr>
            """

        return f"""
        <div class="section">
            <div class="section-header">
                <h2>IP Pool Status</h2>
            </div>
            <div class="section-content">
                <table class="pool-table">
                    <thead>
                        <tr>
                            <th>IP Address</th>
                            <th>Subuser</th>
                            <th>Status</th>
                            <th>Priority</th>
                            <th>Performance</th>
                            <th>Total Sent</th>
                            <th>Total Bounced</th>
                            <th>Bounce Rate</th>
                            <th>Cooldown Until</th>
                            <th>Last Used</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    def _generate_alerts_section(
        self, dashboard_data: Dict, alert_summary: Dict
    ) -> str:
        """Generate alerts section."""
        recent_alerts = dashboard_data.get("recent_alerts", [])

        if not recent_alerts:
            alerts_content = "<p>No recent alerts.</p>"
        else:
            alerts_content = '<div class="alerts-list">'
            for alert in recent_alerts[-10:]:  # Show last 10 alerts
                alert_class = alert["severity"]
                timestamp = datetime.fromisoformat(alert["timestamp"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                alerts_content += f"""
                <div class="alert-item {alert_class}">
                    <div class="alert-time">{timestamp}</div>
                    <div class="alert-message">{alert['message']}</div>
                </div>
                """
            alerts_content += "</div>"

        return f"""
        <div class="section">
            <div class="section-header">
                <h2>Recent Alerts (Last 24 Hours: {alert_summary['total_alerts']})</h2>
            </div>
            <div class="section-content">
                {alerts_content}
            </div>
        </div>
        """

    def _generate_charts_section(self, dashboard_data: Dict) -> str:
        """Generate charts section."""
        return f"""
        <div class="section">
            <div class="section-header">
                <h2>System Metrics</h2>
            </div>
            <div class="section-content">
                <div class="charts-grid">
                    <div>
                        <h3>Alerts by Severity</h3>
                        <div class="chart-container">
                            <canvas id="alertsSeverityChart"></canvas>
                        </div>
                    </div>
                    <div>
                        <h3>Alerts by Type</h3>
                        <div class="chart-container">
                            <canvas id="alertsTypeChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_circuit_breaker_section(self, dashboard_data: Dict) -> str:
        """Generate circuit breaker section."""
        cb_status = dashboard_data["circuit_breaker_status"]
        status_class = f"circuit-{cb_status['state']}"

        return f"""
        <div class="section">
            <div class="section-header">
                <h2>Circuit Breaker Status</h2>
            </div>
            <div class="section-content">
                <div class="circuit-breaker">
                    <div class="circuit-status {status_class}">
                        {cb_status['state']}
                    </div>
                    <div>
                        <p><strong>Failure Count:</strong> {cb_status['failure_count']}</p>
                        <p><strong>Can Execute:</strong> {cb_status['can_execute']}</p>
                        <p><strong>Last Failure:</strong> {cb_status['last_failure_time'] or 'None'}</p>
                    </div>
                </div>
            </div>
        </div>
        """

    def _get_dashboard_javascript(self, dashboard_data: Dict) -> str:
        """Get JavaScript for dashboard interactivity."""
        alerts_by_severity = dashboard_data["metrics"].get("alerts_by_severity", {})
        alerts_by_type = dashboard_data["metrics"].get("alerts_by_type", {})

        return f"""
        // Auto-refresh every 30 seconds
        setTimeout(() => {{
            window.location.reload();
        }}, 30000);

        // Initialize charts
        document.addEventListener('DOMContentLoaded', function() {{
            // Alerts by Severity Chart
            const severityCtx = document.getElementById('alertsSeverityChart').getContext('2d');
            new Chart(severityCtx, {{
                type: 'doughnut',
                data: {{
                    labels: {list(alerts_by_severity.keys())},
                    datasets: [{{
                        data: {list(alerts_by_severity.values())},
                        backgroundColor: [
                            '#17a2b8',  // info
                            '#ffc107',  // warning
                            '#dc3545',  // critical
                            '#6f42c1'   // emergency
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }}
            }});

            // Alerts by Type Chart
            const typeCtx = document.getElementById('alertsTypeChart').getContext('2d');
            new Chart(typeCtx, {{
                type: 'bar',
                data: {{
                    labels: {list(alerts_by_type.keys())},
                    datasets: [{{
                        label: 'Count',
                        data: {list(alerts_by_type.values())},
                        backgroundColor: '#667eea'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        }});
        """

    def export_metrics_json(self) -> str:
        """Export current metrics as JSON."""
        if not self.rotation_service or not self.alerting_service:
            return json.dumps({"error": "Services not available"})

        try:
            pool_status = self.rotation_service.get_pool_status()
            dashboard_data = self.alerting_service.get_dashboard_data()
            alert_summary = self.alerting_service.get_alert_summary(24)

            export_data = {
                "timestamp": datetime.now().isoformat(),
                "pool_status": pool_status,
                "dashboard_data": dashboard_data,
                "alert_summary": alert_summary,
            }

            return json.dumps(export_data, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return json.dumps({"error": str(e)})

    def get_health_check(self) -> Dict[str, Any]:
        """Get system health check data."""
        if not self.rotation_service or not self.alerting_service:
            return {"status": "error", "message": "Services not available"}

        try:
            pool_status = self.rotation_service.get_pool_status()
            dashboard_data = self.alerting_service.get_dashboard_data()

            active_ips = sum(1 for ip in pool_status if ip["status"] == "active")
            total_ips = len(pool_status)

            health_status = "healthy"
            if active_ips == 0:
                health_status = "critical"
            elif active_ips < total_ips * 0.5:
                health_status = "warning"

            return {
                "status": health_status,
                "active_ips": active_ips,
                "total_ips": total_ips,
                "circuit_breaker_state": dashboard_data["circuit_breaker_status"][
                    "state"
                ],
                "last_rotation": dashboard_data["system_status"]["last_rotation"],
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {"status": "error", "message": str(e)}
