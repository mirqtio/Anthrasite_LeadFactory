"""
I/O utility functions for the Anthrasite Lead-Factory pipeline.
Handles database connections, logging, and API requests.
"""

from typing import Dict, List, Optional, Tuple, Union, Any

import os
import sqlite3
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.pool
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
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leadfactory.db"
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

# Database connection constants
DATABASE_URL = os.getenv("DATABASE_URL", None)
DATABASE_POOL_MIN_CONN = int(os.getenv("DATABASE_POOL_MIN_CONN", "2"))
DATABASE_POOL_MAX_CONN = int(os.getenv("DATABASE_POOL_MAX_CONN", "10"))

# Global connection pool for Postgres
_pg_pool = None


def get_postgres_pool():
    """Get or create the Postgres connection pool.

    Returns:
        A connection pool for Postgres connections.
    """
    global _pg_pool
    if _pg_pool is None and DATABASE_URL is not None:
        try:
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                DATABASE_POOL_MIN_CONN,
                DATABASE_POOL_MAX_CONN,
                DATABASE_URL,
            )
            logger.info(
                f"Created Postgres connection pool with "
                f"{DATABASE_POOL_MIN_CONN}-{DATABASE_POOL_MAX_CONN} connections"
            )
        except Exception as e:
            logger.error(f"Error creating Postgres connection pool: {e}")
            # Fall back to SQLite if Postgres connection fails
            logger.warning("Falling back to SQLite database")
    return _pg_pool


class DatabaseConnection:
    """Context manager for database connections.

    Supports both SQLite and Postgres connections based on environment configuration.
    If DATABASE_URL is set, uses Postgres, otherwise falls back to SQLite.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses default path.
                     Only used if DATABASE_URL is not set (SQLite mode).
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn = None
        self.cursor = None
        self.is_postgres = DATABASE_URL is not None
        self.pool_connection = None

    def __enter__(self):
        """Establish database connection and return cursor."""
        if self.is_postgres:
            # Use Postgres connection from pool
            pool = get_postgres_pool()
            if pool is None:
                # Fall back to SQLite if pool creation failed
                self.is_postgres = False
                return self._connect_sqlite()

            try:
                self.pool_connection = pool.getconn()
                self.conn = self.pool_connection
                # Configure cursor to return dictionaries
                self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                return self.cursor
            except Exception as e:
                logger.error(f"Error getting Postgres connection from pool: {e}")
                # Fall back to SQLite if Postgres connection fails
                self.is_postgres = False
                return self._connect_sqlite()
        else:
            # Use SQLite connection
            return self._connect_sqlite()

    def _connect_sqlite(self):
        """Establish SQLite database connection and return cursor."""
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
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

        if self.is_postgres:
            # Return connection to pool
            if self.pool_connection and get_postgres_pool():
                get_postgres_pool().putconn(self.pool_connection)
                self.pool_connection = None
        elif self.conn:
            # Close SQLite connection
            self.conn.close()


def load_yaml_config(file_path: str) -> dict:
    """Load YAML configuration file.
    Args:
        file_path: Path to YAML file.
    Returns:
        Dictionary containing configuration.
    """
    try:
        with Path(file_path).open() as f:
            config = yaml.safe_load(f)
        logger.debug(f"Loaded configuration from {file_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading YAML config from {file_path}: {e}")
        raise


def load_csv_data(file_path: str) -> list[dict]:
    """Load data from CSV file.
    Args:
        file_path: Path to CSV file.
    Returns:
        List of dictionaries, each representing a row in the CSV.
    """
    import csv

    try:
        with Path(file_path).open() as f:
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


def get_active_zip_codes() -> list[dict]:
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


def get_verticals() -> list[dict]:
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
