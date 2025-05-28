"""
Main scoring engine for LeadFactory.

This module provides the main interface for scoring businesses using YAML-defined rules.
"""

from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import LogContext, get_logger, log_execution_time
from leadfactory.utils.metrics import (
    LEADS_SCORED,
    MetricsTimer,
    record_metric,
)

from .rule_evaluator import RuleEvaluator
from .yaml_parser import ScoringRulesParser

logger = get_logger(__name__)


class ScoringEngine:
    """Main scoring engine that orchestrates the scoring process."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the scoring engine.

        Args:
            config_path: Path to YAML configuration file.
                        If not provided, uses default path.
        """
        self.logger = get_logger(__name__ + ".ScoringEngine")
        self.parser = ScoringRulesParser(config_path)
        self.evaluator = RuleEvaluator()
        self.config = None
        self.rules = []
        self.multipliers = []
        self.settings = None

        self.logger.info("Initialized ScoringEngine")

    def load_rules(self) -> None:
        """Load and validate scoring rules from YAML."""
        self.logger.info("Loading scoring rules...")

        try:
            self.config = self.parser.load_and_validate()
            self.rules = self.parser.get_enabled_rules()
            self.multipliers = self.parser.get_enabled_multipliers()
            self.settings = self.parser.get_settings()

            self.logger.info(
                f"Loaded {len(self.rules)} rules and "
                f"{len(self.multipliers)} multipliers"
            )
        except Exception as e:
            self.logger.error(f"Failed to load scoring rules: {e}")
            raise

    @log_execution_time
    def score_business(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single business based on loaded rules.

        Args:
            business: Business data dictionary.

        Returns:
            Dictionary containing:
                - score: Final calculated score
                - base_score: Starting score
                - adjustments: List of applied adjustments
                - multipliers: List of applied multipliers
                - final_multiplier: Combined multiplier value
                - details: Detailed scoring breakdown
        """
        if not self.rules:
            raise RuntimeError("No rules loaded. Call load_rules() first.")

        business_id = business.get("id", "unknown")
        business_name = business.get("name", "unknown")

        with LogContext(
            self.logger, business_id=business_id, business_name=business_name
        ):
            with MetricsTimer("scoring.score_business"):
                result = self._calculate_score(business)

                # Record metrics
                record_metric(LEADS_SCORED, 1)

                self.logger.info(
                    f"Scored business {business_name}: {result['score']} points",
                    extra={
                        "score": result["score"],
                        "adjustments": len(result["adjustments"]),
                        "multiplier": result["final_multiplier"],
                    },
                )

                return result

    def score_businesses(
        self, businesses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Score multiple businesses.

        Args:
            businesses: List of business data dictionaries.

        Returns:
            List of scoring results.
        """
        if not self.rules:
            raise RuntimeError("No rules loaded. Call load_rules() first.")

        self.logger.info(f"Scoring {len(businesses)} businesses...")

        results = []
        with MetricsTimer("scoring.score_businesses"):
            for business in businesses:
                try:
                    result = self.score_business(business)
                    results.append(
                        {
                            "business_id": business.get("id"),
                            "business_name": business.get("name"),
                            **result,
                        }
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error scoring business {business.get('name', 'unknown')}: {e}"
                    )
                    results.append(
                        {
                            "business_id": business.get("id"),
                            "business_name": business.get("name"),
                            "error": str(e),
                            "score": 0,
                        }
                    )

        return results

    def _calculate_score(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate the score for a business.

        Args:
            business: Business data dictionary.

        Returns:
            Detailed scoring result.
        """
        # Start with base score
        base_score = self.settings.base_score
        score = base_score
        adjustments = []
        applied_multipliers = []

        # Apply rules
        for rule in self.rules:
            matched, adjustment = self.evaluator.evaluate_rule(business, rule)
            if matched:
                score += adjustment
                adjustments.append(
                    {
                        "rule": rule.name,
                        "description": rule.description,
                        "adjustment": adjustment,
                        "score_after": score,
                    }
                )

        # Apply multipliers
        final_multiplier = 1.0
        for multiplier in self.multipliers:
            mult_value = self.evaluator.evaluate_multiplier(business, multiplier)
            if mult_value != 1.0:
                final_multiplier *= mult_value
                applied_multipliers.append(
                    {
                        "multiplier": multiplier.name,
                        "description": multiplier.description,
                        "value": mult_value,
                    }
                )

        # Apply final multiplier
        if final_multiplier != 1.0:
            score = int(score * final_multiplier)

        # Ensure score is within bounds
        score = max(self.settings.min_score, min(score, self.settings.max_score))

        return {
            "score": score,
            "base_score": base_score,
            "adjustments": adjustments,
            "multipliers": applied_multipliers,
            "final_multiplier": final_multiplier,
            "is_high_score": score >= self.settings.high_score_threshold,
            "details": {
                "rules_evaluated": len(self.rules),
                "rules_matched": len(adjustments),
                "multipliers_applied": len(applied_multipliers),
                "total_adjustment": sum(adj["adjustment"] for adj in adjustments),
            },
        }

    def get_rule_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about loaded rules.

        Returns:
            Dictionary with rule statistics.
        """
        if not self.rules:
            return {
                "error": "No rules loaded",
                "total_rules": 0,
                "total_multipliers": 0,
            }

        positive_rules = [r for r in self.rules if r.score > 0]
        negative_rules = [r for r in self.rules if r.score < 0]

        return {
            "total_rules": len(self.rules),
            "enabled_rules": len(self.rules),
            "positive_rules": len(positive_rules),
            "negative_rules": len(negative_rules),
            "neutral_rules": len(self.rules)
            - len(positive_rules)
            - len(negative_rules),
            "total_multipliers": len(self.multipliers),
            "settings": {
                "base_score": self.settings.base_score,
                "min_score": self.settings.min_score,
                "max_score": self.settings.max_score,
                "high_score_threshold": self.settings.high_score_threshold,
            },
        }

    def validate_business_data(
        self, business: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that business data has required fields for scoring.

        Args:
            business: Business data dictionary.

        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        issues = []

        # Check for required fields
        if not business.get("id"):
            issues.append("Missing business ID")

        if not business.get("name"):
            issues.append("Missing business name")

        # Warn about potentially missing fields (not errors)
        warnings = []
        optional_fields = [
            "tech_stack",
            "vertical",
            "location",
            "employee_count",
            "revenue",
            "founded_year",
            "social_media",
            "website",
        ]

        for field in optional_fields:
            if field not in business:
                warnings.append(f"Missing optional field: {field}")

        if warnings:
            self.logger.debug(
                f"Business {business.get('name', 'unknown')} missing optional fields: "
                f"{', '.join(warnings)}"
            )

        return len(issues) == 0, issues
