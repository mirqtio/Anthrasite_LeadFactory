"""
Unit tests for the score module.
"""

import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from leadfactory.pipeline import score


@pytest.fixture
def mock_db():
    """Create an in-memory SQLite database for testing."""
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

    # Insert test data
    cursor.execute(
        """
        INSERT INTO businesses (id, name, website, tech_stack, performance, contact_info)
        VALUES (
            1,
            'Test Business',
            'https://example.com',
            '{"cms": "WordPress", "analytics": "Google Analytics"}',
            '{"page_speed": 70, "mobile_friendly": true}',
            '{"name": "John Doe", "position": "CEO"}'
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


def test_score_business(mock_db):
    """Test the main business scoring function."""
    # Call the function
    result = score.score_business(mock_db, 1)

    # Verify the result
    assert isinstance(result, int)
    assert result > 0  # Score should be positive

    # Verify the database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT score, score_details FROM businesses WHERE id = 1")
    business = cursor.fetchone()

    assert business[0] == result  # Score in DB matches returned score
    assert business[1] is not None  # Score details were saved

    # Verify score details format
    score_details = json.loads(business[1])
    assert "tech_stack_score" in score_details
    assert "performance_score" in score_details
    assert "total_score" in score_details


def test_calculate_tech_stack_score():
    """Test calculation of tech stack score component."""
    # Test with good tech stack
    tech_stack = {
        "cms": "WordPress",
        "analytics": "Google Analytics",
        "server": "Nginx",
        "javascript": "React",
    }

    score_result = score.calculate_tech_stack_score(tech_stack)

    assert isinstance(score_result, dict)
    assert "score" in score_result
    assert score_result["score"] > 0
    assert "details" in score_result

    # Test with minimal tech stack
    minimal_stack = {"cms": "WordPress"}

    minimal_score = score.calculate_tech_stack_score(minimal_stack)

    assert minimal_score["score"] < score_result["score"]

    # Test with empty tech stack
    empty_score = score.calculate_tech_stack_score({})

    assert empty_score["score"] == 0


def test_calculate_performance_score():
    """Test calculation of performance score component."""
    # Test with good performance
    performance = {"page_speed": 90, "mobile_friendly": True, "accessibility": 85}

    score_result = score.calculate_performance_score(performance)

    assert isinstance(score_result, dict)
    assert "score" in score_result
    assert score_result["score"] > 0
    assert "details" in score_result

    # Test with poor performance
    poor_performance = {"page_speed": 40, "mobile_friendly": False, "accessibility": 30}

    poor_score = score.calculate_performance_score(poor_performance)

    assert poor_score["score"] < score_result["score"]

    # Test with empty performance data
    empty_score = score.calculate_performance_score({})

    assert empty_score["score"] == 0


def test_calculate_contact_info_score():
    """Test calculation of contact info score component."""
    # Test with complete contact info
    contact_info = {
        "name": "John Doe",
        "position": "CEO",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "linkedin": "https://linkedin.com/in/johndoe",
    }

    score_result = score.calculate_contact_info_score(contact_info)

    assert isinstance(score_result, dict)
    assert "score" in score_result
    assert score_result["score"] > 0
    assert "details" in score_result

    # Test with minimal contact info
    minimal_info = {"name": "John Doe"}

    minimal_score = score.calculate_contact_info_score(minimal_info)

    assert minimal_score["score"] < score_result["score"]

    # Test with empty contact info
    empty_score = score.calculate_contact_info_score({})

    assert empty_score["score"] == 0


def test_weighted_scoring():
    """Test that scoring uses proper weights for different components."""
    # Create component scores
    tech_score = {"score": 80, "details": {}}
    perf_score = {"score": 60, "details": {}}
    contact_score = {"score": 40, "details": {}}

    # Call the weighted scoring function
    with (
        patch("bin.score.calculate_tech_stack_score") as mock_tech,
        patch("bin.score.calculate_performance_score") as mock_perf,
        patch("bin.score.calculate_contact_info_score") as mock_contact,
    ):
        mock_tech.return_value = tech_score
        mock_perf.return_value = perf_score
        mock_contact.return_value = contact_score

        # Test with mock DB
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE businesses (id INTEGER PRIMARY KEY, tech_stack TEXT, performance TEXT, contact_info TEXT)"
        )
        cursor.execute("INSERT INTO businesses VALUES (1, '{}', '{}', '{}')")
        conn.commit()

        # Get the final score
        final_score = score.score_business(conn, 1)

        # Verify weights are applied
        # This assumes some weights are applied, actual formula may vary
        assert final_score != (
            tech_score["score"] + perf_score["score"] + contact_score["score"]
        )

        conn.close()


def test_error_handling(mock_db):
    """Test error handling during scoring."""
    # Test with invalid business ID
    result = score.score_business(mock_db, 999)

    # Should return a default score or error indicator
    assert result == 0 or result is None

    # Test with invalid data in business record
    cursor = mock_db.cursor()
    cursor.execute("UPDATE businesses SET tech_stack = 'invalid json' WHERE id = 1")
    mock_db.commit()

    # Should handle the error gracefully
    result = score.score_business(mock_db, 1)

    # Should return a score based on remaining valid data
    assert isinstance(result, int)
    assert result >= 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
