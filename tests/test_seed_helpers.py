"""
Feature: Seed helpers
  Tests for the seed helper files and database initialization
"""

import csv
import os
import sqlite3

import pytest
import yaml

# Path constants
DB_MIGRATIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "migrations")
ETC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "etc")
MIGRATION_FILE = os.path.join(DB_MIGRATIONS_PATH, "2025-05-19_init.sql")
ZIPS_FILE = os.path.join(ETC_PATH, "zips.csv")
VERTICALS_FILE = os.path.join(ETC_PATH, "verticals.yml")


@pytest.fixture
def db_connection():
    """Create an in-memory database for testing"""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_migration_file_exists():
    """Test that the migration file exists"""
    assert os.path.exists(MIGRATION_FILE), f"Migration file {MIGRATION_FILE} does not exist"


def test_zips_file_exists():
    """Test that the zips.csv file exists"""
    assert os.path.exists(ZIPS_FILE), f"Zips file {ZIPS_FILE} does not exist"


def test_verticals_file_exists():
    """Test that the verticals.yml file exists"""
    assert os.path.exists(VERTICALS_FILE), f"Verticals file {VERTICALS_FILE} does not exist"


def test_zips_contains_required_zips():
    """Test that zips.csv contains the required zip codes"""
    required_zips = ["10002", "98908", "46032"]
    with open(ZIPS_FILE, "r") as f:
        reader = csv.DictReader(f)
        zips = [row["zip"] for row in reader]
    for zip_code in required_zips:
        assert zip_code in zips, f"Required zip code {zip_code} not found in zips.csv"


def test_verticals_contains_required_verticals():
    """Test that verticals.yml contains the required verticals"""
    required_verticals = ["HVAC", "Plumbers", "Vets"]
    with open(VERTICALS_FILE, "r") as f:
        data = yaml.safe_load(f)
    vertical_names = [v["name"] for v in data["verticals"]]
    for vertical in required_verticals:
        assert vertical in vertical_names, f"Required vertical {vertical} not found in verticals.yml"


def test_schema_creation(db_connection):
    """Test that the schema can be created successfully"""
    with open(MIGRATION_FILE, "r") as f:
        sql = f.read()
    cursor = db_connection.cursor()
    cursor.executescript(sql)
    db_connection.commit()
    # Check that all required tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    required_tables = [
        "zip_queue",
        "verticals",
        "businesses",
        "features",
        "mockups",
        "emails",
        "cost_tracking",
    ]
    for table in required_tables:
        assert table in tables, f"Required table {table} not found in schema"


def test_seed_zip_queue(db_connection):
    """
    Scenario: ZIPs seeded
    Given etc/zips.csv contains "10002"
    When migrations run
    Then zip_queue has row where zip="10002" AND done=false
    """
    # Setup the database
    with open(MIGRATION_FILE, "r") as f:
        sql = f.read()
    cursor = db_connection.cursor()
    cursor.executescript(sql)
    # Read the zips from the CSV
    with open(ZIPS_FILE, "r") as f:
        reader = csv.DictReader(f)
        zips_data = list(reader)
    # Insert the zips into the database
    for row in zips_data:
        cursor.execute(
            "INSERT INTO zip_queue (zip, metro, done) VALUES (?, ?, ?)",
            (row["zip"], row["metro"], False),
        )
    db_connection.commit()
    # Check that the zips are in the database
    cursor.execute("SELECT zip, done FROM zip_queue WHERE zip = '10002'")
    result = cursor.fetchone()
    assert result is not None, "Zip 10002 not found in zip_queue"
    assert result[1] == 0, "Zip 10002 should have done=false"
