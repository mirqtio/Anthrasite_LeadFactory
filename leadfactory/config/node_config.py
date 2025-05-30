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


@dataclass
class NodeCapability:
    """Defines a capability that can be enabled/disabled for a node."""

    name: str
    description: str
    required_apis: List[str]
    required_inputs: List[str]  # Input data required for this capability
    cost_estimate_cents: float
    enabled_by_default: bool = True


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
    ),
    "pagespeed": APIConfiguration(
        name="PageSpeed Insights",
        required_env_vars=["PAGESPEED_API_KEY"],
        cost_per_request=0.0,  # Free API
        description="Core Web Vitals and performance metrics",
        enabled_by_default=True,
        requires_budget=False,
    ),
    "screenshot_one": APIConfiguration(
        name="ScreenshotOne",
        required_env_vars=["SCREENSHOT_ONE_API_KEY", "SCREENSHOT_ONE_KEY"],
        cost_per_request=1.0,  # 1 cent per screenshot
        description="Website screenshot capture service",
        enabled_by_default=True,
        requires_budget=True,
    ),
    "semrush": APIConfiguration(
        name="SEMrush",
        required_env_vars=["SEMRUSH_API_KEY", "SEMRUSH_KEY"],
        cost_per_request=10.0,  # 10 cents per site audit
        description="SEMrush Site Audit for comprehensive SEO analysis",
        enabled_by_default=False,  # Expensive, opt-in
        requires_budget=True,
    ),
    "openai": APIConfiguration(
        name="OpenAI",
        required_env_vars=["OPENAI_API_KEY"],
        cost_per_request=5.0,  # 5 cents per AI generation request
        description="AI-powered content generation",
        enabled_by_default=True,
        requires_budget=True,
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
    ),
    NodeCapability(
        name="core_web_vitals",
        description="Analyze Core Web Vitals and performance metrics",
        required_apis=["pagespeed"],
        required_inputs=["website"],
        cost_estimate_cents=0.0,
        enabled_by_default=True,
    ),
    NodeCapability(
        name="screenshot_capture",
        description="Capture website screenshot",
        required_apis=["screenshot_one"],
        required_inputs=["website"],
        cost_estimate_cents=1.0,
        enabled_by_default=True,
    ),
    NodeCapability(
        name="semrush_site_audit",
        description="Comprehensive SEO analysis using SEMrush",
        required_apis=["semrush"],
        required_inputs=["website"],
        cost_estimate_cents=10.0,
        enabled_by_default=False,
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
    ),
    NodeCapability(
        name="email_generation",
        description="Generate personalized email using GPT-4o",
        required_apis=["openai"],
        required_inputs=["website", "name"],
        cost_estimate_cents=5.0,
        enabled_by_default=True,
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


def get_enabled_capabilities(
    node_type: NodeType, budget_cents: Optional[float] = None
) -> List[NodeCapability]:
    """
    Get enabled capabilities for a node based on API availability and budget.

    Args:
        node_type: The type of node to get capabilities for
        budget_cents: Available budget in cents (None = unlimited)

    Returns:
        List of enabled capabilities
    """
    node_config = get_node_config(node_type)
    enabled_capabilities = []

    for capability in node_config.capabilities:
        # Check if all required APIs are available
        apis_available = all(is_api_available(api) for api in capability.required_apis)

        # Check budget if required
        budget_ok = True
        if budget_cents is not None and capability.cost_estimate_cents > 0:
            budget_ok = budget_cents >= capability.cost_estimate_cents

        # Enable if APIs available, budget ok, and enabled by default
        if apis_available and budget_ok and capability.enabled_by_default:
            enabled_capabilities.append(capability)

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
    node_type: NodeType, budget_cents: Optional[float] = None
) -> float:
    """
    Estimate the cost of running a node with enabled capabilities.

    Args:
        node_type: The type of node to estimate cost for
        budget_cents: Available budget in cents

    Returns:
        Estimated cost in cents
    """
    enabled_capabilities = get_enabled_capabilities(node_type, budget_cents)
    return sum(cap.cost_estimate_cents for cap in enabled_capabilities)
