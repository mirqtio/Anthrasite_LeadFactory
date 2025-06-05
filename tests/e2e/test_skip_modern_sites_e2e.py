"""End-to-end tests for skipping modern sites in the full pipeline."""

import json
import subprocess
import pytest
from unittest.mock import patch, Mock

from leadfactory.utils.e2e_db_connector import db_connection, execute_query


class TestSkipModernSitesE2E:
    """End-to-end tests for skipping modern sites functionality."""
    
    @pytest.fixture
    def setup_e2e_businesses(self):
        """Set up test businesses for E2E testing."""
        with db_connection() as conn:
            cursor = conn.cursor()
            # Clean up any existing test data
            cursor.execute("""
                DELETE FROM emails WHERE business_id IN (
                    SELECT id FROM businesses WHERE name LIKE 'E2E Modern Test%'
                )
            """)
            cursor.execute("DELETE FROM features WHERE business_id IN (SELECT id FROM businesses WHERE name LIKE 'E2E Modern Test%')")
            cursor.execute("DELETE FROM businesses WHERE name LIKE 'E2E Modern Test%'")
            conn.commit()
            
            # Insert test businesses with various performance profiles
            cursor.execute("""
                INSERT INTO businesses (name, website, email, address, status, vertical)
                VALUES 
                    ('E2E Modern Test - High Performer', 'https://vercel.com', 'test1@example.com', '123 Modern Ave', 'pending', 'Tech'),
                    ('E2E Modern Test - Low Performer', 'http://old-site-example.com', 'test2@example.com', '456 Legacy Rd', 'pending', 'Retail'),
                    ('E2E Modern Test - Medium Performer', 'https://medium-site.com', 'test3@example.com', '789 Average St', 'pending', 'Services')
                RETURNING id
            """)
            ids = [(row[0],) for row in cursor.fetchall()]
            conn.commit()
            
            yield [id[0] for id in ids]
            
            # Cleanup
            cursor.execute("""
                DELETE FROM emails WHERE business_id IN %s
            """, (tuple([id[0] for id in ids]),))
            cursor.execute("DELETE FROM features WHERE business_id IN %s", (tuple([id[0] for id in ids]),))
            cursor.execute("DELETE FROM businesses WHERE id IN %s", (tuple([id[0] for id in ids]),))
            conn.commit()

    @patch('bin.enrich.PageSpeedAnalyzer')
    @patch('bin.enrich.TechStackAnalyzer')
    def test_full_pipeline_with_modern_site_filtering(
        self, mock_tech_analyzer_class, mock_pagespeed_class, setup_e2e_businesses
    ):
        """Test the complete pipeline flow with modern site filtering."""
        business_ids = setup_e2e_businesses
        
        # Mock analyzers with different scores for each site
        mock_tech_analyzer = Mock()
        mock_tech_analyzer.analyze_website.side_effect = [
            ({"technologies": ["Next.js", "React", "Vercel"]}, None),  # Modern
            ({"technologies": ["PHP", "WordPress 3.0"]}, None),        # Outdated
            ({"technologies": ["React", "Express"]}, None),            # Medium
        ]
        mock_tech_analyzer_class.return_value = mock_tech_analyzer
        
        mock_pagespeed = Mock()
        mock_pagespeed.analyze_website.side_effect = [
            # High performer - should be skipped
            ({
                "performance_score": 98,
                "accessibility_score": 95,
                "best_practices_score": 100,
                "seo_score": 100,
            }, None),
            # Low performer - should be processed
            ({
                "performance_score": 35,
                "accessibility_score": 55,
                "best_practices_score": 60,
                "seo_score": 40,
            }, None),
            # Medium performer - should be processed
            ({
                "performance_score": 75,
                "accessibility_score": 85,
                "best_practices_score": 80,
                "seo_score": 90,
            }, None),
        ]
        mock_pagespeed_class.return_value = mock_pagespeed
        
        # Run enrichment for test businesses
        businesses = execute_query("""
            SELECT * FROM businesses 
            WHERE id IN %s
            ORDER BY id
        """, (tuple(business_ids),))
        
        for business in businesses:
            from bin.enrich import enrich_business
            result = enrich_business(business)
            assert result is True
        
        # Verify results
        with db_connection() as conn:
            cursor = conn.cursor()
            
            # Check high performer (should be skipped)
            cursor.execute("""
                SELECT b.id, b.name, b.status, f.page_speed, f.tech_stack
                FROM businesses b
                LEFT JOIN features f ON b.id = f.business_id
                WHERE b.id = %s
            """, (business_ids[0],))
            
            high_perf = cursor.fetchone()
            assert high_perf[2] == "skipped_modern_site"
            assert high_perf[3] == 90  # Threshold score
            tech_stack = json.loads(high_perf[4])
            assert tech_stack.get("skip_reason") == "modern_site"
            
            # Check low performer (should be processed normally)
            cursor.execute("""
                SELECT b.id, b.name, b.status, f.page_speed, f.tech_stack
                FROM businesses b
                LEFT JOIN features f ON b.id = f.business_id
                WHERE b.id = %s
            """, (business_ids[1],))
            
            low_perf = cursor.fetchone()
            assert low_perf[2] == "pending"  # Not skipped
            assert low_perf[3] == 35  # Actual score
            tech_stack = json.loads(low_perf[4])
            assert "PHP" in tech_stack.get("technologies", [])
            
            # Check medium performer (should be processed)
            cursor.execute("""
                SELECT b.id, b.name, b.status, f.page_speed, f.tech_stack
                FROM businesses b
                LEFT JOIN features f ON b.id = f.business_id
                WHERE b.id = %s
            """, (business_ids[2],))
            
            medium_perf = cursor.fetchone()
            assert medium_perf[2] == "pending"  # Not skipped
            assert medium_perf[3] == 75  # Actual score

    def test_skipped_sites_excluded_from_email_queue(self, setup_e2e_businesses):
        """Test that skipped modern sites don't get queued for emails."""
        business_ids = setup_e2e_businesses
        
        # Manually set up one site as skipped
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE businesses 
                SET status = 'skipped_modern_site' 
                WHERE id = %s
            """, (business_ids[0],))
            cursor.execute("""
                INSERT INTO features (business_id, tech_stack, page_speed)
                VALUES (%s, %s, %s)
            """, (business_ids[0], json.dumps({"skip_reason": "modern_site"}), 95))
            
            # Set up other sites as enriched but not skipped
            for business_id in business_ids[1:]:
                cursor.execute("""
                    INSERT INTO features (business_id, tech_stack, page_speed)
                    VALUES (%s, %s, %s)
                """, (business_id, json.dumps({"technologies": ["PHP"]}), 45))
            
            conn.commit()
        
        # Query for businesses that should receive emails
        # This simulates what the email queue would do
        email_candidates = execute_query("""
            SELECT b.id, b.name, b.status, f.page_speed
            FROM businesses b
            JOIN features f ON b.id = f.business_id
            WHERE b.id IN %s
            AND b.status != 'skipped_modern_site'
            AND b.email IS NOT NULL
        """, (tuple(business_ids),))
        
        # Should only have 2 businesses (not the skipped one)
        assert len(email_candidates) == 2
        candidate_ids = [c['id'] for c in email_candidates]
        assert business_ids[0] not in candidate_ids
        assert business_ids[1] in candidate_ids
        assert business_ids[2] in candidate_ids

    @pytest.mark.parametrize("performance_score,accessibility_score,expected_status", [
        (100, 100, "skipped_modern_site"),  # Perfect scores
        (90, 80, "skipped_modern_site"),    # Exactly at threshold
        (95, 85, "skipped_modern_site"),    # Above threshold
        (89, 85, "pending"),                # Just below performance threshold
        (95, 79, "pending"),                # Just below accessibility threshold
        (50, 50, "pending"),                # Well below thresholds
    ])
    def test_threshold_edge_cases(
        self, performance_score, accessibility_score, expected_status, setup_e2e_businesses
    ):
        """Test various threshold edge cases."""
        business_id = setup_e2e_businesses[0]
        
        with patch('bin.enrich.PageSpeedAnalyzer') as mock_pagespeed_class:
            with patch('bin.enrich.TechStackAnalyzer') as mock_tech_class:
                # Mock analyzers
                mock_tech = Mock()
                mock_tech.analyze_website.return_value = ({"technologies": ["React"]}, None)
                mock_tech_class.return_value = mock_tech
                
                mock_pagespeed = Mock()
                mock_pagespeed.analyze_website.return_value = ({
                    "performance_score": performance_score,
                    "accessibility_score": accessibility_score,
                }, None)
                mock_pagespeed_class.return_value = mock_pagespeed
                
                # Get and enrich business
                business = execute_query(
                    "SELECT * FROM businesses WHERE id = %s",
                    (business_id,)
                )[0]
                
                from bin.enrich import enrich_business
                result = enrich_business(business)
                assert result is True
                
                # Check resulting status
                status = execute_query(
                    "SELECT status FROM businesses WHERE id = %s",
                    (business_id,)
                )[0]['status']
                
                assert status == expected_status