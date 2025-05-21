"""
Step definitions for the lead deduplication feature tests.
"""

import sqlite3
from unittest.mock import patch

import pytest
from pytest_bdd import given, scenario, then, when

from bin import dedupe


# Scenarios
@scenario("../features/deduplication.feature", "Identify exact duplicate businesses")
def test_identify_exact_duplicates():
    """Test identifying exact duplicate businesses."""
    pass


@scenario(
    "../features/deduplication.feature",
    "Identify similar businesses with fuzzy matching",
)
def test_identify_similar_businesses():
    """Test identifying similar businesses with fuzzy matching."""
    pass


@scenario(
    "../features/deduplication.feature",
    "Handle businesses with different addresses but same name",
)
def test_handle_different_addresses():
    """Test handling businesses with different addresses but same name."""
    pass


@scenario("../features/deduplication.feature", "Handle API errors gracefully")
def test_handle_api_errors():
    """Test handling API errors gracefully."""
    pass


@scenario("../features/deduplication.feature", "Skip already processed businesses")
def test_skip_processed_businesses():
    """Test skipping already processed businesses."""
    pass


# Fixtures
@pytest.fixture
def mock_db():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    # Create tables
    cursor.executescript(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            website TEXT,
            phone TEXT,
            email TEXT,
            score REAL DEFAULT 0.0,
            processed INTEGER DEFAULT 0
        );
        CREATE TABLE candidate_duplicate_pairs (
            id INTEGER PRIMARY KEY,
            business_id_1 INTEGER,
            business_id_2 INTEGER,
            similarity_score REAL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (business_id_1) REFERENCES businesses(id),
            FOREIGN KEY (business_id_2) REFERENCES businesses(id)
        );
    """
    )
    conn.commit()
    yield conn, cursor
    conn.close()


@pytest.fixture
def mock_llm():
    """Mock LLM API used for verification."""
    with patch("bin.dedupe.verify_with_llm") as mock_verify:
        # Default to confirming duplicates
        mock_verify.return_value = (True, "These appear to be the same business.")
        yield mock_verify


# Given steps
@given("the database is initialized")
def db_initialized(mock_db):
    """Ensure the database is initialized."""
    conn, cursor = mock_db
    return conn, cursor


@given("the API keys are configured")
def api_keys_configured(monkeypatch):
    """Configure API keys for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    return True


@given("multiple businesses with identical names and addresses")
def exact_duplicate_businesses(mock_db):
    """Create test businesses with identical names and addresses."""
    conn, cursor = mock_db
    # Insert exact duplicates
    businesses = [
        (
            "Acme Corp",
            "123 Main St, New York, NY",
            "https://acme.com",
            "555-1234",
            "info@acme.com",
            0.8,
        ),
        (
            "Acme Corp",
            "123 Main St, New York, NY",
            "https://acme-corp.com",
            "555-5678",
            "contact@acme.com",
            0.6,
        ),
    ]
    for name, address, website, phone, email, score in businesses:
        cursor.execute(
            """
            INSERT INTO businesses (name, address, website, phone, email, score)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (name, address, website, phone, email, score),
        )
    conn.commit()
    return businesses


@given("multiple businesses with similar names and addresses")
def similar_businesses(mock_db):
    """Create test businesses with similar names and addresses."""
    conn, cursor = mock_db
    # Insert similar businesses
    businesses = [
        (
            "Acme Corporation",
            "123 Main Street, New York, NY",
            "https://acme.com",
            "555-1234",
            "info@acme.com",
            0.8,
        ),
        (
            "ACME Corp.",
            "123 Main St, New York, NY",
            "https://acme-corp.com",
            "555-5678",
            "contact@acme.com",
            0.6,
        ),
        (
            "Acme Inc",
            "123 Main Street, New York, NY 10001",
            "https://acmeinc.com",
            "555-9012",
            "hello@acmeinc.com",
            0.7,
        ),
    ]
    for name, address, website, phone, email, score in businesses:
        cursor.execute(
            """
            INSERT INTO businesses (name, address, website, phone, email, score)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (name, address, website, phone, email, score),
        )
    conn.commit()
    return businesses


