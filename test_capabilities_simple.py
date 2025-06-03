#!/usr/bin/env python3
"""
Simple test script for node capabilities without pytest dependencies.
"""

import json
import os
import sys
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_capability_registry():
    """Test the capability registry functionality."""
    print("Testing capability registry...")

    from leadfactory.config.node_config import (
        CapabilityRegistry,
        NodeType,
        get_capability_registry,
    )

    # Test getting the singleton registry
    registry = get_capability_registry()
    assert registry is not None
    print("✅ Registry initialization works")

    # Clear any existing overrides for clean test
    registry._capability_overrides.clear()

    # Test adding override
    registry.add_override(
        NodeType.FINAL_OUTPUT, "mockup_generation", False, "Test override"
    )

    override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
    assert override is not None
    assert override.capability_name == "mockup_generation"
    assert override.enabled is False
    print("✅ Override functionality works")

    # Test singleton pattern
    registry2 = get_capability_registry()
    override2 = registry2.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
    assert override2 is not None
    assert override2.reason == "Test override"
    print("✅ Singleton pattern works")


def test_capability_functions():
    """Test capability management functions."""
    print("Testing capability functions...")

    from leadfactory.config.node_config import (
        NodeType,
        estimate_node_cost,
        get_capability_registry,
        get_capability_status,
        get_enabled_capabilities,
        set_capability_override,
    )

    # Clear registry for clean test
    registry = get_capability_registry()
    registry._capability_overrides.clear()

    # Test getting capabilities
    with patch("leadfactory.config.node_config.is_api_available", return_value=True):
        capabilities = get_enabled_capabilities(NodeType.FINAL_OUTPUT)
        print(
            f"Found {len(capabilities)} capabilities: {[cap.name for cap in capabilities]}"
        )
        assert len(capabilities) >= 2  # Should have mockup and email
        print("✅ get_enabled_capabilities works")

        # Test cost estimation
        cost = estimate_node_cost(NodeType.FINAL_OUTPUT)
        assert cost >= 0
        print("✅ estimate_node_cost works")

    # Test capability status
    status = get_capability_status(NodeType.FINAL_OUTPUT, "mockup_generation")
    assert status["exists"] is True
    assert status["name"] == "mockup_generation"
    print("✅ get_capability_status works")

    # Test setting override
    success = set_capability_override(
        NodeType.FINAL_OUTPUT, "mockup_generation", True, "Test enable"
    )
    assert success is True
    print("✅ set_capability_override works")


def test_legacy_migration():
    """Test legacy configuration migration."""
    print("Testing legacy migration...")

    from leadfactory.config.node_config import (
        NodeType,
        get_capability_registry,
    )

    # Get the singleton registry and clear it
    registry = get_capability_registry()
    registry._capability_overrides.clear()

    # Test MOCKUP_ENABLED=false
    with patch.dict(os.environ, {"MOCKUP_ENABLED": "false"}, clear=True):
        # Re-initialize the registry to pick up environment changes
        registry._load_env_overrides()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is False
        print(f"Override reason: {override.reason}")
        assert "Legacy MOCKUP_ENABLED=false" in override.reason
        print("✅ MOCKUP_ENABLED=false migration works")

    # Clear registry for next test
    registry._capability_overrides.clear()

    # Test TIER=1
    with patch.dict(os.environ, {"TIER": "1"}, clear=True):
        # Re-initialize the registry to pick up environment changes
        registry._load_env_overrides()
        mockup_override = registry.get_override(
            NodeType.FINAL_OUTPUT, "mockup_generation"
        )
        assert mockup_override is not None
        assert mockup_override.enabled is False
        assert "Tier 1" in mockup_override.reason
        print("✅ TIER=1 migration works")


def test_unified_gpt4o_integration():
    """Test integration with unified GPT-4o node."""
    print("Testing unified GPT-4o integration...")

    from leadfactory.config.node_config import (
        NodeType,
        set_capability_override,
    )

    try:
        from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

        # Test business data
        business_data = {
            "id": 1,
            "name": "Test Business",
            "website": "https://example.com",
            "description": "Test description",
            "contact_email": "test@example.com",
        }

        with patch(
            "leadfactory.config.node_config.is_api_available", return_value=True
        ):
            # Create node instance
            node = UnifiedGPT4ONode()

            # Generate content with default capabilities
            result = node.generate_unified_content(business_data)

            assert result["success"] is True
            assert "content" in result
            print("✅ Unified GPT-4o integration works")

            # Test with disabled mockup
            set_capability_override(
                NodeType.FINAL_OUTPUT, "mockup_generation", False, "Test disable"
            )

            result2 = node.generate_unified_content(business_data)
            assert result2["success"] is True
            content = result2["content"]
            assert content["metadata"]["mockup_generated"] is False
            print("✅ Capability override affects content generation")

    except ImportError as e:
        print(f"⚠️  Unified GPT-4o integration test skipped due to import error: {e}")


def main():
    """Run all tests."""
    print("Running Node Capability Tests")
    print("=" * 50)

    try:
        test_capability_registry()
        print()

        test_capability_functions()
        print()

        test_legacy_migration()
        print()

        test_unified_gpt4o_integration()
        print()

        print("=" * 50)
        print("✅ All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
