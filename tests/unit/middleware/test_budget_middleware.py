"""
Tests for budget middleware functionality.
"""

import asyncio
import json
from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.cost.throttling_service import ThrottlingDecision
from leadfactory.middleware.budget_middleware import (
    BudgetGuardMiddleware,
    create_budget_middleware,
    create_express_budget_middleware,
    create_fastapi_budget_middleware,
    create_flask_budget_middleware,
)
from leadfactory.middleware.middleware_config import (
    BudgetMiddlewareOptions,
    FrameworkType,
    MiddlewareConfig,
)


@dataclass
class MockRequest:
    """Mock request object for testing."""

    path: str = "/api/test"
    method: str = "POST"
    headers: dict = None
    args: dict = None
    query_params: dict = None
    url: str = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.args is None:
            self.args = {}
        if self.query_params is None:
            self.query_params = {}
        if self.url is None:
            self.url = self.path


class TestBudgetGuardMiddleware:
    """Test BudgetGuardMiddleware class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MiddlewareConfig(
            framework=FrameworkType.GENERIC,
            budget_options=BudgetMiddlewareOptions(
                cache_decisions=False,  # Disable caching for predictable tests
                fail_open=True,
            ),
        )

    @pytest.fixture
    def middleware(self, config):
        """Create middleware instance for testing."""
        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            return BudgetGuardMiddleware(config)

    def test_initialization(self, config):
        """Test middleware initialization."""
        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)

            assert middleware.config == config
            assert middleware._decision_cache == {}
            assert middleware._cache_timestamps == {}

    def test_should_process_request_excluded_paths(self, middleware):
        """Test request filtering for excluded paths."""
        # Excluded paths should not be processed
        assert not middleware._should_process_request("/health", "GET")
        assert not middleware._should_process_request("/metrics", "POST")
        assert not middleware._should_process_request("/status", "GET")

        # Other paths should be processed
        assert middleware._should_process_request("/api/test", "POST")
        assert middleware._should_process_request("/custom", "GET")

    def test_should_process_request_excluded_methods(self, middleware):
        """Test request filtering for excluded methods."""
        # OPTIONS should be excluded by default
        assert not middleware._should_process_request("/api/test", "OPTIONS")

        # Other methods should be processed
        assert middleware._should_process_request("/api/test", "GET")
        assert middleware._should_process_request("/api/test", "POST")
        assert middleware._should_process_request("/api/test", "PUT")

    def test_should_process_request_include_only_paths(self, config):
        """Test request filtering with include-only paths."""
        config.budget_options.include_only_paths = ["/api", "/v1"]

        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)

        # Only included paths should be processed
        assert middleware._should_process_request("/api/test", "GET")
        assert middleware._should_process_request("/v1/users", "POST")

        # Other paths should not be processed
        assert not middleware._should_process_request("/custom", "GET")
        assert not middleware._should_process_request("/other", "POST")

    def test_extract_request_info_basic(self, middleware):
        """Test basic request information extraction."""
        request = MockRequest(
            path="/api/chat",
            method="POST",
            headers={"X-User-ID": "user123", "X-Model": "gpt-4"},
        )

        info = middleware._extract_request_info(request)

        assert info["endpoint"] == "/api/chat"
        assert info["user_id"] == "user123"
        assert info["model"] == "gpt-4"
        assert info["operation"] == "api_call"
        assert info["estimated_cost"] == 0.01

    def test_extract_request_info_flask_style(self, middleware):
        """Test request information extraction for Flask-style requests."""
        request = MockRequest(
            path="/api/chat",
            args={"user_id": "user456", "model": "gpt-3.5-turbo"},
        )

        info = middleware._extract_request_info(request)

        assert info["user_id"] == "user456"
        assert info["model"] == "gpt-3.5-turbo"

    def test_extract_request_info_fastapi_style(self, middleware):
        """Test request information extraction for FastAPI-style requests."""
        request = MockRequest(
            path="/api/chat",
            query_params={"user_id": "user789", "model": "gpt-4"},
        )

        info = middleware._extract_request_info(request)

        assert info["user_id"] == "user789"
        assert info["model"] == "gpt-4"

    def test_extract_request_info_custom_extractors(self, config):
        """Test custom extractor functions."""

        def custom_user_extractor(request):
            return "custom_user"

        def custom_operation_extractor(request):
            return "custom_operation"

        def custom_cost_extractor(request):
            return 0.05

        config.budget_options.custom_user_extractor = custom_user_extractor
        config.budget_options.custom_operation_extractor = custom_operation_extractor
        config.budget_options.custom_cost_extractor = custom_cost_extractor

        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)

        request = MockRequest()
        info = middleware._extract_request_info(request)

        assert info["user_id"] == "custom_user"
        assert info["operation"] == "custom_operation"
        assert info["estimated_cost"] == 0.05

    def test_cache_functionality(self, config):
        """Test decision caching functionality."""
        config.budget_options.cache_decisions = True
        config.budget_options.cache_ttl_seconds = 60

        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)

        cache_key = "user123:gpt-4:api_call"
        decision = ThrottlingDecision.ALLOW
        cost = 0.01

        # Cache should be empty initially
        assert not middleware._is_cache_valid(cache_key)

        # Cache a decision
        middleware._cache_decision(cache_key, decision, cost)

        # Cache should now be valid
        assert middleware._is_cache_valid(cache_key)
        assert middleware._decision_cache[cache_key] == (decision, cost)

    @patch("time.time")
    def test_cache_expiry(self, mock_time, config):
        """Test cache expiry functionality."""
        config.budget_options.cache_decisions = True
        config.budget_options.cache_ttl_seconds = 60

        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch("leadfactory.middleware.budget_middleware.ThrottlingService"),
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)

        cache_key = "user123:gpt-4:api_call"

        # Set initial time
        mock_time.return_value = 1000
        middleware._cache_decision(cache_key, ThrottlingDecision.ALLOW, 0.01)

        # Cache should be valid
        assert middleware._is_cache_valid(cache_key)

        # Move time forward beyond TTL
        mock_time.return_value = 1100

        # Cache should now be expired
        assert not middleware._is_cache_valid(cache_key)

    def test_make_throttling_decision_allow(self, middleware):
        """Test throttling decision when request is allowed."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.ALLOW
        )

        request_info = {
            "user_id": "user123",
            "model": "gpt-4",
            "operation": "api_call",
            "estimated_cost": 0.01,
            "endpoint": "/api/chat",
        }

        decision, cost = middleware._make_throttling_decision(request_info)

        assert decision == ThrottlingDecision.ALLOW
        assert cost == 0.01
        middleware.cost_tracker.track_request.assert_called_once()
        middleware.throttling_service.should_throttle.assert_called_once()

    def test_make_throttling_decision_throttle(self, middleware):
        """Test throttling decision when request should be throttled."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.THROTTLE
        )

        request_info = {
            "user_id": "user123",
            "model": "gpt-4",
            "operation": "api_call",
            "estimated_cost": 0.01,
            "endpoint": "/api/chat",
        }

        decision, cost = middleware._make_throttling_decision(request_info)

        assert decision == ThrottlingDecision.THROTTLE
        assert cost == 0.01

    def test_make_throttling_decision_error_fail_open(self, middleware):
        """Test throttling decision when error occurs and fail_open is True."""
        middleware.throttling_service.should_throttle.side_effect = Exception(
            "Test error"
        )

        request_info = {
            "user_id": "user123",
            "model": "gpt-4",
            "operation": "api_call",
            "estimated_cost": 0.01,
            "endpoint": "/api/chat",
        }

        decision, cost = middleware._make_throttling_decision(request_info)

        assert decision == ThrottlingDecision.ALLOW
        assert cost == 0.01

    def test_make_throttling_decision_error_fail_closed(self, config):
        """Test throttling decision when error occurs and fail_open is False."""
        config.budget_options.fail_open = False

        with (
            patch("leadfactory.middleware.budget_middleware.BudgetConfig"),
            patch(
                "leadfactory.middleware.budget_middleware.ThrottlingService"
            ) as mock_throttling,
            patch("leadfactory.middleware.budget_middleware.GPTUsageTracker"),
            patch("leadfactory.middleware.budget_middleware.CostTracker"),
        ):
            middleware = BudgetGuardMiddleware(config)
            middleware.throttling_service.should_throttle.side_effect = Exception(
                "Test error"
            )

            request_info = {
                "user_id": "user123",
                "model": "gpt-4",
                "operation": "api_call",
                "estimated_cost": 0.01,
                "endpoint": "/api/chat",
            }

            decision, cost = middleware._make_throttling_decision(request_info)

            assert decision == ThrottlingDecision.REJECT
            assert cost == 0.01

    def test_process_request_skip_excluded(self, middleware):
        """Test processing request that should be skipped."""
        request = MockRequest(path="/health", method="GET")

        result = middleware.process_request(request)

        assert result is None
        middleware.throttling_service.should_throttle.assert_not_called()

    def test_process_request_allow(self, middleware):
        """Test processing request that is allowed."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.ALLOW
        )

        request = MockRequest(
            path="/api/chat",
            method="POST",
            headers={"X-User-ID": "user123"},
        )

        result = middleware.process_request(request)

        assert result is None
        middleware.throttling_service.should_throttle.assert_called_once()

    def test_process_request_throttle_generic(self, middleware):
        """Test processing request that should be throttled (generic framework)."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.THROTTLE
        )

        request = MockRequest(
            path="/api/chat",
            method="POST",
            headers={"X-User-ID": "user123"},
        )

        result = middleware.process_request(request)

        assert result is not None
        assert result["status_code"] == 429
        assert "Budget limit exceeded" in result["body"]

    def test_process_request_reject_generic(self, middleware):
        """Test processing request that should be rejected (generic framework)."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.REJECT
        )

        request = MockRequest(
            path="/api/chat",
            method="POST",
            headers={"X-User-ID": "user123"},
        )

        result = middleware.process_request(request)

        assert result is not None
        assert result["status_code"] == 402
        assert "Budget limit exceeded" in result["body"]

    @pytest.mark.asyncio
    async def test_process_request_async(self, middleware):
        """Test async request processing."""
        middleware.throttling_service.should_throttle.return_value = (
            ThrottlingDecision.ALLOW
        )

        request = MockRequest(
            path="/api/chat",
            method="POST",
            headers={"X-User-ID": "user123"},
        )

        result = await middleware.process_request_async(request)

        assert result is None
        middleware.throttling_service.should_throttle.assert_called_once()


