"""Tests for LLM exception handling and classification."""

import pytest
from leadfactory.llm.exceptions import (
    LLMError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMQuotaExceededError,
    LLMModelNotFoundError,
    LLMTimeoutError,
    LLMValidationError,
    LLMProviderError,
    AllProvidersFailedError,
    classify_error
)


class TestLLMError:
    """Test base LLM error class."""

    def test_init_basic(self):
        """Test basic initialization."""
        error = LLMError("Test error")
        assert str(error) == "Test error"
        assert error.provider is None
        assert error.status_code is None
        assert error.metadata == {}

    def test_init_with_details(self):
        """Test initialization with details."""
        metadata = {"key": "value"}
        error = LLMError("Test error", provider="openai", status_code=500, metadata=metadata)

        assert str(error) == "Test error"
        assert error.provider == "openai"
        assert error.status_code == 500
        assert error.metadata == metadata


class TestLLMRateLimitError:
    """Test rate limit error class."""

    def test_init_with_retry_after(self):
        """Test initialization with retry_after."""
        error = LLMRateLimitError("Rate limited", provider="openai", retry_after=60)

        assert str(error) == "Rate limited"
        assert error.provider == "openai"
        assert error.retry_after == 60


class TestAllProvidersFailedError:
    """Test all providers failed error."""

    def test_init(self):
        """Test initialization."""
        provider_errors = {
            "openai": Exception("OpenAI failed"),
            "anthropic": Exception("Anthropic failed")
        }

        error = AllProvidersFailedError(provider_errors)
        assert "All providers failed" in str(error)
        assert "openai: OpenAI failed" in str(error)
        assert "anthropic: Anthropic failed" in str(error)
        assert error.provider_errors == provider_errors


class TestErrorClassification:
    """Test error classification functionality."""

    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        test_cases = [
            "Connection refused",
            "Network timeout",
            "DNS resolution failed",
            "Connection timeout",
            "Host unreachable"
        ]

        for message in test_cases:
            error = Exception(message)
            classified = classify_error(error, "test_provider")

            assert isinstance(classified, LLMConnectionError)
            assert classified.provider == "test_provider"
            assert message in str(classified)

    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        test_cases = [
            "Rate limit exceeded",
            "Too many requests",
            "Quota exceeded"
        ]

        for message in test_cases:
            error = Exception(message)
            classified = classify_error(error, "test_provider")

            assert isinstance(classified, LLMRateLimitError)
            assert classified.provider == "test_provider"

    def test_classify_rate_limit_with_status_code(self):
        """Test classification with status code 429."""
        error = Exception("Some error")
        error.status_code = 429

        classified = classify_error(error, "test_provider")
        assert isinstance(classified, LLMRateLimitError)
        assert classified.status_code == 429

    def test_classify_authentication_error(self):
        """Test classification of authentication errors."""
        test_cases = [
            ("Unauthorized", 401),
            ("Invalid API key", None),
            ("Authentication failed", None),
            ("Forbidden", 403)
        ]

        for message, status_code in test_cases:
            error = Exception(message)
            if status_code:
                error.status_code = status_code

            classified = classify_error(error, "test_provider")
            assert isinstance(classified, LLMAuthenticationError)

    def test_classify_quota_exceeded_error(self):
        """Test classification of quota exceeded errors."""
        test_cases = [
            ("Quota exceeded", None),
            ("Billing limit reached", None),
            ("Payment required", 402),
            ("Insufficient credits", None)
        ]

        for message, status_code in test_cases:
            error = Exception(message)
            if status_code:
                error.status_code = status_code

            classified = classify_error(error, "test_provider")
            assert isinstance(classified, LLMQuotaExceededError)

    def test_classify_model_not_found_error(self):
        """Test classification of model not found errors."""
        test_cases = [
            ("Model not found", 404),
            ("Invalid model", None),
            ("Model does not exist", None)
        ]

        for message, status_code in test_cases:
            error = Exception(message)
            if status_code:
                error.status_code = status_code

            classified = classify_error(error, "test_provider")
            assert isinstance(classified, LLMModelNotFoundError)

    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        test_cases = [
            ("Request timeout", 408),
            ("Timed out", None),
            ("Operation timeout", None)
        ]

        for message, status_code in test_cases:
            error = Exception(message)
            if status_code:
                error.status_code = status_code

            classified = classify_error(error, "test_provider")
            assert isinstance(classified, LLMTimeoutError)

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        test_cases = [
            ("Validation failed", 400),
            ("Invalid request", None),
            ("Bad request", 400)
        ]

        for message, status_code in test_cases:
            error = Exception(message)
            if status_code:
                error.status_code = status_code

            classified = classify_error(error, "test_provider")
            assert isinstance(classified, LLMValidationError)

    def test_classify_generic_error(self):
        """Test classification of generic errors."""
        error = Exception("Some unknown error")
        classified = classify_error(error, "test_provider")

        assert isinstance(classified, LLMProviderError)
        assert classified.provider == "test_provider"

    def test_classify_rate_limit_with_retry_after(self):
        """Test extraction of retry-after from rate limit messages."""
        test_cases = [
            ("Rate limit exceeded. Retry after: 60 seconds", 60),
            ("Too many requests. Retry-after 30", 30),
            ("Quota exceeded, retry after 120 seconds", 120),
            ("Rate limited", None)  # No retry-after info
        ]

        for message, expected_retry_after in test_cases:
            error = Exception(message)
            classified = classify_error(error, "test_provider")

            assert isinstance(classified, LLMRateLimitError)
            assert classified.retry_after == expected_retry_after
