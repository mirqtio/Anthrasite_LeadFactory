"""
Integration tests for OpenAI API.

These tests verify that the OpenAI API integration works correctly.
They will run with mocks by default, but can use the real API when --use-real-apis is specified.
"""

import os
from unittest.mock import patch

import pytest

from tests.integration.api_test_config import APITestConfig


def test_openai_chat_completion_basic(openai_api, api_metrics_logger):
    """Test basic chat completion functionality."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ]

    result = openai_api.chat_completion(
        messages=messages,
        model="gpt-3.5-turbo",  # Use cheaper model for testing
        metrics_logger=api_metrics_logger,
    )

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "message" in result["choices"][0]
    assert "content" in result["choices"][0]["message"]

    # Check for expected content in real API response
    if APITestConfig.should_use_real_api("openai"):
        content = result["choices"][0]["message"]["content"]
        assert "Paris" in content, f"Expected 'Paris' in response, got: {content}"


@pytest.mark.parametrize(
    "prompt",
    [
        "Explain quantum computing in simple terms",
        "Write a short poem about programming",
        "What are the key features of Python?",
        "How does a refrigerator work?",
    ],
)
def test_openai_different_prompts(openai_api, api_metrics_logger, prompt):
    """Test chat completion with different prompts."""
    messages = [
        {"role": "system", "content": "You are a helpful, concise assistant."},
        {"role": "user", "content": prompt},
    ]

    result = openai_api.chat_completion(
        messages=messages,
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=100,  # Limit token usage for testing
        metrics_logger=api_metrics_logger,
    )

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "message" in result["choices"][0]
    assert "content" in result["choices"][0]["message"]

    # For real API, check that response is relevant to prompt
    if APITestConfig.should_use_real_api("openai"):
        content = result["choices"][0]["message"]["content"].lower()
        # Extract keywords from prompt to check relevance
        keywords = [word.lower() for word in prompt.split() if len(word) > 4]
        relevant = any(keyword in content for keyword in keywords)
        assert relevant, f"Response does not seem relevant to prompt: {prompt}"


@pytest.mark.parametrize("model", ["gpt-3.5-turbo", "gpt-4o"])
def test_openai_different_models(openai_api, api_metrics_logger, model):
    """Test chat completion with different models."""
    # Skip GPT-4 tests unless specifically enabled to avoid high costs
    if model == "gpt-4o" and not os.environ.get("ENABLE_GPT4_TESTS"):
        pytest.skip("GPT-4 tests disabled by default to avoid costs")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ]

    result = openai_api.chat_completion(
        messages=messages,
        model=model,
        max_tokens=10,  # Limit token usage for testing
        metrics_logger=api_metrics_logger,
    )

    assert "choices" in result
    assert len(result["choices"]) > 0
    assert "message" in result["choices"][0]
    assert "content" in result["choices"][0]["message"]

    # For real API, check model used
    if APITestConfig.should_use_real_api("openai"):
        assert "model" in result
        assert model in result["model"], (
            f"Expected model {model}, got: {result['model']}"
        )


def test_openai_token_usage_tracking(openai_api, api_metrics_logger):
    """Test token usage tracking in the OpenAI API responses."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Respond with exactly 10 words."},
    ]

    result = openai_api.chat_completion(
        messages=messages, model="gpt-3.5-turbo", metrics_logger=api_metrics_logger
    )

    assert "choices" in result

    # Check usage statistics
    if APITestConfig.should_use_real_api("openai"):
        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]
        assert "total_tokens" in result["usage"]
        assert result["usage"]["total_tokens"] > 0
        assert result["usage"]["prompt_tokens"] > 0
        assert result["usage"]["completion_tokens"] > 0
        assert (
            result["usage"]["total_tokens"]
            == result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"]
        )


@pytest.mark.real_api
def test_openai_api_error_handling(openai_api):
    """Test error handling in the OpenAI API client."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("openai"):
        pytest.skip("Test requires real API connection")

    # Test with invalid API key
    with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid_key"}):
        # Create a new client with invalid key
        from tests.integration.api_fixtures import openai_api as openai_api_fixture

        invalid_openai_api = openai_api_fixture(None)

        # Test error handling
        with pytest.raises(Exception) as excinfo:
            invalid_openai_api.chat_completion(
                messages=[{"role": "user", "content": "test"}], model="gpt-3.5-turbo"
            )

        assert any(
            term in str(excinfo.value).lower()
            for term in ["authentication", "api key", "invalid", "unauthorized"]
        )


@pytest.mark.real_api
def test_openai_api_invalid_model(openai_api):
    """Test error handling for an invalid model."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("openai"):
        pytest.skip("Test requires real API connection")

    # Test with invalid model
    with pytest.raises(Exception) as excinfo:
        openai_api.chat_completion(
            messages=[{"role": "user", "content": "test"}], model="nonexistent-model"
        )

    assert any(
        term in str(excinfo.value).lower()
        for term in ["model", "invalid", "not found", "nonexistent"]
    )


@pytest.mark.real_api
def test_openai_api_cost_tracking(openai_api, api_metrics_logger):
    """Test that API cost tracking works correctly."""
    # Only run with real API
    if not APITestConfig.should_use_real_api("openai"):
        pytest.skip("Test requires real API connection")

    # Clear previous metrics
    api_metrics_logger.metrics = []

    # Make API call
    openai_api.chat_completion(
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        model="gpt-3.5-turbo",
        metrics_logger=api_metrics_logger,
    )

    # Check that metrics were logged
    assert len(api_metrics_logger.metrics) > 0
    metric = api_metrics_logger.metrics[0]
    assert metric["api"] == "openai"
    assert metric["endpoint"] == "chat_completion"
    assert metric["latency"] > 0

    # Check cost tracking (may be 0 for mock API)
    if APITestConfig.should_use_real_api("openai"):
        assert "cost" in metric
        assert metric["cost"] >= 0
        assert "tokens" in metric
        assert metric["tokens"] > 0