class TestFactoryFunctions:
    """Test middleware factory functions."""

    @patch("leadfactory.middleware.budget_middleware.BudgetGuardMiddleware")
    def test_create_budget_middleware_default_config(self, mock_middleware):
        """Test creating middleware with default configuration."""
        with patch(
            "leadfactory.middleware.budget_middleware.MiddlewareConfig"
        ) as mock_config:
            create_budget_middleware()

            mock_config.from_environment.assert_called_once()
            mock_middleware.assert_called_once()

    @patch("leadfactory.middleware.budget_middleware.BudgetGuardMiddleware")
    def test_create_budget_middleware_custom_config(self, mock_middleware):
        """Test creating middleware with custom configuration."""
        config = MiddlewareConfig()
        create_budget_middleware(config)

        mock_middleware.assert_called_once_with(config)

    def test_create_express_budget_middleware(self):
        """Test creating Express.js middleware."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware:
            middleware_func = create_express_budget_middleware()

            assert callable(middleware_func)
            mock_middleware.assert_called_once()

    def test_create_fastapi_budget_middleware(self):
        """Test creating FastAPI middleware."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware:
            middleware_func = create_fastapi_budget_middleware()

            assert callable(middleware_func)
            mock_middleware.assert_called_once()

    def test_create_flask_budget_middleware(self):
        """Test creating Flask middleware."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware:
            middleware_func = create_flask_budget_middleware()

            assert callable(middleware_func)
            mock_middleware.assert_called_once()


class TestFrameworkSpecificMiddleware:
    """Test framework-specific middleware implementations."""

    def test_express_middleware_allow(self):
        """Test Express middleware when request is allowed."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware_class:
            mock_middleware = Mock()
            mock_middleware.process_request.return_value = None
            mock_middleware_class.return_value = mock_middleware

            middleware_func = create_express_budget_middleware()

            # Mock Express request/response/next
            req = {
                "path": "/api/test",
                "method": "POST",
                "headers": {"X-User-ID": "user123"},
                "query": {},
            }
            res = Mock()
            next_func = Mock()

            middleware_func(req, res, next_func)

            next_func.assert_called_once()
            res.status.assert_not_called()

    def test_express_middleware_block(self):
        """Test Express middleware when request is blocked."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware_class:
            mock_middleware = Mock()
            mock_middleware.process_request.return_value = {
                "status_code": 429,
                "body": '{"error": "Budget limit exceeded"}',
                "headers": {"Content-Type": "application/json"},
            }
            mock_middleware_class.return_value = mock_middleware

            middleware_func = create_express_budget_middleware()

            # Mock Express request/response/next
            req = {
                "path": "/api/test",
                "method": "POST",
                "headers": {"X-User-ID": "user123"},
                "query": {},
            }
            res = Mock()
            next_func = Mock()

            middleware_func(req, res, next_func)

            res.status.assert_called_once_with(429)
            res.set.assert_called_once_with("Content-Type", "application/json")
            res.send.assert_called_once_with('{"error": "Budget limit exceeded"}')
            next_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_fastapi_middleware_allow(self):
        """Test FastAPI middleware when request is allowed."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware_class:
            mock_middleware = Mock()
            mock_middleware.process_request_async.return_value = None
            mock_middleware_class.return_value = mock_middleware

            middleware_func = create_fastapi_budget_middleware()

            # Mock FastAPI request and call_next
            request = Mock()
            call_next = Mock()
            call_next.return_value = Mock()  # Mock response

            result = await middleware_func(request, call_next)

            call_next.assert_called_once_with(request)
            assert result is not None

    def test_flask_middleware_allow(self):
        """Test Flask middleware when request is allowed."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware_class:
            mock_middleware = Mock()
            mock_middleware.process_request.return_value = None
            mock_middleware_class.return_value = mock_middleware

            middleware_func = create_flask_budget_middleware()

            with patch(
                "leadfactory.middleware.budget_middleware.request"
            ) as mock_request:
                result = middleware_func()

                assert result is None
                mock_middleware.process_request.assert_called_once_with(mock_request)

    def test_flask_middleware_block(self):
        """Test Flask middleware when request is blocked."""
        with patch(
            "leadfactory.middleware.budget_middleware.BudgetGuardMiddleware"
        ) as mock_middleware_class:
            mock_middleware = Mock()
            mock_response = Mock()
            mock_response.status_code = 429
            mock_middleware.process_request.return_value = mock_response
            mock_middleware_class.return_value = mock_middleware

            middleware_func = create_flask_budget_middleware()

            with patch(
                "leadfactory.middleware.budget_middleware.request"
            ) as mock_request:
                result = middleware_func()

                assert result == mock_response
                mock_middleware.process_request.assert_called_once_with(mock_request)
