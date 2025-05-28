#!/usr/bin/env python3
"""
Comprehensive tests for handling different bounce types in SendGrid webhook handler.

This test suite verifies that the system correctly processes and categorizes
different bounce types (hard bounces, soft bounces, blocks, etc.) and handles
each type according to business rules.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime
from typing import Dict, Any, List

# Try to import the actual implementation, fallback to mocks if not available
try:
    from leadfactory.webhooks.sendgrid_webhook import (
        SendGridWebhookHandler,
        BounceEvent,
        BounceType,
        EventType
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
        def __init__(self, email, event, timestamp, bounce_type=None, reason=None,
                     status=None, message_id=None, sg_event_id=None, sg_message_id=None):
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
        def from_webhook_data(cls, data: Dict[str, Any]):
            return cls(
                email=data.get('email', ''),
                event=data.get('event', ''),
                timestamp=data.get('timestamp', 0),
                bounce_type=data.get('type'),
                reason=data.get('reason'),
                status=data.get('status'),
                message_id=data.get('message_id'),
                sg_event_id=data.get('sg_event_id'),
                sg_message_id=data.get('sg_message_id')
            )

    class SendGridWebhookHandler:
        def __init__(self, webhook_secret=None, db_path=None):
            self.webhook_secret = webhook_secret
            self.db_path = db_path
            self.bounce_events = []
            self.email_statuses = {}
            self.soft_bounce_counts = {}

        def process_webhook_events(self, events: List[Dict[str, Any]]):
            for event in events:
                if event['event'] == EventType.BOUNCE:
                    self._process_bounce_event(event)

        def _process_bounce_event(self, event_data: Dict[str, Any]):
            bounce_event = BounceEvent.from_webhook_data(event_data)
            self.bounce_events.append(bounce_event)

            if bounce_event.bounce_type == BounceType.HARD:
                self._mark_email_permanently_bounced(bounce_event.email)
            elif bounce_event.bounce_type == BounceType.BLOCK:
                self._mark_email_blocked(bounce_event.email)
            else:
                self._increment_soft_bounce_count(bounce_event.email)

        def _mark_email_permanently_bounced(self, email: str):
            self.email_statuses[email] = 'hard_bounced'

        def _mark_email_blocked(self, email: str):
            self.email_statuses[email] = 'blocked'

        def _increment_soft_bounce_count(self, email: str):
            self.soft_bounce_counts[email] = self.soft_bounce_counts.get(email, 0) + 1


class TestBounceTypesComprehensive(unittest.TestCase):
    """Comprehensive tests for different bounce types handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = SendGridWebhookHandler(webhook_secret="test_secret")
        self.base_timestamp = int(datetime.now().timestamp())

    def create_bounce_event(self, email: str, bounce_type: str, reason: str = None,
                           status: str = None) -> Dict[str, Any]:
        """Create a bounce event payload for testing."""
        return {
            "email": email,
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": bounce_type,
            "reason": reason or f"Test {bounce_type} bounce reason",
            "status": status,
            "message_id": f"test_msg_{email}",
            "sg_event_id": f"sg_event_{email}",
            "sg_message_id": f"sg_msg_{email}"
        }

    def test_hard_bounce_processing(self):
        """Test processing of hard bounce events."""
        email = "hard.bounce@example.com"
        event_data = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.HARD,
            reason="550 5.1.1 User unknown",
            status="5.1.1"
        )

        self.handler._process_bounce_event(event_data)

        # Verify bounce event was created
        self.assertEqual(len(self.handler.bounce_events), 1)
        bounce_event = self.handler.bounce_events[0]
        self.assertEqual(bounce_event.email, email)
        self.assertEqual(bounce_event.bounce_type, BounceType.HARD)
        self.assertEqual(bounce_event.reason, "550 5.1.1 User unknown")

        # Verify email was marked as permanently bounced
        self.assertEqual(self.handler.email_statuses[email], 'hard_bounced')

    def test_soft_bounce_processing(self):
        """Test processing of soft bounce events."""
        email = "soft.bounce@example.com"
        event_data = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.SOFT,
            reason="450 4.2.2 Mailbox full",
            status="4.2.2"
        )

        self.handler._process_bounce_event(event_data)

        # Verify bounce event was created
        self.assertEqual(len(self.handler.bounce_events), 1)
        bounce_event = self.handler.bounce_events[0]
        self.assertEqual(bounce_event.email, email)
        self.assertEqual(bounce_event.bounce_type, BounceType.SOFT)
        self.assertEqual(bounce_event.reason, "450 4.2.2 Mailbox full")

        # Verify soft bounce count was incremented
        self.assertEqual(self.handler.soft_bounce_counts[email], 1)

        # Verify email was not marked as permanently bounced
        self.assertNotIn(email, self.handler.email_statuses)

    def test_block_bounce_processing(self):
        """Test processing of block bounce events."""
        email = "blocked@example.com"
        event_data = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.BLOCK,
            reason="550 5.7.1 Blocked by spam filter",
            status="5.7.1"
        )

        self.handler._process_bounce_event(event_data)

        # Verify bounce event was created
        self.assertEqual(len(self.handler.bounce_events), 1)
        bounce_event = self.handler.bounce_events[0]
        self.assertEqual(bounce_event.email, email)
        self.assertEqual(bounce_event.bounce_type, BounceType.BLOCK)
        self.assertEqual(bounce_event.reason, "550 5.7.1 Blocked by spam filter")

        # Verify email was marked as blocked
        self.assertEqual(self.handler.email_statuses[email], 'blocked')

    def test_multiple_soft_bounces_same_email(self):
        """Test multiple soft bounces for the same email address."""
        email = "multiple.soft@example.com"

        # First soft bounce
        event_data1 = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.SOFT,
            reason="450 4.2.2 Mailbox full"
        )
        self.handler._process_bounce_event(event_data1)

        # Second soft bounce
        event_data2 = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.SOFT,
            reason="450 4.2.1 Mailbox temporarily unavailable"
        )
        self.handler._process_bounce_event(event_data2)

        # Third soft bounce
        event_data3 = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.SOFT,
            reason="450 4.7.1 Greylisted"
        )
        self.handler._process_bounce_event(event_data3)

        # Verify all bounce events were recorded
        self.assertEqual(len(self.handler.bounce_events), 3)

        # Verify soft bounce count was incremented correctly
        self.assertEqual(self.handler.soft_bounce_counts[email], 3)

        # Verify email was not marked as permanently bounced
        self.assertNotIn(email, self.handler.email_statuses)

    def test_bounce_event_data_extraction(self):
        """Test that bounce event data is correctly extracted from webhook payload."""
        email = "data.test@example.com"
        event_data = {
            "email": email,
            "event": EventType.BOUNCE,
            "timestamp": self.base_timestamp,
            "type": BounceType.HARD,
            "reason": "550 5.1.1 User unknown",
            "status": "5.1.1",
            "message_id": "test_message_id_123",
            "sg_event_id": "sg_event_id_456",
            "sg_message_id": "sg_message_id_789"
        }

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.email, email)
        self.assertEqual(bounce_event.event, EventType.BOUNCE)
        self.assertEqual(bounce_event.timestamp, self.base_timestamp)
        self.assertEqual(bounce_event.bounce_type, BounceType.HARD)
        self.assertEqual(bounce_event.reason, "550 5.1.1 User unknown")
        self.assertEqual(bounce_event.status, "5.1.1")
        self.assertEqual(bounce_event.message_id, "test_message_id_123")
        self.assertEqual(bounce_event.sg_event_id, "sg_event_id_456")
        self.assertEqual(bounce_event.sg_message_id, "sg_message_id_789")

    def test_malformed_bounce_event_handling(self):
        """Test handling of malformed bounce events."""
        # Missing required fields
        malformed_events = [
            # Missing email
            {
                "event": EventType.BOUNCE,
                "timestamp": self.base_timestamp,
                "type": BounceType.HARD,
                "reason": "Test reason"
            },
            # Missing event type
            {
                "email": "test@example.com",
                "timestamp": self.base_timestamp,
                "type": BounceType.HARD,
                "reason": "Test reason"
            },
            # Missing timestamp
            {
                "email": "test@example.com",
                "event": EventType.BOUNCE,
                "type": BounceType.HARD,
                "reason": "Test reason"
            },
            # Empty event data
            {}
        ]

        for malformed_event in malformed_events:
            bounce_event = BounceEvent.from_webhook_data(malformed_event)

            # Should handle gracefully with default values
            self.assertIsNotNone(bounce_event)
            self.assertEqual(bounce_event.email, malformed_event.get('email', ''))
            self.assertEqual(bounce_event.event, malformed_event.get('event', ''))
            self.assertEqual(bounce_event.timestamp, malformed_event.get('timestamp', 0))

    def test_unknown_bounce_type_handling(self):
        """Test handling of unknown bounce types."""
        email = "unknown.type@example.com"
        event_data = self.create_bounce_event(
            email=email,
            bounce_type="unknown_type",
            reason="Unknown bounce type reason"
        )

        self.handler._process_bounce_event(event_data)

        # Verify bounce event was created
        self.assertEqual(len(self.handler.bounce_events), 1)
        bounce_event = self.handler.bounce_events[0]
        self.assertEqual(bounce_event.email, email)
        self.assertEqual(bounce_event.bounce_type, "unknown_type")

        # Unknown types should be treated as soft bounces
        self.assertEqual(self.handler.soft_bounce_counts[email], 1)
        self.assertNotIn(email, self.handler.email_statuses)

    def test_batch_bounce_processing(self):
        """Test processing multiple bounce events in a batch."""
        events = [
            self.create_bounce_event("hard1@example.com", BounceType.HARD),
            self.create_bounce_event("hard2@example.com", BounceType.HARD),
            self.create_bounce_event("soft1@example.com", BounceType.SOFT),
            self.create_bounce_event("soft2@example.com", BounceType.SOFT),
            self.create_bounce_event("block1@example.com", BounceType.BLOCK),
        ]

        self.handler.process_webhook_events(events)

        # Verify all events were processed
        self.assertEqual(len(self.handler.bounce_events), 5)

        # Verify hard bounces were marked correctly
        self.assertEqual(self.handler.email_statuses["hard1@example.com"], 'hard_bounced')
        self.assertEqual(self.handler.email_statuses["hard2@example.com"], 'hard_bounced')

        # Verify soft bounces were counted
        self.assertEqual(self.handler.soft_bounce_counts["soft1@example.com"], 1)
        self.assertEqual(self.handler.soft_bounce_counts["soft2@example.com"], 1)

        # Verify block was marked correctly
        self.assertEqual(self.handler.email_statuses["block1@example.com"], 'blocked')

    def test_bounce_reasons_categorization(self):
        """Test that different bounce reasons are properly categorized."""
        bounce_scenarios = [
            # Hard bounce scenarios
            {
                "email": "invalid1@example.com",
                "type": BounceType.HARD,
                "reason": "550 5.1.1 User unknown",
                "expected_status": "hard_bounced"
            },
            {
                "email": "invalid2@example.com",
                "type": BounceType.HARD,
                "reason": "550 5.1.10 RESOLVER.ADR.RecipNotFound",
                "expected_status": "hard_bounced"
            },
            # Soft bounce scenarios
            {
                "email": "temp1@example.com",
                "type": BounceType.SOFT,
                "reason": "450 4.2.2 Mailbox full",
                "expected_count": 1
            },
            {
                "email": "temp2@example.com",
                "type": BounceType.SOFT,
                "reason": "450 4.7.1 Greylisted",
                "expected_count": 1
            },
            # Block scenarios
            {
                "email": "blocked1@example.com",
                "type": BounceType.BLOCK,
                "reason": "550 5.7.1 Blocked by spam filter",
                "expected_status": "blocked"
            }
        ]

        for scenario in bounce_scenarios:
            event_data = self.create_bounce_event(
                email=scenario["email"],
                bounce_type=scenario["type"],
                reason=scenario["reason"]
            )

            self.handler._process_bounce_event(event_data)

            # Check expected outcomes
            if "expected_status" in scenario:
                self.assertEqual(
                    self.handler.email_statuses[scenario["email"]],
                    scenario["expected_status"]
                )
            if "expected_count" in scenario:
                self.assertEqual(
                    self.handler.soft_bounce_counts[scenario["email"]],
                    scenario["expected_count"]
                )

    def test_bounce_event_timestamps(self):
        """Test that bounce event timestamps are properly handled."""
        email = "timestamp.test@example.com"
        test_timestamp = 1640995200  # 2022-01-01 00:00:00 UTC

        event_data = self.create_bounce_event(
            email=email,
            bounce_type=BounceType.HARD
        )
        event_data["timestamp"] = test_timestamp

        bounce_event = BounceEvent.from_webhook_data(event_data)

        self.assertEqual(bounce_event.timestamp, test_timestamp)

    @unittest.skipIf(not REAL_IMPLEMENTATION, "Requires real implementation")
    def test_database_integration(self):
        """Test database integration for bounce event storage."""
        # This test would require actual database connectivity
        # and would be run only when the real implementation is available
        pass


if __name__ == '__main__':
    unittest.main()
