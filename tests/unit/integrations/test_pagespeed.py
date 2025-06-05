"""
Unit tests for PageSpeed Insights integration.
"""

import json
from unittest.mock import Mock, patch

import pytest
import requests

from leadfactory.integrations.pagespeed import PageSpeedInsightsClient


@pytest.fixture
def pagespeed_client():
    """Create a PageSpeed client for testing."""
    return PageSpeedInsightsClient(api_key="test_key")


@pytest.fixture
def mock_modern_site_response():
    """Mock response for a modern, well-optimized site."""
    return {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.95},  # 95% performance
                "accessibility": {"score": 0.88},
                "best-practices": {"score": 0.92},
                "seo": {"score": 0.90}
            },
            "audits": {
                "viewport": {"score": 1},  # Has viewport meta tag
                "tap-targets": {"score": 0.95},  # Good tap targets
                "first-contentful-paint": {"numericValue": 1200},
                "speed-index": {"numericValue": 1500},
                "largest-contentful-paint": {"numericValue": 2000},
                "interactive": {"numericValue": 2500},
                "total-blocking-time": {"numericValue": 100},
                "cumulative-layout-shift": {"numericValue": 0.05}
            }
        }
    }


@pytest.fixture
def mock_outdated_site_response():
    """Mock response for an outdated site."""
    return {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.45},  # 45% performance
                "accessibility": {"score": 0.65},
                "best-practices": {"score": 0.70},
                "seo": {"score": 0.60}
            },
            "audits": {
                "viewport": {"score": 0},  # No viewport meta tag
                "tap-targets": {"score": 0.60},  # Poor tap targets
                "first-contentful-paint": {"numericValue": 4500},
                "speed-index": {"numericValue": 7000},
                "largest-contentful-paint": {"numericValue": 8500},
                "interactive": {"numericValue": 10000},
                "total-blocking-time": {"numericValue": 1500},
                "cumulative-layout-shift": {"numericValue": 0.25}
            }
        }
    }


@pytest.fixture
def mock_good_performance_no_mobile_response():
    """Mock response for a site with good performance but not mobile responsive."""
    return {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.92},  # 92% performance
                "accessibility": {"score": 0.75},
                "best-practices": {"score": 0.80},
                "seo": {"score": 0.85}
            },
            "audits": {
                "viewport": {"score": 0},  # No viewport meta tag
                "tap-targets": {"score": 0.50},  # Poor tap targets
                "first-contentful-paint": {"numericValue": 1800},
                "speed-index": {"numericValue": 2200},
                "largest-contentful-paint": {"numericValue": 2800},
                "interactive": {"numericValue": 3200},
                "total-blocking-time": {"numericValue": 200},
                "cumulative-layout-shift": {"numericValue": 0.08}
            }
        }
    }


