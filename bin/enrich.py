#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Lead Enrichment (02_enrich.py)
Analyzes business websites to extract tech stack and performance metrics.
Usage:
    python bin/02_enrich.py [--limit N] [--id BUSINESS_ID]
Options:
    --limit N        Limit the number of businesses to process (default: all)
    --id BUSINESS_ID Process only the specified business ID
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
from typing import Any, Optional

# Use lowercase dict for Python 3.9 compatibility
# Use lowercase versions for Python 3.9 compatibility
from urllib.parse import urlparse

# Third-party imports
import requests
import wappalyzer
from dotenv import load_dotenv

# Add project root to path to allow importing local 'utils' modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Local application/library specific imports with try-except for Python 3.9 compatibility during testing
try:
    from leadfactory.config.node_config import (
        NodeType,
        get_enabled_capabilities,
        is_api_available,
    )
    from leadfactory.cost.cost_tracking import track_api_cost
    from leadfactory.utils.e2e_db_connector import db_connection
    from leadfactory.utils.logging import get_logger
except ImportError:
    # Fallback for when module is imported in test context
    NodeType = None
    def is_api_available(x):
        return False
    def get_enabled_capabilities(x):
        return []
    def get_logger(x):
        return logging.getLogger(x)
    db_connection = None
    def track_api_cost(*args, **kwargs):
        return None

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)

# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
PAGESPEED_API_KEY = os.getenv("PAGESPEED_KEY")
SCREENSHOT_ONE_KEY = os.getenv("SCREENSHOT_ONE_KEY")
SEMRUSH_KEY = os.getenv("SEMRUSH_KEY")
# Cost tracking constants (in cents)
PAGESPEED_COST = 0  # PageSpeed API is free
SCREENSHOT_ONE_COST = 5  # $0.05 per screenshot
SEMRUSH_SITE_AUDIT_COST = 50  # $0.50 per site audit


def get_database_connection(db_path=None):
    """Return appropriate DatabaseConnection implementation based on environment."""
    if db_connection:
        return db_connection(db_path)
    else:
        # Fallback for testing
        class _TestingDatabaseConnection:
            def __init__(self, db_path=None):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def execute(self, query, params=None):
                return None

            def fetchall(self):
                return []

            def fetchone(self):
                return None

            def commit(self):
                pass

        return _TestingDatabaseConnection(db_path)


def make_request(
    url,
    method="GET",
    headers=None,
    params=None,
    data=None,
    timeout=30,
    max_retries=3,
    retry_delay=2,
    track_cost=True,
    service_name=None,
    operation=None,
    cost_cents=0,
    business_id=None,
):
    """Make API request in a way that works in all environments."""
    if track_cost and service_name and operation:
        track_api_cost(service_name, operation, cost_cents, business_id)

    # Simple request implementation for fallback
    try:
        if method.upper() == "GET":
            response = requests.get(
                url, headers=headers, params=params, timeout=timeout
            )
        elif method.upper() == "POST":
            response = requests.post(
                url, headers=headers, params=params, data=data, timeout=timeout
            )
        else:
            response = requests.request(
                method, url, headers=headers, params=params, data=data, timeout=timeout
            )

        response.raise_for_status()
        return response.json() if response.content else {}, None
    except Exception as e:
        return None, str(e)


def track_cost(service, operation, cost_cents, business_id=None):
    """Track API cost in a way that works in all environments."""
    if track_api_cost:
        track_api_cost(service, operation, cost_cents, business_id)


