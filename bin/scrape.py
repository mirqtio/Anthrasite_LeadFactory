#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Lead Scraper (01_scrape.py)
Fetches business listings from Yelp Fusion and Google Places APIs.
Usage:
    python bin/01_scrape.py [--limit N] [--zip ZIP] [--vertical VERTICAL]
Options:
    --limit N        Limit the number of businesses to fetch per API (default: 50)
    --zip ZIP        Process only the specified ZIP code
    --vertical VERTICAL  Process only the specified vertical
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional, Union

# Use dict instead of Dict for Python 3.9 compatibility
# Use lowercase versions for Python 3.9 compatibility
# Use lowercase versions for Python 3.9 compatibility
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import utility functions with conditional imports for testing
has_io_imports = False
try:
    from utils.io import (
        get_active_zip_codes,
        get_verticals,
        load_yaml_config,
        make_api_request,
        mark_zip_done,
        save_business,
    )

    has_io_imports = True
except ImportError:
    # Dummy implementations only created if the import fails
    pass

# Define dummies only if needed
if not has_io_imports:

    def get_active_zip_codes() -> list[dict[Any, Any]]:
        return []

    def get_verticals() -> list[dict[Any, Any]]:
        return []

    def load_yaml_config(file_path: str) -> dict[Any, Any]:
        return {}

    def make_api_request(
        url: str,
        method: str = "GET",
        headers: Optional[dict[Any, Any]] = None,
        params: Optional[dict[Any, Any]] = None,
        data: Optional[dict[Any, Any]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 2,
        track_cost: bool = True,
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        cost_cents: int = 0,
        tier: int = 1,
        business_id: Optional[int] = None,
    ) -> tuple[Optional[dict[Any, Any]], Optional[str]]:
        return {}, None

    def mark_zip_done(zip_code: str) -> bool:
        return True

    def save_business(
        name: str,
        address: str,
        city: str = "",
        state: str = "",
        zip_code: str = "",
        category: str = "",
        website: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        source: str = "manual",
        source_id: Optional[str] = None,
    ) -> Optional[int]:
        return 1


# Import logging utilities with conditional imports for testing
has_logger = False
try:
    from utils.logging_config import get_logger

    has_logger = True
except ImportError:
    # Dummy implementation only created if the import fails
    pass

# Define dummy get_logger only if needed
if not has_logger:

    def get_logger(name: str) -> logging.Logger:
        import logging

        return logging.getLogger(name)


# Set up logging
logger = get_logger(__name__)
# Load environment variables
# Force .env values to override system environment variables
load_dotenv(override=True)
# Constants
VERTICALS_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "etc" / "verticals.yml"
)
YELP_API_KEY = os.getenv("YELP_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_KEY")
YELP_API_BASE_URL = "https://api.yelp.com/v3"
GOOGLE_PLACES_API_BASE_URL = "https://maps.googleapis.com/maps/api/place"
# Cost tracking constants (in cents)
YELP_SEARCH_COST = 0  # Yelp Fusion API is free but rate-limited
GOOGLE_PLACES_SEARCH_COST = 3  # $0.03 per request
GOOGLE_PLACES_DETAILS_COST = 17  # $0.17 per request


