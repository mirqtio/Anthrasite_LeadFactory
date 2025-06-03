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

# Make sure to clean up after tests
atexit.register(patch.stopall)


@pytest.fixture
def pipeline_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

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
            score REAL DEFAULT 0.0,
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

    conn.commit()
    yield conn
    conn.close()


# Fixture to reset mocks between tests
@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test."""
    mock_track_api_cost.reset_mock()
    yield
    mock_track_api_cost.reset_mock()
