#!/usr/bin/env python3
"""
E2E Database Management Script

This script manages the E2E testing PostgreSQL database:
- Starts the Docker container
- Waits for the database to be ready
- Validates the connection and schema
- Provides helper functions for other scripts to use
"""

import os
import sys
import time
import subprocess
import argparse
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/e2e_db.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("e2e_db")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.e2e.yml"


def run_command(command, check=True, shell=False, cwd=None):
    """Run a command and return the result, logging the output"""
    logger.info(f"Running command: {command}")

    # Handle both string and list commands
    if isinstance(command, str):
        if shell:
            cmd = command
        else:
            cmd = command.split()
    else:  # command is already a list
        cmd = command

    try:
        result = subprocess.run(
            cmd,
            check=check,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd or str(PROJECT_ROOT),
        )
        logger.info(f"Command succeeded with output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e.stderr.strip()}")
        if check:
            logger.error(f"Exit code: {e.returncode}")
            sys.exit(e.returncode)
        return e


def start_database():
    """Start the E2E database container"""
    logger.info("Starting E2E database container...")

    # Check if docker is available
    try:
        run_command("docker --version")
    except Exception as e:
        logger.error(f"Docker is not available: {e}")
        sys.exit(1)

    # Check if docker-compose file exists
    if not DOCKER_COMPOSE_FILE.exists():
        logger.error(f"Docker compose file not found: {DOCKER_COMPOSE_FILE}")
        sys.exit(1)

    # Start the container with docker-compose
    result = run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} up -d", check=False)

    if result.returncode != 0:
        logger.error("Failed to start database container")
        logger.error(f"Error: {result.stderr}")
        sys.exit(1)

    logger.info("Database container started, waiting for it to be ready...")
    return wait_for_database()


def wait_for_database(max_attempts=30, wait_seconds=2):
    """Wait for the database to be ready"""
    logger.info(
        f"Waiting for database to be ready (max {max_attempts} attempts, {wait_seconds}s between attempts)..."
    )

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Connection attempt {attempt}/{max_attempts}")

        # Check container health
        result = run_command(
            "docker inspect leadfactory_e2e_db --format='{{.State.Health.Status}}'",
            check=False,
        )

        if result.returncode == 0 and "healthy" in result.stdout:
            logger.info("Database container is healthy")
            return True

        # Use psql to test connection directly
        result = run_command(
            "docker exec leadfactory_e2e_db pg_isready -U postgres", check=False
        )

        if result.returncode == 0:
            logger.info("Database is accepting connections")

            # Test if we can query the database
            result = run_command(
                "docker exec leadfactory_e2e_db psql -U postgres -d leadfactory -c \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';\"",
                check=False,
            )

            if result.returncode == 0:
                logger.info("Successfully connected to database and executed query")
                logger.info("Database tables found:")
                logger.info(result.stdout)
                return True

        logger.info(f"Database not ready yet, waiting {wait_seconds} seconds...")
        time.sleep(wait_seconds)

    logger.error(f"Database did not become ready after {max_attempts} attempts")
    return False


def stop_database():
    """Stop the E2E database container"""
    logger.info("Stopping E2E database container...")
    run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} down", check=False)
    logger.info("Database container stopped")


