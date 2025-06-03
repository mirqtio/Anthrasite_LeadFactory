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
    print("\n=== Basic Middleware Demo ===")

    # Create basic middleware with default configuration
    middleware = create_budget_middleware()
    print(f"✅ Created middleware: {type(middleware).__name__}")

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
            print("✅ Request allowed by middleware")
        else:
            print(f"❌ Request blocked: {result}")
    except Exception as e:
        print(f"⚠️  Middleware error: {e}")


def demo_custom_configuration():
    """Demonstrate middleware with custom configuration."""
    print("\n=== Custom Configuration Demo ===")

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
    print(f"✅ Created custom middleware: {type(middleware).__name__}")

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

        try:
            result = middleware.process_request(request)
            status = "allowed" if result is None else f"blocked ({result})"
            print(f"  📝 {request.path} -> {status}")
        except Exception as e:
            print(f"  ⚠️  {request.path} -> error: {e}")


def demo_fastapi_integration():
    """Demonstrate FastAPI integration."""
    print("\n=== FastAPI Integration Demo ===")

    try:
        # Create FastAPI middleware
        middleware_func = create_fastapi_budget_middleware()
        print("✅ Created FastAPI middleware function")

        # Show how it would be used
        print("📝 Usage example:")
        print("   from fastapi import FastAPI")
        print("   from leadfactory.middleware import create_fastapi_budget_middleware")
        print("   ")
        print("   app = FastAPI()")
        print("   app.middleware('http')(create_fastapi_budget_middleware())")
        print("   ")
        print("   @app.post('/api/chat')")
        print("   async def chat_endpoint():")
        print("       return {'message': 'Hello from protected endpoint!'}")

    except Exception as e:
        print(f"⚠️  FastAPI demo error: {e}")


def demo_flask_integration():
    """Demonstrate Flask integration."""
    print("\n=== Flask Integration Demo ===")

    try:
        # Create Flask middleware
        middleware_func = create_flask_budget_middleware()
        print("✅ Created Flask middleware function")

        # Show how it would be used
        print("📝 Usage example:")
        print("   from flask import Flask")
        print("   from leadfactory.middleware import create_flask_budget_middleware")
        print("   ")
        print("   app = Flask(__name__)")
        print("   app.before_request(create_flask_budget_middleware())")
        print("   ")
        print("   @app.route('/api/chat', methods=['POST'])")
        print("   def chat_endpoint():")
        print("       return {'message': 'Hello from protected endpoint!'}")

    except Exception as e:
        print(f"⚠️  Flask demo error: {e}")


def demo_environment_configuration():
    """Demonstrate environment-based configuration."""
    print("\n=== Environment Configuration Demo ===")

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
        middleware = create_budget_middleware(config)

        print("✅ Created middleware from environment configuration")
        print("📝 Environment variables used:")
        for key, value in env_vars.items():
            print(f"   {key}={value}")

        # Show the loaded configuration
        print("📝 Loaded configuration:")
        print(f"   Budget monitoring: {config.budget_options.enable_budget_monitoring}")
        print(f"   Throttling: {config.budget_options.enable_throttling}")
        print(f"   Excluded paths: {config.budget_options.exclude_paths}")
        print(f"   Cache TTL: {config.budget_options.cache_ttl_seconds}s")
        print(f"   Fail open: {config.budget_options.fail_open}")
        print(f"   Log level: {config.log_level}")

    except Exception as e:
        print(f"⚠️  Environment config demo error: {e}")

    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


def main():
    """Run all middleware demos."""
    print("🚀 LeadFactory Budget Guard Middleware Demo")
    print("=" * 50)

    try:
        demo_basic_middleware()
        demo_custom_configuration()
        demo_fastapi_integration()
        demo_flask_integration()
        demo_environment_configuration()

        print("\n✅ All demos completed successfully!")
        print("\n📚 For more information, see:")
        print("   - docs/middleware/README.md")
        print("   - leadfactory/middleware/")
        print("   - tests/unit/middleware/")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
