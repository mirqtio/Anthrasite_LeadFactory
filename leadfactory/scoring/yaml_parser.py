"""
YAML parsing and validation module for scoring rules.

This module handles loading, parsing, and validating scoring rules from YAML files.
"""

import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, validator

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class TechStackCondition(BaseModel):
    """Model for technology stack conditions."""

    tech_stack_contains: Optional[str] = None
    tech_stack_contains_any: Optional[list[str]] = None
    tech_stack_version_lt: Optional[dict[str, Union[str, float]]] = None
    tech_stack_version_gt: Optional[dict[str, Union[str, float]]] = None


class BusinessAttributeCondition(BaseModel):
    """Model for business attribute conditions."""

    vertical_in: Optional[list[str]] = None
    vertical_not_in: Optional[list[str]] = None
    location_in: Optional[list[str]] = None
    location_not_in: Optional[list[str]] = None
    employee_count_gt: Optional[int] = None
    employee_count_lt: Optional[int] = None
    revenue_gt: Optional[float] = None
    revenue_lt: Optional[float] = None
    founded_year_gt: Optional[int] = None
    founded_year_lt: Optional[int] = None


class SocialMediaCondition(BaseModel):
    """Model for social media conditions."""

    has_social_media: Optional[list[str]] = None
    social_followers_gt: Optional[dict[str, int]] = None
    social_engagement_gt: Optional[dict[str, float]] = None


class RuleCondition(BaseModel):
    """Combined model for all rule conditions."""

    # Tech stack conditions
    tech_stack_contains: Optional[str] = None
    tech_stack_contains_any: Optional[list[str]] = None
    tech_stack_version_lt: Optional[dict[str, Union[str, float]]] = None
    tech_stack_version_gt: Optional[dict[str, Union[str, float]]] = None

    # Business attribute conditions
    vertical_in: Optional[list[str]] = None
    vertical_not_in: Optional[list[str]] = None
    location_in: Optional[list[str]] = None
    location_not_in: Optional[list[str]] = None
    employee_count_gt: Optional[int] = None
    employee_count_lt: Optional[int] = None
    revenue_gt: Optional[float] = None
    revenue_lt: Optional[float] = None
    founded_year_gt: Optional[int] = None
    founded_year_lt: Optional[int] = None

    # Social media conditions
    has_social_media: Optional[list[str]] = None
    social_followers_gt: Optional[dict[str, int]] = None
    social_engagement_gt: Optional[dict[str, float]] = None

    # Website conditions
    has_contact_form: Optional[bool] = None
    has_phone_number: Optional[bool] = None
    has_email: Optional[bool] = None
    page_count_gt: Optional[int] = None
    page_count_lt: Optional[int] = None

    # Combined conditions
    all_of: Optional[list[dict[str, Any]]] = None
    any_of: Optional[list[dict[str, Any]]] = None
    none_of: Optional[list[dict[str, Any]]] = None


class ScoringRule(BaseModel):
    """Model for a single scoring rule."""

    name: str
    description: Optional[str] = None
    condition: RuleCondition
    score: int = Field(..., ge=-100, le=100)  # Score adjustment between -100 and 100
    enabled: bool = True
    priority: int = Field(
        default=0, ge=0, le=100
    )  # Higher priority rules evaluated first

    @field_validator("score")
    @classmethod
    def validate_score(cls, v):
        """Ensure score is within reasonable bounds."""
        if not -100 <= v <= 100:
            raise ValueError(f"Score must be between -100 and 100, got {v}")
        return v


class ScoringMultiplier(BaseModel):
    """Model for scoring multipliers."""

    name: str
    description: Optional[str] = None
    condition: RuleCondition
    multiplier: float = Field(..., gt=0, le=10)  # Multiplier between 0 and 10
    enabled: bool = True

    @field_validator("multiplier")
    @classmethod
    def validate_multiplier(cls, v):
        """Ensure multiplier is within reasonable bounds."""
        if not 0 < v <= 10:
            raise ValueError(f"Multiplier must be between 0 and 10, got {v}")
        return v


