"""
Variant Reporting System for A/B Testing.

This module provides comprehensive reporting and analytics for pipeline variants,
including performance comparisons, statistical significance testing, and insights.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.pipeline.variant_tracking import (
    VariantMetrics,
    VariantTracker,
    get_variant_tracker,
)
from leadfactory.pipeline.variants import PipelineVariant, get_variant_registry
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ReportType(Enum):
    """Types of variant reports."""

    SUMMARY = "summary"
    DETAILED = "detailed"
    COMPARISON = "comparison"
    PERFORMANCE = "performance"
    STATISTICAL = "statistical"
    CUSTOM = "custom"


class SignificanceLevel(Enum):
    """Statistical significance levels."""

    VERY_HIGH = 0.001  # 99.9%
    HIGH = 0.01  # 99%
    MEDIUM = 0.05  # 95%
    LOW = 0.1  # 90%


@dataclass
class StatisticalTest:
    """Results of statistical significance testing."""

    metric_name: str
    variant_a_value: float
    variant_b_value: float
    variant_a_sample_size: int
    variant_b_sample_size: int
    p_value: float
    confidence_level: float
    is_significant: bool
    effect_size: float
    test_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "variant_a_value": self.variant_a_value,
            "variant_b_value": self.variant_b_value,
            "variant_a_sample_size": self.variant_a_sample_size,
            "variant_b_sample_size": self.variant_b_sample_size,
            "p_value": self.p_value,
            "confidence_level": self.confidence_level,
            "is_significant": self.is_significant,
            "effect_size": self.effect_size,
            "test_type": self.test_type,
        }


@dataclass
class VariantComparison:
    """Comparison between two variants."""

    variant_a_id: str
    variant_b_id: str
    variant_a_name: str
    variant_b_name: str
    metrics_a: VariantMetrics
    metrics_b: VariantMetrics
    statistical_tests: List[StatisticalTest] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "variant_a_id": self.variant_a_id,
            "variant_b_id": self.variant_b_id,
            "variant_a_name": self.variant_a_name,
            "variant_b_name": self.variant_b_name,
            "metrics_a": self.metrics_a.to_dict(),
            "metrics_b": self.metrics_b.to_dict(),
            "statistical_tests": [test.to_dict() for test in self.statistical_tests],
            "insights": self.insights,
            "recommendation": self.recommendation,
        }


@dataclass
class VariantReport:
    """Comprehensive variant report."""

    report_id: str
    report_type: ReportType
    title: str
    description: str
    generated_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    variants: List[str] = field(default_factory=list)
    metrics: List[VariantMetrics] = field(default_factory=list)
    comparisons: List[VariantComparison] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "description": self.description,
            "generated_at": self.generated_at,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "variants": self.variants,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "comparisons": [comp.to_dict() for comp in self.comparisons],
            "insights": self.insights,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class StatisticalAnalyzer:
    """Performs statistical analysis on variant data."""

    @staticmethod
    def z_test_proportions(
        p1: float, n1: int, p2: float, n2: int
    ) -> Tuple[float, float]:
        """
        Perform z-test for difference in proportions.
        Returns (z_score, p_value).
        """
        if n1 == 0 or n2 == 0:
            return 0.0, 1.0

        # Pooled proportion
        p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))

        if se == 0:
            return 0.0, 1.0

        # Z-score
        z = (p1 - p2) / se

        # Two-tailed p-value (approximation)
        p_value = 2 * (1 - StatisticalAnalyzer._normal_cdf(abs(z)))

        return z, p_value

    @staticmethod
    def t_test_means(
        mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int
    ) -> Tuple[float, float]:
        """
        Perform Welch's t-test for difference in means.
        Returns (t_score, p_value).
        """
        if n1 <= 1 or n2 <= 1 or std1 == 0 or std2 == 0:
            return 0.0, 1.0

        # Standard error
        se = math.sqrt((std1**2 / n1) + (std2**2 / n2))

        if se == 0:
            return 0.0, 1.0

        # T-score
        t = (mean1 - mean2) / se

        # Degrees of freedom (Welch's formula)
        df = ((std1**2 / n1) + (std2**2 / n2)) ** 2 / (
            (std1**2 / n1) ** 2 / (n1 - 1) + (std2**2 / n2) ** 2 / (n2 - 1)
        )

        # Approximate p-value (simplified)
        p_value = 2 * (1 - StatisticalAnalyzer._t_cdf(abs(t), df))

        return t, p_value

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate normal CDF using error function approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _t_cdf(t: float, df: float) -> float:
        """Approximate t-distribution CDF (simplified)."""
        # For large df, t-distribution approaches normal
        if df > 30:
            return StatisticalAnalyzer._normal_cdf(t)

        # Simplified approximation for small df
        return 0.5 + 0.5 * math.tanh(t / math.sqrt(df / (df - 2)))

    @staticmethod
    def cohens_d(
        mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int
    ) -> float:
        """Calculate Cohen's d effect size."""
        if n1 <= 1 or n2 <= 1:
            return 0.0

        # Pooled standard deviation
        pooled_std = math.sqrt(
            ((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2)
        )

        if pooled_std == 0:
            return 0.0

        return (mean1 - mean2) / pooled_std


class VariantReporter:
    """Generates comprehensive reports for variant analysis."""

    def __init__(self, tracker: Optional[VariantTracker] = None):
        self.tracker = tracker or get_variant_tracker()
        self.analyzer = StatisticalAnalyzer()

    def generate_summary_report(
        self,
        variant_ids: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> VariantReport:
        """Generate a summary report for variants."""

        report_id = f"summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Get metrics for all variants or specified ones
        if variant_ids:
            metrics = [
                self.tracker.get_variant_metrics(vid, start_time, end_time)
                for vid in variant_ids
            ]
        else:
            metrics = self.tracker.get_all_variant_metrics(start_time, end_time)

        # Generate insights
        insights = self._generate_summary_insights(metrics)

        # Generate recommendations
        recommendations = self._generate_summary_recommendations(metrics)

        report = VariantReport(
            report_id=report_id,
            report_type=ReportType.SUMMARY,
            title="Variant Performance Summary",
            description="Overview of all variant performance metrics",
            generated_at=datetime.utcnow().isoformat(),
            time_range_start=start_time,
            time_range_end=end_time,
            variants=[m.variant_id for m in metrics],
            metrics=metrics,
            insights=insights,
            recommendations=recommendations,
        )

        return report

    def generate_comparison_report(
        self,
        variant_a_id: str,
        variant_b_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        significance_level: SignificanceLevel = SignificanceLevel.MEDIUM,
    ) -> VariantReport:
        """Generate a detailed comparison report between two variants."""

        report_id = f"comparison_{variant_a_id[:8]}_{variant_b_id[:8]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Get metrics for both variants
        metrics_a = self.tracker.get_variant_metrics(variant_a_id, start_time, end_time)
        metrics_b = self.tracker.get_variant_metrics(variant_b_id, start_time, end_time)

        # Get variant names
        registry = get_variant_registry()
        variant_a = registry.get_variant(variant_a_id)
        variant_b = registry.get_variant(variant_b_id)

        variant_a_name = variant_a.name if variant_a else variant_a_id
        variant_b_name = variant_b.name if variant_b else variant_b_id

        # Perform statistical tests
        statistical_tests = self._perform_statistical_tests(
            metrics_a, metrics_b, significance_level
        )

        # Generate comparison insights
        insights = self._generate_comparison_insights(
            metrics_a, metrics_b, statistical_tests
        )

        # Generate recommendation
        recommendation = self._generate_comparison_recommendation(
            metrics_a, metrics_b, statistical_tests
        )

        comparison = VariantComparison(
            variant_a_id=variant_a_id,
            variant_b_id=variant_b_id,
            variant_a_name=variant_a_name,
            variant_b_name=variant_b_name,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            statistical_tests=statistical_tests,
            insights=insights,
            recommendation=recommendation,
        )

        report = VariantReport(
            report_id=report_id,
            report_type=ReportType.COMPARISON,
            title=f"Variant Comparison: {variant_a_name} vs {variant_b_name}",
            description=f"Detailed comparison between {variant_a_name} and {variant_b_name}",
            generated_at=datetime.utcnow().isoformat(),
            time_range_start=start_time,
            time_range_end=end_time,
            variants=[variant_a_id, variant_b_id],
            metrics=[metrics_a, metrics_b],
            comparisons=[comparison],
            insights=insights,
            recommendations=[recommendation] if recommendation else [],
        )

        return report

    def _perform_statistical_tests(
        self,
        metrics_a: VariantMetrics,
        metrics_b: VariantMetrics,
        significance_level: SignificanceLevel,
    ) -> List[StatisticalTest]:
        """Perform statistical significance tests."""
        tests = []

        # Test conversion rate
        if metrics_a.emails_delivered > 0 and metrics_b.emails_delivered > 0:
            z_score, p_value = self.analyzer.z_test_proportions(
                metrics_a.conversion_rate,
                metrics_a.emails_delivered,
                metrics_b.conversion_rate,
                metrics_b.emails_delivered,
            )

            effect_size = abs(metrics_a.conversion_rate - metrics_b.conversion_rate)

            tests.append(
                StatisticalTest(
                    metric_name="conversion_rate",
                    variant_a_value=metrics_a.conversion_rate,
                    variant_b_value=metrics_b.conversion_rate,
                    variant_a_sample_size=metrics_a.emails_delivered,
                    variant_b_sample_size=metrics_b.emails_delivered,
                    p_value=p_value,
                    confidence_level=1 - significance_level.value,
                    is_significant=p_value < significance_level.value,
                    effect_size=effect_size,
                    test_type="z_test_proportions",
                )
            )

        # Test email open rate
        if metrics_a.emails_delivered > 0 and metrics_b.emails_delivered > 0:
            z_score, p_value = self.analyzer.z_test_proportions(
                metrics_a.email_open_rate,
                metrics_a.emails_delivered,
                metrics_b.email_open_rate,
                metrics_b.emails_delivered,
            )

            effect_size = abs(metrics_a.email_open_rate - metrics_b.email_open_rate)

            tests.append(
                StatisticalTest(
                    metric_name="email_open_rate",
                    variant_a_value=metrics_a.email_open_rate,
                    variant_b_value=metrics_b.email_open_rate,
                    variant_a_sample_size=metrics_a.emails_delivered,
                    variant_b_sample_size=metrics_b.emails_delivered,
                    p_value=p_value,
                    confidence_level=1 - significance_level.value,
                    is_significant=p_value < significance_level.value,
                    effect_size=effect_size,
                    test_type="z_test_proportions",
                )
            )

        # Test email click rate
        if metrics_a.emails_delivered > 0 and metrics_b.emails_delivered > 0:
            z_score, p_value = self.analyzer.z_test_proportions(
                metrics_a.email_click_rate,
                metrics_a.emails_delivered,
                metrics_b.email_click_rate,
                metrics_b.emails_delivered,
            )

            effect_size = abs(metrics_a.email_click_rate - metrics_b.email_click_rate)

            tests.append(
                StatisticalTest(
                    metric_name="email_click_rate",
                    variant_a_value=metrics_a.email_click_rate,
                    variant_b_value=metrics_b.email_click_rate,
                    variant_a_sample_size=metrics_a.emails_delivered,
                    variant_b_sample_size=metrics_b.emails_delivered,
                    p_value=p_value,
                    confidence_level=1 - significance_level.value,
                    is_significant=p_value < significance_level.value,
                    effect_size=effect_size,
                    test_type="z_test_proportions",
                )
            )

        return tests

    def _generate_summary_insights(self, metrics: List[VariantMetrics]) -> List[str]:
        """Generate insights from summary metrics."""
        insights = []

        if not metrics:
            insights.append("No variant data available for analysis.")
            return insights

        # Find best performing variants
        if len(metrics) > 1:
            best_conversion = max(metrics, key=lambda m: m.conversion_rate)
            best_open_rate = max(metrics, key=lambda m: m.email_open_rate)
            lowest_cost = min(
                metrics,
                key=lambda m: (
                    m.cost_per_conversion if m.cost_per_conversion > 0 else float("inf")
                ),
            )

            insights.append(
                f"Highest conversion rate: {best_conversion.variant_name} ({best_conversion.conversion_rate:.2%})"
            )
            insights.append(
                f"Highest email open rate: {best_open_rate.variant_name} ({best_open_rate.email_open_rate:.2%})"
            )

            if lowest_cost.cost_per_conversion > 0:
                insights.append(
                    f"Lowest cost per conversion: {lowest_cost.variant_name} (${lowest_cost.cost_per_conversion/100:.2f})"
                )

        # Overall performance insights
        total_assignments = sum(m.total_assignments for m in metrics)
        total_conversions = sum(m.conversions for m in metrics)
        avg_conversion_rate = (
            total_conversions
            / sum(m.emails_delivered for m in metrics if m.emails_delivered > 0)
            if any(m.emails_delivered > 0 for m in metrics)
            else 0
        )

        insights.append(f"Total variant assignments: {total_assignments}")
        insights.append(f"Overall conversion rate: {avg_conversion_rate:.2%}")

        return insights

    def _generate_summary_recommendations(
        self, metrics: List[VariantMetrics]
    ) -> List[str]:
        """Generate recommendations from summary metrics."""
        recommendations = []

        if not metrics:
            return recommendations

        if len(metrics) > 1:
            # Find underperforming variants
            avg_conversion = mean(
                [m.conversion_rate for m in metrics if m.emails_delivered > 0]
            )
            underperforming = [
                m
                for m in metrics
                if m.conversion_rate < avg_conversion * 0.8 and m.emails_delivered > 10
            ]

            if underperforming:
                recommendations.append(
                    f"Consider pausing underperforming variants: {', '.join([m.variant_name for m in underperforming])}"
                )

            # Find variants with insufficient data
            low_sample = [m for m in metrics if m.emails_delivered < 100]
            if low_sample:
                recommendations.append(
                    f"Increase traffic allocation for variants with low sample sizes: {', '.join([m.variant_name for m in low_sample])}"
                )

        return recommendations

    def _generate_comparison_insights(
        self,
        metrics_a: VariantMetrics,
        metrics_b: VariantMetrics,
        tests: List[StatisticalTest],
    ) -> List[str]:
        """Generate insights from variant comparison."""
        insights = []

        # Performance differences
        conv_diff = (metrics_b.conversion_rate - metrics_a.conversion_rate) * 100
        open_diff = (metrics_b.email_open_rate - metrics_a.email_open_rate) * 100
        click_diff = (metrics_b.email_click_rate - metrics_a.email_click_rate) * 100

        insights.append(
            f"Conversion rate difference: {conv_diff:+.2f} percentage points"
        )
        insights.append(
            f"Email open rate difference: {open_diff:+.2f} percentage points"
        )
        insights.append(
            f"Email click rate difference: {click_diff:+.2f} percentage points"
        )

        # Statistical significance
        significant_tests = [t for t in tests if t.is_significant]
        if significant_tests:
            insights.append(
                f"Statistically significant differences found in: {', '.join([t.metric_name for t in significant_tests])}"
            )
        else:
            insights.append("No statistically significant differences found")

        # Sample size adequacy
        min_sample_size = 100  # Minimum for meaningful analysis
        if (
            metrics_a.emails_delivered < min_sample_size
            or metrics_b.emails_delivered < min_sample_size
        ):
            insights.append(
                "Sample sizes may be too small for reliable statistical analysis"
            )

        return insights

    def _generate_comparison_recommendation(
        self,
        metrics_a: VariantMetrics,
        metrics_b: VariantMetrics,
        tests: List[StatisticalTest],
    ) -> Optional[str]:
        """Generate recommendation from variant comparison."""

        # Check for statistically significant improvements
        significant_improvements = [
            t
            for t in tests
            if t.is_significant and t.variant_b_value > t.variant_a_value
        ]

        if significant_improvements:
            if any(
                t.metric_name == "conversion_rate" for t in significant_improvements
            ):
                return f"Recommend switching to {metrics_b.variant_name} due to significantly higher conversion rate"
            else:
                return f"Recommend considering {metrics_b.variant_name} due to significant improvements in engagement metrics"

        # Check for practical significance even without statistical significance
        conv_improvement = (
            (metrics_b.conversion_rate - metrics_a.conversion_rate)
            / metrics_a.conversion_rate
            if metrics_a.conversion_rate > 0
            else 0
        )

        if conv_improvement > 0.1:  # 10% improvement
            return f"Consider testing {metrics_b.variant_name} further - shows {conv_improvement:.1%} conversion improvement"

        if conv_improvement < -0.1:  # 10% decline
            return f"Recommend pausing {metrics_b.variant_name} - shows {abs(conv_improvement):.1%} conversion decline"

        return "Continue testing both variants - no clear winner yet"


def generate_variant_report(report_type: ReportType, **kwargs) -> VariantReport:
    """Factory function to generate variant reports."""
    reporter = VariantReporter()

    if report_type == ReportType.SUMMARY:
        return reporter.generate_summary_report(**kwargs)
    elif report_type == ReportType.COMPARISON:
        return reporter.generate_comparison_report(**kwargs)
    else:
        raise ValueError(f"Unsupported report type: {report_type}")


def export_report_to_json(report: VariantReport, file_path: str) -> bool:
    """Export a report to JSON file."""
    try:
        with open(file_path, "w") as f:
            f.write(report.to_json())
        logger.info(f"Report exported to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export report: {e}")
        return False
