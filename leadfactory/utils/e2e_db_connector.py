"""
E2E Database Connector Module

This module provides utilities for connecting to the E2E PostgreSQL database
and executing queries. It loads configuration from the .env.e2e file when
E2E_MODE is enabled.
"""

import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import psycopg2

# Configure logging
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env.e2e"
PROD_TEST_ENV_FILE = PROJECT_ROOT / ".env.prod_test"


def is_e2e_mode() -> bool:
    """Check if running in E2E testing mode"""
    return os.getenv("E2E_MODE", "").lower() == "true"


def is_production_test_mode() -> bool:
    """Check if running in production test mode"""
    return os.getenv("PRODUCTION_TEST_MODE", "").lower() == "true"


def load_e2e_env() -> bool:
    """Load environment variables from .env.e2e file if E2E_MODE is enabled"""
    if not is_e2e_mode():
        logger.debug("Not in E2E mode, skipping .env.e2e loading")
        return False

    if not ENV_FILE.exists():
        logger.error(f"E2E environment file not found: {ENV_FILE}")
        return False

    logger.info(f"Loading E2E environment from {ENV_FILE}")

    # Parse environment file
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                key, value = line.split("=", 1)
                os.environ[key] = value
                logger.debug(f"Set E2E environment variable: {key}")
            except ValueError:
                logger.warning(f"Skipping invalid line in .env.e2e: {line}")

    return True


