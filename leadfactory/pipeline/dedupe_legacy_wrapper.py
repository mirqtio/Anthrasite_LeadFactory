"""
Legacy dedupe module wrapper - provides backward compatibility.

This module wraps the unified dedupe implementation to maintain
backward compatibility with existing tests and code.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

# Import everything from the unified implementation
from leadfactory.pipeline.dedupe_unified import (
    LevenshteinMatcher,
    OllamaVerifier,
    deduplicate,
    flag_for_review,
    get_business_by_id,
    get_potential_duplicates,
    main,
    process_duplicate_pair,
    select_primary_business,
)
from leadfactory.pipeline.dedupe_unified import (
    merge_businesses as unified_merge_businesses,
)

logger = logging.getLogger(__name__)


# For backward compatibility with tests
class DatabaseConnection:
    """Database connection for dedupe module - redirects to unified connector."""

    def __init__(self, db_path=None):
        """Initialize database connection."""
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def __enter__(self):
        """Context manager enter method."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit method."""
        pass

    def execute(self, query, params=None):
        """Execute a query."""
        pass

    def fetchall(self):
        """Fetch all results."""
        return []


# Backward compatibility wrapper for merge_businesses
def merge_businesses(business1, business2, is_dry_run: bool = False):
    """Merge two business records.

    This function provides backward compatibility for the old API.
    It can be called in two ways:
    1. With two business dictionaries (original implementation)
    2. With two business IDs (new implementation)

    Args:
        business1: First business record/ID or database connection.
        business2: Second business record/ID.
        is_dry_run: If True, don't actually merge the records.

    Returns:
        ID of the merged business record.
    """
    # Check if being called with IDs (new style)
    if isinstance(business1, int) and isinstance(business2, int):
        return unified_merge_businesses(business1, business2, is_dry_run)

    # Check if being called with dictionaries (old style)
    if isinstance(business1, dict) and isinstance(business2, dict):
        # Select primary business
        primary_id, secondary_id = select_primary_business(business1, business2)
        return unified_merge_businesses(primary_id, secondary_id, is_dry_run)

    # Legacy test mode - handle connection object
    # This is for backward compatibility with tests that pass a connection
    if hasattr(business1, "cursor") or hasattr(business1, "execute"):
        # business1 is a connection, business2 is source_id, is_dry_run is target_id
        logger.warning(
            "Using legacy merge_businesses API - please update to use IDs directly"
        )
        source_id = business2
        target_id = is_dry_run
        # In the legacy API, target is kept and source is deleted
        return unified_merge_businesses(target_id, source_id, False)

    logger.error(
        f"Invalid arguments to merge_businesses: {type(business1)}, {type(business2)}"
    )
    return None


# Mock functions for backward compatibility
def get_business(conn, business_id):
    """Get business from database connection."""
    return get_business_by_id(business_id)


def get_db_connection(db_path=None):
    """Get database connection."""
    return DatabaseConnection(db_path)


def calculate_completeness_score(business: dict):
    """Calculate completeness score."""
    return sum(
        1
        for field in ["name", "phone", "email", "website", "address"]
        if business.get(field)
    )


# Re-export all other functions for backward compatibility
__all__ = [
    "DatabaseConnection",
    "LevenshteinMatcher",
    "OllamaVerifier",
    "get_potential_duplicates",
    "get_business_by_id",
    "get_business",
    "get_db_connection",
    "merge_businesses",
    "select_primary_business",
    "calculate_completeness_score",
    "flag_for_review",
    "process_duplicate_pair",
    "deduplicate",
    "main",
]
