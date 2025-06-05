"""Integration tests for score threshold filtering in the pipeline."""

import pytest
from unittest.mock import MagicMock, patch, call
import json

from leadfactory.pipeline.score import score_business, meets_audit_threshold
from leadfactory.pipeline.email_queue import get_businesses_for_email, process_business_email
from leadfactory.storage.postgres_storage import PostgresStorage


class TestScoreThresholdIntegration:
    """Test score threshold filtering across the pipeline."""

    @pytest.mark.integration
    def test_score_threshold_end_to_end(self):
        """Test complete flow from scoring to email filtering."""
        # Create test businesses with different characteristics
        test_businesses = [
            {
                'id': 1,
                'name': 'Outdated Business',
                'website': 'http://outdated.com',
                'performance_score': 40,
                'technology': 'jQuery 1.x',
                'expected_score': 85  # High score due to outdated tech
            },
            {
                'id': 2,
                'name': 'Modern Business',
                'website': 'http://modern.com',
                'performance_score': 90,
                'technology': 'React',
                'expected_score': 35  # Low score due to modern tech
            },
            {
                'id': 3,
                'name': 'Medium Business',
                'website': 'http://medium.com',
                'performance_score': 65,
                'technology': 'WordPress',
                'expected_score': 65  # Medium score
            }
        ]
        
        # Mock storage
        with patch('leadfactory.storage.factory.get_storage') as mock_get_storage:
            mock_storage = MagicMock(spec=PostgresStorage)
            mock_get_storage.return_value = mock_storage
            
            # Test scoring each business
            for business in test_businesses:
                # Mock the scoring engine to return expected scores
                with patch('leadfactory.pipeline.score.RuleEngine') as mock_engine_class:
                    mock_engine = MagicMock()
                    mock_engine.evaluate.return_value = business['expected_score']
                    mock_engine_class.return_value = mock_engine
                    
                    # Score the business
                    score = score_business(business)
                    assert score == business['expected_score']
                    
                    # Save the score to stage_results
                    mock_storage.save_stage_results.assert_called_with(
                        business_id=business['id'],
                        stage='score',
                        results={'score': business['expected_score']}
                    )
            
            # Now test email filtering
            # Mock get_businesses_for_email to return scored businesses
            mock_storage.get_businesses_for_email.return_value = [
                {
                    'id': 1,
                    'name': 'Outdated Business',
                    'email': 'outdated@example.com',
                    'score': 85  # Above threshold
                },
                {
                    'id': 2,
                    'name': 'Modern Business',
                    'email': 'modern@example.com',
                    'score': 35  # Below threshold
                },
                {
                    'id': 3,
                    'name': 'Medium Business',
                    'email': 'medium@example.com',
                    'score': 65  # Above threshold
                }
            ]
            
            # Get businesses for email (should filter by score)
            eligible_businesses = get_businesses_for_email()
            
            # Only businesses with score >= 60 should be returned
            assert len(eligible_businesses) == 2
            assert eligible_businesses[0]['id'] == 1
            assert eligible_businesses[0]['score'] == 85
            assert eligible_businesses[1]['id'] == 3
            assert eligible_businesses[1]['score'] == 65
            
            # Business 2 with score 35 should be filtered out
            business_ids = [b['id'] for b in eligible_businesses]
            assert 2 not in business_ids

    @pytest.mark.integration
    def test_score_threshold_with_custom_threshold(self):
        """Test score threshold with custom configuration."""
        # Mock the scoring engine config
        with patch('leadfactory.scoring.ScoringEngine') as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine.config = {'settings': {'audit_threshold': 70}}
            mock_engine_class.return_value = mock_engine
            mock_engine.load_rules.return_value = None
            
            # Test with custom threshold of 70
            assert meets_audit_threshold(69) is False
            assert meets_audit_threshold(70) is True
            assert meets_audit_threshold(71) is True

    @pytest.mark.integration 
    def test_email_sending_respects_score_threshold(self):
        """Test that email sending skips low-score businesses."""
        with patch('leadfactory.storage.factory.get_storage') as mock_get_storage:
            mock_storage = MagicMock(spec=PostgresStorage)
            mock_get_storage.return_value = mock_storage
            
            # Mock a business with low score
            low_score_business = {
                'id': 1,
                'name': 'Low Score Business',
                'email': 'low@example.com',
                'score': 45  # Below threshold
            }
            
            mock_storage.get_businesses_for_email.return_value = [low_score_business]
            
            # Mock other dependencies
            with patch('leadfactory.pipeline.email_queue.load_email_template') as mock_template:
                mock_template.return_value = '<html>Test template</html>'
                
                with patch('leadfactory.pipeline.email_queue.SendGridEmailSender') as mock_sender_class:
                    mock_sender = MagicMock()
                    mock_sender_class.return_value = mock_sender
                    
                    # Process the business (should be skipped due to low score)
                    result = process_business_email(business_id=1)
                    
                    # Should return False because business was filtered out
                    assert result is False
                    
                    # Email should not have been sent
                    mock_sender.send_email.assert_not_called()

    @pytest.mark.integration
    def test_score_threshold_logging(self):
        """Test that score threshold filtering is properly logged."""
        with patch('leadfactory.storage.factory.get_storage') as mock_get_storage:
            mock_storage = MagicMock(spec=PostgresStorage)
            mock_get_storage.return_value = mock_storage
            
            # Mock businesses with various scores
            mock_storage.get_businesses_for_email.return_value = [
                {'id': 1, 'name': 'High Score', 'score': 90},
                {'id': 2, 'name': 'Low Score', 'score': 40},
                {'id': 3, 'name': 'Border Score', 'score': 60},
            ]
            
            with patch('leadfactory.pipeline.email_queue.logger') as mock_logger:
                # Get businesses for email
                result = get_businesses_for_email()
                
                # Check that skipped business was logged
                skip_calls = [call for call in mock_logger.info.call_args_list 
                             if 'Skipping business' in str(call)]
                assert len(skip_calls) == 1
                assert 'Low Score' in str(skip_calls[0])
                assert 'score 40 below audit threshold' in str(skip_calls[0])

    @pytest.mark.integration
    def test_score_threshold_database_migration(self):
        """Test that score data is properly stored and retrieved from database."""
        with patch('leadfactory.utils.e2e_db_connector.db_cursor') as mock_cursor_context:
            mock_cursor = MagicMock()
            mock_cursor_context.return_value.__enter__.return_value = mock_cursor
            
            storage = PostgresStorage()
            
            # Save score results
            score_data = {
                'score': 75,
                'breakdown': {
                    'technology': 30,
                    'performance': 25,
                    'seo': 20
                },
                'timestamp': '2024-01-01T00:00:00Z'
            }
            
            # Mock successful insert
            mock_cursor.rowcount = 1
            
            success = storage.save_stage_results(
                business_id=123,
                stage='score',
                results=score_data
            )
            
            assert success is True
            
            # Verify the query includes proper JSON handling
            query = mock_cursor.execute.call_args[0][0]
            assert 'stage_results' in query
            assert 'ON CONFLICT' in query
            
            # Test retrieval
            mock_cursor.fetchone.return_value = (json.dumps(score_data),)
            
            retrieved = storage.get_stage_results(business_id=123, stage='score')
            assert retrieved == score_data
            assert retrieved['score'] == 75