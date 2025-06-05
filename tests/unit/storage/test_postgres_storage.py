"""
Comprehensive tests for PostgreSQL storage implementation.

This module tests the PostgresStorage class, including connection management,
CRUD operations, transactions, and error handling.
"""

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, patch, call, mock_open

import pytest

from leadfactory.storage.postgres_storage import PostgresStorage


class TestPostgresStorage:
    """Test cases for PostgresStorage implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_config = {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_pass",
        }
        self.storage = PostgresStorage(self.test_config)

    def test_init_with_config(self):
        """Test initialization with configuration dictionary."""
        storage = PostgresStorage(self.test_config)
        assert storage.config == self.test_config

    def test_init_without_config(self):
        """Test initialization without configuration."""
        storage = PostgresStorage()
        assert storage.config == {}

    @patch("leadfactory.storage.postgres_storage.db_connection")
    def test_connection_context_manager(self, mock_db_connection):
        """Test connection context manager."""
        mock_conn = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn

        with self.storage.connection() as conn:
            assert conn == mock_conn

        mock_db_connection.assert_called_once()

    @patch("leadfactory.storage.postgres_storage.db_cursor")
    def test_cursor_context_manager(self, mock_db_cursor):
        """Test cursor context manager."""
        mock_cursor = MagicMock()
        mock_db_cursor.return_value.__enter__.return_value = mock_cursor

        with self.storage.cursor() as cursor:
            assert cursor == mock_cursor

        mock_db_cursor.assert_called_once()

    @patch("leadfactory.storage.postgres_storage.execute_query")
    def test_execute_query_success(self, mock_execute_query):
        """Test successful query execution."""
        mock_results = [
            {"id": 1, "name": "Business 1"},
            {"id": 2, "name": "Business 2"}
        ]
        mock_execute_query.return_value = mock_results

        results = self.storage.execute_query("SELECT * FROM businesses", fetch=True)

        assert results == mock_results
        mock_execute_query.assert_called_once_with("SELECT * FROM businesses", None, True)

    @patch("leadfactory.storage.postgres_storage.execute_query")
    def test_execute_query_no_fetch(self, mock_execute_query):
        """Test query execution without fetching results."""
        mock_execute_query.return_value = None

        results = self.storage.execute_query("UPDATE businesses SET name = 'New'", fetch=False)

        assert results == []
        mock_execute_query.assert_called_once_with("UPDATE businesses SET name = 'New'", None, False)

    @patch("leadfactory.storage.postgres_storage.execute_query")
    def test_execute_query_tuple_results(self, mock_execute_query):
        """Test query execution that returns tuples."""
        mock_execute_query.return_value = [(1, "Business 1"), (2, "Business 2")]

        results = self.storage.execute_query("SELECT id, name FROM businesses")

        # Should convert tuples to dictionaries
        assert results == [{"result": (1, "Business 1")}, {"result": (2, "Business 2")}]

    @patch("leadfactory.storage.postgres_storage.execute_query")
    def test_execute_query_error(self, mock_execute_query):
        """Test query execution with error."""
        mock_execute_query.side_effect = Exception("Database error")

        results = self.storage.execute_query("SELECT * FROM businesses")

        assert results == []

    @patch("leadfactory.storage.postgres_storage.execute_transaction")
    def test_execute_transaction_success(self, mock_execute_transaction):
        """Test successful transaction execution."""
        mock_execute_transaction.return_value = True

        queries = [
            ("INSERT INTO businesses (name) VALUES (%s)", ("Business 1",)),
            ("UPDATE businesses SET active = true WHERE name = %s", ("Business 1",))
        ]

        result = self.storage.execute_transaction(queries)

        assert result is True
        mock_execute_transaction.assert_called_once_with(queries)

    @patch("leadfactory.storage.postgres_storage.execute_transaction")
    def test_execute_transaction_failure(self, mock_execute_transaction):
        """Test transaction execution failure."""
        mock_execute_transaction.side_effect = Exception("Transaction failed")

        result = self.storage.execute_transaction([])

        assert result is False

    @patch("leadfactory.storage.postgres_storage.check_connection")
    def test_check_connection_success(self, mock_check_connection):
        """Test successful connection check."""
        mock_check_connection.return_value = True

        result = self.storage.check_connection()

        assert result is True
        mock_check_connection.assert_called_once()

    @patch("leadfactory.storage.postgres_storage.check_connection")
    def test_check_connection_failure(self, mock_check_connection):
        """Test connection check failure."""
        mock_check_connection.side_effect = Exception("Connection error")

        result = self.storage.check_connection()

        assert result is False

    @patch("leadfactory.storage.postgres_storage.validate_schema")
    def test_validate_schema_success(self, mock_validate_schema):
        """Test successful schema validation."""
        mock_validate_schema.return_value = True

        result = self.storage.validate_schema()

        assert result is True
        mock_validate_schema.assert_called_once()

    @patch("leadfactory.storage.postgres_storage.validate_schema")
    def test_validate_schema_failure(self, mock_validate_schema):
        """Test schema validation failure."""
        mock_validate_schema.side_effect = Exception("Schema error")

        result = self.storage.validate_schema()

        assert result is False

    def test_get_business_by_id(self):
        """Test getting business by ID."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test with dictionary result
            mock_cursor.fetchone.return_value = {"id": 1, "name": "Test Business"}

            result = self.storage.get_business_by_id(1)

            assert result == {"id": 1, "name": "Test Business"}
            mock_cursor.execute.assert_called_once()

            # Test with tuple result
            mock_cursor.fetchone.return_value = (1, "Test Business")
            mock_cursor.description = [("id",), ("name",)]

            result = self.storage.get_business_by_id(1)

            assert result == {"id": 1, "name": "Test Business"}

    def test_get_business_by_id_not_found(self):
        """Test getting business by ID when not found."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None

            result = self.storage.get_business_by_id(999)

            assert result is None

    def test_get_businesses_by_criteria(self):
        """Test getting businesses by criteria."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test with dictionary results
            mock_cursor.fetchall.return_value = [
                {"id": 1, "name": "Business 1", "zip": "12345"},
                {"id": 2, "name": "Business 2", "zip": "12345"}
            ]

            criteria = {"zip": "12345", "active": None}
            result = self.storage.get_businesses_by_criteria(criteria, limit=10)

            assert len(result) == 2
            assert result[0]["name"] == "Business 1"

            # Verify SQL query construction
            call_args = mock_cursor.execute.call_args
            assert "zip = %s" in call_args[0][0]
            assert "active IS NULL" in call_args[0][0]
            assert "LIMIT 10" in call_args[0][0]

    def test_update_business(self):
        """Test updating business record."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor
            mock_cursor.rowcount = 1

            updates = {"name": "New Name", "email": "new@example.com"}
            result = self.storage.update_business(1, updates)

            assert result is True

            # Verify SQL query construction
            call_args = mock_cursor.execute.call_args
            assert "UPDATE businesses" in call_args[0][0]
            assert "name = %s" in call_args[0][0]
            assert "email = %s" in call_args[0][0]
            assert call_args[0][1] == ("New Name", "new@example.com", 1)

    def test_insert_business(self):
        """Test inserting new business record."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (123,)

            business_data = {
                "name": "Test Business",
                "address": "123 Main St",
                "zip": "12345"
            }
            result = self.storage.insert_business(business_data)

            assert result == 123

            # Verify SQL query construction
            call_args = mock_cursor.execute.call_args
            assert "INSERT INTO businesses" in call_args[0][0]
            assert "RETURNING id" in call_args[0][0]

    def test_get_business_details(self):
        """Test getting detailed business information."""
        with patch.object(self.storage, 'execute_query') as mock_execute_query:
            mock_execute_query.return_value = [{
                "id": 1,
                "name": "Test Business",
                "google_response": '{"rating": 4.5}',
                "yelp_response": '{"rating": 4.0}'
            }]

            result = self.storage.get_business_details(1)

            assert result["id"] == 1
            assert result["name"] == "Test Business"
            assert "google_response" in result
            assert "yelp_response" in result

    def test_get_businesses(self):
        """Test getting multiple businesses by IDs."""
        with patch.object(self.storage, 'execute_query') as mock_execute_query:
            mock_execute_query.return_value = [
                {"id": 1, "name": "Business 1"},
                {"id": 3, "name": "Business 3"}
            ]

            result = self.storage.get_businesses([1, 3])

            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[1]["id"] == 3

            # Test empty list
            result = self.storage.get_businesses([])
            assert result == []

    @patch("leadfactory.utils.e2e_db_connector.merge_business_records")
    def test_merge_businesses(self, mock_merge):
        """Test merging businesses."""
        mock_merge.return_value = {"success": True}

        result = self.storage.merge_businesses(1, 2)

        assert result is True
        mock_merge.assert_called_once_with(1, 2)

        # Test failure
        mock_merge.return_value = None
        result = self.storage.merge_businesses(1, 2)
        assert result is False

    def test_processing_status_operations(self):
        """Test processing status operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test get_processing_status with tuple result
            mock_cursor.fetchone.return_value = ("completed", '{"duration": 5}', datetime.now())

            result = self.storage.get_processing_status(1, "scrape")

            assert result["status"] == "completed"
            assert result["metadata"]["duration"] == 5

            # Test update_processing_status
            mock_cursor.rowcount = 1

            result = self.storage.update_processing_status(
                1, "scrape", "completed", {"duration": 5}
            )

            assert result is True

            # Verify SQL includes ON CONFLICT clause
            call_args = mock_cursor.execute.call_args
            assert "ON CONFLICT" in call_args[0][0]

    def test_stage_results_operations(self):
        """Test stage results operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test save_stage_results
            mock_cursor.rowcount = 1

            results = {"score": 85, "confidence": 0.9}
            result = self.storage.save_stage_results(1, "scoring", results)

            assert result is True

            # Test get_stage_results
            mock_cursor.fetchone.return_value = ('{"score": 85, "confidence": 0.9}',)

            result = self.storage.get_stage_results(1, "scoring")

            assert result["score"] == 85
            assert result["confidence"] == 0.9

    def test_business_lookup_methods(self):
        """Test various business lookup methods."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Setup mock return
            mock_cursor.fetchone.return_value = {"id": 1, "name": "Test Business"}
            mock_cursor.description = [("id",), ("name",)]

            # Test get_business_by_source_id
            result = self.storage.get_business_by_source_id("source123", "yelp")
            assert result["id"] == 1

            # Test get_business_by_website
            result = self.storage.get_business_by_website("https://example.com")
            assert result["id"] == 1

            # Test get_business_by_phone
            result = self.storage.get_business_by_phone("555-1234")
            assert result["id"] == 1

            # Test get_business_by_name_and_zip
            result = self.storage.get_business_by_name_and_zip("Test Business", "12345")
            assert result["id"] == 1

    def test_error_handling(self):
        """Test error handling in various methods."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            # Make cursor raise an exception
            mock_cursor_cm.side_effect = Exception("Database error")

            # All methods should handle errors gracefully
            assert self.storage.get_business_by_id(1) is None
            assert self.storage.get_businesses_by_criteria({}) == []
            assert self.storage.update_business(1, {}) is False
            assert self.storage.insert_business({}) is None
            assert self.storage.get_processing_status(1, "scrape") is None
            assert self.storage.update_processing_status(1, "scrape", "failed") is False
            assert self.storage.save_stage_results(1, "scrape", {}) is False
            assert self.storage.get_stage_results(1, "scrape") is None

    def test_review_queue_operations(self):
        """Test review queue operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test add_to_review_queue
            mock_cursor.fetchone.return_value = (123,)

            result = self.storage.add_to_review_queue(1, 2, "duplicate", "Same business")

            assert result == 123
            assert "INSERT INTO dedupe_review_queue" in mock_cursor.execute.call_args[0][0]

            # Test get_review_queue_items
            mock_cursor.fetchall.return_value = [
                (1, 10, 20, "duplicate", "pending"),
                (2, 30, 40, "conflict", "pending")
            ]
            mock_cursor.description = [("id",), ("business1_id",), ("business2_id",), ("reason",), ("status",)]

            result = self.storage.get_review_queue_items(status="pending", limit=10)

            assert len(result) == 2
            assert result[0]["reason"] == "duplicate"

            # Test update_review_status
            mock_cursor.rowcount = 1

            result = self.storage.update_review_status(1, "resolved", "Merged businesses")

            assert result is True
            assert "UPDATE dedupe_review_queue" in mock_cursor.execute.call_args[0][0]

    def test_review_statistics(self):
        """Test get_review_statistics method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Mock the three queries in get_review_statistics
            mock_cursor.fetchall.side_effect = [
                [("pending", 5), ("resolved", 10)],  # status counts
                [("duplicate", 8), ("conflict", 7)]  # top reasons
            ]
            mock_cursor.fetchone.return_value = (300.5,)  # avg resolution time

            result = self.storage.get_review_statistics()

            assert result["status_counts"]["pending"] == 5
            assert result["status_counts"]["resolved"] == 10
            assert result["avg_resolution_time_seconds"] == 300.5
            assert result["avg_resolution_time_readable"] == "5.0 minutes"
            assert len(result["top_reasons"]) == 2

    def test_asset_management_operations(self):
        """Test asset management operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test get_businesses_needing_screenshots
            mock_cursor.fetchall.return_value = [
                (1, "Business 1", "https://example1.com"),
                (2, "Business 2", "https://example2.com")
            ]

            result = self.storage.get_businesses_needing_screenshots(limit=10)

            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[0]["website"] == "https://example1.com"

            # Test create_asset
            mock_cursor.rowcount = 1

            result = self.storage.create_asset(1, "screenshot", "/path/to/file", "https://url")

            assert result is True
            assert "INSERT INTO assets" in mock_cursor.execute.call_args[0][0]

            # Test get_business_asset
            mock_cursor.fetchone.return_value = (1, 1, "screenshot", "/path", "https://url", datetime.now())
            mock_cursor.description = [("id",), ("business_id",), ("asset_type",), ("file_path",), ("url",), ("created_at",)]

            result = self.storage.get_business_asset(1, "screenshot")

            assert result["asset_type"] == "screenshot"
            assert result["file_path"] == "/path"

    def test_email_operations(self):
        """Test email-related operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test get_businesses_for_email
            mock_cursor.fetchall.return_value = [
                (1, "Business 1", "email1@example.com", "555-1234", "123 Main St",
                 "City", "ST", "12345", "https://example1.com", "https://mockup1.png",
                 "John Doe", 85, "Good lead")
            ]
            mock_cursor.description = [
                ("id",), ("name",), ("email",), ("phone",), ("address",),
                ("city",), ("state",), ("zip",), ("website",), ("mockup_url",),
                ("contact_name",), ("score",), ("notes",)
            ]

            result = self.storage.get_businesses_for_email(force=False, limit=10)

            assert len(result) == 1
            assert result[0]["email"] == "email1@example.com"
            assert result[0]["mockup_url"] == "https://mockup1.png"

            # Test check_unsubscribed
            mock_cursor.fetchone.return_value = ("unsubscribe_id",)

            result = self.storage.check_unsubscribed("test@example.com")

            assert result is True

            # Test is_email_unsubscribed
            mock_cursor.fetchone.return_value = None

            result = self.storage.is_email_unsubscribed("good@example.com")

            assert result is False

            # Test add_unsubscribe
            mock_cursor.fetchone.return_value = None  # Not already unsubscribed
            mock_cursor.rowcount = 1

            result = self.storage.add_unsubscribe("new@example.com", "User request", "192.168.1.1", "Mozilla/5.0")

            assert result is True

    def test_email_logging_operations(self):
        """Test email logging operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test record_email_sent
            mock_cursor.rowcount = 1

            email_data = {"subject": "Test Subject", "content": "Test Content"}
            result = self.storage.record_email_sent(1, email_data)

            assert result is True

            # Test log_email_sent
            result = self.storage.log_email_sent(
                1, "test@example.com", "Test User", "Subject", "msg_123", "sent", None
            )

            assert result is True

            # Test save_email_record
            result = self.storage.save_email_record(
                1, "test@example.com", "Test User", "Subject", "msg_123", "sent", None
            )

            assert result is True

    def test_email_stats(self):
        """Test get_email_stats method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Mock the various count queries
            mock_cursor.fetchone.side_effect = [
                (100,),  # total_sent
                (10,),   # sent_today
                (80,),   # businesses_emailed
                (120,)   # total_businesses_with_email
            ]

            result = self.storage.get_email_stats()

            assert result["total_sent"] == 100
            assert result["sent_today"] == 10
            assert result["businesses_emailed"] == 80
            assert result["total_businesses_with_email"] == 120
            assert result["email_coverage"] == pytest.approx(66.67, rel=0.01)

    def test_read_text(self):
        """Test read_text method."""
        with patch("builtins.open", mock_open(read_data="Test content")):
            result = self.storage.read_text("/path/to/file.txt")
            assert result == "Test content"

        # Test error handling
        with patch("builtins.open", side_effect=IOError("File not found")):
            with pytest.raises(IOError):
                self.storage.read_text("/nonexistent/file.txt")

    def test_data_preservation_operations(self):
        """Test data preservation and audit operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test record_backup_metadata
            result = self.storage.record_backup_metadata(
                "backup_123", "merge", [1, 2, 3], "/backups/backup_123.json",
                1024, "sha256_hash"
            )

            assert result is True

            # Test get_backup_metadata
            mock_cursor.fetchone.return_value = (
                "backup_123", "merge", [1, 2, 3], "/backups/backup_123.json",
                1024, "sha256_hash", datetime.now(), None, None
            )
            mock_cursor.description = [
                ("backup_id",), ("operation_type",), ("business_ids",), ("backup_path",),
                ("backup_size",), ("checksum",), ("created_at",), ("restored_at",), ("restored_by",)
            ]

            result = self.storage.get_backup_metadata("backup_123")

            assert result["backup_id"] == "backup_123"
            assert result["operation_type"] == "merge"
            assert result["business_ids"] == [1, 2, 3]

            # Test update_backup_restored
            result = self.storage.update_backup_restored("backup_123", "user123")

            assert result is True

    def test_audit_trail_operations(self):
        """Test audit trail operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test log_dedupe_operation
            result = self.storage.log_dedupe_operation(
                "merge", 1, 2, {"action": "merge_duplicate"}, "success", None, "user123"
            )

            assert result is True

            # Test get_audit_trail
            mock_cursor.fetchall.return_value = [
                (1, "merge", 1, 2, '{"action": "merge_duplicate"}', "user123", "success", None, datetime.now())
            ]
            mock_cursor.description = [
                ("id",), ("operation_type",), ("business1_id",), ("business2_id",),
                ("operation_data",), ("user_id",), ("status",), ("error_message",), ("created_at",)
            ]

            result = self.storage.get_audit_trail(business_id=1, limit=10)

            assert len(result) == 1
            assert result[0]["operation_type"] == "merge"
            assert result[0]["status"] == "success"

    def test_savepoint_operations(self):
        """Test database savepoint operations."""
        with patch.object(self.storage, 'connection') as mock_connection_cm:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn.cursor.return_value.__exit__.return_value = None
            mock_connection_cm.return_value.__enter__.return_value = mock_conn
            mock_connection_cm.return_value.__exit__.return_value = None

            # Test create_savepoint
            result = self.storage.create_savepoint("test_savepoint")
            assert result is True
            mock_cursor.execute.assert_called_with("SAVEPOINT test_savepoint")

            # Test rollback_to_savepoint
            result = self.storage.rollback_to_savepoint("test_savepoint")
            assert result is True
            mock_cursor.execute.assert_called_with("ROLLBACK TO SAVEPOINT test_savepoint")

            # Test release_savepoint
            result = self.storage.release_savepoint("test_savepoint")
            assert result is True
            mock_cursor.execute.assert_called_with("RELEASE SAVEPOINT test_savepoint")

    def test_ensure_audit_tables(self):
        """Test ensure_audit_tables method."""
        with patch.object(self.storage, 'connection') as mock_connection_cm:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn.cursor.return_value.__exit__.return_value = None
            mock_connection_cm.return_value.__enter__.return_value = mock_conn
            mock_connection_cm.return_value.__exit__.return_value = None

            result = self.storage.ensure_audit_tables()

            assert result is True
            # Should execute multiple CREATE TABLE statements
            assert mock_cursor.execute.call_count >= 2
            mock_conn.commit.assert_called_once()

    def test_log_management_operations(self):
        """Test log management operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test get_logs_with_filters
            mock_cursor.fetchone.return_value = (50,)  # total count
            mock_cursor.fetchall.return_value = [
                (1, 10, "llm", "Test prompt", datetime.now(), '{"model": "gpt-4"}', None, 100)
            ]
            mock_cursor.description = [
                ("id",), ("business_id",), ("log_type",), ("content",),
                ("timestamp",), ("metadata",), ("file_path",), ("content_length",)
            ]

            logs, total = self.storage.get_logs_with_filters(
                business_id=10, log_type="llm", limit=20, offset=0
            )

            assert total == 50
            assert len(logs) == 1
            assert logs[0]["log_type"] == "llm"

            # Test get_log_by_id
            mock_cursor.fetchone.side_effect = [
                (1, 10, "llm", "Test content", datetime.now(), '{"model": "gpt-4"}', None, 100),
                None
            ]

            result = self.storage.get_log_by_id(1)

            assert result["id"] == 1
            assert result["log_type"] == "llm"

    def test_log_statistics(self):
        """Test get_log_statistics method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Mock the various statistics queries
            mock_cursor.fetchone.side_effect = [
                (100,),  # llm_count
                (50,),   # html_count
                (datetime(2023, 1, 1), datetime(2023, 12, 31)),  # llm_dates
                (datetime(2023, 2, 1), datetime(2023, 11, 30))   # html_dates
            ]
            mock_cursor.fetchall.return_value = [
                (1, 25), (2, 20), (3, 15)  # business stats
            ]

            result = self.storage.get_log_statistics()

            assert result["total_logs"] == 150
            assert result["logs_by_type"]["llm"] == 100
            assert result["logs_by_type"]["raw_html"] == 50
            assert "date_range" in result
            assert "1" in result["logs_by_business"]

    def test_get_available_log_types(self):
        """Test get_available_log_types method."""
        result = self.storage.get_available_log_types()
        assert result == ["llm", "raw_html"]

    def test_get_businesses_with_logs(self):
        """Test get_businesses_with_logs method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            mock_cursor.fetchall.return_value = [
                (1, "Business 1"),
                (2, "Business 2")
            ]

            result = self.storage.get_businesses_with_logs()

            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[0]["name"] == "Business 1"

    def test_get_all_businesses(self):
        """Test get_all_businesses method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            mock_cursor.fetchall.return_value = [
                (1, "Business 1", "https://example1.com"),
                (2, "Business 2", "https://example2.com")
            ]

            result = self.storage.get_all_businesses()

            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[0]["website"] == "https://example1.com"

    def test_get_related_business_data(self):
        """Test get_related_business_data method."""
        # This method is mostly a placeholder in the current implementation
        result = self.storage.get_related_business_data(1)
        assert isinstance(result, dict)

    def test_vertical_operations(self):
        """Test vertical-related operations."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor

            # Test get_vertical_id
            mock_cursor.fetchone.return_value = (5,)

            result = self.storage.get_vertical_id("restaurant")

            assert result == 5

            # Test get_vertical_name
            mock_cursor.fetchone.return_value = ("restaurant",)

            result = self.storage.get_vertical_name(5)

            assert result == "restaurant"

    def test_create_business(self):
        """Test create_business method."""
        with patch.object(self.storage, 'cursor') as mock_cursor_cm:
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor_cm.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (123,)

            result = self.storage.create_business(
                "Test Business", "123 Main St", "12345", "restaurant",
                phone="555-1234", email="test@example.com", website="https://example.com",
                source="yelp", source_id="yelp_123",
                yelp_response_json={"rating": 4.5},
                google_response_json={"rating": 4.0}
            )

            assert result == 123
            # Verify complex INSERT query was executed
            assert "INSERT INTO businesses" in mock_cursor.execute.call_args[0][0]
            assert "SELECT id FROM verticals" in mock_cursor.execute.call_args[0][0]

    def test_format_duration(self):
        """Test _format_duration helper method."""
        assert self.storage._format_duration(30) == "30 seconds"
        assert self.storage._format_duration(90) == "1.5 minutes"
        assert self.storage._format_duration(3700) == "1.0 hours"
        assert self.storage._format_duration(90000) == "1.0 days"
