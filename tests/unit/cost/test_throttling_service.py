"""
Unit tests for the throttling service module.
"""

import asyncio
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from threading import Thread

from leadfactory.cost.throttling_service import (
    ThrottlingService,
    ThrottlingStrategy,
    ThrottlingAction,
    ThrottlingDecision,
    RateLimitConfig,
    RequestTracker,
    get_throttling_service,
    reset_throttling_service,
    should_throttle_request,
    apply_throttling_decision,
    apply_throttling_decision_async,
)


class TestRequestTracker(unittest.TestCase):
    """Test the RequestTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = RequestTracker()

    def test_request_tracker_initialization(self):
        """Test RequestTracker initialization."""
        self.assertEqual(self.tracker.concurrent_count, 0)
        self.assertEqual(len(self.tracker.timestamps), 0)

    def test_add_request(self):
        """Test adding requests to tracker."""
        self.tracker.add_request()
        self.assertEqual(self.tracker.concurrent_count, 1)
        self.assertEqual(len(self.tracker.timestamps), 1)

        self.tracker.add_request()
        self.assertEqual(self.tracker.concurrent_count, 2)
        self.assertEqual(len(self.tracker.timestamps), 2)

    def test_complete_request(self):
        """Test completing requests."""
        self.tracker.add_request()
        self.tracker.add_request()
        self.assertEqual(self.tracker.concurrent_count, 2)

        self.tracker.complete_request()
        self.assertEqual(self.tracker.concurrent_count, 1)

        self.tracker.complete_request()
        self.assertEqual(self.tracker.concurrent_count, 0)

        # Should not go below 0
        self.tracker.complete_request()
        self.assertEqual(self.tracker.concurrent_count, 0)

    def test_get_request_counts(self):
        """Test getting request counts."""
        # Add some requests
        self.tracker.add_request()
        time.sleep(0.01)  # Small delay to ensure different timestamps
        self.tracker.add_request()

        minute_count, hour_count = self.tracker.get_request_counts()
        self.assertEqual(minute_count, 2)
        self.assertEqual(hour_count, 2)

    def test_timestamp_cleanup(self):
        """Test that old timestamps are cleaned up."""
        # Mock time to simulate old timestamps
        with patch('time.time') as mock_time:
            # Add request 2 hours ago
            mock_time.return_value = 1000.0
            self.tracker.add_request()

            # Add request now
            mock_time.return_value = 8000.0  # 2+ hours later
            self.tracker.add_request()

            minute_count, hour_count = self.tracker.get_request_counts()
            self.assertEqual(minute_count, 1)  # Only recent request
            self.assertEqual(hour_count, 1)    # Only recent request
            self.assertEqual(len(self.tracker.timestamps), 1)  # Old timestamp cleaned


class TestThrottlingDecision(unittest.TestCase):
    """Test the ThrottlingDecision dataclass."""

    def test_throttling_decision_creation(self):
        """Test creating throttling decisions."""
        decision = ThrottlingDecision(action=ThrottlingAction.ALLOW)
        self.assertEqual(decision.action, ThrottlingAction.ALLOW)
        self.assertEqual(decision.delay_seconds, 0.0)
        self.assertIsNone(decision.alternative_model)
        self.assertEqual(decision.reason, "")

        decision = ThrottlingDecision(
            action=ThrottlingAction.DELAY,
            delay_seconds=5.0,
            reason="Rate limit exceeded"
        )
        self.assertEqual(decision.action, ThrottlingAction.DELAY)
        self.assertEqual(decision.delay_seconds, 5.0)
        self.assertEqual(decision.reason, "Rate limit exceeded")


class TestThrottlingService(unittest.TestCase):
    """Test the ThrottlingService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset global instance
        reset_throttling_service()

        # Mock dependencies
        self.mock_budget_config = Mock()
        self.mock_usage_tracker = Mock()

        # Create service with mocked dependencies
        with patch('leadfactory.cost.throttling_service.get_budget_config') as mock_get_config, \
             patch('leadfactory.cost.throttling_service.get_gpt_usage_tracker') as mock_get_tracker:

            mock_get_config.return_value = self.mock_budget_config
            mock_get_tracker.return_value = self.mock_usage_tracker

            self.service = ThrottlingService()

    def test_throttling_service_initialization(self):
        """Test ThrottlingService initialization."""
        self.assertIsNotNone(self.service.budget_config)
        self.assertIsNotNone(self.service.usage_tracker)
        self.assertIsInstance(self.service.rate_limit_config, RateLimitConfig)
        self.assertEqual(len(self.service.request_trackers), 0)

    def test_model_alternatives_configuration(self):
        """Test that model alternatives are properly configured."""
        self.assertIn("gpt-4o", self.service.model_alternatives)
        self.assertIn("gpt-4o-mini", self.service.model_alternatives["gpt-4o"])

        self.assertIn("gpt-4o", self.service.model_cost_multipliers)
        self.assertLess(
            self.service.model_cost_multipliers["gpt-4o-mini"],
            self.service.model_cost_multipliers["gpt-4o"]
        )

    def test_get_budget_status_success(self):
        """Test successful budget status retrieval."""
        # Mock usage tracker responses
        self.mock_usage_tracker.get_usage_stats.side_effect = [
            {"summary": {"total_cost": 50.0}},  # daily
            {"summary": {"total_cost": 200.0}}, # weekly
            {"summary": {"total_cost": 500.0}}, # monthly
        ]

        # Mock budget config responses
        self.mock_budget_config.get_budget_limit.side_effect = [
            100.0,  # daily limit
            500.0,  # weekly limit
            2000.0, # monthly limit
        ]

        status = self.service._get_budget_status("openai", "gpt-4o", "chat")

        self.assertEqual(status["daily_utilization"], 0.5)
        self.assertEqual(status["weekly_utilization"], 0.4)
        self.assertEqual(status["monthly_utilization"], 0.25)
        self.assertEqual(status["daily_remaining"], 50.0)
        self.assertEqual(status["weekly_remaining"], 300.0)
        self.assertEqual(status["monthly_remaining"], 1500.0)

    def test_get_budget_status_error_handling(self):
        """Test budget status error handling."""
        # Mock usage tracker to raise exception
        self.mock_usage_tracker.get_usage_stats.side_effect = Exception("Database error")

        status = self.service._get_budget_status("openai", "gpt-4o", "chat")

        # Should return safe defaults
        self.assertEqual(status["daily_utilization"], 0)
        self.assertEqual(status["weekly_utilization"], 0)
        self.assertEqual(status["monthly_utilization"], 0)
        self.assertEqual(status["daily_remaining"], float('inf'))

    def test_check_rate_limits_within_limits(self):
        """Test rate limit checking when within limits."""
        decision = self.service._check_rate_limits("openai", "gpt-4o", "chat")
        self.assertEqual(decision.action, ThrottlingAction.ALLOW)

    def test_check_rate_limits_concurrent_exceeded(self):
        """Test rate limit checking when concurrent limit exceeded."""
        # Simulate max concurrent requests
        key = "openai:gpt-4o:chat"
        tracker = RequestTracker()
        tracker.concurrent_count = self.service.rate_limit_config.max_concurrent_requests
        self.service.request_trackers[key] = tracker

        decision = self.service._check_rate_limits("openai", "gpt-4o", "chat")
        self.assertEqual(decision.action, ThrottlingAction.DELAY)
        self.assertGreater(decision.delay_seconds, 0)
        self.assertIn("concurrent", decision.reason)

    def test_check_rate_limits_minute_exceeded(self):
        """Test rate limit checking when per-minute limit exceeded."""
        # Simulate too many requests in the last minute
        key = "openai:gpt-4o:chat"
        tracker = RequestTracker()
        current_time = time.time()

        # Add requests within the last minute
        for _ in range(self.service.rate_limit_config.max_requests_per_minute + 1):
            tracker.timestamps.append(current_time - 30)  # 30 seconds ago

        self.service.request_trackers[key] = tracker

        decision = self.service._check_rate_limits("openai", "gpt-4o", "chat")
        self.assertEqual(decision.action, ThrottlingAction.DELAY)
        self.assertIn("Per-minute", decision.reason)

    def test_choose_adaptive_strategy(self):
        """Test adaptive strategy selection."""
        # Low utilization -> SOFT
        status = {"daily_utilization": 0.5, "weekly_utilization": 0.4, "monthly_utilization": 0.3}
        strategy = self.service._choose_adaptive_strategy(status)
        self.assertEqual(strategy, ThrottlingStrategy.SOFT)

        # Medium utilization -> GRACEFUL
        status = {"daily_utilization": 0.8, "weekly_utilization": 0.7, "monthly_utilization": 0.6}
        strategy = self.service._choose_adaptive_strategy(status)
        self.assertEqual(strategy, ThrottlingStrategy.GRACEFUL)

        # High utilization -> HARD
        status = {"daily_utilization": 0.95, "weekly_utilization": 0.9, "monthly_utilization": 0.8}
        strategy = self.service._choose_adaptive_strategy(status)
        self.assertEqual(strategy, ThrottlingStrategy.HARD)

    def test_find_cheaper_alternative(self):
        """Test finding cheaper model alternatives."""
        # Test with gpt-4o
        alternative = self.service._find_cheaper_alternative("gpt-4o", 10.0, 5.0)
        self.assertIsNotNone(alternative)
        self.assertIn(alternative, self.service.model_alternatives["gpt-4o"])

        # Test with model that has no alternatives
        alternative = self.service._find_cheaper_alternative("unknown-model", 10.0, 5.0)
        self.assertIsNone(alternative)

        # Test when no alternative is cheap enough
        alternative = self.service._find_cheaper_alternative("gpt-4o", 10.0, 0.01)
        self.assertIsNone(alternative)

    def test_calculate_delay(self):
        """Test delay calculation."""
        # Test at threshold
        delay = self.service._calculate_delay(0.8, 0.8)
        self.assertGreaterEqual(delay, 1.0)

        # Test above threshold
        delay = self.service._calculate_delay(0.9, 0.8)
        self.assertGreater(delay, 1.0)

        # Test well above threshold
        delay = self.service._calculate_delay(0.95, 0.8)
        self.assertGreater(delay, 5.0)
        self.assertLessEqual(delay, 30.0)  # Should not exceed max delay

    def test_should_throttle_allow(self):
        """Test throttling decision when request should be allowed."""
        # Mock budget status - low utilization
        self.mock_usage_tracker.get_usage_stats.side_effect = [
            {"summary": {"total_cost": 10.0}},  # daily
            {"summary": {"total_cost": 50.0}},  # weekly
            {"summary": {"total_cost": 100.0}}, # monthly
        ]

        self.mock_budget_config.get_budget_limit.side_effect = [
            100.0,  # daily limit
            500.0,  # weekly limit
            2000.0, # monthly limit
        ]

        self.mock_budget_config.get_alert_thresholds.return_value = [
            Mock(percentage=0.8),
            Mock(percentage=0.95),
        ]

        decision = self.service.should_throttle("openai", "gpt-4o", "chat", 5.0)
        self.assertEqual(decision.action, ThrottlingAction.ALLOW)
        self.assertEqual(decision.estimated_cost, 5.0)

    def test_should_throttle_reject_over_budget(self):
        """Test throttling decision when cost exceeds budget."""
        # Mock budget status - high utilization
        self.mock_usage_tracker.get_usage_stats.side_effect = [
            {"summary": {"total_cost": 95.0}},  # daily
            {"summary": {"total_cost": 400.0}}, # weekly
            {"summary": {"total_cost": 1800.0}}, # monthly
        ]

        self.mock_budget_config.get_budget_limit.side_effect = [
            100.0,  # daily limit
            500.0,  # weekly limit
            2000.0, # monthly limit
        ]

        self.mock_budget_config.get_alert_thresholds.return_value = [
            Mock(percentage=0.8),
            Mock(percentage=0.95),
        ]

        # Request that would exceed daily budget
        decision = self.service.should_throttle("openai", "gpt-4o", "chat", 10.0, ThrottlingStrategy.HARD)
        self.assertEqual(decision.action, ThrottlingAction.REJECT)
        self.assertIn("exceeds remaining budget", decision.reason)

    def test_should_throttle_downgrade(self):
        """Test throttling decision with graceful degradation."""
        # Mock budget status - high utilization
        self.mock_usage_tracker.get_usage_stats.side_effect = [
            {"summary": {"total_cost": 95.0}},  # daily
            {"summary": {"total_cost": 400.0}}, # weekly
            {"summary": {"total_cost": 1800.0}}, # monthly
        ]

        self.mock_budget_config.get_budget_limit.side_effect = [
            100.0,  # daily limit
            500.0,  # weekly limit
            2000.0, # monthly limit
        ]

        self.mock_budget_config.get_alert_thresholds.return_value = [
            Mock(percentage=0.8),
            Mock(percentage=0.95),
        ]

        # Request that would exceed budget but has cheaper alternative
        decision = self.service.should_throttle("openai", "gpt-4o", "chat", 10.0, ThrottlingStrategy.GRACEFUL)
        self.assertEqual(decision.action, ThrottlingAction.DOWNGRADE)
        self.assertIsNotNone(decision.alternative_model)
        self.assertIn("gpt-4o-mini", decision.alternative_model)

    def test_should_throttle_delay(self):
        """Test throttling decision with delay."""
        # Mock budget status - warning level utilization
        self.mock_usage_tracker.get_usage_stats.side_effect = [
            {"summary": {"total_cost": 85.0}},  # daily
            {"summary": {"total_cost": 350.0}}, # weekly
            {"summary": {"total_cost": 1500.0}}, # monthly
        ]

        self.mock_budget_config.get_budget_limit.side_effect = [
            100.0,  # daily limit
            500.0,  # weekly limit
            2000.0, # monthly limit
        ]

        self.mock_budget_config.get_alert_thresholds.return_value = [
            Mock(percentage=0.8),
            Mock(percentage=0.95),
        ]

        decision = self.service.should_throttle("openai", "gpt-4o", "chat", 5.0, ThrottlingStrategy.SOFT)
        self.assertEqual(decision.action, ThrottlingAction.DELAY)
        self.assertGreater(decision.delay_seconds, 0)

    def test_record_request_lifecycle(self):
        """Test recording request start and end."""
        service = "openai"
        model = "gpt-4o"
        endpoint = "chat"

        # Start request
        self.service.record_request_start(service, model, endpoint)

        key = f"{service}:{model}:{endpoint}"
        self.assertIn(key, self.service.request_trackers)
        self.assertEqual(self.service.request_trackers[key].concurrent_count, 1)

        # End request
        self.service.record_request_end(service, model, endpoint)
        self.assertEqual(self.service.request_trackers[key].concurrent_count, 0)

    def test_get_throttling_stats(self):
        """Test getting throttling statistics."""
        # Add some request activity
        self.service.record_request_start("openai", "gpt-4o", "chat")

        stats = self.service.get_throttling_stats()

        self.assertIn("rate_limit_config", stats)
        self.assertIn("active_trackers", stats)
        self.assertIn("openai:gpt-4o:chat", stats["active_trackers"])
        self.assertEqual(stats["active_trackers"]["openai:gpt-4o:chat"]["concurrent_requests"], 1)

    def test_update_rate_limits(self):
        """Test updating rate limit configuration."""
        original_minute_limit = self.service.rate_limit_config.max_requests_per_minute

        self.service.update_rate_limits(max_requests_per_minute=120)

        self.assertEqual(self.service.rate_limit_config.max_requests_per_minute, 120)
        self.assertNotEqual(self.service.rate_limit_config.max_requests_per_minute, original_minute_limit)


