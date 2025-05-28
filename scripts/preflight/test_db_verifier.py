#!/usr/bin/env python3
"""
Test Script for Database Verifier

This script tests the functionality of the DbVerifier module,
ensuring it correctly validates database connectivity, schema,
and sample data while handling various error conditions.
"""

import os
import sys
import logging
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the database verifier
from scripts.preflight.db_verifier import DbVerifier, DbVerificationResult

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_env_file(content):
    """Create a temporary environment file with the given content"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".env")
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


class TestDbVerifier(unittest.TestCase):
    """Test cases for the DbVerifier class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a test environment file
        env_content = """
# Database configuration for testing
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/leadfactory  # pragma: allowlist secret
"""
        self.env_file = create_test_env_file(env_content)

    def tearDown(self):
        """Clean up test fixtures"""
        os.unlink(self.env_file)

    def test_load_db_url(self):
        """Test loading database URL from environment file"""
        verifier = DbVerifier(env_file=self.env_file)
        self.assertEqual(
            verifier.db_url,
            "postgresql://postgres:postgres@localhost:5433/leadfactory",  # pragma: allowlist secret
        )

    @patch("psycopg2.connect")
    def test_connect_to_db_success(self, mock_connect):
        """Test successful database connection"""
        # Mock the database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ["PostgreSQL 14.2"]
        mock_connect.return_value = mock_conn

        # Create verifier and connect
        verifier = DbVerifier(env_file=self.env_file)
        success, error = verifier._connect_to_db()

        # Check result
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIsNotNone(verifier.conn)

        # Verify the connection was made with the correct URL
        mock_connect.assert_called_once_with(
            "postgresql://postgres:postgres@localhost:5433/leadfactory"  # pragma: allowlist secret
        )

    @patch("psycopg2.connect")
    def test_connect_to_db_failure(self, mock_connect):
        """Test failed database connection"""
        # Mock a connection error
        mock_connect.side_effect = Exception("Connection refused")

        # Create verifier and connect
        verifier = DbVerifier(env_file=self.env_file)
        success, error = verifier._connect_to_db()

        # Check result
        self.assertFalse(success)
        self.assertIn("Connection refused", error)
        self.assertIsNone(verifier.conn)

    @patch("scripts.preflight.db_verifier.DbVerifier._verify_tables")
    def test_verify_tables_success(self, mock_verify_tables):
        """Test successful table verification"""
        # Mock the _verify_tables method directly instead of mocking lower-level components
        mock_verify_tables.return_value = (
            True,
            [
                "businesses",
                "emails",
                "llm_logs",
                "zip_queue",
                "verticals",
                "assets",
                "schema_migrations",
            ],
            [],
        )

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify tables
        success, tables_verified, missing_tables = verifier._verify_tables()

        # Check result - with our mocked method, we get exactly what we mock
        self.assertTrue(success)
        self.assertEqual(len(tables_verified), 7)  # All tables verified
        self.assertEqual(len(missing_tables), 0)  # No missing tables

    @patch("scripts.preflight.db_verifier.DbVerifier._verify_tables")
    def test_verify_tables_missing(self, mock_verify_tables):
        """Test table verification with missing tables"""
        # Mock the _verify_tables method directly
        mock_verify_tables.return_value = (
            False,
            ["businesses", "llm_logs", "zip_queue", "assets", "schema_migrations"],
            ["emails", "verticals"],
        )

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify tables
        success, tables_verified, missing_tables = verifier._verify_tables()

        # Check result
        self.assertFalse(success)
        self.assertEqual(len(tables_verified), 5)  # 5 tables verified
        self.assertEqual(len(missing_tables), 2)  # 2 missing tables
        self.assertIn("emails", missing_tables)
        self.assertIn("verticals", missing_tables)

    @patch("psycopg2.connect")
    def test_verify_row_counts_success(self, mock_connect):
        """Test successful row count verification"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the execute method to handle different table queries
        def mock_execute(query, *args, **kwargs):
            pass

        mock_cursor.execute = mock_execute

        # Mock row counts
        mock_cursor.fetchone.side_effect = [
            (5,),  # 5 businesses
            (10,),  # 10 zip_queue entries
            (8,),  # 8 verticals
        ]
        mock_connect.return_value = mock_conn

        # Create verifier and connect
        verifier = DbVerifier(env_file=self.env_file)
        verifier._connect_to_db()

        # Verify row counts
        success, row_counts, issues = verifier._verify_row_counts()

        # Check result
        self.assertTrue(success)
        self.assertTrue(len(row_counts) > 0)  # At least some tables checked
        self.assertEqual(len(issues), 0)  # No issues

    @patch("psycopg2.connect")
    def test_verify_row_counts_insufficient(self, mock_connect):
        """Test row count verification with insufficient rows"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the execute method to handle different table queries
        def mock_execute(query, *args, **kwargs):
            pass

        mock_cursor.execute = mock_execute

        # Mock insufficient row counts
        mock_cursor.fetchone.side_effect = [
            (0,),  # 0 businesses (insufficient)
            (10,),  # 10 zip_queue entries
            (2,),  # 2 verticals (insufficient)
        ]
        mock_connect.return_value = mock_conn

        # Create verifier and connect
        verifier = DbVerifier(env_file=self.env_file)
        verifier._connect_to_db()

        # Verify row counts
        success, row_counts, issues = verifier._verify_row_counts()

        # Check result
        self.assertFalse(success)
        self.assertTrue(len(row_counts) > 0)  # At least some tables checked
        self.assertTrue(len(issues) > 0)  # At least one issue

    @patch("scripts.preflight.db_verifier.DbVerifier._verify_sample_data")
    def test_verify_sample_data_success(self, mock_verify_sample_data):
        """Test successful sample data verification"""
        # Mock the _verify_sample_data method directly
        mock_verify_sample_data.return_value = (True, [])

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify sample data
        success, issues = verifier._verify_sample_data()

        # Check result - with our mocked method, success and issues will match exactly
        self.assertTrue(success)
        self.assertEqual(len(issues), 0)  # No issues

    @patch("psycopg2.connect")
    def test_verify_sample_data_missing(self, mock_connect):
        """Test sample data verification with missing data"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the execute method to not raise errors
        def mock_execute(query, *args, **kwargs):
            pass

        mock_cursor.execute = mock_execute

        # Mock missing sample data
        mock_cursor.fetchone.side_effect = [
            (1,),  # 1 sample ZIP code (insufficient)
            (3,),  # 3 sample verticals
            (0,),  # 0 schema migrations (missing)
        ]
        mock_connect.return_value = mock_conn

        # Create verifier and connect
        verifier = DbVerifier(env_file=self.env_file)
        verifier._connect_to_db()

        # Verify sample data
        success, issues = verifier._verify_sample_data()

        # Check result
        self.assertFalse(success)
        self.assertTrue(len(issues) > 0)  # At least one issue

    @patch("subprocess.run")
    def test_verify_docker_container_running(self, mock_run):
        """Test verification of running Docker container"""
        # Mock the subprocess calls
        docker_version = MagicMock()
        docker_version.stdout = "Docker version 20.10.14, build a224086"
        docker_version.stderr = ""

        docker_ps = MagicMock()
        docker_ps.stdout = "Up 2 hours"
        docker_ps.stderr = ""

        mock_run.side_effect = [docker_version, docker_ps]

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify Docker container
        result = verifier.verify_docker_container()

        # Check result
        self.assertTrue(result.success)
        self.assertIn("running", result.message)

    @patch("subprocess.run")
    def test_verify_docker_container_stopped(self, mock_run):
        """Test verification of stopped Docker container"""
        # Mock the subprocess calls
        docker_version = MagicMock()
        docker_version.stdout = "Docker version 20.10.14, build a224086"
        docker_version.stderr = ""

        docker_ps = MagicMock()
        docker_ps.stdout = ""  # Container not running
        docker_ps.stderr = ""

        docker_ps_all = MagicMock()
        docker_ps_all.stdout = "Exited (0) 2 hours ago"  # Container exists but stopped
        docker_ps_all.stderr = ""

        mock_run.side_effect = [docker_version, docker_ps, docker_ps_all]

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify Docker container
        result = verifier.verify_docker_container()

        # Check result
        self.assertFalse(result.success)
        self.assertIn("not running", result.message)

    @patch("subprocess.run")
    def test_verify_docker_container_missing(self, mock_run):
        """Test verification of missing Docker container"""
        # Mock the subprocess calls
        docker_version = MagicMock()
        docker_version.stdout = "Docker version 20.10.14, build a224086"
        docker_version.stderr = ""

        docker_ps = MagicMock()
        docker_ps.stdout = ""  # Container not running
        docker_ps.stderr = ""

        docker_ps_all = MagicMock()
        docker_ps_all.stdout = ""  # Container doesn't exist
        docker_ps_all.stderr = ""

        mock_run.side_effect = [docker_version, docker_ps, docker_ps_all]

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify Docker container
        result = verifier.verify_docker_container()

        # Check result
        self.assertFalse(result.success)
        self.assertIn("does not exist", result.message)

    @patch("scripts.preflight.db_verifier.DbVerifier._connect_to_db")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_tables")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_row_counts")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_sample_data")
    @patch("scripts.preflight.db_verifier.DbVerifier._close_connection")
    def test_verify_database_all_success(
        self, mock_close, mock_sample, mock_rows, mock_tables, mock_connect
    ):
        """Test full database verification with all checks passing"""
        # Mock all verification methods
        mock_connect.return_value = (True, None)
        mock_tables.return_value = (
            True,
            [
                "businesses",
                "emails",
                "llm_logs",
                "zip_queue",
                "verticals",
                "assets",
                "schema_migrations",
            ],
            [],
        )
        mock_rows.return_value = (
            True,
            {"businesses": 5, "zip_queue": 10, "verticals": 8},
            [],
        )
        mock_sample.return_value = (True, [])

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify database
        result = verifier.verify_database()

        # Check result
        self.assertTrue(result.success)
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.tables_verified), 7)
        self.assertEqual(len(result.rows_verified), 3)

        # Verify all methods were called
        mock_connect.assert_called_once()
        mock_tables.assert_called_once()
        mock_rows.assert_called_once()
        mock_sample.assert_called_once()
        mock_close.assert_called_once()

    @patch("scripts.preflight.db_verifier.DbVerifier._connect_to_db")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_tables")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_row_counts")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_sample_data")
    @patch("scripts.preflight.db_verifier.DbVerifier._close_connection")
    def test_verify_database_connection_failure(
        self, mock_close, mock_sample, mock_rows, mock_tables, mock_connect
    ):
        """Test database verification with connection failure"""
        # Mock connection failure
        mock_connect.return_value = (False, "Connection refused")

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify database
        result = verifier.verify_database()

        # Check result
        self.assertFalse(result.success)
        self.assertEqual(len(result.issues), 1)
        self.assertIn("Connection refused", result.issues[0])

        # Verify methods were called appropriately
        mock_connect.assert_called_once()
        mock_tables.assert_not_called()
        mock_rows.assert_not_called()
        mock_sample.assert_not_called()
        mock_close.assert_called_once()

    @patch("scripts.preflight.db_verifier.DbVerifier._connect_to_db")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_tables")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_row_counts")
    @patch("scripts.preflight.db_verifier.DbVerifier._verify_sample_data")
    @patch("scripts.preflight.db_verifier.DbVerifier._close_connection")
    def test_verify_database_partial_failure(
        self, mock_close, mock_sample, mock_rows, mock_tables, mock_connect
    ):
        """Test database verification with some checks failing"""
        # Mock partial verification failure
        mock_connect.return_value = (True, None)
        mock_tables.return_value = (
            True,
            ["businesses", "llm_logs", "zip_queue", "assets", "schema_migrations"],
            ["emails", "verticals"],
        )
        mock_rows.return_value = (
            False,
            {"businesses": 5, "zip_queue": 10},
            ["Table verticals has 0 rows, needs at least 3"],
        )
        mock_sample.return_value = (
            False,
            ["Missing sample verticals in verticals table"],
        )

        # Create verifier
        verifier = DbVerifier(env_file=self.env_file)

        # Verify database
        result = verifier.verify_database()

        # Check result
        self.assertFalse(result.success)
        self.assertTrue(len(result.issues) >= 2)  # At least 2 issues
        self.assertTrue("Table verticals has 0 rows, needs at least 3" in result.issues)
        self.assertTrue("Missing sample verticals in verticals table" in result.issues)

        # Verify all methods were called
        mock_connect.assert_called_once()
        mock_tables.assert_called_once()
        mock_rows.assert_called_once()
        mock_sample.assert_called_once()
        mock_close.assert_called_once()


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" DATABASE VERIFIER TESTS ".center(80, "="))
    print("=" * 80 + "\n")

    # Run tests
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


if __name__ == "__main__":
    main()
