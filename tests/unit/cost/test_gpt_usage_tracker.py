"""
Unit tests for GPT Usage Tracker module.

Tests the comprehensive tracking and monitoring of GPT API usage,
including token counts, request frequency, and associated costs.
"""

import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.cost.gpt_usage_tracker import (
    GPTUsageTracker,
    get_gpt_usage_tracker,
    gpt_usage_tracker,
)


class TestGPTUsageTracker:
    """Test cases for GPTUsageTracker class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def tracker(self, temp_db):
        """Create a GPTUsageTracker instance with temporary database."""
        return GPTUsageTracker(db_path=temp_db)

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates the database and tables."""
        tracker = GPTUsageTracker(db_path=temp_db)

        # Check that database file exists
        assert os.path.exists(temp_db)

        # Check that table exists
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gpt_usage'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "gpt_usage"

    def test_track_usage_basic(self, tracker):
        """Test basic usage tracking functionality."""
        result = tracker.track_usage(
            model="gpt-4o",
            operation="chat_completion",
            input_tokens=100,
            output_tokens=50,
            request_duration=1.5,
            success=True,
        )

        # Check returned data
        assert result["model"] == "gpt-4o"
        assert result["operation"] == "chat_completion"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert result["success"] is True
        assert result["request_duration"] == 1.5

        # Check cost calculation (gpt-4o: input $0.005/1K, output $0.015/1K)
        expected_input_cost = (100 / 1000) * 0.005  # $0.0005
        expected_output_cost = (50 / 1000) * 0.015  # $0.00075
        expected_total_cost = expected_input_cost + expected_output_cost  # $0.00125

        assert abs(result["input_cost"] - expected_input_cost) < 0.0001
        assert abs(result["output_cost"] - expected_output_cost) < 0.0001
        assert abs(result["total_cost"] - expected_total_cost) < 0.0001

    def test_track_usage_with_metadata(self, tracker):
        """Test usage tracking with metadata."""
        metadata = {"user_id": "test_user", "session_id": "session_123"}

        tracker.track_usage(
            model="gpt-3.5-turbo",
            operation="completion",
            input_tokens=200,
            output_tokens=100,
            metadata=metadata,
            batch_id="batch_456",
        )

        # Verify data was stored in database
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata, batch_id FROM gpt_usage WHERE model = ?",
            ("gpt-3.5-turbo",),
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        stored_metadata = json.loads(result[0])
        assert stored_metadata == metadata
        assert result[1] == "batch_456"

    def test_track_usage_error(self, tracker):
        """Test tracking failed requests."""
        result = tracker.track_usage(
            model="gpt-4",
            operation="chat_completion",
            input_tokens=50,
            output_tokens=0,
            success=False,
            error_message="API rate limit exceeded",
        )

        assert result["success"] is False
        assert result["error_message"] == "API rate limit exceeded"
        assert result["total_cost"] == 0  # No cost for failed requests

    def test_get_usage_stats_basic(self, tracker):
        """Test basic usage statistics retrieval."""
        # Add some test data
        start_time = datetime.now() - timedelta(hours=2)

        tracker.track_usage("gpt-4o", "chat_completion", 100, 50, success=True)
        tracker.track_usage("gpt-3.5-turbo", "completion", 200, 100, success=True)
        tracker.track_usage(
            "gpt-4o", "chat_completion", 150, 75, success=False, error_message="Error"
        )

        # Use a time range that includes the tracked usage (now + 1 hour to be safe)
        now = datetime.now()
        end_time = now + timedelta(hours=1)

        stats = tracker.get_usage_stats(start_time, end_time)

        assert stats["summary"]["total_requests"] == 3
        assert stats["summary"]["successful_requests"] == 2
        assert stats["summary"]["failed_requests"] == 1
        assert stats["summary"]["success_rate"] == 2 / 3
        assert (
            stats["summary"]["total_tokens"] == 675
        )  # (100+50) + (200+100) + (150+75)

        # Check model breakdown
        model_breakdown = {item["model"]: item for item in stats["model_breakdown"]}
        assert "gpt-4o" in model_breakdown
        assert "gpt-3.5-turbo" in model_breakdown
        assert model_breakdown["gpt-4o"]["requests"] == 2
        assert model_breakdown["gpt-3.5-turbo"]["requests"] == 1

    def test_get_usage_stats_with_filters(self, tracker):
        """Test usage statistics with filters."""
        # Add test data with different models and batch IDs
        tracker.track_usage("gpt-4o", "chat_completion", 100, 50, batch_id="batch1")
        tracker.track_usage("gpt-3.5-turbo", "completion", 200, 100, batch_id="batch1")
        tracker.track_usage("gpt-4o", "chat_completion", 150, 75, batch_id="batch2")

        # Filter by model
        stats = tracker.get_usage_stats(model="gpt-4o")
        assert stats["summary"]["total_requests"] == 2
        assert len(stats["model_breakdown"]) == 1
        assert stats["model_breakdown"][0]["model"] == "gpt-4o"

        # Filter by batch ID
        stats = tracker.get_usage_stats(batch_id="batch1")
        assert stats["summary"]["total_requests"] == 2

        # Filter by both
        stats = tracker.get_usage_stats(model="gpt-4o", batch_id="batch1")
        assert stats["summary"]["total_requests"] == 1

    def test_get_current_usage(self, tracker):
        """Test current usage statistics."""
        # Add recent usage
        tracker.track_usage("gpt-4o", "chat_completion", 100, 50)

        stats = tracker.get_current_usage(period_hours=1)
        assert stats["summary"]["total_requests"] == 1
        assert stats["summary"]["total_tokens"] == 150

    def test_estimate_tokens(self, tracker):
        """Test token estimation."""
        # Test empty string
        assert tracker.estimate_tokens("") == 0

        # Test normal text (rough estimation: 1 token ≈ 4 characters)
        text = "Hello, world!"  # 13 characters
        estimated = tracker.estimate_tokens(text)
        assert estimated == 3  # 13 // 4 = 3

        # Test longer text
        long_text = "A" * 100  # 100 characters
        estimated = tracker.estimate_tokens(long_text)
        assert estimated == 25  # 100 // 4 = 25

    def test_estimate_cost(self, tracker):
        """Test cost estimation."""
        input_text = "Hello, world!"  # ~3 tokens
        estimated_output = 10

        cost = tracker.estimate_cost("gpt-4o", input_text, estimated_output)

        # Expected: (3/1000 * 0.005) + (10/1000 * 0.015) = 0.000015 + 0.00015 = 0.000165
        expected = (3 / 1000 * 0.005) + (10 / 1000 * 0.015)
        assert abs(cost - expected) < 0.0001

    def test_pricing_fallback(self, tracker):
        """Test that unknown models fall back to gpt-4o pricing."""
        result = tracker.track_usage(
            model="unknown-model",
            operation="test",
            input_tokens=1000,
            output_tokens=1000,
        )

        # Should use gpt-4o pricing
        expected_cost = (1000 / 1000 * 0.005) + (
            1000 / 1000 * 0.015
        )  # 0.005 + 0.015 = 0.02
        assert abs(result["total_cost"] - expected_cost) < 0.0001


