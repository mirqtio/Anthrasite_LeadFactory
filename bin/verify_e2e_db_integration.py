#!/usr/bin/env python3
"""
E2E Database Integration Verification Script

This script tests the integration between the application and the E2E PostgreSQL database
by using the application's database connector module. It verifies:
1. Loading of .env.e2e configuration
2. Database connection using the application's connector
3. Basic query execution and transaction handling
4. Schema validation
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set E2E_MODE environment variable
os.environ["E2E_MODE"] = "true"

# Import the application's database connector
from leadfactory.utils import e2e_db_connector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/e2e_integration.log"),
    ],
)
logger = logging.getLogger("e2e_integration")

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)


def test_env_loading():
    """Test loading of .env.e2e configuration"""
    logger.info("Testing .env.e2e loading...")

    # Clear any existing DATABASE_URL
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]

    # Load E2E environment
    success = e2e_db_connector.load_e2e_env()

    if not success:
        logger.error("Failed to load .env.e2e configuration")
        return False

    # Check DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set after loading .env.e2e")
        return False

    logger.info(f"Loaded DATABASE_URL: {db_url}")
    logger.info("✅ .env.e2e loading test passed")
    return True


def test_connection():
    """Test database connection"""
    logger.info("Testing database connection...")

    try:
        # Check connection
        success = e2e_db_connector.check_connection()

        if not success:
            logger.error("Database connection check failed")
            return False

        logger.info("✅ Database connection test passed")
        return True
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return False


def test_query_execution():
    """Test query execution"""
    logger.info("Testing query execution...")

    try:
        # Execute a simple query
        results = e2e_db_connector.execute_query(
            "SELECT zip, city, state FROM zip_queue LIMIT 3;"
        )

        if not results or len(results) == 0:
            logger.error("Query returned no results")
            return False

        logger.info(f"Query results: {results}")

        # Execute a transaction
        success = e2e_db_connector.execute_transaction(
            [
                (
                    "INSERT INTO businesses (name, address, city, state, zip, phone, email, website, vertical) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
                    (
                        "Integration Test Business",
                        "123 Test Ave",
                        "Test City",
                        "TS",
                        "12345",
                        "555-123-4567",
                        "integration@test.com",
                        "https://test.com",
                        "retail",
                    ),
                ),
                (
                    "SELECT COUNT(*) FROM businesses WHERE name = %s;",
                    ("Integration Test Business",),
                ),
            ]
        )

        if not success:
            logger.error("Transaction execution failed")
            return False

        # Verify the inserted business
        results = e2e_db_connector.execute_query(
            "SELECT id, name FROM businesses WHERE name = %s;",
            ("Integration Test Business",),
        )

        if not results or len(results) == 0:
            logger.error("Failed to find inserted business")
            return False

        business_id = results[0][0]
        logger.info(f"Inserted business ID: {business_id}")

        logger.info("✅ Query execution test passed")
        return True
    except Exception as e:
        logger.error(f"Error testing query execution: {e}")
        return False


def test_schema_validation():
    """Test schema validation"""
    logger.info("Testing schema validation...")

    try:
        success = e2e_db_connector.validate_schema()

        if not success:
            logger.error("Schema validation failed")
            return False

        logger.info("✅ Schema validation test passed")
        return True
    except Exception as e:
        logger.error(f"Error testing schema validation: {e}")
        return False


def main():
    """Main function to verify E2E database integration"""
    logger.info("Starting E2E database integration verification...")

    tests = [
        ("Loading .env.e2e configuration", test_env_loading),
        ("Database connection", test_connection),
        ("Query execution", test_query_execution),
        ("Schema validation", test_schema_validation),
    ]

    all_passed = True

    for test_name, test_func in tests:
        logger.info(f"Running test: {test_name}")
        success = test_func()

        if not success:
            logger.error(f"❌ Test failed: {test_name}")
            all_passed = False
        else:
            logger.info(f"✅ Test passed: {test_name}")

    if all_passed:
        logger.info("✅ All integration tests passed!")
        return 0
    else:
        logger.error("❌ Some integration tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
