#!/usr/bin/env python3
"""
BDD tests for the lead scraper (scrape.py)
"""
import os
import sqlite3
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest


@contextmanager
def db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Test fixtures
@pytest.fixture
def target_zip_code() -> str:
    """Return a test ZIP code."""
    return "10002"


@pytest.fixture
def target_vertical() -> dict[str, Any]:
    """Return a test vertical configuration."""
    return {
        "name": "restaurants",
        "yelp_categories": "restaurants",
        "google_categories": "restaurant",
    }


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing with the correct schema."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        temp_db_path = tmp.name
    # Set up the database connection string
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path}"
    try:
        # Create the database with the correct schema
        with db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            # Create businesses table with all required columns
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS businesses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    website TEXT,
                    address TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT,
                    country TEXT,
                    latitude REAL,
                    longitude REAL,
                    vertical TEXT,
                    source TEXT,
                    source_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_id)
                )
            """
            )
            # Create zip_queue table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS zip_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zip TEXT NOT NULL,
                    metro TEXT,
                    state TEXT,
                    status TEXT DEFAULT 'pending',
                    last_scraped TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(zip)
                )
            """
            )
            # Create verticals table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verticals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    yelp_categories TEXT,
                    google_categories TEXT,
                    search_params TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name)
                )
            """
            )
            # Insert test data
            cursor.executemany(
                """
                INSERT OR IGNORE INTO zip_queue (zip, metro, state, status)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("10002", "New York", "NY", "pending"),
                    ("98908", "Yakima", "WA", "pending"),
                ],
            )
            cursor.executemany(
                """
                INSERT OR IGNORE INTO verticals
                (name, yelp_categories, google_categories)
                VALUES (?, ?, ?)
                """,
                [
                    ("restaurants", "restaurants", "restaurant"),
                    ("retail", "shopping", "store"),
                ],
            )
            conn.commit()
        yield temp_db_path
    except Exception:
        raise
    finally:
        # Clean up
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


