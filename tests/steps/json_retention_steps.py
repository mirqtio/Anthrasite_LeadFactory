"""Step definitions for JSON retention feature tests."""

import json
from datetime import datetime, timedelta
from pytest_bdd import given, when, then, parsers

from leadfactory.utils.e2e_db_connector import db_connection, execute_query
from leadfactory.pipeline.scrape import save_business


@given("the JSON retention policy is set to 90 days")
def json_retention_policy():
    """Verify JSON retention policy is configured."""
    # The policy is set by default in the migration
    pass


@when("I save a business with Yelp JSON response")
def save_business_with_yelp_json(test_data):
    """Save a business with Yelp JSON."""
    business_id = save_business(
        name="Yelp JSON Test Business",
        address="123 Yelp St",
        city="San Francisco", 
        state="CA",
        zip_code="94105",
        category="Restaurant",
        source="yelp",
        yelp_response_json={"id": "yelp-test-123", "name": "Yelp JSON Test Business"}
    )
    test_data["yelp_business_id"] = business_id


@when("I save a business with Google JSON response")
def save_business_with_google_json(test_data):
    """Save a business with Google JSON."""
    business_id = save_business(
        name="Google JSON Test Business",
        address="456 Google Ave",
        city="Mountain View",
        state="CA", 
        zip_code="94043",
        category="Restaurant",
        source="google",
        google_response_json={"place_id": "ChIJgoogle123", "name": "Google JSON Test Business"}
    )
    test_data["google_business_id"] = business_id


@then("the businesses should have json_retention_expires_at set")
def check_retention_dates_set(test_data):
    """Verify retention dates are set."""
    for key in ["yelp_business_id", "google_business_id"]:
        if key in test_data:
            result = execute_query(
                "SELECT json_retention_expires_at FROM businesses WHERE id = %s",
                (test_data[key],)
            )
            assert len(result) == 1
            assert result[0]["json_retention_expires_at"] is not None


@then("the retention date should be 90 days from now")
def check_retention_date_value(test_data):
    """Verify retention date is 90 days in future."""
    for key in ["yelp_business_id", "google_business_id"]:
        if key in test_data:
            result = execute_query(
                "SELECT json_retention_expires_at FROM businesses WHERE id = %s",
                (test_data[key],)
            )
            retention_date = result[0]["json_retention_expires_at"]
            expected_date = datetime.now() + timedelta(days=90)
            
            # Allow 1 hour tolerance
            diff_seconds = abs((retention_date - expected_date).total_seconds())
            assert diff_seconds < 3600


