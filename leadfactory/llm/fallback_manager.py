"""
LLM Fallback Manager

This module provides a robust fallback mechanism for LLM providers,
implementing automatic failover between GPT-4o and Claude providers
with configurable retry logic and health monitoring.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from leadfactory.utils.logging import get_logger

from .claude_provider import ClaudeProvider
from .gpt4o_provider import GPT4oProvider
from .provider import LLMError, LLMErrorType, LLMHealthStatus, LLMProvider, LLMResponse

logger = get_logger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategy options."""

    FAIL_FAST = "fail_fast"  # Fail immediately on first error
    RETRY_PRIMARY = "retry_primary"  # Retry primary before fallback
    ROUND_ROBIN = "round_robin"  # Alternate between providers
    COST_OPTIMIZED = "cost_optimized"  # Choose cheapest available provider


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    strategy: FallbackStrategy = FallbackStrategy.RETRY_PRIMARY
    max_retries: int = 3
    retry_delay: float = 1.0  # Base delay between retries (exponential backoff)
    max_retry_delay: float = 60.0  # Maximum delay between retries
    health_check_interval: float = 300.0  # Health check interval in seconds
    circuit_breaker_threshold: int = 5  # Consecutive failures before circuit breaker
    circuit_breaker_timeout: float = (
        300.0  # Time to wait before retrying failed provider
    )
    cost_threshold: float = 100.0  # Daily cost threshold for cost-optimized strategy
    enable_pipeline_pause: bool = True  # Pause pipeline when all providers fail


