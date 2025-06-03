"""
Tests for the capabilities CLI interface.

This module tests the command-line interface for managing node capabilities
in the LeadFactory pipeline.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadfactory.cli.capabilities import capabilities
from leadfactory.config.node_config import (
    NodeType,
    get_capability_registry,
    set_capability_override,
)


class TestCapabilitiesCLI:
    """Test the capabilities CLI commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        # Clear any existing overrides
        registry = get_capability_registry()
        registry._capability_overrides.clear()

    def teardown_method(self):
        """Clean up after tests."""
        registry = get_capability_registry()
        registry._capability_overrides.clear()

    @patch('leadfactory.config.node_config.is_api_available')
    def test_list_command_table_format(self, mock_api_available):
        """Test the list command with table format."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['list', '--format', 'table'])

        assert result.exit_code == 0
        assert "Final Output" in result.output
        assert "mockup_generation" in result.output
        assert "email_generation" in result.output

    @patch('leadfactory.config.node_config.is_api_available')
    def test_list_command_json_format(self, mock_api_available):
        """Test the list command with JSON format."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['list', '--format', 'json'])

        assert result.exit_code == 0

        # Parse JSON output
        output_data = json.loads(result.output)
        assert "final_output" in output_data
        assert "node_name" in output_data["final_output"]
        assert "capabilities" in output_data["final_output"]

    @patch('leadfactory.config.node_config.is_api_available')
    def test_list_command_specific_node(self, mock_api_available):
        """Test the list command for a specific node type."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['list', '--node-type', 'final_output'])

        assert result.exit_code == 0
        assert "Final Output" in result.output
        assert "mockup_generation" in result.output

    def test_status_command_existing_capability(self):
        """Test the status command for an existing capability."""
        result = self.runner.invoke(capabilities, ['status', 'final_output', 'mockup_generation'])

        assert result.exit_code == 0
        assert "mockup_generation" in result.output
        assert "Description:" in result.output
        assert "Cost:" in result.output

    def test_status_command_nonexistent_capability(self):
        """Test the status command for a non-existent capability."""
        result = self.runner.invoke(capabilities, ['status', 'final_output', 'nonexistent'])

        assert result.exit_code == 0
        assert "not found" in result.output

    def test_override_command_enable(self):
        """Test the override command to enable a capability."""
        result = self.runner.invoke(capabilities, [
            'override', 'final_output', 'mockup_generation', 'true',
            '--reason', 'Test enable'
        ])

        assert result.exit_code == 0
        assert "Override set" in result.output
        assert "✅" in result.output

        # Verify override was set
        registry = get_capability_registry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is True
        assert override.reason == "Test enable"

    def test_override_command_disable(self):
        """Test the override command to disable a capability."""
        result = self.runner.invoke(capabilities, [
            'override', 'final_output', 'mockup_generation', 'false',
            '--reason', 'Test disable'
        ])

        assert result.exit_code == 0
        assert "Override set" in result.output
        assert "❌" in result.output

        # Verify override was set
        registry = get_capability_registry()
        override = registry.get_override(NodeType.FINAL_OUTPUT, "mockup_generation")
        assert override is not None
        assert override.enabled is False

    def test_override_command_invalid_capability(self):
        """Test the override command with invalid capability."""
        result = self.runner.invoke(capabilities, [
            'override', 'final_output', 'nonexistent', 'true'
        ])

        assert result.exit_code == 0
        assert "Failed to set override" in result.output

    @patch('leadfactory.config.node_config.is_api_available')
    def test_estimate_command_all_nodes(self, mock_api_available):
        """Test the estimate command for all nodes."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['estimate'])

        assert result.exit_code == 0
        assert "final_output:" in result.output
        assert "cents" in result.output
        assert "Total estimated cost:" in result.output

    @patch('leadfactory.config.node_config.is_api_available')
    def test_estimate_command_specific_node(self, mock_api_available):
        """Test the estimate command for a specific node."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['estimate', '--node-type', 'final_output'])

        assert result.exit_code == 0
        assert "final_output:" in result.output
        assert "cents" in result.output

    @patch('leadfactory.config.node_config.is_api_available')
    def test_estimate_command_with_budget(self, mock_api_available):
        """Test the estimate command with budget constraint."""
        mock_api_available.return_value = True

        result = self.runner.invoke(capabilities, ['estimate', '--budget', '5.0'])

        assert result.exit_code == 0
        assert "cents" in result.output

    @patch.dict(os.environ, {"MOCKUP_ENABLED": "false"})
    def test_migrate_command_mockup_disabled(self):
        """Test the migrate command with MOCKUP_ENABLED=false."""
        result = self.runner.invoke(capabilities, ['migrate'])

        assert result.exit_code == 0
        assert "Migrating from legacy configuration" in result.output
        assert "Found MOCKUP_ENABLED=false" in result.output
        assert "Set mockup_generation to False" in result.output
        assert "Migration complete!" in result.output

    @patch.dict(os.environ, {"MOCKUP_ENABLED": "true"})
    def test_migrate_command_mockup_enabled(self):
        """Test the migrate command with MOCKUP_ENABLED=true."""
        result = self.runner.invoke(capabilities, ['migrate'])

        assert result.exit_code == 0
        assert "Found MOCKUP_ENABLED=true" in result.output
        assert "Set mockup_generation to True" in result.output

    @patch.dict(os.environ, {"TIER": "1"})
    def test_migrate_command_tier_1(self):
        """Test the migrate command with TIER=1."""
        result = self.runner.invoke(capabilities, ['migrate'])

        assert result.exit_code == 0
        assert "Found TIER=1" in result.output
        assert "Disabled expensive capabilities for Tier 1" in result.output

    @patch.dict(os.environ, {"TIER": "2"})
    def test_migrate_command_tier_2(self):
        """Test the migrate command with TIER=2."""
        result = self.runner.invoke(capabilities, ['migrate'])

        assert result.exit_code == 0
        assert "Found TIER=2" in result.output
        assert "Enabled full capabilities for Tier 2" in result.output

    @patch.dict(os.environ, {}, clear=True)
    def test_migrate_command_no_legacy_config(self):
        """Test the migrate command with no legacy configuration."""
        result = self.runner.invoke(capabilities, ['migrate'])

        assert result.exit_code == 0
        assert "No legacy configuration found" in result.output
        assert "Migration complete!" in result.output


class TestCapabilitiesCLIIntegration:
    """Test CLI integration with the capability system."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        # Clear any existing overrides
        registry = get_capability_registry()
        registry._capability_overrides.clear()

    def teardown_method(self):
        """Clean up after tests."""
        registry = get_capability_registry()
        registry._capability_overrides.clear()

    @patch('leadfactory.config.node_config.is_api_available')
    def test_end_to_end_capability_management(self, mock_api_available):
        """Test end-to-end capability management workflow."""
        mock_api_available.return_value = True

        # 1. List capabilities initially
        result = self.runner.invoke(capabilities, ['list', '--node-type', 'final_output'])
        assert result.exit_code == 0
        assert "✅ Enabled" in result.output  # Should be enabled by default

        # 2. Disable mockup generation
        result = self.runner.invoke(capabilities, [
            'override', 'final_output', 'mockup_generation', 'false',
            '--reason', 'Cost optimization'
        ])
        assert result.exit_code == 0
        assert "Override set" in result.output

        # 3. Check status shows disabled
        result = self.runner.invoke(capabilities, ['status', 'final_output', 'mockup_generation'])
        assert result.exit_code == 0
        assert "Override Active" in result.output
        assert "Enabled: False" in result.output

        # 4. List should now show disabled
        result = self.runner.invoke(capabilities, ['list', '--node-type', 'final_output'])
        assert result.exit_code == 0
        # Note: The exact output depends on whether APIs are available

        # 5. Re-enable capability
        result = self.runner.invoke(capabilities, [
            'override', 'final_output', 'mockup_generation', 'true',
            '--reason', 'Re-enabled for testing'
        ])
        assert result.exit_code == 0

        # 6. Verify it's enabled again
        result = self.runner.invoke(capabilities, ['status', 'final_output', 'mockup_generation'])
        assert result.exit_code == 0
        assert "Enabled: True" in result.output

    def test_invalid_node_type_handling(self):
        """Test handling of invalid node types."""
        result = self.runner.invoke(capabilities, ['list', '--node-type', 'invalid_node'])

        # Should fail with invalid choice
        assert result.exit_code != 0

    def test_invalid_capability_handling(self):
        """Test handling of invalid capability names."""
        result = self.runner.invoke(capabilities, ['status', 'final_output', 'invalid_capability'])

        assert result.exit_code == 0
        assert "not found" in result.output


if __name__ == "__main__":
    pytest.main([__file__])
