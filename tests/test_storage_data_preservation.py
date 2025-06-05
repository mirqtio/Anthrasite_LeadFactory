"""
Unit tests for storage interface data preservation methods.
"""

import json
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, mock_open, patch

try:
    # Try to import the actual modules
    from leadfactory.pipeline.data_preservation import DataPreservationManager
    from leadfactory.storage.factory import get_storage
    from leadfactory.storage.interface import StorageInterface
    from leadfactory.storage.postgres_storage import PostgresStorage

    IMPORTS_AVAILABLE = True
except ImportError:
    # Create mock classes if imports fail
    class StorageInterface:
        pass

    class PostgresStorage:
        pass

    class DataPreservationManager:
        pass

    def get_storage():
        return Mock()

    IMPORTS_AVAILABLE = False

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStorageDataPreservation(unittest.TestCase):
    """Test cases for storage interface data preservation methods."""

    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Leadfactory modules not available")

        # Create mock connection and cursor with proper context manager support
        self.mock_connection = Mock()
        self.mock_cursor = Mock()

        # Set up cursor context manager properly
        cursor_context = Mock()
        cursor_context.__enter__ = Mock(return_value=self.mock_cursor)
        cursor_context.__exit__ = Mock(return_value=None)
        self.mock_connection.cursor.return_value = cursor_context

        # Create PostgresStorage instance with mocked database functions
        with patch(
            "leadfactory.storage.postgres_storage.db_connection"
        ) as mock_db_conn:
            mock_db_conn.return_value.__enter__.return_value = self.mock_connection
            mock_db_conn.return_value.__exit__.return_value = None
            self.storage = PostgresStorage()

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, "storage"):
            # Reset mock calls
            self.mock_connection.reset_mock()
            self.mock_cursor.reset_mock()

    def test_record_backup_metadata(self):
        """Test recording backup metadata."""
        # Setup
        backup_id = "backup_123"
        operation_type = "merge"
        business_ids = [1, 2, 3]
        backup_path = "/path/to/backup"
        backup_size = 1024
        checksum = "abc123"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.record_backup_metadata(
            backup_id, operation_type, business_ids, backup_path, backup_size, checksum
        )

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called()
        self.mock_connection.commit.assert_called()

    def test_get_backup_metadata(self):
        """Test retrieving backup metadata."""
        # Setup
        backup_id = "backup_123"
        {
            "backup_id": backup_id,
            "operation_type": "merge",
            "business_ids": [1, 2, 3],
            "backup_path": "/path/to/backup",
            "backup_size": 1024,
            "checksum": "abc123",
            "created_at": datetime.now(),
            "restored_at": None,
            "restored_by": None,
        }

        # Mock cursor to return metadata
        self.mock_cursor.fetchone.return_value = (
            backup_id,
            "merge",
            [1, 2, 3],
            "/path/to/backup",
            1024,
            "abc123",
            datetime.now(),
            None,
            None,
        )

        # Execute
        result = self.storage.get_backup_metadata(backup_id)

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(result["backup_id"], backup_id)
        self.mock_cursor.execute.assert_called()

    def test_get_backup_metadata_not_found(self):
        """Test retrieving non-existent backup metadata."""
        # Setup
        backup_id = "nonexistent"
        self.mock_cursor.fetchone.return_value = None

        # Execute
        result = self.storage.get_backup_metadata(backup_id)

        # Verify
        self.assertIsNone(result)

    def test_update_backup_restored(self):
        """Test updating backup as restored."""
        # Setup
        backup_id = "backup_123"
        user_id = "user_456"

        # Mock cursor to return affected rows
        self.mock_cursor.rowcount = 1

        # Execute
        result = self.storage.update_backup_restored(backup_id, user_id)

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called()
        self.mock_connection.commit.assert_called()

    def test_update_backup_restored_not_found(self):
        """Test updating non-existent backup."""
        # Setup
        backup_id = "nonexistent"
        self.mock_cursor.rowcount = 0

        # Execute
        result = self.storage.update_backup_restored(backup_id)

        # Verify
        self.assertFalse(result)

    def test_log_dedupe_operation(self):
        """Test logging deduplication operation."""
        # Setup
        operation_type = "merge"
        business1_id = 1
        business2_id = 2
        operation_data = {"test": "data"}
        status = "success"
        user_id = "user_123"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.log_dedupe_operation(
            operation_type,
            business1_id,
            business2_id,
            operation_data,
            status,
            None,
            user_id,
        )

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called()
        self.mock_connection.commit.assert_called()

    def test_log_dedupe_operation_with_error(self):
        """Test logging failed deduplication operation."""
        # Setup
        operation_type = "merge"
        business1_id = 1
        business2_id = 2
        operation_data = {"test": "data"}
        status = "failed"
        error_message = "Test error"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.log_dedupe_operation(
            operation_type,
            business1_id,
            business2_id,
            operation_data,
            status,
            error_message,
        )

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called()
        self.mock_connection.commit.assert_called()

    def test_get_audit_trail(self):
        """Test retrieving audit trail."""
        # Setup
        business_id = 1
        [
            {
                "operation_type": "merge",
                "business1_id": 1,
                "business2_id": 2,
                "operation_data": {"test": "data"},
                "status": "success",
                "error_message": None,
                "created_at": datetime.now(),
                "user_id": "user_123",
            }
        ]

        # Mock cursor to return trail data
        self.mock_cursor.fetchall.return_value = [
            (
                "merge",
                1,
                2,
                {"test": "data"},
                "success",
                None,
                datetime.now(),
                "user_123",
            )
        ]

        # Execute
        result = self.storage.get_audit_trail(business_id)

        # Verify
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["operation_type"], "merge")
        self.mock_cursor.execute.assert_called()

    def test_create_savepoint(self):
        """Test creating transaction savepoint."""
        # Setup
        savepoint_name = "test_savepoint"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.create_savepoint(savepoint_name)

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_with(f"SAVEPOINT {savepoint_name}")

    def test_rollback_to_savepoint(self):
        """Test rolling back to savepoint."""
        # Setup
        savepoint_name = "test_savepoint"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.rollback_to_savepoint(savepoint_name)

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_with(
            f"ROLLBACK TO SAVEPOINT {savepoint_name}"
        )

    def test_release_savepoint(self):
        """Test releasing savepoint."""
        # Setup
        savepoint_name = "test_savepoint"

        # Mock successful execution
        self.mock_cursor.execute.return_value = None

        # Execute
        result = self.storage.release_savepoint(savepoint_name)

        # Verify
        self.assertTrue(result)
        self.mock_cursor.execute.assert_called_with(
            f"RELEASE SAVEPOINT {savepoint_name}"
        )

    def test_get_related_business_data(self):
        """Test retrieving related business data."""
        # Setup
        business_ids = [1, 2, 3]

        # Mock cursor to return business data
        self.mock_cursor.fetchall.return_value = [
            (1, "Business 1", "123-456-7890"),
            (2, "Business 2", "234-567-8901"),
            (3, "Business 3", "345-678-9012"),
        ]

        # Execute
        result = self.storage.get_related_business_data(business_ids)

        # Verify
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["name"], "Business 1")
        self.mock_cursor.execute.assert_called()

    def test_database_error_handling(self):
        """Test handling of database errors."""
        # Setup
        self.mock_cursor.execute.side_effect = Exception("Database error")

        # Execute and verify exception handling
        result = self.storage.record_backup_metadata(
            "test", "merge", [1], "/path", 1024, "checksum"
        )
        self.assertFalse(result)

        result = self.storage.log_dedupe_operation("merge", 1, 2, {}, "success")
        self.assertFalse(result)

        result = self.storage.create_savepoint("test")
        self.assertFalse(result)


