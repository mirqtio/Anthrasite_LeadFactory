#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Unsubscribe Functionality Tests
Tests for CAN-SPAM compliance and unsubscribe functionality.
"""

import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Import email queue functions
from bin.email_queue import (
    add_unsubscribe,
    generate_email_content,
    is_email_unsubscribed,
    load_email_template,
    send_business_email,
)

# Import unsubscribe handler
from bin.unsubscribe_handler import app

# Import database connection

# Load scenarios from feature file
scenarios("features/unsubscribe.feature")

# Create test client for FastAPI app
client = TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database connection for testing."""
    # Create in-memory SQLite database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create unsubscribes table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS unsubscribes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            reason TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create emails table for testing
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER,
            subject TEXT,
            body_html TEXT,
            body_text TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            message_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create businesses table for testing
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            contact_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.commit()

    # Mock DatabaseConnection to use in-memory database
    with patch("utils.io.DatabaseConnection") as mock:
        db_mock = MagicMock()
        db_mock.__enter__.return_value = cursor
        mock.return_value = db_mock
        yield cursor

    # Close connection
    conn.close()


@given(parsers.parse("a user with email '{email}'"))
def user_with_email(mock_db, email):
    """Create a test user with the given email."""
    mock_db.execute(
        "INSERT INTO businesses (name, email, contact_name) VALUES (?, ?, ?)",
        ("Test Business", email, "Test User"),
    )
    mock_db.connection.commit()


@given(parsers.parse("the user has not unsubscribed"))
def user_not_unsubscribed(mock_db):
    """Ensure the user has not unsubscribed."""
    # No action needed, by default users are not unsubscribed


@given(parsers.parse("the user has unsubscribed"))
def user_has_unsubscribed(mock_db, email="test@example.com"):
    """Mark the user as unsubscribed."""
    mock_db.execute("INSERT INTO unsubscribes (email) VALUES (?)", (email,))
    mock_db.connection.commit()


@when(parsers.parse("I check if the email '{email}' is unsubscribed"))
def check_if_email_unsubscribed(email):
    """Check if the email is unsubscribed."""
    return is_email_unsubscribed(email)


@when(parsers.parse("I add the email '{email}' to the unsubscribe list"))
def add_email_to_unsubscribe_list(mock_db, email):
    """Add the email to the unsubscribe list."""
    add_unsubscribe(email)


@when(parsers.parse("I try to send an email to '{email}'"))
def try_to_send_email(mock_db, email):
    """Try to send an email to the given email address."""
    # Get the business ID
    mock_db.execute("SELECT id FROM businesses WHERE email = ?", (email,))
    business_id = mock_db.fetchone()[0]

    # Create business data
    business = {
        "id": business_id,
        "name": "Test Business",
        "email": email,
        "contact_name": "Test User",
    }

    # Mock email sender
    email_sender = MagicMock()
    email_sender.send_email.return_value = (True, "test-message-id", None)

    # Try to send email
    return send_business_email(business, email_sender, "Test template", is_dry_run=True)


@when(parsers.parse("a user visits the unsubscribe page with email '{email}'"))
def visit_unsubscribe_page(email):
    """Visit the unsubscribe page with the given email."""
    return client.get(f"/unsubscribe?email={email}")


@when(parsers.parse("a user submits the unsubscribe form with email '{email}'"))
def submit_unsubscribe_form(email):
    """Submit the unsubscribe form with the given email."""
    return client.post(
        "/unsubscribe",
        data={"email": email, "reason": "not_interested", "comments": "Test comment"},
    )


@then(parsers.parse("the result should be '{result}'"))
def check_result(result, request):
    """Check if the result matches the expected value."""
    expected = result.lower() == "true"
    assert request.node.funcargs.get("check_if_email_unsubscribed", None) == expected


@then(parsers.parse("the email '{email}' should be in the unsubscribe list"))
def check_email_in_unsubscribe_list(mock_db, email):
    """Check if the email is in the unsubscribe list."""
    mock_db.execute("SELECT email FROM unsubscribes WHERE email = ?", (email,))
    result = mock_db.fetchone()
    assert result is not None
    assert result[0] == email


@then(parsers.parse("the email '{email}' should not be in the unsubscribe list"))
def check_email_not_in_unsubscribe_list(mock_db, email):
    """Check if the email is not in the unsubscribe list."""
    mock_db.execute("SELECT email FROM unsubscribes WHERE email = ?", (email,))
    result = mock_db.fetchone()
    assert result is None


@then(parsers.parse("the email should not be sent"))
def check_email_not_sent(request):
    """Check if the email was not sent."""
    result = request.node.funcargs.get("try_to_send_email", None)
    assert result is not None
    assert result[0] is False  # First element is success flag


@then(parsers.parse("the email should be sent"))
def check_email_sent(request):
    """Check if the email was sent."""
    result = request.node.funcargs.get("try_to_send_email", None)
    assert result is not None
    assert result[0] is True  # First element is success flag


@then(parsers.parse("the response status code should be {status_code:d}"))
def check_response_status_code(status_code, request):
    """Check if the response status code matches the expected value."""
    response = request.node.funcargs.get("visit_unsubscribe_page", None) or request.node.funcargs.get(
        "submit_unsubscribe_form", None
    )
    assert response is not None
    assert response.status_code == status_code


@then(parsers.parse("the response should contain '{text}'"))
def check_response_contains_text(text, request):
    """Check if the response contains the expected text."""
    response = request.node.funcargs.get("visit_unsubscribe_page", None) or request.node.funcargs.get(
        "submit_unsubscribe_form", None
    )
    assert response is not None
    assert text in response.text


@then(parsers.parse("the HTML email template should contain the physical address"))
def check_html_template_contains_address():
    """Check if the HTML email template contains the physical address."""
    template = load_email_template()
    assert "PO Box 12345" in template
    assert "San Francisco, CA 94107" in template


@then(parsers.parse("the HTML email template should contain an unsubscribe link"))
def check_html_template_contains_unsubscribe_link():
    """Check if the HTML email template contains an unsubscribe link."""
    template = load_email_template()
    assert "unsubscribe" in template.lower()
    assert "{{unsubscribe_link}}" in template or "unsubscribe?email=" in template


@then(parsers.parse("the plain text email should contain the physical address"))
def check_text_email_contains_address():
    """Check if the plain text email contains the physical address."""
    # We'll need to generate a sample email to check the plain text content
    business = {
        "id": 1,
        "name": "Test Business",
        "email": "test@example.com",
        "contact_name": "Test User",
    }
    _, _, text_content = generate_email_content(business, load_email_template())
    assert "PO Box 12345" in text_content
    assert "San Francisco, CA 94107" in text_content


@then(parsers.parse("the plain text email should contain unsubscribe instructions"))
def check_text_email_contains_unsubscribe_instructions():
    """Check if the plain text email contains unsubscribe instructions."""
    # We'll need to generate a sample email to check the plain text content
    business = {
        "id": 1,
        "name": "Test Business",
        "email": "test@example.com",
        "contact_name": "Test User",
    }
    _, _, text_content = generate_email_content(business, load_email_template())
    assert "unsubscribe" in text_content.lower()
    assert "If you'd prefer not to receive these emails" in text_content
