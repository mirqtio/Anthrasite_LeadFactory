#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Lead Enrichment (02_enrich.py)
Analyzes business websites to extract tech stack and performance metrics.

Usage:
    python bin/02_enrich.py [--limit N] [--id BUSINESS_ID] [--tier TIER]

Options:
    --limit N        Limit the number of businesses to process (default: all)
    --id BUSINESS_ID Process only the specified business ID
    --tier TIER      Override the tier level (1, 2, or 3)
"""

import os
import sys
import argparse
import logging
import time
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import logging configuration first
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Import utility functions
from utils.io import DatabaseConnection, make_api_request, track_api_cost

# Required third-party libraries
try:
    import requests
    from bs4 import BeautifulSoup
    import wappalyzer
    from wappalyzer.analyze import Wappalyzer, WebPage
except ImportError:
    print("Required libraries not found. Please install them using:")
    print("pip install requests beautifulsoup4 python-wappalyzer")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
CURRENT_TIER = int(os.getenv("TIER", "1"))
PAGESPEED_API_KEY = os.getenv("PAGESPEED_KEY")
SCREENSHOT_ONE_KEY = os.getenv("SCREENSHOT_ONE_KEY")
SEMRUSH_KEY = os.getenv("SEMRUSH_KEY")

# Cost tracking constants (in cents)
PAGESPEED_COST = 0  # PageSpeed API is free
SCREENSHOT_ONE_COST = 5  # $0.05 per screenshot
SEMRUSH_SITE_AUDIT_COST = 50  # $0.50 per site audit


class TechStackAnalyzer:
    """Analyzes websites to identify technologies used."""

    def __init__(self):
        """Initialize the tech stack analyzer."""
        # Initialize Wappalyzer
        try:
            self.wappalyzer = Wappalyzer.latest()
        except Exception as e:
            logger.error(f"Error initializing Wappalyzer: {e}")
            self.wappalyzer = None

    def analyze_website(self, url: str) -> Tuple[Dict, Optional[str]]:
        """Analyze a website to identify technologies used.

        Args:
            url: Website URL.

        Returns:
            Tuple of (tech_stack_data, error_message).
            If successful, error_message is None.
            If failed, tech_stack_data is an empty dict.
        """
        if not url:
            return {}, "No URL provided"

        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            # Fetch the website
            response = requests.get(
                url,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )
            response.raise_for_status()

            # Parse the website
            webpage = WebPage(url, response.text, response.headers)

            # Analyze with Wappalyzer
            if self.wappalyzer:
                analysis = self.wappalyzer.analyze(webpage)
                tech_stack = analysis.technologies

                # Extract technology names and versions
                tech_data = {}
                for tech in tech_stack:
                    tech_data[tech.name] = {
                        "name": tech.name,
                        "categories": [cat.name for cat in tech.categories],
                        "version": tech.version,
                    }

                # Additional manual checks for common technologies
                html_content = response.text.lower()

                # Check for jQuery
                if "jquery" not in tech_data and "jquery" in html_content:
                    tech_data["jQuery"] = {
                        "name": "jQuery",
                        "categories": ["JavaScript Libraries"],
                        "version": None,
                    }
                    # Try to extract jQuery version
                    jquery_version_match = re.search(r"jquery[/-](\d+\.\d+\.\d+)", html_content)
                    if jquery_version_match:
                        tech_data["jQuery"]["version"] = jquery_version_match.group(1)

                # Check for Bootstrap
                if "Bootstrap" not in tech_data and "bootstrap" in html_content:
                    tech_data["Bootstrap"] = {
                        "name": "Bootstrap",
                        "categories": ["UI Frameworks"],
                        "version": None,
                    }

                # Check for outdated HTML/CSS
                if "<center>" in html_content or "<font" in html_content:
                    tech_data["Outdated HTML"] = {
                        "name": "Outdated HTML",
                        "categories": ["Markup"],
                        "version": None,
                    }

                # Check for responsive design
                if "viewport" in html_content and "width=device-width" in html_content:
                    tech_data["Responsive Design"] = {
                        "name": "Responsive Design",
                        "categories": ["Mobile"],
                        "version": None,
                    }

                return tech_data, None
            else:
                return {}, "Wappalyzer not initialized"

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching website {url}: {e}")
            return {}, f"Error fetching website: {str(e)}"

        except Exception as e:
            logger.error(f"Error analyzing website {url}: {e}")
            return {}, f"Error analyzing website: {str(e)}"


class PageSpeedAnalyzer:
    """Analyzes website performance using Google PageSpeed Insights API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the PageSpeed analyzer.

        Args:
            api_key: Google PageSpeed Insights API key.
        """
        self.api_key = api_key

    def analyze_website(self, url: str) -> Tuple[Dict, Optional[str]]:
        """Analyze a website's performance using PageSpeed Insights.

        Args:
            url: Website URL.

        Returns:
            Tuple of (performance_data, error_message).
            If successful, error_message is None.
            If failed, performance_data is an empty dict.
        """
        if not url:
            return {}, "No URL provided"

        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {
            "url": url,
            "strategy": "mobile",
            "category": ["performance", "accessibility", "best-practices", "seo"],
        }

        if self.api_key:
            params["key"] = self.api_key

        response_data, error = make_api_request(
            url=api_url,
            params=params,
            track_cost=True,
            service_name="pagespeed",
            operation="analyze",
            cost_cents=PAGESPEED_COST,
            tier=CURRENT_TIER,
        )

        if error:
            return {}, error

        try:
            # Extract Core Web Vitals and other metrics
            lighthouse_result = response_data.get("lighthouseResult", {})
            audits = lighthouse_result.get("audits", {})
            categories = lighthouse_result.get("categories", {})

            performance_data = {
                "performance_score": int(categories.get("performance", {}).get("score", 0) * 100),
                "accessibility_score": int(categories.get("accessibility", {}).get("score", 0) * 100),
                "best_practices_score": int(categories.get("best-practices", {}).get("score", 0) * 100),
                "seo_score": int(categories.get("seo", {}).get("score", 0) * 100),
                "first_contentful_paint": audits.get("first-contentful-paint", {}).get("numericValue"),
                "largest_contentful_paint": audits.get("largest-contentful-paint", {}).get("numericValue"),
                "cumulative_layout_shift": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                "total_blocking_time": audits.get("total-blocking-time", {}).get("numericValue"),
                "speed_index": audits.get("speed-index", {}).get("numericValue"),
                "time_to_interactive": audits.get("interactive", {}).get("numericValue"),
            }

            return performance_data, None

        except Exception as e:
            logger.error(f"Error parsing PageSpeed results for {url}: {e}")
            return {}, f"Error parsing PageSpeed results: {str(e)}"


class ScreenshotGenerator:
    """Generates screenshots of websites using ScreenshotOne API."""

    def __init__(self, api_key: str):
        """Initialize the screenshot generator.

        Args:
            api_key: ScreenshotOne API key.
        """
        self.api_key = api_key

    def capture_screenshot(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Capture a screenshot of a website.

        Args:
            url: Website URL.

        Returns:
            Tuple of (screenshot_url, error_message).
            If successful, error_message is None.
            If failed, screenshot_url is None.
        """
        if not url:
            return None, "No URL provided"

        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        api_url = "https://api.screenshotone.com/take"
        params = {
            "access_key": self.api_key,
            "url": url,
            "device_scale_factor": "1",
            "format": "png",
            "viewport_width": "1280",
            "viewport_height": "800",
            "full_page": "false",
            "timeout": str(DEFAULT_TIMEOUT * 1000),  # Convert to milliseconds
        }

        try:
            # Make the request directly to get the image
            response = requests.get(api_url, params=params, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            # Track the cost
            track_api_cost(
                service="screenshotone",
                operation="capture",
                cost_cents=SCREENSHOT_ONE_COST,
                tier=CURRENT_TIER,
            )

            # For a real implementation, we would upload this to Supabase Storage
            # For the prototype, we'll return a dummy URL
            screenshot_url = f"https://storage.supabase.co/mockups/{urlparse(url).netloc}.png"

            return screenshot_url, None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error capturing screenshot for {url}: {e}")
            return None, f"Error capturing screenshot: {str(e)}"

        except Exception as e:
            logger.error(f"Error processing screenshot for {url}: {e}")
            return None, f"Error processing screenshot: {str(e)}"


class SEMrushAnalyzer:
    """Analyzes websites using SEMrush Site Audit API."""

    def __init__(self, api_key: str):
        """Initialize the SEMrush analyzer.

        Args:
            api_key: SEMrush API key.
        """
        self.api_key = api_key

    def analyze_website(self, url: str) -> Tuple[Dict, Optional[str]]:
        """Analyze a website using SEMrush Site Audit.

        Args:
            url: Website URL.

        Returns:
            Tuple of (audit_data, error_message).
            If successful, error_message is None.
            If failed, audit_data is an empty dict.
        """
        if not url:
            return {}, "No URL provided"

        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Extract domain
        domain = urlparse(url).netloc

        api_url = "https://api.semrush.com/reports/v1/site-audit/summary.json"
        params = {
            "key": self.api_key,
            "url": domain,
            "limit": "10",  # Limit to top 10 issues
        }

        response_data, error = make_api_request(
            url=api_url,
            params=params,
            track_cost=True,
            service_name="semrush",
            operation="site_audit",
            cost_cents=SEMRUSH_SITE_AUDIT_COST,
            tier=CURRENT_TIER,
        )

        if error:
            return {}, error

        try:
            # Process the SEMrush data
            # For the prototype, we'll return a simplified version
            audit_data = {
                "domain": domain,
                "total_score": response_data.get("total_score", 0),
                "issues": response_data.get("issues", []),
                "crawled_pages": response_data.get("crawled_pages", 0),
                "errors": response_data.get("errors", 0),
                "warnings": response_data.get("warnings", 0),
                "notices": response_data.get("notices", 0),
            }

            return audit_data, None

        except Exception as e:
            logger.error(f"Error parsing SEMrush results for {url}: {e}")
            return {}, f"Error parsing SEMrush results: {str(e)}"


def get_businesses_to_enrich(limit: Optional[int] = None, business_id: Optional[int] = None) -> List[Dict]:
    """Get list of businesses to enrich.

    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.

    Returns:
        List of dictionaries containing business information.
    """
    try:
        with DatabaseConnection() as cursor:
            if business_id:
                cursor.execute(
                    """
                    SELECT b.* FROM businesses b
                    LEFT JOIN features f ON b.id = f.business_id
                    WHERE b.id = ? AND b.website IS NOT NULL AND f.id IS NULL
                    """,
                    (business_id,),
                )
            else:
                query = """
                    SELECT b.* FROM businesses b
                    LEFT JOIN features f ON b.id = f.business_id
                    WHERE b.website IS NOT NULL AND f.id IS NULL
                """
                if limit:
                    query += f" LIMIT {limit}"
                cursor.execute(query)

            businesses = cursor.fetchall()

        logger.info(f"Found {len(businesses)} businesses to enrich")
        return businesses

    except Exception as e:
        logger.error(f"Error getting businesses to enrich: {e}")
        return []


def save_features(
    business_id: int,
    tech_stack: Dict,
    page_speed: Dict,
    screenshot_url: Optional[str] = None,
    semrush_json: Optional[Dict] = None,
) -> bool:
    """Save features information to database.

    Args:
        business_id: Business ID.
        tech_stack: Tech stack information.
        page_speed: PageSpeed information.
        screenshot_url: URL to screenshot (Tier 2+).
        semrush_json: SEMrush Site Audit data (Tier 3 only).

    Returns:
        True if successful, False otherwise.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                INSERT INTO features 
                (business_id, tech_stack, page_speed, screenshot_url, semrush_json) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    json.dumps(tech_stack),
                    page_speed.get("performance_score", 0),
                    screenshot_url,
                    json.dumps(semrush_json) if semrush_json else None,
                ),
            )
        logger.info(f"Saved features for business ID {business_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving features for business ID {business_id}: {e}")
        return False


def enrich_business(business: Dict, tier: int = CURRENT_TIER) -> bool:
    """Enrich a business with tech stack and performance data.

    Args:
        business: Business information.
        tier: Tier level (1, 2, or 3).

    Returns:
        True if successful, False otherwise.
    """
    business_id = business["id"]
    website = business["website"]

    if not website:
        logger.warning(f"No website for business ID {business_id}")
        return False

    logger.info(f"Enriching business ID {business_id} with website {website} (Tier {tier})")

    # Initialize analyzers
    tech_analyzer = TechStackAnalyzer()
    pagespeed_analyzer = PageSpeedAnalyzer(PAGESPEED_API_KEY)

    # Analyze tech stack
    tech_stack, tech_error = tech_analyzer.analyze_website(website)
    if tech_error:
        logger.warning(f"Error analyzing tech stack for {website}: {tech_error}")

    # Analyze performance
    performance_data, perf_error = pagespeed_analyzer.analyze_website(website)
    if perf_error:
        logger.warning(f"Error analyzing performance for {website}: {perf_error}")

    # Tier-specific enrichment
    screenshot_url = None
    semrush_data = None

    # Tier 2+: Capture screenshot
    if tier >= 2 and SCREENSHOT_ONE_KEY:
        screenshot_generator = ScreenshotGenerator(SCREENSHOT_ONE_KEY)
        screenshot_url, screenshot_error = screenshot_generator.capture_screenshot(website)
        if screenshot_error:
            logger.warning(f"Error capturing screenshot for {website}: {screenshot_error}")

    # Tier 3: SEMrush Site Audit
    if tier >= 3 and SEMRUSH_KEY:
        semrush_analyzer = SEMrushAnalyzer(SEMRUSH_KEY)
        semrush_data, semrush_error = semrush_analyzer.analyze_website(website)
        if semrush_error:
            logger.warning(f"Error analyzing with SEMrush for {website}: {semrush_error}")

    # Save features to database
    success = save_features(
        business_id=business_id,
        tech_stack=tech_stack,
        page_speed=performance_data,
        screenshot_url=screenshot_url,
        semrush_json=semrush_data,
    )

    return success


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Enrich business data with tech stack and performance metrics")
    parser.add_argument("--limit", type=int, help="Limit the number of businesses to process")
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], help="Override the tier level")
    args = parser.parse_args()

    # Get tier level
    tier = args.tier if args.tier is not None else CURRENT_TIER
    logger.info(f"Running enrichment with Tier {tier}")

    # Get businesses to enrich
    businesses = get_businesses_to_enrich(limit=args.limit, business_id=args.id)

    if not businesses:
        logger.warning("No businesses to enrich")
        return 0

    logger.info(f"Enriching {len(businesses)} businesses")

    # Process businesses
    success_count = 0
    error_count = 0

    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        # Submit tasks
        future_to_business = {executor.submit(enrich_business, business, tier): business for business in businesses}

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_business):
            business = future_to_business[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"Error enriching business ID {business['id']}: {e}")
                error_count += 1

    logger.info(f"Enrichment completed. Success: {success_count}, Errors: {error_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
