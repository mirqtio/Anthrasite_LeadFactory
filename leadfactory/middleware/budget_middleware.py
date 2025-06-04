"""
Budget Guard Middleware for web frameworks.

This module provides middleware components that integrate LeadFactory's budget
monitoring, throttling, and cost tracking capabilities with various web frameworks.
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable
from dataclasses import asdict
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from ..cost.budget_alerting import AlertMessage, send_budget_alert
from ..cost.budget_config import BudgetConfiguration
from ..cost.cost_tracking import CostTracker
from ..cost.gpt_usage_tracker import GPTUsageTracker
from ..cost.throttling_service import ThrottlingDecision, ThrottlingService
from .middleware_config import BudgetMiddlewareOptions, FrameworkType, MiddlewareConfig

logger = logging.getLogger(__name__)


class BudgetGuardMiddleware:
    """
    Core budget guard middleware that can be adapted for different frameworks.
    """

    def __init__(self, config: MiddlewareConfig):
        """Initialize the budget guard middleware."""
        self.config = config
        self.budget_config = BudgetConfiguration()
        self.throttling_service = ThrottlingService()
        self.usage_tracker = GPTUsageTracker()
        self.cost_tracker = CostTracker()

        # Decision cache for performance
        self._decision_cache: Dict[str, tuple] = {}
        self._cache_timestamps: Dict[str, float] = {}

        logger.info(f"BudgetGuardMiddleware initialized for {config.framework.value}")

    def _should_process_request(self, path: str, method: str) -> bool:
        """Determine if a request should be processed by the middleware."""
        opts = self.config.budget_options

        # Check excluded methods
        if method.upper() in opts.exclude_methods:
            return False

        # Check excluded paths
        if any(path.startswith(excluded) for excluded in opts.exclude_paths):
            return False

        # Check include-only paths if specified
        if opts.include_only_paths:
            if not any(
                path.startswith(included) for included in opts.include_only_paths
            ):
                return False

        return True

    def _extract_request_info(self, request: Any) -> Dict[str, Any]:
        """Extract relevant information from the request."""
        opts = self.config.budget_options

        # Default extraction
        info = {
            "user_id": None,
            "operation": "api_call",
            "model": "gpt-3.5-turbo",
            "endpoint": "/api/unknown",
            "estimated_cost": 0.01,
        }

        # Use custom extractors if provided
        if opts.custom_user_extractor:
            try:
                info["user_id"] = opts.custom_user_extractor(request)
            except Exception as e:
                logger.warning(f"Custom user extractor failed: {e}")

        if opts.custom_operation_extractor:
            try:
                info["operation"] = opts.custom_operation_extractor(request)
            except Exception as e:
                logger.warning(f"Custom operation extractor failed: {e}")

        if opts.custom_cost_extractor:
            try:
                info["estimated_cost"] = opts.custom_cost_extractor(request)
            except Exception as e:
                logger.warning(f"Custom cost extractor failed: {e}")

        # Framework-specific extraction
        if hasattr(request, "path"):
            info["endpoint"] = request.path
        elif hasattr(request, "url"):
            info["endpoint"] = request.url

        # Extract from headers or query params
        if hasattr(request, "headers"):
            headers = request.headers
            info["user_id"] = info["user_id"] or headers.get("X-User-ID")
            info["model"] = headers.get("X-Model", info["model"])

        if hasattr(request, "args"):  # Flask
            args = request.args
            info["user_id"] = info["user_id"] or args.get("user_id")
            info["model"] = args.get("model", info["model"])
        elif hasattr(request, "query_params"):  # FastAPI
            params = request.query_params
            info["user_id"] = info["user_id"] or params.get("user_id")
            info["model"] = params.get("model", info["model"])

        return info

    def _get_cache_key(self, request_info: Dict[str, Any]) -> str:
        """Generate cache key for throttling decisions."""
        return f"{request_info['user_id']}:{request_info['model']}:{request_info['operation']}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached decision is still valid."""
        if not self.config.budget_options.cache_decisions:
            return False

        if cache_key not in self._cache_timestamps:
            return False

        age = time.time() - self._cache_timestamps[cache_key]
        return age < self.config.budget_options.cache_ttl_seconds

    def _cache_decision(
        self, cache_key: str, decision: ThrottlingDecision, cost: float
    ):
        """Cache a throttling decision."""
        if self.config.budget_options.cache_decisions:
            self._decision_cache[cache_key] = (decision, cost)
            self._cache_timestamps[cache_key] = time.time()

    def _make_throttling_decision(
        self, request_info: Dict[str, Any]
    ) -> tuple[ThrottlingDecision, float]:
        """Make a throttling decision for the request."""
        cache_key = self._get_cache_key(request_info)

        # Check cache first
        if self._is_cache_valid(cache_key):
            return self._decision_cache[cache_key]

        try:
            # Track the request
            if self.config.budget_options.enable_cost_tracking:
                self.cost_tracker.track_request(
                    user_id=request_info["user_id"],
                    operation=request_info["operation"],
                    cost=request_info["estimated_cost"],
                    metadata={
                        "model": request_info["model"],
                        "endpoint": request_info["endpoint"],
                    },
                )

            # Make throttling decision
            decision = ThrottlingDecision.ALLOW
            if self.config.budget_options.enable_throttling:
                decision = self.throttling_service.should_throttle(
                    user_id=request_info["user_id"],
                    model=request_info["model"],
                    operation=request_info["operation"],
                    estimated_cost=request_info["estimated_cost"],
                )

            # Cache the decision
            self._cache_decision(cache_key, decision, request_info["estimated_cost"])

            return decision, request_info["estimated_cost"]

        except Exception as e:
            logger.error(f"Error making throttling decision: {e}")
            if self.config.budget_options.fail_open:
                return ThrottlingDecision.ALLOW, request_info["estimated_cost"]
            else:
                return ThrottlingDecision.REJECT, request_info["estimated_cost"]

    def _send_alert_if_needed(
        self, decision: ThrottlingDecision, request_info: Dict[str, Any]
    ):
        """Send alert if throttling decision warrants it."""
        if not self.config.budget_options.enable_alerting:
            return

        if decision in [ThrottlingDecision.REJECT, ThrottlingDecision.THROTTLE]:
            try:
                alert = AlertMessage(
                    alert_type="throttling_activated",
                    user_id=request_info["user_id"],
                    model=request_info["model"],
                    current_cost=request_info["estimated_cost"],
                    threshold=0.0,  # Will be filled by alert system
                    time_period="current",
                    additional_info={
                        "decision": decision.value,
                        "endpoint": request_info["endpoint"],
                        "operation": request_info["operation"],
                    },
                )

                if self.config.budget_options.async_processing:
                    # Send alert asynchronously
                    asyncio.create_task(self._send_alert_async(alert))
                else:
                    send_budget_alert(alert)

            except Exception as e:
                logger.error(f"Failed to send throttling alert: {e}")

    async def _send_alert_async(self, alert: AlertMessage):
        """Send alert asynchronously."""
        try:
            from ..cost.budget_alerting import send_budget_alert_async

            await send_budget_alert_async(alert)
        except Exception as e:
            logger.error(f"Failed to send async alert: {e}")

    def _create_response(
        self,
        decision: ThrottlingDecision,
        request_info: Dict[str, Any],
        framework: FrameworkType,
    ) -> Any:
        """Create appropriate response based on framework and decision."""
        if decision == ThrottlingDecision.ALLOW:
            return None  # Continue processing

        response_data = {
            "error": "Budget limit exceeded",
            "decision": decision.value,
            "user_id": request_info["user_id"],
            "model": request_info["model"],
            "retry_after": 60 if decision == ThrottlingDecision.THROTTLE else None,
        }

        if framework == FrameworkType.FASTAPI:
            from fastapi import HTTPException

            status_code = 429 if decision == ThrottlingDecision.THROTTLE else 402
            raise HTTPException(status_code=status_code, detail=response_data)

        elif framework == FrameworkType.FLASK:
            from flask import jsonify

            status_code = 429 if decision == ThrottlingDecision.THROTTLE else 402
            response = jsonify(response_data)
            response.status_code = status_code
            return response

        else:
            # Generic response
            return {
                "status_code": 429 if decision == ThrottlingDecision.THROTTLE else 402,
                "body": json.dumps(response_data),
                "headers": {"Content-Type": "application/json"},
            }

    def process_request(self, request: Any) -> Any:
        """Process a request synchronously."""
        # Extract request information
        try:
            path = getattr(request, "path", getattr(request, "url", "/unknown"))
            method = getattr(request, "method", "GET")

            if not self._should_process_request(path, method):
                return None  # Skip processing

            request_info = self._extract_request_info(request)
            decision, cost = self._make_throttling_decision(request_info)

            # Send alert if needed
            self._send_alert_if_needed(decision, request_info)

            # Log the decision
            if self.config.enable_request_logging:
                logger.info(
                    f"Budget decision for {request_info['user_id']}: {decision.value}"
                )

            # Create response if needed
            if decision != ThrottlingDecision.ALLOW:
                return self._create_response(
                    decision, request_info, self.config.framework
                )

            return None  # Allow request to continue

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            if self.config.budget_options.fail_open:
                return None
            else:
                return self._create_response(
                    ThrottlingDecision.REJECT, {}, self.config.framework
                )

    async def process_request_async(self, request: Any) -> Any:
        """Process a request asynchronously."""
        # For now, just call the sync version
        # In a real implementation, you might want to make database calls async
        return self.process_request(request)


