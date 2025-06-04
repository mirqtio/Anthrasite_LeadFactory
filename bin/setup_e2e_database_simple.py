#!/usr/bin/env python3
"""
Simple E2E Database Setup for LeadFactory Testing

This script sets up the database for end-to-end testing without requiring Docker.
It can work with an existing PostgreSQL installation or SQLite for testing.
"""

import csv
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import yaml


def create_sqlite_database():
    """Create a SQLite database for E2E testing as fallback."""
    print("Creating SQLite database for E2E testing...")

    project_root = Path(__file__).parent.parent
    db_path = project_root / "test_e2e.db"

    # Remove existing database
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Apply SQLite schema from init file
    schema_file = project_root / "db" / "migrations" / "2025-05-19_init.sql"
    if schema_file.exists():
        with open(schema_file, "r") as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)

    # Apply additional migrations
    migrations = [
        "2025-05-21_llm_logs.sql",
        "2025-05-21_raw_html_storage.sql",
        "2025-05-21_unsubscribe.sql",
    ]

    for migration in migrations:
        migration_file = project_root / "db" / "migrations" / migration
        if migration_file.exists():
            with open(migration_file, "r") as f:
                migration_sql = f.read()
            try:
                cursor.executescript(migration_sql)
            except Exception as e:
                print(f"Warning: Could not apply {migration}: {e}")

    conn.commit()

    # Seed data
    seed_zip_queue_sqlite(cursor)
    seed_verticals_sqlite(cursor)

    conn.commit()
    conn.close()

    print(f"SQLite database created at: {db_path}")
    return str(db_path)


def seed_zip_queue_sqlite(cursor):
    """Seed zip_queue table from CSV for SQLite."""
    print("Seeding zip_queue table...")

    csv_file = Path(__file__).parent.parent / "etc" / "zips.csv"
    if not csv_file.exists():
        print(f"Warning: Zips CSV not found at {csv_file}")
        return

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO zip_queue (zip, metro)
                    VALUES (?, ?)
                """,
                    (row["zip"], row["metro"]),
                )

        # Check count
        cursor.execute("SELECT COUNT(*) FROM zip_queue")
        count = cursor.fetchone()[0]
        print(f"Seeded {count} zip codes")

    except Exception as e:
        print(f"Error seeding zip_queue: {e}")


def seed_verticals_sqlite(cursor):
    """Seed verticals table from YAML for SQLite."""
    print("Seeding verticals table...")

    yaml_file = Path(__file__).parent.parent / "etc" / "verticals.yml"
    if not yaml_file.exists():
        print(f"Warning: Verticals YAML not found at {yaml_file}")
        return

    try:
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        for vertical in data.get("verticals", []):
            cursor.execute(
                """
                INSERT OR IGNORE INTO verticals (name, alias)
                VALUES (?, ?)
            """,
                (
                    vertical["name"],
                    vertical.get("yelp_alias", vertical["name"].lower()),
                ),
            )

        # Check count
        cursor.execute("SELECT COUNT(*) FROM verticals")
        count = cursor.fetchone()[0]
        print(f"Seeded {count} verticals")

    except Exception as e:
        print(f"Error seeding verticals: {e}")


def validate_sqlite_database(db_path: str):
    """Validate SQLite database setup."""
    print("Validating database setup...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check required tables
        required_tables = ["businesses", "zip_queue", "verticals"]

        for table in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if cursor.fetchone():
                print(f"✓ Table '{table}' exists")

                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                count = cursor.fetchone()[0]
                print(f"  - Contains {count} rows")
            else:
                print(f"✗ Table '{table}' missing")
                return False

        # Test connectivity
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
        if result == 1:
            print("✓ Database connectivity test passed")

        conn.close()
        return True

    except Exception as e:
        print(f"Database validation failed: {e}")
        return False


def create_env_file(db_path: str = None):
    """Create .env.e2e file with database configuration."""
    print("Creating .env.e2e configuration file...")

    env_file = Path(__file__).parent.parent / ".env.e2e"

    if db_path:
        database_url = f"sqlite:///{db_path}"
    else:
        database_url = "postgresql://postgres:postgres@localhost:5432/leadfactory"  # pragma: allowlist secret

    env_content = f"""# E2E Testing Configuration
# Generated by setup_e2e_database_simple.py

# Database Configuration
DATABASE_URL={database_url}

# E2E Testing Flags
E2E_MODE=true
MOCKUP_ENABLED=true
EMAIL_OVERRIDE=test@example.com

# API Keys (to be filled in manually for real API testing)
YELP_API_KEY=test_key_replace_for_real_testing
SCREENSHOTONE_API_KEY=test_key_replace_for_real_testing
OPENAI_API_KEY=test_key_replace_for_real_testing
SENDGRID_API_KEY=test_key_replace_for_real_testing

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=DEBUG

# Test Settings
TEST_MODE=true
SKIP_REAL_API_CALLS=true
"""

    with open(env_file, "w") as f:
        f.write(env_content)

    print(f"Created {env_file}")
    return True


def main():
    """Main setup function."""
    print("🚀 Setting up E2E Database for LeadFactory (Simple Mode)")
    print("=" * 60)

    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("\n📦 Creating SQLite database for E2E testing...")

    # Create SQLite database as a simple alternative
    db_path = create_sqlite_database()

    # Validate database setup
    if not validate_sqlite_database(db_path):
        print("❌ Database validation failed")
        sys.exit(1)

    # Create .env.e2e file
    if not create_env_file(db_path):
        print("❌ Environment file creation failed")
        sys.exit(1)

    print("\n✅ E2E Database setup completed successfully!")
    print("\nSetup Summary:")
    print(f"- Database: SQLite at {db_path}")
    print(f"- Configuration: .env.e2e")
    print("- Mode: Testing with mock APIs")

    print("\nNext steps:")
    print("1. Review .env.e2e configuration")
    print("2. For real API testing, update API keys in .env.e2e")
    print("3. Run: python bin/e2e_validate_config.py")
    print("4. Execute E2E tests")

    print("\nNote: This setup uses SQLite for simplicity.")
    print(
        "For PostgreSQL, ensure PostgreSQL is running and update DATABASE_URL in .env.e2e"
    )


if __name__ == "__main__":
    main()
