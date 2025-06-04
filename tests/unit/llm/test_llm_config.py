"""
Tests for LLM configuration management.

This module tests the configuration classes and environment loading
for the LLM fallback system.
"""

import os
from unittest.mock import patch

import pytest

from leadfactory.llm.config import (
    FallbackStrategy,
    LLMConfig,
    LLMProvider,
    ProviderConfig,
)
from leadfactory.llm.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
)


class TestProviderConfig:
    """Test ProviderConfig functionality."""

    def test_openai_provider_available_with_key(self):
        """Test OpenAI provider is available when API key is set."""
        config = ProviderConfig(
            provider=LLMProvider.OPENAI, api_key="test-key", enabled=True
        )

        assert config.is_available() is True

    def test_openai_provider_unavailable_without_key(self):
        """Test OpenAI provider is unavailable without API key."""
        config = ProviderConfig(provider=LLMProvider.OPENAI, api_key=None, enabled=True)

        assert config.is_available() is False

    def test_provider_unavailable_when_disabled(self):
        """Test provider is unavailable when disabled."""
        config = ProviderConfig(
            provider=LLMProvider.OPENAI, api_key="test-key", enabled=False
        )

        assert config.is_available() is False

    def test_anthropic_provider_available_with_key(self):
        """Test Anthropic provider is available when API key is set."""
        config = ProviderConfig(
            provider=LLMProvider.ANTHROPIC, api_key="test-key", enabled=True
        )

        assert config.is_available() is True

    def test_ollama_provider_available_with_url(self):
        """Test Ollama provider is available when base URL is set."""
        config = ProviderConfig(
            provider=LLMProvider.OLLAMA, base_url="http://localhost:11434", enabled=True
        )

        assert config.is_available() is True

    def test_ollama_provider_unavailable_without_url(self):
        """Test Ollama provider is unavailable without base URL."""
        config = ProviderConfig(
            provider=LLMProvider.OLLAMA, base_url=None, enabled=True
        )

        assert config.is_available() is False


