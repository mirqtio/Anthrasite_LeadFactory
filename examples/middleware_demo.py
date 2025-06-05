#!/usr/bin/env python3
"""
Demo script showing how to use the LeadFactory Budget Guard Middleware
with different web frameworks.
"""

import logging
import os
import sys
from typing import Optional

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import contextlib

from leadfactory.middleware import (
    BudgetGuardMiddleware,
    BudgetMiddlewareOptions,
    FrameworkType,
    MiddlewareConfig,
    create_budget_middleware,
    create_fastapi_budget_middleware,
    create_flask_budget_middleware,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_basic_middleware():
    """Demonstrate basic middleware creation and usage."""

    # Create basic middleware with default configuration
    middleware = create_budget_middleware()

    # Simulate a request
    class MockRequest:
        def __init__(
            self, path: str, method: str = "POST", headers: Optional[dict] = None
        ):
            self.path = path
            self.method = method
            self.headers = headers or {}
            self.json = {"message": "test request"}

    request = MockRequest("/api/chat", headers={"X-User-ID": "demo_user"})

    # Process the request
    try:
        result = middleware.process_request(request)
        if result is None:
            pass
        else:
            pass
    except Exception:
        pass


def demo_custom_configuration():
    """Demonstrate middleware with custom configuration."""

    # Custom extractors
    def extract_user_id(request):
        """Extract user ID from request headers."""
        return request.headers.get("X-User-ID", "anonymous")

    def extract_operation(request):
        """Extract operation type from request path."""
        if "chat" in request.path:
            return "chat_completion"
        elif "embedding" in request.path:
            return "text_embedding"
        return "api_call"

    def estimate_cost(request):
        """Estimate request cost."""
        if hasattr(request, "json") and request.json:
            content_length = len(str(request.json))
            return max(0.001, content_length * 0.00001)
        return 0.01

    # Create custom configuration
    budget_options = BudgetMiddlewareOptions(
        enable_budget_monitoring=True,
        enable_throttling=True,
        enable_alerting=True,
        exclude_paths=["/health", "/metrics"],
        cache_ttl_seconds=30,
        fail_open=True,
        custom_user_extractor=extract_user_id,
        custom_operation_extractor=extract_operation,
        custom_cost_extractor=estimate_cost,
    )

    config = MiddlewareConfig(
        framework=FrameworkType.GENERIC,
        budget_options=budget_options,
        log_level="DEBUG",
    )

    middleware = create_budget_middleware(config)

    # Test with different requests
    requests = [
        {"path": "/api/chat", "headers": {"X-User-ID": "user123"}},
        {"path": "/health", "headers": {}},  # Should be excluded
        {"path": "/api/embedding", "headers": {"X-User-ID": "user456"}},
    ]

    for req_data in requests:

        class MockRequest:
            def __init__(self, path, headers):
                self.path = path
                self.method = "POST"
                self.headers = headers
                self.json = {"content": "test message"}

        request = MockRequest(req_data["path"], req_data["headers"])

        with contextlib.suppress(Exception):
            middleware.process_request(request)


def demo_fastapi_integration():
    """Demonstrate FastAPI integration."""

    try:
        # Create FastAPI middleware
        create_fastapi_budget_middleware()

        # Show how it would be used

    except Exception:
        pass


def demo_flask_integration():
    """Demonstrate Flask integration."""

    try:
        # Create Flask middleware
        create_flask_budget_middleware()

        # Show how it would be used

    except Exception:
        pass


def demo_environment_configuration():
    """Demonstrate environment-based configuration."""

    # Set some environment variables for demo
    env_vars = {
        "LEADFACTORY_ENABLE_BUDGET_MONITORING": "true",
        "LEADFACTORY_ENABLE_THROTTLING": "true",
        "LEADFACTORY_EXCLUDE_PATHS": "/health,/metrics,/status",
        "LEADFACTORY_CACHE_TTL_SECONDS": "120",
        "LEADFACTORY_FAIL_OPEN": "true",
        "LEADFACTORY_LOG_LEVEL": "INFO",
    }

    # Temporarily set environment variables
    original_env = {}
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Create middleware that loads from environment
        config = MiddlewareConfig.from_env()
        create_budget_middleware(config)

        for key, value in env_vars.items():
            pass

        # Show the loaded configuration

    except Exception:
        pass

    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def main():
    """Run all middleware demos."""

    try:
        demo_basic_middleware()
        demo_custom_configuration()
        demo_fastapi_integration()
        demo_flask_integration()
        demo_environment_configuration()

    except Exception:
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
