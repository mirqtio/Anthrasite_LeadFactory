"""
Unit tests for deduplication functionality in the Postgres connector.

This module tests the deduplication-specific functions added to the
unified Postgres connector.
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from leadfactory.utils.e2e_db_connector import (
    add_to_review_queue,
    check_dedupe_tables_exist,
    create_dedupe_tables,
    get_business_details,
    get_potential_duplicate_pairs,
    merge_business_records,
    update_business_fields,
)


class TestDedupeConnectorFunctions:
    """Test deduplication functions in the Postgres connector."""

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_get_potential_duplicate_pairs(self, mock_db_cursor):
        """Test getting potential duplicate pairs."""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                1,
                2,
                "Business A",
                "Business A Inc",
                "555-1234",
                "555-1234",
                "123 Main St",
                "123 Main Street",
            ),
            (
                3,
                4,
                "Company B",
                "Company B LLC",
                None,
                "555-5678",
                "456 Oak Ave",
                "456 Oak Avenue",
            ),
        ]
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        # Test without limit
        result = get_potential_duplicate_pairs()

        assert len(result) == 2
        assert result[0]["business1_id"] == 1
        assert result[0]["business2_id"] == 2
        assert result[0]["business1_name"] == "Business A"
        assert result[1]["business1_id"] == 3

        # Verify query was called
        mock_cursor.execute.assert_called_once()
        query = mock_cursor.execute.call_args[0][0]
        assert "SELECT" in query
        assert "businesses b1" in query
        assert "businesses b2" in query

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_get_potential_duplicate_pairs_with_limit(self, mock_db_cursor):
        """Test getting potential duplicate pairs with limit."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, 2, "A", "A", None, None, None, None)]
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        get_potential_duplicate_pairs(limit=10)

        # Verify LIMIT was added to query
        query = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 10" in query

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_get_business_details(self, mock_db_cursor):
        """Test getting business details by ID."""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            1,
            "Test Business",
            "555-1234",
            "test@example.com",
            "www.test.com",
            "123 Main St",
            "Anytown",
            "CA",
            "12345",
            "Restaurant",
            "google",
            False,
            False,
            '{"data": "test"}',
            None,
            None,
            datetime.now(),
            datetime.now(),
        )
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_business_details(1)

        assert result is not None
        assert result["id"] == 1
        assert result["name"] == "Test Business"
        assert result["phone"] == "555-1234"
        assert result["email"] == "test@example.com"
        assert result["google_response"] == '{"data": "test"}'

        # Verify query
        mock_cursor.execute.assert_called_once()
        query = mock_cursor.execute.call_args[0][0]
        assert "SELECT" in query
        assert "FROM businesses" in query
        assert "WHERE id = %s" in query

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_get_business_details_not_found(self, mock_db_cursor):
        """Test getting business details when not found."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = get_business_details(999)

        assert result is None

    @patch("leadfactory.utils.e2e_db_connector.db_transaction")
    def test_merge_business_records(self, mock_db_transaction):
        """Test merging business records."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_transaction.return_value.__enter__.return_value = mock_conn

        result = merge_business_records(1, 2)

        assert result is True

        # Verify all merge operations were executed
        assert mock_cursor.execute.call_count == 4

        # Check merge queries
        calls = mock_cursor.execute.call_args_list

        # Update businesses_json_responses
        assert "UPDATE businesses_json_responses" in calls[0][0][0]
        assert calls[0][0][1] == (1, 2)

        # Update businesses_websites
        assert "UPDATE businesses_websites" in calls[1][0][0]
        assert calls[1][0][1] == (1, 2)

        # Log merge
        assert "INSERT INTO dedupe_log" in calls[2][0][0]
        assert calls[2][0][1] == (1, 2)

        # Delete secondary business
        assert "DELETE FROM businesses" in calls[3][0][0]
        assert calls[3][0][1] == (2,)

    @patch("leadfactory.utils.e2e_db_connector.db_transaction")
    def test_merge_business_records_failure(self, mock_db_transaction):
        """Test merge failure handling."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_db_transaction.return_value.__enter__.return_value = mock_conn

        result = merge_business_records(1, 2)

        assert result is False

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_update_business_fields(self, mock_db_cursor):
        """Test updating business fields."""
        mock_cursor = MagicMock()
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        updates = {
            "phone": "555-9999",
            "email": "new@example.com",
            "category": "Updated Category",
        }

        result = update_business_fields(1, updates)

        assert result is True

        # Verify query construction
        mock_cursor.execute.assert_called_once()
        query = mock_cursor.execute.call_args[0][0]
        values = mock_cursor.execute.call_args[0][1]

        assert "UPDATE businesses" in query
        assert "phone = %s" in query
        assert "email = %s" in query
        assert "category = %s" in query
        assert "updated_at = NOW()" in query
        assert "WHERE id = %s" in query

        # Check values (last one should be the ID)
        assert values[-1] == 1
        assert "555-9999" in values
        assert "new@example.com" in values

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_update_business_fields_empty(self, mock_db_cursor):
        """Test updating with no fields."""
        result = update_business_fields(1, {})

        assert result is True
        # Should not execute any query
        mock_db_cursor.assert_not_called()

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_add_to_review_queue(self, mock_db_cursor):
        """Test adding to review queue."""
        mock_cursor = MagicMock()
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = add_to_review_queue(1, 2, "Low confidence match", 0.65)

        assert result is True

        # Verify both queries were executed
        assert mock_cursor.execute.call_count == 2

        # Check update businesses query
        update_query = mock_cursor.execute.call_args_list[0][0][0]
        assert "UPDATE businesses" in update_query
        assert "flagged_for_review = true" in update_query

        # Check insert into review_queue
        insert_query = mock_cursor.execute.call_args_list[1][0][0]
        assert "INSERT INTO review_queue" in insert_query
        assert mock_cursor.execute.call_args_list[1][0][1] == (
            1,
            2,
            "Low confidence match",
            0.65,
        )

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_check_dedupe_tables_exist(self, mock_db_cursor):
        """Test checking if dedupe tables exist."""
        mock_cursor = MagicMock()
        # Mock both tables exist
        mock_cursor.fetchone.side_effect = [("dedupe_log",), ("review_queue",)]
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = check_dedupe_tables_exist()

        assert result is True
        assert mock_cursor.execute.call_count == 2

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_check_dedupe_tables_not_exist(self, mock_db_cursor):
        """Test checking when dedupe tables don't exist."""
        mock_cursor = MagicMock()
        # Mock first table exists, second doesn't
        mock_cursor.fetchone.side_effect = [("dedupe_log",), None]
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = check_dedupe_tables_exist()

        assert result is False

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_create_dedupe_tables(self, mock_db_cursor):
        """Test creating dedupe tables."""
        mock_cursor = MagicMock()
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = create_dedupe_tables()

        assert result is True

        # Should execute multiple CREATE TABLE statements
        assert mock_cursor.execute.call_count >= 2

        # Check for table creation
        calls = [call[0][0] for call in mock_cursor.execute.call_args_list]

        # Should create extension
        assert any(
            "CREATE EXTENSION IF NOT EXISTS fuzzystrmatch" in call for call in calls
        )

        # Should create dedupe_log table
        assert any("CREATE TABLE IF NOT EXISTS dedupe_log" in call for call in calls)

        # Should create review_queue table
        assert any("CREATE TABLE IF NOT EXISTS review_queue" in call for call in calls)

    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_create_dedupe_tables_failure(self, mock_db_cursor):
        """Test handling failure when creating tables."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Cannot create table")
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        result = create_dedupe_tables()

        assert result is False


class TestDedupeConnectorIntegration:
    """Integration tests for dedupe connector functions."""

    @patch("leadfactory.utils.e2e_db_connector.db_transaction")
    @patch("leadfactory.utils.e2e_db_connector.db_cursor")
    def test_full_merge_workflow(self, mock_db_cursor, mock_db_transaction):
        """Test complete merge workflow."""
        # Mock getting business details
        mock_cursor_get = MagicMock()
        mock_cursor_get.fetchone.side_effect = [
            # First business
            (
                1,
                "Business A",
                "555-1234",
                None,
                None,
                "123 Main St",
                "City",
                "ST",
                "12345",
                "Restaurant",
                "google",
                False,
                False,
                '{"google": "data"}',
                None,
                None,
                datetime.now(),
                datetime.now(),
            ),
            # Second business
            (
                2,
                "Business A Inc",
                None,
                "email@test.com",
                "www.test.com",
                "123 Main Street",
                "City",
                "ST",
                "12345",
                "Restaurant",
                "yelp",
                False,
                False,
                None,
                '{"yelp": "data"}',
                None,
                datetime.now(),
                datetime.now(),
            ),
        ]
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor_get

        # Get business details
        business1 = get_business_details(1)
        business2 = get_business_details(2)

        assert business1["phone"] == "555-1234"
        assert business2["email"] == "email@test.com"

        # Mock update fields
        mock_cursor_update = MagicMock()
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor_update

        # Update primary with secondary's data
        updates = {"email": business2["email"], "website": business2["website"]}
        update_result = update_business_fields(1, updates)
        assert update_result is True

        # Mock merge
        mock_conn = MagicMock()
        mock_cursor_merge = MagicMock()
        mock_conn.cursor.return_value = mock_cursor_merge
        mock_db_transaction.return_value.__enter__.return_value = mock_conn

        # Perform merge
        merge_result = merge_business_records(1, 2)
        assert merge_result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
