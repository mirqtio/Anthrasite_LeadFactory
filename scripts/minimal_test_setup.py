#!/usr/bin/env python3
"""
Minimal Test Environment Setup

This script sets up a minimal test environment with essential directories,
environment variables, and database schema for testing. It focuses on the
bare minimum required for tests to run and includes robust error handling.

Usage:
    python scripts/minimal_test_setup.py [--skip-db] [--verbose]
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def setup_test_environment(skip_db=False, verbose=False):
    """Set up the minimal test environment with essential directories and variables."""
    try:
        logger.info("Starting minimal test environment setup...")

        # Get project root directory
        project_root = Path(__file__).parent.parent

        # Create essential directories
        logger.info("Setting up essential test directories...")
        directories = [
            project_root / "test_results",
            project_root / "data",
            project_root / "logs",
        ]

        for directory in directories:
            directory.mkdir(exist_ok=True)
            logger.info(f"Created directory: {directory}")

        # Set up essential environment variables
        logger.info("Setting up essential environment variables...")
        os.environ["TEST_MODE"] = "True"
        logger.info("Set TEST_MODE=True")

        os.environ["MOCK_EXTERNAL_APIS"] = "True"
        logger.info("Set MOCK_EXTERNAL_APIS=True")

        os.environ["LOG_DIR"] = str(project_root / "logs")
        logger.info(f"Set LOG_DIR={os.environ['LOG_DIR']}")

        os.environ["DATA_DIR"] = str(project_root / "data")
        logger.info(f"Set DATA_DIR={os.environ['DATA_DIR']}")

        os.environ["DATABASE_URL"] = f"sqlite:///{project_root / 'data' / 'test.db'}"
        logger.info(f"Set DATABASE_URL={os.environ['DATABASE_URL']}")

        # Set up test database schema and mock data
        if not skip_db:
            logger.info("Setting up test database schema and mock data...")
            db_setup_script = project_root / "scripts" / "minimal_db_setup.py"

            if not db_setup_script.exists():
                logger.error(f"Database setup script not found: {db_setup_script}")
                return False

            cmd = [sys.executable, str(db_setup_script)]
            if verbose:
                cmd.append("--verbose")

            try:
                logger.info(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                if verbose and result.stdout:
                    logger.info(f"Database setup output:\n{result.stdout}")
                logger.info("Database setup completed successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Database setup failed: {e}")
                if e.stdout:
                    logger.error(f"STDOUT: {e.stdout}")
                if e.stderr:
                    logger.error(f"STDERR: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"Error running database setup: {e}")
                return False
        else:
            logger.info("Skipping database setup as requested")

        logger.info("Minimal test environment setup complete!")
        return True
    except Exception as e:
        logger.error(f"Error setting up test environment: {e}")
        return False


def main():
    """Main function with error handling."""
    try:
        parser = argparse.ArgumentParser(description="Minimal Test Environment Setup")
        parser.add_argument(
            "--skip-db", action="store_true", help="Skip database setup"
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose logging"
        )

        args = parser.parse_args()

        if args.verbose:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        success = setup_test_environment(skip_db=args.skip_db, verbose=args.verbose)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
