"""
Input validation middleware for API endpoints.

Provides validation decorators and functions to ensure API security.
"""

import re
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from flask import abort, jsonify, request

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_integer(
    value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None
) -> bool:
    """Validate integer value with optional range."""
    try:
        int_val = int(value)
        if min_val is not None and int_val < min_val:
            return False
        if max_val is not None and int_val > max_val:
            return False
        return True
    except (TypeError, ValueError):
        return False


def validate_string(
    value: Any, max_length: int = 1000, pattern: Optional[str] = None
) -> bool:
    """Validate string value with optional pattern."""
    if not isinstance(value, str):
        return False
    if len(value) > max_length:
        return False
    if pattern and not re.match(pattern, value):
        return False
    return True


def sanitize_string(value: str) -> str:
    """Sanitize string to prevent SQL injection and XSS."""
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>\'";`]', "", value)
    # Limit length
    return sanitized[:1000]


def validate_log_type(log_type: str) -> bool:
    """Validate log type against allowed values."""
    allowed_types = {"html", "llm", "raw_html", "enrichment", "email", "scoring"}
    return log_type in allowed_types


def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate date range format and logic."""
    try:
        from datetime import datetime

        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        return start <= end
    except (ValueError, TypeError):
        return False


def validate_request_args(validations: Dict[str, Dict[str, Any]]) -> Callable:
    """
    Decorator to validate request arguments.

    Args:
        validations: Dictionary mapping parameter names to validation rules

    Example:
        @validate_request_args({
            'business_id': {'type': 'int', 'min': 1},
            'log_type': {'type': 'string', 'validator': validate_log_type},
            'search': {'type': 'string', 'max_length': 100}
        })
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Validate each parameter
            for param, rules in validations.items():
                value = (
                    request.args.get(param) or request.json.get(param)
                    if request.is_json
                    else None
                )

                if value is None and rules.get("required", False):
                    logger.warning(f"Missing required parameter: {param}")
                    return (
                        jsonify({"error": f"Missing required parameter: {param}"}),
                        400,
                    )

                if value is not None:
                    param_type = rules.get("type", "string")

                    if param_type == "int":
                        if not validate_integer(
                            value, rules.get("min"), rules.get("max")
                        ):
                            logger.warning(
                                f"Invalid integer parameter: {param}={value}"
                            )
                            return (
                                jsonify(
                                    {"error": f"Invalid integer value for {param}"}
                                ),
                                400,
                            )

                    elif param_type == "string":
                        max_length = rules.get("max_length", 1000)
                        pattern = rules.get("pattern")
                        if not validate_string(value, max_length, pattern):
                            logger.warning(f"Invalid string parameter: {param}={value}")
                            return (
                                jsonify({"error": f"Invalid string value for {param}"}),
                                400,
                            )

                        # Custom validator
                        if "validator" in rules and not rules["validator"](value):
                            logger.warning(
                                f"Parameter failed validation: {param}={value}"
                            )
                            return jsonify({"error": f"Invalid value for {param}"}), 400

                    elif param_type == "email":
                        if not validate_email(value):
                            logger.warning(f"Invalid email parameter: {param}={value}")
                            return (
                                jsonify({"error": f"Invalid email format for {param}"}),
                                400,
                            )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_json_body(schema: Dict[str, Dict[str, Any]]) -> Callable:
    """
    Decorator to validate JSON request body.

    Args:
        schema: Dictionary mapping field names to validation rules
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400

            data = request.get_json()
            if not data:
                return jsonify({"error": "Empty request body"}), 400

            # Validate each field
            for field, rules in schema.items():
                value = data.get(field)

                if value is None and rules.get("required", False):
                    return jsonify({"error": f"Missing required field: {field}"}), 400

                if value is not None:
                    field_type = rules.get("type", "string")

                    if field_type == "int" and not isinstance(value, int):
                        return (
                            jsonify({"error": f"Field {field} must be an integer"}),
                            400,
                        )

                    if field_type == "string" and not isinstance(value, str):
                        return (
                            jsonify({"error": f"Field {field} must be a string"}),
                            400,
                        )

                    if field_type == "list" and not isinstance(value, list):
                        return jsonify({"error": f"Field {field} must be a list"}), 400

                    if field_type == "dict" and not isinstance(value, dict):
                        return (
                            jsonify({"error": f"Field {field} must be an object"}),
                            400,
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def rate_limit(max_requests: int = 100, window_seconds: int = 60) -> Callable:
    """
    Simple rate limiting decorator.

    Args:
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
    """
    # Simple in-memory rate limiting (use Redis in production)
    request_counts: Dict[str, List[float]] = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from time import time

            # Get client identifier (IP or authenticated user)
            client_id = request.remote_addr or "unknown"
            current_time = time()

            # Initialize or clean old requests
            if client_id not in request_counts:
                request_counts[client_id] = []

            # Remove old requests outside window
            request_counts[client_id] = [
                t
                for t in request_counts[client_id]
                if current_time - t < window_seconds
            ]

            # Check rate limit
            if len(request_counts[client_id]) >= max_requests:
                logger.warning(f"Rate limit exceeded for client: {client_id}")
                return jsonify({"error": "Rate limit exceeded"}), 429

            # Record this request
            request_counts[client_id].append(current_time)

            return func(*args, **kwargs)

        return wrapper

    return decorator
