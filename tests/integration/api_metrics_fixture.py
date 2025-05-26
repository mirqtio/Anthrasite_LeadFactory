"""
Fixtures for API metrics collection and validation during tests.

This module provides fixtures for tracking API metrics during integration tests,
allowing validation of API call patterns and performance metrics.
"""

import pytest
import time
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from functools import wraps

# Import prometheus metrics if available
try:
    from leadfactory.utils.metrics import (
        API_LATENCY, COST_COUNTER,
        METRICS_AVAILABLE
    )
except ImportError:
    METRICS_AVAILABLE = False

from tests.integration.api_test_config import use_real_apis, should_test_api


@dataclass
class APIMetric:
    """Class to store metrics for an API call."""
    api: str
    endpoint: str
    request_time: float
    status_code: int
    cost: Optional[float] = None
    token_count: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON for logging."""
        return json.dumps(asdict(self))


class APIMetricsLogger:
    """Class to log and track API metrics during tests."""

    def __init__(self, enabled: bool = True):
        """Initialize the logger."""
        self.enabled = enabled
        self.metrics: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("api_metrics")

        # Set up metrics storage directory
        self.metrics_dir = Path(os.environ.get('METRICS_DIR', 'metrics'))
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # Configure log file handler
        self.log_to_file = os.environ.get("LEADFACTORY_LOG_METRICS_TO_FILE", "true").lower() in ("true", "1", "yes")
        if self.log_to_file:
            self.metrics_file = self.metrics_dir / f"api_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            file_handler = logging.FileHandler(self.metrics_file)
            file_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)

    def log_api_call(self,
                     api: str,
                     endpoint: str,
                     request_time: float,
                     status_code: int,
                     cost: Optional[float] = None,
                     token_count: Optional[int] = None) -> None:
        """
        Log an API call with metrics.

        Args:
            api: Name of the API (e.g., 'yelp', 'google', 'openai')
            endpoint: Specific endpoint or operation called
            request_time: Time taken for the request in seconds
            status_code: HTTP status code returned
            cost: Optional cost associated with the API call
            token_count: Optional token count for token-based APIs
        """
        if not self.enabled:
            return

        metric = APIMetric(
            api=api,
            endpoint=endpoint,
            request_time=request_time,
            status_code=status_code,
            cost=cost,
            token_count=token_count
        )

        metric_dict = metric.to_dict()
        self.metrics.append(metric_dict)

        # Log to file if enabled
        if self.log_to_file:
            self.logger.info(json.dumps(metric_dict))
        else:
            self.logger.info(f"API Call: {metric.to_json()}")

        # Update Prometheus metrics if available
        if METRICS_AVAILABLE:
            # Update latency histogram
            API_LATENCY.labels(api_name=api, endpoint=endpoint).observe(request_time)

            # Update cost counter if cost is provided
            if cost is not None and cost > 0:
                COST_COUNTER.labels(api_name=api).inc(cost)

    def get_metrics_for_api(self, api: str) -> List[Dict[str, Any]]:
        """Get all metrics for a specific API."""
        return [m for m in self.metrics if m["api"] == api]

    def get_metrics_for_endpoint(self, api: str, endpoint: str) -> List[Dict[str, Any]]:
        """Get all metrics for a specific API endpoint."""
        return [m for m in self.metrics
                if m["api"] == api and m["endpoint"] == endpoint]

    def get_total_cost(self, api: Optional[str] = None) -> float:
        """Get total cost across all APIs or for a specific API."""
        metrics = self.metrics
        if api:
            metrics = self.get_metrics_for_api(api)

        return sum(m.get("cost", 0) or 0 for m in metrics)

    def get_total_tokens(self, api: Optional[str] = None) -> int:
        """Get total token count across all APIs or for a specific API."""
        metrics = self.metrics
        if api:
            metrics = self.get_metrics_for_api(api)

        return sum(m.get("token_count", 0) or 0 for m in metrics)

    def get_average_request_time(self, api: Optional[str] = None) -> float:
        """Get average request time across all APIs or for a specific API."""
        metrics = self.metrics
        if api:
            metrics = self.get_metrics_for_api(api)

        if not metrics:
            return 0.0

        return sum(m.get("request_time", 0) for m in metrics) / len(metrics)

    def clear(self) -> None:
        """Clear all collected metrics."""
        self.metrics = []

    def summary(self) -> Dict[str, Any]:
        """Generate a summary of all metrics."""
        apis = {m["api"] for m in self.metrics}

        return {
            "total_calls": len(self.metrics),
            "total_cost": self.get_total_cost(),
            "total_tokens": self.get_total_tokens(),
            "average_request_time": self.get_average_request_time(),
            "apis": {
                api: {
                    "calls": len(self.get_metrics_for_api(api)),
                    "cost": self.get_total_cost(api),
                    "tokens": self.get_total_tokens(api),
                    "average_request_time": self.get_average_request_time(api)
                } for api in apis
            }
        }


@pytest.fixture
def api_metrics_logger():
    """Fixture providing an API metrics logger for tests."""
    # Check if metrics logging is enabled in environment
    import os
    enabled = os.environ.get("LEADFACTORY_LOG_API_METRICS", "true").lower() in ("true", "1", "yes")

    logger = APIMetricsLogger(enabled=enabled)
    yield logger

    # Print metrics summary after test if enabled
    if enabled and logger.metrics:
        print("\nAPI Metrics Summary:")
        summary = logger.summary()
        print(f"Total API calls: {summary['total_calls']}")
        print(f"Total cost: ${summary['total_cost']:.6f}")
        if summary['total_tokens'] > 0:
            print(f"Total tokens: {summary['total_tokens']}")
        print(f"Average request time: {summary['average_request_time']*1000:.2f}ms")

        for api, api_stats in summary['apis'].items():
            print(f"\n{api.upper()} API:")
            print(f"  Calls: {api_stats['calls']}")
            if api_stats['cost'] > 0:
                print(f"  Cost: ${api_stats['cost']:.6f}")
            if api_stats['tokens'] > 0:
                print(f"  Tokens: {api_stats['tokens']}")
            print(f"  Avg request time: {api_stats['average_request_time']*1000:.2f}ms")


def calculate_openai_cost(model: str, token_count: int) -> float:
    """Calculate the cost of an OpenAI API call based on the model and token count.

    Args:
        model: OpenAI model name (e.g., 'gpt-3.5-turbo', 'gpt-4')
        token_count: Number of tokens used

    Returns:
        Estimated cost in USD
    """
    # Pricing as of 2025 (simplified)
    model_prices = {
        # GPT-3.5 Turbo
        'gpt-3.5-turbo': {
            'input': 0.0015,   # $0.0015 per 1K input tokens
            'output': 0.002    # $0.002 per 1K output tokens
        },
        # GPT-4
        'gpt-4': {
            'input': 0.03,     # $0.03 per 1K input tokens
            'output': 0.06     # $0.06 per 1K output tokens
        },
        'gpt-4-turbo': {
            'input': 0.01,     # $0.01 per 1K input tokens
            'output': 0.03     # $0.03 per 1K output tokens
        },
        # Default fallback
        'default': {
            'input': 0.01,
            'output': 0.03
        }
    }

    # Get pricing for the model, use default if not found
    pricing = model_prices.get(model.lower(), model_prices['default'])

    # Calculate average price per token (simplified approach)
    avg_price_per_token = (pricing['input'] + pricing['output']) / 2 / 1000

    # Calculate cost
    return token_count * avg_price_per_token


def api_metric_decorator(api_name: str, endpoint: str = ""):
    """
    Decorator to automatically log API metrics for a function.

    Args:
        api_name: Name of the API
        endpoint: Name of the specific endpoint being called

    Example:
        @api_metric_decorator("yelp", "business_search")
        def search_businesses(api_key, location, term):
            # Function implementation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract metrics_logger if provided
            metrics_logger = kwargs.pop('metrics_logger', None)
            if metrics_logger is None:
                # Look for it in args that might be self or have it as attribute
                for arg in args:
                    if hasattr(arg, 'metrics_logger'):
                        metrics_logger = arg.metrics_logger
                        break

            # If no metrics logger found, just call the function
            if metrics_logger is None:
                return func(*args, **kwargs)

            # Measure execution time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                status_code = getattr(result, 'status_code', 200)

                # Extract cost and token count if available
                cost = None
                token_count = None
                model = None

                # Check different result types to extract metrics
                if hasattr(result, 'usage') and result.usage:
                    # OpenAI style response
                    token_count = getattr(result.usage, 'total_tokens', None)

                    # Try to determine the model used
                    if hasattr(result, 'model'):
                        model = result.model
                    elif api_name == 'openai' and 'model' in kwargs:
                        model = kwargs['model']

                    # Calculate cost based on token count and model
                    if token_count and api_name == 'openai':
                        if model:
                            cost = calculate_openai_cost(model, token_count)
                        else:
                            # Fallback to default pricing if model unknown
                            cost = token_count * 0.00002  # $0.02 per 1K tokens

                # Check for Anthropic Claude API calls
                elif api_name == 'anthropic' and hasattr(result, 'usage'):
                    input_tokens = getattr(result.usage, 'input_tokens', 0)
                    output_tokens = getattr(result.usage, 'output_tokens', 0)
                    token_count = input_tokens + output_tokens

                    # Claude pricing (estimated for 2025)
                    input_cost = input_tokens * 0.000008  # $0.008 per 1K input tokens
                    output_cost = output_tokens * 0.000024  # $0.024 per 1K output tokens
                    cost = input_cost + output_cost

                # Google Vertex AI API (estimated)
                elif api_name == 'google_vertex' and hasattr(result, 'usage_metadata'):
                    token_count = getattr(result.usage_metadata, 'total_token_count', 0)
                    cost = token_count * 0.00001  # Approximate cost

                # Log the API call
                metrics_logger.log_api_call(
                    api=api_name,
                    endpoint=endpoint,
                    request_time=time.time() - start_time,
                    status_code=status_code,
                    cost=cost,
                    token_count=token_count
                )
                return result
            except Exception as e:
                # Log failed API call
                metrics_logger.log_api_call(
                    api=api_name,
                    endpoint=endpoint,
                    request_time=time.time() - start_time,
                    status_code=500,  # Internal error
                )
                raise e
        return wrapper
    return decorator
