"""
LLM Fallback System for LeadFactory Pipeline

This module provides a unified interface for multiple LLM providers with
automatic fallback, cost tracking, and intelligent error handling.
"""

from .client import LLMClient
from .config import FallbackStrategy, LLMConfig
from .exceptions import (
    AllProvidersFailedError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)

__all__ = [
    "LLMClient",
    "LLMConfig",
    "FallbackStrategy",
    "LLMError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMQuotaExceededError",
    "LLMModelNotFoundError",
    "LLMTimeoutError",
    "LLMValidationError",
    "LLMProviderError",
    "AllProvidersFailedError",
]
