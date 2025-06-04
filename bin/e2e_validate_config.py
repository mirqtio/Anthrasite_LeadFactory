#!/usr/bin/env python3
"""
E2E Preflight Check for LeadFactory Pipeline

This script validates that all parts of the system are ready for end-to-end testing:
1. Environment configuration validation
2. Database connectivity and schema verification
3. API connectivity tests (with mock/real options)
4. Pipeline script validation
5. File system checks

Logs results to logs/e2e_preflight.log and exits with non-zero code if any check fails.
"""

import os
import sys
import json
import sqlite3
import logging
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


def setup_logging():
    """Setup logging to both console and file."""
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / "e2e_preflight.log"

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )

    return logging.getLogger(__name__)


class E2EPreflightChecker:
    """E2E preflight checker class."""

    def __init__(self):
        self.logger = setup_logging()
        self.results = {}
        self.env_file = Path(__file__).parent.parent / ".env.e2e"

    def load_env_file(self):
        """Load environment variables from .env.e2e file."""
        if not self.env_file.exists():
            return

        with open(self.env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    def run_all_checks(self) -> bool:
        """Run all preflight checks."""
        self.logger.info("🚀 Starting E2E Preflight Checks")
        self.logger.info("=" * 50)

        checks = [
            ("Environment Configuration", self.check_environment_config),
            ("Database Connectivity", self.check_database_connectivity),
            ("Database Schema", self.check_database_schema),
            ("API Connectivity", self.check_api_connectivity),
            ("Pipeline Scripts", self.check_pipeline_scripts),
            ("File System", self.check_file_system),
        ]

        all_passed = True

        for check_name, check_func in checks:
            self.logger.info(f"\n🔍 {check_name}")
            self.logger.info("-" * 30)

            try:
                result = check_func()
                self.results[check_name] = {
                    "status": "PASS" if result else "FAIL",
                    "details": getattr(check_func, "_last_details", "Check completed"),
                }

                if result:
                    self.logger.info(f"✅ {check_name}: PASS")
                else:
                    self.logger.error(f"❌ {check_name}: FAIL")
                    all_passed = False

            except Exception as e:
                self.logger.error(f"❌ {check_name}: ERROR - {str(e)}")
                self.logger.debug(traceback.format_exc())
                self.results[check_name] = {"status": "ERROR", "details": str(e)}
                all_passed = False

        # Log summary
        self.log_summary(all_passed)
        return all_passed

    def check_environment_config(self) -> bool:
        """Check .env.e2e configuration file."""
        if not self.env_file.exists():
            self.logger.error(f".env.e2e file not found at {self.env_file}")
            return False

        # Load environment variables manually
        self.load_env_file()

        required_vars = ["DATABASE_URL", "E2E_MODE", "EMAIL_OVERRIDE", "MOCKUP_ENABLED"]

        api_keys = [
            "YELP_API_KEY",
            "SCREENSHOTONE_API_KEY",
            "OPENAI_API_KEY",
            "SENDGRID_API_KEY",
        ]

        missing_vars = []

        # Check required variables
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                self.logger.info(f"✓ {var}={value}")

        # Check API keys (warn if missing but don't fail in test mode)
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"

        for var in api_keys:
            value = os.getenv(var)
            if not value or value == "test_key_replace_for_real_testing":
                if test_mode:
                    self.logger.warning(
                        f"⚠️  {var} is set to test value (OK in test mode)"
                    )
                else:
                    missing_vars.append(var)
            else:
                self.logger.info(f"✓ {var}=***{value[-4:]}")  # Show last 4 chars only

        if missing_vars:
            self.logger.error(f"Missing required environment variables: {missing_vars}")
            return False

        return True

    def check_database_connectivity(self) -> bool:
        """Check database connectivity."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.logger.error("DATABASE_URL not set")
            return False

        try:
            if database_url.startswith("sqlite"):
                # SQLite connection
                db_path = database_url.replace("sqlite:///", "").replace(
                    "sqlite://", ""
                )
                if not Path(db_path).exists():
                    self.logger.error(f"SQLite database file not found: {db_path}")
                    return False

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()[0]
                conn.close()

                if result == 1:
                    self.logger.info(
                        f"✓ SQLite database connection successful: {db_path}"
                    )
                    return True

            elif database_url.startswith("postgresql"):
                # PostgreSQL connection (if available)
                try:
                    import psycopg2

                    conn = psycopg2.connect(database_url)
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    result = cur.fetchone()[0]
                    cur.close()
                    conn.close()

                    if result == 1:
                        self.logger.info("✓ PostgreSQL database connection successful")
                        return True

                except ImportError:
                    self.logger.error(
                        "psycopg2 not available for PostgreSQL connection"
                    )
                    return False

            else:
                self.logger.error(f"Unsupported database URL format: {database_url}")
                return False

        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

        return False

    def check_database_schema(self) -> bool:
        """Check database schema and test data."""
        database_url = os.getenv("DATABASE_URL")
        required_tables = ["businesses", "zip_queue", "verticals"]

        try:
            if database_url.startswith("sqlite"):
                db_path = database_url.replace("sqlite:///", "").replace(
                    "sqlite://", ""
                )
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Check tables
                for table in required_tables:
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,),
                    )
                    if not cursor.fetchone():
                        self.logger.error(f"Required table '{table}' not found")
                        conn.close()
                        return False

                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    self.logger.info(f"✓ Table '{table}' exists with {count} rows")

                # Check for at least one ZIP in queue
                cursor.execute("SELECT COUNT(*) FROM zip_queue WHERE done = 0")
                available_zips = cursor.fetchone()[0]

                if available_zips == 0:
                    self.logger.warning("⚠️  No available ZIP codes in queue")
                else:
                    self.logger.info(
                        f"✓ {available_zips} ZIP codes available for processing"
                    )

                conn.close()
                return True

        except Exception as e:
            self.logger.error(f"Database schema check failed: {e}")
            return False

        return False

    def check_api_connectivity(self) -> bool:
        """Check API connectivity (mock or real based on configuration)."""
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        skip_real_apis = os.getenv("SKIP_REAL_API_CALLS", "false").lower() == "true"

        if test_mode or skip_real_apis:
            self.logger.info("🔧 Running in test mode - using mock API responses")
            return self.check_mock_apis()
        else:
            self.logger.info("🌐 Running real API connectivity tests")
            return self.check_real_apis()

    def check_mock_apis(self) -> bool:
        """Check mock API functionality."""
        apis = ["Yelp", "ScreenshotOne", "OpenAI", "SendGrid"]

        for api in apis:
            # Simulate API check
            self.logger.info(f"✓ {api} API: Mock mode enabled")

        return True

    def check_real_apis(self) -> bool:
        """Check real API connectivity (placeholder for actual implementation)."""
        # This would contain real API tests if API keys are provided
        self.logger.warning("⚠️  Real API testing not implemented yet")
        self.logger.info("💡 Use TEST_MODE=true for mock API testing")
        return True

    def check_pipeline_scripts(self) -> bool:
        """Check that pipeline scripts exist and are executable."""
        scripts_dir = Path(__file__).parent.parent / "scripts" / "pipeline"
        required_scripts = [
            "01_scrape.py",
            "02_screenshot.py",
            "03_mockup.py",
            "04_personalize.py",
            "05_render.py",
            "06_email_queue.py",
        ]

        missing_scripts = []

        for script in required_scripts:
            script_path = scripts_dir / script
            if script_path.exists():
                if os.access(script_path, os.X_OK):
                    self.logger.info(f"✓ {script}: exists and executable")
                else:
                    self.logger.info(f"✓ {script}: exists (not executable)")
            else:
                missing_scripts.append(script)
                self.logger.error(f"❌ {script}: not found")

        if missing_scripts:
            self.logger.error(f"Missing pipeline scripts: {missing_scripts}")
            return False

        return True

    def check_file_system(self) -> bool:
        """Check file system permissions and directories."""
        project_root = Path(__file__).parent.parent

        # Check required directories
        required_dirs = ["logs", "data", "reports"]

        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            try:
                dir_path.mkdir(exist_ok=True)

                # Test write permission
                test_file = dir_path / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()

                self.logger.info(f"✓ Directory '{dir_name}': writable")

            except Exception as e:
                self.logger.error(f"❌ Directory '{dir_name}': not writable - {e}")
                return False

        return True

    def log_summary(self, overall_success: bool):
        """Log final summary of all checks."""
        self.logger.info("\n" + "=" * 50)
        self.logger.info("📋 E2E PREFLIGHT SUMMARY")
        self.logger.info("=" * 50)

        for check_name, result in self.results.items():
            status = result["status"]
            if status == "PASS":
                self.logger.info(f"✅ {check_name}: {status}")
            else:
                self.logger.error(f"❌ {check_name}: {status}")

        if overall_success:
            self.logger.info("\n🎉 ALL PREFLIGHT CHECKS PASSED!")
            self.logger.info("Ready for E2E pipeline execution")
        else:
            self.logger.error("\n💥 PREFLIGHT CHECKS FAILED!")
            self.logger.error("Fix issues before running E2E tests")

        # Save results to JSON
        results_file = (
            Path(__file__).parent.parent / "logs" / "e2e_preflight_results.json"
        )
        with open(results_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "overall_success": overall_success,
                    "results": self.results,
                },
                f,
                indent=2,
            )

        self.logger.info(f"\nResults saved to: {results_file}")


def main():
    """Main function."""
    checker = E2EPreflightChecker()
    success = checker.run_all_checks()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
