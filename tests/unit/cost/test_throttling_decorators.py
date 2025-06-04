"""
Unit tests for the throttling decorators module.
"""

import asyncio
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from leadfactory.cost.throttling_decorators import (
    AsyncThrottlingContext,
    ThrottlingContext,
    ThrottlingError,
    async_openai_throttled,
    async_throttled,
    gpu_throttled,
    openai_throttled,
    screenshot_throttled,
    semrush_throttled,
    throttled,
)
from leadfactory.cost.throttling_service import (
    ThrottlingAction,
    ThrottlingDecision,
    ThrottlingStrategy,
)


class TestThrottlingError(unittest.TestCase):
    """Test the ThrottlingError exception."""

    def test_throttling_error_creation(self):
        """Test creating ThrottlingError."""
        decision = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )
        error = ThrottlingError("Request throttled", decision)

        self.assertEqual(str(error), "Request throttled")
        self.assertEqual(error.decision, decision)


class TestThrottledDecorator(unittest.TestCase):
    """Test the throttled decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.ALLOW
        )
        self.mock_service.record_request_start = Mock()
        self.mock_service.record_request_end = Mock()

        self.patcher = patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        )
        self.mock_get_service = self.patcher.start()
        self.mock_get_service.return_value = self.mock_service

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()

    def test_throttled_decorator_allow(self):
        """Test throttled decorator when request is allowed."""

        @throttled("openai", "gpt-4o", "chat")
        def test_function(x, y):
            return x + y

        result = test_function(1, 2)

        self.assertEqual(result, 3)
        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 0.0, ThrottlingStrategy.ADAPTIVE
        )
        self.mock_service.record_request_start.assert_called_once_with(
            "openai", "gpt-4o", "chat"
        )
        self.mock_service.record_request_end.assert_called_once_with(
            "openai", "gpt-4o", "chat"
        )

    def test_throttled_decorator_with_cost_estimator(self):
        """Test throttled decorator with cost estimator."""

        def cost_estimator(x, y):
            return x * y * 0.01

        @throttled("openai", "gpt-4o", "chat", cost_estimator=cost_estimator)
        def test_function(x, y):
            return x + y

        result = test_function(10, 5)

        self.assertEqual(result, 15)
        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 0.5, ThrottlingStrategy.ADAPTIVE
        )

    def test_throttled_decorator_reject_with_fallback_value(self):
        """Test throttled decorator when request is rejected with fallback value."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        @throttled("openai", "gpt-4o", "chat", fallback_value="fallback")
        def test_function(x, y):
            return x + y

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=False,
        ):
            result = test_function(1, 2)

        self.assertEqual(result, "fallback")
        self.mock_service.record_request_start.assert_not_called()
        self.mock_service.record_request_end.assert_not_called()

    def test_throttled_decorator_reject_with_fallback_function(self):
        """Test throttled decorator when request is rejected with fallback function."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        def fallback_function(x, y):
            return f"fallback: {x + y}"

        @throttled("openai", "gpt-4o", "chat", fallback_function=fallback_function)
        def test_function(x, y):
            return x + y

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=False,
        ):
            result = test_function(1, 2)

        self.assertEqual(result, "fallback: 3")

    def test_throttled_decorator_reject_with_exception(self):
        """Test throttled decorator when request is rejected and should raise exception."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        @throttled("openai", "gpt-4o", "chat", raise_on_throttle=True)
        def test_function(x, y):
            return x + y

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=False,
        ):
            with self.assertRaises(ThrottlingError) as cm:
                test_function(1, 2)

            self.assertIn("Budget exceeded", str(cm.exception))

    def test_throttled_decorator_downgrade(self):
        """Test throttled decorator with model downgrade."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.DOWNGRADE,
            alternative_model="gpt-4o-mini",
            reason="Budget optimization",
        )

        @throttled("openai", "gpt-4o", "chat", auto_downgrade=True)
        def test_function(model=None):
            return f"Using model: {model}"

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=True,
        ):
            result = test_function(model="gpt-4o")

        self.assertEqual(result, "Using model: gpt-4o-mini")
        self.mock_service.record_request_start.assert_called_once_with(
            "openai", "gpt-4o-mini", "chat"
        )
        self.mock_service.record_request_end.assert_called_once_with(
            "openai", "gpt-4o-mini", "chat"
        )

    def test_throttled_decorator_cost_estimator_error(self):
        """Test throttled decorator when cost estimator raises exception."""

        def failing_cost_estimator(x, y):
            raise ValueError("Cost estimation failed")

        @throttled("openai", "gpt-4o", "chat", cost_estimator=failing_cost_estimator)
        def test_function(x, y):
            return x + y

        # Should not raise exception, should use 0.0 cost
        result = test_function(1, 2)

        self.assertEqual(result, 3)
        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 0.0, ThrottlingStrategy.ADAPTIVE
        )

    def test_throttled_decorator_function_exception(self):
        """Test throttled decorator when decorated function raises exception."""

        @throttled("openai", "gpt-4o", "chat")
        def test_function(x, y):
            raise ValueError("Function error")

        with self.assertRaises(ValueError):
            test_function(1, 2)

        # Should still record request end even on exception
        self.mock_service.record_request_start.assert_called_once()
        self.mock_service.record_request_end.assert_called_once()


class TestAsyncThrottledDecorator(unittest.TestCase):
    """Test the async_throttled decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.ALLOW
        )
        self.mock_service.record_request_start = Mock()
        self.mock_service.record_request_end = Mock()

        self.patcher = patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        )
        self.mock_get_service = self.patcher.start()
        self.mock_get_service.return_value = self.mock_service

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()

    def test_async_throttled_decorator_allow(self):
        """Test async throttled decorator when request is allowed."""

        @async_throttled("openai", "gpt-4o", "chat")
        async def test_function(x, y):
            return x + y

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=True,
            ):
                result = await test_function(1, 2)
            return result

        result = asyncio.run(run_test())

        self.assertEqual(result, 3)
        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 0.0, ThrottlingStrategy.ADAPTIVE
        )

    def test_async_throttled_decorator_reject_with_async_fallback(self):
        """Test async throttled decorator with async fallback function."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        async def async_fallback_function(x, y):
            return f"async fallback: {x + y}"

        @async_throttled(
            "openai", "gpt-4o", "chat", fallback_function=async_fallback_function
        )
        async def test_function(x, y):
            return x + y

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=False,
            ):
                result = await test_function(1, 2)
            return result

        result = asyncio.run(run_test())

        self.assertEqual(result, "async fallback: 3")

    def test_async_throttled_decorator_reject_with_sync_fallback(self):
        """Test async throttled decorator with sync fallback function."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        def sync_fallback_function(x, y):
            return f"sync fallback: {x + y}"

        @async_throttled(
            "openai", "gpt-4o", "chat", fallback_function=sync_fallback_function
        )
        async def test_function(x, y):
            return x + y

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=False,
            ):
                result = await test_function(1, 2)
            return result

        result = asyncio.run(run_test())

        self.assertEqual(result, "sync fallback: 3")


