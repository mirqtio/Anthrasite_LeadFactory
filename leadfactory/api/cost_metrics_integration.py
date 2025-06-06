"""
Cost Metrics Integration Module
==============================

This module integrates the enhanced cost breakdown API with existing infrastructure:
- SQLite databases (cost tracking, purchase metrics, etc.)
- Prometheus metrics system
- Existing dashboard and monitoring systems
- Real-time streaming capabilities

It provides a unified interface for cost analytics across all LeadFactory systems.
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from flask import Flask

try:
    from flask_socketio import SocketIO

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None

from leadfactory.analytics.cost_analytics import cost_analytics_engine
from leadfactory.api.cost_breakdown_api import cost_breakdown_api
from leadfactory.cost.cost_aggregation import cost_aggregation_service
from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import (
    COST_COUNTER,
    COST_PER_LEAD,
    DAILY_REVENUE,
    METRICS_AVAILABLE,
    record_metric,
)

logger = get_logger(__name__)


class CostMetricsIntegration:
    """Unified cost metrics integration system."""

    def __init__(self):
        """Initialize the cost metrics integration system."""
        self.logger = get_logger(f"{__name__}.CostMetricsIntegration")
        self._lock = threading.Lock()
        self._integration_active = False
        self._update_thread = None

        # Database connections
        self._db_paths = self._discover_database_paths()

        # Integration state
        self._last_sync_time = None
        self._sync_interval = 60  # seconds

        # Metrics cache
        self._metrics_cache = {}
        self._cache_expiry = {}

        self.logger.info("Cost metrics integration initialized")

    def _discover_database_paths(self) -> Dict[str, str]:
        """Discover all relevant database paths in the system."""
        db_paths = {}

        # Standard database locations
        base_path = Path(__file__).parent.parent.parent

        # Cost tracking database
        if hasattr(cost_tracker, "db_path"):
            db_paths["cost_tracking"] = cost_tracker.db_path

        # Look for other databases
        potential_dbs = [
            "purchase_metrics.db",
            "ab_tests.db",
            "budget_config.db",
            "conversion_tracking.db",
            "warmup_scheduler.db",
            "payments.db",
            "test_metrics.db",
        ]

        for db_name in potential_dbs:
            db_path = base_path / db_name
            if db_path.exists():
                db_paths[db_name.replace(".db", "")] = str(db_path)

        # Cost aggregation database
        if hasattr(cost_aggregation_service, "db_path"):
            db_paths["cost_aggregation"] = cost_aggregation_service.db_path

        self.logger.info(f"Discovered databases: {list(db_paths.keys())}")
        return db_paths

    def start_integration(self):
        """Start the cost metrics integration system."""
        with self._lock:
            if self._integration_active:
                self.logger.warning("Integration already active")
                return

            self._integration_active = True

            # Start background sync thread
            self._update_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self._update_thread.start()

            # Perform initial sync
            self._sync_all_metrics()

            self.logger.info("Cost metrics integration started")

    def stop_integration(self):
        """Stop the cost metrics integration system."""
        with self._lock:
            self._integration_active = False

        if self._update_thread:
            self._update_thread.join(timeout=10)

        self.logger.info("Cost metrics integration stopped")

    def _sync_loop(self):
        """Background thread for syncing metrics."""
        while self._integration_active:
            try:
                self._sync_all_metrics()
                time.sleep(self._sync_interval)
            except Exception as e:
                self.logger.error(f"Error in sync loop: {e}")
                time.sleep(self._sync_interval * 2)  # Wait longer on error

    def _sync_all_metrics(self):
        """Sync all metrics to Prometheus and update caches."""
        try:
            # Sync cost tracking metrics
            self._sync_cost_tracking_metrics()

            # Sync purchase metrics
            self._sync_purchase_metrics()

            # Sync aggregated metrics
            self._sync_aggregated_metrics()

            # Update analytics cache
            self._update_analytics_cache()

            self._last_sync_time = datetime.now()
            self.logger.debug("All metrics synced successfully")

        except Exception as e:
            self.logger.error(f"Error syncing metrics: {e}")

    def _sync_cost_tracking_metrics(self):
        """Sync cost tracking data to Prometheus metrics."""
        if not METRICS_AVAILABLE:
            return

        try:
            # Get daily cost breakdown
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()

            # Update Prometheus metrics
            for service, operations in daily_breakdown.items():
                for operation, cost in operations.items():
                    record_metric(
                        COST_COUNTER, cost, api_name=service, operation=operation
                    )

            # Get monthly costs for cost per lead calculation
            monthly_costs = cost_tracker.get_monthly_costs()
            total_monthly_cost = monthly_costs.get("spent", 0)

            # Estimate leads processed (this would be better from actual data)
            estimated_leads = self._estimate_monthly_leads()
            if estimated_leads > 0:
                cost_per_lead = total_monthly_cost / estimated_leads
                record_metric(COST_PER_LEAD, cost_per_lead, vertical="all")

            self.logger.debug("Cost tracking metrics synced")

        except Exception as e:
            self.logger.error(f"Error syncing cost tracking metrics: {e}")

    def _sync_purchase_metrics(self):
        """Sync purchase and revenue metrics."""
        if not METRICS_AVAILABLE:
            return

        try:
            # Try to get revenue from purchase_metrics database
            if "purchase_metrics" in self._db_paths:
                daily_revenue = self._get_daily_revenue_from_db()
                if daily_revenue > 0:
                    record_metric(
                        DAILY_REVENUE,
                        daily_revenue * 100,  # Convert to cents
                        date=datetime.now().strftime("%Y-%m-%d"),
                    )

            self.logger.debug("Purchase metrics synced")

        except Exception as e:
            self.logger.error(f"Error syncing purchase metrics: {e}")

    def _sync_aggregated_metrics(self):
        """Sync aggregated cost and revenue metrics."""
        try:
            # Get today's aggregated data
            today = datetime.now().strftime("%Y-%m-%d")
            daily_summary = cost_aggregation_service.get_daily_summary(today)

            if daily_summary:
                # Update metrics cache for dashboard
                self._metrics_cache["daily_summary"] = daily_summary
                self._cache_expiry["daily_summary"] = datetime.now() + timedelta(
                    minutes=5
                )

            self.logger.debug("Aggregated metrics synced")

        except Exception as e:
            self.logger.error(f"Error syncing aggregated metrics: {e}")

    def _update_analytics_cache(self):
        """Update analytics cache with recent analysis."""
        try:
            # Generate trend analysis for the dashboard
            trends = cost_analytics_engine.analyze_cost_trends(
                service_type=None, days_back=30, forecast_days=7
            )

            self._metrics_cache["trends"] = trends
            self._cache_expiry["trends"] = datetime.now() + timedelta(minutes=10)

            # Generate optimization recommendations
            if trends and "error" not in trends:
                recommendations = (
                    cost_analytics_engine.generate_cost_optimization_recommendations(
                        trends
                    )
                )
                self._metrics_cache["recommendations"] = recommendations
                self._cache_expiry["recommendations"] = datetime.now() + timedelta(
                    minutes=15
                )

            self.logger.debug("Analytics cache updated")

        except Exception as e:
            self.logger.error(f"Error updating analytics cache: {e}")

    def _get_daily_revenue_from_db(self) -> float:
        """Get daily revenue from purchase metrics database."""
        try:
            db_path = self._db_paths.get("purchase_metrics")
            if not db_path:
                return 0.0

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime("%Y-%m-%d")

            # Try different possible table structures
            revenue_queries = [
                f"SELECT SUM(amount) FROM purchases WHERE DATE(created_at) = '{today}'",
                f"SELECT SUM(revenue) FROM daily_metrics WHERE date = '{today}'",
                f"SELECT SUM(total_amount) FROM transactions WHERE DATE(timestamp) = '{today}'",
            ]

            for query in revenue_queries:
                try:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    if result and result[0]:
                        conn.close()
                        return float(result[0])
                except sqlite3.OperationalError:
                    continue  # Table doesn't exist, try next query

            conn.close()
            return 0.0

        except Exception as e:
            self.logger.error(f"Error getting daily revenue: {e}")
            return 0.0

    def _estimate_monthly_leads(self) -> int:
        """Estimate monthly leads processed for cost per lead calculation."""
        try:
            # This is a rough estimate - in production this should come from actual lead tracking
            # Try to get from cost tracking data based on transaction counts

            monthly_costs = cost_tracker.get_monthly_costs()
            operations = monthly_costs.get("operations", {})

            # Estimate based on enrichment operations (assuming 1 operation per lead)
            estimated_leads = 0
            for service, ops in operations.items():
                for operation, cost in ops.items():
                    if "enrich" in operation.lower() or "lead" in operation.lower():
                        # Rough estimate: $0.10 per lead enrichment
                        estimated_leads += int(cost / 0.10)

            # Fallback: use total transaction count as proxy
            if estimated_leads == 0:
                conn = sqlite3.connect(cost_tracker.db_path)
                cursor = conn.cursor()

                current_month = datetime.now()
                start_date = current_month.replace(day=1)

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM costs
                    WHERE timestamp >= ? AND service IN ('enrichment', 'scoring', 'mockup')
                """,
                    (start_date.isoformat(),),
                )

                result = cursor.fetchone()
                estimated_leads = result[0] if result else 0
                conn.close()

            return max(1, estimated_leads)  # Avoid division by zero

        except Exception as e:
            self.logger.error(f"Error estimating monthly leads: {e}")
            return 1

    def get_integrated_dashboard_data(
        self, time_period: str = "daily"
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard data from all integrated sources."""
        try:
            dashboard_data = {
                "timestamp": datetime.now().isoformat(),
                "time_period": time_period,
                "cost_breakdown": {},
                "revenue_data": {},
                "analytics": {},
                "recommendations": [],
                "system_health": {},
            }

            # Get cost breakdown from cost breakdown API
            cost_breakdown = cost_breakdown_api._get_cost_breakdown(
                time_period=time_period
            )
            dashboard_data["cost_breakdown"] = cost_breakdown

            # Get cached analytics if available
            if self._is_cached("trends"):
                dashboard_data["analytics"] = self._metrics_cache["trends"]

            if self._is_cached("recommendations"):
                dashboard_data["recommendations"] = self._metrics_cache[
                    "recommendations"
                ].get("recommendations", [])

            # Get aggregated revenue data
            if self._is_cached("daily_summary"):
                daily_summary = self._metrics_cache["daily_summary"]
                dashboard_data["revenue_data"] = {
                    "gross_revenue": daily_summary.get("gross_revenue_cents", 0) / 100,
                    "net_revenue": daily_summary.get("net_revenue_cents", 0) / 100,
                    "transactions": daily_summary.get("transaction_count", 0),
                }

            # Add system health indicators
            dashboard_data["system_health"] = {
                "integration_active": self._integration_active,
                "last_sync": (
                    self._last_sync_time.isoformat() if self._last_sync_time else None
                ),
                "databases_connected": len(self._db_paths),
                "prometheus_available": METRICS_AVAILABLE,
            }

            return dashboard_data

        except Exception as e:
            self.logger.error(f"Error getting integrated dashboard data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def get_cost_efficiency_metrics(self) -> Dict[str, Any]:
        """Get cost efficiency and ROI metrics across all services."""
        try:
            efficiency_metrics = {
                "cost_per_service": {},
                "efficiency_trends": {},
                "roi_metrics": {},
                "optimization_score": 0,
            }

            # Get cost breakdown by service
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()
            monthly_breakdown = cost_tracker.get_monthly_cost_breakdown()

            # Calculate cost efficiency by service
            for service, operations in monthly_breakdown.items():
                service_total = sum(operations.values())
                operation_count = len(
                    [op for op, cost in operations.items() if cost > 0]
                )

                efficiency_metrics["cost_per_service"][service] = {
                    "total_cost": service_total,
                    "operations_count": operation_count,
                    "avg_cost_per_operation": (
                        service_total / operation_count if operation_count > 0 else 0
                    ),
                }

            # Get trends from analytics cache
            if self._is_cached("trends"):
                trends = self._metrics_cache["trends"]
                efficiency_metrics["efficiency_trends"] = {
                    "growth_rate": trends.get("trend_metrics", {}).get(
                        "growth_rate_percent", 0
                    ),
                    "volatility": trends.get("volatility_analysis", {}).get(
                        "coefficient_of_variation", 0
                    ),
                    "trend_direction": trends.get("trend_metrics", {}).get(
                        "direction", "unknown"
                    ),
                }

            # Calculate optimization score (0-100)
            optimization_score = self._calculate_optimization_score(efficiency_metrics)
            efficiency_metrics["optimization_score"] = optimization_score

            return efficiency_metrics

        except Exception as e:
            self.logger.error(f"Error getting cost efficiency metrics: {e}")
            return {"error": str(e)}

    def _calculate_optimization_score(
        self, efficiency_metrics: Dict[str, Any]
    ) -> float:
        """Calculate an overall optimization score (0-100)."""
        try:
            score_factors = []

            # Factor 1: Cost volatility (lower is better)
            volatility = efficiency_metrics.get("efficiency_trends", {}).get(
                "volatility", 0.5
            )
            volatility_score = max(0, 100 - (volatility * 200))  # Invert and scale
            score_factors.append(volatility_score)

            # Factor 2: Growth rate (moderate growth is best)
            growth_rate = efficiency_metrics.get("efficiency_trends", {}).get(
                "growth_rate", 0
            )
            if abs(growth_rate) < 10:  # Within 10% is good
                growth_score = 100
            elif abs(growth_rate) < 25:  # Within 25% is okay
                growth_score = 70
            else:  # High growth/decline is concerning
                growth_score = 30
            score_factors.append(growth_score)

            # Factor 3: Service efficiency distribution
            service_costs = efficiency_metrics.get("cost_per_service", {})
            if service_costs:
                costs = [s["total_cost"] for s in service_costs.values()]
                if costs:
                    # Check if costs are well-distributed (no single service dominates)
                    max_cost = max(costs)
                    total_cost = sum(costs)
                    dominance_ratio = max_cost / total_cost if total_cost > 0 else 1

                    if dominance_ratio < 0.4:  # No service uses >40% of budget
                        distribution_score = 100
                    elif dominance_ratio < 0.6:  # No service uses >60% of budget
                        distribution_score = 70
                    else:
                        distribution_score = 40

                    score_factors.append(distribution_score)

            # Calculate overall score
            return sum(score_factors) / len(score_factors) if score_factors else 50

        except Exception as e:
            self.logger.error(f"Error calculating optimization score: {e}")
            return 50  # Default moderate score

    def stream_realtime_metrics(self, socketio):
        """Stream real-time metrics to connected clients."""
        try:
            # Get real-time cost data
            realtime_data = cost_breakdown_api._get_realtime_cost_data()

            # Add integration-specific data
            realtime_data.update(
                {
                    "integration_status": {
                        "active": self._integration_active,
                        "last_sync": (
                            self._last_sync_time.isoformat()
                            if self._last_sync_time
                            else None
                        ),
                        "databases_connected": len(self._db_paths),
                    },
                    "efficiency_score": self._calculate_optimization_score(
                        self.get_cost_efficiency_metrics()
                    ),
                }
            )

            # Emit to all connected clients
            socketio.emit("integrated_cost_update", realtime_data, room="cost_updates")

        except Exception as e:
            self.logger.error(f"Error streaming realtime metrics: {e}")

    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and not expired."""
        return (
            key in self._metrics_cache
            and key in self._cache_expiry
            and datetime.now() < self._cache_expiry[key]
        )

    def export_integrated_data(
        self, format_type: str = "json", time_period: str = "monthly"
    ) -> str:
        """Export comprehensive integrated data in specified format."""
        try:
            # Get all integrated data
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "time_period": time_period,
                "dashboard_data": self.get_integrated_dashboard_data(time_period),
                "efficiency_metrics": self.get_cost_efficiency_metrics(),
                "system_info": {
                    "integration_version": "1.0.0",
                    "databases": list(self._db_paths.keys()),
                    "prometheus_enabled": METRICS_AVAILABLE,
                },
            }

            if format_type.lower() == "json":
                return json.dumps(data, indent=2, default=str)
            elif format_type.lower() == "csv":
                # Simplified CSV export for key metrics
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write headers
                writer.writerow(["Metric", "Value", "Unit", "Timestamp"])

                # Write cost breakdown
                cost_breakdown = data["dashboard_data"].get("cost_breakdown", {})
                if "summary" in cost_breakdown:
                    summary = cost_breakdown["summary"]
                    writer.writerow(
                        [
                            "Total Cost",
                            summary.get("total_cost", 0),
                            "USD",
                            data["export_timestamp"],
                        ]
                    )
                    writer.writerow(
                        [
                            "Total Transactions",
                            summary.get("total_transactions", 0),
                            "count",
                            data["export_timestamp"],
                        ]
                    )
                    writer.writerow(
                        [
                            "Avg Transaction Cost",
                            summary.get("avg_transaction_cost", 0),
                            "USD",
                            data["export_timestamp"],
                        ]
                    )

                # Write efficiency metrics
                efficiency = data["efficiency_metrics"]
                writer.writerow(
                    [
                        "Optimization Score",
                        efficiency.get("optimization_score", 0),
                        "score",
                        data["export_timestamp"],
                    ]
                )

                return output.getvalue()
            else:
                raise ValueError(f"Unsupported export format: {format_type}")

        except Exception as e:
            self.logger.error(f"Error exporting integrated data: {e}")
            return json.dumps({"error": str(e)})

    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all integrated systems."""
        health_status = {
            "overall_status": "healthy",
            "checks": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Check cost tracker
            try:
                daily_cost = cost_tracker.get_daily_cost()
                health_status["checks"]["cost_tracker"] = {
                    "status": "healthy",
                    "daily_cost": daily_cost,
                }
            except Exception as e:
                health_status["checks"]["cost_tracker"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["overall_status"] = "degraded"

            # Check databases
            for db_name, db_path in self._db_paths.items():
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    conn.close()
                    health_status["checks"][f"database_{db_name}"] = {
                        "status": "healthy"
                    }
                except Exception as e:
                    health_status["checks"][f"database_{db_name}"] = {
                        "status": "unhealthy",
                        "error": str(e),
                    }
                    health_status["overall_status"] = "degraded"

            # Check Prometheus metrics
            health_status["checks"]["prometheus"] = {
                "status": "healthy" if METRICS_AVAILABLE else "unavailable",
                "available": METRICS_AVAILABLE,
            }

            # Check integration thread
            health_status["checks"]["integration_thread"] = {
                "status": "healthy" if self._integration_active else "stopped",
                "active": self._integration_active,
                "last_sync": (
                    self._last_sync_time.isoformat() if self._last_sync_time else None
                ),
            }

            # Check analytics engine
            try:
                # Try to run a simple analysis
                historical_data = cost_analytics_engine._get_historical_cost_data(
                    None, 7
                )
                health_status["checks"]["analytics_engine"] = {
                    "status": "healthy",
                    "data_points": len(historical_data),
                }
            except Exception as e:
                health_status["checks"]["analytics_engine"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["overall_status"] = "degraded"

        except Exception as e:
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status


# Create global instance
cost_metrics_integration = CostMetricsIntegration()


def start_integrated_cost_system():
    """Start the integrated cost monitoring system."""
    cost_metrics_integration.start_integration()
    logger.info("Integrated cost monitoring system started")


def stop_integrated_cost_system():
    """Stop the integrated cost monitoring system."""
    cost_metrics_integration.stop_integration()
    logger.info("Integrated cost monitoring system stopped")


def get_integrated_cost_api() -> Flask:
    """Get Flask app with integrated cost monitoring."""
    app = cost_breakdown_api.get_flask_app()

    # Add integration endpoints
    @app.route("/api/cost/integrated/dashboard")
    def integrated_dashboard():
        """Get integrated dashboard data."""
        time_period = request.args.get("time_period", "daily")
        return jsonify(
            cost_metrics_integration.get_integrated_dashboard_data(time_period)
        )

    @app.route("/api/cost/integrated/efficiency")
    def cost_efficiency():
        """Get cost efficiency metrics."""
        return jsonify(cost_metrics_integration.get_cost_efficiency_metrics())

    @app.route("/api/cost/integrated/health")
    def integration_health():
        """Get integration health status."""
        return jsonify(cost_metrics_integration.health_check())

    @app.route("/api/cost/integrated/export/<format_type>")
    def export_integrated(format_type):
        """Export integrated cost data."""
        time_period = request.args.get("time_period", "monthly")

        try:
            exported_data = cost_metrics_integration.export_integrated_data(
                format_type, time_period
            )

            if format_type.lower() == "json":
                return Response(
                    exported_data,
                    mimetype="application/json",
                    headers={
                        "Content-Disposition": f"attachment; filename=integrated_cost_data_{time_period}.json"
                    },
                )
            elif format_type.lower() == "csv":
                return Response(
                    exported_data,
                    mimetype="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=integrated_cost_data_{time_period}.csv"
                    },
                )
            else:
                return jsonify({"error": f"Unsupported format: {format_type}"}), 400

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    # Start integrated system
    start_integrated_cost_system()

    # Run the integrated API
    app = get_integrated_cost_api()
    socketio = cost_breakdown_api.get_socketio_instance()

    # Start streaming
    def stream_loop():
        while True:
            cost_metrics_integration.stream_realtime_metrics(socketio)
            time.sleep(30)

    streaming_thread = threading.Thread(target=stream_loop, daemon=True)
    streaming_thread.start()

    # Run the app
    socketio.run(app, host="127.0.0.1", port=5001, debug=False)