class TestLLMConfig:
    """Test LLMConfig functionality."""

    def test_default_config_creation(self):
        """Test creating a default LLM configuration."""
        config = LLMConfig()

        assert config.fallback_strategy == FallbackStrategy.SMART_FALLBACK
        assert config.max_fallback_attempts == 3
        assert config.default_timeout == 30.0
        assert config.cost_tracking_enabled is True

    def test_get_available_providers_sorted_by_priority(self):
        """Test getting available providers sorted by priority."""
        config = LLMConfig()

        # Add providers with different priorities
        config.providers[LLMProvider.OPENAI] = ProviderConfig(
            provider=LLMProvider.OPENAI, api_key="test-key", enabled=True, priority=2
        )
        config.providers[LLMProvider.ANTHROPIC] = ProviderConfig(
            provider=LLMProvider.ANTHROPIC, api_key="test-key", enabled=True, priority=1
        )
        config.providers[LLMProvider.OLLAMA] = ProviderConfig(
            provider=LLMProvider.OLLAMA,
            base_url="http://localhost:11434",
            enabled=True,
            priority=3,
        )

        available = config.get_available_providers()

        assert len(available) == 3
        assert available[0].provider == LLMProvider.ANTHROPIC  # Priority 1
        assert available[1].provider == LLMProvider.OPENAI  # Priority 2
        assert available[2].provider == LLMProvider.OLLAMA  # Priority 3

    def test_get_provider_config(self):
        """Test getting configuration for specific provider."""
        config = LLMConfig()

        openai_config = ProviderConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        config.providers[LLMProvider.OPENAI] = openai_config

        retrieved_config = config.get_provider_config(LLMProvider.OPENAI)
        assert retrieved_config == openai_config

        # Test non-existent provider
        missing_config = config.get_provider_config(LLMProvider.ANTHROPIC)
        assert missing_config is None

    def test_fallback_order_cost_optimized(self):
        """Test cost optimized fallback order."""
        config = LLMConfig()
        config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED

        # Add providers with different costs
        config.providers[LLMProvider.OPENAI] = ProviderConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            enabled=True,
            cost_per_input_token=0.005 / 1000,
            cost_per_output_token=0.015 / 1000,
            priority=1,
        )
        config.providers[LLMProvider.ANTHROPIC] = ProviderConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key="test-key",
            enabled=True,
            cost_per_input_token=0.015 / 1000,
            cost_per_output_token=0.075 / 1000,
            priority=2,
        )
        config.providers[LLMProvider.OLLAMA] = ProviderConfig(
            provider=LLMProvider.OLLAMA,
            base_url="http://localhost:11434",
            enabled=True,
            cost_per_input_token=0.0,
            cost_per_output_token=0.0,
            priority=3,
        )

        fallback_order = config.get_fallback_order()

        # Should be ordered by cost: Ollama (free), OpenAI, Anthropic
        assert fallback_order[0].provider == LLMProvider.OLLAMA
        assert fallback_order[1].provider == LLMProvider.OPENAI
        assert fallback_order[2].provider == LLMProvider.ANTHROPIC

    def test_fallback_order_fail_fast(self):
        """Test fail fast strategy returns only first provider."""
        config = LLMConfig()
        config.fallback_strategy = FallbackStrategy.FAIL_FAST

        # Add multiple providers
        config.providers[LLMProvider.OPENAI] = ProviderConfig(
            provider=LLMProvider.OPENAI, api_key="test-key", enabled=True, priority=1
        )
        config.providers[LLMProvider.ANTHROPIC] = ProviderConfig(
            provider=LLMProvider.ANTHROPIC, api_key="test-key", enabled=True, priority=2
        )

        fallback_order = config.get_fallback_order()

        # Should only return first provider
        assert len(fallback_order) == 1
        assert fallback_order[0].provider == LLMProvider.OPENAI

    def test_should_fallback_on_error(self):
        """Test fallback decision based on error types."""
        config = LLMConfig()

        # Should always fallback on these error types
        assert (
            config.should_fallback_on_error(
                LLMRateLimitError("Rate limit"), LLMProvider.OPENAI
            )
            is True
        )
        assert (
            config.should_fallback_on_error(
                LLMServiceUnavailableError("Service down"), LLMProvider.OPENAI
            )
            is True
        )

        # Should not fallback on auth errors unless smart fallback
        config.fallback_strategy = FallbackStrategy.ROUND_ROBIN
        assert (
            config.should_fallback_on_error(
                LLMAuthenticationError("Invalid key"), LLMProvider.OPENAI
            )
            is False
        )

        config.fallback_strategy = FallbackStrategy.SMART_FALLBACK
        assert (
            config.should_fallback_on_error(
                LLMAuthenticationError("Invalid key"), LLMProvider.OPENAI
            )
            is True
        )

        # Fail fast should never fallback
        config.fallback_strategy = FallbackStrategy.FAIL_FAST
        assert (
            config.should_fallback_on_error(
                LLMRateLimitError("Rate limit"), LLMProvider.OPENAI
            )
            is False
        )

    def test_estimate_request_cost(self):
        """Test cost estimation for requests."""
        config = LLMConfig()

        config.providers[LLMProvider.OPENAI] = ProviderConfig(
            provider=LLMProvider.OPENAI,
            cost_per_input_token=0.005 / 1000,  # $0.005 per 1K tokens
            cost_per_output_token=0.015 / 1000,  # $0.015 per 1K tokens
        )

        # Test cost calculation
        cost = config.estimate_request_cost(LLMProvider.OPENAI, 1000, 500)
        expected_cost = (1000 * 0.005 / 1000) + (500 * 0.015 / 1000)
        assert cost == expected_cost

    def test_is_within_cost_limits(self):
        """Test cost limit checking."""
        config = LLMConfig()
        config.max_cost_per_request = 1.0

        assert config.is_within_cost_limits(0.5) is True
        assert config.is_within_cost_limits(1.0) is True
        assert config.is_within_cost_limits(1.5) is False

    def test_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = LLMConfig()

        config.providers[LLMProvider.OPENAI] = ProviderConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            default_model="gpt-4o",
            available_models=["gpt-4o", "gpt-3.5-turbo"],
            enabled=True,
            priority=1,
        )

        config_dict = config.to_dict()

        assert "providers" in config_dict
        assert "openai" in config_dict["providers"]
        assert config_dict["providers"]["openai"]["default_model"] == "gpt-4o"
        assert config_dict["providers"]["openai"]["has_api_key"] is True
        assert config_dict["fallback_strategy"] == "smart_fallback"


