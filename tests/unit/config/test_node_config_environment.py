"""
Unit tests for environment-aware NodeCapability configurations.

Tests the new environment detection, capability tier system, and
environment-specific default configurations.
"""

import os
from unittest.mock import patch

import pytest

from leadfactory.config.node_config import (
    ENRICH_CAPABILITIES,
    FINAL_OUTPUT_CAPABILITIES,
    CapabilityTier,
    DeploymentEnvironment,
    NodeType,
    estimate_node_cost,
    get_capabilities_by_tier,
    get_deployment_environment,
    get_enabled_capabilities,
    get_environment_info,
    is_capability_enabled_for_environment,
    validate_environment_configuration,
)


class TestDeploymentEnvironmentDetection:
    """Test deployment environment detection logic."""

    def test_explicit_development_environment(self):
        """Test explicit development environment setting."""
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            assert get_deployment_environment() == DeploymentEnvironment.DEVELOPMENT

    def test_explicit_production_audit_environment(self):
        """Test explicit production audit environment setting."""
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            assert (
                get_deployment_environment() == DeploymentEnvironment.PRODUCTION_AUDIT
            )

    def test_explicit_production_general_environment(self):
        """Test explicit production general environment setting."""
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            assert (
                get_deployment_environment() == DeploymentEnvironment.PRODUCTION_GENERAL
            )

    def test_node_env_fallback(self):
        """Test fallback to NODE_ENV for development detection."""
        with patch.dict(os.environ, {"NODE_ENV": "development"}, clear=True):
            assert get_deployment_environment() == DeploymentEnvironment.DEVELOPMENT

    def test_business_model_fallback(self):
        """Test fallback to BUSINESS_MODEL for audit detection."""
        with patch.dict(os.environ, {"BUSINESS_MODEL": "audit"}, clear=True):
            assert (
                get_deployment_environment() == DeploymentEnvironment.PRODUCTION_AUDIT
            )

    def test_default_environment(self):
        """Test default environment when no indicators present."""
        with patch.dict(os.environ, {}, clear=True):
            assert (
                get_deployment_environment() == DeploymentEnvironment.PRODUCTION_GENERAL
            )

    def test_case_insensitive_detection(self):
        """Test case-insensitive environment detection."""
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "DEVELOPMENT"}):
            assert get_deployment_environment() == DeploymentEnvironment.DEVELOPMENT

    def test_short_form_detection(self):
        """Test short form environment detection."""
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "dev"}):
            assert get_deployment_environment() == DeploymentEnvironment.DEVELOPMENT


class TestCapabilityEnvironmentOverrides:
    """Test capability environment override logic."""

    def test_environment_override_enabled(self):
        """Test capability enabled by environment override."""
        # Find a capability with environment overrides
        screenshot_cap = next(
            cap for cap in ENRICH_CAPABILITIES if cap.name == "screenshot_capture"
        )

        # Should be enabled in production_general due to override
        assert is_capability_enabled_for_environment(
            screenshot_cap, DeploymentEnvironment.PRODUCTION_GENERAL
        )

    def test_environment_override_disabled(self):
        """Test capability disabled by environment override."""
        screenshot_cap = next(
            cap for cap in ENRICH_CAPABILITIES if cap.name == "screenshot_capture"
        )

        # Should be disabled in development due to override
        assert not is_capability_enabled_for_environment(
            screenshot_cap, DeploymentEnvironment.DEVELOPMENT
        )

    def test_fallback_to_default(self):
        """Test fallback to default when no environment override."""
        # Find a capability without environment overrides
        tech_cap = next(
            cap for cap in ENRICH_CAPABILITIES if cap.name == "tech_stack_analysis"
        )

        # Should use default setting (enabled)
        assert is_capability_enabled_for_environment(
            tech_cap, DeploymentEnvironment.DEVELOPMENT
        )

    def test_semrush_audit_environment_enabled(self):
        """Test SEMrush enabled in audit environment."""
        semrush_cap = next(
            cap for cap in ENRICH_CAPABILITIES if cap.name == "semrush_site_audit"
        )

        # Should be enabled in production_audit
        assert is_capability_enabled_for_environment(
            semrush_cap, DeploymentEnvironment.PRODUCTION_AUDIT
        )

    def test_semrush_general_environment_disabled(self):
        """Test SEMrush disabled in general environment."""
        semrush_cap = next(
            cap for cap in ENRICH_CAPABILITIES if cap.name == "semrush_site_audit"
        )

        # Should be disabled in production_general
        assert not is_capability_enabled_for_environment(
            semrush_cap, DeploymentEnvironment.PRODUCTION_GENERAL
        )


