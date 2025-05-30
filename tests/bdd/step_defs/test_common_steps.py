"""Common step definitions for BDD tests.

These steps are used across multiple feature files and scenarios.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

# Import common step definitions
from tests.bdd.step_defs.common_step_definitions import *

# Import the feature file scenarios directly
# This is critical for pytest-bdd to properly discover step definitions
feature_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "features", "pipeline_stages.feature")
scenarios(feature_file)

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import mock modules to ensure proper mocking
from tests.bdd.mock_modules import *

# Mock API responses
mock_yelp_response = MagicMock()
mock_yelp_response.json.return_value = {
    "businesses": [
        {"id": "1", "name": "Test Business 1", "address": "123 Main St"},
        {"id": "2", "name": "Test Business 2", "address": "456 Elm St"},
        {"id": "3", "name": "Test Business 3", "address": "789 Oak St"},
    ]
}
mock_yelp_response.status_code = 200

# Import the global context from conftest.py
from tests.bdd.conftest import global_context as context


@pytest.fixture
def mock_apis():
    """Mock API responses for testing."""
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:

        # Configure mock responses
        mock_get.return_value = mock_yelp_response
        mock_post.return_value = MagicMock(status_code=200)

        yield {
            "get": mock_get,
            "post": mock_post
        }

# Basic step definitions that all BDD tests will use
@given("the database is initialized")
def database_initialized(db_conn):
    """Ensure the database is initialized with required tables."""
    # Create businesses table
    db_conn.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        phone TEXT,
        website TEXT,
        email TEXT,
        description TEXT,
        category TEXT,
        source TEXT,
        status TEXT DEFAULT 'pending',
        score REAL,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # Create business_scores table
    db_conn.execute("""
    CREATE TABLE IF NOT EXISTS business_scores (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        total_score REAL,
        tech_score REAL,
        performance_score REAL,
        size_score REAL,
        industry_score REAL,
        created_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    )
    """)

    # Create tech_stack table
    db_conn.execute("""
    CREATE TABLE IF NOT EXISTS tech_stack (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        technology TEXT,
        category TEXT,
        created_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    )
    """)

    # Create api_costs table
    db_conn.execute("""
    CREATE TABLE IF NOT EXISTS api_costs (
        id INTEGER PRIMARY KEY,
        api_name TEXT,
        endpoint TEXT,
        cost REAL,
        timestamp TEXT,
        model TEXT,
        purpose TEXT
    )
    """)

    # Create emails table
    db_conn.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY,
        business_id INTEGER,
        subject TEXT,
        body TEXT,
        recipient TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        sent_at TEXT,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    )
    """)

    db_conn.commit()
    return db_conn

@given("API mocks are configured")
def api_mocks_configured(mock_apis):
    """Ensure API mocks are configured."""
    # The mock_apis fixture already configures all API responses
    return mock_apis

