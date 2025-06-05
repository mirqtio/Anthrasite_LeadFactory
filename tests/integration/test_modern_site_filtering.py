"""
Integration tests for modern site filtering in the enrichment pipeline.
"""

import json
from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.enrich import enrich_business, validate_enrichment_dependencies


class TestModernSiteFiltering:
    """Test modern site filtering in enrichment pipeline."""

    @pytest.fixture
    def modern_business(self):
        """Business with a modern website."""
        return {
            "id": 1,
            "name": "Modern Tech Co",
            "website": "https://modern-tech.com"
        }

    @pytest.fixture
    def outdated_business(self):
        """Business with an outdated website."""
        return {
            "id": 2,
            "name": "Old School Store",
            "website": "https://oldschool-store.com"
        }

    @pytest.fixture
    def mock_pagespeed_modern_response(self):
        """Mock PageSpeed response for modern site."""
        return {
            "performance_score": 95,
            "is_mobile_responsive": True,
            "has_viewport": True,
            "tap_targets_ok": True,
            "is_modern": True,
            "lighthouse_result": {
                "categories": {"performance": {"score": 0.95}},
                "audits": {"viewport": {"score": 1}}
            }
        }

    @pytest.fixture
    def mock_pagespeed_outdated_response(self):
        """Mock PageSpeed response for outdated site."""
        return {
            "performance_score": 45,
            "is_mobile_responsive": False,
            "has_viewport": False,
            "tap_targets_ok": False,
            "is_modern": False,
            "lighthouse_result": {
                "categories": {"performance": {"score": 0.45}},
                "audits": {"viewport": {"score": 0}}
            }
        }

    def test_validate_enrichment_dependencies(self, modern_business):
        """Test dependency validation."""
        result = validate_enrichment_dependencies(modern_business)

        assert result["valid"] is True
        assert len(result["missing_dependencies"]) == 0
        assert "pagespeed" in result["available_apis"]

    def test_validate_missing_website(self):
        """Test validation with missing website."""
        business = {"id": 1, "name": "Test Co", "website": ""}
        result = validate_enrichment_dependencies(business)

        assert result["valid"] is False
        assert "website_url" in result["missing_dependencies"]

    @patch('leadfactory.integrations.pagespeed.get_pagespeed_client')
    def test_enrich_modern_site_skipped(
        self, mock_get_client, modern_business, mock_pagespeed_modern_response
    ):
        """Test that modern sites are marked as skipped."""
        # Mock PageSpeed client and its method
        mock_client = Mock()
        mock_client.check_if_modern_site.return_value = (True, mock_pagespeed_modern_response)
        mock_get_client.return_value = mock_client

        # Track save_features calls
        saved_data = []

        def mock_save(*args, **kwargs):
            saved_data.append(kwargs)
            return True

        with patch('leadfactory.pipeline.enrich.save_features', side_effect=mock_save):
            # Run enrichment
            result = enrich_business(modern_business)

        # Should return True (successful)
        assert result is True

        # Verify save_features was called with skip_reason
        assert len(saved_data) > 0
        last_save = saved_data[-1]
        assert last_save.get("skip_reason") == "modern_site"
        assert last_save.get("business_id") == modern_business["id"]

    @patch('leadfactory.pipeline.enrich.save_features')
    @patch('leadfactory.integrations.pagespeed.PageSpeedInsightsClient.check_if_modern_site')
    def test_enrich_outdated_site_processed(
        self, mock_check_modern, mock_save_features, outdated_business, mock_pagespeed_outdated_response
    ):
        """Test that outdated sites are processed normally."""
        # Mock PageSpeed to return outdated site
        mock_check_modern.return_value = (False, mock_pagespeed_outdated_response)
        mock_save_features.return_value = True

        # Mock other enrichment steps to avoid ImportError
        with patch('leadfactory.pipeline.enrich.TechStackAnalyzer'), \
             patch('leadfactory.pipeline.enrich.ScreenshotGenerator'), \
             patch('leadfactory.pipeline.enrich.SEMrushAnalyzer'):

            # Run enrichment
            result = enrich_business(outdated_business)

        # Should return True without skip
        assert result is True

        # Verify save_features was called without skip_reason
        mock_save_features.assert_called()
        call_args = mock_save_features.call_args
        # Check that skip_reason is not in the kwargs
        assert "skip_reason" not in call_args.kwargs

    @patch('leadfactory.pipeline.enrich.save_features')
    @patch('leadfactory.integrations.pagespeed.PageSpeedInsightsClient.check_if_modern_site')
    def test_enrich_pagespeed_error_continues(
        self, mock_check_modern, mock_save_features, outdated_business
    ):
        """Test that PageSpeed errors don't stop enrichment."""
        # Mock PageSpeed to raise error
        mock_check_modern.side_effect = Exception("PageSpeed API error")
        mock_save_features.return_value = True

        # Mock other enrichment steps
        with patch('leadfactory.pipeline.enrich.TechStackAnalyzer'), \
             patch('leadfactory.pipeline.enrich.ScreenshotGenerator'), \
             patch('leadfactory.pipeline.enrich.SEMrushAnalyzer'):

            # Run enrichment - should not raise
            result = enrich_business(outdated_business)

        # Should still succeed (continue without PageSpeed)
        assert result is True

    @patch('leadfactory.integrations.pagespeed.PageSpeedInsightsClient.check_if_modern_site')
    def test_enrich_high_performance_not_mobile(self, mock_check_modern, outdated_business):
        """Test site with high performance but not mobile responsive."""
        # Mock response with high performance but not mobile responsive
        mock_response = {
            "performance_score": 92,
            "is_mobile_responsive": False,
            "has_viewport": False,
            "tap_targets_ok": False,
            "is_modern": False,
            "lighthouse_result": {}
        }
        mock_check_modern.return_value = (False, mock_response)

        with patch('leadfactory.pipeline.enrich.save_features') as mock_save:
            mock_save.return_value = True

            # Mock other enrichment steps
            with patch('leadfactory.pipeline.enrich.TechStackAnalyzer'), \
                 patch('leadfactory.pipeline.enrich.ScreenshotGenerator'), \
                 patch('leadfactory.pipeline.enrich.SEMrushAnalyzer'):

                result = enrich_business(outdated_business)

        # Should NOT skip (needs both performance AND mobile)
        assert result is True
        call_args = mock_save.call_args
        assert "skip_reason" not in call_args.kwargs
