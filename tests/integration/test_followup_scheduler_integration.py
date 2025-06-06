"""Integration tests for FollowUpScheduler."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.email.followup_scheduler import FollowUpScheduler, EngagementLevel


class TestFollowUpSchedulerIntegration(unittest.TestCase):
    """Integration tests for FollowUpScheduler."""

    def setUp(self):
        """Set up test environment."""
        self.scheduler = FollowUpScheduler()
        # Use a mock storage for integration tests
        self.scheduler.storage = Mock()

    def test_full_campaign_workflow(self):
        """Test complete follow-up campaign workflow."""
        # Setup mock storage responses
        self.scheduler.storage.create_followup_campaign.return_value = True
        self.scheduler.storage.get_followup_campaign.return_value = {
            "campaign_id": "test_campaign",
            "business_id": 123,
            "templates": [
                {
                    "template_id": "template_1",
                    "name": "First Follow-up",
                    "subject_line": "Following up on your website redesign",
                    "content": "Hi {recipient_name}, just wanted to follow up on our conversation about {business_name}...",
                    "delay_days": 7,
                    "engagement_threshold": "low",
                    "is_active": True,
                },
                {
                    "template_id": "template_2",
                    "name": "Second Follow-up",
                    "subject_line": "Last chance for website improvements",
                    "content": "Hi again {recipient_name}, this is our final follow-up...",
                    "delay_days": 14,
                    "engagement_threshold": "medium",
                    "is_active": True,
                },
            ],
            "is_active": True,
            "skip_if_engaged": True,
        }
        self.scheduler.storage.create_scheduled_followup.return_value = True

        # Step 1: Create campaign
        campaign_id = self.scheduler.create_campaign(
            business_id=123,
            initial_email_id="initial_email_123",
            templates=[
                {
                    "name": "First Follow-up",
                    "subject_line": "Following up on your website redesign",
                    "content": "Hi {recipient_name}, just wanted to follow up on our conversation about {business_name}...",
                    "delay_days": 7,
                    "engagement_threshold": "low",
                },
                {
                    "name": "Second Follow-up",
                    "subject_line": "Last chance for website improvements",
                    "content": "Hi again {recipient_name}, this is our final follow-up...",
                    "delay_days": 14,
                    "engagement_threshold": "medium",
                },
            ],
            max_follow_ups=2,
        )

        self.assertIsNotNone(campaign_id)
        self.scheduler.storage.create_followup_campaign.assert_called_once()

        # Step 2: Schedule follow-ups for recipients
        recipients = [
            "client1@business.com",
            "client2@business.com",
            "client3@business.com",
        ]

        # Mock unsubscribe checks (client2 is unsubscribed)
        def mock_unsubscribed(email):
            return email == "client2@business.com"

        with patch.object(
            self.scheduler, "_is_unsubscribed", side_effect=mock_unsubscribed
        ):
            scheduled_ids = self.scheduler.schedule_follow_ups(campaign_id, recipients)

        # Should schedule 4 follow-ups (2 active recipients × 2 templates)
        self.assertEqual(len(scheduled_ids), 4)
        self.assertEqual(self.scheduler.storage.create_scheduled_followup.call_count, 4)

        # Step 3: Simulate processing follow-ups
        pending_follow_ups = [
            {
                "follow_up_id": "followup_1",
                "campaign_id": campaign_id,
                "business_id": 123,
                "recipient_email": "client1@business.com",
                "template_id": "template_1",
                "scheduled_for": datetime.utcnow() - timedelta(hours=1),  # Due
            },
            {
                "follow_up_id": "followup_2",
                "campaign_id": campaign_id,
                "business_id": 123,
                "recipient_email": "client3@business.com",
                "template_id": "template_1",
                "scheduled_for": datetime.utcnow() - timedelta(hours=2),  # Due
            },
        ]

        self.scheduler.storage.get_pending_followups.return_value = pending_follow_ups
        self.scheduler.storage.get_followup_template.side_effect = lambda template_id: {
            "template_1": {
                "template_id": "template_1",
                "subject_line": "Following up on your website redesign",
                "content": "Hi {recipient_name}, just wanted to follow up...",
                "engagement_threshold": "low",
            }
        }.get(template_id)

        # Mock engagement and business data
        self.scheduler.storage.get_email_engagement.return_value = {
            "delivered": True,
            "opened": True,  # Make it medium engagement to meet threshold
            "clicked": False,
            "replied": False,
        }

        self.scheduler.storage.get_business_by_id.return_value = {
            "id": 123,
            "name": "Test Business",
            "website": "https://testbusiness.com",
        }

        # Mock email sending
        with patch(
            "leadfactory.email.delivery.EmailDeliveryService"
        ) as mock_email_service_class:
            mock_email_service = Mock()
            mock_email_service.send_email.return_value = {"success": True}
            mock_email_service_class.return_value = mock_email_service

            self.scheduler.storage.update_followup_status.return_value = True

            # Mock unsubscribe check for processing (no one is unsubscribed during processing)
            with patch.object(self.scheduler, "_is_unsubscribed", return_value=False):
                # Process pending follow-ups
                stats = self.scheduler.process_pending_follow_ups()

        # Verify processing results
        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["sent"], 2)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["failed"], 0)

        # Verify emails were sent
        self.assertEqual(mock_email_service.send_email.call_count, 2)

    def test_engagement_tracking_workflow(self):
        """Test engagement tracking and threshold behavior."""
        campaign_id = "engagement_test_campaign"

        # Setup campaign with medium engagement threshold
        self.scheduler.storage.get_followup_campaign.return_value = {
            "campaign_id": campaign_id,
            "is_active": True,
            "skip_if_engaged": False,  # Don't skip engaged users
        }

        self.scheduler.storage.get_followup_template.return_value = {
            "template_id": "template_1",
            "engagement_threshold": "medium",  # Requires medium engagement
        }

        # Test different engagement scenarios
        test_cases = [
            {
                "name": "High engagement - should send",
                "engagement": {
                    "delivered": True,
                    "opened": True,
                    "clicked": True,
                    "replied": False,
                },
                "expected_level": EngagementLevel.HIGH,
                "should_meet_threshold": True,
            },
            {
                "name": "Medium engagement - should send",
                "engagement": {
                    "delivered": True,
                    "opened": True,
                    "clicked": False,
                    "replied": False,
                },
                "expected_level": EngagementLevel.MEDIUM,
                "should_meet_threshold": True,
            },
            {
                "name": "Low engagement - should skip",
                "engagement": {
                    "delivered": True,
                    "opened": False,
                    "clicked": False,
                    "replied": False,
                },
                "expected_level": EngagementLevel.LOW,
                "should_meet_threshold": False,
            },
            {
                "name": "No engagement data - should skip",
                "engagement": None,
                "expected_level": EngagementLevel.UNKNOWN,
                "should_meet_threshold": False,
            },
        ]

        for case in test_cases:
            with self.subTest(case=case["name"]):
                # Mock engagement data
                self.scheduler.storage.get_email_engagement.return_value = case[
                    "engagement"
                ]

                # Test engagement level detection
                level = self.scheduler._get_engagement_level(
                    campaign_id, "test@example.com"
                )
                self.assertEqual(
                    level,
                    case["expected_level"],
                    f"Engagement level mismatch for {case['name']}",
                )

                # Test threshold checking
                meets_threshold = self.scheduler._meets_engagement_threshold(
                    level, "medium"
                )
                self.assertEqual(
                    meets_threshold,
                    case["should_meet_threshold"],
                    f"Threshold check failed for {case['name']}",
                )

    def test_unsubscribe_handling(self):
        """Test unsubscribe handling throughout the workflow."""
        campaign_id = "unsubscribe_test_campaign"

        # Setup campaign
        self.scheduler.storage.get_followup_campaign.return_value = {
            "campaign_id": campaign_id,
            "business_id": 123,
            "templates": [
                {"template_id": "template_1", "delay_days": 7, "is_active": True}
            ],
        }
        self.scheduler.storage.create_scheduled_followup.return_value = True

        # Mock unsubscribe status for different emails
        unsubscribed_emails = {"unsubscribed@example.com"}

        def mock_unsubscribed(email):
            return email in unsubscribed_emails

        # Test 1: Unsubscribed emails are skipped during scheduling
        recipients = [
            "active@example.com",
            "unsubscribed@example.com",
            "another@example.com",
        ]

        with patch.object(
            self.scheduler, "_is_unsubscribed", side_effect=mock_unsubscribed
        ):
            scheduled_ids = self.scheduler.schedule_follow_ups(campaign_id, recipients)

        # Should only schedule for 2 active recipients
        self.assertEqual(len(scheduled_ids), 2)

        # Test 2: Unsubscribed emails are skipped during processing
        follow_up_data = {
            "follow_up_id": "test_followup",
            "recipient_email": "unsubscribed@example.com",
        }

        self.scheduler.storage.update_followup_status.return_value = True

        with patch.object(
            self.scheduler, "_is_unsubscribed", side_effect=mock_unsubscribed
        ):
            result = self.scheduler._process_follow_up(follow_up_data)

        self.assertEqual(result, "skipped")
        self.scheduler.storage.update_followup_status.assert_called_with(
            "test_followup", "skipped", "Recipient unsubscribed"
        )

    def test_campaign_management_operations(self):
        """Test campaign management operations."""
        campaign_id = "management_test_campaign"

        # Test 1: Get campaign statistics
        expected_stats = {
            "campaign_id": campaign_id,
            "business_id": 123,
            "is_active": True,
            "status_counts": {"scheduled": 15, "sent": 8, "skipped": 2, "failed": 1},
            "engagement_stats": {
                "delivered": 8,
                "opened": 6,
                "clicked": 3,
                "replied": 1,
                "total_tracked": 8,
            },
        }

        self.scheduler.storage.get_followup_campaign_stats.return_value = expected_stats

        stats = self.scheduler.get_campaign_stats(campaign_id)
        self.assertEqual(stats, expected_stats)

        # Test 2: Cancel campaign
        self.scheduler.storage.update_campaign_status.return_value = True
        self.scheduler.storage.cancel_pending_followups.return_value = (
            15  # Cancelled 15 pending
        )

        result = self.scheduler.cancel_campaign(
            campaign_id, "Business no longer needs service"
        )

        self.assertTrue(result)
        self.scheduler.storage.update_campaign_status.assert_called_with(
            campaign_id, False, "Business no longer needs service"
        )
        self.scheduler.storage.cancel_pending_followups.assert_called_with(
            campaign_id, "Business no longer needs service"
        )

    def test_email_personalization_integration(self):
        """Test email personalization with realistic data."""
        business_data = {
            "id": 123,
            "name": "ABC Plumbing Services",
            "website": "https://abcplumbing.com",
        }

        follow_up_data = {
            "follow_up_id": "test_followup",
            "campaign_id": "personalization_test",
            "recipient_email": "john.smith@homeservices.com",
        }

        template_content = """Hi {recipient_name},

