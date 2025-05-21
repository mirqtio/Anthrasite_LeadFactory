"""Unit tests for the mockup generation functionality"""

import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the modules to test
from bin.mockup import generate_business_mockup


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    with patch("bin.mockup.DatabaseConnection") as mock_db_conn:
        cursor_mock = MagicMock()
        connection_mock = MagicMock()
        connection_mock.__enter__.return_value = cursor_mock
        mock_db_conn.return_value = connection_mock
        yield cursor_mock


@pytest.fixture
def mock_generators():
    """Create mocks for both GPT-4o and Claude generators."""
    with (
        patch("bin.mockup.GPT4oMockupGenerator") as mock_gpt4o,
        patch("bin.mockup.ClaudeMockupGenerator") as mock_claude,
    ):
        # Configure GPT-4o mock
        mock_gpt4o_instance = MagicMock()
        mock_gpt4o.return_value = mock_gpt4o_instance
        mock_gpt4o_instance.generate_mockup.return_value = (
            "mock_base64_image",
            "<html>Mock HTML</html>",
            {"usage": {"total_tokens": 100}},
            None,
        )
        # Configure Claude mock
        mock_claude_instance = MagicMock()
        mock_claude.return_value = mock_claude_instance
        mock_claude_instance.generate_mockup.return_value = (
            "fallback_base64_image",
            "<html>Fallback HTML</html>",
            {"usage": {"total_tokens": 80}},
            None,
        )
        yield mock_gpt4o_instance, mock_claude_instance


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    # Create tables
    cursor.executescript(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT,
            website TEXT,
            location_data TEXT,
            mockup_data TEXT,
            mockup_generated BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE mockups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            mockup_url TEXT,
            mockup_html TEXT,
            usage_data TEXT,
            mockup_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses (id)
        );
    """
    )
    # Insert test data
    cursor.executescript(
        """
        INSERT INTO businesses (id, name, website, location_data)
        VALUES
        (1, 'High Score Business', 'https://highscore.com', '{"state": "CA"}'),
        (2, 'Medium Score Business', 'https://mediumscore.com', '{"state": "TX"}'),
        (3, 'Low Score Business', 'https://lowscore.com', '{"state": "FL"}'),
        (4, 'No Website Business', NULL, '{"state": "NY"}');
    """
    )
    conn.commit()
    yield conn
    conn.close()


def test_generate_mockup_success(mock_generators, test_db):
    """Test generating a mockup successfully."""
    mock_gpt4o, mock_claude = mock_generators
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.save_mockup", return_value=True) as mock_save,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the business data
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(
            business_data,
            tier=3,  # Premium tier
            style="modern",
            resolution="1024x1024",
        )
        # Verify the result
        assert result is True
        # Verify that GPT-4o was called with the right parameters
        mock_gpt4o.generate_mockup.assert_called_once_with(
            business_data=business_data,
            screenshot_url=None,
            style="modern",
            resolution="1024x1024",
        )
        # Verify that save_mockup was called
        mock_save.assert_called_once()
        # Verify that Claude was not called (since GPT-4o succeeded)
        mock_claude.generate_mockup.assert_not_called()


def test_generate_mockup_medium_scoring(mock_generators, test_db):
    """Test generating a mockup for a medium-scoring business."""
    mock_gpt4o, mock_claude = mock_generators
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.save_mockup", return_value=True) as mock_save,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the medium-scoring business
        cursor.execute("SELECT * FROM businesses WHERE id = 2")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(
            business_data,
            tier=2,  # Standard tier
            style="modern",
            resolution="1024x1024",
        )
        # Verify the result
        assert result is True
        # Verify that GPT-4o was called with the right parameters
        mock_gpt4o.generate_mockup.assert_called_once_with(
            business_data=business_data,
            screenshot_url=None,
            style="modern",
            resolution="1024x1024",
        )
        # Verify that save_mockup was called
        mock_save.assert_called_once()
        # Verify that Claude was not called (since GPT-4o succeeded)
        mock_claude.generate_mockup.assert_not_called()


def test_generate_mockup_low_scoring(mock_generators, test_db):
    """Test generating a mockup for a low-scoring business."""
    mock_gpt4o, mock_claude = mock_generators
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.save_mockup", return_value=True) as mock_save,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the low-scoring business
        cursor.execute("SELECT * FROM businesses WHERE id = 3")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(business_data, tier=1, style="modern", resolution="1024x1024")  # Basic tier
        # Verify the result
        assert result is True
        # Verify that GPT-4o was called with the right parameters
        mock_gpt4o.generate_mockup.assert_called_once_with(
            business_data=business_data,
            screenshot_url=None,
            style="modern",
            resolution="1024x1024",
        )
        # Verify that save_mockup was called
        mock_save.assert_called_once()
        # Verify that Claude was not called (since GPT-4o succeeded)
        mock_claude.generate_mockup.assert_not_called()


def test_fallback_to_claude(mock_generators, test_db):
    """Test fallback to Claude when GPT-4o fails."""
    mock_gpt4o, mock_claude = mock_generators
    # Make GPT-4o fail by returning None for image and HTML
    mock_gpt4o.generate_mockup.return_value = (None, None, {}, "GPT-4o error")
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.save_mockup", return_value=True) as mock_save,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the business data
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(business_data, tier=3, style="modern", resolution="1024x1024")
        # Verify the result
        assert result is True
        # Verify that both models were called
        mock_gpt4o.generate_mockup.assert_called_once()
        mock_claude.generate_mockup.assert_called_once()
        # Verify that a warning was logged
        # TODO: Fix mock_logging reference
        # mock_logging.warning.assert_any_call(ANY)
        # Verify that save_mockup was called with Claude's results
        mock_save.assert_called_once()


def test_both_models_failing(mock_generators, test_db):
    """Test handling the case where both models fail."""
    mock_gpt4o, mock_claude = mock_generators
    # Make both models fail
    mock_gpt4o.generate_mockup.return_value = (None, None, {}, "GPT-4o error")
    mock_claude.generate_mockup.return_value = (None, None, {}, "Claude error")
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the business data
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(business_data, tier=3, style="modern", resolution="1024x1024")
        # Verify the result
        assert result is False
        # Verify that both models were called
        mock_gpt4o.generate_mockup.assert_called_once()
        mock_claude.generate_mockup.assert_called_once()
        # Verify that an error was logged
        # TODO: Fix mock_logging reference
        # mock_logging.error.assert_called_once_with(ANY)
        # Verify that cost tracking was not called (since no model succeeded)
        # TODO: Fix mock_track reference
        # mock_track.assert_not_called()


def test_partial_success_html_only(mock_generators, test_db):
    """Test partial success with HTML but no image."""
    mock_gpt4o, mock_claude = mock_generators
    # Return HTML but no image
    mock_gpt4o.generate_mockup.return_value = (
        None,  # No image
        "<html>Mock HTML</html>",  # HTML content
        {"usage": {"total_tokens": 100}},
        None,
    )
    with (
        patch("bin.mockup.DatabaseConnection") as mock_db,
        patch("bin.mockup.save_mockup", return_value=True) as mock_save,
        patch("bin.mockup.OPENAI_API_KEY", "test_key"),
        patch("bin.mockup.ANTHROPIC_API_KEY", "test_key"),
        patch("utils.io.track_api_cost"),
        patch("bin.mockup.logger"),
    ):
        # Configure the mock database connection
        cursor = test_db.cursor()
        mock_db.return_value.__enter__.return_value = cursor
        # Get the business data
        cursor.execute("SELECT * FROM businesses WHERE id = 1")
        business = cursor.fetchone()
        # Convert row to dict
        columns = [description[0] for description in cursor.description]
        business_data = dict(zip(columns, business))
        # Call the function under test
        result = generate_business_mockup(business_data, tier=3, style="modern", resolution="1024x1024")
        # Verify the result
        assert result is True
        # Verify that a warning was logged about missing image
        # TODO: Fix mock_logging reference
        # mock_logging.warning.assert_any_call(ANY)
        # Verify that save_mockup was called
        mock_save.assert_called_once()
