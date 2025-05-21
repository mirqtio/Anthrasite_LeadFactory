#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Data Retention Cleanup
Cleans up expired HTML files and LLM logs based on the retention policy.

Usage:
    python bin/cleanup_expired_data.py [--dry-run] [--verbose]
"""

import os
import sys
import argparse
import json
import datetime
from typing import Dict, List, Tuple, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import utility functions
from utils.raw_data_retention import identify_expired_data, HTML_STORAGE_DIR, RETENTION_DAYS
from utils.io import DatabaseConnection
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)


def delete_html_files(expired_paths: List[str], dry_run: bool = False) -> int:
    """Delete expired HTML files.

    Args:
        expired_paths: List of paths to expired HTML files.
        dry_run: If True, don't actually delete files.

    Returns:
        Number of files deleted.
    """
    deleted_count = 0

    for path in expired_paths:
        full_path = os.path.join(HTML_STORAGE_DIR, path)

        if os.path.exists(full_path):
            if not dry_run:
                try:
                    os.remove(full_path)
                    logger.info(f"Deleted HTML file: {path}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting HTML file {path}: {e}")
            else:
                logger.info(f"[DRY RUN] Would delete HTML file: {path}")
                deleted_count += 1

    return deleted_count


def delete_database_records(expired_html_paths: List[str], expired_log_ids: List[int], dry_run: bool = False) -> Tuple[int, int]:
    """Delete expired database records.

    Args:
        expired_html_paths: List of paths to expired HTML files.
        expired_log_ids: List of IDs of expired LLM logs.
        dry_run: If True, don't actually delete records.

    Returns:
        Tuple of (html_records_deleted, log_records_deleted).
    """
    html_records_deleted = 0
    log_records_deleted = 0

    if not expired_html_paths and not expired_log_ids:
        return 0, 0

    try:
        with DatabaseConnection() as cursor:
            # Delete HTML storage records
            if expired_html_paths:
                if not dry_run:
                    # Prepare the query with proper parameterization
                    # This avoids SQL injection by not using string formatting for the query
                    if cursor.connection.is_postgres:
                        # PostgreSQL uses %s for parameters
                        placeholders = ", ".join(["%s" for _ in expired_html_paths])
                    else:
                        # SQLite uses ? for parameters
                        placeholders = ", ".join(["?" for _ in expired_html_paths])

                    # Use a safer approach with a fixed query structure and validated placeholders
                    # The placeholders string is constructed from a list comprehension with fixed values
                    # This is safe because we're not using user input in the query structure
                    query = "DELETE FROM raw_html_storage WHERE html_path IN (" + placeholders + ")"  # nosec B608
                    cursor.execute(query, expired_html_paths)
                    html_records_deleted = len(expired_html_paths)
                    logger.info(f"Deleted {html_records_deleted} HTML storage records")
                else:
                    logger.info(f"[DRY RUN] Would delete {len(expired_html_paths)} HTML storage records")
                    html_records_deleted = len(expired_html_paths)

            # Delete LLM log records
            if expired_log_ids:
                if not dry_run:
                    # Prepare the query with proper parameterization
                    # This avoids SQL injection by not using string formatting for the query
                    if cursor.connection.is_postgres:
                        # PostgreSQL uses %s for parameters
                        placeholders = ", ".join(["%s" for _ in expired_log_ids])
                        # Use a safer approach with a fixed query structure and validated placeholders
                        # The placeholders string is constructed from a list comprehension with fixed values
                        # This is safe because we're not using user input in the query structure
                        query = "DELETE FROM llm_logs WHERE id IN (" + placeholders + ")"  # nosec B608
                    else:
                        # SQLite uses ? for parameters
                        placeholders = ", ".join(["?" for _ in expired_log_ids])
                        # Use a safer approach with a fixed query structure and validated placeholders
                        # The placeholders string is constructed from a list comprehension with fixed values
                        # This is safe because we're not using user input in the query structure
                        query = "DELETE FROM llm_logs WHERE id IN (" + placeholders + ")"  # nosec B608

                    # Execute delete query with parameters
                    cursor.execute(query, expired_log_ids)
                    log_records_deleted = len(expired_log_ids)
                    logger.info(f"Deleted {log_records_deleted} LLM log records")
                else:
                    logger.info(f"[DRY RUN] Would delete {len(expired_log_ids)} LLM log records")
                    log_records_deleted = len(expired_log_ids)

    except Exception as e:
        logger.error(f"Error deleting database records: {e}")

    return html_records_deleted, log_records_deleted


def cleanup_expired_data(dry_run: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """Clean up expired data based on retention policy.

    Args:
        dry_run: If True, don't actually delete anything.
        verbose: If True, print verbose output.

    Returns:
        Dictionary with cleanup results.
    """
    if verbose:
        logger.info(f"Identifying expired data (retention period: {RETENTION_DAYS} days)...")

    # Identify expired data
    expired_html_paths, expired_log_ids = identify_expired_data()

    if verbose:
        logger.info(f"Found {len(expired_html_paths)} expired HTML files and {len(expired_log_ids)} expired LLM logs")

    # Delete HTML files
    html_files_deleted = delete_html_files(expired_html_paths, dry_run)

    # Delete database records
    html_records_deleted, log_records_deleted = delete_database_records(expired_html_paths, expired_log_ids, dry_run)

    # Prepare results
    results = {
        "retention_days": RETENTION_DAYS,
        "expired_html_files": len(expired_html_paths),
        "expired_llm_logs": len(expired_log_ids),
        "html_files_deleted": html_files_deleted,
        "html_records_deleted": html_records_deleted,
        "llm_logs_deleted": log_records_deleted,
        "dry_run": dry_run,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    if verbose:
        if dry_run:
            logger.info("[DRY RUN] No actual deletions performed")
        logger.info(f"Cleanup complete: {html_files_deleted} HTML files and {log_records_deleted} LLM logs processed")

    return results


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Data Retention Cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually delete anything, just show what would be deleted",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output",
    )
    args = parser.parse_args()

    try:
        # Run cleanup
        results = cleanup_expired_data(args.dry_run, args.verbose)

        # Print results
        print(json.dumps(results, indent=2))

        return 0
    except Exception as e:
        logger.error(f"Error in cleanup script: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
