"""Tests for score threshold filtering functionality."""

import pytest
from unittest.mock import MagicMock, patch

from leadfactory.pipeline.score import meets_audit_threshold
from leadfactory.pipeline.email_queue import get_businesses_for_email


class TestScoreThreshold:
    """Test score threshold functionality."""

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

    @patch('leadfactory.scoring.simplified_yaml_parser.SimplifiedYamlParser')
    def test_meets_audit_threshold_config_loading(self, mock_parser_class):
        """Test loading threshold from config."""
        # Mock the simplified yaml parser
        mock_parser = MagicMock()
        mock_config = MagicMock()
        mock_config.settings.audit_threshold = 75
        mock_parser.load_and_validate.return_value = mock_config
        mock_parser_class.return_value = mock_parser
        
        # Should use config threshold of 75
        assert meets_audit_threshold(75) is True
        assert meets_audit_threshold(74) is False

    @patch('leadfactory.pipeline.email_queue.storage')
    @patch('leadfactory.pipeline.score.meets_audit_threshold')
    def test_get_businesses_for_email_filtering(self, mock_meets_threshold, mock_storage):
        """Test that businesses are filtered by score threshold."""
        # Mock storage to return businesses with different scores
        mock_businesses = [
            {'id': 1, 'name': 'Business 1', 'score': 80},  # Above threshold
            {'id': 2, 'name': 'Business 2', 'score': 50},  # Below threshold
            {'id': 3, 'name': 'Business 3', 'score': 70},  # Above threshold
            {'id': 4, 'name': 'Business 4', 'score': 40},  # Below threshold
        ]
        mock_storage.get_businesses_for_email.return_value = mock_businesses
        
        # Mock meets_audit_threshold to use threshold of 60
        mock_meets_threshold.side_effect = lambda score: score >= 60
        
        # Get filtered businesses
        result = get_businesses_for_email()
        
        # Should only return businesses with score >= 60
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[0]['score'] == 80
        assert result[1]['id'] == 3
        assert result[1]['score'] == 70
        
        # Verify meets_audit_threshold was called for each business
        assert mock_meets_threshold.call_count == 4

    @patch('leadfactory.pipeline.email_queue.storage')
    @patch('leadfactory.pipeline.score.meets_audit_threshold')
    def test_get_businesses_for_email_no_score(self, mock_meets_threshold, mock_storage):
        """Test handling businesses without scores."""
        # Mock storage to return businesses without scores
        mock_businesses = [
            {'id': 1, 'name': 'Business 1'},  # No score
            {'id': 2, 'name': 'Business 2', 'score': None},  # None score
            {'id': 3, 'name': 'Business 3', 'score': 70},  # Valid score
        ]
        mock_storage.get_businesses_for_email.return_value = mock_businesses
        
        # Mock meets_audit_threshold to treat 0/None as not meeting threshold
        def check_threshold(score):
            return score >= 60
        mock_meets_threshold.side_effect = check_threshold
        
        # Get filtered businesses - default score is 0 which is below threshold
        result = get_businesses_for_email()
        
        # Only business with score 70 should be returned
        assert len(result) == 1
        assert result[0]['id'] == 3
        assert result[0]['score'] == 70


class TestScoreThresholdIntegration:
    """Integration tests for score threshold functionality."""

    @pytest.mark.integration
    @patch('leadfactory.storage.factory.get_storage')
    def test_score_threshold_with_real_storage(self, mock_get_storage):
        """Test score threshold with storage integration."""
        # Create a mock storage instance
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        
        # Mock the query to return businesses with scores from stage_results
        mock_businesses = [
            {
                'id': 1, 
                'name': 'High Score Business',
                'email': 'high@example.com',
                'score': 85
            },
            {
                'id': 2,
                'name': 'Low Score Business', 
                'email': 'low@example.com',
                'score': 45
            },
            {
                'id': 3,
                'name': 'Medium Score Business',
                'email': 'medium@example.com', 
                'score': 65
            }
        ]
        mock_storage.get_businesses_for_email.return_value = mock_businesses
        
        # Import after mocking storage
        from leadfactory.pipeline.email_queue import get_businesses_for_email
        
        # Get businesses for email
        result = get_businesses_for_email()
        
        # Should filter out business with score 45 (below default threshold of 60)
        assert len(result) == 2
        assert all(b['score'] >= 60 for b in result)
        assert 45 not in [b['score'] for b in result]

    @pytest.mark.integration
    def test_score_threshold_in_pipeline(self):
        """Test that score threshold is applied during pipeline execution."""
        # This would be a full pipeline test
        # For now, we just verify the components exist
        from leadfactory.pipeline.score import meets_audit_threshold
        from leadfactory.pipeline.email_queue import get_businesses_for_email
        
        # Verify functions exist and are callable
        assert callable(meets_audit_threshold)
        assert callable(get_businesses_for_email)