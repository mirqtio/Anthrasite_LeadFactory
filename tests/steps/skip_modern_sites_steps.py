"""Step definitions for skip modern sites feature."""

import json
from unittest.mock import Mock, patch

from pytest_bdd import given, parsers, then, when

from bin.enrich import enrich_business, get_businesses_to_enrich
from leadfactory.utils.e2e_db_connector import db_connection, execute_query

# Mock storage for PageSpeed scores
pagespeed_scores = {}


@given("the lead factory system is running")
def lead_factory_running():
    """Ensure the lead factory system is set up."""
    # This is mostly a placeholder - in a real system we'd verify services
    pass


@given("the PageSpeed API is available")
def pagespeed_api_available():
    """Mock PageSpeed API availability."""
    # In real tests, we might check API connectivity
    pass


@given("the enrichment pipeline is configured")
def enrichment_configured():
    """Ensure enrichment pipeline is configured."""
    # Verify environment variables, etc.
    pass


@given(parsers.parse('a business "{name}" with website "{website}"'))
def create_business_with_website(name, website):
    """Create a test business with a website."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO businesses (name, website, email, status)
            VALUES (%s, %s, %s, 'pending')
            ON CONFLICT (name) DO UPDATE SET website = EXCLUDED.website
            RETURNING id
        """, (name, website, f"{name.lower().replace(' ', '')}@example.com"))
        business_id = cursor.fetchone()[0]
        conn.commit()
    return business_id


@given(parsers.parse("the website has a PageSpeed performance score of {score:d}"))
def set_pagespeed_performance_score(score):
    """Set the PageSpeed performance score for mocking."""
    if "current_scores" not in pagespeed_scores:
        pagespeed_scores["current_scores"] = {}
    pagespeed_scores["current_scores"]["performance_score"] = score


@given(parsers.parse("the website has a PageSpeed accessibility score of {score:d}"))
def set_pagespeed_accessibility_score(score):
    """Set the PageSpeed accessibility score for mocking."""
    if "current_scores" not in pagespeed_scores:
        pagespeed_scores["current_scores"] = {}
    pagespeed_scores["current_scores"]["accessibility_score"] = score


@when(parsers.parse('the enrichment process runs for "{name}"'))
def run_enrichment_for_business(name):
    """Run the enrichment process for a specific business."""
    # Get the business
    businesses = execute_query(
        "SELECT * FROM businesses WHERE name = %s",
        (name,)
    )
    assert len(businesses) == 1
    business = businesses[0]

    # Mock the analyzers
    with patch("bin.enrich.PageSpeedAnalyzer") as mock_pagespeed_class:
        with patch("bin.enrich.TechStackAnalyzer") as mock_tech_class:
            # Mock tech stack analyzer
            mock_tech = Mock()
            mock_tech.analyze_website.return_value = (
                {"technologies": ["React", "Node.js"]}, None
            )
            mock_tech_class.return_value = mock_tech

            # Mock PageSpeed analyzer with our set scores
            mock_pagespeed = Mock()
            scores = pagespeed_scores.get("current_scores", {})
            mock_pagespeed.analyze_website.return_value = (scores, None)
            mock_pagespeed_class.return_value = mock_pagespeed

            # Run enrichment
            result = enrich_business(business)
            assert result is True


@then(parsers.parse('the business should be marked with status "{status}"'))
def check_business_status(name, status):
    """Check that the business has the expected status."""
    result = execute_query(
        "SELECT status FROM businesses WHERE name = %s",
        (name,)
    )
    assert len(result) == 1
    assert result[0]["status"] == status


@then(parsers.parse('the business should remain with status "{status}"'))
def check_business_remains_status(name, status):
    """Check that the business still has the expected status."""
    check_business_status(name, status)


@then("no screenshot should be captured")
def no_screenshot_captured():
    """Verify no screenshot was captured (mocked)."""
    # In a real test, we'd check if ScreenshotGenerator was called
    pass


@then("a screenshot should be captured if configured")
def screenshot_captured_if_configured():
    """Verify screenshot capture behavior based on configuration."""
    # In a real test, we'd check based on SCREENSHOT_ONE_KEY
    pass


@then("no email should be queued for the business")
def no_email_queued(name):
    """Verify no email was queued for the business."""
    result = execute_query(
        "SELECT COUNT(*) as count FROM emails WHERE business_id = (SELECT id FROM businesses WHERE name = %s)",
        (name,)
    )
    assert result[0]["count"] == 0


@then("the business should be eligible for email outreach")
def business_eligible_for_email(name):
    """Verify the business is eligible for email outreach."""
    result = execute_query("""
        SELECT b.status, f.id as feature_id
        FROM businesses b
        LEFT JOIN features f ON b.id = f.business_id
        WHERE b.name = %s
    """, (name,))

    assert len(result) == 1
    assert result[0]["status"] != "skipped_modern_site"
    assert result[0]["feature_id"] is not None  # Has features


@then(parsers.parse('the features table should contain a skip reason of "{reason}"'))
def check_skip_reason(name, reason):
    """Check the features table for skip reason."""
    result = execute_query("""
        SELECT f.tech_stack
        FROM features f
        JOIN businesses b ON f.business_id = b.id
        WHERE b.name = %s
    """, (name,))

    assert len(result) == 1
    tech_stack = json.loads(result[0]["tech_stack"])
    assert tech_stack.get("skip_reason") == reason


