"""
Unit tests for the Logs API endpoints and functionality.

Tests API endpoints, data formatting, filtering, export functionality, and error handling.
"""

import io
import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import Flask

from leadfactory.api.logs_api import (
    LogEntry,
    LogsAPI,
    LogSearchFilters,
    create_logs_app,
)


class TestLogEntry:
    """Test LogEntry data structure."""

    def test_log_entry_creation(self):
        """Test LogEntry creation with all fields."""
        timestamp = datetime.utcnow()
        metadata = {"operation": "test", "tokens": 100}

        entry = LogEntry(
            id=1,
            business_id=123,
            log_type="llm",
            content="test content",
            timestamp=timestamp,
            metadata=metadata,
            file_path="/path/to/file",
            file_size=1024,
        )

        assert entry.id == 1
        assert entry.business_id == 123
        assert entry.log_type == "llm"
        assert entry.content == "test content"
        assert entry.timestamp == timestamp
        assert entry.metadata == metadata
        assert entry.file_path == "/path/to/file"
        assert entry.file_size == 1024


class TestLogSearchFilters:
    """Test LogSearchFilters data structure."""

    def test_filters_creation_defaults(self):
        """Test filters creation with default values."""
        filters = LogSearchFilters()

        assert filters.business_id is None
        assert filters.log_type is None
        assert filters.start_date is None
        assert filters.end_date is None
        assert filters.search_query is None
        assert filters.limit == 50
        assert filters.offset == 0
        assert filters.sort_by == "timestamp"
        assert filters.sort_order == "desc"

    def test_filters_creation_custom(self):
        """Test filters creation with custom values."""
        start_date = datetime.utcnow()

        filters = LogSearchFilters(
            business_id=123,
            log_type="llm",
            start_date=start_date,
            search_query="test search",
            limit=100,
            offset=50,
            sort_by="business_id",
            sort_order="asc",
        )

        assert filters.business_id == 123
        assert filters.log_type == "llm"
        assert filters.start_date == start_date
        assert filters.search_query == "test search"
        assert filters.limit == 100
        assert filters.offset == 50
        assert filters.sort_by == "business_id"
        assert filters.sort_order == "asc"


