"""
Configuration classes for LeadFactory middleware components.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class FrameworkType(Enum):
    """Supported web framework types."""

    EXPRESS = "express"
    FASTAPI = "fastapi"
    FLASK = "flask"
    DJANGO = "django"
    GENERIC = "generic"


@dataclass
class BudgetMiddlewareOptions:
    """Configuration options for budget middleware."""

    # Budget monitoring
    enable_budget_monitoring: bool = True
    enable_cost_tracking: bool = True
    enable_throttling: bool = True
    enable_alerting: bool = True

    # Request filtering
    exclude_paths: List[str] = field(
        default_factory=lambda: ["/health", "/metrics", "/status"]
    )
    include_only_paths: Optional[List[str]] = None
    exclude_methods: List[str] = field(default_factory=lambda: ["OPTIONS"])

    # Performance options
    async_processing: bool = True
    cache_decisions: bool = True
    cache_ttl_seconds: int = 60

    # Error handling
    fail_open: bool = True  # Allow requests through if middleware fails
    log_errors: bool = True

    # Custom extractors
    custom_cost_extractor: Optional[Callable] = None
    custom_user_extractor: Optional[Callable] = None
    custom_operation_extractor: Optional[Callable] = None


@dataclass
class MiddlewareConfig:
    """Main configuration for LeadFactory middleware."""

    framework: FrameworkType = FrameworkType.GENERIC
    budget_options: BudgetMiddlewareOptions = field(
        default_factory=BudgetMiddlewareOptions
    )

    # Environment-based configuration
    config_file_path: Optional[str] = None
    load_from_env: bool = True
    env_prefix: str = "LEADFACTORY_"

    # Logging configuration
    enable_request_logging: bool = True
    log_level: str = "INFO"
    log_format: str = "json"

    # Metrics and monitoring
    enable_metrics: bool = True
    metrics_endpoint: str = "/metrics"
    health_endpoint: str = "/health"

    @classmethod
    def from_environment(cls, env_prefix: str = "LEADFACTORY_") -> "MiddlewareConfig":
        """Create configuration from environment variables."""
        config = cls()
        config.env_prefix = env_prefix

        # Framework type
        framework_str = os.getenv(f"{env_prefix}FRAMEWORK", "generic").lower()
        try:
            config.framework = FrameworkType(framework_str)
        except ValueError:
            config.framework = FrameworkType.GENERIC

        # Budget options
        budget_opts = BudgetMiddlewareOptions()

        budget_opts.enable_budget_monitoring = (
            os.getenv(f"{env_prefix}ENABLE_BUDGET_MONITORING", "true").lower() == "true"
        )

        budget_opts.enable_cost_tracking = (
            os.getenv(f"{env_prefix}ENABLE_COST_TRACKING", "true").lower() == "true"
        )

        budget_opts.enable_throttling = (
            os.getenv(f"{env_prefix}ENABLE_THROTTLING", "true").lower() == "true"
        )

        budget_opts.enable_alerting = (
            os.getenv(f"{env_prefix}ENABLE_ALERTING", "true").lower() == "true"
        )

        # Paths configuration
        exclude_paths = os.getenv(
            f"{env_prefix}EXCLUDE_PATHS", "/health,/metrics,/status"
        )
        budget_opts.exclude_paths = [
            p.strip() for p in exclude_paths.split(",") if p.strip()
        ]

        include_paths = os.getenv(f"{env_prefix}INCLUDE_ONLY_PATHS")
        if include_paths:
            budget_opts.include_only_paths = [
                p.strip() for p in include_paths.split(",") if p.strip()
            ]

        exclude_methods = os.getenv(f"{env_prefix}EXCLUDE_METHODS", "OPTIONS")
        budget_opts.exclude_methods = [
            m.strip().upper() for m in exclude_methods.split(",") if m.strip()
        ]

        # Performance options
        budget_opts.async_processing = (
            os.getenv(f"{env_prefix}ASYNC_PROCESSING", "true").lower() == "true"
        )

        budget_opts.cache_decisions = (
            os.getenv(f"{env_prefix}CACHE_DECISIONS", "true").lower() == "true"
        )

        try:
            budget_opts.cache_ttl_seconds = int(
                os.getenv(f"{env_prefix}CACHE_TTL_SECONDS", "60")
            )
        except ValueError:
            budget_opts.cache_ttl_seconds = 60

        # Error handling
        budget_opts.fail_open = (
            os.getenv(f"{env_prefix}FAIL_OPEN", "true").lower() == "true"
        )

        budget_opts.log_errors = (
            os.getenv(f"{env_prefix}LOG_ERRORS", "true").lower() == "true"
        )

        config.budget_options = budget_opts

        # Main config options
        config.config_file_path = os.getenv(f"{env_prefix}CONFIG_FILE_PATH")

        config.enable_request_logging = (
            os.getenv(f"{env_prefix}ENABLE_REQUEST_LOGGING", "true").lower() == "true"
        )

        config.log_level = os.getenv(f"{env_prefix}LOG_LEVEL", "INFO").upper()
        config.log_format = os.getenv(f"{env_prefix}LOG_FORMAT", "json").lower()

        config.enable_metrics = (
            os.getenv(f"{env_prefix}ENABLE_METRICS", "true").lower() == "true"
        )

        config.metrics_endpoint = os.getenv(f"{env_prefix}METRICS_ENDPOINT", "/metrics")
        config.health_endpoint = os.getenv(f"{env_prefix}HEALTH_ENDPOINT", "/health")

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "framework": self.framework.value,
            "budget_options": {
                "enable_budget_monitoring": self.budget_options.enable_budget_monitoring,
                "enable_cost_tracking": self.budget_options.enable_cost_tracking,
                "enable_throttling": self.budget_options.enable_throttling,
                "enable_alerting": self.budget_options.enable_alerting,
                "exclude_paths": self.budget_options.exclude_paths,
                "include_only_paths": self.budget_options.include_only_paths,
                "exclude_methods": self.budget_options.exclude_methods,
                "async_processing": self.budget_options.async_processing,
                "cache_decisions": self.budget_options.cache_decisions,
                "cache_ttl_seconds": self.budget_options.cache_ttl_seconds,
                "fail_open": self.budget_options.fail_open,
                "log_errors": self.budget_options.log_errors,
            },
            "config_file_path": self.config_file_path,
            "load_from_env": self.load_from_env,
            "env_prefix": self.env_prefix,
            "enable_request_logging": self.enable_request_logging,
            "log_level": self.log_level,
            "log_format": self.log_format,
            "enable_metrics": self.enable_metrics,
            "metrics_endpoint": self.metrics_endpoint,
            "health_endpoint": self.health_endpoint,
        }
