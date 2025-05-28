import unittest
import os
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from leadfactory.pipeline.data_preservation import DataPreservationManager


class TestDataPreservationSimple(unittest.TestCase):
    """Simple unit tests for data preservation functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for backups
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.temp_dir, 'backups')
        os.makedirs(self.backup_dir)

        # Set environment variable
        os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'

        # Create preservation manager with test backup directory
        self.manager = DataPreservationManager(backup_dir=self.backup_dir)

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)

        # Remove environment variable
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']

    @patch('leadfactory.pipeline.data_preservation.db_connection')
    @patch('leadfactory.pipeline.data_preservation.get_business_details')
    def test_create_backup(self, mock_get_business, mock_db_conn):
        """Test backup creation."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn

        # Mock business data
        mock_get_business.side_effect = [
            {'id': 1, 'name': 'Business A', 'email': 'a@example.com'},
            {'id': 2, 'name': 'Business B', 'email': 'b@example.com'}
        ]

        # Create backup
        backup_id = self.manager.create_backup([1, 2], 'test_merge')

        # Verify backup was created
        self.assertIsNotNone(backup_id)
        self.assertTrue(backup_id.startswith('test_merge_'))

        # Verify backup file exists
        backup_files = os.listdir(self.backup_dir)
        self.assertEqual(len(backup_files), 1)
        self.assertTrue(backup_files[0].endswith('.json'))

    @patch('leadfactory.pipeline.data_preservation.db_cursor')
    def test_log_operation(self, mock_db_cursor):
        """Test operation logging."""
        # Mock database cursor
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_db_cursor.return_value = mock_cursor

        # Log an operation
        self.manager.log_operation(
            operation_type='merge',
            business1_id=1,
            business2_id=2,
            operation_data={'merged_fields': ['name', 'email']},
            status='success'
        )

        # Verify the insert was called
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        self.assertIn('INSERT INTO dedupe_audit_log', call_args[0])

    @patch('leadfactory.pipeline.data_preservation.db_connection')
    def test_create_transaction_savepoint(self, mock_db_conn):
        """Test savepoint creation."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn

        # Create savepoint
        savepoint_name = 'test_savepoint_123'
        result = self.manager.create_transaction_savepoint(savepoint_name)

        # Verify savepoint was created
        self.assertTrue(result)

        # Verify SQL was executed
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        self.assertIn('SAVEPOINT', call_args[0])
        self.assertIn(savepoint_name, call_args[0])

    def test_backup_file_structure(self):
        """Test the structure of backup files."""
        # Create test data
        businesses = {
            '1': {
                'core_data': {'id': 1, 'name': 'Business A', 'email': 'a@example.com'},
                'related_data': {}
            },
            '2': {
                'core_data': {'id': 2, 'name': 'Business B', 'email': 'b@example.com'},
                'related_data': {}
            }
        }

        # Create backup file directly
        backup_id = f"test_{os.urandom(4).hex()}"
        backup_path = os.path.join(self.backup_dir, f"{backup_id}.json")

        backup_data = {
            'backup_id': backup_id,
            'operation_type': 'test',
            'businesses': businesses,
            'timestamp': '2023-01-01T00:00:00'
        }

        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)

        # Verify file exists and can be read
        self.assertTrue(os.path.exists(backup_path))

        with open(backup_path, 'r') as f:
            loaded_data = json.load(f)

        self.assertEqual(loaded_data['backup_id'], backup_id)
        self.assertEqual(len(loaded_data['businesses']), 2)

    @patch('leadfactory.pipeline.data_preservation.db_connection')
    def test_rollback_savepoint(self, mock_db_conn):
        """Test savepoint rollback."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_conn.return_value = mock_conn

        # Rollback savepoint
        savepoint_name = 'test_savepoint_123'
        result = self.manager.rollback_to_savepoint(savepoint_name)

        # Verify rollback was executed
        self.assertTrue(result)
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        self.assertIn('ROLLBACK TO SAVEPOINT', call_args[0])
        self.assertIn(savepoint_name, call_args[0])


if __name__ == '__main__':
    unittest.main()
