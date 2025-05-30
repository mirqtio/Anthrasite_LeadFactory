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
from typing import Any, Optional, Union

# Use dict instead of Dict for Python 3.9 compatibility
from leadfactory.config import load_config

# Import the unified logging system
from leadfactory.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

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
        get_verticals,
        load_yaml_config,
        make_api_request,
        mark_zip_done,
    )

    has_io_imports = True
except ImportError:
    # Dummy implementations only created if the import fails
    pass

# Define dummies only if needed
if not has_io_imports:

    def get_verticals() -> list[dict[Any, Any]]:
        return []

    def load_yaml_config(file_path: str) -> dict[Any, Any]:
        import yaml

        try:
            with open(file_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load YAML config from {file_path}: {e}")
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
        """Make an API request with retry logic and error handling."""
        import json

        import requests

        for attempt in range(max_retries):
            try:
                # Log the API request
                logger.info(f"Making {method} request to {url}")

                # Make the request
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout,
                )

                # Check for HTTP errors
                response.raise_for_status()

                # Parse JSON response
                return response.json(), None

            except requests.exceptions.Timeout:
                logger.error(
                    f"Request timeout for {url} (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None, "Request timeout"

            except requests.exceptions.ConnectionError:
                logger.error(
                    f"Connection error for {url} (attempt {attempt + 1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None, "Connection error"

            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
                return None, f"HTTP error {e.response.status_code}: {str(e)}"

            except requests.exceptions.JSONDecodeError:
                logger.error(f"Invalid JSON response from {url}")
                return None, "Invalid JSON response"

            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                return None, f"Unexpected error: {str(e)}"

        return None, f"Failed after {max_retries} attempts"

    def mark_zip_done(zip_code: str) -> bool:
        return True

    def get_active_zip_codes() -> list[dict[Any, Any]]:
        # For E2E testing, return a test ZIP code
        if os.getenv("E2E_MODE") == "true":
            return [{"zip_code": "10001", "city": "New York", "state": "NY"}]

        # For production testing or normal operation, query the database
        try:
            from leadfactory.utils.e2e_db_connector import db_connection

            with db_connection() as conn:
                cursor = conn.cursor()
                # Query zip_queue table with correct column names
                cursor.execute(
                    """
                    SELECT zip, city, state
                    FROM zip_queue
                    WHERE processed = false
                    ORDER BY created_at ASC
                    LIMIT 10
                """
                )
                rows = cursor.fetchall()

                # Convert to expected format with zip_code key
                zip_codes = []
                for zip_val, city, state in rows:
                    zip_codes.append(
                        {"zip_code": zip_val, "city": city, "state": state}
                    )

                logger.info(f"Found {len(zip_codes)} unprocessed ZIP codes")
                return zip_codes

        except Exception as e:
            logger.error(f"Failed to query ZIP codes from database: {e}")
            # Fallback for production test mode
            if os.getenv("PRODUCTION_TEST_MODE") == "true":
                logger.info("Using fallback ZIP code for production testing")
                return [{"zip_code": "10001", "city": "New York", "state": "NY"}]
            return []


# API constants
YELP_API_BASE_URL = "https://api.yelp.com/v3"
GOOGLE_PLACES_API_BASE_URL = "https://maps.googleapis.com/maps/api/place"
YELP_SEARCH_COST = 1  # Cost in cents per Yelp search
GOOGLE_SEARCH_COST = 1  # Cost in cents per Google search

# Configuration paths
VERTICALS_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "etc" / "verticals.yml"
)


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
            operation="search",
            cost_cents=GOOGLE_SEARCH_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return [], error
        return response_data.get("results", []), None

    def get_place_details(
        self,
        place_id: str,
        fields: str = "name,formatted_address,website,formatted_phone_number,address_components",
    ) -> tuple[Optional[dict], Optional[str]]:
        """Get detailed information about a place.
        Args:
            place_id: Google Place ID.
            fields: Comma-separated list of fields to return.
        Returns:
            tuple of (place_details, error_message).
            If successful, error_message is None.
            If failed, place_details is None.
        """
        url = f"{GOOGLE_PLACES_API_BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": fields,
            "key": self.api_key,
        }
        response_data, error = make_api_request(
            url=url,
            params=params,
            track_cost=True,
            service_name="google",
            operation="details",
            cost_cents=GOOGLE_SEARCH_COST,
            tier=int(os.getenv("TIER", "1")),
        )
        if error:
            return None, error
        return response_data.get("result", {}), None


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
    yelp_response_json: Optional[dict] = None,
    google_response_json: Optional[dict] = None,
) -> Optional[int]:
    """Save a business to the database with deduplication logic.

    Args:
        name: Business name
        address: Business address
        zip_code: ZIP code
        category: Business category/vertical
        website: Business website URL
        email: Business email
        phone: Business phone number
        source: Data source (yelp, google, manual)
        source_id: Source-specific ID for deduplication
        yelp_response_json: Yelp API response JSON
        google_response_json: Google Places API response JSON

    Returns:
        Business ID if saved successfully, None if failed
    """
    try:
        import json

        import psycopg2.extras

        from leadfactory.utils.e2e_db_connector import db_connection

        with db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Check for existing business using multiple criteria for deduplication
            existing_business_id = None

            # 1. Check by source_id if provided (exact match from same source)
            if source_id and source_id.strip():
                cursor.execute(
                    """
                    SELECT id, source, source_id FROM businesses
                    WHERE source_id = %s AND source = %s
                """,
                    (source_id.strip(), source),
                )

                result = cursor.fetchone()
                if result:
                    existing_business_id = result["id"]
                    logger.info(
                        f"Found existing business {existing_business_id} by source_id: {source_id} from {source}"
                    )
                    return existing_business_id

            # 2. Check by website (strong deduplication signal)
            if website and website.strip():
                cursor.execute(
                    """
                    SELECT id, source, source_id FROM businesses
                    WHERE website = %s AND website IS NOT NULL AND website != ''
                """,
                    (website.strip(),),
                )

                result = cursor.fetchone()
                if result:
                    existing_business_id = result["id"]
                    # Update source information and resolve conflicts
                    new_data = {
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "vertical": category,
                        "yelp_response_json": yelp_response_json,
                        "google_response_json": google_response_json,
                    }
                    _update_business_with_conflict_resolution(
                        cursor, existing_business_id, new_data, source, result["source"]
                    )
                    _update_business_source(
                        cursor,
                        existing_business_id,
                        source,
                        source_id,
                        result["source"],
                        yelp_response_json,
                        google_response_json,
                    )
                    conn.commit()
                    logger.info(
                        f"Found existing business {existing_business_id} by website: {website} (merged source: {source})"
                    )
                    return existing_business_id

            # 3. Check by phone number (good deduplication signal)
            if phone and phone.strip():
                cursor.execute(
                    """
                    SELECT id, source, source_id FROM businesses
                    WHERE phone = %s AND phone IS NOT NULL AND phone != ''
                """,
                    (phone.strip(),),
                )

                result = cursor.fetchone()
                if result:
                    existing_business_id = result["id"]
                    # Update source information and resolve conflicts
                    new_data = {
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "vertical": category,
                        "yelp_response_json": yelp_response_json,
                        "google_response_json": google_response_json,
                    }
                    _update_business_with_conflict_resolution(
                        cursor, existing_business_id, new_data, source, result["source"]
                    )
                    _update_business_source(
                        cursor,
                        existing_business_id,
                        source,
                        source_id,
                        result["source"],
                        yelp_response_json,
                        google_response_json,
                    )
                    conn.commit()
                    logger.info(
                        f"Found existing business {existing_business_id} by phone: {phone} (merged source: {source})"
                    )
                    return existing_business_id

            # 4. Check by name + ZIP (weaker signal, but still useful)
            if name and zip_code:
                cursor.execute(
                    """
                    SELECT id, source, source_id FROM businesses
                    WHERE LOWER(name) = LOWER(%s) AND zip = %s
                """,
                    (name.strip(), zip_code.strip()),
                )

                result = cursor.fetchone()
                if result:
                    existing_business_id = result["id"]
                    # Update source information and resolve conflicts
                    new_data = {
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "vertical": category,
                        "yelp_response_json": yelp_response_json,
                        "google_response_json": google_response_json,
                    }
                    _update_business_with_conflict_resolution(
                        cursor, existing_business_id, new_data, source, result["source"]
                    )
                    _update_business_source(
                        cursor,
                        existing_business_id,
                        source,
                        source_id,
                        result["source"],
                        yelp_response_json,
                        google_response_json,
                    )
                    conn.commit()
                    logger.info(
                        f"Found existing business {existing_business_id} by name+ZIP: {name} in {zip_code} (merged source: {source})"
                    )
                    return existing_business_id

            # No existing business found, create new one
            insert_query = """
                INSERT INTO businesses (
                    name, address, city, state, zip, phone, email, website,
                    vertical_id, created_at, updated_at, status, processed,
                    source, source_id, yelp_response_json, google_response_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    (SELECT id FROM verticals WHERE name = %s LIMIT 1),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'pending', FALSE,
                    %s, %s, %s, %s
                ) RETURNING id
            """

            cursor.execute(
                insert_query,
                (
                    name,
                    address,
                    None,
                    None,
                    zip_code,
                    phone,
                    email,
                    website,
                    category.lower(),
                    source,
                    source_id,
                    json.dumps(yelp_response_json) if yelp_response_json else None,
                    json.dumps(google_response_json) if google_response_json else None,
                ),
            )

            result = cursor.fetchone()
            if result:
                business_id = result["id"]
                conn.commit()
                logger.info(
                    f"Created new business {business_id}: {name} in {zip_code} (source: {source}, source_id: {source_id})"
                )
                return business_id
            else:
                logger.error(f"Failed to create business: {name} in {zip_code}")
                return None

    except Exception as e:
        logger.error(f"Error saving business {name}: {str(e)}")
        return None