@given(parsers.parse("I have businesses with JSON responses:\n{table}"))
def create_businesses_with_json(table, test_data):
    """Create businesses with specified JSON data."""
    test_data["test_businesses"] = []
    
    for row in table:
        # Parse table row
        name = row.get("name", "Test Business")
        json_type = row.get("json_type", "both")
        days_old = int(row.get("days_old", 0))
        
        # Create appropriate JSON data
        yelp_json = None
        google_json = None
        
        if json_type in ["yelp", "both"]:
            yelp_json = {"id": f"yelp-{name}", "name": name}
        
        if json_type in ["google", "both"]:
            google_json = {"place_id": f"ChIJ{name}", "name": name}
        
        # Save business
        business_id = save_business(
            name=name,
            address=f"{days_old} Days St",
            city="Test City",
            state="TC",
            zip_code="99999",
            category="Test",
            source=json_type,
            yelp_response_json=yelp_json,
            google_response_json=google_json
        )
        
        # Update retention date if needed
        if days_old > 90:
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE businesses 
                    SET json_retention_expires_at = CURRENT_TIMESTAMP - INTERVAL '{days_old - 90} days'
                    WHERE id = %s
                    """,
                    (business_id,)
                )
                conn.commit()
        
        test_data["test_businesses"].append({
            "id": business_id,
            "name": name,
            "days_old": days_old
        })


@when("I check for expired JSON responses")
def check_expired_json(test_data):
    """Check for expired JSON responses."""
    result = execute_query("""
        SELECT id, name
        FROM businesses
        WHERE json_retention_expires_at < CURRENT_TIMESTAMP
        AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
    """)
    
    test_data["expired_businesses"] = result


@then(parsers.parse("I should find {count:d} businesses with expired JSON"))
def verify_expired_count(count, test_data):
    """Verify number of expired businesses."""
    assert len(test_data["expired_businesses"]) == count


@then(parsers.parse('"{name}" should not be in the expired list'))
def verify_not_expired(name, test_data):
    """Verify specific business is not expired."""
    expired_names = [b["name"] for b in test_data["expired_businesses"]]
    assert name not in expired_names


@given(parsers.parse('I have a business "{name}" with complete data and JSON responses'))
def create_complete_business(name, test_data):
    """Create a business with all fields populated."""
    business_id = save_business(
        name=name,
        address="123 Complete St",
        city="Full City",
        state="FC",
        zip_code="12345",
        category="Restaurant",
        email="test@restaurant.com",
        phone="(555) 123-4567",
        website="https://testrestaurant.com",
        source="both",
        yelp_response_json={"id": "complete-yelp", "name": name},
        google_response_json={"place_id": "ChIJcomplete", "name": name}
    )
    test_data["complete_business_id"] = business_id


@given("the JSON retention has expired")
def expire_json_retention(test_data):
    """Set JSON retention to expired."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE businesses 
            SET json_retention_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 day'
            WHERE id = %s
            """,
            (test_data["complete_business_id"],)
        )
        conn.commit()


@when("I run the JSON cleanup process")
def run_json_cleanup():
    """Run JSON cleanup."""
    from bin.cleanup_json_responses import cleanup_expired_json_responses
    cleanup_expired_json_responses(dry_run=False)


@then(parsers.parse('the business "{name}" should have no JSON responses'))
def verify_no_json(name):
    """Verify business has no JSON data."""
    result = execute_query(
        """
        SELECT yelp_response_json, google_response_json
        FROM businesses
        WHERE name = %s
        """,
        (name,)
    )
    
    assert len(result) == 1
    assert result[0]["yelp_response_json"] is None
    assert result[0]["google_response_json"] is None


@then("the business should still have all other fields intact")
def verify_other_fields_intact(test_data):
    """Verify non-JSON fields are preserved."""
    result = execute_query(
        """
        SELECT name, address, city, state, zip, email, phone, website
        FROM businesses
        WHERE id = %s
        """,
        (test_data["complete_business_id"],)
    )
    
    assert len(result) == 1
    business = result[0]
    
    # Verify all fields are still populated
    assert business["name"] is not None
    assert business["address"] is not None
    assert business["city"] is not None
    assert business["state"] is not None
    assert business["zip"] is not None
    assert business["email"] is not None
    assert business["phone"] is not None
    assert business["website"] is not None


@given(parsers.parse("I have {count:d} businesses with expired JSON responses"))
def create_expired_businesses(count, test_data):
    """Create multiple businesses with expired JSON."""
    test_data["expired_ids"] = []
    
    for i in range(count):
        business_id = save_business(
            name=f"Expired Business {i}",
            address=f"{i} Expired Ave",
            city="Old City",
            state="OC",
            zip_code="00000",
            category="Test",
            source="test",
            yelp_response_json={"id": f"expired-{i}"}
        )
        
        # Set to expired
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE businesses 
                SET json_retention_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 day'
                WHERE id = %s
                """,
                (business_id,)
            )
            conn.commit()
        
        test_data["expired_ids"].append(business_id)


@when("I run the JSON cleanup in dry-run mode")
def run_cleanup_dry_run(test_data):
    """Run cleanup in dry-run mode."""
    from bin.cleanup_json_responses import cleanup_expired_json_responses
    test_data["dry_run_count"] = cleanup_expired_json_responses(dry_run=True)


@then(parsers.parse("I should see that {count:d} businesses would be cleaned"))
def verify_dry_run_count(count, test_data):
    """Verify dry-run reported count."""
    assert test_data["dry_run_count"] == count


@then("no JSON data should actually be removed")
def verify_no_removal(test_data):
    """Verify JSON data still exists."""
    result = execute_query(
        """
        SELECT COUNT(*) as count
        FROM businesses
        WHERE id = ANY(%s)
        AND yelp_response_json IS NOT NULL
        """,
        (test_data["expired_ids"],)
    )
    
    assert result[0]["count"] == len(test_data["expired_ids"])


# Cleanup function for test data
def cleanup_test_businesses(test_data):
    """Clean up test businesses after scenarios."""
    ids_to_delete = []
    
    # Collect all test business IDs
    for key in ["yelp_business_id", "google_business_id", "complete_business_id"]:
        if key in test_data:
            ids_to_delete.append(test_data[key])
    
    if "test_businesses" in test_data:
        ids_to_delete.extend([b["id"] for b in test_data["test_businesses"]])
    
    if "expired_ids" in test_data:
        ids_to_delete.extend(test_data["expired_ids"])
    
    # Delete test data
    if ids_to_delete:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM businesses WHERE id = ANY(%s)", (ids_to_delete,))
            conn.commit()