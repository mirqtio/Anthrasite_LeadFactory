"""
Enhanced Cost Breakdown API
==========================

This module provides detailed cost breakdown views and analytics for the LeadFactory system.
It extends the existing cost tracking infrastructure with comprehensive reporting capabilities.

Features:
- Detailed cost breakdowns by service type, time period, and operation
- Cost trend analysis and predictions
- Budget utilization forecasting
- ROI calculations and cost optimization recommendations
- Real-time cost streaming via WebSockets
- Integration with existing SQLite databases and Prometheus metrics
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Flask, Response, jsonify, request

try:
    from flask_socketio import SocketIO, emit, join_room, leave_room

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None

from leadfactory.cost.cost_aggregation import cost_aggregation_service
from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class CostBreakdownAPI:
    """Enhanced cost breakdown API with real-time capabilities."""

    def __init__(self, app: Optional[Flask] = None):
        """Initialize the cost breakdown API.

        Args:
            app: Flask app instance. If None, creates a new app.
        """
        self.app = app or Flask(__name__)
        self.socketio = (
            SocketIO(self.app, cors_allowed_origins="*") if SOCKETIO_AVAILABLE else None
        )
        self.logger = get_logger(f"{__name__}.CostBreakdownAPI")

        # Thread-safe locks
        self._lock = threading.Lock()
        self._clients = set()

        # Cache for frequently accessed data
        self._cache = {}
        self._cache_expiry = {}
        self._cache_duration = 300  # 5 minutes

        # Register routes
        self._register_routes()
        if self.socketio and SOCKETIO_AVAILABLE:
            self._register_socketio_handlers()

        # Start background streaming
        self._start_streaming_thread()

        self.logger.info("Cost breakdown API initialized")

    def _register_routes(self):
        """Register Flask routes for the cost breakdown API."""

        @self.app.route("/api/cost/breakdown")
        def cost_breakdown():
            """Get detailed cost breakdown with filtering options."""
            try:
                # Parse query parameters
                service_type = request.args.get("service_type")
                time_period = request.args.get("time_period", "daily")
                operation_type = request.args.get("operation_type")
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")
                group_by = request.args.getlist("group_by")

                # Validate time period
                valid_periods = ["hourly", "daily", "weekly", "monthly"]
                if time_period not in valid_periods:
                    return (
                        jsonify(
                            {
                                "error": f"Invalid time_period. Must be one of: {valid_periods}"
                            }
                        ),
                        400,
                    )

                # Set default date range if not provided
                if not end_date:
                    end_date = datetime.now().strftime("%Y-%m-%d")
                if not start_date:
                    start_date = (datetime.now() - timedelta(days=30)).strftime(
                        "%Y-%m-%d"
                    )

                # Get breakdown data
                breakdown = self._get_cost_breakdown(
                    service_type=service_type,
                    time_period=time_period,
                    operation_type=operation_type,
                    start_date=start_date,
                    end_date=end_date,
                    group_by=group_by,
                )

                return jsonify(breakdown)

            except Exception as e:
                self.logger.error(f"Error in cost breakdown endpoint: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/trends")
        def cost_trends():
            """Get cost trend analysis and predictions."""
            try:
                service_type = request.args.get("service_type")
                days_back = int(request.args.get("days_back", 30))
                forecast_days = int(request.args.get("forecast_days", 7))

                trends = self._get_cost_trends(service_type, days_back, forecast_days)
                return jsonify(trends)

            except Exception as e:
                self.logger.error(f"Error in cost trends endpoint: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/optimization")
        def cost_optimization():
            """Get cost optimization recommendations."""
            try:
                time_period = request.args.get("time_period", "monthly")
                recommendations = self._get_optimization_recommendations(time_period)
                return jsonify(recommendations)

            except Exception as e:
                self.logger.error(f"Error in cost optimization endpoint: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/budget-utilization")
        def budget_utilization():
            """Get budget utilization analysis and forecasting."""
            try:
                year = int(request.args.get("year", datetime.now().year))
                month = int(request.args.get("month", datetime.now().month))

                utilization = self._get_budget_utilization(year, month)
                return jsonify(utilization)

            except Exception as e:
                self.logger.error(f"Error in budget utilization endpoint: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/roi-analysis")
        def roi_analysis():
            """Get ROI calculations and analysis."""
            try:
                time_period = request.args.get("time_period", "monthly")
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")

                roi = self._get_roi_analysis(time_period, start_date, end_date)
                return jsonify(roi)

            except Exception as e:
                self.logger.error(f"Error in ROI analysis endpoint: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/summary")
        def cost_summary():
            """Get comprehensive cost summary dashboard data."""
            try:
                time_period = request.args.get("time_period", "daily")
                summary = self._get_cost_summary(time_period)
                return jsonify(summary)

            except Exception as e:
                self.logger.error(f"Error in cost summary endpoint: {e}")
                return jsonify({"error": str(e)}), 500

    def _register_socketio_handlers(self):
        """Register SocketIO handlers for real-time cost streaming."""
        if not (self.socketio and SOCKETIO_AVAILABLE):
            return

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection."""
            with self._lock:
                self._clients.add(request.sid)
            join_room("cost_updates")
            self.logger.info(f"Client {request.sid} connected for cost updates")

            # Send initial data
            if SOCKETIO_AVAILABLE:
                emit("cost_update", self._get_realtime_cost_data())

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            with self._lock:
                self._clients.discard(request.sid)
            leave_room("cost_updates")
            self.logger.info(f"Client {request.sid} disconnected")

        @self.socketio.on("subscribe_cost_updates")
        def handle_subscribe(data):
            """Handle subscription to specific cost update types."""
            update_types = data.get("types", ["all"])
            room_name = f"cost_updates_{request.sid}"
            join_room(room_name)

            # Store subscription preferences
            with self._lock:
                if not hasattr(self, "_subscriptions"):
                    self._subscriptions = {}
                self._subscriptions[request.sid] = update_types

            self.logger.info(f"Client {request.sid} subscribed to: {update_types}")

    def _get_cost_breakdown(
        self,
        service_type: Optional[str] = None,
        time_period: str = "daily",
        operation_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get detailed cost breakdown with filtering options."""

        # Generate cache key
        cache_key = f"breakdown_{service_type}_{time_period}_{operation_type}_{start_date}_{end_date}_{group_by}"

        # Check cache
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            # Build base query
            where_clauses = []
            params = []

            if start_date:
                where_clauses.append("DATE(timestamp) >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("DATE(timestamp) <= ?")
                params.append(end_date)
            if service_type:
                where_clauses.append("service = ?")
                params.append(service_type)
            if operation_type:
                where_clauses.append("operation = ?")
                params.append(operation_type)

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Determine grouping
            group_by = group_by or ["service"]
            valid_group_fields = ["service", "operation", "date", "hour"]
            group_fields = [f for f in group_by if f in valid_group_fields]

            # Build time-based grouping
            if time_period == "hourly":
                time_group = "strftime('%Y-%m-%d %H', timestamp)"
            elif time_period == "daily":
                time_group = "DATE(timestamp)"
            elif time_period == "weekly":
                time_group = "strftime('%Y-W%W', timestamp)"
            elif time_period == "monthly":
                time_group = "strftime('%Y-%m', timestamp)"
            else:
                time_group = "DATE(timestamp)"

            # Add time grouping if not explicitly excluded
            if "date" in group_fields or len(group_fields) == 0:
                group_fields.append("time_period")

            # Build SELECT and GROUP BY clauses
            select_fields = []
            group_fields_sql = []

            for field in group_fields:
                if field == "service":
                    select_fields.append("service")
                    group_fields_sql.append("service")
                elif field == "operation":
                    select_fields.append("operation")
                    group_fields_sql.append("operation")
                elif field == "time_period":
                    select_fields.append(f"{time_group} as time_period")
                    group_fields_sql.append(time_group)

            select_fields.extend(
                [
                    "SUM(amount) as total_cost",
                    "COUNT(*) as transaction_count",
                    "AVG(amount) as avg_cost",
                    "MIN(amount) as min_cost",
                    "MAX(amount) as max_cost",
                ]
            )

            query = f"""
                SELECT {', '.join(select_fields)}
                FROM costs
                WHERE {where_clause}
                GROUP BY {', '.join(group_fields_sql)}
                ORDER BY time_period DESC, total_cost DESC
            """

            cursor.execute(query, params)
            results = cursor.fetchall()

            # Build breakdown data
            breakdown_data = []
            total_cost = 0
            total_transactions = 0

            for row in results:
                # Map results to dictionary
                row_dict = {}
                col_index = 0

                for field in group_fields:
                    row_dict[field] = row[col_index]
                    col_index += 1

                row_dict.update(
                    {
                        "total_cost": float(row[col_index]),
                        "transaction_count": row[col_index + 1],
                        "avg_cost": float(row[col_index + 2]),
                        "min_cost": float(row[col_index + 3]),
                        "max_cost": float(row[col_index + 4]),
                    }
                )

                breakdown_data.append(row_dict)
                total_cost += row_dict["total_cost"]
                total_transactions += row_dict["transaction_count"]

            # Calculate percentages
            for item in breakdown_data:
                item["cost_percentage"] = (
                    (item["total_cost"] / total_cost * 100) if total_cost > 0 else 0
                )

            # Get service breakdown if not already grouped by service
            service_breakdown = (
                self._get_service_breakdown(start_date, end_date)
                if "service" not in group_fields
                else {}
            )

            # Get recent high-cost transactions
            recent_transactions = self._get_recent_high_cost_transactions(
                service_type, operation_type
            )

            breakdown = {
                "filters": {
                    "service_type": service_type,
                    "time_period": time_period,
                    "operation_type": operation_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "group_by": group_by,
                },
                "summary": {
                    "total_cost": total_cost,
                    "total_transactions": total_transactions,
                    "avg_transaction_cost": (
                        total_cost / total_transactions if total_transactions > 0 else 0
                    ),
                    "time_range_days": (
                        (
                            datetime.strptime(end_date, "%Y-%m-%d")
                            - datetime.strptime(start_date, "%Y-%m-%d")
                        ).days
                        + 1
                        if start_date and end_date
                        else None
                    ),
                },
                "breakdown": breakdown_data,
                "service_breakdown": service_breakdown,
                "recent_high_cost_transactions": recent_transactions,
                "generated_at": datetime.now().isoformat(),
            }

            # Cache the result
            self._cache_result(cache_key, breakdown)

            conn.close()
            return breakdown

        except Exception as e:
            self.logger.error(f"Error getting cost breakdown: {e}")
            if "conn" in locals():
                conn.close()
            raise

    def _get_service_breakdown(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        """Get breakdown by service type."""
        try:
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            where_clauses = []
            params = []

            if start_date:
                where_clauses.append("DATE(timestamp) >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("DATE(timestamp) <= ?")
                params.append(end_date)

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor.execute(
                f"""
                SELECT
                    service,
                    SUM(amount) as total_cost,
                    COUNT(*) as transaction_count,
                    AVG(amount) as avg_cost
                FROM costs
                WHERE {where_clause}
                GROUP BY service
                ORDER BY total_cost DESC
            """,
                params,
            )

            results = cursor.fetchall()
            total_cost = sum(row[1] for row in results)

            service_data = []
            for service, cost, count, avg_cost in results:
                service_data.append(
                    {
                        "service": service,
                        "total_cost": float(cost),
                        "transaction_count": count,
                        "avg_cost": float(avg_cost),
                        "percentage": (
                            (cost / total_cost * 100) if total_cost > 0 else 0
                        ),
                    }
                )

            conn.close()
            return {"services": service_data, "total_cost": total_cost}

        except Exception as e:
            self.logger.error(f"Error getting service breakdown: {e}")
            if "conn" in locals():
                conn.close()
            return {}

    def _get_recent_high_cost_transactions(
        self, service_type: Optional[str], operation_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get recent high-cost transactions for analysis."""
        try:
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            where_clauses = [
                "amount > (SELECT AVG(amount) * 2 FROM costs)"
            ]  # Above 2x average
            params = []

            if service_type:
                where_clauses.append("service = ?")
                params.append(service_type)
            if operation_type:
                where_clauses.append("operation = ?")
                params.append(operation_type)

            where_clause = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT
                    timestamp,
                    service,
                    operation,
                    amount,
                    details
                FROM costs
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT 20
            """,
                params,
            )

            results = cursor.fetchall()
            transactions = []

            for timestamp, service, operation, amount, details in results:
                transaction = {
                    "timestamp": timestamp,
                    "service": service,
                    "operation": operation or "unknown",
                    "amount": float(amount),
                }

                # Parse details if available
                if details:
                    try:
                        transaction["details"] = json.loads(details)
                    except json.JSONDecodeError:
                        transaction["details"] = {"raw": details}

                transactions.append(transaction)

            conn.close()
            return transactions

        except Exception as e:
            self.logger.error(f"Error getting recent high-cost transactions: {e}")
            if "conn" in locals():
                conn.close()
            return []

    def _get_cost_trends(
        self, service_type: Optional[str], days_back: int, forecast_days: int
    ) -> Dict[str, Any]:
        """Get cost trend analysis and predictions."""

        cache_key = f"trends_{service_type}_{days_back}_{forecast_days}"
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            where_clauses = ["DATE(timestamp) >= ? AND DATE(timestamp) <= ?"]
            params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]

            if service_type:
                where_clauses.append("service = ?")
                params.append(service_type)

            where_clause = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT
                    DATE(timestamp) as date,
                    SUM(amount) as daily_cost,
                    COUNT(*) as transaction_count
                FROM costs
                WHERE {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                params,
            )

            results = cursor.fetchall()

            # Prepare trend data
            historical_data = []
            dates = []
            costs = []

            for date_str, daily_cost, count in results:
                historical_data.append(
                    {
                        "date": date_str,
                        "cost": float(daily_cost),
                        "transaction_count": count,
                    }
                )
                dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                costs.append(float(daily_cost))

            # Calculate trend metrics
            trend_analysis = self._calculate_trend_metrics(costs)

            # Generate forecast
            forecast = self._generate_cost_forecast(costs, forecast_days)

            # Identify anomalies
            anomalies = self._detect_cost_anomalies(historical_data)

            trends = {
                "service_type": service_type,
                "analysis_period": {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "days": days_back,
                },
                "historical_data": historical_data,
                "trend_analysis": trend_analysis,
                "forecast": {"days": forecast_days, "predictions": forecast},
                "anomalies": anomalies,
                "generated_at": datetime.now().isoformat(),
            }

            self._cache_result(cache_key, trends)
            conn.close()

            return trends

        except Exception as e:
            self.logger.error(f"Error getting cost trends: {e}")
            if "conn" in locals():
                conn.close()
            raise

    def _calculate_trend_metrics(self, costs: List[float]) -> Dict[str, Any]:
        """Calculate trend analysis metrics."""
        if len(costs) < 2:
            return {"error": "Insufficient data for trend analysis"}

        # Basic statistics
        total_cost = sum(costs)
        avg_cost = total_cost / len(costs)
        min_cost = min(costs)
        max_cost = max(costs)

        # Calculate growth rate
        if len(costs) >= 7:
            recent_avg = sum(costs[-7:]) / 7
            previous_avg = (
                sum(costs[-14:-7]) / 7
                if len(costs) >= 14
                else sum(costs[:-7]) / (len(costs) - 7)
            )
            growth_rate = (
                ((recent_avg - previous_avg) / previous_avg * 100)
                if previous_avg > 0
                else 0
            )
        else:
            growth_rate = (
                ((costs[-1] - costs[0]) / costs[0] * 100) if costs[0] > 0 else 0
            )

        # Calculate volatility (standard deviation)
        variance = sum((x - avg_cost) ** 2 for x in costs) / len(costs)
        volatility = variance**0.5

        # Trend direction
        if len(costs) >= 3:
            recent_trend = sum(costs[-3:]) / 3
            middle_trend = sum(costs[:-3]) / (len(costs) - 3)
            if recent_trend > middle_trend * 1.1:
                trend_direction = "increasing"
            elif recent_trend < middle_trend * 0.9:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

        return {
            "total_cost": total_cost,
            "average_daily_cost": avg_cost,
            "min_daily_cost": min_cost,
            "max_daily_cost": max_cost,
            "growth_rate_percent": growth_rate,
            "volatility": volatility,
            "trend_direction": trend_direction,
            "coefficient_of_variation": (
                (volatility / avg_cost * 100) if avg_cost > 0 else 0
            ),
        }

    def _generate_cost_forecast(
        self, historical_costs: List[float], forecast_days: int
    ) -> List[Dict[str, Any]]:
        """Generate simple cost forecasting based on trends."""
        if len(historical_costs) < 3:
            return []

        # Simple linear trend forecasting
        x = list(range(len(historical_costs)))
        y = historical_costs

        # Calculate linear regression coefficients
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        # Slope and intercept
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        intercept = (sum_y - slope * sum_x) / n

        # Generate forecast
        forecast = []
        base_date = datetime.now()

        for i in range(1, forecast_days + 1):
            forecast_value = slope * (len(historical_costs) + i - 1) + intercept
            forecast_date = base_date + timedelta(days=i)

            # Add some uncertainty bounds (simple approach)
            recent_volatility = sum(
                abs(y[j] - (slope * x[j] + intercept))
                for j in range(-min(7, len(y)), 0)
            ) / min(7, len(y))

            forecast.append(
                {
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "predicted_cost": max(0, forecast_value),  # Ensure non-negative
                    "lower_bound": max(0, forecast_value - recent_volatility),
                    "upper_bound": forecast_value + recent_volatility,
                    "confidence": max(
                        0, min(100, 100 - (i * 10))
                    ),  # Decreasing confidence over time
                }
            )

        return forecast

    def _detect_cost_anomalies(
        self, historical_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect cost anomalies in historical data."""
        if len(historical_data) < 7:
            return []

        costs = [item["cost"] for item in historical_data]
        avg_cost = sum(costs) / len(costs)

        # Calculate standard deviation
        variance = sum((x - avg_cost) ** 2 for x in costs) / len(costs)
        std_dev = variance**0.5

        # Detect anomalies (values beyond 2 standard deviations)
        anomalies = []
        threshold = 2 * std_dev

        for item in historical_data:
            deviation = abs(item["cost"] - avg_cost)
            if deviation > threshold:
                anomaly_type = "high" if item["cost"] > avg_cost else "low"
                anomalies.append(
                    {
                        "date": item["date"],
                        "cost": item["cost"],
                        "expected_cost": avg_cost,
                        "deviation": deviation,
                        "severity": min(5, int(deviation / std_dev)),  # 1-5 scale
                        "type": anomaly_type,
                        "description": (
                            f"Cost was {deviation:.2f} above average"
                            if anomaly_type == "high"
                            else f"Cost was {deviation:.2f} below average"
                        ),
                    }
                )

        return sorted(anomalies, key=lambda x: x["deviation"], reverse=True)[
            :10
        ]  # Top 10 anomalies

    def _get_optimization_recommendations(self, time_period: str) -> Dict[str, Any]:
        """Get cost optimization recommendations."""

        cache_key = f"optimization_{time_period}"
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            # Get cost breakdown by service
            service_breakdown = self._get_service_breakdown(None, None)

            # Analyze patterns and generate recommendations
            recommendations = []

            # Check for high-cost services
            if service_breakdown.get("services"):
                total_cost = service_breakdown["total_cost"]

                for service in service_breakdown["services"]:
                    if service["percentage"] > 40:  # Service consuming >40% of budget
                        recommendations.append(
                            {
                                "type": "high_cost_service",
                                "priority": "high",
                                "service": service["service"],
                                "description": f"{service['service']} accounts for {service['percentage']:.1f}% of total costs",
                                "recommendation": f"Consider implementing rate limiting or usage optimization for {service['service']}",
                                "potential_savings": service["total_cost"]
                                * 0.2,  # Assume 20% potential savings
                            }
                        )

                    if service["avg_cost"] > 1.0:  # High average transaction cost
                        recommendations.append(
                            {
                                "type": "high_transaction_cost",
                                "priority": "medium",
                                "service": service["service"],
                                "description": f"Average transaction cost for {service['service']} is ${service['avg_cost']:.2f}",
                                "recommendation": "Review API usage patterns and consider batching requests",
                                "potential_savings": service["total_cost"] * 0.15,
                            }
                        )

            # Get recent high-cost transactions for additional insights
            high_cost_transactions = self._get_recent_high_cost_transactions(None, None)

            if len(high_cost_transactions) > 5:
                avg_high_cost = sum(t["amount"] for t in high_cost_transactions) / len(
                    high_cost_transactions
                )
                recommendations.append(
                    {
                        "type": "frequent_high_cost",
                        "priority": "medium",
                        "description": f"Detected {len(high_cost_transactions)} high-cost transactions averaging ${avg_high_cost:.2f}",
                        "recommendation": "Implement cost monitoring alerts and usage quotas",
                        "potential_savings": avg_high_cost
                        * len(high_cost_transactions)
                        * 0.1,
                    }
                )

            # Budget utilization recommendations
            current_month = datetime.now()
            budget_data = self._get_budget_utilization(
                current_month.year, current_month.month
            )

            if budget_data.get("utilization_percentage", 0) > 80:
                recommendations.append(
                    {
                        "type": "budget_overrun_risk",
                        "priority": "high",
                        "description": f"Current month budget utilization is {budget_data.get('utilization_percentage', 0):.1f}%",
                        "recommendation": "Implement immediate cost controls and review budget allocation",
                        "potential_savings": budget_data.get("projected_overage", 0),
                    }
                )

            # Sort by priority and potential savings
            priority_order = {"high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda x: (
                    priority_order.get(x["priority"], 0),
                    x.get("potential_savings", 0),
                ),
                reverse=True,
            )

            optimization = {
                "time_period": time_period,
                "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                "total_recommendations": len(recommendations),
                "total_potential_savings": sum(
                    r.get("potential_savings", 0) for r in recommendations
                ),
                "recommendations": recommendations[:10],  # Top 10 recommendations
                "summary": {
                    "high_priority": len(
                        [r for r in recommendations if r["priority"] == "high"]
                    ),
                    "medium_priority": len(
                        [r for r in recommendations if r["priority"] == "medium"]
                    ),
                    "low_priority": len(
                        [r for r in recommendations if r["priority"] == "low"]
                    ),
                },
            }

            self._cache_result(cache_key, optimization)
            return optimization

        except Exception as e:
            self.logger.error(f"Error getting optimization recommendations: {e}")
            raise

    def _get_budget_utilization(self, year: int, month: int) -> Dict[str, Any]:
        """Get budget utilization analysis and forecasting."""

        cache_key = f"budget_{year}_{month}"
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            # Get current month data from cost tracker
            monthly_costs = cost_tracker.get_monthly_costs(year, month)

            # Calculate days in month and elapsed days
            current_date = datetime.now()
            if year == current_date.year and month == current_date.month:
                days_elapsed = current_date.day
            else:
                # For past months, use full month
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                days_elapsed = (next_month - datetime(year, month, 1)).days

            if month == 12:
                days_in_month = (
                    datetime(year + 1, 1, 1) - datetime(year, month, 1)
                ).days
            else:
                days_in_month = (
                    datetime(year, month + 1, 1) - datetime(year, month, 1)
                ).days

            budget = monthly_costs.get("budget", 0)
            spent = monthly_costs.get("spent", 0)
            remaining = budget - spent

            # Calculate utilization percentage
            utilization_percentage = (spent / budget * 100) if budget > 0 else 0

            # Calculate projected spending
            if days_elapsed > 0:
                daily_average = spent / days_elapsed
                projected_monthly_spend = daily_average * days_in_month
                projected_overage = max(0, projected_monthly_spend - budget)
            else:
                daily_average = 0
                projected_monthly_spend = 0
                projected_overage = 0

            # Calculate burn rate
            days_remaining = days_in_month - days_elapsed
            burn_rate = spent / days_elapsed if days_elapsed > 0 else 0

            # Forecast remaining days
            if burn_rate > 0 and remaining > 0:
                days_until_budget_exhausted = remaining / burn_rate
            else:
                days_until_budget_exhausted = float("inf") if remaining > 0 else 0

            # Generate alerts
            alerts = []
            if utilization_percentage > 90:
                alerts.append(
                    {
                        "type": "critical",
                        "message": f"Budget utilization is {utilization_percentage:.1f}% - approaching limit",
                    }
                )
            elif utilization_percentage > 75:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"Budget utilization is {utilization_percentage:.1f}% - monitor closely",
                    }
                )

            if projected_overage > 0:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"Projected overage of ${projected_overage:.2f} based on current spending rate",
                    }
                )

            if days_until_budget_exhausted <= days_remaining:
                alerts.append(
                    {
                        "type": "critical",
                        "message": f"Budget may be exhausted in {days_until_budget_exhausted:.1f} days at current rate",
                    }
                )

            utilization = {
                "year": year,
                "month": month,
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "utilization_percentage": utilization_percentage,
                "days_in_month": days_in_month,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "daily_average_spend": daily_average,
                "projected_monthly_spend": projected_monthly_spend,
                "projected_overage": projected_overage,
                "burn_rate": burn_rate,
                "days_until_budget_exhausted": (
                    days_until_budget_exhausted
                    if days_until_budget_exhausted != float("inf")
                    else None
                ),
                "alerts": alerts,
                "service_breakdown": monthly_costs.get("services", {}),
                "generated_at": datetime.now().isoformat(),
            }

            self._cache_result(cache_key, utilization)
            return utilization

        except Exception as e:
            self.logger.error(f"Error getting budget utilization: {e}")
            raise

    def _get_roi_analysis(
        self, time_period: str, start_date: Optional[str], end_date: Optional[str]
    ) -> Dict[str, Any]:
        """Get ROI calculations and analysis."""

        cache_key = f"roi_{time_period}_{start_date}_{end_date}"
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            # Try to get revenue data from cost aggregation service
            roi_data = {
                "time_period": time_period,
                "start_date": start_date,
                "end_date": end_date,
                "analysis_type": "cost_only",  # Default if no revenue data
                "total_costs": 0,
                "total_revenue": 0,
                "roi_percentage": 0,
                "cost_breakdown": {},
                "generated_at": datetime.now().isoformat(),
            }

            # Get cost data
            cost_breakdown = self._get_cost_breakdown(
                time_period=time_period, start_date=start_date, end_date=end_date
            )

            roi_data["total_costs"] = cost_breakdown["summary"]["total_cost"]
            roi_data["cost_breakdown"] = cost_breakdown["service_breakdown"]

            # Try to get revenue data from aggregation service
            try:
                if (
                    hasattr(cost_aggregation_service, "get_daily_summary")
                    and start_date
                    and end_date
                ):
                    # Get daily summaries for the period
                    current_date = datetime.strptime(start_date, "%Y-%m-%d")
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

                    total_revenue_cents = 0
                    total_transactions = 0

                    while current_date <= end_date_obj:
                        daily_summary = cost_aggregation_service.get_daily_summary(
                            current_date.strftime("%Y-%m-%d")
                        )
                        if daily_summary:
                            total_revenue_cents += daily_summary.get(
                                "gross_revenue_cents", 0
                            )
                            total_transactions += daily_summary.get(
                                "transaction_count", 0
                            )
                        current_date += timedelta(days=1)

                    if total_revenue_cents > 0:
                        roi_data["analysis_type"] = "full_roi"
                        roi_data["total_revenue"] = (
                            total_revenue_cents / 100
                        )  # Convert to dollars
                        roi_data["total_transactions"] = total_transactions

                        # Calculate ROI
                        if roi_data["total_costs"] > 0:
                            roi_data["roi_percentage"] = (
                                (roi_data["total_revenue"] - roi_data["total_costs"])
                                / roi_data["total_costs"]
                            ) * 100
                            roi_data["profit"] = (
                                roi_data["total_revenue"] - roi_data["total_costs"]
                            )
                            roi_data["profit_margin"] = (
                                (roi_data["profit"] / roi_data["total_revenue"]) * 100
                                if roi_data["total_revenue"] > 0
                                else 0
                            )

                        # Calculate per-transaction metrics
                        if total_transactions > 0:
                            roi_data["revenue_per_transaction"] = (
                                roi_data["total_revenue"] / total_transactions
                            )
                            roi_data["cost_per_transaction"] = (
                                roi_data["total_costs"] / total_transactions
                            )
                            roi_data["profit_per_transaction"] = (
                                roi_data.get("profit", 0) / total_transactions
                            )

                        # Calculate cost efficiency metrics
                        roi_data["cost_efficiency"] = {
                            "cost_to_revenue_ratio": (
                                (roi_data["total_costs"] / roi_data["total_revenue"])
                                * 100
                                if roi_data["total_revenue"] > 0
                                else 0
                            ),
                            "revenue_multiple": (
                                roi_data["total_revenue"] / roi_data["total_costs"]
                                if roi_data["total_costs"] > 0
                                else 0
                            ),
                        }

            except Exception as e:
                self.logger.warning(f"Could not get revenue data for ROI analysis: {e}")

            # Add cost efficiency analysis even without revenue
            if roi_data["analysis_type"] == "cost_only":
                roi_data["cost_analysis"] = {
                    "description": "ROI analysis limited to cost data only - revenue data not available",
                    "cost_trends": self._get_cost_trends(None, 30, 7)["trend_analysis"],
                    "optimization_opportunities": self._get_optimization_recommendations(
                        time_period
                    )[
                        "recommendations"
                    ][
                        :5
                    ],
                }

            self._cache_result(cache_key, roi_data)
            return roi_data

        except Exception as e:
            self.logger.error(f"Error getting ROI analysis: {e}")
            raise

    def _get_cost_summary(self, time_period: str) -> Dict[str, Any]:
        """Get comprehensive cost summary dashboard data."""

        cache_key = f"summary_{time_period}"
        if self._is_cached(cache_key):
            return self._get_cached(cache_key)

        try:
            current_date = datetime.now()

            if time_period == "daily":
                start_date = current_date.strftime("%Y-%m-%d")
                end_date = start_date
            elif time_period == "weekly":
                start_date = (current_date - timedelta(days=7)).strftime("%Y-%m-%d")
                end_date = current_date.strftime("%Y-%m-%d")
            elif time_period == "monthly":
                start_date = current_date.replace(day=1).strftime("%Y-%m-%d")
                end_date = current_date.strftime("%Y-%m-%d")
            else:
                start_date = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = current_date.strftime("%Y-%m-%d")

            # Get all the component data
            cost_breakdown = self._get_cost_breakdown(
                time_period=time_period, start_date=start_date, end_date=end_date
            )
            cost_trends = self._get_cost_trends(None, 30, 7)
            budget_utilization = self._get_budget_utilization(
                current_date.year, current_date.month
            )
            optimization = self._get_optimization_recommendations(time_period)

            # Combine into comprehensive summary
            summary = {
                "time_period": time_period,
                "date_range": {"start_date": start_date, "end_date": end_date},
                "overview": {
                    "total_cost": cost_breakdown["summary"]["total_cost"],
                    "total_transactions": cost_breakdown["summary"][
                        "total_transactions"
                    ],
                    "avg_transaction_cost": cost_breakdown["summary"][
                        "avg_transaction_cost"
                    ],
                    "growth_rate": cost_trends["trend_analysis"]["growth_rate_percent"],
                    "trend_direction": cost_trends["trend_analysis"]["trend_direction"],
                },
                "budget_status": {
                    "utilization_percentage": budget_utilization[
                        "utilization_percentage"
                    ],
                    "remaining_budget": budget_utilization["remaining"],
                    "projected_overage": budget_utilization["projected_overage"],
                    "alerts_count": len(budget_utilization["alerts"]),
                },
                "top_services": cost_breakdown["service_breakdown"]["services"][:5],
                "recent_anomalies": cost_trends["anomalies"][:3],
                "optimization_opportunities": optimization["recommendations"][:3],
                "key_metrics": {
                    "cost_volatility": cost_trends["trend_analysis"]["volatility"],
                    "high_cost_transactions": len(
                        cost_breakdown["recent_high_cost_transactions"]
                    ),
                    "potential_savings": optimization["total_potential_savings"],
                },
                "generated_at": datetime.now().isoformat(),
            }

            self._cache_result(cache_key, summary)
            return summary

        except Exception as e:
            self.logger.error(f"Error getting cost summary: {e}")
            raise

    def _get_realtime_cost_data(self) -> Dict[str, Any]:
        """Get real-time cost data for streaming."""
        try:
            # Get current day costs
            daily_cost = cost_tracker.get_daily_cost()
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()

            # Get recent transactions (last hour)
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            cursor.execute(
                """
                SELECT service, operation, amount, timestamp
                FROM costs
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 20
            """,
                (one_hour_ago,),
            )

            recent_transactions = []
            for service, operation, amount, timestamp in cursor.fetchall():
                recent_transactions.append(
                    {
                        "service": service,
                        "operation": operation or "unknown",
                        "amount": float(amount),
                        "timestamp": timestamp,
                    }
                )

            conn.close()

            return {
                "timestamp": datetime.now().isoformat(),
                "daily_total": daily_cost,
                "hourly_total": sum(t["amount"] for t in recent_transactions),
                "service_breakdown": daily_breakdown,
                "recent_transactions": recent_transactions,
                "transaction_count_last_hour": len(recent_transactions),
            }

        except Exception as e:
            self.logger.error(f"Error getting real-time cost data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def _start_streaming_thread(self):
        """Start background thread for real-time cost streaming."""
        import threading
        import time

        def stream_costs():
            """Background function to stream cost updates."""
            while True:
                try:
                    if self._clients:
                        cost_data = self._get_realtime_cost_data()
                        if self.socketio and SOCKETIO_AVAILABLE:
                            self.socketio.emit(
                                "cost_update", cost_data, room="cost_updates"
                            )

                    time.sleep(30)  # Update every 30 seconds

                except Exception as e:
                    self.logger.error(f"Error in cost streaming thread: {e}")
                    time.sleep(60)  # Wait longer on error

        streaming_thread = threading.Thread(target=stream_costs, daemon=True)
        streaming_thread.start()
        self.logger.info("Cost streaming thread started")

    def _is_cached(self, key: str) -> bool:
        """Check if data is cached and not expired."""
        return (
            key in self._cache
            and key in self._cache_expiry
            and datetime.now() < self._cache_expiry[key]
        )

    def _get_cached(self, key: str) -> Any:
        """Get cached data."""
        return self._cache.get(key)

    def _cache_result(self, key: str, data: Any):
        """Cache result with expiry."""
        self._cache[key] = data
        self._cache_expiry[key] = datetime.now() + timedelta(
            seconds=self._cache_duration
        )

    def get_flask_app(self) -> Flask:
        """Get the Flask app instance."""
        return self.app

    def get_socketio_instance(self) -> SocketIO:
        """Get the SocketIO instance."""
        return self.socketio


# Create global instance
cost_breakdown_api = CostBreakdownAPI()


def create_cost_api_app() -> Flask:
    """Create and configure the cost breakdown API Flask app."""
    return cost_breakdown_api.get_flask_app()


def run_cost_api(host: str = "127.0.0.1", port: int = 5001, debug: bool = False):
    """Run the cost breakdown API server."""
    cost_breakdown_api.socketio.run(
        cost_breakdown_api.app, host=host, port=port, debug=debug
    )


if __name__ == "__main__":
    run_cost_api(debug=True)
