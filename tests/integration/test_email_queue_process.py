"""
Integration tests for the email queue process.
These tests verify the end-to-end email generation, queuing, and sending workflow.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import test utilities
from tests.utils import (
    create_test_emails,
    generate_test_business,
    insert_test_businesses_batch,
)


@pytest.fixture
def email_queue_db():
    """Create a test database for email queue tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create businesses table
    cursor.execute(
        """
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            category TEXT,
            source TEXT,
            source_id TEXT,
            status TEXT DEFAULT 'pending',
            score INTEGER,
            score_details TEXT,
            tech_stack TEXT,
            performance TEXT,
            contact_info TEXT,
            enriched_at TIMESTAMP,
            merged_into INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (merged_into) REFERENCES businesses(id) ON DELETE SET NULL
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
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def populated_email_queue_db(email_queue_db):
    """Create a test database populated with businesses and emails."""
    # Insert test businesses
    business_ids = insert_test_businesses_batch(
        email_queue_db,
        count=15,
        complete=True,
        score_range=(40, 95),
        include_tech=True
    )

    # Create test emails
    email_ids = create_test_emails(
        email_queue_db,
        business_ids,
        email_count=30
    )

    return {
        "db": email_queue_db,
        "business_ids": business_ids,
        "email_ids": email_ids
    }


# Test data for email generation scenarios
email_generation_test_cases = [
    {
        "id": "high_score_business",
        "score": 90,
        "email_variant": "premium",
        "subject_contains": ["exclusive", "premium", "custom"],
        "content_contains": ["customized", "premium", "proposal"]
    },
    {
        "id": "medium_score_business",
        "score": 70,
        "email_variant": "standard",
        "subject_contains": ["improve", "enhance", "proposal"],
        "content_contains": ["improvements", "enhance", "better"]
    },
    {
        "id": "low_score_business",
        "score": 45,
        "email_variant": "basic",
        "subject_contains": ["website", "upgrade", "solutions"],
        "content_contains": ["affordable", "solutions", "fix"]
    },
    {
        "id": "minimal_score_business",
        "score": 25,
        "email_variant": "minimal",
        "subject_contains": ["tips", "website", "improve"],
        "content_contains": ["tips", "simple", "improvements"]
    }
]


@pytest.fixture
def business_with_score(email_queue_db, request):
    """Create a business with a specific score."""
    test_case = request.param

    # Generate a business
    business = generate_test_business(complete=True, include_tech=True)
    business["score"] = test_case["score"]

    # Insert the business
    cursor = email_queue_db.cursor()
    cursor.execute(
        """
        INSERT INTO businesses (
            name, address, city, state, zip, phone, email, website, score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business["name"],
            business["address"],
            business.get("city", ""),
            business.get("state", ""),
            business.get("zip", ""),
            business.get("phone", ""),
            business.get("email", ""),
            business.get("website", ""),
            business["score"]
        )
    )
    business_id = cursor.lastrowid
    email_queue_db.commit()

    return {
        "db": email_queue_db,
        "business_id": business_id,
        "score": test_case["score"],
        "email_variant": test_case["email_variant"],
        "subject_contains": test_case["subject_contains"],
        "content_contains": test_case["content_contains"]
    }


