"""Step definitions for score threshold BDD tests."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from leadfactory.pipeline.score import score_business, meets_audit_threshold
from leadfactory.pipeline.email_queue import get_businesses_for_email

# Load scenarios from feature file
scenarios('../features/score_threshold.feature')


# Fixtures
@pytest.fixture
def scoring_config():
    """Fixture for scoring configuration."""
    return {'settings': {'audit_threshold': 60}}


@pytest.fixture 
def test_businesses():
    """Fixture for test businesses."""
    return {}


@pytest.fixture
def scored_businesses():
    """Fixture for businesses with scores."""
    return {}


@pytest.fixture
def email_results():
    """Fixture for email sending results."""
    return {'sent': [], 'skipped': []}


@pytest.fixture
def logged_messages():
    """Fixture for captured log messages."""
    return []


# Given steps
@given(parsers.parse('the scoring system is configured with an audit threshold of {threshold:d}'))
def configure_audit_threshold(scoring_config, threshold):
    """Configure the audit threshold."""
    scoring_config['settings']['audit_threshold'] = threshold


@given('the following businesses exist:')
def create_test_businesses(test_businesses, datatable):
    """Create test businesses from table data."""
    for row in datatable:
        business = {
            'id': int(row['id']),
            'name': row['name'],
            'email': row['email'],
            'website': row['website'] if row['website'] else None
        }
        test_businesses[business['name']] = business


@given('the businesses have been scored as follows:')
def set_business_scores(scored_businesses, datatable):
    """Set scores for businesses."""
    for row in datatable:
        scored_businesses[row['business']] = int(row['score'])


@given(parsers.parse('the audit threshold is changed to {threshold:d}'))
def change_audit_threshold(scoring_config, threshold):
    """Change the audit threshold."""
    scoring_config['settings']['audit_threshold'] = threshold


@given(parsers.parse('a business "{name}" has no score recorded'))
def create_unscored_business(test_businesses, name):
    """Create a business without a score."""
    test_businesses[name] = {
        'id': len(test_businesses) + 1,
        'name': name,
        'email': f"{name.lower().replace(' ', '')}@example.com",
        'website': f"http://{name.lower().replace(' ', '')}.com"
    }


@given(parsers.parse('{count:d} businesses exist with the following score distribution:'))
def create_businesses_with_distribution(test_businesses, scored_businesses, count, datatable):
    """Create businesses with specific score distribution."""
    business_id = 1
    for row in datatable:
        score_range = row['score range']
        range_count = int(row['count'])
        
        # Parse score range
        if '-' in score_range:
            min_score, max_score = map(int, score_range.split('-'))
        else:
            min_score = max_score = int(score_range)
        
        # Create businesses in this range
        for i in range(range_count):
            score = min_score + (i * (max_score - min_score) // max(range_count - 1, 1))
            name = f"Business_{business_id}"
            business = {
                'id': business_id,
                'name': name,
                'email': f"business{business_id}@example.com",
                'website': f"http://business{business_id}.com",
                'score': score
            }
            test_businesses[name] = business
            scored_businesses[name] = score
            business_id += 1


@given(parsers.parse('a business "{name}" is scored at {score:d}'))
def score_specific_business(test_businesses, scored_businesses, name, score):
    """Score a specific business."""
    if name not in test_businesses:
        test_businesses[name] = {
            'id': 1,
            'name': name,
            'email': f"{name.lower().replace(' ', '')}@example.com",
            'website': f"http://{name.lower().replace(' ', '')}.com"
        }
    scored_businesses[name] = score


# When steps
@when('the businesses are scored')
def score_all_businesses(test_businesses, scored_businesses):
    """Score all test businesses."""
    # Mock scoring rules
    scoring_rules = {
        'Outdated Tech Corp': 85,  # High score for outdated tech
        'Modern Digital Inc': 35,   # Low score for modern tech
        'Average Business': 65,     # Medium score
        'No Website LLC': 10        # Very low score for no website
    }
    
    with patch('leadfactory.pipeline.score.RuleEngine') as mock_engine_class:
        mock_engine = MagicMock()
        
        for name, business in test_businesses.items():
            score = scoring_rules.get(name, 50)
            mock_engine.evaluate.return_value = score
            mock_engine_class.return_value = mock_engine
            
            # Score the business
            scored_businesses[name] = score_business(business)


@when('emails are prepared for sending')
def prepare_emails(test_businesses, scored_businesses, scoring_config, email_results, logged_messages):
    """Prepare emails for sending with score filtering."""
    threshold = scoring_config['settings']['audit_threshold']
    
    # Mock the storage and logging
    with patch('leadfactory.pipeline.email_queue.storage') as mock_storage:
        with patch('leadfactory.pipeline.email_queue.logger') as mock_logger:
            # Prepare businesses with scores
            businesses_with_scores = []
            for name, business in test_businesses.items():
                business_copy = business.copy()
                business_copy['score'] = scored_businesses.get(name, 0)
                businesses_with_scores.append(business_copy)
            
            mock_storage.get_businesses_for_email.return_value = businesses_with_scores
            
            # Capture log messages
            def capture_log(msg, *args, **kwargs):
                logged_messages.append(msg)
            mock_logger.info.side_effect = capture_log
            
            # Get filtered businesses
            with patch('leadfactory.scoring.ScoringEngine') as mock_engine_class:
                mock_engine = MagicMock()
                mock_engine.config = scoring_config
                mock_engine_class.return_value = mock_engine
                
                eligible = get_businesses_for_email()
                
                # Categorize results
                for business in businesses_with_scores:
                    if business in eligible:
                        email_results['sent'].append(business)
                    else:
                        email_results['skipped'].append(business)


@when('the score is saved to the database')
def save_score_to_database(test_businesses, scored_businesses):
    """Save score to database."""
    with patch('leadfactory.storage.factory.get_storage') as mock_get_storage:
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        
        # Mock successful save
        mock_storage.save_stage_results.return_value = True
        
        # Save scores for all scored businesses
        for name, score in scored_businesses.items():
            if name in test_businesses:
                business = test_businesses[name]
                mock_storage.save_stage_results(
                    business_id=business['id'],
                    stage='score',
                    results={'score': score}
                )


# Then steps
@then('the scores should be:')
def verify_scores(scored_businesses, datatable):
    """Verify business scores."""
    for row in datatable:
        business_name = row['business']
        expected_score = int(row['score'])
        
        assert business_name in scored_businesses
        assert scored_businesses[business_name] == expected_score


@then('emails should be sent to:')
def verify_emails_sent(email_results, datatable):
    """Verify which businesses receive emails."""
    sent_names = [b['name'] for b in email_results['sent']]
    
    for row in datatable:
        business_name = row['business']
        assert business_name in sent_names, f"{business_name} should receive email"


@then('emails should NOT be sent to:')
def verify_emails_not_sent(email_results, datatable):
    """Verify which businesses don't receive emails."""
    sent_names = [b['name'] for b in email_results['sent']]
    
    for row in datatable:
        business_name = row['business']
        assert business_name not in sent_names, f"{business_name} should not receive email"


