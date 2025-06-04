"""
Configuration management for LLM fallback system.

This module handles loading and managing configuration for multiple LLM providers,
fallback strategies, and cost controls.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class FallbackStrategy(Enum):
    """Available fallback strategies."""

    SMART_FALLBACK = "smart_fallback"
    COST_OPTIMIZED = "cost_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"
    ROUND_ROBIN = "round_robin"
    FAIL_FAST = "fail_fast"


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str
    enabled: bool = True
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    timeout: int = 30
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    cost_per_1k_tokens: float = 0.0
    priority: int = 1
    max_retries: int = 3
    retry_delay: float = 1.0
    additional_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostConfig:
    """Cost control configuration."""

    max_cost_per_request: float = 1.0
    daily_cost_limit: float = 50.0
    monthly_cost_limit: float = 1000.0
    cost_tracking_enabled: bool = True
    budget_alert_threshold: float = 0.8


@dataclass
class LLMConfig:
    """Complete LLM configuration."""

    fallback_strategy: FallbackStrategy = FallbackStrategy.SMART_FALLBACK
    max_fallback_attempts: int = 3
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    cost_config: CostConfig = field(default_factory=CostConfig)
    default_temperature: float = 0.7
    default_max_tokens: int = 1000
    enable_caching: bool = True
    log_requests: bool = True

    @classmethod
    def from_environment(cls) -> "LLMConfig":
        """Create configuration from environment variables."""
        config = cls()

        # Load fallback strategy
        strategy = os.getenv("LLM_FALLBACK_STRATEGY", "smart_fallback")
        try:
            config.fallback_strategy = FallbackStrategy(strategy)
        except ValueError:
            config.fallback_strategy = FallbackStrategy.SMART_FALLBACK

        # Load general settings
        config.max_fallback_attempts = int(os.getenv("LLM_MAX_FALLBACK_ATTEMPTS", "3"))
        config.default_temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0.7"))
        config.default_max_tokens = int(os.getenv("LLM_DEFAULT_MAX_TOKENS", "1000"))
        config.enable_caching = (
            os.getenv("LLM_ENABLE_CACHING", "true").lower() == "true"
        )
        config.log_requests = os.getenv("LLM_LOG_REQUESTS", "true").lower() == "true"

        # Load cost configuration
        config.cost_config = CostConfig(
            max_cost_per_request=float(os.getenv("LLM_MAX_COST_PER_REQUEST", "1.0")),
            daily_cost_limit=float(os.getenv("LLM_DAILY_COST_LIMIT", "50.0")),
            monthly_cost_limit=float(os.getenv("LLM_MONTHLY_COST_LIMIT", "1000.0")),
            cost_tracking_enabled=os.getenv("LLM_COST_TRACKING", "true").lower()
            == "true",
            budget_alert_threshold=float(
                os.getenv("LLM_BUDGET_ALERT_THRESHOLD", "0.8")
            ),
        )

        # Load provider configurations
        config.providers = {}

        # OpenAI configuration
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            config.providers["openai"] = ProviderConfig(
                name="openai",
                enabled=os.getenv("OPENAI_ENABLED", "true").lower() == "true",
                api_key=openai_key,
                default_model=os.getenv("OPENAI_MODEL", "gpt-4"),
                timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
                rate_limit_rpm=(
                    int(os.getenv("OPENAI_RATE_LIMIT_RPM", "60"))
                    if os.getenv("OPENAI_RATE_LIMIT_RPM")
                    else None
                ),
                rate_limit_tpm=(
                    int(os.getenv("OPENAI_RATE_LIMIT_TPM", "60000"))
                    if os.getenv("OPENAI_RATE_LIMIT_TPM")
                    else None
                ),
                cost_per_1k_tokens=float(
                    os.getenv("OPENAI_COST_PER_1K_TOKENS", "0.03")
                ),
                priority=int(os.getenv("OPENAI_PRIORITY", "2")),
                max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
                retry_delay=float(os.getenv("OPENAI_RETRY_DELAY", "1.0")),
            )

        # Anthropic configuration
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            config.providers["anthropic"] = ProviderConfig(
                name="anthropic",
                enabled=os.getenv("ANTHROPIC_ENABLED", "true").lower() == "true",
                api_key=anthropic_key,
                default_model=os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
                timeout=int(os.getenv("ANTHROPIC_TIMEOUT", "30")),
                rate_limit_rpm=(
                    int(os.getenv("ANTHROPIC_RATE_LIMIT_RPM", "50"))
                    if os.getenv("ANTHROPIC_RATE_LIMIT_RPM")
                    else None
                ),
                rate_limit_tpm=(
                    int(os.getenv("ANTHROPIC_RATE_LIMIT_TPM", "100000"))
                    if os.getenv("ANTHROPIC_RATE_LIMIT_TPM")
                    else None
                ),
                cost_per_1k_tokens=float(
                    os.getenv("ANTHROPIC_COST_PER_1K_TOKENS", "0.015")
                ),
                priority=int(os.getenv("ANTHROPIC_PRIORITY", "3")),
                max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "3")),
                retry_delay=float(os.getenv("ANTHROPIC_RETRY_DELAY", "1.0")),
            )

        # Ollama configuration
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        config.providers["ollama"] = ProviderConfig(
            name="ollama",
            enabled=os.getenv("OLLAMA_ENABLED", "true").lower() == "true",
            base_url=ollama_host,
            default_model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
            timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
            rate_limit_rpm=(
                int(os.getenv("OLLAMA_RATE_LIMIT_RPM", "120"))
                if os.getenv("OLLAMA_RATE_LIMIT_RPM")
                else None
            ),
            cost_per_1k_tokens=float(os.getenv("OLLAMA_COST_PER_1K_TOKENS", "0.0")),
            priority=int(os.getenv("OLLAMA_PRIORITY", "1")),
            max_retries=int(os.getenv("OLLAMA_MAX_RETRIES", "2")),
            retry_delay=float(os.getenv("OLLAMA_RETRY_DELAY", "0.5")),
        )

        return config

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get list of enabled providers."""
        return [provider for provider in self.providers.values() if provider.enabled]

    def get_provider_order(self) -> List[str]:
        """Get providers ordered by fallback strategy."""
        enabled_providers = self.get_enabled_providers()

        if self.fallback_strategy == FallbackStrategy.COST_OPTIMIZED:
            # Order by cost (cheapest first)
            return [
                p.name
                for p in sorted(enabled_providers, key=lambda x: x.cost_per_1k_tokens)
            ]

        elif self.fallback_strategy == FallbackStrategy.QUALITY_OPTIMIZED:
            # Order by priority (highest first)
            return [
                p.name
                for p in sorted(
                    enabled_providers, key=lambda x: x.priority, reverse=True
                )
            ]

        elif self.fallback_strategy == FallbackStrategy.ROUND_ROBIN:
            # Fixed order: ollama, openai, anthropic
            order = ["ollama", "openai", "anthropic"]
            return [
                name
                for name in order
                if name in self.providers and self.providers[name].enabled
            ]

        elif self.fallback_strategy == FallbackStrategy.FAIL_FAST:
            # Only the first available provider
            if enabled_providers:
                return [enabled_providers[0].name]
            return []

        else:  # SMART_FALLBACK (default)
            # Balance cost and reliability: ollama first (free), then by priority
            smart_order = []
            if "ollama" in self.providers and self.providers["ollama"].enabled:
                smart_order.append("ollama")

            other_providers = [p for p in enabled_providers if p.name != "ollama"]
            other_providers.sort(key=lambda x: x.priority, reverse=True)
            smart_order.extend([p.name for p in other_providers])

            return smart_order

    def estimate_request_cost(self, tokens: int, provider_name: str) -> float:
        """Estimate cost for a request."""
        if provider_name not in self.providers:
            return 0.0

        provider = self.providers[provider_name]
        return (tokens / 1000.0) * provider.cost_per_1k_tokens

    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []

        if not self.get_enabled_providers():
            issues.append("No providers are enabled")

        for name, provider in self.providers.items():
            if provider.enabled:
                if name in ["openai", "anthropic"] and not provider.api_key:
                    issues.append(f"Provider {name} is enabled but missing API key")

                if provider.timeout <= 0:
                    issues.append(
                        f"Provider {name} has invalid timeout: {provider.timeout}"
                    )

                if provider.cost_per_1k_tokens < 0:
                    issues.append(
                        f"Provider {name} has negative cost: {provider.cost_per_1k_tokens}"
                    )

        if self.cost_config.max_cost_per_request <= 0:
            issues.append(
                f"Invalid max cost per request: {self.cost_config.max_cost_per_request}"
            )

        if self.max_fallback_attempts < 0:
            issues.append(
                f"Invalid max fallback attempts: {self.max_fallback_attempts}"
            )

        return issues
