"""
Pytest configuration and fixtures for testing.
"""

import atexit
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Create a MagicMock object instead of a regular function
mock_track_api_cost = MagicMock(return_value=True)
mock_track_api_cost.__name__ = "mock_track_api_cost"


# Create a mock for the Wappalyzer module
class MockWappalyzer:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, *args, **kwargs):
        return {"technologies": []}

    def analyze_with_categories(self, *args, **kwargs):
        return {"technologies": []}

    @classmethod
    def latest(cls):
        return cls()


class MockWebPage:
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def new_from_url(cls, url, **kwargs):
        return cls()


# Patch the Wappalyzer module
sys.modules["wappalyzer"] = type("wappalyzer", (), {"Wappalyzer": MockWappalyzer, "WebPage": MockWebPage})

# Create directory structure in the module namespace for proper mocking
if 'leadfactory' not in sys.modules:
    sys.modules['leadfactory'] = type('leadfactory', (), {})()
if 'leadfactory.utils' not in sys.modules:
    sys.modules['leadfactory.utils'] = type('utils', (), {})()
if 'leadfactory.utils.io' not in sys.modules:
    sys.modules['leadfactory.utils.io'] = type('io', (), {'track_api_cost': mock_track_api_cost})()

# Direct patch of the module attributes instead of using patch()
sys.modules['leadfactory.utils.io'].track_api_cost = mock_track_api_cost

# Try importing using relative imports for the CI environment
try:
    from leadfactory import utils  # noqa: E402
    # Apply the mock to the imported module
    utils.io.track_api_cost = mock_track_api_cost
except ImportError:
    # In case the above import fails, we'll just use our mock modules defined above
    pass
# Make sure to clean up after tests
atexit.register(patch.stopall)


# Fixture to reset mocks between tests
@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test."""
    mock_track_api_cost.reset_mock()
    yield
    mock_track_api_cost.reset_mock()


@pytest.fixture
def run_mockup_generation(
    mock_gpt4o_client,
    mock_claude_client,
    mock_cost_tracker,
    fixture_high_scoring_business,
):
    """Run the mockup generation process and return the result using an in-memory database."""
    # Mock the API responses with the expected return values
    mock_gpt4o_client.generate_mockup.return_value = (
        "mock_base64_image",  # mockup_image_base64
        "<html>Mock HTML</html>",  # mockup_html
        {"usage": {"total_tokens": 100}},  # usage_data
        None,  # error_message
    )
    mock_claude_client.generate_mockup.return_value = (
        "fallback_base64_image",
        "<html>Fallback HTML</html>",
        {"usage": {"total_tokens": 80}},
        None,
    )
    # Get the business data from the fixture
    business = fixture_high_scoring_business
    # Create an in-memory SQLite database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    try:
        # Create the businesses table with the correct schema
        cursor.execute(
            """
            CREATE TABLE businesses (
                id INTEGER PRIMARY KEY,
                name TEXT,
                website TEXT,
                location_data TEXT,
                mockup_data TEXT,
                mockup_generated BOOLEAN DEFAULT 0,
                tier INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        # Create the mockups table
        cursor.execute(
            """
            CREATE TABLE mockups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                mockup_data TEXT NOT NULL,
                mockup_url TEXT,
                mockup_html TEXT,
                usage_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES businesses (id)
            )
        """
        )
        # Insert the test business
        cursor.execute(
            """
            INSERT INTO businesses (id, name, website, location_data, mockup_generated, tier)
            VALUES (?, ?, ?, ?, 0, 3)
        """,
            (
                business["id"],
                business.get("name", "Test Business"),
                business.get("website", "https://example.com"),
                business.get("location_data", '{"state": "CA", "city": "San Francisco"}'),
            ),
        )
        conn.commit()
        # Call the generate_business_mockup function directly
        from bin.mockup import generate_business_mockup

        # Patch the DatabaseConnection to use our test connection
        with (
            patch("bin.mockup.DatabaseConnection") as mock_db_conn,
            patch("leadfactory.utils.e2e_db_connector.db_connection") as io_db_conn,
        ):
            # Configure the mocks to use our in-memory cursor
            mock_db_conn.return_value.__enter__.return_value = cursor
            io_db_conn.return_value.__enter__.return_value = cursor
            # Generate the mockup
            result = generate_business_mockup(
                business,
                tier=3,  # High tier for high-scoring business
                style="modern",
                resolution="1024x1024",
            )
            # Commit any changes made during the test
            conn.commit()
            # Return the result and database connection for assertions
            return result, conn, cursor
    except Exception as e:
        conn.rollback()
        raise e
