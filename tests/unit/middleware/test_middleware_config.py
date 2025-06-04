"""
Tests for middleware configuration classes.
"""

import os
from unittest.mock import patch

import pytest

from leadfactory.middleware.middleware_config import (
    BudgetMiddlewareOptions,
    FrameworkType,
    MiddlewareConfig,
)


class TestBudgetMiddlewareOptions:
    """Test BudgetMiddlewareOptions configuration."""

    def test_default_options(self):
        """Test default configuration values."""
        options = BudgetMiddlewareOptions()

        assert options.enable_budget_monitoring is True
        assert options.enable_cost_tracking is True
        assert options.enable_throttling is True
        assert options.enable_alerting is True
        assert options.exclude_paths == ["/health", "/metrics", "/status"]
        assert options.include_only_paths is None
        assert options.exclude_methods == ["OPTIONS"]
        assert options.async_processing is True
        assert options.cache_decisions is True
        assert options.cache_ttl_seconds == 60
        assert options.fail_open is True
        assert options.log_errors is True
        assert options.custom_cost_extractor is None
        assert options.custom_user_extractor is None
        assert options.custom_operation_extractor is None

    def test_custom_options(self):
        """Test custom configuration values."""
        options = BudgetMiddlewareOptions(
            enable_budget_monitoring=False,
            exclude_paths=["/custom"],
            cache_ttl_seconds=120,
            fail_open=False,
        )

        assert options.enable_budget_monitoring is False
        assert options.exclude_paths == ["/custom"]
        assert options.cache_ttl_seconds == 120
        assert options.fail_open is False


class TestFrameworkType:
    """Test FrameworkType enum."""

    def test_framework_types(self):
        """Test all framework types are available."""
        assert FrameworkType.EXPRESS.value == "express"
        assert FrameworkType.FASTAPI.value == "fastapi"
        assert FrameworkType.FLASK.value == "flask"
        assert FrameworkType.DJANGO.value == "django"
        assert FrameworkType.GENERIC.value == "generic"