class TestPageSpeedInsightsClient:
    """Tests for PageSpeed Insights client."""

    def test_client_initialization(self):
        """Test client initialization with and without API key."""
        # With API key
        client = PageSpeedInsightsClient(api_key="test_key")
        assert client.api_key == "test_key"

        # Without API key (should use env var or empty string)
        with patch.dict("os.environ", {"PAGESPEED_KEY": "env_key"}):
            client = PageSpeedInsightsClient()
            assert client.api_key == "env_key"

    @patch('requests.Session.get')
    def test_analyze_url_success(self, mock_get, pagespeed_client, mock_modern_site_response):
        """Test successful URL analysis."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_modern_site_response
        mock_get.return_value = mock_response

        result = pagespeed_client.analyze_url("https://example.com")

        assert result == mock_modern_site_response
        mock_get.assert_called_once()

        # Check the call parameters
        call_args = mock_get.call_args
        assert "https://example.com" in str(call_args)
        assert "mobile" in str(call_args)

    @patch('requests.Session.get')
    def test_analyze_url_api_error(self, mock_get, pagespeed_client):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Rate limit")
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            pagespeed_client.analyze_url("https://example.com")

    @patch('requests.Session.get')
    def test_analyze_url_timeout(self, mock_get, pagespeed_client):
        """Test timeout handling."""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        with pytest.raises(requests.exceptions.Timeout):
            pagespeed_client.analyze_url("https://example.com")

    @patch.object(PageSpeedInsightsClient, 'analyze_url')
    def test_check_modern_site_is_modern(self, mock_analyze, pagespeed_client, mock_modern_site_response):
        """Test detection of modern, well-optimized site."""
        mock_analyze.return_value = mock_modern_site_response

        is_modern, analysis_data = pagespeed_client.check_if_modern_site("https://example.com")

        assert is_modern is True
        assert analysis_data["performance_score"] == 95
        assert analysis_data["is_mobile_responsive"] is True
        assert analysis_data["is_modern"] is True

    @patch.object(PageSpeedInsightsClient, 'analyze_url')
    def test_check_modern_site_is_outdated(self, mock_analyze, pagespeed_client, mock_outdated_site_response):
        """Test detection of outdated site."""
        mock_analyze.return_value = mock_outdated_site_response

        is_modern, analysis_data = pagespeed_client.check_if_modern_site("https://example.com")

        assert is_modern is False
        assert analysis_data["performance_score"] == 45
        assert analysis_data["is_mobile_responsive"] is False
        assert analysis_data["is_modern"] is False

    @patch.object(PageSpeedInsightsClient, 'analyze_url')
    def test_check_modern_site_good_performance_no_mobile(
        self, mock_analyze, pagespeed_client, mock_good_performance_no_mobile_response
    ):
        """Test site with good performance but not mobile responsive."""
        mock_analyze.return_value = mock_good_performance_no_mobile_response

        is_modern, analysis_data = pagespeed_client.check_if_modern_site("https://example.com")

        # Should NOT be modern because it's not mobile responsive
        assert is_modern is False
        assert analysis_data["performance_score"] == 92
        assert analysis_data["is_mobile_responsive"] is False
        assert analysis_data["is_modern"] is False

    @patch.object(PageSpeedInsightsClient, 'analyze_url')
    def test_check_modern_site_error_handling(self, mock_analyze, pagespeed_client):
        """Test error handling in modern site check."""
        mock_analyze.side_effect = Exception("API Error")

        is_modern, analysis_data = pagespeed_client.check_if_modern_site("https://example.com")

        # On error, should not skip (assume not modern)
        assert is_modern is False
        assert "error" in analysis_data
        assert analysis_data["error"] == "API Error"

    def test_extract_metrics(self, pagespeed_client, mock_modern_site_response):
        """Test metric extraction from analysis data."""
        metrics = pagespeed_client.extract_metrics(mock_modern_site_response)

        assert metrics["performance_score"] == 95
        assert metrics["accessibility_score"] == 88
        assert metrics["best_practices_score"] == 92
        assert metrics["seo_score"] == 90
        assert metrics["first_contentful_paint"] == 1200
        assert metrics["speed_index"] == 1500
        assert metrics["largest_contentful_paint"] == 2000
        assert metrics["time_to_interactive"] == 2500
        assert metrics["total_blocking_time"] == 100
        assert metrics["cumulative_layout_shift"] == 0.05

    @patch('requests.Session.get')
    def test_cost_tracking(self, mock_get, pagespeed_client, mock_modern_site_response):
        """Test that API calls are tracked for cost (even though free)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_modern_site_response
        mock_get.return_value = mock_response

        # Mock the cost tracker's add_cost method
        with patch.object(pagespeed_client.cost_tracker, 'add_cost') as mock_add_cost:
            pagespeed_client.analyze_url("https://example.com")

            # Verify cost tracking was called
            mock_add_cost.assert_called_once_with(
                amount=0.0,  # PageSpeed is free
                service="pagespeed",
                operation="analyze",
                details={"url": "https://example.com", "strategy": "mobile"}
            )


class TestPageSpeedIntegration:
    """Integration tests for PageSpeed functionality."""

    @patch('leadfactory.integrations.pagespeed.get_env')
    def test_client_factory(self, mock_get_env):
        """Test the get_pagespeed_client factory function."""
        mock_get_env.return_value = "factory_key"

        from leadfactory.integrations.pagespeed import get_pagespeed_client
        client = get_pagespeed_client()

        assert isinstance(client, PageSpeedInsightsClient)
        assert client.api_key == "factory_key"
