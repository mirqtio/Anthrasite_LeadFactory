"""
Step definitions for modern site filtering BDD tests.
"""

from unittest.mock import Mock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from leadfactory.pipeline.enrich import enrich_business, enrich_businesses

# Load scenarios from feature file
scenarios("../features/modern_site_filtering.feature")


# Fixtures and context
@pytest.fixture
def enrichment_context():
    """Context for enrichment tests."""
    return {
        "business": None,
        "businesses": [],
        "enrichment_result": None,
        "batch_results": [],
        "pagespeed_responses": {},
        "save_features_calls": [],
        "logged_warnings": []
    }


# Given steps
@given("the PageSpeed Insights API is available")
def pagespeed_api_available():
    """Mock PageSpeed API availability."""
    pass  # Will be mocked in actual tests


@given("the enrichment pipeline is configured")
def enrichment_configured():
    """Ensure enrichment pipeline is configured."""
    pass  # Configuration is handled by the app


@given(parsers.parse('a business with website "{website}"'))
def business_with_website(enrichment_context, website):
    """Create a business with specified website."""
    enrichment_context["business"] = {
        "id": 1,
        "name": f"Business for {website}",
        "website": website
    }


@given(parsers.parse('the website has a PageSpeed performance score of {score:d}'))
def website_performance_score(enrichment_context, score):
    """Set PageSpeed performance score for current business."""
    website = enrichment_context["business"]["website"]
    enrichment_context["pagespeed_responses"][website] = {
        "performance_score": score,
        "is_mobile_responsive": False,  # Default, will be overridden if needed
        "has_viewport": False,
        "tap_targets_ok": False,
        "is_modern": False,
        "lighthouse_result": {
            "categories": {"performance": {"score": score / 100}},
            "audits": {}
        }
    }


@given("the website is mobile responsive")
def website_mobile_responsive(enrichment_context):
    """Mark website as mobile responsive."""
    website = enrichment_context["business"]["website"]
    response = enrichment_context["pagespeed_responses"][website]
    response["is_mobile_responsive"] = True
    response["has_viewport"] = True
    response["tap_targets_ok"] = True
    # Update is_modern based on PRD rules
    response["is_modern"] = response["performance_score"] >= 90


@given("the website is not mobile responsive")
def website_not_mobile_responsive(enrichment_context):
    """Mark website as not mobile responsive."""
    website = enrichment_context["business"]["website"]
    response = enrichment_context["pagespeed_responses"][website]
    response["is_mobile_responsive"] = False
    response["has_viewport"] = False
    response["tap_targets_ok"] = False
    response["is_modern"] = False  # Can't be modern without mobile


@given("the PageSpeed API returns an error")
def pagespeed_api_error(enrichment_context):
    """Configure PageSpeed API to return error."""
    website = enrichment_context["business"]["website"]
    enrichment_context["pagespeed_responses"][website] = Exception("PageSpeed API error")


@given("the following businesses:")
def businesses_table(enrichment_context, context):
    """Create businesses from table."""
    businesses = []
    for row in context.table:
        business = {
            "id": len(businesses) + 1,
            "name": row["name"],
            "website": row["website"]
        }
        businesses.append(business)

        # Set up PageSpeed response
        performance = int(row["performance"])
        mobile = row["mobile_responsive"].lower() == "true"
        is_modern = performance >= 90 and mobile

        enrichment_context["pagespeed_responses"][row["website"]] = {
            "performance_score": performance,
            "is_mobile_responsive": mobile,
            "has_viewport": mobile,
            "tap_targets_ok": mobile,
            "is_modern": is_modern,
            "lighthouse_result": {
                "categories": {"performance": {"score": performance / 100}},
                "audits": {"viewport": {"score": 1 if mobile else 0}}
            }
        }

    enrichment_context["businesses"] = businesses


