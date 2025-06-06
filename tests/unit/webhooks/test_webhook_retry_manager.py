#!/usr/bin/env python3
"""
Unit tests for webhook retry manager.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from leadfactory.webhooks.webhook_retry_manager import (
    WebhookRetryManager,
    WebhookRetryItem,
    WebhookPriority,
    RetryQueueStatus,
)
from leadfactory.pipeline.retry_mechanisms import RetryConfig, CircuitBreakerConfig


class TestWebhookRetryItem:
    """Test cases for WebhookRetryItem."""

    def test_webhook_retry_item_creation(self):
        """Test webhook retry item creation."""
        next_retry_time = datetime.utcnow() + timedelta(minutes=5)

        item = WebhookRetryItem(
            event_id="test_event_123",
            webhook_name="sendgrid",
            retry_attempt=2,
            next_retry_time=next_retry_time,
            priority=WebhookPriority.HIGH,
            error_count=1,
            last_error="Connection timeout",
        )

        assert item.event_id == "test_event_123"
        assert item.webhook_name == "sendgrid"
        assert item.retry_attempt == 2
        assert item.next_retry_time == next_retry_time
        assert item.priority == WebhookPriority.HIGH
        assert item.error_count == 1
        assert item.last_error == "Connection timeout"

    def test_webhook_retry_item_comparison(self):
        """Test webhook retry item priority queue ordering."""
        now = datetime.utcnow()

        high_priority_item = WebhookRetryItem(
            event_id="high_priority",
            webhook_name="stripe",
            retry_attempt=1,
            next_retry_time=now + timedelta(minutes=10),
            priority=WebhookPriority.HIGH,
        )

        low_priority_item = WebhookRetryItem(
            event_id="low_priority",
            webhook_name="analytics",
            retry_attempt=1,
            next_retry_time=now + timedelta(minutes=5),
            priority=WebhookPriority.LOW,
        )

        # High priority should come before low priority
        assert high_priority_item < low_priority_item

        # Among same priority, earlier time comes first
        early_item = WebhookRetryItem(
            event_id="early",
            webhook_name="sendgrid",
            retry_attempt=1,
            next_retry_time=now + timedelta(minutes=1),
            priority=WebhookPriority.NORMAL,
        )

        late_item = WebhookRetryItem(
            event_id="late",
            webhook_name="sendgrid",
            retry_attempt=1,
            next_retry_time=now + timedelta(minutes=10),
            priority=WebhookPriority.NORMAL,
        )

        assert early_item < late_item


class TestWebhookRetryManager:
    """Test cases for WebhookRetryManager."""

    def setup_method(self):
        """Setup test dependencies."""
        self.mock_storage = Mock()

        with patch('leadfactory.webhooks.webhook_retry_manager.get_storage_instance', return_value=self.mock_storage):
            self.retry_manager = WebhookRetryManager(
                max_concurrent_retries=5,
                batch_size=10,
                queue_check_interval=30,
            )

    def test_retry_manager_initialization(self):
        """Test retry manager initialization."""
        assert self.retry_manager.storage == self.mock_storage
        assert self.retry_manager.max_concurrent_retries == 5
        assert self.retry_manager.batch_size == 10
        assert self.retry_manager.queue_check_interval == 30
        assert self.retry_manager.queue_status == RetryQueueStatus.IDLE
        assert len(self.retry_manager.retry_queue) == 0

        # Check default configurations are loaded
        assert "stripe" in self.retry_manager.webhook_retry_configs
        assert "sendgrid" in self.retry_manager.webhook_retry_configs
        assert "engagement" in self.retry_manager.webhook_retry_configs

    def test_register_webhook_config(self):
        """Test registering webhook retry configuration."""
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=60.0,
        )

        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
        )

        self.retry_manager.register_webhook_config(
            "test_webhook",
            retry_config,
            circuit_breaker_config,
            WebhookPriority.HIGH,
        )

        assert "test_webhook" in self.retry_manager.webhook_retry_configs
        assert self.retry_manager.webhook_retry_configs["test_webhook"] == retry_config
        assert "test_webhook" in self.retry_manager.webhook_circuit_breakers

    def test_schedule_retry_success(self):
        """Test successful retry scheduling."""
        self.mock_storage.store_webhook_retry_item.return_value = True

        result = self.retry_manager.schedule_retry(
            event_id="test_event_123",
            webhook_name="sendgrid",
            retry_attempt=1,
            error="Connection failed",
            priority=WebhookPriority.HIGH,
        )

        assert result is True
        assert len(self.retry_manager.retry_queue) == 1
        assert self.retry_manager.stats["items_in_queue"] == 1

        # Check the queued item
        item = self.retry_manager.retry_queue[0]
        assert item.event_id == "test_event_123"
        assert item.webhook_name == "sendgrid"
        assert item.retry_attempt == 1
        assert item.last_error == "Connection failed"
        assert item.priority == WebhookPriority.HIGH

        # Verify storage call
        self.mock_storage.store_webhook_retry_item.assert_called_once()

    def test_schedule_retry_max_attempts_exceeded(self):
        """Test retry scheduling when max attempts exceeded."""
        # Configure a webhook with max 2 attempts
        retry_config = RetryConfig(max_attempts=2)
        self.retry_manager.webhook_retry_configs["test_webhook"] = retry_config

        result = self.retry_manager.schedule_retry(
            event_id="test_event_123",
            webhook_name="test_webhook",
            retry_attempt=3,  # Exceeds max attempts
        )

        assert result is False
        assert len(self.retry_manager.retry_queue) == 0

    def test_schedule_retry_circuit_breaker_open(self):
        """Test retry scheduling when circuit breaker is open."""
        # Setup circuit breaker
        circuit_breaker = Mock()
        circuit_breaker.can_execute.return_value = False
        self.retry_manager.webhook_circuit_breakers["test_webhook"] = circuit_breaker

        result = self.retry_manager.schedule_retry(
            event_id="test_event_123",
            webhook_name="test_webhook",
            retry_attempt=1,
        )

        assert result is False
        assert len(self.retry_manager.retry_queue) == 0
        assert self.retry_manager.stats["circuit_breaker_trips"] == 1

    def test_calculate_retry_delay_exponential(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=60.0,
            jitter=False,  # Disable jitter for predictable testing
        )

        # Test different attempts
        delay_1 = self.retry_manager._calculate_retry_delay(config, 1)
        delay_2 = self.retry_manager._calculate_retry_delay(config, 2)
        delay_3 = self.retry_manager._calculate_retry_delay(config, 3)

        assert delay_1 == 1.0  # base_delay * 2^0
        assert delay_2 == 2.0  # base_delay * 2^1
        assert delay_3 == 4.0  # base_delay * 2^2

    def test_calculate_retry_delay_linear(self):
        """Test linear backoff delay calculation."""
        from leadfactory.pipeline.retry_mechanisms import RetryStrategy

        config = RetryConfig(
            base_delay=2.0,
            backoff_strategy=RetryStrategy.LINEAR_BACKOFF,
            max_delay=60.0,
            jitter=False,
        )

        delay_1 = self.retry_manager._calculate_retry_delay(config, 1)
        delay_2 = self.retry_manager._calculate_retry_delay(config, 2)
        delay_3 = self.retry_manager._calculate_retry_delay(config, 3)

        assert delay_1 == 2.0  # base_delay * 1
        assert delay_2 == 4.0  # base_delay * 2
        assert delay_3 == 6.0  # base_delay * 3

    def test_calculate_retry_delay_max_limit(self):
        """Test delay calculation respects max limit."""
        config = RetryConfig(
            base_delay=10.0,
            exponential_base=10.0,
            max_delay=30.0,
            jitter=False,
        )

        delay = self.retry_manager._calculate_retry_delay(config, 5)
        assert delay == 30.0  # Should be capped at max_delay

    def test_determine_priority_payment_webhook(self):
        """Test priority determination for payment webhooks."""
        priority = self.retry_manager._determine_priority("stripe", 1, None)
        assert priority == WebhookPriority.CRITICAL

        priority = self.retry_manager._determine_priority("paypal", 1, None)
        assert priority == WebhookPriority.CRITICAL

    def test_determine_priority_timeout_error(self):
        """Test priority determination for timeout errors."""
        priority = self.retry_manager._determine_priority(
            "sendgrid", 1, "Connection timeout"
        )
        assert priority == WebhookPriority.HIGH

        priority = self.retry_manager._determine_priority(
            "sendgrid", 1, "Network error occurred"
        )
        assert priority == WebhookPriority.HIGH

    def test_determine_priority_email_retry(self):
        """Test priority determination for email retries."""
        # First attempt should be normal priority
        priority = self.retry_manager._determine_priority("sendgrid", 1, None)
        assert priority == WebhookPriority.NORMAL

        # Second attempt should be high priority
        priority = self.retry_manager._determine_priority("sendgrid", 2, None)
        assert priority == WebhookPriority.HIGH

    @pytest.mark.asyncio
    async def test_load_retry_items_from_storage(self):
        """Test loading retry items from storage."""
        stored_items = [
            {
                "event_id": "event_1",
                "webhook_name": "sendgrid",
                "retry_attempt": 1,
                "next_retry_time": datetime.utcnow(),
                "priority": WebhookPriority.NORMAL,
                "error_count": 0,
                "last_error": None,
                "created_at": datetime.utcnow(),
            },
            {
                "event_id": "event_2",
                "webhook_name": "stripe",
                "retry_attempt": 2,
                "next_retry_time": datetime.utcnow(),
                "priority": WebhookPriority.CRITICAL,
                "error_count": 1,
                "last_error": "Processing failed",
                "created_at": datetime.utcnow(),
            },
        ]

        self.mock_storage.get_pending_webhook_retries.return_value = stored_items

        await self.retry_manager._load_retry_items_from_storage()

        assert len(self.retry_manager.retry_queue) == 2

        # Verify items were loaded correctly
        event_ids = {item.event_id for item in self.retry_manager.retry_queue}
        assert "event_1" in event_ids
        assert "event_2" in event_ids

    @pytest.mark.asyncio
    async def test_process_ready_items(self):
        """Test processing ready retry items."""
        # Add items to queue
        now = datetime.utcnow()
        ready_item = WebhookRetryItem(
            event_id="ready_event",
            webhook_name="sendgrid",
            retry_attempt=1,
            next_retry_time=now - timedelta(minutes=1),  # Ready for processing
        )

        future_item = WebhookRetryItem(
            event_id="future_event",
            webhook_name="sendgrid",
            retry_attempt=1,
            next_retry_time=now + timedelta(minutes=10),  # Not ready yet
        )

        import heapq
        heapq.heappush(self.retry_manager.retry_queue, ready_item)
        heapq.heappush(self.retry_manager.retry_queue, future_item)

        # Mock event processing
        event_data = {
            "event_id": "ready_event",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"test": "data"},
            "headers": {},
            "timestamp": now.isoformat(),
            "status": "failed",
            "retry_count": 0,
        }

        self.mock_storage.get_webhook_event.return_value = event_data
        self.mock_storage.update_webhook_event.return_value = True
        self.mock_storage.remove_webhook_retry_item.return_value = True

        # Mock successful processing
        with patch('leadfactory.webhooks.webhook_validator.WebhookValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator._process_event_handlers.return_value = True
            mock_validator_class.return_value = mock_validator

            await self.retry_manager._process_ready_items()

        # Only the ready item should have been processed
        assert len(self.retry_manager.retry_queue) == 1
        remaining_item = self.retry_manager.retry_queue[0]
        assert remaining_item.event_id == "future_event"

        # Stats should be updated
        assert self.retry_manager.stats["total_retries"] == 1
        assert self.retry_manager.stats["successful_retries"] == 1

    @pytest.mark.asyncio
    async def test_process_retry_item_success(self):
        """Test successful processing of a retry item."""
        item = WebhookRetryItem(
            event_id="test_event",
            webhook_name="sendgrid",
            retry_attempt=1,
        )

        event_data = {
            "event_id": "test_event",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"test": "data"},
            "headers": {},
            "timestamp": datetime.utcnow().isoformat(),
            "status": "failed",
            "retry_count": 0,
        }

        self.mock_storage.get_webhook_event.return_value = event_data
        self.mock_storage.update_webhook_event.return_value = True

        # Mock successful processing
        with patch('leadfactory.webhooks.webhook_validator.WebhookValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator._process_event_handlers.return_value = True
            mock_validator_class.return_value = mock_validator

            semaphore = asyncio.Semaphore(1)
            result = await self.retry_manager._process_retry_item(item, semaphore)

        assert result is True
        self.mock_storage.update_webhook_event.assert_called()

    @pytest.mark.asyncio
    async def test_process_retry_item_failure(self):
        """Test failed processing of a retry item."""
        item = WebhookRetryItem(
            event_id="test_event",
            webhook_name="sendgrid",
            retry_attempt=1,
        )

        event_data = {
            "event_id": "test_event",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"test": "data"},
            "headers": {},
            "timestamp": datetime.utcnow().isoformat(),
            "status": "failed",
            "retry_count": 0,
        }

        self.mock_storage.get_webhook_event.return_value = event_data
        self.mock_storage.update_webhook_event.return_value = True

        # Mock failed processing
        with patch('leadfactory.webhooks.webhook_validator.WebhookValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator._process_event_handlers.return_value = False
            mock_validator_class.return_value = mock_validator

            semaphore = asyncio.Semaphore(1)
            result = await self.retry_manager._process_retry_item(item, semaphore)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_retry_item_exception(self):
        """Test processing retry item with exception."""
        item = WebhookRetryItem(
            event_id="test_event",
            webhook_name="sendgrid",
            retry_attempt=1,
        )

        event_data = {
            "event_id": "test_event",
            "webhook_name": "sendgrid",
            "event_type": "email_delivery",
            "payload": {"test": "data"},
            "headers": {},
            "timestamp": datetime.utcnow().isoformat(),
            "status": "failed",
            "retry_count": 0,
        }

        self.mock_storage.get_webhook_event.return_value = event_data
        self.mock_storage.update_webhook_event.return_value = True

        # Mock processing exception
        with patch('leadfactory.webhooks.webhook_validator.WebhookValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator._process_event_handlers.side_effect = Exception("Processing failed")
            mock_validator_class.return_value = mock_validator

            semaphore = asyncio.Semaphore(1)
            result = await self.retry_manager._process_retry_item(item, semaphore)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_retry_item_event_not_found(self):
        """Test processing retry item when event not found."""
        item = WebhookRetryItem(
            event_id="nonexistent_event",
            webhook_name="sendgrid",
            retry_attempt=1,
        )

        self.mock_storage.get_webhook_event.return_value = None

        semaphore = asyncio.Semaphore(1)
        result = await self.retry_manager._process_retry_item(item, semaphore)

        assert result is False

    def test_pause_resume_queue(self):
        """Test pausing and resuming the retry queue."""
        # Initially idle
        assert self.retry_manager.queue_status == RetryQueueStatus.IDLE

        # Pause (simulate running state first)
        self.retry_manager.queue_status = RetryQueueStatus.RUNNING
        self.retry_manager.pause_queue()
        assert self.retry_manager.queue_status == RetryQueueStatus.PAUSED

        # Resume
        self.retry_manager.resume_queue()
        assert self.retry_manager.queue_status == RetryQueueStatus.RUNNING

    def test_stop_queue(self):
        """Test stopping the retry queue."""
        self.retry_manager.queue_status = RetryQueueStatus.RUNNING
        self.retry_manager.stop_queue()
        assert self.retry_manager.queue_status == RetryQueueStatus.STOPPED

    def test_get_queue_stats(self):
        """Test getting queue statistics."""
        # Add some test data
        self.retry_manager.stats["total_retries"] = 100
        self.retry_manager.stats["successful_retries"] = 85
        self.retry_manager.stats["failed_retries"] = 15

        stats = self.retry_manager.get_queue_stats()

        assert stats["total_retries"] == 100
        assert stats["successful_retries"] == 85
        assert stats["failed_retries"] == 15
        assert "queue_status" in stats
        assert "current_retries" in stats
        assert "circuit_breakers" in stats
        assert "webhook_configs" in stats

    def test_get_priority_distribution(self):
        """Test getting priority distribution."""
        # Add items with different priorities
        items = [
            WebhookRetryItem("event_1", "sendgrid", 1, datetime.utcnow(), WebhookPriority.HIGH),
            WebhookRetryItem("event_2", "stripe", 1, datetime.utcnow(), WebhookPriority.CRITICAL),
            WebhookRetryItem("event_3", "analytics", 1, datetime.utcnow(), WebhookPriority.LOW),
            WebhookRetryItem("event_4", "sendgrid", 1, datetime.utcnow(), WebhookPriority.HIGH),
        ]

        for item in items:
            import heapq
            heapq.heappush(self.retry_manager.retry_queue, item)

        distribution = self.retry_manager.get_priority_distribution()

        assert distribution["HIGH"] == 2
        assert distribution["CRITICAL"] == 1
        assert distribution["LOW"] == 1
        assert distribution["NORMAL"] == 0

    def test_clear_queue_all(self):
        """Test clearing entire retry queue."""
        # Add some items
        items = [
            WebhookRetryItem("event_1", "sendgrid", 1, datetime.utcnow()),
            WebhookRetryItem("event_2", "stripe", 1, datetime.utcnow()),
        ]

        for item in items:
            import heapq
            heapq.heappush(self.retry_manager.retry_queue, item)

        assert len(self.retry_manager.retry_queue) == 2

        self.retry_manager.clear_queue()

        assert len(self.retry_manager.retry_queue) == 0
        assert self.retry_manager.stats["items_in_queue"] == 0

    def test_clear_queue_specific_webhook(self):
        """Test clearing retry queue for specific webhook."""
        items = [
            WebhookRetryItem("event_1", "sendgrid", 1, datetime.utcnow()),
            WebhookRetryItem("event_2", "stripe", 1, datetime.utcnow()),
            WebhookRetryItem("event_3", "sendgrid", 1, datetime.utcnow()),
        ]

        for item in items:
            import heapq
            heapq.heappush(self.retry_manager.retry_queue, item)

        assert len(self.retry_manager.retry_queue) == 3

        self.retry_manager.clear_queue("sendgrid")

        # Only stripe event should remain
        assert len(self.retry_manager.retry_queue) == 1
        remaining_item = self.retry_manager.retry_queue[0]
        assert remaining_item.webhook_name == "stripe"

    def test_force_retry_event(self):
        """Test forcing immediate retry of an event."""
        event_data = {
            "event_id": "test_event",
            "webhook_name": "sendgrid",
            "retry_count": 2,
        }

        self.mock_storage.get_webhook_event.return_value = event_data

        result = self.retry_manager.force_retry_event("test_event", WebhookPriority.HIGH)

        assert result is True
        assert len(self.retry_manager.retry_queue) == 1

        # Check the queued item
        item = self.retry_manager.retry_queue[0]
        assert item.event_id == "test_event"
        assert item.priority == WebhookPriority.HIGH
        assert item.retry_attempt == 3  # retry_count + 1

        # Should be scheduled for immediate retry
        now = datetime.utcnow()
        assert (item.next_retry_time - now).total_seconds() < 10

    def test_force_retry_event_not_found(self):
        """Test forcing retry of non-existent event."""
        self.mock_storage.get_webhook_event.return_value = None

        result = self.retry_manager.force_retry_event("nonexistent_event")

        assert result is False
        assert len(self.retry_manager.retry_queue) == 0
