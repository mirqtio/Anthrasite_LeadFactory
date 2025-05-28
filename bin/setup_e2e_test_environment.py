#!/usr/bin/env python3
"""
E2E Test Environment Setup Script

This script sets up the complete E2E testing environment:
1. Starts the PostgreSQL Docker container
2. Applies database migrations
3. Seeds test data
4. Validates the database schema
5. Updates the .env.e2e file with necessary configuration
"""

import os
import sys
import logging
import subprocess
import time
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/e2e_setup.log"),
    ],
)
logger = logging.getLogger("e2e_setup")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env.e2e"


def run_command(cmd_list, check=True, log_output=True):
    """Execute a command and return the result"""
    cmd_str = " ".join(cmd_list)
    logger.info(f"Running: {cmd_str}")

    try:
        result = subprocess.run(
            cmd_list,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if log_output and result.stdout.strip():
            logger.info(f"Output: {result.stdout.strip()}")

        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Error: {e.stderr.strip()}")
        if check:
            sys.exit(e.returncode)
        return e


def setup_database():
    """Set up the E2E PostgreSQL database"""
    logger.info("Setting up E2E PostgreSQL database...")

    # Start the database container
    result = run_command(["python3", "bin/setup_e2e_postgres.py"], check=False)
    if result.returncode != 0:
        logger.error("Failed to set up E2E PostgreSQL database")
        return False

    logger.info("✅ E2E PostgreSQL database setup successfully")
    return True


def apply_migrations():
    """Apply database migrations"""
    logger.info("Applying database migrations...")

    result = run_command(
        ["python3", "scripts/db/schema_manager.py", "migrate"], check=False
    )
    if result.returncode != 0:
        logger.error("Failed to apply database migrations")
        return False

    logger.info("✅ Database migrations applied successfully")
    return True


def seed_database():
    """Seed the database with test data"""
    logger.info("Seeding database with test data...")

    result = run_command(
        ["python3", "scripts/db/schema_manager.py", "seed"], check=False
    )
    if result.returncode != 0:
        logger.error("Failed to seed database")
        return False

    logger.info("✅ Database seeded successfully")
    return True


def validate_schema():
    """Validate the database schema"""
    logger.info("Validating database schema...")

    result = run_command(
        ["python3", "scripts/db/schema_manager.py", "validate"], check=False
    )
    if result.returncode != 0:
        logger.error("Failed to validate database schema")
        return False

    logger.info("✅ Database schema validated successfully")
    return True


def update_env_file():
    """Update the .env.e2e file with necessary configuration"""
    logger.info("Updating .env.e2e file...")

    # Create .env.e2e if it doesn't exist
    if not ENV_FILE.exists():
        logger.info(f"Creating new {ENV_FILE.name} file...")
        ENV_FILE.touch()

    # Read existing content
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    lines = content.splitlines()

    # Required variables for E2E testing
    required_vars = {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5433/leadfactory",
        "E2E_MODE": "true",
        "MOCKUP_ENABLED": "true",
        "DEBUG_MODE": "true",
        "ENVIRONMENT": "e2e_testing",
    }

    # Update existing variables or add new ones
    for var, value in required_vars.items():
        var_line = None
        for i, line in enumerate(lines):
            if line.startswith(f"{var}="):
                var_line = i
                break

        if var_line is not None:
            lines[var_line] = f"{var}={value}"
        else:
            lines.append(f"{var}={value}")

    # Write back to file
    ENV_FILE.write_text("\n".join(lines) + "\n")
    logger.info(f"✅ Updated {ENV_FILE.name} with required configuration")
    return True


def verify_connection():
    """Verify the database connection"""
    logger.info("Verifying database connection...")

    result = run_command(["python3", "bin/test_e2e_db_connection.py"], check=False)
    if result.returncode != 0:
        logger.error("Failed to verify database connection")
        return False

    logger.info("✅ Database connection verified successfully")
    return True


def show_summary():
    """Show a summary of the E2E test environment setup"""
    connection_string = "postgresql://postgres:postgres@localhost:5433/leadfactory"

    print("\n" + "=" * 80)
    print(" E2E TEST ENVIRONMENT SETUP SUMMARY ".center(80, "="))
    print("=" * 80)
    print(f"  Database URL:         {connection_string}")
    print(f"  Environment File:     {ENV_FILE}")
    print(f"  Docker Container:     leadfactory_e2e_db")
    print(f"  Port:                 5433")
    print("\nThe E2E test environment is now ready for use.")
    print("To run E2E tests, use the following command:")
    print("\n  python bin/run_e2e_test.py")
    print("\nTo stop the database container:")
    print("\n  python bin/setup_e2e_postgres.py stop")
    print("=" * 80 + "\n")


def main():
    """Main function to set up the E2E test environment"""
    logger.info("Starting E2E test environment setup...")

    steps = [
        ("Setting up database", setup_database),
        ("Applying migrations", apply_migrations),
        ("Seeding database", seed_database),
        ("Validating schema", validate_schema),
        ("Updating environment file", update_env_file),
        ("Verifying connection", verify_connection),
    ]

    all_success = True

    for step_name, step_func in steps:
        logger.info(f"Step: {step_name}")
        success = step_func()
        if not success:
            logger.error(f"❌ Failed at step: {step_name}")
            all_success = False
            break
        logger.info(f"✅ Completed step: {step_name}")

    if all_success:
        logger.info("✅ E2E test environment setup completed successfully!")
        show_summary()
        return 0
    else:
        logger.error("❌ E2E test environment setup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
