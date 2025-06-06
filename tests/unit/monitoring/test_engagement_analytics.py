"""Unit tests for EngagementAnalytics."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.monitoring.engagement_analytics import (
    EngagementAnalytics,
    EventType,
    ConversionGoal,
    EngagementEvent,
    UserSession,
    ConversionFunnel,
)


class TestEngagementAnalytics(unittest.TestCase):
    """Test EngagementAnalytics functionality."""

    def setUp(self):
        """Set up test environment."""
        self.analytics = EngagementAnalytics()
        self.analytics.storage = Mock()

    def test_track_event(self):
        """Test tracking an engagement event."""
        # Mock storage
        self.analytics.storage.store_engagement_event.return_value = True
        self.analytics.storage.get_user_session.return_value = None
        self.analytics.storage.update_user_session.return_value = True
        self.analytics.storage.get_active_conversion_funnels.return_value = []

        # Track event
        result = self.analytics.track_event(
            user_id="user123",
            session_id="session123",
            event_type="page_view",
            properties={"page": "/home"},
            page_url="https://example.com/home",
        )

        # Should succeed
        self.assertTrue(result)
        self.analytics.storage.store_engagement_event.assert_called_once()

    def test_track_event_unknown_type(self):
        """Test tracking an unknown event type."""
        self.analytics.storage.store_engagement_event.return_value = True
        self.analytics.storage.get_user_session.return_value = None
        self.analytics.storage.update_user_session.return_value = True
        self.analytics.storage.get_active_conversion_funnels.return_value = []

        # Track unknown event type
        result = self.analytics.track_event(
            user_id="user123",
            session_id="session123",
            event_type="unknown_event",
            properties={},
        )

        # Should succeed with fallback to page_view
        self.assertTrue(result)

    def test_update_session_new_session(self):
        """Test creating a new session."""
        self.analytics.storage.get_user_session.return_value = None
        self.analytics.storage.update_user_session.return_value = True

        event = EngagementEvent(
            event_id="event123",
            user_id="user123",
            session_id="session123",
            event_type=EventType.PAGE_VIEW,
            timestamp=datetime.utcnow(),
            properties={},
            page_url="https://example.com",
        )

        # Update session
        self.analytics._update_session("session123", "user123", event)

        # Should create new session
        self.analytics.storage.update_user_session.assert_called_once()
        call_args = self.analytics.storage.update_user_session.call_args[0][0]
        self.assertEqual(call_args["session_id"], "session123")
        self.assertEqual(call_args["total_events"], 1)

    def test_update_session_existing_session(self):
        """Test updating an existing session."""
        existing_session = {
            "session_id": "session123",
            "user_id": "user123",
            "start_time": datetime.utcnow() - timedelta(minutes=30),
            "end_time": None,
            "total_events": 5,
            "page_views": 3,
            "unique_pages": 2,
            "bounce_rate": 0.0,
            "time_on_site": 1800.0,
            "conversion_events": [],
        }

        self.analytics.storage.get_user_session.return_value = existing_session
        self.analytics.storage.get_session_unique_pages.return_value = [
            "page1",
            "page2",
            "page3",
        ]
        self.analytics.storage.update_user_session.return_value = True

        event = EngagementEvent(
            event_id="event123",
            user_id="user123",
            session_id="session123",
            event_type=EventType.PAGE_VIEW,
            timestamp=datetime.utcnow(),
            properties={},
            page_url="https://example.com/new-page",
        )

        # Update session
        self.analytics._update_session("session123", "user123", event)

        # Should update existing session
        self.analytics.storage.update_user_session.assert_called_once()
        call_args = self.analytics.storage.update_user_session.call_args[0][0]
        self.assertEqual(call_args["total_events"], 6)
        self.assertEqual(call_args["page_views"], 4)

    def test_extract_device_type(self):
        """Test device type extraction from user agent."""
        # Test mobile
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        self.assertEqual(self.analytics._extract_device_type(mobile_ua), "mobile")

        # Test tablet
        tablet_ua = "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X)"
        self.assertEqual(self.analytics._extract_device_type(tablet_ua), "mobile")

        # Test desktop
        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.assertEqual(self.analytics._extract_device_type(desktop_ua), "desktop")

        # Test None
        self.assertIsNone(self.analytics._extract_device_type(None))

    def test_is_conversion_event(self):
        """Test conversion event detection."""
        # Test conversion events
        self.assertTrue(self.analytics._is_conversion_event(EventType.PURCHASE))
        self.assertTrue(self.analytics._is_conversion_event(EventType.SIGNUP))
        self.assertTrue(self.analytics._is_conversion_event(EventType.FORM_SUBMIT))
        self.assertTrue(self.analytics._is_conversion_event(EventType.DOWNLOAD))

        # Test non-conversion events
        self.assertFalse(self.analytics._is_conversion_event(EventType.PAGE_VIEW))
        self.assertFalse(self.analytics._is_conversion_event(EventType.EMAIL_OPEN))

    def test_check_conversions(self):
        """Test conversion funnel checking."""
        # Mock funnel data
        funnel_data = [
            {
                "funnel_id": "funnel123",
                "name": "Purchase Funnel",
                "steps": [
                    {"event_type": "page_view", "page_pattern": "/product"},
                    {"event_type": "purchase"},
                ],
                "goal_type": "purchase",
                "time_window_hours": 24,
                "is_active": True,
            }
        ]

        self.analytics.storage.get_active_conversion_funnels.return_value = funnel_data
        self.analytics.storage.update_funnel_progress.return_value = True
        self.analytics.storage.record_conversion.return_value = True

        event = EngagementEvent(
            event_id="event123",
            user_id="user123",
            session_id="session123",
            event_type=EventType.PURCHASE,
            timestamp=datetime.utcnow(),
            properties={},
        )

        # Check conversions
        self.analytics._check_conversions("user123", "session123", event)

        # Should update funnel progress
        self.analytics.storage.update_funnel_progress.assert_called_once()

    def test_event_matches_step(self):
        """Test event matching against funnel steps."""
        event = EngagementEvent(
            event_id="event123",
            user_id="user123",
            session_id="session123",
            event_type=EventType.PAGE_VIEW,
            timestamp=datetime.utcnow(),
            properties={"category": "product"},
            page_url="https://example.com/product/123",
        )

        # Test matching step
        step = {
            "event_type": "page_view",
            "properties": {"category": "product"},
            "page_pattern": r".*\/product\/.*",
        }

        self.assertTrue(self.analytics._event_matches_step(event, step))

        # Test non-matching event type
        step_wrong_type = {
            "event_type": "purchase",
            "properties": {"category": "product"},
        }

        self.assertFalse(self.analytics._event_matches_step(event, step_wrong_type))

        # Test non-matching properties
        step_wrong_props = {
            "event_type": "page_view",
            "properties": {"category": "different"},
        }

        self.assertFalse(self.analytics._event_matches_step(event, step_wrong_props))

    def test_get_user_engagement_summary(self):
        """Test getting user engagement summary."""
        # Mock user data
        events = [
            {"event_type": "page_view", "timestamp": "2023-01-01T12:00:00"},
            {"event_type": "email_open", "timestamp": "2023-01-01T12:05:00"},
            {"event_type": "purchase", "timestamp": "2023-01-01T12:10:00"},
        ]

        sessions = [
            {"time_on_site": 600, "page_views": 5},
            {"time_on_site": 300, "page_views": 2},
        ]

        conversions = [{"conversion_id": "conv123"}]

        self.analytics.storage.get_user_events.return_value = events
        self.analytics.storage.get_user_sessions.return_value = sessions
        self.analytics.storage.get_user_conversions.return_value = conversions

        # Get summary
        summary = self.analytics.get_user_engagement_summary("user123", days=30)

        # Check results
        self.assertEqual(summary["user_id"], "user123")
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["total_sessions"], 2)
        self.assertEqual(summary["total_page_views"], 7)
        self.assertEqual(summary["avg_session_duration"], 450.0)
        self.assertEqual(summary["conversions"], 1)
        self.assertEqual(summary["conversion_rate"], 0.5)

    def test_get_campaign_analytics(self):
        """Test getting campaign analytics."""
        # Mock campaign data
        events = [
            {"event_type": "page_view", "user_id": "user1"},
            {"event_type": "email_open", "user_id": "user2"},
            {"event_type": "purchase", "user_id": "user1"},
        ]

        sessions = [
            {"user_id": "user1", "traffic_source": "google"},
            {"user_id": "user2", "traffic_source": "direct"},
        ]

        conversions = [{"conversion_id": "conv123"}]

        self.analytics.storage.get_campaign_events.return_value = events
        self.analytics.storage.get_campaign_sessions.return_value = sessions
        self.analytics.storage.get_campaign_conversions.return_value = conversions

        # Get analytics
        analytics = self.analytics.get_campaign_analytics("campaign123", days=30)

        # Check results
        self.assertEqual(analytics["campaign_id"], "campaign123")
        self.assertEqual(analytics["total_events"], 3)
        self.assertEqual(analytics["total_users"], 2)
        self.assertEqual(analytics["total_sessions"], 2)
        self.assertEqual(analytics["conversions"], 1)
        self.assertEqual(analytics["conversion_rate"], 0.5)

    def test_create_conversion_funnel(self):
        """Test creating a conversion funnel."""
        self.analytics.storage.create_conversion_funnel.return_value = True

        steps = [
            {"name": "Visit Product Page", "event_type": "page_view"},
            {"name": "Add to Cart", "event_type": "form_submit"},
            {"name": "Purchase", "event_type": "purchase"},
        ]

        # Create funnel
        funnel_id = self.analytics.create_conversion_funnel(
            name="Purchase Funnel",
            steps=steps,
            goal_type="purchase",
            time_window_hours=48,
        )

        # Should return a funnel ID
        self.assertIsNotNone(funnel_id)
        self.analytics.storage.create_conversion_funnel.assert_called_once()

    def test_get_funnel_analytics(self):
        """Test getting funnel analytics."""
        # Mock funnel data
        funnel_data = {
            "funnel_id": "funnel123",
            "name": "Purchase Funnel",
            "goal_type": ConversionGoal.PURCHASE,
            "steps": [
                {"name": "Visit Product"},
                {"name": "Add to Cart"},
                {"name": "Purchase"},
            ],
            "time_window_hours": 24,
            "is_active": True,
        }

        progress_data = [
            {"user_id": "user1", "step_index": 0, "timestamp": "2023-01-01T12:00:00"},
            {"user_id": "user1", "step_index": 1, "timestamp": "2023-01-01T12:05:00"},
            {"user_id": "user1", "step_index": 2, "timestamp": "2023-01-01T12:10:00"},
            {"user_id": "user2", "step_index": 0, "timestamp": "2023-01-01T12:00:00"},
            {"user_id": "user2", "step_index": 1, "timestamp": "2023-01-01T12:05:00"},
        ]

        self.analytics.storage.get_conversion_funnel.return_value = funnel_data
        self.analytics.storage.get_funnel_progress.return_value = progress_data

        # Get analytics
        analytics = self.analytics.get_funnel_analytics("funnel123", days=30)

        # Check results
        self.assertEqual(analytics["funnel_id"], "funnel123")
        self.assertEqual(analytics["funnel_name"], "Purchase Funnel")
        self.assertEqual(analytics["total_entries"], 2)
        self.assertEqual(analytics["total_completions"], 1)
        self.assertEqual(analytics["overall_conversion_rate"], 0.5)

    def test_get_real_time_metrics(self):
        """Test getting real-time metrics."""
        # Mock real-time data
        active_events = [
            {"event_type": "page_view", "user_id": "user1"},
            {"event_type": "page_view", "user_id": "user2"},
            {"event_type": "email_open", "user_id": "user1"},
        ]

        active_sessions = [{"session_id": "session1"}, {"session_id": "session2"}]

        self.analytics.storage.get_events_in_timeframe.return_value = active_events
        self.analytics.storage.get_active_sessions.return_value = active_sessions

        # Get metrics
        metrics = self.analytics.get_real_time_metrics()

        # Check results
        self.assertEqual(metrics["active_users"], 2)
        self.assertEqual(metrics["active_sessions"], 2)
        self.assertEqual(metrics["total_events"], 3)
        self.assertEqual(metrics["page_views"], 2)
        self.assertEqual(metrics["events_per_minute"], 0.05)  # 3 events / 60 minutes

    def test_engagement_event_to_dict(self):
        """Test EngagementEvent conversion to dictionary."""
        event = EngagementEvent(
            event_id="event123",
            user_id="user123",
            session_id="session123",
            event_type=EventType.PAGE_VIEW,
            timestamp=datetime(2023, 1, 1, 12, 0, 0),
            properties={"page": "/home"},
        )

        event_dict = event.to_dict()

        self.assertEqual(event_dict["event_id"], "event123")
        self.assertEqual(event_dict["event_type"], "page_view")
        self.assertEqual(event_dict["timestamp"], "2023-01-01T12:00:00")

    def test_user_session_to_dict(self):
        """Test UserSession conversion to dictionary."""
        session = UserSession(
            session_id="session123",
            user_id="user123",
            start_time=datetime(2023, 1, 1, 12, 0, 0),
            end_time=datetime(2023, 1, 1, 12, 30, 0),
            total_events=10,
            page_views=5,
            unique_pages=3,
            bounce_rate=0.0,
            time_on_site=1800.0,
            conversion_events=["event1", "event2"],
        )

        session_dict = session.to_dict()

        self.assertEqual(session_dict["session_id"], "session123")
        self.assertEqual(session_dict["start_time"], "2023-01-01T12:00:00")
        self.assertEqual(session_dict["end_time"], "2023-01-01T12:30:00")

    def test_conversion_funnel_to_dict(self):
        """Test ConversionFunnel conversion to dictionary."""
        funnel = ConversionFunnel(
            funnel_id="funnel123",
            name="Test Funnel",
            steps=[{"name": "Step 1"}],
            goal_type=ConversionGoal.PURCHASE,
            time_window_hours=24,
        )

        funnel_dict = funnel.to_dict()

        self.assertEqual(funnel_dict["funnel_id"], "funnel123")
        self.assertEqual(funnel_dict["goal_type"], "purchase")
        self.assertEqual(funnel_dict["time_window_hours"], 24)


if __name__ == "__main__":
    unittest.main()
