"""
Test suite for deduplication performance optimizations.

This module tests the performance improvements including batch processing,
caching, parallel execution, and database optimizations.
"""

import os
import sys
import tempfile
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import performance module by loading it directly
import importlib.util

spec = importlib.util.spec_from_file_location(
    "dedupe_performance",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "leadfactory/pipeline/dedupe_performance.py")
)
dedupe_performance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dedupe_performance)

# Extract classes and functions
OptimizedDeduplicator = dedupe_performance.OptimizedDeduplicator
BusinessCache = dedupe_performance.BusinessCache
PerformanceMetrics = dedupe_performance.PerformanceMetrics
run_optimized_deduplication = dedupe_performance.run_optimized_deduplication


class TestPerformanceMetrics(unittest.TestCase):
    """Test cases for PerformanceMetrics class."""

    def test_metrics_initialization(self):
        """Test that performance metrics initialize correctly."""
        metrics = PerformanceMetrics()

        self.assertEqual(metrics.total_pairs, 0)
        self.assertEqual(metrics.processed_pairs, 0)
        self.assertEqual(metrics.cache_hits, 0)
        self.assertEqual(metrics.cache_misses, 0)
        self.assertEqual(metrics.duration, 0.0)
        self.assertEqual(metrics.cache_hit_rate, 0.0)
        self.assertEqual(metrics.pairs_per_second, 0.0)

    def test_metrics_calculations(self):
        """Test metric calculations."""
        metrics = PerformanceMetrics()
        metrics.start_time = 1000.0
        metrics.end_time = 1010.0
        metrics.processed_pairs = 100
        metrics.cache_hits = 80
        metrics.cache_misses = 20

        self.assertEqual(metrics.duration, 10.0)
        self.assertEqual(metrics.pairs_per_second, 10.0)
        self.assertEqual(metrics.cache_hit_rate, 0.8)


class TestBusinessCache(unittest.TestCase):
    """Test business caching functionality."""

    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        cache = BusinessCache(max_size=3)

        # Test empty cache
        self.assertIsNone(cache.get(1))

        # Test put and get
        business = {"id": 1, "name": "Test Business"}
        cache.put(1, business)
        self.assertEqual(cache.get(1), business)

        # Test cache miss
        self.assertIsNone(cache.get(2))

    def test_cache_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = BusinessCache(max_size=2)

        # Fill cache
        cache.put(1, {"id": 1, "name": "Business 1"})
        cache.put(2, {"id": 2, "name": "Business 2"})

        # Access first item to make it more recently used
        cache.get(1)

        # Add third item, should evict item 2
        cache.put(3, {"id": 3, "name": "Business 3"})

        self.assertIsNotNone(cache.get(1))  # Should still be there
        self.assertIsNone(cache.get(2))      # Should be evicted
        self.assertIsNotNone(cache.get(3))  # Should be there

    def test_cache_thread_safety(self):
        """Test cache thread safety."""
        cache = BusinessCache(max_size=100)
        errors = []

        def worker(worker_id: int):
            try:
                for i in range(10):
                    business_id = worker_id * 10 + i
                    business = {"id": business_id, "name": f"Business {business_id}"}
                    cache.put(business_id, business)
                    retrieved = cache.get(business_id)
                    self.assertEqual(retrieved, business)
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0, f"Thread safety errors: {errors}")


