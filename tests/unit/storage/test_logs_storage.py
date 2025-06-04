"""
Unit tests for the storage layer log management functionality.

Tests the PostgreSQL storage implementation for log retrieval, filtering, and statistics.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.storage.postgres_storage import PostgresStorage


class TestPostgresStorageLogMethods:
    """Test PostgreSQL storage log management methods."""

    @pytest.fixture
    def mock_cursor(self):
        """Mock database cursor."""
        cursor = Mock()
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None
        cursor.description = []
        return cursor

    @pytest.fixture
    def postgres_storage(self, mock_cursor):
        """Create PostgreSQL storage instance with mocked cursor."""
        storage = PostgresStorage()
        storage.cursor = Mock()
        storage.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        storage.cursor.return_value.__exit__ = Mock(return_value=None)
        return storage

    def test_get_logs_with_filters_basic(self, postgres_storage, mock_cursor):
        """Test basic log retrieval without filters."""
        # Setup mock data
        mock_cursor.fetchall.side_effect = [
            # Count query result
            [(5,)],
            # Data query result
            [
                (1, 123, 'llm', 'test content', datetime.utcnow(), '{}', None, 100),
                (2, 124, 'raw_html', 'html content', datetime.utcnow(), '{}', '/path', 200)
            ]
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters()

        assert total_count == 5
        assert len(logs) == 2
        assert logs[0]['id'] == 1
        assert logs[0]['log_type'] == 'llm'
        assert logs[1]['id'] == 2
        assert logs[1]['log_type'] == 'raw_html'

    def test_get_logs_with_filters_business_id(self, postgres_storage, mock_cursor):
        """Test log retrieval filtered by business ID."""
        mock_cursor.fetchall.side_effect = [
            [(3,)],  # Count
            [(1, 123, 'llm', 'content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(business_id=123)

        assert total_count == 3
        assert len(logs) == 1
        assert logs[0]['business_id'] == 123

        # Verify query was called with business_id filter
        calls = mock_cursor.execute.call_args_list
        assert any('business_id = %s' in str(call) for call in calls)

    def test_get_logs_with_filters_log_type(self, postgres_storage, mock_cursor):
        """Test log retrieval filtered by log type."""
        mock_cursor.fetchall.side_effect = [
            [(2,)],  # Count
            [(1, 123, 'llm', 'content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(log_type='llm')

        assert total_count == 2
        assert len(logs) == 1
        assert logs[0]['log_type'] == 'llm'

    def test_get_logs_with_filters_date_range(self, postgres_storage, mock_cursor):
        """Test log retrieval filtered by date range."""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        mock_cursor.fetchall.side_effect = [
            [(1,)],  # Count
            [(1, 123, 'llm', 'content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(
            start_date=start_date,
            end_date=end_date
        )

        assert total_count == 1
        assert len(logs) == 1

        # Verify date filters in query
        calls = mock_cursor.execute.call_args_list
        assert any('timestamp >=' in str(call) for call in calls)
        assert any('timestamp <=' in str(call) for call in calls)

    def test_get_logs_with_filters_search_query(self, postgres_storage, mock_cursor):
        """Test log retrieval with search query."""
        mock_cursor.fetchall.side_effect = [
            [(1,)],  # Count
            [(1, 123, 'llm', 'matching content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(
            search_query='matching'
        )

        assert total_count == 1
        assert len(logs) == 1
        assert 'matching' in logs[0]['content']

        # Verify search query in SQL
        calls = mock_cursor.execute.call_args_list
        assert any('ILIKE' in str(call) for call in calls)

    def test_get_logs_with_filters_pagination(self, postgres_storage, mock_cursor):
        """Test log retrieval with pagination."""
        mock_cursor.fetchall.side_effect = [
            [(100,)],  # Total count
            [(11, 123, 'llm', 'content', datetime.utcnow(), '{}', None, 100)]  # Page 2 data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(
            limit=10,
            offset=10
        )

        assert total_count == 100
        assert len(logs) == 1

        # Verify LIMIT and OFFSET in query
        calls = mock_cursor.execute.call_args_list
        assert any('LIMIT' in str(call) and 'OFFSET' in str(call) for call in calls)

    def test_get_logs_with_filters_sorting(self, postgres_storage, mock_cursor):
        """Test log retrieval with custom sorting."""
        mock_cursor.fetchall.side_effect = [
            [(2,)],  # Count
            [(1, 123, 'llm', 'content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(
            sort_by='business_id',
            sort_order='asc'
        )

        assert total_count == 2
        assert len(logs) == 1

        # Verify ORDER BY in query
        calls = mock_cursor.execute.call_args_list
        assert any('ORDER BY business_id ASC' in str(call) for call in calls)

    def test_get_log_by_id_llm_logs(self, postgres_storage, mock_cursor):
        """Test retrieving single LLM log by ID."""
        # First query (LLM logs) returns data
        mock_cursor.fetchone.side_effect = [
            (1, 123, 'llm', 'combined content', datetime.utcnow(), '{}', None, 100),
            None  # Second query (HTML logs) returns nothing
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        log = postgres_storage.get_log_by_id(1)

        assert log is not None
        assert log['id'] == 1
        assert log['business_id'] == 123
        assert log['log_type'] == 'llm'

    def test_get_log_by_id_html_logs(self, postgres_storage, mock_cursor):
        """Test retrieving single HTML log by ID."""
        # First query (LLM logs) returns nothing, second query (HTML logs) returns data
        mock_cursor.fetchone.side_effect = [
            None,  # LLM logs query
            (1, 123, 'raw_html', 'URL content', datetime.utcnow(), '{}', '/path', 200)  # HTML logs query
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        log = postgres_storage.get_log_by_id(1)

        assert log is not None
        assert log['id'] == 1
        assert log['log_type'] == 'raw_html'

    def test_get_log_by_id_not_found(self, postgres_storage, mock_cursor):
        """Test retrieving non-existent log by ID."""
        mock_cursor.fetchone.return_value = None

        log = postgres_storage.get_log_by_id(999)

        assert log is None

    def test_get_log_statistics(self, postgres_storage, mock_cursor):
        """Test log statistics calculation."""
        # Mock multiple query results
        mock_cursor.fetchone.side_effect = [
            (150,),  # LLM logs count
            (100,),  # HTML logs count
            (datetime(2023, 1, 1), datetime(2023, 12, 31)),  # LLM date range
            (datetime(2023, 2, 1), datetime(2023, 11, 30)),  # HTML date range
        ]

        # Mock business stats query
        mock_cursor.fetchall.return_value = [
            (123, 50),  # business_id, log_count
            (124, 30),
            (125, 20)
        ]

        stats = postgres_storage.get_log_statistics()

        assert stats['total_logs'] == 250  # 150 + 100
        assert stats['logs_by_type']['llm'] == 150
        assert stats['logs_by_type']['raw_html'] == 100
        assert stats['date_range']['earliest'] == '2023-01-01T00:00:00'
        assert stats['date_range']['latest'] == '2023-12-31T00:00:00'
        assert '123' in stats['logs_by_business']
        assert stats['logs_by_business']['123'] == 50

    def test_get_available_log_types(self, postgres_storage):
        """Test getting available log types."""
        log_types = postgres_storage.get_available_log_types()

        assert 'llm' in log_types
        assert 'raw_html' in log_types
        assert len(log_types) >= 2

    def test_get_businesses_with_logs(self, postgres_storage, mock_cursor):
        """Test getting businesses that have logs."""
        mock_cursor.fetchall.return_value = [
            (1, 'Business One'),
            (2, 'Business Two'),
            (3, 'Business Three')
        ]

        businesses = postgres_storage.get_businesses_with_logs()

        assert len(businesses) == 3
        assert businesses[0]['id'] == 1
        assert businesses[0]['name'] == 'Business One'
        assert businesses[1]['id'] == 2
        assert businesses[1]['name'] == 'Business Two'

    def test_get_all_businesses(self, postgres_storage, mock_cursor):
        """Test getting all businesses."""
        mock_cursor.fetchall.return_value = [
            (1, 'Business One', 'https://business1.com'),
            (2, 'Business Two', 'https://business2.com')
        ]

        businesses = postgres_storage.get_all_businesses()

        assert len(businesses) == 2
        assert businesses[0]['id'] == 1
        assert businesses[0]['name'] == 'Business One'
        assert businesses[0]['website'] == 'https://business1.com'

    def test_metadata_json_parsing(self, postgres_storage, mock_cursor):
        """Test JSON metadata parsing in log entries."""
        # Mock data with JSON metadata
        metadata_json = '{"operation": "test", "tokens": 100}'
        mock_cursor.fetchall.side_effect = [
            [(1,)],  # Count
            [(1, 123, 'llm', 'content', datetime.utcnow(), metadata_json, None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters()

        assert len(logs) == 1
        # Note: The actual JSON parsing happens in the API layer,
        # storage layer returns raw JSON strings

    def test_error_handling(self, postgres_storage):
        """Test error handling in storage methods."""
        # Mock cursor to raise exception
        postgres_storage.cursor.return_value.__enter__.side_effect = Exception("Database error")

        # Should return empty results and log error, not raise exception
        logs, total_count = postgres_storage.get_logs_with_filters()
        assert logs == []
        assert total_count == 0

        log = postgres_storage.get_log_by_id(1)
        assert log is None

        stats = postgres_storage.get_log_statistics()
        assert stats == {
            'total_logs': 0,
            'logs_by_type': {},
            'logs_by_business': {},
            'date_range': {},
            'storage_usage': {}
        }

        businesses = postgres_storage.get_businesses_with_logs()
        assert businesses == []

    def test_complex_filtering_combination(self, postgres_storage, mock_cursor):
        """Test complex combination of multiple filters."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)

        mock_cursor.fetchall.side_effect = [
            [(5,)],  # Count
            [(1, 123, 'llm', 'search content', datetime.utcnow(), '{}', None, 100)]  # Data
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters(
            business_id=123,
            log_type='llm',
            start_date=start_date,
            end_date=end_date,
            search_query='search',
            limit=20,
            offset=0,
            sort_by='timestamp',
            sort_order='desc'
        )

        assert total_count == 5
        assert len(logs) == 1

        # Verify all filters were applied in the query
        calls = mock_cursor.execute.call_args_list
        query_strings = [str(call) for call in calls]

        # Check that complex filtering conditions were applied
        assert any('business_id' in query for query in query_strings)
        assert any('timestamp' in query for query in query_strings)
        assert any('ILIKE' in query for query in query_strings)

    def test_union_query_structure(self, postgres_storage, mock_cursor):
        """Test that union queries are properly structured for multiple log types."""
        mock_cursor.fetchall.side_effect = [
            [(10,)],  # Count
            [
                (1, 123, 'llm', 'llm content', datetime.utcnow(), '{}', None, 100),
                (2, 124, 'raw_html', 'html content', datetime.utcnow(), '{}', '/path', 200)
            ]  # Data with both types
        ]
        mock_cursor.description = [
            ('id',), ('business_id',), ('log_type',), ('content',),
            ('timestamp',), ('metadata',), ('file_path',), ('content_length',)
        ]

        logs, total_count = postgres_storage.get_logs_with_filters()

        assert total_count == 10
        assert len(logs) == 2

        # Verify we get both log types
        log_types = [log['log_type'] for log in logs]
        assert 'llm' in log_types
        assert 'raw_html' in log_types

        # Verify UNION ALL is used in queries
        calls = mock_cursor.execute.call_args_list
        assert any('UNION ALL' in str(call) for call in calls)


if __name__ == '__main__':
    pytest.main([__file__])
