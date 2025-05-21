"""
BDD tests for the lead scoring (04_score.py)
"""
import os
import sys
import yaml
import pytest
import tempfile
import sqlite3
from pathlib import Path
from pytest_bdd import scenario, given, when, then
from unittest.mock import patch, MagicMock, mock_open
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Now we can import project modules
from utils.io import DatabaseConnection  # noqa: E402
# Feature file path
FEATURE_FILE = os.path.join(os.path.dirname(__file__), "features/scoring.feature")
# Create a feature file if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "features"), exist_ok=True)
if not os.path.exists(FEATURE_FILE):
    with open(FEATURE_FILE, "w") as f:
        f.write(
            """
Feature: Lead Scoring
  As a lead generation system
  I want to score leads based on various criteria
  So that I can prioritize high-value leads
  Scenario: Score a business based on tech stack
    Given a business with a modern tech stack
    When the scoring process runs
    Then the business should receive a high tech score
  Scenario: Score a business based on performance metrics
    Given a business with good performance metrics
    When the scoring process runs
    Then the business should receive a high performance score
  Scenario: Score a business based on location
    # Base (50) * 1.5 (healthcare) * 1.2 (multiple locations) = 90
    Given a business in a target location
    When the scoring process runs
    Then the business should receive a high location score
  Scenario: Handle missing data
    Given a business with incomplete data
    When the scoring process runs
    Then the business should receive default scores for missing data
  Scenario: Apply rule weights
    Given a business with mixed scores
    When the scoring process runs with rule weights
    Then the final score should reflect the weighted rules
"""
        )
# Load the scenarios from the feature file
scenarios(FEATURE_FILE)
# Fixtures
@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create a temporary file for the database
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    # Create the database schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            website TEXT,
            email TEXT,
            vertical TEXT,
            score REAL DEFAULT 0,
            tech_score REAL DEFAULT 0,
            performance_score REAL DEFAULT 0,
            location_score REAL DEFAULT 0,
            tech_stack TEXT,
            performance_metrics TEXT,
            enriched_at TIMESTAMP,
            scored_at TIMESTAMP,
            mockup_generated INTEGER DEFAULT 0,
            mockup_retry_count INTEGER DEFAULT 0,
            mockup_data TEXT,
            email_sent INTEGER DEFAULT 0,
            email_retry_count INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()
    # Return the path to the database
    yield db_path
    # Clean up the temporary file
    os.unlink(db_path)
# Given steps
@given("a business with a modern tech stack")
def business_with_modern_tech_stack(temp_db):
    """Create a business with a modern tech stack."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, website, vertical,
            tech_stack
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Modern Tech Co",
            "123 Tech St",
            "San Francisco",
            "CA",
            "94105",
            "555-123-4567",
            "https://moderntechco.com",
            "technology",
            '{"frameworks": ["React", "Node.js"], "cms": "Headless", "hosting": "AWS"}',
        ),
    )
    conn.commit()
    conn.close()
    return temp_db
@given("a business with good performance metrics")
def business_with_good_performance(temp_db):
    """Create a business with good performance metrics."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, website, vertical,
            performance_metrics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Fast Site Inc",
            "456 Speed Ave",
            "Austin",
            "TX",
            "78701",
            "555-987-6543",
            "https://fastsiteinc.com",
            "technology",
            '{"lighthouse": 95, "pagespeed": 92, "fcp": 1.2, "lcp": 2.1}',
        ),
    )
    conn.commit()
    conn.close()
    return temp_db
@given("a business in a target location")
def business_in_target_location(temp_db):
    """Create a business in a target location."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, website, vertical
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Target Location Biz",
            "789 Prime St",
            "New York",
            "NY",
            "10001",
            "555-555-5555",
            "https://targetlocationbiz.com",
            "retail",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db
@given("a business with incomplete data")
def business_with_incomplete_data(temp_db):
    """Create a business with incomplete data."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, vertical
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Incomplete Data LLC",
            "321 Missing Info Rd",
            "Chicago",
            "IL",
            "60601",
            "555-111-2222",
            "services",
        ),
    )
    conn.commit()
    conn.close()
    return temp_db
@given("a business with mixed scores")
def business_with_mixed_scores(temp_db):
    """Create a business with mixed scores."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, website, vertical,
            tech_stack, performance_metrics
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Mixed Scores Co",
            "555 Balance Blvd",
            "Denver",
            "CO",
            "80202",
            "555-444-3333",
            "https://mixedscoresco.com",
            "consulting",
            '{"frameworks": ["WordPress"], "cms": "WordPress", "hosting": "Shared"}',
            '{"lighthouse": 65, "pagespeed": 70, "fcp": 2.8, "lcp": 4.2}',
        ),
    )
    conn.commit()
    conn.close()
    return temp_db
# When steps
@when("the scoring process runs")
def scoring_process_runs(temp_db):
    """Run the scoring process."""
    # Mock the scoring process
    with patch("bin.score.DatabaseConnection") as mock_db:
        # Configure the mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        # Run the scoring process
        from bin import score
        score.main()
@when("the scoring process runs with rule weights")
def scoring_process_runs_with_weights(temp_db):
    """Run the scoring process with rule weights."""
    # Mock the scoring process with weights
    with patch("bin.score.DatabaseConnection") as mock_db, patch(
        "bin.score.load_rules"
    ) as mock_load_rules:
        # Configure the mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        # Mock the rules with weights
        mock_load_rules.return_value = {
            "tech_stack": {"weight": 0.5, "rules": []},
            "performance": {"weight": 0.3, "rules": []},
            "location": {"weight": 0.2, "rules": []},
        }
        # Run the scoring process
        from bin import score
        score.main()
# Then steps
@then("the business should receive a high tech score")
def high_tech_score(temp_db):
    """Verify that the business received a high tech score."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT tech_score FROM businesses WHERE name = 'Modern Tech Co'")
    score = cursor.fetchone()[0]
    conn.close()
    assert score > 0.7, f"Tech score {score} is not high enough"
@then("the business should receive a high performance score")
def high_performance_score(temp_db):
    """Verify that the business received a high performance score."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT performance_score FROM businesses WHERE name = 'Fast Site Inc'"
    )
    score = cursor.fetchone()[0]
    conn.close()
    assert score > 0.7, f"Performance score {score} is not high enough"
@then("the business should receive a high location score")
def high_location_score(temp_db):
    """Verify that the business received a high location score."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT location_score FROM businesses WHERE name = 'Target Location Biz'"
    )
    score = cursor.fetchone()[0]
    conn.close()
    assert score > 0.7, f"Location score {score} is not high enough"
@then("the business should receive default scores for missing data")
def default_scores_for_missing_data(temp_db):
    """Verify that the business received default scores for missing data."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tech_score, performance_score
        FROM businesses
        WHERE name = 'Incomplete Data LLC'
        """
    )
    tech_score, performance_score = cursor.fetchone()
    conn.close()
    assert (
        tech_score == 0 and performance_score == 0
    ), "Default scores were not applied correctly"
@then("the final score should reflect the weighted rules")
def weighted_final_score(temp_db):
    """Verify that the final score reflects the weighted rules."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tech_score, performance_score, location_score, score
        FROM businesses
        WHERE name = 'Mixed Scores Co'
        """
    )
    tech_score, performance_score, location_score, final_score = cursor.fetchone()
    conn.close()
    # Calculate the expected weighted score
    expected_score = (
        tech_score * 0.5 + performance_score * 0.3 + location_score * 0.2
    )
    assert (
        abs(final_score - expected_score) < 0.01
    ), (f"Final score {final_score} does not match expected "
        f"weighted score {expected_score}")