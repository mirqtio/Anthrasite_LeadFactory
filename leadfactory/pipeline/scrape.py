"""
Business scraping module for LeadFactory.

This module provides functionality to scrape business data from various sources.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Use dict instead of Dict for Python 3.9 compatibility
from leadfactory.config import load_config

# Import the unified logging system
from leadfactory.utils.logging import get_logger

# Import metrics
from leadfactory.utils.metrics import (
    LEADS_SCRAPED,
    PIPELINE_DURATION,
    PIPELINE_ERRORS,
    MetricsTimer,
    record_metric,
)

# Import utility functions with conditional imports for testing
has_io_imports = False
try:
    from leadfactory.utils.io import (
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
        zip_code: str,
        category: str,
        website: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        source: str = "manual",
        source_id: Optional[str] = None,
    ) -> Optional[int]:
        return 1


# We're now using the unified logging system from leadfactory.utils.logging:
# Set up logging
logger = get_logger(__name__)

# Load environment variables
load_config()

# Constants
VERTICALS_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "etc" / "verticals.yml"
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
            cost_cents=YELP_SEARCH_COST,  # Yelp details are also free
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
            "fields": "name,formatted_address,formatted_phone_number,website,address_components",
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
    # This is a simplified implementation with some example ZIP codes
    # In a real implementation, we would use a geocoding API or database
    zip_coords = {
        "10001": "40.7501,-73.9967",  # Manhattan, NY
        "90210": "34.0901,-118.4065",  # Beverly Hills, CA
        "60601": "41.8845,-87.6249",  # Chicago, IL
        "30301": "33.7483,-84.3905",  # Atlanta, GA
    }
    return zip_coords.get(zip_code)


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
    if not website or not website.startswith(("http://", "https://")):
        return None

    # Add http:// if missing
    if not website.startswith(("http://", "https://")):
        website = "http://" + website

    try:
        # Fetch the website content
        response_data, error = make_api_request(
            url=website,
            track_cost=False,  # No cost for fetching websites
        )

        if error:
            return None

        # If response_data is not a string (HTML content), return None
        if not isinstance(response_data, str):
            return None

        # Extract email addresses from the content
        # Simple regex for email extraction
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        emails = email_pattern.findall(response_data)

        # Return the first email address found
        if emails:
            return emails[0].lower()

        return None
    except Exception as e:
        logger.exception(f"Error extracting email from website: {str(e)}")
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
        # Extract business data
        name = business.get("name")
        if not name:
            return None

        # Get address components
        location = business.get("location", {})
        address_parts = location.get("display_address", [])
        address = " ".join(address_parts) if address_parts else ""
        zip_code = location.get("zip_code", "")
        if not zip_code:
            return None

        # Get other business details
        phone = business.get("display_phone", "")
        website = business.get("url", "")
        yelp_id = business.get("id", "")

        # Save to database
        business_id = save_business(
            name=name,
            address=address,
            zip_code=zip_code,
            category=category,
            phone=phone,
            website=website,
            source="yelp",
            source_id=yelp_id,
        )

        # Try to extract email from website if provided
        if business_id and website:
            email = extract_email_from_website(website, business_id)
            if email:
                # Update business with email
                with has_io_imports and EmailDBConnection() as conn:
                    conn.execute(
                        "UPDATE businesses SET email = ? WHERE id = ?",
                        [email, business_id],
                    )
                    conn.commit()

        return business_id
    except Exception as e:
        logger.exception(f"Error processing Yelp business: {str(e)}")
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
        # Extract place data
        name = place.get("name")
        if not name:
            return None

        # Get address components
        address = place.get("formatted_address", "")
        zip_code = ""

        # Extract ZIP code from address components
        if "address_components" in place:
            for component in place["address_components"]:
                if "postal_code" in component.get("types", []):
                    zip_code = component.get("long_name", "")
                    break

        # If we couldn't find a ZIP code, try to extract it from the formatted address
        if not zip_code and address:
            # Look for 5-digit number that might be a ZIP code
            zip_match = re.search(r"\b(\d{5})\b", address)
            if zip_match:
                zip_code = zip_match.group(1)

        if not zip_code:
            return None

        # Get place ID for details lookup
        place_id = place.get("place_id")
        if not place_id:
            return None

        # Get detailed information
        details, error = google_api.get_place_details(place_id)
        if error or not details:
            return None

        # Get other business details
        phone = details.get("formatted_phone_number", "")
        website = details.get("website", "")

        # Save to database
        business_id = save_business(
            name=name,
            address=address,
            zip_code=zip_code,
            category=category,
            phone=phone,
            website=website,
            source="google",
            source_id=place_id,
        )

        # Try to extract email from website if provided
        if business_id and website:
            email = extract_email_from_website(website, business_id)
            if email:
                # Update business with email
                with has_io_imports and EmailDBConnection() as conn:
                    conn.execute(
                        "UPDATE businesses SET email = ? WHERE id = ?",
                        [email, business_id],
                    )
                    conn.commit()

        return business_id
    except Exception as e:
        logger.exception(f"Error processing Google place: {str(e)}")
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
    # Count how many businesses we've scraped
    yelp_count = 0
    google_count = 0

    # Get vertical name and keywords
    vertical_name = vertical.get("name", "")
    search_terms = vertical.get("keywords", [])
    if not vertical_name or not search_terms:
        logger.error(f"Invalid vertical: {vertical}")
        return yelp_count, google_count

    # Log what we're doing
    logger.info(f"Scraping businesses for ZIP {zip_code}, vertical: {vertical_name}")

    # Check if we have API keys
    if not YELP_API_KEY:
        logger.warning("No Yelp API key found in environment variables")
    if not GOOGLE_API_KEY:
        logger.warning("No Google API key found in environment variables")

    # Create API clients
    yelp_api = YelpAPI(YELP_API_KEY) if YELP_API_KEY else None
    google_api = GooglePlacesAPI(GOOGLE_API_KEY) if GOOGLE_API_KEY else None

    # Get coordinates for the ZIP code (needed for Google Places API)
    coordinates = get_zip_coordinates(zip_code)
    if not coordinates and google_api:
        logger.warning(f"Could not get coordinates for ZIP {zip_code}")

    # Iterate through search terms
    for term in search_terms:
        logger.info(f"Searching for '{term}' in ZIP {zip_code}")

        # Search Yelp
        if yelp_api:
            logger.info(f"Searching Yelp for '{term}' in ZIP {zip_code}")
            businesses, error = yelp_api.search_businesses(
                term=term, location=zip_code, limit=limit
            )
            if error:
                logger.error(f"Yelp API error: {error}")
            else:
                logger.info(f"Found {len(businesses)} businesses on Yelp")
                for business in businesses:
                    # Process and save business
                    business_id = process_yelp_business(business, vertical_name)
                    if business_id:
                        yelp_count += 1

        # Search Google Places
        if google_api and coordinates:
            logger.info(f"Searching Google Places for '{term}' in ZIP {zip_code}")
            places, error = google_api.search_places(
                query=f"{term} in {zip_code}", location=coordinates
            )
            if error:
                logger.error(f"Google Places API error: {error}")
            else:
                logger.info(f"Found {len(places)} places on Google")
                for place in places:
                    # Process and save place
                    business_id = process_google_place(place, vertical_name, google_api)
                    if business_id:
                        google_count += 1

    # Log the results
    logger.info(
        f"Scraped {yelp_count + google_count} businesses for ZIP {zip_code}: "
        f"Yelp: {yelp_count}, Google: {google_count}"
    )

    # Mark ZIP code as done
    mark_zip_done(zip_code)

    return yelp_count, google_count


def main() -> int:
    """Main entry point for the scraping module."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape business data")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of businesses to fetch per API",
    )
    parser.add_argument("--zip", type=str, help="Process only the specified ZIP code")
    parser.add_argument(
        "--vertical", type=str, help="Process only the specified vertical"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )
    args = parser.parse_args()

    # Configure log level if specified
    if args.log_level:
        logger.setLevel(args.log_level)

    # Generate a batch ID for tracking this scraping run
    batch_id = f"scrape_{int(time.time())}"

    try:
        # Start the process with structured logging
        logger.info(
            f"Starting scraping process",
            extra={
                "cli_args": vars(args),
                "operation": "cli_scrape",
                "batch_id": batch_id,
            },
        )

        # Use MetricsTimer for the entire scraping batch process
        with MetricsTimer(PIPELINE_DURATION, stage="scrape_batch"):
            # Load verticals configuration
            verticals = load_yaml_config(VERTICALS_CONFIG_PATH).get("verticals", [])
            if not verticals:
                logger.error(
                    f"No verticals found in config",
                    extra={"config_path": VERTICALS_CONFIG_PATH, "outcome": "failure"},
                )
                return 1

            # If a specific vertical is specified, filter the list
            if args.vertical:
                verticals = [v for v in verticals if v.get("name") == args.vertical]
                if not verticals:
                    logger.error(
                        f"Vertical not found",
                        extra={"vertical": args.vertical, "outcome": "failure"},
                    )
                    return 1

            # Get active ZIP codes to process
            zip_codes = get_active_zip_codes()
            if not zip_codes:
                logger.error(
                    "No active ZIP codes found in database",
                    extra={"outcome": "failure"},
                )
                return 1

            # If a specific ZIP code is specified, filter the list
            if args.zip:
                zip_codes = [z for z in zip_codes if z.get("zip_code") == args.zip]
                if not zip_codes:
                    logger.error(
                        f"ZIP code not found or not active",
                        extra={"zip_code": args.zip, "outcome": "failure"},
                    )
                    return 1

            # Log what we're doing with structured context
            logger.info(
                f"Processing ZIP codes and verticals",
                extra={
                    "zip_count": len(zip_codes),
                    "vertical_count": len(verticals),
                    "batch_id": batch_id,
                },
            )

            # Process each ZIP code and vertical combination
            total_yelp = 0
            total_google = 0
            processed_combinations = 0

            for zip_info in zip_codes:
                zip_code = zip_info.get("zip_code")
                if not zip_code:
                    continue

                for vertical in verticals:
                    vertical_name = vertical.get("name", "unknown")

                    # Log the current combination we're processing
                    logger.info(
                        f"Processing ZIP code {zip_code} for vertical {vertical_name}",
                        extra={
                            "zip_code": zip_code,
                            "vertical": vertical_name,
                            "limit": args.limit,
                            "operation": "scrape_zip_vertical",
                            "batch_id": batch_id,
                        },
                    )

                    # Scrape businesses for this ZIP code and vertical
                    yelp_count, google_count = scrape_businesses(
                        zip_code, vertical, args.limit
                    )
                    total_yelp += yelp_count
                    total_google += google_count
                    processed_combinations += 1

                    # Log the results for this combination
                    logger.info(
                        f"Completed scraping for ZIP {zip_code} and vertical {vertical_name}",
                        extra={
                            "zip_code": zip_code,
                            "vertical": vertical_name,
                            "yelp_count": yelp_count,
                            "google_count": google_count,
                            "total_count": yelp_count + google_count,
                            "batch_id": batch_id,
                        },
                    )

            # Log the final results with structured data
            logger.info(
                f"Completed scraping process",
                extra={
                    "total_businesses": total_yelp + total_google,
                    "yelp_count": total_yelp,
                    "google_count": total_google,
                    "processed_combinations": processed_combinations,
                    "zip_count": len(zip_codes),
                    "vertical_count": len(verticals),
                    "batch_id": batch_id,
                    "outcome": "success",
                },
            )

        return 0

    except Exception as e:
        # Log any unexpected errors
        logger.error(
            f"Scraping process failed with unexpected error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "batch_id": batch_id,
                "outcome": "failure",
            },
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
