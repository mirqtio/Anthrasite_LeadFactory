"""
I/O utility functions for the Anthrasite Lead-Factory pipeline.
Handles database connections, logging, and API requests.
"""

import os
import sqlite3
import time
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from dotenv import load_dotenv

# Import logging configuration
from .logging_config import get_logger

# Set up logging
logger = get_logger(__name__)
# Load environment variables
load_dotenv()
# Constants
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "leadfactory.db")
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))


class DatabaseConnection:
    """Context manager for database connections."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.
        Args:
            db_path: Path to SQLite database file. If None, uses default path.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish database connection and return cursor."""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Configure row factory to return dictionaries
        self.conn.row_factory = lambda c, r: {col[0]: r[idx] for idx, col in enumerate(c.description)}
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if exc_type is not None:
            # An exception occurred, rollback
            if self.conn:
                self.conn.rollback()
            logger.error(f"Database error: {exc_val}")
        else:
            # No exception, commit changes
            if self.conn:
                self.conn.commit()
        # Close cursor and connection
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def load_yaml_config(file_path: str) -> Dict:
    """Load YAML configuration file.
    Args:
        file_path: Path to YAML file.
    Returns:
        Dictionary containing configuration.
    """
    try:
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)
        logger.debug(f"Loaded configuration from {file_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading YAML config from {file_path}: {e}")
        raise


def load_csv_data(file_path: str) -> List[Dict]:
    """Load data from CSV file.
    Args:
        file_path: Path to CSV file.
    Returns:
        List of dictionaries, each representing a row in the CSV.
    """
    import csv

    try:
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            data = list(reader)
        logger.debug(f"Loaded {len(data)} rows from {file_path}")
        return data
    except Exception as e:
        logger.error(f"Error loading CSV data from {file_path}: {e}")
        raise


def make_api_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict] = None,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
    retry_delay: int = 2,
    track_cost: bool = True,
    service_name: Optional[str] = None,
    operation: Optional[str] = None,
    cost_cents: int = 0,
    tier: int = 1,
    business_id: Optional[int] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Make an API request with retry logic and cost tracking.
    Args:
        url: API endpoint URL.
        method: HTTP method (GET, POST, etc.).
        headers: HTTP headers.
        params: URL parameters.
        data: Request body for POST/PUT requests.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay between retries in seconds.
        track_cost: Whether to track the cost of this API call.
        service_name: Name of the API service (for cost tracking).
        operation: Type of operation (for cost tracking).
        cost_cents: Cost of the API call in cents.
        tier: Tier level (1, 2, or 3).
        business_id: ID of the business associated with this API call.
    Returns:
        Tuple of (response_data, error_message).
        If successful, error_message is None.
        If failed, response_data is None.
    """
    retries = 0
    while retries <= max_retries:
        try:
            logger.debug(f"Making {method} request to {url}")
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data if method.upper() in ["POST", "PUT", "PATCH"] else None,
                timeout=timeout,
            )
            # Check if response is successful
            response.raise_for_status()
            # Track cost if requested
            if track_cost and service_name and operation:
                track_api_cost(service_name, operation, cost_cents, tier, business_id)
            # Parse and return response data
            try:
                response_data = response.json()
            except ValueError:
                # Response is not JSON
                response_data = {"text": response.text}
            return response_data, None
        except requests.exceptions.RequestException as e:
            retries += 1
            if retries <= max_retries:
                # Exponential backoff
                sleep_time = retry_delay * (2 ** (retries - 1))
                logger.warning(f"API request failed: {e}. Retrying in {sleep_time}s " f"({retries}/{max_retries})")
                time.sleep(sleep_time)
            else:
                logger.error(f"API request failed after {max_retries} retries: {e}")
                return None, str(e)


def track_api_cost(
    service: str,
    operation: str,
    cost_cents: int,
    tier: int = 1,
    business_id: Optional[int] = None,
) -> None:
    """Track the cost of an API call.
    Args:
        service: Name of the API service.
        operation: Type of operation.
        cost_cents: Cost of the API call in cents.
        tier: Tier level (1, 2, or 3).
        business_id: ID of the business associated with this API call.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                INSERT INTO cost_tracking
                (service, operation, cost_cents, tier, business_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (service, operation, cost_cents, tier, business_id),
            )
        logger.debug(f"Tracked cost: {service} {operation}, {cost_cents} cents, tier {tier}")
    except Exception as e:
        logger.error(f"Error tracking API cost: {e}")


def get_active_zip_codes() -> List[Dict]:
    """Get list of active zip codes to process.
    Returns:
        List of dictionaries containing zip code information.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute("SELECT * FROM zip_queue WHERE done = 0")
            zip_codes = cursor.fetchall()
        logger.info(f"Found {len(zip_codes)} active zip codes to process")
        return zip_codes
    except Exception as e:
        logger.error(f"Error getting active zip codes: {e}")
        return []


def get_verticals() -> List[Dict]:
    """Get list of verticals to process.
    Returns:
        List of dictionaries containing vertical information.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute("SELECT * FROM verticals")
            verticals = cursor.fetchall()
        logger.info(f"Found {len(verticals)} verticals to process")
        return verticals
    except Exception as e:
        logger.error(f"Error getting verticals: {e}")
        return []


def save_business(
    name: str,
    address: str,
    zip_code: str,
    category: str,
    website: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    source: str = "yelp",
    source_id: Optional[str] = None,
) -> Optional[int]:
    """Save business information to database.
    Args:
        name: Business name.
        address: Business address.
        zip_code: ZIP code.
        category: Business category/vertical.
        website: Business website URL.
        email: Business email address.
        phone: Business phone number.
        source: Source of the data (yelp or google).
        source_id: ID of the business in the source platform.
    Returns:
        ID of the inserted business, or None if insertion failed.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                INSERT INTO businesses
                (name, address, zip, category, website, email, phone, source, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    address,
                    zip_code,
                    category,
                    website,
                    email,
                    phone,
                    source,
                    source_id,
                ),
            )
            # Get the ID of the inserted business
            cursor.execute("SELECT last_insert_rowid()")
            business_id = cursor.fetchone()["last_insert_rowid()"]
        logger.info(f"Saved business: {name} (ID: {business_id})")
        return business_id
    except Exception as e:
        logger.error(f"Error saving business {name}: {e}")
        return None


def mark_zip_done(zip_code: str) -> bool:
    """Mark a ZIP code as processed.
    Args:
        zip_code: ZIP code to mark as done.
    Returns:
        True if successful, False otherwise.
    """
    try:
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                UPDATE zip_queue
                SET done = 1, updated_at = CURRENT_TIMESTAMP
                WHERE zip = ?
                """,
                (zip_code,),
            )
        logger.info(f"Marked ZIP code {zip_code} as done")
        return True
    except Exception as e:
        logger.error(f"Error marking ZIP code {zip_code} as done: {e}")
        return False
