"""
Tests for the LLM client with fallback mechanisms.

This module tests the unified LLM client including fallback behavior,
error handling, rate limiting, and cost tracking.
"""

import json
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.llm import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMModelNotFoundError,
    LLMProvider,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from leadfactory.llm.config import FallbackStrategy, ProviderConfig


@pytest.fixture
def mock_config():
    """Create a mock LLM configuration for testing."""
    config = LLMConfig()

    # Configure OpenAI provider
    config.providers[LLMProvider.OPENAI] = ProviderConfig(
        provider=LLMProvider.OPENAI,
        api_key="mock-openai-key",
        default_model="gpt-4o",
        available_models=["gpt-4o", "gpt-3.5-turbo"],
        max_tokens=4096,
        timeout=30.0,
        cost_per_input_token=0.005 / 1000,
        cost_per_output_token=0.015 / 1000,
        enabled=True,
        priority=1,
    )

    # Configure Anthropic provider
    config.providers[LLMProvider.ANTHROPIC] = ProviderConfig(
        provider=LLMProvider.ANTHROPIC,
        api_key="mock-anthropic-key",
        default_model="claude-3-opus-20240229",
        available_models=["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
        max_tokens=4096,
        timeout=30.0,
        cost_per_input_token=0.015 / 1000,
        cost_per_output_token=0.075 / 1000,
        enabled=True,
        priority=2,
    )

    # Configure Ollama provider
    config.providers[LLMProvider.OLLAMA] = ProviderConfig(
        provider=LLMProvider.OLLAMA,
        base_url="http://localhost:11434",
        default_model="llama3:8b",
        available_models=["llama3:8b", "llama3:70b"],
        max_tokens=2048,
        timeout=60.0,
        cost_per_input_token=0.0,
        cost_per_output_token=0.0,
        enabled=True,
        priority=3,
    )

    config.fallback_strategy = FallbackStrategy.SMART_FALLBACK
    config.max_fallback_attempts = 3

    return config


@pytest.fixture
def mock_usage_tracker():
    """Create a mock usage tracker."""
    with patch("leadfactory.llm.client.GPTUsageTracker") as mock_tracker_class:
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker
        yield mock_tracker


@pytest.fixture
def llm_client(mock_config, mock_usage_tracker):
    """Create an LLM client with mocked dependencies."""
    with patch(
        "leadfactory.llm.client.LLMConfig.from_environment", return_value=mock_config
    ):
        client = LLMClient(mock_config)
        return client


class TestLLMClientInitialization:
    """Test LLM client initialization."""

    def test_client_initialization_with_config(self, mock_config, mock_usage_tracker):
        """Test client initialization with provided config."""
        client = LLMClient(mock_config)

        assert client.config == mock_config
        assert len(client.config.get_available_providers()) == 3

    def test_client_initialization_without_config(
        self, mock_config, mock_usage_tracker
    ):
        """Test client initialization loads config from environment."""
        with patch(
            "leadfactory.llm.client.LLMConfig.from_environment",
            return_value=mock_config,
        ):
            client = LLMClient()
            assert client.config is not None

    def test_rate_limiters_initialized(self, llm_client):
        """Test that rate limiters are initialized for all providers."""
        assert len(llm_client._rate_limiters) == 3
        assert LLMProvider.OPENAI in llm_client._rate_limiters
        assert LLMProvider.ANTHROPIC in llm_client._rate_limiters
        assert LLMProvider.OLLAMA in llm_client._rate_limiters


class TestProviderClients:
    """Test provider client creation and management."""

    @patch("openai.OpenAI")
    def test_create_openai_client(self, mock_openai_class, llm_client):
        """Test OpenAI client creation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = llm_client._get_provider_client(LLMProvider.OPENAI)

        assert client == mock_client
        mock_openai_class.assert_called_once_with(
            api_key="mock-openai-key", timeout=30.0, max_retries=0
        )

    @patch("anthropic.Anthropic")
    def test_create_anthropic_client(self, mock_anthropic_class, llm_client):
        """Test Anthropic client creation."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        client = llm_client._get_provider_client(LLMProvider.ANTHROPIC)

        assert client == mock_client
        mock_anthropic_class.assert_called_once_with(
            api_key="mock-anthropic-key", timeout=30.0, max_retries=0
        )

    @patch("requests.Session")
    def test_create_ollama_client(self, mock_session_class, llm_client):
        """Test Ollama client creation."""
        mock_client = Mock()
        mock_session_class.return_value = mock_client

        client = llm_client._get_provider_client(LLMProvider.OLLAMA)

        assert client == mock_client
        mock_session_class.assert_called_once()

    def test_client_caching(self, llm_client):
        """Test that provider clients are cached."""
        with patch("requests.Session") as mock_session_class:
            mock_client = Mock()
            mock_session_class.return_value = mock_client

            # First call creates client
            client1 = llm_client._get_provider_client(LLMProvider.OLLAMA)
            # Second call returns cached client
            client2 = llm_client._get_provider_client(LLMProvider.OLLAMA)

            assert client1 == client2
            mock_session_class.assert_called_once()


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_check_no_limits(self, llm_client):
        """Test rate limit check when no limits are set."""
        result = llm_client._check_rate_limits(LLMProvider.OPENAI, 100)
        assert result is True

    def test_rate_limit_rpm_exceeded(self, llm_client):
        """Test RPM rate limit exceeded."""
        # Set RPM limit
        llm_client.config.providers[LLMProvider.OPENAI].rate_limit_rpm = 5

        # Fill up the rate limiter
        rate_limiter = llm_client._rate_limiters[LLMProvider.OPENAI]
        now = time.time()
        rate_limiter["requests"] = [now] * 5  # Exactly at limit

        # Should still allow one more
        result = llm_client._check_rate_limits(LLMProvider.OPENAI, 100)
        assert result is True

        # Add one more to exceed limit
        rate_limiter["requests"].append(now)
        result = llm_client._check_rate_limits(LLMProvider.OPENAI, 100)
        assert result is False

    def test_rate_limit_tpm_exceeded(self, llm_client):
        """Test TPM rate limit exceeded."""
        # Set TPM limit
        llm_client.config.providers[LLMProvider.OPENAI].rate_limit_tpm = 1000

        # Fill up the rate limiter
        rate_limiter = llm_client._rate_limiters[LLMProvider.OPENAI]
        now = time.time()
        rate_limiter["tokens"] = [(now, 500), (now, 400)]  # 900 tokens

        # Should allow 100 more tokens
        result = llm_client._check_rate_limits(LLMProvider.OPENAI, 100)
        assert result is True

        # Should not allow 200 more tokens
        result = llm_client._check_rate_limits(LLMProvider.OPENAI, 200)
        assert result is False

    def test_rate_limit_cleanup(self, llm_client):
        """Test that old rate limit entries are cleaned up."""
        rate_limiter = llm_client._rate_limiters[LLMProvider.OPENAI]

        # Add old entries (more than 1 minute ago)
        old_time = time.time() - 120  # 2 minutes ago
        rate_limiter["requests"] = [old_time] * 3
        rate_limiter["tokens"] = [(old_time, 100)] * 3

        # Check rate limits (this should clean up old entries)
        llm_client._check_rate_limits(LLMProvider.OPENAI, 100)

        # Old entries should be cleaned up
        assert len(rate_limiter["requests"]) == 0
        assert len(rate_limiter["tokens"]) == 0


class TestChatCompletion:
    """Test chat completion functionality."""

    def test_successful_completion_openai(self, llm_client):
        """Test successful completion with OpenAI."""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock OpenAI client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 15
        mock_response.model = "gpt-4o"

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = llm_client.chat_completion(messages)

            assert (
                result["choices"][0]["message"]["content"]
                == "Hello! How can I help you?"
            )
            assert result["usage"]["total_tokens"] == 15
            assert result["provider"] == LLMProvider.OPENAI.value

    def test_successful_completion_anthropic(self, llm_client):
        """Test successful completion with Anthropic."""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock Anthropic client
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Hello! How can I help you?"
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 10
        mock_response.model = "claude-3-opus-20240229"

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            # Force use of Anthropic
            result = llm_client.chat_completion(
                messages, provider=LLMProvider.ANTHROPIC
            )

            assert (
                result["choices"][0]["message"]["content"]
                == "Hello! How can I help you?"
            )
            assert result["usage"]["total_tokens"] == 15
            assert result["provider"] == LLMProvider.ANTHROPIC.value

    def test_successful_completion_ollama(self, llm_client):
        """Test successful completion with Ollama."""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock Ollama response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello! How can I help you?",
            "done": True,
        }

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            # Force use of Ollama
            result = llm_client.chat_completion(messages, provider=LLMProvider.OLLAMA)

            assert (
                result["choices"][0]["message"]["content"]
                == "Hello! How can I help you?"
            )
            assert result["provider"] == LLMProvider.OLLAMA.value

    def test_fallback_on_rate_limit(self, llm_client):
        """Test fallback when primary provider is rate limited."""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock successful Anthropic response
        mock_anthropic_response = Mock()
        mock_anthropic_response.content = [Mock()]
        mock_anthropic_response.content[0].text = "Hello from Claude!"
        mock_anthropic_response.stop_reason = "end_turn"
        mock_anthropic_response.usage.input_tokens = 5
        mock_anthropic_response.usage.output_tokens = 10
        mock_anthropic_response.model = "claude-3-opus-20240229"

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:

            def side_effect(provider):
                if provider == LLMProvider.OPENAI:
                    # First call raises rate limit error
                    mock_openai_client = Mock()
                    mock_openai_client.chat.completions.create.side_effect = (
                        LLMRateLimitError(
                            "Rate limit exceeded", provider=LLMProvider.OPENAI.value
                        )
                    )
                    return mock_openai_client
                elif provider == LLMProvider.ANTHROPIC:
                    # Second call succeeds
                    mock_anthropic_client = Mock()
                    mock_anthropic_client.messages.create.return_value = (
                        mock_anthropic_response
                    )
                    return mock_anthropic_client

            mock_get_client.side_effect = side_effect

            result = llm_client.chat_completion(messages)

            # Should get response from Anthropic (fallback)
            assert result["choices"][0]["message"]["content"] == "Hello from Claude!"
            assert result["provider"] == LLMProvider.ANTHROPIC.value

    def test_all_providers_fail(self, llm_client):
        """Test behavior when all providers fail."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:

            def side_effect(provider):
                mock_client = Mock()
                if provider == LLMProvider.OPENAI:
                    mock_client.chat.completions.create.side_effect = LLMRateLimitError(
                        "Rate limit exceeded", provider=LLMProvider.OPENAI.value
                    )
                elif provider == LLMProvider.ANTHROPIC:
                    mock_client.messages.create.side_effect = LLMAuthenticationError(
                        "Invalid API key", provider=LLMProvider.ANTHROPIC.value
                    )
                elif provider == LLMProvider.OLLAMA:
                    mock_client.post.side_effect = LLMServiceUnavailableError(
                        "Service unavailable", provider=LLMProvider.OLLAMA.value
                    )
                return mock_client

            mock_get_client.side_effect = side_effect

            with pytest.raises(LLMError) as exc_info:
                llm_client.chat_completion(messages)

            assert "All LLM providers failed" in str(exc_info.value)

    def test_specific_provider_failure(self, llm_client):
        """Test failure when using specific provider with fallback disabled."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = LLMAuthenticationError(
                "Invalid API key", provider=LLMProvider.OPENAI.value
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(LLMAuthenticationError):
                llm_client.chat_completion(
                    messages, provider=LLMProvider.OPENAI, fallback=False
                )

    def test_cost_limit_exceeded(self, llm_client):
        """Test behavior when cost limit is exceeded."""
        messages = [{"role": "user", "content": "Hello"}]

        # Set a very low cost limit
        llm_client.config.max_cost_per_request = 0.0001

        with pytest.raises(LLMQuotaExceededError) as exc_info:
            llm_client.chat_completion(messages)

        assert "exceeds cost limit" in str(exc_info.value)


