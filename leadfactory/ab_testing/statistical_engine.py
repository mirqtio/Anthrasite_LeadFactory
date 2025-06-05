"""
Statistical Engine for A/B Testing - Statistical significance and power analysis.

This module provides statistical methods for determining test significance,
calculating required sample sizes, and performing Bayesian analysis.
"""

import json
import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger


class StatisticalTest(Enum):
    """Statistical test types."""

    PROPORTIONS_Z_TEST = "proportions_z_test"
    WELCH_T_TEST = "welch_t_test"
    CHI_SQUARE = "chi_square"
    BAYESIAN = "bayesian"


@dataclass
class StatisticalResult:
    """Result of statistical analysis."""

    test_type: StatisticalTest
    p_value: float
    confidence_level: float
    is_significant: bool
    effect_size: float
    power: float
    required_sample_size: Optional[int]
    winner: Optional[str]
    metadata: dict


class StatisticalEngine:
    """Statistical analysis engine for A/B tests."""

    def __init__(self):
        """Initialize statistical engine."""
        self.logger = get_logger(f"{__name__}.StatisticalEngine")

    def calculate_sample_size(
        self,
        baseline_rate: float,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.8,
        two_tailed: bool = True,
    ) -> int:
        """Calculate required sample size for detecting effect.

        Args:
            baseline_rate: Expected baseline conversion rate
            minimum_detectable_effect: Minimum effect size to detect
            alpha: Type I error rate (significance level)
            power: Statistical power (1 - Type II error rate)
            two_tailed: Whether to use two-tailed test

        Returns:
            Required sample size per variant
        """
        # Z-scores for alpha and power
        z_alpha = self._get_z_score(alpha / (2 if two_tailed else 1))
        z_beta = self._get_z_score(1 - power)

        # Effect size in terms of conversion rate
        p1 = baseline_rate
        p2 = baseline_rate * (1 + minimum_detectable_effect)

        # Pooled variance for proportions
        p_pooled = (p1 + p2) / 2
        variance_pooled = p_pooled * (1 - p_pooled)

        # Individual variances
        variance1 = p1 * (1 - p1)
        variance2 = p2 * (1 - p2)

        # Sample size calculation
        numerator = (
            z_alpha * math.sqrt(2 * variance_pooled)
            + z_beta * math.sqrt(variance1 + variance2)
        ) ** 2
        denominator = (p2 - p1) ** 2

        sample_size = math.ceil(numerator / denominator)

        self.logger.info(f"Calculated sample size: {sample_size} per variant")
        return sample_size

    def _get_z_score(self, p: float) -> float:
        """Get Z-score for given probability using approximation."""
        if p <= 0 or p >= 1:
            raise ValueError("Probability must be between 0 and 1")

        # Standard normal quantile approximation (Beasley-Springer-Moro)
        # Simplified version for common significance levels
        z_scores = {
            0.001: 3.09,
            0.005: 2.58,
            0.01: 2.33,
            0.025: 1.96,
            0.05: 1.64,
            0.1: 1.28,
            0.2: 0.84,
            0.5: 0.0,
            0.8: -0.84,
            0.9: -1.28,
            0.95: -1.64,
            0.975: -1.96,
            0.99: -2.33,
            0.995: -2.58,
            0.999: -3.09,
        }

        # Find closest match
        closest_p = min(z_scores.keys(), key=lambda x: abs(x - p))
        return z_scores[closest_p]

    def test_proportions(
        self, variant_data: list[dict[str, int]], alpha: float = 0.05
    ) -> StatisticalResult:
        """Perform statistical test for conversion rate differences.

        Args:
            variant_data: List of variant data with 'conversions' and 'samples'
            alpha: Significance level

        Returns:
            Statistical test result
        """
        if len(variant_data) < 2:
            raise ValueError("Need at least 2 variants for comparison")

        # For now, implement simple two-proportion z-test
        if len(variant_data) == 2:
            return self._two_proportion_z_test(variant_data[0], variant_data[1], alpha)
        else:
            return self._chi_square_test(variant_data, alpha)

    def _two_proportion_z_test(
        self, variant_a: dict[str, int], variant_b: dict[str, int], alpha: float
    ) -> StatisticalResult:
        """Perform two-proportion z-test."""
        # Extract data
        x1, n1 = variant_a["conversions"], variant_a["samples"]
        x2, n2 = variant_b["conversions"], variant_b["samples"]

        # Conversion rates
        p1 = x1 / n1 if n1 > 0 else 0
        p2 = x2 / n2 if n2 > 0 else 0

        # Pooled proportion
        p_pooled = (x1 + x2) / (n1 + n2) if (n1 + n2) > 0 else 0

        # Standard error
        se = (
            math.sqrt(p_pooled * (1 - p_pooled) * (1 / n1 + 1 / n2))
            if p_pooled > 0
            else 0
        )

        # Z-statistic
        z = (p2 - p1) / se if se > 0 else 0

        # P-value (two-tailed)
        p_value = 2 * (1 - self._standard_normal_cdf(abs(z)))

        # Effect size (relative difference)
        effect_size = (p2 - p1) / p1 if p1 > 0 else 0

        # Determine significance
        is_significant = p_value < alpha

        # Winner
        winner = None
        if is_significant:
            winner = "variant_b" if p2 > p1 else "variant_a"

        # Calculate power (simplified)
        power = self._calculate_power(n1, n2, p1, p2, alpha)

        return StatisticalResult(
            test_type=StatisticalTest.PROPORTIONS_Z_TEST,
            p_value=p_value,
            confidence_level=1 - alpha,
            is_significant=is_significant,
            effect_size=effect_size,
            power=power,
            required_sample_size=None,
            winner=winner,
            metadata={
                "z_statistic": z,
                "p1": p1,
                "p2": p2,
                "n1": n1,
                "n2": n2,
                "pooled_proportion": p_pooled,
                "standard_error": se,
            },
        )

    def _chi_square_test(
        self, variant_data: list[dict[str, int]], alpha: float
    ) -> StatisticalResult:
        """Perform chi-square test for multiple proportions."""
        # Simplified chi-square implementation
        total_conversions = sum(v["conversions"] for v in variant_data)
        total_samples = sum(v["samples"] for v in variant_data)
        overall_rate = total_conversions / total_samples if total_samples > 0 else 0

        # Calculate chi-square statistic
        chi_square = 0
        for variant in variant_data:
            observed = variant["conversions"]
            expected = variant["samples"] * overall_rate
            if expected > 0:
                chi_square += ((observed - expected) ** 2) / expected

        # Degrees of freedom
        df = len(variant_data) - 1

        # P-value approximation (simplified)
        # For df=1, chi-square approaches normal distribution
        if df == 1:
            p_value = 2 * (1 - self._standard_normal_cdf(math.sqrt(chi_square)))
        else:
            # Simplified approximation for higher df
            p_value = 1 - self._chi_square_cdf(chi_square, df)

        is_significant = p_value < alpha

        # Find best variant
        best_variant = max(
            enumerate(variant_data),
            key=lambda x: (
                x[1]["conversions"] / x[1]["samples"] if x[1]["samples"] > 0 else 0
            ),
        )

        winner = f"variant_{best_variant[0]}" if is_significant else None

        # Effect size (Cramer's V)
        effect_size = math.sqrt(chi_square / total_samples) if total_samples > 0 else 0

        return StatisticalResult(
            test_type=StatisticalTest.CHI_SQUARE,
            p_value=p_value,
            confidence_level=1 - alpha,
            is_significant=is_significant,
            effect_size=effect_size,
            power=0.8,  # Simplified
            required_sample_size=None,
            winner=winner,
            metadata={
                "chi_square_statistic": chi_square,
                "degrees_of_freedom": df,
                "overall_rate": overall_rate,
                "variant_rates": [
                    v["conversions"] / v["samples"] if v["samples"] > 0 else 0
                    for v in variant_data
                ],
            },
        )

    def _standard_normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        # Approximation using error function
        return 0.5 * (1 + self._erf(x / math.sqrt(2)))

    def _erf(self, x: float) -> float:
        """Approximate error function."""
        # Abramowitz and Stegun approximation
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(
            -x * x
        )

        return sign * y

    def _chi_square_cdf(self, x: float, df: int) -> float:
        """Simplified chi-square CDF approximation."""
        if df == 1:
            return 2 * self._standard_normal_cdf(math.sqrt(x)) - 1
        elif df == 2:
            return 1 - math.exp(-x / 2)
        else:
            # Very rough approximation for higher df
            return min(1.0, x / (df * 2))

    def _calculate_power(
        self, n1: int, n2: int, p1: float, p2: float, alpha: float
    ) -> float:
        """Calculate statistical power for two-proportion test."""
        if p1 == p2 or n1 == 0 or n2 == 0:
            return 0.0

        # Critical value
        z_alpha = self._get_z_score(alpha / 2)

        # Standard errors
        se_null = math.sqrt(((p1 + p2) / 2) * (1 - (p1 + p2) / 2) * (1 / n1 + 1 / n2))
        se_alt = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)

        if se_null == 0 or se_alt == 0:
            return 0.0

        # Power calculation
        z_beta = (abs(p2 - p1) - z_alpha * se_null) / se_alt
        power = self._standard_normal_cdf(z_beta)

        return max(0.0, min(1.0, power))

    def bayesian_analysis(
        self,
        variant_data: list[dict[str, int]],
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
    ) -> dict[str, Any]:
        """Perform Bayesian analysis for conversion rates.

        Args:
            variant_data: List of variant data with 'conversions' and 'samples'
            prior_alpha: Prior alpha parameter for Beta distribution
            prior_beta: Prior beta parameter for Beta distribution

        Returns:
            Bayesian analysis results
        """
        results = {}

        for i, variant in enumerate(variant_data):
            conversions = variant["conversions"]
            samples = variant["samples"]

            # Posterior parameters
            posterior_alpha = prior_alpha + conversions
            posterior_beta = prior_beta + samples - conversions

            # Posterior mean and variance
            mean = posterior_alpha / (posterior_alpha + posterior_beta)
            variance = (posterior_alpha * posterior_beta) / (
                (posterior_alpha + posterior_beta) ** 2
                * (posterior_alpha + posterior_beta + 1)
            )

            # Credible intervals (approximation)
            std = math.sqrt(variance)
            lower_ci = max(0, mean - 1.96 * std)
            upper_ci = min(1, mean + 1.96 * std)

            results[f"variant_{i}"] = {
                "posterior_alpha": posterior_alpha,
                "posterior_beta": posterior_beta,
                "mean": mean,
                "variance": variance,
                "credible_interval_95": [lower_ci, upper_ci],
                "probability_of_improvement": 0.5,  # Simplified
            }

        # Calculate probability that each variant is best
        if len(results) == 2:
            variants = list(results.keys())
            mean_a = results[variants[0]]["mean"]
            mean_b = results[variants[1]]["mean"]

            # Simplified calculation
            if mean_a > mean_b:
                results[variants[0]]["probability_best"] = 0.7
                results[variants[1]]["probability_best"] = 0.3
            else:
                results[variants[0]]["probability_best"] = 0.3
                results[variants[1]]["probability_best"] = 0.7

        return results

    def determine_test_conclusion(
        self,
        test_result: StatisticalResult,
        minimum_sample_size: int = 100,
        minimum_runtime_days: int = 7,
    ) -> dict[str, Any]:
        """Determine overall test conclusion and recommendations.

        Args:
            test_result: Statistical test result
            minimum_sample_size: Minimum sample size per variant
            minimum_runtime_days: Minimum test runtime in days

        Returns:
            Test conclusion and recommendations
        """
        conclusion = {
            "status": "incomplete",
            "recommendation": "continue_testing",
            "confidence": "low",
            "action_items": [],
        }

        # Check statistical significance
        if test_result.is_significant:
            conclusion["status"] = "significant"
            conclusion["confidence"] = (
                "high" if test_result.p_value < 0.01 else "medium"
            )

            if test_result.winner:
                conclusion["recommendation"] = "implement_winner"
                conclusion["winner"] = test_result.winner
                conclusion["action_items"].append(
                    f"Implement {test_result.winner} as default"
                )

        else:
            # Check if test has sufficient power
            if test_result.power < 0.8:
                conclusion["recommendation"] = "increase_sample_size"
                conclusion["action_items"].append(
                    "Increase sample size to achieve 80% power"
                )

            # Check effect size
            if abs(test_result.effect_size) < 0.05:  # Less than 5% effect
                conclusion["recommendation"] = "no_meaningful_difference"
                conclusion["action_items"].append("No meaningful difference detected")

        # Add sample size recommendations
        if test_result.required_sample_size:
            conclusion["required_sample_size"] = test_result.required_sample_size
            if test_result.required_sample_size > minimum_sample_size:
                conclusion["action_items"].append(
                    f"Collect {test_result.required_sample_size} samples per variant"
                )

        return conclusion


# Global instance
statistical_engine = StatisticalEngine()