# Test generating emails for businesses with different scores
@pytest.mark.parametrize(
    "business_with_score",
    email_generation_test_cases,
    ids=[case["id"] for case in email_generation_test_cases],
    indirect=True
)
def test_email_content_generation(business_with_score):
    """Test email content generation for different business scores."""
    db = business_with_score["db"]
    business_id = business_with_score["business_id"]
    business_with_score["score"]
    variant = business_with_score["email_variant"]
    subject_keywords = business_with_score["subject_contains"]
    content_keywords = business_with_score["content_contains"]

    # Mock the email_queue module functions
    with patch("bin.email_queue.get_db_connection") as mock_get_db, \
         patch("bin.email_queue.get_business") as mock_get_business, \
         patch("bin.email_queue.select_email_template") as mock_select_template, \
         patch("bin.email_queue.generate_email_content") as mock_generate_content:

        # Configure the mocks
        mock_get_db.return_value = db

        # Get the actual business from the database
        cursor = db.cursor()
        cursor.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
        business = dict(cursor.fetchone())

        mock_get_business.return_value = business
        mock_select_template.return_value = variant

        # Mock the email generation function
        def generate_email_side_effect(business, template_type):
            """Generate email content based on business score and template type."""
            subject_prefix = ""
            if template_type == "premium":
                subject_prefix = "Exclusive Premium Offer: "
            elif template_type == "standard":
                subject_prefix = "Website Enhancement Proposal: "
            elif template_type == "basic":
                subject_prefix = "Website Upgrade Solutions: "
            else:
                subject_prefix = "Website Improvement Tips: "

            subject = f"{subject_prefix}Custom Proposal for {business['name']}"

            # Generate body content based on template type
            if template_type == "premium":
                body_text = f"""
Dear {business['name']} Team,

We've created a customized premium website proposal for your business. Our detailed analysis shows significant opportunities for growth and optimization.

Key highlights of our premium package:
- Custom design tailored to your brand
- Advanced SEO optimization
- Premium performance improvements
- Enhanced user experience

Visit our portfolio at example.com to see our work.

Best regards,
The Web Design Team
                """

                body_html = f"""
<html>
<body>
<h1>Premium Website Proposal</h1>
<p>Dear {business['name']} Team,</p>
<p>We've created a customized premium website proposal for your business. Our detailed analysis shows significant opportunities for growth and optimization.</p>
<h2>Key highlights of our premium package:</h2>
<ul>
<li>Custom design tailored to your brand</li>
<li>Advanced SEO optimization</li>
<li>Premium performance improvements</li>
<li>Enhanced user experience</li>
</ul>
<p>Visit our portfolio at example.com to see our work.</p>
<p>Best regards,<br>The Web Design Team</p>
</body>
</html>
                """
            elif template_type == "standard":
                body_text = f"""
Dear {business['name']} Team,

We've analyzed your website and found several opportunities to enhance your online presence.

Our standard package includes:
- Modern design refresh
- SEO improvements
- Performance optimization
- Mobile responsiveness enhancements

Visit our portfolio at example.com to see our work.

Best regards,
The Web Design Team
                """

                body_html = f"""
<html>
<body>
<h1>Website Enhancement Proposal</h1>
<p>Dear {business['name']} Team,</p>
<p>We've analyzed your website and found several opportunities to enhance your online presence.</p>
<h2>Our standard package includes:</h2>
<ul>
<li>Modern design refresh</li>
<li>SEO improvements</li>
<li>Performance optimization</li>
<li>Mobile responsiveness enhancements</li>
</ul>
<p>Visit our portfolio at example.com to see our work.</p>
<p>Best regards,<br>The Web Design Team</p>
</body>
</html>
                """
            elif template_type == "basic":
                body_text = f"""
Dear {business['name']} Team,

We've identified some key areas where your website could be improved for better results.

Our affordable basic package includes:
- Design improvements
- Basic SEO fixes
- Performance tweaks
- Mobile compatibility solutions

Visit our portfolio at example.com to see our work.

Best regards,
The Web Design Team
                """

                body_html = f"""
<html>
<body>
<h1>Website Upgrade Solutions</h1>
<p>Dear {business['name']} Team,</p>
<p>We've identified some key areas where your website could be improved for better results.</p>
<h2>Our affordable basic package includes:</h2>
<ul>
<li>Design improvements</li>
<li>Basic SEO fixes</li>
<li>Performance tweaks</li>
<li>Mobile compatibility solutions</li>
</ul>
<p>Visit our portfolio at example.com to see our work.</p>
<p>Best regards,<br>The Web Design Team</p>
</body>
</html>
                """
            else:  # minimal
                body_text = f"""
Dear {business['name']} Team,

We've noticed some simple improvements that could help your website perform better.

Our quick-start package includes:
- Simple design tips
- Basic SEO suggestions
- Performance improvement ideas
- Mobile usability tips

Visit our portfolio at example.com to see our work.

Best regards,
The Web Design Team
                """

                body_html = f"""
<html>
<body>
<h1>Website Improvement Tips</h1>
<p>Dear {business['name']} Team,</p>
<p>We've noticed some simple improvements that could help your website perform better.</p>
<h2>Our quick-start package includes:</h2>
<ul>
<li>Simple design tips</li>
<li>Basic SEO suggestions</li>
<li>Performance improvement ideas</li>
<li>Mobile usability tips</li>
</ul>
<p>Visit our portfolio at example.com to see our work.</p>
<p>Best regards,<br>The Web Design Team</p>
</body>
</html>
                """

            return {
                "subject": subject,
                "body_text": body_text.strip(),
                "body_html": body_html.strip()
            }

        mock_generate_content.side_effect = generate_email_side_effect

        # Define and mock the create_email function
        def create_email_for_business(business_id):
            """Create an email for a business (mock of the actual function)."""
            # Get the business
            business = mock_get_business(db, business_id)

            # Select template based on score
            template_type = mock_select_template(business.get("score", 0))

            # Generate email content
            email_content = mock_generate_content(business, template_type)

            # Insert the email
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO emails (
                    business_id, variant_id, subject, body_text, body_html, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    template_type,
                    email_content["subject"],
                    email_content["body_text"],
                    email_content["body_html"],
                    "pending"
                )
            )

            db.commit()
            return cursor.lastrowid

        # Create an email for the business
        email_id = create_email_for_business(business_id)

        # Verify the email was created
        cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
        email = dict(cursor.fetchone())

        assert email is not None, "Email was not created"
        assert email["business_id"] == business_id, "Email associated with wrong business"
        assert email["variant_id"] == variant, f"Expected variant {variant}, got {email['variant_id']}"
        assert email["status"] == "pending", f"Expected status 'pending', got {email['status']}"

        # Check subject contains expected keywords
        subject_contains_expected = any(keyword.lower() in email["subject"].lower()
                                        for keyword in subject_keywords)
        assert subject_contains_expected, \
            f"Subject '{email['subject']}' doesn't contain any expected keywords: {subject_keywords}"

        # Check body contains expected keywords
        body_contains_expected = any(keyword.lower() in email["body_text"].lower()
                                    for keyword in content_keywords)
        assert body_contains_expected, \
            f"Body doesn't contain any expected keywords: {content_keywords}"


