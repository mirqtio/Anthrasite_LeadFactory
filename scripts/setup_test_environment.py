#!/usr/bin/env python3
"""
Setup Test Environment

This script sets up the necessary environment for running tests, including:
- Creating required directories
- Setting up mock data
- Configuring environment variables
- Initializing test databases

Usage:
    python scripts/setup_test_environment.py
"""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

def setup_directories():
    """Create necessary directories for tests."""
    print("Setting up test directories...")
    
    # Project root
    project_root = Path(__file__).parent.parent
    
    # Create directories
    directories = [
        project_root / "data" / "html_storage",
        project_root / "data" / "llm_logs",
        project_root / "test_results",
        project_root / "test_results" / "visualizations",
        project_root / "schema",
        project_root / "logs"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    return project_root

def setup_mock_data(project_root):
    """Set up mock data for tests."""
    print("Setting up mock data...")
    
    # Create mock tech stack data for rule engine tests
    mock_tech_stack = {
        "WordPress": {"version": "5.8"},
        "PHP": {"version": "7.2.0"},
        "MySQL": {"version": "5.7"},
        "Apache": {"version": "2.4"}
    }
    
    # Create mock data directory
    mock_data_dir = project_root / "data" / "mock"
    mock_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Write mock tech stack data
    with open(mock_data_dir / "tech_stack.json", "w") as f:
        json.dump(mock_tech_stack, f)
    
    # Create mock rules file for rule engine tests
    mock_rules = """
settings:
  base_score: 50
  min_score: 0
  max_score: 100
  high_score_threshold: 75
rules:
  - name: "wordpress"
    description: "Business uses WordPress"
    condition:
      tech_stack_contains: "WordPress"
    score: 10
  - name: "outdated_php"
    description: "Site uses PHP version below 7.4"
    condition:
      tech_stack_contains: "PHP"
      tech_stack_version_lt:
        technology: "PHP"
        version: "7.4.0"
    score: 15
multipliers:
  - name: "High Priority Industry"
    description: "Business is in a high priority industry"
    condition:
      vertical_in: ["healthcare", "legal", "financial"]
    multiplier: 1.5
"""
    
    with open(mock_data_dir / "rules.yml", "w") as f:
        f.write(mock_rules)
    
    # Create mock scaling gate history file
    scaling_gate_history = {
        "history": []
    }
    
    with open(mock_data_dir / "scaling_gate_history.json", "w") as f:
        json.dump(scaling_gate_history, f)
    
    print(f"Created mock data in {mock_data_dir}")

def setup_test_database(project_root):
    """Set up test database for tests."""
    print("Setting up test database...")
    
    # Create test database directory
    db_dir = project_root / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Create test database
    db_path = db_dir / "test.db"
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables needed for tests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        phone TEXT,
        website TEXT,
        email TEXT,
        vertical TEXT,
        score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_duplicate_pairs (
        id INTEGER PRIMARY KEY,
        business_id_1 INTEGER NOT NULL,
        business_id_2 INTEGER NOT NULL,
        similarity_score REAL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id_1) REFERENCES businesses(id),
        FOREIGN KEY (business_id_2) REFERENCES businesses(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scaling_gate (
        id INTEGER PRIMARY KEY,
        active BOOLEAN NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Insert some test data
    cursor.execute("""
    INSERT INTO businesses (name, address, city, state, zip, vertical)
    VALUES 
        ('Test Business 1', '123 Main St', 'San Francisco', 'CA', '94105', 'healthcare'),
        ('Test Business 2', '456 Market St', 'San Francisco', 'CA', '94105', 'legal')
    """)
    
    # Commit and close
    conn.commit()
    conn.close()
    
    print(f"Created test database at {db_path}")
    
    # Create database URL environment variable
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    print(f"Set DATABASE_URL environment variable to sqlite:///{db_path}")

def setup_environment_variables():
    """Set up environment variables for tests."""
    print("Setting up environment variables...")
    
    # Set environment variables
    env_vars = {
        "BOUNCE_RATE_THRESHOLD": "0.02",
        "SPAM_RATE_THRESHOLD": "0.001",
        "MONTHLY_BUDGET": "250",
        "SENDGRID_IP_POOL_NAMES": "primary,secondary,tertiary",
        "SENDGRID_SUBUSER_NAMES": "primary,secondary,tertiary",
        "YELP_API_KEY": "mock_yelp_key",
        "GOOGLE_PLACES_API_KEY": "mock_google_key",
        "OPENAI_API_KEY": "mock_openai_key",
        "ANTHROPIC_API_KEY": "mock_anthropic_key",
        "SENDGRID_API_KEY": "mock_sendgrid_key",
        "LOG_DIR": str(Path(__file__).parent.parent / "logs"),
        "SCALING_GATE_LOCKFILE": str(Path(__file__).parent.parent / "data" / "mock" / "scaling_gate.lock"),
        "SCALING_GATE_HISTORY_FILE": str(Path(__file__).parent.parent / "data" / "mock" / "scaling_gate_history.json")
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"Set {key}={value}")

def main():
    """Main function."""
    print("Setting up test environment...")
    
    # Setup directories
    project_root = setup_directories()
    
    # Setup mock data
    setup_mock_data(project_root)
    
    # Setup test database
    setup_test_database(project_root)
    
    # Setup environment variables
    setup_environment_variables()
    
    print("\nTest environment setup complete!")
    print("You can now run tests with:")
    print("  python scripts/test_status_tracker.py --run-tests --test-pattern=\"tests/test_*.py\" --report")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
