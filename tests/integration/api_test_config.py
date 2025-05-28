"""
API Test Configuration Module

This module provides a centralized configuration interface for API testing.
It determines whether to use real APIs or mocks based on environment variables
and command-line options set in conftest.py.
"""

import os
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast
import json
from datetime import datetime
from pathlib import Path

# Type variables for decorator return typing
F = TypeVar('F', bound=Callable[..., Any])

# Initialize the environment flags
_USE_REAL_APIS = os.environ.get("LEADFACTORY_USE_REAL_APIS", "0") == "1"
_LOG_METRICS = os.environ.get("LEADFACTORY_LOG_API_METRICS", "0") in ("1", "true", "yes")
_API_FLAGS = {
}

# Define supported APIs and their description
SUPPORTED_APIS = {
    'yelp': 'Yelp Fusion API for business discovery',
    'google': 'Google Places API for location data',
    'openai': 'OpenAI API for GPT models',
    'sendgrid': 'SendGrid API for email delivery',
    'screenshotone': 'ScreenshotOne API for website captures',
    'anthropic': 'Anthropic API for Claude models',
    'mapbox': 'Mapbox API for mapping services',
    'stripe': 'Stripe API for payment processing',
    'twilio': 'Twilio API for SMS and voice'
}

# Define endpoints for each API for better metrics grouping
API_ENDPOINTS = {
    'yelp': ['business_search', 'business_details', 'business_reviews'],
    'google': ['places_search', 'place_details', 'place_photos'],
    'openai': ['chat_completion', 'embedding', 'moderation'],
    'sendgrid': ['send_email', 'validate_email'],
    'screenshotone': ['take_screenshot', 'pdf_generation'],
    'anthropic': ['message_create', 'message_stream'],
    'mapbox': ['geocoding', 'directions'],
    'stripe': ['create_charge', 'create_customer'],
    'twilio': ['send_sms', 'verify_phone']
}