class ProviderStatus(Enum):
    """Provider status for circuit breaker pattern."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class ProviderState:
    """Internal state tracking for each provider."""

    provider: LLMProvider
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: float = 0
    last_health_check: float = 0
    total_requests: int = 0
    total_cost: float = 0.0
    response_times: List[float] = None

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []


class FallbackManager:
    """
    Manages LLM provider fallback and retry logic.

    This class orchestrates multiple LLM providers, implementing intelligent
    fallback strategies, circuit breaker patterns, and cost monitoring.
    """

    def __init__(self, config: Optional[FallbackConfig] = None):
        """
        Initialize the fallback manager.

        Args:
            config: Fallback configuration (uses defaults if None)
        """
        self.config = config or FallbackConfig()
        self.providers: Dict[str, ProviderState] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._pipeline_paused = False

        logger.info(
            f"Fallback manager initialized with strategy: {self.config.strategy.value}"
        )

    async def initialize_providers(
        self,
        primary_config: Optional[Dict[str, Any]] = None,
        secondary_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize primary and secondary providers.

        Args:
            primary_config: Configuration for GPT-4o provider
            secondary_config: Configuration for Claude provider
        """
        try:
            # Initialize GPT-4o as primary provider
            gpt4o = GPT4oProvider(primary_config)
            self.providers["gpt4o"] = ProviderState(provider=gpt4o)

            # Initialize Claude as secondary provider
            claude = ClaudeProvider(secondary_config)
            self.providers["claude"] = ProviderState(provider=claude)

            logger.info("Initialized providers: GPT-4o (primary), Claude (secondary)")

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        except Exception as e:
            logger.error(f"Failed to initialize providers: {e}")
            raise

    async def generate_response(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
        preferred_provider: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response using the fallback strategy.

        Args:
            prompt: Input prompt
            parameters: Generation parameters
            preferred_provider: Preferred provider name (optional)

        Returns:
            LLMResponse from successful provider

        Raises:
            LLMError: If all providers fail
        """
        if self._pipeline_paused:
            raise LLMError(
                error_type=LLMErrorType.SERVICE_UNAVAILABLE,
                message="Pipeline is paused - all LLM providers are unavailable",
                provider="fallback_manager",
            )

        async with self._lock:
            providers_to_try = self._get_provider_order(preferred_provider)

            last_error = None
            for provider_name in providers_to_try:
                provider_state = self.providers[provider_name]

                # Skip providers with open circuit breakers
                if provider_state.status == ProviderStatus.CIRCUIT_OPEN:
                    if not self._should_retry_circuit_breaker(provider_state):
                        logger.debug(f"Skipping {provider_name} - circuit breaker open")
                        continue
                    else:
                        # Reset circuit breaker for retry
                        provider_state.status = ProviderStatus.DEGRADED
                        logger.info(
                            f"Retrying {provider_name} - circuit breaker timeout expired"
                        )

                # Attempt to generate response
                try:
                    response = await self._generate_with_retries(
                        provider_state, prompt, parameters
                    )

                    # Update success metrics
                    provider_state.consecutive_failures = 0
                    provider_state.status = ProviderStatus.HEALTHY
                    provider_state.total_requests += 1
                    provider_state.total_cost += response.cost
                    provider_state.response_times.append(response.latency)

                    # Keep only last 100 response times for moving average
                    if len(provider_state.response_times) > 100:
                        provider_state.response_times = provider_state.response_times[
                            -100:
                        ]

                    logger.info(
                        f"Successfully generated response using {provider_name}"
                    )
                    return response

                except LLMError as e:
                    last_error = e
                    await self._handle_provider_failure(provider_state, e)
                    logger.warning(f"Provider {provider_name} failed: {e.message}")
                    continue

            # All providers failed
            await self._handle_all_providers_failed()
            raise last_error or LLMError(
                error_type=LLMErrorType.SERVICE_UNAVAILABLE,
                message="All LLM providers are unavailable",
                provider="fallback_manager",
            )

    async def check_health(self) -> Dict[str, LLMHealthStatus]:
        """
        Check health of all providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        health_status = {}

        for name, state in self.providers.items():
            try:
                status = await state.provider.check_health()
                health_status[name] = status

                # Update internal state based on health check
                if status.is_healthy:
                    if state.status == ProviderStatus.FAILED:
                        state.status = ProviderStatus.HEALTHY
                        state.consecutive_failures = 0
                        logger.info(f"Provider {name} recovered")
                else:
                    if state.status == ProviderStatus.HEALTHY:
                        state.status = ProviderStatus.DEGRADED
                        logger.warning(f"Provider {name} is degraded")

            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                health_status[name] = LLMHealthStatus(
                    is_healthy=False,
                    provider=name,
                    last_check=time.time(),
                    error_message=str(e),
                )

        return health_status

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all providers.

        Returns:
            Dictionary with provider statistics
        """
        stats = {}

        for name, state in self.providers.items():
            avg_response_time = (
                sum(state.response_times) / len(state.response_times)
                if state.response_times
                else 0
            )

            stats[name] = {
                "status": state.status.value,
                "total_requests": state.total_requests,
                "total_cost": state.total_cost,
                "consecutive_failures": state.consecutive_failures,
                "average_response_time": avg_response_time,
                "last_failure_time": state.last_failure_time,
                "supported_models": state.provider.get_supported_models(),
            }

        return stats

    def is_pipeline_paused(self) -> bool:
        """Check if pipeline is paused due to provider failures."""
        return self._pipeline_paused

    async def resume_pipeline(self) -> bool:
        """
        Attempt to resume paused pipeline.

        Returns:
            True if pipeline was resumed, False otherwise
        """
        if not self._pipeline_paused:
            return True

        # Check if any provider is available
        health_status = await self.check_health()
        available_providers = [
            name for name, status in health_status.items() if status.is_healthy
        ]

        if available_providers:
            self._pipeline_paused = False
            logger.info(
                f"Pipeline resumed - available providers: {available_providers}"
            )
            return True

        return False

    async def _generate_with_retries(
        self,
        provider_state: ProviderState,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate response with retry logic."""
        retries = 0
        delay = self.config.retry_delay

        while retries <= self.config.max_retries:
            try:
                return await provider_state.provider.generate_response(
                    prompt, parameters
                )
            except LLMError as e:
                retries += 1

                # Don't retry certain error types
                if e.error_type in [
                    LLMErrorType.AUTHENTICATION,
                    LLMErrorType.INVALID_REQUEST,
                    LLMErrorType.QUOTA_EXCEEDED,
                ]:
                    raise

                if retries > self.config.max_retries:
                    raise

                # Wait before retry with exponential backoff
                await asyncio.sleep(min(delay, self.config.max_retry_delay))
                delay *= 2

                logger.debug(
                    f"Retrying {provider_state.provider.name} (attempt {retries})"
                )

    async def _handle_provider_failure(
        self, provider_state: ProviderState, error: LLMError
    ):
        """Handle provider failure and update state."""
        provider_state.consecutive_failures += 1
        provider_state.last_failure_time = time.time()

        # Update provider status based on failure count
        if provider_state.consecutive_failures >= self.config.circuit_breaker_threshold:
            provider_state.status = ProviderStatus.CIRCUIT_OPEN
            logger.warning(
                f"Circuit breaker opened for {provider_state.provider.name} "
                f"after {provider_state.consecutive_failures} consecutive failures"
            )
        else:
            provider_state.status = ProviderStatus.DEGRADED

    async def _handle_all_providers_failed(self):
        """Handle the case when all providers have failed."""
        if self.config.enable_pipeline_pause:
            self._pipeline_paused = True
            logger.error("All LLM providers failed - pipeline paused")
        else:
            logger.error("All LLM providers failed - continuing without pause")

    def _get_provider_order(
        self, preferred_provider: Optional[str] = None
    ) -> List[str]:
        """Get the order of providers to try based on strategy."""
        if preferred_provider and preferred_provider in self.providers:
            # Try preferred provider first, then others
            others = [
                name for name in self.providers.keys() if name != preferred_provider
            ]
            return [preferred_provider] + others

        if self.config.strategy == FallbackStrategy.FAIL_FAST:
            return ["gpt4o"]  # Only try primary
        elif self.config.strategy == FallbackStrategy.RETRY_PRIMARY:
            return ["gpt4o", "claude"]  # Primary first, then secondary
        elif self.config.strategy == FallbackStrategy.ROUND_ROBIN:
            # Simple round-robin based on total requests
            total_requests = sum(
                state.total_requests for state in self.providers.values()
            )
            if total_requests % 2 == 0:
                return ["gpt4o", "claude"]
            else:
                return ["claude", "gpt4o"]
        elif self.config.strategy == FallbackStrategy.COST_OPTIMIZED:
            # Choose provider with lower cost per request
            return self._get_cost_optimized_order()
        else:
            return ["gpt4o", "claude"]  # Default order

    def _get_cost_optimized_order(self) -> List[str]:
        """Get provider order optimized for cost."""
        provider_costs = []

        for name, state in self.providers.items():
            if state.total_requests > 0:
                avg_cost = state.total_cost / state.total_requests
            else:
                # Use estimated cost for new providers
                avg_cost = state.provider.estimate_cost(
                    "Sample prompt", {"max_tokens": 100}
                )

            provider_costs.append((name, avg_cost))

        # Sort by average cost (ascending)
        provider_costs.sort(key=lambda x: x[1])
        return [name for name, _ in provider_costs]

    def _should_retry_circuit_breaker(self, provider_state: ProviderState) -> bool:
        """Check if circuit breaker timeout has expired."""
        if provider_state.status != ProviderStatus.CIRCUIT_OPEN:
            return True

        time_since_failure = time.time() - provider_state.last_failure_time
        return time_since_failure >= self.config.circuit_breaker_timeout

    async def _health_check_loop(self):
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self.check_health()

                # Try to resume pipeline if paused
                if self._pipeline_paused:
                    await self.resume_pipeline()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all providers
        for state in self.providers.values():
            if hasattr(state.provider, "__aexit__"):
                await state.provider.__aexit__(exc_type, exc_val, exc_tb)