class TestCapabilityTiers:
    """Test capability tier system."""

    def test_essential_tier_capabilities(self):
        """Test essential tier capability identification."""
        essential_caps = get_capabilities_by_tier(
            CapabilityTier.ESSENTIAL, NodeType.ENRICH
        )

        # Should include tech stack and web vitals
        essential_names = [cap.name for cap in essential_caps]
        assert "tech_stack_analysis" in essential_names
        assert "core_web_vitals" in essential_names

    def test_high_value_tier_capabilities(self):
        """Test high-value tier capability identification."""
        high_value_caps = get_capabilities_by_tier(
            CapabilityTier.HIGH_VALUE, NodeType.ENRICH
        )

        # Should include SEMrush
        high_value_names = [cap.name for cap in high_value_caps]
        assert "semrush_site_audit" in high_value_names

    def test_optional_tier_capabilities(self):
        """Test optional tier capability identification."""
        optional_caps = get_capabilities_by_tier(
            CapabilityTier.OPTIONAL, NodeType.ENRICH
        )

        # Should include screenshot
        optional_names = [cap.name for cap in optional_caps]
        assert "screenshot_capture" in optional_names

    def test_final_output_tiers(self):
        """Test final output capability tiers."""
        high_value_caps = get_capabilities_by_tier(
            CapabilityTier.HIGH_VALUE, NodeType.FINAL_OUTPUT
        )
        optional_caps = get_capabilities_by_tier(
            CapabilityTier.OPTIONAL, NodeType.FINAL_OUTPUT
        )

        # Email should be high value, mockup should be optional
        high_value_names = [cap.name for cap in high_value_caps]
        optional_names = [cap.name for cap in optional_caps]

        assert "email_generation" in high_value_names
        assert "mockup_generation" in optional_names


