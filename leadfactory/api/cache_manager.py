"""
Cache management for API responses and frequently accessed data.

Provides multi-level caching with Redis and in-memory caches for
optimal performance.
"""

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for cache manager."""

    redis_url: str = "redis://localhost:6379/0"
    default_ttl: int = 300  # 5 minutes
    max_memory_items: int = 1000
    enable_compression: bool = True
    key_prefix: str = "leadfactory"

    # TTL configurations for different data types
    ttl_configs: dict[str, int] = None

    def __post_init__(self):
        if self.ttl_configs is None:
            self.ttl_configs = {
                "api_response": 60,  # 1 minute for API responses
                "business_data": 3600,  # 1 hour for business data
                "enrichment": 86400,  # 24 hours for enrichment data
                "report": 7200,  # 2 hours for reports
                "pricing": 300,  # 5 minutes for pricing
                "static": 86400,  # 24 hours for static content
            }


class CacheManager:
    """Manages multi-level caching for application data."""

    def __init__(self, config: CacheConfig = None):
        """Initialize cache manager."""
        self.config = config or CacheConfig()
        self._memory_cache = {}
        self._cache_stats = {"hits": 0, "misses": 0, "errors": 0, "evictions": 0}

        # Initialize Redis connection
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                decode_responses=False,  # We'll handle encoding/decoding
            )
            self.redis_client.ping()
            self.redis_available = True
            logger.info("Redis cache connected successfully")
        except (RedisError, Exception) as e:
            logger.warning(f"Redis not available, using memory cache only: {e}")
            self.redis_client = None
            self.redis_available = False

    def _generate_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Generate a namespaced cache key."""
        parts = [self.config.key_prefix]
        if namespace:
            parts.append(namespace)
        parts.append(key)
        return ":".join(parts)

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            # Try JSON first (more portable)
            return json.dumps(value).encode("utf-8")
        except (TypeError, ValueError):
            # Fall back to pickle for complex objects
            return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if not data:
            return None

        try:
            # Try JSON first
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(data)

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Get value from cache."""
        full_key = self._generate_key(key, namespace)

        # Check memory cache first
        if full_key in self._memory_cache:
            entry = self._memory_cache[full_key]
            if entry["expires_at"] > time.time():
                self._cache_stats["hits"] += 1
                logger.debug(f"Memory cache hit: {full_key}")
                return entry["value"]
            else:
                # Expired, remove from memory
                del self._memory_cache[full_key]

        # Check Redis if available
        if self.redis_available:
            try:
                data = self.redis_client.get(full_key)
                if data:
                    value = self._deserialize(data)

                    # Store in memory cache for faster subsequent access
                    ttl = self.redis_client.ttl(full_key)
                    if ttl > 0:
                        self._store_in_memory(full_key, value, ttl)

                    self._cache_stats["hits"] += 1
                    logger.debug(f"Redis cache hit: {full_key}")
                    return value
            except RedisError as e:
                logger.warning(f"Redis get error: {e}")
                self._cache_stats["errors"] += 1

        self._cache_stats["misses"] += 1
        logger.debug(f"Cache miss: {full_key}")
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        cache_type: Optional[str] = None,
    ) -> bool:
        """Set value in cache."""
        full_key = self._generate_key(key, namespace)

        # Determine TTL
        if ttl is None:
            if cache_type and cache_type in self.config.ttl_configs:
                ttl = self.config.ttl_configs[cache_type]
            else:
                ttl = self.config.default_ttl

        # Store in memory cache
        self._store_in_memory(full_key, value, ttl)

        # Store in Redis if available
        if self.redis_available:
            try:
                serialized = self._serialize(value)
                self.redis_client.setex(full_key, ttl, serialized)
                logger.debug(f"Cached {full_key} with TTL {ttl}s")
                return True
            except RedisError as e:
                logger.warning(f"Redis set error: {e}")
                self._cache_stats["errors"] += 1

        return True

    def _store_in_memory(self, key: str, value: Any, ttl: int):
        """Store value in memory cache with eviction if needed."""
        # Evict oldest entries if at capacity
        if len(self._memory_cache) >= self.config.max_memory_items:
            # Find and remove oldest entry
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k]["created_at"],
            )
            del self._memory_cache[oldest_key]
            self._cache_stats["evictions"] += 1

        self._memory_cache[key] = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete value from cache."""
        full_key = self._generate_key(key, namespace)

        # Remove from memory cache
        if full_key in self._memory_cache:
            del self._memory_cache[full_key]

        # Remove from Redis
        if self.redis_available:
            try:
                self.redis_client.delete(full_key)
                return True
            except RedisError as e:
                logger.warning(f"Redis delete error: {e}")
                self._cache_stats["errors"] += 1

        return True

    def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        pattern = self._generate_key("*", namespace)
        count = 0

        # Clear from memory cache
        keys_to_delete = [k for k in self._memory_cache if k.startswith(pattern[:-1])]
        for key in keys_to_delete:
            del self._memory_cache[key]
            count += 1

        # Clear from Redis
        if self.redis_available:
            try:
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor, match=pattern, count=100
                    )
                    if keys:
                        self.redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except RedisError as e:
                logger.warning(f"Redis clear namespace error: {e}")
                self._cache_stats["errors"] += 1

        logger.info(f"Cleared {count} keys from namespace {namespace}")
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0
        )

        stats = {
            **self._cache_stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "memory_cache_size": len(self._memory_cache),
            "redis_available": self.redis_available,
        }

        # Get Redis stats if available
        if self.redis_available:
            try:
                info = self.redis_client.info()
                stats["redis_memory_used"] = info.get("used_memory_human", "N/A")
                stats["redis_connected_clients"] = info.get("connected_clients", 0)
                stats["redis_total_keys"] = self.redis_client.dbsize()
            except RedisError:
                pass

        return stats

    def cached(
        self,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        cache_type: Optional[str] = None,
        key_func: Optional[Callable] = None,
    ):
        """Decorator for caching function results."""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                    cache_key = hashlib.md5(
                        ":".join(key_parts).encode(), usedforsecurity=False
                    ).hexdigest()

                # Try to get from cache
                cached_value = self.get(cache_key, namespace)
                if cached_value is not None:
                    return cached_value

                # Call function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl, namespace, cache_type)

                return result

            return wrapper

        return decorator


