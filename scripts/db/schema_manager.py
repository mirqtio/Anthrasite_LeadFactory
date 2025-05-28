#!/usr/bin/env python3
"""
E2E Database Schema Manager

This script manages the database schema for E2E testing:
- Applies schema migrations in order
- Seeds the database with test data
- Validates schema correctness
- Provides utilities for schema inspection and maintenance
"""

import os
import sys
import logging
import argparse
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/schema_manager.log"),
    ],
)
logger = logging.getLogger("schema_manager")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "scripts/db/migrations"
SEEDS_DIR = PROJECT_ROOT / "scripts/db/seeds"
ENV_FILE = PROJECT_ROOT / ".env.e2e"


def get_connection_string():
    """Get database connection string from .env.e2e file"""
    if not ENV_FILE.exists():
        logger.error(f"Environment file not found: {ENV_FILE}")
        return None

    with open(ENV_FILE, "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                return line.strip().split("=", 1)[1]

    logger.error("DATABASE_URL not found in environment file")
    return None


def connect_to_db():
    """Connect to the database using the connection string from .env.e2e"""
    conn_string = get_connection_string()
    if not conn_string:
        return None

    try:
        logger.info(f"Connecting to database: {conn_string}")
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        logger.info("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def create_migrations_table(conn):
    """Create the migrations table if it doesn't exist"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        logger.info("Migrations table created or already exists")
        cursor.close()
        return True
    except Exception as e:
        logger.error(f"Failed to create migrations table: {e}")
        return False


def get_applied_migrations(conn):
    """Get a list of already applied migrations"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY id;")
        applied = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return applied
    except Exception as e:
        logger.error(f"Failed to get applied migrations: {e}")
        return []


def apply_migration(conn, migration_file):
    """Apply a single migration file"""
    version = migration_file.stem
    logger.info(f"Applying migration: {version}")

    try:
        # Read migration SQL
        sql = migration_file.read_text()

        # Execute migration in a transaction
        cursor = conn.cursor()
        cursor.execute("BEGIN;")
        cursor.execute(sql)

        # Record migration in migrations table
        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s);", (version,)
        )
        cursor.execute("COMMIT;")
        cursor.close()

        logger.info(f"✅ Migration {version} applied successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to apply migration {version}: {e}")
        cursor = conn.cursor()
        cursor.execute("ROLLBACK;")
        cursor.close()
        return False


def apply_migrations():
    """Apply all pending migrations in order"""
    conn = connect_to_db()
    if not conn:
        return False

    try:
        # Create migrations table if it doesn't exist
        if not create_migrations_table(conn):
            conn.close()
            return False

        # Get already applied migrations
        applied_migrations = get_applied_migrations(conn)
        logger.info(f"Found {len(applied_migrations)} applied migrations")

        # Get all migration files
        MIGRATIONS_DIR.mkdir(exist_ok=True)
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        if not migration_files:
            logger.warning(f"No migration files found in {MIGRATIONS_DIR}")
            conn.close()
            return True

        # Apply pending migrations
        success = True
        for migration_file in migration_files:
            version = migration_file.stem
            if version in applied_migrations:
                logger.info(f"Migration {version} already applied, skipping")
                continue

            if not apply_migration(conn, migration_file):
                success = False
                break

        conn.close()
        return success
    except Exception as e:
        logger.error(f"Error applying migrations: {e}")
        conn.close()
        return False


def seed_data():
    """Seed the database with test data"""
    conn = connect_to_db()
    if not conn:
        return False

    try:
        # Get all seed files
        SEEDS_DIR.mkdir(exist_ok=True)
        seed_files = sorted(SEEDS_DIR.glob("*.sql"))

        if not seed_files:
            logger.warning(f"No seed files found in {SEEDS_DIR}")
            conn.close()
            return True

        # Apply all seed files
        success = True
        cursor = conn.cursor()

        for seed_file in seed_files:
            try:
                logger.info(f"Applying seed file: {seed_file.name}")
                sql = seed_file.read_text()
                cursor.execute(sql)
                logger.info(f"✅ Seed file {seed_file.name} applied successfully")
            except Exception as e:
                logger.error(f"Failed to apply seed file {seed_file.name}: {e}")
                success = False

        cursor.close()
        conn.close()
        return success
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        conn.close()
        return False


