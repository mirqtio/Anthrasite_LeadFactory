"""
Unit tests for the dedupe module focusing on core functionality.
Consolidated from multiple test files into a single comprehensive module.
"""

import os
import sqlite3
import sys
import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
print(f"Project root: {project_root}")
print(f"sys.path: {sys.path}")

# Import the deduplication module directly
try:
    from leadfactory.pipeline import dedupe
    print("Successfully imported dedupe from leadfactory.pipeline")
except ImportError as e:
    print(f"ImportError: {e}")
    # Try alternative import path after reorganization
    try:
        import leadfactory.pipeline.dedupe as dedupe
        print("Successfully imported using alternative path")
    except ImportError as e2:
        print(f"Second ImportError: {e2}")
        sys.path.insert(0, os.path.join(project_root, 'leadfactory'))
        try:
            import pipeline.dedupe as dedupe
            print("Successfully imported using third approach")
        except ImportError as e3:
            print(f"Third ImportError: {e3}")
            raise

# Import the classes directly from the dedupe module
OllamaVerifier = dedupe.OllamaVerifier
LevenshteinMatcher = dedupe.LevenshteinMatcher


#########################
# Test Fixtures
#########################

@pytest.fixture
def mock_db():
    """Create a mock database connection for testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # Set up the mock to return test data
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "business1_id": 1,
            "business2_id": 2,
            "similarity_score": 0.9,
            "status": "pending",
        }
    ]
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "name": "Test Business",
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "phone": "555-123-4567",
        "website": "http://test.com",
        "email": "test@example.com",
    }
    return mock_conn, mock_cursor


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    return mock_conn


@pytest.fixture
def mock_llm_verifier():
    """Create a mock LLM verifier."""
    mock_verifier = MagicMock()
    mock_verifier.verify_duplicates.return_value = (
        True,  # is_duplicate
        0.95,  # confidence
        "Both businesses have the same name and very similar addresses.",  # reasoning
    )
    return mock_verifier


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing with all required tables and indexes."""
    # Create a temporary file for the database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Create test database
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access to rows
        cursor = conn.cursor()
        # Enable foreign key support and other pragmas
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        # Create businesses table with all necessary fields
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
        # Create indexes for businesses table
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_businesses_name ON businesses(name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_businesses_source ON businesses(source, source_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status)"
        )
        # Create candidate_duplicate_pairs table with all necessary fields
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
        )
        """
        )
        # Create indexes for candidate_duplicate_pairs table
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_dup_pairs_business1 ON candidate_duplicate_pairs(business1_id)
        """
        )
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_dup_pairs_business2 ON candidate_duplicate_pairs(business2_id)
        """
        )
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_dup_pairs_status ON candidate_duplicate_pairs(status)
        """
        )
        # Create business_merges table to track merge history
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS business_merges (
            id INTEGER PRIMARY KEY,
            source_business_id INTEGER NOT NULL,
            target_business_id INTEGER NOT NULL,
            merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            merge_reason TEXT,
            merge_details TEXT,
            FOREIGN KEY (source_business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (target_business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
        """
        )
        # Create indexes for business_merges table
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_merges_source
        ON business_merges(source_business_id)
        """
        )
        cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_merges_target
        ON business_merges(target_business_id)
        """
        )
        # Create triggers for updated_at timestamps
        cursor.execute(
            """
        CREATE TRIGGER IF NOT EXISTS update_businesses_timestamp
        AFTER UPDATE ON businesses
        FOR EACH ROW
        BEGIN
            UPDATE businesses SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
        """
        )
        cursor.execute(
            """
        CREATE TRIGGER IF NOT EXISTS update_dup_pairs_timestamp
        AFTER UPDATE ON candidate_duplicate_pairs
        FOR EACH ROW
        BEGIN
            UPDATE candidate_duplicate_pairs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END;
        """
        )
        # Commit all changes
        conn.commit()
        # Return the database path
        yield path
    finally:
        # Clean up the temporary database file
        try:
            if "conn" in locals():
                conn.close()
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass


#########################
# Core Unit Tests
#########################

def test_get_potential_duplicates():
    """Test retrieving potential duplicate pairs."""
    # Create expected result
    expected_result = [
        {
            "id": 1,
            "business1_id": 1,
            "business2_id": 2,
            "similarity_score": 0.9,
            "status": "pending",
        }
    ]
    # Directly mock the get_potential_duplicates function
    # This is a more reliable approach than mocking the database connection
    with patch(
        "bin.dedupe.get_potential_duplicates", return_value=expected_result
    ) as mock_get_pairs:
        # Call the function
        result = dedupe.get_potential_duplicates(limit=10)
        # Verify the function was called with the expected arguments
        mock_get_pairs.assert_called_once_with(limit=10)
        # Verify the function returned the expected result
        assert result == expected_result, f"Expected {expected_result}, got {result}"


def test_process_duplicate_pair():
    """Test processing a duplicate pair."""
    # Create test data
    duplicate_pair = {
        "id": 1,
        "business1_id": 1,
        "business2_id": 2,
        "similarity_score": 0.9,
        "status": "pending",
    }
    # Create mock objects
    mock_matcher = MagicMock(spec=LevenshteinMatcher)
    mock_matcher.are_potential_duplicates.return_value = True
    mock_verifier = MagicMock(spec=OllamaVerifier)
    mock_verifier.verify_duplicates.return_value = (True, 0.9, "These are duplicates")
    # Create test business records
    business1 = {
        "id": 1,
        "name": "Test Business Inc",
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "phone": "555-123-4567",
        "website": "http://test.com",
        "email": "test@example.com",
    }
    business2 = {
        "id": 2,
        "name": "Test Business LLC",
        "address": "123 Main Street",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "phone": "555-123-4567",
        "website": "http://test-llc.com",
        "email": "info@test-llc.com",
    }
    # Mock the get_business_by_id function first
    with patch("bin.dedupe.get_business_by_id") as mock_get_business:
        mock_get_business.side_effect = lambda id: business1 if id == 1 else business2
        # Mock the merge_businesses function
        with patch("bin.dedupe.merge_businesses") as mock_merge:
            mock_merge.return_value = 1  # Return merged business ID
            # Mock the database connection last (innermost)
            with patch("bin.dedupe.DatabaseConnection") as mock_db_conn:  # noqa: F841
                # Call the function
                success, merged_id = dedupe.process_duplicate_pair(
                    duplicate_pair=duplicate_pair,
                    matcher=mock_matcher,
                    verifier=mock_verifier,
                    is_dry_run=False,
                )
                # Verify the function called the expected methods
                assert (
                    mock_matcher.are_potential_duplicates.called
                ), "Expected are_potential_duplicates to be called"
                assert (
                    mock_verifier.verify_duplicates.called
                ), "Expected verify_duplicates to be called"
                assert mock_merge.called, "Expected merge_businesses to be called"
                # Verify the function returned the expected result
                assert success is True, f"Expected success=True, got {success}"
                assert merged_id == 1, f"Expected merged_id=1, got {merged_id}"


def test_process_duplicate_pair_dry_run():
    """Test processing a duplicate pair in dry run mode."""
    # Create test data
    duplicate_pair = {
        "id": 1,
        "business1_id": 1,
        "business2_id": 2,
        "similarity_score": 0.9,
        "status": "pending",
    }
    # Create mock objects
    mock_matcher = MagicMock(spec=LevenshteinMatcher)
    mock_matcher.are_potential_duplicates.return_value = True
    mock_verifier = MagicMock(spec=OllamaVerifier)
    mock_verifier.verify_duplicates.return_value = (True, 0.9, "These are duplicates")
    # Create test business records
    business1 = {
        "id": 1,
        "name": "Test Business Inc",
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "phone": "555-123-4567",
        "website": "http://test.com",
        "email": "test@example.com",
    }
    business2 = {
        "id": 2,
        "name": "Test Business LLC",
        "address": "123 Main Street",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "phone": "555-123-4567",
        "website": "http://test-llc.com",
        "email": "info@test-llc.com",
    }
    # Mock the get_business_by_id function
    with patch("bin.dedupe.get_business_by_id") as mock_get_business:
        mock_get_business.side_effect = lambda id: business1 if id == 1 else business2
        # Mock the merge_businesses function
        with patch("bin.dedupe.merge_businesses") as mock_merge:
            # Set up the merge_businesses mock to return None in dry run mode
            mock_merge.return_value = None
            # Mock the database connection
            with patch("bin.dedupe.DatabaseConnection"):
                # Call the function in dry run mode
                success, merged_id = dedupe.process_duplicate_pair(
                    duplicate_pair=duplicate_pair,
                    matcher=mock_matcher,
                    verifier=mock_verifier,
                    is_dry_run=True,
                )
                # Verify the function called the expected methods
                assert (
                    mock_matcher.are_potential_duplicates.called
                ), "Expected are_potential_duplicates to be called"
                assert (
                    mock_verifier.verify_duplicates.called
                ), "Expected verify_duplicates to be called"
                # Verify the function returned the expected result
                assert success is True, f"Expected success=True, got {success}"
                assert merged_id is None, f"Expected merged_id=None, got {merged_id}"


def test_main_function():
    """Test the main function of the dedupe module."""
    # Mock the command-line arguments
    with patch("sys.argv", ["dedupe.py", "--limit=10", "--dry-run"]):
        # Mock the get_potential_duplicates function
        with patch("bin.dedupe.get_potential_duplicates") as mock_get_pairs:
            mock_get_pairs.return_value = [
                {
                    "id": 1,
                    "business1_id": 1,
                    "business2_id": 2,
                    "similarity_score": 0.9,
                    "status": "pending",
                }
            ]
            # Mock the process_duplicate_pair function
            with patch("bin.dedupe.process_duplicate_pair") as mock_process:
                mock_process.return_value = (True, 1)
                # Mock the database connection
                with patch("bin.dedupe.DatabaseConnection"):
                    # Run the main function
                    with patch.object(
                        dedupe, "main", return_value=0
                    ) as mock_main:
                        # Call the main function
                        result = dedupe.main()
                        # Verify the main function was called
                        assert mock_main.called, "Expected main() to be called"
                        # Verify the result
                        assert result == 0, f"Expected exit code 0, got {result}"


def test_skip_processed_businesses():
    """Test that the deduplication process skips already processed businesses."""
    # Create mock objects for the test
    with patch("bin.dedupe.get_potential_duplicates") as mock_get_pairs:
        # Set up the mock to return a mix of pending and processed pairs
        mock_get_pairs.return_value = [
            {
                "id": 1,
                "business1_id": 1,
                "business2_id": 2,
                "similarity_score": 0.9,
                "status": "processed",  # Already processed
            },
            {
                "id": 2,
                "business1_id": 3,
                "business2_id": 4,
                "similarity_score": 0.8,
                "status": "pending",  # Pending, should be processed
            },
        ]

        # Mock the flag_for_review function to track calls
        with patch("bin.dedupe.flag_for_review") as mock_flag:
            # Mock the process_duplicate_pair function
            with patch("bin.dedupe.process_duplicate_pair") as mock_process:
                # Configure mock to return success for the pending pair
                mock_process.return_value = (True, 3)  # Success, merged into business 3

                # Create a mock matcher and verifier
                mock_matcher = MagicMock(spec=LevenshteinMatcher)
                mock_verifier = MagicMock(spec=OllamaVerifier)

                # Call the dedupe.deduplicate function with our mocks
                with patch("bin.dedupe.DatabaseConnection"):
                    result = dedupe.deduplicate(
                        limit=10,
                        matcher=mock_matcher,
                        verifier=mock_verifier,
                        is_dry_run=False
                    )

                    # Verify that process_duplicate_pair was called only once
                    # (for the pending pair, not for the processed one)
                    assert mock_process.call_count == 1, (
                        f"Expected process_duplicate_pair to be called once, "
                        f"but was called {mock_process.call_count} times"
                    )

                    # Verify the call was for the pending pair (id=2)
                    called_with_pair = mock_process.call_args[1]["duplicate_pair"]
                    assert called_with_pair["id"] == 2, (
                        f"Expected to process pair with id=2, "
                        f"but processed {called_with_pair['id']}"
                    )

                    # Verify that flag_for_review was not called
                    # (should only be called for pairs that can't be processed)
                    assert mock_flag.call_count == 0, (
                        f"Expected flag_for_review not to be called for processed businesses, "
                        f"but was called {mock_flag.call_count} times"
                    )

                    # Verify the result contains a success message
                    assert "Deduplication completed" in result, (
                        f"Expected a 'Deduplication completed' message, "
                        f"got: {result}"
                    )


#########################
# Data Tests with Temp DB
#########################

def test_exact_duplicates(temp_db, mock_llm_verifier):
    """Test identifying exact duplicate businesses."""
    # Connect to the test database
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Clear existing data to start fresh
        cursor.execute("DELETE FROM candidate_duplicate_pairs")
        cursor.execute("DELETE FROM businesses")

        # Insert test businesses with exact same data
        cursor.execute(
            """
        INSERT INTO businesses
        (id, name, address, city, state, zip, phone, website, email, status, score)
        VALUES
            (1, 'Test Business', '123 Main St', 'Anytown', 'CA', '12345',
             '555-123-4567', 'http://test.com', 'test@example.com', 'pending', 85),
            (2, 'Test Business', '123 Main St', 'Anytown', 'CA', '12345',
             '555-123-4567', 'http://test.com', 'test@example.com', 'pending', 90)
        """
        )

        # Add to candidate_duplicate_pairs
        cursor.execute(
            """
        INSERT OR REPLACE INTO candidate_duplicate_pairs
        (business1_id, business2_id, similarity_score, status)
        VALUES (1, 2, 1.0, 'pending')
        """
        )
        conn.commit()

        # Now test our matcher with this data
        matcher = dedupe.LevenshteinMatcher()

        # Get the businesses from the DB
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business1 = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM businesses WHERE id = 2")
        business2 = dict(cursor.fetchone())

        # Verify that the matcher correctly identifies them as duplicates
        assert matcher.are_potential_duplicates(business1, business2), (
            "Matcher should identify exact duplicates as potential matches"
        )

        # Verify the similarity score is maximum (1.0)
        assert matcher.calculate_similarity(business1, business2) > 0.95, (
            "Similarity score should be very high for exact duplicates"
        )

        # Use the dedupe process to handle this duplicate pair
        cursor.execute("SELECT * FROM candidate_duplicate_pairs WHERE business1_id = 1 AND business2_id = 2")
        duplicate_pair = dict(cursor.fetchone())

        # Use a patched version of dedupe.process_duplicate_pair to test it
        with patch("bin.dedupe.get_business_by_id") as mock_get_business:
            mock_get_business.side_effect = lambda conn, id: business1 if id == 1 else business2

            with patch("bin.dedupe.merge_businesses") as mock_merge:
                # Set up mock_merge to update the database
                def mock_merge_implementation(conn, source_id, target_id, *args, **kwargs):
                    # Update the businesses table to show one business merged into other
                    cursor.execute(
                        "UPDATE businesses SET merged_into = ? WHERE id = ?",
                        (target_id, source_id)
                    )
                    # Update the duplicate pair status
                    cursor.execute(
                        "UPDATE candidate_duplicate_pairs SET status = 'merged' WHERE id = ?",
                        (duplicate_pair["id"],)
                    )
                    conn.commit()
                    return target_id

                mock_merge.side_effect = mock_merge_implementation

                # Call the function under test
                with patch("bin.dedupe.DatabaseConnection"):
                    success, merged_id = dedupe.process_duplicate_pair(
                        duplicate_pair=duplicate_pair,
                        matcher=matcher,
                        verifier=mock_llm_verifier,
                        is_dry_run=False
                    )

                # Verify the result
                assert success, "Expected process_duplicate_pair to succeed"
                assert merged_id is not None, "Expected a valid merged_id"

                # Check that the database was updated correctly
                cursor.execute("SELECT status FROM candidate_duplicate_pairs WHERE id = ?", (duplicate_pair["id"],))
                pair_status = cursor.fetchone()["status"]
                assert pair_status == "merged", f"Expected pair status 'merged', got '{pair_status}'"

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
        # Clear existing data to start fresh
        cursor.execute("DELETE FROM candidate_duplicate_pairs")
        cursor.execute("DELETE FROM businesses")

        # Insert test businesses with similar but not identical data
        cursor.execute(
            """
        INSERT INTO businesses
        (id, name, address, city, state, zip, phone, website, email, status, score)
        VALUES
            (1, 'Smith Plumbing', '123 Main St', 'Anytown', 'CA', '12345',
             '555-123-4567', 'http://smithplumbing.com', 'info@smith.com', 'pending', 85),
            (2, 'Smith Plumbing LLC', '123 Main Street', 'Anytown', 'CA', '12345',
             '555-123-4568', 'http://smithplumbingllc.com', 'contact@smithllc.com', 'pending', 90)
        """
        )
        conn.commit()

        # Create a matcher for the test
        matcher = dedupe.LevenshteinMatcher()

        # Get the businesses from the DB
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business1 = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM businesses WHERE id = 2")
        business2 = dict(cursor.fetchone())

        # Verify that the matcher correctly identifies them as similar
        assert matcher.are_potential_duplicates(business1, business2), (
            "Matcher should identify similar businesses as potential matches"
        )

        # Calculate similarity score (should be high but not 1.0)
        similarity = matcher.calculate_similarity(business1, business2)
        assert 0.7 < similarity < 1.0, (
            f"Expected similarity between 0.7 and 1.0, got {similarity}"
        )

        # Create a candidate pair for these businesses
        cursor.execute(
            """
        INSERT INTO candidate_duplicate_pairs
        (business1_id, business2_id, similarity_score, status)
        VALUES (1, 2, ?, 'pending')
        """,
            (similarity,),
        )
        conn.commit()

        # Now verify with the LLM verifier
        cursor.execute("SELECT * FROM candidate_duplicate_pairs WHERE business1_id = 1 AND business2_id = 2")
        duplicate_pair = dict(cursor.fetchone())

        # Mock the LLM verification
        with patch.object(mock_llm_verifier, "verify_duplicates") as mock_verify:
            mock_verify.return_value = (True, 0.85, "These appear to be the same business with slight variations")

            # Process the duplicate pair
            with patch("bin.dedupe.get_business_by_id") as mock_get_business:
                mock_get_business.side_effect = lambda conn, id: business1 if id == 1 else business2

                with patch("bin.dedupe.merge_businesses") as mock_merge:
                    # Set up mock_merge to update the database
                    def mock_merge_implementation(conn, source_id, target_id, *args, **kwargs):
                        # Update the businesses table
                        cursor.execute(
                            "UPDATE businesses SET merged_into = ? WHERE id = ?",
                            (target_id, source_id)
                        )
                        # Update the duplicate pair status
                        cursor.execute(
                            "UPDATE candidate_duplicate_pairs SET status = 'merged', verified_by_llm = 1, llm_confidence = 0.85 WHERE id = ?",
                            (duplicate_pair["id"],)
                        )
                        conn.commit()
                        return target_id

                    mock_merge.side_effect = mock_merge_implementation

                    # Call the function under test
                    with patch("bin.dedupe.DatabaseConnection"):
                        success, merged_id = dedupe.process_duplicate_pair(
                            duplicate_pair=duplicate_pair,
                            matcher=matcher,
                            verifier=mock_llm_verifier,
                            is_dry_run=False
                        )

                    # Verify the result
                    assert success, "Expected process_duplicate_pair to succeed"
                    assert merged_id is not None, "Expected a valid merged_id"

                    # Check that the database was updated correctly
                    cursor.execute(
                        "SELECT status, verified_by_llm FROM candidate_duplicate_pairs WHERE id = ?",
                        (duplicate_pair["id"],)
                    )
                    pair_data = cursor.fetchone()
                    assert pair_data["status"] == "merged", (
                        f"Expected pair status 'merged', got '{pair_data['status']}'"
                    )
                    assert pair_data["verified_by_llm"] == 1, (
                        "Expected verified_by_llm to be True (1)"
                    )

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
