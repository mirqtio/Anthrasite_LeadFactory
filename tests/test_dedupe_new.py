"""
Tests for the deduplication module.
"""

import os
import sys
import pytest
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the deduplication module
from bin import dedupe

# Constants for test data
TEST_BUSINESS_1 = {
    "id": 1,
    "name": "Test Business 1",
    "address": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "zip": "12345",
    "phone": "555-123-4567",
    "email": "test1@example.com",
    "website": "http://test1.com",
    "status": "pending",
    "score": 85,
}
TEST_BUSINESS_2 = {
    "id": 2,
    "name": "Test Business 2",
    "address": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "zip": "12345",
    "phone": "555-123-4567",
    "email": "test1@example.com",
    "website": "http://test1.com",
    "status": "pending",
    "score": 90,
}
TEST_BUSINESS_3 = {
    "id": 3,
    "name": "Test Business 1",  # Same name as business 1
    "address": "456 Oak Ave",  # Different address
    "city": "Othertown",
    "state": "CA",
    "zip": "12345",
    "phone": "555-123-4568",
    "email": "test3@example.com",
    "website": "http://test3.com",
    "status": "pending",
    "score": 88,
}


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create a temporary file for the database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # Enable dictionary-like access to rows
    cursor = conn.cursor()
    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")
    # Create businesses table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        phone TEXT,
        email TEXT,
        website TEXT,
        category TEXT,
        source TEXT,
        source_id TEXT,
        status TEXT DEFAULT 'pending',
        score INTEGER,
        score_details TEXT,
        tech_stack TEXT,
        performance TEXT,
        contact_info TEXT,
        enriched_at TIMESTAMP,
        merged_into INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (merged_into) REFERENCES businesses(id) ON DELETE SET NULL
    )"""
    )
    # Create features table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        tech_stack TEXT,
        page_speed INTEGER,
        screenshot_url TEXT,
        semrush_json TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )"""
    )
    # Create mockups table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS mockups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        mockup_md TEXT,
        mockup_png TEXT,
        prompt_used TEXT,
        model_used TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )"""
    )
    # Create emails table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        variant_id TEXT NOT NULL,
        subject TEXT,
        body_text TEXT,
        body_html TEXT,
        status TEXT DEFAULT 'pending',
        sent_at TIMESTAMP,
        opened_at TIMESTAMP,
        clicked_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )"""
    )
    # Create candidate_duplicate_pairs table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS candidate_duplicate_pairs (
        id INTEGER PRIMARY KEY,
        business1_id INTEGER NOT NULL,
        business2_id INTEGER NOT NULL,
        similarity_score REAL NOT NULL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processed', 'merged', 'rejected', 'review')),
        verified_by_llm BOOLEAN DEFAULT 0,
        llm_confidence REAL,
        llm_reasoning TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business1_id) REFERENCES businesses(id) ON DELETE CASCADE,
        FOREIGN KEY (business2_id) REFERENCES businesses(id) ON DELETE CASCADE,
        UNIQUE(business1_id, business2_id),
        CHECK(business1_id < business2_id)
    )"""
    )
    # Create triggers for updated_at timestamps
    cursor.execute(
        """
    CREATE TRIGGER IF NOT EXISTS update_businesses_timestamp
    AFTER UPDATE ON businesses
    FOR EACH ROW
    BEGIN
        UPDATE businesses SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;"""
    )
    cursor.execute(
        """
    CREATE TRIGGER IF NOT EXISTS update_dup_pairs_timestamp
    AFTER UPDATE ON candidate_duplicate_pairs
    FOR EACH ROW
    BEGIN
        UPDATE candidate_duplicate_pairs SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;"""
    )
    # Commit all changes
    conn.commit()
    # Return the database path and connection
    yield path, conn
    # Clean up
    conn.close()
    try:
        os.unlink(path)
    except Exception as e:
        print(f"Error cleaning up temporary database: {e}", file=sys.stderr)


def insert_business(conn, business):
    """Helper function to insert a business into the database."""
    cursor = conn.cursor()
    # Set default values for optional fields
    business_data = {
        "id": business.get("id"),
        "name": business.get("name"),
        "address": business.get("address"),
        "city": business.get("city"),
        "state": business.get("state"),
        "zip": business.get("zip"),
        "phone": business.get("phone"),
        "email": business.get("email"),
        "website": business.get("website"),
        "category": business.get("category"),
        "source": business.get("source"),
        "source_id": business.get("source_id"),
        "status": business.get("status", "pending"),
        "score": business.get("score"),
        "score_details": business.get("score_details"),
        "tech_stack": business.get("tech_stack"),
        "performance": business.get("performance"),
        "contact_info": business.get("contact_info"),
        "enriched_at": business.get("enriched_at"),
        "merged_into": business.get("merged_into"),
    }
    cursor.execute(
        """
    INSERT INTO businesses
    (id, name, address, city, state, zip, phone, email, website, category, source, source_id,
     status, score, score_details, tech_stack, performance, contact_info, enriched_at, merged_into)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            business_data["id"],
            business_data["name"],
            business_data["address"],
            business_data["city"],
            business_data["state"],
            business_data["zip"],
            business_data["phone"],
            business_data["email"],
            business_data["website"],
            business_data["category"],
            business_data["source"],
            business_data["source_id"],
            business_data["status"],
            business_data["score"],
            business_data["score_details"],
            business_data["tech_stack"],
            business_data["performance"],
            business_data["contact_info"],
            business_data["enriched_at"],
            business_data["merged_into"],
        ),
    )
    conn.commit()
    return cursor.lastrowid


