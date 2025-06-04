"""
Tests for Conversion Tracking System
===================================

Tests for the comprehensive conversion tracking and analytics functionality.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.monitoring.conversion_tracking import (
    ConversionTracker,
    ConversionEventType,
    ConversionChannel,
    ConversionEvent,
    ConversionFunnel,
    AttributionReport
)


class TestConversionTracker:
    """Test conversion tracking functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        os.unlink(path)

    @pytest.fixture
    def tracker(self, temp_db):
        """Create conversion tracker with temporary database."""
        return ConversionTracker(db_path=temp_db)

    def test_initialization(self, tracker, temp_db):
        """Test conversion tracker initialization."""
        assert tracker.db_path == temp_db

        # Verify database tables were created
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor]

            expected_tables = [
                'conversion_events',
                'conversion_sessions',
                'conversion_attribution'
            ]

            for table in expected_tables:
                assert table in tables

    def test_track_event(self, tracker):
        """Test tracking conversion events."""
        session_id = "session_123"

        # Track a page view event
        event_id = tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAGE_VIEW,
            audit_type="basic",
            properties={"page": "/audit-report"},
            channel=ConversionChannel.ORGANIC_SEARCH,
            referrer="https://google.com",
            user_agent="Mozilla/5.0..."
        )

        assert event_id is not None
        assert len(event_id) > 0

        # Verify event was stored
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM conversion_events WHERE event_id = ?",
                (event_id,)
            )
            row = cursor.fetchone()

            assert row is not None
            assert row[1] == session_id  # session_id
            assert row[3] == ConversionEventType.PAGE_VIEW.value  # event_type
            assert row[5] == "basic"  # audit_type
            assert row[8] == ConversionChannel.ORGANIC_SEARCH.value  # channel

    def test_track_purchase_event(self, tracker):
        """Test tracking purchase events with revenue."""
        session_id = "session_purchase"

        # Track purchase event
        event_id = tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAYMENT_SUCCESS,
            audit_type="premium",
            revenue_cents=9900,
            channel=ConversionChannel.PAID_SEARCH,
            user_id="user_123"
        )

        # Verify event with revenue
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT revenue_cents, user_id FROM conversion_events WHERE event_id = ?",
                (event_id,)
            )
            row = cursor.fetchone()

            assert row[0] == 9900  # revenue_cents
            assert row[1] == "user_123"  # user_id

    def test_session_creation_and_update(self, tracker):
        """Test session creation and update logic."""
        session_id = "session_update_test"

        # Track first event - should create session
        tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAGE_VIEW,
            channel=ConversionChannel.DIRECT
        )

        # Verify session was created
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT event_count, conversion_completed FROM conversion_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            assert row[0] == 1  # event_count
            assert row[1] == 0  # conversion_completed (False)

        # Track purchase event - should update session
        tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAYMENT_SUCCESS,
            revenue_cents=5000
        )

        # Verify session was updated
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT event_count, conversion_completed, revenue_cents FROM conversion_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            assert row[0] == 2  # event_count
            assert row[1] == 1  # conversion_completed (True)
            assert row[2] == 5000  # revenue_cents

    def test_analyze_funnel(self, tracker):
        """Test conversion funnel analysis."""
        # Create sample funnel data
        session_ids = ["funnel_1", "funnel_2", "funnel_3"]

        # Simulate typical conversion funnel
        for i, session_id in enumerate(session_ids):
            # All sessions start with page view
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAGE_VIEW,
                audit_type="basic",
                channel=ConversionChannel.ORGANIC_SEARCH
            )

            # Some continue to form
            if i < 2:
                tracker.track_event(
                    session_id=session_id,
                    event_type=ConversionEventType.FORM_START,
                    audit_type="basic"
                )

            # Only one completes purchase
            if i == 0:
                tracker.track_event(
                    session_id=session_id,
                    event_type=ConversionEventType.PAYMENT_SUCCESS,
                    audit_type="basic",
                    revenue_cents=4900
                )

        # Analyze funnel
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)

        funnel = tracker.analyze_funnel(start_date, end_date, "basic")

        assert isinstance(funnel, ConversionFunnel)
        assert funnel.audit_type == "basic"
        assert funnel.total_revenue_cents == 4900
        assert len(funnel.funnel_steps) > 0

        # Verify funnel step data
        page_view_step = next(
            (step for step in funnel.funnel_steps
             if step['step'] == ConversionEventType.PAGE_VIEW.value),
            None
        )
        assert page_view_step is not None
        assert page_view_step['count'] == 3  # All sessions had page views

    def test_analyze_attribution(self, tracker):
        """Test marketing attribution analysis."""
        # Create sessions with different channels
        channels = [
            ConversionChannel.ORGANIC_SEARCH,
            ConversionChannel.PAID_SEARCH,
            ConversionChannel.SOCIAL_MEDIA
        ]

        for i, channel in enumerate(channels):
            session_id = f"attribution_{i}"

            # Page view
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAGE_VIEW,
                channel=channel
            )

            # Purchase (different revenue amounts)
            revenue = (i + 1) * 5000  # 5000, 10000, 15000
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAYMENT_SUCCESS,
                revenue_cents=revenue,
                channel=channel
            )

        # Analyze attribution
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)

        attribution = tracker.analyze_attribution(start_date, end_date)

        assert isinstance(attribution, AttributionReport)
        assert len(attribution.top_converting_channels) == 3
        assert len(attribution.revenue_attribution) == 3

        # Verify channel performance
        social_media_performance = attribution.channel_performance.get(
            ConversionChannel.SOCIAL_MEDIA.value
        )
        assert social_media_performance is not None
        assert social_media_performance['conversions'] == 1
        assert social_media_performance['revenue_cents'] == 15000

    def test_get_conversion_summary(self, tracker):
        """Test conversion summary generation."""
        session_id = "summary_test"

        # Create sample events
        tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAGE_VIEW,
            channel=ConversionChannel.DIRECT
        )

        tracker.track_event(
            session_id=session_id,
            event_type=ConversionEventType.PAYMENT_SUCCESS,
            revenue_cents=7500
        )

        # Get summary
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)

        summary = tracker.get_conversion_summary(start_date, end_date)

        assert "period" in summary
        assert "overall_metrics" in summary
        assert "event_breakdown" in summary

        overall_metrics = summary["overall_metrics"]
        assert overall_metrics["total_sessions"] == 1
        assert overall_metrics["converted_sessions"] == 1
        assert overall_metrics["overall_conversion_rate"] == 100.0  # 1/1 * 100
        assert overall_metrics["total_revenue_cents"] == 7500

    def test_cleanup_old_data(self, tracker):
        """Test cleanup of old conversion data."""
        # Add some test data
        old_session = "old_session"
        new_session = "new_session"

        # Create events with different timestamps
        with sqlite3.connect(tracker.db_path) as conn:
            # Insert old event (100 days ago)
            old_timestamp = datetime.now() - timedelta(days=100)
            conn.execute("""
                INSERT INTO conversion_events
                (event_id, session_id, event_type, timestamp, channel)
                VALUES (?, ?, ?, ?, ?)
            """, ("old_event", old_session, "page_view", old_timestamp, "direct"))

            # Insert old session
            conn.execute("""
                INSERT INTO conversion_sessions
                (session_id, first_event_timestamp, last_event_timestamp, attribution_channel, event_count)
                VALUES (?, ?, ?, ?, ?)
            """, (old_session, old_timestamp, old_timestamp, "direct", 1))

        # Add recent event
        tracker.track_event(
            session_id=new_session,
            event_type=ConversionEventType.PAGE_VIEW,
            channel=ConversionChannel.DIRECT
        )

        # Cleanup data older than 90 days
        tracker.cleanup_old_data(retention_days=90)

        # Verify old data was deleted
        with sqlite3.connect(tracker.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversion_events WHERE session_id = ?",
                (old_session,)
            )
            old_events_count = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversion_events WHERE session_id = ?",
                (new_session,)
            )
            new_events_count = cursor.fetchone()[0]

            assert old_events_count == 0  # Old events should be deleted
            assert new_events_count > 0   # New events should remain

    def test_funnel_with_channel_filter(self, tracker):
        """Test funnel analysis with channel filter."""
        # Create events for different channels
        channels = [ConversionChannel.ORGANIC_SEARCH, ConversionChannel.PAID_SEARCH]

        for i, channel in enumerate(channels):
            session_id = f"channel_test_{i}"
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAGE_VIEW,
                channel=channel
            )

        # Analyze funnel filtered by organic search
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)

        funnel = tracker.analyze_funnel(
            start_date,
            end_date,
            channel=ConversionChannel.ORGANIC_SEARCH
        )

        assert funnel.channel == ConversionChannel.ORGANIC_SEARCH

        # Should only include organic search events
        page_view_step = next(
            (step for step in funnel.funnel_steps
             if step['step'] == ConversionEventType.PAGE_VIEW.value),
            None
        )
        assert page_view_step['count'] == 1  # Only one organic search session