class TestOptimizedDeduplicator:
    """Test optimized deduplication functionality."""

    @unittest.mock.patch("leadfactory.pipeline.dedupe_performance.DedupeConfig")
    def test_deduplicator_initialization(self, mock_config):
        """Test deduplicator initialization."""
        deduplicator = OptimizedDeduplicator(mock_config, max_workers=2)
        self.assertEqual(deduplicator.max_workers, 2)
        self.assertIsInstance(deduplicator.business_cache, BusinessCache)
        self.assertIsInstance(deduplicator.metrics, PerformanceMetrics)

    @patch("leadfactory.pipeline.dedupe_performance.db_connection")
    @patch("leadfactory.pipeline.dedupe_performance.db_cursor")
    def test_get_business_batch(self, mock_cursor, mock_connection):
        """Test batch business retrieval."""
        # Mock database response
        mock_conn = MagicMock()
        mock_connection.return_value.__enter__.return_value = mock_conn
        mock_cur = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cur

        # Mock query results
        mock_cur.fetchall.return_value = [
            {
                "id": 1, "name": "Business 1", "address": "123 Main St",
                "zip": "12345", "phone": "555-1234", "email": "test@example.com",
                "website": "https://example.com", "vertical": "retail",
                "source": "google", "google_response": None, "yelp_response": None,
                "manual_response": None, "created_at": None, "updated_at": None
            },
            {
                "id": 2, "name": "Business 2", "address": "456 Oak Ave",
                "zip": "12345", "phone": "555-5678", "email": "test2@example.com",
                "website": "https://example2.com", "vertical": "food",
                "source": "yelp", "google_response": None, "yelp_response": None,
                "manual_response": None, "created_at": None, "updated_at": None
            }
        ]

        # Test batch retrieval
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        businesses = deduplicator.get_business_batch([1, 2])

        self.assertEqual(len(businesses), 2)
        self.assertEqual(businesses[1]["name"], "Business 1")
        self.assertEqual(businesses[2]["name"], "Business 2")
        self.assertEqual(deduplicator.metrics.cache_misses, 2)

    def test_should_merge_exact_website_match(self):
        """Test merge decision for exact website match."""
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        business1 = {"id": 1, "website": "https://example.com", "name": "Test Business"}
        business2 = {"id": 2, "website": "https://example.com", "name": "Test Company"}

        self.assertTrue(deduplicator._should_merge(business1, business2))

    def test_should_merge_phone_match(self):
        """Test merge decision for phone match."""
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        business1 = {"id": 1, "phone": "555-1234", "name": "Test Business"}
        business2 = {"id": 2, "phone": "555-1234", "name": "Different Name"}

        self.assertTrue(deduplicator._should_merge(business1, business2))

    @patch("leadfactory.pipeline.dedupe_performance.ratio")
    def test_should_merge_name_similarity(self, mock_ratio):
        """Test merge decision for name similarity."""
        mock_ratio.return_value = 0.9  # High similarity

        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        business1 = {"id": 1, "name": "Test Business Inc"}
        business2 = {"id": 2, "name": "Test Business LLC"}

        self.assertTrue(deduplicator._should_merge(business1, business2))
        mock_ratio.assert_called_once()

    def test_select_primary_by_completeness(self):
        """Test primary selection based on data completeness."""
        # Business 1 has more complete data
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        business1 = {
            "id": 1, "name": "Complete Business", "address": "123 Main St",
            "phone": "555-1234", "email": "test@example.com", "website": "https://example.com"
        }
        business2 = {
            "id": 2, "name": "Incomplete Business", "phone": "555-5678"
        }

        primary_id, secondary_id = deduplicator._select_primary(business1, business2)
        self.assertEqual(primary_id, 1)
        self.assertEqual(secondary_id, 2)

    @patch("leadfactory.pipeline.dedupe_performance.merge_business_records")
    def test_merge_businesses_optimized(self, mock_merge):
        """Test optimized business merge."""
        mock_merge.return_value = {"id": 1, "merged": True}

        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        result = deduplicator._merge_businesses_optimized(1, 2)
        self.assertTrue(result)
        mock_merge.assert_called_once_with(1, 2)

    @patch("leadfactory.pipeline.dedupe_performance.merge_business_records")
    def test_merge_businesses_optimized_error(self, mock_merge):
        """Test optimized business merge with error."""
        mock_merge.side_effect = Exception("Database error")

        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        result = deduplicator._merge_businesses_optimized(1, 2)
        self.assertFalse(result)

    def test_performance_report_generation(self):
        """Test performance report generation."""
        # Set some metrics
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        deduplicator.metrics.total_pairs = 100
        deduplicator.metrics.processed_pairs = 95
        deduplicator.metrics.cache_hits = 80
        deduplicator.metrics.cache_misses = 20
        deduplicator.metrics.start_time = 1000.0
        deduplicator.metrics.end_time = 1010.0

        report = deduplicator.get_performance_report()

        self.assertIn("metrics", report)
        self.assertIn("recommendations", report)
        self.assertEqual(report["metrics"]["total_pairs"], 100)
        self.assertEqual(report["metrics"]["processed_pairs"], 95)
        self.assertEqual(report["metrics"]["cache_hit_rate"], 0.8)
        self.assertEqual(report["metrics"]["pairs_per_second"], 9.5)

    def test_recommendations_generation(self):
        """Test performance recommendations."""
        # Set low cache hit rate
        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        deduplicator.metrics.cache_hits = 10
        deduplicator.metrics.cache_misses = 90
        deduplicator.metrics.processed_pairs = 50
        deduplicator.metrics.start_time = 1000.0
        deduplicator.metrics.end_time = 1010.0  # 10 seconds for 50 pairs = 5 pairs/sec

        recommendations = deduplicator._generate_recommendations()

        self.assertTrue(any("cache size" in rec for rec in recommendations))
        self.assertTrue(any("batch size" in rec or "parallel workers" in rec for rec in recommendations))