class TestConfigFromEnvironment:
    """Test loading configuration from environment variables."""

    def test_openai_config_from_env(self):
        """Test loading OpenAI configuration from environment."""
        env_vars = {
            "OPENAI_API_KEY": "test-openai-key",
            "OPENAI_MODEL": "gpt-4o",
            "OPENAI_MAX_TOKENS": "4096",
            "OPENAI_TIMEOUT": "30.0",
            "OPENAI_ENABLED": "true",
            "OPENAI_PRIORITY": "1",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with (
                patch("leadfactory.llm.config.OPENAI_API_KEY", "test-openai-key"),
                patch("leadfactory.llm.config.OPENAI_MODEL", "gpt-4o"),
            ):
                config = LLMConfig.from_environment()

                assert LLMProvider.OPENAI in config.providers
                openai_config = config.providers[LLMProvider.OPENAI]
                assert openai_config.api_key == "test-openai-key"
                assert openai_config.default_model == "gpt-4o"
                assert openai_config.enabled is True
                assert openai_config.priority == 1

    def test_anthropic_config_from_env(self):
        """Test loading Anthropic configuration from environment."""
        env_vars = {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "ANTHROPIC_MODEL": "claude-3-opus-20240229",
            "ANTHROPIC_MAX_TOKENS": "4096",
            "ANTHROPIC_TIMEOUT": "30.0",
            "ANTHROPIC_ENABLED": "true",
            "ANTHROPIC_PRIORITY": "2",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with (
                patch("leadfactory.llm.config.ANTHROPIC_API_KEY", "test-anthropic-key"),
                patch(
                    "leadfactory.llm.config.ANTHROPIC_MODEL", "claude-3-opus-20240229"
                ),
            ):
                config = LLMConfig.from_environment()

                assert LLMProvider.ANTHROPIC in config.providers
                anthropic_config = config.providers[LLMProvider.ANTHROPIC]
                assert anthropic_config.api_key == "test-anthropic-key"
                assert anthropic_config.default_model == "claude-3-opus-20240229"
                assert anthropic_config.enabled is True
                assert anthropic_config.priority == 2

    def test_ollama_config_from_env(self):
        """Test loading Ollama configuration from environment."""
        env_vars = {
            "OLLAMA_HOST": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3:8b",
            "OLLAMA_MAX_TOKENS": "2048",
            "OLLAMA_TIMEOUT": "60.0",
            "OLLAMA_ENABLED": "true",
            "OLLAMA_PRIORITY": "3",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with (
                patch("leadfactory.llm.config.OLLAMA_HOST", "http://localhost:11434"),
                patch("leadfactory.llm.config.OLLAMA_MODEL", "llama3:8b"),
            ):
                config = LLMConfig.from_environment()

                assert LLMProvider.OLLAMA in config.providers
                ollama_config = config.providers[LLMProvider.OLLAMA]
                assert ollama_config.base_url == "http://localhost:11434"
                assert ollama_config.default_model == "llama3:8b"
                assert ollama_config.enabled is True
                assert ollama_config.priority == 3

    def test_global_overrides_from_env(self):
        """Test global configuration overrides from environment."""
        env_vars = {
            "LLM_FALLBACK_STRATEGY": "cost_optimized",
            "LLM_MAX_FALLBACK_ATTEMPTS": "5",
            "LLM_DEFAULT_TIMEOUT": "45.0",
            "LLM_MAX_COST_PER_REQUEST": "2.0",
            "LLM_DAILY_COST_LIMIT": "100.0",
            "LLM_MONTHLY_COST_LIMIT": "2000.0",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with (
                patch("leadfactory.llm.config.get_int_env") as mock_get_int,
                patch("leadfactory.llm.config.get_float_env") as mock_get_float,
            ):
                # Mock the environment getters to return our test values
                def mock_int_env(key, default):
                    if key == "LLM_MAX_FALLBACK_ATTEMPTS":
                        return 5
                    return default

                def mock_float_env(key, default):
                    if key == "LLM_DEFAULT_TIMEOUT":
                        return 45.0
                    elif key == "LLM_MAX_COST_PER_REQUEST":
                        return 2.0
                    elif key == "LLM_DAILY_COST_LIMIT":
                        return 100.0
                    elif key == "LLM_MONTHLY_COST_LIMIT":
                        return 2000.0
                    return default

                mock_get_int.side_effect = mock_int_env
                mock_get_float.side_effect = mock_float_env

                config = LLMConfig.from_environment()

                assert config.fallback_strategy == FallbackStrategy.COST_OPTIMIZED
                assert config.max_fallback_attempts == 5
                assert config.default_timeout == 45.0
                assert config.max_cost_per_request == 2.0
                assert config.daily_cost_limit == 100.0
                assert config.monthly_cost_limit == 2000.0

    def test_no_providers_configured(self):
        """Test behavior when no providers are configured."""
        # Clear all API keys
        with (
            patch("leadfactory.llm.config.OPENAI_API_KEY", None),
            patch("leadfactory.llm.config.ANTHROPIC_API_KEY", None),
            patch("leadfactory.llm.config.OLLAMA_HOST", None),
        ):
            config = LLMConfig.from_environment()

            # Should have empty providers dict or all disabled
            available_providers = config.get_available_providers()
            assert len(available_providers) == 0
