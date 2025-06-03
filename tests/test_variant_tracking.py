"""
Tests for variant tracking module.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.pipeline.variant_tracking import (
    TrackingEvent, EventType, VariantMetrics, VariantTracker,
    track_variant_assignment, track_pipeline_start, track_stage_completion,
    track_email_sent, track_conversion, get_variant_tracker
)


class TestTrackingEvent:
    """Test TrackingEvent class."""

    def test_tracking_event_creation(self):
        """Test creating a tracking event."""
        event = TrackingEvent(
            variant_id="variant123",
            business_id=456,
            event_type=EventType.VARIANT_ASSIGNED,
            stage=None,
            properties={"key": "value"}
        )

        assert event.variant_id == "variant123"
        assert event.business_id == 456
        assert event.event_type == EventType.VARIANT_ASSIGNED
        assert event.stage is None
        assert event.properties == {"key": "value"}
        assert event.timestamp is not None

    def test_tracking_event_serialization(self):
        """Test tracking event serialization."""
        event = TrackingEvent(
            variant_id="variant123",
            business_id=456,
            event_type=EventType.PIPELINE_COMPLETED,
            stage="scrape",
            properties={"duration": 120}
        )

        data = event.to_dict()

        assert data["variant_id"] == "variant123"
        assert data["business_id"] == 456
        assert data["event_type"] == "pipeline_completed"
        assert data["stage"] == "scrape"
        assert data["properties"] == {"duration": 120}
        assert "timestamp" in data


class TestVariantMetrics:
    """Test VariantMetrics class."""

    def test_variant_metrics_creation(self):
        """Test creating variant metrics."""
        metrics = VariantMetrics(
            variant_id="variant123",
            total_assignments=100,
            pipeline_starts=95,
            pipeline_completions=90,
            pipeline_failures=5,
            emails_sent=85,
            emails_delivered=80,
            emails_opened=40,
            emails_clicked=20,
            conversions=10
        )

        assert metrics.variant_id == "variant123"
        assert metrics.total_assignments == 100
        assert metrics.pipeline_completions == 90
        assert metrics.conversions == 10

    def test_variant_metrics_rates(self):
        """Test variant metrics rate calculations."""
        metrics = VariantMetrics(
            variant_id="variant123",
            total_assignments=100,
            pipeline_starts=100,
            pipeline_completions=80,
            emails_sent=75,
            emails_delivered=70,
            emails_opened=35,
            emails_clicked=14,
            conversions=7
        )

        assert metrics.pipeline_success_rate == 0.8  # 80/100
        assert metrics.conversion_rate == 0.1  # 7/70 (delivered emails)
        assert metrics.email_open_rate == 0.5  # 35/70
        assert metrics.email_click_rate == 0.2  # 14/70 (delivered emails, not opened)

    def test_variant_metrics_zero_division(self):
        """Test variant metrics with zero denominators."""
        metrics = VariantMetrics(
            variant_id="variant123",
            total_assignments=0,
            pipeline_starts=0,
            emails_sent=0,
            emails_delivered=0,
            emails_opened=0
        )

        assert metrics.pipeline_success_rate == 0.0
        assert metrics.conversion_rate == 0.0
        assert metrics.email_open_rate == 0.0
        assert metrics.email_click_rate == 0.0


class TestVariantTracker:
    """Test VariantTracker class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    def test_track_event(self):
        """Test tracking an event."""
        event = TrackingEvent(
            variant_id="variant123",
            business_id=456,
            event_type=EventType.VARIANT_ASSIGNED
        )

        success = self.tracker.track_event(event)
        assert success is True

        # Verify event was stored
        events = self.tracker.get_events(variant_id="variant123")
        assert len(events) == 1
        assert events[0].variant_id == "variant123"
        assert events[0].business_id == 456

    def test_get_variant_metrics(self):
        """Test getting variant metrics."""
        variant_id = "variant123"
        business_id = 456

        # Track various events
        events = [
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.PIPELINE_STARTED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.PIPELINE_COMPLETED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_SENT),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_DELIVERED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_OPENED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.CONVERSION)
        ]

        for event in events:
            self.tracker.track_event(event)

        metrics = self.tracker.get_variant_metrics(variant_id)

        assert metrics.variant_id == variant_id
        assert metrics.total_assignments == 1
        assert metrics.pipeline_starts == 1
        assert metrics.pipeline_completions == 1
        assert metrics.emails_sent == 1
        assert metrics.emails_delivered == 1
        assert metrics.emails_opened == 1
        assert metrics.conversions == 1

    def test_get_events_filtering(self):
        """Test getting events with filters."""
        # Track events for different variants and businesses
        events = [
            TrackingEvent(variant_id="variant1", business_id=100, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant1", business_id=200, event_type=EventType.PIPELINE_STARTED),
            TrackingEvent(variant_id="variant2", business_id=100, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant2", business_id=200, event_type=EventType.PIPELINE_COMPLETED)
        ]

        for event in events:
            self.tracker.track_event(event)

        # Filter by variant_id
        variant1_events = self.tracker.get_events(variant_id="variant1")
        assert len(variant1_events) == 2

        # Filter by business_id
        business100_events = self.tracker.get_events(business_id=100)
        assert len(business100_events) == 2

        # Filter by event_type
        assignment_events = self.tracker.get_events(event_type=EventType.VARIANT_ASSIGNED)
        assert len(assignment_events) == 2

    def test_clear_old_events(self):
        """Test clearing old events."""
        # Create old and new events
        old_timestamp = (datetime.utcnow() - timedelta(days=10)).isoformat()
        new_timestamp = datetime.utcnow().isoformat()

        # Track events with different timestamps
        old_event = TrackingEvent(
            variant_id="variant1",
            business_id=100,
            event_type=EventType.VARIANT_ASSIGNED
        )
        old_event.timestamp = old_timestamp

        new_event = TrackingEvent(
            variant_id="variant1",
            business_id=200,
            event_type=EventType.VARIANT_ASSIGNED
        )
        new_event.timestamp = new_timestamp

        self.tracker.track_event(old_event)
        self.tracker.track_event(new_event)

        # Clear events older than 5 days
        cutoff_date = datetime.utcnow() - timedelta(days=5)
        cleared_count = self.tracker.clear_old_events(cutoff_date)

        assert cleared_count == 1

        # Verify only new event remains
        remaining_events = self.tracker.get_events()
        assert len(remaining_events) == 1
        assert remaining_events[0].business_id == 200


class TestTrackingFunctions:
    """Test convenience tracking functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Mock the global tracker
        self.mock_tracker = Mock()
        self.patcher = patch('leadfactory.pipeline.variant_tracking.get_variant_tracker')
        self.mock_get_tracker = self.patcher.start()
        self.mock_get_tracker.return_value = self.mock_tracker

    def teardown_method(self):
        """Clean up test fixtures."""
        self.patcher.stop()
        os.unlink(self.temp_db.name)

    def test_track_variant_assignment(self):
        """Test tracking variant assignment."""
        track_variant_assignment("variant123", 456, {"source": "test"})

        self.mock_tracker.track_variant_assignment.assert_called_once_with(
            "variant123", 456, properties={"source": "test"}
        )

    def test_track_pipeline_start(self):
        """Test tracking pipeline start."""
        track_pipeline_start("variant123", 456, {"session": "abc"})

        self.mock_tracker.track_pipeline_start.assert_called_once_with(
            "variant123", 456, properties={"session": "abc"}
        )

    def test_track_stage_completion(self):
        """Test tracking stage completion."""
        track_stage_completion("variant123", 456, "scrape", {"duration": 120})

        self.mock_tracker.track_stage_completion.assert_called_once_with(
            "variant123", 456, "scrape", properties={"duration": 120}
        )

    def test_track_email_sent(self):
        """Test tracking email sent."""
        track_email_sent("variant123", 456, {"email_id": "email123"})

        self.mock_tracker.track_email_event.assert_called_once_with(
            "variant123", 456, EventType.EMAIL_SENT, properties={"email_id": "email123"}
        )

    def test_track_conversion(self):
        """Test tracking conversion."""
        track_conversion("variant123", 456, {"value": 100.0})

        self.mock_tracker.track_conversion.assert_called_once_with(
            "variant123", 456, properties={"value": 100.0}
        )


class TestVariantTrackerIntegration:
    """Integration tests for variant tracker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    def test_full_pipeline_tracking(self):
        """Test tracking a complete pipeline execution."""
        variant_id = "variant123"
        business_id = 456

        # Track complete pipeline flow
        events = [
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.PIPELINE_STARTED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.STAGE_STARTED, stage="scrape"),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.STAGE_COMPLETED, stage="scrape"),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.STAGE_STARTED, stage="enrich"),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.STAGE_COMPLETED, stage="enrich"),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.PIPELINE_COMPLETED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_SENT),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_DELIVERED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_OPENED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.EMAIL_CLICKED),
            TrackingEvent(variant_id=variant_id, business_id=business_id, event_type=EventType.CONVERSION)
        ]

        # Track all events
        for event in events:
            success = self.tracker.track_event(event)
            assert success is True

        # Get metrics
        metrics = self.tracker.get_variant_metrics(variant_id)

        assert metrics.variant_id == variant_id
        assert metrics.total_assignments == 1
        assert metrics.pipeline_starts == 1
        assert metrics.pipeline_completions == 1
        assert metrics.emails_sent == 1
        assert metrics.emails_delivered == 1
        assert metrics.emails_opened == 1
        assert metrics.emails_clicked == 1
        assert metrics.conversions == 1

        # Check rates
        assert metrics.pipeline_success_rate == 1.0
        assert metrics.conversion_rate == 1.0
        assert metrics.email_open_rate == 1.0
        assert metrics.email_click_rate == 1.0

    def test_multiple_variants_tracking(self):
        """Test tracking multiple variants."""
        # Track events for two different variants
        variant1_events = [
            TrackingEvent(variant_id="variant1", business_id=100, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant1", business_id=100, event_type=EventType.PIPELINE_COMPLETED),
            TrackingEvent(variant_id="variant1", business_id=200, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant1", business_id=200, event_type=EventType.PIPELINE_FAILED)
        ]

        variant2_events = [
            TrackingEvent(variant_id="variant2", business_id=300, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant2", business_id=300, event_type=EventType.PIPELINE_COMPLETED),
            TrackingEvent(variant_id="variant2", business_id=400, event_type=EventType.VARIANT_ASSIGNED),
            TrackingEvent(variant_id="variant2", business_id=400, event_type=EventType.PIPELINE_COMPLETED)
        ]

        all_events = variant1_events + variant2_events
        for event in all_events:
            self.tracker.track_event(event)

        # Get metrics for each variant
        metrics1 = self.tracker.get_variant_metrics("variant1")
        metrics2 = self.tracker.get_variant_metrics("variant2")

        assert metrics1.total_assignments == 2
        assert metrics1.pipeline_completions == 1
        assert metrics1.pipeline_failures == 1
        assert metrics1.pipeline_success_rate == 0.5

        assert metrics2.total_assignments == 2
        assert metrics2.pipeline_completions == 2
        assert metrics2.pipeline_failures == 0
        assert metrics2.pipeline_success_rate == 1.0