class TestBatchProcessing:
    """Test batch processing functionality."""

    @unittest.mock.patch("leadfactory.pipeline.dedupe_performance.DedupeConfig")
    def test_process_single_batch(self, mock_config):
        """Test processing a single batch."""
        # Setup mocks
        mock_get_batch = unittest.mock.patch.object(OptimizedDeduplicator, "get_business_batch")
        mock_should_merge = unittest.mock.patch.object(OptimizedDeduplicator, "_should_merge")
        mock_merge = unittest.mock.patch.object(OptimizedDeduplicator, "_merge_businesses_optimized")

        mock_get_batch.return_value = {
            1: {"id": 1, "name": "Business 1"},
            2: {"id": 2, "name": "Business 2"},
            3: {"id": 3, "name": "Business 3"},
            4: {"id": 4, "name": "Business 4"}
        }
        mock_should_merge.side_effect = [True, False]  # First pair merges, second flags
        mock_merge.return_value = True

        # Test data
        batch = [
            {"business1_id": 1, "business2_id": 2},
            {"business1_id": 3, "business2_id": 4}
        ]

        deduplicator = OptimizedDeduplicator(mock_config, max_workers=2)
        stats = deduplicator._process_single_batch(batch)

        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["merged"], 1)
        self.assertEqual(stats["flagged"], 1)
        self.assertEqual(stats["errors"], 0)

    @patch.object(OptimizedDeduplicator, "_process_single_batch")
    def test_process_pairs_batch(self, mock_process_batch):
        """Test batch processing with multiple batches."""
        mock_process_batch.side_effect = [
            {"processed": 2, "merged": 1, "flagged": 1, "errors": 0},
            {"processed": 2, "merged": 0, "flagged": 2, "errors": 0},
            {"processed": 1, "merged": 1, "flagged": 0, "errors": 0}
        ]

        # Create 5 pairs, batch size 2 = 3 batches
        pairs = [{"business1_id": i, "business2_id": i+1} for i in range(1, 6)]

        deduplicator = OptimizedDeduplicator(MagicMock(), max_workers=2)
        stats = deduplicator.process_pairs_batch(pairs, batch_size=2)

        self.assertEqual(stats["processed"], 5)
        self.assertEqual(stats["merged"], 2)
        self.assertEqual(stats["flagged"], 3)
        self.assertEqual(stats["errors"], 0)
        self.assertEqual(mock_process_batch.call_count, 3)


class TestParallelProcessing:
    """Test parallel processing functionality."""

    @unittest.mock.patch("leadfactory.pipeline.dedupe_performance.DedupeConfig")
    def test_process_pairs_parallel(self, mock_config):
        """Test parallel processing."""
        mock_process_batch = unittest.mock.patch.object(OptimizedDeduplicator, "_process_single_batch")
        mock_process_batch.return_value = {"processed": 2, "merged": 1, "flagged": 1, "errors": 0}

        # Create pairs for parallel processing
        pairs = [{"business1_id": i, "business2_id": i+1} for i in range(1, 9)]  # 8 pairs

        deduplicator = OptimizedDeduplicator(mock_config, max_workers=2)
        stats = deduplicator.process_pairs_parallel(pairs)

        # Should process all pairs
        self.assertGreaterEqual(stats["processed"], 8)  # Might be more due to chunk processing
        self.assertGreaterEqual(stats["merged"], 4)
        self.assertGreaterEqual(stats["flagged"], 4)
        self.assertGreater(deduplicator.metrics.parallel_operations, 0)


class TestIntegration:
    """Integration tests for optimized deduplication."""

    @patch("leadfactory.pipeline.dedupe_performance.get_potential_duplicate_pairs")
    @patch("leadfactory.pipeline.dedupe_performance.load_dedupe_config")
    @patch.object(OptimizedDeduplicator, "optimize_database_indexes")
    @patch.object(OptimizedDeduplicator, "process_pairs_batch")
    def test_run_optimized_deduplication(self, mock_process, mock_optimize, mock_config, mock_get_pairs):
        """Test complete optimized deduplication run."""
        # Setup mocks
        mock_config.return_value = dedupe_performance.DedupeConfig()
        mock_get_pairs.return_value = [
            {"business1_id": 1, "business2_id": 2},
            {"business1_id": 3, "business2_id": 4}
        ]
        mock_optimize.return_value = True
        mock_process.return_value = {"processed": 2, "merged": 1, "flagged": 1, "errors": 0}

        result = run_optimized_deduplication(limit=10, use_parallel=False)

        self.assertIn("stats", result)
        self.assertIn("performance", result)
        self.assertEqual(result["stats"]["processed"], 2)
        self.assertEqual(result["stats"]["merged"], 1)
        self.assertEqual(result["stats"]["flagged"], 1)

        mock_optimize.assert_called_once()
        mock_get_pairs.assert_called_once_with(10)
        mock_process.assert_called_once()

    @patch("leadfactory.pipeline.dedupe_performance.get_potential_duplicate_pairs")
    @patch("leadfactory.pipeline.dedupe_performance.load_dedupe_config")
    @patch.object(OptimizedDeduplicator, "optimize_database_indexes")
    @patch.object(OptimizedDeduplicator, "process_pairs_parallel")
    def test_run_optimized_deduplication_parallel(self, mock_process, mock_optimize, mock_config, mock_get_pairs):
        """Test optimized deduplication with parallel processing."""
        # Setup mocks
        mock_config.return_value = dedupe_performance.DedupeConfig()
        mock_get_pairs.return_value = [{"business1_id": i, "business2_id": i+1} for i in range(1, 101)]  # 100 pairs
        mock_optimize.return_value = True
        mock_process.return_value = {"processed": 100, "merged": 50, "flagged": 50, "errors": 0}

        result = run_optimized_deduplication(use_parallel=True)

        self.assertIn("stats", result)
        self.assertIn("performance", result)
        self.assertEqual(result["stats"]["processed"], 100)

        mock_process.assert_called_once()  # Should use parallel processing for 100+ pairs


if __name__ == "__main__":
    unittest.main()
