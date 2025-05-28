#!/usr/bin/env python3
"""
Test E2E Database Connection

This script tests the connection to the E2E testing PostgreSQL database
and verifies that the schema is properly set up with test data.
"""

import os
import sys
import psycopg2
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/e2e_db_test.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("e2e_db_test")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Database connection string from docker setup
CONNECTION_STRING = "postgresql://postgres:postgres@localhost:5432/leadfactory"  # pragma: allowlist secret


def test_connection():
    """Test connection to the database"""
    logger.info("Testing connection to E2E database...")

    try:
        conn = psycopg2.connect(CONNECTION_STRING)
        cursor = conn.cursor()

        # Test query - get PostgreSQL version
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"Connected to: {version}")

        # Get table counts
        tables = [
            "businesses",
            "emails",
            "llm_logs",
            "zip_queue",
            "verticals",
            "assets",
        ]
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
            count = cursor.fetchone()[0]
            logger.info(f"Table {table}: {count} rows")

        cursor.close()
        conn.close()
        logger.info("Database connection test successful!")
        return True

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