# Framework-specific factory functions


def create_budget_middleware(
    config: Optional[MiddlewareConfig] = None,
) -> BudgetGuardMiddleware:
    """Create a generic budget middleware instance."""
    if config is None:
        config = MiddlewareConfig.from_environment()
    return BudgetGuardMiddleware(config)


def create_express_budget_middleware(config: Optional[MiddlewareConfig] = None):
    """Create Express.js compatible middleware."""
    if config is None:
        config = MiddlewareConfig.from_environment()
        config.framework = FrameworkType.EXPRESS

    middleware = BudgetGuardMiddleware(config)

    def express_middleware(req, res, next):
        """Express.js middleware function."""
        try:
            # Create a request-like object
            request_obj = type(
                "Request",
                (),
                {
                    "path": req.get("path", "/"),
                    "method": req.get("method", "GET"),
                    "headers": req.get("headers", {}),
                    "query": req.get("query", {}),
                },
            )()

            result = middleware.process_request(request_obj)

            if result is not None:
                # Request was blocked
                status_code = result.get("status_code", 402)
                body = result.get("body", '{"error": "Budget limit exceeded"}')
                headers = result.get("headers", {})

                res.status(status_code)
                for key, value in headers.items():
                    res.set(key, value)
                res.send(body)
                return

            # Continue to next middleware
            next()

        except Exception as e:
            logger.error(f"Express middleware error: {e}")
            if config.budget_options.fail_open:
                next()
            else:
                res.status(500).send('{"error": "Internal server error"}')

    return express_middleware