class TestGlobalFunctions(unittest.TestCase):
    """Test global functions and singleton management."""

    def setUp(self):
        """Set up test fixtures."""
        reset_throttling_service()

    def tearDown(self):
        """Clean up after tests."""
        reset_throttling_service()

    def test_get_throttling_service_singleton(self):
        """Test that get_throttling_service returns a singleton."""
        with patch('leadfactory.cost.throttling_service.get_budget_config'), \
             patch('leadfactory.cost.throttling_service.get_gpt_usage_tracker'):

            service1 = get_throttling_service()
            service2 = get_throttling_service()

            self.assertIs(service1, service2)

    def test_reset_throttling_service(self):
        """Test resetting the global throttling service."""
        with patch('leadfactory.cost.throttling_service.get_budget_config'), \
             patch('leadfactory.cost.throttling_service.get_gpt_usage_tracker'):

            service1 = get_throttling_service()
            reset_throttling_service()
            service2 = get_throttling_service()

            self.assertIsNot(service1, service2)

    def test_should_throttle_request_convenience(self):
        """Test the convenience function for throttling requests."""
        with patch('leadfactory.cost.throttling_service.get_budget_config'), \
             patch('leadfactory.cost.throttling_service.get_gpt_usage_tracker'):

            with patch.object(ThrottlingService, 'should_throttle') as mock_should_throttle:
                mock_should_throttle.return_value = ThrottlingDecision(action=ThrottlingAction.ALLOW)

                decision = should_throttle_request("openai", "gpt-4o", "chat", 5.0)

                self.assertEqual(decision.action, ThrottlingAction.ALLOW)
                mock_should_throttle.assert_called_once_with("openai", "gpt-4o", "chat", 5.0, ThrottlingStrategy.ADAPTIVE)

    def test_apply_throttling_decision_allow(self):
        """Test applying ALLOW throttling decision."""
        decision = ThrottlingDecision(action=ThrottlingAction.ALLOW)
        result = apply_throttling_decision(decision)
        self.assertTrue(result)

    def test_apply_throttling_decision_delay(self):
        """Test applying DELAY throttling decision."""
        decision = ThrottlingDecision(action=ThrottlingAction.DELAY, delay_seconds=0.01)

        start_time = time.time()
        result = apply_throttling_decision(decision)
        end_time = time.time()

        self.assertTrue(result)
        self.assertGreaterEqual(end_time - start_time, 0.01)

    def test_apply_throttling_decision_reject(self):
        """Test applying REJECT throttling decision."""
        decision = ThrottlingDecision(action=ThrottlingAction.REJECT, reason="Budget exceeded")
        result = apply_throttling_decision(decision)
        self.assertFalse(result)

    def test_apply_throttling_decision_downgrade(self):
        """Test applying DOWNGRADE throttling decision."""
        decision = ThrottlingDecision(
            action=ThrottlingAction.DOWNGRADE,
            alternative_model="gpt-4o-mini",
            reason="Budget optimization"
        )
        result = apply_throttling_decision(decision)
        self.assertTrue(result)  # Should return True to let caller handle downgrade