def _update_business_source(
    cursor,
    business_id: int,
    new_source: str,
    new_source_id: Optional[str],
    existing_source: str,
    yelp_response_json: Optional[dict] = None,
    google_response_json: Optional[dict] = None,
    business_data: Optional[dict] = None,
):
    """Update business source information when merging duplicates from different sources.

    Args:
        cursor: Database cursor
        business_id: ID of the existing business
        new_source: Source of the duplicate business being merged
        new_source_id: Source ID of the duplicate business being merged
        existing_source: Current source of the existing business
        yelp_response_json: Yelp API response JSON (if from Yelp)
        google_response_json: Google Places API response JSON (if from Google)
        business_data: Additional business data to update (if provided)
    """
    import json

    # If sources are different, combine them
    if existing_source != new_source:
        # Create combined source string (e.g., "yelp,google")
        sources = existing_source.split(",") if existing_source else []
        if new_source not in sources:
            sources.append(new_source)
            combined_source = ",".join(sorted(sources))

            # Prepare JSON update fields
            json_updates = []
            json_params = []

            if yelp_response_json and new_source == "yelp":
                json_updates.append("yelp_response_json = %s")
                json_params.append(json.dumps(yelp_response_json))

            if google_response_json and new_source == "google":
                json_updates.append("google_response_json = %s")
                json_params.append(json.dumps(google_response_json))

            # Build the update query
            update_query = (
                "UPDATE businesses SET source = %s, updated_at = CURRENT_TIMESTAMP"
            )
            params = [combined_source]

            if json_updates:
                update_query += ", " + ", ".join(json_updates)
                params.extend(json_params)

            if business_data:
                for field, value in business_data.items():
                    update_query += f", {field} = %s"
                    params.append(value)

            update_query += " WHERE id = %s"
            params.append(business_id)

            # Update the business record with combined source and JSON data
            cursor.execute(update_query, params)

            logger.info(
                f"Updated business {business_id} source from '{existing_source}' to '{combined_source}'"
            )


