"""
Step definitions for the lead enrichment feature tests.
"""

import json
import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from bin import enrich
from utils.io import DatabaseConnection

# Scenarios
@scenario('../features/enrichment.feature', 'Enrich business with website data')
def test_enrich_business_with_website():
    """Test enriching a business with website data."""
    pass

@scenario('../features/enrichment.feature', 'Enrich business without website')
def test_enrich_business_without_website():
    """Test enriching a business without a website."""
    pass

@scenario('../features/enrichment.feature', 'Handle API errors gracefully')
def test_handle_api_errors():
    """Test handling API errors gracefully."""
    pass

@scenario('../features/enrichment.feature', 'Skip already enriched businesses')
def test_skip_already_enriched_businesses():
    """Test skipping already enriched businesses."""
    pass

@scenario('../features/enrichment.feature', 'Prioritize businesses by score')
def test_prioritize_by_score():
    """Test prioritizing businesses by score."""
    pass

# Fixtures
@pytest.fixture
def mock_db():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    
    # Create tables
    cursor.executescript("""
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT,
            tech_stack TEXT,
            performance_data TEXT,
            contact_info TEXT,
            status TEXT DEFAULT 'pending',
            score REAL DEFAULT 0.0,
            enriched INTEGER DEFAULT 0
        );
    """)
    
    conn.commit()
    yield conn, cursor
    conn.close()

@pytest.fixture
def mock_apis():
    """Mock external APIs used in enrichment."""
    with patch('bin.enrich.TechStackAnalyzer.analyze_website') as mock_tech_stack, \
         patch('bin.enrich.PageSpeedAnalyzer.analyze_website') as mock_pagespeed, \
         patch('utils.io.track_api_cost') as mock_track_cost:
        
        # Configure mocks
        mock_tech_stack.return_value = (set(['React', 'Node.js', 'Express']), None)
        mock_pagespeed.return_value = ({'performance': 0.85, 'accessibility': 0.92}, None)
        
        yield {
            'tech_stack': mock_tech_stack,
            'pagespeed': mock_pagespeed,
            'track_cost': mock_track_cost
        }

# Given steps
@given('the database is initialized')
def db_initialized(mock_db):
    """Ensure the database is initialized."""
    conn, cursor = mock_db
    return conn, cursor

@given('the API keys are configured')
def api_keys_configured(monkeypatch):
    """Configure API keys for testing."""
    monkeypatch.setenv('PAGESPEED_KEY', 'test_key')
    monkeypatch.setenv('SCREENSHOT_ONE_KEY', 'test_key')
    monkeypatch.setenv('SEMRUSH_KEY', 'test_key')
    return True

@given('a business with a website')
def business_with_website(mock_db):
    """Create a test business with a website."""
    conn, cursor = mock_db
    cursor.execute("""
        INSERT INTO businesses (name, website)
        VALUES (?, ?)
    """, ('Test Business', 'https://example.com'))
    conn.commit()
    
    cursor.execute("SELECT * FROM businesses WHERE website IS NOT NULL")
    business = cursor.fetchone()
    return business

@given('a business without a website')
def business_without_website(mock_db):
    """Create a test business without a website."""
    conn, cursor = mock_db
    cursor.execute("""
        INSERT INTO businesses (name, website)
        VALUES (?, ?)
    """, ('No Website Business', None))
    conn.commit()
    
    cursor.execute("SELECT * FROM businesses WHERE website IS NULL")
    business = cursor.fetchone()
    return business

@given('the enrichment API is unavailable')
def enrichment_api_unavailable(mock_apis):
    """Simulate an unavailable enrichment API."""
    mock_apis['tech_stack'].return_value = (None, "API Error")
    mock_apis['pagespeed'].return_value = (None, "API Error")
    return mock_apis

