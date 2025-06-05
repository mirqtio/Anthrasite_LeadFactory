"""
Database query optimization utilities.

Provides query analysis, optimization hints, and performance monitoring
for PostgreSQL queries.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Optimizes database queries for better performance."""

    def __init__(self, connection_string: str):
        """Initialize query optimizer."""
        self.connection_string = connection_string
        self._slow_query_threshold = 1.0  # seconds
        self._query_cache = {}

    @contextmanager
    def connection(self):
        """Create a database connection context."""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()

    def analyze_query(
        self, query: str, params: Optional[tuple] = None
    ) -> dict[str, Any]:
        """Analyze query performance using EXPLAIN ANALYZE."""
        with self.connection() as conn, conn.cursor() as cursor:
            # Get query plan
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            cursor.execute(explain_query, params)
            plan = cursor.fetchone()[0][0]

            # Extract key metrics
            metrics = {
                "total_time": plan.get("Execution Time", 0),
                "planning_time": plan.get("Planning Time", 0),
                "shared_buffers_hit": 0,
                "shared_buffers_read": 0,
                "rows_returned": 0,
                "plan": plan,
            }

            # Parse buffer information
            if "Shared Hit Blocks" in plan:
                metrics["shared_buffers_hit"] = plan["Shared Hit Blocks"]
            if "Shared Read Blocks" in plan:
                metrics["shared_buffers_read"] = plan["Shared Read Blocks"]

            return metrics

    def suggest_indexes(self, table_name: str) -> list[dict[str, Any]]:
        """Suggest missing indexes based on query patterns."""
        suggestions = []

        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Find sequential scans on large tables
                cursor.execute(
                    """
                    SELECT
                        schemaname,
                        tablename,
                        seq_scan,
                        seq_tup_read,
                        idx_scan,
                        idx_tup_fetch,
                        n_tup_ins + n_tup_upd + n_tup_del as total_writes
                    FROM pg_stat_user_tables
                    WHERE tablename = %s
                    AND seq_scan > 0
                    AND seq_tup_read > 100000
                """,
                    (table_name,),
                )

                stats = cursor.fetchone()
                if stats and stats["seq_scan"] > stats["idx_scan"]:
                    suggestions.append(
                        {
                            "type": "index",
                            "reason": "High sequential scan rate",
                            "details": f"Table {table_name} has {stats['seq_scan']} sequential scans vs {stats['idx_scan']} index scans",
                        }
                    )

                # Find columns used in WHERE clauses without indexes
                cursor.execute(
                    """
                    SELECT
                        a.attname as column_name,
                        s.n_distinct,
                        s.null_frac
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    LEFT JOIN pg_stats s ON s.tablename = c.relname AND s.attname = a.attname
                    WHERE c.relname = %s
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                    AND NOT EXISTS (
                        SELECT 1 FROM pg_index i
                        JOIN pg_attribute ia ON ia.attrelid = i.indrelid AND ia.attnum = ANY(i.indkey)
                        WHERE i.indrelid = c.oid AND ia.attname = a.attname
                    )
                """,
                    (table_name,),
                )

                for row in cursor.fetchall():
                    if row["n_distinct"] and row["n_distinct"] > 10:
                        suggestions.append(
                            {
                                "type": "index",
                                "table": table_name,
                                "column": row["column_name"],
                                "reason": "Column with high cardinality without index",
                                "sql": f"CREATE INDEX idx_{table_name}_{row['column_name']} ON {table_name}({row['column_name']});",
                            }
                        )

        return suggestions

    def optimize_business_queries(self) -> list[dict[str, str]]:
        """Provide specific optimizations for business-related queries."""
        optimizations = []

        # Optimize business lookup by multiple fields
        optimizations.append(
            {
                "original": """
                SELECT * FROM businesses
                WHERE name = %s OR phone = %s OR email = %s OR website = %s
            """,
                "optimized": """
                SELECT * FROM businesses
                WHERE id IN (
                    SELECT id FROM businesses WHERE name = %s
                    UNION
                    SELECT id FROM businesses WHERE phone = %s
                    UNION
                    SELECT id FROM businesses WHERE email = %s
                    UNION
                    SELECT id FROM businesses WHERE website = %s
                )
            """,
                "reason": "Use UNION with individual index scans instead of OR conditions",
                "indexes_needed": [
                    "CREATE INDEX idx_businesses_name ON businesses(name);",
                    "CREATE INDEX idx_businesses_phone ON businesses(phone);",
                    "CREATE INDEX idx_businesses_email ON businesses(email);",
                    "CREATE INDEX idx_businesses_website ON businesses(website);",
                ],
            }
        )

        # Optimize deduplication queries
        optimizations.append(
            {
                "original": """
                SELECT b1.*, b2.*
                FROM businesses b1
                JOIN businesses b2 ON b1.id < b2.id
                WHERE (b1.name = b2.name AND b1.zip = b2.zip)
                   OR b1.phone = b2.phone
                   OR b1.email = b2.email
            """,
                "optimized": """
                WITH potential_duplicates AS (
                    SELECT b1.id as id1, b2.id as id2
                    FROM businesses b1
                    JOIN businesses b2 ON b1.id < b2.id AND b1.name = b2.name AND b1.zip = b2.zip
                    UNION
                    SELECT b1.id, b2.id
                    FROM businesses b1
                    JOIN businesses b2 ON b1.id < b2.id AND b1.phone = b2.phone
                    WHERE b1.phone IS NOT NULL
                    UNION
                    SELECT b1.id, b2.id
                    FROM businesses b1
                    JOIN businesses b2 ON b1.id < b2.id AND b1.email = b2.email
                    WHERE b1.email IS NOT NULL
                )
                SELECT DISTINCT b1.*, b2.*
                FROM potential_duplicates pd
                JOIN businesses b1 ON pd.id1 = b1.id
                JOIN businesses b2 ON pd.id2 = b2.id
            """,
                "reason": "Use CTE with UNION to leverage individual indexes",
                "indexes_needed": [
                    "CREATE INDEX idx_businesses_name_zip ON businesses(name, zip);",
                    "CREATE INDEX idx_businesses_phone_not_null ON businesses(phone) WHERE phone IS NOT NULL;",
                    "CREATE INDEX idx_businesses_email_not_null ON businesses(email) WHERE email IS NOT NULL;",
                ],
            }
        )

        # Optimize pagination queries
        optimizations.append(
            {
                "original": """
                SELECT * FROM businesses
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """,
                "optimized": """
                SELECT * FROM businesses
                WHERE created_at < %s  -- Use cursor-based pagination
                ORDER BY created_at DESC
                LIMIT %s
            """,
                "reason": "Replace OFFSET with cursor-based pagination for better performance",
                "indexes_needed": [
                    "CREATE INDEX idx_businesses_created_at_desc ON businesses(created_at DESC);"
                ],
            }
        )

        return optimizations

    def add_query_hints(self, query: str) -> str:
        """Add optimizer hints to improve query performance."""
        hints = []

        # Check for missing JOIN conditions
        if "JOIN" in query.upper() and "WHERE" not in query.upper():
            hints.append(
                "/* Warning: JOIN without WHERE clause can cause cartesian product */"
            )

        # Check for SELECT *
        if "SELECT *" in query.upper():
            hints.append("/* Consider selecting only needed columns instead of * */")

        # Check for missing ORDER BY with LIMIT
        if "LIMIT" in query.upper() and "ORDER BY" not in query.upper():
            hints.append(
                "/* Warning: LIMIT without ORDER BY may return inconsistent results */"
            )

        # Add hints to query
        if hints:
            return "\n".join(hints) + "\n" + query

        return query

    @contextmanager
    def track_query_performance(self, query_name: str):
        """Context manager to track query performance."""
        start_time = time.time()

        yield

        elapsed_time = time.time() - start_time

        if elapsed_time > self._slow_query_threshold:
            logger.warning(
                f"Slow query detected: {query_name} took {elapsed_time:.2f}s "
                f"(threshold: {self._slow_query_threshold}s)"
            )

        # Store metrics for analysis
        if query_name not in self._query_cache:
            self._query_cache[query_name] = {
                "count": 0,
                "total_time": 0,
                "max_time": 0,
                "min_time": float("inf"),
            }

        cache = self._query_cache[query_name]
        cache["count"] += 1
        cache["total_time"] += elapsed_time
        cache["max_time"] = max(cache["max_time"], elapsed_time)
        cache["min_time"] = min(cache["min_time"], elapsed_time)

    def get_performance_report(self) -> dict[str, Any]:
        """Get performance report for tracked queries."""
        report = {}

        for query_name, metrics in self._query_cache.items():
            avg_time = (
                metrics["total_time"] / metrics["count"] if metrics["count"] > 0 else 0
            )

            report[query_name] = {
                "execution_count": metrics["count"],
                "average_time": avg_time,
                "max_time": metrics["max_time"],
                "min_time": (
                    metrics["min_time"] if metrics["min_time"] != float("inf") else 0
                ),
                "total_time": metrics["total_time"],
                "is_slow": avg_time > self._slow_query_threshold,
            }

        return report

    def vacuum_analyze_tables(self, tables: Optional[list[str]] = None):
        """Run VACUUM ANALYZE on tables to update statistics."""
        with self.connection() as conn:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            with conn.cursor() as cursor:
                if tables:
                    for table in tables:
                        logger.info(f"Running VACUUM ANALYZE on {table}")
                        cursor.execute(f"VACUUM ANALYZE {table}")
                else:
                    logger.info("Running VACUUM ANALYZE on all tables")
                    cursor.execute("VACUUM ANALYZE")

    def get_missing_indexes_report(self) -> list[dict[str, Any]]:
        """Generate a report of potentially missing indexes."""
        report = []

        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Find tables with high sequential scan rates
                cursor.execute(
                    """
                    SELECT
                        schemaname,
                        tablename,
                        seq_scan,
                        seq_tup_read,
                        idx_scan,
                        idx_tup_fetch,
                        CASE
                            WHEN seq_scan > 0
                            THEN round((seq_tup_read::numeric / seq_scan), 2)
                            ELSE 0
                        END as avg_tup_per_seq_scan
                    FROM pg_stat_user_tables
                    WHERE seq_scan > 1000
                    AND seq_tup_read > 1000000
                    ORDER BY seq_tup_read DESC
                    LIMIT 20
                """
                )

                for row in cursor.fetchall():
                    if (
                        row["seq_scan"] > row["idx_scan"] * 2
                    ):  # Sequential scans are 2x more than index scans
                        report.append(
                            {
                                "table": row["tablename"],
                                "issue": "High sequential scan rate",
                                "seq_scans": row["seq_scan"],
                                "index_scans": row["idx_scan"],
                                "avg_rows_per_scan": row["avg_tup_per_seq_scan"],
                                "recommendation": f"Consider adding indexes to {row['tablename']}",
                            }
                        )

        return report


