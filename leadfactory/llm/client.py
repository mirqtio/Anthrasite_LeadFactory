"""
Unified LLM client with automatic fallback and intelligent error handling.

This module provides a single interface for multiple LLM providers with
automatic provider fallback, cost tracking, and rate limiting.
"""

import hashlib
import json
import logging
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

from .config import FallbackStrategy, LLMConfig
from .exceptions import (
    AllProvidersFailedError,
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    classify_error,
)

# Try to import provider clients
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client with automatic fallback support.

    This client provides a single interface to multiple LLM providers
    with intelligent fallback, cost tracking, and error handling.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM client.

        Args:
            config: LLM configuration. If None, loads from environment.
        """
        self.config = config or LLMConfig.from_environment()
        self._provider_clients = {}
        self._rate_limiters = {}
        self._cost_tracker = {}
        self._request_cache = {}

        # Validate configuration
        issues = self.config.validate()
        if issues:
            logger.warning(f"LLM configuration issues: {', '.join(issues)}")

        # Initialize provider clients
        self._initialize_providers()

        logger.info(
            f"LLM client initialized with strategy: {self.config.fallback_strategy.value}"
        )
        logger.info(f"Available providers: {list(self._provider_clients.keys())}")

    def _initialize_providers(self):
        """Initialize provider-specific clients."""
        for name, provider_config in self.config.providers.items():
            if not provider_config.enabled:
                continue

            try:
                if name == "openai" and OPENAI_AVAILABLE and provider_config.api_key:
                    self._provider_clients[name] = openai.OpenAI(
                        api_key=provider_config.api_key, timeout=provider_config.timeout
                    )
                    logger.info(
                        f"OpenAI client initialized with model: {provider_config.default_model}"
                    )

                elif (
                    name == "anthropic"
                    and ANTHROPIC_AVAILABLE
                    and provider_config.api_key
                ):
                    self._provider_clients[name] = anthropic.Anthropic(
                        api_key=provider_config.api_key, timeout=provider_config.timeout
                    )
                    logger.info(
                        f"Anthropic client initialized with model: {provider_config.default_model}"
                    )

                elif (
                    name == "ollama" and REQUESTS_AVAILABLE and provider_config.base_url
                ):
                    # Ollama uses simple HTTP requests
                    self._provider_clients[name] = {
                        "base_url": provider_config.base_url,
                        "timeout": provider_config.timeout,
                    }
                    logger.info(
                        f"Ollama client initialized at: {provider_config.base_url}"
                    )

                # Initialize rate limiter for this provider
                self._rate_limiters[name] = RateLimiter(
                    rpm=provider_config.rate_limit_rpm,
                    tpm=provider_config.rate_limit_tpm,
                )

                # Initialize cost tracker
                self._cost_tracker[name] = {
                    "daily_cost": 0.0,
                    "monthly_cost": 0.0,
                    "last_reset": time.time(),
                }

            except Exception as e:
                logger.error(f"Failed to initialize {name} provider: {e}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a chat completion using the best available provider.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (optional, uses provider default)
            temperature: Sampling temperature (optional, uses config default)
            max_tokens: Maximum tokens to generate (optional, uses config default)
            **kwargs: Additional provider-specific parameters

        Returns:
            Standardized response dictionary with content, usage, and metadata

        Raises:
            AllProvidersFailedError: If all providers fail
            LLMQuotaExceededError: If cost limits are exceeded
        """
        # Set defaults
        temperature = temperature or self.config.default_temperature
        max_tokens = max_tokens or self.config.default_max_tokens

        # Check cache if enabled
        cache_key = None
        if self.config.enable_caching:
            cache_key = self._generate_cache_key(
                messages, model, temperature, max_tokens, kwargs
            )
            if cache_key in self._request_cache:
                logger.debug("Returning cached response")
                return self._request_cache[cache_key]

        # Estimate tokens for cost calculation
        estimated_tokens = self._estimate_tokens(messages, max_tokens)

        # Get provider order based on strategy
        provider_order = self.config.get_provider_order()

        if not provider_order:
            raise AllProvidersFailedError({"all": Exception("No providers available")})

        # Try each provider in order
        provider_errors = {}

        for attempt, provider_name in enumerate(provider_order):
            if attempt >= self.config.max_fallback_attempts:
                break

            if provider_name not in self._provider_clients:
                continue

            try:
                # Check cost limits
                self._check_cost_limits(provider_name, estimated_tokens)

                # Check rate limits
                self._rate_limiters[provider_name].wait_if_needed()

                # Make the request
                logger.debug(f"Attempting request with provider: {provider_name}")
                response = self._make_request(
                    provider_name, messages, model, temperature, max_tokens, **kwargs
                )

                # Track usage and cost
                self._track_usage(provider_name, response.get("usage", {}))

                # Cache response if enabled
                if cache_key and self.config.enable_caching:
                    self._request_cache[cache_key] = response

                logger.info(f"Request successful with provider: {provider_name}")
                return response

            except LLMRateLimitError as e:
                logger.warning(f"Rate limit hit for {provider_name}: {e}")
                provider_errors[provider_name] = e

                # For rate limits, we might want to try next provider immediately
                continue

            except (LLMQuotaExceededError, Exception) as e:
                classified_error = classify_error(e, provider_name)
                logger.error(f"Provider {provider_name} failed: {classified_error}")
                provider_errors[provider_name] = classified_error

                # For some errors, don't try more providers
                if isinstance(classified_error, LLMQuotaExceededError):
                    break

                continue

        # All providers failed
        raise AllProvidersFailedError(provider_errors)

    def _make_request(
        self,
        provider_name: str,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a request to a specific provider."""
        provider_config = self.config.providers[provider_name]
        actual_model = model or provider_config.default_model

        try:
            if provider_name == "openai":
                return self._openai_request(
                    messages, actual_model, temperature, max_tokens, **kwargs
                )
            elif provider_name == "anthropic":
                return self._anthropic_request(
                    messages, actual_model, temperature, max_tokens, **kwargs
                )
            elif provider_name == "ollama":
                return self._ollama_request(
                    messages, actual_model, temperature, max_tokens, **kwargs
                )
            else:
                raise ValueError(f"Unknown provider: {provider_name}")

        except Exception as e:
            raise classify_error(e, provider_name)

    def _openai_request(self, messages, model, temperature, max_tokens, **kwargs):
        """Make OpenAI API request."""
        client = self._provider_clients["openai"]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return {
            "provider": "openai",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": response.choices[0].message.role,
                        "content": response.choices[0].message.content,
                    },
                    "finish_reason": response.choices[0].finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    def _anthropic_request(self, messages, model, temperature, max_tokens, **kwargs):
        """Make Anthropic API request."""
        client = self._provider_clients["anthropic"]

        # Convert messages format for Anthropic
        system_message = None
        formatted_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

        request_params = {
            "model": model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        if system_message:
            request_params["system"] = system_message

        response = client.messages.create(**request_params)

        return {
            "provider": "anthropic",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": response.content[0].text,
                    },
                    "finish_reason": response.stop_reason,
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
        }

    def _ollama_request(self, messages, model, temperature, max_tokens, **kwargs):
        """Make Ollama API request."""
        ollama_config = self._provider_clients["ollama"]

        # Format request for Ollama
        request_data = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs,
            },
            "stream": False,
        }

        response = requests.post(
            f"{ollama_config['base_url']}/api/chat",
            json=request_data,
            timeout=ollama_config["timeout"],
        )

        response.raise_for_status()
        data = response.json()

        return {
            "provider": "ollama",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": data["message"]["role"],
                        "content": data["message"]["content"],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0)
                + data.get("eval_count", 0),
            },
        }

    def _estimate_tokens(self, messages: List[Dict[str, str]], max_tokens: int) -> int:
        """Estimate token count for messages."""
        # Simple estimation: ~4 characters per token
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        estimated_input_tokens = total_chars // 4
        return estimated_input_tokens + max_tokens

    def _check_cost_limits(self, provider_name: str, estimated_tokens: int):
        """Check if request would exceed cost limits."""
        if not self.config.cost_config.cost_tracking_enabled:
            return

        estimated_cost = self.config.estimate_request_cost(
            estimated_tokens, provider_name
        )

        if estimated_cost > self.config.cost_config.max_cost_per_request:
            raise LLMQuotaExceededError(
                f"Request cost ${estimated_cost:.4f} exceeds limit ${self.config.cost_config.max_cost_per_request}",
                provider_name,
            )

        # Check daily/monthly limits
        tracker = self._cost_tracker[provider_name]
        if (
            tracker["daily_cost"] + estimated_cost
            > self.config.cost_config.daily_cost_limit
        ):
            raise LLMQuotaExceededError(
                f"Daily cost limit ${self.config.cost_config.daily_cost_limit} would be exceeded",
                provider_name,
            )

    def _track_usage(self, provider_name: str, usage: Dict[str, int]):
        """Track usage and costs."""
        if not self.config.cost_config.cost_tracking_enabled:
            return

        total_tokens = usage.get("total_tokens", 0)
        cost = self.config.estimate_request_cost(total_tokens, provider_name)

        tracker = self._cost_tracker[provider_name]
        tracker["daily_cost"] += cost
        tracker["monthly_cost"] += cost

        if self.config.log_requests:
            logger.info(f"Provider {provider_name}: {total_tokens} tokens, ${cost:.4f}")

    def _generate_cache_key(
        self, messages, model, temperature, max_tokens, kwargs
    ) -> str:
        """Generate cache key for request."""
        cache_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs,
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()

    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self._provider_clients.keys())

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all providers."""
        status = {}

        for name, config in self.config.providers.items():
            status[name] = {
                "enabled": config.enabled,
                "available": name in self._provider_clients,
                "model": config.default_model,
                "cost_per_1k_tokens": config.cost_per_1k_tokens,
                "priority": config.priority,
            }

            if name in self._cost_tracker:
                status[name].update(
                    {
                        "daily_cost": self._cost_tracker[name]["daily_cost"],
                        "monthly_cost": self._cost_tracker[name]["monthly_cost"],
                    }
                )

        return status

    def clear_cache(self):
        """Clear the request cache."""
        self._request_cache.clear()
        logger.info("Request cache cleared")

    def reset_cost_tracking(self, provider_name: Optional[str] = None):
        """Reset cost tracking for one or all providers."""
        if provider_name:
            if provider_name in self._cost_tracker:
                self._cost_tracker[provider_name]["daily_cost"] = 0.0
                self._cost_tracker[provider_name]["monthly_cost"] = 0.0
                logger.info(f"Cost tracking reset for {provider_name}")
        else:
            for tracker in self._cost_tracker.values():
                tracker["daily_cost"] = 0.0
                tracker["monthly_cost"] = 0.0
            logger.info("Cost tracking reset for all providers")


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, rpm: Optional[int] = None, tpm: Optional[int] = None):
        self.rpm = rpm
        self.tpm = tpm
        self.request_times = []
        self.token_usage = []

    def wait_if_needed(self, tokens: int = 1):
        """Wait if rate limits would be exceeded."""
        current_time = time.time()

        # Clean old entries (older than 1 minute)
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        self.token_usage = [
            (t, tokens) for t, tokens in self.token_usage if current_time - t < 60
        ]

        # Check RPM limit
        if self.rpm and len(self.request_times) >= self.rpm:
            sleep_time = 60 - (current_time - self.request_times[0])
            if sleep_time > 0:
                logger.info(f"Rate limit: sleeping {sleep_time:.2f}s for RPM")
                time.sleep(sleep_time)

        # Check TPM limit
        if self.tpm:
            total_tokens = sum(tokens for _, tokens in self.token_usage) + tokens
            if total_tokens > self.tpm:
                sleep_time = 60 - (current_time - self.token_usage[0][0])
                if sleep_time > 0:
                    logger.info(f"Rate limit: sleeping {sleep_time:.2f}s for TPM")
                    time.sleep(sleep_time)

        # Record this request
        self.request_times.append(current_time)
        self.token_usage.append((current_time, tokens))
