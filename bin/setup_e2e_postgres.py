#!/usr/bin/env python3
"""
E2E PostgreSQL Database Setup Script

This script provides a simplified, reliable way to set up the PostgreSQL database
for E2E testing using Docker.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("e2e_postgres")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.e2e.yml"
ENV_FILE = PROJECT_ROOT / ".env.e2e"


def exec_command(cmd_list, check=True):
    """Execute a command using subprocess and return the result"""
    cmd_str = " ".join(cmd_list)
    logger.info(f"Running: {cmd_str}")

    try:
        result = subprocess.run(
            cmd_list,
            check=check,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            logger.info(f"Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Error: {e.stderr.strip()}")
        if check:
            sys.exit(e.returncode)
        return e


def docker_compose(action):
    """Run docker compose command with the e2e file"""
    return exec_command(
        ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), *action.split()]
    )


def check_prereqs():
    """Check if Docker and docker-compose are available"""
    logger.info("Checking prerequisites...")

    # Check Docker
    try:
        result = exec_command(["docker", "--version"])
        if result.returncode == 0:
            logger.info("✅ Docker is installed")
        else:
            logger.error("❌ Docker is not available")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking Docker: {e}")
        sys.exit(1)

    # Check docker compose
    try:
        result = exec_command(["docker", "compose", "version"])
        if result.returncode == 0:
            logger.info("✅ Docker Compose is installed")
        else:
            logger.error("❌ Docker Compose is not available")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking Docker Compose: {e}")
        sys.exit(1)

    # Check if docker-compose file exists
    if not DOCKER_COMPOSE_FILE.exists():
        logger.error(f"❌ Docker compose file not found: {DOCKER_COMPOSE_FILE}")
        sys.exit(1)

    logger.info("✅ All prerequisites checked")


def stop_container():
    """Stop and remove the container"""
    logger.info("Stopping E2E database container...")
    docker_compose("down")
    logger.info("✅ Database container stopped")


def start_container():
    """Start the container and wait for it to be ready"""
    logger.info("Starting E2E database container...")
    docker_compose("up -d")
    logger.info("Waiting for database to be ready...")

    max_attempts = 30
    wait_seconds = 2

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Attempt {attempt}/{max_attempts} to connect to database...")

        # Check if container is running
        result = exec_command(
            [
                "docker",
                "ps",
                "-f",
                "name=leadfactory_e2e_db",
                "--format",
                "{{.Status}}",
            ],
            check=False,
        )
        if result.returncode != 0 or "Up" not in result.stdout:
            logger.info("Container not running yet, waiting...")
            time.sleep(wait_seconds)
            continue

        # Check if PostgreSQL is accepting connections
        result = exec_command(
            ["docker", "exec", "leadfactory_e2e_db", "pg_isready", "-U", "postgres"],
            check=False,
        )

        if result.returncode == 0 and "accepting connections" in result.stdout:
            logger.info("✅ Database is accepting connections")
            return True

        logger.info(f"Database not ready yet, waiting {wait_seconds} seconds...")
        time.sleep(wait_seconds)

    logger.error(f"❌ Database did not become ready after {max_attempts} attempts")
    return False


def setup_schema():
    """Initialize the database schema"""
    logger.info("Setting up database schema...")

    # First check if our scripts exist in the container
    result = exec_command(
        [
            "docker",
            "exec",
            "leadfactory_e2e_db",
            "ls",
            "-la",
            "/docker-entrypoint-initdb.d/",
        ],
        check=False,
    )

    if result.returncode != 0 or "01-schema.sql" not in result.stdout:
        logger.error("❌ Schema initialization files not found in container")
        return False

    # Execute schema script
    logger.info("Executing schema initialization script...")
    result = exec_command(
        [
            "docker",
            "exec",
            "leadfactory_e2e_db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "leadfactory",
            "-f",
            "/docker-entrypoint-initdb.d/01-schema.sql",
        ],
        check=False,
    )

    if result.returncode != 0:
        logger.error(f"❌ Failed to initialize schema: {result.stderr}")
        return False

    # Execute seed data script
    logger.info("Loading seed data...")
    result = exec_command(
        [
            "docker",
            "exec",
            "leadfactory_e2e_db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "leadfactory",
            "-f",
            "/docker-entrypoint-initdb.d/02-seed-data.sql",
        ],
        check=False,
    )

    if result.returncode != 0:
        logger.error(f"❌ Failed to load seed data: {result.stderr}")
        return False

    logger.info("✅ Database schema and seed data initialized")
    return True


def verify_tables():
    """Verify that all required tables exist and have data"""
    logger.info("Verifying database tables...")

    required_tables = [
        "businesses",
        "emails",
        "llm_logs",
        "zip_queue",
        "verticals",
        "assets",
    ]
    success = True

    for table in required_tables:
        query = f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='{table}');"
        result = exec_command(
            [
                "docker",
                "exec",
                "leadfactory_e2e_db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "leadfactory",
                "-t",
                "-c",
                query,
            ],
            check=False,
        )

        if result.returncode != 0 or "t" not in result.stdout.lower():
            logger.error(f"❌ Table {table} not found")
            success = False
        else:
            logger.info(f"✅ Table {table} exists")

    # Check if zip_queue has data
    result = exec_command(
        [
            "docker",
            "exec",
            "leadfactory_e2e_db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "leadfactory",
            "-t",
            "-c",
            "SELECT COUNT(*) FROM zip_queue;",
        ],
        check=False,
    )

    if result.returncode != 0:
        logger.error("❌ Failed to query zip_queue table")
        success = False
    elif "0" in result.stdout.strip():
        logger.error("❌ zip_queue table is empty")
        success = False
    else:
        count = result.stdout.strip()
        logger.info(f"✅ zip_queue table has {count} rows")

    return success


def update_env_file():
    """Update the .env.e2e file with the database connection string"""
    logger.info("Updating .env.e2e file with database connection string...")

    # Create the connection string
    connection_string = "postgresql://postgres:postgres@localhost:5433/leadfactory"  # pragma: allowlist secret

    # Create .env.e2e if it doesn't exist
    if not ENV_FILE.exists():
        logger.info(f"Creating new {ENV_FILE.name} file...")
        ENV_FILE.touch()

    # Read existing content
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    lines = content.splitlines()

    # Find DATABASE_URL line if it exists
    db_url_line = None
    for i, line in enumerate(lines):
        if line.startswith("DATABASE_URL="):
            db_url_line = i
            break

    # Update or add the DATABASE_URL
    if db_url_line is not None:
        lines[db_url_line] = f"DATABASE_URL={connection_string}"
    else:
        lines.append(f"DATABASE_URL={connection_string}")

    # Write back to file
    ENV_FILE.write_text("\n".join(lines) + "\n")
    logger.info(f"✅ Updated {ENV_FILE.name} with DATABASE_URL={connection_string}")
    return True


def main():
    """Main function to set up the E2E PostgreSQL database"""
    logger.info("Starting E2E PostgreSQL database setup...")

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_container()
        return 0

    # Check prerequisites
    check_prereqs()

    # Stop any existing container
    stop_container()

    # Start container
    if not start_container():
        logger.error("❌ Failed to start database container")
        return 1

    # Set up schema
    if not setup_schema():
        logger.error("❌ Failed to set up database schema")
        return 1

    # Verify tables
    if not verify_tables():
        logger.error("❌ Database verification failed")
        return 1

    # Update .env.e2e file
    if not update_env_file():
        logger.error("❌ Failed to update .env.e2e file")
        return 1

    logger.info("✅ E2E PostgreSQL database setup completed successfully!")
    logger.info("You can now run E2E tests against this database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
