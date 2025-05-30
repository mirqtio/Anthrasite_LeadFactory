"""
Pytest configuration and fixtures for BDD tests.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables for testing
os.environ["TEST_MODE"] = "True"
os.environ["MOCK_EXTERNAL_APIS"] = "True"

# Global context dictionary for sharing state between steps
@pytest.fixture(scope="function")
def context():
    """Shared context between test steps."""
    return {}

# Database connection fixture
@pytest.fixture(scope="function")
def db_conn():
    """Create an in-memory SQLite database for testing."""
    # Use an in-memory database for testing
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create tables for BDD tests - with expanded schema to cover all requirements
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        phone TEXT,
        website TEXT,
        email TEXT,
        description TEXT,
        category TEXT,
        source TEXT,
        status TEXT DEFAULT 'pending',
        score REAL,
        performance TEXT,
        tech_stack TEXT,
        created_at TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS business_scores (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        total_score REAL,
        tech_score REAL,
        performance_score REAL,
        size_score REAL,
        industry_score REAL,
        created_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    );

    CREATE TABLE IF NOT EXISTS tech_stack (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        technology TEXT,
        category TEXT,
        created_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    );

    CREATE TABLE IF NOT EXISTS enrichment (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        tech_stack TEXT,
        performance_score REAL,
        contact_info TEXT,
        enrichment_timestamp TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    );

    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        score REAL,
        criteria TEXT,
        scoring_timestamp TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    );

    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        subject TEXT,
        body TEXT,
        recipient TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        sent_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    );

    CREATE TABLE IF NOT EXISTS api_costs (
        id INTEGER PRIMARY KEY,
        api_name TEXT,
        endpoint TEXT,
        cost REAL,
        timestamp TEXT,
        model TEXT,
        purpose TEXT
    );
    """)

    yield conn
    conn.close()

# Create a shared context object available to all tests
global_context = {}

@pytest.fixture(scope="function")
def context():
    """Provide a shared context between test steps."""
    # Clear the context at the start of each test
    global_context.clear()
    return global_context