# Example usage and optimization functions
def optimize_business_lookup_query(
    storage, business_data: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Optimized business lookup using multiple strategies."""
    optimizer = QueryOptimizer(storage.connection_string)

    with optimizer.track_query_performance("business_lookup"):
        # Try exact matches first (most selective)
        if business_data.get("source_id") and business_data.get("source"):
            result = storage.get_business_by_source_id(
                business_data["source_id"], business_data["source"]
            )
            if result:
                return result

        # Try unique identifiers
        if business_data.get("website"):
            result = storage.get_business_by_website(business_data["website"])
            if result:
                return result

        if business_data.get("phone"):
            result = storage.get_business_by_phone(business_data["phone"])
            if result:
                return result

        # Finally try name + location match
        if business_data.get("name") and business_data.get("zip"):
            result = storage.get_business_by_name_and_zip(
                business_data["name"], business_data["zip"]
            )
            if result:
                return result

    return None


def create_optimized_indexes(connection_string: str):
    """Create optimized indexes for common query patterns."""
    optimizer = QueryOptimizer(connection_string)

    indexes = [
        # Business lookups
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_source_id_source ON businesses(source_id, source) WHERE source_id IS NOT NULL",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_website ON businesses(website) WHERE website IS NOT NULL",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_phone ON businesses(phone) WHERE phone IS NOT NULL",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_email ON businesses(email) WHERE email IS NOT NULL",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_name_zip ON businesses(name, zip)",
        # Status and processing
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_status ON businesses(status)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_processed ON businesses(processed)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_created_at ON businesses(created_at DESC)",
        # Processing status
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_status_business_stage ON processing_status(business_id, stage)",
        # Email tracking
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emails_business_id ON emails(business_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emails_sent_at ON emails(sent_at DESC)",
        # Logs
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_logs_business_id ON llm_logs(business_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_logs_created_at ON llm_logs(created_at DESC)",
        # Partial indexes for common queries
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_pending ON businesses(id) WHERE status = 'pending'",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_businesses_unprocessed ON businesses(id) WHERE processed = false",
    ]

    with optimizer.connection() as conn, conn.cursor() as cursor:
        for index_sql in indexes:
            try:
                logger.info(f"Creating index: {index_sql[:50]}...")
                cursor.execute(index_sql)
                conn.commit()
            except psycopg2.Error as e:
                logger.warning(f"Index creation failed (may already exist): {e}")
                conn.rollback()

    # Update statistics
    optimizer.vacuum_analyze_tables(["businesses", "processing_status", "emails"])


if __name__ == "__main__":
    # Example usage
    import os

    connection_string = os.getenv("DATABASE_URL", "postgresql://localhost/leadfactory")
    optimizer = QueryOptimizer(connection_string)

    # Get optimization suggestions
    suggestions = optimizer.optimize_business_queries()
    for _suggestion in suggestions:
        pass

    # Get missing indexes report
    missing_indexes = optimizer.get_missing_indexes_report()
    for _index in missing_indexes:
        pass
