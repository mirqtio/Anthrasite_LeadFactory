"""
Exception classes for LLM fallback system.

This module defines specific exception types for different LLM failure modes
to enable intelligent error handling and provider selection.
"""

import re
from typing import Any, Dict, Optional


class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        status_code: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.metadata = metadata or {}


class LLMConnectionError(LLMError):
    """Network connection error when calling LLM API."""

    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, provider, **kwargs)
        self.retry_after = retry_after


class LLMAuthenticationError(LLMError):
    """Authentication/authorization error."""

    pass


class LLMQuotaExceededError(LLMError):
    """Quota or billing limit exceeded."""

    pass


class LLMModelNotFoundError(LLMError):
    """Requested model not found or not available."""

    pass


class LLMTimeoutError(LLMError):
    """Request timeout error."""

    pass


class LLMValidationError(LLMError):
    """Input validation error."""

    pass


class LLMProviderError(LLMError):
    """General provider-specific error."""

    pass


class AllProvidersFailedError(LLMError):
    """All configured providers failed."""

    def __init__(self, provider_errors: Dict[str, Exception]):
        self.provider_errors = provider_errors
        error_summary = ", ".join(
            [f"{provider}: {str(error)}" for provider, error in provider_errors.items()]
        )
        super().__init__(f"All providers failed: {error_summary}")


def classify_error(error: Exception, provider: str) -> LLMError:
    """
    Classify a raw exception into an appropriate LLM exception type.

    Args:
        error: The original exception
        provider: The provider that generated the error

    Returns:
        Classified LLMError subclass
    """
    error_message = str(error)
    status_code = getattr(error, "status_code", None)

    # Connection errors
    if any(
        keyword in error_message.lower()
        for keyword in ["connection", "network", "timeout", "unreachable", "dns"]
    ):
        return LLMConnectionError(error_message, provider, status_code)

    # Rate limit errors
    if (
        any(
            keyword in error_message.lower()
            for keyword in ["rate limit", "too many requests", "quota exceeded"]
        )
        or status_code == 429
    ):
        # Try to extract retry-after from message
        retry_match = re.search(
            r"retry[- ]after[:\s]+(\d+)", error_message, re.IGNORECASE
        )
        retry_after = int(retry_match.group(1)) if retry_match else None
        return LLMRateLimitError(
            error_message, provider, retry_after, status_code=status_code
        )

    # Authentication errors
    if any(
        keyword in error_message.lower()
        for keyword in [
            "unauthorized",
            "authentication",
            "invalid api key",
            "forbidden",
        ]
    ) or status_code in [401, 403]:
        return LLMAuthenticationError(error_message, provider, status_code)

    # Quota/billing errors
    if (
        any(
            keyword in error_message.lower()
            for keyword in [
                "quota",
                "billing",
                "payment required",
                "insufficient credits",
            ]
        )
        or status_code == 402
    ):
        return LLMQuotaExceededError(error_message, provider, status_code)

    # Model not found
    if (
        any(
            keyword in error_message.lower()
            for keyword in ["model not found", "invalid model", "model does not exist"]
        )
        or status_code == 404
    ):
        return LLMModelNotFoundError(error_message, provider, status_code)

    # Timeout errors
    if (
        any(keyword in error_message.lower() for keyword in ["timeout", "timed out"])
        or status_code == 408
    ):
        return LLMTimeoutError(error_message, provider, status_code)

    # Validation errors
    if (
        any(
            keyword in error_message.lower()
            for keyword in ["validation", "invalid request", "bad request"]
        )
        or status_code == 400
    ):
        return LLMValidationError(error_message, provider, status_code)

    # Default to generic provider error
    return LLMProviderError(error_message, provider, status_code)
