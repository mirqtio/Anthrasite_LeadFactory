"""
Test utility functions and mock classes for testing the LeadFactory application.
This module provides shared utilities to help with testing across different modules.
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock


def get_random_business_name():
    """Generate a random business name for testing."""
    prefixes = ["Tech", "Digital", "Cyber", "Cloud", "Smart", "Eco", "Global", "Next", "Pro", "Fast"]
    suffixes = ["Solutions", "Systems", "Technologies", "Innovations", "Services", "Consultants", "Group", "Labs", "Partners", "Enterprises"]
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"


def get_random_address():
    """Generate a random address for testing."""
    street_numbers = list(range(100, 1000, 25))
    street_names = ["Main", "Oak", "Pine", "Maple", "Cedar", "Elm", "Park", "Lake", "River", "Hill"]
    street_types = ["St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Way", "Place", "Court", "Circle"]
    cities = ["Springfield", "Riverdale", "Lakeside", "Hillcrest", "Woodland", "Fairview", "Georgetown", "Maplewood", "Oakville", "Brookside"]
    states = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
    zips = [f"{random.randint(10000, 99999)}" for _ in range(10)]

    return {
        "street": f"{random.choice(street_numbers)} {random.choice(street_names)} {random.choice(street_types)}",
        "city": random.choice(cities),
        "state": random.choice(states),
        "zip": random.choice(zips)
    }


def get_random_contact_info():
    """Generate random contact information for testing."""
    email_domains = ["gmail.com", "yahoo.com", "outlook.com", "company.com", "business.net", "example.org"]
    names = ["John Smith", "Jane Doe", "Robert Johnson", "Emily Williams", "Michael Brown", "Sarah Davis", "David Miller", "Lisa Wilson", "James Moore", "Jennifer Taylor"]
    positions = ["CEO", "CTO", "CFO", "CMO", "COO", "Director", "Manager", "VP", "President", "Founder"]

    name = random.choice(names)
    first_name = name.split()[0].lower()
    email = f"{first_name}@{random.choice(email_domains)}"
    phone = f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"

    return {
        "name": name,
        "position": random.choice(positions),
        "email": email,
        "phone": phone
    }


def generate_test_business(complete=True, score_range=None, include_tech=True):
    """Generate a test business object with randomized data.

    Args:
        complete: Whether to generate a complete business object or one with minimal fields
        score_range: Tuple of (min, max) for generating a random score
        include_tech: Whether to include tech stack and performance data

    Returns:
        Dictionary containing business data
    """
    business = {
        "name": get_random_business_name(),
        "address": get_random_address()["street"],
    }

    # Add more fields for complete business objects
    if complete:
        address = get_random_address()
        business.update({
            "city": address["city"],
            "state": address["state"],
            "zip": address["zip"],
            "phone": f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "email": f"info@{business['name'].lower().replace(' ', '')}.com",
            "website": f"http://www.{business['name'].lower().replace(' ', '')}.com",
            "category": random.choice(["tech", "consulting", "services", "retail", "healthcare"]),
            "source": random.choice(["google", "yelp", "linkedin", "manual", "referral"]),
            "source_id": f"src_{random.randint(10000, 99999)}"
        })

    # Add score if requested
    if score_range:
        min_score, max_score = score_range
        business["score"] = random.randint(min_score, max_score)

        # Generate score details based on score
        details = {}
        if business["score"] >= 80:
            details["tech_score"] = random.randint(80, 100)
            details["performance_score"] = random.randint(75, 100)
            details["contact_score"] = random.randint(70, 100)
        elif business["score"] >= 50:
            details["tech_score"] = random.randint(50, 80)
            details["performance_score"] = random.randint(40, 75)
            details["contact_score"] = random.randint(50, 80)
        else:
            details["tech_score"] = random.randint(20, 50)
            details["performance_score"] = random.randint(10, 40)
            details["contact_score"] = random.randint(20, 50)

        business["score_details"] = json.dumps(details)

    # Add tech data if requested
    if include_tech:
        # Generate tech stack
        cms_options = ["WordPress", "Drupal", "Joomla", "Shopify", "Wix", "Squarespace"]
        analytics_options = ["Google Analytics", "Mixpanel", "HotJar", "Matomo", "Adobe Analytics"]
        server_options = ["Nginx", "Apache", "IIS", "Cloudflare", "AWS"]
        js_options = ["React", "Angular", "Vue", "jQuery", "Vanilla JS"]

        tech_stack = {
            "cms": random.choice(cms_options) if random.random() > 0.2 else None,
            "analytics": random.choice(analytics_options) if random.random() > 0.3 else None,
            "server": random.choice(server_options) if random.random() > 0.1 else None,
            "javascript": random.choice(js_options) if random.random() > 0.2 else None
        }

        # Filter out None values
        tech_stack = {k: v for k, v in tech_stack.items() if v is not None}

        if tech_stack:
            business["tech_stack"] = json.dumps(tech_stack)

        # Generate performance data
        performance = {
            "page_speed": random.randint(30, 100),
            "mobile_friendly": random.random() > 0.3,  # 70% chance of being mobile friendly
        }

        if random.random() > 0.5:
            performance["accessibility"] = random.randint(30, 100)

        business["performance"] = json.dumps(performance)

        # Generate contact info
        contact = get_random_contact_info()
        business["contact_info"] = json.dumps(contact)

    return business


def insert_test_businesses_batch(db_conn, count=10, complete=True, score_range=None, include_tech=True):
    """Insert a batch of test businesses into the database.

    Args:
        db_conn: SQLite database connection
        count: Number of businesses to insert
        complete: Whether to generate complete business objects
        score_range: Tuple of (min, max) for generating random scores
        include_tech: Whether to include tech stack and performance data

    Returns:
        List of business IDs
    """
    cursor = db_conn.cursor()
    business_ids = []

    for _ in range(count):
        business = generate_test_business(complete, score_range, include_tech)

        # Extract fields
        name = business.get("name", "")
        address = business.get("address", "")
        city = business.get("city", "")
        state = business.get("state", "")
        zip_code = business.get("zip", "")
        phone = business.get("phone", "")
        email = business.get("email", "")
        website = business.get("website", "")
        category = business.get("category", "")
        source = business.get("source", "")
        source_id = business.get("source_id", "")
        score = business.get("score")
        score_details = business.get("score_details")
        tech_stack = business.get("tech_stack")
        performance = business.get("performance")
        contact_info = business.get("contact_info")

        # Insert the business
        cursor.execute(
            """
            INSERT INTO businesses (
                name, address, city, state, zip, phone, email, website, category, source, source_id,
                score, score_details, tech_stack, performance, contact_info
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name, address, city, state, zip_code, phone, email, website, category, source, source_id,
                score, score_details, tech_stack, performance, contact_info
            )
        )

        business_ids.append(cursor.lastrowid)

    db_conn.commit()
    return business_ids


