"""
Unit tests for data preservation module.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadfactory.pipeline.data_preservation import (
    DataPreservationManager,
    with_data_preservation,
)


class TestDataPreservationManager(unittest.TestCase):
    """Test cases for DataPreservationManager."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DataPreservationManager(backup_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("leadfactory.pipeline.data_preservation.db_connection")
    def test_ensure_audit_tables(self, mock_connection):
        """Test audit table creation."""
        mock_cursor_instance = MagicMock()
        mock_conn_instance = MagicMock()
        mock_conn_instance.cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_connection.return_value.__enter__.return_value = mock_conn_instance

        # Create a new manager to trigger table creation
        DataPreservationManager(backup_dir=self.temp_dir)

        # Verify tables were created
        self.assertTrue(mock_cursor_instance.execute.called)
        self.assertTrue(mock_conn_instance.commit.called)

    @patch("leadfactory.pipeline.data_preservation.get_business_details")
    @patch("leadfactory.pipeline.data_preservation.db_cursor")
    def test_create_backup(self, mock_cursor, mock_get_business):
        """Test backup creation."""
        # Mock business data
        mock_get_business.side_effect = [
            {"id": 1, "name": "Business 1", "email": "test1@example.com"},
            {"id": 2, "name": "Business 2", "email": "test2@example.com"}
        ]

        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance

        # Create backup
        backup_id = self.manager.create_backup([1, 2], "merge")

        self.assertIsNotNone(backup_id)

        # Verify backup file exists
        backup_files = os.listdir(self.temp_dir)
        self.assertEqual(len(backup_files), 1)

        # Verify backup content
        with open(os.path.join(self.temp_dir, backup_files[0])) as f:
            backup_data = json.load(f)

        self.assertEqual(backup_data["operation_type"], "merge")
        self.assertIn("1", backup_data["businesses"])
        self.assertIn("2", backup_data["businesses"])

    @patch("leadfactory.pipeline.data_preservation.db_cursor")
    def test_log_operation(self, mock_cursor):
        """Test operation logging."""
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance

        self.manager.log_operation(
            operation_type="merge",
            business1_id=1,
            business2_id=2,
            operation_data={"test": "data"},
            status="success"
        )

        # Verify insert was called
        mock_cursor_instance.execute.assert_called_once()
        call_args = mock_cursor_instance.execute.call_args[0]
        self.assertIn("INSERT INTO dedupe_audit_log", call_args[0])

    @patch("leadfactory.pipeline.data_preservation.db_cursor")
    def test_get_audit_trail(self, mock_cursor):
        """Test audit trail retrieval."""
        mock_cursor_instance = MagicMock()
        mock_cursor_instance.fetchall.return_value = [
            (1, "merge", 1, 2, "{}", None, "success", None, datetime.now())
        ]
        mock_cursor_instance.description = [
            ("id",), ("operation_type",), ("business1_id",), ("business2_id",),
            ("operation_data",), ("user_id",), ("status",), ("error_message",),
            ("created_at",)
        ]
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance

        # Get audit trail
        trail = self.manager.get_audit_trail(business_id=1)

        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0]["operation_type"], "merge")
        self.assertEqual(trail[0]["business1_id"], 1)

    @patch("leadfactory.pipeline.data_preservation.db_connection")
    def test_savepoint_operations(self, mock_connection):
        """Test savepoint operations."""
        mock_cursor_instance = MagicMock()
        mock_conn_instance = MagicMock()
        mock_conn_instance.cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_connection.return_value.__enter__.return_value = mock_conn_instance

        # Test create savepoint
        result = self.manager.create_transaction_savepoint("test_savepoint")
        self.assertTrue(result)
        mock_cursor_instance.execute.assert_called_with("SAVEPOINT test_savepoint")

        # Test rollback
        result = self.manager.rollback_to_savepoint("test_savepoint")
        self.assertTrue(result)
        mock_cursor_instance.execute.assert_called_with("ROLLBACK TO SAVEPOINT test_savepoint")

        # Test release
        result = self.manager.release_savepoint("test_savepoint")
        self.assertTrue(result)
        mock_cursor_instance.execute.assert_called_with("RELEASE SAVEPOINT test_savepoint")


class TestDataPreservationDecorator(unittest.TestCase):
    """Test cases for data preservation decorator."""

    @patch("leadfactory.pipeline.data_preservation.DataPreservationManager")
    def test_with_data_preservation_success(self, mock_manager_class):
        """Test decorator with successful operation."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.create_backup.return_value = "backup_123"

        @with_data_preservation("test_operation")
        def test_function(id1, id2):
            return id1 + id2

        result = test_function(1, 2)

        self.assertEqual(result, 3)
        mock_manager.create_backup.assert_called_once_with([1, 2], "test_operation")
        mock_manager.create_transaction_savepoint.assert_called_once()
        mock_manager.release_savepoint.assert_called_once()
        mock_manager.log_operation.assert_called()

    @patch("leadfactory.pipeline.data_preservation.DataPreservationManager")
    def test_with_data_preservation_failure(self, mock_manager_class):
        """Test decorator with failed operation."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.create_backup.return_value = "backup_123"

        @with_data_preservation("test_operation")
        def test_function(id1, id2):
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            test_function(1, 2)

        mock_manager.create_backup.assert_called_once_with([1, 2], "test_operation")
        mock_manager.create_transaction_savepoint.assert_called_once()
        mock_manager.rollback_to_savepoint.assert_called_once()
        mock_manager.release_savepoint.assert_not_called()

        # Check that failure was logged
        log_calls = mock_manager.log_operation.call_args_list
        self.assertTrue(any(call[1]["status"] == "failed" for call in log_calls))


if __name__ == "__main__":
    unittest.main()