def test_scrape_businesses(target_zip_code, target_vertical, temp_db, monkeypatch, capsys):
    """Test the scrape_businesses function."""
    # Set up test API keys in environment first
    yelp_key = "test_yelp_key"
    google_key = "test_google_key"
    monkeypatch.setenv("YELP_KEY", yelp_key)
    monkeypatch.setenv("GOOGLE_KEY", google_key)
    # Now import the module after setting environment variables
    sys.modules.pop("bin.scrape", None)  # Clear any existing import
    from bin.scrape import scrape_businesses  # Only import what's needed

    # Verify environment variables are set correctly
    assert os.environ.get("YELP_KEY") == yelp_key
    assert os.environ.get("GOOGLE_KEY") == google_key
    # Mock the Yelp and Google Places APIs
    mock_yelp = MagicMock()
    # Yelp API returns a tuple of (businesses, error)
    mock_yelp.search_businesses.return_value = (
        [
            {"id": "test1", "name": "Test Business 1", "location": {}},
            {"id": "test2", "name": "Test Business 2", "location": {}},
        ],
        None,  # No error
    )
    mock_google = MagicMock()
    # Google Places API returns a tuple of (places, error)
    mock_google.search_places.return_value = (
        [
            {"place_id": "place1", "name": "Test Place 1"},
            {"place_id": "place2", "name": "Test Place 2"},
        ],
        None,  # No error
    )

    # Mock the process functions to insert into the test database
    def mock_process_yelp(business, category):
        with db_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO businesses
                (name, phone, email, website, vertical, source, source_id)
                VALUES (?, ?, ?, ?, ?, 'yelp', ?)
            """,
                (
                    business.get("name", ""),
                    business.get("phone", ""),
                    business.get("email", ""),
                    business.get("url", ""),
                    category,
                    business.get("id", ""),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def mock_process_google(place, category, google_api):
        with db_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO businesses
                (name, phone, email, website, vertical, source, source_id)
                VALUES (?, ?, ?, ?, ?, 'google', ?)
            """,
                (
                    place.get("name", ""),
                    place.get("formatted_phone_number", ""),
                    place.get("email", ""),
                    place.get("website", ""),
                    category,
                    place.get("place_id", ""),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    # Mock the get_zip_coordinates function
    def mock_get_zip_coordinates(zip_code):
        return "40.7128,-74.0060"  # Return mock coordinates

    # Mock the load_yaml_config function
    def mock_load_yaml_config(path):
        return {
            "search_params": {
                "yelp": {"radius": 40000, "sort_by": "best_match"},
                "google": {"radius": 40000, "type": "business"},
            }
        }

    # Apply the mocks
    monkeypatch.setattr("bin.scrape.YelpAPI", lambda *args, **kwargs: mock_yelp)
    monkeypatch.setattr("bin.scrape.GooglePlacesAPI", lambda *args, **kwargs: mock_google)
    monkeypatch.setattr("bin.scrape.process_yelp_business", mock_process_yelp)
    monkeypatch.setattr("bin.scrape.process_google_place", mock_process_google)
    monkeypatch.setattr("bin.scrape.get_zip_coordinates", mock_get_zip_coordinates)
    monkeypatch.setattr("bin.scrape.load_yaml_config", mock_load_yaml_config)
    # Add yelp_alias and google_alias to the target_vertical
    test_vertical = target_vertical.copy()
    test_vertical["yelp_alias"] = "restaurants"
    test_vertical["google_alias"] = "restaurant"
    # Call the function
    yelp_count, google_count = scrape_businesses(target_zip_code, test_vertical, limit=2)
    # Print debug information
    # Verify the results
    assert yelp_count == 2, f"Expected 2 Yelp businesses, got {yelp_count}"
    assert google_count == 2, f"Expected 2 Google businesses, got {google_count}"
    # Verify the database was updated
    with db_connection(temp_db) as conn:
        # Check businesses table
        cursor = conn.execute("SELECT * FROM businesses")
        cursor.fetchall()
        # Check for the specific businesses we expect
        cursor = conn.execute("SELECT COUNT(*) FROM businesses WHERE source = 'yelp'")
        yelp_count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM businesses WHERE source = 'google'")
        google_count = cursor.fetchone()[0]
        # Verify we have the expected number of businesses from each source
        assert yelp_count == 2, f"Expected 2 Yelp businesses in DB, got {yelp_count}"
        assert google_count == 2, f"Expected 2 Google businesses in DB, got {google_count}"


def test_main(target_vertical, temp_db, monkeypatch, capsys):
    """Test the main function."""
    # Set up test API keys in environment first
    yelp_key = "test_yelp_key"
    google_key = "test_google_key"
    monkeypatch.setenv("YELP_KEY", yelp_key)
    monkeypatch.setenv("GOOGLE_KEY", google_key)
    # Now import the module after setting environment variables
    sys.modules.pop("bin.scrape", None)  # Clear any existing import
    from bin.scrape import main  # Only import what's needed

    # Mock the command line arguments
    def mock_parse_args():
        class Args:
            limit = 2
            # Changed from zip_code to zip to match the argument name in main()
            zip = None
            vertical = target_vertical["name"]

        return Args()

    # Mock the required functions
    def mock_get_active_zip_codes():
        return [{"zip": "10002", "metro": "Test Metro"}]

    def mock_get_verticals():
        return [target_vertical]

    def mock_scrape_businesses(zip_code, vertical, limit):
        return (1, 1)  # (yelp_count, google_count)

    def mock_mark_zip_done(zip_code):
        pass  # No need to do anything in test

    # Apply the mocks
    monkeypatch.setattr("argparse.ArgumentParser.parse_args", lambda _: mock_parse_args())
    monkeypatch.setattr("bin.scrape.get_active_zip_codes", mock_get_active_zip_codes)
    monkeypatch.setattr("bin.scrape.get_verticals", mock_get_verticals)
    monkeypatch.setattr("bin.scrape.scrape_businesses", mock_scrape_businesses)
    monkeypatch.setattr("bin.scrape.mark_zip_done", mock_mark_zip_done)
    # Call the main function
    result = main()
    # Verify the result
    assert result == 0  # Success exit code
