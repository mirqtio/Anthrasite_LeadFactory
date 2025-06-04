"""Tests for LLM configuration management."""

import os
from unittest.mock import patch

import pytest

from leadfactory.llm.config import (
    CostConfig,
    FallbackStrategy,
    LLMConfig,
    ProviderConfig,
)


class TestProviderConfig:
    """Test provider configuration."""

    def test_default_values(self):
        """Test provider config default values."""
        config = ProviderConfig(name="test")

        assert config.name == "test"
        assert config.enabled is True
        assert config.api_key is None
        assert config.timeout == 30
        assert config.priority == 1
        assert config.cost_per_1k_tokens == 0.0


class TestCostConfig:
    """Test cost configuration."""

    def test_default_values(self):
        """Test cost config default values."""
        config = CostConfig()

        assert config.max_cost_per_request == 1.0
        assert config.daily_cost_limit == 50.0
        assert config.monthly_cost_limit == 1000.0
        assert config.cost_tracking_enabled is True
        assert config.budget_alert_threshold == 0.8


class TestLLMConfig:
    """Test LLM configuration."""

    def test_default_values(self):
        """Test LLM config default values."""
        config = LLMConfig()

        assert config.fallback_strategy == FallbackStrategy.SMART_FALLBACK
        assert config.max_fallback_attempts == 3
        assert config.default_temperature == 0.7
        assert config.default_max_tokens == 1000
        assert config.enable_caching is True
        assert config.log_requests is True

    @patch.dict(
        os.environ,
        {
            "LLM_FALLBACK_STRATEGY": "cost_optimized",
            "LLM_MAX_FALLBACK_ATTEMPTS": "5",
            "LLM_DEFAULT_TEMPERATURE": "0.5",
            "LLM_DEFAULT_MAX_TOKENS": "2000",
            "LLM_ENABLE_CACHING": "false",
            "LLM_LOG_REQUESTS": "false",
            "OPENAI_API_KEY": "test-openai-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "OLLAMA_HOST": "http://test:11434",
        },
    )
    def test_from_environment(self):
        """Test loading configuration from environment."""
        config = LLMConfig.from_environment()

        assert config.fallback_strategy == FallbackStrategy.COST_OPTIMIZED
        assert config.max_fallback_attempts == 5
        assert config.default_temperature == 0.5
        assert config.default_max_tokens == 2000
        assert config.enable_caching is False
        assert config.log_requests is False

        # Check providers
        assert "openai" in config.providers
        assert "anthropic" in config.providers
        assert "ollama" in config.providers

        assert config.providers["openai"].api_key == "test-openai-key"
        assert config.providers["anthropic"].api_key == "test-anthropic-key"
        assert config.providers["ollama"].base_url == "http://test:11434"

    def test_get_enabled_providers(self):
        """Test getting enabled providers."""
        config = LLMConfig()
        config.providers = {
            "provider1": ProviderConfig(name="provider1", enabled=True),
            "provider2": ProviderConfig(name="provider2", enabled=False),
            "provider3": ProviderConfig(name="provider3", enabled=True),
        }

        enabled = config.get_enabled_providers()
        assert len(enabled) == 2
        assert all(p.enabled for p in enabled)

    def test_get_provider_order_cost_optimized(self):
        """Test provider order for cost optimized strategy."""
        config = LLMConfig()
        config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED
        config.providers = {
            "expensive": ProviderConfig(name="expensive", cost_per_1k_tokens=0.03),
            "cheap": ProviderConfig(name="cheap", cost_per_1k_tokens=0.01),
            "free": ProviderConfig(name="free", cost_per_1k_tokens=0.0),
        }

        order = config.get_provider_order()
        assert order == ["free", "cheap", "expensive"]

    def test_get_provider_order_quality_optimized(self):
        """Test provider order for quality optimized strategy."""
        config = LLMConfig()
        config.fallback_strategy = FallbackStrategy.QUALITY_OPTIMIZED
        config.providers = {
            "low": ProviderConfig(name="low", priority=1),
            "high": ProviderConfig(name="high", priority=3),
            "medium": ProviderConfig(name="medium", priority=2),
        }

        order = config.get_provider_order()
        assert order == ["high", "medium", "low"]

    def test_get_provider_order_smart_fallback(self):
        """Test provider order for smart fallback strategy."""
        config = LLMConfig()
        config.fallback_strategy = FallbackStrategy.SMART_FALLBACK
        config.providers = {
            "ollama": ProviderConfig(name="ollama", priority=1),
            "openai": ProviderConfig(name="openai", priority=3),
            "anthropic": ProviderConfig(name="anthropic", priority=2),
        }

        order = config.get_provider_order()
        # Should start with ollama (free), then order by priority
        assert order[0] == "ollama"
        assert "openai" in order
        assert "anthropic" in order

    def test_estimate_request_cost(self):
        """Test request cost estimation."""
        config = LLMConfig()
        config.providers = {
            "test": ProviderConfig(name="test", cost_per_1k_tokens=0.02)
        }

        cost = config.estimate_request_cost(1000, "test")
        assert cost == 0.02

        cost = config.estimate_request_cost(500, "test")
        assert cost == 0.01

        # Unknown provider
        cost = config.estimate_request_cost(1000, "unknown")
        assert cost == 0.0

    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = LLMConfig()
        config.providers = {
            "openai": ProviderConfig(name="openai", api_key="test-key"),
            "ollama": ProviderConfig(name="ollama"),
        }

        issues = config.validate()
        assert len(issues) == 0

    def test_validate_missing_api_keys(self):
        """Test validation with missing API keys."""
        config = LLMConfig()
        config.providers = {
            "openai": ProviderConfig(name="openai", enabled=True),  # Missing API key
            "anthropic": ProviderConfig(
                name="anthropic", enabled=True
            ),  # Missing API key
        }

        issues = config.validate()
        assert len(issues) == 2
        assert any("openai" in issue and "API key" in issue for issue in issues)
        assert any("anthropic" in issue and "API key" in issue for issue in issues)

    def test_validate_invalid_values(self):
        """Test validation with invalid values."""
        config = LLMConfig()
        config.providers = {
            "test": ProviderConfig(
                name="test",
                timeout=-1,  # Invalid timeout
                cost_per_1k_tokens=-0.01,  # Negative cost
            )
        }
        config.cost_config.max_cost_per_request = -1  # Invalid cost
        config.max_fallback_attempts = -1  # Invalid attempts

        issues = config.validate()
        assert len(issues) >= 4  # Should have multiple validation issues
