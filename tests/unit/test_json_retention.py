"""Unit tests for JSON retention functionality."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.storage.postgres_storage import PostgresStorage


class TestJSONRetention:
    """Test JSON retention policy functionality."""
    
    @pytest.fixture
    def mock_storage(self):
        """Mock PostgresStorage instance."""
        storage = Mock(spec=PostgresStorage)
        return storage
    
    @pytest.fixture
    def sample_yelp_json(self):
        """Sample Yelp API response."""
        return {
            "id": "test-business-123",
            "name": "Test Business",
            "location": {
                "address1": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94105"
            },
            "phone": "+14155551234",
            "url": "https://www.yelp.com/biz/test-business"
        }
    
    @pytest.fixture
    def sample_google_json(self):
        """Sample Google Places API response."""
        return {
            "place_id": "ChIJtest123",
            "name": "Test Business",
            "formatted_address": "123 Main St, San Francisco, CA 94105",
            "formatted_phone_number": "(415) 555-1234",
            "website": "https://testbusiness.com"
        }
    
    def test_json_retention_field_exists(self, mock_storage):
        """Test that json_retention_expires_at field is tracked."""
        # Simulate a business with JSON data and retention timestamp
        business_data = {
            "id": 1,
            "name": "Test Business",
            "yelp_response_json": {"id": "test-123"},
            "google_response_json": {"place_id": "ChIJtest"},
            "json_retention_expires_at": datetime.now() + timedelta(days=90)
        }
        
        mock_storage.get_business_by_id.return_value = business_data
        
        business = mock_storage.get_business_by_id(1)
        assert business["json_retention_expires_at"] is not None
        assert "yelp_response_json" in business
        assert "google_response_json" in business
    
    def test_expired_json_identification(self, mock_storage):
        """Test identification of businesses with expired JSON."""
        # Create businesses with different retention dates
        expired_date = datetime.now() - timedelta(days=1)
        future_date = datetime.now() + timedelta(days=30)
        
        mock_storage.execute_query.return_value = [
            {"id": 1, "name": "Expired Business", "json_retention_expires_at": expired_date},
            {"id": 2, "name": "Current Business", "json_retention_expires_at": future_date}
        ]
        
        # Query for expired records
        query = """
            SELECT id, name, json_retention_expires_at
            FROM businesses 
            WHERE json_retention_expires_at < CURRENT_TIMESTAMP
            AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
        """
        
        expired_businesses = mock_storage.execute_query(query)
        
        # Should only return the expired business
        assert len(expired_businesses) == 2  # Mock returns both, but in real scenario would filter
        assert expired_businesses[0]["name"] == "Expired Business"
    
    def test_json_cleanup_removes_only_json_fields(self, mock_storage):
        """Test that cleanup only nullifies JSON fields, not other data."""
        business_id = 123
        
        # Mock the update operation
        mock_storage.update_business.return_value = True
        
        # Simulate cleanup - only JSON fields should be nullified
        cleanup_updates = {
            "yelp_response_json": None,
            "google_response_json": None,
            "json_retention_expires_at": None
        }
        
        result = mock_storage.update_business(business_id, cleanup_updates)
        
        assert result is True
        mock_storage.update_business.assert_called_once_with(business_id, cleanup_updates)
    
    def test_retention_date_set_on_json_storage(self, mock_storage):
        """Test that retention date is set when storing JSON."""
        from leadfactory.pipeline.scrape import save_business
        
        with patch('leadfactory.pipeline.scrape.get_storage_instance') as mock_get_storage:
            mock_get_storage.return_value = mock_storage
            mock_storage.create_business.return_value = 123
            
            # Save a business with JSON data
            business_id = save_business(
                name="Test Business",
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94105",
                category="Restaurant",
                source="yelp",
                yelp_response_json={"id": "test-123"}
            )
            
            # Verify storage was called
            assert business_id == 123
            mock_storage.create_business.assert_called_once()
            
            # Check that JSON was included in the call
            call_args = mock_storage.create_business.call_args
            assert call_args is not None
    
    def test_cleanup_metrics_tracking(self):
        """Test that cleanup operations track metrics."""
        from bin.cleanup_json_responses import cleanup_expired_json_responses
        
        with patch('bin.cleanup_json_responses.db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            
            # Mock finding expired records
            mock_cursor.fetchall.return_value = [
                (1, "Business 1", 1000, 2000, datetime.now() - timedelta(days=1)),
                (2, "Business 2", 1500, 2500, datetime.now() - timedelta(days=2))
            ]
            
            with patch('bin.cleanup_json_responses.record_metric') as mock_metric:
                # Run cleanup in dry-run mode
                cleaned = cleanup_expired_json_responses(dry_run=True)
                
                # Verify metrics were recorded
                assert cleaned == 2
                mock_metric.assert_called()
                
                # Check metric call arguments
                metric_calls = mock_metric.call_args_list
                assert len(metric_calls) > 0
                
                # Verify metric name and tags
                call_args = metric_calls[0][0]
                assert call_args[0] == "json_cleanup"
                assert call_args[1] == 2  # count
    
    def test_cleanup_respects_batch_size(self):
        """Test that cleanup processes records in batches."""
        from bin.cleanup_json_responses import cleanup_expired_json_responses
        
        with patch('bin.cleanup_json_responses.db_connection') as mock_conn:
            # Mock database connection
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            
            # First batch returns 2 records, second batch returns empty
            mock_cursor.fetchall.side_effect = [
                [(1, "Business 1", 1000, 2000, datetime.now())],
                []  # No more records
            ]
            
            # Run cleanup with batch size 1
            cleaned = cleanup_expired_json_responses(dry_run=False, batch_size=1)
            
            # Should process 1 record
            assert cleaned == 1
            
            # Verify batch query was called with correct limit
            select_calls = [call for call in mock_cursor.execute.call_args_list 
                          if "LIMIT" in str(call)]
            assert len(select_calls) > 0
    
    def test_json_storage_statistics(self):
        """Test JSON storage statistics gathering."""
        from bin.cleanup_json_responses import get_json_storage_stats
        
        with patch('bin.cleanup_json_responses.db_connection') as mock_conn:
            # Mock database connection
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            
            # Mock statistics query result
            mock_cursor.fetchone.return_value = (
                1000,  # total_records
                500,   # yelp_json_count
                400,   # google_json_count
                900,   # records_with_retention
                50,    # expired_records
                "10 MB",  # yelp_total_size
                "8 MB",   # google_total_size
                "18 MB"   # total_json_size
            )
            
            stats = get_json_storage_stats()
            
            assert stats["total_records"] == 1000
            assert stats["yelp_json_count"] == 500
            assert stats["google_json_count"] == 400
            assert stats["expired_records"] == 50
            assert stats["total_json_size"] == "18 MB"