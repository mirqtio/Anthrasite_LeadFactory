"""Tests for score retrieval in storage queries."""

import json
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.storage.postgres_storage import PostgresStorage


class TestScoreQuery:
    """Test score retrieval in storage queries."""

    def test_get_businesses_for_email_includes_score(self):
        """Test that get_businesses_for_email query includes score from stage_results."""
        storage = PostgresStorage()

        # Mock cursor and its methods
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (1, "Business 1", "email1@example.com", "555-1234", "123 Main St",
             "New York", "NY", "10001", "http://example1.com", "http://mockup1.png",
             "John Doe", 75, "Some notes"),
            (2, "Business 2", "email2@example.com", "555-5678", "456 Oak Ave",
             "Los Angeles", "CA", "90001", "http://example2.com", "http://mockup2.png",
             "Jane Smith", 45, "Other notes"),
        ]
        mock_cursor.description = [
            ("id",), ("name",), ("email",), ("phone",), ("address",),
            ("city",), ("state",), ("zip",), ("website",), ("mockup_url",),
            ("contact_name",), ("score",), ("notes",)
        ]

        # Mock the cursor context manager
        with patch.object(storage, "cursor") as mock_cursor_context:
            mock_cursor_context.return_value.__enter__.return_value = mock_cursor

            # Call the method
            result = storage.get_businesses_for_email()

            # Verify the query includes the score from stage_results
            mock_cursor.execute.assert_called_once()
            query = mock_cursor.execute.call_args[0][0]

            # Check that the query joins with stage_results
            assert "LEFT JOIN stage_results sr" in query
            assert "sr.stage = 'score'" in query
            assert "COALESCE((sr.results->>'score')::int, 0) as score" in query

            # Verify the results include scores
            assert len(result) == 2
            assert result[0]["score"] == 75
            assert result[1]["score"] == 45

    def test_get_businesses_for_email_handles_missing_scores(self):
        """Test that missing scores default to 0."""
        storage = PostgresStorage()

        # Mock cursor with results where stage_results is NULL
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (1, "Business 1", "email1@example.com", "555-1234", "123 Main St",
             "New York", "NY", "10001", "http://example1.com", "http://mockup1.png",
             "John Doe", 0, "Some notes"),  # No score in stage_results, defaults to 0
        ]
        mock_cursor.description = [
            ("id",), ("name",), ("email",), ("phone",), ("address",),
            ("city",), ("state",), ("zip",), ("website",), ("mockup_url",),
            ("contact_name",), ("score",), ("notes",)
        ]

        with patch.object(storage, "cursor") as mock_cursor_context:
            mock_cursor_context.return_value.__enter__.return_value = mock_cursor

            result = storage.get_businesses_for_email()

            # Verify default score of 0
            assert len(result) == 1
            assert result[0]["score"] == 0

    def test_get_businesses_for_email_parses_json_score(self):
        """Test that JSON score values are properly parsed."""
        storage = PostgresStorage()

        # Mock the actual database interaction
        with patch("leadfactory.storage.postgres_storage.db_cursor") as mock_db_cursor:
            mock_cursor = MagicMock()

            # Mock the query result with proper score extraction
            # Simulating PostgreSQL's JSON extraction: (results->>'score')::int
            mock_cursor.fetchall.return_value = [
                {
                    "id": 1,
                    "name": "Test Business",
                    "email": "test@example.com",
                    "phone": "555-1234",
                    "address": "123 Test St",
                    "city": "Test City",
                    "state": "TS",
                    "zip": "12345",
                    "website": "http://test.com",
                    "mockup_url": "http://mockup.png",
                    "contact_name": "",
                    "score": 95,  # Already extracted from JSON
                    "notes": ""
                }
            ]

            mock_cursor.description = [
                ("id",), ("name",), ("email",), ("phone",), ("address",),
                ("city",), ("state",), ("zip",), ("website",), ("mockup_url",),
                ("contact_name",), ("score",), ("notes",)
            ]

            mock_db_cursor.return_value.__enter__.return_value = mock_cursor

            result = storage.get_businesses_for_email()

            # Verify the score was properly extracted
            assert len(result) == 1
            assert result[0]["score"] == 95


class TestStageResultsIntegration:
    """Test integration with stage_results table."""

    @pytest.mark.integration
    def test_save_and_retrieve_score(self):
        """Test saving score to stage_results and retrieving it."""
        storage = PostgresStorage()

        # Mock saving score results
        score_results = {"score": 82, "breakdown": {"seo": 30, "performance": 52}}

        with patch.object(storage, "cursor") as mock_cursor_context:
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor_context.return_value.__enter__.return_value = mock_cursor

            # Save the score
            success = storage.save_stage_results(
                business_id=123,
                stage="score",
                results=score_results
            )

            assert success is True

            # Verify the INSERT/UPDATE query
            mock_cursor.execute.assert_called_once()
            query = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]

            assert "INSERT INTO stage_results" in query
            assert "ON CONFLICT (business_id, stage)" in query
            assert params[0] == 123  # business_id
            assert params[1] == "score"  # stage
            assert json.loads(params[2]) == score_results  # results as JSON