class TechStackAnalyzer:
    """Analyzes websites to identify technologies used."""

    def __init__(self):
        """Initialize the tech stack analyzer."""
        # Initialize the Wappalyzer instance - new API doesn't need initialization
        logger.info("Wappalyzer initialized successfully")

    def analyze_website(self, url: str) -> tuple[dict, Optional[str]]:
        """
        Analyze a website's technology stack using Wappalyzer.

        Args:
            url: The URL to analyze

        Returns:
            A tuple containing:
            - A dictionary with technology information
            - An optional error message
        """
        try:
            logger.info(f"Analyzing tech stack for: {url}")

            # Use the new wappalyzer.analyze() API
            analysis = wappalyzer.analyze(url)

            # For test compatibility, we need to return a set of technologies
            # But we'll also maintain the categorized dictionary for actual use
            tech_set: set[str] = set()
            tech_data: dict[str, dict[str, Any]] = {}

            # Process the analysis results
            if isinstance(analysis, dict):
                for tech_name, tech_info in analysis.items():
                    # Add to the set for test compatibility
                    tech_set.add(tech_name)
                    # Store detailed information
                    if isinstance(tech_info, dict):
                        tech_data[tech_name] = tech_info
                    else:
                        tech_data[tech_name] = {"name": tech_name}
            elif isinstance(analysis, list):
                # Handle case where analysis returns a list
                for tech in analysis:
                    if isinstance(tech, str):
                        tech_set.add(tech)
                        tech_data[tech] = {"name": tech}
                    elif isinstance(tech, dict) and "name" in tech:
                        tech_name = tech["name"]
                        tech_set.add(tech_name)
                        tech_data[tech_name] = tech
            # Convert tech_data to the expected return type (dict)
            return_data: dict[Any, Any] = {
                "technologies": list(tech_set),
                "categorized": tech_data,
            }
            return return_data, None
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch website {url}: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
        except Exception as e:
            error_msg = f"Error analyzing website {url}: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg


class PageSpeedAnalyzer:
    """Analyzes website performance using Google PageSpeed Insights API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the PageSpeed analyzer.
        Args:
            api_key: Google PageSpeed Insights API key.
        """
        self.api_key = api_key

    def analyze_website(self, url: str) -> tuple[dict, Optional[str]]:
        """Analyze a website's performance using PageSpeed Insights.
        Args:
            url: Website URL.
        Returns:
            tuple of (performance_data, error_message).
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
        response_data, error = make_request(
            url=api_url,
            params=params,
            track_cost=True,
            service_name="pagespeed",
            operation="analyze",
            cost_cents=PAGESPEED_COST,
            business_id=None,
        )
        if error:
            return {}, error
        try:
            # Extract Core Web Vitals and other metrics
            lighthouse_result = response_data.get("lighthouseResult", {})
            audits = lighthouse_result.get("audits", {})
            categories = lighthouse_result.get("categories", {})
            performance_data = {
                "performance_score": int(
                    categories.get("performance", {}).get("score", 0) * 100
                ),
                "accessibility_score": int(
                    categories.get("accessibility", {}).get("score", 0) * 100
                ),
                "best_practices_score": int(
                    categories.get("best-practices", {}).get("score", 0) * 100
                ),
                "seo_score": int(categories.get("seo", {}).get("score", 0) * 100),
                "first_contentful_paint": audits.get("first-contentful-paint", {}).get(
                    "numericValue"
                ),
                "largest_contentful_paint": audits.get(
                    "largest-contentful-paint", {}
                ).get("numericValue"),
                "cumulative_layout_shift": audits.get(
                    "cumulative-layout-shift", {}
                ).get("numericValue"),
                "total_blocking_time": audits.get("total-blocking-time", {}).get(
                    "numericValue"
                ),
                "speed_index": audits.get("speed-index", {}).get("numericValue"),
                "time_to_interactive": audits.get("interactive", {}).get(
                    "numericValue"
                ),
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

    def capture_screenshot(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Capture a screenshot of a website.
        Args:
            url: Website URL.
        Returns:
            tuple of (screenshot_url, error_message).
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
            track_cost(
                service="screenshotone",
                operation="capture",
                cost_cents=SCREENSHOT_ONE_COST,
                business_id=None,
            )
            # For a real implementation, we would upload this to Supabase Storage
            # For the prototype, we'll return a dummy URL
            screenshot_url = (
                f"https://storage.supabase.co/mockups/{urlparse(url).netloc}.png"
            )
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

    def analyze_website(self, url: str) -> tuple[dict, Optional[str]]:
        """Analyze a website using SEMrush Site Audit.
        Args:
            url: Website URL.
        Returns:
            tuple of (audit_data, error_message).
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
        response_data, error = make_request(
            url=api_url,
            params=params,
            track_cost=True,
            service_name="semrush",
            operation="site_audit",
            cost_cents=SEMRUSH_SITE_AUDIT_COST,
            business_id=None,
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


def get_businesses_to_enrich(
    limit: Optional[int] = None, business_id: Optional[int] = None
) -> list[dict]:
    """Get list of businesses to enrich.
    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
    Returns:
        list of dictionaries containing business information.
    """
    try:
        with get_database_connection() as cursor:
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
                # Use parameterized query to prevent SQL injection
                query = """
                    SELECT b.* FROM businesses b
                    LEFT JOIN features f ON b.id = f.business_id
                    WHERE b.website IS NOT NULL AND f.id IS NULL
                """
                if limit:
                    # Use parameterized query for the limit
                    query += " LIMIT ?"
                    cursor.execute(query, (limit,))
                else:
                    cursor.execute(query)
            businesses = cursor.fetchall()
        logger.info(f"Found {len(businesses)} businesses to enrich")
        return businesses
    except Exception as e:
        logger.error(f"Error getting businesses to enrich: {e}")
        return []


def save_features(
    business_id: int,
    tech_stack: dict,
    page_speed: dict,
    screenshot_url: Optional[str] = None,
    semrush_json: Optional[dict] = None,
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
        with get_database_connection() as cursor:
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


def mark_business_as_processed(business_id: int, skip_reason: str) -> bool:
    """Mark a business as processed without sending email.
    Args:
        business_id: Business ID.
        skip_reason: Reason for skipping (e.g., "modern_site").
    Returns:
        True if successful, False otherwise.
    """
    try:
        with get_database_connection() as cursor:
            # Update business status to indicate it was skipped
            cursor.execute(
                """
                UPDATE businesses
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("skipped_" + skip_reason, business_id),
            )
            # Also insert a minimal features record to prevent re-processing
            cursor.execute(
                """
                INSERT INTO features
                (business_id, tech_stack, page_speed, screenshot_url, semrush_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    business_id,
                    json.dumps({"skip_reason": skip_reason}),
                    90,  # High performance score that triggered the skip
                    None,
                    None,
                ),
            )
        logger.info(f"Marked business ID {business_id} as processed (reason: {skip_reason})")
        return True
    except Exception as e:
        logger.error(f"Error marking business ID {business_id} as processed: {e}")
        return False


def enrich_business(business: dict) -> bool:
    """Enrich a business with tech stack and performance data.
    Args:
        business: Business information.
    Returns:
        True if successful, False otherwise.
    """
    business_id = business["id"]
    website = business["website"]
    if not website:
        logger.warning(f"No website for business ID {business_id}")
        return False
    logger.info(f"Enriching business ID {business_id} with website {website}")
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

    # Task 41: Skip modern sites with high performance scores
    # Check if site has performance score >= 90 and is mobile responsive
    performance_score = performance_data.get("performance_score", 0)
    accessibility_score = performance_data.get("accessibility_score", 0)

    # Consider a site "modern" if it has high performance and good accessibility (proxy for mobile responsiveness)
    if performance_score >= 90 and accessibility_score >= 80:
        logger.info(
            f"Skipping modern site {website} (performance: {performance_score}, "
            f"accessibility: {accessibility_score}) - marking as processed"
        )
        # Mark business as processed without further enrichment or email
        mark_business_as_processed(business_id, skip_reason="modern_site")
        return True

    # Tier-specific enrichment
    screenshot_url = None
    semrush_data = None
    # Tier 2+: Capture screenshot
    if SCREENSHOT_ONE_KEY:
        screenshot_generator = ScreenshotGenerator(SCREENSHOT_ONE_KEY)
        screenshot_url, screenshot_error = screenshot_generator.capture_screenshot(
            website
        )
        if screenshot_error:
            logger.warning(
                f"Error capturing screenshot for {website}: {screenshot_error}"
            )
    # Tier 3: SEMrush Site Audit
    if SEMRUSH_KEY:
        semrush_analyzer = SEMrushAnalyzer(SEMRUSH_KEY)
        semrush_data, semrush_error = semrush_analyzer.analyze_website(website)
        if semrush_error:
            logger.warning(
                f"Error analyzing with SEMrush for {website}: {semrush_error}"
            )
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
    parser = argparse.ArgumentParser(
        description="Enrich business data with tech stack and performance metrics"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of businesses to process"
    )
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    args = parser.parse_args()
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
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_REQUESTS
    ) as executor:
        # Submit tasks
        future_to_business = {
            executor.submit(enrich_business, business): business
            for business in businesses
        }
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
    logger.info(
        f"Enrichment completed. Success: {success_count}, Errors: {error_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
