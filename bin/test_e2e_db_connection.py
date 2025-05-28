#!/usr/bin/env python3
"""
Test E2E Database Connection

This script tests the connection to the E2E PostgreSQL database and verifies
that the expected tables and data are present.
"""

import os
import sys
import logging
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 module not found. Please install it with:")
    print("pip install psycopg2-binary")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("e2e_db_test")

# Load DATABASE_URL from .env.e2e
ENV_FILE = Path(__file__).parent.parent / ".env.e2e"
DATABASE_URL = None

if ENV_FILE.exists():
    with open(ENV_FILE, "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                DATABASE_URL = line.strip().split("=", 1)[1]
                break

if not DATABASE_URL:
    logger.error("DATABASE_URL not found in .env.e2e file")
    sys.exit(1)

logger.info(f"Using database URL: {DATABASE_URL}")


def test_connection():
    """Test connection to the E2E PostgreSQL database"""
    try:
        logger.info("Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Get PostgreSQL version
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"Connected to: {version}")

        # Check tables
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
        )
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")

        # Required tables
        required_tables = [
            "businesses",
            "emails",
            "llm_logs",
            "zip_queue",
            "verticals",
            "assets",
        ]
        missing_tables = [table for table in required_tables if table not in tables]

        if missing_tables:
            logger.error(f"Missing tables: {', '.join(missing_tables)}")
            return False
        else:
            logger.info("✅ All required tables exist")

        # Check table counts
        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"Table {table}: {count} rows")

        # Check specific data in zip_queue
        cursor.execute("SELECT zip, city, state FROM zip_queue LIMIT 5")
        rows = cursor.fetchall()
        logger.info(f"Sample ZIP codes: {rows}")

        # Check specific data in businesses
        cursor.execute("SELECT name, city, state FROM businesses LIMIT 5")
        rows = cursor.fetchall()
        logger.info(f"Sample businesses: {rows}")

        cursor.close()
        conn.close()
        logger.info("✅ Database connection test successful!")
        return True

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
