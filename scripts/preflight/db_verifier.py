"""
Database Connectivity Verifier Module

This module validates connectivity to the PostgreSQL database
used for E2E testing, ensuring:
1. Database connection can be established
2. Required tables exist
3. Schema integrity is maintained
4. Test data is properly seeded

Usage:
    from scripts.preflight.db_verifier import DbVerifier

    # Create verifier
    verifier = DbVerifier()

    # Run verification
    result = verifier.verify_database()

    if result.success:
        print("Database connectivity and schema verified!")
    else:
        print(f"Database verification failed: {result.message}")
        for issue in result.issues:
            print(f"- {issue}")
"""

import os
import sys
import logging
import psycopg2
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env.e2e"


@dataclass
class DbVerificationResult:
    """Result of a database verification operation"""

    success: bool
    message: str
    issues: List[str] = None
    tables_verified: List[str] = None
    rows_verified: Dict[str, int] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.tables_verified is None:
            self.tables_verified = []
        if self.rows_verified is None:
            self.rows_verified = {}


class DbVerifier:
    """
    Verifies database connectivity and schema for E2E testing

    This class checks that the PostgreSQL database is accessible,
    has the required tables, and contains the necessary test data.
    """

    # Required tables for E2E testing
    REQUIRED_TABLES = [
        "businesses",
        "emails",
        "llm_logs",
        "zip_queue",
        "verticals",
        "assets",
        "schema_migrations",
    ]

    # Minimum number of rows required in specific tables
    MIN_ROWS = {"businesses": 1, "zip_queue": 3, "verticals": 3}

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize the database verifier

        Args:
            env_file: Path to the environment file with database connection info (default: .env.e2e)
        """
        self.env_file = Path(env_file) if env_file else ENV_FILE
        self.db_url = None
        self.conn = None
        self._load_db_url()

    def _load_db_url(self) -> None:
        """Load database connection URL from environment or file"""
        # First try environment variable
        self.db_url = os.getenv("DATABASE_URL", "")

        # If not in environment, try loading from file
        if not self.db_url and self.env_file.exists():
            logger.info(f"Loading database URL from {self.env_file}")

            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    try:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        if key == "DATABASE_URL":
                            self.db_url = value
                            break
                    except ValueError:
                        continue

        if not self.db_url:
            logger.error("Database URL not found in environment or file")
            self.db_url = None

    def _connect_to_db(self) -> Tuple[bool, Optional[str]]:
        """
        Connect to the database

        Returns:
            Tuple of (success, error_message)
        """
        if not self.db_url:
            return False, "Database URL not found"

        try:
            logger.info(f"Connecting to database: {self.db_url}")
            self.conn = psycopg2.connect(self.db_url)

            # Test connection
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                logger.info(f"Connected to: {version}")

            return True, None
        except Exception as e:
            error_message = f"Database connection error: {str(e)}"
            logger.error(error_message)
            self.conn = None
            return False, error_message

    def _close_connection(self) -> None:
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def _verify_tables(self) -> Tuple[bool, List[str], List[str]]:
        """
        Verify that required tables exist

        Returns:
            Tuple of (success, tables_verified, missing_tables)
        """
        if not self.conn:
            return False, [], self.REQUIRED_TABLES

        tables_verified = []
        missing_tables = []

        try:
            with self.conn.cursor() as cursor:
                for table in self.REQUIRED_TABLES:
                    cursor.execute(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=%s);",
                        (table,),
                    )
                    exists = cursor.fetchone()[0]

                    if exists:
                        logger.info(f"✅ Table {table} exists")
                        tables_verified.append(table)
                    else:
                        logger.error(f"❌ Table {table} does not exist")
                        missing_tables.append(table)

            return len(missing_tables) == 0, tables_verified, missing_tables
        except Exception as e:
            error_message = f"Error verifying tables: {str(e)}"
            logger.error(error_message)
            return (
                False,
                tables_verified,
                list(set(self.REQUIRED_TABLES) - set(tables_verified)),
            )

    def _verify_row_counts(self) -> Tuple[bool, Dict[str, int], List[str]]:
        """
        Verify that tables have the minimum required number of rows

        Returns:
            Tuple of (success, row_counts, issues)
        """
        if not self.conn:
            return False, {}, [f"No database connection to verify row counts"]

        row_counts = {}
        issues = []

        try:
            with self.conn.cursor() as cursor:
                for table, min_rows in self.MIN_ROWS.items():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table};")
                        count = cursor.fetchone()[0]
                        row_counts[table] = count

                        if count < min_rows:
                            issue = f"Table {table} has {count} rows, needs at least {min_rows}"
                            logger.error(f"❌ {issue}")
                            issues.append(issue)
                        else:
                            logger.info(f"✅ Table {table} has {count} rows")
                    except Exception as e:
                        # Skip tables that don't exist or have other errors
                        logger.warning(
                            f"Could not check row count for table {table}: {e}"
                        )

            return len(issues) == 0, row_counts, issues
        except Exception as e:
            error_message = f"Error verifying row counts: {str(e)}"
            logger.error(error_message)
            return False, row_counts, [error_message]

    def _verify_sample_data(self) -> Tuple[bool, List[str]]:
        """
        Verify that sample data exists in the database

        Returns:
            Tuple of (success, issues)
        """
        if not self.conn:
            return False, ["No database connection to verify sample data"]

        issues = []

        try:
            with self.conn.cursor() as cursor:
                try:
                    # Verify ZIP codes
                    cursor.execute(
                        "SELECT COUNT(*) FROM zip_queue WHERE zip IN ('90210', '10001', '60601');"
                    )
                    count = cursor.fetchone()[0]

                    if count < 3:
                        issue = f"Missing sample ZIP codes in zip_queue"
                        logger.error(f"❌ {issue}")
                        issues.append(issue)
                    else:
                        logger.info("✅ Sample ZIP codes verified")
                except Exception as e:
                    logger.warning(f"Could not verify ZIP codes: {e}")
                    issues.append("Could not verify ZIP codes")

                try:
                    # Verify business verticals
                    cursor.execute(
                        "SELECT COUNT(*) FROM verticals WHERE name IN ('restaurant', 'retail', 'salon');"
                    )
                    count = cursor.fetchone()[0]

                    if count < 3:
                        issue = f"Missing sample verticals in verticals table"
                        logger.error(f"❌ {issue}")
                        issues.append(issue)
                    else:
                        logger.info("✅ Sample verticals verified")
                except Exception as e:
                    logger.warning(f"Could not verify business verticals: {e}")
                    issues.append("Could not verify business verticals")

                try:
                    # Verify schema migrations
                    cursor.execute(
                        "SELECT COUNT(*) FROM schema_migrations WHERE version = '001_initial_schema';"
                    )
                    count = cursor.fetchone()[0]

                    if count == 0:
                        issue = f"Missing initial schema migration record"
                        logger.error(f"❌ {issue}")
                        issues.append(issue)
                    else:
                        logger.info("✅ Schema migration record verified")
                except Exception as e:
                    logger.warning(f"Could not verify schema migrations: {e}")
                    issues.append("Could not verify schema migrations")

            return len(issues) == 0, issues
        except Exception as e:
            error_message = f"Error verifying sample data: {str(e)}"
            logger.error(error_message)
            return False, [error_message]

    def generate_sample_env_file(self, output_path: str) -> None:
        """Generate a sample .env file with required database configuration.

        Args:
            output_path: Path to write the sample .env file to
        """
        logger.info(f"Generating sample database configuration file at {output_path}")

        sample_config = """
