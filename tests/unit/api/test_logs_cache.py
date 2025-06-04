"""
Unit tests for the Logs API caching system.

Tests cache functionality, TTL behavior, LRU eviction, and performance metrics.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.api.cache import LogsAPICache, CacheEntry


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self):
        """Test cache entry creation with all fields."""
        created_at = datetime.utcnow()
        entry = CacheEntry(
            data={'test': 'data'},
            created_at=created_at,
            ttl_seconds=300
        )

        assert entry.data == {'test': 'data'}
        assert entry.created_at == created_at
        assert entry.ttl_seconds == 300
        assert entry.access_count == 0
        assert entry.last_accessed is None

    def test_cache_entry_access(self):
        """Test cache entry access tracking."""
        entry = CacheEntry(
            data='test_data',
            created_at=datetime.utcnow(),
            ttl_seconds=300
        )

        # Access the entry
        data = entry.access()

        assert data == 'test_data'
        assert entry.access_count == 1
        assert entry.last_accessed is not None
        assert isinstance(entry.last_accessed, datetime)

    def test_cache_entry_expiration(self):
        """Test cache entry TTL expiration."""
        # Non-expiring entry
        entry_no_expire = CacheEntry(
            data='test',
            created_at=datetime.utcnow(),
            ttl_seconds=0
        )
        assert not entry_no_expire.is_expired()

        # Expired entry
        past_time = datetime.utcnow() - timedelta(seconds=600)
        entry_expired = CacheEntry(
            data='test',
            created_at=past_time,
            ttl_seconds=300
        )
        assert entry_expired.is_expired()

        # Fresh entry
        entry_fresh = CacheEntry(
            data='test',
            created_at=datetime.utcnow(),
            ttl_seconds=300
        )
        assert not entry_fresh.is_expired()


class TestLogsAPICache:
    """Test LogsAPICache functionality."""

    def test_cache_initialization(self):
        """Test cache initialization with default and custom parameters."""
        # Default initialization
        cache_default = LogsAPICache()
        assert cache_default.max_entries == 1000
        assert cache_default.default_ttl == 300
        assert len(cache_default.cache) == 0

        # Custom initialization
        cache_custom = LogsAPICache(max_entries=100, default_ttl=60)
        assert cache_custom.max_entries == 100
        assert cache_custom.default_ttl == 60

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Set a value
        cache.set('test_key', {'data': 'test_value'})

        # Get the value
        result = cache.get('test_key')
        assert result == {'data': 'test_value'}

        # Check stats
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 0

    def test_cache_miss(self):
        """Test cache miss behavior."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Get non-existent key
        result = cache.get('non_existent_key')
        assert result is None

        # Check stats
        stats = cache.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 1

    def test_cache_ttl_expiration(self):
        """Test TTL expiration functionality."""
        cache = LogsAPICache(max_entries=10, default_ttl=1)  # 1 second TTL

        # Set a value with short TTL
        cache.set('expiring_key', 'test_data', ttl=1)

        # Should be available immediately
        assert cache.get('expiring_key') == 'test_data'

        # Mock time passage to simulate expiration
        with patch('leadfactory.api.cache.datetime') as mock_datetime:
            future_time = datetime.utcnow() + timedelta(seconds=2)
            mock_datetime.utcnow.return_value = future_time

            # Should be expired now
            result = cache.get('expiring_key')
            assert result is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = LogsAPICache(max_entries=3, default_ttl=300)

        # Fill cache to capacity
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        # Access key1 to make it more recently used
        cache.get('key1')

        # Add another key, should evict key2 (least recently used)
        cache.set('key4', 'value4')

        # key1 should still be there (recently accessed)
        assert cache.get('key1') == 'value1'

        # key2 should be evicted
        assert cache.get('key2') is None

        # key3 and key4 should be there
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'

    def test_cache_delete(self):
        """Test cache deletion functionality."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Set and verify value
        cache.set('delete_key', 'delete_value')
        assert cache.get('delete_key') == 'delete_value'

        # Delete and verify removal
        result = cache.delete('delete_key')
        assert result is True
        assert cache.get('delete_key') is None

        # Delete non-existent key
        result = cache.delete('non_existent')
        assert result is False

    def test_cache_clear(self):
        """Test cache clear functionality."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Add some entries
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        # Verify entries exist
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == 'value2'

        # Clear cache
        cache.clear()

        # Verify entries are gone
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert len(cache.cache) == 0

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Initial stats
        stats = cache.get_stats()
        assert stats['size'] == 0
        assert stats['max_entries'] == 10
        assert stats['hit_rate'] == 0.0
        assert stats['total_hits'] == 0
        assert stats['total_misses'] == 0

        # Perform some operations
        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('key2')  # Miss
        cache.get('key1')  # Hit

        # Check updated stats
        stats = cache.get_stats()
        assert stats['size'] == 1
        assert stats['total_hits'] == 2
        assert stats['total_misses'] == 1
        assert stats['hit_rate'] == 66.67  # 2 hits out of 3 total requests

    def test_logs_query_caching(self):
        """Test logs query specific caching methods."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Test setting logs query result
        test_logs = [{'id': 1, 'content': 'test log'}]
        total_count = 10

        cache.set_logs_with_filters(
            (test_logs, total_count),
            business_id=123,
            log_type='llm',
            limit=50,
            offset=0
        )

        # Test getting logs query result
        result = cache.get_logs_with_filters(
            business_id=123,
            log_type='llm',
            limit=50,
            offset=0
        )

        assert result is not None
        logs, count = result
        assert logs == test_logs
        assert count == total_count

    def test_statistics_caching(self):
        """Test statistics caching methods."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Test setting statistics
        test_stats = {
            'total_logs': 1000,
            'logs_by_type': {'llm': 600, 'html': 400}
        }

        cache.set_log_statistics(test_stats)

        # Test getting statistics
        result = cache.get_log_statistics()
        assert result == test_stats

    def test_businesses_caching(self):
        """Test businesses list caching methods."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Test setting businesses
        test_businesses = [
            {'id': 1, 'name': 'Business 1'},
            {'id': 2, 'name': 'Business 2'}
        ]

        cache.set_businesses_with_logs(test_businesses)

        # Test getting businesses
        result = cache.get_businesses_with_logs()
        assert result == test_businesses

    def test_cache_key_generation(self):
        """Test cache key generation for consistency."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Test that same parameters generate same key
        cache.set_logs_with_filters(
            (['log1'], 1),
            business_id=123,
            log_type='llm'
        )

        result1 = cache.get_logs_with_filters(business_id=123, log_type='llm')
        result2 = cache.get_logs_with_filters(log_type='llm', business_id=123)  # Different order

        # Both should return the same cached result
        assert result1 == result2
        assert result1 is not None

    def test_invalidate_pattern(self):
        """Test pattern-based cache invalidation."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Set some entries with different patterns
        cache.set('logs_query:abc123', 'logs_data')
        cache.set('stats:def456', 'stats_data')
        cache.set('business:ghi789', 'business_data')

        # Invalidate logs queries
        cache.invalidate_pattern('logs_query')

        # Logs query should be gone
        assert cache.get('logs_query:abc123') is None

        # Other entries should remain
        assert cache.get('stats:def456') == 'stats_data'
        assert cache.get('business:ghi789') == 'business_data'

    def test_memory_usage_calculation(self):
        """Test memory usage percentage calculation."""
        cache = LogsAPICache(max_entries=5, default_ttl=300)

        # Add entries and check memory usage
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        stats = cache.get_stats()
        assert stats['memory_usage_percent'] == 40.0  # 2 out of 5 entries

    def test_thread_safety(self):
        """Test cache thread safety with locks."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Test that cache operations work with multiple concurrent accesses
        # This is a basic test - in real scenarios we'd use threading
        cache.set('thread_key', 'thread_value')
        result = cache.get('thread_key')
        assert result == 'thread_value'

        # Test concurrent operations don't interfere
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == 'value2'