def validate_schema():
    """Validate the database schema"""
    conn = connect_to_db()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Check required tables
        required_tables = [
            "businesses",
            "emails",
            "llm_logs",
            "zip_queue",
            "verticals",
            "assets",
        ]
        missing_tables = []

        for table in required_tables:
            cursor.execute(
                f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='{table}'
                );
            """
            )
            exists = cursor.fetchone()[0]
            if exists:
                logger.info(f"✅ Table {table} exists")
            else:
                logger.error(f"❌ Table {table} does not exist")
                missing_tables.append(table)

        if missing_tables:
            logger.error(f"Missing tables: {', '.join(missing_tables)}")
            cursor.close()
            conn.close()
            return False

        # Check zip_queue has data
        cursor.execute("SELECT COUNT(*) FROM zip_queue;")
        count = cursor.fetchone()[0]
        logger.info(f"zip_queue has {count} rows")

        if count == 0:
            logger.error("❌ zip_queue table is empty")
            cursor.close()
            conn.close()
            return False

        cursor.close()
        conn.close()
        logger.info("✅ Schema validation successful")
        return True
    except Exception as e:
        logger.error(f"Error validating schema: {e}")
        conn.close()
        return False


def show_schema():
    """Show detailed information about the database schema"""
    conn = connect_to_db()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Get all tables
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
            ORDER BY table_name;
        """
        )
        tables = [row[0] for row in cursor.fetchall()]

        print("\n=== DATABASE SCHEMA ===\n")

        for table in tables:
            print(f"\nTABLE: {table}")
            print("-" * (len(table) + 7))

            # Get columns
            cursor.execute(
                f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='{table}'
                ORDER BY ordinal_position;
            """
            )
            columns = cursor.fetchall()

            for column in columns:
                name, data_type, nullable, default = column
                nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
                default_str = f" DEFAULT {default}" if default else ""
                print(f"  {name} {data_type} {nullable_str}{default_str}")

            # Get constraints
            cursor.execute(
                f"""
                SELECT con.conname, con.contype, pg_get_constraintdef(con.oid)
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE rel.relname = '{table}' AND nsp.nspname = 'public';
            """
            )
            constraints = cursor.fetchall()

            if constraints:
                print("\n  Constraints:")
                for constraint in constraints:
                    name, type_code, definition = constraint
                    type_name = {
                        "p": "PRIMARY KEY",
                        "f": "FOREIGN KEY",
                        "u": "UNIQUE",
                        "c": "CHECK",
                    }.get(type_code, "UNKNOWN")
                    print(f"    {name} ({type_name}): {definition}")

            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"\n  Row count: {count}")

            # Show sample data if table has rows
            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
                rows = cursor.fetchall()

                # Get column names
                cursor.execute(
                    f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='{table}'
                    ORDER BY ordinal_position;
                """
                )
                column_names = [col[0] for col in cursor.fetchall()]

                print("\n  Sample data:")
                for row in rows:
                    for i, value in enumerate(row):
                        print(f"    {column_names[i]}: {value}")
                    print("")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error showing schema: {e}")
        conn.close()
        return False


def main():
    """Main function to manage the E2E database schema"""
    parser = argparse.ArgumentParser(description="E2E Database Schema Manager")
    parser.add_argument(
        "action",
        choices=["migrate", "seed", "validate", "show"],
        help="Action to perform",
    )

    args = parser.parse_args()

    if args.action == "migrate":
        success = apply_migrations()
        return 0 if success else 1

    elif args.action == "seed":
        success = seed_data()
        return 0 if success else 1

    elif args.action == "validate":
        success = validate_schema()
        return 0 if success else 1

    elif args.action == "show":
        success = show_schema()
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
