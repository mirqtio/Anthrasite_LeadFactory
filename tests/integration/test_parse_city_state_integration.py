"""Integration tests for parsing and storing city/state."""

import json
import pytest
from unittest.mock import patch, Mock

from leadfactory.utils.e2e_db_connector import db_connection, execute_query
from leadfactory.pipeline.scrape import save_business
from leadfactory.storage.factory import get_storage


class TestParseCityStateIntegration:
    """Integration tests for city/state parsing and storage."""
    
    @pytest.fixture
    def setup_test_vertical(self):
        """Set up a test vertical in the database."""
        with db_connection() as conn:
            cursor = conn.cursor()
            # Clean up any existing test data
            cursor.execute("DELETE FROM businesses WHERE name LIKE 'City State Test%'")
            cursor.execute("DELETE FROM verticals WHERE name = 'Test Vertical'")
            conn.commit()
            
            # Insert test vertical
            cursor.execute("""
                INSERT INTO verticals (name, yelp_alias, google_alias, priority)
                VALUES ('Test Vertical', 'testvertical', 'test_vertical', 1)
                RETURNING id
            """)
            vertical_id = cursor.fetchone()[0]
            conn.commit()
            
            yield vertical_id
            
            # Cleanup
            cursor.execute("DELETE FROM businesses WHERE name LIKE 'City State Test%'")
            cursor.execute("DELETE FROM verticals WHERE id = %s", (vertical_id,))
            conn.commit()

    def test_save_business_with_city_state(self, setup_test_vertical):
        """Test saving a business with city and state information."""
        # Save a business with city and state
        business_id = save_business(
            name="City State Test Business",
            address="123 Test Street",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            category="Test Vertical",
            website="https://testbusiness.com",
            email="test@business.com",
            phone="(415) 555-1234",
            source="yelp",
            source_id="test-yelp-123"
        )
        
        assert business_id is not None
        
        # Verify the data was saved correctly
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, address, city, state, zip, website, email, phone, source
                FROM businesses
                WHERE id = %s
            """, (business_id,))
            
            result = cursor.fetchone()
            assert result is not None
            
            name, address, city, state, zip_code, website, email, phone, source = result
            assert name == "City State Test Business"
            assert address == "123 Test Street"
            assert city == "San Francisco"
            assert state == "CA"
            assert zip_code == "94105"
            assert website == "https://testbusiness.com"
            assert email == "test@business.com"
            assert phone == "(415) 555-1234"
            assert source == "yelp"

    def test_save_multiple_businesses_different_cities(self, setup_test_vertical):
        """Test saving multiple businesses with different cities."""
        businesses = [
            {
                "name": "City State Test SF",
                "address": "100 Market St",
                "city": "San Francisco",
                "state": "CA",
                "zip_code": "94105"
            },
            {
                "name": "City State Test NYC",
                "address": "200 Broadway",
                "city": "New York",
                "state": "NY",
                "zip_code": "10001"
            },
            {
                "name": "City State Test Chicago",
                "address": "300 Michigan Ave",
                "city": "Chicago",
                "state": "IL",
                "zip_code": "60601"
            }
        ]
        
        saved_ids = []
        for biz in businesses:
            business_id = save_business(
                name=biz["name"],
                address=biz["address"],
                city=biz["city"],
                state=biz["state"],
                zip_code=biz["zip_code"],
                category="Test Vertical",
                source="manual"
            )
            saved_ids.append(business_id)
        
        # Verify all were saved
        assert all(id is not None for id in saved_ids)
        assert len(saved_ids) == 3
        
        # Query and verify
        results = execute_query("""
            SELECT name, city, state
            FROM businesses
            WHERE name LIKE 'City State Test%'
            ORDER BY name
        """)
        
        assert len(results) == 3
        assert results[0]['city'] == "Chicago"
        assert results[0]['state'] == "IL"
        assert results[1]['city'] == "New York"
        assert results[1]['state'] == "NY"
        assert results[2]['city'] == "San Francisco"
        assert results[2]['state'] == "CA"

    def test_deduplication_preserves_city_state(self, setup_test_vertical):
        """Test that deduplication preserves city/state information."""
        # Save initial business
        business_id1 = save_business(
            name="City State Dedupe Test",
            address="500 First St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            category="Test Vertical",
            website="https://dedupe-test.com",
            source="yelp",
            source_id="dedupe-123"
        )
        
        # Try to save duplicate with same website but different source
        business_id2 = save_business(
            name="City State Dedupe Test",
            address="500 First Street",  # Slightly different
            city="San Francisco",
            state="CA",
            zip_code="94105",
            category="Test Vertical",
            website="https://dedupe-test.com",  # Same website
            source="google",
            source_id="google-dedupe-456"
        )
        
        # Should return same business ID (deduped)
        assert business_id1 == business_id2
        
        # Verify city/state are still correct
        result = execute_query(
            "SELECT city, state, source FROM businesses WHERE id = %s",
            (business_id1,)
        )[0]
        
        assert result['city'] == "San Francisco"
        assert result['state'] == "CA"
        # Source should be combined
        assert "yelp" in result['source'] or "google" in result['source']

    def test_empty_city_state_handling(self, setup_test_vertical):
        """Test handling of empty city/state values."""
        business_id = save_business(
            name="City State Empty Test",
            address="Unknown Location",
            city="",
            state="",
            zip_code="00000",
            category="Test Vertical",
            source="manual"
        )
        
        assert business_id is not None
        
        result = execute_query(
            "SELECT city, state FROM businesses WHERE id = %s",
            (business_id,)
        )[0]
        
        # Empty strings should be stored as empty, not NULL
        assert result['city'] == ""
        assert result['state'] == ""

    def test_query_businesses_by_city(self, setup_test_vertical):
        """Test querying businesses by city."""
        # Save businesses in different cities
        cities = ["San Francisco", "San Francisco", "Los Angeles", "Los Angeles", "San Diego"]
        
        for i, city in enumerate(cities):
            save_business(
                name=f"City State Query Test {i}",
                address=f"{i}00 Main St",
                city=city,
                state="CA",
                zip_code=f"9{i}000",
                category="Test Vertical",
                source="test"
            )
        
        # Query businesses in San Francisco
        sf_businesses = execute_query("""
            SELECT COUNT(*) as count
            FROM businesses
            WHERE city = 'San Francisco'
            AND name LIKE 'City State Query Test%'
        """)[0]['count']
        
        assert sf_businesses == 2
        
        # Query businesses by state
        ca_businesses = execute_query("""
            SELECT COUNT(*) as count
            FROM businesses
            WHERE state = 'CA'
            AND name LIKE 'City State Query Test%'
        """)[0]['count']
        
        assert ca_businesses == 5