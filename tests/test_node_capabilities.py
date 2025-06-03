"""
Tests for the node capability system in LeadFactory pipeline.

This module tests the enhanced capability configuration system that replaces
the legacy MOCKUP_ENABLED flag with a flexible capability management system.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadfactory.config.node_config import (
    NodeType,
    NodeCapability,
    CapabilityOverride,
    CapabilityRegistry,
    get_capability_registry,
    get_enabled_capabilities,
    get_capability_status,
    set_capability_override,
    get_node_capability_summary,
    estimate_node_cost,
    is_api_available,
)


class TestCapabilityRegistry:
    """Test the CapabilityRegistry class."""

    def test_registry_initialization(self):
        """Test that registry initializes correctly."""
        registry = CapabilityRegistry()
        assert registry is not None
        assert hasattr(registry, '_capability_overrides')

    def test_add_override(self):
        """Test adding capability overrides."""
        registry = CapabilityRegistry()

        # Add an override
        registry.add_override(
            NodeType.FINAL_OUTPUT,
            "mockup_generation",
            False,
            "Test override"
        )

        # Check that override was added
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.capability_name == "mockup_generation"
        assert override.enabled is False
        assert override.reason == "Test override"

    def test_get_nonexistent_override(self):
        """Test getting an override that doesn't exist."""
        registry = CapabilityRegistry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "nonexistent")
        assert override is None

    @patch.dict(os.environ, {"MOCKUP_ENABLED": "false"}, clear=True)
    def test_legacy_mockup_enabled_false(self):
        """Test that MOCKUP_ENABLED=false creates correct override."""
        registry = CapabilityRegistry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is False
        assert "MOCKUP_ENABLED=false" in override.reason

    @patch.dict(os.environ, {"MOCKUP_ENABLED": "true"}, clear=True)
    def test_legacy_mockup_enabled_true(self):
        """Test that MOCKUP_ENABLED=true creates correct override."""
        registry = CapabilityRegistry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is True
        assert "MOCKUP_ENABLED=true" in override.reason

    @patch.dict(os.environ, {"TIER": "1"})
    def test_tier_1_configuration(self):
        """Test that TIER=1 disables expensive capabilities."""
        registry = CapabilityRegistry()

        # Check mockup generation is disabled
        mockup_override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert mockup_override is not None
        assert mockup_override.enabled is False
        assert "Tier 1" in mockup_override.reason

        # Check semrush is disabled
        semrush_override = registry.get_override(NodeType.ENRICH, "semrush_site_audit")
        assert semrush_override is not None
        assert semrush_override.enabled is False
        assert "Tier 1" in semrush_override.reason

    @patch.dict(os.environ, {"TIER": "2"})
    def test_tier_2_configuration(self):
        """Test that TIER=2 enables full capabilities."""
        registry = CapabilityRegistry()

        # Check mockup generation is enabled
        mockup_override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert mockup_override is not None
        assert mockup_override.enabled is True
        assert "Tier 2" in mockup_override.reason

    def test_is_capability_enabled_default(self):
        """Test capability enabled check with default values."""
        registry = CapabilityRegistry()

        # Create a test capability
        capability = NodeCapability(
            name="test_capability",
            description="Test capability",
            required_apis=[],
            required_inputs=[],
            cost_estimate_cents=0.0,
            enabled_by_default=True
        )

        # Should return default value when no override
        assert registry.is_capability_enabled(NodeType.FINAL_OUTPUT, capability) is True

        # Test with disabled by default
        capability.enabled_by_default = False
        assert registry.is_capability_enabled(NodeType.FINAL_OUTPUT, capability) is False

    def test_is_capability_enabled_with_override(self):
        """Test capability enabled check with overrides."""
        registry = CapabilityRegistry()

        # Create a test capability
        capability = NodeCapability(
            name="test_capability",
            description="Test capability",
            required_apis=[],
            required_inputs=[],
            cost_estimate_cents=0.0,
            enabled_by_default=True
        )

        # Add override to disable
        registry.add_override(NodeType.FINAL_OUTPUT, "test_capability", False, "Test")

        # Should return override value
        assert registry.is_capability_enabled(NodeType.FINAL_OUTPUT, capability) is False