class TestConversionEventTypes:
    """Test conversion event type functionality."""

    def test_event_type_enum(self):
        """Test event type enum values."""
        # Test all expected event types exist
        expected_types = [
            "PAGE_VIEW", "AUDIT_TYPE_SELECTION", "FORM_START", "FORM_SUBMIT",
            "PAYMENT_INTENT_CREATED", "PAYMENT_PROCESSING", "PAYMENT_SUCCESS",
            "PAYMENT_FAILED", "EMAIL_OPEN", "EMAIL_CLICK", "REPORT_DOWNLOAD"
        ]

        for event_type_name in expected_types:
            assert hasattr(ConversionEventType, event_type_name)

        # Test string values
        assert ConversionEventType.PAGE_VIEW.value == "page_view"
        assert ConversionEventType.PAYMENT_SUCCESS.value == "payment_success"


class TestConversionChannels:
    """Test conversion channel functionality."""

    def test_channel_enum(self):
        """Test channel enum values."""
        expected_channels = [
            "DIRECT", "ORGANIC_SEARCH", "PAID_SEARCH", "SOCIAL_MEDIA",
            "EMAIL_MARKETING", "REFERRAL", "UNKNOWN"
        ]

        for channel_name in expected_channels:
            assert hasattr(ConversionChannel, channel_name)

        # Test string values
        assert ConversionChannel.ORGANIC_SEARCH.value == "organic_search"
        assert ConversionChannel.SOCIAL_MEDIA.value == "social_media"


