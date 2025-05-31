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

from leadfactory.storage.factory import get_storage

logger = logging.getLogger(__name__)


class DataPreservationManager:
    """Manages data preservation for deduplication operations."""

    def __init__(self, storage=None, backup_dir: str = None):
        """
        Initialize data preservation manager.

        Args:
            storage: Storage interface for database operations
            backup_dir: Directory for storing backups (defaults to ./dedupe_backups)
        """
        self.storage = storage or get_storage()
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
        try:
            self.storage.ensure_audit_tables()
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
                business_data = self.storage.get_business_details(business_id)
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
        return self.storage.get_related_business_data(business_id)

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
        success = self.storage.record_backup_metadata(
            backup_id, operation_type, business_ids, backup_path, backup_size, checksum
        )
        if not success:
            logger.error(f"Failed to record backup metadata for {backup_id}")

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
            backup_metadata = self.storage.get_backup_metadata(backup_id)

            if not backup_metadata:
                logger.error(f"Backup {backup_id} not found")
                return False

            backup_path = backup_metadata["backup_path"]
            expected_checksum = backup_metadata["checksum"]

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
            success = self.storage.update_backup_restored(backup_id, user_id)
            if not success:
                logger.warning(
                    f"Failed to update backup restored status for {backup_id}"
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
        success = self.storage.log_dedupe_operation(
            operation_type,
            business1_id,
            business2_id,
            operation_data,
            status,
            error_message,
            user_id,
        )
        if not success:
            logger.error(f"Failed to log {operation_type} operation")

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
        return self.storage.get_audit_trail(
            business_id, operation_type, start_date, end_date, limit
        )

    def create_transaction_savepoint(self, savepoint_name: str) -> bool:
        """
        Create a database savepoint for transaction rollback.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        return self.storage.create_savepoint(savepoint_name)

    def rollback_to_savepoint(self, savepoint_name: str) -> bool:
        """
        Rollback to a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        return self.storage.rollback_to_savepoint(savepoint_name)

    def release_savepoint(self, savepoint_name: str) -> bool:
        """
        Release a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        return self.storage.release_savepoint(savepoint_name)


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
