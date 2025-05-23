#!/usr/bin/env python
"""
Supabase Usage Monitor
-------------------
This script monitors Supabase project usage, including storage and database
row counts, and exposes metrics for alerting when approaching free tier limits.

Usage:
    python scripts/monitor_supabase_usage.py --alert-threshold 80

Features:
- Fetches project disk and row usage from Supabase admin API
- Exposes metrics for monitoring and alerting
- Sends notifications when approaching tier limits
- Provides detailed logging for troubleshooting
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import requests

# Add parent directory to path to allow importing metrics
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
from bin.metrics import metrics  # noqa: E402

# Setup logging
Path("logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "supabase_usage.log"),
    ],
)
logger = logging.getLogger("supabase_usage")


class SupabaseUsageMonitor:
    """Supabase usage monitor for LeadFactory."""

    def __init__(self):
        """Initialize Supabase usage monitor."""
        # Load configuration from environment variables
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "")
        self.supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        self.project_ref = self._extract_project_ref()

        # Free tier limits
        self.storage_limit_mb = 1000  # 1 GB
        self.database_size_limit_mb = 500  # 500 MB
        self.row_limit = 50000  # 50K rows

        # Alert thresholds (percentage of limit)
        self.alert_threshold = int(os.environ.get("SUPABASE_ALERT_THRESHOLD", "80"))

        logger.info(
            f"Supabase usage monitor initialized (project_ref={self.project_ref}, "
            f"alert_threshold={self.alert_threshold}%)"
        )

    def _extract_project_ref(self) -> str:
        """Extract project reference from Supabase URL.

        Returns:
            Project reference string
        """
        if not self.supabase_url:
            return ""

        try:
            # URL format: https://<project_ref>.supabase.co
            parts = self.supabase_url.split(".")
            if len(parts) >= 2:
                project_ref = parts[0].split("//")[1]
                return project_ref
        except Exception as e:
            logger.error(f"Error extracting project reference: {e}")

        return ""

    def get_storage_usage(self) -> Dict[str, Any]:
        """Get storage usage from Supabase.

        Returns:
            Dictionary with storage usage information
        """
        try:
            if not self.supabase_url or not self.supabase_service_key:
                logger.error("Supabase URL or service key not configured")
                return {
                    "size_mb": 0,
                    "size_bytes": 0,
                    "buckets": [],
                    "percentage_used": 0,
                }

            # Make API request to get storage usage
            headers = {
                "Authorization": f"Bearer {self.supabase_service_key}",
                "Content-Type": "application/json",
            }

            select_params = (
                "name,id,created_at,updated_at,owner,public,"
                "file_size_limit,allowed_mime_types"
            )
            url = f"{self.supabase_url}/rest/v1/storage/buckets?select={select_params}"

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(
                    f"Error getting storage buckets: {response.status_code} "
                    f"{response.text}"
                )
                return {
                    "size_mb": 0,
                    "size_bytes": 0,
                    "buckets": [],
                    "percentage_used": 0,
                }

            buckets = response.json()

            # Get size of each bucket
            total_size_bytes = 0
            bucket_sizes = []

            for bucket in buckets:
                bucket_name = bucket["name"]

                # Get objects in bucket
                select_params_obj = (
                    "name,bucket_id,owner,created_at,updated_at,metadata,id,size"
                )
                bucket_id_param = f"bucket_id=eq.{bucket['id']}"
                objects_url = (
                    f"{self.supabase_url}/rest/v1/storage/objects"
                    f"?{select_params_obj}&{bucket_id_param}"
                )
                objects_response = requests.get(
                    objects_url, headers=headers, timeout=30
                )

                if objects_response.status_code != 200:
                    logger.error(
                        f"Error getting objects for bucket {bucket_name}: "
                        f"{objects_response.status_code} {objects_response.text}"
                    )
                    continue

                objects = objects_response.json()

                # Calculate bucket size
                bucket_size_bytes = sum(obj.get("size", 0) for obj in objects)
                total_size_bytes += bucket_size_bytes

                bucket_sizes.append(
                    {
                        "name": bucket_name,
                        "size_bytes": bucket_size_bytes,
                        "size_mb": bucket_size_bytes / (1024 * 1024),
                        "object_count": len(objects),
                    }
                )

            # Calculate total size in MB
            total_size_mb = total_size_bytes / (1024 * 1024)

            # Calculate percentage of limit used
            percentage_used = (
                (total_size_mb / self.storage_limit_mb) * 100
                if self.storage_limit_mb > 0
                else 0
            )

            result = {
                "size_mb": total_size_mb,
                "size_bytes": total_size_bytes,
                "buckets": bucket_sizes,
                "percentage_used": percentage_used,
            }

            logger.info(
                f"Storage usage: {total_size_mb:.2f} MB "
                f"({percentage_used:.2f}% of limit)"
            )

            # Update metrics
            metrics.update_supabase_storage(total_size_mb)

            # Check if approaching limit
            if percentage_used >= self.alert_threshold:
                logger.warning(
                    f"Storage usage ({percentage_used:.2f}%) is approaching "
                    f"the limit ({self.storage_limit_mb} MB)"
                )

            return result
        except Exception as e:
            logger.exception(f"Error getting storage usage: {e}")
            return {"size_mb": 0, "size_bytes": 0, "buckets": [], "percentage_used": 0}

    def get_database_usage(self) -> Dict[str, Any]:
        """Get database usage from Supabase.

        Returns:
            Dictionary with database usage information
        """
        try:
            if not self.supabase_url or not self.supabase_service_key:
                logger.error("Supabase URL or service key not configured")
                return {
                    "size_mb": 0,
                    "size_bytes": 0,
                    "tables": [],
                    "percentage_used": 0,
                    "row_count": 0,
                    "row_percentage_used": 0,
                }

            # Make API request to get database tables
            headers = {
                "Authorization": f"Bearer {self.supabase_service_key}",
                "Content-Type": "application/json",
            }

            # Get table information
            tables_query = """
            SELECT
                table_schema,
                table_name,
                pg_total_relation_size(
                    quote_ident(table_schema) || '.' || quote_ident(table_name)
                ) as size_bytes,
                pg_relation_size(
                    quote_ident(table_schema) || '.' || quote_ident(table_name)
                ) as table_size_bytes,
                pg_indexes_size(
                    quote_ident(table_schema) || '.' || quote_ident(table_name)
                ) as index_size_bytes,
                (
                    SELECT reltuples
                    FROM pg_class
                    WHERE oid = (
                        quote_ident(table_schema) || '.' || quote_ident(table_name)
                    )::regclass
                ) as row_estimate
            FROM
                information_schema.tables
            WHERE
                table_schema NOT IN ('pg_catalog', 'information_schema')
                AND table_type = 'BASE TABLE'
            ORDER BY
                size_bytes DESC;
            """

            # Use Supabase's SQL API
            sql_url = f"{self.supabase_url}/rest/v1/rpc/sql"
            sql_payload = {"query": tables_query}

            response = requests.post(
                sql_url, headers=headers, json=sql_payload, timeout=30
            )

            if response.status_code != 200:
                logger.error(
                    f"Error getting database usage: {response.status_code} "
                    f"{response.text}"
                )
                return {
                    "size_mb": 0,
                    "size_bytes": 0,
                    "tables": [],
                    "percentage_used": 0,
                    "row_count": 0,
                    "row_percentage_used": 0,
                }

            result = response.json()

            if not result or "data" not in result:
                logger.error(f"Invalid response format: {result}")
                return {
                    "size_mb": 0,
                    "size_bytes": 0,
                    "tables": [],
                    "percentage_used": 0,
                    "row_count": 0,
                    "row_percentage_used": 0,
                }

            tables = result["data"]

            # Calculate total size and row count
            total_size_bytes = sum(table.get("size_bytes", 0) for table in tables)
            total_size_mb = total_size_bytes / (1024 * 1024)
            total_row_count = sum(int(table.get("row_estimate", 0)) for table in tables)

            # Calculate percentage of limits used
            size_percentage_used = (
                (total_size_mb / self.database_size_limit_mb) * 100
                if self.database_size_limit_mb > 0
                else 0
            )
            row_percentage_used = (
                (total_row_count / self.row_limit) * 100 if self.row_limit > 0 else 0
            )

            # Format table information
            table_info = []
            for table in tables:
                table_schema = table.get("table_schema", "")
                table_name = table.get("table_name", "")
                size_bytes = table.get("size_bytes", 0)
                row_estimate = int(table.get("row_estimate", 0))

                table_info.append(
                    {
                        "schema": table_schema,
                        "name": table_name,
                        "size_bytes": size_bytes,
                        "size_mb": size_bytes / (1024 * 1024),
                        "row_count": row_estimate,
                    }
                )

                # Update row count metric for this table
                metrics.update_supabase_row_count(
                    f"{table_schema}.{table_name}", row_estimate
                )

            result = {
                "size_mb": total_size_mb,
                "size_bytes": total_size_bytes,
                "tables": table_info,
                "percentage_used": size_percentage_used,
                "row_count": total_row_count,
                "row_percentage_used": row_percentage_used,
            }

            logger.info(
                f"Database usage: {total_size_mb:.2f} MB "
                f"({size_percentage_used:.2f}% of size limit), "
                f"{total_row_count} rows ({row_percentage_used:.2f}% of row limit)"
            )

            # Check if approaching limits
            if size_percentage_used >= self.alert_threshold:
                logger.warning(
                    f"Database size ({size_percentage_used:.2f}%) is approaching "
                    f"the limit ({self.database_size_limit_mb} MB)"
                )

            if row_percentage_used >= self.alert_threshold:
                logger.warning(
                    f"DB row count ({row_percentage_used:.2f}%) is approaching "
                    f"the limit ({self.row_limit} rows)"
                )

            return result
        except Exception as e:
            logger.exception(f"Error getting database usage: {e}")
            return {
                "size_mb": 0,
                "size_bytes": 0,
                "tables": [],
                "percentage_used": 0,
                "row_count": 0,
                "row_percentage_used": 0,
            }

    def get_all_usage(self) -> Dict[str, Any]:
        """Get all usage information from Supabase.

        Returns:
            Dictionary with all usage information
        """
        storage_usage = self.get_storage_usage()
        database_usage = self.get_database_usage()

        return {
            "timestamp": datetime.now().isoformat(),
            "storage": storage_usage,
            "database": database_usage,
            "limits": {
                "storage_mb": self.storage_limit_mb,
                "database_size_mb": self.database_size_limit_mb,
                "row_count": self.row_limit,
            },
        }

    def save_usage_report(
        self, usage_data: Dict[str, Any], output_file: Optional[str] = None
    ) -> str:
        """Save usage report to a file.

        Args:
            usage_data: Usage data to save
            output_file: Output path (default: data/supabase_usage_{timestamp}.json)

        Returns:
            Path to the saved file
        """
        try:
            # Create data directory if it doesn't exist
            Path("data/supabase_usage").mkdir(parents=True, exist_ok=True)

            # Generate filename if not provided
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"data/supabase_usage/supabase_usage_{timestamp}.json"

            # Save to file
            with Path(output_file).open("w") as f:
                json.dump(usage_data, f, indent=2)

            logger.info(f"Usage report saved to {output_file}")

            # Create symlink to latest report
            latest_link = "data/supabase_usage/latest.json"

            if Path(latest_link).exists():
                Path(latest_link).unlink(missing_ok=True)

            Path(latest_link).symlink_to(Path(output_file).resolve())

            return output_file
        except Exception as e:
            logger.exception(f"Error saving usage report: {e}")
            return ""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Supabase Usage Monitor")
    parser.add_argument(
        "--alert-threshold",
        type=int,
        default=80,
        help="Alert threshold as percentage of limit (default: 80)",
    )
    parser.add_argument("--output", type=str, help="Output file for usage report")
    args = parser.parse_args()

    try:
        # Create monitor
        monitor = SupabaseUsageMonitor()

        # Set alert threshold
        monitor.alert_threshold = args.alert_threshold

        # Get usage information
        usage_data = monitor.get_all_usage()

        # Save usage report
        monitor.save_usage_report(usage_data, args.output)

        # Print summary
        storage_percentage = usage_data["storage"]["percentage_used"]
        database_percentage = usage_data["database"]["percentage_used"]
        row_percentage = usage_data["database"]["row_percentage_used"]

        # Return non-zero exit code if any usage is above threshold
        if (
            storage_percentage >= monitor.alert_threshold
            or database_percentage >= monitor.alert_threshold
            or row_percentage >= monitor.alert_threshold
        ):
            return 1

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
