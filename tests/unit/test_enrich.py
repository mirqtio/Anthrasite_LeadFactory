"""
Unit tests for the enrich module.
"""

import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from leadfactory.pipeline import enrich


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
            email TEXT,
            phone TEXT,
            tech_stack TEXT,
            performance TEXT,
            contact_info TEXT,
            enriched_at TIMESTAMP
        )
        """
    )

    # Create features table
    cursor.execute(
        """
        CREATE TABLE features (
            id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            tech_stack TEXT,
            page_speed INTEGER,
            screenshot_url TEXT,
            semrush_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        )
        """
    )

    # Insert test data
    cursor.execute(
        """
        INSERT INTO businesses (id, name, website)
        VALUES (1, 'Test Business', 'https://example.com')
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_apis():
    """Mock all external APIs used in the enrichment process."""
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post, \
         patch("utils.io.track_api_cost") as mock_track_cost:

        # Configure mock responses
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "data": {
                "email": "contact@example.com",
                "phone": "555-123-4567",
                "contact_info": json.dumps({
                    "first_name": "John",
                    "last_name": "Doe",
                    "position": "CEO"
                })
            }
        }
        mock_get.return_value = mock_get_response

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "tech_stack": json.dumps({
                "cms": "WordPress",
                "analytics": "Google Analytics",
                "server": "Nginx"
            }),
            "performance": json.dumps({
                "page_speed": 85,
                "mobile_friendly": True
            })
        }
        mock_post.return_value = mock_post_response

        yield {
            "get": mock_get,
            "post": mock_post,
            "track_cost": mock_track_cost
        }


def test_enrich_business(mock_db, mock_apis):
    """Test the business enrichment function."""
    # Call the function
    result = enrich.enrich_business(mock_db, 1)

    # Verify API calls were made
    assert mock_apis["get"].called
    assert mock_apis["post"].called

    # Verify the result
    assert result is True

    # Verify the database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT email, phone, tech_stack, performance, enriched_at FROM businesses WHERE id = 1")
    business = cursor.fetchone()

    assert business[0] == "contact@example.com"
    assert business[1] == "555-123-4567"
    assert "WordPress" in business[2]
    assert "page_speed" in business[3]
    assert business[4] is not None  # enriched_at timestamp


def test_enrich_tech_stack(mock_db, mock_apis):
    """Test the tech stack enrichment function."""
    # Configure mock to return specific tech stack data
    mock_apis["post"].return_value.json.return_value = {
        "technologies": [
            {"name": "WordPress", "categories": ["CMS"]},
            {"name": "Google Analytics", "categories": ["Analytics"]},
            {"name": "Nginx", "categories": ["Web Server"]}
        ]
    }

    # Call the function
    result = enrich.enrich_tech_stack(mock_db, 1, "https://example.com")

    # Verify API call was made
    assert mock_apis["post"].called

    # Verify the result
    assert result is not None
    assert "WordPress" in result

    # Verify the database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT tech_stack FROM businesses WHERE id = 1")
    tech_stack = cursor.fetchone()[0]

    assert "WordPress" in tech_stack
    assert "Nginx" in tech_stack


def test_enrich_contact_info(mock_db, mock_apis):
    """Test the contact info enrichment function."""
    # Configure mock to return specific contact data
    contact_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-123-4567",
        "title": "CEO"
    }
    mock_apis["get"].return_value.json.return_value = {"data": contact_data}

    # Call the function
    result = enrich.enrich_contact_info(mock_db, 1, "Test Business")

    # Verify API call was made
    assert mock_apis["get"].called

    # Verify the result
    assert result is not None
    assert "John Doe" in result

    # Verify the database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT contact_info FROM businesses WHERE id = 1")
    contact_info = cursor.fetchone()[0]

    assert "John" in contact_info
    assert "CEO" in contact_info


def test_enrich_performance_data(mock_db, mock_apis):
    """Test the performance data enrichment function."""
    # Configure mock to return specific performance data
    performance_data = {
        "page_speed": 85,
        "mobile_score": 90,
        "accessibility": 75
    }
    mock_apis["post"].return_value.json.return_value = {"data": performance_data}

    # Call the function
    result = enrich.enrich_performance_data(mock_db, 1, "https://example.com")

    # Verify API call was made
    assert mock_apis["post"].called

    # Verify the result
    assert result is not None
    assert "page_speed" in result

    # Verify the database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT performance FROM businesses WHERE id = 1")
    performance = cursor.fetchone()[0]

    assert "page_speed" in performance
    assert "mobile_score" in performance


def test_error_handling(mock_db, mock_apis):
    """Test error handling during enrichment."""
    # Configure mock to raise an exception
    mock_apis["get"].side_effect = Exception("API Error")

    # Call the function and verify it handles the error
    result = enrich.enrich_business(mock_db, 1)

    # Function should return False on error
    assert result is False

    # Verify the database was not updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT enriched_at FROM businesses WHERE id = 1")
    enriched_at = cursor.fetchone()[0]

    assert enriched_at is None


if __name__ == "__main__":
    pytest.main(["-v", __file__])