class TestConversionDataStructures:
    """Test conversion data structure functionality."""

    def test_conversion_event_structure(self):
        """Test ConversionEvent data structure."""
        event = ConversionEvent(
            event_id="test_event",
            session_id="test_session",
            user_id="test_user",
            event_type=ConversionEventType.PAGE_VIEW,
            timestamp=datetime.now(),
            audit_type="basic",
            revenue_cents=5000,
            properties={"page": "/audit"},
            channel=ConversionChannel.DIRECT,
            referrer="https://example.com",
            user_agent="test-agent"
        )

        assert event.event_id == "test_event"
        assert event.session_id == "test_session"
        assert event.event_type == ConversionEventType.PAGE_VIEW
        assert event.revenue_cents == 5000
        assert event.channel == ConversionChannel.DIRECT

    def test_conversion_funnel_structure(self):
        """Test ConversionFunnel data structure."""
        now = datetime.now()

        funnel = ConversionFunnel(
            period_start=now - timedelta(days=1),
            period_end=now,
            audit_type="premium",
            channel=ConversionChannel.PAID_SEARCH,
            funnel_steps=[{"step": "page_view", "count": 100}],
            conversion_rates={"page_view_to_form": 20.0},
            drop_off_points=[],
            total_revenue_cents=50000,
            average_time_to_conversion=15.5
        )

        assert funnel.audit_type == "premium"
        assert funnel.channel == ConversionChannel.PAID_SEARCH
        assert len(funnel.funnel_steps) == 1
        assert funnel.total_revenue_cents == 50000
        assert funnel.average_time_to_conversion == 15.5

    def test_attribution_report_structure(self):
        """Test AttributionReport data structure."""
        now = datetime.now()

        report = AttributionReport(
            period_start=now - timedelta(days=7),
            period_end=now,
            channel_performance={"organic_search": {"conversions": 10}},
            top_converting_channels=[{"channel": "organic_search", "conversions": 10}],
            revenue_attribution={"organic_search": 25000},
            conversion_paths=[]
        )

        assert "organic_search" in report.channel_performance
        assert len(report.top_converting_channels) == 1
        assert report.revenue_attribution["organic_search"] == 25000


@pytest.mark.integration
class TestConversionTrackingIntegration:
    """Integration tests for conversion tracking system."""

    def test_end_to_end_conversion_flow(self):
        """Test complete conversion tracking flow."""
        # Create temporary tracker
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            tracker = ConversionTracker(db_path=db_path)

            # Simulate complete user journey
            session_id = "integration_test_session"

            # 1. User lands on page
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAGE_VIEW,
                audit_type="premium",
                channel=ConversionChannel.ORGANIC_SEARCH,
                referrer="https://google.com"
            )

            # 2. User selects audit type
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.AUDIT_TYPE_SELECTION,
                audit_type="premium"
            )

            # 3. User starts form
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.FORM_START,
                audit_type="premium"
            )

            # 4. User completes purchase
            tracker.track_event(
                session_id=session_id,
                event_type=ConversionEventType.PAYMENT_SUCCESS,
                audit_type="premium",
                revenue_cents=9900
            )

            # Analyze the funnel
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=1)

            funnel = tracker.analyze_funnel(start_date, end_date, "premium")

            # Verify funnel analysis
            assert funnel.total_revenue_cents == 9900
            assert len(funnel.funnel_steps) > 0

            # Get conversion summary
            summary = tracker.get_conversion_summary(start_date, end_date)
            assert summary["overall_metrics"]["converted_sessions"] == 1
            assert summary["overall_metrics"]["total_revenue_cents"] == 9900

        finally:
            os.unlink(db_path)
