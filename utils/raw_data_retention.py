#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Raw Data Retention
Utilities for storing and retrieving raw HTML and LLM interactions.
"""

import datetime
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Union

# Use lowercase versions for Python 3.9 compatibility
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import database utilities
import contextlib

from utils.io import DatabaseConnection

# Import logging configuration
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Constants
HTML_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "html_storage"
RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))


def ensure_storage_directories() -> None:
    """Ensure storage directories exist."""
    HTML_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured HTML storage directory exists: {HTML_STORAGE_DIR}")


def get_retention_expiry_date() -> datetime.datetime:
    """Get the retention expiry date based on the retention period.

    Returns:
        Datetime object representing when data should expire.
    """
    return datetime.datetime.now() + datetime.timedelta(days=RETENTION_DAYS)


def generate_storage_path(url: str, business_id: int) -> str:
    """Generate a storage path for a URL.

    Args:
        url: URL to generate path for.
        business_id: Business ID associated with the URL.

    Returns:
        Relative path where the HTML should be stored.
    """
    # Parse URL to get domain
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    # Generate a hash of the URL for uniqueness
    # Not for security, just for filename generation.
    url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()

    # Create directory structure: domain/business_id/hash.html.gz
    if domain:
        domain_dir = domain.replace(":", "_").replace(".", "_")
    else:
        domain_dir = "unknown_domain"

    # Changed to pathlib, returns str for DB compatibility
    return str(Path(domain_dir) / str(business_id) / f"{url_hash}.html.gz")


def compress_html(html_content: str) -> tuple[bytes, float]:
    """Compress HTML content using gzip.

    Args:
        html_content: HTML content to compress.

    Returns:
        tuple of (compressed_content, compression_ratio).
    """
    # Convert to bytes if string
    if isinstance(html_content, str):
        html_bytes = html_content.encode("utf-8")
    else:
        html_bytes = html_content

    # Compress using gzip
    compressed = gzip.compress(html_bytes)

    # Calculate compression ratio
    original_size = len(html_bytes)
    compressed_size = len(compressed)
    compression_ratio = (
        (original_size - compressed_size) / original_size if original_size > 0 else 0
    )

    return compressed, compression_ratio


def store_html(html_content: str, url: str, business_id: int) -> Optional[str]:
    """Store HTML content for a URL.

    Args:
        html_content: HTML content to store.
        url: URL the HTML was fetched from.
        business_id: Business ID associated with the URL.

    Returns:
        Path to stored HTML file, or None if storage failed.
    """
    try:
        # Ensure storage directories exist
        ensure_storage_directories()

        # Generate storage path
        relative_path = generate_storage_path(url, business_id)
        full_path = HTML_STORAGE_DIR / relative_path

        # Create directory if it doesn't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Compress HTML
        compressed_content, compression_ratio = compress_html(html_content)

        # Calculate content hash for integrity verification
        content_hash = hashlib.sha256(html_content.encode()).hexdigest()

        # Write compressed content to file
        with full_path.open("wb") as f:
            f.write(compressed_content)

        # Calculate size in bytes
        size_bytes = full_path.stat().st_size

        # Calculate retention expiry date
        retention_expires_at = get_retention_expiry_date()

        # Store metadata in database
        with DatabaseConnection() as cursor:
            # Insert into raw_html_storage table
            if cursor.connection.is_postgres:
                cursor.execute(
                    """
                    INSERT INTO raw_html_storage
                    (business_id, html_path, original_url, compression_ratio,
                     content_hash, size_bytes, retention_expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        business_id,
                        relative_path,
                        url,
                        compression_ratio,
                        content_hash,
                        size_bytes,
                        retention_expires_at,
                    ),
                )
                result = cursor.fetchone()
                # Store the ID for potential future use or logging
                _ = result["id"] if result else None
            else:
                cursor.execute(
                    """
                    INSERT INTO raw_html_storage
                    (business_id, html_path, original_url, compression_ratio,
                     content_hash, size_bytes, retention_expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        business_id,
                        relative_path,
                        url,
                        compression_ratio,
                        content_hash,
                        size_bytes,
                        retention_expires_at,
                    ),
                )
                # Store the ID for potential future use or logging
                _ = cursor.lastrowid

            # Update businesses table with html_path
            if cursor.connection.is_postgres:
                cursor.execute(
                    "UPDATE businesses SET html_path = %s WHERE id = %s",
                    (relative_path, business_id),
                )
            else:
                cursor.execute(
                    "UPDATE businesses SET html_path = ? WHERE id = ?",
                    (relative_path, business_id),
                )

        logger.info(
            f"Stored HTML for URL: {url}, path: {relative_path}, "
            f"size: {size_bytes} bytes, compression ratio: {compression_ratio:.2f}"
        )
        return relative_path

    except Exception as e:
        logger.error(f"Error storing HTML for business {business_id}, URL: {url}: {e}")
        return None


def retrieve_html(html_path: str) -> Optional[str]:
    """Retrieve HTML content from storage.

    Args:
        html_path: Path to stored HTML file.

    Returns:
        HTML content, or None if retrieval failed.
    """
    try:
        # Construct full path
        full_path = HTML_STORAGE_DIR / html_path

        # Check if file exists
        if not full_path.exists():
            logger.error(f"HTML file not found: {full_path}")
            return None

        # Read and decompress file
        with full_path.open("rb") as f:
            compressed_content = f.read()

        # Decompress content
        html_content = gzip.decompress(compressed_content).decode("utf-8")

        logger.debug(f"Retrieved HTML from {html_path}")
        return html_content

    except Exception as e:
        logger.error(f"Error retrieving HTML from {html_path}: {e}")
        return None


def log_llm_interaction(
    operation: str,
    model_version: str,
    prompt_text: str,
    response_json: Union[dict, str],
    business_id: Optional[int] = None,
    tokens_prompt: Optional[int] = None,
    tokens_completion: Optional[int] = None,
    duration_ms: Optional[int] = None,
    status: str = "success",
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Log an LLM interaction.

    Args:
        operation: Type of operation (e.g., 'deduplication', 'mockup_generation').
        model_version: Version of the LLM model used.
        prompt_text: Text of the prompt sent to the LLM.
        response_json: JSON response from the LLM.
        business_id: Business ID associated with the interaction.
        tokens_prompt: Number of tokens in the prompt.
        tokens_completion: Number of tokens in the completion.
        duration_ms: Duration of the interaction in milliseconds.
        status: Status of the interaction (success, error, etc.).
        metadata: Additional metadata for the interaction.

    Returns:
        ID of the log entry, or None if logging failed.
    """
    try:
        # Convert response_json to string if it's a dict
        if isinstance(response_json, dict):
            response_json_str = json.dumps(response_json)
        else:
            response_json_str = response_json

        # Convert metadata to string if it's a dict
        if metadata and isinstance(metadata, dict):
            metadata_str = json.dumps(metadata)
        else:
            metadata_str = None

        # Calculate retention expiry date
        retention_expires_at = get_retention_expiry_date()

        # Store in database
        with DatabaseConnection() as cursor:
            if cursor.connection.is_postgres:
                cursor.execute(
                    """
                    INSERT INTO llm_logs
                    (business_id, operation, model_version, prompt_text, response_json,
                     tokens_prompt, tokens_completion, duration_ms, status,
                     retention_expires_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        business_id,
                        operation,
                        model_version,
                        prompt_text,
                        response_json_str,
                        tokens_prompt,
                        tokens_completion,
                        duration_ms,
                        status,
                        retention_expires_at,
                        metadata_str,
                    ),
                )
                result = cursor.fetchone()
                log_id = result["id"] if result else None
            else:
                cursor.execute(
                    """
                    INSERT INTO llm_logs
                    (business_id, operation, model_version, prompt_text, response_json,
                     tokens_prompt, tokens_completion, duration_ms, status,
                     retention_expires_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        business_id,
                        operation,
                        model_version,
                        prompt_text,
                        response_json_str,
                        tokens_prompt,
                        tokens_completion,
                        duration_ms,
                        status,
                        retention_expires_at,
                        metadata_str,
                    ),
                )
                log_id = cursor.lastrowid

        logger.info(
            f"Logged LLM interaction: operation={operation}, model={model_version}, "
            f"business_id={business_id}, status={status}"
        )
        return log_id

    except Exception as e:
        logger.error(f"Error logging LLM interaction: {e}")
        return None


def get_llm_logs(
    business_id: Optional[int] = None,
    operation: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get LLM logs from the database.

    Args:
        business_id: Filter by business ID.
        operation: Filter by operation type.
        limit: Maximum number of logs to return.
        offset: Offset for pagination.

    Returns:
        list of log entries.
    """
    try:
        # Build query
        query = "SELECT * FROM llm_logs WHERE 1=1"
        params: list[Union[int, str]] = []

        if business_id is not None:
            query += " AND business_id = ?"
            params.append(int(business_id) if business_id is not None else None)

        if operation is not None:
            query += " AND operation = ?"
            params.append(operation)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        # Execute query
        with DatabaseConnection() as cursor:
            if cursor.connection.is_postgres:
                # Convert ? to %s for Postgres
                query = query.replace("?", "%s")

            cursor.execute(query, params)
            logs = cursor.fetchall()

        # Parse JSON fields
        for log in logs:
            if "response_json" in log and isinstance(log["response_json"], str):
                with contextlib.suppress(json.JSONDecodeError):
                    log["response_json"] = json.loads(log["response_json"])

            if "metadata" in log and isinstance(log["metadata"], str):
                with contextlib.suppress(json.JSONDecodeError):
                    log["metadata"] = json.loads(log["metadata"])

        return logs

    except Exception as e:
        logger.error(f"Error getting LLM logs: {e}")
        return []


def identify_expired_data() -> tuple[list[dict], list[dict]]:
    """Identify data that has expired based on retention policy.

    Returns:
        tuple of (expired_html_files, expired_llm_logs).
    """
    try:
        expired_html_files = []
        expired_llm_logs = []

        # Get current date
        now = datetime.datetime.now()

        # Query database for expired HTML files
        with DatabaseConnection() as cursor:
            # Query for expired HTML files
            cursor.execute(
                "SELECT id, business_id, html_path, original_url "
                "FROM raw_html_storage WHERE retention_expires_at < ?",
                (now,),
            )
            expired_html_files = cursor.fetchall()

            # Query for expired LLM logs
            cursor.execute(
                "SELECT id, business_id, operation FROM llm_logs "
                "WHERE retention_expires_at < ?",
                (now,),
            )
            expired_llm_logs = cursor.fetchall()

        logger.info(
            f"Identified {len(expired_html_files)} expired HTML files and "
            f"{len(expired_llm_logs)} expired LLM logs"
        )
        return expired_html_files, expired_llm_logs

    except Exception as e:
        logger.error(f"Error identifying expired data: {e}")
        return [], []


def fetch_website_html(url: str) -> Optional[str]:
    """Fetch HTML content from a website.

    Args:
        url: URL to fetch HTML from.

    Returns:
        HTML content, or None if fetching failed.
    """
    try:
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Get HTML content
        html_content = response.text

        logger.debug(f"Fetched HTML from {url}, size: {len(html_content)} bytes")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching HTML from {url}: {e}")
        return None
