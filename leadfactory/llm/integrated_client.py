"""
Integrated LLM client with fallback system.

This module provides a high-level client that integrates the fallback manager,
cost monitoring, and health monitoring systems for seamless LLM operations
in the pipeline.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union

from leadfactory.config.fallback_config_loader import (
    LLMFallbackConfig,
    get_fallback_config,
)
from leadfactory.llm.claude_provider import ClaudeProvider
from leadfactory.llm.cost_monitor import CostMonitor
from leadfactory.llm.fallback_manager import FallbackManager
from leadfactory.llm.gpt4o_provider import GPT4oProvider
from leadfactory.llm.health_monitor import HealthMonitor
from leadfactory.llm.provider import LLMError, LLMResponse
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class IntegratedLLMClient:
    """
    High-level LLM client with integrated fallback, cost monitoring, and health checks.

    This client provides a simple interface for making LLM requests while automatically
    handling fallbacks, monitoring costs, and tracking provider health.
    """

    def __init__(self, config: Optional[LLMFallbackConfig] = None):
        """
        Initialize the integrated LLM client.

        Args:
            config: Optional fallback configuration. If None, loads from default config.
        """
        self.config = config or get_fallback_config()
        self.fallback_manager: Optional[FallbackManager] = None
        self.cost_monitor: Optional[CostMonitor] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self._initialized = False

    async def initialize(self):
        """Initialize all components of the LLM client."""
        if self._initialized:
            return

        try:
            # Initialize providers
            primary_provider = self._create_provider(self.config.primary_provider)
            secondary_provider = self._create_provider(self.config.secondary_provider)

            # Initialize fallback manager
            self.fallback_manager = FallbackManager(self.config.fallback)
            await self.fallback_manager.add_provider("primary", primary_provider)
            await self.fallback_manager.add_provider("secondary", secondary_provider)

            # Initialize cost monitor if enabled
            if self.config.cost_monitoring.enabled:
                self.cost_monitor = CostMonitor(self.config.cost_monitoring)
                await self.cost_monitor.__aenter__()

            # Initialize health monitor if enabled
            if self.config.health_monitoring.enabled:
                self.health_monitor = HealthMonitor(self.config.health_monitoring)
                self.health_monitor.register_provider("primary", primary_provider)
                self.health_monitor.register_provider("secondary", secondary_provider)
                await self.health_monitor.__aenter__()

            self._initialized = True
            logger.info("Integrated LLM client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize integrated LLM client: {e}")
            raise

    async def cleanup(self):
        """Cleanup all components."""
        if not self._initialized:
            return

        try:
            if self.health_monitor:
                await self.health_monitor.__aexit__(None, None, None)

            if self.cost_monitor:
                await self.cost_monitor.__aexit__(None, None, None)

            if self.fallback_manager:
                await self.fallback_manager.__aexit__(None, None, None)

            self._initialized = False
            logger.info("Integrated LLM client cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    @asynccontextmanager
    async def managed_client(self):
        """Context manager for the integrated LLM client."""
        await self.initialize()
        try:
            yield self
        finally:
            await self.cleanup()

    async def generate_response(
        self,
        prompt: str,
        parameters: Optional[Dict[str, Any]] = None,
        preferred_provider: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response using the fallback system.

        Args:
            prompt: The input prompt
            parameters: Optional parameters for the LLM request
            preferred_provider: Optional preferred provider name
            request_id: Optional request ID for tracking

        Returns:
            LLMResponse: The generated response

        Raises:
            LLMError: If all providers fail
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Check cost constraints before making request
            if self.cost_monitor:
                estimated_cost = self._estimate_request_cost(prompt, parameters)
                if not await self.cost_monitor.check_budget_constraint(estimated_cost):
                    raise LLMError(
                        error_type="quota_exceeded",
                        message="Request would exceed budget constraints",
                        provider="cost_monitor",
                    )

            # Generate response using fallback manager
            response = await self.fallback_manager.generate_response(
                prompt=prompt,
                parameters=parameters,
                preferred_provider=preferred_provider,
            )

            # Record cost if monitoring is enabled
            if self.cost_monitor:
                await self.cost_monitor.record_cost(
                    provider=response.provider,
                    operation="text_generation",
                    cost=response.cost,
                    tokens_used=response.tokens_used,
                    metadata={
                        "model": response.model,
                        "request_id": request_id,
                        "latency": response.latency,
                    },
                )

            # Log successful request
            logger.info(
                f"LLM request completed successfully - "
                f"Provider: {response.provider}, "
                f"Model: {response.model}, "
                f"Tokens: {response.tokens_used}, "
                f"Cost: ${response.cost:.4f}, "
                f"Latency: {response.latency:.2f}s"
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"LLM request failed after {duration:.2f}s: {e}")

            # Record failed request cost if applicable
            if self.cost_monitor and isinstance(e, LLMError):
                # Estimate minimal cost for failed request
                estimated_cost = self._estimate_request_cost(prompt, parameters) * 0.1
                await self.cost_monitor.record_cost(
                    provider=e.provider,
                    operation="text_generation",
                    cost=estimated_cost,
                    tokens_used=0,
                    metadata={
                        "request_id": request_id,
                        "error": str(e),
                        "failed": True,
                    },
                )

            raise

    async def batch_generate_responses(
        self, requests: List[Dict[str, Any]], max_concurrent: Optional[int] = None
    ) -> List[Union[LLMResponse, LLMError]]:
        """
        Generate multiple responses concurrently.

        Args:
            requests: List of request dictionaries with 'prompt' and optional 'parameters'
            max_concurrent: Maximum number of concurrent requests

        Returns:
            List of responses or errors
        """
        if not self._initialized:
            await self.initialize()

        max_concurrent = max_concurrent or self.config.pipeline.max_concurrent_requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_request(
            request: Dict[str, Any]
        ) -> Union[LLMResponse, LLMError]:
            async with semaphore:
                try:
                    return await self.generate_response(
                        prompt=request["prompt"],
                        parameters=request.get("parameters"),
                        preferred_provider=request.get("preferred_provider"),
                        request_id=request.get("request_id"),
                    )
                except Exception as e:
                    return e

        tasks = [process_request(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to LLMError objects
        processed_results = []
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, LLMError):
                processed_results.append(
                    LLMError(
                        error_type="unknown",
                        message=str(result),
                        provider="batch_processor",
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def get_provider_status(self) -> Dict[str, Any]:
        """
        Get the status of all providers.

        Returns:
            Dictionary with provider status information
        """
        if not self._initialized:
            await self.initialize()

        status = {
            "fallback_manager": {
                "pipeline_paused": (
                    self.fallback_manager._pipeline_paused
                    if self.fallback_manager
                    else False
                ),
                "providers": {},
            }
        }

        if self.fallback_manager:
            for name, state in self.fallback_manager.providers.items():
                status["fallback_manager"]["providers"][name] = {
                    "available": state.available,
                    "failure_count": state.failure_count,
                    "last_failure": state.last_failure,
                    "circuit_breaker_state": state.circuit_breaker.state.name,
                }

        if self.health_monitor:
            status["health_monitor"] = await self.health_monitor.get_dashboard_data()

        if self.cost_monitor:
            status["cost_monitor"] = await self.cost_monitor.get_cost_summary()

        return status

    async def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get cost summary from the cost monitor.

        Returns:
            Cost summary dictionary
        """
        if not self.cost_monitor:
            return {"error": "Cost monitoring not enabled"}

        return await self.cost_monitor.get_cost_summary()

    async def pause_pipeline(self, duration: Optional[int] = None):
        """
        Manually pause the pipeline.

        Args:
            duration: Pause duration in seconds. If None, uses config default.
        """
        if self.fallback_manager:
            await self.fallback_manager.pause_pipeline(duration)

    async def resume_pipeline(self):
        """Resume the pipeline if paused."""
        if self.fallback_manager:
            await self.fallback_manager.resume_pipeline()

    def _create_provider(self, provider_config):
        """Create a provider instance from configuration."""
        if provider_config.type == "openai":
            return GPT4oProvider(
                {
                    "model": provider_config.model,
                    "api_key": provider_config.api_key_env,
                    "base_url": provider_config.base_url,
                    "timeout": provider_config.timeout,
                    "max_retries": provider_config.max_retries,
                    "retry_delay": provider_config.retry_delay,
                }
            )
        elif provider_config.type == "anthropic":
            return ClaudeProvider(
                {
                    "model": provider_config.model,
                    "api_key": provider_config.api_key_env,
                    "base_url": provider_config.base_url,
                    "timeout": provider_config.timeout,
                    "max_retries": provider_config.max_retries,
                    "retry_delay": provider_config.retry_delay,
                }
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_config.type}")

    def _estimate_request_cost(
        self, prompt: str, parameters: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Estimate the cost of a request.

        Args:
            prompt: The input prompt
            parameters: Optional parameters

        Returns:
            Estimated cost in dollars
        """
        # Simple estimation based on prompt length
        # In a real implementation, this would use tokenization
        estimated_input_tokens = len(prompt.split()) * 1.3  # Rough approximation
        estimated_output_tokens = (
            parameters.get("max_tokens", 150) if parameters else 150
        )

        # Use primary provider cost for estimation
        cost_per_token = self.config.cost_monitoring.cost_per_token
        primary_model = self.config.primary_provider.model

        if primary_model in cost_per_token:
            input_cost = (estimated_input_tokens / 1000) * cost_per_token[
                primary_model
            ].get("input", 0.005)
            output_cost = (estimated_output_tokens / 1000) * cost_per_token[
                primary_model
            ].get("output", 0.015)
            return input_cost + output_cost

        # Default fallback cost estimation
        return (estimated_input_tokens + estimated_output_tokens) / 1000 * 0.01


# Global client instance
_global_client: Optional[IntegratedLLMClient] = None


async def get_global_llm_client() -> IntegratedLLMClient:
    """
    Get the global LLM client instance.

    Returns:
        IntegratedLLMClient: The global client instance
    """
    global _global_client

    if _global_client is None:
        _global_client = IntegratedLLMClient()
        await _global_client.initialize()

    return _global_client


async def cleanup_global_llm_client():
    """Cleanup the global LLM client."""
    global _global_client

    if _global_client is not None:
        await _global_client.cleanup()
        _global_client = None
