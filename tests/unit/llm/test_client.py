"""Tests for LLM client functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from leadfactory.llm.client import LLMClient, RateLimiter
from leadfactory.llm.config import LLMConfig, ProviderConfig, FallbackStrategy
from leadfactory.llm.exceptions import (
    LLMError,
    LLMRateLimitError,
    AllProvidersFailedError,
    LLMQuotaExceededError
)


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rpm=60, tpm=1000)
        assert limiter.rpm == 60
        assert limiter.tpm == 1000
        assert limiter.request_times == []
        assert limiter.token_usage == []

    def test_wait_if_needed_no_limits(self):
        """Test wait when no rate limits are set."""
        limiter = RateLimiter()
        # Should not block
        start_time = time.time()
        limiter.wait_if_needed(100)
        elapsed = time.time() - start_time
        assert elapsed < 0.1  # Should be very fast

    @patch('time.sleep')
    def test_wait_if_needed_rpm_limit(self, mock_sleep):
        """Test wait when RPM limit is exceeded."""
        limiter = RateLimiter(rpm=2)  # Very low limit

        # Make requests to exceed limit
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        limiter.wait_if_needed()  # This should trigger rate limiting

        # Should have called sleep
        assert mock_sleep.called

    def test_request_tracking(self):
        """Test that requests are tracked properly."""
        limiter = RateLimiter(rpm=60)

        limiter.wait_if_needed(100)
        assert len(limiter.request_times) == 1
        assert len(limiter.token_usage) == 1
        assert limiter.token_usage[0][1] == 100


class TestLLMClient:
    """Test LLM client functionality."""

    def create_test_config(self):
        """Create a test configuration."""
        config = LLMConfig()
        config.providers = {
            'openai': ProviderConfig(
                name='openai',
                api_key='test-key',
                default_model='gpt-4',
                cost_per_1k_tokens=0.03
            ),
            'anthropic': ProviderConfig(
                name='anthropic',
                api_key='test-key',
                default_model='claude-3-sonnet-20240229',
                cost_per_1k_tokens=0.015
            ),
            'ollama': ProviderConfig(
                name='ollama',
                base_url='http://localhost:11434',
                default_model='llama3:8b',
                cost_per_1k_tokens=0.0
            )
        }
        return config

    @patch('leadfactory.llm.client.OPENAI_AVAILABLE', False)
    @patch('leadfactory.llm.client.ANTHROPIC_AVAILABLE', False)
    @patch('leadfactory.llm.client.REQUESTS_AVAILABLE', True)
    def test_init_only_ollama(self):
        """Test initialization with only Ollama available."""
        config = self.create_test_config()
        client = LLMClient(config)

        # Should only have ollama initialized
        assert 'ollama' in client._provider_clients
        assert 'openai' not in client._provider_clients
        assert 'anthropic' not in client._provider_clients

    def test_get_available_providers(self):
        """Test getting available providers."""
        config = self.create_test_config()

        with patch('leadfactory.llm.client.OPENAI_AVAILABLE', True), \
             patch('leadfactory.llm.client.ANTHROPIC_AVAILABLE', False), \
             patch('leadfactory.llm.client.REQUESTS_AVAILABLE', True):

            client = LLMClient(config)
            providers = client.get_available_providers()

            assert 'ollama' in providers
            # openai might be in providers depending on mock setup

    def test_estimate_tokens(self):
        """Test token estimation."""
        config = self.create_test_config()
        client = LLMClient(config)

        messages = [
            {"role": "user", "content": "Hello world"}
        ]
        max_tokens = 100

        estimated = client._estimate_tokens(messages, max_tokens)
        assert estimated > 100  # Should include input + max_tokens
        assert estimated < 200  # But not too high

    def test_check_cost_limits_within_limit(self):
        """Test cost checking when within limits."""
        config = self.create_test_config()
        config.cost_config.max_cost_per_request = 1.0
        client = LLMClient(config)

        # Should not raise exception
        client._check_cost_limits('openai', 1000)  # $0.03

    def test_check_cost_limits_exceeds_limit(self):
        """Test cost checking when exceeding limits."""
        config = self.create_test_config()
        config.cost_config.max_cost_per_request = 0.01
        client = LLMClient(config)

        # Should raise exception
        with pytest.raises(LLMQuotaExceededError):
            client._check_cost_limits('openai', 1000)  # $0.03 > $0.01

    def test_track_usage(self):
        """Test usage tracking."""
        config = self.create_test_config()
        client = LLMClient(config)

        usage = {'total_tokens': 1000}
        initial_cost = client._cost_tracker['openai']['daily_cost']

        client._track_usage('openai', usage)

        final_cost = client._cost_tracker['openai']['daily_cost']
        assert final_cost > initial_cost
        assert final_cost - initial_cost == 0.03  # 1000 tokens * $0.03/1k

    def test_generate_cache_key(self):
        """Test cache key generation."""
        config = self.create_test_config()
        client = LLMClient(config)

        messages = [{"role": "user", "content": "test"}]
        key1 = client._generate_cache_key(messages, "gpt-4", 0.7, 100, {})
        key2 = client._generate_cache_key(messages, "gpt-4", 0.7, 100, {})
        key3 = client._generate_cache_key(messages, "gpt-4", 0.8, 100, {})  # Different temp

        assert key1 == key2  # Same inputs should give same key
        assert key1 != key3  # Different inputs should give different key
        assert len(key1) == 32  # MD5 hash length

    def test_get_provider_status(self):
        """Test provider status reporting."""
        config = self.create_test_config()
        client = LLMClient(config)

        status = client.get_provider_status()

        assert 'openai' in status
        assert 'anthropic' in status
        assert 'ollama' in status

        for provider_name, provider_status in status.items():
            assert 'enabled' in provider_status
            assert 'available' in provider_status
            assert 'model' in provider_status
            assert 'cost_per_1k_tokens' in provider_status
            assert 'priority' in provider_status

    def test_clear_cache(self):
        """Test cache clearing."""
        config = self.create_test_config()
        client = LLMClient(config)

        # Add something to cache
        client._request_cache['test_key'] = {'test': 'value'}
        assert len(client._request_cache) == 1

        client.clear_cache()
        assert len(client._request_cache) == 0

    def test_reset_cost_tracking_single_provider(self):
        """Test resetting cost tracking for single provider."""
        config = self.create_test_config()
        client = LLMClient(config)

        # Track some usage
        client._cost_tracker['openai']['daily_cost'] = 10.0
        client._cost_tracker['openai']['monthly_cost'] = 50.0

        client.reset_cost_tracking('openai')

        assert client._cost_tracker['openai']['daily_cost'] == 0.0
        assert client._cost_tracker['openai']['monthly_cost'] == 0.0

    def test_reset_cost_tracking_all_providers(self):
        """Test resetting cost tracking for all providers."""
        config = self.create_test_config()
        client = LLMClient(config)

        # Track some usage
        for provider in client._cost_tracker:
            client._cost_tracker[provider]['daily_cost'] = 10.0
            client._cost_tracker[provider]['monthly_cost'] = 50.0

        client.reset_cost_tracking()

        for provider in client._cost_tracker:
            assert client._cost_tracker[provider]['daily_cost'] == 0.0
            assert client._cost_tracker[provider]['monthly_cost'] == 0.0

    @patch('leadfactory.llm.client.REQUESTS_AVAILABLE', True)
    def test_mock_ollama_request(self):
        """Test making a mock Ollama request."""
        config = self.create_test_config()
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Hello"}]

        # Mock the requests.post call
        mock_response = Mock()
        mock_response.json.return_value = {
            'message': {'role': 'assistant', 'content': 'Hello there!'},
            'prompt_eval_count': 10,
            'eval_count': 5
        }
        mock_response.raise_for_status = Mock()

        with patch('requests.post', return_value=mock_response):
            response = client._ollama_request(messages, 'llama3:8b', 0.7, 100)

            assert response['provider'] == 'ollama'
            assert response['model'] == 'llama3:8b'
            assert response['choices'][0]['message']['content'] == 'Hello there!'
            assert response['usage']['prompt_tokens'] == 10
            assert response['usage']['completion_tokens'] == 5

    def test_fallback_strategy_cost_optimized(self):
        """Test cost optimized fallback strategy."""
        config = self.create_test_config()
        config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED

        order = config.get_provider_order()

        # Should be ordered by cost (cheapest first)
        costs = [config.providers[name].cost_per_1k_tokens for name in order]
        assert costs == sorted(costs)

    def test_chat_completion_no_providers(self):
        """Test chat completion when no providers are available."""
        config = LLMConfig()
        config.providers = {}
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Hello"}]

        with pytest.raises(AllProvidersFailedError):
            client.chat_completion(messages)

    @patch('leadfactory.llm.client.REQUESTS_AVAILABLE', True)
    def test_chat_completion_with_caching(self):
        """Test chat completion with caching enabled."""
        config = self.create_test_config()
        config.enable_caching = True
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Hello"}]

        # Mock successful response
        mock_response = {
            'provider': 'ollama',
            'model': 'llama3:8b',
            'choices': [{'message': {'role': 'assistant', 'content': 'Hello!'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}
        }

        with patch.object(client, '_make_request', return_value=mock_response):
            # First call
            response1 = client.chat_completion(messages)

            # Second call should use cache
            response2 = client.chat_completion(messages)

            assert response1 == response2
            assert len(client._request_cache) == 1
