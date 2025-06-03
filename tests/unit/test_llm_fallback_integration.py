"""
Unit tests for LLM fallback system integration with pipeline.

This module tests the integration of the LLM fallback system with the
unified GPT-4o node and other pipeline components.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from leadfactory.llm.integrated_client import IntegratedLLMClient
from leadfactory.llm.provider import LLMResponse, LLMError
from leadfactory.pipeline.unified_gpt4o import (
    UnifiedGPT4ONode,
    generate_unified_content_for_business_async,
    get_llm_client_status,
    get_llm_cost_summary
)
from leadfactory.config.fallback_config_loader import LLMFallbackConfig


class TestIntegratedLLMClient:
    """Test the integrated LLM client."""

    @pytest.fixture
    def mock_config(self):
        """Mock fallback configuration."""
        config = Mock()
        config.cost_monitoring.enabled = True
        config.cost_monitoring.cost_per_token = {
            "gpt-4o": {"input": 0.00001, "output": 0.00003},
            "claude-3-sonnet": {"input": 0.000015, "output": 0.000075}
        }
        config.health_monitoring.enabled = True
        config.pipeline.max_concurrent_requests = 10
        config.primary_provider.type = "openai"
        config.primary_provider.model = "gpt-4o"
        config.secondary_provider.type = "anthropic"
        config.secondary_provider.model = "claude-3-sonnet"
        return config

    @pytest.fixture
    def mock_fallback_manager(self):
        """Mock fallback manager."""
        manager = AsyncMock()
        manager.generate_response.return_value = LLMResponse(
            content='{"test": "response"}',
            provider="gpt-4o",
            model="gpt-4o",
            tokens_used=100,
            cost=0.001,
            latency=1.5
        )
        return manager

    @pytest.fixture
    def mock_cost_monitor(self):
        """Mock cost monitor."""
        monitor = AsyncMock()
        monitor.check_budget_constraint.return_value = True
        monitor.record_cost.return_value = None
        monitor.get_cost_summary.return_value = {"total_cost": 10.50}
        return monitor

    @pytest.fixture
    def mock_health_monitor(self):
        """Mock health monitor."""
        monitor = AsyncMock()
        monitor.get_dashboard_data.return_value = {"status": "healthy"}
        return monitor

    @pytest_asyncio.fixture
    async def client(self, mock_config):
        """Create integrated LLM client with mocked dependencies."""
        client = IntegratedLLMClient(mock_config)
        return client

    @pytest.mark.asyncio
    async def test_client_initialization(self, client, mock_config):
        """Test client initialization."""
        with patch.object(client, '_create_provider') as mock_create:
            mock_create.return_value = Mock()

            with patch('leadfactory.llm.integrated_client.FallbackManager') as mock_fm:
                mock_fm_instance = AsyncMock()
                mock_fm.return_value = mock_fm_instance

                with patch('leadfactory.llm.integrated_client.CostMonitor') as mock_cm:
                    mock_cm_instance = AsyncMock()
                    mock_cm.return_value = mock_cm_instance

                    with patch('leadfactory.llm.integrated_client.HealthMonitor') as mock_hm:
                        mock_hm_instance = AsyncMock()
                        mock_hm.return_value = mock_hm_instance

                        await client.initialize()

                        assert client._initialized
                        mock_fm.assert_called_once()
                        mock_cm.assert_called_once()
                        mock_hm.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_success(self, client, mock_fallback_manager, mock_cost_monitor):
        """Test successful response generation."""
        client.fallback_manager = mock_fallback_manager
        client.cost_monitor = mock_cost_monitor
        client._initialized = True

        response = await client.generate_response(
            prompt="Test prompt",
            parameters={"max_tokens": 100}
        )

        assert isinstance(response, LLMResponse)
        assert response.content == '{"test": "response"}'
        assert response.provider == "gpt-4o"
        mock_cost_monitor.check_budget_constraint.assert_called_once()
        mock_cost_monitor.record_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_budget_exceeded(self, client, mock_cost_monitor):
        """Test response generation when budget is exceeded."""
        client.cost_monitor = mock_cost_monitor
        client._initialized = True
        mock_cost_monitor.check_budget_constraint.return_value = False

        with pytest.raises(LLMError) as exc_info:
            await client.generate_response("Test prompt")

        assert exc_info.value.error_type == "quota_exceeded"
        assert "budget constraints" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_batch_generate_responses(self, client, mock_fallback_manager):
        """Test batch response generation."""
        client.fallback_manager = mock_fallback_manager
        client._initialized = True

        requests = [
            {"prompt": "Test 1"},
            {"prompt": "Test 2"}
        ]

        responses = await client.batch_generate_responses(requests)

        assert len(responses) == 2
        assert all(isinstance(r, LLMResponse) for r in responses)

    @pytest.mark.asyncio
    async def test_get_provider_status(self, client, mock_fallback_manager, mock_health_monitor, mock_cost_monitor):
        """Test getting provider status."""
        client.fallback_manager = mock_fallback_manager
        client.health_monitor = mock_health_monitor
        client.cost_monitor = mock_cost_monitor
        client._initialized = True

        mock_fallback_manager.providers = {
            "primary": Mock(available=True, failure_count=0)
        }
        mock_fallback_manager._pipeline_paused = False

        status = await client.get_provider_status()

        assert "fallback_manager" in status
        assert "health_monitor" in status
        assert "cost_monitor" in status


class TestUnifiedGPT4ONodeIntegration:
    """Test the unified GPT-4o node with fallback system integration."""

    @pytest.fixture
    def mock_business_data(self):
        """Mock business data."""
        return {
            "id": 123,
            "name": "Test Business",
            "industry": "Technology",
            "website": "https://test.com"
        }

    @pytest.fixture
    def node(self):
        """Create unified GPT-4o node."""
        return UnifiedGPT4ONode({"use_fallback_system": True})

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response."""
        return LLMResponse(
            content=json.dumps({
                "mockup_concept": {
                    "design_theme": "Modern Professional",
                    "color_scheme": ["#2C3E50", "#3498DB"],
                    "layout_sections": []
                },
                "email_content": {
                    "subject": "Test Subject",
                    "greeting": "Hi there",
                    "opening": "Test opening"
                }
            }),
            provider="gpt-4o",
            model="gpt-4o",
            tokens_used=150,
            cost=0.002,
            latency=2.1
        )

    @pytest.mark.asyncio
    async def test_node_initialization(self, node):
        """Test node LLM client initialization."""
        with patch('leadfactory.pipeline.unified_gpt4o.get_global_llm_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await node.initialize_llm_client()

            assert node.llm_client == mock_client
            assert node._use_fallback_system

    @pytest.mark.asyncio
    async def test_generate_with_llm_success(self, node, mock_business_data, mock_llm_response):
        """Test successful LLM generation."""
        mock_client = AsyncMock()
        mock_client.generate_response.return_value = mock_llm_response
        node.llm_client = mock_client

        with patch.object(node, 'construct_unified_prompt') as mock_prompt:
            mock_prompt.return_value = "Test prompt"

            result = await node._generate_with_llm(
                "Test prompt", mock_business_data, True, True
            )

            assert result["success"]
            assert "content" in result
            assert "llm_response" in result
            assert result["llm_response"]["provider"] == "gpt-4o"
            assert result["llm_response"]["cost"] == 0.002

    @pytest.mark.asyncio
    async def test_generate_unified_content_async_with_llm(self, node, mock_business_data, mock_llm_response):
        """Test async unified content generation with LLM."""
        mock_client = AsyncMock()
        mock_client.generate_response.return_value = mock_llm_response

        with patch.object(node, 'initialize_llm_client') as mock_init:
            with patch.object(node, 'validate_inputs') as mock_validate:
                with patch('leadfactory.pipeline.unified_gpt4o.get_enabled_capabilities') as mock_caps:
                    mock_validate.return_value = {"is_valid": True}
                    mock_caps.return_value = [Mock(name="mockup_generation"), Mock(name="email_generation")]
                    node.llm_client = mock_client
                    node._use_fallback_system = True

                    result = await node._generate_unified_content_async(mock_business_data)

                    assert result["success"]
                    assert "content" in result
                    assert "llm_response" in result

    @pytest.mark.asyncio
    async def test_generate_unified_content_async_fallback_to_mock(self, node, mock_business_data):
        """Test fallback to mock implementation when LLM fails."""
        mock_client = AsyncMock()
        mock_client.generate_response.side_effect = LLMError("test_error", "Test error", "test_provider")

        with patch.object(node, 'initialize_llm_client') as mock_init:
            with patch.object(node, 'validate_inputs') as mock_validate:
                with patch('leadfactory.pipeline.unified_gpt4o.get_enabled_capabilities') as mock_caps:
                    with patch.object(node, '_generate_mock_response') as mock_gen_mock:
                        mock_validate.return_value = {"is_valid": True}
                        mock_caps.return_value = [Mock(name="mockup_generation")]
                        mock_gen_mock.return_value = {"success": True, "content": {"mock": True}}
                        node.llm_client = mock_client
                        node._use_fallback_system = True

                        result = await node._generate_unified_content_async(mock_business_data)

                        assert result["success"]
                        mock_gen_mock.assert_called_once()

    def test_extract_json_from_response(self, node):
        """Test JSON extraction from LLM response."""
        # Test valid JSON
        response_text = 'Here is the JSON: {"test": "value", "number": 42}'
        result = node._extract_json_from_response(response_text)
        assert result == {"test": "value", "number": 42}

        # Test no JSON
        response_text = "No JSON here"
        result = node._extract_json_from_response(response_text)
        assert result == {}

        # Test invalid JSON
        response_text = '{"invalid": json}'
        result = node._extract_json_from_response(response_text)
        assert result == {}

    def test_structure_llm_response(self, node, mock_business_data):
        """Test LLM response structuring."""
        content = {
            "mockup_concept": {
                "design_theme": "Custom Theme",
                "color_scheme": ["#FF0000", "#00FF00"]
            },
            "email_content": {
                "subject": "Custom Subject",
                "greeting": "Custom Greeting"
            }
        }

        result = node._structure_llm_response(content, True, True, mock_business_data)

        assert "mockup_concept" in result
        assert "email_content" in result
        assert result["mockup_concept"]["design_theme"] == "Custom Theme"
        assert result["email_content"]["subject"] == "Custom Subject"

    def test_structure_llm_response_fallback(self, node, mock_business_data):
        """Test LLM response structuring with fallback values."""
        content = {}  # Empty content

        result = node._structure_llm_response(content, True, True, mock_business_data)

        assert "mockup_concept" in result
        assert "email_content" in result
        assert result["mockup_concept"]["design_theme"] == "Modern Professional"
        assert "Test Business" in result["email_content"]["subject"]


class TestAsyncConvenienceFunctions:
    """Test async convenience functions."""

    @pytest.fixture
    def mock_business_data(self):
        """Mock business data."""
        return {
            "id": 123,
            "name": "Test Business",
            "industry": "Technology",
            "website": "https://test.com"
        }

    @pytest.mark.asyncio
    async def test_generate_unified_content_for_business_async(self, mock_business_data):
        """Test async business content generation."""
        with patch('leadfactory.pipeline.unified_gpt4o.get_storage') as mock_storage:
            with patch('leadfactory.pipeline.unified_gpt4o.UnifiedGPT4ONode') as mock_node_class:
                mock_storage.return_value.get_business_data.return_value = mock_business_data
                mock_node = Mock()
                mock_node._generate_unified_content_async = AsyncMock(return_value={
                    "success": True,
                    "content": {"test": "data"}
                })
                mock_node.save_unified_results.return_value = True
                mock_node_class.return_value = mock_node

                result = await generate_unified_content_for_business_async(123)

                assert result["success"]
                assert result["saved_to_database"]

    def test_get_llm_client_status(self):
        """Test getting LLM client status."""
        with patch('leadfactory.llm.integrated_client.get_global_llm_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_provider_status = AsyncMock(return_value={"status": "healthy"})
            mock_get_client.return_value = mock_client

            status = get_llm_client_status()

            assert status["status"] == "healthy"

    def test_get_llm_cost_summary(self):
        """Test getting LLM cost summary."""
        with patch('leadfactory.llm.integrated_client.get_global_llm_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_cost_summary = AsyncMock(return_value={"total_cost": 25.75})
            mock_get_client.return_value = mock_client

            summary = get_llm_cost_summary()

            assert summary["total_cost"] == 25.75


class TestErrorHandling:
    """Test error handling in fallback integration."""

    @pytest.mark.asyncio
    async def test_llm_client_initialization_failure(self):
        """Test handling of LLM client initialization failure."""
        node = UnifiedGPT4ONode({"use_fallback_system": True})

        with patch('leadfactory.pipeline.unified_gpt4o.get_global_llm_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Initialization failed")

            await node.initialize_llm_client()

            assert not node._use_fallback_system
            assert node.llm_client is None

    @pytest.mark.asyncio
    async def test_llm_generation_error_handling(self):
        """Test error handling during LLM generation."""
        node = UnifiedGPT4ONode()
        mock_client = AsyncMock()
        mock_client.generate_response.side_effect = LLMError("rate_limit", "Rate limited", "gpt-4o")
        node.llm_client = mock_client

        with pytest.raises(LLMError):
            await node._generate_with_llm("prompt", {}, True, True)

    def test_status_functions_error_handling(self):
        """Test error handling in status functions."""
        with patch('leadfactory.llm.integrated_client.get_global_llm_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Client unavailable")

            status = get_llm_client_status()
            assert "error" in status
            assert status.get("fallback_available", False) == False

            cost_summary = get_llm_cost_summary()
            assert "error" in cost_summary
            assert cost_summary.get("cost_monitoring_available", False) == False


class TestConfigurationIntegration:
    """Test configuration integration."""

    def test_node_with_fallback_disabled(self):
        """Test node behavior when fallback system is disabled."""
        node = UnifiedGPT4ONode({"use_fallback_system": False})

        assert not node._use_fallback_system
        assert node.llm_client is None

    @pytest.mark.asyncio
    async def test_node_fallback_system_configuration(self):
        """Test node configuration for fallback system."""
        node = UnifiedGPT4ONode({"use_fallback_system": True})

        with patch('leadfactory.pipeline.unified_gpt4o.get_global_llm_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await node.initialize_llm_client()

            assert node._use_fallback_system
            assert node.llm_client == mock_client