# Global cache instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance."""
    global _cache_manager

    if _cache_manager is None:
        import os

        config = CacheConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            key_prefix=os.getenv("CACHE_KEY_PREFIX", "leadfactory"),
        )
        _cache_manager = CacheManager(config)

    return _cache_manager


# Convenience decorators
def cache_api_response(ttl: int = 60):
    """Cache API responses for the specified TTL."""
    cache = get_cache_manager()
    return cache.cached(ttl=ttl, namespace="api", cache_type="api_response")


def cache_business_data(ttl: int = 3600):
    """Cache business data for the specified TTL."""
    cache = get_cache_manager()
    return cache.cached(ttl=ttl, namespace="business", cache_type="business_data")


def cache_report(ttl: int = 7200):
    """Cache generated reports for the specified TTL."""
    cache = get_cache_manager()
    return cache.cached(ttl=ttl, namespace="report", cache_type="report")


# Example usage
if __name__ == "__main__":
    # Initialize cache
    cache = get_cache_manager()

    # Basic usage
    cache.set("test_key", {"data": "test"}, ttl=60)
    value = cache.get("test_key")

    # Using decorator
    @cache_api_response(ttl=30)
    def expensive_api_call(param1: str, param2: int) -> dict:
        time.sleep(1)  # Simulate expensive operation
        return {
            "result": f"{param1}_{param2}",
            "timestamp": datetime.utcnow().isoformat(),
        }

    # First call - will execute function
    result1 = expensive_api_call("test", 123)

    # Second call - will use cache
    result2 = expensive_api_call("test", 123)

    # Get cache stats
    stats = cache.get_stats()