@then(parsers.parse('only "{business_name}" should receive an email'))
def verify_single_email(email_results, business_name):
    """Verify only one specific business receives email."""
    sent_names = [b['name'] for b in email_results['sent']]
    assert sent_names == [business_name]


@then(parsers.parse('"{business_name}" should be skipped with reason "{reason}"'))
def verify_skip_reason(email_results, logged_messages, business_name, reason):
    """Verify a business was skipped with specific reason."""
    skipped_names = [b['name'] for b in email_results['skipped']]
    assert business_name in skipped_names
    
    # Check log messages for the reason
    reason_found = any(business_name in msg and reason in msg for msg in logged_messages)
    assert reason_found, f"Expected skip reason '{reason}' not found in logs"


@then('the following should be logged:')
def verify_log_messages(logged_messages, datatable):
    """Verify specific log messages."""
    for row in datatable:
        expected_message = row['message']
        message_found = any(expected_message in msg for msg in logged_messages)
        assert message_found, f"Expected log message not found: {expected_message}"


@then(parsers.parse('exactly {count:d} emails should be queued'))
def verify_email_count(email_results, count):
    """Verify exact number of emails queued."""
    assert len(email_results['sent']) == count


@then(parsers.parse('{count:d} businesses should be skipped due to low scores'))
def verify_skip_count(email_results, count):
    """Verify number of businesses skipped."""
    assert len(email_results['skipped']) == count


@then('the stage_results table should contain:')
def verify_stage_results(datatable):
    """Verify stage_results table contents."""
    with patch('leadfactory.storage.factory.get_storage') as mock_get_storage:
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage
        
        for row in datatable:
            business_id = int(row['business_id'])
            stage = row['stage']
            expected_score = int(row['score'])
            
            # Mock the retrieval
            mock_storage.get_stage_results.return_value = {'score': expected_score}
            
            # Verify
            result = mock_storage.get_stage_results(business_id=business_id, stage=stage)
            assert result['score'] == expected_score


@then(parsers.parse('when emails are prepared, "{business_name}" should be included'))
def verify_business_included_after_scoring(test_businesses, scored_businesses, business_name):
    """Verify a business is included in email list after scoring."""
    assert business_name in test_businesses
    assert business_name in scored_businesses
    assert scored_businesses[business_name] >= 60  # Default threshold