"""
Node capability configuration for LeadFactory pipeline processing.

This module defines the node-based processing configuration that determines
which capabilities are available for each pipeline node, replacing the
tier-based system with dynamic dependency evaluation.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Union

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class DeploymentEnvironment(Enum):
    """Deployment environment types for environment-aware defaults."""

    DEVELOPMENT = "development"
    PRODUCTION_AUDIT = "production_audit"
    PRODUCTION_GENERAL = "production_general"


class CapabilityTier(Enum):
    """Capability tiers based on business value and cost."""

    ESSENTIAL = "essential"  # Always enabled, low/no cost
    HIGH_VALUE = "high_value"  # Enabled when budget allows, high ROI
    OPTIONAL = "optional"  # Enabled only with specific requirements


class NodeType(Enum):
    """Enumeration of available node types in the pipeline."""

    SCRAPE = "scrape"
    ENRICH = "enrich"
    DEDUPE = "dedupe"
    SCORE = "score"
    SCREENSHOT = "screenshot"
    MOCKUP = "mockup"
    EMAIL = "email"
    FINAL_OUTPUT = "final_output"  # Unified GPT-4o node


@dataclass
class APIConfiguration:
    """Configuration for API usage in pipeline nodes."""

    name: str
    required_env_vars: List[str]
    cost_per_request: float  # Cost in cents
    description: str
    enabled_by_default: bool = True
    requires_budget: bool = True  # Whether this API requires budget allocation
    fallback_available: bool = False  # Whether a fallback option exists
    fallback_description: Optional[str] = None


@dataclass
class NodeCapability:
    """Defines a capability that can be enabled/disabled for a node."""

    name: str
    description: str
    required_apis: List[str]
    required_inputs: List[str]  # Input data required for this capability
    cost_estimate_cents: float
    enabled_by_default: bool = True
    tier: CapabilityTier = CapabilityTier.ESSENTIAL
    environment_overrides: Optional[Dict[DeploymentEnvironment, bool]] = None


@dataclass
class NodeConfiguration:
    """Complete configuration for a pipeline node."""

    node_type: NodeType
    name: str
    description: str
    capabilities: List[NodeCapability]
    required_inputs: List[str]  # Base inputs required for node to run
    optional_inputs: List[str]  # Optional inputs that enable additional capabilities
    output_keys: List[str]  # Keys this node adds to the lead data


# API Configurations
API_CONFIGS = {
    "wappalyzer": APIConfiguration(
        name="Wappalyzer",
        required_env_vars=[],  # Built-in library
        cost_per_request=0.0,
        description="Tech stack detection using Wappalyzer library",
        enabled_by_default=True,
        requires_budget=False,
        fallback_available=False,
    ),
    "pagespeed": APIConfiguration(
        name="PageSpeed Insights",
        required_env_vars=["PAGESPEED_API_KEY"],
        cost_per_request=0.0,  # Free API
        description="Core Web Vitals and performance metrics",
        enabled_by_default=True,
        requires_budget=False,
        fallback_available=True,
        fallback_description="Local Lighthouse CLI analysis",
    ),
    "screenshot_one": APIConfiguration(
        name="ScreenshotOne",
        required_env_vars=["SCREENSHOT_ONE_API_KEY", "SCREENSHOT_ONE_KEY"],
        cost_per_request=1.0,  # 1 cent per screenshot
        description="Website screenshot capture service",
        enabled_by_default=False,  # Updated: disabled by default due to cost
        requires_budget=True,
        fallback_available=True,
        fallback_description="Local Puppeteer screenshot generation",
    ),
    "semrush": APIConfiguration(
        name="SEMrush",
        required_env_vars=["SEMRUSH_API_KEY", "SEMRUSH_KEY"],
        cost_per_request=10.0,  # 10 cents per site audit
        description="SEMrush Site Audit for comprehensive SEO analysis",
        enabled_by_default=False,  # Expensive, opt-in
        requires_budget=True,
        fallback_available=False,
    ),
    "openai": APIConfiguration(
        name="OpenAI",
        required_env_vars=["OPENAI_API_KEY"],
        cost_per_request=5.0,  # 5 cents per AI generation request
        description="AI-powered content generation",
        enabled_by_default=True,
        requires_budget=True,
        fallback_available=True,
        fallback_description="Template-based content generation",
    ),
}

# Node Capability Definitions
ENRICH_CAPABILITIES = [
    NodeCapability(
        name="tech_stack_analysis",
        description="Analyze website technology stack using Wappalyzer",
        required_apis=["wappalyzer"],
        required_inputs=["website"],
        cost_estimate_cents=0.0,
        enabled_by_default=True,
        tier=CapabilityTier.ESSENTIAL,
    ),
    NodeCapability(
        name="core_web_vitals",
        description="Analyze Core Web Vitals and performance metrics",
        required_apis=["pagespeed"],
        required_inputs=["website"],
        cost_estimate_cents=0.0,
        enabled_by_default=True,
        tier=CapabilityTier.ESSENTIAL,
    ),
    NodeCapability(
        name="screenshot_capture",
        description="Capture website screenshot",
        required_apis=["screenshot_one"],
        required_inputs=["website"],
        cost_estimate_cents=1.0,
        enabled_by_default=False,  # Updated: disabled by default
        tier=CapabilityTier.OPTIONAL,
        environment_overrides={
            DeploymentEnvironment.DEVELOPMENT: False,
            DeploymentEnvironment.PRODUCTION_AUDIT: False,
            DeploymentEnvironment.PRODUCTION_GENERAL: True,
        },
    ),
    NodeCapability(
        name="semrush_site_audit",
        description="Comprehensive SEO analysis using SEMrush",
        required_apis=["semrush"],
        required_inputs=["website"],
        cost_estimate_cents=10.0,
        enabled_by_default=False,
        tier=CapabilityTier.HIGH_VALUE,
        environment_overrides={
            DeploymentEnvironment.DEVELOPMENT: False,
            DeploymentEnvironment.PRODUCTION_AUDIT: True,  # Enable for audit model
            DeploymentEnvironment.PRODUCTION_GENERAL: False,
        },
    ),
]

FINAL_OUTPUT_CAPABILITIES = [
    NodeCapability(
        name="mockup_generation",
        description="Generate PNG mockup using GPT-4o",
        required_apis=["openai"],
        required_inputs=["website", "name"],
        cost_estimate_cents=5.0,
        enabled_by_default=True,
        tier=CapabilityTier.OPTIONAL,
        environment_overrides={
            DeploymentEnvironment.DEVELOPMENT: False,  # Reduce OpenAI costs in dev
            DeploymentEnvironment.PRODUCTION_AUDIT: True,
            DeploymentEnvironment.PRODUCTION_GENERAL: True,
        },
    ),
    NodeCapability(
        name="email_generation",
        description="Generate personalized email using GPT-4o",
        required_apis=["openai"],
        required_inputs=["website", "name"],
        cost_estimate_cents=5.0,
        enabled_by_default=True,
        tier=CapabilityTier.HIGH_VALUE,  # Core business value
        environment_overrides={
            DeploymentEnvironment.DEVELOPMENT: True,  # Keep for testing
            DeploymentEnvironment.PRODUCTION_AUDIT: True,
            DeploymentEnvironment.PRODUCTION_GENERAL: True,
        },
    ),
]

# Node Configurations
NODE_CONFIGS = {
    NodeType.SCRAPE: NodeConfiguration(
        node_type=NodeType.SCRAPE,
        name="Scrape",
        description="Scrape business data from various sources",
        capabilities=[],  # Scraping has no optional capabilities
        required_inputs=[],  # No inputs required for scraping
        optional_inputs=[],
        output_keys=["name", "website", "industry", "location"],
    ),
    NodeType.ENRICH: NodeConfiguration(
        node_type=NodeType.ENRICH,
        name="Enrich",
        description="Enrich business data with technology and performance analysis",
        capabilities=ENRICH_CAPABILITIES,
        required_inputs=["website"],
        optional_inputs=["name", "industry"],
        output_keys=[
            "tech_stack",
            "performance_metrics",
            "screenshot_url",
            "semrush_data",
        ],
    ),
    NodeType.DEDUPE: NodeConfiguration(
        node_type=NodeType.DEDUPE,
        name="Dedupe",
        description="Remove duplicate businesses from the dataset",
        capabilities=[],  # No optional capabilities
        required_inputs=["name", "website"],
        optional_inputs=["location", "industry"],
        output_keys=["is_duplicate", "duplicate_group_id"],
    ),
    NodeType.SCORE: NodeConfiguration(
        node_type=NodeType.SCORE,
        name="Score",
        description="Score businesses based on various criteria",
        capabilities=[],  # No optional capabilities
        required_inputs=["name", "website"],
        optional_inputs=["tech_stack", "performance_metrics", "industry"],
        output_keys=["score", "score_breakdown"],
    ),
    NodeType.FINAL_OUTPUT: NodeConfiguration(
        node_type=NodeType.FINAL_OUTPUT,
        name="Final Output",
        description="Generate final mockup and email using GPT-4o",
        capabilities=FINAL_OUTPUT_CAPABILITIES,
        required_inputs=["name", "website"],
        optional_inputs=[
            "tech_stack",
            "performance_metrics",
            "screenshot_url",
            "score",
        ],
        output_keys=["mockup_url", "email_content"],
    ),
}


def get_node_config(node_type: NodeType) -> NodeConfiguration:
    """Get configuration for a specific node type."""
    return NODE_CONFIGS[node_type]


def is_api_available(api_name: str) -> bool:
    """Check if an API is available (has required environment variables)."""
    if api_name not in API_CONFIGS:
        return False

    api_config = API_CONFIGS[api_name]
    for env_var in api_config.required_env_vars:
        if not os.getenv(env_var):
            return False

    return True


def get_deployment_environment() -> DeploymentEnvironment:
    """
    Detect the current deployment environment based on environment variables.

    Returns:
        The detected deployment environment
    """
    env_mode = os.getenv("DEPLOYMENT_ENVIRONMENT", "").lower()

    if env_mode == "development" or env_mode == "dev":
        return DeploymentEnvironment.DEVELOPMENT
    elif env_mode == "production_audit" or env_mode == "prod_audit":
        return DeploymentEnvironment.PRODUCTION_AUDIT
    elif env_mode == "production_general" or env_mode == "prod_general":
        return DeploymentEnvironment.PRODUCTION_GENERAL
    else:
        # Default based on other environment indicators
        if os.getenv("NODE_ENV") == "development":
            return DeploymentEnvironment.DEVELOPMENT
        elif os.getenv("BUSINESS_MODEL", "").lower() == "audit":
            return DeploymentEnvironment.PRODUCTION_AUDIT
        else:
            return DeploymentEnvironment.PRODUCTION_GENERAL


def is_capability_enabled_for_environment(
    capability: NodeCapability, environment: DeploymentEnvironment
) -> bool:
    """
    Check if a capability should be enabled for a specific environment.

    Args:
        capability: The capability to check
        environment: The deployment environment

    Returns:
        True if the capability should be enabled
    """
    # Check for environment-specific overrides
    if (
        capability.environment_overrides
        and environment in capability.environment_overrides
    ):
        return capability.environment_overrides[environment]

    # Fall back to default setting
    return capability.enabled_by_default


def get_capabilities_by_tier(
    tier: CapabilityTier, node_type: NodeType
) -> List[NodeCapability]:
    """
    Get capabilities of a specific tier for a node type.

    Args:
        tier: The capability tier to filter by
        node_type: The type of node to get capabilities for

    Returns:
        List of capabilities in the specified tier
    """
    node_config = get_node_config(node_type)
    return [cap for cap in node_config.capabilities if cap.tier == tier]


def get_enabled_capabilities(
    node_type: NodeType,
    budget_cents: Optional[float] = None,
    environment: Optional[DeploymentEnvironment] = None,
) -> List[NodeCapability]:
    """
    Get enabled capabilities for a node based on API availability, budget, and environment.

    Args:
        node_type: The type of node to get capabilities for
        budget_cents: Available budget in cents (None = unlimited)
        environment: Deployment environment (auto-detected if None)

    Returns:
        List of enabled capabilities
    """
    if environment is None:
        environment = get_deployment_environment()

    node_config = get_node_config(node_type)
    enabled_capabilities = []

    logger.debug(
        f"Evaluating capabilities for {node_type.value} in {environment.value} environment"
    )

    for capability in node_config.capabilities:
        # Check if capability should be enabled for this environment
        env_enabled = is_capability_enabled_for_environment(capability, environment)

        if not env_enabled:
            logger.debug(
                f"Capability {capability.name} disabled for environment {environment.value}"
            )
            continue

        # Check if all required APIs are available
        apis_available = all(is_api_available(api) for api in capability.required_apis)

        if not apis_available:
            missing_apis = [
                api for api in capability.required_apis if not is_api_available(api)
            ]
            logger.info(
                f"Capability {capability.name} disabled due to missing APIs: {missing_apis}"
            )

            # Check for fallback options
            fallback_available = any(
                API_CONFIGS.get(api, APIConfiguration("", [], 0, "")).fallback_available
                for api in missing_apis
            )
            if fallback_available:
                logger.info(f"Fallback available for {capability.name}")
            continue

        # Check budget if required
        budget_ok = True
        if budget_cents is not None and capability.cost_estimate_cents > 0:
            budget_ok = budget_cents >= capability.cost_estimate_cents

        if not budget_ok:
            logger.debug(
                f"Capability {capability.name} disabled due to budget constraint: "
                f"requires {capability.cost_estimate_cents}, available {budget_cents}"
            )
            continue

        enabled_capabilities.append(capability)
        logger.debug(
            f"Enabled capability: {capability.name} (tier: {capability.tier.value})"
        )

    logger.info(
        f"Enabled {len(enabled_capabilities)} capabilities for {node_type.value}: "
        f"{[cap.name for cap in enabled_capabilities]}"
    )

    return enabled_capabilities


def can_node_run(node_type: NodeType, lead_data: dict) -> tuple[bool, List[str]]:
    """
    Check if a node can run with the given lead data.

    Args:
        node_type: The type of node to check
        lead_data: Current lead data dictionary

    Returns:
        Tuple of (can_run, missing_inputs)
    """
    node_config = get_node_config(node_type)
    missing_inputs = []

    for required_input in node_config.required_inputs:
        if required_input not in lead_data or not lead_data[required_input]:
            missing_inputs.append(required_input)

    return len(missing_inputs) == 0, missing_inputs


def estimate_node_cost(
    node_type: NodeType,
    budget_cents: Optional[float] = None,
    environment: Optional[DeploymentEnvironment] = None,
) -> float:
    """
    Estimate the cost of running a node with enabled capabilities.

    Args:
        node_type: The type of node to estimate cost for
        budget_cents: Available budget in cents
        environment: Deployment environment (auto-detected if None)

    Returns:
        Estimated cost in cents
    """
    enabled_capabilities = get_enabled_capabilities(
        node_type, budget_cents, environment
    )
    return sum(cap.cost_estimate_cents for cap in enabled_capabilities)


def get_environment_info() -> Dict[str, Union[str, bool, List[str]]]:
    """
    Get information about the current environment configuration.

    Returns:
        Dictionary with environment configuration details
    """
    environment = get_deployment_environment()

    # Check API availability
    available_apis = [api for api in API_CONFIGS if is_api_available(api)]
    unavailable_apis = [api for api in API_CONFIGS if not is_api_available(api)]

    # Check fallback availability
    fallback_apis = [
        api
        for api, config in API_CONFIGS.items()
        if config.fallback_available and not is_api_available(api)
    ]

    return {
        "environment": environment.value,
        "available_apis": available_apis,
        "unavailable_apis": unavailable_apis,
        "fallback_apis": fallback_apis,
        "budget_tracking_enabled": bool(
            os.getenv("ENABLE_BUDGET_TRACKING", "true").lower() == "true"
        ),
        "cost_optimization_enabled": bool(
            os.getenv("ENABLE_COST_OPTIMIZATION", "true").lower() == "true"
        ),
    }


def validate_environment_configuration() -> Dict[str, Union[bool, List[str]]]:
    """
    Validate the current environment configuration and identify issues.

    Returns:
        Dictionary with validation results and recommendations
    """
    environment = get_deployment_environment()
    issues = []
    warnings = []
    recommendations = []

    # Check essential capabilities
    essential_nodes = [NodeType.ENRICH, NodeType.FINAL_OUTPUT]
    for node_type in essential_nodes:
        essential_caps = get_capabilities_by_tier(CapabilityTier.ESSENTIAL, node_type)
        enabled_caps = get_enabled_capabilities(node_type, environment=environment)

        missing_essential = [cap for cap in essential_caps if cap not in enabled_caps]
        if missing_essential:
            issues.append(
                f"Missing essential capabilities for {node_type.value}: {[c.name for c in missing_essential]}"
            )

    # Check high-value capabilities for audit environment
    if environment == DeploymentEnvironment.PRODUCTION_AUDIT:
        audit_caps = get_capabilities_by_tier(
            CapabilityTier.HIGH_VALUE, NodeType.ENRICH
        )
        enabled_audit_caps = [
            cap
            for cap in audit_caps
            if is_capability_enabled_for_environment(cap, environment)
        ]

        if not enabled_audit_caps:
            warnings.append(
                "No high-value audit capabilities enabled in audit environment"
            )
            recommendations.append(
                "Consider enabling SEMrush site audit for better audit lead identification"
            )

    # Check cost optimization
    if environment == DeploymentEnvironment.DEVELOPMENT:
        expensive_caps = []
        for node_type in [NodeType.ENRICH, NodeType.FINAL_OUTPUT]:
            caps = get_enabled_capabilities(node_type, environment=environment)
            expensive_caps.extend(
                [cap for cap in caps if cap.cost_estimate_cents > 1.0]
            )

        if expensive_caps:
            warnings.append(
                f"Expensive capabilities enabled in development: {[c.name for c in expensive_caps]}"
            )
            recommendations.append(
                "Consider disabling expensive capabilities in development environment"
            )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
    }
