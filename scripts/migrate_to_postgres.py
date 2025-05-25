#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: SQLite to Postgres Migration Script
This script migrates data from a SQLite database to a Postgres database.
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

# Use lowercase versions for Python 3.9 compatibility
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import logging configuration
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)
# Load environment variables
load_dotenv()

# Constants
DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "leadfactory.db"
)
DATABASE_URL = os.getenv("DATABASE_URL")

# Table definitions with their schema
TABLE_SCHEMAS = {
    "businesses": """
        CREATE TABLE IF NOT EXISTS businesses (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            category TEXT,
            source TEXT,
            source_id TEXT,
            status TEXT DEFAULT 'pending',
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "features": """
        CREATE TABLE IF NOT EXISTS features (
            id SERIAL PRIMARY KEY,
            business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            tech_stack JSONB,
            social_profiles JSONB,
            business_type TEXT,
            employee_count INTEGER,
            annual_revenue NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "mockups": """
        CREATE TABLE IF NOT EXISTS mockups (
            id SERIAL PRIMARY KEY,
            business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            image_url TEXT,
            html_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "emails": """
        CREATE TABLE IF NOT EXISTS emails (
            id SERIAL PRIMARY KEY,
            business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            subject TEXT,
            body_html TEXT,
            body_text TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            message_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "candidate_duplicate_pairs": """
        CREATE TABLE IF NOT EXISTS candidate_duplicate_pairs (
            id SERIAL PRIMARY KEY,
            business_id_1 INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            business_id_2 INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            similarity_score NUMERIC,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_pair UNIQUE (business_id_1, business_id_2)
        )
    """,
    "business_merges": """
        CREATE TABLE IF NOT EXISTS business_merges (
            id SERIAL PRIMARY KEY,
            source_business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            target_business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
            merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "zip_queue": """
        CREATE TABLE IF NOT EXISTS zip_queue (
            id SERIAL PRIMARY KEY,
            zip TEXT NOT NULL UNIQUE,
            priority INTEGER DEFAULT 0,
            done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "verticals": """
        CREATE TABLE IF NOT EXISTS verticals (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "cost_tracking": """
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id SERIAL PRIMARY KEY,
            service TEXT NOT NULL,
            cost NUMERIC NOT NULL,
            date DATE NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "email_metrics": """
        CREATE TABLE IF NOT EXISTS email_metrics (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            sent INTEGER DEFAULT 0,
            delivered INTEGER DEFAULT 0,
            opened INTEGER DEFAULT 0,
            clicked INTEGER DEFAULT 0,
            bounced INTEGER DEFAULT 0,
            spam_reports INTEGER DEFAULT 0,
            unsubscribes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# Indexes to create after migration
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_businesses_name ON businesses(name)",
    "CREATE INDEX IF NOT EXISTS idx_businesses_zip ON businesses(zip)",
    "CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status)",
    "CREATE INDEX IF NOT EXISTS idx_businesses_score ON businesses(score)",
    "CREATE INDEX IF NOT EXISTS idx_features_business_id ON features(business_id)",
    "CREATE INDEX IF NOT EXISTS idx_mockups_business_id ON mockups(business_id)",
    "CREATE INDEX IF NOT EXISTS idx_emails_business_id ON emails(business_id)",
    "CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status)",
    "CREATE INDEX IF NOT EXISTS idx_candidate_duplicate_pairs_status ON candidate_duplicate_pairs(status)",
    "CREATE INDEX IF NOT EXISTS idx_zip_queue_done ON zip_queue(done)",
    "CREATE INDEX IF NOT EXISTS idx_cost_tracking_service ON cost_tracking(service)",
    "CREATE INDEX IF NOT EXISTS idx_cost_tracking_date ON cost_tracking(date)",
    "CREATE INDEX IF NOT EXISTS idx_email_metrics_date ON email_metrics(date)",
]

# Type conversion mapping from SQLite to Postgres
TYPE_CONVERSIONS = {
    "INTEGER": "INTEGER",
    "REAL": "NUMERIC",
    "TEXT": "TEXT",
    "BLOB": "BYTEA",
    "BOOLEAN": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMP",
    "DATE": "DATE",
    "JSON": "JSONB",
}


@contextmanager
def sqlite_connection(db_path: str):
    """Context manager for SQLite connections.

    Args:
        db_path: Path to SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def postgres_connection(db_url: str):
    """Context manager for Postgres connections.

    Args:
        db_url: Postgres connection URL.
    """
    conn = psycopg2.connect(db_url)
    try:
        yield conn
    finally:
        conn.close()


def get_sqlite_tables(sqlite_conn) -> list[str]:
    """Get list of tables in SQLite database.

    Args:
        sqlite_conn: SQLite connection.

    Returns:
        list of table names.
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def get_sqlite_table_schema(sqlite_conn, table_name: str) -> list[tuple[str, str]]:
    """Get schema of a table in SQLite database.

    Args:
        sqlite_conn: SQLite connection.
        table_name: Name of the table.

    Returns:
        list of (column_name, column_type) tuples.
    """
    cursor = sqlite_conn.cursor()

    # Validate table name to prevent SQL injection
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name: {table_name}")

    # Use f-string with validated table name
    cursor.execute(f"PRAGMA table_info({table_name})")  # nosec B608
    return [(row[1], row[2]) for row in cursor.fetchall()]


def create_postgres_tables(pg_conn):
    """Create tables in Postgres database.

    Args:
        pg_conn: Postgres connection.
    """
    cursor = pg_conn.cursor()

    # Create tables
    for table_name, schema in TABLE_SCHEMAS.items():
        logger.info(f"Creating table {table_name} in Postgres")
        cursor.execute(schema)

    # Create indexes
    for index in INDEXES:
        logger.info(f"Creating index: {index}")
        cursor.execute(index)

    pg_conn.commit()


def get_sqlite_data(sqlite_conn, table_name: str) -> list[dict[str, Any]]:
    """Get data from a table in SQLite database.

    Args:
        sqlite_conn: SQLite connection.
        table_name: Name of the table.

    Returns:
        list of dictionaries representing rows.
    """
    cursor = sqlite_conn.cursor()
    # Use parameterized query to avoid SQL injection
    # Table names cannot be parameterized directly in most database APIs
    # Adding a validation step to ensure table_name contains only alphanumeric characters and underscores
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name: {table_name}")

    # Use string formatting with a validated table name instead of concatenation
    # This is safe because we've validated the table_name above
    cursor.execute(f"SELECT * FROM {table_name}")  # nosec B608
    columns = [column[0] for column in cursor.description]
    # In Python 3.9, zip() doesn't have the strict parameter
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def insert_postgres_data(pg_conn, table_name: str, data: list[dict[str, Any]]):
    """Insert data into a table in Postgres database.

    Args:
        pg_conn: Postgres connection.
        table_name: Name of the table.
        data: list of dictionaries representing rows.
    """
    if not data:
        logger.info(f"No data to insert for table {table_name}")
        return

    cursor = pg_conn.cursor()

    # Get column names from the first row
    columns = list(data[0].keys())

    # Prepare the SQL statement
    placeholders = ", ".join(["%s"] * len(columns))
    column_str = ", ".join(columns)
    # Table names cannot be parameterized directly, but this is a controlled internal script
    # with validated table names from get_sqlite_tables()
    # Adding a validation step to ensure table_name contains only alphanumeric characters and underscores
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    # Using a prepared statement approach for better security
    # The table_name has been validated with regex pattern earlier
    # Create a parameterized query using a validated table name
    # This is secure because we validate the table name with a regex pattern
    # that only allows alphanumeric characters and underscores
    sql = (
        f"INSERT INTO {table_name} ({column_str}) VALUES ({placeholders})"  # nosec B608
    )

    # Insert data in batches
    batch_size = 1000
    total_rows = len(data)
    for i in range(0, total_rows, batch_size):
        batch = data[i : i + batch_size]
        batch_values = [[row.get(col, None) for col in columns] for row in batch]
        cursor.executemany(sql, batch_values)
        pg_conn.commit()
        logger.info(
            f"Inserted {min(i+batch_size, total_rows)}/{total_rows} rows into {table_name}"
        )


def migrate_table(sqlite_conn, pg_conn, table_name: str):
    """Migrate a table from SQLite to Postgres.

    Args:
        sqlite_conn: SQLite connection.
        pg_conn: Postgres connection.
        table_name: Name of the table.
    """
    logger.info(f"Migrating table {table_name}")

    # Get data from SQLite
    data = get_sqlite_data(sqlite_conn, table_name)
    logger.info(f"Retrieved {len(data)} rows from SQLite table {table_name}")

    # Insert data into Postgres
    insert_postgres_data(pg_conn, table_name, data)
    logger.info(f"Migration of table {table_name} completed")


def migrate_database(sqlite_path: str, postgres_url: str):
    """Migrate database from SQLite to Postgres.

    Args:
        sqlite_path: Path to SQLite database file.
        postgres_url: Postgres connection URL.
    """
    logger.info(f"Starting migration from SQLite ({sqlite_path}) to Postgres")

    # Connect to databases
    with (
        sqlite_connection(sqlite_path) as sqlite_conn,
        postgres_connection(postgres_url) as pg_conn,
    ):
        # Get list of tables in SQLite
        sqlite_tables = get_sqlite_tables(sqlite_conn)
        logger.info(
            f"Found {len(sqlite_tables)} tables in SQLite: {', '.join(sqlite_tables)}"
        )

        # Create tables in Postgres
        create_postgres_tables(pg_conn)

        # Migrate each table
        for table_name in sqlite_tables:
            if table_name in TABLE_SCHEMAS:
                migrate_table(sqlite_conn, pg_conn, table_name)
            else:
                logger.warning(
                    f"Skipping table {table_name} as it is not defined in TABLE_SCHEMAS"
                )

    logger.info("Migration completed successfully")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Migrate SQLite database to Postgres")
    parser.add_argument(
        "--sqlite-path",
        default=DEFAULT_SQLITE_PATH,
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--postgres-url", default=DATABASE_URL, help="Postgres connection URL"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run (no actual migration)"
    )
    args = parser.parse_args()

    if not args.postgres_url:
        logger.error(
            "Postgres connection URL not specified. Set DATABASE_URL environment variable or use --postgres-url"
        )
        sys.exit(1)

    if not os.path.exists(args.sqlite_path):
        logger.error(f"SQLite database file not found: {args.sqlite_path}")
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry run mode - no actual migration will be performed")
        # Connect to databases
        with sqlite_connection(args.sqlite_path) as sqlite_conn:
            # Get list of tables in SQLite
            sqlite_tables = get_sqlite_tables(sqlite_conn)
            logger.info(
                f"Found {len(sqlite_tables)} tables in SQLite: {', '.join(sqlite_tables)}"
            )

            # Check each table
            for table_name in sqlite_tables:
                if table_name in TABLE_SCHEMAS:
                    schema = get_sqlite_table_schema(sqlite_conn, table_name)
                    # Table names cannot be parameterized directly, but this is a controlled internal script
                    # with validated table names from get_sqlite_tables()
                    # Adding a validation step to ensure table_name contains only alphanumeric characters and underscores
                    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                        raise ValueError(f"Invalid table name: {table_name}")
                    # Using a prepared statement approach for better security
                    # Use a safer approach with a parameterized query for table names
                    # Create a query that is safe from SQL injection
                    cursor = sqlite_conn.cursor()
                    # SQLite doesn't support parameterized table names, so we use a whitelist approach
                    # Validate that table_name only contains alphanumeric characters and underscores
                    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                        raise ValueError(f"Invalid table name format: {table_name}")

                    # Now it's safe to use the table name in the query
                    # We've validated the table name with a regex pattern to ensure it only contains
                    # alphanumeric characters and underscores, so it's safe from SQL injection
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")  # nosec B608
                    row_count = cursor.fetchone()[0]
                    logger.info(
                        f"Table {table_name}: {row_count} rows, {len(schema)} columns"
                    )
                else:
                    logger.warning(
                        f"Table {table_name} is not defined in TABLE_SCHEMAS and will be skipped"
                    )

        logger.info("Dry run completed")
    else:
        # Perform actual migration
        start_time = time.time()
        migrate_database(args.sqlite_path, args.postgres_url)
        end_time = time.time()
        logger.info(f"Migration completed in {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    main()
