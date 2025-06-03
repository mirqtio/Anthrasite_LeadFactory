"""
Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement
to ensure consistent behavior across different providers in the fallback system.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class LLMErrorType(Enum):
    """Types of errors that can occur with LLM providers."""

    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    MODEL_UNAVAILABLE = "model_unavailable"
    UNKNOWN = "unknown"


@dataclass
class LLMResponse:
    """Standardized response from LLM providers."""

    content: str
    model: str
    provider: str
    tokens_used: int
    cost: float
    latency: float
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate response data."""
        if not isinstance(self.content, str):
            raise ValueError("Response content must be a string")
        if self.tokens_used < 0:
            raise ValueError("Tokens used cannot be negative")
        if self.cost < 0:
            raise ValueError("Cost cannot be negative")
        if self.latency < 0:
            raise ValueError("Latency cannot be negative")


@dataclass
class LLMError(Exception):
    """Standardized error from LLM providers."""

    error_type: Union[LLMErrorType, str]
    message: str
    provider: str
    retry_after: Optional[int] = None
    details: Optional[Dict[str, Any]] = None

    def __str__(self):
        error_type_str = (
            self.error_type.value
            if hasattr(self.error_type, "value")
            else str(self.error_type)
        )
        return f"{self.provider} {error_type_str}: {self.message}"

    def is_retryable(self) -> bool:
        """Check if this error type is retryable."""
        retryable_types = {
            LLMErrorType.RATE_LIMIT,
            LLMErrorType.TIMEOUT,
            LLMErrorType.SERVER_ERROR,
            LLMErrorType.NETWORK_ERROR,
        }
        return self.error_type in retryable_types


@dataclass
class LLMHealthStatus:
    """Health status of an LLM provider."""

    is_healthy: bool
    provider: str
    last_check: float
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0

    def __post_init__(self):
        """Set last_check to current time if not provided."""
        if self.last_check == 0:
            self.last_check = time.time()


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface to be compatible
    with the fallback system.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LLM provider.

        Args:
            name: Human-readable name for this provider
            config: Provider-specific configuration
        """
        self.name = name
        self.config = config or {}
        self._health_status = LLMHealthStatus(
            is_healthy=True, provider=name, last_check=0
        )

    @abstractmethod
    async def generate_response(
        self, prompt: str, parameters: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """
        Generate a response from the LLM provider.

        Args:
            prompt: The input prompt for the LLM
            parameters: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse object with the generated content and metadata

        Raises:
            LLMError: If the request fails
        """
        pass

    @abstractmethod
    async def check_health(self) -> LLMHealthStatus:
        """
        Check the health status of the LLM provider.

        Returns:
            LLMHealthStatus object indicating provider availability
        """
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of models supported by this provider.

        Returns:
            List of model names/identifiers
        """
        pass

    @abstractmethod
    def estimate_cost(
        self, prompt: str, parameters: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Estimate the cost of a request before making it.

        Args:
            prompt: The input prompt
            parameters: Request parameters

        Returns:
            Estimated cost in USD
        """
        pass

    def get_health_status(self) -> LLMHealthStatus:
        """Get the current health status without performing a check."""
        return self._health_status

    def _update_health_status(self, status: LLMHealthStatus) -> None:
        """Update the internal health status."""
        self._health_status = status

    def _normalize_parameters(
        self, parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Normalize parameters to provider-specific format.

        This method should be overridden by providers to map
        common parameters to their specific API format.

        Args:
            parameters: Common parameters

        Returns:
            Provider-specific parameters
        """
        if parameters is None:
            return {}

        # Default implementation returns parameters as-is
        return parameters.copy()

    def _handle_api_error(self, error: Exception) -> LLMError:
        """
        Convert provider-specific errors to standardized LLMError.

        This method should be overridden by providers to map
        their specific error types to LLMErrorType enum values.

        Args:
            error: Provider-specific error

        Returns:
            Standardized LLMError
        """
        return LLMError(
            error_type=LLMErrorType.UNKNOWN,
            message=str(error),
            provider=self.name,
            details={"original_error": str(error)},
        )