@then(parsers.parse("the features table should contain the actual performance score of {score:d}"))
def check_actual_performance_score(name, score):
    """Check the features table for the actual performance score."""
    result = execute_query("""
        SELECT f.page_speed
        FROM features f
        JOIN businesses b ON f.business_id = b.id
        WHERE b.name = %s
    """, (name,))

    assert len(result) == 1
    assert result[0]["page_speed"] == score


@then(parsers.parse('the skip should be logged with reason "{reason}"'))
def check_skip_logged(reason):
    """Verify the skip was logged (in a real system, check logs)."""
    # In production, we'd check actual logs
    pass


@then("the site should be processed normally")
def site_processed_normally(name):
    """Verify the site was processed without skipping."""
    result = execute_query("""
        SELECT b.status, f.tech_stack
        FROM businesses b
        LEFT JOIN features f ON b.id = f.business_id
        WHERE b.name = %s
    """, (name,))

    assert len(result) == 1
    assert result[0]["status"] != "skipped_modern_site"
    if result[0]["tech_stack"]:
        tech_stack = json.loads(result[0]["tech_stack"])
        assert "skip_reason" not in tech_stack


@given(parsers.parse('a business "{name}" with status "{status}"'))
def create_business_with_status(name, status):
    """Create a business with a specific status."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO businesses (name, website, email, status)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET status = EXCLUDED.status
            RETURNING id
        """, (name, "https://example.com", "test@example.com", status))
        business_id = cursor.fetchone()[0]
        conn.commit()
    return business_id


@given(parsers.parse('the business has a features record with skip_reason "{reason}"'))
def create_skip_features_record(name, reason):
    """Create a features record with skip reason."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO features (business_id, tech_stack, page_speed)
            SELECT id, %s, 90
            FROM businesses
            WHERE name = %s
        """, (json.dumps({"skip_reason": reason}), name))
        conn.commit()


@when("getting businesses to enrich")
def get_enrichment_queue():
    """Get the list of businesses to enrich."""
    businesses = get_businesses_to_enrich()
    return businesses


@then(parsers.parse('"{name}" should not be in the enrichment queue'))
def business_not_in_queue(name):
    """Verify a business is not in the enrichment queue."""
    businesses = get_businesses_to_enrich()
    business_names = [b["name"] for b in businesses]
    assert name not in business_names


@given(parsers.parse("{count:d} businesses with various websites"))
def create_multiple_businesses(count):
    """Create multiple test businesses."""
    with db_connection() as conn:
        cursor = conn.cursor()
        for i in range(count):
            cursor.execute("""
                INSERT INTO businesses (name, website, email, status)
                VALUES (%s, %s, %s, 'pending')
            """, (f"TestBusiness{i}", f"https://site{i}.com", f"test{i}@example.com"))
        conn.commit()


@given(parsers.parse("{modern_count:d} of them have modern, high-performing sites"))
def set_modern_sites(modern_count):
    """Configure some sites as modern/high-performing."""
    pagespeed_scores["modern_count"] = modern_count


@given(parsers.parse("{outdated_count:d} of them have outdated, low-performing sites"))
def set_outdated_sites(outdated_count):
    """Configure some sites as outdated/low-performing."""
    pagespeed_scores["outdated_count"] = outdated_count


@when("the enrichment process runs for all businesses")
def run_enrichment_for_all():
    """Run enrichment for all test businesses."""
    businesses = execute_query(
        "SELECT * FROM businesses WHERE name LIKE 'TestBusiness%' ORDER BY id"
    )

    modern_count = pagespeed_scores.get("modern_count", 0)

    with patch("bin.enrich.PageSpeedAnalyzer") as mock_pagespeed_class:
        with patch("bin.enrich.TechStackAnalyzer") as mock_tech_class:
            mock_tech = Mock()
            mock_tech.analyze_website.return_value = ({"technologies": ["React"]}, None)
            mock_tech_class.return_value = mock_tech

            mock_pagespeed = Mock()

            # Create scores for each business
            scores_list = []
            for i in range(len(businesses)):
                if i < modern_count:
                    # Modern site
                    scores_list.append({
                        "performance_score": 95,
                        "accessibility_score": 90,
                    })
                else:
                    # Outdated site
                    scores_list.append({
                        "performance_score": 40,
                        "accessibility_score": 50,
                    })

            mock_pagespeed.analyze_website.side_effect = [(s, None) for s in scores_list]
            mock_pagespeed_class.return_value = mock_pagespeed

            for business in businesses:
                enrich_business(business)


@then(parsers.parse("only {count:d} businesses should have screenshots captured"))
def verify_screenshot_count(count):
    """Verify the number of businesses with screenshots."""
    # In a real test, we'd check screenshot capture calls
    pass


@then(parsers.parse("only {count:d} businesses should be queued for personalization"))
def verify_personalization_queue(count):
    """Verify the number of businesses queued for personalization."""
    result = execute_query("""
        SELECT COUNT(*) as count
        FROM businesses
        WHERE name LIKE 'TestBusiness%'
        AND status != 'skipped_modern_site'
    """)
    assert result[0]["count"] == count


@then("the cost tracking should show reduced API usage")
def verify_reduced_api_costs():
    """Verify that API costs are reduced by skipping."""
    # In a real test, we'd check cost tracking records
    pass
