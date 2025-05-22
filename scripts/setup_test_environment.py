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
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Create schema directory if it doesn't exist
    schema_dir = project_root / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    
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
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        has_multiple_locations BOOLEAN DEFAULT 0,
        features TEXT
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
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_opt_outs (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY,
        metric_name TEXT NOT NULL,
        metric_value REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cost_tracking (
        id INTEGER PRIMARY KEY,
        service TEXT NOT NULL,
        operation TEXT NOT NULL,
        cost REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_queue (
        id INTEGER PRIMARY KEY,
        business_id INTEGER NOT NULL,
        template TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sent_at TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS html_storage (
        id INTEGER PRIMARY KEY,
        business_id INTEGER NOT NULL,
        html TEXT NOT NULL,
        url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_id) REFERENCES businesses(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS llm_logs (
        id INTEGER PRIMARY KEY,
        model TEXT NOT NULL,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        tokens INTEGER NOT NULL,
        cost REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create views needed for tests
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS business_metrics AS
    SELECT b.id, b.name, b.score, COUNT(e.id) as email_count
    FROM businesses b
    LEFT JOIN email_queue e ON b.id = e.business_id
    GROUP BY b.id
    """)
    
    # Create indexes needed for tests
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_score ON businesses(score)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status)")
    
    # Create triggers needed for tests
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS update_business_timestamp
    AFTER UPDATE ON businesses
    FOR EACH ROW
    BEGIN
        UPDATE businesses SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """)
    
    # Insert test data for businesses with features
    cursor.execute("""
    INSERT INTO businesses (name, address, city, state, zip, vertical, has_multiple_locations, features, score, status)
    VALUES 
        ('Test Business 1', '123 Main St', 'San Francisco', 'CA', '94105', 'healthcare', 1, 
         '{"tech_stack": {"WordPress": {"version": "5.8"}, "PHP": {"version": "7.2.0"}}, "page_speed": 85}', 75, 'pending'),
        ('Test Business 2', '456 Market St', 'San Francisco', 'CA', '94105', 'legal', 0, 
         '{"tech_stack": {"Wix": {"version": "1.0"}, "JavaScript": {"version": "ES6"}}, "page_speed": 65}', 50, 'pending'),
        ('Test Business 3', '789 Howard St', 'San Francisco', 'CA', '94105', 'financial', 1, 
         '{"tech_stack": {"React": {"version": "17.0"}, "Node.js": {"version": "14.0"}}, "page_speed": 90}', 85, 'pending')
    """)
    
    # Insert test data for candidate_duplicate_pairs
    cursor.execute("""
    INSERT INTO candidate_duplicate_pairs (business_id_1, business_id_2, similarity_score, status)
    VALUES 
        (1, 2, 0.75, 'pending'),
        (1, 3, 0.50, 'review')
    """)
    
    # Insert test data for email_opt_outs
    cursor.execute("""
    INSERT INTO email_opt_outs (email, reason)
    VALUES 
        ('optout@example.com', 'Not interested'),
        ('unsubscribe@example.com', 'Requested removal')
    """)
    
    # Insert test data for metrics
    cursor.execute("""
    INSERT INTO metrics (metric_name, metric_value)
    VALUES 
        ('bounce_rate', 0.015),
        ('spam_rate', 0.0005),
        ('cost_per_lead', 2.50),
        ('batch_completion', 0.85),
        ('gpu_usage', 0.0)
    """)
    
    # Insert test data for cost_tracking
    cursor.execute("""
    INSERT INTO cost_tracking (service, operation, cost)
    VALUES 
        ('openai', 'text-generation', 0.05),
        ('anthropic', 'text-generation', 0.08),
        ('google', 'places-api', 0.01),
        ('yelp', 'business-search', 0.02)
    """)
    
    # Insert test data for email_queue
    cursor.execute("""
    INSERT INTO email_queue (business_id, template, status)
    VALUES 
        (1, 'initial_outreach', 'pending'),
        (2, 'initial_outreach', 'sent'),
        (3, 'follow_up', 'pending')
    """)
    
    # Insert test data for html_storage
    cursor.execute("""
    INSERT INTO html_storage (business_id, html, url)
    VALUES 
        (1, '<html><body><h1>Test Business 1</h1><p>Healthcare provider</p></body></html>', 'https://example.com/business1'),
        (2, '<html><body><h1>Test Business 2</h1><p>Legal services</p></body></html>', 'https://example.com/business2')
    """)
    
    # Insert test data for llm_logs
    cursor.execute("""
    INSERT INTO llm_logs (model, prompt, response, tokens, cost)
    VALUES 
        ('gpt-4', 'Generate a mockup for Test Business 1', 'Here is a mockup for Test Business 1...', 150, 0.03),
        ('claude-3', 'Generate a mockup for Test Business 2', 'Here is a mockup for Test Business 2...', 200, 0.04)
    """)
    
    # Insert test data for scaling_gate
    cursor.execute("""
    INSERT INTO scaling_gate (active, reason)
    VALUES (0, 'Scaling gate is inactive')
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
    
    # Project root
    project_root = Path(__file__).parent.parent
    
    # Set environment variables
    env_vars = {
        # Email deliverability thresholds
        "BOUNCE_RATE_THRESHOLD": "0.02",
        "SPAM_RATE_THRESHOLD": "0.001",
        "MONTHLY_BUDGET": "250",
        
        # SendGrid configuration
        "SENDGRID_IP_POOL_NAMES": "primary,secondary,tertiary",
        "SENDGRID_SUBUSER_NAMES": "primary,secondary,tertiary",
        "SENDGRID_API_KEY": "mock_sendgrid_key",
        
        # API keys
        "YELP_API_KEY": "mock_yelp_key",
        "GOOGLE_PLACES_API_KEY": "mock_google_key",
        "OPENAI_API_KEY": "mock_openai_key",
        "ANTHROPIC_API_KEY": "mock_anthropic_key",
        
        # Directory paths
        "LOG_DIR": str(project_root / "logs"),
        "DATA_DIR": str(project_root / "data"),
        "HTML_STORAGE_DIR": str(project_root / "data" / "html_storage"),
        "LLM_LOGS_DIR": str(project_root / "data" / "llm_logs"),
        
        # Scaling gate configuration
        "SCALING_GATE_LOCKFILE": str(project_root / "data" / "mock" / "scaling_gate.lock"),
        "SCALING_GATE_HISTORY_FILE": str(project_root / "data" / "mock" / "scaling_gate_history.json"),
        
        # Test configuration
        "TEST_MODE": "True",
        "MOCK_EXTERNAL_APIS": "True",
        
        # Feature flags
        "HEALTH_CHECK_FAILURES_THRESHOLD": "2",
        "GPU_BURST": "0",
        
        # Rule engine configuration
        "RULES_FILE": str(project_root / "data" / "mock" / "rules.yml"),
        
        # Email configuration
        "EMAIL_FROM": "test@example.com",
        "EMAIL_REPLY_TO": "noreply@example.com",
        "PHYSICAL_ADDRESS": "123 Test St, San Francisco, CA 94105",
        
        # Database configuration - set in setup_test_database
        # "DATABASE_URL": "sqlite:///path/to/test.db",
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
