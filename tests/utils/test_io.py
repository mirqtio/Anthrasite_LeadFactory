"""
Tests for utility IO functions used across the application.
"""

import os
import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
# Import the utils module
from utils import io


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = {"id": 1, "name": "Test"}
    return mock_conn, mock_cursor


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Clean up the temporary database file
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def test_database_connection_context_manager():
    """Test that DatabaseConnection works as a context manager."""
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Test using context manager
        with io.DatabaseConnection(db_path=":memory:") as conn:
            assert conn is not None, "Connection should not be None"
            assert mock_connect.called, "sqlite3.connect should be called"

        # Verify connection was closed
        assert mock_conn.close.called, "Connection should be closed"


def test_database_connection_with_existing_db(temp_db_path):
    """Test DatabaseConnection with an existing database."""
    # Create a test database
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("INSERT INTO test (name) VALUES ('test_data')")
    conn.commit()
    conn.close()

    # Test connecting to the existing database
    with io.DatabaseConnection(db_path=temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test")
        result = cursor.fetchone()
        assert result is not None, "Should retrieve test data"
        assert result[1] == "test_data", "Retrieved data should match inserted data"


def test_track_api_cost():
    """Test tracking API costs."""
    with patch("leadfactory.utils.e2e_db_connector.db_connection") as mock_db_class:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Test tracking API cost
        io.track_api_cost(
            model="gpt-4", tokens=1000, cost=0.05, purpose="Testing", business_id=1
        )

        # Verify the right SQL was executed
        assert mock_cursor.execute.called, "cursor.execute should be called"
        args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO api_costs" in args[0], "Should insert into api_costs table"
        assert "gpt-4" in args[1], "Model name should be in parameters"
        assert 1000 in args[1], "Token count should be in parameters"
        assert 0.05 in args[1], "Cost should be in parameters"
        assert "Testing" in args[1], "Purpose should be in parameters"
        assert 1 in args[1], "Business ID should be in parameters"


def test_get_business_by_id():
    """Test retrieving a business by ID."""
    mock_conn, mock_cursor = mock_db_connection

    with patch.object(mock_cursor, "fetchone") as mock_fetchone:
        test_business = {
            "id": 1,
            "name": "Test Business",
            "address": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
        }
        mock_fetchone.return_value = test_business

        # Test getting business by ID
        result = io.get_business_by_id(mock_conn, business_id=1)

        # Verify the function returned the expected business
        assert result == test_business, f"Expected {test_business}, got {result}"

        # Verify the right SQL was executed
        assert mock_cursor.execute.called, "cursor.execute should be called"
        args = mock_cursor.execute.call_args[0]
        assert "SELECT * FROM businesses WHERE id = ?" in args[0], (
            "SQL should select from businesses table"
        )
        assert 1 in args[1], "Business ID should be in parameters"


def test_save_to_json():
    """Test saving data to a JSON file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Test data
        test_data = {"name": "Test", "values": [1, 2, 3]}

        # Test saving to JSON
        io.save_to_json(test_data, temp_path)

        # Verify the file exists and contains the expected data
        assert os.path.exists(temp_path), f"JSON file should exist at {temp_path}"

        # Read back the data
        import json

        with open(temp_path) as f:
            loaded_data = json.load(f)

        # Verify the data matches
        assert loaded_data == test_data, f"Expected {test_data}, got {loaded_data}"

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_from_json():
    """Test loading data from a JSON file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name

        # Write test data to the file
        import json

        test_data = {"name": "Test", "values": [1, 2, 3]}
        json.dump(test_data, temp_file)

    try:
        # Test loading from JSON
        loaded_data = io.load_from_json(temp_path)

        # Verify the data matches
        assert loaded_data == test_data, f"Expected {test_data}, got {loaded_data}"

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_from_nonexistent_json():
    """Test loading from a nonexistent JSON file returns default."""
    # Test loading from nonexistent file
    default_value = {"default": True}
    loaded_data = io.load_from_json("nonexistent_file.json", default=default_value)

    # Verify the default was returned
    assert loaded_data == default_value, f"Expected {default_value}, got {loaded_data}"
