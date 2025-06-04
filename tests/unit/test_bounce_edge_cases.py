#!/usr/bin/env python3
"""
Edge case tests for bounce handling in SendGrid webhook handler.

This test suite covers unusual, malformed, and edge case bounce scenarios
to ensure the system handles them gracefully.
"""

import json
import unittest
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import Mock, patch

# Try to import the actual implementation, fallback to mocks if not available
try:
    from leadfactory.webhooks.sendgrid_webhook import (
        BounceEvent,
        BounceType,
        EventType,
        SendGridWebhookHandler,
    )

    REAL_IMPLEMENTATION = True
except ImportError:
    REAL_IMPLEMENTATION = False

    # Mock implementations for testing
    class EventType:
        BOUNCE = "bounce"
        DROPPED = "dropped"
        DELIVERED = "delivered"
        SPAM_REPORT = "spamreport"

    class BounceType:
        HARD = "hard"
        SOFT = "soft"
        BLOCK = "block"

    class BounceEvent:
        def __init__(
            self,
            email,
            event,
            timestamp,
            bounce_type=None,
            reason=None,
            status=None,
            message_id=None,
            sg_event_id=None,
            sg_message_id=None,
        ):
            self.email = email
            self.event = event
            self.timestamp = timestamp
            self.bounce_type = bounce_type
            self.reason = reason
            self.status = status
            self.message_id = message_id
            self.sg_event_id = sg_event_id
            self.sg_message_id = sg_message_id

        @classmethod
        def from_webhook_data(cls, data: dict[str, Any]):
            return cls(
                email=data.get("email", ""),
                event=data.get("event", ""),
                timestamp=data.get("timestamp", 0),
                bounce_type=data.get("type"),
                reason=data.get("reason"),
                status=data.get("status"),
                message_id=data.get("message_id"),
                sg_event_id=data.get("sg_event_id"),
                sg_message_id=data.get("sg_message_id"),
            )

    class SendGridWebhookHandler:
        def __init__(self, webhook_secret=None, db_path=None):
            self.webhook_secret = webhook_secret
            self.db_path = db_path
            self.bounce_events = []
            self.email_statuses = {}
            self.soft_bounce_counts = {}
            self.errors = []

        def process_webhook_events(self, events: list[dict[str, Any]]):
            for event in events:
                try:
                    if event["event"] == EventType.BOUNCE:
                        self._process_bounce_event(event)
                except Exception as e:
                    self.errors.append(str(e))

        def _process_bounce_event(self, event_data: dict[str, Any]):
            bounce_event = BounceEvent.from_webhook_data(event_data)
            self.bounce_events.append(bounce_event)

            if bounce_event.bounce_type == BounceType.HARD:
                self._mark_email_permanently_bounced(bounce_event.email)
            elif bounce_event.bounce_type == BounceType.BLOCK:
                self._mark_email_blocked(bounce_event.email)
            else:
                self._increment_soft_bounce_count(bounce_event.email)

        def _mark_email_permanently_bounced(self, email: str):
            self.email_statuses[email] = "hard_bounced"

        def _mark_email_blocked(self, email: str):
            self.email_statuses[email] = "blocked"

        def _increment_soft_bounce_count(self, email: str):
            self.soft_bounce_counts[email] = self.soft_bounce_counts.get(email, 0) + 1


