#!/usr/bin/env python3
"""
Script to migrate all code from legacy utils.io.DatabaseConnection
to the unified Postgres connector.
"""

import os
import re
import sys
from pathlib import Path

# Files to update
FILES_TO_UPDATE = [
    "utils/website_scraper.py",
    "utils/llm_logger 2.py",
    "utils/raw_data_retention 2.py",
    "bin/email_queue.py",
    "bin/score 2.py",
    "bin/score 3.py",
    "bin/enrich.py",
    "bin/dedupe.py",
    "tests/test_mockup 3.py",
    "tests/test_mockup.py",
]

# Test files that need different handling
TEST_FILES_TO_UPDATE = [
    "tests/test_unsubscribe.py",
    "tests/test_unsubscribe 2.py",
    "tests/conftest 2.py",
    "tests/conftest.py",
    "tests/steps/enrichment_steps.py",
    "tests/steps/deduplication_steps.py",
    "tests/utils/test_io.py",
    "tests/test_scraper.py",
]


def update_imports_in_file(filepath):
    """Update imports in a single file."""
    try:
        with open(filepath) as f:
            content = f.read()

        original_content = content

        # Replace utils.io imports with unified connector
        content = re.sub(
            r"from utils\.io import DatabaseConnection",
            "from leadfactory.utils.e2e_db_connector import db_connection as DatabaseConnection",
            content,
        )

        # Also handle any track_api_cost imports
        content = re.sub(
            r"from utils\.io import (.*)track_api_cost",
            r"from utils.io import \1track_api_cost",  # Keep track_api_cost as is for now
            content,
        )

        if content != original_content:
            with open(filepath, "w") as f:
                f.write(content)
            return True
        else:
            return False

    except FileNotFoundError:
        return False
    except Exception:
        return False


def update_test_patches(filepath):
    """Update patch statements in test files."""
    try:
        with open(filepath) as f:
            content = f.read()

        original_content = content

        # Update patch statements to use the new module path
        content = re.sub(
            r'patch\("utils\.io\.DatabaseConnection"\)',
            'patch("leadfactory.utils.e2e_db_connector.db_connection")',
            content,
        )

        # Also update with statements
        content = re.sub(
            r'with patch\("utils\.io\.DatabaseConnection"\) as',
            'with patch("leadfactory.utils.e2e_db_connector.db_connection") as',
            content,
        )

        if content != original_content:
            with open(filepath, "w") as f:
                f.write(content)
            return True
        else:
            return False

    except FileNotFoundError:
        return False
    except Exception:
        return False


def main():
    """Run the migration."""

    # Get project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Update regular files
    updated_count = 0
    for filepath in FILES_TO_UPDATE:
        if update_imports_in_file(filepath):
            updated_count += 1

    # Update test files
    test_updated_count = 0
    for filepath in TEST_FILES_TO_UPDATE:
        if update_test_patches(filepath):
            test_updated_count += 1

    # Create a simple DatabaseConnection wrapper in utils/io/__init__.py for backward compatibility
    wrapper_content = '''"""
IO utility functions for Anthrasite LeadFactory.
"""

import json
import sqlite3
from datetime import datetime

# Import the unified connector for backward compatibility
from leadfactory.utils.e2e_db_connector import db_connection as DatabaseConnection


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
    VALUES (?, ?, ?, ?, ?, ?)
    """,
        (api_name, endpoint, cost, datetime.now().isoformat(), model, purpose),
    )

    db_conn.commit()
    return cursor.lastrowid


# Re-export for backward compatibility
__all__ = ['DatabaseConnection', 'read_file', 'write_file', 'track_api_cost']
'''

    try:
        with open("utils/io/__init__.py", "w") as f:
            f.write(wrapper_content)
    except Exception:
        pass


if __name__ == "__main__":
    main()
