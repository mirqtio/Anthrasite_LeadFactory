#!/usr/bin/env python3
"""
Cleanup expired JSON responses from businesses table.

This script removes Yelp and Google API JSON responses that have exceeded
the retention period to comply with PII data governance policies.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from leadfactory.utils.e2e_db_connector import db_connection
from leadfactory.utils.logging import get_logger
from leadfactory.utils.metrics import record_metric
from leadfactory.config.json_retention_policy import get_retention_policy

logger = get_logger(__name__)


def get_expired_json_count() -> int:
    """Get count of businesses with expired JSON responses."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM businesses
                WHERE json_retention_expires_at < CURRENT_TIMESTAMP
                AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
            """
            )
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting expired JSON count: {e}")
        return 0


def cleanup_expired_json_responses(dry_run: bool = False, batch_size: int = 100) -> int:
    """
    Remove JSON responses that have exceeded retention period.

    Args:
        dry_run: If True, only report what would be cleaned without making changes
        batch_size: Number of records to process at once

    Returns:
        Number of records cleaned
    """
    total_cleaned = 0

    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            while True:
                # Find expired records in batches
                cursor.execute(
                    """
                    SELECT id, name,
                           pg_column_size(yelp_response_json) as yelp_size,
                           pg_column_size(google_response_json) as google_size,
                           json_retention_expires_at
                    FROM businesses
                    WHERE json_retention_expires_at < CURRENT_TIMESTAMP
                    AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
                    LIMIT %s
                """,
                    (batch_size,),
                )

                records = cursor.fetchall()
                if not records:
                    break

                # Calculate total size being freed
                total_size = sum((row[2] or 0) + (row[3] or 0) for row in records)

                logger.info(
                    f"{'Would clean' if dry_run else 'Cleaning'} {len(records)} records, "
                    f"freeing {total_size:,} bytes"
                )

                if not dry_run:
                    # Clean the JSON fields
                    ids = [row[0] for row in records]
                    cursor.execute(
                        """
                        UPDATE businesses
                        SET yelp_response_json = NULL,
                            google_response_json = NULL,
                            json_retention_expires_at = NULL
                        WHERE id = ANY(%s)
                    """,
                        (ids,),
                    )

                    conn.commit()

                    # Log individual records for audit trail
                    for record in records:
                        logger.debug(
                            f"Cleaned JSON for business {record[0]} ({record[1]}), "
                            f"expired at {record[4]}"
                        )

                total_cleaned += len(records)

                # Record metrics
                record_metric(
                    "json_cleanup",
                    len(records),
                    {
                        "operation": "cleanup_expired",
                        "dry_run": str(dry_run),
                        "bytes_freed": total_size,
                    },
                )

                # For dry run, just process one batch to show what would happen
                if dry_run:
                    # Get total count for dry run report
                    remaining = get_expired_json_count() - len(records)
                    if remaining > 0:
                        logger.info(
                            f"Dry run: {remaining} more records would be cleaned"
                        )
                    break

        logger.info(
            f"JSON cleanup {'simulation' if dry_run else 'completed'}: "
            f"{total_cleaned} records {'would be' if dry_run else ''} cleaned"
        )

        return total_cleaned

    except Exception as e:
        logger.error(f"Error during JSON cleanup: {e}")
        return total_cleaned


def get_json_storage_stats() -> dict:
    """Get statistics about JSON storage usage."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_records,
                    COUNT(yelp_response_json) as yelp_json_count,
                    COUNT(google_response_json) as google_json_count,
                    COUNT(json_retention_expires_at) as records_with_retention,
                    COUNT(CASE WHEN json_retention_expires_at < CURRENT_TIMESTAMP
                               AND (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
                               THEN 1 END) as expired_records,
                    pg_size_pretty(COALESCE(SUM(pg_column_size(yelp_response_json)), 0)) as yelp_total_size,
                    pg_size_pretty(COALESCE(SUM(pg_column_size(google_response_json)), 0)) as google_total_size,
                    pg_size_pretty(
                        COALESCE(SUM(pg_column_size(yelp_response_json)), 0) +
                        COALESCE(SUM(pg_column_size(google_response_json)), 0)
                    ) as total_json_size
                FROM businesses
            """
            )

            result = cursor.fetchone()

            return {
                "total_records": result[0],
                "yelp_json_count": result[1],
                "google_json_count": result[2],
                "records_with_retention": result[3],
                "expired_records": result[4],
                "yelp_total_size": result[5],
                "google_total_size": result[6],
                "total_json_size": result[7],
            }

    except Exception as e:
        logger.error(f"Error getting JSON storage stats: {e}")
        return {}


def main():
    """Main entry point for JSON cleanup script."""
    parser = argparse.ArgumentParser(
        description="Cleanup expired JSON responses from businesses table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process at once (default: 100)",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show JSON storage statistics and exit"
    )
    parser.add_argument(
        "--policy", action="store_true", help="Show current retention policy and exit"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Configure logging
    if args.log_level:
        logger.setLevel(args.log_level)

    try:
        if args.policy:
            # Show retention policy
            policy = get_retention_policy()
            summary = policy.get_policy_summary()

            print("Current JSON Retention Policy:")
            print("=" * 40)
            print(f"Enabled: {summary['enabled']}")
            print(f"Retention Period: {summary['retention_behavior']}")
            print(f"Anonymization: {'Enabled' if summary['anonymize'] else 'Disabled'}")
            print(f"Will Store JSON: {summary['should_store']}")
            if summary["preserve_fields"]:
                print(f"Preserved Fields: {', '.join(summary['preserve_fields'])}")

            return 0

        if args.stats:
            # Show statistics
            stats = get_json_storage_stats()

            print("JSON Storage Statistics:")
            print("=" * 30)
            for key, value in stats.items():
                print(f"{key.replace('_', ' ').title()}: {value}")

            return 0

        # Run cleanup
        start_time = datetime.now()

        logger.info(
            f"Starting JSON cleanup {'(DRY RUN)' if args.dry_run else ''} "
            f"with batch size {args.batch_size}"
        )

        cleaned = cleanup_expired_json_responses(
            dry_run=args.dry_run, batch_size=args.batch_size
        )

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"JSON cleanup completed in {duration:.2f} seconds. "
            f"{cleaned} records {'would be' if args.dry_run else ''} cleaned."
        )

        return 0

    except Exception as e:
        logger.error(f"JSON cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
