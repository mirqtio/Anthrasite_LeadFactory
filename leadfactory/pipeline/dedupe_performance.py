"""
Performance optimization module for deduplication operations.

This module provides optimized versions of deduplication functions
with batch processing, caching, and parallel execution capabilities.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.config.dedupe_config import DedupeConfig
from leadfactory.pipeline.dedupe_logging import DedupeLogger, dedupe_operation
from leadfactory.storage.factory import get_storage
from leadfactory.utils.e2e_db_connector import (
    get_potential_duplicate_pairs,
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Track performance metrics for deduplication operations."""

    total_pairs: int = 0
    processed_pairs: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    batch_operations: int = 0
    parallel_operations: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def pairs_per_second(self) -> float:
        return self.processed_pairs / self.duration if self.duration > 0 else 0.0


class BusinessCache:
    """Thread-safe cache for business records."""

    def __init__(self, max_size: int = 1000):
        self._cache = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._access_count = defaultdict(int)

    def get(self, business_id: int) -> Optional[dict[str, Any]]:
        """Get business from cache."""
        with self._lock:
            if business_id in self._cache:
                self._access_count[business_id] += 1
                return self._cache[business_id]
            return None

    def put(self, business_id: int, business: dict[str, Any]) -> None:
        """Put business in cache with LRU eviction."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict least recently used
                lru_id = min(
                    self._access_count.keys(), key=lambda k: self._access_count[k]
                )
                del self._cache[lru_id]
                del self._access_count[lru_id]

            self._cache[business_id] = business
            self._access_count[business_id] = 1

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_count.clear()


class OptimizedDeduplicator:
    """Optimized deduplication processor with batch operations and caching."""

    def __init__(self, config: DedupeConfig, max_workers: int = 4):
        self.config = config
        self.max_workers = max_workers
        self.business_cache = BusinessCache(
            max_size=config.cache_size if hasattr(config, "cache_size") else 1000
        )
        self.metrics = PerformanceMetrics()
        self.dedupe_logger = DedupeLogger()

    def get_business_batch(self, business_ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        Get multiple businesses in a single database query.

        Args:
            business_ids: List of business IDs to fetch

        Returns:
            Dictionary mapping business_id to business data
        """
        # Check cache first
        cached_businesses = {}
        missing_ids = []

        for business_id in business_ids:
            cached = self.business_cache.get(business_id)
            if cached:
                cached_businesses[business_id] = cached
                self.metrics.cache_hits += 1
            else:
                missing_ids.append(business_id)
                self.metrics.cache_misses += 1

        # Fetch missing businesses in batch
        if missing_ids:
            storage = get_storage()
            businesses = storage.get_businesses(missing_ids)

            for business in businesses:
                business_id = business["id"]
                cached_businesses[business_id] = business
                self.business_cache.put(business_id, business)

        return cached_businesses

    def process_pairs_batch(
        self, pairs: list[dict[str, Any]], batch_size: int = 50
    ) -> dict[str, int]:
        """
        Process duplicate pairs in batches for better performance.

        Args:
            pairs: List of duplicate pairs to process
            batch_size: Number of pairs to process in each batch

        Returns:
            Statistics dictionary
        """
        stats = {"processed": 0, "merged": 0, "flagged": 0, "errors": 0}

        # Process in batches
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i : i + batch_size]
            batch_stats = self._process_single_batch(batch)

            # Aggregate stats
            for key in stats:
                stats[key] += batch_stats[key]

            self.metrics.batch_operations += 1

            # Log progress
            logger.info(
                f"Processed batch {i//batch_size + 1}/{(len(pairs) + batch_size - 1)//batch_size}"
            )

        return stats

    def _process_single_batch(self, batch: list[dict[str, Any]]) -> dict[str, int]:
        """Process a single batch of duplicate pairs."""
        stats = {"processed": 0, "merged": 0, "flagged": 0, "errors": 0}

        # Collect all unique business IDs in the batch
        business_ids = set()
        for pair in batch:
            business_ids.add(pair["business1_id"])
            business_ids.add(pair["business2_id"])

        # Fetch all businesses in one query
        businesses = self.get_business_batch(list(business_ids))

        # Process each pair
        for pair in batch:
            try:
                business1 = businesses.get(pair["business1_id"])
                business2 = businesses.get(pair["business2_id"])

                if not business1 or not business2:
                    logger.warning(
                        f"Missing business data for pair {pair['business1_id']}, {pair['business2_id']}"
                    )
                    stats["errors"] += 1
                    continue

                # Apply business logic (simplified for performance)
                if self._should_merge(business1, business2):
                    # Perform merge
                    primary_id, secondary_id = self._select_primary(
                        business1, business2
                    )
                    if self._merge_businesses_optimized(primary_id, secondary_id):
                        stats["merged"] += 1
                        self.dedupe_logger.log_merge(
                            primary_id, secondary_id, 0.9, "batch_processing"
                        )
                    else:
                        stats["errors"] += 1
                else:
                    # Flag for review
                    stats["flagged"] += 1

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing pair: {e}")
                stats["errors"] += 1

        return stats

    def process_pairs_parallel(self, pairs: list[dict[str, Any]]) -> dict[str, int]:
        """
        Process duplicate pairs in parallel using thread pool.

        Args:
            pairs: List of duplicate pairs to process

        Returns:
            Statistics dictionary
        """
        stats = {"processed": 0, "merged": 0, "flagged": 0, "errors": 0}

        # Split pairs into chunks for parallel processing
        chunk_size = max(1, len(pairs) // self.max_workers)
        chunks = [pairs[i : i + chunk_size] for i in range(0, len(pairs), chunk_size)]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(self._process_single_batch, chunk): chunk
                for chunk in chunks
            }

            # Collect results
            for future in as_completed(future_to_chunk):
                try:
                    chunk_stats = future.result()
                    for key in stats:
                        stats[key] += chunk_stats[key]
                    self.metrics.parallel_operations += 1
                except Exception as e:
                    logger.error(f"Error in parallel processing: {e}")
                    stats["errors"] += len(future_to_chunk[future])

        return stats

    def _should_merge(
        self, business1: dict[str, Any], business2: dict[str, Any]
    ) -> bool:
        """Determine if two businesses should be merged (simplified logic)."""
        # Quick checks for exact matches
        if business1.get("website") and business2.get("website"):
            return business1["website"].lower() == business2["website"].lower()

        if business1.get("phone") and business2.get("phone"):
            return business1["phone"] == business2["phone"]

        # Name similarity check
        if business1.get("name") and business2.get("name"):
            from Levenshtein import ratio

            similarity = ratio(business1["name"].lower(), business2["name"].lower())
            return similarity >= self.config.name_similarity_threshold

        return False

    def _select_primary(
        self, business1: dict[str, Any], business2: dict[str, Any]
    ) -> tuple[int, int]:
        """Select primary business based on data quality."""
        # Simple heuristic: prefer business with more complete data
        score1 = sum(
            1
            for field in ["name", "address", "phone", "email", "website"]
            if business1.get(field)
        )
        score2 = sum(
            1
            for field in ["name", "address", "phone", "email", "website"]
            if business2.get(field)
        )

        if score1 >= score2:
            return business1["id"], business2["id"]
        else:
            return business2["id"], business1["id"]

    def _merge_businesses_optimized(self, primary_id: int, secondary_id: int) -> bool:
        """Optimized business merge with minimal database operations."""
        try:
            # Use the existing merge function but with optimizations
            storage = get_storage()
            result = storage.merge_businesses(primary_id, secondary_id)
            return result is not None
        except Exception as e:
            logger.error(f"Error merging businesses {primary_id}, {secondary_id}: {e}")
            return False

    def optimize_database_indexes(self) -> bool:
        """Create database indexes for better performance."""
        indexes = [
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_name_gin ON businesses USING gin(to_tsvector('english', name))",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_phone ON businesses(phone) WHERE phone IS NOT NULL",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_website ON businesses(website) WHERE website IS NOT NULL",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_zip ON businesses(zip)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_source ON businesses(source)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_processed ON businesses(processed)",
        ]

        try:
            storage = get_storage()
            for index_sql in indexes:
                try:
                    storage.execute(index_sql)
                    logger.info(f"Created index: {index_sql}")
                except Exception as e:
                    logger.warning(f"Index creation failed (may already exist): {e}")
            return True
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            return False

    def get_performance_report(self) -> dict[str, Any]:
        """Generate a performance report."""
        return {
            "metrics": {
                "total_pairs": self.metrics.total_pairs,
                "processed_pairs": self.metrics.processed_pairs,
                "duration_seconds": self.metrics.duration,
                "pairs_per_second": self.metrics.pairs_per_second,
                "cache_hit_rate": self.metrics.cache_hit_rate,
                "cache_hits": self.metrics.cache_hits,
                "cache_misses": self.metrics.cache_misses,
                "batch_operations": self.metrics.batch_operations,
                "parallel_operations": self.metrics.parallel_operations,
            },
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> list[str]:
        """Generate performance recommendations based on metrics."""
        recommendations = []

        if self.metrics.cache_hit_rate < 0.5:
            recommendations.append(
                "Consider increasing cache size for better performance"
            )

        if self.metrics.pairs_per_second < 10:
            recommendations.append("Consider increasing batch size or parallel workers")

        if self.metrics.parallel_operations == 0:
            recommendations.append("Enable parallel processing for large datasets")

        return recommendations


def run_optimized_deduplication(
    config: Optional[DedupeConfig] = None,
    limit: Optional[int] = None,
    use_parallel: bool = True,
    batch_size: int = 50,
) -> dict[str, Any]:
    """
    Run optimized deduplication with performance tracking.

    Args:
        config: Deduplication configuration
        limit: Maximum number of pairs to process
        use_parallel: Whether to use parallel processing
        batch_size: Batch size for processing

    Returns:
        Results dictionary with stats and performance metrics
    """
    from leadfactory.config.dedupe_config import load_dedupe_config

    if config is None:
        config = load_dedupe_config()

    # Initialize optimized deduplicator
    deduplicator = OptimizedDeduplicator(config)
    deduplicator.metrics.start_time = time.time()

    try:
        # Optimize database indexes first
        logger.info("Optimizing database indexes...")
        deduplicator.optimize_database_indexes()

        # Get potential duplicates
        logger.info("Fetching potential duplicates...")
        pairs = get_potential_duplicate_pairs(limit)
        deduplicator.metrics.total_pairs = len(pairs)

        logger.info(f"Processing {len(pairs)} potential duplicate pairs...")

        # Choose processing method
        if use_parallel and len(pairs) > 100:
            logger.info("Using parallel processing...")
            stats = deduplicator.process_pairs_parallel(pairs)
        else:
            logger.info("Using batch processing...")
            stats = deduplicator.process_pairs_batch(pairs, batch_size)

        deduplicator.metrics.processed_pairs = stats["processed"]
        deduplicator.metrics.end_time = time.time()

        # Generate performance report
        performance_report = deduplicator.get_performance_report()

        return {"stats": stats, "performance": performance_report}

    except Exception as e:
        logger.error(f"Error in optimized deduplication: {e}")
        deduplicator.metrics.end_time = time.time()
        raise