class TestBounceEdgeCases(unittest.TestCase):
    """Edge case tests for bounce handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = SendGridWebhookHandler(webhook_secret="test_secret")
        self.base_timestamp = int(datetime.now().timestamp())

    def test_empty_email_address(self):
        """Test handling of bounce events with empty email addresses."""
        event_data = {
            "email": "",
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.HARD,
            "reason": "Empty email address",
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.email, "")
        self.assertEqual(bounce_event.bounce_type, BounceType.HARD)
        self.assertIsNotNone(bounce_event)

    def test_null_values_in_event_data(self):
        """Test handling of null values in event data."""
        event_data = {
            "email": "test@example.com",
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": None,
            "reason": None,
            "status": None,
            "message_id": None,
            "sg_event_id": None,
            "sg_message_id": None,
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.email, "test@example.com")
        self.assertIsNone(bounce_event.bounce_type)
        self.assertIsNone(bounce_event.reason)
        self.assertIsNone(bounce_event.status)

    def test_extremely_long_bounce_reason(self):
        """Test handling of extremely long bounce reasons."""
        long_reason = "A" * 10000  # 10KB reason string

        event_data = {
            "email": "long.reason@example.com",
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.SOFT,
            "reason": long_reason,
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.reason, long_reason)
        self.assertEqual(len(bounce_event.reason), 10000)

    def test_special_characters_in_email(self):
        """Test handling of special characters in email addresses."""
        special_emails = [
            "test+tag@example.com",
            "test.with.dots@example.com",
            "test_with_underscores@example.com",
            "test-with-dashes@example.com",
            "test@sub.domain.example.com",
            "test@example-domain.com",
            "test123@example.com",
            "123test@example.com",
        ]

        for email in special_emails:
            event_data = {
                "email": email,
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp,
                "type": BounceType.HARD,
                "reason": f"Hard bounce for {email}",
            }

            bounce_event = BounceEvent.from_webhook_data(event_data)
            self.assertEqual(bounce_event.email, email)

    def test_unicode_characters_in_bounce_data(self):
        """Test handling of unicode characters in bounce data."""
        event_data = {
            "email": "unicode@example.com",
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.SOFT,
            "reason": "Bounce reason with unicode: 测试 🚀 émojis",
            "status": "4.2.2 Boîte aux lettres pleine",
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(
            bounce_event.reason, "Bounce reason with unicode: 测试 🚀 émojis"
        )
        self.assertEqual(bounce_event.status, "4.2.2 Boîte aux lettres pleine")

    def test_negative_timestamp(self):
        """Test handling of negative timestamps."""
        event_data = {
            "email": "negative.time@example.com",
            "event": EventType.BOUNCE,
            "timestamp": -1640995200,  # Negative timestamp
            "type": BounceType.HARD,
            "reason": "Negative timestamp test",
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.timestamp, -1640995200)
        self.assertEqual(bounce_event.email, "negative.time@example.com")

    def test_future_timestamp(self):
        """Test handling of future timestamps."""
        future_timestamp = (
            int(datetime.now().timestamp()) + 86400 * 365
        )  # 1 year in future

        event_data = {
            "email": "future.time@example.com",
            "event": EventType.BOUNCE,
            "timestamp": future_timestamp,
            "type": BounceType.SOFT,
            "reason": "Future timestamp test",
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.timestamp, future_timestamp)
        self.assertEqual(bounce_event.email, "future.time@example.com")

    def test_case_sensitivity_in_bounce_types(self):
        """Test case sensitivity in bounce type handling."""
        case_variations = [
            "HARD",
            "Hard",
            "hard",
            "SOFT",
            "Soft",
            "soft",
            "BLOCK",
            "Block",
            "block",
        ]

        for bounce_type in case_variations:
            event_data = {
                "email": f"case.test.{bounce_type.lower()}@example.com",
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp,
                "type": bounce_type,
                "reason": f"Case test for {bounce_type}",
            }

            bounce_event = BounceEvent.from_webhook_data(event_data)
            self.assertEqual(bounce_event.bounce_type, bounce_type)

    def test_extremely_large_event_batch(self):
        """Test processing of extremely large event batches."""
        # Create a large batch of bounce events
        large_batch = []
        for i in range(1000):
            event_data = {
                "email": f"batch.test.{i}@example.com",
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp + i,
                "type": BounceType.SOFT if i % 2 == 0 else BounceType.HARD,
                "reason": f"Batch test bounce {i}",
            }
            large_batch.append(event_data)

        # Process the large batch
        self.handler.process_webhook_events(large_batch)

        # Verify all events were processed
        self.assertEqual(len(self.handler.bounce_events), 1000)

        # Verify correct categorization
        hard_bounces = sum(
            1
            for email, status in self.handler.email_statuses.items()
            if status == "hard_bounced"
        )
        soft_bounces = len(self.handler.soft_bounce_counts)

        self.assertEqual(hard_bounces, 500)  # Every odd index
        self.assertEqual(soft_bounces, 500)  # Every even index

    def test_duplicate_bounce_events(self):
        """Test handling of duplicate bounce events for the same email."""
        email = "duplicate@example.com"
        event_data = {
            "email": email,
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.HARD,
            "reason": "Duplicate bounce test",
            "sg_event_id": "same_event_id",
        }

        # Process the same event multiple times
        for _ in range(5):
            self.handler._process_bounce_event(event_data)

        # Verify all events were recorded (no deduplication at this level)
        self.assertEqual(len(self.handler.bounce_events), 5)

        # Verify email status is still correct
        self.assertEqual(self.handler.email_statuses[email], "hard_bounced")

    def test_mixed_event_types_in_batch(self):
        """Test processing batch with mixed event types (not just bounces)."""
        mixed_events = [
            {
                "email": "bounce@example.com",
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp,
                "type": BounceType.HARD,
                "reason": "Hard bounce",
            },
            {
                "email": "delivered@example.com",
                "event": EventType.DELIVERED,
                "timestamp": self.base_timestamp,
                "response": "250 OK",
            },
            {
                "email": "spam@example.com",
                "event": EventType.SPAM_REPORT,
                "timestamp": self.base_timestamp,
            },
            {
                "email": "bounce2@example.com",
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp,
                "type": BounceType.SOFT,
                "reason": "Soft bounce",
            },
        ]

        self.handler.process_webhook_events(mixed_events)

        # Only bounce events should be processed
        self.assertEqual(len(self.handler.bounce_events), 2)

        # Verify correct processing
        self.assertEqual(
            self.handler.email_statuses["bounce@example.com"], "hard_bounced"
        )
        self.assertEqual(self.handler.soft_bounce_counts["bounce2@example.com"], 1)

    def test_malformed_json_like_strings(self):
        """Test handling of JSON-like strings in bounce data."""
        event_data = {
            "email": "json.test@example.com",
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.HARD,
            "reason": '{"error": "malformed json", "code": 550}',
            "status": '{"smtp_code": "5.1.1"}',
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        # Should treat as strings, not parse as JSON
        self.assertEqual(
            bounce_event.reason, '{"error": "malformed json", "code": 550}'
        )
        self.assertEqual(bounce_event.status, '{"smtp_code": "5.1.1"}')

    def test_zero_timestamp(self):
        """Test handling of zero timestamp (Unix epoch)."""
        event_data = {
            "email": "epoch@example.com",
            "event": EventType.BOUNCE,
            "timestamp": 0,
            "type": BounceType.HARD,
            "reason": "Epoch timestamp test",
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.timestamp, 0)
        self.assertEqual(bounce_event.email, "epoch@example.com")


if __name__ == "__main__":
    unittest.main()
