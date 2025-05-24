#!/usr/bin/env python
"""
Data Retention Manager
-------------------
This module provides utilities for managing raw data retention in the
Anthrasite LeadFactory platform. It handles storing and retrieving raw HTML,
LLM prompts and completions, and other raw data with configurable retention
periods.

Usage:
    from bin.data_retention import data_retention

    # Store raw HTML
    html_path = data_retention.store_html(business_id, html_content)

    # Log LLM interaction
    data_retention.log_llm_interaction(
        stage="scoring",
        prompt="Rate this business...",
        response="The business scores 8/10...",
        cost=0.12
    )
"""

import gzip
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union

# Add parent directory to path to allow importing supabase client
# Use pathlib for better path handling
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


# Use function to get the module to avoid E402 errors
def _get_supabase():
    from bin.db.supabase_client import supabase

    return supabase


# Create reference to use in the code
supabase = _get_supabase()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(Path("logs") / "data_retention.log")),
    ],
)
logger = logging.getLogger("data_retention")


class DataRetentionManager:
    """Data retention manager for LeadFactory."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize data retention manager.

        Args:
            db_path: Path to SQLite database for data retention
        """
        # Set default database path if not provided
        if not db_path:
            db_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
            )
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "data_retention.db")

        self.db_path = db_path

        # Initialize database
        self._init_db()

        # Load configuration from environment variables
        self.html_retention_days = int(os.environ.get("HTML_RETENTION_DAYS", "90"))
        self.llm_retention_days = int(os.environ.get("LLM_RETENTION_DAYS", "90"))
        self.storage_bucket = os.environ.get("STORAGE_BUCKET", "raw_data")

        # Create local storage directories
        self.local_storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "raw_data",
        )
        os.makedirs(os.path.join(self.local_storage_dir, "html"), exist_ok=True)

        # Start cleanup thread
        self._start_cleanup_thread()

        logger.info(
            f"Data retention manager initialized (html_retention={self.html_retention_days} days, "
            f"llm_retention={self.llm_retention_days} days)"
        )

    def _init_db(self):
        """Initialize the data retention database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create raw_html table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS raw_html (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                size_bytes INTEGER,
                md5_hash TEXT
            )
            """
            )

            # Create llm_logs table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS llm_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                cost REAL,
                timestamp TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                model TEXT,
                tokens INTEGER
            )
            """
            )

            conn.commit()
            conn.close()

            logger.info("Data retention database initialized")
        except Exception as e:
            logger.exception(f"Error initializing database: {e}")

    def store_html(self, business_id: str, html_content: str) -> str:
        """Store raw HTML content for a business.

        Args:
            business_id: Business ID
            html_content: Raw HTML content

        Returns:
            Storage path for the HTML content
        """
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{business_id}_{timestamp}.html.gz"
            storage_path = f"raw_html/{filename}"
            local_path = os.path.join(self.local_storage_dir, "html", filename)

            # Compress HTML content
            with gzip.open(local_path, "wt", encoding="utf-8") as f:
                f.write(html_content)

            # Calculate size and hash
            size_bytes = os.path.getsize(local_path)
            md5_hash = self._calculate_md5(local_path)

            # Upload to Supabase Storage
            with open(local_path, "rb") as f:
                supabase.storage.from_(self.storage_bucket).upload(
                    path=storage_path,
                    file=f,
                    file_options={"content-type": "application/gzip"},
                )

            # Calculate expiration date
            stored_at = datetime.now()
            expires_at = stored_at + timedelta(days=self.html_retention_days)

            # Add to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            INSERT INTO raw_html (business_id, storage_path, stored_at, expires_at, size_bytes, md5_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    business_id,
                    storage_path,
                    stored_at.isoformat(),
                    expires_at.isoformat(),
                    size_bytes,
                    md5_hash,
                ),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Stored HTML for business {business_id} at {storage_path} "
                f"(size={size_bytes} bytes, expires={expires_at.isoformat()})"
            )

            return storage_path
        except Exception as e:
            logger.exception(f"Error storing HTML for business {business_id}: {e}")
            return ""

    def get_html(self, business_id: str) -> Optional[str]:
        """Get the most recent HTML content for a business.

        Args:
            business_id: Business ID

        Returns:
            HTML content or None if not found
        """
        try:
            # Query database for most recent HTML
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            SELECT storage_path FROM raw_html
            WHERE business_id = ? AND expires_at > ?
            ORDER BY stored_at DESC
            LIMIT 1
            """,
                (business_id, datetime.now().isoformat()),
            )

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.warning(f"No HTML found for business {business_id}")
                return None

            storage_path = result[0]

            # Download from Supabase Storage
            try:
                response = supabase.storage.from_(self.storage_bucket).download(
                    storage_path
                )

                # Decompress content
                with gzip.open(response, "rt", encoding="utf-8") as f:
                    html_content = f.read()

                logger.info(
                    f"Retrieved HTML for business {business_id} from {storage_path}"
                )

                return html_content
            except Exception as e:
                logger.error(f"Error downloading HTML from Supabase: {e}")

                # Try local fallback
                local_path = os.path.join(
                    self.local_storage_dir, *storage_path.split("/")
                )

                if os.path.exists(local_path):
                    with gzip.open(local_path, "rt", encoding="utf-8") as f:
                        html_content = f.read()

                    logger.info(
                        f"Retrieved HTML for business {business_id} from local storage"
                    )

                    return html_content

                return None
        except Exception as e:
            logger.exception(f"Error getting HTML for business {business_id}: {e}")
            return None

    def log_llm_interaction(
        self,
        stage: str,
        prompt: str,
        response: str,
        cost: float = 0.0,
        model: str = "gpt-4",
        tokens: int = 0,
    ) -> str:
        """Log an LLM interaction.

        Args:
            stage: Processing stage (e.g., scoring, enrichment)
            prompt: Prompt sent to the LLM
            response: Response from the LLM
            cost: Cost of the interaction in USD
            model: LLM model used
            tokens: Number of tokens used

        Returns:
            Log ID
        """
        try:
            # Generate log ID
            log_id = str(uuid.uuid4())

            # Calculate expiration date
            timestamp = datetime.now()
            expires_at = timestamp + timedelta(days=self.llm_retention_days)

            # Add to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            INSERT INTO llm_logs (log_id, stage, prompt, response, cost, timestamp, expires_at, model, tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log_id,
                    stage,
                    prompt,
                    response,
                    cost,
                    timestamp.isoformat(),
                    expires_at.isoformat(),
                    model,
                    tokens,
                ),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Logged LLM interaction for stage {stage} "
                f"(log_id={log_id}, cost=${cost:.4f}, expires={expires_at.isoformat()})"
            )

            return log_id
        except Exception as e:
            logger.exception(f"Error logging LLM interaction: {e}")
            return ""

    def get_llm_log(self, log_id: str) -> Optional[dict[str, Any]]:
        """Get an LLM interaction log by ID.

        Args:
            log_id: Log ID

        Returns:
            Log data or None if not found
        """
        try:
            # Query database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
            SELECT * FROM llm_logs
            WHERE log_id = ? AND expires_at > ?
            """,
                (log_id, datetime.now().isoformat()),
            )

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.warning(f"No LLM log found for ID {log_id}")
                return None

            # Convert to dictionary
            log_data = dict(result)

            logger.info(f"Retrieved LLM log for ID {log_id}")

            return log_data
        except Exception as e:
            logger.exception(f"Error getting LLM log for ID {log_id}: {e}")
            return None

    def get_llm_logs_for_stage(
        self, stage: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get LLM interaction logs for a specific stage.

        Args:
            stage: Processing stage
            limit: Maximum number of logs to return

        Returns:
            List of log data
        """
        try:
            # Query database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
            SELECT * FROM llm_logs
            WHERE stage = ? AND expires_at > ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
                (stage, datetime.now().isoformat(), limit),
            )

            results = cursor.fetchall()
            conn.close()

            # Convert to list of dictionaries
            logs = [dict(row) for row in results]

            logger.info(f"Retrieved {len(logs)} LLM logs for stage {stage}")

            return logs
        except Exception as e:
            logger.exception(f"Error getting LLM logs for stage {stage}: {e}")
            return []

    def cleanup_expired_data(self):
        """Clean up expired data from database and storage."""
        try:
            now = datetime.now().isoformat()

            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get expired HTML records
            cursor.execute(
                """
            SELECT storage_path FROM raw_html
            WHERE expires_at < ?
            """,
                (now,),
            )

            expired_html_paths = [row[0] for row in cursor.fetchall()]

            # Delete expired HTML from storage
            for path in expired_html_paths:
                try:
                    # Delete from Supabase Storage
                    supabase.storage.from_(self.storage_bucket).remove([path])

                    # Delete local copy
                    local_path = os.path.join(self.local_storage_dir, *path.split("/"))
                    if os.path.exists(local_path):
                        os.remove(local_path)
                except Exception as e:
                    logger.error(f"Error deleting expired HTML at {path}: {e}")

            # Delete expired HTML records from database
            cursor.execute(
                """
            DELETE FROM raw_html
            WHERE expires_at < ?
            """,
                (now,),
            )

            html_deleted = cursor.rowcount

            # Delete expired LLM logs from database
            cursor.execute(
                """
            DELETE FROM llm_logs
            WHERE expires_at < ?
            """,
                (now,),
            )

            llm_deleted = cursor.rowcount

            conn.commit()
            conn.close()

            logger.info(
                f"Cleaned up expired data: {html_deleted} HTML records, {llm_deleted} LLM logs"
            )
        except Exception as e:
            logger.exception(f"Error cleaning up expired data: {e}")

    def _calculate_md5(self, file_path: str) -> str:
        """Calculate MD5 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            MD5 hash as a hexadecimal string
        """
        import hashlib

        md5 = hashlib.md5(usedforsecurity=False)

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)

        return md5.hexdigest()

    def _start_cleanup_thread(self):
        """Start a background thread to clean up expired data periodically."""

        def cleanup_thread():
            while True:
                try:
                    # Sleep first to avoid immediate cleanup on startup
                    time.sleep(3600 * 6)  # Run every 6 hours

                    # Clean up expired data
                    self.cleanup_expired_data()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")

        # Start thread
        thread = threading.Thread(target=cleanup_thread, daemon=True)
        thread.start()
        logger.info("Started data cleanup thread")


# Create a singleton instance
data_retention = DataRetentionManager()

# Example usage
if __name__ == "__main__":
    # Store HTML
    html_content = "<html><body><h1>Test Business</h1></body></html>"
    storage_path = data_retention.store_html("test_business_123", html_content)

    # Log LLM interaction
    log_id = data_retention.log_llm_interaction(
        stage="scoring",
        prompt="Rate this business on a scale of 1-10",
        response="Based on the information provided, I would rate this business as 8/10.",
        cost=0.12,
        model="gpt-4",
        tokens=150,
    )

    # Get LLM log
    log_data = data_retention.get_llm_log(log_id)

    # Clean up expired data
    data_retention.cleanup_expired_data()