# When steps
@when("the business is enriched")
def enrich_single_business(enrichment_context):
    """Enrich a single business."""
    business = enrichment_context["business"]
    website = business["website"]

    # Mock PageSpeed client
    def mock_check_modern_site(url):
        response = enrichment_context["pagespeed_responses"].get(url)
        if isinstance(response, Exception):
            raise response
        return response["is_modern"], response

    # Mock save_features to capture calls
    def mock_save_features(**kwargs):
        enrichment_context["save_features_calls"].append(kwargs)
        return True

    # Mock logger to capture warnings
    def mock_warning(msg, *args, **kwargs):
        enrichment_context["logged_warnings"].append(msg)

    with patch('leadfactory.integrations.pagespeed.PageSpeedInsightsClient.check_if_modern_site', side_effect=mock_check_modern_site), \
         patch('leadfactory.pipeline.enrich.save_features', side_effect=mock_save_features), \
         patch('leadfactory.pipeline.enrich.logger.warning', side_effect=mock_warning):

        # Mock other enrichment components to avoid import errors
        with patch('leadfactory.pipeline.enrich.TechStackAnalyzer'), \
             patch('leadfactory.pipeline.enrich.ScreenshotGenerator'), \
             patch('leadfactory.pipeline.enrich.SEMrushAnalyzer'):

            enrichment_context["enrichment_result"] = enrich_business(business)


@when("the businesses are enriched in batch")
def enrich_batch_businesses(enrichment_context):
    """Enrich multiple businesses."""
    businesses = enrichment_context["businesses"]
    results = []

    for business in businesses:
        # Set up context for individual business
        enrichment_context["business"] = business
        enrich_single_business(enrichment_context)

        # Capture result
        results.append({
            "business": business,
            "result": enrichment_context["enrichment_result"],
            "save_calls": enrichment_context["save_features_calls"][-1] if enrichment_context["save_features_calls"] else None
        })

    enrichment_context["batch_results"] = results


# Then steps
@then(parsers.parse('the business should be marked as "{status}"'))
def business_marked_as(enrichment_context, status):
    """Check business marking status."""
    assert enrichment_context["enrichment_result"] is True

    if status == "modern_site_skipped":
        # Check that save_features was called with skip_reason
        assert len(enrichment_context["save_features_calls"]) > 0
        last_call = enrichment_context["save_features_calls"][-1]
        assert last_call.get("skip_reason") == "modern_site"


@then("no email should be sent to this business")
def no_email_sent(enrichment_context):
    """Verify no email will be sent (indicated by skip_reason)."""
    assert len(enrichment_context["save_features_calls"]) > 0
    last_call = enrichment_context["save_features_calls"][-1]
    assert last_call.get("skip_reason") == "modern_site"


@then(parsers.parse('the skip reason should be "{reason}"'))
def skip_reason_is(enrichment_context, reason):
    """Check skip reason."""
    assert len(enrichment_context["save_features_calls"]) > 0
    last_call = enrichment_context["save_features_calls"][-1]
    assert last_call.get("skip_reason") == reason


@then("the business should be processed normally")
def business_processed_normally(enrichment_context):
    """Check normal processing."""
    assert enrichment_context["enrichment_result"] is True


@then("the business should be eligible for email outreach")
def business_eligible_for_email(enrichment_context):
    """Check email eligibility (no skip reason)."""
    if enrichment_context["save_features_calls"]:
        last_call = enrichment_context["save_features_calls"][-1]
        assert "skip_reason" not in last_call or last_call.get("skip_reason") is None


@then("no skip reason should be set")
def no_skip_reason(enrichment_context):
    """Verify no skip reason."""
    if enrichment_context["save_features_calls"]:
        last_call = enrichment_context["save_features_calls"][-1]
        assert "skip_reason" not in last_call or last_call.get("skip_reason") is None


@then("a warning should be logged about PageSpeed failure")
def warning_logged(enrichment_context):
    """Check for warning log."""
    warnings = [w for w in enrichment_context["logged_warnings"] if "PageSpeed" in w]
    assert len(warnings) > 0


@then("the following businesses should be skipped:")
def businesses_skipped(enrichment_context, context):
    """Check which businesses were skipped."""
    skipped_businesses = {}

    for result in enrichment_context["batch_results"]:
        if result["save_calls"] and result["save_calls"].get("skip_reason"):
            name = result["business"]["name"]
            reason = result["save_calls"]["skip_reason"]
            skipped_businesses[name] = reason

    # Verify expected skips
    for row in context.table:
        name = row["name"]
        expected_reason = row["reason"]
        assert name in skipped_businesses, f"Business {name} should be skipped"
        assert skipped_businesses[name] == expected_reason


@then("the following businesses should be processed:")
def businesses_processed(enrichment_context, context):
    """Check which businesses were processed normally."""
    processed_businesses = []

    for result in enrichment_context["batch_results"]:
        if not result["save_calls"] or not result["save_calls"].get("skip_reason"):
            processed_businesses.append(result["business"]["name"])

    # Verify expected processed
    for row in context.table:
        name = row["name"]
        assert name in processed_businesses, f"Business {name} should be processed"
