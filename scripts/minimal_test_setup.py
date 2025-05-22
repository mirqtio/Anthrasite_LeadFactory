#!/usr/bin/env python3
"""
Minimal Test Environment Setup

This script sets up the minimal necessary environment for running tests in CI.
It focuses on essential directories and configuration with robust error handling.

Usage:
    python scripts/minimal_test_setup.py
"""

import json
import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def setup_directories():
    """Create only essential directories for tests with error handling."""
    logger.info("Setting up essential test directories...")

    # Project root
    project_root = Path(__file__).parent.parent

    # Create only essential directories
    essential_directories = [
        project_root / "test_results",
        project_root / "data",
        project_root / "logs",
    ]

    for directory in essential_directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {e}")
            # Continue with other directories even if one fails

    return project_root


def setup_environment_variables():
    """Set up essential environment variables for tests."""
    logger.info("Setting up essential environment variables...")

    # Set only essential environment variables
    essential_env_vars = {
        "TEST_MODE": "True",
        "MOCK_EXTERNAL_APIS": "True",
        "LOG_DIR": str(Path(__file__).parent.parent / "logs"),
        "DATA_DIR": str(Path(__file__).parent.parent / "data"),
    }

    # Set environment variables
    for key, value in essential_env_vars.items():
        try:
            os.environ[key] = value
            logger.info(f"Set {key}={value}")
        except Exception as e:
            logger.error(f"Error setting environment variable {key}: {e}")

    # Check if DATABASE_URL is already set (e.g., by CI)
    if "DATABASE_URL" not in os.environ:
        # Use SQLite as fallback
        db_path = Path(__file__).parent.parent / "data" / "test.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        logger.info(f"Set DATABASE_URL=sqlite:///{db_path}")


def main():
    """Main function with error handling."""
    try:
        logger.info("Starting minimal test environment setup...")

        # Setup essential directories
        project_root = setup_directories()

        # Setup essential environment variables
        setup_environment_variables()

        logger.info("Minimal test environment setup complete!")
        return 0
    except Exception as e:
        logger.error(f"Error setting up test environment: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