class ScoringSettings(BaseModel):
    """Model for global scoring settings."""

    base_score: int = Field(default=50, ge=0, le=100)
    min_score: int = Field(default=0, ge=0)
    max_score: int = Field(default=100, le=1000)
    high_score_threshold: int = Field(default=75, ge=0, le=100)

    @field_validator("max_score")
    @classmethod
    def validate_max_score(cls, v, info):
        """Ensure max_score is greater than min_score."""
        if (
            hasattr(info, "data")
            and "min_score" in info.data
            and v <= info.data["min_score"]
        ):
            raise ValueError("max_score must be greater than min_score")
        return v


class ScoringRulesConfig(BaseModel):
    """Model for the complete scoring rules configuration."""

    settings: ScoringSettings
    rules: list[ScoringRule]
    multipliers: Optional[list[ScoringMultiplier]] = []


class ScoringRulesParser:
    """Parser for YAML scoring rules files."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the parser.

        Args:
            config_path: Path to the YAML configuration file.
                        If not provided, uses default path.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "../../etc/scoring_rules.yml"
        self.config_path = Path(config_path)
        self.config: Optional[ScoringRulesConfig] = None
        logger.info(
            f"Initialized ScoringRulesParser with config path: {self.config_path}"
        )

    def load_and_validate(self) -> ScoringRulesConfig:
        """
        Load and validate the YAML configuration.

        Returns:
            Validated ScoringRulesConfig object.

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.
            yaml.YAMLError: If the YAML is invalid.
            ValidationError: If the configuration doesn't match the schema.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        logger.info(f"Loading scoring rules from: {self.config_path}")

        try:
            with self.config_path.open() as f:
                raw_config = yaml.safe_load(f)

            logger.debug(
                f"Loaded raw configuration with {len(raw_config.get('rules', []))} rules"
            )

            # Validate the configuration
            self.config = ScoringRulesConfig(**raw_config)

            logger.info(
                f"Successfully validated configuration: "
                f"{len(self.config.rules)} rules, "
                f"{len(self.config.multipliers)} multipliers"
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

    def get_enabled_rules(self) -> list[ScoringRule]:
        """
        Get only the enabled rules.

        Returns:
            List of enabled ScoringRule objects.
        """
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        enabled_rules = [rule for rule in self.config.rules if rule.enabled]
        logger.debug(
            f"Found {len(enabled_rules)} enabled rules out of {len(self.config.rules)} total"
        )

        # Sort by priority (higher priority first)
        enabled_rules.sort(key=lambda r: r.priority, reverse=True)

        return enabled_rules

    def get_enabled_multipliers(self) -> list[ScoringMultiplier]:
        """
        Get only the enabled multipliers.

        Returns:
            List of enabled ScoringMultiplier objects.
        """
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        enabled_multipliers = [m for m in self.config.multipliers if m.enabled]
        logger.debug(
            f"Found {len(enabled_multipliers)} enabled multipliers "
            f"out of {len(self.config.multipliers)} total"
        )

        return enabled_multipliers

    def get_settings(self) -> ScoringSettings:
        """
        Get the scoring settings.

        Returns:
            ScoringSettings object.
        """
        if not self.config:
            raise RuntimeError(
                "Configuration not loaded. Call load_and_validate() first."
            )

        return self.config.settings

    def validate_rule_syntax(self, rule_dict: dict[str, Any]) -> bool:
        """
        Validate a single rule dictionary.

        Args:
            rule_dict: Dictionary representing a rule.

        Returns:
            True if valid, False otherwise.
        """
        try:
            ScoringRule(**rule_dict)
            return True
        except ValidationError as e:
            logger.error(f"Rule validation failed: {e}")
            return False
