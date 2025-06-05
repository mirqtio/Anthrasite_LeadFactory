"""Test skip modern sites functionality."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the module we're testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bin.enrich import (
    enrich_business,
    mark_business_as_processed,
    PageSpeedAnalyzer,
    TechStackAnalyzer,
)


class TestSkipModernSites:
    """Test skipping modern sites functionality."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection."""
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        mock_cursor.fetchone = Mock(return_value=None)
        
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.__exit__ = Mock(return_value=None)
        
        return mock_conn, mock_cursor

    @pytest.fixture
    def high_performing_site_data(self):
        """Performance data for a modern, high-performing site."""
        return {
            "performance_score": 95,
            "accessibility_score": 88,
            "best_practices_score": 92,
            "seo_score": 100,
            "first_contentful_paint": 800,
            "largest_contentful_paint": 1500,
            "cumulative_layout_shift": 0.05,
            "total_blocking_time": 50,
            "speed_index": 1200,
            "time_to_interactive": 2000,
        }

    @pytest.fixture
    def low_performing_site_data(self):
        """Performance data for an outdated, low-performing site."""
        return {
            "performance_score": 45,
            "accessibility_score": 60,
            "best_practices_score": 70,
            "seo_score": 75,
            "first_contentful_paint": 3000,
            "largest_contentful_paint": 5000,
            "cumulative_layout_shift": 0.25,
            "total_blocking_time": 500,
            "speed_index": 4000,
            "time_to_interactive": 6000,
        }

    @patch('bin.enrich.get_database_connection')
    def test_mark_business_as_processed(self, mock_get_db, mock_db_connection):
        """Test marking a business as processed with skip reason."""
        mock_conn, mock_cursor = mock_db_connection
        mock_get_db.return_value = mock_conn
        
        # Call the function
        result = mark_business_as_processed(123, "modern_site")
        
        # Verify it returns True
        assert result is True
        
        # Verify database calls
        assert mock_cursor.execute.call_count == 2
        
        # Check UPDATE call
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE businesses" in update_call[0][0]
        assert update_call[0][1] == ("skipped_modern_site", 123)
        
        # Check INSERT call
        insert_call = mock_cursor.execute.call_args_list[1]
        assert "INSERT INTO features" in insert_call[0][0]
        insert_params = insert_call[0][1]
        assert insert_params[0] == 123  # business_id
        assert json.loads(insert_params[1]) == {"skip_reason": "modern_site"}
        assert insert_params[2] == 90  # page_speed score

    @patch('bin.enrich.get_database_connection')
    @patch('bin.enrich.PageSpeedAnalyzer')
    @patch('bin.enrich.TechStackAnalyzer')
    @patch('bin.enrich.logger')
    def test_enrich_business_skips_modern_site(
        self, mock_logger, mock_tech_analyzer_class, mock_pagespeed_class, mock_get_db, 
        mock_db_connection, high_performing_site_data
    ):
        """Test that high-performing sites are skipped."""
        mock_conn, mock_cursor = mock_db_connection
        mock_get_db.return_value = mock_conn
        
        # Mock analyzers
        mock_tech_analyzer = Mock()
        mock_tech_analyzer.analyze_website.return_value = (
            {"technologies": ["React", "Node.js"]}, None
        )
        mock_tech_analyzer_class.return_value = mock_tech_analyzer
        
        mock_pagespeed = Mock()
        mock_pagespeed.analyze_website.return_value = (high_performing_site_data, None)
        mock_pagespeed_class.return_value = mock_pagespeed
        
        # Test data
        business = {
            "id": 123,
            "website": "https://example.com",
            "name": "Example Business"
        }
        
        # Call the function
        result = enrich_business(business)
        
        # Verify it returns True
        assert result is True
        
        # Verify it analyzed the site
        mock_tech_analyzer.analyze_website.assert_called_once_with("https://example.com")
        mock_pagespeed.analyze_website.assert_called_once_with("https://example.com")
        
        # Verify it logged the skip
        mock_logger.info.assert_any_call(
            "Skipping modern site https://example.com (performance: 95, "
            "accessibility: 88) - marking as processed"
        )
        
        # Verify database updates for skipping
        assert mock_cursor.execute.call_count == 2
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE businesses" in update_call[0][0]
        assert "skipped_modern_site" in update_call[0][1]

    @patch('bin.enrich.get_database_connection')
    @patch('bin.enrich.PageSpeedAnalyzer')
    @patch('bin.enrich.TechStackAnalyzer')
    @patch('bin.enrich.save_features')
    def test_enrich_business_processes_low_performing_site(
        self, mock_save_features, mock_tech_analyzer_class, mock_pagespeed_class, 
        mock_get_db, mock_db_connection, low_performing_site_data
    ):
        """Test that low-performing sites are processed normally."""
        mock_conn, mock_cursor = mock_db_connection
        mock_get_db.return_value = mock_conn
        mock_save_features.return_value = True
        
        # Mock analyzers
        mock_tech_analyzer = Mock()
        mock_tech_analyzer.analyze_website.return_value = (
            {"technologies": ["WordPress", "PHP"]}, None
        )
        mock_tech_analyzer_class.return_value = mock_tech_analyzer
        
        mock_pagespeed = Mock()
        mock_pagespeed.analyze_website.return_value = (low_performing_site_data, None)
        mock_pagespeed_class.return_value = mock_pagespeed
        
        # Test data
        business = {
            "id": 456,
            "website": "https://outdated-site.com",
            "name": "Outdated Business"
        }
        
        # Call the function
        result = enrich_business(business)
        
        # Verify it returns True
        assert result is True
        
        # Verify it analyzed the site
        mock_tech_analyzer.analyze_website.assert_called_once()
        mock_pagespeed.analyze_website.assert_called_once()
        
        # Verify it saved features (not skipped)
        mock_save_features.assert_called_once()
        save_call_args = mock_save_features.call_args[1]
        assert save_call_args["business_id"] == 456
        assert save_call_args["page_speed"] == low_performing_site_data
        
        # Verify no skip database calls
        assert mock_cursor.execute.call_count == 0

    @patch('bin.enrich.get_database_connection')
    @patch('bin.enrich.PageSpeedAnalyzer')
    @patch('bin.enrich.TechStackAnalyzer')
    @patch('bin.enrich.logger')
    def test_enrich_business_edge_case_scores(
        self, mock_logger, mock_tech_analyzer_class, mock_pagespeed_class, 
        mock_get_db, mock_db_connection
    ):
        """Test edge cases for performance scores."""
        mock_conn, mock_cursor = mock_db_connection
        mock_get_db.return_value = mock_conn
        
        # Mock analyzers
        mock_tech_analyzer = Mock()
        mock_tech_analyzer.analyze_website.return_value = ({}, None)
        mock_tech_analyzer_class.return_value = mock_tech_analyzer
        
        mock_pagespeed = Mock()
        mock_pagespeed_class.return_value = mock_pagespeed
        
        test_cases = [
            # (performance_score, accessibility_score, should_skip)
            (90, 80, True),   # Exactly at threshold - should skip
            (89, 80, False),  # Just below performance threshold
            (90, 79, False),  # Just below accessibility threshold
            (95, 85, True),   # Well above thresholds
            (100, 100, True), # Perfect scores
            (0, 0, False),    # Worst scores
        ]
        
        for perf_score, access_score, should_skip in test_cases:
            mock_cursor.execute.reset_mock()
            
            performance_data = {
                "performance_score": perf_score,
                "accessibility_score": access_score,
            }
            mock_pagespeed.analyze_website.return_value = (performance_data, None)
            
            business = {"id": 999, "website": "https://test.com"}
            
            # Mock save_features to avoid actual DB call
            with patch('bin.enrich.save_features', return_value=True):
                result = enrich_business(business)
            
            assert result is True
            
            if should_skip:
                # Should have called mark_business_as_processed
                assert mock_cursor.execute.call_count == 2
                assert "UPDATE businesses" in mock_cursor.execute.call_args_list[0][0][0]
            else:
                # Should not have called mark_business_as_processed
                assert mock_cursor.execute.call_count == 0