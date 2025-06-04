"""
Sharded PostgreSQL storage implementation for LeadFactory.

Provides high-performance database operations across multiple shards
with automatic routing and connection pooling.
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.pool

from .interface import StorageInterface
from .sharding_strategy import ShardConfig, ShardRouter, get_shard_router

logger = logging.getLogger(__name__)


class ShardedPostgresStorage(StorageInterface):
    """
    Sharded PostgreSQL storage implementation.

    Automatically routes queries to appropriate shards based on the configured
    sharding strategy and provides connection pooling for performance.
    """

    def __init__(self, shard_router: Optional[ShardRouter] = None, pool_size: int = 10):
        """
        Initialize sharded storage.

        Args:
            shard_router: Shard routing strategy (uses default if None)
            pool_size: Connection pool size per shard
        """
        self.shard_router = shard_router or get_shard_router()
        self.pool_size = pool_size
        self._connection_pools: Dict[str, psycopg2.pool.ThreadedConnectionPool] = {}
        self._pool_lock = threading.Lock()

        # Initialize connection pools for all shards
        self._initialize_pools()

        logger.info(
            f"Initialized sharded storage with {len(self.shard_router.config.shards)} shards"
        )

    def _initialize_pools(self):
        """Initialize connection pools for all shards."""
        for shard in self.shard_router.config.shards:
            self._create_pool_for_shard(shard)

    def _create_pool_for_shard(self, shard: ShardConfig):
        """Create connection pool for a specific shard."""
        with self._pool_lock:
            if shard.shard_id in self._connection_pools:
                return

            try:
                pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.pool_size,
                    host=shard.host,
                    port=shard.port,
                    database=shard.database,
                    user=shard.username,
                    password=shard.password,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )

                self._connection_pools[shard.shard_id] = pool
                logger.info(f"Created connection pool for shard {shard.shard_id}")

            except Exception as e:
                logger.error(
                    f"Failed to create connection pool for shard {shard.shard_id}: {e}"
                )
                raise

    def close_all_pools(self):
        """Close all connection pools."""
        with self._pool_lock:
            for shard_id, pool in self._connection_pools.items():
                try:
                    pool.closeall()
                    logger.info(f"Closed connection pool for shard {shard_id}")
                except Exception as e:
                    logger.error(f"Error closing pool for shard {shard_id}: {e}")

            self._connection_pools.clear()

    @contextmanager
    def get_connection(self, shard_id: str, read_only: bool = False):
        """Get database connection for a specific shard."""
        pool = self._connection_pools.get(shard_id)
        if not pool:
            raise ValueError(f"No connection pool for shard {shard_id}")

        # For read operations, try to use read replica
        if read_only:
            shard_config = self.shard_router.config.get_shard(shard_id)
            if shard_config and shard_config.read_replicas:
                # TODO: Implement read replica connection
                # For now, fall back to primary
                pass

        conn = None
        try:
            conn = pool.getconn()
            yield conn
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.putconn(conn)

    def execute_on_shard(
        self,
        shard_id: str,
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = True,
        read_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Execute query on a specific shard."""
        with self.get_connection(shard_id, read_only=read_only) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)

                if not fetch:
                    conn.commit()
                    return []

                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []

    def execute_on_multiple_shards(
        self,
        shard_ids: List[str],
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = True,
        read_only: bool = False,
        max_workers: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Execute query on multiple shards in parallel."""
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks for each shard
            future_to_shard = {
                executor.submit(
                    self.execute_on_shard, shard_id, query, params, fetch, read_only
                ): shard_id
                for shard_id in shard_ids
            }

            # Collect results
            for future in as_completed(future_to_shard):
                shard_id = future_to_shard[future]
                try:
                    results[shard_id] = future.result()
                except Exception as e:
                    logger.error(f"Query failed on shard {shard_id}: {e}")
                    results[shard_id] = []

        return results

    def insert_business(self, business_data: Dict[str, Any]) -> int:
        """Insert business data into appropriate shard."""
        # Determine target shard
        shard_id = self.shard_router.get_shard_for_business(business_data)

        # Prepare insert query
        fields = list(business_data.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        query = f"""
            INSERT INTO businesses ({", ".join(fields)})
            VALUES ({placeholders})
            RETURNING id
        """

        # Execute insert
        results = self.execute_on_shard(
            shard_id, query, tuple(business_data.values()), fetch=True
        )

        if results:
            business_id = results[0]["id"]
            logger.debug(f"Inserted business {business_id} into shard {shard_id}")
            return business_id
        else:
            raise ValueError("Failed to insert business")

    def get_business_by_id(
        self, business_id: int, hint_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get business by ID, optionally using hint data for shard routing."""
        if hint_data:
            # Use hint to route to specific shard
            shard_id = self.shard_router.get_shard_for_business(hint_data)
            shard_ids = [shard_id]
        else:
            # Search all shards
            shard_ids = [shard.shard_id for shard in self.shard_router.config.shards]

        query = "SELECT * FROM businesses WHERE id = %s"

        # Search shards
        results = self.execute_on_multiple_shards(
            shard_ids, query, (business_id,), fetch=True, read_only=True
        )

        # Return first found result
        for shard_id, shard_results in results.items():
            if shard_results:
                return shard_results[0]

        return None

    def search_businesses(
        self, search_params: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search businesses across appropriate shards."""
        # Determine which shards to query
        shard_ids = self.shard_router.get_shards_for_query(search_params)

        # Build search query
        where_clauses = []
        query_params = []

        for key, value in search_params.items():
            if key in ["zip_codes", "states", "cities", "sources"]:
                continue  # These are routing hints, not search criteria

            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"{key} IN ({placeholders})")
                query_params.extend(value)
            else:
                where_clauses.append(f"{key} = %s")
                query_params.append(value)

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
        query = f"""
            SELECT * FROM businesses
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        query_params.append(limit)

        # Execute on all relevant shards
        results = self.execute_on_multiple_shards(
            shard_ids, query, tuple(query_params), fetch=True, read_only=True
        )

        # Aggregate and sort results
        all_results = []
        for shard_results in results.values():
            all_results.extend(shard_results)

        # Sort by created_at and limit
        all_results.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        return all_results[:limit]

    def update_business(
        self,
        business_id: int,
        updates: Dict[str, Any],
        hint_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update business data."""
        if hint_data:
            shard_id = self.shard_router.get_shard_for_business(hint_data)
            shard_ids = [shard_id]
        else:
            shard_ids = [shard.shard_id for shard in self.shard_router.config.shards]

        # Build update query
        set_clauses = [f"{key} = %s" for key in updates]
        query = f"""
            UPDATE businesses
            SET {", ".join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """

        query_params = list(updates.values()) + [business_id]

        # Try to update on relevant shards
        for shard_id in shard_ids:
            try:
                self.execute_on_shard(shard_id, query, tuple(query_params), fetch=False)
                return True
            except Exception as e:
                logger.debug(f"Update failed on shard {shard_id}: {e}")
                continue

        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics across all shards."""
        query = """
            SELECT
                COUNT(*) as total_businesses,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_count,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as week_count
            FROM businesses
        """

        # Get stats from all shards
        all_shard_ids = [shard.shard_id for shard in self.shard_router.config.shards]
        results = self.execute_on_multiple_shards(
            all_shard_ids, query, fetch=True, read_only=True
        )

        # Aggregate statistics
        total_businesses = 0
        today_count = 0
        week_count = 0

        for shard_id, shard_results in results.items():
            if shard_results:
                stats = shard_results[0]
                total_businesses += stats.get("total_businesses", 0)
                today_count += stats.get("today_count", 0)
                week_count += stats.get("week_count", 0)

        return {
            "total_businesses": total_businesses,
            "today_count": today_count,
            "week_count": week_count,
            "active_shards": len([s for s in results.values() if s]),
            "total_shards": len(all_shard_ids),
        }

    def health_check(self) -> Dict[str, Any]:
        """Check health of all shards."""
        health_status = {}

        for shard_config in self.shard_router.config.shards:
            try:
                results = self.execute_on_shard(
                    shard_config.shard_id,
                    "SELECT 1 as health_check",
                    fetch=True,
                    read_only=True,
                )

                health_status[shard_config.shard_id] = {
                    "status": "healthy" if results else "unhealthy",
                    "host": shard_config.host,
                    "port": shard_config.port,
                }

            except Exception as e:
                health_status[shard_config.shard_id] = {
                    "status": "error",
                    "error": str(e),
                    "host": shard_config.host,
                    "port": shard_config.port,
                }

        overall_health = all(
            status["status"] == "healthy" for status in health_status.values()
        )

        return {
            "overall_health": "healthy" if overall_health else "degraded",
            "shards": health_status,
        }


# Convenience function for default sharded storage
def get_sharded_storage() -> ShardedPostgresStorage:
    """Get default sharded storage instance."""
    return ShardedPostgresStorage()
