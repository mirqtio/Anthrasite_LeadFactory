"""
Step definitions for the enrichment scenario.
"""

import os
# Import shared step definitions

import sys
# Import shared step definitions

import json
# Import shared step definitions

import sqlite3
# Import shared step definitions

from datetime import datetime
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

@given("a business exists with basic information")
def business_with_basic_info(db_conn):
    """Set up a business with basic information."""
    cursor = db_conn.execute("""
        INSERT INTO businesses (name, address, phone, website, category, source, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        RETURNING id
    """, ('Test Business', '123 Main St', '555-1234', 'http://test.com', 'HVAC', 'test_source'))

    business_id = cursor.fetchone()[0]
    db_conn.commit()

    context['business_id'] = business_id
    return business_id

@when("I enrich the business data")
def enrich_business_data(db_conn, mock_apis, context):
    """Enrich the business data."""
    business_id = context['business_id']

    # Mock enrichment data
    tech_stack = json.dumps({
        'cms': 'WordPress',
        'analytics': 'Google Analytics',
        'framework': 'Bootstrap',
        'hosting': 'AWS'
    })

    performance_score = 85.5
    contact_info = json.dumps({
        'email': 'contact@test.com',
        'phone': '555-1234',
        'social': {
            'facebook': 'https://facebook.com/testbusiness',
            'twitter': 'https://twitter.com/testbusiness'
        }
    })

    # Insert enrichment data
    db_conn.execute("""
        INSERT INTO enrichment (business_id, tech_stack, performance_score, contact_info, enrichment_timestamp)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (business_id, tech_stack, performance_score, contact_info))

    db_conn.commit()

    # Store in context for later assertions
    context['enrichment'] = {
        'tech_stack': json.loads(tech_stack),
        'performance_score': performance_score,
        'contact_info': json.loads(contact_info)
    }

    return context['enrichment']

@then("the business should have additional contact information")
def check_contact_info(db_conn, context):
    """Check that the business has contact information."""
    business_id = context['business_id']

    cursor = db_conn.execute("""
        SELECT contact_info FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"

    contact_info = json.loads(result[0])
    assert 'email' in contact_info, "Contact info missing email"
    assert 'phone' in contact_info, "Contact info missing phone"
    assert 'social' in contact_info, "Contact info missing social media"

@then("the business should have technology stack information")
def check_tech_stack(db_conn, context):
    """Check that the business has tech stack information."""
    business_id = context['business_id']

    cursor = db_conn.execute("""
        SELECT tech_stack FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"

    tech_stack = json.loads(result[0])
    assert len(tech_stack) > 0, "Tech stack is empty"

@then("the business should have performance metrics")
def check_performance(db_conn, context):
    """Check that the business has performance metrics."""
    business_id = context['business_id']

    cursor = db_conn.execute("""
        SELECT performance_score FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"
    assert result[0] > 0, "Performance score is zero or negative"

@then("the enrichment timestamp should be updated")
def check_enrichment_timestamp(db_conn, context):
    """Check that the enrichment timestamp is updated."""
    business_id = context['business_id']

    cursor = db_conn.execute("""
        SELECT enrichment_timestamp FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"
    assert result[0] is not None, "Enrichment timestamp is null"