def create_fastapi_budget_middleware(config: Optional[MiddlewareConfig] = None):
    """Create FastAPI compatible middleware."""
    if config is None:
        config = MiddlewareConfig.from_environment()
        config.framework = FrameworkType.FASTAPI

    middleware = BudgetGuardMiddleware(config)

    async def fastapi_middleware(request, call_next):
        """FastAPI middleware function."""
        try:
            result = await middleware.process_request_async(request)

            if result is not None:
                # Request was blocked - exception will be raised
                pass

            # Continue processing
            response = await call_next(request)
            return response

        except Exception:
            # FastAPI will handle HTTPException automatically
            raise

    return fastapi_middleware


def create_flask_budget_middleware(config: Optional[MiddlewareConfig] = None):
    """Create Flask compatible middleware."""
    if config is None:
        config = MiddlewareConfig.from_environment()
        config.framework = FrameworkType.FLASK

    middleware = BudgetGuardMiddleware(config)

    def flask_middleware():
        """Flask before_request handler."""
        from flask import request

        try:
            result = middleware.process_request(request)

            if result is not None:
                # Request was blocked
                return result

            # Continue processing
            return None

        except Exception as e:
            logger.error(f"Flask middleware error: {e}")
            if config.budget_options.fail_open:
                return None
            else:
                from flask import jsonify

                response = jsonify({"error": "Internal server error"})
                response.status_code = 500
                return response
