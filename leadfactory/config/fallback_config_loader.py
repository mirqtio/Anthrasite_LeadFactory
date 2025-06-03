"""
Configuration loader for LLM fallback system.

This module provides functionality to load and manage configuration for the
LLM fallback system, including provider settings, cost thresholds, and
health monitoring parameters.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    name: str
    type: str
    model: str
    api_key_env: str
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: int = 300
    half_open_max_calls: int = 3


@dataclass
class FallbackConfig:
    """Configuration for fallback strategy."""

    strategy: str = "cost_optimized"
    max_attempts: int = 5
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    triggers: list = field(
        default_factory=lambda: [
            "rate_limit",
            "cost_threshold_exceeded",
            "timeout",
            "server_error",
            "quota_exceeded",
            "model_unavailable",
        ]
    )


@dataclass
class CostMonitoringConfig:
    """Configuration for cost monitoring."""

    enabled: bool = True
    budget_limits: Dict[str, float] = field(
        default_factory=lambda: {"daily": 100.0, "monthly": 2000.0, "per_request": 5.0}
    )
    thresholds: Dict[str, float] = field(
        default_factory=lambda: {"warning": 0.8, "critical": 0.95, "fallback": 0.9}
    )
    cost_per_token: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class HealthMonitoringConfig:
    """Configuration for health monitoring."""

    enabled: bool = True
    check_interval: int = 60
    timeout: int = 10
    response_time_threshold: float = 5.0
    failure_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "consecutive_failures": 3,
            "failure_rate": 0.5,
            "slow_response_threshold": 2.0,
        }
    )
    alert_settings: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "severity_levels": ["INFO", "WARNING", "ERROR", "CRITICAL"],
        }
    )


@dataclass
class PipelineConfig:
    """Configuration for pipeline integration."""

    pause_on_all_failures: bool = True
    pause_duration: int = 300
    graceful_degradation: bool = True
    cache_responses: bool = True
    cache_ttl: int = 3600
    batching: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "max_batch_size": 10,
            "batch_timeout": 5.0,
        }
    )
    async_processing: bool = True
    max_concurrent_requests: int = 10


@dataclass
class LLMFallbackConfig:
    """Complete configuration for LLM fallback system."""

    primary_provider: ProviderConfig
    secondary_provider: ProviderConfig
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    cost_monitoring: CostMonitoringConfig = field(default_factory=CostMonitoringConfig)
    health_monitoring: HealthMonitoringConfig = field(
        default_factory=HealthMonitoringConfig
    )
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    logging: Dict[str, Any] = field(
        default_factory=lambda: {
            "level": "INFO",
            "log_requests": True,
            "log_responses": False,
            "log_costs": True,
            "log_health_checks": True,
            "log_fallbacks": True,
        }
    )


class FallbackConfigLoader:
    """Loader for LLM fallback configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "fallback_config.yaml"

        self.config_path = Path(config_path)
        self._config_cache: Optional[LLMFallbackConfig] = None

    def load_config(self, environment: Optional[str] = None) -> LLMFallbackConfig:
        """
        Load configuration from YAML file.

        Args:
            environment: Environment name for environment-specific overrides

        Returns:
            LLMFallbackConfig: Loaded configuration
        """
        try:
            if not self.config_path.exists():
                logger.warning(
                    f"Config file not found: {self.config_path}, using defaults"
                )
                return self._get_default_config()

            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)

            # Apply environment-specific overrides
            if environment and "environments" in config_data:
                env_overrides = config_data["environments"].get(environment, {})
                config_data = self._merge_config(config_data, env_overrides)

            # Parse configuration
            config = self._parse_config(config_data)

            # Cache the configuration
            self._config_cache = config

            logger.info(f"Loaded fallback configuration from {self.config_path}")
            if environment:
                logger.info(f"Applied environment overrides for: {environment}")

            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Using default configuration")
            return self._get_default_config()

    def get_cached_config(self) -> Optional[LLMFallbackConfig]:
        """Get cached configuration if available."""
        return self._config_cache

    def reload_config(self, environment: Optional[str] = None) -> LLMFallbackConfig:
        """Reload configuration from file."""
        self._config_cache = None
        return self.load_config(environment)

    def _parse_config(self, config_data: Dict[str, Any]) -> LLMFallbackConfig:
        """Parse configuration data into dataclass."""
        # Parse provider configurations
        providers = config_data.get("providers", {})
        primary_data = providers.get("primary", {})
        secondary_data = providers.get("secondary", {})

        primary_provider = ProviderConfig(
            name=primary_data.get("name", "GPT-4o"),
            type=primary_data.get("type", "openai"),
            model=primary_data.get("model", "gpt-4o"),
            api_key_env=primary_data.get("api_key_env", "OPENAI_API_KEY"),
            base_url=primary_data.get("base_url", "https://api.openai.com/v1"),  # pragma: allowlist secret
            timeout=primary_data.get("timeout", 30),
            max_retries=primary_data.get("max_retries", 3),
            retry_delay=primary_data.get("retry_delay", 1.0),
        )

        secondary_provider = ProviderConfig(
            name=secondary_data.get("name", "Claude"),
            type=secondary_data.get("type", "anthropic"),
            model=secondary_data.get("model", "claude-3-sonnet-20240229"),
            api_key_env=secondary_data.get("api_key_env", "ANTHROPIC_API_KEY"),
            base_url=secondary_data.get("base_url", "https://api.anthropic.com"),  # pragma: allowlist secret
            timeout=secondary_data.get("timeout", 30),
            max_retries=secondary_data.get("max_retries", 2),
            retry_delay=secondary_data.get("retry_delay", 2.0),
        )

        # Parse fallback configuration
        fallback_data = config_data.get("fallback", {})
        circuit_breaker_data = fallback_data.get("circuit_breaker", {})
        circuit_breaker = CircuitBreakerConfig(
            failure_threshold=circuit_breaker_data.get("failure_threshold", 5),
            recovery_timeout=circuit_breaker_data.get("recovery_timeout", 300),
            half_open_max_calls=circuit_breaker_data.get("half_open_max_calls", 3),
        )

        fallback = FallbackConfig(
            strategy=fallback_data.get("strategy", "cost_optimized"),
            max_attempts=fallback_data.get("max_attempts", 5),
            circuit_breaker=circuit_breaker,
            triggers=fallback_data.get(
                "triggers",
                [
                    "rate_limit",
                    "cost_threshold_exceeded",
                    "timeout",
                    "server_error",
                    "quota_exceeded",
                    "model_unavailable",
                ],
            ),
        )

        # Parse cost monitoring configuration
        cost_data = config_data.get("cost_monitoring", {})
        cost_monitoring = CostMonitoringConfig(
            enabled=cost_data.get("enabled", True),
            budget_limits=cost_data.get(
                "budget_limits", {"daily": 100.0, "monthly": 2000.0, "per_request": 5.0}
            ),
            thresholds=cost_data.get(
                "thresholds", {"warning": 0.8, "critical": 0.95, "fallback": 0.9}
            ),
            cost_per_token=cost_data.get("cost_per_token", {}),
        )

        # Parse health monitoring configuration
        health_data = config_data.get("health_monitoring", {})
        health_monitoring = HealthMonitoringConfig(
            enabled=health_data.get("enabled", True),
            check_interval=health_data.get("check_interval", 60),
            timeout=health_data.get("timeout", 10),
            response_time_threshold=health_data.get("response_time_threshold", 5.0),
            failure_thresholds=health_data.get(
                "failure_thresholds",
                {
                    "consecutive_failures": 3,
                    "failure_rate": 0.5,
                    "slow_response_threshold": 2.0,
                },
            ),
            alert_settings=health_data.get(
                "alert_settings",
                {
                    "enabled": True,
                    "severity_levels": ["INFO", "WARNING", "ERROR", "CRITICAL"],
                },
            ),
        )

        # Parse pipeline configuration
        pipeline_data = config_data.get("pipeline", {})
        pipeline = PipelineConfig(
            pause_on_all_failures=pipeline_data.get("pause_on_all_failures", True),
            pause_duration=pipeline_data.get("pause_duration", 300),
            graceful_degradation=pipeline_data.get("graceful_degradation", True),
            cache_responses=pipeline_data.get("cache_responses", True),
            cache_ttl=pipeline_data.get("cache_ttl", 3600),
            batching=pipeline_data.get(
                "batching",
                {"enabled": False, "max_batch_size": 10, "batch_timeout": 5.0},
            ),
            async_processing=pipeline_data.get("async_processing", True),
            max_concurrent_requests=pipeline_data.get("max_concurrent_requests", 10),
        )

        return LLMFallbackConfig(
            primary_provider=primary_provider,
            secondary_provider=secondary_provider,
            fallback=fallback,
            cost_monitoring=cost_monitoring,
            health_monitoring=health_monitoring,
            pipeline=pipeline,
            logging=config_data.get(
                "logging",
                {
                    "level": "INFO",
                    "log_requests": True,
                    "log_responses": False,
                    "log_costs": True,
                    "log_health_checks": True,
                    "log_fallbacks": True,
                },
            ),
        )

    def _merge_config(
        self, base_config: Dict[str, Any], overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge environment-specific overrides into base configuration."""

        def merge_dict(
            base: Dict[str, Any], override: Dict[str, Any]
        ) -> Dict[str, Any]:
            result = base.copy()
            for key, value in override.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result

        return merge_dict(base_config, overrides)

    def _get_default_config(self) -> LLMFallbackConfig:
        """Get default configuration."""
        return LLMFallbackConfig(
            primary_provider=ProviderConfig(
                name="GPT-4o",
                type="openai",
                model="gpt-4o",
                api_key_env="OPENAI_API_KEY",
                base_url="https://api.openai.com/v1",  # pragma: allowlist secret
            ),
            secondary_provider=ProviderConfig(
                name="Claude",
                type="anthropic",
                model="claude-3-sonnet-20240229",
                api_key_env="ANTHROPIC_API_KEY",
                base_url="https://api.anthropic.com",  # pragma: allowlist secret
            ),
        )


# Global configuration loader instance
_config_loader = FallbackConfigLoader()


def get_fallback_config(environment: Optional[str] = None) -> LLMFallbackConfig:
    """
    Get the fallback configuration.

    Args:
        environment: Environment name for environment-specific overrides

    Returns:
        LLMFallbackConfig: The configuration
    """
    # Try to get from environment variable first
    if environment is None:
        environment = os.getenv("LEADFACTORY_ENV", os.getenv("ENV"))

    # Check if we have a cached config
    cached_config = _config_loader.get_cached_config()
    if cached_config is not None:
        return cached_config

    # Load configuration
    return _config_loader.load_config(environment)


def reload_fallback_config(environment: Optional[str] = None) -> LLMFallbackConfig:
    """
    Reload the fallback configuration from file.

    Args:
        environment: Environment name for environment-specific overrides

    Returns:
        LLMFallbackConfig: The reloaded configuration
    """
    if environment is None:
        environment = os.getenv("LEADFACTORY_ENV", os.getenv("ENV"))

    return _config_loader.reload_config(environment)