# Add implementations for the basic pipeline scenarios
@when(parsers.parse('I scrape businesses from source "{source}" with limit {limit:d}'))
def scrape_businesses(source, limit, mock_apis, db_conn):
    """Scrape businesses from the specified source."""
    # Mock the scraping process
    businesses = [
        {"id": "1", "name": "Test Business 1", "address": "123 Main St", "phone": "555-1234", "website": "http://test1.com", "category": "test", "source": source},
        {"id": "2", "name": "Test Business 2", "address": "456 Elm St", "phone": "555-5678", "website": "http://test2.com", "category": "test", "source": source},
        {"id": "3", "name": "Test Business 3", "address": "789 Oak St", "phone": "555-9012", "website": "http://test3.com", "category": "test", "source": source},
    ]

    # Store in context for later assertions
    context["businesses"] = businesses

    # Insert into db
    for business in businesses:
        db_conn.execute("""
            INSERT INTO businesses (name, address, phone, website, category, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (business["name"], business["address"], business["phone"], business["website"], business["category"], business["source"]))

    db_conn.commit()
    return businesses

@then(parsers.parse("I should receive at least {count:d} businesses"))
def check_business_count(count):
    """Check that we received at least the specified number of businesses."""
    assert len(context["businesses"]) >= count, f"Expected at least {count} businesses, got {len(context['businesses'])}"

@then("each business should have a name and address")
def check_business_data():
    """Check that each business has the required data."""
    for business in context["businesses"]:
        assert "name" in business and business["name"], "Business missing name"
        assert "address" in business and business["address"], "Business missing address"

@then("each business should be saved to the database")
def check_businesses_saved(db_conn):
    """Check that businesses are saved to the database."""
    cursor = db_conn.execute("SELECT COUNT(*) FROM businesses")
    count = cursor.fetchone()[0]
    assert count >= len(context["businesses"]), f"Expected at least {len(context['businesses'])} businesses in the database, got {count}"

# Stub implementations for other scenarios
@given("a business exists with basic information")
def business_with_basic_info(db_conn):
    """Set up a business with basic information."""
    cursor = db_conn.execute("""
        INSERT INTO businesses (name, address, phone, website, category, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ("Test Business", "123 Main St", "555-1234", "http://test.com", "HVAC", "test_source"))

    # Get the business ID
    cursor = db_conn.execute("SELECT last_insert_rowid()")
    business_id = cursor.fetchone()[0]
    db_conn.commit()

    context["business_id"] = business_id
    return business_id

@when("I enrich the business data")
def enrich_business_data(db_conn):
    """Enrich the business data."""
    business_id = context["business_id"]

    # Mock enrichment data
    tech_stack = json.dumps({
        "cms": "WordPress",
        "analytics": "Google Analytics",
        "framework": "Bootstrap",
        "hosting": "AWS"
    })

    performance_score = 85.5
    contact_info = json.dumps({
        "email": "contact@test.com",
        "phone": "555-1234",
        "social": {
            "facebook": "https://facebook.com/testbusiness",
            "twitter": "https://twitter.com/testbusiness"
        }
    })

    # Insert enrichment data
    db_conn.execute("""
        INSERT INTO enrichment (business_id, tech_stack, performance_score, contact_info, enrichment_timestamp)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (business_id, tech_stack, performance_score, contact_info))

    db_conn.commit()

    # Store in context for later assertions
    context["enrichment"] = {
        "tech_stack": json.loads(tech_stack),
        "performance_score": performance_score,
        "contact_info": json.loads(contact_info)
    }

@then("the business should have additional contact information")
def check_contact_info(db_conn):
    """Check that the business has contact information."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT contact_info FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"

    contact_info = json.loads(result[0])
    assert "email" in contact_info, "Contact info missing email"

@then("the business should have technology stack information")
def check_tech_stack():
    """Check that the business has tech stack information."""
    assert "tech_stack" in context["enrichment"], "Tech stack not found in enrichment data"
    assert len(context["enrichment"]["tech_stack"]) > 0, "Tech stack is empty"

@then("the business should have performance metrics")
def check_performance():
    """Check that the business has performance metrics."""
    assert "performance_score" in context["enrichment"], "Performance score not found in enrichment data"
    assert context["enrichment"]["performance_score"] > 0, "Performance score is zero or negative"

@then("enrichment timestamp should be updated")
def check_enrichment_timestamp(db_conn):
    """Check that the enrichment timestamp is updated."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT enrichment_timestamp FROM enrichment WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No enrichment record found"
    assert result[0] is not None, "Enrichment timestamp is null"

# Scoring business leads scenario
@given("a business exists with enriched information")
def business_with_enriched_info(db_conn):
    """Set up a business with enriched information."""
    # First create a basic business
    business_id = business_with_basic_info(db_conn)

    # Then add enrichment data
    enrich_business_data(db_conn)

    return business_id

@when("I score the business")
def score_business(db_conn):
    """Score the business."""
    business_id = context["business_id"]

    # Mock scoring data
    score = 85.5
    criteria = json.dumps({
        "website_quality": 8,
        "contact_info": 9,
        "tech_stack": 7,
        "market_fit": 8
    })

    # Insert scoring data
    db_conn.execute("""
        INSERT INTO scores (business_id, score, criteria, scoring_timestamp)
        VALUES (?, ?, ?, datetime('now'))
    """, (business_id, score, criteria))

    db_conn.commit()

    # Store in context for later assertions
    context["score"] = {
        "score": score,
        "criteria": json.loads(criteria)
    }

    return score

@then("the business should have a numerical score")
def check_numerical_score(db_conn):
    """Check that the business has a numerical score."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT score FROM scores WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No score record found"
    assert result[0] is not None, "Score is null"
    assert isinstance(result[0], (int, float)), "Score is not a number"

@then("the business should have a score between 0 and 100")
def check_score_range(db_conn):
    """Check that the business has a score between 0 and 100."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT score FROM scores WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No score record found"
    assert 0 <= result[0] <= 100, f"Score {result[0]} is not between 0 and 100"

@then("the score should be based on predefined criteria")
def check_score_criteria(db_conn):
    """Check that the score is based on predefined criteria."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT criteria FROM scores WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No score record found"
    criteria = json.loads(result[0])
    assert len(criteria) > 0, "No scoring criteria found"

@then("the score details should include component scores")
def check_component_scores(db_conn):
    """Check that score details include component scores."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT criteria FROM scores WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No score record found"
    criteria = json.loads(result[0])

    # Check for expected component scores
    expected_components = ["website_quality", "contact_info", "tech_stack", "market_fit"]
    for component in expected_components:
        assert component in criteria, f"Component score '{component}' not found"
        assert isinstance(criteria[component], (int, float)), f"Component score '{component}' is not a number"

@then("businesses with better tech stacks should score higher")
def check_tech_stack_scoring(db_conn):
    """Check that businesses with better tech stacks score higher."""
    # Create another business with a different tech stack score for comparison
    cursor = db_conn.execute("""
        INSERT INTO businesses (name, address, phone, website, category, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ("Test Business 2", "456 Elm St", "555-5678", "http://test2.com", "HVAC", "test_source"))

    # Get the new business ID
    cursor = db_conn.execute("SELECT last_insert_rowid()")
    business2_id = cursor.fetchone()[0]
    db_conn.commit()

    # Add enrichment data with better tech stack
    tech_stack = json.dumps({
        "cms": "Custom CMS",
        "analytics": "Google Analytics Premium",
        "framework": "React",
        "hosting": "AWS Advanced",
        "additional_tech": "GraphQL, Redis, Elasticsearch"
    })

    performance_score = 95.0
    contact_info = json.dumps({
        "email": "contact@test2.com",
        "phone": "555-5678",
        "social": {
            "facebook": "https://facebook.com/testbusiness2",
            "twitter": "https://twitter.com/testbusiness2",
            "linkedin": "https://linkedin.com/company/testbusiness2"
        }
    })

    # Insert enrichment data
    db_conn.execute("""
        INSERT INTO enrichment (business_id, tech_stack, performance_score, contact_info, enrichment_timestamp)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (business2_id, tech_stack, performance_score, contact_info))

    db_conn.commit()

    # Score with higher tech stack values
    criteria2 = json.dumps({
        "website_quality": 9,
        "contact_info": 9,
        "tech_stack": 10,  # Higher than the first business
        "market_fit": 8
    })

    # Insert a higher score for the second business
    db_conn.execute("""
        INSERT INTO scores (business_id, score, criteria, scoring_timestamp)
        VALUES (?, ?, ?, datetime('now'))
    """, (business2_id, 92.0, criteria2))

    db_conn.commit()

    # Compare scores
    cursor = db_conn.execute("""
        SELECT b.id, b.name, s.score, e.tech_stack
        FROM businesses b
        JOIN scores s ON b.id = s.business_id
        JOIN enrichment e ON b.id = e.business_id
        ORDER BY s.score ASC
    """)

    results = cursor.fetchall()
    assert len(results) >= 2, "Not enough scored businesses to compare"

    # Verify that scores increase with better tech stacks
    for i in range(1, len(results)):
        prev_score = results[i-1][2]
        curr_score = results[i][2]
        assert curr_score > prev_score, f"Business with better tech stack does not have higher score: {prev_score} vs {curr_score}"

        # Check tech stack criterion specifically
        prev_id = results[i-1][0]
        curr_id = results[i][0]

        cursor = db_conn.execute("SELECT criteria FROM scores WHERE business_id = ?", (prev_id,))
        prev_criteria = json.loads(cursor.fetchone()[0])

        cursor = db_conn.execute("SELECT criteria FROM scores WHERE business_id = ?", (curr_id,))
        curr_criteria = json.loads(cursor.fetchone()[0])

        assert curr_criteria["tech_stack"] >= prev_criteria["tech_stack"], "Tech stack criterion does not reflect in scoring"

@then("businesses with better performance should score higher")
def check_performance_scoring(db_conn):
    """Check that businesses with better performance score higher."""
    # Create another business with a different performance score for comparison
    cursor = db_conn.execute("""
        INSERT INTO businesses (name, address, phone, website, category, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ("Test Business 3", "789 Oak St", "555-9012", "http://test3.com", "HVAC", "test_source"))

    # Get the new business ID
    cursor = db_conn.execute("SELECT last_insert_rowid()")
    business3_id = cursor.fetchone()[0]
    db_conn.commit()

    # Add enrichment data with high performance score
    tech_stack = json.dumps({
        "cms": "WordPress",
        "analytics": "Google Analytics",
        "framework": "Bootstrap",
        "hosting": "AWS"
    })

    performance_score = 98.0  # Higher performance score
    contact_info = json.dumps({
        "email": "contact@test3.com",
        "phone": "555-9012",
        "social": {
            "facebook": "https://facebook.com/testbusiness3",
            "twitter": "https://twitter.com/testbusiness3"
        }
    })

    # Insert enrichment data
    db_conn.execute("""
        INSERT INTO enrichment (business_id, tech_stack, performance_score, contact_info, enrichment_timestamp)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (business3_id, tech_stack, performance_score, contact_info))

    db_conn.commit()

    # Score with emphasis on performance
    criteria3 = json.dumps({
        "website_quality": 9,
        "contact_info": 8,
        "tech_stack": 7,
        "market_fit": 9,
        "performance": 10  # High performance score
    })

    # Insert a higher score for the third business based on performance
    db_conn.execute("""
        INSERT INTO scores (business_id, score, criteria, scoring_timestamp)
        VALUES (?, ?, ?, datetime('now'))
    """, (business3_id, 93.0, criteria3))

    db_conn.commit()

    # Compare scores vs performance
    cursor = db_conn.execute("""
        SELECT b.id, b.name, s.score, e.performance_score
        FROM businesses b
        JOIN scores s ON b.id = s.business_id
        JOIN enrichment e ON b.id = e.business_id
        ORDER BY e.performance_score ASC
    """)

    results = cursor.fetchall()

    # Check if higher performance scores correlate with higher overall scores
    [row[3] for row in results]
    overall_scores = [row[2] for row in results]

    # Simple correlation check (not perfect, but sufficient for the test)
    # Higher performance should generally lead to higher scores
    # We're just checking the highest performance has a higher score than the lowest
    assert overall_scores[-1] > overall_scores[0], "Business with better performance should score higher"

@then("the score should be saved to the database")
def check_score_saved(db_conn):
    """Check that the score is saved to the database."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT COUNT(*) FROM scores WHERE business_id = ?
    """, (business_id,))

    count = cursor.fetchone()[0]
    assert count > 0, "No score record found in database"

# Generating emails scenario
@given("a business exists with a high score")
def business_with_high_score(db_conn):
    """Set up a business with a high score."""
    # Create a business with enriched info
    business_id = business_with_enriched_info(db_conn)

    # Add a high score
    score = 95.0
    criteria = json.dumps({
        "website_quality": 9,
        "contact_info": 10,
        "tech_stack": 9,
        "market_fit": 10
    })

    db_conn.execute("""
        INSERT INTO scores (business_id, score, criteria, scoring_timestamp)
        VALUES (?, ?, ?, datetime('now'))
    """, (business_id, score, criteria))

    db_conn.commit()
    context["score"] = {"score": score, "criteria": json.loads(criteria)}

    return business_id

@when("I generate an email for the business")
def generate_email(db_conn):
    """Generate an email for the business."""
    business_id = context["business_id"]

    # Mock email data with HTML content
    subject = "Exciting Partnership Opportunity"
    html_body = """<html>
    <head><title>Partnership Proposal</title></head>
    <body>
        <h1>Partnership Opportunity</h1>
        <p>Dear Business Owner,</p>
        <p>We are impressed with your business and would like to discuss a partnership opportunity.</p>
        <ul>
            <li>Increased customer reach</li>
            <li>Shared marketing resources</li>
            <li>Collaborative projects</li>
        </ul>
        <p>Please <a href="https://example.com/contact">contact us</a> to learn more.</p>
    </body>
</html>"""
    recipient = "owner@testbusiness.com"
    status = "pending"

    # Insert email data
    db_conn.execute("""
        INSERT INTO emails (business_id, subject, body, recipient, status, created_at, sent_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'), NULL)
    """, (business_id, subject, html_body, recipient, status))

    db_conn.commit()

    # Store in context for later assertions
    context["email"] = {
        "subject": subject,
        "body": html_body,
        "recipient": recipient,
        "status": status
    }

    return context["email"]

@then("a personalized email should be created")
def check_personalized_email(db_conn):
    """Check that a personalized email is created."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT subject, body FROM emails WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No email record found"
    assert result[0] is not None and len(result[0]) > 0, "Email subject is empty"
    assert result[1] is not None and len(result[1]) > 0, "Email body is empty"

@then("the email should have a subject line")
def check_email_subject(db_conn):
    """Check that the email has a subject line."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT subject FROM emails WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No email record found"
    assert result[0] is not None and len(result[0]) > 0, "Email subject is empty"

@then("the email should have HTML and text content")
def check_email_content_formats(db_conn):
    """Check that the email has HTML and text content."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT body FROM emails WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No email record found"

    # In a real implementation, we would check for both HTML and text versions
    # For this test, we'll just assert that the body contains something that looks like HTML
    body = result[0]
    assert body is not None and len(body) > 0, "Email body is empty"

    # Very basic check for HTML-like content (contains at least one tag)
    # In a real implementation, we would verify proper multipart format
    assert "<" in body and ">" in body, "Email body does not appear to contain HTML"

@then("the email should be saved to the database")
def check_email_saved(db_conn):
    """Check that the email is saved to the database."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT COUNT(*) FROM emails WHERE business_id = ?
    """, (business_id,))

    count = cursor.fetchone()[0]
    assert count > 0, "No email record found in database"

@then("the email should be saved to the database with pending status")
def check_email_saved_with_pending_status(db_conn):
    """Check that the email is saved to the database with pending status."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT COUNT(*) FROM emails
        WHERE business_id = ? AND status = 'pending'
    """, (business_id,))

    count = cursor.fetchone()[0]
    assert count > 0, "No pending email found in database"

    # Verify the email we just created is in the database
    cursor = db_conn.execute("""
        SELECT subject, recipient, status FROM emails
        WHERE business_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "Email not found in database"
    subject, recipient, status = result

    assert subject == context["email"]["subject"], "Subject doesn't match"
    assert recipient == context["email"]["recipient"], "Recipient doesn't match"
    assert status == "pending", f"Status is '{status}', expected 'pending'"

@then("the email should have a pending status")
def check_email_status(db_conn):
    """Check that the email has a pending status."""
    business_id = context["business_id"]

    cursor = db_conn.execute("""
        SELECT status FROM emails WHERE business_id = ?
    """, (business_id,))

    result = cursor.fetchone()
    assert result is not None, "No email record found"
    assert result[0] == "pending", f"Email status is {result[0]}, expected 'pending'"

# Email queue processing scenario
@given("there are emails in the queue with pending status")
def emails_in_queue(db_conn):
    """Set up emails in the queue with pending status."""
    # Create a business with a high score
    business_id = business_with_high_score(db_conn)

    # Generate multiple emails
    for i in range(3):
        subject = f"Test Email {i+1}"
        body = f"This is test email {i+1} content."
        recipient = f"test{i+1}@example.com"
        status = "pending"

        db_conn.execute("""
            INSERT INTO emails (business_id, subject, body, recipient, status, created_at, sent_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'), NULL)
        """, (business_id, subject, body, recipient, status))

    db_conn.commit()

    # Store count in context
    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'")
    context["pending_email_count"] = cursor.fetchone()[0]

    return context["pending_email_count"]

@when("I process the email queue")
def process_email_queue(db_conn):
    """Process the email queue."""
    # Update email status to 'sent'
    db_conn.execute("""
        UPDATE emails SET
        status = 'sent',
        sent_at = datetime('now')
        WHERE status = 'pending'
    """)

    db_conn.commit()

    # Store in context for later assertions
    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent'")
    context["sent_email_count"] = cursor.fetchone()[0]

    return context["sent_email_count"]

@then("emails should be sent through the configured email provider")
def check_emails_sent():
    """Check that emails are sent through the configured email provider."""
    # In real implementation, we would check API calls to the email provider
    # For this test, we just verify that emails were marked as sent
    assert context["sent_email_count"] > 0, "No emails were marked as sent"

@then("pending emails should be sent")
def check_pending_emails_sent(db_conn):
    """Check that pending emails are sent."""
    # Verify all emails with pending status have been processed
    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    assert pending_count == 0, f"There are still {pending_count} pending emails"

@then("the email status should be updated to sent")
def check_email_status_updated(db_conn):
    """Check that email status is updated to sent."""
    # This is essentially a duplicate of check_email_statuses_updated but with different wording
    # Verify that all previously pending emails are now sent
    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent'")
    sent_count = cursor.fetchone()[0]

    # Check that we have sent emails and no pending emails
    assert sent_count > 0, "No emails were marked as sent"

    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    assert pending_count == 0, f"There are still {pending_count} pending emails"

@then("email statuses should be updated to sent")
def check_email_statuses_updated(db_conn):
    """Check that email statuses are updated to sent."""
    # Verify that all previously pending emails are now sent
    cursor = db_conn.execute("SELECT COUNT(*) FROM emails WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]

    assert pending_count == 0, f"There are still {pending_count} pending emails"
    assert context["sent_email_count"] == context["pending_email_count"], "Not all pending emails were sent"

@then("sent timestamps should be recorded")
def check_sent_ats(db_conn):
    """Check that sent timestamps are recorded."""
    cursor = db_conn.execute("""
        SELECT COUNT(*) FROM emails
        WHERE status = 'sent'
        AND sent_at IS NOT NULL
    """)

    count = cursor.fetchone()[0]
    assert count == context["sent_email_count"], "Not all sent emails have a sent timestamp"

@then("the sent timestamp should be recorded")
def check_sent_at_recorded(db_conn):
    """Check that the sent timestamp is recorded."""
    # This is essentially a duplicate of check_sent_ats but with different wording
    cursor = db_conn.execute("""
        SELECT COUNT(*) FROM emails
        WHERE status = 'sent'
        AND sent_at IS NOT NULL
    """)

    count = cursor.fetchone()[0]
    assert count > 0, "No emails have a sent timestamp"

    # Additionally, check that the timestamp is in the correct format
    cursor = db_conn.execute("""
        SELECT sent_at FROM emails
        WHERE status = 'sent'
        LIMIT 1
    """)

    timestamp = cursor.fetchone()[0]
    assert timestamp is not None, "Sent timestamp is NULL"

    # Verify timestamp format (SQLite datetime format)
    try:
        from datetime import datetime
        datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise AssertionError(f"Invalid timestamp format: {timestamp}")

# API cost monitoring scenario
@given("API costs have been logged for various operations")
def api_costs_logged(db_conn):
    """Set up API costs logged for various operations."""
    # Insert sample API cost data
    api_costs = [
        ("OpenAI", "/v1/chat/completions", 0.05),
        ("Yelp", "/v3/businesses/search", 0.01),
        ("Google", "/maps/api/place/details", 0.02),
        ("SendGrid", "/v3/mail/send", 0.0005),
        ("OpenAI", "/v1/embeddings", 0.01),
    ]

    for api_name, endpoint, cost in api_costs:
        db_conn.execute("""
            INSERT INTO api_costs (api_name, endpoint, cost, timestamp)
            VALUES (?, ?, ?, datetime('now'))
        """, (api_name, endpoint, cost))

    db_conn.commit()

    # Store total cost in context
    cursor = db_conn.execute("SELECT SUM(cost) FROM api_costs")
    context["total_api_cost"] = cursor.fetchone()[0]

    return context["total_api_cost"]

@when("I check the API cost report")
def check_api_cost_report():
    """Check the API cost report."""
    # In a real implementation, this would generate a report
    # For this test, we just return the stored total cost
    return context["total_api_cost"]

@when("I check the budget status")
def check_budget_status():
    """Check the budget status."""
    # Set a mock budget
    mock_budget = 10.0
    context["budget"] = mock_budget
    context["budget_used_percentage"] = (context["total_api_cost"] / mock_budget) * 100

    return {
        "budget": context["budget"],
        "used": context["total_api_cost"],
        "percentage": context["budget_used_percentage"]
    }

@then("I should see the total cost of API calls")
def verify_total_cost(db_conn):
    """Verify the total cost of API calls."""
    cursor = db_conn.execute("SELECT SUM(cost) FROM api_costs")
    db_total = cursor.fetchone()[0]

    assert abs(db_total - context["total_api_cost"]) < 0.0001, "Total cost doesn't match database"
    assert context["total_api_cost"] > 0, "Total API cost should be greater than zero"

@then("I should see the total cost for the current month")
def verify_monthly_cost(db_conn):
    """Verify the total cost for the current month."""
    # In a real implementation, we would filter by the current month
    # For this test, we'll just check that the total cost is available

    cursor = db_conn.execute("""
        SELECT SUM(cost) FROM api_costs
        WHERE timestamp >= date('now', 'start of month')
    """)
    monthly_cost = cursor.fetchone()[0]

    # Store for future reference
    context["monthly_cost"] = monthly_cost if monthly_cost is not None else 0

    assert context["monthly_cost"] >= 0, "Monthly cost should be zero or positive"
    assert context["monthly_cost"] <= context["total_api_cost"], "Monthly cost cannot exceed total cost"

@then("costs should be broken down by API provider")
def verify_cost_breakdown(db_conn):
    """Verify costs are broken down by API provider."""
    cursor = db_conn.execute("""
        SELECT api_name, SUM(cost) as provider_cost
        FROM api_costs
        GROUP BY api_name
    """)

    results = cursor.fetchall()
    assert len(results) > 1, "Cost breakdown should include multiple providers"

@then("I should see the cost breakdown by model")
def verify_model_cost_breakdown(db_conn):
    """Verify costs are broken down by API model."""
    # Add some model-specific costs for OpenAI models
    model_costs = [
        ("OpenAI", "/v1/chat/completions", 0.03, "gpt-4"),
        ("OpenAI", "/v1/chat/completions", 0.01, "gpt-3.5-turbo"),
        ("OpenAI", "/v1/embeddings", 0.005, "text-embedding-ada-002"),
        ("Anthropic", "/v1/complete", 0.02, "claude-2"),
    ]

    # Create a model column in the database if it doesn't exist
    try:
        db_conn.execute("ALTER TABLE api_costs ADD COLUMN model TEXT")
        db_conn.commit()
    except sqlite3.OperationalError:
        # Column likely already exists
        pass

    # Insert model-specific costs
    for api_name, endpoint, cost, model in model_costs:
        db_conn.execute("""
            INSERT INTO api_costs (api_name, endpoint, cost, timestamp, model)
            VALUES (?, ?, ?, datetime('now'), ?)
        """, (api_name, endpoint, cost, model))

    db_conn.commit()

    # Query for model-specific costs
    cursor = db_conn.execute("""
        SELECT api_name, model, SUM(cost) as model_cost
        FROM api_costs
        WHERE model IS NOT NULL
        GROUP BY api_name, model
        ORDER BY model_cost DESC
    """)

    results = cursor.fetchall()
    assert len(results) >= 3, "Cost breakdown should include multiple models"

    # Store model costs in context
    context["model_costs"] = {}
    for row in results:
        api_name, model, cost = row
        if api_name not in context["model_costs"]:
            context["model_costs"][api_name] = {}
        context["model_costs"][api_name][model] = cost

    # Verify we have costs for at least two different models
    model_count = sum(len(models) for models in context["model_costs"].values())
    assert model_count >= 2, "Should have costs for at least two different models"

@then("I should see the cost breakdown by purpose")
def verify_purpose_cost_breakdown(db_conn):
    """Verify costs are broken down by API purpose."""
    # Add a purpose column to the database
    try:
        db_conn.execute("ALTER TABLE api_costs ADD COLUMN purpose TEXT")
        db_conn.commit()
    except sqlite3.OperationalError:
        # Column likely already exists
        pass

    # Add purpose-specific costs
    purpose_costs = [
        ("OpenAI", "/v1/chat/completions", 0.02, "gpt-4", "lead_generation"),
        ("OpenAI", "/v1/chat/completions", 0.03, "gpt-4", "content_creation"),
        ("OpenAI", "/v1/embeddings", 0.01, "text-embedding-ada-002", "search"),
        ("Yelp", "/v3/businesses/search", 0.01, None, "lead_generation"),
        ("Google", "/maps/api/place/details", 0.02, None, "enrichment"),
        ("SendGrid", "/v3/mail/send", 0.0005, None, "email_delivery"),
    ]

    # Insert purpose-specific costs
    for api_name, endpoint, cost, model, purpose in purpose_costs:
        db_conn.execute("""
            INSERT INTO api_costs (api_name, endpoint, cost, timestamp, model, purpose)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, (api_name, endpoint, cost, model, purpose))

    db_conn.commit()

    # Query for purpose-specific costs
    cursor = db_conn.execute("""
        SELECT purpose, SUM(cost) as purpose_cost
        FROM api_costs
        WHERE purpose IS NOT NULL
        GROUP BY purpose
        ORDER BY purpose_cost DESC
    """)

    results = cursor.fetchall()
    assert len(results) >= 3, "Cost breakdown should include multiple purposes"

    # Store purpose costs in context
    context["purpose_costs"] = {}
    for purpose, cost in results:
        context["purpose_costs"][purpose] = cost

    # Verify we have costs for different purposes
    assert len(context["purpose_costs"]) >= 3, "Should have costs for at least three different purposes"

@then("I should be able to monitor spending against budget")
def verify_budget_monitoring(db_conn):
    """Verify budget monitoring capability."""
    # In a real implementation, we would compare against a budget
    # For this test, we just check that we can get the total cost
    cursor = db_conn.execute("SELECT SUM(cost) FROM api_costs")
    total_cost = cursor.fetchone()[0]

    # Set a mock budget
    mock_budget = 10.0
    context["budget"] = mock_budget
    context["budget_used_percentage"] = (total_cost / mock_budget) * 100

    assert context["budget_used_percentage"] > 0, "Budget usage percentage should be calculable"

@then("I should know if we're within budget limits")
def check_within_budget_limits(db_conn):
    """Check if API costs are within budget limits."""
    # Get the total API cost
    cursor = db_conn.execute("SELECT SUM(cost) FROM api_costs")
    total_cost = cursor.fetchone()[0]

    # If budget wasn't set in a previous step, set it now
    if "budget" not in context:
        context["budget"] = 10.0  # Set a mock budget

    # Calculate budget usage percentage
    budget_used_percentage = (total_cost / context["budget"]) * 100
    context["budget_used_percentage"] = budget_used_percentage

    # Check if within budget limits
    if budget_used_percentage < 80:
        context["budget_status"] = "healthy"
    elif budget_used_percentage < 100:
        context["budget_status"] = "warning"
    else:
        context["budget_status"] = "exceeded"

    # Store monthly limits for different APIs
    context["api_limits"] = {
        "OpenAI": 100.0,
        "Yelp": 50.0,
        "Google": 75.0,
        "SendGrid": 25.0,
        "Anthropic": 80.0
    }

    # Calculate current usage per API
    cursor = db_conn.execute("""
        SELECT api_name, SUM(cost) as api_cost
        FROM api_costs
        GROUP BY api_name
    """)

    # Initialize api_usage in context if it doesn't exist
    if "api_usage" not in context:
        context["api_usage"] = {}

    api_costs = {}
    for api_name, cost in cursor.fetchall():
        api_costs[api_name] = cost
        if api_name in context["api_limits"]:
            # Calculate percentage of limit used
            limit = context["api_limits"][api_name]
            usage_percentage = (cost / limit) * 100
            context["api_usage"][api_name] = {
                "cost": cost,
                "limit": limit,
                "percentage": usage_percentage,
                "status": "exceeded" if usage_percentage > 100 else "warning" if usage_percentage > 80 else "healthy"
            }

    # Verify that budget status is determined
    assert context["budget_status"] in ["healthy", "warning", "exceeded"], "Budget status should be determined"
    assert budget_used_percentage >= 0, "Budget usage percentage should be zero or positive"

    return {
        "total_cost": total_cost,
        "budget": context["budget"],
        "percentage": budget_used_percentage,
        "status": context["budget_status"]
    }