# Database Configuration for E2E Tests
# ----------------------------------

# Database Connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory
DB_HOST=localhost
DB_PORT=5433
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=leadfactory

# Database Docker Container
DB_CONTAINER_NAME=leadfactory-postgres
DB_CONTAINER_PORT=5433

# Database Schema Settings
DB_MIN_TABLES=6
DB_REQUIRED_TABLES=businesses,emails,llm_logs,zip_queue,verticals,assets

# Database Testing Settings
MOCKUP_ENABLED=false
E2E_MODE=true
"""

        try:
            with open(output_path, "w") as f:
                f.write(sample_config.strip())
            logger.info(f"✅ Sample database configuration written to {output_path}")
        except IOError as e:
            logger.error(f"Failed to write sample database configuration: {str(e)}")

    def verify_database(self) -> DbVerificationResult:
        """
        Verify database connectivity and schema

        This method connects to the database, verifies the tables exist,
        checks row counts, and validates sample data.

        Returns:
            DbVerificationResult with verification results
        """
        logger.info("Starting database verification...")

        all_issues = []
        tables_verified = []
        row_counts = {}

        # Connect to database
        connection_success, connection_error = self._connect_to_db()
        if not connection_success:
            logger.error(f"Database connection failed: {connection_error}")
            # Always close connection, even if it failed
            self._close_connection()
            return DbVerificationResult(
                success=False,
                message="Database connection failed",
                issues=[connection_error],
            )

        # Verify tables
        tables_success, tables_verified, missing_tables = self._verify_tables()
        if not tables_success:
            all_issues.extend([f"Missing table: {table}" for table in missing_tables])

        # Verify row counts
        rows_success, row_counts, row_issues = self._verify_row_counts()
        if not rows_success:
            all_issues.extend(row_issues)

        # Verify sample data
        data_success, data_issues = self._verify_sample_data()
        if not data_success:
            all_issues.extend(data_issues)

        # Close connection
        self._close_connection()

        # Generate result
        if connection_success and tables_success and rows_success and data_success:
            logger.info("✅ Database verification successful")
            return DbVerificationResult(
                success=True,
                message="Database verification successful",
                tables_verified=tables_verified,
                rows_verified=row_counts,
            )
        else:
            logger.error("❌ Database verification failed")
            for issue in all_issues:
                logger.error(f"  - {issue}")

            return DbVerificationResult(
                success=False,
                message="Database verification failed",
                issues=all_issues,
                tables_verified=tables_verified,
                rows_verified=row_counts,
            )

    def verify_docker_container(self) -> DbVerificationResult:
        """
        Verify that the Docker container for the database is running

        Returns:
            DbVerificationResult with verification results
        """
        logger.info("Verifying database Docker container...")

        import subprocess

        try:
            # Check if Docker is available
            try:
                result = subprocess.run(
                    ["docker", "--version"], capture_output=True, text=True, check=True
                )
                logger.info(f"Docker version: {result.stdout.strip()}")
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.error("Docker command not found or failed")
                return DbVerificationResult(
                    success=False,
                    message="Docker command not found or failed",
                    issues=["Docker is not installed or not in PATH"],
                )

            # Check if the container is running
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=leadfactory_e2e_db",
                    "--format",
                    "{{.Status}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            container_status = result.stdout.strip()

            if container_status:
                logger.info(f"✅ Database container is running: {container_status}")
                return DbVerificationResult(
                    success=True,
                    message=f"Database container is running: {container_status}",
                )
            else:
                # Check if the container exists but is not running
                result = subprocess.run(
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        "name=leadfactory_e2e_db",
                        "--format",
                        "{{.Status}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                container_status = result.stdout.strip()

                if container_status:
                    logger.error(
                        f"❌ Database container exists but is not running: {container_status}"
                    )
                    return DbVerificationResult(
                        success=False,
                        message="Database container exists but is not running",
                        issues=[f"Container status: {container_status}"],
                    )
                else:
                    logger.error("❌ Database container does not exist")
                    return DbVerificationResult(
                        success=False,
                        message="Database container does not exist",
                        issues=[
                            "Container 'leadfactory_e2e_db' not found, run setup_e2e_postgres.py to create it"
                        ],
                    )
        except Exception as e:
            error_message = f"Error verifying Docker container: {str(e)}"
            logger.error(error_message)
            return DbVerificationResult(
                success=False,
                message="Error verifying Docker container",
                issues=[error_message],
            )


def main():
    """Command-line interface for the database verifier"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify database connectivity and schema for E2E testing"
    )
    parser.add_argument(
        "--env-file",
        help="Path to the environment file with database connection info (default: .env.e2e)",
    )
    parser.add_argument(
        "--container",
        action="store_true",
        help="Verify the Docker container instead of database connectivity",
    )

    args = parser.parse_args()

    # Create verifier
    verifier = DbVerifier(env_file=args.env_file)

    # Run verification
    if args.container:
        result = verifier.verify_docker_container()
    else:
        result = verifier.verify_database()

    # Print results
    print("\n" + "=" * 80)
    print(" DATABASE VERIFICATION RESULTS ".center(80, "="))
    print("=" * 80)

    if result.success:
        print(f"\n✅ {result.message}")

        if result.tables_verified:
            print("\nVerified Tables:")
            for table in result.tables_verified:
                row_count = result.rows_verified.get(table, "N/A")
                print(f"  - {table}: {row_count} rows")
    else:
        print(f"\n❌ {result.message}")

        if result.issues:
            print("\nIssues:")
            for issue in result.issues:
                print(f"  - {issue}")

        if result.tables_verified:
            print("\nVerified Tables:")
            for table in result.tables_verified:
                row_count = result.rows_verified.get(table, "N/A")
                print(f"  - {table}: {row_count} rows")

    print("\n" + "=" * 80)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