class TestSpecializedDecorators(unittest.TestCase):
    """Test specialized decorators for different services."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.ALLOW
        )
        self.mock_service.record_request_start = Mock()
        self.mock_service.record_request_end = Mock()

        self.patcher = patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        )
        self.mock_get_service = self.patcher.start()
        self.mock_get_service.return_value = self.mock_service

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()

    def test_openai_throttled_decorator(self):
        """Test OpenAI specialized decorator."""

        @openai_throttled(model="gpt-4o", endpoint="chat")
        def test_openai_function(prompt="Hello", max_tokens=100):
            return f"Response to: {prompt}"

        result = test_openai_function(prompt="Test prompt", max_tokens=150)

        self.assertEqual(result, "Response to: Test prompt")
        # Should have called with estimated cost based on tokens
        args, kwargs = self.mock_service.should_throttle.call_args
        self.assertEqual(args[:3], ("openai", "gpt-4o", "chat"))
        self.assertGreater(args[3], 0)  # Should have estimated cost > 0

    def test_openai_throttled_with_messages(self):
        """Test OpenAI decorator with messages format."""

        @openai_throttled(model="gpt-4o", endpoint="chat")
        def test_openai_function(messages=None):
            return "Response"

        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = test_openai_function(messages=messages)

        self.assertEqual(result, "Response")
        # Should have estimated cost based on message content
        args, kwargs = self.mock_service.should_throttle.call_args
        self.assertGreater(args[3], 0)

    def test_async_openai_throttled_decorator(self):
        """Test async OpenAI specialized decorator."""

        @async_openai_throttled(model="gpt-4o", endpoint="chat")
        async def test_async_openai_function(prompt="Hello"):
            return f"Async response to: {prompt}"

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=True,
            ):
                result = await test_async_openai_function(prompt="Test")
            return result

        result = asyncio.run(run_test())

        self.assertEqual(result, "Async response to: Test")

    def test_semrush_throttled_decorator(self):
        """Test SEMrush specialized decorator."""

        @semrush_throttled(operation="domain-overview")
        def test_semrush_function(domain="example.com"):
            return f"SEMrush data for: {domain}"

        result = test_semrush_function(domain="test.com")

        self.assertEqual(result, "SEMrush data for: test.com")
        self.mock_service.should_throttle.assert_called_once_with(
            "semrush", "domain-overview", "api", 0.10, ThrottlingStrategy.ADAPTIVE
        )

    def test_screenshot_throttled_decorator(self):
        """Test screenshot specialized decorator."""

        @screenshot_throttled()
        def test_screenshot_function(width=1920, height=1080):
            return f"Screenshot {width}x{height}"

        result = test_screenshot_function(width=2560, height=1440)

        self.assertEqual(result, "Screenshot 2560x1440")
        # Should have estimated cost based on dimensions
        args, kwargs = self.mock_service.should_throttle.call_args
        self.assertEqual(args[:3], ("screenshot", "browser", "capture"))
        self.assertGreater(args[3], 0.01)  # Should be higher than base cost

    def test_gpu_throttled_decorator(self):
        """Test GPU specialized decorator."""

        @gpu_throttled(gpu_type="A100")
        def test_gpu_function(duration_hours=2.0):
            return f"GPU computation for {duration_hours} hours"

        result = test_gpu_function(duration_hours=1.5)

        self.assertEqual(result, "GPU computation for 1.5 hours")
        # Should have estimated cost based on duration and GPU type
        args, kwargs = self.mock_service.should_throttle.call_args
        self.assertEqual(args[:3], ("gpu", "A100", "compute"))
        self.assertEqual(args[3], 2.5 * 1.5)  # A100 cost * duration


class TestThrottlingContext(unittest.TestCase):
    """Test the ThrottlingContext context manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.ALLOW
        )
        self.mock_service.record_request_start = Mock()
        self.mock_service.record_request_end = Mock()

        self.patcher = patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        )
        self.mock_get_service = self.patcher.start()
        self.mock_get_service.return_value = self.mock_service

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()

    def test_throttling_context_allow(self):
        """Test throttling context when request is allowed."""
        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=True,
        ):
            with ThrottlingContext("openai", "gpt-4o", "chat", 5.0) as decision:
                self.assertEqual(decision.action, ThrottlingAction.ALLOW)

        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 5.0, ThrottlingStrategy.ADAPTIVE
        )
        self.mock_service.record_request_start.assert_called_once()
        self.mock_service.record_request_end.assert_called_once()

    def test_throttling_context_reject(self):
        """Test throttling context when request is rejected."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=False,
        ):
            with self.assertRaises(ThrottlingError):
                with ThrottlingContext("openai", "gpt-4o", "chat", 5.0):
                    pass

        self.mock_service.record_request_start.assert_not_called()
        self.mock_service.record_request_end.assert_not_called()

    def test_throttling_context_no_raise(self):
        """Test throttling context when not raising on throttle."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=False,
        ):
            with ThrottlingContext(
                "openai", "gpt-4o", "chat", 5.0, raise_on_throttle=False
            ) as decision:
                self.assertEqual(decision.action, ThrottlingAction.REJECT)

        self.mock_service.record_request_end.assert_not_called()

    def test_throttling_context_exception_in_block(self):
        """Test throttling context when exception occurs in block."""
        with patch(
            "leadfactory.cost.throttling_decorators.apply_throttling_decision",
            return_value=True,
        ):
            with self.assertRaises(ValueError):
                with ThrottlingContext("openai", "gpt-4o", "chat", 5.0):
                    raise ValueError("Test error")

        # Should still record request end
        self.mock_service.record_request_start.assert_called_once()
        self.mock_service.record_request_end.assert_called_once()


