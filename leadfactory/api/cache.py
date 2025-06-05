"""
Caching layer for the Logs API to improve performance.

This module provides in-memory caching for frequently accessed data
and implements cache invalidation strategies.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL and metadata."""

    data: Any
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl_seconds <= 0:
            return False  # Never expires
        return datetime.utcnow() - self.created_at > timedelta(seconds=self.ttl_seconds)

    def access(self) -> Any:
        """Access the cached data and update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        return self.data


class LogsAPICache:
    """
    In-memory cache for the Logs API with TTL and LRU eviction.

    Features:
    - Time-based expiration (TTL)
    - LRU eviction when memory limit is reached
    - Query result caching with cache key generation
    - Statistics and cache hit/miss tracking
    """

    def __init__(self, max_entries: int = 1000, default_ttl: int = 300):
        """
        Initialize the cache.

        Args:
            max_entries: Maximum number of entries to store
            default_ttl: Default TTL in seconds (5 minutes)
        """
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.cache: dict[str, CacheEntry] = {}
        self.lock = Lock()

        # Statistics
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "expired_cleanups": 0}

        logger.info(
            f"Cache initialized with max_entries={max_entries}, default_ttl={default_ttl}s"
        )

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from parameters."""
        # Sort kwargs to ensure consistent key generation
        sorted_params = sorted(kwargs.items())
        params_str = json.dumps(sorted_params, sort_keys=True, default=str)
        hash_obj = hashlib.md5(params_str.encode(), usedforsecurity=False)  # nosec
        return f"{prefix}:{hash_obj.hexdigest()}"

    def _evict_lru(self):
        """Evict least recently used entries."""
        if len(self.cache) <= self.max_entries:
            return

        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            self.cache.items(), key=lambda x: x[1].last_accessed or x[1].created_at
        )

        # Remove oldest entries until we're under the limit
        entries_to_remove = len(self.cache) - self.max_entries + 1
        for i in range(entries_to_remove):
            key, _ = sorted_entries[i]
            del self.cache[key]
            self.stats["evictions"] += 1

        logger.debug(f"Evicted {entries_to_remove} LRU entries")

    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        datetime.utcnow()
        expired_keys = []

        for key, entry in self.cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]
            self.stats["expired_cleanups"] += 1

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self.lock:
            entry = self.cache.get(key)

            if entry is None:
                self.stats["misses"] += 1
                return None

            if entry.is_expired():
                del self.cache[key]
                self.stats["misses"] += 1
                self.stats["expired_cleanups"] += 1
                return None

            self.stats["hits"] += 1
            return entry.access()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache."""
        with self.lock:
            ttl = ttl if ttl is not None else self.default_ttl

            self.cache[key] = CacheEntry(
                data=value, created_at=datetime.utcnow(), ttl_seconds=ttl
            )

            # Cleanup and eviction
            self._cleanup_expired()
            self._evict_lru()

    def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            logger.info("Cache cleared")

    def get_logs_with_filters(
        self,
        business_id: Optional[int] = None,
        log_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ) -> Optional[tuple[list[dict[str, Any]], int]]:
        """Get cached logs query result."""
        cache_key = self._generate_cache_key(
            "logs_query",
            business_id=business_id,
            log_type=log_type,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            search_query=search_query,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return self.get(cache_key)

    def set_logs_with_filters(
        self,
        result: tuple[list[dict[str, Any]], int],
        business_id: Optional[int] = None,
        log_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
        ttl: Optional[int] = None,
    ) -> None:
        """Cache logs query result."""
        cache_key = self._generate_cache_key(
            "logs_query",
            business_id=business_id,
            log_type=log_type,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            search_query=search_query,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Use shorter TTL for search queries and larger datasets
        if search_query or limit > 100:
            ttl = ttl or 60  # 1 minute for search results
        else:
            ttl = ttl or self.default_ttl

        self.set(cache_key, result, ttl)

    def get_log_statistics(self) -> Optional[dict[str, Any]]:
        """Get cached log statistics."""
        return self.get("log_statistics")

    def set_log_statistics(
        self, stats: dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """Cache log statistics."""
        # Statistics change less frequently, cache for longer
        ttl = ttl or 600  # 10 minutes
        self.set("log_statistics", stats, ttl)

    def get_businesses_with_logs(self) -> Optional[list[dict[str, Any]]]:
        """Get cached businesses with logs."""
        return self.get("businesses_with_logs")

    def set_businesses_with_logs(
        self, businesses: list[dict[str, Any]], ttl: Optional[int] = None
    ) -> None:
        """Cache businesses with logs."""
        ttl = ttl or 900  # 15 minutes
        self.set("businesses_with_logs", businesses, ttl)

    def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching a pattern."""
        with self.lock:
            keys_to_delete = [key for key in self.cache if pattern in key]
            for key in keys_to_delete:
                del self.cache[key]

            if keys_to_delete:
                logger.info(
                    f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}"
                )

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = (self.stats["hits"] / max(total_requests, 1)) * 100

            return {
                "size": len(self.cache),
                "max_entries": self.max_entries,
                "hit_rate": round(hit_rate, 2),
                "total_hits": self.stats["hits"],
                "total_misses": self.stats["misses"],
                "total_evictions": self.stats["evictions"],
                "expired_cleanups": self.stats["expired_cleanups"],
                "memory_usage_percent": round(
                    (len(self.cache) / self.max_entries) * 100, 2
                ),
            }


# Global cache instance
_cache_instance = None


def get_cache() -> LogsAPICache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = LogsAPICache()
    return _cache_instance


def clear_cache():
    """Clear the global cache."""
    cache = get_cache()
    cache.clear()


def get_cache_stats() -> dict[str, Any]:
    """Get global cache statistics."""
    cache = get_cache()
    return cache.get_stats()
