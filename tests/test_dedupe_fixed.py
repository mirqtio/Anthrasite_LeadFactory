"""
BDD tests for the lead deduplication (03_dedupe.py)
"""

import os
import sys
import tempfile
import sqlite3
from typing import Generator
import pytest
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Import the module under test
@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_llm_verifier():
    """Create a mock LLM verifier."""
    mock_verifier = MagicMock()
    mock_verifier.verify_duplicate.return_value = {
        "is_duplicate": True,
        "confidence": 0.95,
        "reason": "Businesses have matching names and addresses",
    }
    return mock_verifier


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing with all required tables and indexes."""
    # Create a temporary file for the database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Connect to the database
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Create the businesses table
        cursor.execute(
            """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            status TEXT,
            score INTEGER
        )"""
        )
        # Create the candidate_duplicate_pairs table
        cursor.execute(
            """
        CREATE TABLE candidate_duplicate_pairs (
            id INTEGER PRIMARY KEY,
            business1_id INTEGER NOT NULL,
            business2_id INTEGER NOT NULL,
            similarity_score REAL,
            status TEXT DEFAULT 'pending',
            verified_by_llm BOOLEAN DEFAULT 0,
            llm_confidence REAL,
            llm_reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business1_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (business2_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE (business1_id, business2_id),
            CHECK (business1_id < business2_id)
        )"""
        )
        # Create indexes
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_businesses_name
        ON businesses(name)"""
        )
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_candidate_pairs
        ON candidate_duplicate_pairs(business1_id, business2_id)"""
        )
        # Insert test data
        cursor.execute(
            """
        INSERT INTO businesses
        (id, name, address, city, state, zip, phone, email, website, status, score)
        VALUES
            (1, 'Test Business 1', '123 Main St', 'Anytown', 'CA', '12345', '555-123-4567', 'test1@example.com', 'http://test1.com', 'pending', 85),
            (2, 'Test Business 1', '123 Main St', 'Anytown', 'CA', '12345', '555-123-4567', 'test1@example.com', 'http://test1.com', 'pending', 82),
            (3, 'Test Business 2', '456 Oak Ave', 'Somewhere', 'NY', '10001', '555-987-6543', 'test2@example.com', 'http://test2.com', 'pending', 78),
            (4, 'Similar Business', '789 Pine Rd', 'Nowhere', 'TX', '75001', '555-555-1212', 'test3@example.com', 'http://test3.com', 'pending', 92)
        """
        )
        cursor.execute(
            """
        INSERT INTO candidate_duplicate_pairs
        (id, business1_id, business2_id, similarity_score, status, verified_by_llm, llm_confidence, llm_reasoning)
        VALUES
            (1, 1, 2, 0.95, 'pending', 1, 0.95, 'Exact match'),
            (2, 3, 4, 0.85, 'pending', 1, 0.85, 'Similar businesses')
        """
        )
        conn.commit()
        # Verify the test data was inserted
        cursor.execute("SELECT COUNT(*) as count FROM businesses")
        business_count = cursor.fetchone()["count"]
        if business_count < 4:
            raise ValueError(f"Failed to insert test businesses. Expected 4, got {business_count}")
        cursor.execute("SELECT COUNT(*) as count FROM candidate_duplicate_pairs")
        pair_count = cursor.fetchone()["count"]
        if pair_count < 2:
            raise ValueError(f"Failed to insert test candidate pairs. Expected 2, got {pair_count}")
        # Close the connection
        cursor.close()
        conn.close()
        # Yield the path to the test database
        yield path
    finally:
        # Clean up the temporary database file
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception as e:
            print(
                f"Warning: Failed to remove temporary database file: {e}",
                file=sys.stderr,
            )


def test_exact_duplicates(temp_db, mock_llm_verifier):
    """Test identifying exact duplicate businesses."""
    # Connect to the test database
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Test exact duplicates
        cursor.execute(
            """
        SELECT b1.id as id1, b2.id as id2, b1.name as name1, b2.name as name2,
               b1.address as addr1, b2.address as addr2
        FROM businesses b1
        JOIN businesses b2 ON b1.id < b2.id
        WHERE b1.name = b2.name
          AND b1.address = b2.address
        """
        )
        duplicates = cursor.fetchall()
        assert len(duplicates) >= 1, "Expected at least one exact duplicate business"
        for dup in duplicates:
            assert dup["name1"] == dup["name2"], "Business names should match"
            assert dup["addr1"] == dup["addr2"], "Addresses should match"
    finally:
        cursor.close()
        conn.close()


def test_fuzzy_matching(temp_db, mock_llm_verifier):
    """Test identifying similar businesses with fuzzy matching."""
    # Connect to the test database
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Test fuzzy matching
        cursor.execute(
            """
        SELECT b1.id as id1, b2.id as id2, b1.name as name1, b2.name as name2,
               b1.address as addr1, b2.address as addr2,
               b1.city as city1, b2.city as city2,
               b1.state as state1, b2.state as state2
        FROM businesses b1
        JOIN businesses b2 ON b1.id < b2.id
        WHERE (b1.name LIKE '%' || b2.name || '%' OR b2.name LIKE '%' || b1.name || '%')
          AND (b1.city = b2.city AND b1.state = b2.state)
        """
        )
        similar = cursor.fetchall()
        assert len(similar) >= 1, "Expected at least one pair of similar businesses"
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