I hope this email finds you well. I'm following up on our conversation about improving the website for {business_name}.

Our team has prepared some specific recommendations for {business_website} that could help increase your online visibility and customer conversions.

Would you be interested in a quick 15-minute call to discuss these improvements?

Best regards,
The {business_name} Team

If you'd prefer not to receive these emails, you can unsubscribe here: {unsubscribe_url}"""

        # Test personalization
        personalized_content = self.scheduler._personalize_content(
            template_content, business_data, follow_up_data
        )

        # Verify all placeholders were replaced
        self.assertIn("john.smith", personalized_content)  # Recipient name from email
        self.assertIn("ABC Plumbing Services", personalized_content)  # Business name
        self.assertIn("https://abcplumbing.com", personalized_content)  # Website
        self.assertIn(
            "unsubscribe?email=john.smith@homeservices.com", personalized_content
        )  # Unsubscribe
        self.assertIn(
            "campaign=personalization_test", personalized_content
        )  # Campaign ID

        # Verify no placeholders remain
        self.assertNotIn("{recipient_name}", personalized_content)
        self.assertNotIn("{business_name}", personalized_content)
        self.assertNotIn("{business_website}", personalized_content)
        self.assertNotIn("{unsubscribe_url}", personalized_content)

    def test_error_handling_and_resilience(self):
        """Test error handling and system resilience."""
        # Test 1: Handle storage errors gracefully
        self.scheduler.storage.get_pending_followups.side_effect = Exception(
            "Database connection error"
        )

        stats = self.scheduler.process_pending_follow_ups()

        # Should return zero stats instead of crashing
        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["sent"], 0)

        # Test 2: Handle individual follow-up processing errors
        self.scheduler.storage.get_pending_followups.side_effect = None
        self.scheduler.storage.get_pending_followups.return_value = [
            {
                "follow_up_id": "error_followup",
                "campaign_id": "test",
                "recipient_email": "test@example.com",
                "template_id": "template_1",
            }
        ]

        # Mock processing to raise an error
        self.scheduler._process_follow_up = Mock(
            side_effect=Exception("Email service unavailable")
        )
        self.scheduler.storage.update_followup_status.return_value = True

        stats = self.scheduler.process_pending_follow_ups()

        # Should record the failure
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["failed"], 1)
        self.scheduler.storage.update_followup_status.assert_called_with(
            "error_followup", "failed", error_message="Email service unavailable"
        )

    def test_engagement_update_workflow(self):
        """Test the engagement update workflow."""
        campaign_id = "engagement_update_test"
        recipient_email = "tracking@example.com"

        self.scheduler.storage.update_email_engagement.return_value = True

        # Test various engagement events
        engagement_events = [
            ("delivered", "Email delivered successfully"),
            ("opened", "Recipient opened the email"),
            ("clicked", "Recipient clicked a link"),
            ("replied", "Recipient replied to the email"),
        ]

        for engagement_type, description in engagement_events:
            with self.subTest(engagement_type=engagement_type):
                timestamp = datetime.utcnow()

                result = self.scheduler.update_engagement(
                    campaign_id, recipient_email, engagement_type, timestamp
                )

                self.assertTrue(
                    result, f"Failed to update {engagement_type} engagement"
                )

        # Verify all engagement updates were recorded
        self.assertEqual(
            self.scheduler.storage.update_email_engagement.call_count,
            len(engagement_events),
        )


if __name__ == "__main__":
    unittest.main()
