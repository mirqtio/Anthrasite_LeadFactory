"""
Simplified YAML Parser for Audit-Focused Scoring Rules

This module provides a new, simplified YAML format for scoring rules
that is optimized for the audit business model.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AuditSettings(BaseModel):
    """Settings for audit-focused scoring."""

    base_score: int = Field(default=50, ge=0, le=100)
    min_score: int = Field(default=0, ge=0)
    max_score: int = Field(default=100, le=1000)
    audit_threshold: int = Field(default=60, ge=0, le=100)


class RuleTemplate(BaseModel):
    """Template for reusable rule components."""

    description: str
    score: int = Field(..., ge=-100, le=100)
    audit_category: str
    enabled: bool = True


class SimpleCondition(BaseModel):
    """Simplified condition model for easier rule definition."""

    # Technology conditions
    technology: Optional[Union[str, List[str]]] = None
    version: Optional[str] = None  # e.g., "<3.0.0", ">2.5", ">=1.0"
    missing_any: Optional[List[str]] = None
    has_any: Optional[List[str]] = None

    # Performance conditions
    performance_score: Optional[str] = None  # e.g., "<50", ">80"
    lcp: Optional[str] = None  # Largest Contentful Paint, e.g., ">2.5s"
    cls: Optional[str] = None  # Cumulative Layout Shift, e.g., ">0.25"
    fid: Optional[str] = None  # First Input Delay, e.g., ">100ms"

    # Business conditions
    business_type: Optional[Union[str, List[str]]] = None
    location: Optional[Union[str, List[str]]] = None
    indicators: Optional[List[str]] = None

    # Composite conditions
    all: Optional[List[Dict[str, Any]]] = None
    any: Optional[List[Dict[str, Any]]] = None
    none: Optional[List[Dict[str, Any]]] = None


class AuditRule(BaseModel):
    """Simplified audit rule model."""

    name: str
    template: Optional[str] = None
    description: Optional[str] = None
    score: Optional[int] = Field(None, ge=-100, le=100)
    audit_category: Optional[str] = None
    audit_potential: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    when: SimpleCondition
    enabled: bool = True
    priority: int = Field(default=0, ge=0, le=100)

    @field_validator("score")
    @classmethod
    def validate_score(cls, v, info):
        """Validate score is provided either directly or via template."""
        if v is None and info.data.get("template") is None:
            raise ValueError("Score must be provided either directly or via template")
        return v


class AuditMultiplier(BaseModel):
    """Audit-focused scoring multiplier."""

    name: str
    description: str
    multiplier: float = Field(..., gt=0, le=10)
    when: SimpleCondition
    enabled: bool = True


class SimplifiedScoringConfig(BaseModel):
    """Complete configuration for simplified scoring rules."""

    settings: AuditSettings
    templates: Optional[Dict[str, RuleTemplate]] = {}
    audit_opportunities: List[AuditRule] = []
    exclusions: Optional[List[AuditRule]] = []
    audit_multipliers: Optional[List[AuditMultiplier]] = []


class SimplifiedYamlParser:
    """Parser for simplified audit-focused YAML scoring rules."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the simplified parser."""
        if config_path is None:
            config_path = (
                Path(__file__).parent / "../../etc/scoring_rules_simplified.yml"
            )
        self.config_path = Path(config_path)
        self.config: Optional[SimplifiedScoringConfig] = None
        logger.info(f"Initialized SimplifiedYamlParser with config: {self.config_path}")

    def load_and_validate(self) -> SimplifiedScoringConfig:
        """Load and validate the simplified YAML configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        logger.info(f"Loading simplified scoring rules from: {self.config_path}")

        try:
            with self.config_path.open() as f:
                raw_config = yaml.safe_load(f)

            # Validate the configuration
            self.config = SimplifiedScoringConfig(**raw_config)

            # Resolve template references
            self._resolve_templates()

            logger.info(
                f"Successfully loaded simplified configuration: "
                f"{len(self.config.audit_opportunities)} audit opportunities, "
                f"{len(self.config.exclusions or [])} exclusions, "
                f"{len(self.config.audit_multipliers or [])} multipliers"
            )

            return self.config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file: {e}")
            raise
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise

    def _resolve_templates(self):
        """Resolve template references in rules."""
        if not self.config:
            return

        # Resolve templates for audit opportunities
        for rule in self.config.audit_opportunities:
            if rule.template and rule.template in self.config.templates:
                template = self.config.templates[rule.template]

                # Apply template values if not overridden
                if rule.description is None:
                    rule.description = template.description
                if rule.score is None:
                    rule.score = template.score
                if rule.audit_category is None:
                    rule.audit_category = template.audit_category
                if rule.enabled is None:
                    rule.enabled = template.enabled

        # Resolve templates for exclusions
        if self.config.exclusions:
            for rule in self.config.exclusions:
                if rule.template and rule.template in self.config.templates:
                    template = self.config.templates[rule.template]

                    if rule.description is None:
                        rule.description = template.description
                    if rule.score is None:
                        rule.score = template.score
                    if rule.audit_category is None:
                        rule.audit_category = template.audit_category

    def get_audit_opportunities(self) -> List[AuditRule]:
        """Get all enabled audit opportunity rules."""
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        enabled_rules = [
            rule for rule in self.config.audit_opportunities if rule.enabled
        ]

        # Sort by priority (higher first) then by audit potential
        priority_map = {"high": 3, "medium": 2, "low": 1}
        enabled_rules.sort(
            key=lambda r: (
                r.priority,
                priority_map.get(r.audit_potential or "medium", 2),
            ),
            reverse=True,
        )

        return enabled_rules

    def get_exclusions(self) -> List[AuditRule]:
        """Get all enabled exclusion rules."""
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        return [rule for rule in (self.config.exclusions or []) if rule.enabled]

    def get_audit_multipliers(self) -> List[AuditMultiplier]:
        """Get all enabled audit multipliers."""
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        return [mult for mult in (self.config.audit_multipliers or []) if mult.enabled]

    def get_settings(self) -> AuditSettings:
        """Get the audit settings."""
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        return self.config.settings

    def convert_to_legacy_format(self) -> Dict[str, Any]:
        """Convert simplified format to legacy format for backward compatibility."""
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        legacy_config = {
            "settings": {
                "base_score": self.config.settings.base_score,
                "min_score": self.config.settings.min_score,
                "max_score": self.config.settings.max_score,
                "high_score_threshold": self.config.settings.audit_threshold,
            },
            "rules": [],
            "multipliers": [],
        }

        # Convert audit opportunities to legacy rules
        for rule in self.config.audit_opportunities:
            legacy_rule = self._convert_rule_to_legacy(rule)
            if legacy_rule:
                legacy_config["rules"].append(legacy_rule)

        # Convert exclusions to legacy rules
        for rule in self.config.exclusions or []:
            legacy_rule = self._convert_rule_to_legacy(rule)
            if legacy_rule:
                legacy_config["rules"].append(legacy_rule)

        # Convert multipliers to legacy format
        for mult in self.config.audit_multipliers or []:
            legacy_mult = self._convert_multiplier_to_legacy(mult)
            if legacy_mult:
                legacy_config["multipliers"].append(legacy_mult)

        return legacy_config

    def _convert_rule_to_legacy(self, rule: AuditRule) -> Optional[Dict[str, Any]]:
        """Convert a simplified rule to legacy format."""
        try:
            legacy_rule = {
                "name": rule.name,
                "description": rule.description or "",
                "score": rule.score or 0,
                "condition": self._convert_condition_to_legacy(rule.when),
            }
            return legacy_rule
        except Exception as e:
            logger.warning(f"Failed to convert rule {rule.name} to legacy format: {e}")
            return None

    def _convert_condition_to_legacy(
        self, condition: SimpleCondition
    ) -> Dict[str, Any]:
        """Convert simplified condition to legacy condition format."""
        legacy_condition = {}

        # Technology conditions
        if condition.technology:
            if isinstance(condition.technology, list):
                legacy_condition["tech_stack_contains_any"] = condition.technology
            else:
                legacy_condition["tech_stack_contains"] = condition.technology

        if condition.has_any:
            legacy_condition["tech_stack_contains_any"] = condition.has_any

        # Performance conditions
        if condition.performance_score:
            value = self._parse_comparison(condition.performance_score)
            if value["operator"] == "<":
                legacy_condition["performance_score_lt"] = value["value"]
            elif value["operator"] == ">":
                legacy_condition["performance_score_gt"] = value["value"]

        if condition.lcp:
            value = self._parse_comparison(condition.lcp)
            if value["operator"] == ">":
                # Convert seconds to milliseconds
                ms_value = float(value["value"].rstrip("s")) * 1000
                legacy_condition["lcp_gt"] = ms_value

        if condition.cls:
            value = self._parse_comparison(condition.cls)
            if value["operator"] == ">":
                legacy_condition["cls_gt"] = value["value"]

        # Business conditions
        if condition.business_type:
            if isinstance(condition.business_type, list):
                legacy_condition["category_contains_any"] = condition.business_type
            else:
                legacy_condition["category_contains"] = condition.business_type

        if condition.location:
            if isinstance(condition.location, list):
                legacy_condition["state_in"] = condition.location
            else:
                legacy_condition["state_equals"] = condition.location

        return legacy_condition

    def _convert_multiplier_to_legacy(
        self, mult: AuditMultiplier
    ) -> Optional[Dict[str, Any]]:
        """Convert simplified multiplier to legacy format."""
        try:
            legacy_mult = {
                "name": mult.name,
                "description": mult.description,
                "multiplier": mult.multiplier,
                "condition": self._convert_condition_to_legacy(mult.when),
            }
            return legacy_mult
        except Exception as e:
            logger.warning(
                f"Failed to convert multiplier {mult.name} to legacy format: {e}"
            )
            return None

    def _parse_comparison(self, comparison: str) -> Dict[str, Any]:
        """Parse comparison strings like '<50', '>2.5s', '>=1.0'."""
        comparison = comparison.strip()

        if comparison.startswith(">="):
            return {"operator": ">=", "value": comparison[2:].strip()}
        elif comparison.startswith("<="):
            return {"operator": "<=", "value": comparison[2:].strip()}
        elif comparison.startswith(">"):
            return {"operator": ">", "value": comparison[1:].strip()}
        elif comparison.startswith("<"):
            return {"operator": "<", "value": comparison[1:].strip()}
        elif comparison.startswith("="):
            return {"operator": "=", "value": comparison[1:].strip()}
        else:
            return {"operator": "=", "value": comparison}
