"""
GPT-4o provider implementation for the LLM abstraction layer.

This module provides a concrete implementation of the LLMProvider interface
for OpenAI's GPT-4o model, handling API integration, error mapping, and
cost estimation.
"""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from leadfactory.utils.logging import get_logger

from .provider import LLMError, LLMErrorType, LLMHealthStatus, LLMProvider, LLMResponse

logger = get_logger(__name__)


class GPT4oProvider(LLMProvider):
    """
    GPT-4o provider implementation using OpenAI API.
    """

    # Model pricing per 1K tokens (as of 2024)
    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize GPT-4o provider.

        Args:
            config: Configuration dictionary with optional keys:
                - api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
                - model: Model to use (defaults to gpt-4o)
                - base_url: API base URL (defaults to OpenAI API)
                - timeout: Request timeout in seconds (defaults to 30)
                - max_retries: Maximum number of retries (defaults to 3)
        """
        super().__init__("GPT-4o", config)

        self.api_key = self.config.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key found in config or environment")

        self.model = self.config.get("model", "gpt-4o")
        self.base_url = self.config.get("base_url", "https://api.openai.com/v1")
        self.timeout = self.config.get("timeout", 30)
        self.max_retries = self.config.get("max_retries", 3)

        # Initialize HTTP client
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_response(
        self, prompt: str, parameters: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """
        Generate a response using GPT-4o.

        Args:
            prompt: The input prompt
            parameters: Optional parameters:
                - temperature: Sampling temperature (0-2)
                - max_tokens: Maximum tokens to generate
                - top_p: Nucleus sampling parameter
                - frequency_penalty: Frequency penalty (-2 to 2)
                - presence_penalty: Presence penalty (-2 to 2)
                - stop: Stop sequences
                - model: Override default model

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            LLMError: If the request fails
        """
        start_time = time.time()

        try:
            # Normalize parameters
            normalized_params = self._normalize_parameters(parameters)

            # Prepare request payload
            payload = {
                "model": normalized_params.get("model", self.model),
                "messages": [{"role": "user", "content": prompt}],
                **{k: v for k, v in normalized_params.items() if k != "model"},
            }

            logger.debug(f"Making GPT-4o request with model: {payload['model']}")

            # Make API request
            response = await self._client.post(
                f"{self.base_url}/chat/completions", json=payload
            )

            # Handle response
            if response.status_code != 200:
                error = self._handle_http_error(response)
                logger.error(f"GPT-4o API error: {error}")
                raise error

            data = response.json()

            # Extract response data
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            # Calculate cost
            cost = self._calculate_cost(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=payload["model"],
            )

            latency = time.time() - start_time

            # Update health status on success
            self._update_health_status(
                LLMHealthStatus(
                    is_healthy=True,
                    provider=self.name,
                    last_check=time.time(),
                    response_time=latency,
                    consecutive_failures=0,
                )
            )

            return LLMResponse(
                content=content,
                model=payload["model"],
                provider=self.name,
                tokens_used=tokens_used,
                cost=cost,
                latency=latency,
                metadata={
                    "usage": usage,
                    "finish_reason": data["choices"][0].get("finish_reason"),
                    "response_id": data.get("id"),
                },
            )

        except LLMError:
            # Re-raise LLM errors as-is
            raise
        except Exception as e:
            # Convert other exceptions to LLM errors
            error = self._handle_api_error(e)
            logger.error(f"Unexpected error in GPT-4o provider: {error}")

            # Update health status on failure
            current_status = self.get_health_status()
            self._update_health_status(
                LLMHealthStatus(
                    is_healthy=False,
                    provider=self.name,
                    last_check=time.time(),
                    error_message=str(error),
                    consecutive_failures=current_status.consecutive_failures + 1,
                )
            )

            raise error

    async def check_health(self) -> LLMHealthStatus:
        """
        Check the health of the GPT-4o API.

        Returns:
            LLMHealthStatus indicating provider availability
        """
        start_time = time.time()

        try:
            # Make a minimal request to check API health
            response = await self._client.get(f"{self.base_url}/models")

            if response.status_code == 200:
                response_time = time.time() - start_time
                status = LLMHealthStatus(
                    is_healthy=True,
                    provider=self.name,
                    last_check=time.time(),
                    response_time=response_time,
                    consecutive_failures=0,
                )
            else:
                status = LLMHealthStatus(
                    is_healthy=False,
                    provider=self.name,
                    last_check=time.time(),
                    error_message=f"API returned status {response.status_code}",
                    consecutive_failures=self.get_health_status().consecutive_failures
                    + 1,
                )

            self._update_health_status(status)
            return status

        except Exception as e:
            logger.error(f"Health check failed for GPT-4o: {e}")
            status = LLMHealthStatus(
                is_healthy=False,
                provider=self.name,
                last_check=time.time(),
                error_message=str(e),
                consecutive_failures=self.get_health_status().consecutive_failures + 1,
            )
            self._update_health_status(status)
            return status

    def get_supported_models(self) -> List[str]:
        """
        Get list of supported GPT models.

        Returns:
            List of model identifiers
        """
        return ["gpt-4o", "gpt-4o-mini"]

    def estimate_cost(
        self, prompt: str, parameters: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Estimate the cost of a GPT-4o request.

        Args:
            prompt: Input prompt
            parameters: Request parameters

        Returns:
            Estimated cost in USD
        """
        # Simple token estimation (rough approximation)
        estimated_input_tokens = len(prompt.split()) * 1.3  # ~1.3 tokens per word

        # Estimate output tokens based on max_tokens parameter
        max_tokens = (parameters or {}).get("max_tokens", 150)
        estimated_output_tokens = min(max_tokens, estimated_input_tokens * 0.5)

        model = (parameters or {}).get("model", self.model)

        return self._calculate_cost(
            input_tokens=int(estimated_input_tokens),
            output_tokens=int(estimated_output_tokens),
            model=model,
        )

    def _normalize_parameters(
        self, parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Normalize parameters to OpenAI API format.

        Args:
            parameters: Common parameters

        Returns:
            OpenAI-specific parameters
        """
        if not parameters:
            return {}

        normalized = {}

        # Map common parameters to OpenAI format
        param_mapping = {
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "stop": "stop",
            "model": "model",
        }

        for common_name, openai_name in param_mapping.items():
            if common_name in parameters:
                normalized[openai_name] = parameters[common_name]

        # Set defaults
        if "temperature" not in normalized:
            normalized["temperature"] = 0.7
        if "max_tokens" not in normalized:
            normalized["max_tokens"] = 150

        return normalized

    def _handle_http_error(self, response: httpx.Response) -> LLMError:
        """
        Handle HTTP errors from OpenAI API.

        Args:
            response: HTTP response object

        Returns:
            Appropriate LLMError
        """
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            error_type_str = error_data.get("error", {}).get("type", "unknown")
        except:
            error_message = f"HTTP {response.status_code}: {response.text}"
            error_type_str = "unknown"

        # Map OpenAI error types to our error types
        if response.status_code == 429:
            error_type = LLMErrorType.RATE_LIMIT
            # Try to extract retry-after header
            retry_after = response.headers.get("retry-after")
            retry_after = int(retry_after) if retry_after else None
        elif response.status_code == 401:
            error_type = LLMErrorType.AUTHENTICATION
            retry_after = None
        elif response.status_code == 400:
            error_type = LLMErrorType.INVALID_REQUEST
            retry_after = None
        elif response.status_code >= 500:
            error_type = LLMErrorType.SERVER_ERROR
            retry_after = None
        else:
            error_type = LLMErrorType.UNKNOWN
            retry_after = None

        return LLMError(
            error_type=error_type,
            message=error_message,
            provider=self.name,
            retry_after=retry_after,
            details={
                "status_code": response.status_code,
                "error_type": error_type_str,
                "response_text": response.text[:500],  # Limit response text
            },
        )

    def _handle_api_error(self, error: Exception) -> LLMError:
        """
        Convert generic exceptions to LLMError.

        Args:
            error: Generic exception

        Returns:
            Appropriate LLMError
        """
        if isinstance(error, httpx.TimeoutException):
            return LLMError(
                error_type=LLMErrorType.TIMEOUT,
                message="Request timed out",
                provider=self.name,
                details={"timeout": self.timeout},
            )
        elif isinstance(error, httpx.NetworkError):
            return LLMError(
                error_type=LLMErrorType.NETWORK_ERROR,
                message="Network error occurred",
                provider=self.name,
                details={"original_error": str(error)},
            )
        else:
            return LLMError(
                error_type=LLMErrorType.UNKNOWN,
                message=str(error),
                provider=self.name,
                details={"original_error": str(error)},
            )

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """
        Calculate the cost of a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used

        Returns:
            Cost in USD
        """
        if model not in self.PRICING:
            logger.warning(f"Unknown model {model}, using gpt-4o pricing")
            model = "gpt-4o"

        pricing = self.PRICING[model]
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
