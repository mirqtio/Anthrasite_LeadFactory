"""
Tests for the Supabase usage monitoring script.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Add the parent directory to the path to import the script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.monitor_supabase_usage import SupabaseUsageMonitor


class TestSupabaseUsageMonitor(unittest.TestCase):
    """Test cases for the Supabase usage monitoring script."""

    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'SUPABASE_URL': 'https://test-project.supabase.co',
            'SUPABASE_KEY': 'test-key',
            'SUPABASE_SERVICE_KEY': 'test-service-key'
        })
        self.env_patcher.start()
        
        # Create the monitor instance
        self.monitor = SupabaseUsageMonitor()
        
        # Set up mock data
        self.mock_buckets = [
            {
                'name': 'test-bucket',
                'id': 'test-bucket-id',
                'created_at': '2025-01-01T00:00:00Z',
                'updated_at': '2025-01-01T00:00:00Z',
                'owner': 'test-owner',
                'public': False,
                'file_size_limit': 5242880,
                'allowed_mime_types': ['image/jpeg', 'image/png']
            }
        ]
        
        self.mock_objects = [
            {
                'name': 'test-object.jpg',
                'bucket_id': 'test-bucket-id',
                'owner': 'test-owner',
                'created_at': '2025-01-01T00:00:00Z',
                'updated_at': '2025-01-01T00:00:00Z',
                'metadata': {},
                'id': 'test-object-id',
                'size': 1048576  # 1 MB
            }
        ]
        
        self.mock_tables = [
            {
                'table_schema': 'public',
                'table_name': 'test_table',
                'size_bytes': 1048576,  # 1 MB
                'table_size_bytes': 524288,  # 0.5 MB
                'index_size_bytes': 524288,  # 0.5 MB
                'row_estimate': 1000
            }
        ]

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch('requests.get')
    def test_get_storage_usage(self, mock_get):
        """Test getting storage usage."""
        # Configure the mock responses
        mock_response_buckets = MagicMock()
        mock_response_buckets.status_code = 200
        mock_response_buckets.json.return_value = self.mock_buckets
        
        mock_response_objects = MagicMock()
        mock_response_objects.status_code = 200
        mock_response_objects.json.return_value = self.mock_objects
        
        # Set up the mock to return different responses for different URLs
        mock_get.side_effect = lambda url, headers, timeout: (
            mock_response_buckets if 'buckets' in url else mock_response_objects
        )
        
        # Call the method
        result = self.monitor.get_storage_usage()
        
        # Verify the result
        self.assertEqual(result['size_bytes'], 1048576)
        self.assertEqual(result['size_mb'], 1.0)
        self.assertEqual(len(result['buckets']), 1)
        self.assertEqual(result['buckets'][0]['name'], 'test-bucket')
        self.assertEqual(result['buckets'][0]['size_bytes'], 1048576)
        self.assertEqual(result['buckets'][0]['object_count'], 1)
        
        # Verify the percentage calculation
        expected_percentage = (1.0 / self.monitor.storage_limit_mb) * 100
        self.assertEqual(result['percentage_used'], expected_percentage)

    @patch('requests.post')
    def test_get_database_usage(self, mock_post):
        """Test getting database usage."""
        # Configure the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': self.mock_tables}
        
        mock_post.return_value = mock_response
        
        # Call the method
        result = self.monitor.get_database_usage()
        
        # Verify the result
        self.assertEqual(result['size_bytes'], 1048576)
        self.assertEqual(result['size_mb'], 1.0)
        self.assertEqual(len(result['tables']), 1)
        self.assertEqual(result['tables'][0]['name'], 'test_table')
        self.assertEqual(result['tables'][0]['size_bytes'], 1048576)
        self.assertEqual(result['tables'][0]['row_count'], 1000)
        
        # Verify the percentage calculations
        expected_size_percentage = (1.0 / self.monitor.database_size_limit_mb) * 100
        expected_row_percentage = (1000 / self.monitor.row_limit) * 100
        self.assertEqual(result['percentage_used'], expected_size_percentage)
        self.assertEqual(result['row_percentage_used'], expected_row_percentage)

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.symlink')
    @patch('os.path.abspath')
    def test_save_usage_report(self, mock_abspath, mock_symlink, mock_remove, mock_exists, mock_open, mock_makedirs):
        """Test saving the usage report."""
        # Configure the mocks
        mock_exists.return_value = True
        mock_abspath.return_value = '/absolute/path/to/report.json'
        
        # Create test data
        usage_data = {
            'timestamp': datetime.now().isoformat(),
            'storage': {'size_mb': 1.0},
            'database': {'size_mb': 1.0}
        }
        
        # Call the method
        result = self.monitor.save_usage_report(usage_data, 'test_report.json')
        
        # Verify the result
        self.assertEqual(result, 'test_report.json')
        
        # Verify the mocks were called correctly
        mock_makedirs.assert_called_once_with('data/supabase_usage', exist_ok=True)
        mock_open.assert_called_once_with('test_report.json', 'w')
        mock_exists.assert_called_once_with('data/supabase_usage/latest.json')
        mock_remove.assert_called_once_with('data/supabase_usage/latest.json')
        mock_symlink.assert_called_once_with('/absolute/path/to/report.json', 'data/supabase_usage/latest.json')

    def test_extract_project_ref(self):
        """Test extracting project reference from Supabase URL."""
        # Test with a valid URL
        self.monitor.supabase_url = 'https://test-project.supabase.co'
        self.assertEqual(self.monitor.project_ref, 'test-project')
        
        # Test with an empty URL
        self.monitor.supabase_url = ''
        self.assertEqual(self.monitor._extract_project_ref(), '')
        
        # Test with an invalid URL
        self.monitor.supabase_url = 'invalid-url'
        self.assertEqual(self.monitor._extract_project_ref(), '')


if __name__ == '__main__':
    unittest.main()
