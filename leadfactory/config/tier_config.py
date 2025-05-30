"""
Tier configuration schema for LeadFactory pipeline processing.

This module defines the tier-based processing configuration that determines
which APIs and features are available at each tier level.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Union

from leadfactory.config.settings import TIER


class TierLevel(Enum):
    """Enumeration of available tier levels."""

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


@dataclass
class APIConfiguration:
    """Configuration for API usage at different tiers."""

    name: str
    required_env_vars: List[str]
    cost_per_request: float  # Cost in cents
    enabled_tiers: Set[TierLevel]
    description: str


@dataclass
class EnrichmentFeatures:
    """Features available for enrichment at each tier."""

    tech_stack_analysis: bool = True  # Available in all tiers
    core_web_vitals: bool = True  # Available in all tiers
    screenshot_capture: bool = False  # Tier 2+
    semrush_site_audit: bool = False  # Tier 3 only

    def __post_init__(self):
        """Validate feature configuration."""
        if self.semrush_site_audit and not self.screenshot_capture:
            # Tier 3 implies Tier 2 features
            self.screenshot_capture = True


@dataclass
class MockupFeatures:
    """Features available for mockup generation at each tier."""

    basic_template: bool = True  # Available in all tiers
    custom_branding: bool = False  # Tier 2+
    ai_content_generation: bool = False  # Tier 3 only
    advanced_layouts: bool = False  # Tier 3 only

    def __post_init__(self):
        """Validate feature configuration."""
        if self.ai_content_generation and not self.custom_branding:
            # Tier 3 implies Tier 2 features
            self.custom_branding = True
        if self.advanced_layouts and not self.ai_content_generation:
            # Advanced layouts require AI content generation
            self.ai_content_generation = True
            self.custom_branding = True


@dataclass
class TierConfiguration:
    """Complete configuration for a specific tier level."""

    level: TierLevel
    name: str
    description: str
    enrichment_features: EnrichmentFeatures
    mockup_features: MockupFeatures
    enabled_apis: Set[str]
    max_concurrent_requests: int
    cost_threshold_cents: int  # Alert threshold for this tier


# API Configurations
API_CONFIGS = {
    "wappalyzer": APIConfiguration(
        name="Wappalyzer",
        required_env_vars=[],  # Built-in library
        cost_per_request=0.0,
        enabled_tiers={TierLevel.TIER_1, TierLevel.TIER_2, TierLevel.TIER_3},
        description="Tech stack detection using Wappalyzer library",
    ),
    "pagespeed": APIConfiguration(
        name="PageSpeed Insights",
        required_env_vars=["PAGESPEED_API_KEY"],
        cost_per_request=0.0,  # Free API
        enabled_tiers={TierLevel.TIER_1, TierLevel.TIER_2, TierLevel.TIER_3},
        description="Core Web Vitals and performance metrics",
    ),
    "screenshot_one": APIConfiguration(
        name="ScreenshotOne",
        required_env_vars=["SCREENSHOT_ONE_API_KEY", "SCREENSHOT_ONE_KEY"],
        cost_per_request=1.0,  # 1 cent per screenshot
        enabled_tiers={TierLevel.TIER_2, TierLevel.TIER_3},
        description="Website screenshot capture service",
    ),
    "semrush": APIConfiguration(
        name="SEMrush",
        required_env_vars=["SEMRUSH_API_KEY", "SEMRUSH_KEY"],
        cost_per_request=10.0,  # 10 cents per site audit
        enabled_tiers={TierLevel.TIER_3},
        description="SEMrush Site Audit for comprehensive SEO analysis",
    ),
    "openai": APIConfiguration(
        name="OpenAI",
        required_env_vars=["OPENAI_API_KEY"],
        cost_per_request=5.0,  # 5 cents per AI generation request
        enabled_tiers={TierLevel.TIER_3},
        description="AI-powered content generation for mockups",
    ),
}

# Tier Configurations
TIER_CONFIGS = {
    TierLevel.TIER_1: TierConfiguration(
        level=TierLevel.TIER_1,
        name="Basic",
        description="Basic tech stack analysis and Core Web Vitals",
        enrichment_features=EnrichmentFeatures(
            tech_stack_analysis=True,
            core_web_vitals=True,
            screenshot_capture=False,
            semrush_site_audit=False,
        ),
        mockup_features=MockupFeatures(
            basic_template=True,
            custom_branding=False,
            ai_content_generation=False,
            advanced_layouts=False,
        ),
        enabled_apis={"wappalyzer", "pagespeed"},
        max_concurrent_requests=10,
        cost_threshold_cents=100,  # $1.00 alert threshold
    ),
    TierLevel.TIER_2: TierConfiguration(
        level=TierLevel.TIER_2,
        name="Enhanced",
        description="Basic features plus screenshot capture and custom branding",
        enrichment_features=EnrichmentFeatures(
            tech_stack_analysis=True,
            core_web_vitals=True,
            screenshot_capture=True,
            semrush_site_audit=False,
        ),
        mockup_features=MockupFeatures(
            basic_template=True,
            custom_branding=True,
            ai_content_generation=False,
            advanced_layouts=False,
        ),
        enabled_apis={"wappalyzer", "pagespeed", "screenshot_one"},
        max_concurrent_requests=5,
        cost_threshold_cents=600,  # $6.00 alert threshold
    ),
    TierLevel.TIER_3: TierConfiguration(
        level=TierLevel.TIER_3,
        name="Premium",
        description="All features including SEMrush analysis and AI-powered mockups",
        enrichment_features=EnrichmentFeatures(
            tech_stack_analysis=True,
            core_web_vitals=True,
            screenshot_capture=True,
            semrush_site_audit=True,
        ),
        mockup_features=MockupFeatures(
            basic_template=True,
            custom_branding=True,
            ai_content_generation=True,
            advanced_layouts=True,
        ),
        enabled_apis={"wappalyzer", "pagespeed", "screenshot_one", "semrush", "openai"},
        max_concurrent_requests=3,
        cost_threshold_cents=1000,  # $10.00 alert threshold
    ),
}


def get_current_tier_config() -> TierConfiguration:
    """
    Get the configuration for the current tier level.

    Returns:
        TierConfiguration for the current tier level.
    """
    tier_level = TierLevel(TIER)
    return TIER_CONFIGS[tier_level]


def get_tier_config(tier: Union[int, TierLevel]) -> TierConfiguration:
    """
    Get the configuration for a specific tier.

    Args:
        tier: Tier level (1, 2, or 3) or TierLevel enum

    Returns:
        TierConfiguration object for the specified tier

    Raises:
        ValueError: If tier is not 1, 2, or 3
    """
    # Handle TierLevel enum
    if isinstance(tier, TierLevel):
        tier_level = tier
        tier_int = tier.value
    else:
        tier_int = tier
        if tier_int not in [1, 2, 3]:
            raise ValueError(f"Invalid tier level: {tier}. Must be 1, 2, or 3.")
        tier_level = TierLevel(tier_int)

    return TIER_CONFIGS[tier_level]


def is_api_enabled(api_name: str, tier: Optional[int] = None) -> bool:
    """
    Check if an API is enabled for the specified tier.

    Args:
        api_name: Name of the API to check.
        tier: Tier level to check. If None, uses current tier.

    Returns:
        True if the API is enabled for the tier, False otherwise.
    """
    if tier is None:
        tier = TIER

    tier_config = get_tier_config(tier)
    return api_name in tier_config.enabled_apis


def get_api_config(api_name: str) -> Optional[APIConfiguration]:
    """
    Get the configuration for a specific API.

    Args:
        api_name: Name of the API.

    Returns:
        APIConfiguration if found, None otherwise.
    """
    return API_CONFIGS.get(api_name)


def validate_tier_requirements(tier: int) -> Dict[str, List[str]]:
    """
    Validate that all requirements for a tier are met.

    Args:
        tier: Tier level to validate.

    Returns:
        Dictionary with 'missing_env_vars' and 'disabled_apis' lists.
    """
    import os

    tier_config = get_tier_config(tier)
    missing_env_vars = []
    disabled_apis = []

    for api_name in tier_config.enabled_apis:
        api_config = API_CONFIGS.get(api_name)
        if not api_config:
            disabled_apis.append(api_name)
            continue

        for env_var in api_config.required_env_vars:
            if not os.getenv(env_var):
                missing_env_vars.append(env_var)
                if api_name not in disabled_apis:
                    disabled_apis.append(api_name)

    return {"missing_env_vars": missing_env_vars, "disabled_apis": disabled_apis}


def calculate_tier_cost_estimate(tier: int, num_businesses: int) -> float:
    """
    Calculate estimated cost for processing businesses at a specific tier.

    Args:
        tier: Tier level.
        num_businesses: Number of businesses to process.

    Returns:
        Estimated cost in cents.
    """
    tier_config = get_tier_config(tier)
    total_cost = 0.0

    for api_name in tier_config.enabled_apis:
        api_config = API_CONFIGS.get(api_name)
        if api_config:
            total_cost += api_config.cost_per_request * num_businesses

    return total_cost


def get_tier_summary() -> Dict[int, Dict[str, any]]:
    """
    Get a summary of all tier configurations.

    Returns:
        Dictionary mapping tier numbers to their configuration summaries.
    """
    summary = {}

    for tier_level, config in TIER_CONFIGS.items():
        summary[tier_level.value] = {
            "name": config.name,
            "description": config.description,
            "enabled_apis": list(config.enabled_apis),
            "enrichment_features": {
                "tech_stack_analysis": config.enrichment_features.tech_stack_analysis,
                "core_web_vitals": config.enrichment_features.core_web_vitals,
                "screenshot_capture": config.enrichment_features.screenshot_capture,
                "semrush_site_audit": config.enrichment_features.semrush_site_audit,
            },
            "mockup_features": {
                "basic_template": config.mockup_features.basic_template,
                "custom_branding": config.mockup_features.custom_branding,
                "ai_content_generation": config.mockup_features.ai_content_generation,
                "advanced_layouts": config.mockup_features.advanced_layouts,
            },
            "max_concurrent_requests": config.max_concurrent_requests,
            "cost_threshold_cents": config.cost_threshold_cents,
        }

    return summary


# Alias for backward compatibility
TIER_CONFIG = TIER_CONFIGS


def is_api_enabled_for_tier(api_name: str, tier: int) -> bool:
    """
    Check if an API is enabled for a specific tier.

    Args:
        api_name: Name of the API to check.
        tier: Tier level to check.

    Returns:
        True if the API is enabled for the tier, False otherwise.
    """
    return is_api_enabled(api_name, tier)


def is_feature_enabled_for_tier(
    feature_name: str, feature_type: str, tier: int
) -> bool:
    """
    Check if a feature is enabled for a specific tier.

    Args:
        feature_name: Name of the feature to check.
        feature_type: Type of feature ('enrichment' or 'mockup').
        tier: Tier level to check.

    Returns:
        True if the feature is enabled for the tier, False otherwise.
    """
    try:
        tier_level = TierLevel(tier)
        config = TIER_CONFIGS[tier_level]

        if feature_type == "enrichment":
            features = config.enrichment_features
        elif feature_type == "mockup":
            features = config.mockup_features
        else:
            return False

        return hasattr(features, feature_name) and getattr(
            features, feature_name, False
        )
    except (ValueError, KeyError):
        return False
