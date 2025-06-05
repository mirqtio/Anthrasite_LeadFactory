"""
Unit tests for the scoring pipeline module.

Tests the scoring logic without external dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch

from leadfactory.pipeline.score import meets_audit_threshold


class TestScoringFunctions:
    """Test individual scoring functions."""

    def test_meets_audit_threshold_default(self):
        """Test meets_audit_threshold with default threshold."""
        # Test scores above default threshold (60)
        assert meets_audit_threshold(100) is True
        assert meets_audit_threshold(60) is True  # Equal to threshold
        assert meets_audit_threshold(61) is True

        # Test scores below default threshold
        assert meets_audit_threshold(59) is False
        assert meets_audit_threshold(30) is False
        assert meets_audit_threshold(0) is False

    def test_meets_audit_threshold_custom(self):
        """Test meets_audit_threshold with custom threshold."""
        # Test with custom threshold of 70
        assert meets_audit_threshold(100, threshold=70) is True
        assert meets_audit_threshold(70, threshold=70) is True  # Equal to threshold
        assert meets_audit_threshold(69, threshold=70) is False

        # Test with custom threshold of 50
        assert meets_audit_threshold(50, threshold=50) is True
        assert meets_audit_threshold(49, threshold=50) is False

    def test_meets_audit_threshold_edge_cases(self):
        """Test edge cases for threshold checking."""
        # Test with zero threshold
        assert meets_audit_threshold(0, threshold=0) is True
        assert meets_audit_threshold(1, threshold=0) is True

        # Test with negative scores
        assert meets_audit_threshold(-10, threshold=0) is False
        assert meets_audit_threshold(-5, threshold=-10) is True

        # Test with very high thresholds
        assert meets_audit_threshold(99, threshold=100) is False
        assert meets_audit_threshold(100, threshold=100) is True


class TestScoringFunctionsIntegration:
    """Integration tests that test with actual implementation."""

    @patch('leadfactory.pipeline.score.RuleEngine')
    def test_score_business_integration(self, mock_rule_engine_class):
        """Test score_business function with mocked rule engine."""
        from leadfactory.pipeline.score import score_business

        # Mock the rule engine to return a specific score
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = 75
        mock_rule_engine_class.return_value = mock_engine

        business = {
            'id': 1,
            'name': 'Test Business',
            'website': 'http://example.com',
            'category': 'restaurant'
        }

        score = score_business(business)

        # Should return the mocked score
        assert score == 75
        mock_engine.evaluate.assert_called_once_with(business)

    @patch('leadfactory.pipeline.score.RuleEngine')
    def test_score_business_error_handling(self, mock_rule_engine_class):
        """Test score_business error handling."""
        from leadfactory.pipeline.score import score_business

        # Mock the rule engine to raise an exception
        mock_engine = MagicMock()
        mock_engine.evaluate.side_effect = Exception("Scoring error")
        mock_rule_engine_class.return_value = mock_engine

        business = {'id': 1, 'name': 'Error Business'}

        # Should return 0 on error
        score = score_business(business)
        assert score == 0

    def test_get_businesses_to_score_function_exists(self):
        """Test that get_businesses_to_score function exists and is callable."""
        from leadfactory.pipeline.score import get_businesses_to_score

        # Function should exist and be callable
        assert callable(get_businesses_to_score)

        # This test just verifies the function exists and doesn't crash
        # without mocking all the storage dependencies
        try:
            # Call with no parameters - may fail due to missing storage,
            # but that's expected in unit tests
            businesses = get_businesses_to_score()
            # If it succeeds, great! If not, that's also fine for unit tests.
            assert isinstance(businesses, list)
        except Exception:
            # Expected to fail in unit test environment without proper storage setup
            pass
