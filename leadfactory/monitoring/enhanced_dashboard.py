"""
Enhanced Dashboard for Cost Analytics and Real-time Metrics
==========================================================

This module extends the existing purchase metrics dashboard with enhanced cost breakdown
views and real-time metric updates. It provides comprehensive cost analytics without
requiring external dependencies like SocketIO or advanced analytics packages.

Features:
- Detailed cost breakdown by service and operation type
- Real-time cost monitoring with auto-refresh
- Budget utilization tracking and alerts
- Cost trend analysis using built-in statistics
- ROI calculation and optimization insights
- Enhanced visual dashboard with improved UX
"""

import json
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, render_template, request

from leadfactory.cost.cost_aggregation import cost_aggregation_service
from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.cost.financial_tracking import financial_tracker
from leadfactory.monitoring.dashboard import PurchaseMetricsDashboard
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedCostDashboard(PurchaseMetricsDashboard):
    """Enhanced dashboard with advanced cost analytics and real-time updates."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5001, debug: bool = False):
        """Initialize the enhanced dashboard."""
        super().__init__(host, port, debug)
        self.logger = get_logger(f"{__name__}.EnhancedCostDashboard")

        # Add enhanced routes
        self._register_enhanced_routes()
        self.logger.info("Enhanced cost dashboard initialized")

    def _register_enhanced_routes(self):
        """Register enhanced cost analytics routes."""

        @self.app.route("/api/cost/detailed-breakdown")
        def detailed_cost_breakdown():
            """Get detailed cost breakdown with enhanced analytics."""
            try:
                # Parse query parameters
                service_type = request.args.get("service_type")
                days_back = int(request.args.get("days_back", "30"))
                group_by = request.args.get("group_by", "service")

                # Get cost data
                cost_data = self._get_enhanced_cost_data(
                    service_type=service_type, days_back=days_back, group_by=group_by
                )

                return jsonify(
                    {
                        "success": True,
                        "data": cost_data,
                        "metadata": {
                            "generated_at": datetime.utcnow().isoformat(),
                            "filters": {
                                "service_type": service_type,
                                "days_back": days_back,
                                "group_by": group_by,
                            },
                        },
                    }
                )
            except Exception as e:
                logger.error(f"Error in detailed cost breakdown: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/trends")
        def cost_trends():
            """Get cost trends with simple statistical analysis."""
            try:
                days_back = int(request.args.get("days_back", "90"))
                service_type = request.args.get("service_type")

                trends_data = self._analyze_cost_trends(
                    days_back=days_back, service_type=service_type
                )

                return jsonify(
                    {
                        "success": True,
                        "data": trends_data,
                        "metadata": {
                            "generated_at": datetime.utcnow().isoformat(),
                            "analysis_period": f"{days_back} days",
                        },
                    }
                )
            except Exception as e:
                logger.error(f"Error in cost trends analysis: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/optimization-insights")
        def optimization_insights():
            """Get cost optimization insights and recommendations."""
            try:
                insights = self._generate_optimization_insights()

                return jsonify(
                    {
                        "success": True,
                        "data": insights,
                        "metadata": {"generated_at": datetime.utcnow().isoformat()},
                    }
                )
            except Exception as e:
                logger.error(f"Error generating optimization insights: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/budget-status")
        def budget_status():
            """Get current budget status and utilization."""
            try:
                status = self._get_budget_status()

                return jsonify(
                    {
                        "success": True,
                        "data": status,
                        "metadata": {"generated_at": datetime.utcnow().isoformat()},
                    }
                )
            except Exception as e:
                logger.error(f"Error getting budget status: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/cost/realtime-summary")
        def realtime_cost_summary():
            """Get real-time cost summary for dashboard updates."""
            try:
                summary = self._get_realtime_cost_summary()

                return jsonify(
                    {
                        "success": True,
                        "data": summary,
                        "metadata": {
                            "generated_at": datetime.utcnow().isoformat(),
                            "refresh_interval": 30,  # seconds
                        },
                    }
                )
            except Exception as e:
                logger.error(f"Error getting realtime cost summary: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/enhanced-dashboard")
        def enhanced_dashboard_ui():
            """Render the enhanced dashboard UI."""
            return render_template("enhanced_dashboard.html")

    def _get_enhanced_cost_data(
        self,
        service_type: Optional[str] = None,
        days_back: int = 30,
        group_by: str = "service",
    ) -> Dict[str, Any]:
        """Get enhanced cost data with detailed breakdown."""
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)

            # Get aggregated cost data (use monthly breakdown for now)
            monthly_breakdown = cost_tracker.get_monthly_cost_breakdown()
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()

            # Get cost reports for the period
            monthly_report = cost_tracker.get_monthly_cost_report()
            daily_report = cost_tracker.get_daily_cost_report()

            # Combine the cost data
            raw_costs = []
            aggregated_costs = {
                "monthly": monthly_breakdown,
                "daily": daily_breakdown,
                "reports": {"monthly": monthly_report, "daily": daily_report},
            }

            # Process data based on grouping
            if group_by == "service":
                breakdown = self._group_by_service_from_breakdown(monthly_breakdown)
            elif group_by == "daily":
                breakdown = self._group_by_day_from_breakdown(daily_breakdown)
            elif group_by == "operation":
                breakdown = self._group_by_service_from_breakdown(
                    monthly_breakdown
                )  # Fallback to service
            else:
                breakdown = self._group_by_service_from_breakdown(monthly_breakdown)

            # Calculate totals from breakdown data
            total_cost = self._calculate_total_from_breakdown(monthly_breakdown)
            avg_daily_cost = total_cost / max(days_back, 1)

            return {
                "breakdown": breakdown,
                "summary": {
                    "total_cost": total_cost,
                    "average_daily_cost": avg_daily_cost,
                    "period_days": days_back,
                    "total_transactions": len(breakdown),
                },
                "aggregated_data": aggregated_costs,
            }

        except Exception as e:
            logger.error(f"Error getting enhanced cost data: {e}")
            return {"error": str(e)}

    def _group_by_service(self, costs) -> List[Dict[str, Any]]:
        """Group costs by service type."""
        service_totals = {}
        for cost in costs:
            service = cost.service_type
            if service not in service_totals:
                service_totals[service] = {
                    "service_type": service,
                    "total_cost": 0,
                    "transaction_count": 0,
                    "costs": [],
                }
            service_totals[service]["total_cost"] += cost.amount
            service_totals[service]["transaction_count"] += 1
            service_totals[service]["costs"].append(
                {
                    "amount": cost.amount,
                    "timestamp": cost.timestamp.isoformat() if cost.timestamp else None,
                    "operation": getattr(cost, "operation_type", "unknown"),
                }
            )

        return list(service_totals.values())

    def _group_by_day(self, costs) -> List[Dict[str, Any]]:
        """Group costs by day."""
        daily_totals = {}
        for cost in costs:
            date_key = (
                cost.timestamp.date().isoformat() if cost.timestamp else "unknown"
            )
            if date_key not in daily_totals:
                daily_totals[date_key] = {
                    "date": date_key,
                    "total_cost": 0,
                    "transaction_count": 0,
                    "services": {},
                }
            daily_totals[date_key]["total_cost"] += cost.amount
            daily_totals[date_key]["transaction_count"] += 1

            service = cost.service_type
            if service not in daily_totals[date_key]["services"]:
                daily_totals[date_key]["services"][service] = 0
            daily_totals[date_key]["services"][service] += cost.amount

        return list(daily_totals.values())

    def _group_by_operation(self, costs) -> List[Dict[str, Any]]:
        """Group costs by operation type."""
        operation_totals = {}
        for cost in costs:
            operation = getattr(cost, "operation_type", "unknown")
            if operation not in operation_totals:
                operation_totals[operation] = {
                    "operation_type": operation,
                    "total_cost": 0,
                    "transaction_count": 0,
                    "services": {},
                }
            operation_totals[operation]["total_cost"] += cost.amount
            operation_totals[operation]["transaction_count"] += 1

            service = cost.service_type
            if service not in operation_totals[operation]["services"]:
                operation_totals[operation]["services"][service] = 0
            operation_totals[operation]["services"][service] += cost.amount

        return list(operation_totals.values())

    def _group_by_service_from_breakdown(
        self, breakdown: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """Group costs by service type from breakdown data."""
        service_data = []
        for date, services in breakdown.items():
            for service, cost in services.items():
                service_data.append(
                    {
                        "service_type": service,
                        "total_cost": cost,
                        "transaction_count": 1,  # Approximation
                        "date": date,
                    }
                )

        # Aggregate by service
        service_totals = {}
        for item in service_data:
            service = item["service_type"]
            if service not in service_totals:
                service_totals[service] = {
                    "service_type": service,
                    "total_cost": 0,
                    "transaction_count": 0,
                    "costs": [],
                }
            service_totals[service]["total_cost"] += item["total_cost"]
            service_totals[service]["transaction_count"] += 1
            service_totals[service]["costs"].append(
                {
                    "amount": item["total_cost"],
                    "timestamp": item["date"],
                    "operation": "unknown",
                }
            )

        return list(service_totals.values())

    def _group_by_day_from_breakdown(
        self, breakdown: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """Group costs by day from breakdown data."""
        daily_data = []
        for date, services in breakdown.items():
            total_cost = sum(services.values())
            daily_data.append(
                {
                    "date": date,
                    "total_cost": total_cost,
                    "transaction_count": len(services),
                    "services": services,
                }
            )

        return daily_data

    def _calculate_total_from_breakdown(
        self, breakdown: Dict[str, Dict[str, float]]
    ) -> float:
        """Calculate total cost from breakdown data."""
        total = 0.0
        for date, services in breakdown.items():
            total += sum(services.values())
        return total

    def _analyze_cost_trends(
        self, days_back: int = 90, service_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze cost trends using simple statistical methods."""
        try:
            # Get historical cost data
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)

            # Get daily breakdown for trend analysis
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()

            # Convert breakdown to cost-like objects for analysis
            costs = []
            for date_str, services in daily_breakdown.items():
                for service, amount in services.items():
                    if service_type is None or service == service_type:
                        # Create a simple cost-like object
                        class MockCost:
                            def __init__(self, amount, timestamp, service_type):
                                self.amount = amount
                                self.timestamp = (
                                    datetime.strptime(date_str, "%Y-%m-%d")
                                    if isinstance(date_str, str)
                                    else datetime.utcnow()
                                )
                                self.service_type = service_type

                        costs.append(MockCost(amount, date_str, service))

            # Group by day for trend analysis
            daily_costs = {}
            for cost in costs:
                date_key = (
                    cost.timestamp.date()
                    if cost.timestamp
                    else datetime.utcnow().date()
                )
                if date_key not in daily_costs:
                    daily_costs[date_key] = 0
                daily_costs[date_key] += cost.amount

            # Fill missing days with 0
            current_date = start_date.date()
            while current_date <= end_date.date():
                if current_date not in daily_costs:
                    daily_costs[current_date] = 0
                current_date += timedelta(days=1)

            # Sort by date
            sorted_dates = sorted(daily_costs.keys())
            cost_values = [daily_costs[date] for date in sorted_dates]

            # Calculate statistics
            if cost_values:
                avg_cost = statistics.mean(cost_values)
                median_cost = statistics.median(cost_values)
                min_cost = min(cost_values)
                max_cost = max(cost_values)

                # Calculate trend (simple linear regression alternative)
                trend_direction = self._calculate_simple_trend(cost_values)

                # Detect anomalies (values > 2 standard deviations from mean)
                if len(cost_values) > 1:
                    std_dev = statistics.stdev(cost_values)
                    anomalies = []
                    for i, value in enumerate(cost_values):
                        if abs(value - avg_cost) > 2 * std_dev:
                            anomalies.append(
                                {
                                    "date": sorted_dates[i].isoformat(),
                                    "cost": value,
                                    "deviation": abs(value - avg_cost) / std_dev,
                                }
                            )
                else:
                    std_dev = 0
                    anomalies = []
            else:
                avg_cost = median_cost = min_cost = max_cost = 0
                std_dev = 0
                trend_direction = "stable"
                anomalies = []

            return {
                "daily_costs": [
                    {"date": date.isoformat(), "cost": daily_costs[date]}
                    for date in sorted_dates
                ],
                "statistics": {
                    "average": avg_cost,
                    "median": median_cost,
                    "minimum": min_cost,
                    "maximum": max_cost,
                    "standard_deviation": std_dev,
                },
                "trend": {"direction": trend_direction, "analysis_period": days_back},
                "anomalies": anomalies,
            }

        except Exception as e:
            logger.error(f"Error analyzing cost trends: {e}")
            return {"error": str(e)}

    def _calculate_simple_trend(self, values: List[float]) -> str:
        """Calculate simple trend direction."""
        if len(values) < 2:
            return "stable"

        # Compare first and last thirds
        third = len(values) // 3
        if third < 1:
            third = 1

        first_third_avg = statistics.mean(values[:third])
        last_third_avg = statistics.mean(values[-third:])

        diff_percent = (last_third_avg - first_third_avg) / max(first_third_avg, 0.01)

        if diff_percent > 0.1:  # 10% increase
            return "increasing"
        elif diff_percent < -0.1:  # 10% decrease
            return "decreasing"
        else:
            return "stable"

    def _generate_optimization_insights(self) -> Dict[str, Any]:
        """Generate cost optimization insights and recommendations."""
        try:
            # Get recent cost data (last 30 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)

            # Get recent cost data from daily breakdown
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()

            # Convert to cost-like objects for analysis
            recent_costs = []
            for date_str, services in daily_breakdown.items():
                for service, amount in services.items():
                    # Create a simple cost-like object
                    class MockCost:
                        def __init__(self, amount, service_type):
                            self.amount = amount
                            self.service_type = service_type

                    recent_costs.append(MockCost(amount, service))

            # Analyze by service type
            service_analysis = {}
            total_cost = 0

            for cost in recent_costs:
                service = cost.service_type
                if service not in service_analysis:
                    service_analysis[service] = {
                        "total_cost": 0,
                        "transaction_count": 0,
                        "avg_cost_per_transaction": 0,
                    }
                service_analysis[service]["total_cost"] += cost.amount
                service_analysis[service]["transaction_count"] += 1
                total_cost += cost.amount

            # Calculate averages and generate insights
            recommendations = []
            optimization_score = 100  # Start with perfect score

            for service, data in service_analysis.items():
                if data["transaction_count"] > 0:
                    data["avg_cost_per_transaction"] = (
                        data["total_cost"] / data["transaction_count"]
                    )
                    data["cost_percentage"] = (
                        data["total_cost"] / max(total_cost, 0.01)
                    ) * 100

                    # Generate service-specific recommendations
                    if data["cost_percentage"] > 50:
                        recommendations.append(
                            {
                                "priority": "high",
                                "service": service,
                                "message": f"{service} accounts for {data['cost_percentage']:.1f}% of total costs. Consider optimization.",
                                "potential_savings": data["total_cost"]
                                * 0.1,  # Assume 10% savings potential
                            }
                        )
                        optimization_score -= 20
                    elif data["cost_percentage"] > 30:
                        recommendations.append(
                            {
                                "priority": "medium",
                                "service": service,
                                "message": f"{service} is a significant cost driver ({data['cost_percentage']:.1f}%). Monitor usage.",
                                "potential_savings": data["total_cost"]
                                * 0.05,  # Assume 5% savings potential
                            }
                        )
                        optimization_score -= 10

            # Add general recommendations
            if total_cost > 0:
                daily_avg = total_cost / 30
                if daily_avg > 100:  # Arbitrary threshold
                    recommendations.append(
                        {
                            "priority": "medium",
                            "service": "general",
                            "message": f"Daily average cost (${daily_avg:.2f}) is high. Review overall usage patterns.",
                            "potential_savings": daily_avg
                            * 0.15
                            * 30,  # 15% monthly savings
                        }
                    )

            optimization_score = max(0, min(100, optimization_score))

            return {
                "service_analysis": service_analysis,
                "recommendations": recommendations,
                "optimization_score": optimization_score,
                "total_monthly_cost": total_cost,
                "potential_monthly_savings": sum(
                    r.get("potential_savings", 0) for r in recommendations
                ),
            }

        except Exception as e:
            logger.error(f"Error generating optimization insights: {e}")
            return {"error": str(e)}

    def _get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status and utilization."""
        try:
            # Get monthly budget info
            current_month = datetime.utcnow().replace(day=1)

            # Get monthly cost directly
            monthly_spent = cost_tracker.get_monthly_cost()

            # Get budget limits (mock values - would come from config in real implementation)
            monthly_budget = 1000.0  # Default budget
            daily_budget = monthly_budget / 30

            # Calculate utilization
            days_into_month = (datetime.utcnow() - current_month).days + 1
            expected_spend = daily_budget * days_into_month
            utilization_percent = (monthly_spent / monthly_budget) * 100

            # Determine status
            if utilization_percent > 90:
                status = "critical"
            elif utilization_percent > 75:
                status = "warning"
            elif utilization_percent > 50:
                status = "good"
            else:
                status = "excellent"

            return {
                "monthly_budget": monthly_budget,
                "monthly_spent": monthly_spent,
                "monthly_remaining": monthly_budget - monthly_spent,
                "utilization_percent": utilization_percent,
                "expected_spend": expected_spend,
                "variance": monthly_spent - expected_spend,
                "daily_average": monthly_spent / max(days_into_month, 1),
                "status": status,
                "days_into_month": days_into_month,
            }

        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return {"error": str(e)}

    def _get_realtime_cost_summary(self) -> Dict[str, Any]:
        """Get real-time cost summary for dashboard updates."""
        try:
            # Get today's and yesterday's costs using daily cost method
            today_total = cost_tracker.get_daily_cost()

            # Get daily breakdown to find yesterday's cost
            daily_breakdown = cost_tracker.get_daily_cost_breakdown()
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

            yesterday_total = 0.0
            if yesterday in daily_breakdown:
                yesterday_total = sum(daily_breakdown[yesterday].values())

            # Get today's service breakdown
            today_key = datetime.utcnow().strftime("%Y-%m-%d")
            service_breakdown = daily_breakdown.get(today_key, {})

            # Calculate change
            if yesterday_total > 0:
                daily_change_percent = (
                    (today_total - yesterday_total) / yesterday_total
                ) * 100
            else:
                daily_change_percent = 0

            return {
                "today_total": today_total,
                "yesterday_total": yesterday_total,
                "daily_change_percent": daily_change_percent,
                "service_breakdown": service_breakdown,
                "transaction_count": len(service_breakdown),
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting realtime cost summary: {e}")
            return {"error": str(e)}


# Create global instance
enhanced_dashboard = EnhancedCostDashboard()


def create_enhanced_dashboard_app(host: str = "127.0.0.1", port: int = 5001) -> Flask:
    """Create and configure the enhanced dashboard Flask app."""
    dashboard = EnhancedCostDashboard(host=host, port=port)
    return dashboard.app


def run_enhanced_dashboard(
    host: str = "127.0.0.1", port: int = 5001, debug: bool = False
):
    """Run the enhanced cost dashboard server."""
    try:
        dashboard = EnhancedCostDashboard(host=host, port=port, debug=debug)
        logger.info(f"Starting enhanced cost dashboard on http://{host}:{port}")
        dashboard.run()
    except Exception as e:
        logger.error(f"Failed to start enhanced dashboard: {e}")
        raise


if __name__ == "__main__":
    run_enhanced_dashboard()