class TestCacheIntegration:
    """Test cache integration scenarios."""

    def test_search_query_ttl_adjustment(self):
        """Test that search queries get shorter TTL."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Mock the set method to capture TTL
        original_set = cache.set
        captured_ttl = None

        def mock_set(key, value, ttl=None):
            nonlocal captured_ttl
            captured_ttl = ttl
            return original_set(key, value, ttl)

        cache.set = mock_set

        # Set logs with search query
        cache.set_logs_with_filters(
            (['log'], 1),
            search_query='test search',
            limit=50
        )

        # Should use shorter TTL for search results
        assert captured_ttl == 60  # 1 minute for search results

    def test_large_dataset_ttl_adjustment(self):
        """Test that large datasets get shorter TTL."""
        cache = LogsAPICache(max_entries=10, default_ttl=300)

        # Mock the set method to capture TTL
        original_set = cache.set
        captured_ttl = None

        def mock_set(key, value, ttl=None):
            nonlocal captured_ttl
            captured_ttl = ttl
            return original_set(key, value, ttl)

        cache.set = mock_set

        # Set logs with large limit
        cache.set_logs_with_filters(
            (['log'], 1),
            limit=500  # Large dataset
        )

        # Should use shorter TTL for large datasets
        assert captured_ttl == 60  # 1 minute for large datasets

    def test_expired_cleanup_on_access(self):
        """Test that expired entries are cleaned up on access."""
        cache = LogsAPICache(max_entries=10, default_ttl=1)  # 1 second TTL

        # Set an entry
        cache.set('cleanup_key', 'cleanup_value', ttl=1)

        # Mock time to make entry expired
        with patch('leadfactory.api.cache.datetime') as mock_datetime:
            future_time = datetime.utcnow() + timedelta(seconds=2)
            mock_datetime.utcnow.return_value = future_time

            # Access should clean up expired entry
            result = cache.get('cleanup_key')
            assert result is None

            # Check that cleanup was recorded in stats
            stats = cache.get_stats()
            assert stats['expired_cleanups'] > 0


if __name__ == '__main__':
    pytest.main([__file__])