class TestDataPreservationManager(unittest.TestCase):
    """Test cases for DataPreservationManager using storage interface."""

    def setUp(self):
        """Set up test fixtures."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Leadfactory modules not available")

        # Create mock storage
        self.mock_storage = Mock(spec=StorageInterface)

        # Create DataPreservationManager with mocked storage by patching the decorator
        with patch(
            "leadfactory.pipeline.data_preservation.get_storage",
            return_value=self.mock_storage,
        ):
            self.manager = DataPreservationManager()
            # Manually set the storage to our mock since the decorator might not work in tests
            self.manager.storage = self.mock_storage

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, "mock_storage"):
            self.mock_storage.reset_mock()

    def test_create_backup_with_storage(self):
        """Test backup creation using storage interface."""
        # Setup
        business_ids = [1, 2, 3]
        operation_type = "merge"

        self.mock_storage.record_backup_metadata.return_value = True
        self.mock_storage.get_related_business_data.return_value = [
            {"id": 1, "name": "Business 1"},
            {"id": 2, "name": "Business 2"},
            {"id": 3, "name": "Business 3"},
        ]

        # Execute
        result = self.manager.create_backup(business_ids, operation_type)

        # Verify
        self.assertIsNotNone(result)  # Should return a generated backup ID
        self.assertTrue(
            result.startswith(operation_type)
        )  # Should start with operation type
        self.mock_storage.record_backup_metadata.assert_called_once()
        self.mock_storage.get_related_business_data.assert_called_once_with(
            business_ids
        )

    def test_restore_backup_with_storage(self):
        """Test backup restoration using storage interface."""
        # Setup
        backup_id = "backup_123"
        user_id = "user_456"

        self.mock_storage.get_backup_metadata.return_value = {
            "backup_id": backup_id,
            "business_ids": [1, 2, 3],
            "backup_path": "/path/to/backup",
            "checksum": "abc123",
        }
        self.mock_storage.update_backup_restored.return_value = True

        # Mock file operations
        with (
            patch("builtins.open", mock_open(read_data='{"test": "data"}')),
            patch("os.path.exists", return_value=True),
            patch("hashlib.sha256") as mock_hash,
        ):
            mock_hash.return_value.hexdigest.return_value = "abc123"

            # Execute
            result = self.manager.restore_backup(backup_id, user_id)

        # Verify
        self.assertTrue(result)
        self.mock_storage.get_backup_metadata.assert_called_once_with(backup_id)
        self.mock_storage.update_backup_restored.assert_called_once_with(
            backup_id, user_id
        )

    def test_log_operation_with_storage(self):
        """Test operation logging using storage interface."""
        # Setup
        operation_type = "merge"
        business1_id = 1
        business2_id = 2
        operation_data = {"test": "data"}
        status = "success"

        self.mock_storage.log_dedupe_operation.return_value = True

        # Execute
        self.manager.log_operation(
            operation_type, business1_id, business2_id, operation_data, status
        )

        # Verify
        self.mock_storage.log_dedupe_operation.assert_called_once_with(
            operation_type,
            business1_id,
            business2_id,
            operation_data,
            status,
            None,
            None,
        )

    def test_get_audit_trail_with_storage(self):
        """Test audit trail retrieval using storage interface."""
        # Setup
        business_id = 1
        expected_trail = [{"operation_type": "merge", "status": "success"}]

        self.mock_storage.get_audit_trail.return_value = expected_trail

        # Execute
        result = self.manager.get_audit_trail(business_id)

        # Verify
        self.assertEqual(result, expected_trail)
        # The actual call includes additional parameters with defaults
        self.mock_storage.get_audit_trail.assert_called_once_with(
            business_id, None, None, None, 100
        )

    def test_transaction_savepoints_with_storage(self):
        """Test transaction savepoint operations using storage interface."""
        # Setup
        savepoint_name = "test_savepoint"

        self.mock_storage.create_savepoint.return_value = True
        self.mock_storage.rollback_to_savepoint.return_value = True
        self.mock_storage.release_savepoint.return_value = True

        # Execute
        create_result = self.manager.create_transaction_savepoint(savepoint_name)
        rollback_result = self.manager.rollback_to_savepoint(savepoint_name)
        release_result = self.manager.release_savepoint(savepoint_name)

        # Verify
        self.assertTrue(create_result)
        self.assertTrue(rollback_result)
        self.assertTrue(release_result)

        self.mock_storage.create_savepoint.assert_called_once_with(savepoint_name)
        self.mock_storage.rollback_to_savepoint.assert_called_once_with(savepoint_name)
        self.mock_storage.release_savepoint.assert_called_once_with(savepoint_name)


if __name__ == "__main__":
    unittest.main()