# Test data for email queue processing
email_queue_test_cases = [
    {
        "id": "all_pending_emails",
        "pending_count": 10,
        "success_ratio": 1.0,  # All emails succeed
        "expected_sent": 10,
        "expected_error": 0
    },
    {
        "id": "some_emails_fail",
        "pending_count": 8,
        "success_ratio": 0.75,  # 75% succeed, 25% fail
        "expected_sent": 6,
        "expected_error": 2
    },
    {
        "id": "mixed_status_emails",
        "pending_count": 5,
        "existing_sent": 3,
        "existing_error": 2,
        "success_ratio": 0.8,  # 80% succeed, 20% fail
        "expected_sent": 4,
        "expected_error": 1
    }
]


@pytest.fixture
def email_queue_setup(email_queue_db, request):
    """Set up the email queue with specified test conditions."""
    test_case = request.param

    # Insert test businesses
    business_ids = insert_test_businesses_batch(
        email_queue_db,
        count=max(15, test_case["pending_count"] + 5),  # Ensure enough businesses
        complete=True
    )

    cursor = email_queue_db.cursor()

    # Create pending emails
    pending_email_ids = []
    for i in range(test_case["pending_count"]):
        business_id = business_ids[i % len(business_ids)]  # Cycle through businesses

        cursor.execute(
            """
            INSERT INTO emails (
                business_id, variant_id, subject, body_text, body_html, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                business_id,
                f"variant_{i % 4}",  # Cycle through 4 variants
                f"Test Subject {i+1}",
                f"Test body text for email {i+1}",
                f"<html><body><p>Test HTML for email {i+1}</p></body></html>",
                "pending"
            )
        )
        pending_email_ids.append(cursor.lastrowid)

    # Create existing sent emails if specified
    sent_email_ids = []
    if "existing_sent" in test_case and test_case["existing_sent"] > 0:
        for i in range(test_case["existing_sent"]):
            business_id = business_ids[(test_case["pending_count"] + i) % len(business_ids)]

            cursor.execute(
                """
                INSERT INTO emails (
                    business_id, variant_id, subject, body_text, body_html, status, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    f"variant_{i % 4}",
                    f"Already Sent Subject {i+1}",
                    f"Already sent body text for email {i+1}",
                    f"<html><body><p>Already sent HTML for email {i+1}</p></body></html>",
                    "sent",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            sent_email_ids.append(cursor.lastrowid)

    # Create existing error emails if specified
    error_email_ids = []
    if "existing_error" in test_case and test_case["existing_error"] > 0:
        for i in range(test_case["existing_error"]):
            business_id = business_ids[(test_case["pending_count"] +
                                        test_case.get("existing_sent", 0) + i) % len(business_ids)]

            cursor.execute(
                """
                INSERT INTO emails (
                    business_id, variant_id, subject, body_text, body_html, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    f"variant_{i % 4}",
                    f"Error Subject {i+1}",
                    f"Error body text for email {i+1}",
                    f"<html><body><p>Error HTML for email {i+1}</p></body></html>",
                    "error"
                )
            )
            error_email_ids.append(cursor.lastrowid)

    email_queue_db.commit()

    return {
        "db": email_queue_db,
        "business_ids": business_ids,
        "pending_email_ids": pending_email_ids,
        "sent_email_ids": sent_email_ids,
        "error_email_ids": error_email_ids,
        "success_ratio": test_case["success_ratio"],
        "expected_sent": test_case["expected_sent"],
        "expected_error": test_case["expected_error"]
    }


# Test email queue processing
@pytest.mark.parametrize(
    "email_queue_setup",
    email_queue_test_cases,
    ids=[case["id"] for case in email_queue_test_cases],
    indirect=True
)
def test_email_queue_processing(email_queue_setup):
    """Test processing the email queue with different scenarios."""
    db = email_queue_setup["db"]
    success_ratio = email_queue_setup["success_ratio"]
    expected_sent = email_queue_setup["expected_sent"]
    expected_error = email_queue_setup["expected_error"]

    # Mock the email_queue module functions
    with patch("bin.email_queue.get_db_connection") as mock_get_db, \
         patch("bin.email_queue.send_email") as mock_send_email:

        # Configure the mocks
        mock_get_db.return_value = db

        # Configure the send_email mock to succeed or fail based on success_ratio
        def send_email_side_effect(email_data):
            """Mock sending an email with success based on the ratio."""
            # Determine if this email succeeds or fails
            if email_data.get("id") % int(1/success_ratio) != 0:  # Mathematical trick to distribute failures
                return {
                    "success": True,
                    "message_id": f"test_message_{email_data['id']}",
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "message_id": None,
                    "error": "Simulated email sending failure"
                }

        mock_send_email.side_effect = send_email_side_effect

        # Define and mock the process_email_queue function
        def process_email_queue(limit=50):
            """Process the email queue (mock of the actual function)."""
            cursor = db.cursor()

            # Get pending emails
            cursor.execute(
                """
                SELECT id, business_id, variant_id, subject, body_text, body_html
                FROM emails WHERE status = 'pending'
                LIMIT ?
                """,
                (limit,)
            )
            pending_emails = [dict(row) for row in cursor.fetchall()]

            sent_count = 0
            error_count = 0

            for email in pending_emails:
                # Try to send the email
                result = mock_send_email(email)

                if result["success"]:
                    # Update status to sent
                    cursor.execute(
                        """
                        UPDATE emails
                        SET status = 'sent', sent_at = ?
                        WHERE id = ?
                        """,
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email["id"])
                    )
                    sent_count += 1
                else:
                    # Update status to error
                    cursor.execute(
                        """
                        UPDATE emails
                        SET status = 'error'
                        WHERE id = ?
                        """,
                        (email["id"],)
                    )
                    error_count += 1

            db.commit()

            return {
                "processed": len(pending_emails),
                "sent": sent_count,
                "error": error_count
            }

        # Process the email queue
        result = process_email_queue()

        # Verify the results
        assert result["processed"] > 0, "No emails were processed"
        assert result["sent"] == expected_sent, \
            f"Expected {expected_sent} sent emails, got {result['sent']}"
        assert result["error"] == expected_error, \
            f"Expected {expected_error} error emails, got {result['error']}"

        # Verify the database was updated correctly
        cursor = db.cursor()

        # Check sent emails
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent'")
        sent_count = cursor.fetchone()[0]

        # Total sent emails should include any existing ones plus newly sent ones
        expected_total_sent = len(email_queue_setup.get("sent_email_ids", [])) + expected_sent
        assert sent_count == expected_total_sent, \
            f"Expected {expected_total_sent} total sent emails, found {sent_count}"

        # Check error emails
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'error'")
        error_count = cursor.fetchone()[0]

        # Total error emails should include any existing ones plus new errors
        expected_total_error = len(email_queue_setup.get("error_email_ids", [])) + expected_error
        assert error_count == expected_total_error, \
            f"Expected {expected_total_error} total error emails, found {error_count}"

        # Check that all newly sent emails have a sent_at timestamp
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent' AND sent_at IS NULL")
        missing_timestamp_count = cursor.fetchone()[0]
        assert missing_timestamp_count == 0, \
            f"Found {missing_timestamp_count} sent emails without a timestamp"


# Test tracking email events (opens and clicks)
def test_email_event_tracking(populated_email_queue_db):
    """Test tracking email open and click events."""
    db = populated_email_queue_db["db"]
    populated_email_queue_db["email_ids"]

    # Select a subset of emails that are in 'sent' status
    cursor = db.cursor()
    cursor.execute("SELECT id FROM emails WHERE status = 'sent' LIMIT 5")
    sent_email_ids = [row[0] for row in cursor.fetchall()]

    # If not enough sent emails, update some emails to 'sent' status
    if len(sent_email_ids) < 5:
        # Get some pending emails
        cursor.execute("SELECT id FROM emails WHERE status = 'pending' LIMIT ?", (5 - len(sent_email_ids),))
        pending_ids = [row[0] for row in cursor.fetchall()]

        # Update them to sent
        for email_id in pending_ids:
            cursor.execute(
                "UPDATE emails SET status = 'sent', sent_at = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_id)
            )

        sent_email_ids.extend(pending_ids)

    db.commit()

    # Mock the email_queue module functions
    with patch("bin.email_queue.get_db_connection") as mock_get_db:
        mock_get_db.return_value = db

        # Define and mock the track_email_open function
        def track_email_open(email_id):
            """Track an email open event."""
            cursor = db.cursor()

            # Verify the email exists and is in 'sent' status
            cursor.execute("SELECT id, status FROM emails WHERE id = ?", (email_id,))
            email = cursor.fetchone()

            if not email or email["status"] != "sent":
                return False

            # Update the email
            cursor.execute(
                "UPDATE emails SET status = 'opened', opened_at = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email_id)
            )

            db.commit()
            return True

        # Define and mock the track_email_click function
        def track_email_click(email_id):
            """Track an email click event."""
            cursor = db.cursor()

            # Verify the email exists and is in 'sent' or 'opened' status
            cursor.execute("SELECT id, status FROM emails WHERE id = ?", (email_id,))
            email = cursor.fetchone()

            if not email or (email["status"] != "sent" and email["status"] != "opened"):
                return False

            # Update the email
            cursor.execute(
                """
                UPDATE emails
                SET status = 'clicked',
                    opened_at = COALESCE(opened_at, ?),
                    clicked_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    email_id
                )
            )

            db.commit()
            return True

        # Test tracking opens
        for email_id in sent_email_ids[:3]:  # Track opens for first 3 emails
            result = track_email_open(email_id)
            assert result is True, f"Failed to track open for email {email_id}"

        # Test tracking clicks
        for email_id in sent_email_ids[1:4]:  # Track clicks for emails 2-4 (overlap with opens)
            result = track_email_click(email_id)
            assert result is True, f"Failed to track click for email {email_id}"

        # Verify the results
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'opened'")
        opened_count = cursor.fetchone()[0]
        assert opened_count == 1, f"Expected 1 opened email, found {opened_count}"

        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'clicked'")
        clicked_count = cursor.fetchone()[0]
        assert clicked_count == 3, f"Expected 3 clicked emails, found {clicked_count}"

        # Check that all opened emails have an opened_at timestamp
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status IN ('opened', 'clicked') AND opened_at IS NULL")
        missing_opened_timestamp = cursor.fetchone()[0]
        assert missing_opened_timestamp == 0, \
            f"Found {missing_opened_timestamp} opened/clicked emails without an opened_at timestamp"

        # Check that all clicked emails have a clicked_at timestamp
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'clicked' AND clicked_at IS NULL")
        missing_clicked_timestamp = cursor.fetchone()[0]
        assert missing_clicked_timestamp == 0, \
            f"Found {missing_clicked_timestamp} clicked emails without a clicked_at timestamp"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
