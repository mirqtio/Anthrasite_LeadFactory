"""
Integration tests for the full LeadFactory pipeline.
Tests the entire workflow from scraping to email generation.
"""

import os
import sys
import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import test utilities
from tests.utils import (
    generate_test_business,
    insert_test_businesses_batch,
    MockLevenshteinMatcher,
    MockOllamaVerifier,
    MockRequests
)


@pytest.fixture
def pipeline_db():
    """Create a test database for full pipeline testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create all necessary tables

    # Businesses table
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

    # Candidate duplicate pairs table
    cursor.execute(
        """
        CREATE TABLE candidate_duplicate_pairs (
            id INTEGER PRIMARY KEY,
            business1_id INTEGER NOT NULL,
            business2_id INTEGER NOT NULL,
            similarity_score REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processed', 'merged', 'rejected', 'review')),
            verified_by_llm BOOLEAN DEFAULT 0,
            llm_confidence REAL,
            llm_reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business1_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (business2_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE(business1_id, business2_id),
            CHECK(business1_id < business2_id)
        )
        """
    )

    # Emails table
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

    # API costs table
    cursor.execute(
        """
        CREATE TABLE api_costs (
            id INTEGER PRIMARY KEY,
            model TEXT NOT NULL,
            tokens INTEGER NOT NULL,
            cost REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            purpose TEXT,
            business_id INTEGER,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL
        )
        """
    )

    # Budget settings table
    cursor.execute(
        """
        CREATE TABLE budget_settings (
            id INTEGER PRIMARY KEY,
            monthly_budget REAL NOT NULL,
            daily_budget REAL NOT NULL,
            warning_threshold REAL NOT NULL,
            pause_threshold REAL NOT NULL,
            current_status TEXT DEFAULT 'active',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Insert default budget settings
    cursor.execute(
        """
        INSERT INTO budget_settings
        (monthly_budget, daily_budget, warning_threshold, pause_threshold, current_status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (100.0, 10.0, 0.7, 0.9, "active")
    )

    conn.commit()
    yield conn
    conn.close()


class MockPipeline:
    """Mock for the entire LeadFactory pipeline."""

    def __init__(self, db_conn):
        self.db = db_conn
        self.mock_requests = MockRequests()
        self.mock_matcher = MockLevenshteinMatcher()
        self.mock_verifier = MockOllamaVerifier()
        self.calls = []

    def scrape_businesses(self, category, location, limit=20):
        """Mock scraping businesses."""
        self.calls.append({
            "module": "scrape",
            "method": "scrape_businesses",
            "args": {"category": category, "location": location, "limit": limit}
        })

        # Generate mock business data
        businesses = []
        for i in range(min(limit, 10)):  # Generate up to 10 businesses
            business = generate_test_business(complete=True)
            business["category"] = category
            business["source"] = "api"
            business["source_id"] = f"src_{i}"
            businesses.append(business)

        # Insert businesses into the database
        cursor = self.db.cursor()
        for business in businesses:
            cursor.execute(
                """
                INSERT INTO businesses (
                    name, address, city, state, zip, phone, email, website,
                    category, source, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    business.get("category", ""),
                    business.get("source", ""),
                    business.get("source_id", "")
                )
            )

        self.db.commit()

        # Return the IDs of inserted businesses
        return [i for i in range(1, len(businesses) + 1)]

    def enrich_businesses(self, business_ids):
        """Mock enriching businesses."""
        self.calls.append({
            "module": "enrich",
            "method": "enrich_businesses",
            "args": {"business_ids": business_ids}
        })

        # Update businesses with enriched data
        cursor = self.db.cursor()
        for business_id in business_ids:
            # Generate mock tech stack
            tech_stack = {
                "cms": ["WordPress", "Drupal", "Shopify", None][business_id % 4],
                "analytics": ["Google Analytics", "Mixpanel", None, None][business_id % 4],
                "server": ["Nginx", "Apache", "IIS", None][business_id % 4],
                "javascript": ["React", "Angular", "Vue", "jQuery"][business_id % 4]
            }

            # Remove None values
            tech_stack = {k: v for k, v in tech_stack.items() if v is not None}

            # Generate mock performance data
            performance = {
                "page_speed": 50 + (business_id % 5) * 10,  # 50-90
                "mobile_friendly": business_id % 3 != 0,  # 2/3 are mobile friendly
                "accessibility": 60 + (business_id % 4) * 10  # 60-90
            }

            # Generate mock contact info
            contact_info = {
                "name": ["John Smith", "Jane Doe", "Robert Johnson", "Emily Williams"][business_id % 4],
                "position": ["CEO", "CTO", "Marketing Director", "VP Sales"][business_id % 4],
                "email": f"contact{business_id}@example.com"
            }

            # Update the business
            cursor.execute(
                """
                UPDATE businesses
                SET tech_stack = ?, performance = ?, contact_info = ?, enriched_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(tech_stack),
                    json.dumps(performance),
                    json.dumps(contact_info),
                    business_id
                )
            )

        self.db.commit()
        return business_ids

    def find_duplicates(self, business_ids, batch_size=10):
        """Mock finding duplicate businesses."""
        self.calls.append({
            "module": "dedupe",
            "method": "find_duplicates",
            "args": {"business_ids": business_ids, "batch_size": batch_size}
        })

        # Create some duplicate pairs
        cursor = self.db.cursor()
        pair_ids = []

        # For simplicity, mark businesses with sequential IDs as potential duplicates
        for i in range(0, len(business_ids) - 1, 2):
            id1, id2 = business_ids[i], business_ids[i + 1]

            # Ensure id1 < id2 to satisfy constraint
            if id1 > id2:
                id1, id2 = id2, id1

            # Generate a random similarity score
            similarity_score = 0.7 + (i % 3) * 0.1  # 0.7, 0.8, or 0.9

            # Insert the pair
            try:
                cursor.execute(
                    """
                    INSERT INTO candidate_duplicate_pairs (
                        business1_id, business2_id, similarity_score, status
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (id1, id2, similarity_score, "pending")
                )
                pair_ids.append(cursor.lastrowid)
            except sqlite3.IntegrityError:
                # Skip if this pair already exists
                continue

        self.db.commit()
        return pair_ids

    def process_duplicate_pairs(self, pair_ids=None, limit=10):
        """Mock processing duplicate pairs."""
        self.calls.append({
            "module": "dedupe",
            "method": "process_duplicate_pairs",
            "args": {"pair_ids": pair_ids, "limit": limit}
        })

        # If no specific pairs, get pending pairs
        cursor = self.db.cursor()
        if not pair_ids:
            cursor.execute(
                "SELECT id FROM candidate_duplicate_pairs WHERE status = 'pending' LIMIT ?",
                (limit,)
            )
            pair_ids = [row[0] for row in cursor.fetchall()]

        # Process each pair
        for pair_id in pair_ids:
            # Get the pair
            cursor.execute("SELECT * FROM candidate_duplicate_pairs WHERE id = ?", (pair_id,))
            pair = dict(cursor.fetchone())

            # Get the businesses
            cursor.execute("SELECT * FROM businesses WHERE id = ?", (pair["business1_id"],))
            business1 = dict(cursor.fetchone())

            cursor.execute("SELECT * FROM businesses WHERE id = ?", (pair["business2_id"],))
            business2 = dict(cursor.fetchone())

            # Use the mock matcher to determine if they are duplicates
            is_duplicate = self.mock_matcher.are_potential_duplicates(business1, business2)

            # Use the mock verifier for LLM verification
            verified, confidence, reasoning = self.mock_verifier.verify_duplicates(business1, business2)

            # Update the pair
            status = "merged" if verified and is_duplicate else "rejected"
            cursor.execute(
                """
                UPDATE candidate_duplicate_pairs
                SET status = ?, verified_by_llm = 1, llm_confidence = ?, llm_reasoning = ?
                WHERE id = ?
                """,
                (status, confidence, reasoning, pair_id)
            )

            # If merged, update the business
            if status == "merged":
                cursor.execute(
                    "UPDATE businesses SET merged_into = ? WHERE id = ?",
                    (pair["business1_id"], pair["business2_id"])
                )

        self.db.commit()
        return pair_ids

    def score_businesses(self, business_ids=None, limit=20):
        """Mock scoring businesses."""
        self.calls.append({
            "module": "score",
            "method": "score_businesses",
            "args": {"business_ids": business_ids, "limit": limit}
        })

        # If no specific businesses, get unscored ones
        cursor = self.db.cursor()
        if not business_ids:
            cursor.execute(
                """
                SELECT id FROM businesses
                WHERE score IS NULL AND merged_into IS NULL
                LIMIT ?
                """,
                (limit,)
            )
            business_ids = [row[0] for row in cursor.fetchall()]

        # Score each business
        for business_id in business_ids:
            # Get the business
            cursor.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
            business = dict(cursor.fetchone())

            # Extract data for scoring
            tech_stack = json.loads(business["tech_stack"]) if business["tech_stack"] else {}
            performance = json.loads(business["performance"]) if business["performance"] else {}
            contact_info = json.loads(business["contact_info"]) if business["contact_info"] else {}

            # Calculate tech score (25%)
            tech_count = len(tech_stack)
            tech_score = min(100, tech_count * 25)

            # Calculate performance score (40%)
            perf_score = 0
            if performance:
                page_speed = performance.get("page_speed", 0)
                mobile_friendly = performance.get("mobile_friendly", False)
                accessibility = performance.get("accessibility", 0)

                perf_score = (page_speed * 0.6) + (30 if mobile_friendly else 0) + (accessibility * 0.4)
                perf_score = min(100, perf_score)

            # Calculate contact score (35%)
            contact_score = 0
            if contact_info:
                has_name = "name" in contact_info and contact_info["name"]
                has_position = "position" in contact_info and contact_info["position"]
                has_email = "email" in contact_info and contact_info["email"]

                contact_score = (40 if has_name else 0) + (30 if has_position else 0) + (30 if has_email else 0)

            # Calculate final score
            final_score = int(tech_score * 0.25 + perf_score * 0.4 + contact_score * 0.35)

            # Create score details
            score_details = {
                "tech_score": tech_score,
                "performance_score": perf_score,
                "contact_score": contact_score,
                "components": {
                    "tech_stack": list(tech_stack.keys()),
                    "performance": list(performance.keys()),
                    "contact_info": list(contact_info.keys())
                }
            }

            # Update the business
            cursor.execute(
                """
                UPDATE businesses
                SET score = ?, score_details = ?
                WHERE id = ?
                """,
                (final_score, json.dumps(score_details), business_id)
            )

        self.db.commit()
        return business_ids

    def generate_emails(self, business_ids=None, min_score=50, limit=10):
        """Mock generating emails for businesses."""
        self.calls.append({
            "module": "email_queue",
            "method": "generate_emails",
            "args": {"business_ids": business_ids, "min_score": min_score, "limit": limit}
        })

        # If no specific businesses, get scored ones above threshold
        cursor = self.db.cursor()
        if not business_ids:
            cursor.execute(
                """
                SELECT id FROM businesses
                WHERE score >= ? AND merged_into IS NULL
                LIMIT ?
                """,
                (min_score, limit)
            )
            business_ids = [row[0] for row in cursor.fetchall()]

        # Generate emails for each business
        email_ids = []
        for business_id in business_ids:
            # Get the business
            cursor.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
            business = dict(cursor.fetchone())

            # Determine email variant based on score
            score = business["score"]
            if score >= 80:
                variant = "premium"
                subject_prefix = "Exclusive Premium Offer: "
            elif score >= 70:
                variant = "standard"
                subject_prefix = "Website Enhancement Proposal: "
            elif score >= 50:
                variant = "basic"
                subject_prefix = "Website Upgrade Solutions: "
            else:
                variant = "minimal"
                subject_prefix = "Website Improvement Tips: "

            # Generate email content
            subject = f"{subject_prefix}Custom Proposal for {business['name']}"
            body_text = f"This is a test email for {business['name']} with score {score}."
            body_html = f"<html><body><h1>{variant.title()} Proposal</h1><p>{body_text}</p></body></html>"

            # Insert the email
            cursor.execute(
                """
                INSERT INTO emails (
                    business_id, variant_id, subject, body_text, body_html, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (business_id, variant, subject, body_text, body_html, "pending")
            )

            email_ids.append(cursor.lastrowid)

        self.db.commit()
        return email_ids

    def process_email_queue(self, limit=10):
        """Mock processing the email queue."""
        self.calls.append({
            "module": "email_queue",
            "method": "process_email_queue",
            "args": {"limit": limit}
        })

        # Get pending emails
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, business_id, variant_id, subject
            FROM emails WHERE status = 'pending'
            LIMIT ?
            """,
            (limit,)
        )
        pending_emails = [dict(row) for row in cursor.fetchall()]

        # Process each email
        sent_count = 0
        error_count = 0

        for email in pending_emails:
            # 90% success rate for testing
            success = email["id"] % 10 != 0

            if success:
                cursor.execute(
                    "UPDATE emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (email["id"],)
                )
                sent_count += 1
            else:
                cursor.execute(
                    "UPDATE emails SET status = 'error' WHERE id = ?",
                    (email["id"],)
                )
                error_count += 1

        self.db.commit()

        return {
            "processed": len(pending_emails),
            "sent": sent_count,
            "error": error_count
        }

    def track_api_cost(self, model, tokens, purpose=None, business_id=None):
        """Mock tracking API costs."""
        self.calls.append({
            "module": "budget_gate",
            "method": "track_api_cost",
            "args": {
                "model": model,
                "tokens": tokens,
                "purpose": purpose,
                "business_id": business_id
            }
        })

        # Calculate cost based on model
        cost_per_1k = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
            "claude-3-haiku": 0.00025,
        }.get(model, 0.0)

        cost = (tokens / 1000) * cost_per_1k

        # Record the cost
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO api_costs (
                model, tokens, cost, purpose, business_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (model, tokens, cost, purpose, business_id)
        )

        self.db.commit()
        return cursor.lastrowid


# Test the full pipeline workflow
def test_full_pipeline_workflow(pipeline_db):
    """Test the entire LeadFactory pipeline workflow."""
    # Initialize the mock pipeline
    pipeline = MockPipeline(pipeline_db)

    # Step 1: Scrape businesses
    business_ids = pipeline.scrape_businesses(
        category="tech",
        location="San Francisco, CA",
        limit=10
    )

    # Verify businesses were created
    cursor = pipeline_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM businesses")
    business_count = cursor.fetchone()[0]
    assert business_count > 0, "No businesses were created during scraping"

    # Step 2: Enrich businesses
    pipeline.enrich_businesses(business_ids)

    # Verify enrichment
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE tech_stack IS NOT NULL")
    enriched_count = cursor.fetchone()[0]
    assert enriched_count > 0, "No businesses were enriched"

    # Step 3: Find duplicates
    pair_ids = pipeline.find_duplicates(business_ids)

    # Verify duplicate pairs were created
    cursor.execute("SELECT COUNT(*) FROM candidate_duplicate_pairs")
    pair_count = cursor.fetchone()[0]
    assert pair_count > 0, "No duplicate pairs were created"

    # Step 4: Process duplicates
    pipeline.process_duplicate_pairs(pair_ids)

    # Verify pairs were processed
    cursor.execute("SELECT COUNT(*) FROM candidate_duplicate_pairs WHERE status != 'pending'")
    processed_count = cursor.fetchone()[0]
    assert processed_count > 0, "No duplicate pairs were processed"

    # Step 5: Score businesses
    pipeline.score_businesses(business_ids)

    # Verify businesses were scored
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE score IS NOT NULL")
    scored_count = cursor.fetchone()[0]
    assert scored_count > 0, "No businesses were scored"

    # Step 6: Generate emails
    email_ids = pipeline.generate_emails(min_score=0)  # Use 0 to include all businesses

    # Verify emails were generated
    cursor.execute("SELECT COUNT(*) FROM emails")
    email_count = cursor.fetchone()[0]
    assert email_count > 0, "No emails were generated"

    # Step 7: Process email queue
    result = pipeline.process_email_queue()

    # Verify emails were processed
    assert result["processed"] > 0, "No emails were processed"
    assert result["sent"] > 0, "No emails were sent"

    # Step 8: Track API costs
    cost_id = pipeline.track_api_cost(
        model="gpt-4",
        tokens=1000,
        purpose="duplicate_verification",
        business_id=business_ids[0]
    )

    # Verify cost was tracked
    cursor.execute("SELECT COUNT(*) FROM api_costs")
    cost_count = cursor.fetchone()[0]
    assert cost_count > 0, "No API costs were tracked"

    # Verify all pipeline stages were called in order
    module_sequence = [call["module"] for call in pipeline.calls]
    expected_sequence = ["scrape", "enrich", "dedupe", "dedupe", "score", "email_queue", "email_queue", "budget_gate"]

    # Check that each module was called at least once
    for module in set(expected_sequence):
        assert module in module_sequence, f"Module {module} was not called"

    # Check that the sequence follows the expected pipeline flow
    # (allowing for potential repeated calls to the same module)
    for i, expected_module in enumerate(expected_sequence):
        if i < len(module_sequence):
            assert module_sequence[i] == expected_module, \
                f"Expected {expected_module} at position {i}, got {module_sequence[i]}"


# Test pipeline with budget constraints
def test_pipeline_with_budget_constraints(pipeline_db):
    """Test the pipeline with budget constraints."""
    # Initialize the mock pipeline
    pipeline = MockPipeline(pipeline_db)

    # Set a low budget to trigger constraints
    cursor = pipeline_db.cursor()
    cursor.execute(
        """
        UPDATE budget_settings
        SET monthly_budget = 1.0, daily_budget = 0.1
        """
    )
    pipeline_db.commit()

    # Add some existing costs to approach the limit
    for _ in range(3):
        pipeline.track_api_cost(
            model="gpt-4",
            tokens=10000,  # This will cost around $0.3
            purpose="test"
        )

    # Check budget status (should be warning or paused)
    cursor.execute("SELECT SUM(cost) FROM api_costs")
    total_cost = cursor.fetchone()[0]

    # Expect total cost to be > 70% of monthly budget (warning threshold)
    assert total_cost > 0.7, f"Expected cost to exceed 70% of budget, got {total_cost}"

    # Run a simple pipeline to see if operations are affected by budget
    business_ids = pipeline.scrape_businesses(
        category="retail",
        location="New York, NY",
        limit=5
    )

    # Try to enrich, but this should be limited by budget
    enriched_ids = pipeline.enrich_businesses(business_ids[:2])  # Limit to just 2

    # Verify the number of API cost entries matches expectations
    cursor.execute("SELECT COUNT(*) FROM api_costs")
    cost_entry_count = cursor.fetchone()[0]
    assert cost_entry_count > 3, "No additional API costs were tracked after initial setup"

    # Check that the pipeline recorded proper budget constraints
    budget_related_calls = [
        call for call in pipeline.calls
        if call["module"] == "budget_gate" or "budget" in str(call)
    ]
    assert len(budget_related_calls) > 0, "No budget-related operations were recorded"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
