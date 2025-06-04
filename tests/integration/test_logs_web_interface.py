"""
Integration tests for the Logs Web Interface.

Tests the complete logs web interface functionality including API endpoints,
database integration, caching, and export capabilities.
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from leadfactory.api.cache import LogsAPICache, clear_cache, get_cache
from leadfactory.api.logs_api import create_logs_app
from leadfactory.storage.postgres_storage import PostgresStorage


class TestLogsWebInterfaceIntegration:
    """Integration tests for logs web interface."""

    @pytest.fixture(scope="class")
    def test_db(self):
        """Create a temporary SQLite database for testing."""
        db_fd, db_path = tempfile.mkstemp()

        # Create test database schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create test tables
        cursor.execute("""
            CREATE TABLE businesses (
                id INTEGER PRIMARY KEY,
                name TEXT,
                website TEXT,
                email TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE llm_logs (
                id INTEGER PRIMARY KEY,
                business_id INTEGER,
                operation TEXT,
                model_version TEXT,
                prompt_text TEXT,
                response_json TEXT,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                duration_ms INTEGER,
                status TEXT,
                created_at TIMESTAMP,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE raw_html_storage (
                id INTEGER PRIMARY KEY,
                business_id INTEGER,
                html_path TEXT,
                original_url TEXT,
                compression_ratio REAL,
                content_hash TEXT,
                size_bytes INTEGER,
                created_at TIMESTAMP
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO businesses (id, name, website, email)
            VALUES
                (1, 'Test Business 1', 'https://test1.com', 'test1@example.com'),
                (2, 'Test Business 2', 'https://test2.com', 'test2@example.com'),
                (3, 'Test Business 3', 'https://test3.com', 'test3@example.com')
        """)

        # Insert LLM logs
        now = datetime.utcnow()
        for i in range(10):
            cursor.execute(
                """
                INSERT INTO llm_logs (
                    business_id, operation, model_version, prompt_text, response_json,
                    tokens_prompt, tokens_completion, duration_ms, status, created_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    (i % 3) + 1,  # business_id (1, 2, 3)
                    f"operation_{i}",
                    "gpt-4",
                    f"Test prompt {i}",
                    f'{{"response": "Test response {i}"}}',
                    100 + i,
                    200 + i,
                    1000 + i * 100,
                    "success",
                    now - timedelta(hours=i),
                    f'{{"test": "metadata_{i}"}}',
                ),
            )

        # Insert HTML logs
        for i in range(15):
            cursor.execute(
                """
                INSERT INTO raw_html_storage (
                    business_id, html_path, original_url, compression_ratio,
                    content_hash, size_bytes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    (i % 3) + 1,  # business_id (1, 2, 3)
                    f"/path/to/html_{i}.html",
                    f"https://test{(i % 3) + 1}.com/page_{i}",
                    0.8,
                    f"hash_{i}",
                    5000 + i * 100,
                    now - timedelta(hours=i),
                ),
            )

        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        os.close(db_fd)
        os.unlink(db_path)

    @pytest.fixture
    def mock_storage(self, test_db):
        """Create a mock storage that uses the test database."""
        storage = Mock(spec=PostgresStorage)

        def get_logs_with_filters(**kwargs):
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()

            # Build query based on filters
            where_conditions = []
            params = []

            business_id = kwargs.get("business_id")
            log_type = kwargs.get("log_type")
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            search_query = kwargs.get("search_query")
            limit = kwargs.get("limit", 50)
            offset = kwargs.get("offset", 0)
            sort_by = kwargs.get("sort_by", "timestamp")
            sort_order = kwargs.get("sort_order", "desc")

            # Build unified query
            if log_type == "llm":
                query = """
                    SELECT id, business_id, 'llm' as log_type, prompt_text as content,
                           created_at as timestamp, metadata, NULL as file_path,
                           LENGTH(prompt_text) as content_length
                    FROM llm_logs
                """
            elif log_type == "raw_html":
                query = """
                    SELECT id, business_id, 'raw_html' as log_type, original_url as content,
                           created_at as timestamp, '{}' as metadata, html_path as file_path,
                           size_bytes as content_length
                    FROM raw_html_storage
                """
            else:
                # Union query for all types
                query = """
                    SELECT id, business_id, 'llm' as log_type, prompt_text as content,
                           created_at as timestamp, metadata, NULL as file_path,
                           LENGTH(prompt_text) as content_length
                    FROM llm_logs
                    UNION ALL
                    SELECT id, business_id, 'raw_html' as log_type, original_url as content,
                           created_at as timestamp, '{}' as metadata, html_path as file_path,
                           size_bytes as content_length
                    FROM raw_html_storage
                """

            # Add filters
            if business_id:
                where_conditions.append("business_id = ?")
                params.append(business_id)

            if start_date:
                where_conditions.append("created_at >= ?")
                params.append(start_date.isoformat())

            if end_date:
                where_conditions.append("created_at <= ?")
                params.append(end_date.isoformat())

            if search_query:
                where_conditions.append("content LIKE ?")
                params.append(f"%{search_query}%")

            if where_conditions:
                if "UNION ALL" in query:
                    # Wrap union query and add WHERE
                    query = f"SELECT * FROM ({query}) as combined WHERE {' AND '.join(where_conditions)}"
                else:
                    query += f" WHERE {' AND '.join(where_conditions)}"

            # Count query
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Data query with pagination
            if sort_by == "timestamp":
                sort_by = "created_at"
            data_query = (
                f"{query} ORDER BY {sort_by} {sort_order.upper()} LIMIT ? OFFSET ?"
            )
            cursor.execute(data_query, params + [limit, offset])

            rows = cursor.fetchall()
            columns = [
                "id",
                "business_id",
                "log_type",
                "content",
                "timestamp",
                "metadata",
                "file_path",
                "content_length",
            ]
            logs = [dict(zip(columns, row)) for row in rows]

            conn.close()
            return logs, total_count

        def get_log_by_id(log_id):
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()

            # Try LLM logs first
            cursor.execute(
                """
                SELECT id, business_id, 'llm' as log_type,
                       prompt_text || ' -> ' || response_json as content,
                       created_at as timestamp, metadata, NULL as file_path,
                       LENGTH(prompt_text) as content_length
                FROM llm_logs WHERE id = ?
            """,
                (log_id,),
            )

            row = cursor.fetchone()
            if row:
                columns = [
                    "id",
                    "business_id",
                    "log_type",
                    "content",
                    "timestamp",
                    "metadata",
                    "file_path",
                    "content_length",
                ]
                result = dict(zip(columns, row))
                conn.close()
                return result

            # Try HTML logs
            cursor.execute(
                """
                SELECT id, business_id, 'raw_html' as log_type,
                       'URL: ' || original_url || ', Path: ' || html_path as content,
                       created_at as timestamp, '{}' as metadata, html_path as file_path,
                       size_bytes as content_length
                FROM raw_html_storage WHERE id = ?
            """,
                (log_id,),
            )

            row = cursor.fetchone()
            if row:
                columns = [
                    "id",
                    "business_id",
                    "log_type",
                    "content",
                    "timestamp",
                    "metadata",
                    "file_path",
                    "content_length",
                ]
                result = dict(zip(columns, row))
                conn.close()
                return result

            conn.close()
            return None

        def get_log_statistics():
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM llm_logs")
            llm_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_html_storage")
            html_count = cursor.fetchone()[0]

            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM llm_logs")
            llm_dates = cursor.fetchone()

            cursor.execute(
                "SELECT MIN(created_at), MAX(created_at) FROM raw_html_storage"
            )
            html_dates = cursor.fetchone()

            # Business stats
            cursor.execute("""
                SELECT business_id, COUNT(*) as log_count FROM (
                    SELECT business_id FROM llm_logs
                    UNION ALL
                    SELECT business_id FROM raw_html_storage
                ) GROUP BY business_id ORDER BY log_count DESC
            """)
            business_stats = cursor.fetchall()

            conn.close()

            return {
                "total_logs": llm_count + html_count,
                "logs_by_type": {"llm": llm_count, "raw_html": html_count},
                "logs_by_business": {str(row[0]): row[1] for row in business_stats},
                "date_range": {
                    "earliest": min(d[0] for d in [llm_dates, html_dates] if d[0])
                    if any(d[0] for d in [llm_dates, html_dates])
                    else None,
                    "latest": max(d[1] for d in [llm_dates, html_dates] if d[1])
                    if any(d[1] for d in [llm_dates, html_dates])
                    else None,
                },
                "storage_usage": {},
            }

        def get_available_log_types():
            return ["llm", "raw_html"]

        def get_businesses_with_logs():
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT id, name FROM businesses ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            return [{"id": row[0], "name": row[1]} for row in rows]

        def get_all_businesses():
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, website FROM businesses ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
            return [{"id": row[0], "name": row[1], "website": row[2]} for row in rows]

        storage.get_logs_with_filters = get_logs_with_filters
        storage.get_log_by_id = get_log_by_id
        storage.get_log_statistics = get_log_statistics
        storage.get_available_log_types = get_available_log_types
        storage.get_businesses_with_logs = get_businesses_with_logs
        storage.get_all_businesses = get_all_businesses

        return storage

    @pytest.fixture
    def app(self, mock_storage):
        """Create Flask app with mocked storage."""
        with patch("leadfactory.api.logs_api.get_storage", return_value=mock_storage):
            app = create_logs_app()
            app.config["TESTING"] = True
            yield app

        # Clear cache after each test
        clear_cache()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_health_endpoint_integration(self, client):
        """Test health endpoint integration."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_get_logs_basic_integration(self, client):
        """Test basic log retrieval integration."""
        response = client.get("/api/logs?limit=5")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert "logs" in data
        assert "pagination" in data
        assert "filters" in data

        assert len(data["logs"]) <= 5
        assert data["pagination"]["limit"] == 5
        assert data["pagination"]["total"] == 25  # 10 LLM + 15 HTML logs

    def test_filter_by_business_id_integration(self, client):
        """Test filtering by business ID integration."""
        response = client.get("/api/logs?business_id=1&limit=20")

        assert response.status_code == 200
        data = json.loads(response.data)

        # All logs should be for business_id 1
        for log in data["logs"]:
            assert log["business_id"] == 1

        # Should have logs from both tables for business 1
        log_types = [log["log_type"] for log in data["logs"]]
        assert "llm" in log_types
        assert "raw_html" in log_types

    def test_filter_by_log_type_integration(self, client):
        """Test filtering by log type integration."""
        # Test LLM logs only
        response = client.get("/api/logs?log_type=llm")

        assert response.status_code == 200
        data = json.loads(response.data)

        # All logs should be LLM type
        for log in data["logs"]:
            assert log["log_type"] == "llm"

        assert data["pagination"]["total"] == 10  # Only LLM logs

    def test_search_functionality_integration(self, client):
        """Test search functionality integration."""
        search_data = {
            "query": "Test prompt 5",
            "filters": {},
            "pagination": {"limit": 10, "offset": 0},
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
        assert data["search"]["query"] == "Test prompt 5"

        # Should find the specific log with "Test prompt 5"
        assert len(data["logs"]) >= 1
        assert any("Test prompt 5" in log["content_preview"] for log in data["logs"])

    def test_pagination_integration(self, client):
        """Test pagination integration."""
        # Get first page
        response1 = client.get("/api/logs?limit=10&offset=0")
        assert response1.status_code == 200
        data1 = json.loads(response1.data)

        # Get second page
        response2 = client.get("/api/logs?limit=10&offset=10")
        assert response2.status_code == 200
        data2 = json.loads(response2.data)

        # Should have different logs
        ids1 = [log["id"] for log in data1["logs"]]
        ids2 = [log["id"] for log in data2["logs"]]
        assert set(ids1).isdisjoint(set(ids2))  # No overlap

        # Total should be same
        assert data1["pagination"]["total"] == data2["pagination"]["total"]

    def test_log_detail_integration(self, client):
        """Test log detail retrieval integration."""
        # First get a log ID
        response = client.get("/api/logs?limit=1")
        data = json.loads(response.data)
        log_id = data["logs"][0]["id"]

        # Get detailed log
        detail_response = client.get(f"/api/logs/{log_id}")

        assert detail_response.status_code == 200
        detail_data = json.loads(detail_response.data)

        assert detail_data["id"] == log_id
        assert "content" in detail_data  # Full content included
        assert "metadata" in detail_data

    def test_log_detail_not_found_integration(self, client):
        """Test log detail for non-existent log."""
        response = client.get("/api/logs/99999")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "Log not found"

    def test_statistics_integration(self, client):
        """Test statistics endpoint integration."""
        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["total_logs"] == 25  # 10 LLM + 15 HTML
        assert data["logs_by_type"]["llm"] == 10
        assert data["logs_by_type"]["raw_html"] == 15
        assert "logs_by_business" in data
        assert "date_range" in data

    def test_export_csv_integration(self, client):
        """Test CSV export integration."""
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
        assert "attachment" in response.headers["Content-Disposition"]

        # Check CSV content
        csv_content = response.get_data(as_text=True)
        lines = csv_content.strip().split("\n")
        assert len(lines) == 11  # Header + 10 LLM logs
        assert "id,business_id,log_type" in lines[0]

    def test_export_json_integration(self, client):
        """Test JSON export integration."""
        export_data = {
            "format": "json",
            "include_content": True,
            "filters": {"business_id": 1},
        }

        response = client.post(
            "/api/logs/export",
            data=json.dumps(export_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.mimetype == "application/json"

        # Check JSON content
        json_content = response.get_data(as_text=True)
        data = json.loads(json_content)

        assert "export_timestamp" in data
        assert "total_logs" in data
        assert "logs" in data

        # All logs should be for business 1
        for log in data["logs"]:
            assert log["business_id"] == 1

    def test_businesses_endpoint_integration(self, client):
        """Test businesses endpoint integration."""
        response = client.get("/api/businesses")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert "businesses" in data
        assert len(data["businesses"]) == 3

        business_names = [b["name"] for b in data["businesses"]]
        assert "Test Business 1" in business_names
        assert "Test Business 2" in business_names
        assert "Test Business 3" in business_names

    def test_log_types_endpoint_integration(self, client):
        """Test log types endpoint integration."""
        response = client.get("/api/logs/types")

        assert response.status_code == 200
        data = json.loads(response.data)

        assert "log_types" in data
        assert "llm" in data["log_types"]
        assert "raw_html" in data["log_types"]

    def test_cache_integration(self, client):
        """Test caching integration."""
        # First request should hit storage
        response1 = client.get("/api/logs?limit=5")
        assert response1.status_code == 200

        # Second identical request should hit cache
        response2 = client.get("/api/logs?limit=5")
        assert response2.status_code == 200

        # Data should be identical
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        assert data1["logs"] == data2["logs"]

        # Check cache stats
        cache_response = client.get("/api/cache/stats")
        assert cache_response.status_code == 200
        cache_data = json.loads(cache_response.data)

        assert cache_data["cache_stats"]["total_hits"] > 0

    def test_cache_clear_integration(self, client):
        """Test cache clearing integration."""
        # Make some requests to populate cache
        client.get("/api/logs?limit=5")
        client.get("/api/logs/stats")

        # Check cache has entries
        cache_response = client.get("/api/cache/stats")
        cache_data = json.loads(cache_response.data)
        assert cache_data["cache_stats"]["size"] > 0

        # Clear cache
        clear_response = client.post("/api/cache/clear")
        assert clear_response.status_code == 200
        clear_data = json.loads(clear_response.data)
        assert clear_data["message"] == "Cache cleared successfully"

        # Verify cache is empty
        cache_response2 = client.get("/api/cache/stats")
        cache_data2 = json.loads(cache_response2.data)
        assert cache_data2["cache_stats"]["size"] == 0

    def test_complex_filtering_integration(self, client):
        """Test complex filtering with multiple parameters."""
        # Test multiple filters together
        start_date = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/logs?business_id=2&log_type=raw_html&start_date={start_date}&end_date={end_date}&limit=10"
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        # All results should match all filters
        for log in data["logs"]:
            assert log["business_id"] == 2
            assert log["log_type"] == "raw_html"
            # Timestamp should be within range (roughly)
            log_time = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
            assert log_time >= datetime.fromisoformat(start_date.replace("Z", "+00:00"))

    def test_advanced_search_integration(self, client):
        """Test advanced search with filters."""
        search_data = {
            "query": "test",
            "filters": {
                "business_id": 1,
                "log_type": "llm",
                "start_date": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
                "end_date": datetime.utcnow().isoformat(),
            },
            "pagination": {"limit": 5, "offset": 0},
            "sort": {"by": "timestamp", "order": "desc"},
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

        # Verify search and filter results
        for log in data["logs"]:
            assert log["business_id"] == 1
            assert log["log_type"] == "llm"
            assert "test" in log["content_preview"].lower()

    def test_sorting_integration(self, client):
        """Test sorting functionality integration."""
        # Test ascending sort by business_id
        response = client.get("/api/logs?sort_by=business_id&sort_order=asc&limit=10")

        assert response.status_code == 200
        data = json.loads(response.data)

        # Verify sort order
        business_ids = [log["business_id"] for log in data["logs"]]
        assert business_ids == sorted(business_ids)

    def test_error_handling_integration(self, client):
        """Test error handling integration."""
        # Test invalid parameters
        response = client.get("/api/logs?limit=2000")  # Over limit

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_static_file_serving_integration(self, client):
        """Test static file serving integration."""
        # Test logs interface
        response = client.get("/logs")
        assert response.status_code == 200
        assert b"Logs Browser" in response.data

        # Test dashboard interface
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Analytics Dashboard" in response.data

    def test_end_to_end_workflow_integration(self, client):
        """Test complete end-to-end workflow."""
        # 1. Get initial statistics
        stats_response = client.get("/api/logs/stats")
        stats_data = json.loads(stats_response.data)
        initial_total = stats_data["total_logs"]

        # 2. Browse logs with pagination
        page1_response = client.get("/api/logs?limit=10&offset=0")
        page1_data = json.loads(page1_response.data)
        assert len(page1_data["logs"]) == 10

        # 3. Filter by business
        business_response = client.get("/api/logs?business_id=1")
        business_data = json.loads(business_response.data)
        assert all(log["business_id"] == 1 for log in business_data["logs"])

        # 4. Search for specific content
        search_data = {"query": "prompt", "filters": {}, "pagination": {"limit": 5}}
        search_response = client.post(
            "/api/logs/search",
            data=json.dumps(search_data),
            content_type="application/json",
        )
        search_results = json.loads(search_response.data)
        assert len(search_results["logs"]) > 0

        # 5. View detailed log
        log_id = search_results["logs"][0]["id"]
        detail_response = client.get(f"/api/logs/{log_id}")
        detail_data = json.loads(detail_response.data)
        assert detail_data["id"] == log_id

        # 6. Export filtered data
        export_data = {
            "format": "csv",
            "filters": {"business_id": 1},
            "include_content": False,
        }
        export_response = client.post(
            "/api/logs/export",
            data=json.dumps(export_data),
            content_type="application/json",
        )
        assert export_response.status_code == 200
        assert export_response.mimetype == "text/csv"

        # 7. Check cache performance
        cache_response = client.get("/api/cache/stats")
        cache_data = json.loads(cache_response.data)
        assert cache_data["cache_stats"]["total_hits"] > 0


if __name__ == "__main__":
    pytest.main([__file__])
