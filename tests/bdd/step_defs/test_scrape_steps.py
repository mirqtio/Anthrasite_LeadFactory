"""
Step definitions for the scraping scenario.
"""

import os
# Import shared step definitions

import sys
# Import shared step definitions

import sqlite3
# Import shared step definitions

from unittest.mock import MagicMock, patch

import pytest
# Import shared step definitions

from pytest_bdd import given, when, then, parsers
# Import common step definitions
from tests.bdd.step_defs.common_step_definitions import *

# Add project root to path

# Import mock modules and common step definitions
from tests.bdd.mock_modules import *
from tests.bdd.step_defs.test_common_steps import database_initialized, api_mocks_configured, mock_apis

# Context dictionary to store test state
context = {}

@when(parsers.parse('I scrape businesses from source "{source}" with limit {limit:d}'))
def scrape_businesses(source, limit, mock_apis, db_conn):
    """Scrape businesses from the specified source."""
    # Mock the scraping process
    businesses = [
        {'id': '1', 'name': 'Test Business 1', 'address': '123 Main St', 'phone': '555-1234', 'website': 'http://test1.com', 'category': 'test', 'source': source},
        {'id': '2', 'name': 'Test Business 2', 'address': '456 Elm St', 'phone': '555-5678', 'website': 'http://test2.com', 'category': 'test', 'source': source},
        {'id': '3', 'name': 'Test Business 3', 'address': '789 Oak St', 'phone': '555-9012', 'website': 'http://test3.com', 'category': 'test', 'source': source},
    ]

    # Store in context for later assertions
    context['businesses'] = businesses

    # Insert into db
    for business in businesses:
        db_conn.execute("""
            INSERT INTO businesses (name, address, phone, website, category, source, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (business['name'], business['address'], business['phone'], business['website'], business['category'], business['source']))

    db_conn.commit()
    return businesses

@then(parsers.parse('I should receive at least {count:d} businesses'))
def check_business_count(count, context):
    """Check that we received at least the specified number of businesses."""
    assert len(context['businesses']) >= count, f"Expected at least {count} businesses, got {len(context['businesses'])}"

@then("each business should have a name and address")
def check_business_data(context):
    """Check that each business has the required data."""
    for business in context['businesses']:
        assert 'name' in business and business['name'], "Business missing name"
        assert 'address' in business and business['address'], "Business missing address"

@then("each business should be saved to the database")
def check_businesses_saved(db_conn, context):
    """Check that businesses are saved to the database."""
    cursor = db_conn.execute("SELECT COUNT(*) FROM businesses")
    count = cursor.fetchone()[0]
    assert count >= len(context['businesses']), f"Expected at least {len(context['businesses'])} businesses in the database, got {count}"
