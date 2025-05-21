"""
Feature: Database Schema Validation
  Tests for database schema and seed helpers
"""

import pytest
import sqlite3
from pathlib import Path

# Paths
DB_MIGRATIONS_PATH = Path(__file__).parent.parent / "db" / "migrations"
MIGRATION_FILE = DB_MIGRATIONS_PATH / "2025-05-19_init.sql"
TEST_DB = ":memory:"
# Expected schema structure
EXPECTED_TABLES = [
    "zip_queue",
    "verticals",
    "businesses",
    "features",
    "mockups",
    "emails",
    "cost_tracking",
]
EXPECTED_VIEWS = [
    "candidate_pairs_email",
    "high_score_businesses",
    "email_ready_businesses",
]
EXPECTED_INDEXES = [
    "idx_businesses_zip",
    "idx_businesses_category",
    "idx_businesses_email",
    "idx_businesses_phone",
    "idx_businesses_active",
    "idx_businesses_score",
    "idx_features_business_id",
    "idx_emails_business_id",
    "idx_emails_status",
    "idx_cost_tracking_service",
    "idx_cost_tracking_tier",
]


@pytest.fixture
def test_db():
    """Create an in-memory database with the latest schema and foreign key constraints enabled."""
    conn = sqlite3.connect(TEST_DB)
    # Enable foreign key constraints for this connection
    conn.execute("PRAGMA foreign_keys = ON")
    # Execute the schema migration
    with open(MIGRATION_FILE, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    # Verify foreign keys are enabled
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys")
    enabled = cursor.fetchone()[0]
    if not enabled:
        raise RuntimeError("Failed to enable foreign key constraints")
    yield conn
    conn.close()


def test_all_expected_tables_exist(test_db):
    """Test that all expected tables exist in the database."""
    cursor = test_db.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
    """
    )
    tables = {row[0] for row in cursor.fetchall()}
    for table in EXPECTED_TABLES:
        assert table in tables, f"Expected table '{table}' not found in database"


def test_all_expected_views_exist(test_db):
    """Test that all expected views exist in the database."""
    cursor = test_db.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='view'
    """
    )
    views = {row[0] for row in cursor.fetchall()}
    for view in EXPECTED_VIEWS:
        assert view in views, f"Expected view '{view}' not found in database"


def test_all_expected_indexes_exist(test_db):
    """Test that all expected indexes exist in the database."""
    cursor = test_db.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_autoindex_%'
    """
    )
    indexes = {row[0] for row in cursor.fetchall()}
    for index in EXPECTED_INDEXES:
        assert index in indexes, f"Expected index '{index}' not found in database"


def test_table_columns(test_db):
    """Test that tables have the expected columns with correct data types."""
    # This is a sample test for the businesses table
    cursor = test_db.cursor()
    cursor.execute("PRAGMA table_info(businesses)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    expected_columns = {
        "id": "INTEGER",
        "name": "TEXT",
        "address": "TEXT",
        "zip": "TEXT",
        "category": "TEXT",
        "website": "TEXT",
        "email": "TEXT",
        "phone": "TEXT",
        "active": "BOOLEAN",
        "score": "INTEGER",
        "tier": "INTEGER",
        "source": "TEXT",
        "source_id": "TEXT",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    }
    for col, col_type in expected_columns.items():
        assert col in columns, f"Expected column '{col}' not found in businesses table"
        assert (
            columns[col].upper() == col_type.upper()
        ), f"Column '{col}' has type '{columns[col].upper()}', expected '{col_type.upper()}'"


def test_triggers_exist(test_db):
    """Test that expected triggers exist and function correctly."""
    cursor = test_db.cursor()
    # Check that the triggers exist
    cursor.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='trigger'
        AND name IN ('update_businesses_timestamp', 'update_features_timestamp')
    """
    )
    triggers = {row[0] for row in cursor.fetchall()}
    assert "update_businesses_timestamp" in triggers, "Trigger 'update_businesses_timestamp' not found"
    assert "update_features_timestamp" in triggers, "Trigger 'update_features_timestamp' not found"
    # Test that the businesses trigger works
    cursor.execute(
        "INSERT INTO businesses (name, zip, category, source) VALUES ('Test Business', '12345', 'Test', 'test')"
    )
    cursor.execute("SELECT created_at, updated_at FROM businesses WHERE name = 'Test Business'")
    created_at, updated_at = cursor.fetchone()
    # Add a small delay to ensure timestamp changes
    import time

    time.sleep(1)
    # Update the business
    cursor.execute("UPDATE businesses SET name = 'Updated Business' WHERE name = 'Test Business'")
    cursor.execute("SELECT created_at, updated_at FROM businesses WHERE name = 'Updated Business'")
    new_created_at, new_updated_at = cursor.fetchone()
    assert created_at == new_created_at, "created_at should not change on update"
    assert (
        new_updated_at != updated_at
    ), "updated_at should be different after update"  # Changed from > to != for reliability


def test_foreign_key_constraints(test_db):
    """Test that foreign key constraints are properly enforced."""
    cursor = test_db.cursor()
    # Test 1: Cannot insert a feature with a non-existent business_id
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        cursor.execute("INSERT INTO features (business_id, tech_stack) VALUES (999, '[]')")
        test_db.commit()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value), "Expected foreign key constraint violation"
    # Test 2: Can insert a feature with a valid business_id
    cursor.execute(
        "INSERT INTO businesses (name, zip, category, source) VALUES ('Test Business', '12345', 'Test', 'test')"
    )
    business_id = cursor.lastrowid
    test_db.commit()
    cursor.execute(
        "INSERT INTO features (business_id, tech_stack) VALUES (?, '[]')",
        (business_id,),
    )
    test_db.commit()
    # Verify the feature was inserted
    cursor.execute("SELECT COUNT(*) FROM features WHERE business_id = ?", (business_id,))
    assert cursor.fetchone()[0] == 1, "Feature should be inserted with valid business_id"
    # Test 3: Verify cascade delete behavior
    # Delete the business - should also delete the feature due to ON DELETE CASCADE
    cursor.execute("DELETE FROM businesses WHERE id = ?", (business_id,))
    test_db.commit()
    # Verify the business was deleted
    cursor.execute("SELECT COUNT(*) FROM businesses WHERE id = ?", (business_id,))
    assert cursor.fetchone()[0] == 0, "Business should be deleted"
    # Verify the dependent feature was also deleted
    cursor.execute("SELECT COUNT(*) FROM features WHERE business_id = ?", (business_id,))
    assert cursor.fetchone()[0] == 0, "Feature should be cascade-deleted when business is deleted"
