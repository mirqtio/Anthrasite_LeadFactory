"""
IO utility functions for Anthrasite LeadFactory.
"""

import json
import sqlite3
from datetime import datetime


# Mock implementation for testing
def read_file(path):
    """Read a file and return its contents."""
    return "mock file contents"


def write_file(path, content):
    """Write content to a file."""
    return True


def track_api_cost(db_conn, api_name, endpoint, cost, model=None, purpose=None):
    """
    Track the cost of an API call in the database.

    Args:
        db_conn: SQLite connection object
        api_name: Name of the API provider (e.g., 'OpenAI', 'Yelp')
        endpoint: API endpoint used (e.g., '/v1/chat/completions')
        cost: Cost of the API call
        model: Optional API model used (e.g., 'gpt-4')
        purpose: Optional purpose of the API call (e.g., 'lead_generation')

    Returns:
        ID of the inserted record
    """
    # Ensure the api_costs table exists
    db_conn.execute(
        """
    CREATE TABLE IF NOT EXISTS api_costs (
        id INTEGER PRIMARY KEY,
        api_name TEXT,
        endpoint TEXT,
        cost REAL,
        timestamp TEXT,
        model TEXT,
        purpose TEXT
    )
    """
    )

    # Insert the API cost record
    cursor = db_conn.execute(
        """
    INSERT INTO api_costs (api_name, endpoint, cost, timestamp, model, purpose)
    VALUES (?, ?, ?, datetime('now'), ?, ?)
    """,
        (api_name, endpoint, cost, model, purpose),
    )

    db_conn.commit()

    # Return the ID of the inserted record
    return cursor.lastrowid
