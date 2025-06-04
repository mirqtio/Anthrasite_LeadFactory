"""
Shared step definitions for BDD tests.
These steps are imported by all test files.
"""

import sqlite3

from pytest_bdd import given, parsers, then, when

# Import the global context from conftest.py
from tests.bdd.conftest import global_context as context


@given("the database is initialized")
def initialize_database(db_conn):
    """Initialize the database with necessary tables for testing."""
    # The db_conn fixture in conftest.py already creates all necessary tables
    # Just confirm that the database is ready by checking for the existence of key tables
    cursor = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='businesses'"
    )
    if not cursor.fetchone():
        raise Exception("Database tables not properly initialized")

    # Reset the global context for this test
    context.clear()

    # Mark that we've initialized the database
    context["database_initialized"] = True

    return db_conn
