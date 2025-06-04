#!/usr/bin/env python3
"""
Setup E2E Database for LeadFactory Testing

This script provisions a PostgreSQL database for end-to-end testing:
1. Starts PostgreSQL Docker container
2. Creates database and applies schema
3. Seeds initial data from CSV/YAML files
4. Validates database setup
5. Creates .env.e2e configuration file
"""

import csv
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import psycopg2
import yaml


def run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0 and check:
        print(f"Command failed with return code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)

    return result


def wait_for_postgres(host: str = "localhost", port: int = 5432, timeout: int = 60):
    """Wait for PostgreSQL to be ready."""
    print(f"Waiting for PostgreSQL at {host}:{port}...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database="postgres",
                user="postgres",
                password="postgres",  # pragma: allowlist secret
            )
            conn.close()
            print("PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError:
            time.sleep(2)

    print(f"PostgreSQL not ready after {timeout} seconds")
    return False


def apply_schema(database_url: str):
    """Apply PostgreSQL schema to the database."""
    print("Applying database schema...")

    schema_file = (
        Path(__file__).parent.parent / "db" / "migrations" / "postgres_schema.sql"
    )
    if not schema_file.exists():
        print(f"Schema file not found: {schema_file}")
        return False

    try:
        # Read schema file
        with open(schema_file, "r") as f:
            schema_sql = f.read()

        # Connect and apply schema
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute(schema_sql)
        conn.commit()
        cur.close()
        conn.close()

        print("Schema applied successfully!")
        return True

    except Exception as e:
        print(f"Error applying schema: {e}")
        return False


def seed_zip_queue(database_url: str):
    """Seed zip_queue table from zips.csv."""
    print("Seeding zip_queue table...")

    csv_file = Path(__file__).parent.parent / "etc" / "zips.csv"
    if not csv_file.exists():
        print(f"Zips CSV file not found: {csv_file}")
        return False

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        # First create zip_queue table if it doesn't exist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zip_queue (
                id SERIAL PRIMARY KEY,
                zip TEXT NOT NULL,
                metro TEXT NOT NULL,
                state TEXT,
                done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(zip)
            )
        """
        )

        # Read and insert CSV data
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cur.execute(
                    """
                    INSERT INTO zip_queue (zip, metro, state)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (zip) DO NOTHING
                """,
                    (row["zip"], row["metro"], row.get("state", "")),
                )

        conn.commit()

        # Check how many were inserted
        cur.execute("SELECT COUNT(*) FROM zip_queue")
        count = cur.fetchone()[0]
        print(f"Seeded {count} zip codes in zip_queue")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Error seeding zip_queue: {e}")
        return False


def seed_verticals(database_url: str):
    """Seed verticals table from verticals.yml."""
    print("Seeding verticals table...")

    yaml_file = Path(__file__).parent.parent / "etc" / "verticals.yml"
    if not yaml_file.exists():
        print(f"Verticals YAML file not found: {yaml_file}")
        return False

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        # First create verticals table if it doesn't exist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS verticals (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                yelp_alias TEXT,
                google_alias TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        """
        )

        # Read and insert YAML data
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        for vertical in data.get("verticals", []):
            cur.execute(
                """
                INSERT INTO verticals (name, description, yelp_alias, google_alias)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING
            """,
                (
                    vertical["name"],
                    vertical.get("description", ""),
                    vertical.get("yelp_alias", ""),
                    vertical.get("google_alias", ""),
                ),
            )

        conn.commit()

        # Check how many were inserted
        cur.execute("SELECT COUNT(*) FROM verticals")
        count = cur.fetchone()[0]
        print(f"Seeded {count} verticals")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Error seeding verticals: {e}")
        return False


def validate_database(database_url: str):
    """Validate database setup by checking tables and data."""
    print("Validating database setup...")

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()

        # Check if required tables exist
        required_tables = ["businesses", "emails", "llm_logs", "zip_queue", "verticals"]

        for table in required_tables:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """,
                (table,),
            )

            exists = cur.fetchone()[0]
            if exists:
                print(f"✓ Table '{table}' exists")

                # Get row count
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                count = cur.fetchone()[0]
                print(f"  - Contains {count} rows")
            else:
                print(f"✗ Table '{table}' missing")
                return False

        # Test a simple SELECT to ensure connectivity
        cur.execute("SELECT 1")
        result = cur.fetchone()[0]
        if result == 1:
            print("✓ Database connectivity test passed")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Database validation failed: {e}")
        return False


def create_env_file():
    """Create .env.e2e file with database configuration."""
    print("Creating .env.e2e configuration file...")

    env_file = Path(__file__).parent.parent / ".env.e2e"
    database_url = "postgresql://postgres:postgres@localhost:5432/leadfactory"  # pragma: allowlist secret

    env_content = f"""# E2E Testing Configuration
# Generated by setup_e2e_database.py

# Database Configuration
DATABASE_URL={database_url}
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=leadfactory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# E2E Testing Flags
E2E_MODE=true
MOCKUP_ENABLED=true
EMAIL_OVERRIDE=test@example.com

# API Keys (to be filled in manually)
YELP_API_KEY=your_yelp_api_key_here
SCREENSHOTONE_API_KEY=your_screenshotone_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
SENDGRID_API_KEY=your_sendgrid_api_key_here

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=DEBUG
"""

    with open(env_file, "w") as f:
        f.write(env_content)

    print(f"Created {env_file}")
    print("Please update the API keys in .env.e2e before running E2E tests")
    return True


def main():
    """Main setup function."""
    print("🚀 Setting up E2E Database for LeadFactory")
    print("=" * 50)

    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Step 1: Start PostgreSQL with Docker Compose
    print("\n📦 Starting PostgreSQL Docker container...")
    result = run_command(
        ["docker-compose", "-f", "docker-compose.e2e.yml", "up", "-d", "postgres-e2e"]
    )

    # Step 2: Wait for PostgreSQL to be ready
    if not wait_for_postgres():
        print("❌ PostgreSQL setup failed")
        sys.exit(1)

    # Step 3: Apply database schema
    database_url = "postgresql://postgres:postgres@localhost:5432/leadfactory"  # pragma: allowlist secret
    if not apply_schema(database_url):
        print("❌ Schema application failed")
        sys.exit(1)

    # Step 4: Seed initial data
    if not seed_zip_queue(database_url):
        print("❌ Zip queue seeding failed")
        sys.exit(1)

    if not seed_verticals(database_url):
        print("❌ Verticals seeding failed")
        sys.exit(1)

    # Step 5: Validate database setup
    if not validate_database(database_url):
        print("❌ Database validation failed")
        sys.exit(1)

    # Step 6: Create .env.e2e file
    if not create_env_file():
        print("❌ Environment file creation failed")
        sys.exit(1)

    print("\n✅ E2E Database setup completed successfully!")
    print("\nNext steps:")
    print("1. Update API keys in .env.e2e")
    print("2. Run: bin/e2e_validate_config.py")
    print("3. Execute E2E tests")

    print(f"\nDatabase URL: {database_url}")
    print("Container: leadfactory-postgres-e2e")
    print("To stop: docker-compose -f docker-compose.e2e.yml down")


if __name__ == "__main__":
    main()