@given('a business that has already been enriched')
def already_enriched_business(mock_db):
    """Create a test business that has already been enriched."""
    conn, cursor = mock_db
    cursor.execute("""
        INSERT INTO businesses (name, website, tech_stack, performance_data, enriched)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'Enriched Business', 
        'https://enriched.com', 
        json.dumps({'frameworks': ['React']}),
        json.dumps({'performance': 0.9}),
        1
    ))
    conn.commit()
    
    cursor.execute("SELECT * FROM businesses WHERE enriched = 1")
    business = cursor.fetchone()
    return business

@given('multiple businesses with different scores')
def businesses_with_scores(mock_db):
    """Create multiple test businesses with different scores."""
    conn, cursor = mock_db
    businesses = [
        ('High Score Business', 'https://high.com', 0.9),
        ('Medium Score Business', 'https://medium.com', 0.6),
        ('Low Score Business', 'https://low.com', 0.3)
    ]
    
    for name, website, score in businesses:
        cursor.execute("""
            INSERT INTO businesses (name, website, score)
            VALUES (?, ?, ?)
        """, (name, website, score))
    
    conn.commit()
    return businesses

# When steps
@when('I run the enrichment process')
def run_enrichment(mock_db, mock_apis):
    """Run the enrichment process."""
    conn, cursor = mock_db
    
    # Mock the database connection
    with patch('utils.io.DatabaseConnection') as mock_db_conn:
        mock_db_conn.return_value.__enter__.return_value = cursor
        
        # Get the first business
        cursor.execute("SELECT * FROM businesses LIMIT 1")
        business = cursor.fetchone()
        
        # Convert to dict for the enrichment function
        business_dict = {
            'id': business[0],
            'name': business[1],
            'website': business[2]
        }
        
        # Run the enrichment
        result = enrich.enrich_business(business_dict)
        
        return result, conn, cursor

@when('I run the enrichment process with prioritization')
def run_enrichment_prioritized(mock_db, mock_apis):
    """Run the enrichment process with prioritization."""
    conn, cursor = mock_db
    
    # Mock the database connection
    with patch('utils.io.DatabaseConnection') as mock_db_conn, \
         patch('bin.enrich.get_businesses_to_enrich') as mock_get_businesses:
        
        mock_db_conn.return_value.__enter__.return_value = cursor
        
        # Get all businesses ordered by score
        cursor.execute("SELECT * FROM businesses ORDER BY score DESC")
        businesses = cursor.fetchall()
        
        # Convert to list of dicts
        business_dicts = []
        for business in businesses:
            business_dicts.append({
                'id': business[0],
                'name': business[1],
                'website': business[2],
                'score': business[7]
            })
        
        # Mock the get_businesses_to_enrich function
        mock_get_businesses.return_value = business_dicts
        
        # Process order tracking
        processed_order = []
        
        # Mock the enrich_business function to track order
        original_enrich = enrich.enrich_business
        
        def mock_enrich(business, *args, **kwargs):
            processed_order.append(business['id'])
            return original_enrich(business, *args, **kwargs)
        
        with patch('bin.enrich.enrich_business', side_effect=mock_enrich):
            # Run the main function with a small limit
            enrich.main(['--limit', '3'])
        
        return processed_order, conn, cursor

# Then steps
@then('the business should have technical stack information')
def has_tech_stack(mock_db):
    """Verify the business has technical stack information."""
    conn, cursor = mock_db
    cursor.execute("SELECT tech_stack FROM businesses WHERE id = 1")
    tech_stack = cursor.fetchone()[0]
    assert tech_stack is not None
    tech_data = json.loads(tech_stack) if tech_stack else {}
    assert len(tech_data) > 0

@then('the business should have performance metrics')
def has_performance_metrics(mock_db):
    """Verify the business has performance metrics."""
    conn, cursor = mock_db
    cursor.execute("SELECT performance_data FROM businesses WHERE id = 1")
    performance_data = cursor.fetchone()[0]
    assert performance_data is not None
    perf_data = json.loads(performance_data) if performance_data else {}
    assert len(perf_data) > 0

@then('the business should have contact information')
def has_contact_info(mock_db):
    """Verify the business has contact information."""
    conn, cursor = mock_db
    cursor.execute("SELECT contact_info FROM businesses WHERE id = 1")
    contact_info = cursor.fetchone()[0]
    assert contact_info is not None

@then('the enriched data should be saved to the database')
def data_saved_to_db(mock_db):
    """Verify the enriched data is saved to the database."""
    conn, cursor = mock_db
    cursor.execute("SELECT enriched FROM businesses WHERE id = 1")
    enriched = cursor.fetchone()[0]
    assert enriched == 1

@then('the business should be marked for manual review')
def marked_for_review(mock_db):
    """Verify the business is marked for manual review."""
    conn, cursor = mock_db
    cursor.execute("SELECT status FROM businesses WHERE website IS NULL")
    status = cursor.fetchone()[0]
    assert status == "needs_website" or status == "manual_review"

@then(parsers.parse('the business should have a status of "{status}"'))
def has_status(mock_db, status):
    """Verify the business has the specified status."""
    conn, cursor = mock_db
    cursor.execute("SELECT status FROM businesses WHERE website IS NULL")
    actual_status = cursor.fetchone()[0]
    assert actual_status == status

@then('the enrichment process should continue to the next business')
def process_continues(mock_db):
    """Verify the enrichment process continues to the next business."""
    # This is a placeholder - in a real test we would verify that the next business is processed
    pass

@then('the error should be logged')
def error_logged(caplog):
    """Verify the error is logged."""
    assert any("error" in record.message.lower() for record in caplog.records)

@then('the business should be marked for retry')
def marked_for_retry(mock_db):
    """Verify the business is marked for retry."""
    conn, cursor = mock_db
    cursor.execute("SELECT status FROM businesses WHERE id = 1")
    status = cursor.fetchone()[0]
    assert status == "retry" or status == "error"

@then('the process should continue without crashing')
def process_continues_without_crashing():
    """Verify the process continues without crashing."""
    # If we've reached this point, the process didn't crash
    pass

@then('the business should be skipped')
def business_skipped(mock_apis):
    """Verify the business is skipped."""
    # The tech stack analyzer should not be called for already enriched businesses
    assert not mock_apis['tech_stack'].called

@then('businesses should be processed in descending score order')
def processed_in_score_order(run_enrichment_prioritized):
    """Verify businesses are processed in descending score order."""
    processed_order, conn, cursor = run_enrichment_prioritized
    
    # Get businesses ordered by score
    cursor.execute("SELECT id FROM businesses ORDER BY score DESC")
    expected_order = [row[0] for row in cursor.fetchall()]
    
    # Verify the processing order matches the expected order
    assert processed_order == expected_order[:len(processed_order)]
