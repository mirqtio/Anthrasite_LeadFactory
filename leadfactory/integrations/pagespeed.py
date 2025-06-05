"""
Google PageSpeed Insights API client for analyzing website performance.

This module provides integration with Google's PageSpeed Insights API to:
- Analyze website performance scores
- Check mobile responsiveness
- Filter out modern, well-optimized sites
"""

import logging
import os
from typing import Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from leadfactory.config import get_env
from leadfactory.cost.cost_tracking import CostTracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class PageSpeedInsightsClient:
    """Client for Google PageSpeed Insights API."""

    BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    COST_PER_CALL = 0.0  # PageSpeed Insights is free

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PageSpeed Insights client.

        Args:
            api_key: Optional API key. If not provided, uses PAGESPEED_KEY env var.
        """
        self.api_key = api_key or get_env("PAGESPEED_KEY", "")
        self.cost_tracker = CostTracker()

        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def analyze_url(self, url: str, strategy: str = "mobile") -> Dict:
        """
        Analyze a URL using PageSpeed Insights.

        Args:
            url: The URL to analyze
            strategy: Analysis strategy - "mobile" or "desktop" (default: "mobile")

        Returns:
            Dictionary containing analysis results

        Raises:
            requests.RequestException: If API call fails
        """
        params = {
            "url": url,
            "strategy": strategy,
            "category": "performance",  # Focus on performance metrics
        }

        if self.api_key:
            params["key"] = self.api_key

        try:
            logger.info(f"Analyzing URL with PageSpeed Insights: {url}")
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            # Track the API call (free service)
            self.cost_tracker.add_cost(
                amount=self.COST_PER_CALL,
                service="pagespeed",
                operation="analyze",
                details={"url": url, "strategy": strategy},
            )

            # API call successful

            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"PageSpeed API timeout for URL: {url}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"PageSpeed API error for URL {url}: {str(e)}")
            raise

    def check_if_modern_site(self, url: str) -> Tuple[bool, Dict]:
        """
        Check if a website is modern and well-optimized.

        According to PRD: Skip sites with performance >= 90 AND mobile responsive.

        Args:
            url: The URL to check

        Returns:
            Tuple of (is_modern, analysis_data)
            - is_modern: True if site should be skipped
            - analysis_data: Full analysis results
        """
        try:
            # Analyze the URL with mobile strategy (PRD specifies mobile)
            data = self.analyze_url(url, strategy="mobile")

            # Extract performance score
            lighthouse_result = data.get("lighthouseResult", {})
            categories = lighthouse_result.get("categories", {})
            performance = categories.get("performance", {})
            performance_score = (
                performance.get("score", 0) * 100
            )  # Convert to percentage

            # Check mobile responsiveness
            # PageSpeed includes mobile-friendly checks in its audits
            audits = lighthouse_result.get("audits", {})
            viewport_audit = audits.get("viewport", {})
            has_viewport = viewport_audit.get("score", 0) == 1

            # Additional mobile-friendly checks
            tap_targets = audits.get("tap-targets", {})
            tap_targets_ok = tap_targets.get("score", 0) >= 0.9

            is_mobile_responsive = has_viewport and tap_targets_ok

            # Site is modern if performance >= 90 AND mobile responsive
            is_modern = performance_score >= 90 and is_mobile_responsive

            analysis_data = {
                "url": url,
                "performance_score": performance_score,
                "is_mobile_responsive": is_mobile_responsive,
                "has_viewport": has_viewport,
                "tap_targets_ok": tap_targets_ok,
                "is_modern": is_modern,
                "lighthouse_result": lighthouse_result,
            }

            logger.info(
                f"PageSpeed analysis for {url}: "
                f"performance={performance_score:.1f}, "
                f"mobile_responsive={is_mobile_responsive}, "
                f"is_modern={is_modern}"
            )

            return is_modern, analysis_data

        except Exception as e:
            logger.error(f"Error checking if site is modern: {str(e)}")
            # On error, assume site is not modern (don't skip)
            return False, {"error": str(e), "url": url}

    def extract_metrics(self, analysis_data: Dict) -> Dict:
        """
        Extract key metrics from PageSpeed analysis.

        Args:
            analysis_data: Full analysis data from analyze_url

        Returns:
            Dictionary of extracted metrics
        """
        lighthouse_result = analysis_data.get("lighthouseResult", {})
        categories = lighthouse_result.get("categories", {})
        audits = lighthouse_result.get("audits", {})

        return {
            "performance_score": categories.get("performance", {}).get("score", 0)
            * 100,
            "accessibility_score": categories.get("accessibility", {}).get("score", 0)
            * 100,
            "best_practices_score": categories.get("best-practices", {}).get("score", 0)
            * 100,
            "seo_score": categories.get("seo", {}).get("score", 0) * 100,
            "first_contentful_paint": audits.get("first-contentful-paint", {}).get(
                "numericValue", 0
            ),
            "speed_index": audits.get("speed-index", {}).get("numericValue", 0),
            "largest_contentful_paint": audits.get("largest-contentful-paint", {}).get(
                "numericValue", 0
            ),
            "time_to_interactive": audits.get("interactive", {}).get("numericValue", 0),
            "total_blocking_time": audits.get("total-blocking-time", {}).get(
                "numericValue", 0
            ),
            "cumulative_layout_shift": audits.get("cumulative-layout-shift", {}).get(
                "numericValue", 0
            ),
        }


def get_pagespeed_client() -> PageSpeedInsightsClient:
    """Get a configured PageSpeed Insights client instance."""
    return PageSpeedInsightsClient()