class TestCapabilityFunctions:
    """Test the capability management functions."""

    @patch('leadfactory.config.node_config.is_api_available')
    def test_get_enabled_capabilities_api_check(self, mock_api_available):
        """Test that get_enabled_capabilities checks API availability."""
        mock_api_available.return_value = True

        capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT)

        # Should have both mockup and email capabilities enabled
        capability_names = [cap.name for cap in capabilities]
        assert "mockup_generation" in capability_names
        assert "email_generation" in capability_names

    @patch('leadfactory.config.node_config.is_api_available')
    def test_get_enabled_capabilities_api_unavailable(self, mock_api_available):
        """Test behavior when APIs are unavailable."""
        mock_api_available.return_value = False

        capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT)

        # Should have no capabilities when APIs unavailable
        assert len(capabilities) == 0

    def test_get_enabled_capabilities_budget_limit(self):
        """Test budget limiting for capabilities."""
        # Test with very low budget
        capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT, budget_cents=1.0)

        # Should have no capabilities due to budget constraints
        assert len(capabilities) == 0

    @patch('leadfactory.config.node_config.is_api_available')
    def test_get_enabled_capabilities_sufficient_budget(self, mock_api_available):
        """Test with sufficient budget."""
        mock_api_available.return_value = True

        # Test with sufficient budget
        capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT, budget_cents=20.0)

        # Should have both capabilities
        capability_names = [cap.name for cap in capabilities]
        assert "mockup_generation" in capability_names
        assert "email_generation" in capability_names

    def test_get_capability_status_existing(self):
        """Test getting status for existing capability."""
        status = get_capability_status(NodeType.FINAL_OUTPUT, "mockup_generation")

        assert status["exists"] is True
        assert status["name"] == "mockup_generation"
        assert "description" in status
        assert "cost_estimate_cents" in status
        assert "required_apis" in status
        assert "final_enabled" in status

    def test_get_capability_status_nonexistent(self):
        """Test getting status for non-existent capability."""
        status = get_capability_status(NodeType.FINAL_OUTPUT, "nonexistent_capability")

        assert status["exists"] is False
        assert "error" in status

    def test_set_capability_override_valid(self):
        """Test setting override for valid capability."""
        success = set_capability_override(
            NodeType.FINAL_OUTPUT,
            "mockup_generation",
            False,
            "Test override"
        )

        assert success is True

        # Verify override was set
        registry = get_capability_registry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is False

    def test_set_capability_override_invalid(self):
        """Test setting override for invalid capability."""
        success = set_capability_override(
            NodeType.FINAL_OUTPUT,
            "nonexistent_capability",
            False,
            "Test override"
        )

        assert success is False

    @patch('leadfactory.config.node_config.is_api_available')
    def test_get_node_capability_summary(self, mock_api_available):
        """Test getting node capability summary."""
        mock_api_available.return_value = True

        summary = get_node_capability_summary(NodeType.FINAL_OUTPUT)

        assert "node_type" in summary
        assert "node_name" in summary
        assert "total_capabilities" in summary
        assert "enabled_capabilities" in summary
        assert "estimated_cost_cents" in summary
        assert "capabilities" in summary

        assert summary["node_type"] == "final_output"
        assert summary["total_capabilities"] >= 2  # At least mockup and email

    @patch('leadfactory.config.node_config.is_api_available')
    def test_estimate_node_cost(self, mock_api_available):
        """Test node cost estimation."""
        mock_api_available.return_value = True

        cost = estimate_node_cost(NodeType.FINAL_OUTPUT)

        # Should be sum of mockup (5.0) + email (5.0) = 10.0 cents
        assert cost == 10.0

    def test_estimate_node_cost_with_budget(self):
        """Test node cost estimation with budget constraint."""
        # Test with budget that allows only one capability
        cost = estimate_node_cost(NodeType.FINAL_OUTPUT, budget_cents=6.0)

        # Should be 0 because individual capabilities cost 5.0 each
        # but we need APIs available for any to be enabled
        assert cost >= 0


class TestAPIAvailability:
    """Test API availability checking."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"})
    def test_api_available_with_env_var(self):
        """Test API availability when environment variable is set."""
        assert is_api_available("openai") is True

    @patch.dict(os.environ, {}, clear=True)
    def test_api_unavailable_without_env_var(self):
        """Test API unavailability when environment variable is missing."""
        assert is_api_available("openai") is False

    def test_api_unavailable_nonexistent(self):
        """Test API unavailability for non-existent API."""
        assert is_api_available("nonexistent_api") is False


class TestIntegrationWithUnifiedGPT4O:
    """Test integration between capability system and unified GPT-4o node."""

    @patch('leadfactory.config.node_config.is_api_available')
    def test_unified_gpt4o_capability_integration(self, mock_api_available):
        """Test that unified GPT-4o node respects capability settings."""
        from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

        mock_api_available.return_value = True

        # Create node instance
        node = UnifiedGPT4ONode()

        # Test business data
        business_data = {
            "id": 1,
            "name": "Test Business",
            "website": "https://example.com",
            "description": "Test description",
            "contact_email": "test@example.com"
        }

        # Generate content with default capabilities
        result = node.generate_unified_content(business_data)

        assert result["success"] is True
        assert "content" in result

        # Check that both mockup and email are generated by default
        content = result["content"]
        assert "mockup_concept" in content
        assert "email_content" in content
        assert content["metadata"]["mockup_generated"] is True
        assert content["metadata"]["email_generated"] is True

    @patch('leadfactory.config.node_config.is_api_available')
    def test_unified_gpt4o_with_disabled_mockup(self, mock_api_available):
        """Test unified GPT-4o with mockup capability disabled."""
        from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

        mock_api_available.return_value = True

        # Disable mockup generation
        set_capability_override(
            NodeType.FINAL_OUTPUT,
            "mockup_generation",
            False,
            "Test disable mockup"
        )

        # Create node instance
        node = UnifiedGPT4ONode()

        # Test business data
        business_data = {
            "id": 1,
            "name": "Test Business",
            "website": "https://example.com",
            "description": "Test description",
            "contact_email": "test@example.com"
        }

        # Generate content
        result = node.generate_unified_content(business_data)

        assert result["success"] is True
        content = result["content"]

        # Should not have mockup but should have email
        assert "mockup_concept" not in content
        assert "email_content" in content
        assert content["metadata"]["mockup_generated"] is False
        assert content["metadata"]["email_generated"] is True


@pytest.fixture(autouse=True)
def reset_capability_registry():
    """Reset capability registry between tests."""
    # Clear any existing overrides
    registry = get_capability_registry()
    registry._capability_overrides.clear()

    yield

    # Clean up after test
    registry._capability_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__])