def create_duplicate_pairs(db_conn, business_ids, pair_count=5, verified_ratio=0.5):
    """Create candidate duplicate pairs in the database.

    Args:
        db_conn: SQLite database connection
        business_ids: List of business IDs to use for creating pairs
        pair_count: Number of duplicate pairs to create
        verified_ratio: Ratio of pairs that should be verified by LLM

    Returns:
        List of duplicate pair IDs
    """
    cursor = db_conn.cursor()
    pair_ids = []

    # Create duplicate pairs
    for _ in range(pair_count):
        # Choose two random businesses
        # Ensure id1 < id2 to satisfy the CHECK constraint
        id1, id2 = sorted(random.sample(business_ids, 2))

        # Generate random similarity score
        similarity_score = round(random.uniform(0.6, 0.95), 2)

        # Determine if verified by LLM
        verified_by_llm = random.random() < verified_ratio

        # Generate LLM data if verified
        llm_confidence = round(random.uniform(0.7, 0.99), 2) if verified_by_llm else None
        llm_reasoning = "These businesses appear to be duplicates based on name and address similarity." if verified_by_llm else None

        # Status is based on verification
        status = random.choice(["merged", "rejected"]) if verified_by_llm else "pending"

        # Insert the pair
        try:
            cursor.execute(
                """
                INSERT INTO candidate_duplicate_pairs (
                    business1_id, business2_id, similarity_score, status,
                    verified_by_llm, llm_confidence, llm_reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id1, id2, similarity_score, status,
                    1 if verified_by_llm else 0, llm_confidence, llm_reasoning
                )
            )

            pair_ids.append(cursor.lastrowid)

            # If merged, update the business record
            if status == "merged":
                cursor.execute(
                    "UPDATE businesses SET merged_into = ? WHERE id = ?",
                    (id1, id2)
                )
        except sqlite3.IntegrityError:
            # Skip this pair if it violates constraints
            continue

    db_conn.commit()
    return pair_ids


def create_test_emails(db_conn, business_ids, email_count=10):
    """Create test emails in the database.

    Args:
        db_conn: SQLite database connection
        business_ids: List of business IDs to associate emails with
        email_count: Number of emails to create

    Returns:
        List of email IDs
    """
    cursor = db_conn.cursor()
    email_ids = []

    # Email variants
    variants = ["welcome", "followup", "offer", "proposal", "newsletter"]

    # Email statuses and their probabilities
    statuses = {
        "pending": 0.4,
        "sent": 0.3,
        "error": 0.1,
        "opened": 0.1,
        "clicked": 0.1
    }

    # Create emails
    for _ in range(email_count):
        # Choose a random business
        business_id = random.choice(business_ids)

        # Choose a random variant
        variant_id = random.choice(variants)

        # Generate subject and content
        subject = f"Test Email for Business {business_id}: {variant_id.title()}"
        body_text = f"This is a test email of type {variant_id} for business {business_id}."
        body_html = f"<html><body><h1>{variant_id.title()} Email</h1><p>{body_text}</p></body></html>"

        # Choose a status based on probabilities
        status = random.choices(
            list(statuses.keys()),
            weights=list(statuses.values())
        )[0]

        # Set timestamps based on status
        now = datetime.now()
        sent_at = now - timedelta(hours=random.randint(1, 48)) if status != "pending" else None
        opened_at = now - timedelta(hours=random.randint(1, 24)) if status in ["opened", "clicked"] else None
        clicked_at = now - timedelta(hours=random.randint(1, 12)) if status == "clicked" else None

        # Insert the email
        cursor.execute(
            """
            INSERT INTO emails (
                business_id, variant_id, subject, body_text, body_html,
                status, sent_at, opened_at, clicked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                business_id, variant_id, subject, body_text, body_html,
                status, sent_at, opened_at, clicked_at
            )
        )

        email_ids.append(cursor.lastrowid)

    db_conn.commit()
    return email_ids