def validate_schema():
    """Validate the database schema"""
    logger.info("Validating database schema...")

    # Check if our initialization scripts exist where expected
    result = run_command(
        "docker exec leadfactory_e2e_db ls -la /docker-entrypoint-initdb.d/",
        check=False,
    )

    if result.returncode != 0 or "01-schema.sql" not in result.stdout:
        logger.error("Schema initialization files not found in container")
        logger.error(f"Directory contents: {result.stdout}")
        return False

    # Manually execute our schema script to ensure tables are created
    logger.info("Executing schema initialization script...")
    result = run_command(
        "docker exec leadfactory_e2e_db bash -c 'psql -U postgres -d leadfactory -f /docker-entrypoint-initdb.d/01-schema.sql'",
        check=False,
    )

    if "already exists" in result.stderr:
        logger.info("Tables already exist, schema is initialized")
    elif result.returncode != 0 and "ERROR" in result.stderr:
        logger.error(f"Failed to initialize schema: {result.stderr}")
        return False
    else:
        logger.info("Schema initialized successfully")

    # Manually execute our seed data script
    logger.info("Executing seed data script...")
    result = run_command(
        "docker exec leadfactory_e2e_db bash -c 'psql -U postgres -d leadfactory -f /docker-entrypoint-initdb.d/02-seed-data.sql'",
        check=False,
    )

    if result.returncode != 0 and "ERROR" in result.stderr:
        logger.error(f"Failed to seed data: {result.stderr}")
        return False
    else:
        logger.info("Seed data loaded successfully")

    # Check if zip_queue table has data
    logger.info("Checking if zip_queue table has data...")
    result = run_command(
        [
            "docker",
            "exec",
            "leadfactory_e2e_db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "leadfactory",
            "-c",
            "SELECT COUNT(*) FROM zip_queue;",
        ],
        check=False,
        shell=False,
    )

    if result.returncode != 0:
        logger.error(f"Error querying zip_queue: {result.stderr}")
        return False
    else:
        logger.info(f"zip_queue query result: {result.stdout}")
        if "0" in result.stdout and "rows" in result.stdout:
            logger.error("zip_queue table is empty")
            return False

    # Verify all required tables exist
    required_tables = [
        "businesses",
        "emails",
        "llm_logs",
        "zip_queue",
        "verticals",
        "assets",
    ]
    all_tables_exist = True

    for table in required_tables:
        result = run_command(
            [
                "docker",
                "exec",
                "leadfactory_e2e_db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "leadfactory",
                "-c",
                f"SELECT to_regclass('{table}');",
            ],
            check=False,
            shell=False,
        )

        if table in result.stdout:
            logger.info(f"Table verified: {table}")
        else:
            logger.error(f"Missing table: {table}")
            all_tables_exist = False

    if not all_tables_exist:
        logger.error("Some required tables are missing")
        return False

    logger.info(
        "Schema validation successful - all required tables exist and have data"
    )
    return True


def get_connection_string():
    """Return the connection string for the E2E database"""
    return "postgresql://postgres:postgres@localhost:5432/leadfactory"


def update_env_file():
    """Update the .env.e2e file with the database connection string"""
    env_file = PROJECT_ROOT / ".env.e2e"

    if not env_file.exists():
        logger.warning(".env.e2e file not found, creating it")
        env_file.touch()

    # Read existing content
    content = env_file.read_text() if env_file.exists() else ""
    lines = content.splitlines()

    # Find DATABASE_URL line if it exists
    db_url_line = None
    for i, line in enumerate(lines):
        if line.startswith("DATABASE_URL="):
            db_url_line = i
            break

    # Update or add the DATABASE_URL
    connection_string = get_connection_string()
    if db_url_line is not None:
        lines[db_url_line] = f"DATABASE_URL={connection_string}"
    else:
        lines.append(f"DATABASE_URL={connection_string}")

    # Write back to file
    env_file.write_text("\n".join(lines) + "\n")
    logger.info(f"Updated {env_file} with DATABASE_URL={connection_string}")


def main():
    """Main function to handle command line arguments"""
    parser = argparse.ArgumentParser(description="Manage E2E testing database")

    parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "validate"],
        help="Action to perform on the database",
    )

    args = parser.parse_args()

    if args.action == "start":
        if start_database():
            if validate_schema():
                update_env_file()
                logger.info("Database started and validated successfully")
                sys.exit(0)
            else:
                logger.error("Database schema validation failed")
                sys.exit(1)
        else:
            logger.error("Failed to start database")
            sys.exit(1)

    elif args.action == "stop":
        stop_database()

    elif args.action == "restart":
        stop_database()
        if start_database():
            if validate_schema():
                update_env_file()
                logger.info("Database restarted and validated successfully")
                sys.exit(0)
            else:
                logger.error("Database schema validation failed")
                sys.exit(1)
        else:
            logger.error("Failed to restart database")
            sys.exit(1)

    elif args.action == "validate":
        if wait_for_database():
            if validate_schema():
                logger.info("Database validation successful")
                sys.exit(0)
            else:
                logger.error("Database schema validation failed")
                sys.exit(1)
        else:
            logger.error("Database is not ready")
            sys.exit(1)


if __name__ == "__main__":
    main()
