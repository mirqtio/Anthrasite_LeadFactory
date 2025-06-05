"""Integration tests for skipping modern sites."""

import json
import pytest
from unittest.mock import patch, Mock

from leadfactory.utils.e2e_db_connector import db_connection, execute_query
from bin.enrich import enrich_business, get_businesses_to_enrich


class TestSkipModernSitesIntegration:
    """Integration tests for skipping modern sites functionality."""
    
    @pytest.fixture
    def setup_test_business(self):
        """Set up a test business in the database."""
        with db_connection() as conn:
            cursor = conn.cursor()
            # Clean up any existing test data
            cursor.execute("DELETE FROM features WHERE business_id IN (SELECT id FROM businesses WHERE name LIKE 'Test Modern Site%')")
            cursor.execute("DELETE FROM businesses WHERE name LIKE 'Test Modern Site%'")
            conn.commit()
            
            # Insert test businesses
            cursor.execute("""
                INSERT INTO businesses (name, website, email, address, status)
                VALUES 
                    ('Test Modern Site 1', 'https://modern-site.com', 'contact@modern.com', '123 Main St', 'pending'),
                    ('Test Modern Site 2', 'https://outdated-site.com', 'contact@outdated.com', '456 Old St', 'pending')
                RETURNING id
            """)
            ids = cursor.fetchall()
            conn.commit()
            
            yield [id[0] for id in ids]
            
            # Cleanup
            cursor.execute("DELETE FROM features WHERE business_id IN %s", (tuple([id[0] for id in ids]),))
            cursor.execute("DELETE FROM businesses WHERE id IN %s", (tuple([id[0] for id in ids]),))
            conn.commit()

    @patch('bin.enrich.PageSpeedAnalyzer')
    @patch('bin.enrich.TechStackAnalyzer')
    def test_full_enrichment_flow_with_modern_site_skip(
        self, mock_tech_analyzer_class, mock_pagespeed_class, setup_test_business
    ):
        """Test the full enrichment flow with modern site skipping."""
        business_ids = setup_test_business
        
        # Mock analyzers
        mock_tech_analyzer = Mock()
        mock_tech_analyzer.analyze_website.return_value = (
            {"technologies": ["React", "Next.js", "Vercel"]}, None
        )
        mock_tech_analyzer_class.return_value = mock_tech_analyzer
        
        mock_pagespeed = Mock()
        # First site is modern (high scores)
        # Second site is outdated (low scores)
        mock_pagespeed.analyze_website.side_effect = [
            ({
                "performance_score": 95,
                "accessibility_score": 90,
                "best_practices_score": 92,
                "seo_score": 100,
            }, None),
            ({
                "performance_score": 45,
                "accessibility_score": 60,
                "best_practices_score": 70,
                "seo_score": 75,
            }, None),
        ]
        mock_pagespeed_class.return_value = mock_pagespeed
        
        # Get businesses to enrich
        businesses = get_businesses_to_enrich()
        test_businesses = [b for b in businesses if b['id'] in business_ids]
        
        assert len(test_businesses) >= 2
        
        # Enrich businesses
        for business in test_businesses:
            result = enrich_business(business)
            assert result is True
        
        # Check results in database
        with db_connection() as conn:
            cursor = conn.cursor()
            
            # Check first business (modern site - should be skipped)
            cursor.execute("""
                SELECT b.status, f.tech_stack, f.page_speed
                FROM businesses b
                LEFT JOIN features f ON b.id = f.business_id
                WHERE b.id = %s
            """, (business_ids[0],))
            
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "skipped_modern_site"
            assert json.loads(result[1]) == {"skip_reason": "modern_site"}
            assert result[2] == 90  # The threshold score we set
            
            # Check second business (outdated site - should be processed)
            cursor.execute("""
                SELECT b.status, f.tech_stack, f.page_speed
                FROM businesses b
                LEFT JOIN features f ON b.id = f.business_id
                WHERE b.id = %s
            """, (business_ids[1],))
            
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "pending"  # Status unchanged
            assert "React" in json.loads(result[1]).get("technologies", [])
            assert result[2] == 45  # Actual low score

    def test_skipped_businesses_not_reprocessed(self, setup_test_business):
        """Test that skipped businesses are not picked up for re-enrichment."""
        business_id = setup_test_business[0]
        
        # Manually mark as skipped
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE businesses SET status = 'skipped_modern_site' WHERE id = %s
            """, (business_id,))
            cursor.execute("""
                INSERT INTO features (business_id, tech_stack, page_speed)
                VALUES (%s, %s, %s)
            """, (business_id, json.dumps({"skip_reason": "modern_site"}), 90))
            conn.commit()
        
        # Try to get businesses to enrich
        businesses = get_businesses_to_enrich()
        
        # The skipped business should not be in the list
        business_ids_to_enrich = [b['id'] for b in businesses]
        assert business_id not in business_ids_to_enrich

    @patch('bin.enrich.PAGESPEED_API_KEY', 'test-key')
    @patch('bin.enrich.requests.get')
    def test_real_pagespeed_api_integration(self, mock_requests_get, setup_test_business):
        """Test integration with actual PageSpeed API response format."""
        business_id = setup_test_business[0]
        
        # Mock PageSpeed API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.95},
                    "accessibility": {"score": 0.88},
                    "best-practices": {"score": 0.92},
                    "seo": {"score": 1.0}
                },
                "audits": {
                    "first-contentful-paint": {"numericValue": 800},
                    "largest-contentful-paint": {"numericValue": 1500},
                    "cumulative-layout-shift": {"numericValue": 0.05},
                    "total-blocking-time": {"numericValue": 50},
                    "speed-index": {"numericValue": 1200},
                    "interactive": {"numericValue": 2000}
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response
        
        # Get and enrich business
        businesses = execute_query(
            "SELECT * FROM businesses WHERE id = %s",
            (business_id,)
        )
        
        assert len(businesses) == 1
        result = enrich_business(businesses[0])
        assert result is True
        
        # Verify API was called
        mock_requests_get.assert_called()
        api_call = mock_requests_get.call_args
        assert "pagespeedonline/v5/runPagespeed" in api_call[0][0]
        
        # Verify business was marked as skipped
        status = execute_query(
            "SELECT status FROM businesses WHERE id = %s",
            (business_id,)
        )[0]['status']
        assert status == "skipped_modern_site"