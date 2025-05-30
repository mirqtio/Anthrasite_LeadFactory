"""
Legacy utils.io compatibility module.

This module provides backward compatibility for legacy code that imports
from utils.io. It re-exports functions from the new leadfactory.utils modules.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional, Union

# Set up logging
logger = logging.getLogger(__name__)

# Add project root to path to import leadfactory modules
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def track_api_cost(
    service: str,
    operation: str,
    cost_cents: float,
    tier: int = 1,
    business_id: Optional[str] = None,
) -> None:
    """
    Track API cost for monitoring and billing purposes.

    This is a compatibility function that provides the same interface as the legacy utils.io.track_api_cost.
    In test environments, this function is typically mocked.

    Args:
        service: The API service name (e.g., 'yelp', 'google_places')
        operation: The operation performed (e.g., 'search', 'details')
        cost_cents: The cost in cents
        tier: The tier level (default: 1)
        business_id: Optional business ID for tracking
    """
    try:
        # Try to import from the new metrics module
        from leadfactory.utils.metrics import track_metric

        # Convert to the new metrics format
        track_metric(
            metric_name=f"api_cost_{service}_{operation}",
            value=cost_cents,
            tags={
                "service": service,
                "operation": operation,
                "tier": str(tier),
                "business_id": business_id or "unknown",
            },
        )

        logger.debug(f"Tracked API cost: {service}.{operation} = {cost_cents} cents")

    except ImportError:
        # Fallback for test environments
        logger.debug(
            f"Mock tracking API cost: {service}.{operation} = {cost_cents} cents (tier={tier}, business_id={business_id})"
        )


def make_api_request(
    url: str,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    data: Optional[Union[dict[str, Any], str]] = None,
    timeout: int = 30,
    **kwargs,
) -> Any:
    """
    Make an API request with proper error handling and logging.

    This is a compatibility function that provides the same interface as the legacy utils.io.make_api_request.

    Args:
        url: The URL to make the request to
        method: HTTP method (GET, POST, etc.)
        headers: Optional headers dictionary
        params: Optional query parameters
        data: Optional request body data
        timeout: Request timeout in seconds
        **kwargs: Additional arguments passed to requests

    Returns:
        Response object or parsed JSON data
    """
    import requests

    try:
        # Set default headers
        if headers is None:
            headers = {}

        # Add user agent if not provided
        if "User-Agent" not in headers:
            headers["User-Agent"] = "LeadFactory/1.0"

        # Make the request
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            params=params,
            json=data if isinstance(data, dict) else None,
            data=data if isinstance(data, str) else None,
            timeout=timeout,
            **kwargs,
        )

        # Log the request
        logger.debug(f"API request: {method.upper()} {url} -> {response.status_code}")

        # Raise for HTTP errors
        response.raise_for_status()

        # Try to return JSON if possible, otherwise return response object
        try:
            return response.json()
        except ValueError:
            return response

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {method.upper()} {url} -> {str(e)}")
        raise


class DatabaseConnection:
    """
    Legacy DatabaseConnection compatibility class.

    This provides backward compatibility for legacy code that uses utils.io.DatabaseConnection.
    It delegates to the appropriate database connector based on the environment.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Optional database path (for SQLite compatibility)
        """
        self.db_path = db_path
        self._connection = None

        # Try to determine which database connector to use
        try:
            from leadfactory.utils.e2e_db_connector import get_connection

            self._get_connection = get_connection
            self._connection_type = "postgresql"
            logger.debug("Using PostgreSQL database connector")
        except ImportError:
            # Fallback to SQLite for testing
            import sqlite3

            self._connection_type = "sqlite"
            logger.debug("Using SQLite database connector")

    def __enter__(self):
        """Context manager entry."""
        if self._connection_type == "postgresql":
            self._connection = self._get_connection()
        else:
            # SQLite fallback
            import sqlite3

            db_path = self.db_path or ":memory:"
            self._connection = sqlite3.connect(db_path)
            self._connection.row_factory = sqlite3.Row

        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._connection:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
            self._connection.close()
            self._connection = None


# Default database path for compatibility
DEFAULT_DB_PATH = os.path.join(project_root, "data", "leadfactory.db")
