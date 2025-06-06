#!/usr/bin/env python3
"""
Webhook-specific retry management with intelligent backoff and circuit breakers.

This module extends the general retry mechanisms with webhook-specific logic,
including priority queues, batch processing, and webhook-specific failure patterns.
"""

import asyncio
import heapq
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from leadfactory.pipeline.retry_mechanisms import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryConfig,
    RetryManager,
    RetryStrategy,
)
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookPriority(Enum):
    """Webhook processing priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class RetryQueueStatus(Enum):
    """Retry queue processing status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class WebhookRetryItem:
    """Item in the webhook retry queue."""

    event_id: str
    webhook_name: str
    retry_attempt: int
    next_retry_time: datetime
    priority: WebhookPriority = WebhookPriority.NORMAL
    error_count: int = 0
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other):
        """Comparison for priority queue ordering."""
        # Higher priority first, then earlier retry time
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        return self.next_retry_time < other.next_retry_time


class WebhookRetryManager:
    """Enhanced retry manager specifically for webhooks."""

    def __init__(
        self,
        max_concurrent_retries: int = 10,
        batch_size: int = 50,
        queue_check_interval: int = 30,
    ):
        """Initialize webhook retry manager.

        Args:
            max_concurrent_retries: Maximum concurrent retry operations
            batch_size: Number of retries to process in each batch
            queue_check_interval: Interval between queue checks in seconds
        """
        self.storage = get_storage_instance()
        self.max_concurrent_retries = max_concurrent_retries
        self.batch_size = batch_size
        self.queue_check_interval = queue_check_interval

        # Priority queue for retry items
        self.retry_queue: List[WebhookRetryItem] = []
        self.queue_status = RetryQueueStatus.IDLE
        self.current_retries: Set[str] = set()

        # Webhook-specific retry configurations
        self.webhook_retry_configs: Dict[str, RetryConfig] = {}
        self.webhook_circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Statistics
        self.stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "items_in_queue": 0,
            "circuit_breaker_trips": 0,
            "last_queue_check": None,
        }

        # Setup default configurations
        self._setup_default_configs()

        logger.info("Initialized WebhookRetryManager")

    def _setup_default_configs(self):
        """Setup default retry configurations for different webhook types."""
        # High-priority webhooks (payments, critical system events)
        critical_config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=2.0,
            backoff_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )

        # Standard webhooks (email events, user actions)
        standard_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            backoff_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )

        # Low-priority webhooks (analytics, logs)
        low_priority_config = RetryConfig(
            max_attempts=2,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=1.5,
            backoff_strategy=RetryStrategy.LINEAR_BACKOFF,
        )

        # Circuit breaker configs
        critical_cb_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
        )

        standard_cb_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
        )

        # Assign configs to webhook types
        webhook_type_configs = {
            "stripe": (critical_config, critical_cb_config, WebhookPriority.CRITICAL),
            "paypal": (critical_config, critical_cb_config, WebhookPriority.CRITICAL),
            "sendgrid": (standard_config, standard_cb_config, WebhookPriority.NORMAL),
            "mailgun": (standard_config, standard_cb_config, WebhookPriority.NORMAL),
            "engagement": (
                low_priority_config,
                standard_cb_config,
                WebhookPriority.LOW,
            ),
            "analytics": (low_priority_config, standard_cb_config, WebhookPriority.LOW),
        }

        for webhook_name, (
            retry_config,
            cb_config,
            priority,
        ) in webhook_type_configs.items():
            self.register_webhook_config(
                webhook_name, retry_config, cb_config, priority
            )

    def register_webhook_config(
        self,
        webhook_name: str,
        retry_config: RetryConfig,
        circuit_breaker_config: CircuitBreakerConfig,
        default_priority: WebhookPriority = WebhookPriority.NORMAL,
    ):
        """Register retry configuration for a webhook.

        Args:
            webhook_name: Name of the webhook
            retry_config: Retry configuration
            circuit_breaker_config: Circuit breaker configuration
            default_priority: Default priority for this webhook type
        """
        self.webhook_retry_configs[webhook_name] = retry_config
        self.webhook_circuit_breakers[webhook_name] = CircuitBreaker(
            circuit_breaker_config
        )

        logger.info(f"Registered retry config for webhook: {webhook_name}")

    def schedule_retry(
        self,
        event_id: str,
        webhook_name: str,
        retry_attempt: int,
        error: Optional[str] = None,
        priority: Optional[WebhookPriority] = None,
    ) -> bool:
        """Schedule a webhook event for retry.

        Args:
            event_id: Webhook event ID
            webhook_name: Name of the webhook
            retry_attempt: Current retry attempt number
            error: Error message from failed attempt
            priority: Optional priority override

        Returns:
            True if scheduled successfully
        """
        try:
            # Get retry config for this webhook
            retry_config = self.webhook_retry_configs.get(
                webhook_name, RetryConfig()  # Default config
            )

            # Check if we've exceeded max attempts
            if retry_attempt >= retry_config.max_attempts:
                logger.warning(
                    f"Event {event_id} exceeded max retry attempts ({retry_config.max_attempts})"
                )
                return False

            # Check circuit breaker
            circuit_breaker = self.webhook_circuit_breakers.get(webhook_name)
            if circuit_breaker and not circuit_breaker.can_execute():
                logger.warning(
                    f"Circuit breaker open for webhook {webhook_name}, "
                    f"not scheduling retry for event {event_id}"
                )
                self.stats["circuit_breaker_trips"] += 1
                return False

            # Calculate next retry time
            delay = self._calculate_retry_delay(retry_config, retry_attempt)
            next_retry_time = datetime.utcnow() + timedelta(seconds=delay)

            # Determine priority
            if priority is None:
                priority = self._determine_priority(webhook_name, retry_attempt, error)

            # Create retry item
            retry_item = WebhookRetryItem(
                event_id=event_id,
                webhook_name=webhook_name,
                retry_attempt=retry_attempt,
                next_retry_time=next_retry_time,
                priority=priority,
                last_error=error,
            )

            # Add to priority queue
            heapq.heappush(self.retry_queue, retry_item)
            self.stats["items_in_queue"] = len(self.retry_queue)

            # Store in persistent storage
            self.storage.store_webhook_retry_item(retry_item.__dict__)

            logger.info(
                f"Scheduled retry for event {event_id} at {next_retry_time} "
                f"(attempt {retry_attempt}, priority {priority.name})"
            )

            return True

        except Exception as e:
            logger.error(f"Error scheduling retry for event {event_id}: {e}")
            return False

    def _calculate_retry_delay(self, config: RetryConfig, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if config.backoff_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.exponential_base ** (attempt - 1))
        elif config.backoff_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt
        else:
            delay = config.base_delay

        # Apply jitter to prevent thundering herd
        if config.jitter:
            import random

            jitter = delay * 0.1 * random.random()
            delay += jitter

        # Apply max delay limit
        return min(delay, config.max_delay)

    def _determine_priority(
        self, webhook_name: str, retry_attempt: int, error: Optional[str]
    ) -> WebhookPriority:
        """Determine priority for a retry based on webhook type and context."""
        # Payment-related webhooks get critical priority
        if webhook_name in ["stripe", "paypal", "square"]:
            return WebhookPriority.CRITICAL

        # Authentication/security events get high priority
        if "auth" in webhook_name.lower() or "security" in webhook_name.lower():
            return WebhookPriority.HIGH

        # Email delivery issues get elevated priority on later attempts
        if webhook_name in ["sendgrid", "mailgun"] and retry_attempt > 1:
            return WebhookPriority.HIGH

        # Timeout errors get higher priority (likely transient)
        if error and any(
            keyword in error.lower() for keyword in ["timeout", "connection", "network"]
        ):
            return WebhookPriority.HIGH

        # Default to normal priority
        return WebhookPriority.NORMAL

    async def process_retry_queue(self):
        """Process the retry queue in batches."""
        if self.queue_status != RetryQueueStatus.IDLE:
            logger.debug("Retry queue processor already running")
            return

        self.queue_status = RetryQueueStatus.RUNNING
        logger.info("Started retry queue processor")

        try:
            while self.queue_status == RetryQueueStatus.RUNNING:
                # Load items from persistent storage if queue is empty
                if not self.retry_queue:
                    await self._load_retry_items_from_storage()

                # Process ready items
                await self._process_ready_items()

                # Update statistics
                self.stats["items_in_queue"] = len(self.retry_queue)
                self.stats["last_queue_check"] = datetime.utcnow().isoformat()

                # Wait before next check
                await asyncio.sleep(self.queue_check_interval)

        except Exception as e:
            logger.error(f"Error in retry queue processor: {e}")
        finally:
            self.queue_status = RetryQueueStatus.IDLE
            logger.info("Retry queue processor stopped")

    async def _load_retry_items_from_storage(self):
        """Load retry items from persistent storage."""
        try:
            # Get pending retry items from storage
            stored_items = self.storage.get_pending_webhook_retries(
                limit=self.batch_size * 2
            )

            for item_data in stored_items:
                # Convert to WebhookRetryItem
                item = WebhookRetryItem(**item_data)
                heapq.heappush(self.retry_queue, item)

            if stored_items:
                logger.debug(f"Loaded {len(stored_items)} retry items from storage")

        except Exception as e:
            logger.error(f"Error loading retry items from storage: {e}")

    async def _process_ready_items(self):
        """Process items that are ready for retry."""
        current_time = datetime.utcnow()
        ready_items = []

        # Find items ready for processing
        while (
            self.retry_queue
            and self.retry_queue[0].next_retry_time <= current_time
            and len(ready_items) < self.batch_size
        ):
            item = heapq.heappop(self.retry_queue)
            ready_items.append(item)

        if not ready_items:
            return

        logger.info(f"Processing {len(ready_items)} ready retry items")

        # Process items with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent_retries)
        tasks = [self._process_retry_item(item, semaphore) for item in ready_items]

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle results
        for item, result in zip(ready_items, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing retry item {item.event_id}: {result}")
                # Reschedule with increased attempt count
                self.schedule_retry(
                    item.event_id,
                    item.webhook_name,
                    item.retry_attempt + 1,
                    str(result),
                    item.priority,
                )
            elif result:
                # Success
                self.stats["successful_retries"] += 1
                # Remove from storage
                self.storage.remove_webhook_retry_item(item.event_id)
            else:
                # Failed but not an exception
                self.stats["failed_retries"] += 1
                # Reschedule with increased attempt count
                self.schedule_retry(
                    item.event_id,
                    item.webhook_name,
                    item.retry_attempt + 1,
                    "Retry handler returned False",
                    item.priority,
                )

        self.stats["total_retries"] += len(ready_items)

    async def _process_retry_item(self, item: WebhookRetryItem, semaphore) -> bool:
        """Process a single retry item.

        Args:
            item: Retry item to process
            semaphore: Concurrency control semaphore

        Returns:
            True if successful, False otherwise
        """
        async with semaphore:
            try:
                # Add to current retries set
                self.current_retries.add(item.event_id)

                # Get the webhook event from storage
                event_data = self.storage.get_webhook_event(item.event_id)
                if not event_data:
                    logger.error(f"Webhook event not found: {item.event_id}")
                    return False

                # Import here to avoid circular imports
                from leadfactory.webhooks.webhook_validator import (
                    WebhookEvent,
                    WebhookStatus,
                )

                # Convert to WebhookEvent
                event = WebhookEvent(**event_data)
                event.status = WebhookStatus.RETRYING
                event.retry_count = item.retry_attempt

                # Get circuit breaker
                circuit_breaker = self.webhook_circuit_breakers.get(item.webhook_name)

                # Process the event
                success = False
                try:
                    # Import the webhook validator to process
                    from leadfactory.webhooks.webhook_validator import WebhookValidator

                    validator = WebhookValidator()
                    success = validator._process_event_handlers(event)

                    # Record success/failure in circuit breaker
                    if circuit_breaker:
                        if success:
                            circuit_breaker.record_success()
                        else:
                            circuit_breaker.record_failure()

                    # Update event status
                    if success:
                        event.status = WebhookStatus.COMPLETED
                        event.processed_at = datetime.utcnow()
                    else:
                        event.status = WebhookStatus.FAILED

                    # Update in storage
                    self.storage.update_webhook_event(item.event_id, event.to_dict())

                    return success

                except Exception as e:
                    logger.error(
                        f"Error processing retry for event {item.event_id}: {e}"
                    )

                    # Record failure in circuit breaker
                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    # Update event status
                    event.status = WebhookStatus.FAILED
                    event.last_error = str(e)
                    self.storage.update_webhook_event(item.event_id, event.to_dict())

                    return False

            finally:
                # Remove from current retries set
                self.current_retries.discard(item.event_id)

    def pause_queue(self):
        """Pause the retry queue processing."""
        self.queue_status = RetryQueueStatus.PAUSED
        logger.info("Paused retry queue processing")

    def resume_queue(self):
        """Resume the retry queue processing."""
        if self.queue_status == RetryQueueStatus.PAUSED:
            self.queue_status = RetryQueueStatus.RUNNING
            logger.info("Resumed retry queue processing")

    def stop_queue(self):
        """Stop the retry queue processing."""
        self.queue_status = RetryQueueStatus.STOPPED
        logger.info("Stopped retry queue processing")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get retry queue statistics."""
        circuit_breaker_stats = {}
        for name, cb in self.webhook_circuit_breakers.items():
            circuit_breaker_stats[name] = cb.get_stats()

        return {
            **self.stats,
            "queue_status": self.queue_status.value,
            "current_retries": len(self.current_retries),
            "circuit_breakers": circuit_breaker_stats,
            "webhook_configs": {
                name: {
                    "max_attempts": config.max_attempts,
                    "base_delay": config.base_delay,
                    "max_delay": config.max_delay,
                    "backoff_strategy": config.backoff_strategy.value,
                }
                for name, config in self.webhook_retry_configs.items()
            },
        }

    def get_priority_distribution(self) -> Dict[str, int]:
        """Get distribution of items by priority in the queue."""
        distribution = {priority.name: 0 for priority in WebhookPriority}

        for item in self.retry_queue:
            distribution[item.priority.name] += 1

        return distribution

    def clear_queue(self, webhook_name: Optional[str] = None):
        """Clear the retry queue.

        Args:
            webhook_name: Optional webhook name to filter by
        """
        if webhook_name:
            # Remove items for specific webhook
            self.retry_queue = [
                item for item in self.retry_queue if item.webhook_name != webhook_name
            ]
            # Re-heapify after modification
            heapq.heapify(self.retry_queue)
            logger.info(f"Cleared retry queue for webhook: {webhook_name}")
        else:
            # Clear entire queue
            self.retry_queue.clear()
            logger.info("Cleared entire retry queue")

        self.stats["items_in_queue"] = len(self.retry_queue)

    def force_retry_event(
        self, event_id: str, priority: WebhookPriority = WebhookPriority.HIGH
    ) -> bool:
        """Force immediate retry of a specific event.

        Args:
            event_id: Event ID to retry
            priority: Priority for the retry

        Returns:
            True if scheduled successfully
        """
        try:
            # Get event data
            event_data = self.storage.get_webhook_event(event_id)
            if not event_data:
                logger.error(f"Event not found: {event_id}")
                return False

            # Schedule immediate retry
            retry_item = WebhookRetryItem(
                event_id=event_id,
                webhook_name=event_data.get("webhook_name", "unknown"),
                retry_attempt=event_data.get("retry_count", 0) + 1,
                next_retry_time=datetime.utcnow(),  # Immediate
                priority=priority,
            )

            heapq.heappush(self.retry_queue, retry_item)
            self.stats["items_in_queue"] = len(self.retry_queue)

            logger.info(f"Forced immediate retry for event {event_id}")
            return True

        except Exception as e:
            logger.error(f"Error forcing retry for event {event_id}: {e}")
            return False