def load_production_test_env() -> bool:
    """Load environment variables from .env.prod_test file if PRODUCTION_TEST_MODE is enabled"""
    if not is_production_test_mode():
        logger.debug("Not in production test mode, skipping .env.prod_test loading")
        return False

    if not PROD_TEST_ENV_FILE.exists():
        logger.error(
            f"Production test environment file not found: {PROD_TEST_ENV_FILE}"
        )
        return False

    logger.info(f"Loading production test environment from {PROD_TEST_ENV_FILE}")

    # Parse environment file
    with open(PROD_TEST_ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value
                logger.debug(f"Set environment variable: {key}")

    return True


def get_db_connection_string() -> str:
    """Get the database connection string from environment variables"""
    # Ensure E2E environment is loaded if in E2E mode
    if is_e2e_mode() and not load_e2e_env():
        logger.warning("Failed to load E2E environment, using default configuration")

    # Ensure production test environment is loaded if in production test mode
    if is_production_test_mode() and not load_production_test_env():
        logger.warning(
            "Failed to load production test environment, using default configuration"
        )

    # Get the database URL from environment variables
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")

    return db_url


@contextmanager
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager for database connections.

    Usage:
        with db_connection() as conn:
            # Use connection
    """
    conn = None
    try:
        conn_string = get_db_connection_string()
        conn = psycopg2.connect(conn_string)
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


@contextmanager
def db_cursor() -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Context manager for database cursors.

    Usage:
        with db_cursor() as cursor:
            # Use cursor
    """
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


def execute_query(
    query: str, params: Optional[Tuple] = None, fetch: bool = True
) -> List[Tuple]:
    """
    Execute a SQL query and return the results.

    Args:
        query: SQL query string
        params: Query parameters
        fetch: Whether to fetch and return results

    Returns:
        List of result rows
    """
    try:
        with db_cursor() as cursor:
            cursor.execute(query, params)

            if fetch:
                return cursor.fetchall()
            return []
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        raise


def execute_transaction(queries: List[Tuple[str, Optional[Tuple]]]) -> bool:
    """
    Execute multiple queries in a transaction.

    Args:
        queries: List of (query, params) tuples

    Returns:
        True if transaction succeeded
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            try:
                for query, params in queries:
                    cursor.execute(query, params)

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction error: {e}")
                raise
            finally:
                cursor.close()
    except Exception as e:
        logger.error(f"Transaction connection error: {e}")
        raise


def check_connection() -> bool:
    """
    Check if the database connection is working.

    Returns:
        True if connection is successful
    """
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            return result == (1,)
    except Exception as e:
        logger.error(f"Connection check failed: {e}")
        return False


def validate_schema() -> bool:
    """
    Validate that the database schema has the required tables.

    Returns:
        True if schema is valid
    """
    required_tables = [
        "businesses",
        "emails",
        "llm_logs",
        "zip_queue",
        "verticals",
        "assets",
    ]

    try:
        with db_cursor() as cursor:
            # Check each required table
            for table in required_tables:
                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name=%s);",
                    (table,),
                )
                exists = cursor.fetchone()[0]

                if not exists:
                    logger.error(f"Required table missing: {table}")
                    return False

            return True
    except Exception as e:
        logger.error(f"Schema validation error: {e}")
        return False


# ===== DEDUPLICATION FUNCTIONS =====


def get_potential_duplicate_pairs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get potential duplicate business pairs from the database.

    Args:
        limit: Maximum number of pairs to return

    Returns:
        List of potential duplicate pairs
    """
    query = """
    WITH business_pairs AS (
        SELECT
            b1.id AS business1_id,
            b2.id AS business2_id,
            b1.name AS business1_name,
            b2.name AS business2_name,
            b1.phone AS business1_phone,
            b2.phone AS business2_phone,
            b1.email AS business1_email,
            b2.email AS business2_email,
            b1.website AS business1_website,
            b2.website AS business2_website,
            b1.address AS business1_address,
            b2.address AS business2_address,
            b1.city AS business1_city,
            b2.city AS business2_city,
            b1.state AS business1_state,
            b2.state AS business2_state,
            b1.zip AS business1_zip,
            b2.zip AS business2_zip,
            -- Calculate similarity score
            GREATEST(
                CASE WHEN b1.phone IS NOT NULL AND b1.phone = b2.phone THEN 1.0 ELSE 0 END,
                CASE WHEN b1.email IS NOT NULL AND b1.email = b2.email THEN 1.0 ELSE 0 END,
                CASE WHEN b1.website IS NOT NULL AND b1.website = b2.website THEN 0.9 ELSE 0 END,
                CASE WHEN b1.name IS NOT NULL AND b2.name IS NOT NULL
                     AND levenshtein(LOWER(b1.name), LOWER(b2.name)) / GREATEST(LENGTH(b1.name), LENGTH(b2.name))::float < 0.3
                     THEN 0.8 ELSE 0 END
            ) AS similarity_score
        FROM businesses b1
        INNER JOIN businesses b2 ON b1.id < b2.id
        WHERE
            -- Not already processed
            NOT EXISTS (
                SELECT 1 FROM dedupe_log dl
                WHERE (dl.primary_id = b1.id AND dl.secondary_id = b2.id)
                   OR (dl.primary_id = b2.id AND dl.secondary_id = b1.id)
            )
            -- Not in review queue
            AND NOT EXISTS (
                SELECT 1 FROM review_queue rq
                WHERE (rq.business1_id = b1.id AND rq.business2_id = b2.id)
                   OR (rq.business1_id = b2.id AND rq.business2_id = b1.id)
            )
            -- At least one matching criteria
            AND (
                (b1.phone IS NOT NULL AND b1.phone = b2.phone)
                OR (b1.email IS NOT NULL AND b1.email = b2.email)
                OR (b1.website IS NOT NULL AND b1.website = b2.website)
                OR (b1.name IS NOT NULL AND b2.name IS NOT NULL
                    AND levenshtein(LOWER(b1.name), LOWER(b2.name)) / GREATEST(LENGTH(b1.name), LENGTH(b2.name))::float < 0.3)
            )
    )
    SELECT * FROM business_pairs
    WHERE similarity_score > 0.5
    ORDER BY similarity_score DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    try:
        with db_cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting potential duplicates: {e}")
        return []


def get_business_details(business_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed business information including JSON responses.

    Args:
        business_id: ID of the business

    Returns:
        Business details or None if not found
    """
    query = """
    SELECT
        id, name, phone, email, website, address, city, state, zip,
        category, vertical_id, source, created_at, updated_at,
        google_response, yelp_response, manual_response
    FROM businesses
    WHERE id = %s
    """

    try:
        with db_cursor() as cursor:
            cursor.execute(query, (business_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    except Exception as e:
        logger.error(f"Error getting business details: {e}")
        return None


def merge_business_records(primary_id: int, secondary_id: int) -> bool:
    """
    Merge two business records in the database.

    Args:
        primary_id: ID of the business to keep
        secondary_id: ID of the business to merge and delete

    Returns:
        True if successful, False otherwise
    """
    merge_queries = [
        # Update emails to point to primary business
        "UPDATE emails SET business_id = %s WHERE business_id = %s",
        # Update assets to point to primary business
        "UPDATE assets SET business_id = %s WHERE business_id = %s",
        # Log the merge operation
        "INSERT INTO dedupe_log (primary_id, secondary_id) VALUES (%s, %s)",
        # Delete the secondary business
        "DELETE FROM businesses WHERE id = %s",
    ]

    try:
        with db_transaction() as conn:
            cursor = conn.cursor()

            # Execute merge operations
            cursor.execute(merge_queries[0], (primary_id, secondary_id))
            cursor.execute(merge_queries[1], (primary_id, secondary_id))
            cursor.execute(merge_queries[2], (primary_id, secondary_id))
            cursor.execute(merge_queries[3], (secondary_id,))

            logger.info(
                f"Successfully merged business {secondary_id} into {primary_id}"
            )
            return True

    except Exception as e:
        logger.error(f"Error merging businesses: {e}")
        return False


def update_business_fields(business_id: int, updates: Dict[str, Any]) -> bool:
    """
    Update specific fields of a business record.

    Args:
        business_id: ID of the business to update
        updates: Dictionary of field names and values to update

    Returns:
        True if successful, False otherwise
    """
    if not updates:
        return True

    # Build UPDATE query dynamically
    set_clauses = []
    values = []

    for field, value in updates.items():
        set_clauses.append(f"{field} = %s")
        values.append(value)

    values.append(business_id)

    query = f"""
    UPDATE businesses
    SET {', '.join(set_clauses)}, updated_at = NOW()
    WHERE id = %s
    """

    try:
        with db_cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating business fields: {e}")
        return False


def add_to_review_queue(
    business1_id: int,
    business2_id: int,
    reason: str,
    similarity_score: float = None,
    details: str = None,
) -> int:
    """
    Add a potential duplicate pair to the manual review queue.

    Args:
        business1_id: First business ID
        business2_id: Second business ID
        reason: Reason for manual review
        similarity_score: Calculated similarity score (optional)
        details: Additional details in JSON format (optional)

    Returns:
        Review queue ID if successful, None otherwise
    """
    query = """
    INSERT INTO dedupe_review_queue (business1_id, business2_id, reason, similarity_score, details, status, created_at)
    VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
    RETURNING id
    """

    try:
        with db_cursor() as cursor:
            cursor.execute(
                query, (business1_id, business2_id, reason, similarity_score, details)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error adding to review queue: {e}")
        return None


def get_review_queue_items(
    status: str = None, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get items from the review queue.

    Args:
        status: Filter by status (pending, resolved, deferred)
        limit: Maximum number of items to return

    Returns:
        List of review queue items
    """
    query = """
    SELECT id, business1_id, business2_id, reason, similarity_score,
           details, status, created_at, updated_at
    FROM dedupe_review_queue
    """

    params = []
    if status:
        query += " WHERE status = %s"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    try:
        with db_cursor() as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting review queue items: {e}")
        return []


def update_review_status(review_id: int, status: str, resolution: str = None) -> bool:
    """
    Update the status of a review queue item.

    Args:
        review_id: ID of the review item
        status: New status (resolved, deferred, etc.)
        resolution: Resolution details in JSON format

    Returns:
        True if successful, False otherwise
    """
    query = """
    UPDATE dedupe_review_queue
    SET status = %s, resolution = %s, updated_at = NOW()
    WHERE id = %s
    """

    try:
        with db_cursor() as cursor:
            cursor.execute(query, (status, resolution, review_id))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating review status: {e}")
        return False


def check_dedupe_tables_exist() -> bool:
    """
    Check if dedupe-related tables exist in the database.

    Returns:
        True if all tables exist, False otherwise
    """
    required_tables = ["dedupe_log", "dedupe_review_queue"]

    try:
        with db_cursor() as cursor:
            for table in required_tables:
                cursor.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name=%s);",
                    (table,),
                )
                if not cursor.fetchone()[0]:
                    logger.warning(f"Dedupe table missing: {table}")
                    return False
        return True
    except Exception as e:
        logger.error(f"Error checking dedupe tables: {e}")
        return False


def create_dedupe_tables() -> bool:
    """
    Create dedupe-related tables if they don't exist.

    Returns:
        True if successful, False otherwise
    """
    create_statements = [
        """
        CREATE TABLE IF NOT EXISTS dedupe_log (
            id SERIAL PRIMARY KEY,
            primary_id INTEGER NOT NULL REFERENCES businesses(id),
            secondary_id INTEGER NOT NULL,
            merge_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS dedupe_review_queue (
            id SERIAL PRIMARY KEY,
            business1_id INTEGER NOT NULL REFERENCES businesses(id),
            business2_id INTEGER NOT NULL REFERENCES businesses(id),
            reason TEXT NOT NULL,
            similarity_score FLOAT,
            details TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            resolution TEXT,
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_dedupe_log_primary_id ON dedupe_log(primary_id)",
        "CREATE INDEX IF NOT EXISTS idx_dedupe_log_secondary_id ON dedupe_log(secondary_id)",
        "CREATE INDEX IF NOT EXISTS idx_dedupe_review_queue_business1 ON dedupe_review_queue(business1_id)",
        "CREATE INDEX IF NOT EXISTS idx_dedupe_review_queue_business2 ON dedupe_review_queue(business2_id)",
        "CREATE EXTENSION IF NOT EXISTS fuzzystrmatch",
    ]

    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            for statement in create_statements:
                cursor.execute(statement)
            logger.info("Successfully created dedupe tables")
            return True
    except Exception as e:
        logger.error(f"Error creating dedupe tables: {e}")
        return False
