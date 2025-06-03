"""
Node capability configuration for LeadFactory pipeline processing.

This module defines the node-based processing configuration that determines
which capabilities are available for each pipeline node, replacing the
tier-based system with dynamic dependency evaluation.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


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
    priority: int = (
        1  # Higher priority capabilities are preferred when budget is limited
    )
    fallback_capability: Optional[str] = None  # Fallback if this capability can't run


@dataclass
class CapabilityOverride:
    """Override configuration for specific capabilities."""

    capability_name: str
    enabled: bool
    reason: str = ""
    environment_condition: Optional[str] = None  # e.g., "TIER=1" or "E2E_MODE=true"


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
    capability_overrides: List[CapabilityOverride] = field(default_factory=list)


class CapabilityRegistry:
    """Registry for managing node capabilities and their configurations."""

    def __init__(self):
        self._capability_overrides: Dict[str, Dict[str, CapabilityOverride]] = {}
        self._load_configuration()

    def _load_configuration(self):
        """Load capability configuration from environment and config files."""
        # Load from environment variables
        self._load_env_overrides()

        # Load from configuration file if it exists
        config_path = Path("config/capabilities.json")
        if config_path.exists():
            self._load_config_file(config_path)

    def _load_env_overrides(self):
        """Load capability overrides from environment variables."""
        # Handle legacy MOCKUP_ENABLED flag
        mockup_enabled = os.getenv("MOCKUP_ENABLED", "").lower()
        if mockup_enabled in ("true", "false"):
            enabled = mockup_enabled == "true"
            self.add_override(
                NodeType.FINAL_OUTPUT,
                "mockup_generation",
                enabled,
                f"Legacy MOCKUP_ENABLED={mockup_enabled} environment variable",
            )

        # Handle tier-based configuration
        tier = os.getenv("TIER", "")
        if tier == "1":
            # Tier 1: Disable expensive capabilities
            self.add_override(
                NodeType.FINAL_OUTPUT,
                "mockup_generation",
                False,
                "Tier 1 configuration - cost optimization",
            )
            self.add_override(
                NodeType.ENRICH,
                "semrush_site_audit",
                False,
                "Tier 1 configuration - cost optimization",
            )
        elif tier in ("2", "3"):
            # Tier 2/3: Enable all capabilities
            self.add_override(
                NodeType.FINAL_OUTPUT,
                "mockup_generation",
                True,
                f"Tier {tier} configuration - full feature set",
            )

    def _load_config_file(self, config_path: Path):
        """Load capability configuration from JSON file."""
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)

            for node_type_str, capabilities in config_data.get(
                "capabilities", {}
            ).items():
                try:
                    node_type = NodeType(node_type_str)
                    for cap_name, cap_config in capabilities.items():
                        self.add_override(
                            node_type,
                            cap_name,
                            cap_config.get("enabled", True),
                            cap_config.get("reason", "Configuration file override"),
                        )
                except ValueError:
                    continue  # Skip invalid node types
        except (json.JSONDecodeError, FileNotFoundError):
            pass  # Ignore config file errors

    def add_override(
        self, node_type: NodeType, capability_name: str, enabled: bool, reason: str = ""
    ):
        """Add a capability override for a specific node type."""
        if node_type.value not in self._capability_overrides:
            self._capability_overrides[node_type.value] = {}

        self._capability_overrides[node_type.value][capability_name] = (
            CapabilityOverride(
                capability_name=capability_name, enabled=enabled, reason=reason
            )
        )

    def get_override(
        self, node_type: NodeType, capability_name: str
    ) -> Optional[CapabilityOverride]:
        """Get capability override for a specific node type and capability."""
        return self._capability_overrides.get(node_type.value, {}).get(capability_name)

    def is_capability_enabled(
        self, node_type: NodeType, capability: NodeCapability
    ) -> bool:
        """Check if a capability is enabled, considering overrides."""
        override = self.get_override(node_type, capability.name)
        if override:
            return override.enabled
        return capability.enabled_by_default


# Global capability registry instance
_capability_registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    """Get the global capability registry instance."""
    return _capability_registry


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
    NodeType.SCREENSHOT: NodeConfiguration(
        node_type=NodeType.SCREENSHOT,
        name="Screenshot",
        description="Capture website screenshots",
        capabilities=[],  # No optional capabilities
        required_inputs=["website"],
        optional_inputs=[],
        output_keys=["screenshot_url"],
    ),
    NodeType.MOCKUP: NodeConfiguration(
        node_type=NodeType.MOCKUP,
        name="Mockup",
        description="Generate PNG mockup using GPT-4o",
        capabilities=[],  # No optional capabilities
        required_inputs=["website", "name"],
        optional_inputs=["tech_stack", "performance_metrics"],
        output_keys=["mockup_url"],
    ),
    NodeType.EMAIL: NodeConfiguration(
        node_type=NodeType.EMAIL,
        name="Email",
        description="Generate personalized email using GPT-4o",
        capabilities=[],  # No optional capabilities
        required_inputs=["website", "name"],
        optional_inputs=["tech_stack", "performance_metrics", "mockup_url"],
        output_keys=["email_content"],
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
    registry = get_capability_registry()

    for capability in node_config.capabilities:
        # Check if all required APIs are available
        apis_available = all(is_api_available(api) for api in capability.required_apis)

        # Check budget if required
        budget_ok = True
        if budget_cents is not None and capability.cost_estimate_cents > 0:
            budget_ok = budget_cents >= capability.cost_estimate_cents

        # Check capability registry for overrides
        capability_enabled = registry.is_capability_enabled(node_type, capability)

        # Enable if APIs available, budget ok, and capability is enabled
        if apis_available and budget_ok and capability_enabled:
            enabled_capabilities.append(capability)

    return enabled_capabilities


def get_capability_status(node_type: NodeType, capability_name: str) -> Dict[str, Any]:
    """
    Get detailed status information for a specific capability.

    Args:
        node_type: The type of node
        capability_name: Name of the capability to check

    Returns:
        Dictionary with capability status details
    """
    node_config = get_node_config(node_type)
    registry = get_capability_registry()

    # Find the capability
    capability = None
    for cap in node_config.capabilities:
        if cap.name == capability_name:
            capability = cap
            break

    if not capability:
        return {
            "exists": False,
            "error": f"Capability '{capability_name}' not found for node type '{node_type.value}'",
        }

    # Check API availability
    apis_status = {}
    for api_name in capability.required_apis:
        apis_status[api_name] = {
            "available": is_api_available(api_name),
            "config": API_CONFIGS.get(api_name, {}),
        }

    # Check override status
    override = registry.get_override(node_type, capability_name)

    return {
        "exists": True,
        "name": capability.name,
        "description": capability.description,
        "enabled_by_default": capability.enabled_by_default,
        "cost_estimate_cents": capability.cost_estimate_cents,
        "priority": capability.priority,
        "required_apis": capability.required_apis,
        "apis_status": apis_status,
        "override": (
            {
                "active": override is not None,
                "enabled": override.enabled if override else None,
                "reason": override.reason if override else None,
            }
            if override
            else None
        ),
        "final_enabled": registry.is_capability_enabled(node_type, capability),
    }


def set_capability_override(
    node_type: NodeType, capability_name: str, enabled: bool, reason: str = ""
) -> bool:
    """
    Set a capability override for runtime configuration.

    Args:
        node_type: The type of node
        capability_name: Name of the capability
        enabled: Whether to enable or disable the capability
        reason: Reason for the override

    Returns:
        True if override was set successfully
    """
    registry = get_capability_registry()

    # Verify capability exists
    node_config = get_node_config(node_type)
    capability_exists = any(
        cap.name == capability_name for cap in node_config.capabilities
    )

    if not capability_exists:
        return False

    registry.add_override(node_type, capability_name, enabled, reason)
    return True


def get_node_capability_summary(node_type: NodeType) -> Dict[str, Any]:
    """
    Get a summary of all capabilities for a node type.

    Args:
        node_type: The type of node

    Returns:
        Dictionary with capability summary
    """
    node_config = get_node_config(node_type)
    registry = get_capability_registry()

    capabilities_summary = []
    total_cost = 0
    enabled_count = 0

    for capability in node_config.capabilities:
        status = get_capability_status(node_type, capability.name)
        capabilities_summary.append(status)

        if status["final_enabled"]:
            enabled_count += 1
            total_cost += capability.cost_estimate_cents

    return {
        "node_type": node_type.value,
        "node_name": node_config.name,
        "total_capabilities": len(node_config.capabilities),
        "enabled_capabilities": enabled_count,
        "estimated_cost_cents": total_cost,
        "capabilities": capabilities_summary,
    }


def estimate_node_cost(
    node_type: NodeType, budget_cents: Optional[float] = None
) -> float:
    """
    Estimate the total cost for running all enabled capabilities of a node.

    Args:
        node_type: The type of node to estimate cost for
        budget_cents: Available budget in cents (None = unlimited)

    Returns:
        Estimated cost in cents
    """
    enabled_capabilities = get_enabled_capabilities(node_type, budget_cents)
    total_cost = sum(cap.cost_estimate_cents for cap in enabled_capabilities)
    return total_cost


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