class TestGPTUsageTrackerDecorator:
    """Test cases for the gpt_usage_tracker decorator."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def tracker(self, temp_db):
        """Create a GPTUsageTracker instance with temporary database."""
        return GPTUsageTracker(db_path=temp_db)

    def test_decorator_basic_function(self, tracker):
        """Test decorator on a basic function."""

        @gpt_usage_tracker(model="gpt-4o", operation="test", tracker=tracker)
        def mock_gpt_call(messages):
            return {
                "choices": [{"message": {"content": "Hello, world!"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

        result = mock_gpt_call([{"role": "user", "content": "Hi"}])

        # Check function result
        assert result["choices"][0]["message"]["content"] == "Hello, world!"

        # Check that usage was tracked
        stats = tracker.get_current_usage()
        assert stats["summary"]["total_requests"] == 1
        assert stats["summary"]["total_tokens"] == 15

    def test_decorator_with_error(self, tracker):
        """Test decorator when function raises an error."""

        @gpt_usage_tracker(model="gpt-4o", operation="test", tracker=tracker)
        def failing_gpt_call():
            raise Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            failing_gpt_call()

        # Check that failed usage was tracked
        stats = tracker.get_current_usage()
        assert stats["summary"]["total_requests"] == 1
        assert stats["summary"]["failed_requests"] == 1
        assert stats["summary"]["success_rate"] == 0

    def test_decorator_token_estimation(self, tracker):
        """Test decorator with token estimation from messages."""

        @gpt_usage_tracker(model="gpt-3.5-turbo", operation="chat", tracker=tracker)
        def mock_chat_call(messages):
            return {"choices": [{"message": {"content": "Response text here"}}]}

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello there"},
        ]

        mock_chat_call(messages=messages)

        # Check that usage was tracked with estimated tokens
        stats = tracker.get_current_usage()
        assert stats["summary"]["total_requests"] == 1
        assert stats["summary"]["total_tokens"] > 0  # Should have estimated some tokens


class TestGlobalTracker:
    """Test cases for global tracker functionality."""

    def test_get_global_tracker(self):
        """Test getting the global tracker instance."""
        tracker1 = get_gpt_usage_tracker()
        tracker2 = get_gpt_usage_tracker()

        # Should return the same instance
        assert tracker1 is tracker2
        assert isinstance(tracker1, GPTUsageTracker)

    @patch("leadfactory.cost.gpt_usage_tracker._global_tracker", None)
    def test_global_tracker_initialization(self):
        """Test that global tracker is initialized on first access."""
        # Reset global tracker
        import leadfactory.cost.gpt_usage_tracker as module

        module._global_tracker = None

        tracker = get_gpt_usage_tracker()
        assert tracker is not None
        assert isinstance(tracker, GPTUsageTracker)


class TestIntegrationWithCostTracker:
    """Test integration with the existing cost tracking system."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @patch("leadfactory.cost.gpt_usage_tracker.CostTracker")
    def test_cost_tracker_integration(self, mock_cost_tracker_class, temp_db):
        """Test that GPT usage is also tracked in the main cost tracker."""
        mock_cost_tracker = MagicMock()
        mock_cost_tracker_class.return_value = mock_cost_tracker

        tracker = GPTUsageTracker(db_path=temp_db)

        tracker.track_usage(
            model="gpt-4o",
            operation="chat_completion",
            input_tokens=100,
            output_tokens=50,
            success=True,
            batch_id="test_batch",
        )

        # Verify cost tracker was called
        mock_cost_tracker.add_cost.assert_called_once()
        call_args = mock_cost_tracker.add_cost.call_args

        assert call_args[1]["service"] == "openai"
        assert call_args[1]["operation"] == "gpt-4o_chat_completion"
        assert call_args[1]["batch_id"] == "test_batch"
        assert "input_tokens" in call_args[1]["details"]
        assert "output_tokens" in call_args[1]["details"]
        assert call_args[1]["details"]["input_tokens"] == 100
        assert call_args[1]["details"]["output_tokens"] == 50

    @patch("leadfactory.cost.gpt_usage_tracker.CostTracker")
    def test_no_cost_tracking_on_failure(self, mock_cost_tracker_class, temp_db):
        """Test that failed requests don't add costs to the cost tracker."""
        mock_cost_tracker = MagicMock()
        mock_cost_tracker_class.return_value = mock_cost_tracker

        tracker = GPTUsageTracker(db_path=temp_db)

        tracker.track_usage(
            model="gpt-4o",
            operation="chat_completion",
            input_tokens=100,
            output_tokens=0,
            success=False,
            error_message="API Error",
        )

        # Verify cost tracker was NOT called for failed request
        mock_cost_tracker.add_cost.assert_not_called()


class TestDatabaseOperations:
    """Test database operations and data persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_database_persistence(self, temp_db):
        """Test that data persists across tracker instances."""
        # Create first tracker and add data
        tracker1 = GPTUsageTracker(db_path=temp_db)
        tracker1.track_usage("gpt-4o", "test", 100, 50)

        # Create second tracker with same database
        tracker2 = GPTUsageTracker(db_path=temp_db)
        stats = tracker2.get_current_usage()

        assert stats["summary"]["total_requests"] == 1
        assert stats["summary"]["total_tokens"] == 150

    def test_concurrent_access(self, temp_db):
        """Test concurrent access to the database."""
        import threading

        tracker = GPTUsageTracker(db_path=temp_db)
        results = []

        def add_usage(i):
            try:
                tracker.track_usage("gpt-4o", "test", 100, 50)
                results.append(True)
            except Exception:
                results.append(False)

        # Create multiple threads
        threads = [threading.Thread(target=add_usage, args=(i,)) for i in range(10)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that all operations succeeded
        assert all(results)
        assert len(results) == 10

        # Check final count
        stats = tracker.get_current_usage()
        assert stats["summary"]["total_requests"] == 10
