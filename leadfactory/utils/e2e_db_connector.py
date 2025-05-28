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