class TestLogsAPI:
    """Test LogsAPI functionality."""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for testing."""
        storage = Mock()
        storage.get_logs_with_filters.return_value = ([], 0)
        storage.get_log_by_id.return_value = None
        storage.get_log_statistics.return_value = {
            "total_logs": 0,
            "logs_by_type": {},
            "logs_by_business": {},
            "date_range": {},
            "storage_usage": {},
        }
        storage.get_available_log_types.return_value = ["llm", "raw_html"]
        storage.get_businesses_with_logs.return_value = []
        return storage

    @pytest.fixture
    def mock_cache(self):
        """Mock cache for testing."""
        cache = Mock()
        cache.get_logs_with_filters.return_value = None
        cache.get_log_statistics.return_value = None
        cache.get_businesses_with_logs.return_value = None
        cache.get_stats.return_value = {
            "size": 0,
            "hit_rate": 0.0,
            "total_hits": 0,
            "total_misses": 0,
        }
        return cache

    @pytest.fixture
    def logs_api(self, mock_storage, mock_cache):
        """Create LogsAPI instance with mocked dependencies."""
        api = LogsAPI()
        api.storage = mock_storage
        api.cache = mock_cache
        return api

    @pytest.fixture
    def flask_app(self, logs_api):
        """Create Flask app for testing."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        logs_api.init_app(app)
        return app

    def test_api_initialization(self, mock_storage, mock_cache):
        """Test API initialization."""
        api = LogsAPI()
        assert api.storage is not None
        assert api.cache is not None

    def test_parse_query_filters(self, logs_api):
        """Test query parameter parsing."""
        # Mock request args
        args = Mock()
        args.get.side_effect = lambda key, default=None, type=None: {
            "business_id": 123,
            "log_type": "llm",
            "start_date": "2023-01-01T00:00:00Z",
            "search": "test query",
            "limit": 100,
            "offset": 50,
            "sort_by": "business_id",
            "sort_order": "asc",
        }.get(key, default)

        filters = logs_api._parse_query_filters(args)

        assert filters.business_id == 123
        assert filters.log_type == "llm"
        assert filters.search_query == "test query"
        assert filters.limit == 100
        assert filters.offset == 50
        assert filters.sort_by == "business_id"
        assert filters.sort_order == "asc"

    def test_validate_filters_valid(self, logs_api):
        """Test filter validation with valid parameters."""
        filters = LogSearchFilters(
            limit=50, offset=0, sort_by="timestamp", sort_order="desc", log_type="llm"
        )

        error = logs_api._validate_filters(filters)
        assert error is None

    def test_validate_filters_invalid_limit(self, logs_api):
        """Test filter validation with invalid limit."""
        filters = LogSearchFilters(limit=2000)  # Over limit
        error = logs_api._validate_filters(filters)
        assert error == "Limit must be between 1 and 1000"

    def test_validate_filters_invalid_sort_by(self, logs_api):
        """Test filter validation with invalid sort field."""
        filters = LogSearchFilters(sort_by="invalid_field")
        error = logs_api._validate_filters(filters)
        assert error == "Invalid sort_by field"

    def test_validate_filters_invalid_log_type(self, logs_api):
        """Test filter validation with invalid log type."""
        filters = LogSearchFilters(log_type="invalid_type")
        error = logs_api._validate_filters(filters)
        assert error == "Invalid log_type"

    def test_parse_datetime_valid(self, logs_api):
        """Test datetime parsing with valid ISO format."""
        dt_str = "2023-01-01T00:00:00Z"
        result = logs_api._parse_datetime(dt_str)

        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_datetime_invalid(self, logs_api):
        """Test datetime parsing with invalid format."""
        dt_str = "invalid-date"
        result = logs_api._parse_datetime(dt_str)

        assert result is None

    def test_parse_datetime_none(self, logs_api):
        """Test datetime parsing with None input."""
        result = logs_api._parse_datetime(None)
        assert result is None

    def test_fetch_logs_cache_hit(self, logs_api, mock_cache):
        """Test log fetching with cache hit."""
        # Setup cache to return data
        cached_logs = [{"id": 1, "content": "cached log"}]
        mock_cache.get_logs_with_filters.return_value = (cached_logs, 1)

        filters = LogSearchFilters()
        logs, total = logs_api._fetch_logs(filters)

        assert len(logs) == 1
        assert total == 1
        assert logs[0].content == "cached log"

        # Verify cache was called but storage was not
        mock_cache.get_logs_with_filters.assert_called_once()
        logs_api.storage.get_logs_with_filters.assert_not_called()

    def test_fetch_logs_cache_miss(self, logs_api, mock_cache, mock_storage):
        """Test log fetching with cache miss."""
        # Setup cache miss and storage return
        mock_cache.get_logs_with_filters.return_value = None
        storage_logs = [
            {
                "id": 1,
                "content": "storage log",
                "business_id": 123,
                "log_type": "llm",
                "timestamp": datetime.utcnow(),
                "metadata": {},
            }
        ]
        mock_storage.get_logs_with_filters.return_value = (storage_logs, 1)

        filters = LogSearchFilters()
        logs, total = logs_api._fetch_logs(filters)

        assert len(logs) == 1
        assert total == 1
        assert logs[0].content == "storage log"

        # Verify both cache and storage were called
        mock_cache.get_logs_with_filters.assert_called_once()
        mock_storage.get_logs_with_filters.assert_called_once()
        mock_cache.set_logs_with_filters.assert_called_once()

    def test_fetch_log_by_id(self, logs_api, mock_storage):
        """Test fetching single log by ID."""
        # Setup storage to return log data
        log_data = {
            "id": 1,
            "business_id": 123,
            "log_type": "llm",
            "content": "test log content",
            "timestamp": datetime.utcnow(),
            "metadata": {"operation": "test"},
        }
        mock_storage.get_log_by_id.return_value = log_data

        result = logs_api._fetch_log_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.business_id == 123
        assert result.content == "test log content"

    def test_fetch_log_by_id_not_found(self, logs_api, mock_storage):
        """Test fetching non-existent log by ID."""
        mock_storage.get_log_by_id.return_value = None

        result = logs_api._fetch_log_by_id(999)
        assert result is None

    def test_format_log_entry(self, logs_api):
        """Test log entry formatting for API response."""
        timestamp = datetime.utcnow()
        log = LogEntry(
            id=1,
            business_id=123,
            log_type="llm",
            content="This is a long content that should be truncated for preview",
            timestamp=timestamp,
            metadata={"operation": "test"},
            file_path="/path/to/file",
            file_size=1024,
        )

        # Test normal formatting (with preview)
        formatted = logs_api._format_log_entry(log)

        assert formatted["id"] == 1
        assert formatted["business_id"] == 123
        assert formatted["log_type"] == "llm"
        assert len(formatted["content_preview"]) <= 203  # 200 + '...'
        assert formatted["content_length"] == len(log.content)
        assert "content" not in formatted  # Full content not included

        # Test with full content
        formatted_full = logs_api._format_log_entry(log, include_full_content=True)
        assert "content" in formatted_full
        assert formatted_full["content"] == log.content

    def test_calculate_log_stats_cache_hit(self, logs_api, mock_cache):
        """Test statistics calculation with cache hit."""
        cached_stats = {"total_logs": 100, "logs_by_type": {"llm": 60, "html": 40}}
        mock_cache.get_log_statistics.return_value = cached_stats

        result = logs_api._calculate_log_stats()

        assert result == cached_stats
        mock_cache.get_log_statistics.assert_called_once()
        logs_api.storage.get_log_statistics.assert_not_called()

    def test_calculate_log_stats_cache_miss(self, logs_api, mock_cache, mock_storage):
        """Test statistics calculation with cache miss."""
        mock_cache.get_log_statistics.return_value = None
        storage_stats = {"total_logs": 200, "logs_by_type": {"llm": 120, "html": 80}}
        mock_storage.get_log_statistics.return_value = storage_stats

        result = logs_api._calculate_log_stats()

        assert result == storage_stats
        mock_cache.get_log_statistics.assert_called_once()
        mock_storage.get_log_statistics.assert_called_once()
        mock_cache.set_log_statistics.assert_called_once_with(storage_stats)

    def test_export_csv(self, logs_api):
        """Test CSV export functionality."""
        timestamp = datetime.utcnow()
        logs = [
            LogEntry(1, 123, "llm", "Content 1", timestamp, {}, "/path1", 1024),
            LogEntry(2, 124, "html", "Content 2", timestamp, {}, "/path2", 2048),
        ]

        response = logs_api._export_csv(logs, include_content=False)

        assert response.mimetype == "text/csv"
        assert "attachment" in response.headers["Content-Disposition"]
        assert "logs_export_" in response.headers["Content-Disposition"]

        # Check CSV content
        csv_content = response.get_data(as_text=True)
        lines = csv_content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "id,business_id,log_type" in lines[0]

    def test_export_json(self, logs_api):
        """Test JSON export functionality."""
        timestamp = datetime.utcnow()
        logs = [LogEntry(1, 123, "llm", "Content 1", timestamp, {}, "/path1", 1024)]

        response = logs_api._export_json(logs, include_content=True)

        assert response.mimetype == "application/json"
        assert "attachment" in response.headers["Content-Disposition"]

        # Check JSON content
        json_content = response.get_data(as_text=True)
        data = json.loads(json_content)

        assert "export_timestamp" in data
        assert "total_logs" in data
        assert "logs" in data
        assert len(data["logs"]) == 1

    def test_get_available_log_types(self, logs_api, mock_storage):
        """Test getting available log types."""
        mock_storage.get_available_log_types.return_value = [
            "llm",
            "raw_html",
            "enrichment",
        ]

        result = logs_api._get_available_log_types()
        assert result == ["llm", "raw_html", "enrichment"]

    def test_get_businesses_with_logs(self, logs_api, mock_storage):
        """Test getting businesses with logs."""
        businesses = [{"id": 1, "name": "Business 1"}, {"id": 2, "name": "Business 2"}]
        mock_storage.get_businesses_with_logs.return_value = businesses

        result = logs_api._get_businesses_with_logs()
        assert result == businesses


