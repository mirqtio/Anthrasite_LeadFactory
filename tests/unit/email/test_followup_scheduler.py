"""Unit tests for FollowUpScheduler."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.email.followup_scheduler import (
    FollowUpScheduler,
    FollowUpTemplate,
    FollowUpCampaign,
    ScheduledFollowUp,
    FollowUpStatus,
    EngagementLevel,
)


class TestFollowUpScheduler(unittest.TestCase):
    """Test FollowUpScheduler functionality."""

    def setUp(self):
        """Set up test environment."""
        self.scheduler = FollowUpScheduler()
        self.scheduler.storage = Mock()

    def test_create_campaign(self):
        """Test creating a follow-up campaign."""
        # Mock storage
        self.scheduler.storage.create_followup_campaign.return_value = True

        # Create campaign
        campaign_id = self.scheduler.create_campaign(
            business_id=123,
            initial_email_id="email_123",
            templates=[
                {
                    "name": "First Follow-up",
                    "subject_line": "Following up on our conversation",
                    "content": "Hi {recipient_name}, just wanted to follow up...",
                    "delay_days": 7,
                    "engagement_threshold": "low",
                },
                {
                    "name": "Second Follow-up",
                    "subject_line": "One more time",
                    "content": "Hi again, still interested in improving your website?",
                    "delay_days": 14,
                    "engagement_threshold": "medium",
                },
            ],
            max_follow_ups=2,
        )

        # Verify campaign was created
        self.assertIsNotNone(campaign_id)
        self.scheduler.storage.create_followup_campaign.assert_called_once()

        # Check the campaign data
        call_args = self.scheduler.storage.create_followup_campaign.call_args[0][0]
        self.assertEqual(call_args["business_id"], 123)
        self.assertEqual(call_args["initial_email_id"], "email_123")
        self.assertEqual(call_args["max_follow_ups"], 2)
        self.assertEqual(len(call_args["templates"]), 2)

    def test_schedule_follow_ups(self):
        """Test scheduling follow-ups for recipients."""
        # Mock campaign data
        campaign_data = {
            "campaign_id": "test_campaign",
            "business_id": 123,
            "templates": [
                {"template_id": "template_1", "delay_days": 7, "is_active": True},
                {"template_id": "template_2", "delay_days": 14, "is_active": True},
            ],
        }

        self.scheduler.storage.get_followup_campaign.return_value = campaign_data
        self.scheduler.storage.create_scheduled_followup.return_value = True

        # Mock unsubscribe check
        self.scheduler._is_unsubscribed = Mock(return_value=False)

        # Schedule follow-ups
        recipient_emails = ["test1@example.com", "test2@example.com"]
        scheduled_ids = self.scheduler.schedule_follow_ups(
            "test_campaign", recipient_emails
        )

        # Should schedule 4 follow-ups (2 recipients × 2 templates)
        self.assertEqual(len(scheduled_ids), 4)
        self.assertEqual(self.scheduler.storage.create_scheduled_followup.call_count, 4)

    def test_schedule_follow_ups_skip_unsubscribed(self):
        """Test that unsubscribed recipients are skipped."""
        campaign_data = {
            "campaign_id": "test_campaign",
            "business_id": 123,
            "templates": [
                {"template_id": "template_1", "delay_days": 7, "is_active": True}
            ],
        }

        self.scheduler.storage.get_followup_campaign.return_value = campaign_data

        # Mock unsubscribe check - first email is unsubscribed
        def mock_unsubscribed(email):
            return email == "unsubscribed@example.com"

        self.scheduler._is_unsubscribed = Mock(side_effect=mock_unsubscribed)

        # Schedule follow-ups
        recipient_emails = ["unsubscribed@example.com", "subscribed@example.com"]
        scheduled_ids = self.scheduler.schedule_follow_ups(
            "test_campaign", recipient_emails
        )

        # Should only schedule 1 follow-up (unsubscribed recipient skipped)
        self.assertEqual(len(scheduled_ids), 1)

    def test_process_pending_follow_ups(self):
        """Test processing pending follow-ups."""
        # Mock pending follow-ups
        pending_follow_ups = [
            {
                "follow_up_id": "followup_1",
                "campaign_id": "campaign_1",
                "recipient_email": "test1@example.com",
                "template_id": "template_1",
            },
            {
                "follow_up_id": "followup_2",
                "campaign_id": "campaign_1",
                "recipient_email": "test2@example.com",
                "template_id": "template_1",
            },
        ]

        self.scheduler.storage.get_pending_followups.return_value = pending_follow_ups

        # Mock processing method
        self.scheduler._process_follow_up = Mock(side_effect=["sent", "skipped"])

        # Process follow-ups
        stats = self.scheduler.process_pending_follow_ups()

        # Check stats
        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["failed"], 0)

    def test_process_follow_up_sent(self):
        """Test successfully processing a follow-up."""
        follow_up_data = {
            "follow_up_id": "test_followup",
            "campaign_id": "test_campaign",
            "recipient_email": "test@example.com",
            "template_id": "template_1",
        }

        # Mock dependencies
        self.scheduler._is_unsubscribed = Mock(return_value=False)
        self.scheduler._get_engagement_level = Mock(return_value=EngagementLevel.LOW)
        self.scheduler._meets_engagement_threshold = Mock(return_value=True)
        self.scheduler._send_follow_up_email = Mock(return_value=True)

        # Mock storage returns
        self.scheduler.storage.get_followup_template.return_value = {
            "template_id": "template_1",
            "engagement_threshold": "low",
        }
        self.scheduler.storage.get_followup_campaign.return_value = {
            "is_active": True,
            "skip_if_engaged": True,
        }
        self.scheduler.storage.update_followup_status.return_value = True

        # Process follow-up
        result = self.scheduler._process_follow_up(follow_up_data)

        # Should be sent
        self.assertEqual(result, "sent")
        self.scheduler.storage.update_followup_status.assert_called_with(
            "test_followup", FollowUpStatus.SENT.value, "Successfully sent"
        )

    def test_process_follow_up_skipped_unsubscribed(self):
        """Test skipping follow-up for unsubscribed recipient."""
        follow_up_data = {
            "follow_up_id": "test_followup",
            "recipient_email": "unsubscribed@example.com",
        }

        # Mock unsubscribed
        self.scheduler._is_unsubscribed = Mock(return_value=True)
        self.scheduler.storage.update_followup_status.return_value = True

        # Process follow-up
        result = self.scheduler._process_follow_up(follow_up_data)

        # Should be skipped
        self.assertEqual(result, "skipped")
        self.scheduler.storage.update_followup_status.assert_called_with(
            "test_followup", FollowUpStatus.SKIPPED.value, "Recipient unsubscribed"
        )

    def test_process_follow_up_skipped_high_engagement(self):
        """Test skipping follow-up for highly engaged recipient."""
        follow_up_data = {
            "follow_up_id": "test_followup",
            "campaign_id": "test_campaign",
            "recipient_email": "engaged@example.com",
            "template_id": "template_1",
        }

        # Mock high engagement
        self.scheduler._is_unsubscribed = Mock(return_value=False)
        self.scheduler._get_engagement_level = Mock(return_value=EngagementLevel.HIGH)
        self.scheduler._meets_engagement_threshold = Mock(return_value=True)

        # Mock storage returns
        self.scheduler.storage.get_followup_template.return_value = {
            "engagement_threshold": "low"
        }
        self.scheduler.storage.get_followup_campaign.return_value = {
            "is_active": True,
            "skip_if_engaged": True,  # Skip if highly engaged
        }
        self.scheduler.storage.update_followup_status.return_value = True

        # Process follow-up
        result = self.scheduler._process_follow_up(follow_up_data)

        # Should be skipped
        self.assertEqual(result, "skipped")
        self.scheduler.storage.update_followup_status.assert_called_with(
            "test_followup", FollowUpStatus.SKIPPED.value, "Recipient highly engaged"
        )

    def test_get_engagement_level(self):
        """Test engagement level detection."""
        # Test high engagement (replied)
        self.scheduler.storage.get_email_engagement.return_value = {
            "delivered": True,
            "opened": True,
            "clicked": False,
            "replied": True,
            "forwarded": False,
        }

        level = self.scheduler._get_engagement_level("campaign_1", "high@example.com")
        self.assertEqual(level, EngagementLevel.HIGH)

        # Test medium engagement (opened only)
        self.scheduler.storage.get_email_engagement.return_value = {
            "delivered": True,
            "opened": True,
            "clicked": False,
            "replied": False,
            "forwarded": False,
        }

        level = self.scheduler._get_engagement_level("campaign_1", "medium@example.com")
        self.assertEqual(level, EngagementLevel.MEDIUM)

        # Test low engagement (delivered only)
        self.scheduler.storage.get_email_engagement.return_value = {
            "delivered": True,
            "opened": False,
            "clicked": False,
            "replied": False,
            "forwarded": False,
        }

        level = self.scheduler._get_engagement_level("campaign_1", "low@example.com")
        self.assertEqual(level, EngagementLevel.LOW)

        # Test unknown engagement
        self.scheduler.storage.get_email_engagement.return_value = None

        level = self.scheduler._get_engagement_level(
            "campaign_1", "unknown@example.com"
        )
        self.assertEqual(level, EngagementLevel.UNKNOWN)

    def test_meets_engagement_threshold(self):
        """Test engagement threshold checking."""
        # High engagement meets all thresholds
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.HIGH, "high")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.HIGH, "medium")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.HIGH, "low")
        )

        # Medium engagement meets medium and low thresholds
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(EngagementLevel.MEDIUM, "high")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.MEDIUM, "medium")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.MEDIUM, "low")
        )

        # Low engagement only meets low threshold
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(EngagementLevel.LOW, "high")
        )
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(EngagementLevel.LOW, "medium")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.LOW, "low")
        )

        # Unknown engagement doesn't meet any threshold except none
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(EngagementLevel.UNKNOWN, "high")
        )
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(
                EngagementLevel.UNKNOWN, "medium"
            )
        )
        self.assertFalse(
            self.scheduler._meets_engagement_threshold(EngagementLevel.UNKNOWN, "low")
        )
        self.assertTrue(
            self.scheduler._meets_engagement_threshold(EngagementLevel.UNKNOWN, "none")
        )

    def test_personalize_content(self):
        """Test content personalization."""
        business = {"name": "Test Business", "website": "https://testbusiness.com"}

        follow_up_data = {
            "recipient_email": "john.doe@example.com",
            "campaign_id": "test_campaign",
        }

        content = "Hi {recipient_name}, {business_name} would like to help improve {business_website}. Unsubscribe: {unsubscribe_url}"

        personalized = self.scheduler._personalize_content(
            content, business, follow_up_data
        )

        self.assertIn("john.doe", personalized)  # Extracted from email
        self.assertIn("Test Business", personalized)
        self.assertIn("https://testbusiness.com", personalized)
        self.assertIn("unsubscribe?email=john.doe@example.com", personalized)

    @patch("leadfactory.email.delivery.EmailDeliveryService")
    def test_send_follow_up_email(self, mock_email_service_class):
        """Test sending follow-up email."""
        # Mock email service
        mock_email_service = Mock()
        mock_email_service.send_email.return_value = {"success": True}
        mock_email_service_class.return_value = mock_email_service

        # Mock business data
        self.scheduler.storage.get_business_by_id.return_value = {
            "id": 123,
            "name": "Test Business",
            "website": "https://testbusiness.com",
        }

        follow_up_data = {
            "follow_up_id": "test_followup",
            "recipient_email": "test@example.com",
            "campaign_id": "test_campaign",
        }

        template_data = {
            "subject_line": "Follow-up from {business_name}",
            "content": "Hi {recipient_name}, this is a follow-up from {business_name}.",
        }

        campaign_data = {"business_id": 123}

        # Send email
        result = self.scheduler._send_follow_up_email(
            follow_up_data, template_data, campaign_data
        )

        # Should succeed
        self.assertTrue(result)
        mock_email_service.send_email.assert_called_once()

    def test_cancel_campaign(self):
        """Test cancelling a campaign."""
        self.scheduler.storage.update_campaign_status.return_value = True
        self.scheduler.storage.cancel_pending_followups.return_value = 5

        # Cancel campaign
        result = self.scheduler.cancel_campaign("test_campaign", "No longer needed")

        # Should succeed
        self.assertTrue(result)
        self.scheduler.storage.update_campaign_status.assert_called_with(
            "test_campaign", False, "No longer needed"
        )
        self.scheduler.storage.cancel_pending_followups.assert_called_with(
            "test_campaign", "No longer needed"
        )

    def test_get_campaign_stats(self):
        """Test getting campaign statistics."""
        expected_stats = {
            "campaign_id": "test_campaign",
            "business_id": 123,
            "status_counts": {"sent": 10, "scheduled": 5},
            "engagement_stats": {"delivered": 8, "opened": 6, "clicked": 2},
        }

        self.scheduler.storage.get_followup_campaign_stats.return_value = expected_stats

        # Get stats
        stats = self.scheduler.get_campaign_stats("test_campaign")

        # Should return expected stats
        self.assertEqual(stats, expected_stats)

    def test_update_engagement(self):
        """Test updating engagement tracking."""
        self.scheduler.storage.update_email_engagement.return_value = True

        # Update engagement
        timestamp = datetime.utcnow()
        result = self.scheduler.update_engagement(
            "test_campaign", "test@example.com", "opened", timestamp
        )

        # Should succeed
        self.assertTrue(result)
        self.scheduler.storage.update_email_engagement.assert_called_with(
            "test_campaign", "test@example.com", "opened", timestamp
        )

    def test_followup_template_dataclass(self):
        """Test FollowUpTemplate dataclass."""
        template = FollowUpTemplate(
            template_id="test_template",
            name="Test Template",
            subject_line="Test Subject",
            content="Test Content",
            delay_days=7,
            engagement_threshold="medium",
        )

        # Test conversion to dict
        template_dict = template.to_dict()
        self.assertEqual(template_dict["template_id"], "test_template")
        self.assertEqual(template_dict["delay_days"], 7)
        self.assertTrue(template_dict["is_active"])

    def test_scheduled_followup_dataclass(self):
        """Test ScheduledFollowUp dataclass."""
        scheduled_for = datetime.utcnow() + timedelta(days=7)

        followup = ScheduledFollowUp(
            follow_up_id="test_followup",
            campaign_id="test_campaign",
            business_id=123,
            recipient_email="test@example.com",
            template_id="test_template",
            scheduled_for=scheduled_for,
        )

        # Test conversion to dict
        followup_dict = followup.to_dict()
        self.assertEqual(followup_dict["follow_up_id"], "test_followup")
        self.assertEqual(followup_dict["business_id"], 123)
        self.assertEqual(followup_dict["status"], "scheduled")
        self.assertEqual(followup_dict["engagement_level"], "unknown")


if __name__ == "__main__":
    unittest.main()
