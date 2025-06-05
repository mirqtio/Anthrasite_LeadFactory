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
            with self.cursor() as cursor:
                insert_query = """
                    INSERT INTO businesses (
                        name, address, city, state, zip, phone, email, website,
                        vertical_id, created_at, updated_at, status, processed,
                        source, source_id, yelp_response_json, google_response_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        (SELECT id FROM verticals WHERE name = %s LIMIT 1),
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'pending', FALSE,
                        %s, %s, %s, %s
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
                query = """
                SELECT b.id, b.name, b.email, b.phone, b.address, b.city, b.state, b.zip,
                       b.website, a.url as mockup_url, '' as contact_name,
                       COALESCE((sr.results->>'score')::int, 0) as score, '' as notes
                FROM businesses b
                LEFT JOIN emails e ON b.id = e.business_id
                LEFT JOIN assets a ON b.id = a.business_id AND a.asset_type = 'mockup'
                LEFT JOIN stage_results sr ON b.id = sr.business_id AND sr.stage = 'score'
                WHERE b.email IS NOT NULL
                  AND b.email != ''
                  AND a.url IS NOT NULL
                  AND a.url != ''
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