def test_flag_for_review(temp_db):
    """Test that the flag_for_review function works as expected."""
    db_path, conn = temp_db
    # Insert test businesses
    insert_business(conn, TEST_BUSINESS_1)  # ID 1
    insert_business(conn, TEST_BUSINESS_2)  # ID 2
    # Create a candidate duplicate pair
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO candidate_duplicate_pairs
    (business1_id, business2_id, similarity_score, status)
    VALUES (?, ?, ?, ?)
    """,
        (1, 2, 0.8, "pending"),
    )
    conn.commit()
    # Mock the database connection to use our test database
    with patch("bin.dedupe.DatabaseConnection") as mock_db_conn:
        # Create a real connection to the test database
        real_conn = conn
        # Set up the mock to return a tuple of (connection, cursor)
        mock_db_conn.return_value.__enter__.return_value = real_conn
        # Call the function - it doesn't return a value but updates the database
        dedupe.flag_for_review(
            business1_id=1,
            business2_id=2,
            reason="Same name but different addresses",
            similarity_score=0.8,
        )
        # No need to verify a return value, just check that the database was updated correctly
        # Verify the database was updated
        cursor.execute(
            "SELECT * FROM candidate_duplicate_pairs WHERE business1_id = 1 AND business2_id = 2"
        )
        pair = cursor.fetchone()
        assert pair is not None
        assert pair["status"] == "review"
        assert pair["llm_reasoning"] == "Same name but different addresses"


def test_skip_processed_businesses(temp_db):
    """Test that processed businesses are skipped."""
    db_path, conn = temp_db
    # Insert test businesses
    insert_business(conn, TEST_BUSINESS_1)
    insert_business(conn, TEST_BUSINESS_2)
    # Create a processed candidate duplicate pair
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO candidate_duplicate_pairs
    (business1_id, business2_id, similarity_score, status, verified_by_llm, llm_confidence, llm_reasoning)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (1, 2, 0.9, "processed", 1, 0.95, "Already processed"),
    )
    conn.commit()
    # Mock the get_potential_duplicates function to return our test pair
    with patch("bin.dedupe.get_potential_duplicates") as mock_get_pairs:
        mock_get_pairs.return_value = [
            {
                "id": 1,
                "business1_id": 1,
                "business2_id": 2,
                "similarity_score": 0.9,
                "status": "processed",
            }
        ]
        # Mock the get_business_by_id function
        with patch("bin.dedupe.get_business_by_id") as mock_get_business:
            # Set up the side effect to return our test businesses
            def get_business_side_effect(business_id):
                if business_id == 1:
                    return TEST_BUSINESS_1
                elif business_id == 2:
                    return TEST_BUSINESS_2
                return None

            mock_get_business.side_effect = get_business_side_effect
            # Mock the logger
            with patch("bin.dedupe.logger") as mock_logger:
                # Mock the flag_for_review function
                with patch("bin.dedupe.flag_for_review") as mock_flag_for_review:
                    # Mock the LevenshteinMatcher
                    with patch("bin.dedupe.LevenshteinMatcher") as mock_matcher_class:
                        # Create a mock instance
                        mock_matcher = MagicMock()
                        mock_matcher_class.return_value = mock_matcher
                        # Mock the OllamaVerifier
                        with patch("bin.dedupe.OllamaVerifier") as mock_verifier_class:
                            # Create a mock instance
                            mock_verifier = MagicMock()
                            mock_verifier_class.return_value = mock_verifier
                            # Run the deduplication process
                            with patch("sys.argv", ["bin/dedupe.py"]):
                                dedupe.main()
                            # Verify that the processed pair was skipped
                            # Check for various possible log messages related to skipping
                            expected_messages = [
                                "Skipping already processed business pair",
                                "already processed",
                                "Skipping pair",
                                "status is not pending",
                            ]
                            log_messages = [
                                str(call[0][0])
                                for call in mock_logger.info.call_args_list
                            ]
                            found_skip_message = False
                            for msg in log_messages:
                                if any(
                                    expected in msg for expected in expected_messages
                                ):
                                    found_skip_message = True
                                    break
                            assert (
                                found_skip_message
                            ), f"Expected message about skipping processed pairs, got: {log_messages}"
                            assert (
                                not mock_flag_for_review.called
                            ), "flag_for_review should not be called for processed pairs"