class TestLogsAPIEndpoints:
    """Test API endpoints with Flask test client."""

    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app = create_logs_app()
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_health_endpoint(self, mock_cache, mock_storage, client):
        """Test health check endpoint."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_logs_endpoint(self, mock_cache, mock_storage, client):
        """Test GET /api/logs endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_logs_with_filters.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_logs_with_filters.return_value = ([], 0)
        mock_storage.return_value = mock_storage_instance

        response = client.get("/api/logs?limit=10&offset=0")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "logs" in data
        assert "pagination" in data
        assert "filters" in data

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_logs_with_filters(self, mock_cache, mock_storage, client):
        """Test GET /api/logs with filter parameters."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_logs_with_filters.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_logs_with_filters.return_value = ([], 0)
        mock_storage.return_value = mock_storage_instance

        response = client.get("/api/logs?business_id=123&log_type=llm&limit=50")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["filters"]["business_id"] == 123
        assert data["filters"]["log_type"] == "llm"

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_log_detail_endpoint(self, mock_cache, mock_storage, client):
        """Test GET /api/logs/{id} endpoint."""
        # Setup mocks
        mock_cache.return_value = Mock()

        mock_storage_instance = Mock()
        mock_storage_instance.get_log_by_id.return_value = {
            "id": 1,
            "business_id": 123,
            "log_type": "llm",
            "content": "test content",
            "timestamp": datetime.utcnow(),
            "metadata": {},
        }
        mock_storage.return_value = mock_storage_instance

        response = client.get("/api/logs/1")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == 1
        assert data["business_id"] == 123

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_log_detail_not_found(self, mock_cache, mock_storage, client):
        """Test GET /api/logs/{id} with non-existent log."""
        # Setup mocks
        mock_cache.return_value = Mock()

        mock_storage_instance = Mock()
        mock_storage_instance.get_log_by_id.return_value = None
        mock_storage.return_value = mock_storage_instance

        response = client.get("/api/logs/999")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "Log not found"

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_search_logs_endpoint(self, mock_cache, mock_storage, client):
        """Test POST /api/logs/search endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_logs_with_filters.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_logs_with_filters.return_value = ([], 0)
        mock_storage.return_value = mock_storage_instance

        search_data = {
            "query": "test search",
            "filters": {"business_id": 123, "log_type": "llm"},
            "pagination": {"limit": 20, "offset": 0},
        }

        response = client.post(
            "/api/logs/search",
            data=json.dumps(search_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "logs" in data
        assert "search" in data
        assert data["search"]["query"] == "test search"

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_export_logs_endpoint(self, mock_cache, mock_storage, client):
        """Test POST /api/logs/export endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_logs_with_filters.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_logs_with_filters.return_value = ([], 0)
        mock_storage.return_value = mock_storage_instance

        export_data = {
            "format": "csv",
            "include_content": False,
            "filters": {"log_type": "llm"},
        }

        response = client.post(
            "/api/logs/export",
            data=json.dumps(export_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.mimetype == "text/csv"

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_stats_endpoint(self, mock_cache, mock_storage, client):
        """Test GET /api/logs/stats endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_log_statistics.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_storage_instance = Mock()
        mock_storage_instance.get_log_statistics.return_value = {
            "total_logs": 100,
            "logs_by_type": {"llm": 60, "html": 40},
        }
        mock_storage.return_value = mock_storage_instance

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total_logs"] == 100
        assert data["logs_by_type"]["llm"] == 60

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_get_cache_stats_endpoint(self, mock_cache, mock_storage, client):
        """Test GET /api/cache/stats endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_stats.return_value = {
            "size": 10,
            "hit_rate": 75.5,
            "total_hits": 100,
            "total_misses": 25,
        }
        mock_cache.return_value = mock_cache_instance

        response = client.get("/api/cache/stats")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "cache_stats" in data
        assert data["cache_stats"]["hit_rate"] == 75.5

    @patch("leadfactory.api.logs_api.get_storage")
    @patch("leadfactory.api.logs_api.get_cache")
    def test_clear_cache_endpoint(self, mock_cache, mock_storage, client):
        """Test POST /api/cache/clear endpoint."""
        # Setup mocks
        mock_cache_instance = Mock()
        mock_cache_instance.get_stats.return_value = {"size": 10}
        mock_cache.return_value = mock_cache_instance

        response = client.post("/api/cache/clear")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["message"] == "Cache cleared successfully"
        assert "stats_before_clear" in data
        mock_cache_instance.clear.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