def _update_business_with_conflict_resolution(
    cursor, business_id: int, new_data: dict, source: str, existing_source: str
):
    """Update business record with smart conflict resolution for overlapping data.

    Args:
        cursor: Database cursor
        business_id: ID of existing business to update
        new_data: Dictionary with new data fields
        source: Source of new data (yelp, google, manual)
        existing_source: Existing source(s) of the business
    """
    # Get current business data
    cursor.execute(
        """
        SELECT name, address, phone, email, website, vertical_id
        FROM businesses WHERE id = %s
    """,
        (business_id,),
    )

    current = cursor.fetchone()
    if not current:
        return

    (
        current_name,
        current_address,
        current_phone,
        current_email,
        current_website,
        current_vertical_id,
    ) = current

    # Resolve conflicts for each field
    updates = {}

    # Name conflict resolution
    if new_data.get("name"):
        resolved_name = _resolve_field_conflict(
            current_name, new_data["name"], source, existing_source
        )
        if resolved_name != current_name:
            updates["name"] = resolved_name

    # Address conflict resolution
    if new_data.get("address"):
        resolved_address = _resolve_field_conflict(
            current_address, new_data["address"], source, existing_source
        )
        if resolved_address != current_address:
            updates["address"] = resolved_address

    # Phone conflict resolution
    if new_data.get("phone"):
        resolved_phone = _resolve_field_conflict(
            current_phone, new_data["phone"], source, existing_source
        )
        if resolved_phone != current_phone:
            updates["phone"] = resolved_phone

    # Email conflict resolution
    if new_data.get("email"):
        resolved_email = _resolve_field_conflict(
            current_email, new_data["email"], source, existing_source
        )
        if resolved_email != current_email:
            updates["email"] = resolved_email

    # Website conflict resolution
    if new_data.get("website"):
        resolved_website = _resolve_field_conflict(
            current_website, new_data["website"], source, existing_source
        )
        if resolved_website != current_website:
            updates["website"] = resolved_website

    # Vertical conflict resolution (convert category to vertical_id)
    if new_data.get("vertical"):
        # Get vertical_id for the new category
        cursor.execute(
            "SELECT id FROM verticals WHERE name = %s", (new_data["vertical"],)
        )
        new_vertical_result = cursor.fetchone()
        new_vertical_id = new_vertical_result[0] if new_vertical_result else None

        if new_vertical_id and new_vertical_id != current_vertical_id:
            # Get current vertical name for comparison
            cursor.execute(
                "SELECT name FROM verticals WHERE id = %s", (current_vertical_id,)
            )
            current_vertical_result = cursor.fetchone()
            current_vertical_name = (
                current_vertical_result[0] if current_vertical_result else None
            )

            resolved_vertical = _resolve_field_conflict(
                current_vertical_name, new_data["vertical"], source, existing_source
            )

            # Convert resolved vertical back to ID
            if resolved_vertical != current_vertical_name:
                cursor.execute(
                    "SELECT id FROM verticals WHERE name = %s", (resolved_vertical,)
                )
                resolved_vertical_result = cursor.fetchone()
                if resolved_vertical_result:
                    updates["vertical_id"] = resolved_vertical_result[0]

    # Apply updates if any
    if updates:
        set_clauses = []
        values = []

        for field, value in updates.items():
            set_clauses.append(f"{field} = %s")
            values.append(value)

        # Add updated_at
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values.append(business_id)

        update_query = f"""
            UPDATE businesses
            SET {', '.join(set_clauses)}
            WHERE id = %s
        """  # nosec B608

        cursor.execute(update_query, values)
        logger.info(
            f"Business {business_id}: Applied conflict resolution updates from {source}"
        )

    # Always update JSON responses (these don't conflict, they accumulate)
    json_updates = []
    json_values = []

    if new_data.get("yelp_response_json"):
        json_updates.append("yelp_response_json = %s")
        json_values.append(json.dumps(new_data["yelp_response_json"]))

    if new_data.get("google_response_json"):
        json_updates.append("google_response_json = %s")
        json_values.append(json.dumps(new_data["google_response_json"]))

    if json_updates:
        json_values.append(business_id)
        json_query = f"""
            UPDATE businesses
            SET {', '.join(json_updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """  # nosec B608
        cursor.execute(json_query, json_values)
        logger.info(f"Business {business_id}: Updated JSON responses from {source}")


