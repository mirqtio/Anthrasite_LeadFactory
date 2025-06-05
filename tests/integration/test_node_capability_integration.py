"""
Integration tests for NodeCapability configurations with pipeline components.

Tests the interaction between environment-aware NodeCapability configurations
and other pipeline components like DAG traversal and cost tracking.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.config.node_config import (
    DeploymentEnvironment,
    NodeType,
    estimate_node_cost,
    get_enabled_capabilities,
    get_environment_info,
)
from leadfactory.pipeline.dag_traversal import PipelineDAG, PipelineStage


class TestDAGTraversalIntegration:
    """Test integration with DAG traversal system."""

    @patch("leadfactory.config.node_config.is_api_available")
    def test_dag_traversal_with_environment_capabilities(self, mock_api_available):
        """Test DAG traversal uses environment-aware capabilities."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        dag = PipelineDAG()

        # Test development environment (reduced capabilities)
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            plan = dag.get_execution_plan(node_type=NodeType.ENRICH)

        # Should still include all essential stages
        assert PipelineStage.SCRAPE in plan
        assert PipelineStage.ENRICH in plan
        assert PipelineStage.SCORE in plan

    @patch("leadfactory.config.node_config.is_api_available")
    def test_dag_traversal_with_budget_constraints(self, mock_api_available):
        """Test DAG traversal with budget-constrained capabilities."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        dag = PipelineDAG()

        # Test with low budget
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            plan = dag.get_execution_plan(node_type=NodeType.ENRICH, budget_cents=1.0)

        # Should still work with reduced capabilities
        assert len(plan) > 0

    @patch("leadfactory.config.node_config.is_api_available")
    def test_dag_stage_filtering_by_environment(self, mock_api_available):
        """Test stage filtering based on environment capabilities."""

        # Mock APIs selectively
        def mock_availability(api):
            return api in ["wappalyzer", "pagespeed"]  # Only free APIs

        mock_api_available.side_effect = mock_availability

        dag = PipelineDAG()

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            plan = dag.get_execution_plan(node_type=NodeType.ENRICH)

        # Should include stages that can run with available capabilities
        assert PipelineStage.ENRICH in plan


class TestCostTrackingIntegration:
    """Test integration with cost tracking system."""

    @patch("leadfactory.config.node_config.is_api_available")
    @patch("leadfactory.cost.cost_tracking.track_cost")
    def test_environment_cost_tracking(self, mock_track_cost, mock_api_available):
        """Test cost tracking with environment-aware capabilities."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        # Test cost estimation across environments
        environments = [
            DeploymentEnvironment.DEVELOPMENT,
            DeploymentEnvironment.PRODUCTION_AUDIT,
            DeploymentEnvironment.PRODUCTION_GENERAL,
        ]

        costs = {}
        for env in environments:
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env.value}):
                enrich_cost = estimate_node_cost(NodeType.ENRICH)
                final_cost = estimate_node_cost(NodeType.FINAL_OUTPUT)
                costs[env] = {"enrich": enrich_cost, "final": final_cost}

        # Development should have lowest costs
        dev_total = (
            costs[DeploymentEnvironment.DEVELOPMENT]["enrich"]
            + costs[DeploymentEnvironment.DEVELOPMENT]["final"]
        )

        audit_total = (
            costs[DeploymentEnvironment.PRODUCTION_AUDIT]["enrich"]
            + costs[DeploymentEnvironment.PRODUCTION_AUDIT]["final"]
        )

        general_total = (
            costs[DeploymentEnvironment.PRODUCTION_GENERAL]["enrich"]
            + costs[DeploymentEnvironment.PRODUCTION_GENERAL]["final"]
        )

        # Development should be cheapest
        assert dev_total <= audit_total
        assert dev_total <= general_total

        # Audit environment should prioritize high-value expensive capabilities
        assert (
            costs[DeploymentEnvironment.PRODUCTION_AUDIT]["enrich"]
            > costs[DeploymentEnvironment.PRODUCTION_GENERAL]["enrich"]
        )

    @patch("leadfactory.config.node_config.is_api_available")
    def test_budget_constraint_compliance(self, mock_api_available):
        """Test that capabilities respect budget constraints across environments."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        test_budgets = [0.0, 1.0, 5.0, 10.0, 20.0]

        for budget in test_budgets:
            for env in DeploymentEnvironment:
                with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env.value}):
                    # Test both node types
                    for node_type in [NodeType.ENRICH, NodeType.FINAL_OUTPUT]:
                        actual_cost = estimate_node_cost(node_type, budget_cents=budget)

                        # Actual cost should not exceed budget
                        assert actual_cost <= budget, (
                            f"Cost {actual_cost} exceeds budget {budget} for {node_type.value} in {env.value}"
                        )


class TestEnvironmentConfiguration:
    """Test environment configuration scenarios."""

    def test_api_fallback_scenario(self):
        """Test behavior when APIs are unavailable but fallbacks exist."""
        # Mock scenario where main APIs are down but fallbacks available
        with patch("leadfactory.config.node_config.is_api_available") as mock_api:
            mock_api.return_value = False  # All APIs unavailable

            with patch.dict(
                os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}
            ):
                info = get_environment_info()
                caps = get_enabled_capabilities(NodeType.ENRICH)

            # Should identify fallback options
            assert len(info["fallback_apis"]) > 0

            # Should handle gracefully with no enabled capabilities
            assert isinstance(caps, list)

    @patch("leadfactory.config.node_config.is_api_available")
    def test_mixed_api_availability(self, mock_api_available):
        """Test scenario with mixed API availability."""

        # Mock some APIs available, others not
        def mock_availability(api):
            return api in ["wappalyzer", "pagespeed"]  # Only free APIs

        mock_api_available.side_effect = mock_availability

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            caps = get_enabled_capabilities(NodeType.ENRICH)

        cap_names = [cap.name for cap in caps]

        # Should include capabilities with available APIs
        assert "tech_stack_analysis" in cap_names
        assert "core_web_vitals" in cap_names

        # Should exclude capabilities with unavailable APIs
        assert "semrush_site_audit" not in cap_names

    def test_environment_variable_precedence(self):
        """Test environment variable precedence for configuration."""
        # Test explicit DEPLOYMENT_ENVIRONMENT takes precedence
        env_vars = {
            "DEPLOYMENT_ENVIRONMENT": "development",
            "NODE_ENV": "production",
            "BUSINESS_MODEL": "audit",
        }

        with patch.dict(os.environ, env_vars):
            info = get_environment_info()

        assert info["environment"] == "development"

    def test_business_model_detection(self):
        """Test business model-based environment detection."""
        # Test audit business model detection
        with patch.dict(os.environ, {"BUSINESS_MODEL": "audit"}, clear=True):
            info = get_environment_info()

        assert info["environment"] == "production_audit"


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    @patch("leadfactory.config.node_config.is_api_available")
    def test_development_to_production_migration(self, mock_api_available):
        """Test configuration changes from development to production."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        # Simulate development environment
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "development"}):
            dev_caps = get_enabled_capabilities(NodeType.ENRICH)
            dev_cost = estimate_node_cost(NodeType.ENRICH)

        # Simulate production environment
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            prod_caps = get_enabled_capabilities(NodeType.ENRICH)
            prod_cost = estimate_node_cost(NodeType.ENRICH)

        # Production should have more capabilities and higher cost
        assert len(prod_caps) >= len(dev_caps)
        assert prod_cost >= dev_cost

    @patch("leadfactory.config.node_config.is_api_available")
    def test_audit_vs_general_production(self, mock_api_available):
        """Test differences between audit and general production environments."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        # Test audit production
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            audit_caps = get_enabled_capabilities(NodeType.ENRICH)
            audit_cost = estimate_node_cost(NodeType.ENRICH)

        # Test general production
        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_general"}):
            general_caps = get_enabled_capabilities(NodeType.ENRICH)
            general_cost = estimate_node_cost(NodeType.ENRICH)

        audit_names = [cap.name for cap in audit_caps]
        general_names = [cap.name for cap in general_caps]

        # Audit should prioritize SEMrush over screenshot
        assert "semrush_site_audit" in audit_names
        assert "semrush_site_audit" not in general_names
        assert "screenshot_capture" not in audit_names
        assert "screenshot_capture" in general_names

    @patch("leadfactory.config.node_config.is_api_available")
    def test_budget_scaling_scenario(self, mock_api_available):
        """Test capability scaling with increasing budget."""
        # Mock all APIs as available
        mock_api_available.return_value = True

        budgets = [0, 1, 5, 10, 15, 20]

        with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": "production_audit"}):
            capabilities_by_budget = {}
            costs_by_budget = {}

            for budget in budgets:
                caps = get_enabled_capabilities(NodeType.ENRICH, budget_cents=budget)
                cost = estimate_node_cost(NodeType.ENRICH, budget_cents=budget)

                capabilities_by_budget[budget] = len(caps)
                costs_by_budget[budget] = cost

        # Should see increasing capabilities with higher budgets
        prev_cap_count = 0
        for budget in budgets:
            current_cap_count = capabilities_by_budget[budget]
            assert current_cap_count >= prev_cap_count, (
                f"Capability count decreased from budget {budget - 1} to {budget}"
            )
            prev_cap_count = current_cap_count

    def test_configuration_validation_across_environments(self):
        """Test configuration validation in different environments."""
        from leadfactory.config.node_config import validate_environment_configuration

        environments = ["development", "production_audit", "production_general"]

        for env in environments:
            with patch.dict(os.environ, {"DEPLOYMENT_ENVIRONMENT": env}):
                with patch(
                    "leadfactory.config.node_config.is_api_available"
                ) as mock_api:
                    # Test with all APIs available
                    mock_api.return_value = True
                    validation = validate_environment_configuration()

                    # Should be valid with all APIs available
                    assert validation["valid"] is True, (
                        f"Environment {env} validation failed with all APIs available"
                    )


if __name__ == "__main__":
    pytest.main([__file__])