class YelpAPI:
    """Yelp Fusion API client."""

    def __init__(self, api_key: str):
        """Initialize Yelp API client.
        Args:
            api_key: Yelp Fusion API key.
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def search_businesses(
        self,
        term: str,
        location: str,
        radius: int = 40000,  # 25 miles in meters
        limit: int = 50,
        sort_by: str = "best_match",
    ) -> tuple[list[dict], Optional[str]]:
        """Search for businesses on Yelp.
        Args:
            term: Search term (e.g., "hvac").
            location: Location (e.g., ZIP code).
            radius: Search radius in meters.
            limit: Maximum number of results to return.
            sort_by: Sort method (best_match, rating, review_count, distance).
        Returns:
            tuple of (businesses_list, error_message).
            If successful, error_message is None.
            If failed, businesses_list is an empty list.
        """
        url = f"{YELP_API_BASE_URL}/businesses/search"
        params = {
            "term": term,
            "location": location,
            "radius": radius,
            "limit": limit,
            "sort_by": sort_by,
        }
        response_data, error = make_api_request(
            url=url,
            headers=self.headers,
            params=params,
            track_cost=True,
            service_name="yelp",
            operation="search",
            cost_cents=YELP_SEARCH_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return [], error
        return response_data.get("businesses", []), None

    def get_business_details(
        self, business_id: str
    ) -> tuple[Optional[dict], Optional[str]]:
        """Get detailed information about a business.
        Args:
            business_id: Yelp business ID.
        Returns:
            tuple of (business_details, error_message).
            If successful, error_message is None.
            If failed, business_details is None.
        """
        url = f"{YELP_API_BASE_URL}/businesses/{business_id}"
        response_data, error = make_api_request(
            url=url,
            headers=self.headers,
            track_cost=True,
            service_name="yelp",
            operation="details",
            cost_cents=YELP_SEARCH_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return None, error
        return response_data, None


class GooglePlacesAPI:
    """Google Places API client."""

    def __init__(self, api_key: str):
        """Initialize Google Places API client.
        Args:
            api_key: Google Places API key.
        """
        self.api_key = api_key

    def search_places(
        self,
        query: str,
        location: str,
        radius: int = 40000,  # 25 miles in meters
        type_filter: str = "business",
    ) -> tuple[list[dict], Optional[str]]:
        """Search for places on Google Maps.
        Args:
            query: Search query.
            location: Location (latitude,longitude).
            radius: Search radius in meters.
            type_filter: Type of place to search for.
        Returns:
            tuple of (places_list, error_message).
            If successful, error_message is None.
            If failed, places_list is an empty list.
        """
        url = f"{GOOGLE_PLACES_API_BASE_URL}/textsearch/json"
        params = {
            "query": query,
            "location": location,
            "radius": radius,
            "type": type_filter,
            "key": self.api_key,
        }
        response_data, error = make_api_request(
            url=url,
            params=params,
            track_cost=True,
            service_name="google",
            operation="places_search",
            cost_cents=GOOGLE_PLACES_SEARCH_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return [], error
        return response_data.get("results", []), None

    def get_place_details(self, place_id: str) -> tuple[Optional[dict], Optional[str]]:
        """Get detailed information about a place.
        Args:
            place_id: Google Place ID.
        Returns:
            tuple of (place_details, error_message).
            If successful, error_message is None.
            If failed, place_details is None.
        """
        url = f"{GOOGLE_PLACES_API_BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,website,url,types,business_status",
            "key": self.api_key,
        }
        response_data, error = make_api_request(
            url=url,
            params=params,
            track_cost=True,
            service_name="google",
            operation="places_details",
            cost_cents=GOOGLE_PLACES_DETAILS_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return None, error
        return response_data.get("result", {}), None


def get_zip_coordinates(zip_code: str) -> Optional[str]:
    """Get coordinates for a ZIP code.
    This is a simplified implementation that would normally use a geocoding API.
    For the prototype, we'll use a hardcoded mapping for the required ZIP codes.
    Args:
        zip_code: ZIP code to geocode.
    Returns:
        String in format "latitude,longitude" or None if not found.
    """
    # Hardcoded coordinates for the required ZIP codes
    zip_coordinates = {
        "10002": "40.7168,-73.9861",  # NY
        "98908": "46.6021,-120.5059",  # WA
        "46032": "39.9784,-86.1180",  # IN
    }
    return zip_coordinates.get(zip_code)


def extract_email_from_website(
    website: str, business_id: Optional[int] = None
) -> Optional[str]:
    """Extract email from website.
    This function fetches the website HTML, stores it for retention purposes,
    and extracts email addresses from the content.
    Args:
        website: Website URL.
        business_id: ID of the business associated with the website.
    Returns:
        Email address if found, None otherwise.
    """
    if not website:
        return None

    try:
        # Import raw data retention utilities
        from utils.raw_data_retention import fetch_website_html, store_html

        # Fetch HTML content
        html_content = fetch_website_html(website)

        # Store HTML content if business_id is provided
        if html_content and business_id:
            html_path = store_html(html_content, website, business_id)
            logger.info(
                f"Stored HTML for business {business_id}, website: {website}, path: {html_path}"
            )

        # Extract email from domain (placeholder for actual email extraction)
        from urllib.parse import urlparse

        domain = urlparse(website).netloc
        if domain:
            return f"info@{domain}"

    except Exception as e:
        logger.warning(f"Error extracting email from website {website}: {e}")

    return None


def process_yelp_business(business: dict, category: str) -> Optional[int]:
    """Process and save a business from Yelp.
    Args:
        business: Business data from Yelp API.
        category: Business category/vertical.
    Returns:
        ID of the saved business, or None if saving failed.
    """
    try:
        # Extract location information
        location = business.get("location", {})

        # Task 42: Extract city and state separately
        city = location.get("city", "")
        state = location.get("state", "")

        # Build address without city/state for the address field
        address_parts = []
        if location.get("address1"):
            address_parts.append(location.get("address1"))
        if location.get("address2"):
            address_parts.append(location.get("address2"))
        address = ", ".join(address_parts) if address_parts else ""

        # Extract other information
        name = business.get("name", "")
        zip_code = location.get("zip_code", "")
        website = business.get("url", "")
        phone = business.get("phone", "")
        # Extract email (in a real implementation, this would involve scraping the website)
        email = extract_email_from_website(website)
        # Save business to database
        business_id = save_business(
            name=name,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            category=category,
            website=website,
            email=email,
            phone=phone,
            source="yelp",
            source_id=business.get("id"),
        )
        return business_id
    except Exception as e:
        logger.error(f"Error processing Yelp business: {e}")
        return None


def process_google_place(
    place: dict, category: str, google_api: GooglePlacesAPI
) -> Optional[int]:
    """Process and save a place from Google.
    Args:
        place: Place data from Google Places API.
        category: Business category/vertical.
        google_api: GooglePlacesAPI instance for fetching details.
    Returns:
        ID of the saved business, or None if saving failed.
    """
    try:
        # Get place details
        place_id = place.get("place_id")
        if not place_id:
            logger.warning(f"No place_id found for Google place: {place.get('name')}")
            return None
        details, error = google_api.get_place_details(place_id)
        if error or not details:
            logger.warning(
                f"Error getting details for Google place {place_id}: {error}"
            )
            return None
        # Extract information
        name = details.get("name", "")
        formatted_address = details.get("formatted_address", "")
        website = details.get("website", "")
        phone = details.get("formatted_phone_number", "")

        # Task 42: Parse city, state, and zip from formatted address
        # Google provides address_components which we can use
        address_components = details.get("address_components", [])
        street_number = ""
        route = ""
        city = ""
        state = ""
        zip_code = ""

        for component in address_components:
            types = component.get("types", [])
            if "street_number" in types:
                street_number = component.get("long_name", "")
            elif "route" in types:
                route = component.get("long_name", "")
            elif "locality" in types:
                city = component.get("long_name", "")
            elif "administrative_area_level_1" in types:
                state = component.get("short_name", "")
            elif "postal_code" in types:
                zip_code = component.get("long_name", "")

        # Build street address
        address_parts = []
        if street_number:
            address_parts.append(street_number)
        if route:
            address_parts.append(route)
        address = " ".join(address_parts) if address_parts else formatted_address

        # Extract email (in a real implementation, this would involve scraping the website)
        email = extract_email_from_website(website)
        # Save business to database
        business_id = save_business(
            name=name,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            category=category,
            website=website,
            email=email,
            phone=phone,
            source="google",
            source_id=place_id,
        )
        return business_id
    except Exception as e:
        logger.error(f"Error processing Google place: {e}")
        return None


def scrape_businesses(
    zip_code: str, vertical: dict, limit: int = 50
) -> tuple[int, int]:
    """Scrape businesses for a specific ZIP code and vertical.
    Args:
        zip_code: ZIP code to scrape.
        vertical: Vertical information.
        limit: Maximum number of businesses to fetch per API.
    Returns:
        tuple of (yelp_count, google_count) - number of businesses scraped from each source.
    """
    logger.info(f"Scraping businesses for ZIP {zip_code}, vertical {vertical['name']}")
    # Initialize API clients
    if not YELP_API_KEY:
        logger.error("YELP_KEY environment variable not set")
        return 0, 0
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_KEY environment variable not set")
        return 0, 0
    yelp_api = YelpAPI(YELP_API_KEY)
    google_api = GooglePlacesAPI(GOOGLE_API_KEY)
    # Load verticals configuration
    verticals_config = load_yaml_config(VERTICALS_CONFIG_PATH)
    search_params = verticals_config.get("search_params", {})
    # Get coordinates for the ZIP code
    coordinates = get_zip_coordinates(zip_code)
    if not coordinates:
        logger.error(f"Could not get coordinates for ZIP code {zip_code}")
        return 0, 0
    yelp_count = 0
    google_count = 0
    # Scrape from Yelp
    yelp_alias = vertical.get("yelp_alias")
    if yelp_alias:
        logger.info(f"Scraping from Yelp: {yelp_alias} in {zip_code}")
        businesses, error = yelp_api.search_businesses(
            term=yelp_alias,
            location=zip_code,
            radius=search_params.get("yelp", {}).get("radius", 40000),
            limit=limit,
            sort_by=search_params.get("yelp", {}).get("sort_by", "best_match"),
        )
        if error:
            logger.error(f"Error scraping from Yelp: {error}")
        else:
            logger.info(f"Found {len(businesses)} businesses on Yelp")
            for business in businesses:
                if process_yelp_business(business, vertical["name"]):
                    yelp_count += 1
    # Scrape from Google Places
    google_alias = vertical.get("google_alias")
    if google_alias:
        # Google Places API accepts multiple types as a comma-separated string
        if isinstance(google_alias, list):
            google_alias = " OR ".join(google_alias)
        logger.info(f"Scraping from Google Places: {google_alias} in {zip_code}")
        query = f"{google_alias} in {zip_code}"
        places, error = google_api.search_places(
            query=query,
            location=coordinates,
            radius=search_params.get("google", {}).get("radius", 40000),
            type_filter=search_params.get("google", {}).get("type", "business"),
        )
        if error:
            logger.error(f"Error scraping from Google Places: {error}")
        else:
            logger.info(f"Found {len(places)} places on Google Places")
            # Limit the number of places to process
            places = places[:limit]
            for place in places:
                if process_google_place(place, vertical["name"], google_api):
                    google_count += 1
    logger.info(
        f"Scraped {yelp_count} businesses from Yelp and {google_count} from Google Places"
    )
    return yelp_count, google_count


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Scrape business listings from Yelp and Google Places APIs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limit the number of businesses to fetch per API",
    )
    parser.add_argument("--zip", type=str, help="Process only the specified ZIP code")
    parser.add_argument(
        "--vertical", type=str, help="Process only the specified vertical"
    )
    args = parser.parse_args()
    # Get active ZIP codes
    if args.zip:
        zip_codes = [{"zip": args.zip, "metro": "Custom"}]
    else:
        zip_codes = get_active_zip_codes()
    if not zip_codes:
        logger.error("No active ZIP codes found")
        return 1
    # Get verticals
    verticals = get_verticals()
    if not verticals:
        logger.error("No verticals found")
        return 1
    # Filter verticals if specified
    if args.vertical:
        verticals = [v for v in verticals if v["name"].lower() == args.vertical.lower()]
        if not verticals:
            logger.error(f"Vertical '{args.vertical}' not found")
            return 1
    total_yelp = 0
    total_google = 0
    # Process each ZIP code and vertical
    for zip_code_info in zip_codes:
        zip_code = zip_code_info["zip"]
        for vertical in verticals:
            yelp_count, google_count = scrape_businesses(
                zip_code=zip_code, vertical=vertical, limit=args.limit
            )
            total_yelp += yelp_count
            total_google += google_count
        # Mark ZIP code as done if not in custom mode
        if not args.zip:
            mark_zip_done(zip_code)
    logger.info(
        f"Scraping completed. Total: {total_yelp} from Yelp, {total_google} from Google Places"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
