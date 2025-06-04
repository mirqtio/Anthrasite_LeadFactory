"""
Rule Converter for YAML Scoring Rules

This module provides utilities to convert between legacy and simplified
YAML scoring rule formats.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from leadfactory.scoring.simplified_yaml_parser import (
    AuditMultiplier,
    AuditRule,
    AuditSettings,
    RuleTemplate,
    SimpleCondition,
    SimplifiedScoringConfig,
)
from leadfactory.scoring.yaml_parser import ScoringRulesParser
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class RuleConverter:
    """Converts between legacy and simplified scoring rule formats."""

    def __init__(self):
        """Initialize the rule converter."""
        self.legacy_parser = ScoringRulesParser()

    def convert_legacy_to_simplified(self, legacy_path: str, output_path: str) -> bool:
        """
        Convert legacy YAML format to simplified format.

        Args:
            legacy_path: Path to legacy YAML file
            output_path: Path for simplified YAML output

        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Load legacy configuration
            self.legacy_parser.config_path = Path(legacy_path)
            legacy_config = self.legacy_parser.load_and_validate()

            # Convert to simplified format
            simplified_config = self._convert_config_to_simplified(legacy_config)

            # Generate simplified YAML
            simplified_dict = self._simplified_config_to_dict(simplified_config)

            # Write to output file
            with open(output_path, "w") as f:
                yaml.dump(simplified_dict, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Successfully converted {legacy_path} to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to convert {legacy_path}: {e}")
            return False

    def _convert_config_to_simplified(self, legacy_config) -> SimplifiedScoringConfig:
        """Convert legacy config object to simplified format."""

        # Convert settings
        settings = AuditSettings(
            base_score=legacy_config.settings.base_score,
            min_score=legacy_config.settings.min_score,
            max_score=legacy_config.settings.max_score,
            audit_threshold=legacy_config.settings.high_score_threshold,
        )

        # Create common templates
        templates = self._create_common_templates()

        # Convert rules
        audit_opportunities = []
        exclusions = []

        for rule in legacy_config.rules:
            simplified_rule = self._convert_legacy_rule(rule, templates)
            if simplified_rule:
                if simplified_rule.score > 0:
                    audit_opportunities.append(simplified_rule)
                else:
                    exclusions.append(simplified_rule)

        # Convert multipliers
        audit_multipliers = []
        for mult in legacy_config.multipliers:
            simplified_mult = self._convert_legacy_multiplier(mult)
            if simplified_mult:
                audit_multipliers.append(simplified_mult)

        return SimplifiedScoringConfig(
            settings=settings,
            templates=templates,
            audit_opportunities=audit_opportunities,
            exclusions=exclusions,
            audit_multipliers=audit_multipliers,
        )

    def _create_common_templates(self) -> Dict[str, RuleTemplate]:
        """Create common rule templates based on legacy patterns."""
        return {
            "tech_modernization": RuleTemplate(
                description="Technology modernization opportunity identified",
                score=15,
                audit_category="technology_upgrade",
            ),
            "performance_optimization": RuleTemplate(
                description="Website performance optimization needed",
                score=20,
                audit_category="performance_improvement",
            ),
            "business_opportunity": RuleTemplate(
                description="Business alignment opportunity",
                score=10,
                audit_category="business_alignment",
            ),
            "location_bonus": RuleTemplate(
                description="Target market location bonus",
                score=5,
                audit_category="market_alignment",
            ),
        }

    def _convert_legacy_rule(
        self, legacy_rule, templates: Dict[str, RuleTemplate]
    ) -> Optional[AuditRule]:
        """Convert a single legacy rule to simplified format."""
        try:
            # Determine audit potential based on score
            audit_potential = "low"
            if abs(legacy_rule.score) >= 15:
                audit_potential = "high"
            elif abs(legacy_rule.score) >= 10:
                audit_potential = "medium"

            # Determine template based on rule characteristics
            template = self._determine_template(legacy_rule)

            # Convert condition
            simplified_condition = self._convert_legacy_condition(legacy_rule.condition)

            # Create simplified rule
            simplified_rule = AuditRule(
                name=legacy_rule.name,
                template=template,
                description=legacy_rule.description,
                score=legacy_rule.score,
                audit_potential=audit_potential,
                when=simplified_condition,
                priority=legacy_rule.priority,
            )

            return simplified_rule

        except Exception as e:
            logger.warning(f"Failed to convert rule {legacy_rule.name}: {e}")
            return None

    def _determine_template(self, legacy_rule) -> Optional[str]:
        """Determine appropriate template based on legacy rule characteristics."""
        rule_name = legacy_rule.name.lower()

        if any(
            tech in rule_name
            for tech in ["jquery", "tech", "framework", "outdated", "html"]
        ):
            return "tech_modernization"
        elif any(
            perf in rule_name for perf in ["performance", "speed", "lcp", "cls", "fid"]
        ):
            return "performance_optimization"
        elif any(
            bus in rule_name for bus in ["category", "business", "restaurant", "retail"]
        ):
            return "business_opportunity"
        elif any(
            loc in rule_name
            for loc in ["location", "new_york", "washington", "indiana"]
        ):
            return "location_bonus"

        return None

    def _convert_legacy_condition(self, legacy_condition) -> SimpleCondition:
        """Convert legacy condition format to simplified format."""
        simplified = SimpleCondition()

        # Technology conditions
        if hasattr(legacy_condition, "tech_stack_contains"):
            simplified.technology = legacy_condition.tech_stack_contains
        elif hasattr(legacy_condition, "tech_stack_contains_any"):
            simplified.technology = legacy_condition.tech_stack_contains_any

        if hasattr(legacy_condition, "tech_stack_version_lt"):
            version_info = legacy_condition.tech_stack_version_lt
            if isinstance(version_info, dict):
                tech = version_info.get("technology")
                version = version_info.get("version")
                if tech and version:
                    simplified.technology = tech
                    simplified.version = f"<{version}"

        # Performance conditions
        if hasattr(legacy_condition, "performance_score_lt"):
            simplified.performance_score = f"<{legacy_condition.performance_score_lt}"
        elif hasattr(legacy_condition, "performance_score_gt"):
            simplified.performance_score = f">{legacy_condition.performance_score_gt}"
        elif hasattr(legacy_condition, "performance_score_between"):
            between = legacy_condition.performance_score_between
            # Simplify to single condition for now
            simplified.performance_score = f"<{between.get('max', 100)}"

        if hasattr(legacy_condition, "lcp_gt"):
            # Convert milliseconds to seconds
            seconds = legacy_condition.lcp_gt / 1000
            simplified.lcp = f">{seconds}s"

        if hasattr(legacy_condition, "cls_gt"):
            simplified.cls = f">{legacy_condition.cls_gt}"

        # Business conditions
        if hasattr(legacy_condition, "category_contains_any"):
            simplified.business_type = legacy_condition.category_contains_any
        elif hasattr(legacy_condition, "category_contains"):
            simplified.business_type = legacy_condition.category_contains

        if hasattr(legacy_condition, "state_equals"):
            simplified.location = legacy_condition.state_equals
        elif hasattr(legacy_condition, "state_in"):
            simplified.location = legacy_condition.state_in

        # Website conditions
        website_indicators = []
        if (
            hasattr(legacy_condition, "website_missing")
            and legacy_condition.website_missing
        ):
            website_indicators.append("website_missing")
        if (
            hasattr(legacy_condition, "has_multiple_locations")
            and legacy_condition.has_multiple_locations
        ):
            website_indicators.append("multiple_locations")
        if (
            hasattr(legacy_condition, "review_count_gt")
            and legacy_condition.review_count_gt > 50
        ):
            website_indicators.append("high_review_count")

        if website_indicators:
            simplified.indicators = website_indicators

        return simplified

    def _convert_legacy_multiplier(self, legacy_mult) -> Optional[AuditMultiplier]:
        """Convert legacy multiplier to simplified format."""
        try:
            simplified_condition = self._convert_legacy_condition(legacy_mult.condition)

            return AuditMultiplier(
                name=legacy_mult.name,
                description=legacy_mult.description,
                multiplier=legacy_mult.multiplier,
                when=simplified_condition,
            )
        except Exception as e:
            logger.warning(f"Failed to convert multiplier {legacy_mult.name}: {e}")
            return None

    def _simplified_config_to_dict(
        self, config: SimplifiedScoringConfig
    ) -> Dict[str, Any]:
        """Convert simplified config object to dictionary for YAML output."""
        result = {
            "settings": {
                "base_score": config.settings.base_score,
                "min_score": config.settings.min_score,
                "max_score": config.settings.max_score,
                "audit_threshold": config.settings.audit_threshold,
            }
        }

        # Add templates
        if config.templates:
            result["templates"] = {}
            for name, template in config.templates.items():
                result["templates"][name] = {
                    "description": template.description,
                    "score": template.score,
                    "audit_category": template.audit_category,
                }

        # Add audit opportunities
        result["audit_opportunities"] = []
        for rule in config.audit_opportunities:
            rule_dict = self._audit_rule_to_dict(rule)
            result["audit_opportunities"].append(rule_dict)

        # Add exclusions
        if config.exclusions:
            result["exclusions"] = []
            for rule in config.exclusions:
                rule_dict = self._audit_rule_to_dict(rule)
                result["exclusions"].append(rule_dict)

        # Add multipliers
        if config.audit_multipliers:
            result["audit_multipliers"] = []
            for mult in config.audit_multipliers:
                mult_dict = {
                    "name": mult.name,
                    "description": mult.description,
                    "multiplier": mult.multiplier,
                    "when": self._condition_to_dict(mult.when),
                }
                result["audit_multipliers"].append(mult_dict)

        return result

    def _audit_rule_to_dict(self, rule: AuditRule) -> Dict[str, Any]:
        """Convert AuditRule to dictionary."""
        rule_dict = {"name": rule.name, "when": self._condition_to_dict(rule.when)}

        if rule.template:
            rule_dict["template"] = rule.template
        if rule.description:
            rule_dict["description"] = rule.description
        if rule.score is not None:
            rule_dict["score"] = rule.score
        if rule.audit_potential:
            rule_dict["audit_potential"] = rule.audit_potential
        if rule.priority != 0:
            rule_dict["priority"] = rule.priority

        return rule_dict

    def _condition_to_dict(self, condition: SimpleCondition) -> Dict[str, Any]:
        """Convert SimpleCondition to dictionary."""
        result = {}

        for field, value in condition.model_dump().items():
            if value is not None:
                result[field] = value

        return result


def main():
    """CLI utility for converting YAML formats."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert between YAML scoring rule formats"
    )
    parser.add_argument("input", help="Input YAML file path")
    parser.add_argument("output", help="Output YAML file path")
    parser.add_argument(
        "--format",
        choices=["legacy", "simplified"],
        default="simplified",
        help="Output format (default: simplified)",
    )

    args = parser.parse_args()

    converter = RuleConverter()

    if args.format == "simplified":
        success = converter.convert_legacy_to_simplified(args.input, args.output)
    else:
        print("Legacy format conversion not implemented yet")
        success = False

    if success:
        print(f"Successfully converted {args.input} to {args.output}")
    else:
        print("Conversion failed")
        exit(1)


if __name__ == "__main__":
    main()