class TestEnvironmentAwareCapabilities:
    """Test environment-aware capability selection."""

    @patch("leadfactory.config.node_config.is_api_available")
    def test_development_environment_capabilities(self, mock_api_available):
        """Test capability selection in development environment."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            caps = get_enabled_capabilities(NodeType.ENRICH)

        cap_names = [cap.name for cap in caps]

        # Should include essential capabilities
        assert "tech_stack_analysis" in cap_names
        assert "core_web_vitals" in cap_names

        # Should exclude expensive capabilities in development
        assert "screenshot_capture" not in cap_names
        assert "semrush_site_audit" not in cap_names

    @patch("leadfactory.config.node_config.is_api_available")
    def test_production_audit_environment_capabilities(self, mock_api_available):
        """Test capability selection in production audit environment."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            caps = get_enabled_capabilities(NodeType.ENRICH)

        cap_names = [cap.name for cap in caps]

        # Should include essential capabilities
        assert "tech_stack_analysis" in cap_names
        assert "core_web_vitals" in cap_names

        # Should include high-value audit capabilities
        assert "semrush_site_audit" in cap_names

        # Should exclude screenshot (not valuable for audit)
        assert "screenshot_capture" not in cap_names

    @patch("leadfactory.config.node_config.is_api_available")
    def test_production_general_environment_capabilities(self, mock_api_available):
        """Test capability selection in production general environment."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            caps = get_enabled_capabilities(NodeType.ENRICH)

        cap_names = [cap.name for cap in caps]

        # Should include essential capabilities
        assert "tech_stack_analysis" in cap_names
        assert "core_web_vitals" in cap_names

        # Should include screenshot for general leads
        assert "screenshot_capture" in cap_names

        # Should exclude expensive SEMrush
        assert "semrush_site_audit" not in cap_names

    @patch("leadfactory.config.node_config.is_api_available")
    def test_final_output_development_environment(self, mock_api_available):
        """Test final output capabilities in development."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            caps = get_enabled_capabilities(NodeType.FINAL_OUTPUT)

        cap_names = [cap.name for cap in caps]

        # Should include email for testing
        assert "email_generation" in cap_names

        # Should exclude mockup to reduce costs
        assert "mockup_generation" not in cap_names

    @patch("leadfactory.config.node_config.is_api_available")
    def test_budget_constraint_handling(self, mock_api_available):
        """Test capability selection with budget constraints."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        # Low budget should exclude expensive capabilities
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            caps = get_enabled_capabilities(NodeType.ENRICH, budget_cents=5.0)

        cap_names = [cap.name for cap in caps]

        # Should include free capabilities
        assert "tech_stack_analysis" in cap_names
        assert "core_web_vitals" in cap_names

        # Should exclude expensive SEMrush due to budget
        assert "semrush_site_audit" not in cap_names


class TestCostEstimation:
    """Test environment-aware cost estimation."""

    @patch("leadfactory.config.node_config.is_api_available")
    def test_development_cost_estimation(self, mock_api_available):
        """Test cost estimation in development environment."""
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            enrich_cost = estimate_node_cost(NodeType.ENRICH)
            final_cost = estimate_node_cost(NodeType.FINAL_OUTPUT)

        # Development should have minimal costs
        assert enrich_cost == 0.0  # Only free APIs enabled
        assert final_cost == 5.0  # Only email generation enabled

    @patch("leadfactory.config.node_config.is_api_available")
    def test_production_audit_cost_estimation(self, mock_api_available):
        """Test cost estimation in production audit environment."""
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            enrich_cost = estimate_node_cost(NodeType.ENRICH)
            final_cost = estimate_node_cost(NodeType.FINAL_OUTPUT)

        # Should include SEMrush cost
        assert enrich_cost == 10.0  # SEMrush site audit
        assert final_cost == 10.0  # Both AI capabilities

    @patch("leadfactory.config.node_config.is_api_available")
    def test_production_general_cost_estimation(self, mock_api_available):
        """Test cost estimation in production general environment."""
        mock_api_available.return_value = True

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            enrich_cost = estimate_node_cost(NodeType.ENRICH)
            final_cost = estimate_node_cost(NodeType.FINAL_OUTPUT)

        # Should include screenshot cost
        assert enrich_cost == 1.0  # Screenshot capture
        assert final_cost == 10.0  # Both AI capabilities


class TestEnvironmentInfo:
    """Test environment information and validation."""

    @patch("leadfactory.config.node_config.is_api_available")
    def test_environment_info_collection(self, mock_api_available):
        """Test environment information collection."""

        # Mock some APIs as available, others not
        def mock_availability(api):
            return api in ["wappalyzer", "pagespeed"]

        mock_api_available.side_effect = mock_availability

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            info = get_environment_info()

        assert info["environment"] == "development"
        assert "wappalyzer" in info["available_apis"]
        assert "pagespeed" in info["available_apis"]
        assert "openai" in info["unavailable_apis"]
        # fallback_apis only includes unavailable APIs that have fallbacks
        assert "screenshot_one" in info["fallback_apis"] or "openai" in info["fallback_apis"]

    @patch("leadfactory.config.node_config.is_api_available")
    def test_environment_validation_success(self, mock_api_available):
        """Test successful environment validation."""

        # Mock essential APIs as available
        def mock_availability(api):
            return api in ["wappalyzer", "pagespeed", "openai"]

        mock_api_available.side_effect = mock_availability

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            validation = validate_environment_configuration()

        assert validation["valid"] is True
        assert len(validation["issues"]) == 0

    @patch("leadfactory.config.node_config.is_api_available")
    def test_environment_validation_missing_essential(self, mock_api_available):
        """Test validation with missing essential capabilities."""
        # Mock essential APIs as unavailable
        mock_api_available.return_value = False

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            validation = validate_environment_configuration()

        assert validation["valid"] is False
        assert len(validation["issues"]) > 0

    @patch("leadfactory.config.node_config.is_api_available")
    def test_audit_environment_validation_warnings(self, mock_api_available):
        """Test validation warnings in audit environment."""

        # Mock NO APIs available to trigger warnings
        def mock_availability(api):
            return False  # No APIs available

        mock_api_available.side_effect = mock_availability

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            validation = validate_environment_configuration()

        # Should warn when no high-value audit capabilities are available
        assert len(validation["warnings"]) > 0
        assert len(validation["recommendations"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])