class TestMiddlewareConfig:
    """Test MiddlewareConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MiddlewareConfig()

        assert config.framework == FrameworkType.GENERIC
        assert isinstance(config.budget_options, BudgetMiddlewareOptions)
        assert config.config_file_path is None
        assert config.load_from_env is True
        assert config.env_prefix == "LEADFACTORY_"
        assert config.enable_request_logging is True
        assert config.log_level == "INFO"
        assert config.log_format == "json"
        assert config.enable_metrics is True
        assert config.metrics_endpoint == "/metrics"
        assert config.health_endpoint == "/health"

    def test_custom_config(self):
        """Test custom configuration values."""
        budget_opts = BudgetMiddlewareOptions(enable_throttling=False)
        config = MiddlewareConfig(
            framework=FrameworkType.FASTAPI,
            budget_options=budget_opts,
            log_level="DEBUG",
        )

        assert config.framework == FrameworkType.FASTAPI
        assert config.budget_options.enable_throttling is False
        assert config.log_level == "DEBUG"

    @patch.dict(
        os.environ,
        {
            "LEADFACTORY_FRAMEWORK": "fastapi",
            "LEADFACTORY_ENABLE_BUDGET_MONITORING": "false",
            "LEADFACTORY_ENABLE_COST_TRACKING": "true",
            "LEADFACTORY_ENABLE_THROTTLING": "false",
            "LEADFACTORY_ENABLE_ALERTING": "true",
            "LEADFACTORY_EXCLUDE_PATHS": "/health,/status,/custom",
            "LEADFACTORY_INCLUDE_ONLY_PATHS": "/api,/v1",
            "LEADFACTORY_EXCLUDE_METHODS": "OPTIONS,HEAD",
            "LEADFACTORY_ASYNC_PROCESSING": "false",
            "LEADFACTORY_CACHE_DECISIONS": "false",
            "LEADFACTORY_CACHE_TTL_SECONDS": "120",
            "LEADFACTORY_FAIL_OPEN": "false",
            "LEADFACTORY_LOG_ERRORS": "false",
            "LEADFACTORY_CONFIG_FILE_PATH": "/path/to/config.json",
            "LEADFACTORY_ENABLE_REQUEST_LOGGING": "false",
            "LEADFACTORY_LOG_LEVEL": "DEBUG",
            "LEADFACTORY_LOG_FORMAT": "text",
            "LEADFACTORY_ENABLE_METRICS": "false",
            "LEADFACTORY_METRICS_ENDPOINT": "/custom-metrics",
            "LEADFACTORY_HEALTH_ENDPOINT": "/custom-health",
        },
    )
    def test_from_environment(self):
        """Test configuration loading from environment variables."""
        config = MiddlewareConfig.from_environment()

        # Framework
        assert config.framework == FrameworkType.FASTAPI

        # Budget options
        assert config.budget_options.enable_budget_monitoring is False
        assert config.budget_options.enable_cost_tracking is True
        assert config.budget_options.enable_throttling is False
        assert config.budget_options.enable_alerting is True
        assert config.budget_options.exclude_paths == ["/health", "/status", "/custom"]
        assert config.budget_options.include_only_paths == ["/api", "/v1"]
        assert config.budget_options.exclude_methods == ["OPTIONS", "HEAD"]
        assert config.budget_options.async_processing is False
        assert config.budget_options.cache_decisions is False
        assert config.budget_options.cache_ttl_seconds == 120
        assert config.budget_options.fail_open is False
        assert config.budget_options.log_errors is False

        # Main config
        assert config.config_file_path == "/path/to/config.json"
        assert config.enable_request_logging is False
        assert config.log_level == "DEBUG"
        assert config.log_format == "text"
        assert config.enable_metrics is False
        assert config.metrics_endpoint == "/custom-metrics"
        assert config.health_endpoint == "/custom-health"

    @patch.dict(
        os.environ,
        {
            "LEADFACTORY_FRAMEWORK": "invalid",
            "LEADFACTORY_CACHE_TTL_SECONDS": "invalid",
        },
    )
    def test_from_environment_invalid_values(self):
        """Test handling of invalid environment values."""
        config = MiddlewareConfig.from_environment()

        # Invalid framework should default to GENERIC
        assert config.framework == FrameworkType.GENERIC

        # Invalid cache TTL should default to 60
        assert config.budget_options.cache_ttl_seconds == 60

    @patch.dict(
        os.environ,
        {
            "CUSTOM_FRAMEWORK": "flask",
            "CUSTOM_ENABLE_BUDGET_MONITORING": "false",
        },
    )
    def test_from_environment_custom_prefix(self):
        """Test configuration loading with custom prefix."""
        config = MiddlewareConfig.from_environment(env_prefix="CUSTOM_")

        assert config.framework == FrameworkType.FLASK
        assert config.budget_options.enable_budget_monitoring is False
        assert config.env_prefix == "CUSTOM_"

    def test_to_dict(self):
        """Test configuration serialization to dictionary."""
        budget_opts = BudgetMiddlewareOptions(
            enable_throttling=False,
            cache_ttl_seconds=120,
        )
        config = MiddlewareConfig(
            framework=FrameworkType.FASTAPI,
            budget_options=budget_opts,
            log_level="DEBUG",
        )

        config_dict = config.to_dict()

        assert config_dict["framework"] == "fastapi"
        assert config_dict["budget_options"]["enable_throttling"] is False
        assert config_dict["budget_options"]["cache_ttl_seconds"] == 120
        assert config_dict["log_level"] == "DEBUG"
        assert isinstance(config_dict, dict)

    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_defaults(self):
        """Test environment loading with no environment variables set."""
        config = MiddlewareConfig.from_environment()

        # Should use all defaults
        assert config.framework == FrameworkType.GENERIC
        assert config.budget_options.enable_budget_monitoring is True
        assert config.budget_options.exclude_paths == ["/health", "/metrics", "/status"]
        assert config.log_level == "INFO"
