"""Integration tests for JSON retention functionality."""

import json
from datetime import datetime, timedelta

import pytest

from leadfactory.pipeline.scrape import save_business
from leadfactory.storage.factory import get_storage
from leadfactory.utils.e2e_db_connector import db_connection, execute_query


class TestJSONRetentionIntegration:
    """Integration tests for JSON retention with real database."""

    @pytest.fixture
    def setup_test_business(self):
        """Set up test business with JSON data."""
        # Clean up any existing test data
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM businesses WHERE name LIKE 'JSON Retention Test%'")
            conn.commit()

        # Create test business with JSON data
        yelp_json = {
            "id": "json-retention-test-123",
            "name": "JSON Retention Test Business",
            "location": {
                "address1": "999 Test Ave",
                "city": "Test City",
                "state": "TC",
                "zip_code": "99999"
            }
        }

        google_json = {
            "place_id": "ChIJjsonRetentionTest",
            "name": "JSON Retention Test Business",
            "formatted_address": "999 Test Ave, Test City, TC 99999"
        }

        business_id = save_business(
            name="JSON Retention Test Business",
            address="999 Test Ave",
            city="Test City",
            state="TC",
            zip_code="99999",
            category="Test",
            source="test",
            yelp_response_json=yelp_json,
            google_response_json=google_json
        )

        yield business_id

        # Cleanup
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM businesses WHERE id = %s", (business_id,))
            conn.commit()

    def test_json_retention_field_populated(self, setup_test_business):
        """Test that json_retention_expires_at is populated when saving JSON."""
        business_id = setup_test_business

        # Check that retention field was set
        result = execute_query(
            "SELECT json_retention_expires_at FROM businesses WHERE id = %s",
            (business_id,)
        )

        assert len(result) == 1
        assert result[0]["json_retention_expires_at"] is not None

        # Verify it's set to approximately 90 days from now
        retention_date = result[0]["json_retention_expires_at"]
        expected_date = datetime.now() + timedelta(days=90)

        # Allow 1 hour tolerance for test execution time
        assert abs((retention_date - expected_date).total_seconds()) < 3600

    def test_expired_json_cleanup(self, setup_test_business):
        """Test cleanup of expired JSON data."""
        business_id = setup_test_business

        # Manually set retention date to past
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

        # Import and run cleanup function
        from bin.cleanup_json_responses import cleanup_expired_json_responses

        # Run cleanup
        cleaned_count = cleanup_expired_json_responses(dry_run=False)

        assert cleaned_count >= 1

        # Verify JSON fields are now NULL
        result = execute_query(
            """
            SELECT yelp_response_json, google_response_json, json_retention_expires_at
            FROM businesses
            WHERE id = %s
            """,
            (business_id,)
        )

        assert len(result) == 1
        assert result[0]["yelp_response_json"] is None
        assert result[0]["google_response_json"] is None
        assert result[0]["json_retention_expires_at"] is None

    def test_cleanup_preserves_other_fields(self, setup_test_business):
        """Test that cleanup only affects JSON fields."""
        business_id = setup_test_business

        # Get original business data
        original = execute_query(
            "SELECT name, address, city, state, zip, email, phone, website FROM businesses WHERE id = %s",
            (business_id,)
        )[0]

        # Set retention to expired
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

        # Run cleanup
        from bin.cleanup_json_responses import cleanup_expired_json_responses
        cleanup_expired_json_responses(dry_run=False)

        # Verify other fields are unchanged
        after_cleanup = execute_query(
            "SELECT name, address, city, state, zip, email, phone, website FROM businesses WHERE id = %s",
            (business_id,)
        )[0]

        assert after_cleanup == original

    def test_cleanup_statistics(self):
        """Test JSON storage statistics calculation."""
        from bin.cleanup_json_responses import get_json_storage_stats

        stats = get_json_storage_stats()

        # Verify statistics structure
        assert "total_records" in stats
        assert "yelp_json_count" in stats
        assert "google_json_count" in stats
        assert "expired_records" in stats
        assert "total_json_size" in stats

        # Verify counts are non-negative
        assert stats["total_records"] >= 0
        assert stats["yelp_json_count"] >= 0
        assert stats["google_json_count"] >= 0
        assert stats["expired_records"] >= 0

    def test_dry_run_mode(self, setup_test_business):
        """Test that dry run doesn't modify data."""
        business_id = setup_test_business

        # Set retention to expired
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

        # Get JSON data before dry run
        before = execute_query(
            "SELECT yelp_response_json, google_response_json FROM businesses WHERE id = %s",
            (business_id,)
        )[0]

        # Run cleanup in dry run mode
        from bin.cleanup_json_responses import cleanup_expired_json_responses
        cleaned_count = cleanup_expired_json_responses(dry_run=True)

        # Should report what would be cleaned
        assert cleaned_count >= 1

        # Verify data is unchanged
        after = execute_query(
            "SELECT yelp_response_json, google_response_json FROM businesses WHERE id = %s",
            (business_id,)
        )[0]

        assert after == before
        assert after["yelp_response_json"] is not None
        assert after["google_response_json"] is not None

    def test_batch_processing(self):
        """Test that cleanup processes in batches correctly."""
        # Create multiple test businesses
        business_ids = []

        try:
            for i in range(5):
                business_id = save_business(
                    name=f"JSON Batch Test {i}",
                    address=f"{i} Batch St",
                    city="Batch City",
                    state="BC",
                    zip_code="12345",
                    category="Test",
                    source="test",
                    yelp_response_json={"id": f"batch-{i}"},
                    google_response_json={"place_id": f"ChIJbatch{i}"}
                )
                business_ids.append(business_id)

            # Set all to expired
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE businesses
                    SET json_retention_expires_at = CURRENT_TIMESTAMP - INTERVAL '1 day'
                    WHERE id = ANY(%s)
                    """,
                    (business_ids,)
                )
                conn.commit()

            # Run cleanup with small batch size
            from bin.cleanup_json_responses import cleanup_expired_json_responses
            cleaned = cleanup_expired_json_responses(dry_run=False, batch_size=2)

            # Should clean all 5 records across multiple batches
            assert cleaned == 5

            # Verify all are cleaned
            result = execute_query(
                """
                SELECT COUNT(*) as count
                FROM businesses
                WHERE id = ANY(%s)
                AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
                """,
                (business_ids,)
            )

            assert result[0]["count"] == 0

        finally:
            # Cleanup test data
            if business_ids:
                with db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM businesses WHERE id = ANY(%s)", (business_ids,))
                    conn.commit()
