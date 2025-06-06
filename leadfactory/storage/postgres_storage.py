"""
PostgreSQL storage implementation for LeadFactory.

This module provides a PostgreSQL-specific implementation of the storage interface,
wrapping the existing e2e_db_connector functionality.
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from leadfactory.config.json_retention_policy import get_retention_expiry_date
from leadfactory.utils.e2e_db_connector import (
    check_connection,
    db_connection,
    db_cursor,
    execute_query,
    execute_transaction,
    validate_schema,
)

from .interface import StorageInterface

logger = logging.getLogger(__name__)


class PostgresStorage(StorageInterface):
    """
    PostgreSQL implementation of the storage interface.

    This class wraps the existing e2e_db_connector functionality to provide
    a clean, abstracted interface for database operations.
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize PostgreSQL storage.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        logger.debug("PostgreSQL storage initialized")

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        with db_connection() as conn:
            yield conn

    @contextmanager
    def cursor(self):
        """Context manager for database cursors."""
        with db_cursor() as cursor:
            yield cursor

    def execute_query(
        self, query: str, params: Optional[tuple] = None, fetch: bool = True
    ) -> list[dict[str, Any]]:
        """Execute a SQL query and return results."""
        try:
            results = execute_query(query, params, fetch)
            if not fetch:
                return []

            # Convert to list of dictionaries if needed
            if results and isinstance(results[0], (tuple, list)):
                # If we get tuples/lists, we need column names
                # This is a limitation of the current execute_query function
                logger.warning("Query returned tuples instead of dictionaries")
                return [{"result": row} for row in results]

            return results if results else []
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []

    def execute_transaction(self, queries: list[tuple[str, Optional[tuple]]]) -> bool:
        """Execute multiple queries in a transaction."""
        try:
            return execute_transaction(queries)
        except Exception as e:
            logger.error(f"Transaction execution failed: {e}")
            return False

    def get_business_by_id(self, business_id: int) -> Optional[dict[str, Any]]:
        """Get business data by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM businesses
                    WHERE id = %s
                    """,
                    (business_id,),
                )
                result = cursor.fetchone()

                if result:
                    # Convert to dictionary if it's a tuple
                    if isinstance(result, tuple):
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(f"Failed to get business {business_id}: {e}")
            return None

    def get_businesses_by_criteria(
        self, criteria: dict[str, Any], limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """Get businesses matching specific criteria."""
        try:
            # Build WHERE clause from criteria
            where_conditions = []
            params = []

            for field, value in criteria.items():
                if value is not None:
                    where_conditions.append(f"{field} = %s")
                    params.append(value)
                else:
                    where_conditions.append(f"{field} IS NULL")

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            query = f"""
                SELECT * FROM businesses
                WHERE {where_clause}
            """

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            with self.cursor() as cursor:
                cursor.execute(query, tuple(params))
                results = cursor.fetchall()

                if not results:
                    return []

                # Convert to list of dictionaries
                if isinstance(results[0], tuple):
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in results]

                return [dict(row) if hasattr(row, "keys") else row for row in results]

        except Exception as e:
            logger.error(f"Failed to get businesses by criteria {criteria}: {e}")
            return []

    def update_business(self, business_id: int, updates: dict[str, Any]) -> bool:
        """Update business record with new data."""
        try:
            if not updates:
                return True

            # Build SET clause from updates
            set_conditions = []
            params = []

            for field, value in updates.items():
                set_conditions.append(f"{field} = %s")
                params.append(value)

            params.append(business_id)

            query = f"""
                UPDATE businesses
                SET {", ".join(set_conditions)}
                WHERE id = %s
            """

            with self.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update business {business_id}: {e}")
            return False

    def insert_business(self, business_data: dict[str, Any]) -> Optional[int]:
        """Insert a new business record."""
        try:
            if not business_data:
                return None

            # Build INSERT statement
            fields = list(business_data.keys())
            values = list(business_data.values())
            placeholders = ", ".join(["%s"] * len(fields))

            query = f"""
                INSERT INTO businesses ({", ".join(fields)})
                VALUES ({placeholders})
                RETURNING id
            """

            with self.cursor() as cursor:
                cursor.execute(query, tuple(values))
                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logger.error(f"Failed to insert business: {e}")
            return None

    def get_business_details(self, business_id: int) -> Optional[dict[str, Any]]:
        """Get detailed business information including JSON responses."""
        try:
            query = """
            SELECT id, name, address, zip, phone, email, website, vertical, source,
                   google_response, yelp_response, manual_response, created_at, updated_at
            FROM businesses
            WHERE id = %s
            """
            results = self.execute_query(query, (business_id,))
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Error getting business details for {business_id}: {e}")
            return None

    def get_businesses(self, business_ids: list[int]) -> list[dict[str, Any]]:
        """Get multiple businesses by their IDs."""
        try:
            if not business_ids:
                return []

            placeholders = ",".join(["%s"] * len(business_ids))
            query = f"""
            SELECT id, name, address, zip, phone, email, website, vertical, source,
                   google_response, yelp_response, manual_response, created_at, updated_at
            FROM businesses
            WHERE id IN ({placeholders})
            """
            return self.execute_query(query, business_ids)
        except Exception as e:
            logger.error(f"Error getting businesses {business_ids}: {e}")
            return []

    def merge_businesses(self, primary_id: int, secondary_id: int) -> bool:
        """Merge two business records, keeping primary and removing secondary."""
        try:
            # Import the existing merge function
            from leadfactory.utils.e2e_db_connector import merge_business_records

            result = merge_business_records(primary_id, secondary_id)
            return result is not None
        except Exception as e:
            logger.error(f"Error merging businesses {primary_id}, {secondary_id}: {e}")
            return False

    def get_processing_status(
        self, business_id: int, stage: str
    ) -> Optional[dict[str, Any]]:
        """Get processing status for a business at a specific stage."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, metadata, updated_at
                    FROM processing_status
                    WHERE business_id = %s AND stage = %s
                    """,
                    (business_id, stage),
                )
                result = cursor.fetchone()

                if result:
                    if isinstance(result, tuple):
                        return {
                            "status": result[0],
                            "metadata": json.loads(result[1]) if result[1] else {},
                            "updated_at": result[2],
                        }
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(
                f"Failed to get processing status for {business_id}/{stage}: {e}"
            )
            return None

    def update_processing_status(
        self,
        business_id: int,
        stage: str,
        status: str,
        metadata: Optional[dict[str, Any]] = None,
        skip_reason: Optional[str] = None,
    ) -> bool:
        """Update processing status for a business at a specific stage."""
        try:
            metadata_json = json.dumps(metadata) if metadata else None

            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO processing_status (business_id, stage, status, metadata, skip_reason)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (business_id, stage)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        skip_reason = EXCLUDED.skip_reason,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (business_id, stage, status, metadata_json, skip_reason),
                )
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(
                f"Failed to update processing status for {business_id}/{stage}: {e}"
            )
            return False

    def save_stage_results(
        self, business_id: int, stage: str, results: dict[str, Any]
    ) -> bool:
        """Save results from a pipeline stage."""
        try:
            results_json = json.dumps(results)

            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stage_results (business_id, stage, results)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (business_id, stage)
                    DO UPDATE SET
                        results = EXCLUDED.results,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (business_id, stage, results_json),
                )
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to save stage results for {business_id}/{stage}: {e}")
            return False

    def get_stage_results(
        self, business_id: int, stage: str
    ) -> Optional[dict[str, Any]]:
        """Get saved results from a pipeline stage."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT results FROM stage_results
                    WHERE business_id = %s AND stage = %s
                    """,
                    (business_id, stage),
                )
                result = cursor.fetchone()

                if result:
                    results_json = (
                        result[0] if isinstance(result, tuple) else result["results"]
                    )
                    return json.loads(results_json) if results_json else {}

                return None
        except Exception as e:
            logger.error(f"Failed to get stage results for {business_id}/{stage}: {e}")
            return None

    def check_connection(self) -> bool:
        """Check if the storage connection is working."""
        try:
            return check_connection()
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False

    def validate_schema(self) -> bool:
        """Validate that the storage schema has required tables."""
        try:
            return validate_schema()
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False

    def get_business_by_source_id(
        self, source_id: str, source: str
    ) -> Optional[dict[str, Any]]:
        """Get business by source ID and source."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM businesses
                    WHERE source_id = %s AND source = %s
                    """,
                    (source_id.strip(), source),
                )
                result = cursor.fetchone()

                if result:
                    if isinstance(result, tuple):
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(
                f"Failed to get business by source_id {source_id}/{source}: {e}"
            )
            return None

    def get_business_by_website(self, website: str) -> Optional[dict[str, Any]]:
        """Get business by website."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM businesses
                    WHERE website = %s AND website IS NOT NULL AND website != ''
                    """,
                    (website.strip(),),
                )
                result = cursor.fetchone()

                if result:
                    if isinstance(result, tuple):
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(f"Failed to get business by website {website}: {e}")
            return None

    def get_business_by_phone(self, phone: str) -> Optional[dict[str, Any]]:
        """Get business by phone number."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM businesses
                    WHERE phone = %s AND phone IS NOT NULL AND phone != ''
                    """,
                    (phone.strip(),),
                )
                result = cursor.fetchone()

                if result:
                    if isinstance(result, tuple):
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(f"Failed to get business by phone {phone}: {e}")
            return None

    def get_business_by_name_and_zip(
        self, name: str, zip_code: str
    ) -> Optional[dict[str, Any]]:
        """Get business by name and ZIP code."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM businesses
                    WHERE LOWER(name) = LOWER(%s) AND zip = %s
                    """,
                    (name.strip(), zip_code.strip()),
                )
                result = cursor.fetchone()

                if result:
                    if isinstance(result, tuple):
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return dict(result) if hasattr(result, "keys") else result

                return None
        except Exception as e:
            logger.error(f"Failed to get business by name/zip {name}/{zip_code}: {e}")
            return None

    def create_business(
        self,
        name: str,
        address: str,
        city: str,
        state: str,
        zip_code: str,
        category: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        website: Optional[str] = None,
        source: Optional[str] = None,
        source_id: Optional[str] = None,
        yelp_response_json: Optional[dict] = None,
        google_response_json: Optional[dict] = None,
    ) -> Optional[int]:
        """Create a new business record."""
        try:
            # Get retention expiry date if JSON responses are provided
            retention_expiry = None
            if yelp_response_json or google_response_json:
                retention_expiry = get_retention_expiry_date()

            with self.cursor() as cursor:
                insert_query = """
                    INSERT INTO businesses (
                        name, address, city, state, zip, phone, email, website,
                        vertical_id, created_at, updated_at, status, processed,
                        source, source_id, yelp_response_json, google_response_json,
                        json_retention_expires_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        (SELECT id FROM verticals WHERE name = %s LIMIT 1),
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'pending', FALSE,
                        %s, %s, %s, %s, %s
                    ) RETURNING id
                """

                cursor.execute(
                    insert_query,
                    (
                        name,
                        address,
                        city,
                        state,
                        zip_code,
                        phone,
                        email,
                        website,
                        category.lower() if category else None,
                        source,
                        source_id,
                        json.dumps(yelp_response_json) if yelp_response_json else None,
                        (
                            json.dumps(google_response_json)
                            if google_response_json
                            else None
                        ),
                        retention_expiry,
                    ),
                )

                result = cursor.fetchone()
                return result[0] if result else None

        except Exception as e:
            logger.error(f"Failed to create business {name}: {e}")
            return None

    def get_business(self, business_id: int) -> Optional[dict[str, Any]]:
        """Get business by ID (alias for get_business_by_id)."""
        return self.get_business_by_id(business_id)

    def get_vertical_id(self, vertical_name: str) -> Optional[int]:
        """Get vertical ID by name."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM verticals WHERE name = %s", (vertical_name,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get vertical ID for {vertical_name}: {e}")
            return None

    def get_vertical_name(self, vertical_id: int) -> Optional[str]:
        """Get vertical name by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM verticals WHERE id = %s", (vertical_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get vertical name for ID {vertical_id}: {e}")
            return None

    # Review Queue Methods
    def add_to_review_queue(
        self,
        primary_id: int,
        secondary_id: int,
        reason: str = None,
        details: str = None,
    ) -> Optional[int]:
        """Add a manual review request to the queue."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dedupe_review_queue
                    (business1_id, business2_id, reason, details, status, created_at)
                    VALUES (%s, %s, %s, %s, 'pending', NOW())
                    RETURNING id
                    """,
                    (primary_id, secondary_id, reason, details),
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to add review to queue: {e}")
            return None

    def get_review_queue_items(
        self, status: str = None, limit: int = None
    ) -> list[dict[str, Any]]:
        """Get review queue items."""
        try:
            with self.cursor() as cursor:
                query = "SELECT * FROM dedupe_review_queue"
                params = []

                if status:
                    query += " WHERE status = %s"
                    params.append(status)

                query += " ORDER BY created_at DESC"

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                results = cursor.fetchall()

                if not results:
                    return []

                # Convert to list of dictionaries
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Failed to get review queue items: {e}")
            return []

    def update_review_status(
        self, review_id: int, status: str, resolution: str = None
    ) -> bool:
        """Update the status of a review request."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dedupe_review_queue
                    SET status = %s, resolution = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, resolution, review_id),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update review status: {e}")
            return False

    def get_review_statistics(self) -> dict[str, Any]:
        """Get statistics about manual reviews."""
        try:
            with self.cursor() as cursor:
                # Get counts by status
                cursor.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM dedupe_review_queue
                    GROUP BY status
                    """
                )
                status_counts = dict(cursor.fetchall())

                # Get average resolution time
                cursor.execute(
                    """
                    SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds
                    FROM dedupe_review_queue
                    WHERE status = 'resolved'
                    """
                )
                result = cursor.fetchone()
                avg_resolution_time = result[0] if result and result[0] else 0

                # Get conflict type distribution
                cursor.execute(
                    """
                    SELECT reason, COUNT(*) as count
                    FROM dedupe_review_queue
                    GROUP BY reason
                    ORDER BY count DESC
                    LIMIT 10
                    """
                )
                top_reasons = cursor.fetchall()

                return {
                    "status_counts": status_counts,
                    "avg_resolution_time_seconds": avg_resolution_time,
                    "avg_resolution_time_readable": self._format_duration(
                        avg_resolution_time
                    ),
                    "top_reasons": [
                        {"reason": r[0], "count": r[1]} for r in top_reasons
                    ],
                }

        except Exception as e:
            logger.error(f"Failed to get review statistics: {e}")
            return {}

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} minutes"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f} hours"
        else:
            return f"{seconds / 86400:.1f} days"

    # Asset Management Methods
    def get_businesses_needing_screenshots(
        self, limit: int = None
    ) -> list[dict[str, Any]]:
        """Get businesses that need screenshots taken."""
        try:
            with self.cursor() as cursor:
                query = """
                SELECT DISTINCT b.id, b.name, b.website
                FROM businesses b
                LEFT JOIN assets a ON b.id = a.business_id AND a.asset_type = 'screenshot'
                WHERE b.website IS NOT NULL
                  AND b.website != ''
                  AND a.id IS NULL
                ORDER BY b.id
                """

                params = []
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                results = cursor.fetchall()

                if not results:
                    return []

                # Convert to list of dictionaries
                businesses = []
                for row in results:
                    businesses.append({"id": row[0], "name": row[1], "website": row[2]})

                return businesses

        except Exception as e:
            logger.error(f"Failed to get businesses needing screenshots: {e}")
            return []

    def create_asset(
        self, business_id: int, asset_type: str, file_path: str = None, url: str = None
    ) -> bool:
        """Create an asset record."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO assets (business_id, asset_type, file_path, url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (business_id, asset_type, file_path, url),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to create asset: {e}")
            return False

    def get_businesses_needing_mockups(self, limit: int = None) -> list[dict[str, Any]]:
        """Get businesses that need mockups generated."""
        try:
            with self.cursor() as cursor:
                query = """
                SELECT DISTINCT b.id, b.name, b.website
                FROM businesses b
                INNER JOIN assets screenshot_asset ON b.id = screenshot_asset.business_id
                    AND screenshot_asset.asset_type = 'screenshot'
                LEFT JOIN assets mockup_asset ON b.id = mockup_asset.business_id
                    AND mockup_asset.asset_type = 'mockup'
                WHERE mockup_asset.id IS NULL
                ORDER BY b.id
                """

                params = []
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                results = cursor.fetchall()

                if not results:
                    return []

                # Convert to list of dictionaries
                businesses = []
                for row in results:
                    businesses.append({"id": row[0], "name": row[1], "website": row[2]})

                return businesses

        except Exception as e:
            logger.error(f"Failed to get businesses needing mockups: {e}")
            return []

    def get_business_asset(
        self, business_id: int, asset_type: str
    ) -> Optional[dict[str, Any]]:
        """Get an asset for a business by type."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, business_id, asset_type, file_path, url, created_at
                    FROM assets
                    WHERE business_id = %s AND asset_type = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (business_id, asset_type),
                )
                result = cursor.fetchone()

                if result:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result))

                return None

        except Exception as e:
            logger.error(f"Failed to get business asset: {e}")
            return None

    def get_businesses_for_email(
        self,
        force: bool = False,
        business_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get businesses ready for email sending."""
        try:
            with self.cursor() as cursor:
                # Build the query - join with assets table to get mockup URLs and stage_results for score
                # Also exclude modern sites by checking processing_status
                query = """
                SELECT b.id, b.name, b.email, b.phone, b.address, b.city, b.state, b.zip,
                       b.website, a.url as mockup_url, '' as contact_name,
                       COALESCE((sr.results->>'score')::int, 0) as score, '' as notes
                FROM businesses b
                LEFT JOIN emails e ON b.id = e.business_id
                LEFT JOIN assets a ON b.id = a.business_id AND a.asset_type = 'mockup'
                LEFT JOIN stage_results sr ON b.id = sr.business_id AND sr.stage = 'score'
                LEFT JOIN processing_status ps ON b.id = ps.business_id AND ps.stage = 'enrich'
                WHERE b.email IS NOT NULL
                  AND b.email != ''
                  AND a.url IS NOT NULL
                  AND a.url != ''
                  -- Exclude modern sites (PageSpeed >= 90)
                  AND (ps.skip_reason IS NULL OR ps.skip_reason != 'modern_site')
                """

                # Add filters
                params = []
                if not force:
                    # Only include businesses that haven't been emailed yet
                    query += " AND e.id IS NULL"

                if business_id is not None:
                    # Filter by business ID
                    query += " AND b.id = %s"
                    params.append(business_id)

                # Order by ID and limit
                query += " ORDER BY b.id"
                if limit is not None:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Convert to list of dictionaries
                columns = [desc[0] for desc in cursor.description]
                businesses = [dict(zip(columns, row)) for row in rows]
                logger.info(f"Found {len(businesses)} businesses for email sending")
                return businesses

        except Exception as e:
            logger.error(f"Error getting businesses for email: {e}")
            return []

    def check_unsubscribed(self, email: str) -> bool:
        """Check if an email address is unsubscribed."""
        try:
            with self.cursor() as cursor:
                cursor.execute("SELECT id FROM unsubscribes WHERE email = %s", (email,))
                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Error checking unsubscribe status: {e}")
            return False

    def record_email_sent(self, business_id: int, email_data: dict[str, Any]) -> bool:
        """Record that an email was sent to a business."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO emails (business_id, subject, content, sent_at, status)
                    VALUES (%s, %s, %s, NOW(), 'sent')
                    """,
                    (
                        business_id,
                        email_data.get("subject", ""),
                        email_data.get("content", ""),
                    ),
                )
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error recording email sent: {e}")
            return False

    def get_email_stats(self) -> dict[str, Any]:
        """Get email sending statistics."""
        try:
            with self.cursor() as cursor:
                # Get total emails sent
                cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent'")
                total_sent = cursor.fetchone()[0] or 0

                # Get emails sent today
                cursor.execute(
                    "SELECT COUNT(*) FROM emails WHERE status = 'sent' AND DATE(sent_at) = CURRENT_DATE"
                )
                sent_today = cursor.fetchone()[0] or 0

                # Get businesses with emails vs total businesses
                cursor.execute(
                    "SELECT COUNT(DISTINCT business_id) FROM emails WHERE status = 'sent'"
                )
                businesses_emailed = cursor.fetchone()[0] or 0

                cursor.execute(
                    "SELECT COUNT(*) FROM businesses WHERE email IS NOT NULL AND email != ''"
                )
                total_businesses_with_email = cursor.fetchone()[0] or 0

                return {
                    "total_sent": total_sent,
                    "sent_today": sent_today,
                    "businesses_emailed": businesses_emailed,
                    "total_businesses_with_email": total_businesses_with_email,
                    "email_coverage": (
                        businesses_emailed / max(total_businesses_with_email, 1)
                    )
                    * 100,
                }

        except Exception as e:
            logger.error(f"Error getting email stats: {e}")
            return {
                "total_sent": 0,
                "sent_today": 0,
                "businesses_emailed": 0,
                "total_businesses_with_email": 0,
                "email_coverage": 0.0,
            }

    def is_email_unsubscribed(self, email: str) -> bool:
        """Check if an email address is unsubscribed."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM unsubscribes WHERE email = %s", (email.lower(),)
                )
                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Error checking unsubscribe status: {e}")
            return False

    def add_unsubscribe(
        self,
        email: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Add an email to the unsubscribe list."""
        try:
            with self.cursor() as cursor:
                # Check if already unsubscribed
                cursor.execute("SELECT id FROM unsubscribes WHERE email = %s", (email,))
                if cursor.fetchone() is not None:
                    logger.info(f"Email already unsubscribed: {email}")
                    return True

                cursor.execute(
                    """
                    INSERT INTO unsubscribes (email, reason, ip_address, user_agent, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (email, reason or "", ip_address or "", user_agent or ""),
                )
                logger.info(f"Added unsubscribe for email: {email}")
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error adding unsubscribe for {email}: {e}")
            return False

    def log_email_sent(
        self,
        business_id: int,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        message_id: str,
        status: str = "sent",
        error_message: Optional[str] = None,
    ) -> bool:
        """Log that an email was sent."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO emails (
                        business_id, recipient_email, recipient_name, subject,
                        message_id, status, error_message, sent_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        business_id,
                        recipient_email,
                        recipient_name,
                        subject,
                        message_id,
                        status,
                        error_message,
                    ),
                )
                logger.info(
                    f"Logged email sent to {recipient_email} for business {business_id}"
                )
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error logging email: {e}")
            return False

    def save_email_record(
        self,
        business_id: int,
        to_email: str,
        to_name: str,
        subject: str,
        message_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Save an email record to the database."""
        try:
            with self.cursor() as cursor:
                # Insert the email record - match actual table structure
                cursor.execute(
                    """
                    INSERT INTO emails (
                        business_id, to_email, template, status, sendgrid_message_id, sent_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        business_id,
                        to_email,
                        f"{subject} (to: {to_name})",  # Store subject and name in template field
                        status,
                        message_id or "",
                    ),
                )
                logger.info(f"Saved email record for business {business_id}")
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error saving email record: {e}")
            return False

    def read_text(self, file_path: str) -> str:
        """Read text content from a file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    # Data Preservation Methods
    def record_backup_metadata(
        self,
        backup_id: str,
        operation_type: str,
        business_ids: list[int],
        backup_path: str,
        backup_size: int,
        checksum: str,
    ) -> bool:
        """Record backup metadata in the database."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dedupe_backup_metadata
                    (backup_id, operation_type, business_ids, backup_path, backup_size, checksum)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        backup_id,
                        operation_type,
                        business_ids,
                        backup_path,
                        backup_size,
                        checksum,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record backup metadata: {e}")
            return False

    def get_backup_metadata(self, backup_id: str) -> Optional[dict[str, Any]]:
        """Get backup metadata by backup ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT backup_id, operation_type, business_ids, backup_path,
                           backup_size, checksum, created_at, restored_at, restored_by
                    FROM dedupe_backup_metadata
                    WHERE backup_id = %s
                    """,
                    (backup_id,),
                )
                result = cursor.fetchone()

                if result:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result))
                return None
        except Exception as e:
            logger.error(f"Failed to get backup metadata for {backup_id}: {e}")
            return None

    def update_backup_restored(
        self, backup_id: str, user_id: Optional[str] = None
    ) -> bool:
        """Update backup metadata to mark as restored."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dedupe_backup_metadata
                    SET restored_at = NOW(), restored_by = %s
                    WHERE backup_id = %s
                    """,
                    (user_id, backup_id),
                )
            return True
        except Exception as e:
            logger.error(
                f"Failed to update backup restored status for {backup_id}: {e}"
            )
            return False

    def log_dedupe_operation(
        self,
        operation_type: str,
        business1_id: Optional[int],
        business2_id: Optional[int],
        operation_data: dict[str, Any],
        status: str,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Log a deduplication operation to the audit trail."""
        try:
            import json

            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dedupe_audit_log
                    (operation_type, business1_id, business2_id, operation_data,
                     user_id, status, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        operation_type,
                        business1_id,
                        business2_id,
                        json.dumps(operation_data),
                        user_id,
                        status,
                        error_message,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to log dedupe operation: {e}")
            return False

    def get_audit_trail(
        self,
        business_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve audit trail entries."""
        query = "SELECT * FROM dedupe_audit_log WHERE 1=1"
        params = []

        if business_id:
            query += " AND (business1_id = %s OR business2_id = %s)"
            params.extend([business_id, business_id])

        if operation_type:
            query += " AND operation_type = %s"
            params.append(operation_type)

        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        try:
            with self.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []

    def create_savepoint(self, savepoint_name: str) -> bool:
        """Create a database savepoint for transaction rollback."""
        try:
            with self.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SAVEPOINT {savepoint_name}")
                logger.debug(f"Created savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to create savepoint {savepoint_name}: {e}")
            return False

    def rollback_to_savepoint(self, savepoint_name: str) -> bool:
        """Rollback to a database savepoint."""
        try:
            with self.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                logger.info(f"Rolled back to savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to rollback to savepoint {savepoint_name}: {e}")
            return False

    def release_savepoint(self, savepoint_name: str) -> bool:
        """Release a database savepoint."""
        try:
            with self.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                logger.debug(f"Released savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to release savepoint {savepoint_name}: {e}")
            return False

    def ensure_audit_tables(self) -> bool:
        """Ensure audit tables exist in the database."""
        create_audit_tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS dedupe_audit_log (
                id SERIAL PRIMARY KEY,
                operation_type VARCHAR(50) NOT NULL,
                business1_id INTEGER,
                business2_id INTEGER,
                operation_data JSONB,
                user_id VARCHAR(255),
                status VARCHAR(50) NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS dedupe_backup_metadata (
                id SERIAL PRIMARY KEY,
                backup_id VARCHAR(255) UNIQUE NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                business_ids INTEGER[],
                backup_path TEXT NOT NULL,
                backup_size BIGINT,
                checksum VARCHAR(64),
                created_at TIMESTAMP DEFAULT NOW(),
                restored_at TIMESTAMP,
                restored_by VARCHAR(255)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_audit_log_business1 ON dedupe_audit_log(business1_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_business2 ON dedupe_audit_log(business2_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON dedupe_audit_log(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_backup_metadata_backup_id ON dedupe_backup_metadata(backup_id)",
        ]

        try:
            with self.connection() as conn:
                with conn.cursor() as cursor:
                    for sql in create_audit_tables_sql:
                        cursor.execute(sql)
                conn.commit()
                logger.info("Audit tables verified/created")
                return True
        except Exception as e:
            logger.error(f"Failed to create audit tables: {e}")
            return False

    def get_related_business_data(self, business_id: int) -> dict[str, Any]:
        """Get related data for a business (e.g., responses, metadata)."""
        related_data = {}

        try:
            with self.cursor() as cursor:
                # Get any related data from other tables
                # This is a placeholder - adjust based on your schema
                cursor.execute(
                    """
                    SELECT 'placeholder' as data
                    WHERE 1=0  -- Placeholder query
                    """
                )
                # related_data['other_table'] = cursor.fetchall()
        except Exception as e:
            logger.warning(
                f"Failed to get related data for business {business_id}: {e}"
            )

        return related_data

    def merge_businesses(self, primary_id: int, secondary_id: int) -> bool:
        """Merge two business records, keeping primary and removing secondary."""
        try:
            with self.connection() as conn, conn.cursor():
                # This would be a complex operation involving multiple tables
                # For now, just a placeholder
                logger.warning("merge_businesses not fully implemented")
                return False
        except Exception as e:
            logger.error(
                f"Failed to merge businesses {primary_id} and {secondary_id}: {e}"
            )
            return False

    # Log Management Methods for Web Interface
    def get_logs_with_filters(
        self,
        business_id: Optional[int] = None,
        log_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """Get logs with filtering, pagination, and search."""
        try:
            with self.cursor() as cursor:
                # Build base query to union LLM logs and HTML storage
                base_queries = []

                # Query LLM logs
                if not log_type or log_type == "llm":
                    llm_query = """
                        SELECT
                            id,
                            business_id,
                            'llm' as log_type,
                            COALESCE(prompt_text, '') as content,
                            created_at as timestamp,
                            JSONB_BUILD_OBJECT(
                                'operation', operation,
                                'model_version', model_version,
                                'tokens_prompt', tokens_prompt,
                                'tokens_completion', tokens_completion,
                                'duration_ms', duration_ms,
                                'status', status,
                                'metadata', metadata
                            ) as metadata,
                            NULL as file_path,
                            COALESCE(LENGTH(prompt_text) + LENGTH(response_json::text), 0) as content_length
                        FROM llm_logs
                        WHERE 1=1
                    """
                    base_queries.append(llm_query)

                # Query raw HTML storage
                if not log_type or log_type == "raw_html":
                    html_query = """
                        SELECT
                            id,
                            business_id,
                            'raw_html' as log_type,
                            COALESCE(original_url, '') as content,
                            created_at as timestamp,
                            JSONB_BUILD_OBJECT(
                                'original_url', original_url,
                                'compression_ratio', compression_ratio,
                                'content_hash', content_hash,
                                'size_bytes', size_bytes
                            ) as metadata,
                            html_path as file_path,
                            COALESCE(size_bytes, 0) as content_length
                        FROM raw_html_storage
                        WHERE 1=1
                    """
                    base_queries.append(html_query)

                if not base_queries:
                    return [], 0

                # Combine queries
                main_query = f"({') UNION ALL ('.join(base_queries)})"

                # Count query for pagination
                count_query = f"SELECT COUNT(*) FROM ({main_query}) as combined_logs"

                # Add filters
                filter_conditions = []
                filter_params = []

                if business_id is not None:
                    filter_conditions.append("business_id = %s")
                    filter_params.append(business_id)

                if start_date:
                    filter_conditions.append("timestamp >= %s")
                    filter_params.append(start_date)

                if end_date:
                    filter_conditions.append("timestamp <= %s")
                    filter_params.append(end_date)

                if search_query:
                    filter_conditions.append("content ILIKE %s")
                    filter_params.append(f"%{search_query}%")

                # Apply filters to both count and data queries
                if filter_conditions:
                    filter_clause = " WHERE " + " AND ".join(filter_conditions)
                    count_query = f"SELECT COUNT(*) FROM ({main_query}) as combined_logs{filter_clause}"
                    main_query = (
                        f"SELECT * FROM ({main_query}) as combined_logs{filter_clause}"
                    )
                else:
                    main_query = f"SELECT * FROM ({main_query}) as combined_logs"

                # Get total count
                cursor.execute(count_query, filter_params)
                total_count = cursor.fetchone()[0] or 0

                # Add sorting and pagination
                valid_sort_fields = ["timestamp", "business_id", "log_type", "id"]
                if sort_by not in valid_sort_fields:
                    sort_by = "timestamp"

                sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
                main_query += f" ORDER BY {sort_by} {sort_order} LIMIT %s OFFSET %s"

                # Execute data query
                data_params = filter_params + [limit, offset]
                cursor.execute(main_query, data_params)

                # Convert results to dictionaries
                columns = [desc[0] for desc in cursor.description]
                logs = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Convert metadata from JSON if needed
                for log in logs:
                    if isinstance(log.get("metadata"), str):
                        try:
                            log["metadata"] = json.loads(log["metadata"])
                        except (json.JSONDecodeError, TypeError):
                            log["metadata"] = {}

                logger.info(f"Retrieved {len(logs)} logs (total: {total_count})")
                return logs, total_count

        except Exception as e:
            logger.error(f"Error fetching logs with filters: {e}")
            return [], 0

    def get_log_by_id(self, log_id: int) -> Optional[dict[str, Any]]:
        """Get a single log entry by ID."""
        try:
            with self.cursor() as cursor:
                # Try LLM logs first
                cursor.execute(
                    """
                    SELECT
                        id,
                        business_id,
                        'llm' as log_type,
                        COALESCE(prompt_text || E'\n\n--- Response ---\n' || response_json::text, '') as content,
                        created_at as timestamp,
                        JSONB_BUILD_OBJECT(
                            'operation', operation,
                            'model_version', model_version,
                            'tokens_prompt', tokens_prompt,
                            'tokens_completion', tokens_completion,
                            'duration_ms', duration_ms,
                            'status', status,
                            'metadata', metadata
                        ) as metadata,
                        NULL as file_path,
                        COALESCE(LENGTH(prompt_text) + LENGTH(response_json::text), 0) as content_length
                    FROM llm_logs
                    WHERE id = %s
                """,
                    (log_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    log = dict(zip(columns, result))

                    if isinstance(log.get("metadata"), str):
                        try:
                            log["metadata"] = json.loads(log["metadata"])
                        except (json.JSONDecodeError, TypeError):
                            log["metadata"] = {}

                    return log

                # Try raw HTML storage
                cursor.execute(
                    """
                    SELECT
                        id,
                        business_id,
                        'raw_html' as log_type,
                        COALESCE('URL: ' || original_url || E'\nPath: ' || html_path, '') as content,
                        created_at as timestamp,
                        JSONB_BUILD_OBJECT(
                            'original_url', original_url,
                            'compression_ratio', compression_ratio,
                            'content_hash', content_hash,
                            'size_bytes', size_bytes
                        ) as metadata,
                        html_path as file_path,
                        COALESCE(size_bytes, 0) as content_length
                    FROM raw_html_storage
                    WHERE id = %s
                """,
                    (log_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    log = dict(zip(columns, result))

                    if isinstance(log.get("metadata"), str):
                        try:
                            log["metadata"] = json.loads(log["metadata"])
                        except (json.JSONDecodeError, TypeError):
                            log["metadata"] = {}

                    return log

                return None

        except Exception as e:
            logger.error(f"Error fetching log by ID {log_id}: {e}")
            return None

    def get_log_statistics(self) -> dict[str, Any]:
        """Get statistical information about logs."""
        try:
            with self.cursor() as cursor:
                stats = {
                    "total_logs": 0,
                    "logs_by_type": {},
                    "logs_by_business": {},
                    "date_range": {},
                    "storage_usage": {},
                }

                # Count LLM logs
                cursor.execute("SELECT COUNT(*) FROM llm_logs")
                llm_count = cursor.fetchone()[0] or 0

                # Count raw HTML logs
                cursor.execute("SELECT COUNT(*) FROM raw_html_storage")
                html_count = cursor.fetchone()[0] or 0

                stats["total_logs"] = llm_count + html_count
                stats["logs_by_type"] = {"llm": llm_count, "raw_html": html_count}

                # Get date range for LLM logs
                cursor.execute(
                    """
                    SELECT MIN(created_at), MAX(created_at)
                    FROM llm_logs
                    WHERE created_at IS NOT NULL
                """
                )
                llm_dates = cursor.fetchone()

                # Get date range for HTML logs
                cursor.execute(
                    """
                    SELECT MIN(created_at), MAX(created_at)
                    FROM raw_html_storage
                    WHERE created_at IS NOT NULL
                """
                )
                html_dates = cursor.fetchone()

                # Combine date ranges
                min_dates = [
                    d
                    for d in [
                        llm_dates[0] if llm_dates else None,
                        html_dates[0] if html_dates else None,
                    ]
                    if d
                ]
                max_dates = [
                    d
                    for d in [
                        llm_dates[1] if llm_dates else None,
                        html_dates[1] if html_dates else None,
                    ]
                    if d
                ]

                if min_dates and max_dates:
                    stats["date_range"] = {
                        "earliest": min(min_dates).isoformat(),
                        "latest": max(max_dates).isoformat(),
                    }

                # Get top businesses by log count
                cursor.execute(
                    """
                    SELECT business_id, COUNT(*) as log_count
                    FROM (
                        SELECT business_id FROM llm_logs
                        UNION ALL
                        SELECT business_id FROM raw_html_storage
                    ) combined
                    GROUP BY business_id
                    ORDER BY log_count DESC
                    LIMIT 10
                """
                )

                business_stats = cursor.fetchall()
                stats["logs_by_business"] = {
                    str(row[0]): row[1] for row in business_stats
                }

                return stats

        except Exception as e:
            logger.error(f"Error calculating log statistics: {e}")
            return {
                "total_logs": 0,
                "logs_by_type": {},
                "logs_by_business": {},
                "date_range": {},
                "storage_usage": {},
            }

    def get_available_log_types(self) -> list[str]:
        """Get list of available log types in the database."""
        return ["llm", "raw_html"]

    def get_businesses_with_logs(self) -> list[dict[str, Any]]:
        """Get list of businesses that have log entries."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT b.id, COALESCE(b.name, 'Unknown') as name
                    FROM businesses b
                    WHERE b.id IN (
                        SELECT DISTINCT business_id FROM llm_logs
                        UNION
                        SELECT DISTINCT business_id FROM raw_html_storage
                    )
                    AND b.id IS NOT NULL
                    ORDER BY b.name
                """
                )

                return [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting businesses with logs: {e}")
            return []

    def get_all_businesses(self) -> list[dict[str, Any]]:
        """Get all businesses for general purposes."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, COALESCE(name, 'Unknown') as name, website
                    FROM businesses
                    ORDER BY name
                """
                )

                return [
                    {"id": row[0], "name": row[1], "website": row[2]}
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Error getting all businesses: {e}")
            return []

    def archive_business(self, business_id: int, reason: str = "manual_reject") -> bool:
        """Archive a business by setting archived flag and reason.

        Args:
            business_id: Business ID to archive
            reason: Reason for archiving

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.cursor() as cursor:
                # First check if archived column exists, if not add it
                cursor.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'businesses' AND column_name = 'archived'
                """
                )

                if not cursor.fetchone():
                    # Add archived columns
                    cursor.execute(
                        """
                        ALTER TABLE businesses
                        ADD COLUMN archived BOOLEAN DEFAULT FALSE,
                        ADD COLUMN archive_reason TEXT,
                        ADD COLUMN archived_at TIMESTAMP
                    """
                    )
                    logger.info("Added archive columns to businesses table")

                # Archive the business
                cursor.execute(
                    """
                    UPDATE businesses
                    SET archived = TRUE,
                        archive_reason = %s,
                        archived_at = NOW()
                    WHERE id = %s
                """,
                    (reason, business_id),
                )

                success = cursor.rowcount > 0
                if success:
                    logger.info(
                        f"Archived business {business_id} with reason: {reason}"
                    )
                else:
                    logger.warning(
                        f"No business found with ID {business_id} to archive"
                    )

                return success

        except Exception as e:
            logger.error(f"Error archiving business {business_id}: {e}")
            return False

    def restore_business(self, business_id: int) -> bool:
        """Restore an archived business by clearing archived flag.

        Args:
            business_id: Business ID to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE businesses
                    SET archived = FALSE,
                        archive_reason = NULL,
                        archived_at = NULL
                    WHERE id = %s
                """,
                    (business_id,),
                )

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Restored business {business_id}")
                else:
                    logger.warning(
                        f"No business found with ID {business_id} to restore"
                    )

                return success

        except Exception as e:
            logger.error(f"Error restoring business {business_id}: {e}")
            return False

    def list_businesses(
        self,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        search: str = "",
    ) -> list[dict[str, Any]]:
        """List businesses with optional filtering.

        Args:
            include_archived: Whether to include archived businesses
            limit: Maximum number of results
            offset: Pagination offset
            search: Search term for name/address

        Returns:
            List of business dictionaries
        """
        try:
            with self.cursor() as cursor:
                # Build query conditions
                conditions = []
                params = []

                if not include_archived:
                    conditions.append("(archived IS NULL OR archived = FALSE)")

                if search:
                    conditions.append("(name ILIKE %s OR address ILIKE %s)")
                    search_term = f"%{search}%"
                    params.extend([search_term, search_term])

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Add limit and offset
                params.extend([limit, offset])

                cursor.execute(
                    f"""
                    SELECT
                        id, name, address, city, state, website, phone, email,
                        archived, archive_reason, archived_at,
                        created_at, score, vertical
                    FROM businesses
                    {where_clause}
                    ORDER BY
                        CASE WHEN archived THEN 1 ELSE 0 END,
                        created_at DESC
                    LIMIT %s OFFSET %s
                """,
                    params,
                )

                businesses = []
                for row in cursor.fetchall():
                    business = {
                        "id": row[0],
                        "name": row[1],
                        "address": row[2],
                        "city": row[3],
                        "state": row[4],
                        "website": row[5],
                        "phone": row[6],
                        "email": row[7],
                        "archived": row[8] or False,
                        "archive_reason": row[9],
                        "archived_at": row[10],
                        "created_at": row[11],
                        "score": row[12],
                        "vertical": row[13],
                    }
                    businesses.append(business)

                return businesses

        except Exception as e:
            logger.error(f"Error listing businesses: {e}")
            return []

    def count_businesses(self, include_archived: bool = False, search: str = "") -> int:
        """Count businesses with optional filtering.

        Args:
            include_archived: Whether to include archived businesses
            search: Search term for name/address

        Returns:
            Total count of businesses matching criteria
        """
        try:
            with self.cursor() as cursor:
                # Build query conditions
                conditions = []
                params = []

                if not include_archived:
                    conditions.append("(archived IS NULL OR archived = FALSE)")

                if search:
                    conditions.append("(name ILIKE %s OR address ILIKE %s)")
                    search_term = f"%{search}%"
                    params.extend([search_term, search_term])

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                cursor.execute(
                    f"""
                    SELECT COUNT(*) FROM businesses {where_clause}
                """,
                    params,
                )

                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error counting businesses: {e}")
            return 0

    def list_mockups(
        self,
        business_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        version: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List mockups with optional filtering.

        Args:
            business_id: Filter by business ID
            status: Filter by QA status
            limit: Maximum number of results
            offset: Pagination offset
            version: Show specific version or all versions

        Returns:
            List of mockup dictionaries
        """
        try:
            with self.cursor() as cursor:
                # First check if mockups table exists, if not create it
                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_name = 'mockups'
                """
                )

                if not cursor.fetchone():
                    # Create mockups table
                    cursor.execute(
                        """
                        CREATE TABLE mockups (
                            id SERIAL PRIMARY KEY,
                            business_id INTEGER REFERENCES businesses(id),
                            version INTEGER DEFAULT 1,
                            content JSONB,
                            status TEXT DEFAULT 'pending',
                            qa_score DECIMAL(3,1),
                            ai_confidence DECIMAL(3,2),
                            reviewer_notes TEXT,
                            revised_prompt TEXT,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        );

                        CREATE INDEX idx_mockups_business_id ON mockups(business_id);
                        CREATE INDEX idx_mockups_status ON mockups(status);
                        CREATE INDEX idx_mockups_version ON mockups(business_id, version);
                    """
                    )
                    logger.info("Created mockups table with indexes")

                # Build query conditions
                conditions = []
                params = []

                if business_id:
                    conditions.append("business_id = %s")
                    params.append(business_id)

                if status:
                    conditions.append("status = %s")
                    params.append(status)

                if version:
                    if version == "latest":
                        # Get only the latest version for each business
                        conditions.append(
                            """
                            (business_id, version) IN (
                                SELECT business_id, MAX(version)
                                FROM mockups
                                GROUP BY business_id
                            )
                        """
                        )
                    else:
                        conditions.append("version = %s")
                        params.append(int(version))

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Add limit and offset
                params.extend([limit, offset])

                cursor.execute(
                    f"""
                    SELECT
                        m.id, m.business_id, m.version, m.content, m.status,
                        m.qa_score, m.ai_confidence, m.reviewer_notes,
                        m.created_at, m.updated_at,
                        b.name as business_name, b.website
                    FROM mockups m
                    LEFT JOIN businesses b ON m.business_id = b.id
                    {where_clause}
                    ORDER BY m.updated_at DESC
                    LIMIT %s OFFSET %s
                """,
                    params,
                )

                mockups = []
                for row in cursor.fetchall():
                    mockup = {
                        "id": row[0],
                        "business_id": row[1],
                        "version": row[2],
                        "content": row[3] or {},
                        "status": row[4],
                        "qa_score": float(row[5]) if row[5] is not None else None,
                        "ai_confidence": float(row[6]) if row[6] is not None else None,
                        "reviewer_notes": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                        "business_name": row[10],
                        "business_website": row[11],
                    }
                    mockups.append(mockup)

                return mockups

        except Exception as e:
            logger.error(f"Error listing mockups: {e}")
            return []

    def count_mockups(
        self,
        business_id: Optional[int] = None,
        status: Optional[str] = None,
        version: Optional[str] = None,
    ) -> int:
        """Count mockups with optional filtering."""
        try:
            with self.cursor() as cursor:
                # Build query conditions
                conditions = []
                params = []

                if business_id:
                    conditions.append("business_id = %s")
                    params.append(business_id)

                if status:
                    conditions.append("status = %s")
                    params.append(status)

                if version and version != "latest":
                    conditions.append("version = %s")
                    params.append(int(version))

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                if version == "latest":
                    # Count only latest versions
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT business_id
                            FROM mockups
                            {where_clause}
                        ) latest_mockups
                    """,
                        params,
                    )
                else:
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) FROM mockups {where_clause}
                    """,
                        params,
                    )

                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error counting mockups: {e}")
            return 0

    def get_mockup_by_id(self, mockup_id: int) -> Optional[dict[str, Any]]:
        """Get mockup by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, business_id, version, content, status,
                        qa_score, ai_confidence, reviewer_notes, revised_prompt,
                        created_at, updated_at
                    FROM mockups
                    WHERE id = %s
                """,
                    (mockup_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    "id": row[0],
                    "business_id": row[1],
                    "version": row[2],
                    "content": row[3] or {},
                    "status": row[4],
                    "qa_score": float(row[5]) if row[5] is not None else None,
                    "ai_confidence": float(row[6]) if row[6] is not None else None,
                    "reviewer_notes": row[7],
                    "revised_prompt": row[8],
                    "created_at": row[9],
                    "updated_at": row[10],
                }

        except Exception as e:
            logger.error(f"Error getting mockup {mockup_id}: {e}")
            return None

    def get_mockup_with_versions(self, mockup_id: int) -> Optional[dict[str, Any]]:
        """Get mockup with all its versions."""
        try:
            # First get the main mockup
            mockup = self.get_mockup_by_id(mockup_id)
            if not mockup:
                return None

            # Get all versions for this business
            versions = self.get_mockup_versions_by_business(mockup["business_id"])
            mockup["versions"] = versions

            return mockup

        except Exception as e:
            logger.error(f"Error getting mockup with versions {mockup_id}: {e}")
            return None

    def get_mockup_versions(self, mockup_id: int) -> list[dict[str, Any]]:
        """Get all versions for a mockup's business."""
        try:
            # First get the business_id for this mockup
            mockup = self.get_mockup_by_id(mockup_id)
            if not mockup:
                return []

            return self.get_mockup_versions_by_business(mockup["business_id"])

        except Exception as e:
            logger.error(f"Error getting versions for mockup {mockup_id}: {e}")
            return []

    def get_mockup_versions_by_business(self, business_id: int) -> list[dict[str, Any]]:
        """Get all mockup versions for a business."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, business_id, version, content, status,
                        qa_score, ai_confidence, reviewer_notes,
                        created_at, updated_at
                    FROM mockups
                    WHERE business_id = %s
                    ORDER BY version DESC
                """,
                    (business_id,),
                )

                versions = []
                for row in cursor.fetchall():
                    version = {
                        "id": row[0],
                        "business_id": row[1],
                        "version": row[2],
                        "content": row[3] or {},
                        "status": row[4],
                        "qa_score": float(row[5]) if row[5] is not None else None,
                        "ai_confidence": float(row[6]) if row[6] is not None else None,
                        "reviewer_notes": row[7],
                        "created_at": row[8],
                        "updated_at": row[9],
                    }
                    versions.append(version)

                return versions

        except Exception as e:
            logger.error(f"Error getting versions for business {business_id}: {e}")
            return []

    def get_mockup_version_by_id(self, version_id: int) -> Optional[dict[str, Any]]:
        """Get specific mockup version by ID."""
        return self.get_mockup_by_id(version_id)  # Same as get_mockup_by_id

    def apply_qa_override(
        self,
        mockup_id: int,
        new_status: str,
        qa_score: Optional[float] = None,
        reviewer_notes: str = "",
        revised_prompt: Optional[str] = None,
    ) -> bool:
        """Apply QA override to a mockup."""
        try:
            with self.cursor() as cursor:
                # Build update query dynamically
                updates = ["status = %s", "updated_at = NOW()"]
                params = [new_status]

                if qa_score is not None:
                    updates.append("qa_score = %s")
                    params.append(qa_score)

                if reviewer_notes:
                    updates.append("reviewer_notes = %s")
                    params.append(reviewer_notes)

                if revised_prompt:
                    updates.append("revised_prompt = %s")
                    params.append(revised_prompt)

                params.append(mockup_id)

                cursor.execute(
                    f"""
                    UPDATE mockups
                    SET {', '.join(updates)}
                    WHERE id = %s
                """,
                    params,
                )

                success = cursor.rowcount > 0
                if success:
                    logger.info(
                        f"Applied QA override to mockup {mockup_id}: {new_status}"
                    )
                else:
                    logger.warning(f"No mockup found with ID {mockup_id} to update")

                return success

        except Exception as e:
            logger.error(f"Error applying QA override to mockup {mockup_id}: {e}")
            return False

    def update_mockup_status(self, mockup_id: int, new_status: str) -> bool:
        """Update mockup status."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE mockups
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                """,
                    (new_status, mockup_id),
                )

                success = cursor.rowcount > 0
                if success:
                    logger.info(f"Updated mockup {mockup_id} status to {new_status}")

                return success

        except Exception as e:
            logger.error(f"Error updating mockup {mockup_id} status: {e}")
            return False

    def create_mockup(
        self,
        business_id: int,
        content: dict[str, Any],
        version: int = 1,
        status: str = "pending",
        qa_score: Optional[float] = None,
        ai_confidence: Optional[float] = None,
    ) -> Optional[int]:
        """Create a new mockup."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mockups (
                        business_id, version, content, status, qa_score, ai_confidence
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (business_id, version, content, status, qa_score, ai_confidence),
                )

                mockup_id = cursor.fetchone()[0]
                logger.info(f"Created mockup {mockup_id} for business {business_id}")
                return mockup_id

        except Exception as e:
            logger.error(f"Error creating mockup for business {business_id}: {e}")
            return None

    # Follow-up Email Campaign Methods

    def create_followup_campaign(self, campaign_data: dict[str, Any]) -> bool:
        """Create a new follow-up campaign."""
        try:
            with self.cursor() as cursor:
                # Create followup_campaigns table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS followup_campaigns (
                        campaign_id VARCHAR(255) PRIMARY KEY,
                        business_id INTEGER NOT NULL,
                        initial_email_id VARCHAR(255),
                        max_follow_ups INTEGER DEFAULT 3,
                        respect_unsubscribe BOOLEAN DEFAULT TRUE,
                        skip_if_engaged BOOLEAN DEFAULT TRUE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        templates JSONB
                    )
                """
                )

                # Insert campaign
                cursor.execute(
                    """
                    INSERT INTO followup_campaigns (
                        campaign_id, business_id, initial_email_id, max_follow_ups,
                        respect_unsubscribe, skip_if_engaged, is_active, templates,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        campaign_data["campaign_id"],
                        campaign_data["business_id"],
                        campaign_data["initial_email_id"],
                        campaign_data["max_follow_ups"],
                        campaign_data["respect_unsubscribe"],
                        campaign_data["skip_if_engaged"],
                        campaign_data["is_active"],
                        json.dumps(campaign_data["templates"]),
                        campaign_data["created_at"],
                    ),
                )

                logger.info(
                    f"Created follow-up campaign {campaign_data['campaign_id']}"
                )
                return True

        except Exception as e:
            logger.error(f"Error creating follow-up campaign: {e}")
            return False

    def get_followup_campaign(self, campaign_id: str) -> Optional[dict[str, Any]]:
        """Get follow-up campaign by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT campaign_id, business_id, initial_email_id, max_follow_ups,
                           respect_unsubscribe, skip_if_engaged, is_active, templates,
                           created_at, updated_at
                    FROM followup_campaigns
                    WHERE campaign_id = %s
                """,
                    (campaign_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    campaign_data = dict(zip(columns, result))

                    # Parse JSON templates
                    if campaign_data["templates"]:
                        campaign_data["templates"] = json.loads(
                            campaign_data["templates"]
                        )

                    return campaign_data

                return None

        except Exception as e:
            logger.error(f"Error getting follow-up campaign {campaign_id}: {e}")
            return None

    def create_scheduled_followup(self, followup_data: dict[str, Any]) -> bool:
        """Create a scheduled follow-up email."""
        try:
            with self.cursor() as cursor:
                # Create scheduled_followups table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scheduled_followups (
                        follow_up_id VARCHAR(255) PRIMARY KEY,
                        campaign_id VARCHAR(255) NOT NULL,
                        business_id INTEGER NOT NULL,
                        recipient_email VARCHAR(255) NOT NULL,
                        template_id VARCHAR(255) NOT NULL,
                        scheduled_for TIMESTAMP NOT NULL,
                        status VARCHAR(50) DEFAULT 'scheduled',
                        attempt_count INTEGER DEFAULT 0,
                        last_attempt TIMESTAMP,
                        engagement_level VARCHAR(50) DEFAULT 'unknown',
                        created_at TIMESTAMP DEFAULT NOW(),
                        error_message TEXT,
                        notes TEXT
                    )
                """
                )

                # Insert scheduled follow-up
                cursor.execute(
                    """
                    INSERT INTO scheduled_followups (
                        follow_up_id, campaign_id, business_id, recipient_email,
                        template_id, scheduled_for, status, engagement_level, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        followup_data["follow_up_id"],
                        followup_data["campaign_id"],
                        followup_data["business_id"],
                        followup_data["recipient_email"],
                        followup_data["template_id"],
                        followup_data["scheduled_for"],
                        followup_data["status"],
                        followup_data["engagement_level"],
                        followup_data["created_at"],
                    ),
                )

                return True

        except Exception as e:
            logger.error(f"Error creating scheduled follow-up: {e}")
            return False

    def get_pending_followups(
        self, due_before: datetime, limit: int = 100
    ) -> List[dict[str, Any]]:
        """Get pending follow-ups that are due to be sent."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT follow_up_id, campaign_id, business_id, recipient_email,
                           template_id, scheduled_for, status, attempt_count,
                           last_attempt, engagement_level, created_at
                    FROM scheduled_followups
                    WHERE status = 'scheduled'
                      AND scheduled_for <= %s
                    ORDER BY scheduled_for ASC
                    LIMIT %s
                """,
                    (due_before, limit),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting pending follow-ups: {e}")
            return []

    def update_followup_status(
        self,
        follow_up_id: str,
        status: str,
        notes: str = None,
        error_message: str = None,
    ) -> bool:
        """Update follow-up status."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE scheduled_followups
                    SET status = %s,
                        last_attempt = NOW(),
                        attempt_count = attempt_count + 1,
                        notes = COALESCE(%s, notes),
                        error_message = COALESCE(%s, error_message)
                    WHERE follow_up_id = %s
                """,
                    (status, notes, error_message, follow_up_id),
                )

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating follow-up status: {e}")
            return False

    def get_followup_template(self, template_id: str) -> Optional[dict[str, Any]]:
        """Get follow-up template by ID."""
        try:
            with self.cursor() as cursor:
                # Get template from campaign
                cursor.execute(
                    """
                    SELECT templates
                    FROM followup_campaigns
                    WHERE templates::jsonb @> %s::jsonb
                """,
                    (json.dumps([{"template_id": template_id}]),),
                )

                result = cursor.fetchone()
                if result and result[0]:
                    templates = json.loads(result[0])
                    for template in templates:
                        if template.get("template_id") == template_id:
                            return template

                return None

        except Exception as e:
            logger.error(f"Error getting follow-up template {template_id}: {e}")
            return None

    def is_email_unsubscribed(self, email: str) -> bool:
        """Check if email is unsubscribed."""
        try:
            with self.cursor() as cursor:
                # Create unsubscribes table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unsubscribes (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        unsubscribed_at TIMESTAMP DEFAULT NOW(),
                        reason VARCHAR(255),
                        campaign_id VARCHAR(255)
                    )
                """
                )

                cursor.execute(
                    """
                    SELECT 1 FROM unsubscribes WHERE email = %s
                """,
                    (email,),
                )

                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Error checking unsubscribe status for {email}: {e}")
            return False

    def get_email_engagement(
        self, campaign_id: str, email: str
    ) -> Optional[dict[str, Any]]:
        """Get email engagement data."""
        try:
            with self.cursor() as cursor:
                # Create email_engagement table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS email_engagement (
                        id SERIAL PRIMARY KEY,
                        campaign_id VARCHAR(255) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        delivered BOOLEAN DEFAULT FALSE,
                        opened BOOLEAN DEFAULT FALSE,
                        clicked BOOLEAN DEFAULT FALSE,
                        replied BOOLEAN DEFAULT FALSE,
                        forwarded BOOLEAN DEFAULT FALSE,
                        bounced BOOLEAN DEFAULT FALSE,
                        first_opened_at TIMESTAMP,
                        last_opened_at TIMESTAMP,
                        click_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(campaign_id, email)
                    )
                """
                )

                cursor.execute(
                    """
                    SELECT delivered, opened, clicked, replied, forwarded, bounced,
                           first_opened_at, last_opened_at, click_count
                    FROM email_engagement
                    WHERE campaign_id = %s AND email = %s
                """,
                    (campaign_id, email),
                )

                result = cursor.fetchone()
                if result:
                    columns = [
                        "delivered",
                        "opened",
                        "clicked",
                        "replied",
                        "forwarded",
                        "bounced",
                        "first_opened_at",
                        "last_opened_at",
                        "click_count",
                    ]
                    return dict(zip(columns, result))

                return None

        except Exception as e:
            logger.error(f"Error getting email engagement: {e}")
            return None

    def update_email_engagement(
        self, campaign_id: str, email: str, engagement_type: str, timestamp: datetime
    ) -> bool:
        """Update email engagement tracking."""
        try:
            with self.cursor() as cursor:
                # Insert or update engagement record
                cursor.execute(
                    """
                    INSERT INTO email_engagement (campaign_id, email, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (campaign_id, email)
                    DO UPDATE SET updated_at = %s
                """,
                    (campaign_id, email, timestamp, timestamp, timestamp),
                )

                # Update specific engagement type
                if engagement_type == "delivered":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET delivered = TRUE
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (campaign_id, email),
                    )
                elif engagement_type == "opened":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET opened = TRUE,
                            first_opened_at = COALESCE(first_opened_at, %s),
                            last_opened_at = %s
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (timestamp, timestamp, campaign_id, email),
                    )
                elif engagement_type == "clicked":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET clicked = TRUE,
                            click_count = click_count + 1
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (campaign_id, email),
                    )
                elif engagement_type == "replied":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET replied = TRUE
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (campaign_id, email),
                    )
                elif engagement_type == "forwarded":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET forwarded = TRUE
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (campaign_id, email),
                    )
                elif engagement_type == "bounced":
                    cursor.execute(
                        """
                        UPDATE email_engagement
                        SET bounced = TRUE
                        WHERE campaign_id = %s AND email = %s
                    """,
                        (campaign_id, email),
                    )

                return True

        except Exception as e:
            logger.error(f"Error updating email engagement: {e}")
            return False

    def update_campaign_status(
        self, campaign_id: str, is_active: bool, reason: str = None
    ) -> bool:
        """Update campaign active status."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE followup_campaigns
                    SET is_active = %s, updated_at = NOW()
                    WHERE campaign_id = %s
                """,
                    (is_active, campaign_id),
                )

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating campaign status: {e}")
            return False

    def cancel_pending_followups(self, campaign_id: str, reason: str) -> int:
        """Cancel all pending follow-ups for a campaign."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE scheduled_followups
                    SET status = 'cancelled', notes = %s
                    WHERE campaign_id = %s AND status = 'scheduled'
                """,
                    (reason, campaign_id),
                )

                return cursor.rowcount

        except Exception as e:
            logger.error(f"Error cancelling pending follow-ups: {e}")
            return 0

    def get_followup_campaign_stats(self, campaign_id: str) -> dict[str, Any]:
        """Get statistics for a follow-up campaign."""
        try:
            with self.cursor() as cursor:
                # Get campaign info
                cursor.execute(
                    """
                    SELECT business_id, is_active, created_at
                    FROM followup_campaigns
                    WHERE campaign_id = %s
                """,
                    (campaign_id,),
                )

                campaign_info = cursor.fetchone()
                if not campaign_info:
                    return {}

                # Get follow-up statistics
                cursor.execute(
                    """
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM scheduled_followups
                    WHERE campaign_id = %s
                    GROUP BY status
                """,
                    (campaign_id,),
                )

                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get engagement statistics
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN delivered THEN 1 ELSE 0 END) as delivered,
                        SUM(CASE WHEN opened THEN 1 ELSE 0 END) as opened,
                        SUM(CASE WHEN clicked THEN 1 ELSE 0 END) as clicked,
                        SUM(CASE WHEN replied THEN 1 ELSE 0 END) as replied,
                        COUNT(*) as total_tracked
                    FROM email_engagement
                    WHERE campaign_id = %s
                """,
                    (campaign_id,),
                )

                engagement_row = cursor.fetchone()
                engagement_stats = {}
                if engagement_row:
                    engagement_stats = {
                        "delivered": engagement_row[0] or 0,
                        "opened": engagement_row[1] or 0,
                        "clicked": engagement_row[2] or 0,
                        "replied": engagement_row[3] or 0,
                        "total_tracked": engagement_row[4] or 0,
                    }

                return {
                    "campaign_id": campaign_id,
                    "business_id": campaign_info[0],
                    "is_active": campaign_info[1],
                    "created_at": (
                        campaign_info[2].isoformat() if campaign_info[2] else None
                    ),
                    "status_counts": status_counts,
                    "engagement_stats": engagement_stats,
                }

        except Exception as e:
            logger.error(f"Error getting campaign stats: {e}")
            return {}

    # Engagement Analytics Methods

    def store_engagement_event(self, event_data: dict[str, Any]) -> bool:
        """Store an engagement event."""
        try:
            with self.cursor() as cursor:
                # Create engagement_events table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS engagement_events (
                        event_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        session_id VARCHAR(255) NOT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        properties JSONB,
                        page_url TEXT,
                        referrer TEXT,
                        user_agent TEXT,
                        ip_address INET,
                        campaign_id VARCHAR(255),
                        ab_test_variant VARCHAR(100),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """
                )

                # Create indexes for better query performance
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_engagement_events_user_id
                    ON engagement_events(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_engagement_events_session_id
                    ON engagement_events(session_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_engagement_events_timestamp
                    ON engagement_events(timestamp)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_engagement_events_campaign_id
                    ON engagement_events(campaign_id)
                """
                )

                # Insert event
                cursor.execute(
                    """
                    INSERT INTO engagement_events (
                        event_id, user_id, session_id, event_type, timestamp,
                        properties, page_url, referrer, user_agent, ip_address,
                        campaign_id, ab_test_variant
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        event_data["event_id"],
                        event_data["user_id"],
                        event_data["session_id"],
                        event_data["event_type"],
                        event_data["timestamp"],
                        json.dumps(event_data.get("properties", {})),
                        event_data.get("page_url"),
                        event_data.get("referrer"),
                        event_data.get("user_agent"),
                        event_data.get("ip_address"),
                        event_data.get("campaign_id"),
                        event_data.get("ab_test_variant"),
                    ),
                )

                return True

        except Exception as e:
            logger.error(f"Error storing engagement event: {e}")
            return False

    def get_user_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get user session by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, start_time, end_time, total_events,
                           page_views, unique_pages, bounce_rate, time_on_site,
                           conversion_events, traffic_source, campaign_id, device_type
                    FROM user_sessions
                    WHERE session_id = %s
                """,
                    (session_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    session_data = dict(zip(columns, result))

                    # Parse JSON conversion_events
                    if session_data["conversion_events"]:
                        session_data["conversion_events"] = json.loads(
                            session_data["conversion_events"]
                        )

                    return session_data

                return None

        except Exception as e:
            logger.error(f"Error getting user session {session_id}: {e}")
            return None

    def update_user_session(self, session_data: dict[str, Any]) -> bool:
        """Update or create user session."""
        try:
            with self.cursor() as cursor:
                # Create user_sessions table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        total_events INTEGER DEFAULT 0,
                        page_views INTEGER DEFAULT 0,
                        unique_pages INTEGER DEFAULT 0,
                        bounce_rate FLOAT DEFAULT 0,
                        time_on_site FLOAT DEFAULT 0,
                        conversion_events JSONB,
                        traffic_source TEXT,
                        campaign_id VARCHAR(255),
                        device_type VARCHAR(50),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """
                )

                # Upsert session data
                cursor.execute(
                    """
                    INSERT INTO user_sessions (
                        session_id, user_id, start_time, end_time, total_events,
                        page_views, unique_pages, bounce_rate, time_on_site,
                        conversion_events, traffic_source, campaign_id, device_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id)
                    DO UPDATE SET
                        end_time = EXCLUDED.end_time,
                        total_events = EXCLUDED.total_events,
                        page_views = EXCLUDED.page_views,
                        unique_pages = EXCLUDED.unique_pages,
                        bounce_rate = EXCLUDED.bounce_rate,
                        time_on_site = EXCLUDED.time_on_site,
                        conversion_events = EXCLUDED.conversion_events,
                        updated_at = NOW()
                """,
                    (
                        session_data["session_id"],
                        session_data["user_id"],
                        session_data["start_time"],
                        session_data.get("end_time"),
                        session_data["total_events"],
                        session_data["page_views"],
                        session_data["unique_pages"],
                        session_data["bounce_rate"],
                        session_data["time_on_site"],
                        json.dumps(session_data.get("conversion_events", [])),
                        session_data.get("traffic_source"),
                        session_data.get("campaign_id"),
                        session_data.get("device_type"),
                    ),
                )

                return True

        except Exception as e:
            logger.error(f"Error updating user session: {e}")
            return False

    def get_session_unique_pages(self, session_id: str) -> List[str]:
        """Get unique pages visited in a session."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT page_url
                    FROM engagement_events
                    WHERE session_id = %s
                      AND page_url IS NOT NULL
                      AND event_type = 'page_view'
                """,
                    (session_id,),
                )

                results = cursor.fetchall()
                return [row[0] for row in results]

        except Exception as e:
            logger.error(f"Error getting session unique pages: {e}")
            return []

    def get_active_conversion_funnels(self) -> List[dict[str, Any]]:
        """Get all active conversion funnels."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT funnel_id, name, steps, goal_type, time_window_hours, is_active
                    FROM conversion_funnels
                    WHERE is_active = TRUE
                """
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                funnels = []
                for row in results:
                    funnel_data = dict(zip(columns, row))
                    if funnel_data["steps"]:
                        funnel_data["steps"] = json.loads(funnel_data["steps"])
                    funnels.append(funnel_data)

                return funnels

        except Exception as e:
            logger.error(f"Error getting active conversion funnels: {e}")
            return []

    def update_funnel_progress(
        self,
        funnel_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        timestamp: datetime,
    ) -> bool:
        """Update funnel progress for a user."""
        try:
            with self.cursor() as cursor:
                # Create funnel_progress table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS funnel_progress (
                        id SERIAL PRIMARY KEY,
                        funnel_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        session_id VARCHAR(255) NOT NULL,
                        step_index INTEGER NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """
                )

                cursor.execute(
                    """
                    INSERT INTO funnel_progress (funnel_id, user_id, session_id, step_index, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (funnel_id, user_id, session_id, step_index, timestamp),
                )

                return True

        except Exception as e:
            logger.error(f"Error updating funnel progress: {e}")
            return False

    def record_conversion(self, conversion_data: dict[str, Any]) -> bool:
        """Record a conversion event."""
        try:
            with self.cursor() as cursor:
                # Create conversions table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversions (
                        id SERIAL PRIMARY KEY,
                        funnel_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        session_id VARCHAR(255) NOT NULL,
                        conversion_time TIMESTAMP NOT NULL,
                        goal_type VARCHAR(100) NOT NULL,
                        event_id VARCHAR(255),
                        campaign_id VARCHAR(255),
                        ab_test_variant VARCHAR(100),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """
                )

                cursor.execute(
                    """
                    INSERT INTO conversions (
                        funnel_id, user_id, session_id, conversion_time,
                        goal_type, event_id, campaign_id, ab_test_variant
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        conversion_data["funnel_id"],
                        conversion_data["user_id"],
                        conversion_data["session_id"],
                        conversion_data["conversion_time"],
                        conversion_data["goal_type"],
                        conversion_data.get("event_id"),
                        conversion_data.get("campaign_id"),
                        conversion_data.get("ab_test_variant"),
                    ),
                )

                return True

        except Exception as e:
            logger.error(f"Error recording conversion: {e}")
            return False

    def get_user_events(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get events for a user within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, user_id, session_id, event_type, timestamp,
                           properties, page_url, referrer, campaign_id, ab_test_variant
                    FROM engagement_events
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """,
                    (user_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                events = []
                for row in results:
                    event_data = dict(zip(columns, row))
                    if event_data["properties"]:
                        event_data["properties"] = json.loads(event_data["properties"])
                    events.append(event_data)

                return events

        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return []

    def get_user_sessions(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get sessions for a user within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, start_time, end_time, total_events,
                           page_views, unique_pages, bounce_rate, time_on_site,
                           conversion_events, traffic_source, campaign_id, device_type
                    FROM user_sessions
                    WHERE user_id = %s
                      AND start_time BETWEEN %s AND %s
                    ORDER BY start_time DESC
                """,
                    (user_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                sessions = []
                for row in results:
                    session_data = dict(zip(columns, row))
                    if session_data["conversion_events"]:
                        session_data["conversion_events"] = json.loads(
                            session_data["conversion_events"]
                        )
                    sessions.append(session_data)

                return sessions

        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []

    def get_user_conversions(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get conversions for a user within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT funnel_id, user_id, session_id, conversion_time,
                           goal_type, event_id, campaign_id, ab_test_variant
                    FROM conversions
                    WHERE user_id = %s
                      AND conversion_time BETWEEN %s AND %s
                    ORDER BY conversion_time DESC
                """,
                    (user_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting user conversions: {e}")
            return []

    def get_campaign_events(
        self, campaign_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get events for a campaign within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, user_id, session_id, event_type, timestamp,
                           properties, page_url, referrer, campaign_id, ab_test_variant
                    FROM engagement_events
                    WHERE campaign_id = %s
                      AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """,
                    (campaign_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                events = []
                for row in results:
                    event_data = dict(zip(columns, row))
                    if event_data["properties"]:
                        event_data["properties"] = json.loads(event_data["properties"])
                    events.append(event_data)

                return events

        except Exception as e:
            logger.error(f"Error getting campaign events: {e}")
            return []

    def get_campaign_sessions(
        self, campaign_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get sessions for a campaign within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, start_time, end_time, total_events,
                           page_views, unique_pages, bounce_rate, time_on_site,
                           conversion_events, traffic_source, campaign_id, device_type
                    FROM user_sessions
                    WHERE campaign_id = %s
                      AND start_time BETWEEN %s AND %s
                    ORDER BY start_time DESC
                """,
                    (campaign_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                sessions = []
                for row in results:
                    session_data = dict(zip(columns, row))
                    if session_data["conversion_events"]:
                        session_data["conversion_events"] = json.loads(
                            session_data["conversion_events"]
                        )
                    sessions.append(session_data)

                return sessions

        except Exception as e:
            logger.error(f"Error getting campaign sessions: {e}")
            return []

    def get_campaign_conversions(
        self, campaign_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get conversions for a campaign within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT funnel_id, user_id, session_id, conversion_time,
                           goal_type, event_id, campaign_id, ab_test_variant
                    FROM conversions
                    WHERE campaign_id = %s
                      AND conversion_time BETWEEN %s AND %s
                    ORDER BY conversion_time DESC
                """,
                    (campaign_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting campaign conversions: {e}")
            return []

    def create_conversion_funnel(self, funnel_data: dict[str, Any]) -> bool:
        """Create a conversion funnel."""
        try:
            with self.cursor() as cursor:
                # Create conversion_funnels table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversion_funnels (
                        funnel_id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        steps JSONB NOT NULL,
                        goal_type VARCHAR(100) NOT NULL,
                        time_window_hours INTEGER DEFAULT 24,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """
                )

                cursor.execute(
                    """
                    INSERT INTO conversion_funnels (
                        funnel_id, name, steps, goal_type, time_window_hours, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    (
                        funnel_data["funnel_id"],
                        funnel_data["name"],
                        json.dumps(funnel_data["steps"]),
                        funnel_data["goal_type"],
                        funnel_data["time_window_hours"],
                        funnel_data["is_active"],
                    ),
                )

                return True

        except Exception as e:
            logger.error(f"Error creating conversion funnel: {e}")
            return False

    def get_conversion_funnel(self, funnel_id: str) -> Optional[dict[str, Any]]:
        """Get conversion funnel by ID."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT funnel_id, name, steps, goal_type, time_window_hours, is_active
                    FROM conversion_funnels
                    WHERE funnel_id = %s
                """,
                    (funnel_id,),
                )

                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    funnel_data = dict(zip(columns, result))
                    if funnel_data["steps"]:
                        funnel_data["steps"] = json.loads(funnel_data["steps"])
                    return funnel_data

                return None

        except Exception as e:
            logger.error(f"Error getting conversion funnel {funnel_id}: {e}")
            return None

    def get_funnel_progress(
        self, funnel_id: str, start_date: datetime, end_date: datetime
    ) -> List[dict[str, Any]]:
        """Get funnel progress data within date range."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT funnel_id, user_id, session_id, step_index, timestamp
                    FROM funnel_progress
                    WHERE funnel_id = %s
                      AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp ASC
                """,
                    (funnel_id, start_date, end_date),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting funnel progress: {e}")
            return []

    def get_events_in_timeframe(
        self, start_time: datetime, end_time: datetime
    ) -> List[dict[str, Any]]:
        """Get all events within a timeframe."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, user_id, session_id, event_type, timestamp,
                           properties, page_url, campaign_id
                    FROM engagement_events
                    WHERE timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """,
                    (start_time, end_time),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                events = []
                for row in results:
                    event_data = dict(zip(columns, row))
                    if event_data["properties"]:
                        event_data["properties"] = json.loads(event_data["properties"])
                    events.append(event_data)

                return events

        except Exception as e:
            logger.error(f"Error getting events in timeframe: {e}")
            return []

    def get_active_sessions(self, since_time: datetime) -> List[dict[str, Any]]:
        """Get sessions that have been active since a given time."""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, start_time, end_time, total_events,
                           page_views, device_type, campaign_id
                    FROM user_sessions
                    WHERE start_time >= %s OR end_time >= %s OR end_time IS NULL
                    ORDER BY start_time DESC
                """,
                    (since_time, since_time),
                )

                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
