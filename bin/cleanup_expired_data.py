#!/usr/bin/env python3
"""
Script to clean up expired HTML and LLM log data based on retention policy.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import get_config
from utils.database import DatabaseConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cleanup_expired_data")


def get_expired_data(
    retention_days: int, dry_run: bool = False
) -> tuple[list[str], list[int]]:
    """
    Get a list of HTML files and LLM log IDs that are older than the retention period.

    Args:
        retention_days: Number of days to keep data
        dry_run: If True, only log what would be deleted without actually deleting

    Returns:
        Tuple containing (list of expired HTML paths, list of expired LLM log IDs)
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        logger.info(f"Identifying data older than {cutoff_date}")

        expired_html_paths = []
        expired_log_ids = []

        with DatabaseConnection() as cursor:
            # Find expired HTML records
            cursor.execute(
                "SELECT html_path FROM raw_html_storage WHERE created_at < %s",
                (cutoff_date,),
            )
            expired_html_paths = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(expired_html_paths)} expired HTML records")

            # Find expired LLM log records
            cursor.execute(
                "SELECT id FROM llm_logs WHERE created_at < %s", (cutoff_date,)
            )
            expired_log_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(expired_log_ids)} expired LLM log records")

        return expired_html_paths, expired_log_ids

    except Exception as e:
        logger.error(f"Error finding expired data: {e}")
        return [], []


def delete_expired_files(expired_html_paths: list[str], dry_run: bool = False) -> int:
    """
    Delete expired HTML files from the filesystem.

    Args:
        expired_html_paths: List of paths to HTML files to delete
        dry_run: If True, only log what would be deleted without actually deleting

    Returns:
        Number of files deleted
    """
    files_deleted = 0
    for path in expired_html_paths:
        if os.path.exists(path):
            if not dry_run:
                try:
                    os.remove(path)
                    files_deleted += 1
                except Exception as e:
                    logger.error(f"Error deleting file {path}: {e}")
            else:
                logger.info(f"[DRY RUN] Would delete file: {path}")
                files_deleted += 1
    return files_deleted


def delete_database_records(
    expired_html_paths: list[str], expired_log_ids: list[int], dry_run: bool = False
) -> tuple[int, int]:
    """
    Delete expired records from the database.

    Args:
        expired_html_paths: List of HTML file paths to delete from database
        expired_log_ids: List of LLM log IDs to delete
        dry_run: If True, only log what would be deleted without actually deleting

    Returns:
        Tuple containing (number of HTML records deleted, number of LLM log records deleted)
    """
    html_records_deleted = 0
    log_records_deleted = 0

    try:
        with DatabaseConnection() as cursor:
            # Delete HTML storage records
            if expired_html_paths:
                if not dry_run:
                    # Use parameterized queries to avoid SQL injection
                    # This is the safest approach as it lets the database handle parameter substitution
                    for path in expired_html_paths:
                        cursor.execute(
                            "DELETE FROM raw_html_storage WHERE html_path = %s",
                            (path,),
                        )
                    html_records_deleted = len(expired_html_paths)
                    logger.info(f"Deleted {html_records_deleted} HTML storage records")
                else:
                    logger.info(
                        f"[DRY RUN] Would delete {len(expired_html_paths)} HTML storage records"
                    )
                    html_records_deleted = len(expired_html_paths)

            # Delete LLM log records
            if expired_log_ids:
                if not dry_run:
                    # Use parameterized queries to avoid SQL injection
                    # This is the safest approach as it lets the database handle parameter substitution
                    for log_id in expired_log_ids:
                        cursor.execute(
                            "DELETE FROM llm_logs WHERE id = %s",
                            (log_id,),
                        )
                    log_records_deleted = len(expired_log_ids)
                    logger.info(f"Deleted {log_records_deleted} LLM log records")
                else:
                    logger.info(
                        f"[DRY RUN] Would delete {len(expired_log_ids)} LLM log records"
                    )
                    log_records_deleted = len(expired_log_ids)

    except Exception as e:
        logger.error(f"Error deleting database records: {e}")

    return html_records_deleted, log_records_deleted


def cleanup_expired_data(
    retention_days: Optional[int] = None, dry_run: bool = False
) -> None:
    """
    Clean up expired HTML and LLM log data based on retention policy.

    Args:
        retention_days: Number of days to keep data, defaults to DATA_RETENTION_DAYS from config
        dry_run: If True, only log what would be deleted without actually deleting
    """
    if retention_days is None:
        config = get_config()
        retention_days = int(config.get("DATA_RETENTION_DAYS", 90))

    logger.info(f"Starting cleanup of data older than {retention_days} days")
    if dry_run:
        logger.info("DRY RUN MODE - No data will be deleted")

    # Get expired data
    expired_html_paths, expired_log_ids = get_expired_data(retention_days, dry_run)

    # Delete expired files from filesystem
    files_deleted = delete_expired_files(expired_html_paths, dry_run)
    logger.info(f"Deleted {files_deleted} HTML files from filesystem")

    # Delete expired records from database
    html_records_deleted, log_records_deleted = delete_database_records(
        expired_html_paths, expired_log_ids, dry_run
    )

    logger.info(
        f"Cleanup complete: {files_deleted} files, {html_records_deleted} HTML records, "
        f"{log_records_deleted} LLM log records"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean up expired data based on retention policy"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        help="Number of days to keep data (default: DATA_RETENTION_DAYS from config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only log what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    cleanup_expired_data(args.retention_days, args.dry_run)
