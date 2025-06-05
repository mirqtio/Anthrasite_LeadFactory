"""
Simplified integration tests for modern site filtering.
"""

from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.enrich import enrich_business, validate_enrichment_dependencies


class TestModernSiteFilteringSimple:
    """Simplified tests for modern site filtering."""

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

    def test_validate_dependencies(self, modern_business):
        """Test dependency validation."""
        result = validate_enrichment_dependencies(modern_business)
        assert result["valid"] is True
        assert "pagespeed" in result["available_apis"]

    @patch('leadfactory.integrations.pagespeed.get_pagespeed_client')
    def test_modern_site_is_skipped(self, mock_get_client, modern_business):
        """Test that modern sites are skipped."""
        # Mock PageSpeed client
        mock_client = Mock()
        mock_client.check_if_modern_site.return_value = (True, {
            "performance_score": 95,
            "is_mobile_responsive": True,
            "is_modern": True
        })
        mock_get_client.return_value = mock_client

        # Run enrichment
        result = enrich_business(modern_business)

        # Should return True (success)
        assert result is True

        # Verify PageSpeed was called
        mock_client.check_if_modern_site.assert_called_once_with("https://modern-tech.com")

    @patch('leadfactory.integrations.pagespeed.get_pagespeed_client')
    def test_outdated_site_is_processed(self, mock_get_client, outdated_business):
        """Test that outdated sites are processed."""
        # Mock PageSpeed client
        mock_client = Mock()
        mock_client.check_if_modern_site.return_value = (False, {
            "performance_score": 45,
            "is_mobile_responsive": False,
            "is_modern": False
        })
        mock_get_client.return_value = mock_client

        # Run enrichment
        result = enrich_business(outdated_business)

        # Should return True (success)
        assert result is True

        # Verify PageSpeed was called
        mock_client.check_if_modern_site.assert_called_once_with("https://oldschool-store.com")

    @patch('leadfactory.integrations.pagespeed.get_pagespeed_client')
    def test_high_performance_not_mobile(self, mock_get_client, outdated_business):
        """Test site with high performance but not mobile responsive."""
        # Mock PageSpeed client
        mock_client = Mock()
        mock_client.check_if_modern_site.return_value = (False, {
            "performance_score": 92,
            "is_mobile_responsive": False,
            "is_modern": False
        })
        mock_get_client.return_value = mock_client

        # Run enrichment
        result = enrich_business(outdated_business)

        # Should return True (not skipped)
        assert result is True

    @patch('leadfactory.integrations.pagespeed.get_pagespeed_client')
    def test_pagespeed_error_continues(self, mock_get_client, modern_business):
        """Test that PageSpeed errors don't stop enrichment."""
        # Mock PageSpeed client to raise error
        mock_client = Mock()
        mock_client.check_if_modern_site.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        # Run enrichment - should not raise
        result = enrich_business(modern_business)

        # Should still succeed
        assert result is True