@given("multiple businesses with same name but different addresses")
def same_name_different_addresses(mock_db):
    """Create test businesses with same name but different addresses."""
    conn, cursor = mock_db
    # Insert businesses with same name but different addresses
    businesses = [
        (
            "Starbucks Coffee",
            "123 Main St, New York, NY",
            "https://starbucks.com",
            "555-1234",
            "ny@starbucks.com",
            0.8,
        ),
        (
            "Starbucks Coffee",
            "456 Oak Ave, Boston, MA",
            "https://starbucks.com",
            "555-5678",
            "boston@starbucks.com",
            0.7,
        ),
    ]
    for name, address, website, phone, email, score in businesses:
        cursor.execute(
            """
            INSERT INTO businesses (name, address, website, phone, email, score)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (name, address, website, phone, email, score),
        )
    conn.commit()
    return businesses


@given("the LLM verification API is unavailable")
def llm_api_unavailable(mock_llm):
    """Simulate an unavailable LLM API."""
    mock_llm.side_effect = Exception("API Error: Service unavailable")
    return mock_llm


@given("multiple businesses that have already been processed for deduplication")
def processed_businesses(mock_db):
    """Create test businesses that have already been processed for deduplication."""
    conn, cursor = mock_db
    # Insert processed businesses
    businesses = [
        (
            "Processed Corp",
            "123 Main St, New York, NY",
            "https://processed.com",
            "555-1234",
            "info@processed.com",
            0.8,
            1,
        ),
        (
            "Another Processed",
            "456 Oak Ave, Boston, MA",
            "https://another.com",
            "555-5678",
            "info@another.com",
            0.7,
            1,
        ),
    ]
    for name, address, website, phone, email, score, processed in businesses:
        cursor.execute(
            """
            INSERT INTO businesses (name, address, website, phone, email, score, processed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (name, address, website, phone, email, score, processed),
        )
    conn.commit()
    return businesses


# When steps
@when("I run the deduplication process")
def run_deduplication(mock_db, mock_llm):
    """Run the deduplication process."""
    conn, cursor = mock_db
    # Mock the database connection
    with patch("utils.io.DatabaseConnection") as mock_db_conn:
        mock_db_conn.return_value.__enter__.return_value = cursor
        # Run the deduplication process
        dedupe.find_exact_duplicates()
        dedupe.process_duplicate_candidates()
        return conn, cursor


@when("I run the deduplication process with fuzzy matching")
def run_deduplication_fuzzy(mock_db, mock_llm):
    """Run the deduplication process with fuzzy matching."""
    conn, cursor = mock_db
    # Mock the database connection
    with patch("utils.io.DatabaseConnection") as mock_db_conn:
        mock_db_conn.return_value.__enter__.return_value = cursor
        # Run the deduplication process with fuzzy matching
        dedupe.find_fuzzy_duplicates()
        dedupe.process_duplicate_candidates()
        return conn, cursor


# Then steps
@then("the duplicate businesses should be identified")
def duplicates_identified(mock_db):
    """Verify duplicate businesses are identified."""
    conn, cursor = mock_db
    cursor.execute("SELECT COUNT(*) FROM candidate_duplicate_pairs")
    count = cursor.fetchone()[0]
    assert count > 0, "No duplicate pairs were identified"


@then("the duplicate businesses should be merged")
def duplicates_merged(mock_db):
    """Verify duplicate businesses are merged."""
    conn, cursor = mock_db
    # Check if any businesses were marked as merged
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE processed = 1")
    count = cursor.fetchone()[0]
    assert count > 0, "No businesses were marked as processed after merging"


@then("the merged business should retain the highest score")
def merged_business_highest_score(mock_db):
    """Verify the merged business retains the highest score."""
    conn, cursor = mock_db
    # Get the highest score from the original businesses
    cursor.execute("SELECT MAX(score) FROM businesses")
    highest_score = cursor.fetchone()[0]
    # Get the score of the merged business
    cursor.execute("SELECT score FROM businesses WHERE processed = 1 LIMIT 1")
    merged_score = cursor.fetchone()[0]
    assert (
        merged_score >= highest_score
    ), "Merged business does not have the highest score"


@then("the merged business should have all contact information")
def merged_business_all_contact_info(mock_db):
    """Verify the merged business has all contact information."""
    conn, cursor = mock_db
    # Get the merged business
    cursor.execute("SELECT * FROM businesses WHERE processed = 1 LIMIT 1")
    merged_business = cursor.fetchone()
    # Check if it has non-empty contact information
    assert merged_business[3] is not None, "Merged business has no website"
    assert merged_business[4] is not None, "Merged business has no phone"
    assert merged_business[5] is not None, "Merged business has no email"


@then("the similar businesses should be identified")
def similar_businesses_identified(mock_db):
    """Verify similar businesses are identified."""
    conn, cursor = mock_db
    cursor.execute("SELECT COUNT(*) FROM candidate_duplicate_pairs")
    count = cursor.fetchone()[0]
    assert count > 0, "No similar business pairs were identified"


@then("the similar businesses should be verified with LLM")
def similar_businesses_verified(mock_llm):
    """Verify similar businesses are verified with LLM."""
    assert mock_llm.called, "LLM verification was not called"


@then("the confirmed duplicates should be merged")
def confirmed_duplicates_merged(mock_db):
    """Verify confirmed duplicates are merged."""
    conn, cursor = mock_db
    # Check if any businesses were marked as merged
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE processed = 1")
    count = cursor.fetchone()[0]
    assert count > 0, "No businesses were marked as processed after merging"


@then("the businesses should be flagged for manual review")
def businesses_flagged_for_review(mock_db):
    """Verify businesses are flagged for manual review."""
    conn, cursor = mock_db
    cursor.execute(
        "SELECT COUNT(*) FROM candidate_duplicate_pairs WHERE status = 'review'"
    )
    count = cursor.fetchone()[0]
    assert count > 0, "No businesses were flagged for manual review"


@then("the businesses should not be automatically merged")
def businesses_not_automatically_merged(mock_db):
    """Verify businesses are not automatically merged."""
    conn, cursor = mock_db
    # Check that no businesses were processed as a result of merging
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE processed = 1")
    count = cursor.fetchone()[0]
    assert (
        count == 0
    ), "Businesses were automatically merged when they should not have been"


@then("the process should continue to the next set of businesses")
def process_continues_to_next_set():
    """Verify the process continues to the next set of businesses."""
    # If we've reached this point, the process didn't stop
    pass


@then("the error should be logged")
def error_logged(caplog):
    """Verify the error is logged."""
    assert any("error" in record.message.lower() for record in caplog.records)


@then("the process should continue without crashing")
def process_continues_without_crashing():
    """Verify the process continues without crashing."""
    # If we've reached this point, the process didn't crash
    pass


@then("the businesses should be skipped")
def businesses_skipped(mock_db):
    """Verify the businesses are skipped."""
    conn, cursor = mock_db
    # Check that processed businesses were not included in candidate pairs
    cursor.execute(
        """
        SELECT COUNT(*) FROM candidate_duplicate_pairs cdp
        JOIN businesses b1 ON cdp.business_id_1 = b1.id
        JOIN businesses b2 ON cdp.business_id_2 = b2.id
        WHERE b1.processed = 1 OR b2.processed = 1
    """
    )
    count = cursor.fetchone()[0]
    assert count == 0, "Processed businesses were not skipped"


@then("the deduplication process should continue to the next set")
def deduplication_continues_to_next_set():
    """Verify the deduplication process continues to the next set."""
    # If we've reached this point, the process didn't stop
    pass
