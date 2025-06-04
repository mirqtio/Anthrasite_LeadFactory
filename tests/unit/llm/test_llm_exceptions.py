"""
Tests for LLM exception handling and error classification.

This module tests the custom exception classes and error classification
logic for the LLM fallback system.
"""

import pytest

from leadfactory.llm.exceptions import (
    LLMError,
    LLMAPIError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMModelNotFoundError,
    LLMQuotaExceededError,
    LLMTimeoutError,
    LLMContextLengthError,
    LLMContentFilterError,
    LLMServiceUnavailableError,
    classify_error,
    create_llm_exception
)


class TestLLMExceptions:
    """Test LLM exception classes."""

    def test_base_llm_error(self):
        """Test base LLM error functionality."""
        error = LLMError(
            message="Test error",
            provider="openai",
            model="gpt-4o"
        )

        assert str(error) == "Test error (Provider: openai, Model: gpt-4o)"
        assert error.provider == "openai"
        assert error.model == "gpt-4o"
        assert error.original_error is None

    def test_llm_error_with_original_error(self):
        """Test LLM error with original exception."""
        original = ValueError("Original error")
        error = LLMError(
            message="Wrapped error",
            provider="anthropic",
            original_error=original
        )

        assert error.original_error == original
        assert str(error) == "Wrapped error (Provider: anthropic)"

    def test_llm_error_minimal(self):
        """Test LLM error with minimal information."""
        error = LLMError("Simple error")

        assert str(error) == "Simple error"
        assert error.provider is None
        assert error.model is None

    def test_llm_api_error(self):
        """Test LLM API error with status code."""
        error = LLMAPIError(
            message="API error",
            status_code=500,
            provider="openai",
            model="gpt-4o"
        )

        assert error.status_code == 500
        assert str(error) == "API error (Provider: openai, Model: gpt-4o)"

    def test_llm_rate_limit_error(self):
        """Test LLM rate limit error with retry information."""
        error = LLMRateLimitError(
            message="Rate limited",
            retry_after=60,
            provider="anthropic"
        )

        assert error.retry_after == 60
        assert str(error) == "Rate limited (Provider: anthropic)"

    def test_llm_authentication_error(self):
        """Test LLM authentication error."""
        error = LLMAuthenticationError(
            message="Invalid API key",
            provider="openai"
        )

        assert str(error) == "Invalid API key (Provider: openai)"

    def test_llm_model_not_found_error(self):
        """Test LLM model not found error with available models."""
        error = LLMModelNotFoundError(
            message="Model not found",
            available_models=["gpt-4o", "gpt-3.5-turbo"],
            provider="openai",
            model="gpt-5"
        )

        assert error.available_models == ["gpt-4o", "gpt-3.5-turbo"]
        assert str(error) == "Model not found (Provider: openai, Model: gpt-5)"

    def test_llm_quota_exceeded_error(self):
        """Test LLM quota exceeded error with quota type."""
        error = LLMQuotaExceededError(
            message="Daily quota exceeded",
            quota_type="daily",
            provider="anthropic"
        )

        assert error.quota_type == "daily"
        assert str(error) == "Daily quota exceeded (Provider: anthropic)"

    def test_llm_timeout_error(self):
        """Test LLM timeout error with duration."""
        error = LLMTimeoutError(
            message="Request timed out",
            timeout_duration=30.0,
            provider="ollama"
        )

        assert error.timeout_duration == 30.0
        assert str(error) == "Request timed out (Provider: ollama)"

    def test_llm_context_length_error(self):
        """Test LLM context length error with token information."""
        error = LLMContextLengthError(
            message="Context too long",
            max_tokens=4096,
            requested_tokens=5000,
            provider="openai",
            model="gpt-4o"
        )

        assert error.max_tokens == 4096
        assert error.requested_tokens == 5000
        assert str(error) == "Context too long (Provider: openai, Model: gpt-4o)"

    def test_llm_content_filter_error(self):
        """Test LLM content filter error."""
        error = LLMContentFilterError(
            message="Content filtered",
            filter_type="safety",
            provider="openai"
        )

        assert error.filter_type == "safety"
        assert str(error) == "Content filtered (Provider: openai)"

    def test_llm_service_unavailable_error(self):
        """Test LLM service unavailable error."""
        error = LLMServiceUnavailableError(
            message="Service down",
            estimated_recovery_time=300,
            provider="ollama"
        )

        assert error.estimated_recovery_time == 300
        assert str(error) == "Service down (Provider: ollama)"