class TestAsyncThrottlingContext(unittest.TestCase):
    """Test the AsyncThrottlingContext context manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = Mock()
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.ALLOW
        )
        self.mock_service.record_request_start = Mock()
        self.mock_service.record_request_end = Mock()

        self.patcher = patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        )
        self.mock_get_service = self.patcher.start()
        self.mock_get_service.return_value = self.mock_service

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()

    def test_async_throttling_context_allow(self):
        """Test async throttling context when request is allowed."""

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=True,
            ):
                async with AsyncThrottlingContext(
                    "openai", "gpt-4o", "chat", 5.0
                ) as decision:
                    self.assertEqual(decision.action, ThrottlingAction.ALLOW)

        asyncio.run(run_test())

        self.mock_service.should_throttle.assert_called_once_with(
            "openai", "gpt-4o", "chat", 5.0, ThrottlingStrategy.ADAPTIVE
        )
        self.mock_service.record_request_start.assert_called_once()
        self.mock_service.record_request_end.assert_called_once()

    def test_async_throttling_context_reject(self):
        """Test async throttling context when request is rejected."""
        self.mock_service.should_throttle.return_value = ThrottlingDecision(
            action=ThrottlingAction.REJECT, reason="Budget exceeded"
        )

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=False,
            ):
                with self.assertRaises(ThrottlingError):
                    async with AsyncThrottlingContext("openai", "gpt-4o", "chat", 5.0):
                        pass

        asyncio.run(run_test())

        self.mock_service.record_request_start.assert_not_called()
        self.mock_service.record_request_end.assert_not_called()

    def test_async_throttling_context_exception_in_block(self):
        """Test async throttling context when exception occurs in block."""

        async def run_test():
            with patch(
                "leadfactory.cost.throttling_decorators.apply_throttling_decision_async",
                return_value=True,
            ):
                with self.assertRaises(ValueError):
                    async with AsyncThrottlingContext("openai", "gpt-4o", "chat", 5.0):
                        raise ValueError("Test error")

        asyncio.run(run_test())

        # Should still record request end
        self.mock_service.record_request_start.assert_called_once()
        self.mock_service.record_request_end.assert_called_once()


class TestCostEstimators(unittest.TestCase):
    """Test cost estimation logic in specialized decorators."""

    def test_openai_cost_estimator_with_tokens(self):
        """Test OpenAI cost estimator with explicit token count."""
        from leadfactory.cost.throttling_decorators import openai_throttled

        # Extract the cost estimator function
        decorator_func = openai_throttled(model="gpt-4o")

        # Get the actual decorator
        def dummy_func(**kwargs):
            return "test"

        decorated = decorator_func(dummy_func)

        # The cost estimator is embedded in the decorator, so we test indirectly
        # by checking that different inputs produce different estimated costs
        with patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        ) as mock_get_service:
            mock_service = Mock()
            mock_service.should_throttle.return_value = ThrottlingDecision(
                action=ThrottlingAction.ALLOW
            )
            mock_service.record_request_start = Mock()
            mock_service.record_request_end = Mock()
            mock_get_service.return_value = mock_service

            # Test with different token counts
            decorated(max_tokens=100)
            cost_100 = mock_service.should_throttle.call_args[0][3]

            mock_service.reset_mock()
            decorated(max_tokens=200)
            cost_200 = mock_service.should_throttle.call_args[0][3]

            self.assertGreater(cost_200, cost_100)

    def test_semrush_cost_estimator_different_operations(self):
        """Test SEMrush cost estimator for different operations."""
        from leadfactory.cost.throttling_decorators import semrush_throttled

        with patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        ) as mock_get_service:
            mock_service = Mock()
            mock_service.should_throttle.return_value = ThrottlingDecision(
                action=ThrottlingAction.ALLOW
            )
            mock_service.record_request_start = Mock()
            mock_service.record_request_end = Mock()
            mock_get_service.return_value = mock_service

            # Test domain-overview operation
            @semrush_throttled(operation="domain-overview")
            def test_func():
                return "test"

            test_func()
            overview_cost = mock_service.should_throttle.call_args[0][3]
            self.assertEqual(overview_cost, 0.10)

            # Test domain-organic operation
            mock_service.reset_mock()

            @semrush_throttled(operation="domain-organic")
            def test_func2():
                return "test"

            test_func2()
            organic_cost = mock_service.should_throttle.call_args[0][3]
            self.assertEqual(organic_cost, 0.15)

    def test_gpu_cost_estimator_different_types(self):
        """Test GPU cost estimator for different GPU types and durations."""
        from leadfactory.cost.throttling_decorators import gpu_throttled

        with patch(
            "leadfactory.cost.throttling_decorators.get_throttling_service"
        ) as mock_get_service:
            mock_service = Mock()
            mock_service.should_throttle.return_value = ThrottlingDecision(
                action=ThrottlingAction.ALLOW
            )
            mock_service.record_request_start = Mock()
            mock_service.record_request_end = Mock()
            mock_get_service.return_value = mock_service

            # Test A100 for 2 hours
            @gpu_throttled(gpu_type="A100")
            def test_func(duration_hours=2.0):
                return "test"

            test_func(duration_hours=2.0)
            a100_cost = mock_service.should_throttle.call_args[0][3]
            self.assertEqual(a100_cost, 2.5 * 2.0)  # A100 hourly rate * duration

            # Test T4 for 1 hour
            mock_service.reset_mock()

            @gpu_throttled(gpu_type="T4")
            def test_func2(duration_hours=1.0):
                return "test"

            test_func2(duration_hours=1.0)
            t4_cost = mock_service.should_throttle.call_args[0][3]
            self.assertEqual(t4_cost, 0.5 * 1.0)  # T4 hourly rate * duration


if __name__ == "__main__":
    unittest.main()
