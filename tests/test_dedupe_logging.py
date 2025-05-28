"""
Tests for the enhanced deduplication logging system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import os
from datetime import datetime

from leadfactory.pipeline.dedupe_logging import (
    DedupeLogger, dedupe_operation, log_dedupe_performance,
    DedupeLogAnalyzer
)


class TestDedupeLogger(unittest.TestCase):
    """Test cases for DedupeLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = DedupeLogger("test_dedupe")

    def test_log_merge(self):
        """Test logging merge operations."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_merge(
                primary_id=1,
                secondary_id=2,
                confidence=0.95,
                strategy="name_match"
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            self.assertEqual(call_args[0][0], "Business merge completed")

            extra = call_args[1]['extra']
            self.assertEqual(extra['event_type'], 'business_merge')
            self.assertEqual(extra['primary_id'], 1)
            self.assertEqual(extra['secondary_id'], 2)
            self.assertEqual(extra['confidence'], 0.95)

    def test_log_conflict(self):
        """Test logging field conflicts."""
        with patch.object(self.logger.logger, 'warning') as mock_warning:
            self.logger.log_conflict(
                field="email",
                primary_value="test1@example.com",
                secondary_value="test2@example.com",
                resolved_value="test1@example.com",
                resolution_strategy="keep_primary"
            )

            mock_warning.assert_called_once()
            extra = mock_warning.call_args[1]['extra']
            self.assertEqual(extra['event_type'], 'field_conflict')
            self.assertEqual(extra['field'], 'email')

    def test_log_duplicate_found(self):
        """Test logging duplicate detection."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_duplicate_found(
                business1_id=1,
                business2_id=2,
                similarity_score=0.87,
                match_type="fuzzy_match",
                reason="High name similarity"
            )

            mock_info.assert_called_once()
            extra = mock_info.call_args[1]['extra']
            self.assertEqual(extra['event_type'], 'duplicate_found')
            self.assertEqual(extra['similarity_score'], 0.87)

    def test_start_end_operation(self):
        """Test operation tracking."""
        # Start operation
        op_id = self.logger.start_operation("test_op", test_param="value")
        self.assertIsNotNone(op_id)
        self.assertIn(op_id, self.logger.operations)

        # End operation
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.end_operation(op_id, status="success", result_count=10)

            mock_info.assert_called_once()
            extra = mock_info.call_args[1]['extra']
            self.assertEqual(extra['operation_id'], op_id)
            self.assertEqual(extra['status'], 'success')
            self.assertIn('duration_seconds', extra)

    def test_log_batch_progress(self):
        """Test batch progress logging."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_batch_progress(
                batch_id="batch_123",
                processed=50,
                total=100,
                errors=2,
                merged=30,
                flagged=5
            )

            mock_info.assert_called_once()
            extra = mock_info.call_args[1]['extra']
            self.assertEqual(extra['event_type'], 'batch_progress')
            self.assertEqual(extra['progress_percentage'], 50.0)

    def test_log_performance_metrics(self):
        """Test performance metrics logging."""
        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_performance_metrics(
                operation_type="full_dedupe",
                duration_seconds=120.5,
                records_processed=1000,
                memory_usage_mb=256.7
            )

            mock_info.assert_called_once()
            extra = mock_info.call_args[1]['extra']
            self.assertEqual(extra['event_type'], 'performance_metrics')
            self.assertEqual(extra['records_per_second'], 1000 / 120.5)


class TestDedupeOperation(unittest.TestCase):
    """Test cases for dedupe_operation context manager."""

    def test_successful_operation(self):
        """Test successful operation tracking."""
        logger = DedupeLogger("test")

        with patch.object(logger, 'start_operation') as mock_start:
            with patch.object(logger, 'end_operation') as mock_end:
                mock_start.return_value = "op_123"

                with dedupe_operation(logger, "test_op", param1="value1") as op_id:
                    self.assertEqual(op_id, "op_123")

                mock_start.assert_called_once_with("test_op", param1="value1")
                mock_end.assert_called_once_with("op_123", status="success")

    def test_failed_operation(self):
        """Test operation tracking with exception."""
        logger = DedupeLogger("test")

        with patch.object(logger, 'start_operation') as mock_start:
            with patch.object(logger, 'end_operation') as mock_end:
                mock_start.return_value = "op_123"

                try:
                    with dedupe_operation(logger, "test_op") as op_id:
                        raise ValueError("Test error")
                except ValueError:
                    pass

                mock_end.assert_called_once_with(
                    "op_123",
                    status="error",
                    error="Test error"
                )


class TestLogDedupePerformance(unittest.TestCase):
    """Test cases for performance decorator."""

    def test_performance_decorator(self):
        """Test performance logging decorator."""
        logger = DedupeLogger("test")

        @log_dedupe_performance(logger)
        def test_function(x, y):
            return x + y

        with patch.object(logger, 'log_performance_metrics') as mock_log:
            result = test_function(1, 2)

            self.assertEqual(result, 3)
            mock_log.assert_called_once()

            call_args = mock_log.call_args[1]
            self.assertEqual(call_args['operation_type'], 'test_function')
            self.assertIn('duration_seconds', call_args)


class TestDedupeLogAnalyzer(unittest.TestCase):
    """Test cases for log analyzer."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = DedupeLogAnalyzer()

        # Sample logs
        self.sample_logs = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "event_type": "business_merge",
                "primary_id": 1,
                "secondary_id": 2,
                "confidence": 0.95,
                "status": "success"
            },
            {
                "timestamp": "2024-01-01T10:01:00Z",
                "event_type": "business_merge",
                "primary_id": 3,
                "secondary_id": 4,
                "confidence": 0.87,
                "status": "success"
            },
            {
                "timestamp": "2024-01-01T10:02:00Z",
                "event_type": "business_merge",
                "primary_id": 5,
                "secondary_id": 6,
                "confidence": 0.92,
                "status": "failure"
            }
        ]

        self.analyzer.logs = self.sample_logs

    def test_analyze_merge_patterns(self):
        """Test merge pattern analysis."""
        result = self.analyzer.analyze_merge_patterns()

        self.assertEqual(result['total_merges'], 3)
        self.assertEqual(result['successful_merges'], 2)
        self.assertEqual(result['failed_merges'], 1)
        self.assertAlmostEqual(result['success_rate'], 66.67, places=2)
        self.assertAlmostEqual(result['average_confidence'], 0.91, places=2)

    def test_get_operation_summary(self):
        """Test operation summary generation."""
        # Add operation logs
        self.analyzer.logs.extend([
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "operation_id": "op1",
                "operation_type": "find_duplicates",
                "duration_seconds": 5.2,
                "status": "success"
            },
            {
                "timestamp": "2024-01-01T10:01:00Z",
                "operation_id": "op2",
                "operation_type": "merge_businesses",
                "duration_seconds": 2.1,
                "status": "success"
            }
        ])

        result = self.analyzer.get_operation_summary()

        self.assertIn('find_duplicates', result)
        self.assertIn('merge_businesses', result)
        self.assertEqual(result['find_duplicates']['count'], 1)
        self.assertEqual(result['merge_businesses']['avg_duration'], 2.1)

    def test_empty_logs(self):
        """Test analyzer with no logs."""
        self.analyzer.logs = []

        merge_result = self.analyzer.analyze_merge_patterns()
        self.assertEqual(merge_result['message'], "No merge logs found")

        op_result = self.analyzer.get_operation_summary()
        self.assertEqual(op_result['message'], "No operation logs found")


class TestLogAnalysisIntegration(unittest.TestCase):
    """Integration tests for log analysis."""

    def test_log_and_analyze(self):
        """Test logging and analyzing in sequence."""
        # Create temporary log file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_file = f.name

        try:
            # Configure logger to write to file
            logger = DedupeLogger("test", log_file=log_file)

            # Log some operations
            logger.log_merge(1, 2, 0.95, "exact_match")
            logger.log_merge(3, 4, 0.87, "fuzzy_match")
            logger.log_conflict("email", "a@test.com", "b@test.com", "a@test.com", "keep_primary")

            op_id = logger.start_operation("test_op")
            logger.end_operation(op_id, status="success")

            # Close logger to flush
            if hasattr(logger.logger, 'handlers'):
                for handler in logger.logger.handlers:
                    handler.flush()
                    handler.close()

            # Analyze logs
            analyzer = DedupeLogAnalyzer(log_file)

            # Verify analysis
            merge_patterns = analyzer.analyze_merge_patterns()
            self.assertEqual(merge_patterns['total_merges'], 2)

        finally:
            # Clean up
            if os.path.exists(log_file):
                os.unlink(log_file)


if __name__ == '__main__':
    unittest.main()