def _resolve_field_conflict(
    existing_value: Optional[str],
    new_value: Optional[str],
    source: str,
    existing_source: str,
) -> Optional[str]:
    """Resolve conflicts between existing and new field values using source precedence and data quality.

    Args:
        existing_value: Current value in database
        new_value: New value from current source
        source: Source of new value
        existing_source: Existing source(s) of the business

    Returns:
        The value that should be stored (existing or new)
    """
    # If one value is None/empty and the other isn't, prefer the non-empty one
    if not existing_value and new_value:
        return new_value.strip()
    if not new_value and existing_value:
        return existing_value
    if not existing_value and not new_value:
        return None

    # If values are the same (case-insensitive), keep existing
    if existing_value.strip().lower() == new_value.strip().lower():
        return existing_value

    # Source precedence: manual > google > yelp
    # Manual entries are considered most authoritative
    source_priority = {"manual": 3, "google": 2, "yelp": 1}

    # Get highest priority from existing sources
    existing_sources = existing_source.split(",") if existing_source else []
    existing_priority = max(
        [source_priority.get(s.strip(), 0) for s in existing_sources], default=0
    )
    new_priority = source_priority.get(source, 0)

    # If new source has higher priority, use new value
    if new_priority > existing_priority:
        return new_value.strip()

    # If same priority, prefer more complete/longer value (often more informative)
    if new_priority == existing_priority:
        if len(new_value.strip()) > len(existing_value.strip()):
            return new_value.strip()

    # Default: keep existing value
    return existing_value


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

    # Get vertical name and search terms
    vertical_name = vertical.get("name", "")
    yelp_alias = vertical.get("yelp_alias", "")
    google_alias = vertical.get("google_alias", "")

    if not vertical_name:
        logger.error(f"Invalid vertical: {vertical}")
        return yelp_count, google_count

    # Log what we're doing
    logger.info(f"Scraping businesses for ZIP {zip_code}, vertical: {vertical_name}")

    # Get API keys from environment (reload in case they were loaded after import)
    yelp_api_key = os.getenv("YELP_KEY")
    google_api_key = os.getenv("GOOGLE_KEY")

    # Check if we have API keys
    if not yelp_api_key:
        logger.warning("No Yelp API key found in environment variables")
    if not google_api_key:
        logger.warning("No Google API key found in environment variables")

    # Create API clients
    yelp_api = YelpAPI(yelp_api_key) if yelp_api_key else None
    google_api = GooglePlacesAPI(google_api_key) if google_api_key else None

    # Get coordinates for the ZIP code (needed for Google Places API)
    coordinates = get_zip_coordinates(zip_code)
    if not coordinates and google_api:
        logger.warning(f"Could not get coordinates for ZIP {zip_code}")

    # Search Yelp using the yelp_alias
    if yelp_api and yelp_alias:
        logger.info(f"Searching Yelp for '{yelp_alias}' in ZIP {zip_code}")
        # Use smaller radius (2 miles) to get more precise results
        businesses, error = yelp_api.search_businesses(
            term=yelp_alias,
            location=zip_code,
            limit=limit,
            radius=3219,  # 2 miles in meters
        )
        if error:
            logger.error(f"Yelp API error: {error}")
        else:
            logger.info(
                f"Found {len(businesses)} businesses on Yelp (before ZIP filtering)"
            )
            # Filter to only businesses that are actually in the target ZIP code
            filtered_businesses = []
            for business in businesses:
                business_zip = business.get("location", {}).get("zip_code", "")
                if business_zip == zip_code:
                    filtered_businesses.append(business)
                else:
                    logger.debug(
                        f"Filtered out {business.get('name', 'Unknown')} - ZIP {business_zip} != {zip_code}"
                    )

            logger.info(
                f"After ZIP filtering: {len(filtered_businesses)} businesses match exact ZIP {zip_code}"
            )

            for business in filtered_businesses:
                # Process and save business
                business_id = process_yelp_business(business, vertical_name)
                if business_id:
                    yelp_count += 1

    # Search Google Places using the google_alias
    if google_api and coordinates and google_alias:
        # Google alias might have multiple types separated by comma
        google_types = [t.strip() for t in google_alias.split(",")]

        for google_type in google_types:
            logger.info(
                f"Searching Google Places for '{google_type}' in ZIP {zip_code}"
            )
            places, error = google_api.search_places(
                query=f"{google_type} in {zip_code}", location=coordinates
            )
            if error:
                logger.error(f"Google Places API error: {error}")
            else:
                logger.info(
                    f"Found {len(places)} places on Google (before ZIP filtering)"
                )
                # Filter to only places that are actually in the target ZIP code
                filtered_places = []
                for place in places:
                    # Get detailed place info to check ZIP code
                    place_details, detail_error = google_api.get_place_details(
                        place.get("place_id", "")
                    )
                    if detail_error:
                        logger.debug(
                            f"Could not get details for place {place.get('name', 'Unknown')}: {detail_error}"
                        )
                        continue

                    # Check if the place's ZIP code matches
                    place_zip = None
                    address_components = place_details.get("address_components", [])
                    for component in address_components:
                        if "postal_code" in component.get("types", []):
                            place_zip = component.get("short_name", "")
                            break

                    if place_zip == zip_code:
                        filtered_places.append(place)
                    else:
                        logger.debug(
                            f"Filtered out {place.get('name', 'Unknown')} - ZIP {place_zip} != {zip_code}"
                        )

                logger.info(
                    f"After ZIP filtering: {len(filtered_places)} places match exact ZIP {zip_code}"
                )

                for place in filtered_places:
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
            yelp_response_json=business,
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
            google_response_json=place,
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

    # Load environment variables for production test mode
    if os.getenv("PRODUCTION_TEST_MODE") == "true":
        from dotenv import load_dotenv

        env_file = Path(__file__).resolve().parent.parent.parent / ".env.prod_test"
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loading production test environment from {env_file}")
        else:
            logger.warning(f"Production test environment file not found: {env_file}")

    # Generate a batch ID for tracking this scraping run
    batch_id = f"scrape_{int(time.time())}"

    try:
        # Start the process with structured logging
        logger.info(
            "Starting scraping process",
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
                    "No verticals found in config",
                    extra={"config_path": VERTICALS_CONFIG_PATH, "outcome": "failure"},
                )
                return 1

            # If a specific vertical is specified, filter the list
            if args.vertical:
                verticals = [v for v in verticals if v.get("name") == args.vertical]
                if not verticals:
                    logger.error(
                        "Vertical not found",
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
                        "ZIP code not found or not active",
                        extra={"zip_code": args.zip, "outcome": "failure"},
                    )
                    return 1

            # Log what we're doing with structured context
            logger.info(
                "Processing ZIP codes and verticals",
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
                "Completed scraping process",
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
            f"Scraping process failed with unexpected error: {e}",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "batch_id": batch_id,
                "outcome": "failure",
            },
        )
        # Also print to stderr for debugging
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
