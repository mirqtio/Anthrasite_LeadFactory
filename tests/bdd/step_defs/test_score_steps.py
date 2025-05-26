"""
BDD step definitions for the scoring functionality feature.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, when, then, parsers, scenarios

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Import the modules being tested
from leadfactory.pipeline import score

# Import shared steps to ensure 'the database is initialized' step is available
from tests.bdd.step_defs.shared_steps import initialize_database

# Load the scenarios from the feature file
scenarios('../features/pipeline_stages.feature')


@pytest.fixture
def score_db_conn():
    """Fixture for an in-memory test database for scoring tests."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create businesses table
    cursor.execute(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT,
            tech_stack TEXT,
            performance TEXT,
            contact_info TEXT,
            score INTEGER,
            score_details TEXT
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def business_with_enriched_info(score_db_conn):
    """Set up a business with enriched information."""
    cursor = score_db_conn.cursor()

    # Insert a business with enriched information
    cursor.execute(
        """
        INSERT INTO businesses (
            name,
            website,
            tech_stack,
            performance,
            contact_info
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Test Business",
            "https://example.com",
            json.dumps({
                "cms": "WordPress",
                "analytics": "Google Analytics",
                "server": "Nginx",
                "javascript": "React"
            }),
            json.dumps({
                "page_speed": 85,
                "mobile_friendly": True,
                "accessibility": 90
            }),
            json.dumps({
                "name": "John Doe",
                "position": "CEO",
                "email": "john@example.com"
            })
        )
    )
    score_db_conn.commit()

    cursor.execute("SELECT id FROM businesses ORDER BY id DESC LIMIT 1")
    business_id = cursor.fetchone()[0]
    return {"score_db_conn": score_db_conn, "business_id": business_id}


# Given step implementation
@given("a business exists with enriched information")
def business_exists_with_enriched_info(business_with_enriched_info):
    """A business exists with enriched information."""
    return business_with_enriched_info


# When step implementation
@when("I score the business")
def score_the_business(business_with_enriched_info):
    """Score the business."""
    db_conn = business_with_enriched_info["score_db_conn"]
    business_id = business_with_enriched_info["business_id"]

    # Call the scoring function
    result = score.score_business(db_conn, business_id)

    # Store the result for later assertions
    business_with_enriched_info["score_result"] = result
    return business_with_enriched_info


# Then step implementations
@then(parsers.parse("the business should have a score between {min:d} and {max:d}"))
def check_score_range(business_with_enriched_info, min, max):
    """Check that the business has a score within the expected range."""
    db_conn = business_with_enriched_info["score_db_conn"]
    business_id = business_with_enriched_info["business_id"]

    cursor = db_conn.cursor()
    cursor.execute("SELECT score FROM businesses WHERE id = ?", (business_id,))
    score_value = cursor.fetchone()[0]

    assert score_value is not None, "Score should not be None"
    assert min <= score_value <= max, f"Score {score_value} should be between {min} and {max}"


@then("the score details should include component scores")
def check_score_details(business_with_enriched_info):
    """Check that score details include component scores."""
    db_conn = business_with_enriched_info["score_db_conn"]
    business_id = business_with_enriched_info["business_id"]

    cursor = db_conn.cursor()
    cursor.execute("SELECT score_details FROM businesses WHERE id = ?", (business_id,))
    score_details_json = cursor.fetchone()[0]

    assert score_details_json is not None, "Score details should not be None"

    # Parse the JSON score details
    score_details = json.loads(score_details_json)

    # Verify component scores exist
    assert "tech_stack_score" in score_details, "Score details should include tech_stack_score"
    assert "performance_score" in score_details, "Score details should include performance_score"
    assert "contact_info_score" in score_details, "Score details should include contact_info_score"
    assert "total_score" in score_details, "Score details should include total_score"


@then("businesses with better tech stacks should score higher")
def compare_tech_stack_scores(business_with_enriched_info):
    """Check that businesses with better tech stacks score higher."""
    db_conn = business_with_enriched_info["score_db_conn"]
    business_id = business_with_enriched_info["business_id"]

    cursor = db_conn.cursor()

    # Get the current score
    cursor.execute("SELECT score FROM businesses WHERE id = ?", (business_id,))
    original_score = cursor.fetchone()[0]

    # Insert a business with a minimal tech stack
    cursor.execute(
        """
        INSERT INTO businesses (
            name,
            website,
            tech_stack,
            performance,
            contact_info
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Minimal Tech Business",
            "https://minimal.com",
            json.dumps({"cms": "Basic CMS"}),  # Minimal tech stack
            json.dumps({
                "page_speed": 85,
                "mobile_friendly": True,
                "accessibility": 90
            }),  # Same performance as original
            json.dumps({
                "name": "Jane Smith",
                "position": "CEO",
                "email": "jane@minimal.com"
            })  # Similar contact info
        )
    )
    db_conn.commit()

    minimal_id = cursor.lastrowid

    # Score the new business
    minimal_score_result = score.score_business(db_conn, minimal_id)

    # Get the updated score from the database
    cursor.execute("SELECT score FROM businesses WHERE id = ?", (minimal_id,))
    minimal_score = cursor.fetchone()[0]

    # The business with more tech stack items should have a higher score
    assert original_score > minimal_score, f"Business with better tech stack ({original_score}) should score higher than business with minimal tech stack ({minimal_score})"


@then("businesses with better performance should score higher")
def compare_performance_scores(business_with_enriched_info):
    """Check that businesses with better performance score higher."""
    db_conn = business_with_enriched_info["score_db_conn"]
    business_id = business_with_enriched_info["business_id"]

    cursor = db_conn.cursor()

    # Get the current score
    cursor.execute("SELECT score FROM businesses WHERE id = ?", (business_id,))
    original_score = cursor.fetchone()[0]

    # Insert a business with poor performance
    cursor.execute(
        """
        INSERT INTO businesses (
            name,
            website,
            tech_stack,
            performance,
            contact_info
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Poor Performance Business",
            "https://poorperf.com",
            json.dumps({
                "cms": "WordPress",
                "analytics": "Google Analytics",
                "server": "Nginx",
                "javascript": "React"
            }),  # Same tech stack as original
            json.dumps({
                "page_speed": 30,  # Poor page speed
                "mobile_friendly": False,  # Not mobile friendly
                "accessibility": 40  # Poor accessibility
            }),
            json.dumps({
                "name": "Bob Johnson",
                "position": "CEO",
                "email": "bob@poorperf.com"
            })  # Similar contact info
        )
    )
    db_conn.commit()

    poor_perf_id = cursor.lastrowid

    # Score the new business
    poor_perf_score_result = score.score_business(db_conn, poor_perf_id)

    # Get the updated score from the database
    cursor.execute("SELECT score FROM businesses WHERE id = ?", (poor_perf_id,))
    poor_perf_score = cursor.fetchone()[0]

    # The business with better performance should have a higher score
    assert original_score > poor_perf_score, f"Business with better performance ({original_score}) should score higher than business with poor performance ({poor_perf_score})"
