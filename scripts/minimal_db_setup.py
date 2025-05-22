#!/usr/bin/env python3
"""
Minimal Database Setup Script

This script creates a minimal database schema with essential tables
and populates them with mock data for testing purposes.

It follows the principles of:
1. Incremental Changes: Creates only essential tables
2. Evidence-Based Fixes: Based on actual test requirements
3. Comprehensive Error Handling: Robust error handling for all operations

Usage:
    python scripts/minimal_db_setup.py [--verbose]
"""

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def setup_database_schema(db_path, verbose=False):
    """
    Set up the minimal database schema with essential tables.

    Args:
        db_path (str): Path to the SQLite database file
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Setting up database schema at {db_path}")

        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create businesses table (core table)
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            country TEXT,
            industry TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            score REAL DEFAULT 0.0
        )
        """
        )

        # Create email_opt_outs table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS email_opt_outs (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Create metrics table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Create cost_tracking table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id INTEGER PRIMARY KEY,
            service TEXT NOT NULL,
            operation TEXT NOT NULL,
            cost_dollars REAL NOT NULL,
            business_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses (id)
        )
        """
        )

        # Create api_keys table (for testing API key validation)
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Commit changes
        conn.commit()

        if verbose:
            # List all tables to verify schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            logger.info(f"Created tables: {', '.join([t[0] for t in tables])}")

        conn.close()
        logger.info("Database schema setup complete")
        return True

    except Exception as e:
        logger.error(f"Error setting up database schema: {e}")
        return False


def create_mock_data(db_path, verbose=False):
    """
    Create mock data for testing.

    Args:
        db_path (str): Path to the SQLite database file
        verbose (bool): Whether to enable verbose logging

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Creating mock data for testing")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Insert mock businesses
        mock_businesses = [
            (
                1,
                "Test Business 1",
                "https://example1.com",
                "test1@example.com",
                "555-1234",
                "123 Main St",
                "New York",
                "NY",
                "10001",
                "USA",
                "Technology",
            ),
            (
                2,
                "Test Business 2",
                "https://example2.com",
                "test2@example.com",
                "555-5678",
                "456 Oak St",
                "San Francisco",
                "CA",
                "94107",
                "USA",
                "Healthcare",
            ),
            (
                3,
                "Test Business 3",
                "https://example3.com",
                "test3@example.com",
                "555-9012",
                "789 Pine St",
                "Chicago",
                "IL",
                "60601",
                "USA",
                "Finance",
            ),
        ]

        cursor.executemany(
            """
        INSERT OR REPLACE INTO businesses (id, name, website, email, phone, address, city, state, zip_code, country, industry)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            mock_businesses,
        )

        # Insert mock email opt-outs
        mock_opt_outs = [
            ("optout1@example.com", "Unsubscribed"),
            ("optout2@example.com", "Bounced"),
            ("optout3@example.com", "Spam complaint"),
        ]

        cursor.executemany(
            """
        INSERT OR REPLACE INTO email_opt_outs (email, reason)
        VALUES (?, ?)
        """,
            mock_opt_outs,
        )

        # Insert mock metrics
        mock_metrics = [
            ("bounce_rate", 0.02),
            ("spam_complaint_rate", 0.01),
            ("open_rate", 0.35),
            ("click_rate", 0.15),
        ]

        cursor.executemany(
            """
        INSERT OR REPLACE INTO metrics (name, value)
        VALUES (?, ?)
        """,
            mock_metrics,
        )

        # Insert mock cost tracking
        mock_costs = [
            ("enrichment_api", "lookup", 0.05, 1),
            ("email_verification", "verify", 0.01, 2),
            ("data_provider", "fetch", 0.10, 3),
        ]

        cursor.executemany(
            """
        INSERT OR REPLACE INTO cost_tracking (service, operation, cost_dollars, business_id)
        VALUES (?, ?, ?, ?)
        """,
            mock_costs,
        )

        # Insert mock API keys
        mock_api_keys = [
            ("test_api_key_1", "Test API Key 1"),
            ("test_api_key_2", "Test API Key 2"),
        ]

        cursor.executemany(
            """
        INSERT OR REPLACE INTO api_keys (key, name)
        VALUES (?, ?)
        """,
            mock_api_keys,
        )

        # Commit changes
        conn.commit()

        if verbose:
            # Count records in each table to verify data
            # Use a whitelist approach to prevent SQL injection
            allowed_tables = [
                "businesses",
                "email_opt_outs",
                "metrics",
                "cost_tracking",
                "api_keys",
            ]
            for table_name in allowed_tables:
                # Using a fixed string SQL query with no interpolation for table names
                if table_name == "businesses":
                    cursor.execute("SELECT COUNT(*) FROM businesses")
                elif table_name == "email_opt_outs":
                    cursor.execute("SELECT COUNT(*) FROM email_opt_outs")
                elif table_name == "metrics":
                    cursor.execute("SELECT COUNT(*) FROM metrics")
                elif table_name == "cost_tracking":
                    cursor.execute("SELECT COUNT(*) FROM cost_tracking")
                elif table_name == "api_keys":
                    cursor.execute("SELECT COUNT(*) FROM api_keys")
                count = cursor.fetchone()[0]
                logger.info(f"Table {table_name}: {count} records")

        conn.close()
        logger.info("Mock data creation complete")
        return True

    except Exception as e:
        logger.error(f"Error creating mock data: {e}")
        return False


def main():
    """Main function with error handling."""
    try:
        parser = argparse.ArgumentParser(description="Minimal Database Setup Script")
        parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
        parser.add_argument("--db-path", type=str, help="Path to the database file")

        args = parser.parse_args()

        if args.verbose:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        # Determine project root and database path
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"

        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)

        # Use provided database path or default
        db_path = args.db_path if args.db_path else str(data_dir / "test.db")

        # Set up database schema
        schema_success = setup_database_schema(db_path, args.verbose)

        if not schema_success:
            logger.error("Failed to set up database schema")
            return 1

        # Create mock data
        data_success = create_mock_data(db_path, args.verbose)

        if not data_success:
            logger.error("Failed to create mock data")
            return 1

        logger.info(f"Database setup complete at {db_path}")
        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