class TestAsyncFunctions(unittest.TestCase):
    """Test async throttling functions."""

    def test_apply_throttling_decision_async_allow(self):
        """Test async ALLOW throttling decision."""
        async def test_async():
            decision = ThrottlingDecision(action=ThrottlingAction.ALLOW)
            result = await apply_throttling_decision_async(decision)
            self.assertTrue(result)

        asyncio.run(test_async())

    def test_apply_throttling_decision_async_delay(self):
        """Test async DELAY throttling decision."""
        async def test_async():
            decision = ThrottlingDecision(action=ThrottlingAction.DELAY, delay_seconds=0.01)

            start_time = time.time()
            result = await apply_throttling_decision_async(decision)
            end_time = time.time()

            self.assertTrue(result)
            self.assertGreaterEqual(end_time - start_time, 0.01)

        asyncio.run(test_async())

    def test_apply_throttling_decision_async_reject(self):
        """Test async REJECT throttling decision."""
        async def test_async():
            decision = ThrottlingDecision(action=ThrottlingAction.REJECT, reason="Budget exceeded")
            result = await apply_throttling_decision_async(decision)
            self.assertFalse(result)

        asyncio.run(test_async())


class TestConcurrency(unittest.TestCase):
    """Test concurrent access to throttling service."""

    def setUp(self):
        """Set up test fixtures."""
        reset_throttling_service()

        with patch('leadfactory.cost.throttling_service.get_budget_config'), \
             patch('leadfactory.cost.throttling_service.get_gpt_usage_tracker'):
            self.service = ThrottlingService()

    def test_concurrent_request_tracking(self):
        """Test concurrent request tracking."""
        def add_requests():
            for _ in range(10):
                self.service.record_request_start("openai", "gpt-4o", "chat")
                time.sleep(0.001)
                self.service.record_request_end("openai", "gpt-4o", "chat")

        threads = [Thread(target=add_requests) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All requests should be completed
        key = "openai:gpt-4o:chat"
        if key in self.service.request_trackers:
            self.assertEqual(self.service.request_trackers[key].concurrent_count, 0)

    def test_concurrent_throttling_decisions(self):
        """Test concurrent throttling decisions."""
        # Mock dependencies
        self.service.usage_tracker.get_usage_stats.return_value = {"summary": {"total_cost": 50.0}}
        self.service.budget_config.get_budget_limit.return_value = 100.0
        self.service.budget_config.get_alert_thresholds.return_value = [
            Mock(percentage=0.8),
            Mock(percentage=0.95),
        ]

        decisions = []

        def make_decision():
            decision = self.service.should_throttle("openai", "gpt-4o", "chat", 5.0)
            decisions.append(decision)

        threads = [Thread(target=make_decision) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All decisions should be made without errors
        self.assertEqual(len(decisions), 10)
        for decision in decisions:
            self.assertIsInstance(decision, ThrottlingDecision)


if __name__ == "__main__":
    unittest.main()
