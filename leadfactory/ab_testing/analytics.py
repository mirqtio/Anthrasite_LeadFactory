"""
A/B Testing Analytics - Comprehensive reporting and analysis.

This module provides analytics and reporting capabilities for A/B tests including
performance dashboards, trend analysis, and automated insights.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.ab_testing.ab_test_manager import (
    ABTestManager,
    TestType,
    ab_test_manager,
)
from leadfactory.ab_testing.statistical_engine import (
    StatisticalEngine,
    statistical_engine,
)
from leadfactory.utils.logging import get_logger


class ReportPeriod(Enum):
    """Reporting time periods."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTER = "quarterly"


@dataclass
class TestPerformanceMetric:
    """Performance metric for a test variant."""

    variant_id: str
    impressions: int
    conversions: int
    conversion_rate: float
    revenue: float
    revenue_per_visitor: float
    confidence_interval: tuple[float, float]
    is_winner: bool
    significance_level: float


@dataclass
class TestInsight:
    """Automated insight from test analysis."""

    test_id: str
    insight_type: str
    title: str
    description: str
    confidence: float
    actionable: bool
    recommendation: str
    impact_estimate: Optional[float]


class ABTestAnalytics:
    """Analytics engine for A/B testing insights and reporting."""

    def __init__(
        self,
        test_manager: Optional[ABTestManager] = None,
        statistical_engine: Optional[StatisticalEngine] = None,
    ):
        """Initialize A/B test analytics.

        Args:
            test_manager: A/B test manager instance
            statistical_engine: Statistical engine instance
        """
        self.test_manager = test_manager or ab_test_manager
        self.statistical_engine = statistical_engine or statistical_engine
        self.logger = get_logger(f"{__name__}.ABTestAnalytics")

    def generate_test_report(self, test_id: str) -> dict[str, Any]:
        """Generate comprehensive test performance report.

        Args:
            test_id: Test identifier

        Returns:
            Comprehensive test report
        """
        # Get test results
        test_results = self.test_manager.get_test_results(test_id)
        test_config = test_results["test_config"]

        # Calculate statistical significance
        variant_data = []
        for variant_id, results in test_results["variant_results"].items():
            # Get primary conversion metric
            primary_conversions = 0
            if test_config.test_type == TestType.EMAIL_SUBJECT:
                primary_conversions = (
                    results["conversions"].get("email_opened", {}).get("count", 0)
                )
            elif test_config.test_type == TestType.PRICING:
                primary_conversions = (
                    results["conversions"].get("pricing_purchase", {}).get("count", 0)
                )
            else:
                # Default to first conversion type
                conv_types = list(results["conversions"].keys())
                if conv_types:
                    primary_conversions = results["conversions"][conv_types[0]].get(
                        "count", 0
                    )

            variant_data.append(
                {
                    "variant_id": variant_id,
                    "conversions": primary_conversions,
                    "samples": results["assignments"],
                }
            )

        # Perform statistical analysis
        statistical_result = None
        if len(variant_data) >= 2 and any(v["samples"] > 0 for v in variant_data):
            statistical_result = self.statistical_engine.test_proportions(variant_data)

        # Generate performance metrics
        performance_metrics = []
        for variant_data_item in variant_data:
            variant_id = variant_data_item["variant_id"]
            results = test_results["variant_results"][variant_id]

            # Calculate revenue
            revenue = 0
            for _conv_type, conv_data in results["conversions"].items():
                revenue += conv_data.get("total_value", 0)

            # Calculate conversion rate
            conversion_rate = (
                variant_data_item["conversions"] / variant_data_item["samples"]
                if variant_data_item["samples"] > 0
                else 0
            )

            # Revenue per visitor
            revenue_per_visitor = (
                revenue / variant_data_item["samples"]
                if variant_data_item["samples"] > 0
                else 0
            )

            # Confidence interval (simplified)
            ci_margin = (
                1.96
                * (
                    conversion_rate
                    * (1 - conversion_rate)
                    / variant_data_item["samples"]
                )
                ** 0.5
            )
            confidence_interval = (
                max(0, conversion_rate - ci_margin),
                min(1, conversion_rate + ci_margin),
            )

            # Is winner
            is_winner = statistical_result and statistical_result.winner == variant_id

            metric = TestPerformanceMetric(
                variant_id=variant_id,
                impressions=variant_data_item["samples"],
                conversions=variant_data_item["conversions"],
                conversion_rate=conversion_rate,
                revenue=revenue,
                revenue_per_visitor=revenue_per_visitor,
                confidence_interval=confidence_interval,
                is_winner=is_winner,
                significance_level=(
                    statistical_result.p_value if statistical_result else 1.0
                ),
            )
            performance_metrics.append(metric)

        # Generate insights
        insights = self._generate_insights(
            test_id, performance_metrics, statistical_result
        )

        # Calculate test health metrics
        health_metrics = self._calculate_test_health(
            test_config, test_results, statistical_result
        )

        return {
            "test_id": test_id,
            "test_name": test_config.name,
            "test_type": test_config.test_type.value,
            "status": test_config.status.value,
            "start_date": test_config.start_date,
            "end_date": test_config.end_date,
            "runtime_days": (
                (datetime.utcnow() - test_config.start_date).days
                if test_config.start_date
                else 0
            ),
            "total_participants": test_results["total_assignments"],
            "performance_metrics": [
                {
                    "variant_id": m.variant_id,
                    "impressions": m.impressions,
                    "conversions": m.conversions,
                    "conversion_rate": m.conversion_rate,
                    "revenue": m.revenue,
                    "revenue_per_visitor": m.revenue_per_visitor,
                    "confidence_interval": m.confidence_interval,
                    "is_winner": m.is_winner,
                    "significance_level": m.significance_level,
                }
                for m in performance_metrics
            ],
            "statistical_result": {
                "test_type": (
                    statistical_result.test_type.value if statistical_result else None
                ),
                "p_value": statistical_result.p_value if statistical_result else None,
                "is_significant": (
                    statistical_result.is_significant if statistical_result else False
                ),
                "effect_size": (
                    statistical_result.effect_size if statistical_result else 0
                ),
                "power": statistical_result.power if statistical_result else 0,
                "winner": statistical_result.winner if statistical_result else None,
            },
            "health_metrics": health_metrics,
            "insights": [
                {
                    "type": i.insight_type,
                    "title": i.title,
                    "description": i.description,
                    "confidence": i.confidence,
                    "actionable": i.actionable,
                    "recommendation": i.recommendation,
                    "impact_estimate": i.impact_estimate,
                }
                for i in insights
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _generate_insights(
        self,
        test_id: str,
        performance_metrics: list[TestPerformanceMetric],
        statistical_result: Optional[Any],
    ) -> list[TestInsight]:
        """Generate automated insights from test performance."""
        insights = []

        if not performance_metrics:
            return insights

        # Sort by conversion rate
        sorted_metrics = sorted(
            performance_metrics, key=lambda x: x.conversion_rate, reverse=True
        )
        best_variant = sorted_metrics[0]
        worst_variant = sorted_metrics[-1]

        # Significant winner insight
        if (
            statistical_result
            and statistical_result.is_significant
            and statistical_result.winner
        ):
            insights.append(
                TestInsight(
                    test_id=test_id,
                    insight_type="significant_winner",
                    title="Statistically Significant Winner Detected",
                    description=f"Variant {statistical_result.winner} shows significantly better performance with {statistical_result.confidence_level:.1%} confidence.",
                    confidence=statistical_result.confidence_level,
                    actionable=True,
                    recommendation=f"Implement {statistical_result.winner} as the default variant",
                    impact_estimate=statistical_result.effect_size,
                )
            )

        # Large effect size insight
        if statistical_result and abs(statistical_result.effect_size) > 0.2:
            insights.append(
                TestInsight(
                    test_id=test_id,
                    insight_type="large_effect",
                    title="Large Effect Size Detected",
                    description=f"The test shows a {statistical_result.effect_size:.1%} effect size, indicating substantial practical significance.",
                    confidence=0.8,
                    actionable=True,
                    recommendation="Consider early implementation due to large impact",
                    impact_estimate=statistical_result.effect_size,
                )
            )

        # Revenue impact insight
        revenue_diff = (
            best_variant.revenue_per_visitor - worst_variant.revenue_per_visitor
        )
        if revenue_diff > 0.1:  # More than $0.10 difference
            insights.append(
                TestInsight(
                    test_id=test_id,
                    insight_type="revenue_impact",
                    title="Significant Revenue Impact",
                    description=f"Best variant generates ${revenue_diff:.2f} more revenue per visitor than worst variant.",
                    confidence=0.7,
                    actionable=True,
                    recommendation="Focus on revenue-optimized variant",
                    impact_estimate=revenue_diff,
                )
            )

        # Sample size insight
        total_samples = sum(m.impressions for m in performance_metrics)
        if statistical_result and statistical_result.required_sample_size:
            if total_samples < statistical_result.required_sample_size:
                insights.append(
                    TestInsight(
                        test_id=test_id,
                        insight_type="insufficient_sample",
                        title="Insufficient Sample Size",
                        description=f"Test needs {statistical_result.required_sample_size - total_samples} more participants to achieve statistical power.",
                        confidence=0.9,
                        actionable=True,
                        recommendation="Continue test to reach required sample size",
                        impact_estimate=None,
                    )
                )

        # Low conversion rate insight
        avg_conversion_rate = sum(m.conversion_rate for m in performance_metrics) / len(
            performance_metrics
        )
        if avg_conversion_rate < 0.01:  # Less than 1%
            insights.append(
                TestInsight(
                    test_id=test_id,
                    insight_type="low_conversion",
                    title="Low Overall Conversion Rate",
                    description=f"Average conversion rate is {avg_conversion_rate:.2%}, which may indicate fundamental issues.",
                    confidence=0.6,
                    actionable=True,
                    recommendation="Review test setup and conversion tracking",
                    impact_estimate=None,
                )
            )

        return insights

    def _calculate_test_health(
        self,
        test_config: Any,
        test_results: dict[str, Any],
        statistical_result: Optional[Any],
    ) -> dict[str, Any]:
        """Calculate test health metrics."""
        total_assignments = test_results["total_assignments"]
        target_sample_size = test_config.target_sample_size

        # Progress towards target
        progress = (
            min(1.0, total_assignments / target_sample_size)
            if target_sample_size > 0
            else 0
        )

        # Statistical power
        power = statistical_result.power if statistical_result else 0

        # Test balance (how evenly distributed are assignments)
        variant_assignments = [
            v["assignments"] for v in test_results["variant_results"].values()
        ]
        if variant_assignments:
            max_assignments = max(variant_assignments)
            min_assignments = min(variant_assignments)
            balance = min_assignments / max_assignments if max_assignments > 0 else 0
        else:
            balance = 0

        # Test velocity (assignments per day)
        runtime_days = (
            (datetime.utcnow() - test_config.start_date).days
            if test_config.start_date
            else 1
        )
        velocity = total_assignments / max(1, runtime_days)

        # Overall health score
        health_score = (
            progress * 0.3 + power * 0.3 + balance * 0.2 + min(1.0, velocity / 10) * 0.2
        )

        return {
            "overall_score": health_score,
            "progress_to_target": progress,
            "statistical_power": power,
            "assignment_balance": balance,
            "daily_velocity": velocity,
            "total_assignments": total_assignments,
            "target_sample_size": target_sample_size,
            "runtime_days": runtime_days,
        }

    def get_portfolio_overview(
        self, test_type: Optional[TestType] = None
    ) -> dict[str, Any]:
        """Get overview of all A/B tests in portfolio.

        Args:
            test_type: Filter by test type (optional)

        Returns:
            Portfolio overview with summary statistics
        """
        active_tests = self.test_manager.get_active_tests(test_type)

        # Generate reports for all active tests
        test_reports = []
        for test in active_tests:
            try:
                report = self.generate_test_report(test.id)
                test_reports.append(report)
            except Exception as e:
                self.logger.error(f"Failed to generate report for test {test.id}: {e}")

        # Calculate portfolio metrics
        total_participants = sum(r["total_participants"] for r in test_reports)
        significant_tests = sum(
            1 for r in test_reports if r["statistical_result"]["is_significant"]
        )

        # Average health score
        avg_health_score = (
            sum(r["health_metrics"]["overall_score"] for r in test_reports)
            / len(test_reports)
            if test_reports
            else 0
        )

        # Test type distribution
        test_type_distribution = {}
        for report in test_reports:
            test_type = report["test_type"]
            test_type_distribution[test_type] = (
                test_type_distribution.get(test_type, 0) + 1
            )

        # Insights summary
        all_insights = []
        for report in test_reports:
            all_insights.extend(report["insights"])

        actionable_insights = [i for i in all_insights if i["actionable"]]

        return {
            "summary": {
                "total_active_tests": len(test_reports),
                "total_participants": total_participants,
                "significant_tests": significant_tests,
                "significance_rate": (
                    significant_tests / len(test_reports) if test_reports else 0
                ),
                "avg_health_score": avg_health_score,
                "actionable_insights": len(actionable_insights),
            },
            "test_type_distribution": test_type_distribution,
            "test_reports": test_reports,
            "insights": {
                "total": len(all_insights),
                "actionable": len(actionable_insights),
                "by_type": self._group_insights_by_type(all_insights),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _group_insights_by_type(self, insights: list[dict[str, Any]]) -> dict[str, int]:
        """Group insights by type for summary."""
        grouped = {}
        for insight in insights:
            insight_type = insight["type"]
            grouped[insight_type] = grouped.get(insight_type, 0) + 1
        return grouped

    def export_test_data(self, test_id: str, format_type: str = "json") -> str:
        """Export test data in specified format.

        Args:
            test_id: Test identifier
            format_type: Export format (json, csv)

        Returns:
            Exported data as string
        """
        report = self.generate_test_report(test_id)

        if format_type.lower() == "json":
            return json.dumps(report, indent=2, default=str)
        elif format_type.lower() == "csv":
            return self._convert_to_csv(report)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _convert_to_csv(self, report: dict[str, Any]) -> str:
        """Convert test report to CSV format."""
        lines = []

        # Header
        lines.append(
            "variant_id,impressions,conversions,conversion_rate,revenue,revenue_per_visitor,is_winner"
        )

        # Data rows
        for metric in report["performance_metrics"]:
            lines.append(
                f"{metric['variant_id']},{metric['impressions']},{metric['conversions']},"
                f"{metric['conversion_rate']:.4f},{metric['revenue']:.2f},"
                f"{metric['revenue_per_visitor']:.4f},{metric['is_winner']}"
            )

        return "\n".join(lines)

    def get_historical_trends(
        self,
        period: ReportPeriod = ReportPeriod.WEEKLY,
        test_type: Optional[TestType] = None,
        days_back: int = 90,
    ) -> dict[str, Any]:
        """Get historical trends for A/B testing performance.

        Args:
            period: Reporting period
            test_type: Filter by test type
            days_back: Number of days to look back

        Returns:
            Historical trend data
        """
        # This would require storing historical snapshots
        # For now, return a simplified structure

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Get all tests from the period
        active_tests = self.test_manager.get_active_tests(test_type)

        # Generate trend data (simplified)
        trend_data = []
        current_date = start_date

        while current_date <= end_date:
            # Calculate metrics for this period
            period_metrics = {
                "date": current_date.isoformat(),
                "active_tests": len(active_tests),
                "total_participants": 0,
                "conversion_rate": 0.05,  # Placeholder
                "significance_rate": 0.2,  # Placeholder
            }

            trend_data.append(period_metrics)

            # Move to next period
            if period == ReportPeriod.DAILY:
                current_date += timedelta(days=1)
            elif period == ReportPeriod.WEEKLY:
                current_date += timedelta(weeks=1)
            elif period == ReportPeriod.MONTHLY:
                current_date += timedelta(days=30)

        return {
            "period": period.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trend_data": trend_data,
            "summary": {
                "avg_active_tests": sum(t["active_tests"] for t in trend_data)
                / len(trend_data),
                "total_participants": sum(t["total_participants"] for t in trend_data),
                "avg_conversion_rate": sum(t["conversion_rate"] for t in trend_data)
                / len(trend_data),
                "avg_significance_rate": sum(t["significance_rate"] for t in trend_data)
                / len(trend_data),
            },
        }


# Global instance
ab_test_analytics = ABTestAnalytics()
