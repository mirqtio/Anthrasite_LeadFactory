"""
Unit tests for the email_queue module.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from leadfactory.pipeline import email_queue


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
            email TEXT,
            contact_info TEXT
        )
        """
    )

    # Create emails table
    cursor.execute(
        """
        CREATE TABLE emails (
            id INTEGER PRIMARY KEY,
            business_id INTEGER NOT NULL,
            variant_id TEXT NOT NULL,
            subject TEXT,
            body_text TEXT,
            body_html TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            opened_at TIMESTAMP,
            clicked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
        """
    )

    # Insert test business
    cursor.execute(
        """
        INSERT INTO businesses (id, name, email, contact_info)
        VALUES (1, 'Test Business', 'test@example.com', '{"name": "John Doe", "position": "CEO"}')
        """
    )

    # Insert test emails
    cursor.execute(
        """
        INSERT INTO emails (id, business_id, variant_id, subject, body_text, body_html, status)
        VALUES (1, 1, 'variant_a', 'Test Subject 1', 'Test Body 1', '<p>Test Body 1</p>', 'pending')
        """
    )

    cursor.execute(
        """
        INSERT INTO emails (id, business_id, variant_id, subject, body_text, body_html, status)
        VALUES (2, 1, 'variant_b', 'Test Subject 2', 'Test Body 2', '<p>Test Body 2</p>', 'sent')
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_email_sender():
    """Mock for email sending service."""
    with patch("bin.email_queue.send_email") as mock_sender:
        mock_sender.return_value = {"success": True, "message_id": "test_message_123"}
        yield mock_sender


def test_get_pending_emails(mock_db):
    """Test retrieving pending emails from the queue."""
    # Call the function
    pending_emails = email_queue.get_pending_emails(mock_db, limit=10)

    # Verify the result
    assert len(pending_emails) == 1
    assert pending_emails[0]["id"] == 1
    assert pending_emails[0]["business_id"] == 1
    assert pending_emails[0]["subject"] == "Test Subject 1"
    assert pending_emails[0]["status"] == "pending"


def test_send_queued_emails(mock_db, mock_email_sender):
    """Test sending emails from the queue."""
    # Call the function
    result = email_queue.process_email_queue(mock_db, limit=10)

    # Verify email sender was called
    assert mock_email_sender.called
    assert mock_email_sender.call_count == 1

    # Verify the result
    assert result["processed"] == 1
    assert result["success"] == 1

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT status, sent_at FROM emails WHERE id = 1")
    email = cursor.fetchone()

    assert email[0] == "sent"
    assert email[1] is not None  # sent_at timestamp


def test_mark_email_as_sent(mock_db):
    """Test marking an email as sent."""
    # Call the function
    email_queue.mark_email_as_sent(mock_db, 1, "test_message_123")

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT status, sent_at FROM emails WHERE id = 1")
    email = cursor.fetchone()

    assert email[0] == "sent"
    assert email[1] is not None  # sent_at timestamp


def test_track_email_open(mock_db):
    """Test tracking email opens."""
    # Call the function
    email_queue.track_email_open(mock_db, 1)

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT opened_at FROM emails WHERE id = 1")
    email = cursor.fetchone()

    assert email[0] is not None  # opened_at timestamp


def test_track_email_click(mock_db):
    """Test tracking email clicks."""
    # Call the function
    email_queue.track_email_click(mock_db, 1)

    # Verify database was updated
    cursor = mock_db.cursor()
    cursor.execute("SELECT clicked_at FROM emails WHERE id = 1")
    email = cursor.fetchone()

    assert email[0] is not None  # clicked_at timestamp


def test_email_queue_with_limit(mock_db, mock_email_sender):
    """Test processing email queue with a specific limit."""
    # Insert additional pending emails
    cursor = mock_db.cursor()
    for i in range(3, 6):
        cursor.execute(
            """
            INSERT INTO emails (id, business_id, variant_id, subject, body_text, body_html, status)
            VALUES (?, 1, 'variant_a', ?, ?, ?, 'pending')
            """,
            (i, f"Subject {i}", f"Body {i}", f"<p>Body {i}</p>")
        )
    mock_db.commit()

    # Process with limit of 2
    result = email_queue.process_email_queue(mock_db, limit=2)

    # Verify only 2 were processed
    assert result["processed"] == 2
    assert mock_email_sender.call_count == 2

    # Verify correct emails were processed
    cursor = mock_db.cursor()
    cursor.execute("SELECT id FROM emails WHERE status = 'sent' ORDER BY id")
    sent_ids = [row[0] for row in cursor.fetchall()]

    assert 1 in sent_ids
    assert 3 in sent_ids
    assert 4 not in sent_ids
    assert 5 not in sent_ids


def test_error_handling(mock_db, mock_email_sender):
    """Test error handling during email sending."""
    # Configure mock to fail on second email
    calls = 0
    def side_effect(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"success": True, "message_id": "test_message_123"}
        else:
            raise Exception("Email sending failed")

    mock_email_sender.side_effect = side_effect

    # Insert additional pending email
    cursor = mock_db.cursor()
    cursor.execute(
        """
        INSERT INTO emails (id, business_id, variant_id, subject, body_text, body_html, status)
        VALUES (3, 1, 'variant_a', 'Subject 3', 'Body 3', '<p>Body 3</p>', 'pending')
        """
    )
    mock_db.commit()

    # Process the queue
    result = email_queue.process_email_queue(mock_db, limit=10)

    # Verify one succeeded and one failed
    assert result["processed"] == 2
    assert result["success"] == 1
    assert result["failed"] == 1

    # Verify first email was sent but second remains pending
    cursor = mock_db.cursor()
    cursor.execute("SELECT status FROM emails WHERE id = 1")
    assert cursor.fetchone()[0] == "sent"

    cursor.execute("SELECT status FROM emails WHERE id = 3")
    assert cursor.fetchone()[0] == "error"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
