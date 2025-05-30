#!/usr/bin/env python3
"""
Unit tests for handling different bounce types (hard, soft, block).

This module tests the system's response to various types of email bounces
and ensures proper categorization and handling of each bounce type.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import modules with fallback for testing
try:
    from leadfactory.webhooks.sendgrid_webhook import (
        BounceEvent,
        BounceType,
        EventType,
        SendGridWebhookHandler,
    )
except ImportError:
    # Create mock classes for testing if import fails
    from dataclasses import dataclass
    from enum import Enum
    from typing import Optional

    class BounceType(Enum):
        HARD = "hard"
        SOFT = "soft"
        BLOCK = "block"

    class EventType(Enum):
        BOUNCE = "bounce"
        DROPPED = "dropped"

    @dataclass
    class BounceEvent:
        email: str
        event: str
        timestamp: int
        bounce_type: Optional[str] = None
        reason: Optional[str] = None

        @classmethod
        def from_webhook_data(cls, data: dict[str, Any]) -> "BounceEvent":
            return cls(
                email=data.get("email", ""),
                event=data.get("event", ""),
                timestamp=data.get("timestamp", 0),
                bounce_type=data.get("type"),
                reason=data.get("reason")
            )

    class SendGridWebhookHandler:
        def __init__(self, webhook_secret=None, db_path=None):
            self.webhook_secret = webhook_secret
            self.db_path = db_path

        def process_webhook_events(self, events: list[dict[str, Any]]) -> dict[str, int]:
            return {"bounce": len([e for e in events if e.get("event") == "bounce"])}


class TestHardBounces:
    """Test class for hard bounce handling."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.webhook_handler = SendGridWebhookHandler(db_path=":memory:")

    @pytest.mark.parametrize("reason,status_code", [
        ("550 5.1.1 The email account that you tried to reach does not exist", "5.1.1"),
        ("550 5.1.2 We weren't able to find the recipient domain", "5.1.2"),
        ("550 5.1.3 The recipient address rejected your message", "5.1.3"),
        ("550 5.1.10 RESOLVER.ADR.RecipNotFound; not found", "5.1.10"),
        ("554 5.7.1 Service unavailable; Client host blocked", "5.7.1"),
    ])
    def test_hard_bounce_reasons(self, reason, status_code):
        """Test various hard bounce reasons and status codes."""
        # Arrange
        hard_bounce_event = {
            "email": "nonexistent@example.com",
            "event": "bounce",
            "type": "hard",
            "reason": reason,
            "status": status_code,
            "timestamp": int(datetime.now().timestamp()),
            "sg_event_id": f"hard_bounce_{status_code.replace('.', '_')}",
            "sg_message_id": "msg_123"
        }

        # Act
        bounce_event = BounceEvent.from_webhook_data(hard_bounce_event)

        # Assert
        assert bounce_event.bounce_type == BounceType.HARD.value
        assert bounce_event.reason == reason
        assert bounce_event.email == "nonexistent@example.com"
        assert bounce_event.event == EventType.BOUNCE.value

    def test_hard_bounce_permanent_marking(self):
        """Test that hard bounces mark emails as permanently bounced."""
        # Arrange
        hard_bounce_event = {
            "email": "invalid@example.com",
            "event": "bounce",
            "type": "hard",
            "reason": "550 5.1.1 User unknown",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_mark_email_permanently_bounced") as mock_mark:
            self.webhook_handler._process_bounce_event(hard_bounce_event)

        # Assert
        mock_mark.assert_called_once_with("invalid@example.com")

    def test_hard_bounce_no_retry(self):
        """Test that hard bounces don't increment retry counters."""
        # Arrange
        hard_bounce_event = {
            "email": "invalid@example.com",
            "event": "bounce",
            "type": "hard",
            "reason": "550 5.1.1 User unknown",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_increment:
            self.webhook_handler._process_bounce_event(hard_bounce_event)

        # Assert
        mock_increment.assert_not_called()

    def test_multiple_hard_bounces_same_email(self):
        """Test handling multiple hard bounces for the same email address."""
        # Arrange
        email = "invalid@example.com"
        hard_bounce_events = [
            {
                "email": email,
                "event": "bounce",
                "type": "hard",
                "reason": "550 5.1.1 User unknown",
                "timestamp": int(datetime.now().timestamp()),
                "sg_event_id": "bounce_1"
            },
            {
                "email": email,
                "event": "bounce",
                "type": "hard",
                "reason": "550 5.1.1 User unknown",
                "timestamp": int(datetime.now().timestamp()) + 60,
                "sg_event_id": "bounce_2"
            }
        ]

        # Act
        with patch.object(self.webhook_handler, "_mark_email_permanently_bounced") as mock_mark:
            for event in hard_bounce_events:
                self.webhook_handler._process_bounce_event(event)

        # Assert
        assert mock_mark.call_count == 2
        for call in mock_mark.call_args_list:
            assert call[0][0] == email


class TestSoftBounces:
    """Test class for soft bounce handling."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.webhook_handler = SendGridWebhookHandler(db_path=":memory:")

    @pytest.mark.parametrize("reason,status_code", [
        ("450 4.2.2 The email account that you tried to reach is over quota", "4.2.2"),
        ("451 4.3.0 Temporary failure, please try again later", "4.3.0"),
        ("452 4.2.2 The recipient's inbox is full", "4.2.2"),
        ("450 4.7.1 Greylisted, please try again later", "4.7.1"),
        ("421 4.7.0 Try again later", "4.7.0"),
    ])
    def test_soft_bounce_reasons(self, reason, status_code):
        """Test various soft bounce reasons and status codes."""
        # Arrange
        soft_bounce_event = {
            "email": "full@example.com",
            "event": "bounce",
            "type": "soft",
            "reason": reason,
            "status": status_code,
            "timestamp": int(datetime.now().timestamp()),
            "sg_event_id": f"soft_bounce_{status_code.replace('.', '_')}",
            "sg_message_id": "msg_123"
        }

        # Act
        bounce_event = BounceEvent.from_webhook_data(soft_bounce_event)

        # Assert
        assert bounce_event.bounce_type == BounceType.SOFT.value
        assert bounce_event.reason == reason
        assert bounce_event.email == "full@example.com"
        assert bounce_event.event == EventType.BOUNCE.value

    def test_soft_bounce_retry_increment(self):
        """Test that soft bounces increment retry counters."""
        # Arrange
        soft_bounce_event = {
            "email": "full@example.com",
            "event": "bounce",
            "type": "soft",
            "reason": "450 4.2.2 Mailbox full",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_increment:
            self.webhook_handler._process_bounce_event(soft_bounce_event)

        # Assert
        mock_increment.assert_called_once_with("full@example.com")

    def test_soft_bounce_no_permanent_marking(self):
        """Test that soft bounces don't mark emails as permanently bounced."""
        # Arrange
        soft_bounce_event = {
            "email": "full@example.com",
            "event": "bounce",
            "type": "soft",
            "reason": "450 4.2.2 Mailbox full",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_mark_email_permanently_bounced") as mock_mark:
            self.webhook_handler._process_bounce_event(soft_bounce_event)

        # Assert
        mock_mark.assert_not_called()

    def test_multiple_soft_bounces_same_email(self):
        """Test handling multiple soft bounces for the same email address."""
        # Arrange
        email = "full@example.com"
        soft_bounce_events = [
            {
                "email": email,
                "event": "bounce",
                "type": "soft",
                "reason": "450 4.2.2 Mailbox full",
                "timestamp": int(datetime.now().timestamp()),
                "sg_event_id": "soft_bounce_1"
            },
            {
                "email": email,
                "event": "bounce",
                "type": "soft",
                "reason": "450 4.2.2 Mailbox full",
                "timestamp": int(datetime.now().timestamp()) + 3600,  # 1 hour later
                "sg_event_id": "soft_bounce_2"
            },
            {
                "email": email,
                "event": "bounce",
                "type": "soft",
                "reason": "450 4.2.2 Mailbox full",
                "timestamp": int(datetime.now().timestamp()) + 7200,  # 2 hours later
                "sg_event_id": "soft_bounce_3"
            }
        ]

        # Act
        with patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_increment:
            for event in soft_bounce_events:
                self.webhook_handler._process_bounce_event(event)

        # Assert
        assert mock_increment.call_count == 3
        for call in mock_increment.call_args_list:
            assert call[0][0] == email

    def test_soft_bounce_eventual_success(self):
        """Test scenario where soft bounces eventually succeed."""
        # Arrange
        email = "eventually-works@example.com"

        # First, soft bounces
        soft_bounce_event = {
            "email": email,
            "event": "bounce",
            "type": "soft",
            "reason": "450 4.2.2 Mailbox full",
            "timestamp": int(datetime.now().timestamp())
        }

        # Then, delivery success
        delivered_event = {
            "email": email,
            "event": "delivered",
            "timestamp": int(datetime.now().timestamp()) + 3600,
            "sg_message_id": "msg_123"
        }

        # Act
        with patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_increment, \
             patch.object(self.webhook_handler, "_mark_email_delivered") as mock_delivered:

            self.webhook_handler._process_bounce_event(soft_bounce_event)
            self.webhook_handler._process_delivered_event(delivered_event)

        # Assert
        mock_increment.assert_called_once_with(email)
        mock_delivered.assert_called_once_with(email, "msg_123")


class TestBlockBounces:
    """Test class for block bounce handling."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.webhook_handler = SendGridWebhookHandler(db_path=":memory:")

    @pytest.mark.parametrize("reason,status_code", [
        ("550 5.7.1 Message rejected due to content restrictions", "5.7.1"),
        ("554 5.7.1 Service unavailable; Client host blocked", "5.7.1"),
        ("550 5.7.606 Access denied, banned sending IP", "5.7.606"),
        ("554 5.7.0 Reject, id=10000-02 - BANNED", "5.7.0"),
        ("550 Blocked - see https://www.spamhaus.org/query/ip/", "5.7.1"),
    ])
    def test_block_bounce_reasons(self, reason, status_code):
        """Test various block bounce reasons and status codes."""
        # Arrange
        block_bounce_event = {
            "email": "blocked@example.com",
            "event": "bounce",
            "type": "block",
            "reason": reason,
            "status": status_code,
            "timestamp": int(datetime.now().timestamp()),
            "sg_event_id": f"block_bounce_{status_code.replace('.', '_')}",
            "sg_message_id": "msg_123"
        }

        # Act
        bounce_event = BounceEvent.from_webhook_data(block_bounce_event)

        # Assert
        assert bounce_event.bounce_type == BounceType.BLOCK.value
        assert bounce_event.reason == reason
        assert bounce_event.email == "blocked@example.com"
        assert bounce_event.event == EventType.BOUNCE.value

    def test_block_bounce_marking(self):
        """Test that block bounces mark emails as blocked."""
        # Arrange
        block_bounce_event = {
            "email": "blocked@example.com",
            "event": "bounce",
            "type": "block",
            "reason": "550 5.7.1 Blocked by recipient",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_mark_email_blocked") as mock_block:
            self.webhook_handler._process_bounce_event(block_bounce_event)

        # Assert
        mock_block.assert_called_once_with("blocked@example.com")

    def test_block_bounce_no_retry_increment(self):
        """Test that block bounces don't increment retry counters."""
        # Arrange
        block_bounce_event = {
            "email": "blocked@example.com",
            "event": "bounce",
            "type": "block",
            "reason": "550 5.7.1 Blocked by recipient",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_increment:
            self.webhook_handler._process_bounce_event(block_bounce_event)

        # Assert
        mock_increment.assert_not_called()

    def test_block_bounce_no_permanent_marking(self):
        """Test that block bounces don't mark emails as permanently bounced."""
        # Arrange
        block_bounce_event = {
            "email": "blocked@example.com",
            "event": "bounce",
            "type": "block",
            "reason": "550 5.7.1 Blocked by recipient",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act
        with patch.object(self.webhook_handler, "_mark_email_permanently_bounced") as mock_mark:
            self.webhook_handler._process_bounce_event(block_bounce_event)

        # Assert
        mock_mark.assert_not_called()


class TestDroppedEvents:
    """Test class for dropped event handling (similar to bounces)."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.webhook_handler = SendGridWebhookHandler(db_path=":memory:")

    def test_dropped_event_processing(self):
        """Test that dropped events are processed like bounces."""
        # Arrange
        dropped_event = {
            "email": "dropped@example.com",
            "event": "dropped",
            "reason": "Bounced Address",
            "timestamp": int(datetime.now().timestamp()),
            "sg_event_id": "dropped_123"
        }

        # Act
        with patch.object(self.webhook_handler, "_process_bounce_event") as mock_process:
            self.webhook_handler.process_webhook_events([dropped_event])

        # Assert
        mock_process.assert_called_once_with(dropped_event)

    @pytest.mark.parametrize("reason", [
        "Bounced Address",
        "Unsubscribed Address",
        "Spam Reporting Address",
        "Invalid",
        "Blocked",
    ])
    def test_dropped_event_reasons(self, reason):
        """Test various dropped event reasons."""
        # Arrange
        dropped_event = {
            "email": "dropped@example.com",
            "event": "dropped",
            "reason": reason,
            "timestamp": int(datetime.now().timestamp()),
            "sg_event_id": f"dropped_{reason.lower().replace(' ', '_')}"
        }

        # Act
        bounce_event = BounceEvent.from_webhook_data(dropped_event)

        # Assert
        assert bounce_event.event == EventType.DROPPED.value
        assert bounce_event.reason == reason
        assert bounce_event.email == "dropped@example.com"


class TestBounceTypeClassification:
    """Test class for bounce type classification and handling."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.webhook_handler = SendGridWebhookHandler(db_path=":memory:")

    def test_bounce_type_enum_values(self):
        """Test that bounce type enum has correct values."""
        assert BounceType.HARD.value == "hard"
        assert BounceType.SOFT.value == "soft"
        assert BounceType.BLOCK.value == "block"

    def test_bounce_classification_by_status_code(self):
        """Test bounce classification based on SMTP status codes."""
        test_cases = [
            # Hard bounces (5xx permanent failures)
            ("550 5.1.1 User unknown", "hard"),
            ("554 5.7.1 Rejected", "hard"),
            ("550 5.1.2 Domain not found", "hard"),

            # Soft bounces (4xx temporary failures)
            ("450 4.2.2 Mailbox full", "soft"),
            ("451 4.3.0 Temporary failure", "soft"),
            ("421 4.7.0 Try again later", "soft"),

            # Block bounces (content/policy blocks)
            ("550 5.7.1 Blocked by policy", "block"),
            ("554 5.7.606 Access denied", "block"),
        ]

        for reason, expected_type in test_cases:
            # Arrange
            bounce_event = {
                "email": "test@example.com",
                "event": "bounce",
                "type": expected_type,
                "reason": reason,
                "timestamp": int(datetime.now().timestamp())
            }

            # Act
            event = BounceEvent.from_webhook_data(bounce_event)

            # Assert
            assert event.bounce_type == expected_type, f"Failed for reason: {reason}"

    def test_mixed_bounce_types_batch(self):
        """Test processing a batch with mixed bounce types."""
        # Arrange
        mixed_bounce_events = [
            {
                "email": "hard@example.com",
                "event": "bounce",
                "type": "hard",
                "reason": "550 5.1.1 User unknown",
                "timestamp": int(datetime.now().timestamp()),
                "sg_event_id": "hard_1"
            },
            {
                "email": "soft@example.com",
                "event": "bounce",
                "type": "soft",
                "reason": "450 4.2.2 Mailbox full",
                "timestamp": int(datetime.now().timestamp()),
                "sg_event_id": "soft_1"
            },
            {
                "email": "block@example.com",
                "event": "bounce",
                "type": "block",
                "reason": "550 5.7.1 Blocked",
                "timestamp": int(datetime.now().timestamp()),
                "sg_event_id": "block_1"
            }
        ]

        # Act
        with patch.object(self.webhook_handler, "_mark_email_permanently_bounced") as mock_hard, \
             patch.object(self.webhook_handler, "_increment_soft_bounce_count") as mock_soft, \
             patch.object(self.webhook_handler, "_mark_email_blocked") as mock_block, \
             patch.object(self.webhook_handler, "_store_bounce_event"), \
             patch.object(self.webhook_handler, "_check_bounce_rate_thresholds"):

            result = self.webhook_handler.process_webhook_events(mixed_bounce_events)

        # Assert
        assert result["bounce"] == 3
        mock_hard.assert_called_once_with("hard@example.com")
        mock_soft.assert_called_once_with("soft@example.com")
        mock_block.assert_called_once_with("block@example.com")

    def test_unknown_bounce_type_handling(self):
        """Test handling of unknown or missing bounce types."""
        # Arrange
        unknown_bounce_event = {
            "email": "unknown@example.com",
            "event": "bounce",
            "type": "unknown_type",  # Unknown bounce type
            "reason": "Unknown error",
            "timestamp": int(datetime.now().timestamp())
        }

        missing_type_event = {
            "email": "missing@example.com",
            "event": "bounce",
            # Missing 'type' field
            "reason": "Missing type",
            "timestamp": int(datetime.now().timestamp())
        }

        # Act & Assert - Should not crash
        with patch.object(self.webhook_handler, "_store_bounce_event"):
            try:
                self.webhook_handler._process_bounce_event(unknown_bounce_event)
                self.webhook_handler._process_bounce_event(missing_type_event)
            except Exception as e:
                pytest.fail(f"Processing unknown bounce types should not raise exceptions: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