class APITestConfig:
    """Configuration for API integration tests.

    This class provides methods to control which APIs are tested with real
    credentials versus mocks, and maintains configuration for metrics collection.
    """

    # Cache for configuration to avoid repeated environment lookups
    _config_cache: Dict[str, Any] = {}

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get the complete API test configuration."""
        if cls._config_cache:
            return cls._config_cache

        # Base configuration
        config = {
            'use_real_apis': cls.use_real_apis(),
            'apis_to_test': cls.apis_to_test(),
            'metrics': {
                'enabled': cls.metrics_enabled(),
                'log_to_file': cls.should_log_to_file(),
                'log_to_prometheus': cls.should_log_to_prometheus(),
                'directory': cls.metrics_directory()
            }
        }

        # Add API-specific configurations
        config['api_configs'] = {}
        for api in SUPPORTED_APIS.keys():
            config['api_configs'][api] = {
                'enabled': cls.should_test_api(api),
                'throttling': cls.get_api_throttling(api),
                'endpoints': cls.get_api_endpoints(api)
            }

        cls._config_cache = config
        return config

    @staticmethod
    def use_real_apis() -> bool:
        """Check if the tests should use real APIs based on environment settings."""
        return os.environ.get("LEADFACTORY_USE_REAL_APIS", "0").lower() in ("1", "true", "yes")

    @staticmethod
    def apis_to_test() -> List[str]:
        """Get the list of APIs to test with real credentials."""
        apis_env = os.environ.get("LEADFACTORY_TEST_APIS", "all")

        if apis_env.lower() == "all":
            return list(SUPPORTED_APIS.keys())
        elif apis_env.lower() == "none":
            return []
        else:
            return [api.strip().lower() for api in apis_env.split(',') if api.strip()]

    @classmethod
    def should_test_api(cls, api_name: str) -> bool:
        """Check if a specific API should be tested with real calls."""
        # Global setting - if not using real APIs at all, return False
        if not cls.use_real_apis():
            return False

        # Check if this API is in the list of APIs to test
        apis_to_test = cls.apis_to_test()
        if apis_to_test == [] or (apis_to_test != list(SUPPORTED_APIS.keys()) and api_name not in apis_to_test):
            return False

        # Check if this specific API is enabled via environment variable
        env_var = f"LEADFACTORY_TEST_{api_name.upper()}_API"
        env_value = os.environ.get(env_var)

        # If the environment variable is explicitly set, use its value
        if env_value is not None:
            return env_value.lower() in ("1", "true", "yes")

        # Otherwise, consider it enabled since it's in the apis_to_test list
        return True

    @staticmethod
    def metrics_enabled() -> bool:
        """Check if metrics collection is enabled."""
        return os.environ.get("LEADFACTORY_LOG_API_METRICS", "true").lower() in ("1", "true", "yes")

    @staticmethod
    def should_log_to_file() -> bool:
        """Check if metrics should be logged to files."""
        return os.environ.get("LEADFACTORY_LOG_METRICS_TO_FILE", "true").lower() in ("1", "true", "yes")

    @staticmethod
    def should_log_to_prometheus() -> bool:
        """Check if metrics should be logged to Prometheus."""
        return os.environ.get("LEADFACTORY_LOG_METRICS_TO_PROMETHEUS", "true").lower() in ("1", "true", "yes")

    @staticmethod
    def metrics_directory() -> str:
        """Get the directory where metrics should be stored."""
        return os.environ.get("METRICS_DIR", "metrics")

    @staticmethod
    def get_api_throttling(api_name: str) -> Dict[str, Any]:
        """Get throttling configuration for an API."""
        throttling = {
            'enabled': False,
            'requests_per_minute': 60,
            'requests_per_day': 1000
        }

        # Check if throttling is enabled for this API
        throttle_env = f"LEADFACTORY_THROTTLE_{api_name.upper()}_API"
        if os.environ.get(throttle_env, "0").lower() in ("1", "true", "yes"):
            throttling['enabled'] = True

            # Get specific throttling parameters if set
            rpm_env = f"LEADFACTORY_{api_name.upper()}_RPM"
            rpd_env = f"LEADFACTORY_{api_name.upper()}_RPD"

            if rpm_env in os.environ:
                try:
                    throttling['requests_per_minute'] = int(os.environ[rpm_env])
                except ValueError:
                    pass

            if rpd_env in os.environ:
                try:
                    throttling['requests_per_day'] = int(os.environ[rpd_env])
                except ValueError:
                    pass

        return throttling

    @staticmethod
    def get_api_endpoints(api_name: str) -> List[str]:
        """Get the list of endpoints for an API."""
        return API_ENDPOINTS.get(api_name, [])

    @classmethod
    def save_config(cls, filepath: Optional[str] = None) -> str:
        """Save the current configuration to a JSON file."""
        config = cls.get_config()
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"api_test_config_{timestamp}.json"

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2, default=str)

        return filepath

    @staticmethod
    def get_api_keys() -> Dict[str, Optional[str]]:
        """
        Get API keys from environment variables.

        Returns:
            Dict[str, Optional[str]]: Dictionary of API keys
        """
        return {
            "yelp": os.environ.get("YELP_API_KEY"),
            "google": os.environ.get("GOOGLE_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "sendgrid": os.environ.get("SENDGRID_API_KEY"),
            "screenshotone": os.environ.get("SCREENSHOTONE_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        }

    @staticmethod
    def check_api_key(api_name: str) -> bool:
        """
        Check if a specific API key is available in the environment.

        Args:
            api_name: The name of the API to check

        Returns:
            bool: True if the API key is available
        """
        api_keys = APITestConfig.get_api_keys()
        return bool(api_keys.get(api_name.lower()))

    @staticmethod
    def should_use_real_api(api_name: str) -> bool:
        """
        Determine if a specific API should use real calls based on:
        1. Global setting for using real APIs
        2. Specific API being enabled for testing
        3. API key being available

        Args:
            api_name: The name of the API to check

        Returns:
            bool: True if real API calls should be used
        """
        return (
            use_real_apis() and
            should_test_api(api_name) and
            APITestConfig.check_api_key(api_name)
        )


# Helper functions for backward compatibility
def use_real_apis() -> bool:
    """Check if the tests should use real APIs based on environment settings."""
    return APITestConfig.use_real_apis()


def should_test_api(api_name: str) -> bool:
    """Check if a specific API should be tested with real calls."""
    return APITestConfig.should_test_api(api_name)


def log_api_metrics() -> bool:
    """
    Check if API metrics should be logged.

    Returns:
        bool: True if API metrics should be logged
    """
    return _LOG_METRICS


def api_call_metrics(api_name: str, endpoint: str = "default") -> Callable[[F], F]:
    """
    Decorator for measuring API call metrics like latency and logging them.

    Args:
        api_name: The name of the API being called
        endpoint: The specific API endpoint or operation being called

    Returns:
        Callable: Decorated function that logs metrics
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip metrics for mock APIs unless specifically enabled
            if not use_real_apis() and not log_api_metrics():
                return func(*args, **kwargs)

            # Extract metrics_logger from kwargs if available
            metrics_logger = kwargs.pop('metrics_logger', None)

            # Measure latency
            start_time = time.time()
            result = func(*args, **kwargs)
            latency = time.time() - start_time

            # Log metrics if a logger was provided
            if metrics_logger:
                # Try to extract token usage and cost info from result if available
                tokens = 0
                cost = 0.0

                # Handle OpenAI-style responses
                if api_name.lower() == "openai" and isinstance(result, dict):
                    usage = result.get("usage", {})
                    tokens = usage.get("total_tokens", 0)
                    # Approximate cost calculation based on model and tokens
                    model = result.get("model", "")
                    if "gpt-4" in model:
                        cost = tokens * 0.00003  # $0.03 per 1K tokens (simplified)
                    else:
                        cost = tokens * 0.000002  # $0.002 per 1K tokens (simplified)

                # Log the metrics
                metrics_logger.log_api_call(
                    api_name=api_name,
                    endpoint=endpoint,
                    latency=latency,
                    cost=cost,
                    tokens=tokens
                )

            return result
        return cast(F, wrapper)
    return decorator
