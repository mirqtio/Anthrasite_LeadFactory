"""
Data preservation module for deduplication.

This module provides backup, recovery, and audit trail functionality
to ensure data integrity and prevent data loss during deduplication.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.utils.e2e_db_connector import (
    db_connection,
    db_cursor,
    get_business_details,
)

logger = logging.getLogger(__name__)


class DataPreservationManager:
    """Manages data preservation for deduplication operations."""

    def __init__(self, backup_dir: str = None):
        """
        Initialize data preservation manager.

        Args:
            backup_dir: Directory for storing backups (defaults to ./dedupe_backups)
        """
        self.backup_dir = backup_dir or os.path.join(os.getcwd(), "dedupe_backups")
        self._ensure_backup_dir()
        self._ensure_audit_tables()

    def _ensure_backup_dir(self):
        """Ensure backup directory exists."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"Created backup directory: {self.backup_dir}")

    def _ensure_audit_tables(self):
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
            with db_connection() as conn:
                with conn.cursor() as cursor:
                    for sql in create_audit_tables_sql:
                        cursor.execute(sql)
                conn.commit()
                logger.info("Audit tables verified/created")
        except Exception as e:
            logger.error(f"Failed to create audit tables: {e}")

    def create_backup(
        self, business_ids: list[int], operation_type: str
    ) -> Optional[str]:
        """
        Create a backup of business records before modification.

        Args:
            business_ids: List of business IDs to backup
            operation_type: Type of operation (merge, delete, update)

        Returns:
            Backup ID if successful, None otherwise
        """
        backup_id = f"{operation_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        backup_path = os.path.join(self.backup_dir, f"{backup_id}.json")

        try:
            # Fetch all business data
            backup_data = {
                "backup_id": backup_id,
                "operation_type": operation_type,
                "timestamp": datetime.now().isoformat(),
                "businesses": {},
            }

            for business_id in business_ids:
                business_data = get_business_details(business_id)
                if business_data:
                    # Include all related data
                    backup_data["businesses"][str(business_id)] = {
                        "core_data": business_data,
                        "related_data": self._get_related_data(business_id),
                    }

            # Write backup to file
            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            # Calculate checksum
            import hashlib

            with open(backup_path, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            # Record backup metadata
            backup_size = os.path.getsize(backup_path)
            self._record_backup_metadata(
                backup_id,
                operation_type,
                business_ids,
                backup_path,
                backup_size,
                checksum,
            )

            logger.info(
                f"Created backup {backup_id} for {len(business_ids)} businesses"
            )
            return backup_id

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Clean up partial backup
            if os.path.exists(backup_path):
                os.remove(backup_path)
            return None

    def _get_related_data(self, business_id: int) -> dict[str, Any]:
        """Get related data for a business (e.g., responses, metadata)."""
        related_data = {}

        try:
            with db_cursor() as cursor:
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

    def _record_backup_metadata(
        self,
        backup_id: str,
        operation_type: str,
        business_ids: list[int],
        backup_path: str,
        backup_size: int,
        checksum: str,
    ):
        """Record backup metadata in the database."""
        try:
            with db_cursor() as cursor:
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
        except Exception as e:
            logger.error(f"Failed to record backup metadata: {e}")

    def restore_backup(self, backup_id: str, user_id: str = None) -> bool:
        """
        Restore data from a backup.

        Args:
            backup_id: ID of the backup to restore
            user_id: ID of user performing restoration

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get backup metadata
            with db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT backup_path, checksum
                    FROM dedupe_backup_metadata
                    WHERE backup_id = %s
                """,
                    (backup_id,),
                )
                result = cursor.fetchone()

                if not result:
                    logger.error(f"Backup {backup_id} not found")
                    return False

                backup_path, expected_checksum = result

            # Verify backup integrity
            import hashlib

            with open(backup_path, "rb") as f:
                actual_checksum = hashlib.sha256(f.read()).hexdigest()

            if actual_checksum != expected_checksum:
                logger.error(f"Backup {backup_id} checksum mismatch!")
                return False

            # Load backup data
            with open(backup_path) as f:
                backup_data = json.load(f)

            # Restore businesses
            restored_count = 0
            for business_id, data in backup_data["businesses"].items():
                if self._restore_business(int(business_id), data["core_data"]):
                    restored_count += 1

            # Update backup metadata
            with db_cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE dedupe_backup_metadata
                    SET restored_at = NOW(), restored_by = %s
                    WHERE backup_id = %s
                """,
                    (user_id, backup_id),
                )

            logger.info(f"Restored {restored_count} businesses from backup {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return False

    def _restore_business(
        self, business_id: int, business_data: dict[str, Any]
    ) -> bool:
        """Restore a single business record."""
        # This is a simplified restoration - adjust based on your needs
        # In practice, you might need to handle conflicts, check if record exists, etc.
        logger.warning(
            f"Business restoration not fully implemented for ID {business_id}"
        )
        return True

    def log_operation(
        self,
        operation_type: str,
        business1_id: Optional[int],
        business2_id: Optional[int],
        operation_data: dict[str, Any],
        status: str,
        error_message: str = None,
        user_id: str = None,
    ):
        """
        Log a deduplication operation to the audit trail.

        Args:
            operation_type: Type of operation (merge, delete, update, etc.)
            business1_id: First business ID
            business2_id: Second business ID (if applicable)
            operation_data: Additional operation details
            status: Operation status (success, failed, pending)
            error_message: Error message if failed
            user_id: User performing the operation
        """
        try:
            with db_cursor() as cursor:
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
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")

    def get_audit_trail(
        self,
        business_id: int = None,
        operation_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieve audit trail entries.

        Args:
            business_id: Filter by business ID
            operation_type: Filter by operation type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of entries

        Returns:
            List of audit trail entries
        """
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
            with db_cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []

    def create_transaction_savepoint(self, savepoint_name: str) -> bool:
        """
        Create a database savepoint for transaction rollback.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        try:
            with db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SAVEPOINT {savepoint_name}")
                logger.debug(f"Created savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to create savepoint {savepoint_name}: {e}")
            return False

    def rollback_to_savepoint(self, savepoint_name: str) -> bool:
        """
        Rollback to a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        try:
            with db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                logger.info(f"Rolled back to savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to rollback to savepoint {savepoint_name}: {e}")
            return False

    def release_savepoint(self, savepoint_name: str) -> bool:
        """
        Release a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        try:
            with db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                logger.debug(f"Released savepoint: {savepoint_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to release savepoint {savepoint_name}: {e}")
            return False


def with_data_preservation(operation_type: str):
    """
    Decorator to add data preservation to deduplication operations.

    Args:
        operation_type: Type of operation being performed
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            preservation_manager = DataPreservationManager()

            # Extract business IDs from arguments
            business_ids = []
            if len(args) >= 2:
                business_ids = [args[0], args[1]]  # Assuming first two args are IDs

            # Create backup
            backup_id = None
            if business_ids:
                backup_id = preservation_manager.create_backup(
                    business_ids, operation_type
                )

            # Create savepoint
            savepoint_name = (
                f"dedupe_{operation_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            preservation_manager.create_transaction_savepoint(savepoint_name)

            try:
                # Execute the operation
                result = func(*args, **kwargs)

                # Log success
                preservation_manager.log_operation(
                    operation_type=operation_type,
                    business1_id=business_ids[0] if len(business_ids) > 0 else None,
                    business2_id=business_ids[1] if len(business_ids) > 1 else None,
                    operation_data={"backup_id": backup_id},
                    status="success",
                )

                # Release savepoint on success
                preservation_manager.release_savepoint(savepoint_name)

                return result

            except Exception as e:
                # Rollback on failure
                preservation_manager.rollback_to_savepoint(savepoint_name)

                # Log failure
                preservation_manager.log_operation(
                    operation_type=operation_type,
                    business1_id=business_ids[0] if len(business_ids) > 0 else None,
                    business2_id=business_ids[1] if len(business_ids) > 1 else None,
                    operation_data={"backup_id": backup_id},
                    status="failed",
                    error_message=str(e),
                )

                raise

        return wrapper

    return decorator