class TestErrorClassification:
    """Test error classification logic."""

    def test_classify_rate_limit_patterns(self):
        """Test classification of rate limit error patterns."""
        patterns = [
            "rate_limit_exceeded",
            "rate limited",
            "too many requests"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMRateLimitError

    def test_classify_authentication_patterns(self):
        """Test classification of authentication error patterns."""
        patterns = [
            "invalid_api_key",
            "incorrect_api_key",
            "authentication_error",
            "permission_error"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMAuthenticationError

    def test_classify_quota_patterns(self):
        """Test classification of quota exceeded patterns."""
        patterns = [
            "quota_exceeded",
            "billing limit exceeded",
            "usage limit reached"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMQuotaExceededError

    def test_classify_model_not_found_patterns(self):
        """Test classification of model not found patterns."""
        patterns = [
            "model_not_found",
            "model does not exist",
            "invalid model"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMModelNotFoundError

    def test_classify_service_unavailable_patterns(self):
        """Test classification of service unavailable patterns."""
        patterns = [
            "service_unavailable",
            "overloaded_error",
            "connection_error",
            "server error"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMServiceUnavailableError

    def test_classify_timeout_patterns(self):
        """Test classification of timeout patterns."""
        patterns = [
            "timeout",
            "request timed out",
            "deadline exceeded"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMTimeoutError

    def test_classify_context_length_patterns(self):
        """Test classification of context length patterns."""
        patterns = [
            "context_length_exceeded",
            "maximum context length",
            "token limit exceeded"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMContextLengthError

    def test_classify_content_filter_patterns(self):
        """Test classification of content filter patterns."""
        patterns = [
            "content_filter",
            "content policy violation",
            "inappropriate content"
        ]

        for pattern in patterns:
            error_class = classify_error(pattern)
            assert error_class == LLMContentFilterError

    def test_classify_by_status_code(self):
        """Test classification based on HTTP status codes."""
        status_code_mappings = {
            401: LLMAuthenticationError,
            403: LLMAuthenticationError,
            404: LLMModelNotFoundError,
            429: LLMRateLimitError,
            500: LLMServiceUnavailableError,
            502: LLMServiceUnavailableError,
            503: LLMServiceUnavailableError,
            504: LLMTimeoutError
        }

        for status_code, expected_class in status_code_mappings.items():
            error_class = classify_error("generic error", status_code=status_code)
            assert error_class == expected_class

    def test_classify_unknown_error(self):
        """Test classification of unknown error falls back to general API error."""
        error_class = classify_error("some unknown error")
        assert error_class == LLMAPIError

    def test_classify_with_provider_context(self):
        """Test classification with provider context."""
        # Provider-specific patterns
        error_class = classify_error(
            "rate limited",
            provider="anthropic"
        )
        assert error_class == LLMRateLimitError

        error_class = classify_error(
            "model not loaded",
            provider="ollama"
        )
        assert error_class == LLMModelNotFoundError


class TestCreateLLMException:
    """Test the create_llm_exception factory function."""

    def test_create_rate_limit_exception(self):
        """Test creating rate limit exception."""
        exception = create_llm_exception(
            error_message="Rate limit exceeded",
            provider="openai",
            model="gpt-4o",
            status_code=429,
            retry_after=60
        )

        assert isinstance(exception, LLMRateLimitError)
        assert exception.provider == "openai"
        assert exception.model == "gpt-4o"
        assert exception.retry_after == 60

    def test_create_authentication_exception(self):
        """Test creating authentication exception."""
        original_error = ValueError("Invalid key")
        exception = create_llm_exception(
            error_message="Invalid API key",
            provider="anthropic",
            status_code=401,
            original_error=original_error
        )

        assert isinstance(exception, LLMAuthenticationError)
        assert exception.provider == "anthropic"
        assert exception.original_error == original_error

    def test_create_model_not_found_exception(self):
        """Test creating model not found exception."""
        exception = create_llm_exception(
            error_message="Model not found",
            provider="openai",
            model="nonexistent-model",
            status_code=404,
            available_models=["gpt-4o", "gpt-3.5-turbo"]
        )

        assert isinstance(exception, LLMModelNotFoundError)
        assert exception.model == "nonexistent-model"
        assert exception.available_models == ["gpt-4o", "gpt-3.5-turbo"]

    def test_create_quota_exceeded_exception(self):
        """Test creating quota exceeded exception."""
        exception = create_llm_exception(
            error_message="Daily quota exceeded",
            provider="anthropic",
            quota_type="daily"
        )

        assert isinstance(exception, LLMQuotaExceededError)
        assert exception.quota_type == "daily"

    def test_create_timeout_exception(self):
        """Test creating timeout exception."""
        exception = create_llm_exception(
            error_message="Request timed out",
            provider="ollama",
            status_code=504,
            timeout_duration=30.0
        )

        assert isinstance(exception, LLMTimeoutError)
        assert exception.timeout_duration == 30.0

    def test_create_service_unavailable_exception(self):
        """Test creating service unavailable exception."""
        exception = create_llm_exception(
            error_message="Service temporarily unavailable",
            provider="ollama",
            status_code=503,
            estimated_recovery_time=300
        )

        assert isinstance(exception, LLMServiceUnavailableError)
        assert exception.estimated_recovery_time == 300

    def test_create_context_length_exception(self):
        """Test creating context length exception."""
        exception = create_llm_exception(
            error_message="Context length exceeded",
            provider="openai",
            model="gpt-4o",
            max_tokens=4096,
            requested_tokens=5000
        )

        assert isinstance(exception, LLMContextLengthError)
        assert exception.max_tokens == 4096
        assert exception.requested_tokens == 5000

    def test_create_content_filter_exception(self):
        """Test creating content filter exception."""
        exception = create_llm_exception(
            error_message="Content filtered for safety",
            provider="openai",
            filter_type="safety"
        )

        assert isinstance(exception, LLMContentFilterError)
        assert exception.filter_type == "safety"

    def test_create_generic_api_exception(self):
        """Test creating generic API exception for unknown errors."""
        exception = create_llm_exception(
            error_message="Unknown error occurred",
            provider="openai",
            model="gpt-4o",
            status_code=418  # Unknown status code
        )

        assert isinstance(exception, LLMAPIError)
        assert exception.status_code == 418
        assert exception.provider == "openai"
        assert exception.model == "gpt-4o"

    def test_preserve_all_parameters(self):
        """Test that all parameters are preserved in created exceptions."""
        original_error = Exception("Original")
        exception = create_llm_exception(
            error_message="Test error",
            provider="test_provider",
            model="test_model",
            status_code=500,
            original_error=original_error,
            custom_field="custom_value"
        )

        assert exception.provider == "test_provider"
        assert exception.model == "test_model"
        assert exception.original_error == original_error
        # Custom fields should be passed through
        assert hasattr(exception, 'custom_field')
        assert exception.custom_field == "custom_value"
