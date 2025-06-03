"""
Profit Reporting Service
=======================

This module provides comprehensive profit and business intelligence reporting
for the LeadFactory system, integrating cost and revenue data.

Features:
- Daily, weekly, monthly profit reports
- Margin analysis and trends
- Cost breakdown analysis
- Revenue stream analysis
- Export capabilities (JSON, CSV)
- Grafana dashboard integration
"""

import csv
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ProfitReportingService:
    """Service for generating profit and business intelligence reports."""

    def __init__(
        self,
        cost_aggregation_service: "CostAggregationService",
        reports_dir: Optional[str] = None,
    ):
        """Initialize profit reporting service."""
        self.cost_aggregation = cost_aggregation_service
        self.reports_dir = reports_dir or tempfile.gettempdir()

        # Create reports directory if it doesn't exist
        os.makedirs(self.reports_dir, exist_ok=True)

        logger.info("Profit reporting service initialized")

    def generate_daily_report(self, date: str) -> Dict[str, Any]:
        """Generate daily profit report with enhanced fee breakdowns.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Daily profit report with detailed fee breakdown structure
        """
        logger.info(f"Generating daily profit report for {date}")

        # Get or create daily aggregation
        daily_data = self.cost_aggregation.get_daily_summary(date)
        if not daily_data:
            daily_data = self.cost_aggregation.aggregate_daily_data(date)

        # Ensure daily_data is a valid dictionary (handle Mock objects in tests)
        if not isinstance(daily_data, dict):
            daily_data = {}

        # Calculate subtotals before agency fees
        gross_revenue_subtotal = daily_data.get("gross_revenue_cents", 0) / 100
        net_revenue_subtotal = daily_data.get("net_revenue_cents", 0) / 100
        stripe_fees_subtotal = daily_data.get("stripe_fees_cents", 0) / 100
        tax_amount_subtotal = daily_data.get("tax_amount_cents", 0) / 100
        operational_costs_subtotal = (
            daily_data.get("total_operational_costs_cents", 0) / 100
        )

        # Agency fees (future implementation - placeholder for now)
        agency_revenue = 0.0  # Future: incremental agency revenue
        agency_costs = 0.0  # Future: incremental agency costs
        agency_fees = 0.0  # Future: agency processing fees

        # Grand totals including agency fees
        total_gross_revenue = gross_revenue_subtotal + agency_revenue
        total_net_revenue = net_revenue_subtotal + agency_revenue - agency_fees
        total_stripe_fees = stripe_fees_subtotal + agency_fees
        total_tax_amount = tax_amount_subtotal
        total_operational_costs = operational_costs_subtotal + agency_costs

        # Profit calculations
        gross_profit = total_gross_revenue - total_operational_costs
        net_profit = total_net_revenue - total_operational_costs
        gross_margin_percent = (
            (gross_profit / total_gross_revenue * 100) if total_gross_revenue > 0 else 0
        )
        net_margin_percent = (
            (net_profit / total_net_revenue * 100) if total_net_revenue > 0 else 0
        )

        # Format enhanced report with fee breakdowns
        report = {
            "report_type": "daily",
            "date": date,
            "generated_at": datetime.now().isoformat(),
            # Subtotals before agency fees
            "revenue_subtotal": {
                "gross_revenue": gross_revenue_subtotal,
                "net_revenue": net_revenue_subtotal,
                "stripe_fees": stripe_fees_subtotal,
                "tax_amount": tax_amount_subtotal,
                "transaction_count": daily_data.get("transaction_count", 0),
                "refund_count": daily_data.get("refund_count", 0),
                "refund_amount": daily_data.get("refund_amount_cents", 0) / 100,
            },
            "costs_subtotal": {
                "total_operational_costs": operational_costs_subtotal,
                "openai_costs": daily_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": daily_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": daily_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": daily_data.get("other_api_costs_cents", 0) / 100,
            },
            # Agency fees section (future implementation)
            "agency_adjustments": {
                "agency_revenue": agency_revenue,
                "agency_costs": agency_costs,
                "agency_processing_fees": agency_fees,
                "note": "Agency fees implementation reserved for future phase",
            },
            # Grand totals including all fees
            "revenue_total": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "total_stripe_fees": total_stripe_fees,
                "total_tax_amount": total_tax_amount,
                "transaction_count": daily_data.get("transaction_count", 0),
                "refund_count": daily_data.get("refund_count", 0),
                "refund_amount": daily_data.get("refund_amount_cents", 0) / 100,
            },
            "costs_total": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": daily_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": daily_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": daily_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": daily_data.get("other_api_costs_cents", 0) / 100,
                "agency_costs": agency_costs,
            },
            "profit": {
                "gross_profit": gross_profit,
                "net_profit": net_profit,
                "gross_margin_percent": gross_margin_percent,
                "net_margin_percent": net_margin_percent,
            },
            # Enhanced metrics with fee breakdown analysis
            "metrics": {
                "average_transaction_value": total_gross_revenue
                / max(daily_data.get("transaction_count", 1), 1),
                "cost_per_transaction": total_operational_costs
                / max(daily_data.get("transaction_count", 1), 1),
                "stripe_fee_rate": (total_stripe_fees / max(total_gross_revenue, 1))
                * 100,
                "refund_rate": (
                    daily_data.get("refund_count", 0)
                    / max(daily_data.get("transaction_count", 1), 1)
                )
                * 100,
                "net_revenue_retention": (
                    total_net_revenue / max(total_gross_revenue, 1)
                )
                * 100,
                "operational_efficiency": (net_profit / max(total_operational_costs, 1))
                * 100,
            },
            # Legacy format for backward compatibility
            "revenue": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "stripe_fees": total_stripe_fees,
                "tax_amount": total_tax_amount,
                "transaction_count": daily_data.get("transaction_count", 0),
                "refund_count": daily_data.get("refund_count", 0),
                "refund_amount": daily_data.get("refund_amount_cents", 0) / 100,
            },
            "costs": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": daily_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": daily_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": daily_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": daily_data.get("other_api_costs_cents", 0) / 100,
            },
            # Business insights
        }

        # Add business insights after report structure is complete
        if total_gross_revenue > 0:
            report["insights"] = self._generate_business_insights(report)
        else:
            report["insights"] = ["No data available for this date"]

        logger.info(
            f"Daily report generated: gross_profit=${report['profit']['gross_profit']:.2f}, net_profit=${report['profit']['net_profit']:.2f}"
        )
        return report

    def generate_weekly_report(self, start_date: str) -> Dict[str, Any]:
        """Generate weekly profit report with enhanced fee breakdowns.

        Args:
            start_date: Start date of week in YYYY-MM-DD format

        Returns:
            Weekly profit report with detailed fee breakdown structure
        """
        logger.info(f"Generating weekly profit report starting {start_date}")

        # Calculate week dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=6)
        end_date = end_dt.strftime("%Y-%m-%d")

        # Get daily data for the week
        daily_reports = []
        week_totals = {
            "gross_revenue_cents": 0,
            "net_revenue_cents": 0,
            "stripe_fees_cents": 0,
            "tax_amount_cents": 0,
            "transaction_count": 0,
            "refund_count": 0,
            "refund_amount_cents": 0,
            "total_operational_costs_cents": 0,
            "openai_costs_cents": 0,
            "semrush_costs_cents": 0,
            "gpu_costs_cents": 0,
            "other_api_costs_cents": 0,
        }

        current_dt = start_dt
        while current_dt <= end_dt:
            date_str = current_dt.strftime("%Y-%m-%d")
            daily_data = self.cost_aggregation.get_daily_summary(date_str)

            if daily_data:
                daily_reports.append(daily_data)
                for key in week_totals:
                    week_totals[key] += daily_data.get(key, 0)

            current_dt += timedelta(days=1)

        # Calculate subtotals before agency fees
        gross_revenue_subtotal = week_totals["gross_revenue_cents"] / 100
        net_revenue_subtotal = week_totals["net_revenue_cents"] / 100
        stripe_fees_subtotal = week_totals["stripe_fees_cents"] / 100
        tax_amount_subtotal = week_totals["tax_amount_cents"] / 100
        operational_costs_subtotal = week_totals["total_operational_costs_cents"] / 100

        # Agency fees (future implementation - placeholder for now)
        agency_revenue = 0.0  # Future: incremental agency revenue
        agency_costs = 0.0  # Future: incremental agency costs
        agency_fees = 0.0  # Future: agency processing fees

        # Grand totals including agency fees
        total_gross_revenue = gross_revenue_subtotal + agency_revenue
        total_net_revenue = net_revenue_subtotal + agency_revenue - agency_fees
        total_stripe_fees = stripe_fees_subtotal + agency_fees
        total_tax_amount = tax_amount_subtotal
        total_operational_costs = operational_costs_subtotal + agency_costs

        # Calculate weekly profit metrics
        gross_profit = total_gross_revenue - total_operational_costs
        net_profit = total_net_revenue - total_operational_costs
        gross_margin_percent = (
            (gross_profit / total_gross_revenue * 100) if total_gross_revenue > 0 else 0
        )
        net_margin_percent = (
            (net_profit / total_net_revenue * 100) if total_net_revenue > 0 else 0
        )

        report = {
            "report_type": "weekly",
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.now().isoformat(),
            "active_days": len(daily_reports),
            # Subtotals before agency fees
            "revenue_subtotal": {
                "gross_revenue": gross_revenue_subtotal,
                "net_revenue": net_revenue_subtotal,
                "stripe_fees": stripe_fees_subtotal,
                "tax_amount": tax_amount_subtotal,
                "transaction_count": week_totals["transaction_count"],
                "refund_count": week_totals["refund_count"],
                "refund_amount": week_totals["refund_amount_cents"] / 100,
            },
            "costs_subtotal": {
                "total_operational_costs": operational_costs_subtotal,
                "openai_costs": week_totals["openai_costs_cents"] / 100,
                "semrush_costs": week_totals["semrush_costs_cents"] / 100,
                "gpu_costs": week_totals["gpu_costs_cents"] / 100,
                "other_api_costs": week_totals["other_api_costs_cents"] / 100,
            },
            # Agency fees section (future implementation)
            "agency_adjustments": {
                "agency_revenue": agency_revenue,
                "agency_costs": agency_costs,
                "agency_processing_fees": agency_fees,
                "note": "Agency fees implementation reserved for future phase",
            },
            # Grand totals including all fees
            "revenue_total": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "total_stripe_fees": total_stripe_fees,
                "total_tax_amount": total_tax_amount,
                "transaction_count": week_totals["transaction_count"],
                "refund_count": week_totals["refund_count"],
                "refund_amount": week_totals["refund_amount_cents"] / 100,
            },
            "costs_total": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": week_totals["openai_costs_cents"] / 100,
                "semrush_costs": week_totals["semrush_costs_cents"] / 100,
                "gpu_costs": week_totals["gpu_costs_cents"] / 100,
                "other_api_costs": week_totals["other_api_costs_cents"] / 100,
                "agency_costs": agency_costs,
            },
            "profit": {
                "gross_profit": gross_profit,
                "net_profit": net_profit,
                "gross_margin_percent": gross_margin_percent,
                "net_margin_percent": net_margin_percent,
            },
            # Enhanced metrics with fee breakdown analysis
            "metrics": {
                "average_transaction_value": total_gross_revenue
                / max(week_totals["transaction_count"], 1),
                "cost_per_transaction": total_operational_costs
                / max(week_totals["transaction_count"], 1),
                "stripe_fee_rate": (total_stripe_fees / max(total_gross_revenue, 1))
                * 100,
                "refund_rate": (
                    week_totals["refund_count"]
                    / max(week_totals["transaction_count"], 1)
                )
                * 100,
                "net_revenue_retention": (
                    total_net_revenue / max(total_gross_revenue, 1)
                )
                * 100,
                "operational_efficiency": (net_profit / max(total_operational_costs, 1))
                * 100,
                "average_daily_revenue": total_gross_revenue
                / max(len(daily_reports), 1),
                "average_daily_profit": gross_profit / max(len(daily_reports), 1),
            },
            "daily_breakdown": [
                {
                    "date": daily["date"],
                    "gross_revenue": daily.get("gross_revenue_cents", 0) / 100,
                    "net_profit": (
                        daily.get("net_revenue_cents", 0)
                        - daily.get("total_operational_costs_cents", 0)
                    )
                    / 100,
                    "transaction_count": daily.get("transaction_count", 0),
                    "stripe_fees": daily.get("stripe_fees_cents", 0) / 100,
                }
                for daily in daily_reports
            ],
            # Legacy format for backward compatibility
            "revenue": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "stripe_fees": total_stripe_fees,
                "tax_amount": total_tax_amount,
                "transaction_count": week_totals["transaction_count"],
                "refund_count": week_totals["refund_count"],
                "refund_amount": week_totals["refund_amount_cents"] / 100,
            },
            "costs": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": week_totals["openai_costs_cents"] / 100,
                "semrush_costs": week_totals["semrush_costs_cents"] / 100,
                "gpu_costs": week_totals["gpu_costs_cents"] / 100,
                "other_api_costs": week_totals["other_api_costs_cents"] / 100,
            },
        }

        logger.info(
            f"Weekly report generated: gross_profit=${report['profit']['gross_profit']:.2f}, net_profit=${report['profit']['net_profit']:.2f}"
        )
        return report

    def generate_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        """Generate monthly profit report with enhanced fee breakdowns.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Monthly profit report with detailed fee breakdown structure
        """
        logger.info(f"Generating monthly profit report for {year}-{month:02d}")

        # Get or create monthly aggregation
        monthly_data = self.cost_aggregation.get_monthly_summary(year, month)
        if not monthly_data:
            monthly_data = self.cost_aggregation.aggregate_monthly_data(year, month)

        # Ensure monthly_data is a valid dictionary (handle Mock objects in tests)
        if not isinstance(monthly_data, dict):
            monthly_data = {}

        # Get previous month for comparison
        prev_year = year if month > 1 else year - 1
        prev_month = month - 1 if month > 1 else 12
        prev_monthly_data = self.cost_aggregation.get_monthly_summary(
            prev_year, prev_month
        )

        # Ensure prev_monthly_data is a valid dictionary if it exists
        if prev_monthly_data and not isinstance(prev_monthly_data, dict):
            prev_monthly_data = None

        # Calculate subtotals before agency fees
        gross_revenue_subtotal = monthly_data.get("gross_revenue_cents", 0) / 100
        net_revenue_subtotal = monthly_data.get("net_revenue_cents", 0) / 100
        stripe_fees_subtotal = monthly_data.get("stripe_fees_cents", 0) / 100
        tax_amount_subtotal = monthly_data.get("tax_amount_cents", 0) / 100
        operational_costs_subtotal = (
            monthly_data.get("total_operational_costs_cents", 0) / 100
        )

        # Agency fees (future implementation - placeholder for now)
        agency_revenue = 0.0  # Future: incremental agency revenue
        agency_costs = 0.0  # Future: incremental agency costs
        agency_fees = 0.0  # Future: agency processing fees

        # Grand totals including agency fees
        total_gross_revenue = gross_revenue_subtotal + agency_revenue
        total_net_revenue = net_revenue_subtotal + agency_revenue - agency_fees
        total_stripe_fees = stripe_fees_subtotal + agency_fees
        total_tax_amount = tax_amount_subtotal
        total_operational_costs = operational_costs_subtotal + agency_costs

        # Calculate monthly profit metrics
        gross_profit = total_gross_revenue - total_operational_costs
        net_profit = total_net_revenue - total_operational_costs
        gross_margin_percent = (
            (gross_profit / total_gross_revenue * 100) if total_gross_revenue > 0 else 0
        )
        net_margin_percent = (
            (net_profit / total_net_revenue * 100) if total_net_revenue > 0 else 0
        )

        # Calculate month-over-month changes
        mom_changes = {}
        if prev_monthly_data:
            prev_gross_revenue = prev_monthly_data.get("gross_revenue_cents", 0) / 100
            prev_net_profit = (
                prev_monthly_data.get("net_revenue_cents", 0)
                - prev_monthly_data.get("total_operational_costs_cents", 0)
            ) / 100
            prev_transaction_count = prev_monthly_data.get("transaction_count", 0)

            mom_changes = {
                "gross_revenue_percent": (
                    (total_gross_revenue - prev_gross_revenue)
                    / max(prev_gross_revenue, 1)
                )
                * 100,
                "net_profit_percent": (
                    (net_profit - prev_net_profit) / max(abs(prev_net_profit), 1)
                )
                * 100,
                "transaction_count_percent": (
                    (monthly_data.get("transaction_count", 0) - prev_transaction_count)
                    / max(prev_transaction_count, 1)
                )
                * 100,
            }

        report = {
            "report_type": "monthly",
            "year": year,
            "month": month,
            "generated_at": datetime.now().isoformat(),
            "active_days": monthly_data.get("active_days", 0),
            # Subtotals before agency fees
            "revenue_subtotal": {
                "gross_revenue": gross_revenue_subtotal,
                "net_revenue": net_revenue_subtotal,
                "stripe_fees": stripe_fees_subtotal,
                "tax_amount": tax_amount_subtotal,
                "transaction_count": monthly_data.get("transaction_count", 0),
                "refund_count": monthly_data.get("refund_count", 0),
                "refund_amount": monthly_data.get("refund_amount_cents", 0) / 100,
            },
            "costs_subtotal": {
                "total_operational_costs": operational_costs_subtotal,
                "openai_costs": monthly_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": monthly_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": monthly_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": monthly_data.get("other_api_costs_cents", 0) / 100,
            },
            # Agency fees section (future implementation)
            "agency_adjustments": {
                "agency_revenue": agency_revenue,
                "agency_costs": agency_costs,
                "agency_processing_fees": agency_fees,
                "note": "Agency fees implementation reserved for future phase",
            },
            # Grand totals including all fees
            "revenue_total": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "total_stripe_fees": total_stripe_fees,
                "total_tax_amount": total_tax_amount,
                "transaction_count": monthly_data.get("transaction_count", 0),
                "refund_count": monthly_data.get("refund_count", 0),
                "refund_amount": monthly_data.get("refund_amount_cents", 0) / 100,
            },
            "costs_total": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": monthly_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": monthly_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": monthly_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": monthly_data.get("other_api_costs_cents", 0) / 100,
                "agency_costs": agency_costs,
            },
            "profit": {
                "gross_profit": gross_profit,
                "net_profit": net_profit,
                "gross_margin_percent": gross_margin_percent,
                "net_margin_percent": net_margin_percent,
            },
            # Enhanced metrics with fee breakdown analysis
            "metrics": {
                "average_transaction_value": total_gross_revenue
                / max(monthly_data.get("transaction_count", 1), 1),
                "cost_per_transaction": total_operational_costs
                / max(monthly_data.get("transaction_count", 1), 1),
                "stripe_fee_rate": (total_stripe_fees / max(total_gross_revenue, 1))
                * 100,
                "refund_rate": (
                    monthly_data.get("refund_count", 0)
                    / max(monthly_data.get("transaction_count", 1), 1)
                )
                * 100,
                "net_revenue_retention": (
                    total_net_revenue / max(total_gross_revenue, 1)
                )
                * 100,
                "operational_efficiency": (net_profit / max(total_operational_costs, 1))
                * 100,
                "average_daily_revenue": total_gross_revenue
                / max(monthly_data.get("active_days", 1), 1),
                "average_daily_profit": net_profit
                / max(monthly_data.get("active_days", 1), 1),
            },
            "month_over_month": mom_changes,
            # Legacy fields for backward compatibility
            "average_daily_revenue": round(
                total_gross_revenue / max(monthly_data.get("active_days", 1), 1), 2
            ),
            "average_daily_profit": round(
                net_profit / max(monthly_data.get("active_days", 1), 1), 2
            ),
            # Legacy format for backward compatibility
            "revenue": {
                "gross_revenue": total_gross_revenue,
                "net_revenue": total_net_revenue,
                "stripe_fees": total_stripe_fees,
                "tax_amount": total_tax_amount,
                "transaction_count": monthly_data.get("transaction_count", 0),
                "refund_count": monthly_data.get("refund_count", 0),
                "refund_amount": monthly_data.get("refund_amount_cents", 0) / 100,
            },
            "costs": {
                "total_operational_costs": total_operational_costs,
                "openai_costs": monthly_data.get("openai_costs_cents", 0) / 100,
                "semrush_costs": monthly_data.get("semrush_costs_cents", 0) / 100,
                "gpu_costs": monthly_data.get("gpu_costs_cents", 0) / 100,
                "other_api_costs": monthly_data.get("other_api_costs_cents", 0) / 100,
            },
        }

        # Add business insights after report structure is complete
        if total_gross_revenue > 0:
            report["insights"] = self._generate_business_insights(report)
        else:
            report["insights"] = ["No data available for this date"]

        logger.info(
            f"Monthly report generated: gross_profit=${report['profit']['gross_profit']:.2f}, net_profit=${report['profit']['net_profit']:.2f}"
        )
        return report

    def analyze_trends(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Analyze trends over a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Trend analysis report
        """
        logger.info(f"Analyzing trends from {start_date} to {end_date}")

        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Collect daily data for the period
        time_series = []
        current_date = start_dt
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data = self.cost_aggregation.get_daily_summary(date_str)

            if daily_data and isinstance(daily_data, dict):
                time_series.append(
                    {
                        "date": date_str,
                        "gross_revenue": daily_data.get("gross_revenue_cents", 0) / 100,
                        "gross_profit": daily_data.get("gross_profit_cents", 0) / 100,
                        "total_costs": daily_data.get(
                            "total_operational_costs_cents", 0
                        )
                        / 100,
                        "transaction_count": daily_data.get("transaction_count", 0),
                        "gross_margin_percent": daily_data.get(
                            "gross_margin_percent", 0
                        ),
                    }
                )

            current_date += timedelta(days=1)

        if not time_series:
            return {"error": "No data available for the specified period"}

        # Calculate trends
        revenue_trend = self._calculate_trend(
            [day["gross_revenue"] for day in time_series]
        )
        profit_trend = self._calculate_trend(
            [day["gross_profit"] for day in time_series]
        )
        cost_trend = self._calculate_trend([day["total_costs"] for day in time_series])
        transaction_trend = self._calculate_trend(
            [day["transaction_count"] for day in time_series]
        )

        return {
            "revenue_trend": revenue_trend,
            "profit_trend": profit_trend,
            "cost_trend": cost_trend,
            "transaction_trend": transaction_trend,
            "period_days": len(time_series),
            "start_date": start_date,
            "end_date": end_date,
        }

    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """Calculate trend statistics for a series of values.

        Args:
            values: List of numeric values

        Returns:
            Trend statistics including slope, correlation, and direction
        """
        if len(values) < 2:
            return {
                "slope": 0,
                "correlation": 0,
                "direction": "stable",
                "change_percent": 0,
            }

        # Simple linear regression calculation
        n = len(values)
        x = list(range(n))

        # Calculate means
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        # Calculate slope and correlation
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        x_variance = sum((x[i] - x_mean) ** 2 for i in range(n))
        y_variance = sum((values[i] - y_mean) ** 2 for i in range(n))

        slope = numerator / x_variance if x_variance != 0 else 0
        correlation = (
            numerator / (x_variance * y_variance) ** 0.5
            if x_variance * y_variance > 0
            else 0
        )

        # Determine direction
        if slope > 0.01:
            direction = "increasing"
        elif slope < -0.01:
            direction = "decreasing"
        else:
            direction = "stable"

        # Calculate percentage change
        start_val = values[0] if values[0] != 0 else 1
        end_val = values[-1]
        change_percent = ((end_val - start_val) / abs(start_val)) * 100

        return {
            "slope": slope,
            "correlation": correlation,
            "direction": direction,
            "change_percent": change_percent,
        }

    def generate_trend_analysis(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate trend analysis report.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Trend analysis report
        """
        logger.info(f"Generating trend analysis from {start_date} to {end_date}")

        # Get Grafana dashboard data for the period
        dashboard_data = self.cost_aggregation.get_grafana_dashboard_data(
            start_date, end_date
        )
        time_series = dashboard_data.get("time_series", [])

        if not time_series:
            return {"error": "No data available for the specified period"}

        # Calculate trends
        revenue_trend = self._calculate_trend(
            [day["gross_revenue"] for day in time_series]
        )
        profit_trend = self._calculate_trend(
            [day["gross_profit"] for day in time_series]
        )
        margin_trend = self._calculate_trend(
            [day["gross_margin_percent"] for day in time_series]
        )
        cost_trend = self._calculate_trend([day["total_costs"] for day in time_series])

        # Find best and worst performing days
        best_day = max(time_series, key=lambda x: x["gross_profit"])
        worst_day = min(time_series, key=lambda x: x["gross_profit"])

        report = {
            "report_type": "trend_analysis",
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.now().isoformat(),
            "period_days": len(time_series),
            "trends": {
                "revenue_trend": revenue_trend,
                "profit_trend": profit_trend,
                "margin_trend": margin_trend,
                "cost_trend": cost_trend,
            },
            "performance": {
                "best_day": {
                    "date": best_day["date"],
                    "gross_profit": best_day["gross_profit"],
                    "gross_revenue": best_day["gross_revenue"],
                    "transaction_count": best_day["transaction_count"],
                },
                "worst_day": {
                    "date": worst_day["date"],
                    "gross_profit": worst_day["gross_profit"],
                    "gross_revenue": worst_day["gross_revenue"],
                    "transaction_count": worst_day["transaction_count"],
                },
            },
            "summary": dashboard_data.get("summary", {}),
            "insights": self._generate_insights(time_series, dashboard_data["summary"]),
        }

        logger.info(f"Trend analysis generated for {len(time_series)} days")
        return report

    def _generate_insights(self, time_series: List[Dict], summary: Dict) -> List[str]:
        """Generate business insights from the data.

        Args:
            time_series: Daily time series data
            summary: Summary statistics

        Returns:
            List of insight strings
        """
        insights = []

        # Revenue insights
        avg_daily_revenue = summary.get("total_gross_revenue", 0) / max(
            len(time_series), 1
        )
        if avg_daily_revenue > 1000:
            insights.append(
                f"Strong daily revenue performance averaging ${avg_daily_revenue:.2f}"
            )
        elif avg_daily_revenue > 500:
            insights.append(
                f"Moderate daily revenue performance averaging ${avg_daily_revenue:.2f}"
            )
        else:
            insights.append(
                f"Revenue growth opportunity identified - current average ${avg_daily_revenue:.2f}/day"
            )

        # Margin insights
        avg_gross_margin = summary.get("avg_gross_margin", 0)
        if avg_gross_margin > 70:
            insights.append("Excellent gross margin performance above 70%")
        elif avg_gross_margin > 50:
            insights.append("Good gross margin performance above 50%")
        else:
            insights.append(
                "Margin improvement opportunity - consider cost optimization"
            )

        # Cost insights
        total_costs = summary.get("total_costs", 0)
        total_revenue = summary.get("total_gross_revenue", 0)
        if total_revenue > 0:
            cost_ratio = (total_costs / total_revenue) * 100
            if cost_ratio < 30:
                insights.append(
                    "Efficient cost structure with low cost-to-revenue ratio"
                )
            elif cost_ratio > 50:
                insights.append(
                    "High cost-to-revenue ratio - review operational efficiency"
                )

        # Transaction insights
        total_transactions = summary.get("total_transactions", 0)
        if total_transactions > 0:
            avg_transaction_value = total_revenue / total_transactions
            if avg_transaction_value > 100:
                insights.append(
                    f"High-value transactions averaging ${avg_transaction_value:.2f}"
                )
            elif avg_transaction_value < 50:
                insights.append("Opportunity to increase average transaction value")

        return insights

    def _generate_business_insights(self, report: Dict[str, Any]) -> List[str]:
        """
        Generate business insights from a profit report.

        Args:
            report: Profit report dictionary

        Returns:
            List of business insight strings
        """
        insights = []

        # Get revenue and cost data
        revenue = report.get("revenue", {})
        costs = report.get("costs", {})
        profit = report.get("profit", {})

        gross_revenue = revenue.get("gross_revenue", 0)
        gross_margin = profit.get("gross_margin_percent", 0)
        net_margin = profit.get("net_margin_percent", 0)
        transaction_count = revenue.get("transaction_count", 0)

        # Margin analysis
        if gross_margin > 80:
            insights.append(
                f"Excellent gross margin of {gross_margin:.1f}% indicates strong pricing power"
            )
        elif gross_margin > 60:
            insights.append(
                f"Good gross margin of {gross_margin:.1f}% shows healthy profitability"
            )
        elif gross_margin > 40:
            insights.append(
                f"Moderate gross margin of {gross_margin:.1f}% suggests room for optimization"
            )
        else:
            insights.append(
                f"Low gross margin of {gross_margin:.1f}% requires immediate attention"
            )

        # Cost analysis
        openai_costs = costs.get("openai_costs", 0)
        total_costs = costs.get("total_operational_costs", 0)

        if total_costs > 0:
            openai_percentage = (openai_costs / total_costs) * 100
            if openai_percentage > 70:
                insights.append(
                    f"OpenAI costs represent {openai_percentage:.1f}% of total operational costs - primary expense driver"
                )
            elif openai_percentage > 40:
                insights.append(
                    f"OpenAI costs account for {openai_percentage:.1f}% of operational costs - significant expense"
                )

        # Transaction analysis
        if transaction_count > 0 and gross_revenue > 0:
            avg_transaction_value = gross_revenue / transaction_count
            insights.append(
                f"Average transaction value of ${avg_transaction_value:.2f} across {transaction_count} transactions"
            )

            if avg_transaction_value > 100:
                insights.append(
                    "High average transaction value indicates premium customer base"
                )
            elif avg_transaction_value < 20:
                insights.append(
                    "Low average transaction value suggests volume-based business model"
                )

        # Profitability insights
        if net_margin > 20:
            insights.append("Strong net margin indicates efficient operations")
        elif net_margin < 5:
            insights.append("Low net margin suggests need for cost optimization")

        return insights

    def export_report_csv(self, report: Dict[str, Any]) -> str:
        """Export report to CSV format.

        Args:
            report: Report dictionary

        Returns:
            CSV content as string
        """
        output = StringIO()

        # Handle different report structures
        if "daily_breakdown" in report:
            # Weekly report with daily breakdown
            data_rows = report["daily_breakdown"]
        elif "revenue_total" in report:
            # Enhanced format - flatten to single row
            data_rows = [
                {
                    "date": report.get(
                        "date",
                        f"{report.get('year', '')}-{report.get('month', ''):02d}",
                    ),
                    "gross_revenue": report["revenue_total"]["gross_revenue"],
                    "net_revenue": report["revenue_total"]["net_revenue"],
                    "total_costs": report["costs_total"]["total_operational_costs"],
                    "gross_profit": report["profit"]["gross_profit"],
                    "net_profit": report["profit"]["net_profit"],
                    "transaction_count": report["revenue_total"].get(
                        "transaction_count", 0
                    ),
                }
            ]
        else:
            # Legacy format fallback
            data_rows = [
                {
                    "date": report.get("date", ""),
                    "gross_revenue": report.get("revenue", {}).get("gross_revenue", 0),
                    "total_costs": report.get("costs", {}).get(
                        "total_operational_costs", 0
                    ),
                    "gross_profit": report.get("revenue", {}).get("gross_revenue", 0)
                    - report.get("costs", {}).get("total_operational_costs", 0),
                }
            ]

        if data_rows:
            writer = csv.DictWriter(output, fieldnames=data_rows[0].keys())
            writer.writeheader()
            writer.writerows(data_rows)

        return output.getvalue()

    def export_to_json(self, report: Dict[str, Any], filename: str) -> str:
        """
        Export report to JSON format.

        Args:
            report: Report dictionary to export
            filename: Base filename (without extension)

        Returns:
            Path to the exported JSON file
        """
        filepath = os.path.join(self.reports_dir, f"{filename}.json")

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report exported to JSON: {filepath}")
        return filepath

    def export_to_csv(self, report: Dict[str, Any], filename: str) -> str:
        """
        Export report to CSV format.

        Args:
            report: Report dictionary to export
            filename: Base filename (without extension)

        Returns:
            Path to the exported CSV file
        """
        filepath = os.path.join(self.reports_dir, f"{filename}.csv")

        # Handle different report structures
        if "daily_breakdown" in report:
            # Weekly report with daily breakdown
            data_rows = report["daily_breakdown"]
        elif "revenue_total" in report:
            # Enhanced format - flatten to single row
            data_rows = [
                {
                    "date": report.get(
                        "date",
                        f"{report.get('year', '')}-{report.get('month', ''):02d}",
                    ),
                    "gross_revenue": report["revenue_total"]["gross_revenue"],
                    "net_revenue": report["revenue_total"]["net_revenue"],
                    "total_costs": report["costs_total"]["total_operational_costs"],
                    "gross_profit": report["profit"]["gross_profit"],
                    "net_profit": report["profit"]["net_profit"],
                    "transaction_count": report["revenue_total"].get(
                        "transaction_count", 0
                    ),
                }
            ]
        else:
            # Legacy format fallback
            data_rows = [
                {
                    "date": report.get("date", ""),
                    "gross_revenue": report.get("revenue", {}).get("gross_revenue", 0),
                    "total_costs": report.get("costs", {}).get(
                        "total_operational_costs", 0
                    ),
                    "gross_profit": report.get("revenue", {}).get("gross_revenue", 0)
                    - report.get("costs", {}).get("total_operational_costs", 0),
                }
            ]

        if data_rows:
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data_rows[0].keys())
                writer.writeheader()
                writer.writerows(data_rows)

        logger.info(f"Report exported to CSV: {filepath}")
        return filepath

    def save_report(
        self, report: Dict[str, Any], filename: str, format: str = "json"
    ) -> Optional[str]:
        """
        Save report to disk in specified format.

        Args:
            report: Report dictionary to save
            filename: Base filename (without extension)
            format: File format ('json' or 'csv')

        Returns:
            Path to the saved file, or None if save failed
        """
        try:
            if format.lower() == "json":
                filepath = self.export_to_json(report, filename)
            elif format.lower() == "csv":
                filepath = self.export_to_csv(report, filename)
            else:
                logger.error(f"Unsupported format: {format}")
                return None

            logger.info(f"Report saved to {filename} in {format} format")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return None


# Create singleton instance
profit_reporting_service = None


def get_profit_reporting_service(cost_aggregation_service=None, reports_dir="reports"):
    """Get or create the profit reporting service singleton."""
    global profit_reporting_service
    if profit_reporting_service is None:
        if cost_aggregation_service is None:
            from leadfactory.cost.cost_aggregation import (
                cost_aggregation_service as default_service,
            )

            cost_aggregation_service = default_service
        profit_reporting_service = ProfitReportingService(
            cost_aggregation_service, reports_dir
        )
    return profit_reporting_service
