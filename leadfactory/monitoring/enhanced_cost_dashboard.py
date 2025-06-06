"""
Enhanced Cost Dashboard
======================

This module provides an enhanced cost dashboard that integrates with the new cost breakdown API,
real-time streaming, and advanced analytics capabilities.

Features:
- Real-time cost monitoring with WebSocket updates
- Advanced cost breakdown views and filters
- Trend analysis and forecasting visualizations
- Cost optimization recommendations
- Integration with existing monitoring infrastructure
- Export capabilities for reports and analysis
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request
from flask_socketio import SocketIO

from leadfactory.analytics.cost_analytics import cost_analytics_engine
from leadfactory.api.cost_breakdown_api import cost_breakdown_api
from leadfactory.api.cost_metrics_integration import cost_metrics_integration
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedCostDashboard:
    """Enhanced cost dashboard with advanced analytics and real-time updates."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5002, debug: bool = False):
        """Initialize the enhanced cost dashboard."""
        self.host = host
        self.port = port
        self.debug = debug
        self.logger = get_logger(f"{__name__}.EnhancedCostDashboard")

        # Initialize Flask app with SocketIO
        self.app = Flask(
            __name__,
            template_folder=self._get_template_folder(),
            static_folder=self._get_static_folder(),
        )
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Configure Flask app
        self.app.config["SECRET_KEY"] = os.environ.get(
            "FLASK_SECRET_KEY", "enhanced-cost-dashboard-secret"
        )

        # Register routes
        self._register_routes()
        self._register_socketio_handlers()

        self.logger.info(
            f"Enhanced cost dashboard initialized (host={host}, port={port})"
        )

    def _get_template_folder(self) -> str:
        """Get templates folder path."""
        return os.path.join(os.path.dirname(__file__), "templates")

    def _get_static_folder(self) -> str:
        """Get static files folder path."""
        return os.path.join(os.path.dirname(__file__), "static")

    def _register_routes(self):
        """Register Flask routes for the enhanced dashboard."""

        @self.app.route("/")
        def enhanced_dashboard_home():
            """Enhanced dashboard main page."""
            return render_template("enhanced_cost_dashboard.html")

        @self.app.route("/api/enhanced/dashboard-data")
        def api_enhanced_dashboard_data():
            """API endpoint for enhanced dashboard data."""
            try:
                time_period = request.args.get("time_period", "daily")
                service_filter = request.args.get("service_filter")
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")

                # Get integrated dashboard data
                dashboard_data = cost_metrics_integration.get_integrated_dashboard_data(
                    time_period
                )

                # Apply filters if specified
                if service_filter:
                    dashboard_data = self._apply_service_filter(
                        dashboard_data, service_filter
                    )

                if start_date and end_date:
                    dashboard_data = self._apply_date_filter(
                        dashboard_data, start_date, end_date
                    )

                return jsonify(dashboard_data)

            except Exception as e:
                self.logger.error(f"Error generating enhanced dashboard data: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/cost-trends")
        def api_enhanced_cost_trends():
            """API endpoint for advanced cost trend analysis."""
            try:
                service_type = request.args.get("service_type")
                days_back = int(request.args.get("days_back", 90))
                forecast_days = int(request.args.get("forecast_days", 30))

                trends = cost_analytics_engine.analyze_cost_trends(
                    service_type=service_type,
                    days_back=days_back,
                    forecast_days=forecast_days,
                )

                return jsonify(trends)

            except Exception as e:
                self.logger.error(f"Error generating cost trends: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/optimization-recommendations")
        def api_optimization_recommendations():
            """API endpoint for cost optimization recommendations."""
            try:
                # Get recent trend analysis
                trends = cost_analytics_engine.analyze_cost_trends(
                    days_back=30, forecast_days=7
                )

                if "error" in trends:
                    return (
                        jsonify(
                            {
                                "error": "Cannot generate recommendations: "
                                + trends["error"]
                            }
                        ),
                        400,
                    )

                recommendations = (
                    cost_analytics_engine.generate_cost_optimization_recommendations(
                        trends
                    )
                )
                return jsonify(recommendations)

            except Exception as e:
                self.logger.error(f"Error generating optimization recommendations: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/cost-efficiency")
        def api_cost_efficiency():
            """API endpoint for cost efficiency metrics."""
            try:
                efficiency_metrics = (
                    cost_metrics_integration.get_cost_efficiency_metrics()
                )
                return jsonify(efficiency_metrics)

            except Exception as e:
                self.logger.error(f"Error getting cost efficiency metrics: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/detailed-breakdown")
        def api_detailed_breakdown():
            """API endpoint for detailed cost breakdown with advanced filtering."""
            try:
                # Get all filter parameters
                service_type = request.args.get("service_type")
                time_period = request.args.get("time_period", "daily")
                operation_type = request.args.get("operation_type")
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")
                group_by = request.args.getlist("group_by")
                min_cost = request.args.get("min_cost", type=float)
                max_cost = request.args.get("max_cost", type=float)
                sort_by = request.args.get("sort_by", "total_cost")
                sort_order = request.args.get("sort_order", "desc")

                # Get base breakdown
                breakdown = cost_breakdown_api._get_cost_breakdown(
                    service_type=service_type,
                    time_period=time_period,
                    operation_type=operation_type,
                    start_date=start_date,
                    end_date=end_date,
                    group_by=group_by,
                )

                # Apply additional filters
                if min_cost is not None or max_cost is not None:
                    breakdown = self._apply_cost_filter(breakdown, min_cost, max_cost)

                # Apply sorting
                breakdown = self._apply_sorting(breakdown, sort_by, sort_order)

                return jsonify(breakdown)

            except Exception as e:
                self.logger.error(f"Error getting detailed breakdown: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/cost-alerts")
        def api_cost_alerts():
            """API endpoint for cost-related alerts and warnings."""
            try:
                alerts = self._generate_cost_alerts()
                return jsonify(alerts)

            except Exception as e:
                self.logger.error(f"Error generating cost alerts: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/export/<format_type>")
        def api_enhanced_export(format_type):
            """API endpoint for enhanced data export."""
            try:
                export_type = request.args.get("export_type", "dashboard")
                time_period = request.args.get("time_period", "monthly")
                include_trends = (
                    request.args.get("include_trends", "true").lower() == "true"
                )
                include_recommendations = (
                    request.args.get("include_recommendations", "true").lower()
                    == "true"
                )

                exported_data = self._export_enhanced_data(
                    format_type,
                    export_type,
                    time_period,
                    include_trends,
                    include_recommendations,
                )

                if format_type.lower() == "json":
                    return Response(
                        exported_data,
                        mimetype="application/json",
                        headers={
                            "Content-Disposition": f"attachment; filename=enhanced_cost_report_{export_type}_{time_period}.json"
                        },
                    )
                elif format_type.lower() == "csv":
                    return Response(
                        exported_data,
                        mimetype="text/csv",
                        headers={
                            "Content-Disposition": f"attachment; filename=enhanced_cost_report_{export_type}_{time_period}.csv"
                        },
                    )
                else:
                    return jsonify({"error": f"Unsupported format: {format_type}"}), 400

            except Exception as e:
                self.logger.error(f"Error exporting enhanced data: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/enhanced/health")
        def api_enhanced_health():
            """API endpoint for enhanced dashboard health check."""
            try:
                health_status = cost_metrics_integration.health_check()

                # Add dashboard-specific health checks
                health_status["enhanced_dashboard"] = {
                    "status": "healthy",
                    "version": "1.0.0",
                    "features": {
                        "real_time_streaming": True,
                        "advanced_analytics": True,
                        "cost_optimization": True,
                        "multi_format_export": True,
                    },
                }

                return jsonify(health_status)

            except Exception as e:
                self.logger.error(f"Error getting enhanced health status: {e}")
                return jsonify({"error": str(e)}), 500

    def _register_socketio_handlers(self):
        """Register SocketIO handlers for real-time updates."""

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection for enhanced dashboard."""
            self.logger.info(f"Enhanced dashboard client {request.sid} connected")

            # Send initial enhanced data
            try:
                initial_data = {
                    "dashboard_data": cost_metrics_integration.get_integrated_dashboard_data(),
                    "efficiency_metrics": cost_metrics_integration.get_cost_efficiency_metrics(),
                    "alerts": self._generate_cost_alerts(),
                }
                self.socketio.emit(
                    "enhanced_initial_data", initial_data, room=request.sid
                )
            except Exception as e:
                self.logger.error(f"Error sending initial data: {e}")

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            self.logger.info(f"Enhanced dashboard client {request.sid} disconnected")

        @self.socketio.on("subscribe_enhanced_updates")
        def handle_subscribe_enhanced(data):
            """Handle subscription to enhanced update types."""
            update_types = data.get("types", ["all"])
            filters = data.get("filters", {})

            # Store subscription preferences (you might want to persist this)
            self.logger.info(
                f"Client {request.sid} subscribed to enhanced updates: {update_types}"
            )

    def _apply_service_filter(
        self, data: Dict[str, Any], service_filter: str
    ) -> Dict[str, Any]:
        """Apply service filter to dashboard data."""
        # This would filter the data based on service type
        # Implementation depends on the data structure
        return data

    def _apply_date_filter(
        self, data: Dict[str, Any], start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Apply date range filter to dashboard data."""
        # This would filter the data based on date range
        # Implementation depends on the data structure
        return data

    def _apply_cost_filter(
        self,
        breakdown: Dict[str, Any],
        min_cost: Optional[float],
        max_cost: Optional[float],
    ) -> Dict[str, Any]:
        """Apply cost range filter to breakdown data."""
        if "breakdown" not in breakdown:
            return breakdown

        filtered_items = []
        for item in breakdown["breakdown"]:
            total_cost = item.get("total_cost", 0)

            if min_cost is not None and total_cost < min_cost:
                continue
            if max_cost is not None and total_cost > max_cost:
                continue

            filtered_items.append(item)

        breakdown["breakdown"] = filtered_items

        # Recalculate summary
        if filtered_items:
            breakdown["summary"]["total_cost"] = sum(
                item.get("total_cost", 0) for item in filtered_items
            )
            breakdown["summary"]["total_transactions"] = sum(
                item.get("transaction_count", 0) for item in filtered_items
            )
            breakdown["summary"]["avg_transaction_cost"] = (
                breakdown["summary"]["total_cost"]
                / breakdown["summary"]["total_transactions"]
                if breakdown["summary"]["total_transactions"] > 0
                else 0
            )

        return breakdown

    def _apply_sorting(
        self, breakdown: Dict[str, Any], sort_by: str, sort_order: str
    ) -> Dict[str, Any]:
        """Apply sorting to breakdown data."""
        if "breakdown" not in breakdown:
            return breakdown

        reverse = sort_order.lower() == "desc"

        try:
            breakdown["breakdown"].sort(
                key=lambda x: x.get(sort_by, 0), reverse=reverse
            )
        except (KeyError, TypeError):
            # Fallback to default sorting
            breakdown["breakdown"].sort(
                key=lambda x: x.get("total_cost", 0), reverse=True
            )

        return breakdown

    def _generate_cost_alerts(self) -> Dict[str, Any]:
        """Generate cost-related alerts and warnings."""
        alerts = {"alerts": [], "warnings": [], "info": [], "total_count": 0}

        try:
            # Get current metrics
            efficiency_metrics = cost_metrics_integration.get_cost_efficiency_metrics()
            dashboard_data = cost_metrics_integration.get_integrated_dashboard_data()

            # Check optimization score
            optimization_score = efficiency_metrics.get("optimization_score", 50)
            if optimization_score < 30:
                alerts["alerts"].append(
                    {
                        "type": "optimization",
                        "severity": "high",
                        "message": f"Low optimization score: {optimization_score:.1f}/100",
                        "recommendation": "Review cost optimization recommendations immediately",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            elif optimization_score < 60:
                alerts["warnings"].append(
                    {
                        "type": "optimization",
                        "severity": "medium",
                        "message": f"Moderate optimization score: {optimization_score:.1f}/100",
                        "recommendation": "Consider implementing cost optimization measures",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Check cost volatility
            trends = efficiency_metrics.get("efficiency_trends", {})
            volatility = trends.get("volatility", 0)
            if volatility > 0.5:
                alerts["warnings"].append(
                    {
                        "type": "volatility",
                        "severity": "medium",
                        "message": f"High cost volatility detected: {volatility:.2f}",
                        "recommendation": "Implement cost smoothing strategies",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Check growth rate
            growth_rate = trends.get("growth_rate", 0)
            if abs(growth_rate) > 50:
                alerts["alerts"].append(
                    {
                        "type": "growth",
                        "severity": "high",
                        "message": f"Extreme cost growth rate: {growth_rate:.1f}%",
                        "recommendation": "Immediate review of cost drivers required",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            elif abs(growth_rate) > 25:
                alerts["warnings"].append(
                    {
                        "type": "growth",
                        "severity": "medium",
                        "message": f"High cost growth rate: {growth_rate:.1f}%",
                        "recommendation": "Monitor cost trends closely",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Add informational alerts for positive trends
            if optimization_score > 80:
                alerts["info"].append(
                    {
                        "type": "optimization",
                        "severity": "info",
                        "message": f"Excellent optimization score: {optimization_score:.1f}/100",
                        "recommendation": "Current cost management is performing well",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            alerts["total_count"] = (
                len(alerts["alerts"]) + len(alerts["warnings"]) + len(alerts["info"])
            )

        except Exception as e:
            self.logger.error(f"Error generating cost alerts: {e}")
            alerts["alerts"].append(
                {
                    "type": "system",
                    "severity": "high",
                    "message": f"Error generating cost alerts: {str(e)}",
                    "recommendation": "Check system health and retry",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return alerts

    def _export_enhanced_data(
        self,
        format_type: str,
        export_type: str,
        time_period: str,
        include_trends: bool,
        include_recommendations: bool,
    ) -> str:
        """Export enhanced cost data in specified format."""
        try:
            # Compile comprehensive export data
            export_data = {
                "export_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "export_type": export_type,
                    "time_period": time_period,
                    "format": format_type,
                    "includes": {
                        "trends": include_trends,
                        "recommendations": include_recommendations,
                    },
                }
            }

            if export_type == "dashboard":
                export_data["dashboard_data"] = (
                    cost_metrics_integration.get_integrated_dashboard_data(time_period)
                )
                export_data["efficiency_metrics"] = (
                    cost_metrics_integration.get_cost_efficiency_metrics()
                )
                export_data["alerts"] = self._generate_cost_alerts()

            if include_trends:
                export_data["trend_analysis"] = (
                    cost_analytics_engine.analyze_cost_trends(
                        days_back=90 if time_period == "monthly" else 30,
                        forecast_days=30 if time_period == "monthly" else 7,
                    )
                )

            if include_recommendations:
                if (
                    include_trends
                    and "trend_analysis" in export_data
                    and "error" not in export_data["trend_analysis"]
                ):
                    export_data["recommendations"] = (
                        cost_analytics_engine.generate_cost_optimization_recommendations(
                            export_data["trend_analysis"]
                        )
                    )

            if format_type.lower() == "json":
                return json.dumps(export_data, indent=2, default=str)
            elif format_type.lower() == "csv":
                return self._convert_to_csv(export_data)
            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            self.logger.error(f"Error exporting enhanced data: {e}")
            return json.dumps({"error": str(e)})

    def _convert_to_csv(self, data: Dict[str, Any]) -> str:
        """Convert export data to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write metadata
        writer.writerow(["Enhanced Cost Dashboard Export"])
        writer.writerow(["Generated At", data["export_metadata"]["generated_at"]])
        writer.writerow(["Export Type", data["export_metadata"]["export_type"]])
        writer.writerow(["Time Period", data["export_metadata"]["time_period"]])
        writer.writerow([])

        # Write dashboard summary
        if "dashboard_data" in data:
            dashboard = data["dashboard_data"]
            writer.writerow(["Dashboard Summary"])

            if (
                "cost_breakdown" in dashboard
                and "summary" in dashboard["cost_breakdown"]
            ):
                summary = dashboard["cost_breakdown"]["summary"]
                writer.writerow(["Total Cost", summary.get("total_cost", 0)])
                writer.writerow(
                    ["Total Transactions", summary.get("total_transactions", 0)]
                )
                writer.writerow(
                    ["Avg Transaction Cost", summary.get("avg_transaction_cost", 0)]
                )

            writer.writerow([])

        # Write efficiency metrics
        if "efficiency_metrics" in data:
            efficiency = data["efficiency_metrics"]
            writer.writerow(["Efficiency Metrics"])
            writer.writerow(
                ["Optimization Score", efficiency.get("optimization_score", 0)]
            )

            trends = efficiency.get("efficiency_trends", {})
            writer.writerow(["Growth Rate %", trends.get("growth_rate", 0)])
            writer.writerow(["Volatility", trends.get("volatility", 0)])
            writer.writerow(
                ["Trend Direction", trends.get("trend_direction", "unknown")]
            )
            writer.writerow([])

        # Write alerts summary
        if "alerts" in data:
            alerts = data["alerts"]
            writer.writerow(["Alerts Summary"])
            writer.writerow(["High Priority Alerts", len(alerts.get("alerts", []))])
            writer.writerow(["Warnings", len(alerts.get("warnings", []))])
            writer.writerow(["Info Messages", len(alerts.get("info", []))])
            writer.writerow([])

        return output.getvalue()

    def run(self):
        """Run the enhanced cost dashboard server."""
        try:
            self.logger.info(
                f"Starting enhanced cost dashboard on {self.host}:{self.port}"
            )
            self.socketio.run(
                self.app, host=self.host, port=self.port, debug=self.debug
            )
        except Exception as e:
            self.logger.error(f"Error starting enhanced dashboard server: {e}")
            raise

    def create_wsgi_app(self):
        """Create WSGI application for production deployment."""
        return self.app


def create_enhanced_dashboard_templates():
    """Create enhanced HTML templates for the dashboard."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    os.makedirs(template_dir, exist_ok=True)

    # Enhanced dashboard template
    enhanced_dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Cost Dashboard - LeadFactory</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: rgba(255, 255, 255, 0.95);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }
        .header h1 {
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 0;
            color: #7f8c8d;
            font-size: 1.1em;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255, 255, 255, 0.95);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        .metric-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .metric-change {
            font-size: 0.9em;
            margin-top: 8px;
            display: flex;
            align-items: center;
        }
        .metric-change.positive { color: #27ae60; }
        .metric-change.negative { color: #e74c3c; }
        .metric-change.neutral { color: #95a5a6; }
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: #ecf0f1;
            color: #2c3e50;
        }
        .btn-secondary:hover {
            background: #d5dbdb;
        }
        select, input {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            background: white;
        }
        .chart-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
        }
        .chart-container h3 {
            margin-top: 0;
            color: #2c3e50;
            font-size: 1.4em;
            font-weight: 500;
        }
        .alert-banner {
            background: linear-gradient(45deg, #ff6b6b, #ee5a52);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(255, 107, 107, 0.3);
        }
        .warning-banner {
            background: linear-gradient(45deg, #ffa726, #ff8f65);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(255, 167, 38, 0.3);
        }
        .loading {
            text-align: center;
            padding: 50px;
            color: #7f8c8d;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-healthy { background-color: #27ae60; }
        .status-warning { background-color: #f39c12; }
        .status-error { background-color: #e74c3c; }
        .realtime-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(39, 174, 96, 0.9);
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 1000;
        }
        .realtime-indicator.disconnected {
            background: rgba(231, 76, 60, 0.9);
        }
        .optimization-score {
            text-align: center;
            margin: 20px 0;
        }
        .score-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            margin: 0 auto 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2em;
            font-weight: bold;
            color: white;
        }
        .score-excellent { background: linear-gradient(45deg, #27ae60, #2ecc71); }
        .score-good { background: linear-gradient(45deg, #f39c12, #e67e22); }
        .score-poor { background: linear-gradient(45deg, #e74c3c, #c0392b); }
    </style>
</head>
<body>
    <div class="realtime-indicator" id="realtimeStatus">
        <span class="status-indicator status-healthy"></span>
        Real-time Connected
    </div>

    <div class="container">
        <div class="header">
            <h1>Enhanced Cost Dashboard</h1>
            <p>Advanced cost monitoring, analytics, and optimization for LeadFactory</p>
        </div>

        <div id="alert-container"></div>

        <div class="controls">
            <select id="time-period-selector">
                <option value="hourly">Hourly</option>
                <option value="daily" selected>Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
            </select>
            <select id="service-filter">
                <option value="">All Services</option>
                <option value="openai">OpenAI</option>
                <option value="semrush">Semrush</option>
                <option value="gpu">GPU</option>
                <option value="screenshotone">ScreenshotOne</option>
            </select>
            <input type="date" id="start-date" />
            <input type="date" id="end-date" />
            <button class="btn btn-primary" onclick="refreshData()">Refresh</button>
            <button class="btn btn-secondary" onclick="exportData('json')">Export JSON</button>
            <button class="btn btn-secondary" onclick="exportData('csv')">Export CSV</button>
        </div>

        <div id="metrics-container" class="dashboard-grid">
            <div class="loading">Loading enhanced metrics...</div>
        </div>

        <div class="chart-container">
            <h3>Cost Trends & Forecasting</h3>
            <canvas id="trendsChart" width="400" height="200"></canvas>
        </div>

        <div class="chart-container">
            <h3>Service Cost Breakdown</h3>
            <canvas id="breakdownChart" width="400" height="200"></canvas>
        </div>

        <div class="chart-container">
            <h3>Optimization Recommendations</h3>
            <div id="recommendations-container">
                <div class="loading">Loading recommendations...</div>
            </div>
        </div>
    </div>

    <script>
        let socket;
        let trendsChart, breakdownChart;
        let currentData = {};

        // Initialize socket connection
        function initializeSocket() {
            socket = io();

            socket.on('connect', function() {
                updateRealtimeStatus(true);
                console.log('Connected to enhanced cost dashboard');

                // Subscribe to enhanced updates
                socket.emit('subscribe_enhanced_updates', {
                    types: ['dashboard', 'efficiency', 'alerts'],
                    filters: {}
                });
            });

            socket.on('disconnect', function() {
                updateRealtimeStatus(false);
                console.log('Disconnected from enhanced cost dashboard');
            });

            socket.on('enhanced_initial_data', function(data) {
                console.log('Received initial enhanced data:', data);
                updateDashboard(data);
            });

            socket.on('integrated_cost_update', function(data) {
                console.log('Received real-time cost update:', data);
                updateRealtimeData(data);
            });
        }

        function updateRealtimeStatus(connected) {
            const indicator = document.getElementById('realtimeStatus');
            const statusDot = indicator.querySelector('.status-indicator');

            if (connected) {
                indicator.innerHTML = '<span class="status-indicator status-healthy"></span>Real-time Connected';
                indicator.classList.remove('disconnected');
            } else {
                indicator.innerHTML = '<span class="status-indicator status-error"></span>Real-time Disconnected';
                indicator.classList.add('disconnected');
            }
        }

        async function loadEnhancedDashboardData() {
            try {
                const timePeriod = document.getElementById('time-period-selector').value;
                const serviceFilter = document.getElementById('service-filter').value;
                const startDate = document.getElementById('start-date').value;
                const endDate = document.getElementById('end-date').value;

                const params = new URLSearchParams({
                    time_period: timePeriod
                });

                if (serviceFilter) params.append('service_filter', serviceFilter);
                if (startDate) params.append('start_date', startDate);
                if (endDate) params.append('end_date', endDate);

                const [dashboardResponse, trendsResponse, efficiencyResponse, alertsResponse] = await Promise.all([
                    fetch(`/api/enhanced/dashboard-data?${params}`),
                    fetch(`/api/enhanced/cost-trends?service_type=${serviceFilter}`),
                    fetch('/api/enhanced/cost-efficiency'),
                    fetch('/api/enhanced/cost-alerts')
                ]);

                const [dashboardData, trendsData, efficiencyData, alertsData] = await Promise.all([
                    dashboardResponse.json(),
                    trendsResponse.json(),
                    efficiencyResponse.json(),
                    alertsResponse.json()
                ]);

                currentData = {
                    dashboard: dashboardData,
                    trends: trendsData,
                    efficiency: efficiencyData,
                    alerts: alertsData
                };

                updateDashboard(currentData);

            } catch (error) {
                console.error('Error loading enhanced dashboard data:', error);
                showError('Error loading dashboard data: ' + error.message);
            }
        }

        function updateDashboard(data) {
            updateMetrics(data);
            updateCharts(data);
            updateAlerts(data.alerts || {});
            updateRecommendations(data);
        }

        function updateMetrics(data) {
            const container = document.getElementById('metrics-container');
            container.innerHTML = '';

            // Create optimization score card
            const optimizationCard = createOptimizationScoreCard(data.efficiency);
            container.appendChild(optimizationCard);

            // Create cost summary cards
            if (data.dashboard && data.dashboard.cost_breakdown) {
                const summary = data.dashboard.cost_breakdown.summary;
                const cards = [
                    {
                        title: 'Total Cost',
                        value: `$${(summary.total_cost || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`,
                        change: calculateChange(summary.total_cost, 'cost'),
                        icon: '💰'
                    },
                    {
                        title: 'Transactions',
                        value: (summary.total_transactions || 0).toLocaleString(),
                        change: calculateChange(summary.total_transactions, 'transactions'),
                        icon: '📊'
                    },
                    {
                        title: 'Avg Cost/Transaction',
                        value: `$${(summary.avg_transaction_cost || 0).toFixed(4)}`,
                        change: calculateChange(summary.avg_transaction_cost, 'avg_cost'),
                        icon: '⚡'
                    }
                ];

                cards.forEach(cardData => {
                    const card = createMetricCard(cardData);
                    container.appendChild(card);
                });
            }

            // Create efficiency metrics cards
            if (data.efficiency && data.efficiency.efficiency_trends) {
                const trends = data.efficiency.efficiency_trends;
                const efficiencyCards = [
                    {
                        title: 'Growth Rate',
                        value: `${(trends.growth_rate || 0).toFixed(1)}%`,
                        change: trends.trend_direction,
                        icon: '📈'
                    },
                    {
                        title: 'Cost Volatility',
                        value: (trends.volatility || 0).toFixed(3),
                        change: trends.volatility > 0.3 ? 'high' : 'normal',
                        icon: '📊'
                    }
                ];

                efficiencyCards.forEach(cardData => {
                    const card = createMetricCard(cardData);
                    container.appendChild(card);
                });
            }
        }

        function createOptimizationScoreCard(efficiencyData) {
            const card = document.createElement('div');
            card.className = 'card optimization-score';

            const score = efficiencyData ? efficiencyData.optimization_score || 50 : 50;
            const scoreClass = score >= 80 ? 'score-excellent' : score >= 60 ? 'score-good' : 'score-poor';

            card.innerHTML = `
                <h4>🎯 Optimization Score</h4>
                <div class="score-circle ${scoreClass}">${score.toFixed(0)}</div>
                <p>Overall cost optimization effectiveness</p>
            `;

            return card;
        }

        function createMetricCard(cardData) {
            const card = document.createElement('div');
            card.className = 'card';

            const changeClass = getChangeClass(cardData.change);
            const changeIcon = getChangeIcon(cardData.change);

            card.innerHTML = `
                <h4>${cardData.icon} ${cardData.title}</h4>
                <div class="metric-value">${cardData.value}</div>
                <div class="metric-change ${changeClass}">
                    ${changeIcon} ${formatChange(cardData.change)}
                </div>
            `;

            return card;
        }

        function updateCharts(data) {
            // Update trends chart
            if (data.trends && data.trends.historical_data) {
                updateTrendsChart(data.trends);
            }

            // Update breakdown chart
            if (data.dashboard && data.dashboard.cost_breakdown) {
                updateBreakdownChart(data.dashboard.cost_breakdown);
            }
        }

        function updateTrendsChart(trendsData) {
            const ctx = document.getElementById('trendsChart').getContext('2d');

            if (trendsChart) {
                trendsChart.destroy();
            }

            const historicalData = trendsData.historical_data || [];
            const forecastData = trendsData.forecasts && trendsData.forecasts.ensemble_forecast
                ? trendsData.forecasts.ensemble_forecast.values || []
                : [];

            trendsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [
                        ...historicalData.map(d => new Date(d.date).toLocaleDateString()),
                        ...forecastData.map((_, i) => `Forecast +${i+1}`)
                    ],
                    datasets: [
                        {
                            label: 'Historical Costs',
                            data: historicalData.map(d => d.cost),
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Forecast',
                            data: [...Array(historicalData.length).fill(null), ...forecastData],
                            borderColor: '#764ba2',
                            backgroundColor: 'rgba(118, 75, 162, 0.1)',
                            borderDash: [5, 5],
                            tension: 0.4,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Cost Trends with AI Forecasting'
                        }
                    },
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

        function updateBreakdownChart(breakdownData) {
            const ctx = document.getElementById('breakdownChart').getContext('2d');

            if (breakdownChart) {
                breakdownChart.destroy();
            }

            const services = breakdownData.service_breakdown ? breakdownData.service_breakdown.services || [] : [];

            breakdownChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: services.map(s => s.service),
                    datasets: [{
                        data: services.map(s => s.total_cost),
                        backgroundColor: [
                            '#667eea',
                            '#764ba2',
                            '#f093fb',
                            '#f5576c',
                            '#4facfe',
                            '#00f2fe'
                        ],
                        borderWidth: 2,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const percentage = context.parsed ? ((context.parsed / services.reduce((a, b) => a + b.total_cost, 0)) * 100).toFixed(1) : 0;
                                    return context.label + ': $' + context.parsed.toLocaleString() + ' (' + percentage + '%)';
                                }
                            }
                        }
                    }
                }
            });
        }

        function updateAlerts(alertsData) {
            const container = document.getElementById('alert-container');
            container.innerHTML = '';

            if (alertsData.alerts && alertsData.alerts.length > 0) {
                alertsData.alerts.forEach(alert => {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert-banner';
                    alertDiv.innerHTML = `
                        <strong>${alert.type.toUpperCase()}:</strong> ${alert.message}
                        <br><small><em>Recommendation: ${alert.recommendation}</em></small>
                    `;
                    container.appendChild(alertDiv);
                });
            }

            if (alertsData.warnings && alertsData.warnings.length > 0) {
                alertsData.warnings.forEach(warning => {
                    const warningDiv = document.createElement('div');
                    warningDiv.className = 'warning-banner';
                    warningDiv.innerHTML = `
                        <strong>${warning.type.toUpperCase()}:</strong> ${warning.message}
                        <br><small><em>Recommendation: ${warning.recommendation}</em></small>
                    `;
                    container.appendChild(warningDiv);
                });
            }
        }

        async function updateRecommendations(data) {
            const container = document.getElementById('recommendations-container');

            try {
                const response = await fetch('/api/enhanced/optimization-recommendations');
                const recommendations = await response.json();

                if (recommendations.error) {
                    container.innerHTML = `<p class="error">Error loading recommendations: ${recommendations.error}</p>`;
                    return;
                }

                container.innerHTML = '';

                if (recommendations.recommendations && recommendations.recommendations.length > 0) {
                    recommendations.recommendations.slice(0, 5).forEach((rec, index) => {
                        const recDiv = document.createElement('div');
                        recDiv.className = 'card';
                        recDiv.style.marginBottom = '15px';

                        const priorityColor = rec.priority === 'high' ? '#e74c3c' :
                                            rec.priority === 'medium' ? '#f39c12' : '#95a5a6';

                        recDiv.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <h5 style="margin: 0; color: #2c3e50;">${rec.title}</h5>
                                <span style="background: ${priorityColor}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                                    ${rec.priority.toUpperCase()}
                                </span>
                            </div>
                            <p style="margin: 10px 0; color: #7f8c8d;">${rec.description}</p>
                            <p style="margin: 10px 0; color: #2c3e50;"><strong>Impact:</strong> ${rec.impact}</p>
                            ${rec.estimated_savings > 0 ? `<p style="margin: 0; color: #27ae60;"><strong>Potential Savings:</strong> $${rec.estimated_savings.toFixed(2)}</p>` : ''}
                        `;

                        container.appendChild(recDiv);
                    });
                } else {
                    container.innerHTML = '<p style="text-align: center; color: #7f8c8d;">No optimization recommendations available at this time.</p>';
                }

            } catch (error) {
                container.innerHTML = `<p class="error">Error loading recommendations: ${error.message}</p>`;
            }
        }

        function updateRealtimeData(data) {
            // Update real-time indicators
            console.log('Real-time update:', data);

            // You could update specific metrics here without full refresh
            // For now, we'll just log the data
        }

        // Helper functions
        function calculateChange(value, type) {
            // This would calculate actual change based on historical data
            // For demo purposes, return random change
            const changes = ['increasing', 'decreasing', 'stable'];
            return changes[Math.floor(Math.random() * changes.length)];
        }

        function getChangeClass(change) {
            if (typeof change === 'string') {
                if (change === 'increasing' || change === 'good' || change === 'normal') return 'positive';
                if (change === 'decreasing' || change === 'high') return 'negative';
                return 'neutral';
            }
            return change > 0 ? 'positive' : change < 0 ? 'negative' : 'neutral';
        }

        function getChangeIcon(change) {
            const changeClass = getChangeClass(change);
            return changeClass === 'positive' ? '▲' : changeClass === 'negative' ? '▼' : '●';
        }

        function formatChange(change) {
            if (typeof change === 'string') return change;
            if (typeof change === 'number') return `${change > 0 ? '+' : ''}${change.toFixed(1)}%`;
            return 'No change';
        }

        function showError(message) {
            const container = document.getElementById('alert-container');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert-banner';
            errorDiv.innerHTML = `<strong>Error:</strong> ${message}`;
            container.appendChild(errorDiv);
        }

        function refreshData() {
            loadEnhancedDashboardData();
        }

        function exportData(format) {
            const timePeriod = document.getElementById('time-period-selector').value;
            const params = new URLSearchParams({
                time_period: timePeriod,
                export_type: 'dashboard',
                include_trends: 'true',
                include_recommendations: 'true'
            });

            window.open(`/api/enhanced/export/${format}?${params}`, '_blank');
        }

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            // Set default dates
            const today = new Date();
            const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

            document.getElementById('end-date').value = today.toISOString().split('T')[0];
            document.getElementById('start-date').value = thirtyDaysAgo.toISOString().split('T')[0];

            // Initialize socket and load data
            initializeSocket();
            loadEnhancedDashboardData();

            // Set up event listeners
            document.getElementById('time-period-selector').addEventListener('change', loadEnhancedDashboardData);
            document.getElementById('service-filter').addEventListener('change', loadEnhancedDashboardData);
            document.getElementById('start-date').addEventListener('change', loadEnhancedDashboardData);
            document.getElementById('end-date').addEventListener('change', loadEnhancedDashboardData);
        });

        // Auto-refresh every 2 minutes
        setInterval(loadEnhancedDashboardData, 2 * 60 * 1000);
    </script>
</body>
</html>
    """

    with open(os.path.join(template_dir, "enhanced_cost_dashboard.html"), "w") as f:
        f.write(enhanced_dashboard_html)


# Global instance
enhanced_dashboard = EnhancedCostDashboard()

# Create templates if they don't exist
create_enhanced_dashboard_templates()


def run_enhanced_dashboard(
    host: str = "127.0.0.1", port: int = 5002, debug: bool = False
):
    """Run the enhanced cost dashboard server."""
    dashboard_instance = EnhancedCostDashboard(host, port, debug)
    dashboard_instance.run()


if __name__ == "__main__":
    run_enhanced_dashboard(debug=True)
