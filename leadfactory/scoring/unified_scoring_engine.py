"""
Unified Scoring Engine with Support for Both Legacy and Simplified YAML Formats

This module provides a unified scoring engine that automatically detects
and processes both legacy and simplified YAML formats.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import LEADS_SCORED, MetricsTimer, record_metric

from .rule_evaluator import RuleEvaluator
from .simplified_yaml_parser import SimplifiedYamlParser
from .yaml_parser import ScoringRulesParser

logger = get_logger(__name__)


class UnifiedScoringEngine:
    """
    Unified scoring engine that supports both legacy and simplified YAML formats.
    Automatically detects format and uses appropriate parser.
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the unified scoring engine."""
        self.logger = get_logger(__name__ + ".UnifiedScoringEngine")
        self.config_path = config_path
        self.format_type = None  # "legacy" or "simplified"
        self.legacy_parser = None
        self.simplified_parser = None
        self.evaluator = RuleEvaluator()
        self.config = None
        self.rules = []
        self.multipliers = []
        self.settings = None

        self.logger.info("Initialized UnifiedScoringEngine")

    def load_rules(self) -> None:
        """Load and validate scoring rules, auto-detecting format."""
        self.logger.info("Loading scoring rules with format auto-detection...")

        try:
            # Detect format
            self.format_type = self._detect_format()
            self.logger.info(f"Detected format: {self.format_type}")

            if self.format_type == "simplified":
                self._load_simplified_rules()
            else:
                self._load_legacy_rules()

            self.logger.info(
                f"Successfully loaded {len(self.rules)} rules and "
                f"{len(self.multipliers)} multipliers in {self.format_type} format"
            )

        except Exception as e:
            self.logger.error(f"Failed to load scoring rules: {e}")
            raise

    def _detect_format(self) -> str:
        """
        Detect whether the YAML file uses legacy or simplified format.

        Returns:
            "simplified" or "legacy"
        """
        # Try multiple paths if no specific path provided
        potential_paths = []
        if self.config_path:
            potential_paths.append(Path(self.config_path))
        else:
            base_path = Path(__file__).parent / "../../etc"
            potential_paths.extend(
                [
                    base_path / "scoring_rules_simplified.yml",
                    base_path / "scoring_rules.yml",
                ]
            )

        for path in potential_paths:
            if not path.exists():
                continue

            try:
                with path.open() as f:
                    content = yaml.safe_load(f)

                # Check for simplified format indicators
                if self._is_simplified_format(content):
                    self.config_path = str(path)
                    return "simplified"

                # Check for legacy format indicators
                if self._is_legacy_format(content):
                    self.config_path = str(path)
                    return "legacy"

            except Exception as e:
                self.logger.warning(f"Could not parse {path}: {e}")
                continue

        # Default to legacy if no format detected
        if not self.config_path:
            self.config_path = str(
                Path(__file__).parent / "../../etc/scoring_rules.yml"
            )
        return "legacy"

    def _is_simplified_format(self, content: dict[str, Any]) -> bool:
        """Check if content matches simplified format."""
        # Simplified format has these key indicators
        simplified_indicators = [
            "audit_opportunities",
            "templates",
            "audit_multipliers",
            "exclusions",
        ]

        # Check for audit_threshold in settings (specific to simplified)
        if "settings" in content and "audit_threshold" in content["settings"]:
            return True

        # Check for any simplified-specific keys
        return any(key in content for key in simplified_indicators)

    def _is_legacy_format(self, content: dict[str, Any]) -> bool:
        """Check if content matches legacy format."""
        # Legacy format has rules and multipliers as top-level keys
        return "rules" in content and isinstance(content["rules"], list)

    def _load_simplified_rules(self) -> None:
        """Load rules using simplified parser."""
        self.simplified_parser = SimplifiedYamlParser(self.config_path)
        self.config = self.simplified_parser.load_and_validate()

        # Convert to unified format
        self.rules = self._convert_simplified_rules()
        self.multipliers = self._convert_simplified_multipliers()
        self.settings = self.simplified_parser.get_settings()

    def _load_legacy_rules(self) -> None:
        """Load rules using legacy parser."""
        self.legacy_parser = ScoringRulesParser(self.config_path)
        self.config = self.legacy_parser.load_and_validate()

        self.rules = self.legacy_parser.get_enabled_rules()
        self.multipliers = self.legacy_parser.get_enabled_multipliers()
        self.settings = self.legacy_parser.get_settings()

    def _convert_simplified_rules(self) -> list[Any]:
        """Convert simplified rules to unified format for the evaluator."""
        unified_rules = []

        # Convert audit opportunities
        for rule in self.simplified_parser.get_audit_opportunities():
            unified_rule = self._create_unified_rule(rule)
            unified_rules.append(unified_rule)

        # Convert exclusions
        for rule in self.simplified_parser.get_exclusions():
            unified_rule = self._create_unified_rule(rule)
            unified_rules.append(unified_rule)

        return unified_rules

    def _convert_simplified_multipliers(self) -> list[Any]:
        """Convert simplified multipliers to unified format."""
        unified_multipliers = []

        for mult in self.simplified_parser.get_audit_multipliers():
            unified_mult = self._create_unified_multiplier(mult)
            unified_multipliers.append(unified_mult)

        return unified_multipliers

    def _create_unified_rule(self, simplified_rule) -> Any:
        """Create a unified rule object from simplified rule."""
        # Convert simplified rule to legacy-compatible format for the evaluator
        # This uses the conversion method from the simplified parser
        legacy_dict = self.simplified_parser.convert_to_legacy_format()

        # Find the corresponding rule in the legacy format
        for legacy_rule_dict in legacy_dict["rules"]:
            if legacy_rule_dict["name"] == simplified_rule.name:
                # Create a mock object that matches the legacy rule interface
                return self._create_rule_object(legacy_rule_dict)

        # Fallback: create basic rule object
        return self._create_rule_object(
            {
                "name": simplified_rule.name,
                "description": simplified_rule.description or "",
                "score": simplified_rule.score or 0,
                "condition": {},
            }
        )

    def _create_unified_multiplier(self, simplified_mult) -> Any:
        """Create a unified multiplier object from simplified multiplier."""
        legacy_dict = self.simplified_parser.convert_to_legacy_format()

        for legacy_mult_dict in legacy_dict["multipliers"]:
            if legacy_mult_dict["name"] == simplified_mult.name:
                return self._create_multiplier_object(legacy_mult_dict)

        # Fallback
        return self._create_multiplier_object(
            {
                "name": simplified_mult.name,
                "description": simplified_mult.description,
                "multiplier": simplified_mult.multiplier,
                "condition": {},
            }
        )

    def _create_rule_object(self, rule_dict: dict[str, Any]) -> Any:
        """Create a rule object that matches the expected interface."""

        # Create a simple object with the required attributes
        class UnifiedRule:
            def __init__(self, data):
                self.name = data["name"]
                self.description = data.get("description", "")
                self.score = data.get("score", 0)
                self.condition = self._create_condition_object(
                    data.get("condition", {})
                )
                self.enabled = True
                self.priority = data.get("priority", 0)

        return UnifiedRule(rule_dict)

    def _create_multiplier_object(self, mult_dict: dict[str, Any]) -> Any:
        """Create a multiplier object that matches the expected interface."""

        class UnifiedMultiplier:
            def __init__(self, data):
                self.name = data["name"]
                self.description = data.get("description", "")
                self.multiplier = data.get("multiplier", 1.0)
                self.condition = self._create_condition_object(
                    data.get("condition", {})
                )
                self.enabled = True

        return UnifiedMultiplier(mult_dict)

    def _create_condition_object(self, condition_dict: dict[str, Any]) -> Any:
        """Create a condition object with dynamic attributes."""

        class UnifiedCondition:
            def __init__(self, data):
                # Add all condition fields as attributes
                for key, value in data.items():
                    setattr(self, key, value)

        return UnifiedCondition(condition_dict)

    def score_business(self, business_data: dict[str, Any]) -> dict[str, Any]:
        """
        Score a business using the loaded rules.

        Args:
            business_data: Dictionary containing business attributes

        Returns:
            Dictionary containing score and scoring details
        """
        if not self.rules:
            raise RuntimeError("No rules loaded. Call load_rules() first.")

        with MetricsTimer(LEADS_SCORED, score_range="unknown"):
            try:
                # Calculate base score
                base_score = self.settings.base_score if self.settings else 50

                # Apply rules
                rule_scores = []
                total_adjustment = 0

                for rule in self.rules:
                    if self.evaluator.evaluate_condition(rule.condition, business_data):
                        rule_scores.append(
                            {
                                "rule": rule.name,
                                "description": rule.description,
                                "score_adjustment": rule.score,
                            }
                        )
                        total_adjustment += rule.score

                # Calculate preliminary score
                preliminary_score = base_score + total_adjustment

                # Apply multipliers
                final_multiplier = 1.0
                applied_multipliers = []

                for multiplier in self.multipliers:
                    if self.evaluator.evaluate_condition(
                        multiplier.condition, business_data
                    ):
                        applied_multipliers.append(
                            {
                                "multiplier": multiplier.name,
                                "description": multiplier.description,
                                "factor": multiplier.multiplier,
                            }
                        )
                        final_multiplier *= multiplier.multiplier

                # Calculate final score
                final_score = preliminary_score * final_multiplier

                # Apply bounds
                min_score = self.settings.min_score if self.settings else 0
                max_score = self.settings.max_score if self.settings else 100
                final_score = max(min_score, min(max_score, final_score))

                # Determine score range for metrics
                score_range = self._get_score_range(final_score)

                # Record metrics
                record_metric(LEADS_SCORED, 1, score_range=score_range)

                result = {
                    "final_score": round(final_score, 2),
                    "base_score": base_score,
                    "rule_adjustments": total_adjustment,
                    "preliminary_score": preliminary_score,
                    "final_multiplier": final_multiplier,
                    "applied_rules": rule_scores,
                    "applied_multipliers": applied_multipliers,
                    "format_used": self.format_type,
                    "audit_potential": self._determine_audit_potential(final_score),
                }

                self.logger.debug(
                    f"Scored business: {final_score} "
                    f"(base: {base_score}, adj: {total_adjustment}, mult: {final_multiplier})"
                )

                return result

            except Exception as e:
                self.logger.error(f"Error scoring business: {e}")
                raise

    def _get_score_range(self, score: float) -> str:
        """Determine score range for metrics."""
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "low"
        else:
            return "very_low"

    def _determine_audit_potential(self, score: float) -> str:
        """Determine audit potential based on score."""
        # For simplified format, higher scores indicate more audit potential
        # For legacy format, this provides audit context
        audit_threshold = getattr(self.settings, "audit_threshold", 60)

        if score >= audit_threshold + 20:
            return "high"
        elif score >= audit_threshold:
            return "medium"
        else:
            return "low"

    def get_format_info(self) -> dict[str, Any]:
        """Get information about the currently loaded format."""
        return {
            "format_type": self.format_type,
            "config_path": self.config_path,
            "rules_count": len(self.rules),
            "multipliers_count": len(self.multipliers),
            "settings": (
                self.settings.model_dump()
                if hasattr(self.settings, "model_dump")
                else vars(self.settings)
            ),
        }