def create_test_api_costs(db_conn, business_ids=None, count=20):
    """Create test API cost records in the database.

    Args:
        db_conn: SQLite database connection
        business_ids: Optional list of business IDs to associate with costs
        count: Number of cost records to create

    Returns:
        List of cost record IDs
    """
    cursor = db_conn.cursor()
    cost_ids = []

    # Define models and their typical token counts and costs per 1K tokens
    models = {
        "gpt-4": {"tokens_range": (500, 3000), "cost_per_1k": 0.03},
        "gpt-3.5-turbo": {"tokens_range": (800, 4000), "cost_per_1k": 0.002},
        "claude-3-opus": {"tokens_range": (1000, 5000), "cost_per_1k": 0.015},
        "claude-3-sonnet": {"tokens_range": (1200, 6000), "cost_per_1k": 0.003},
        "claude-3-haiku": {"tokens_range": (1500, 7000), "cost_per_1k": 0.00025},
        "llama3": {"tokens_range": (2000, 8000), "cost_per_1k": 0.0}
    }

    # Define possible purposes
    purposes = ["business_description", "duplicate_check", "mockup_generation", "email_content", "scoring"]

    # Create API cost records
    for _ in range(count):
        # Choose a random model
        model = random.choice(list(models.keys()))
        model_info = models[model]

        # Generate tokens
        min_tokens, max_tokens = model_info["tokens_range"]
        tokens = random.randint(min_tokens, max_tokens)

        # Calculate cost
        cost = (tokens / 1000) * model_info["cost_per_1k"]

        # Choose a random purpose
        purpose = random.choice(purposes)

        # Choose a random business if provided
        business_id = random.choice(business_ids) if business_ids else None

        # Generate a timestamp within the last month
        now = datetime.now()
        days_ago = random.randint(0, 30)
        timestamp = now - timedelta(days=days_ago)

        # Insert the cost record
        cursor.execute(
            """
            INSERT INTO api_costs (
                model, tokens, cost, timestamp, purpose, business_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                model, tokens, cost, timestamp, purpose, business_id
            )
        )

        cost_ids.append(cursor.lastrowid)

    db_conn.commit()
    return cost_ids


def setup_budget_settings(db_conn, monthly_budget=100.0, daily_budget=10.0, status="active"):
    """Set up budget settings in the database.

    Args:
        db_conn: SQLite database connection
        monthly_budget: Monthly budget amount
        daily_budget: Daily budget amount
        status: Current budget status

    Returns:
        ID of the budget settings record
    """
    cursor = db_conn.cursor()

    # Delete existing settings
    cursor.execute("DELETE FROM budget_settings")

    # Insert new settings
    cursor.execute(
        """
        INSERT INTO budget_settings (
            monthly_budget, daily_budget, warning_threshold, pause_threshold, current_status
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            monthly_budget, daily_budget, 0.7, 0.9, status
        )
    )

    db_conn.commit()
    return cursor.lastrowid


# Mock classes for testing