class TestFallbackStrategies:
    """Test different fallback strategies."""

    def test_fail_fast_strategy(self, llm_client):
        """Test fail fast strategy doesn't fallback."""
        llm_client.config.fallback_strategy = FallbackStrategy.FAIL_FAST
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = LLMRateLimitError(
                "Rate limit exceeded", provider=LLMProvider.OPENAI.value
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                llm_client.chat_completion(messages)

            # Should only be called once (no fallback)
            assert mock_get_client.call_count == 1

    def test_cost_optimized_strategy(self, llm_client):
        """Test cost optimized strategy tries cheapest first."""
        llm_client.config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED

        fallback_order = llm_client.config.get_fallback_order()

        # Ollama should be first (free), then OpenAI, then Anthropic
        assert fallback_order[0].provider == LLMProvider.OLLAMA
        assert fallback_order[1].provider == LLMProvider.OPENAI
        assert fallback_order[2].provider == LLMProvider.ANTHROPIC


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_available_models(self, llm_client):
        """Test getting available models."""
        models = llm_client.get_available_models()

        assert "openai" in models
        assert "anthropic" in models
        assert "ollama" in models
        assert "gpt-4o" in models["openai"]
        assert "claude-3-opus-20240229" in models["anthropic"]
        assert "llama3:8b" in models["ollama"]

    def test_get_available_models_specific_provider(self, llm_client):
        """Test getting models for specific provider."""
        models = llm_client.get_available_models(LLMProvider.OPENAI)

        assert "openai" in models
        assert len(models) == 1
        assert "gpt-4o" in models["openai"]

    def test_get_provider_status(self, llm_client):
        """Test getting provider status."""
        status = llm_client.get_provider_status()

        assert "openai" in status
        assert "anthropic" in status
        assert "ollama" in status

        openai_status = status["openai"]
        assert openai_status["available"] is True
        assert openai_status["enabled"] is True
        assert openai_status["priority"] == 1

    def test_estimate_cost(self, llm_client):
        """Test cost estimation."""
        messages = [{"role": "user", "content": "Hello world"}]

        # Test all providers
        costs = llm_client.estimate_cost(messages, 100)
        assert "openai" in costs
        assert "anthropic" in costs
        assert "ollama" in costs
        assert costs["ollama"] == 0.0  # Free
        assert costs["openai"] > 0.0
        assert costs["anthropic"] > 0.0

        # Test specific provider
        openai_cost = llm_client.estimate_cost(messages, 100, LLMProvider.OPENAI)
        assert openai_cost == costs["openai"]

    def test_token_estimation(self, llm_client):
        """Test token count estimation."""
        # Short message
        short_messages = [{"role": "user", "content": "Hi"}]
        short_tokens = llm_client._estimate_token_count(short_messages)

        # Long message
        long_messages = [
            {
                "role": "user",
                "content": "This is a much longer message that should have more tokens",
            }
        ]
        long_tokens = llm_client._estimate_token_count(long_messages)

        assert long_tokens > short_tokens
        assert short_tokens >= 1  # Minimum 1 token


class TestErrorHandling:
    """Test error handling and exception mapping."""

    def test_openai_error_mapping(self, llm_client):
        """Test that OpenAI errors are properly mapped."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()

            # Mock different OpenAI error types
            openai_error = Exception("Rate limit exceeded")
            openai_error.status_code = 429
            mock_client.chat.completions.create.side_effect = openai_error
            mock_get_client.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                llm_client.chat_completion(
                    messages, provider=LLMProvider.OPENAI, fallback=False
                )

    def test_usage_tracking_on_success(self, llm_client):
        """Test that usage is tracked on successful requests."""
        messages = [{"role": "user", "content": "Hello"}]

        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 15
        mock_response.model = "gpt-4o"

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            llm_client.chat_completion(messages, provider=LLMProvider.OPENAI)

            # Verify usage was tracked
            llm_client.usage_tracker.track_usage.assert_called_once()
            call_args = llm_client.usage_tracker.track_usage.call_args
            assert call_args[1]["success"] is True
            assert call_args[1]["input_tokens"] == 5
            assert call_args[1]["output_tokens"] == 10

    def test_usage_tracking_on_failure(self, llm_client):
        """Test that usage is tracked on failed requests."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(llm_client, "_get_provider_client") as mock_get_client:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = LLMRateLimitError(
                "Rate limit exceeded", provider=LLMProvider.OPENAI.value
            )
            mock_get_client.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                llm_client.chat_completion(
                    messages, provider=LLMProvider.OPENAI, fallback=False
                )

            # Verify usage was tracked
            llm_client.usage_tracker.track_usage.assert_called()
            call_args = llm_client.usage_tracker.track_usage.call_args
            assert call_args[1]["success"] is False
            assert "Rate limit exceeded" in call_args[1]["error_message"]