class MockResponse:
    """Mock for HTTP responses."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.content = text.encode("utf-8") if text else b""
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP Error: {self.status_code}", response=self)


class MockRequests:
    """Mock for the requests library."""

    def __init__(self, default_response=None):
        self.default_response = default_response or MockResponse()
        self.calls = []

    def get(self, url, params=None, headers=None, **kwargs):
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers, "kwargs": kwargs})
        return self.default_response

    def post(self, url, data=None, json=None, headers=None, **kwargs):
        self.calls.append({"method": "POST", "url": url, "data": data, "json": json, "headers": headers, "kwargs": kwargs})
        return self.default_response

    def put(self, url, data=None, json=None, headers=None, **kwargs):
        self.calls.append({"method": "PUT", "url": url, "data": data, "json": json, "headers": headers, "kwargs": kwargs})
        return self.default_response

    def delete(self, url, headers=None, **kwargs):
        self.calls.append({"method": "DELETE", "url": url, "headers": headers, "kwargs": kwargs})
        return self.default_response


class MockLevenshteinMatcher:
    """Mock for the LevenshteinMatcher class."""

    def __init__(self, name_threshold=0.7, address_threshold=0.7):
        self.name_threshold = name_threshold
        self.address_threshold = address_threshold
        self.calls = []

    def calculate_similarity(self, business1, business2):
        self.calls.append({"method": "calculate_similarity", "business1": business1, "business2": business2})

        # Simple implementation for testing
        similarity = 0.0

        # Check name similarity
        if self.are_similar_names(business1, business2):
            similarity += 0.6

        # Check address similarity
        if self.are_similar_addresses(business1, business2):
            similarity += 0.4

        return min(similarity, 1.0)

    def are_potential_duplicates(self, business1, business2):
        self.calls.append({"method": "are_potential_duplicates", "business1": business1, "business2": business2})
        similarity = self.calculate_similarity(business1, business2)
        return similarity >= 0.7

    def are_similar_names(self, business1, business2):
        self.calls.append({"method": "are_similar_names", "business1": business1, "business2": business2})

        name1 = business1.get("name", "").lower()
        name2 = business2.get("name", "").lower()

        # Exact match
        if name1 == name2:
            return True

        # Simple contains check
        if name1 and name2 and (name1 in name2 or name2 in name1):
            return True

        # For testing purposes, hardcode some special cases
        special_cases = [
            ("abc corp", "abc corporation"),
            ("abc corp", "abc inc"),
            ("smith & jones", "smith and jones")
        ]

        for case1, case2 in special_cases:
            if (name1 == case1 and name2 == case2) or (name1 == case2 and name2 == case1):
                return True

        return False

    def are_similar_addresses(self, business1, business2):
        self.calls.append({"method": "are_similar_addresses", "business1": business1, "business2": business2})

        addr1 = business1.get("address", "").lower()
        addr2 = business2.get("address", "").lower()

        # Exact match
        if addr1 == addr2:
            return True

        # Normalize addresses (very simple for testing)
        addr1 = addr1.replace("street", "st").replace("avenue", "ave").replace("boulevard", "blvd")
        addr2 = addr2.replace("street", "st").replace("avenue", "ave").replace("boulevard", "blvd")

        if addr1 == addr2:
            return True

        # For testing purposes, hardcode some special cases
        special_cases = [
            ("123 main st", "123 main street"),
            ("123 main st, suite 100", "123 main st"),
            ("123 oak ave", "123 oak avenue")
        ]

        for case1, case2 in special_cases:
            if (addr1.startswith(case1) and addr2.startswith(case2)) or (addr1.startswith(case2) and addr2.startswith(case1)):
                return True

        return False


class MockOllamaVerifier:
    """Mock for the OllamaVerifier class."""

    def __init__(self):
        self.calls = []

    def verify_duplicates(self, business1, business2):
        self.calls.append({"method": "verify_duplicates", "business1": business1, "business2": business2})

        # Calculate similarity using Levenshtein matcher logic
        matcher = MockLevenshteinMatcher()
        similarity = matcher.calculate_similarity(business1, business2)

        # Determine if they are duplicates
        is_duplicate = similarity >= 0.7

        # Set confidence based on similarity
        confidence = similarity if is_duplicate else 1.0 - similarity

        # Generate reasoning
        if is_duplicate:
            if similarity > 0.9:
                reasoning = "These are definitely the same business with identical name and address."
            elif similarity > 0.8:
                reasoning = "These appear to be the same business with very similar name and address."
            else:
                reasoning = "These businesses are likely duplicates based on similarities in their information."
        else:
            reasoning = "These do not appear to be the same business. The names and addresses are different."

        return is_duplicate, confidence, reasoning
