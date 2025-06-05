"""
Storage factory for LeadFactory.

This module provides a factory function for creating storage instances
based on configuration or environment variables.
"""

import logging
import os
from typing import Any, Dict, Optional

from .interface import StorageInterface
from .postgres_storage import PostgresStorage

logger = logging.getLogger(__name__)

# Global storage instance for singleton pattern
_storage_instance: Optional[StorageInterface] = None


def get_storage_instance(
    storage_type: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
    force_new: bool = False,
) -> StorageInterface:
    """
    Get a storage instance based on configuration.

    Args:
        storage_type: Type of storage backend ('postgres', 'supabase', etc.)
        config: Optional configuration dictionary
        force_new: Force creation of new instance instead of using singleton

    Returns:
        Storage interface instance

    Raises:
        ValueError: If storage type is not supported
    """
    global _storage_instance

    # Return singleton instance if available and not forcing new
    if _storage_instance and not force_new:
        return _storage_instance

    # Determine storage type from parameter, config, or environment
    if not storage_type:
        storage_type = (config or {}).get("storage_type")
    if not storage_type:
        storage_type = os.getenv("STORAGE_TYPE", "postgres")

    storage_type = storage_type.lower()

    # Create storage instance based on type
    if storage_type == "postgres" or storage_type == "postgresql":
        instance = PostgresStorage(config)
    elif storage_type == "supabase":
        # For now, Supabase uses the same PostgreSQL implementation
        # In the future, this could be a separate SupabaseStorage class
        instance = PostgresStorage(config)
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")

    # Store as singleton if not forcing new
    if not force_new:
        _storage_instance = instance

    logger.info(f"Created {storage_type} storage instance")
    return instance


def reset_storage_instance():
    """Reset the global storage instance (useful for testing)."""
    global _storage_instance
    _storage_instance = None


def configure_storage(
    storage_type: str, config: Optional[dict[str, Any]] = None
) -> StorageInterface:
    """
    Configure and return a new storage instance.

    Args:
        storage_type: Type of storage backend
        config: Configuration dictionary

    Returns:
        Configured storage interface instance
    """
    return get_storage_instance(storage_type, config, force_new=True)


# Convenience functions for common operations
def get_default_storage() -> StorageInterface:
    """Get the default storage instance."""
    return get_storage_instance()


def get_storage() -> StorageInterface:
    """Get the default storage instance (alias for get_default_storage)."""
    return get_storage_instance()


def get_postgres_storage(config: Optional[dict[str, Any]] = None) -> PostgresStorage:
    """Get a PostgreSQL storage instance."""
    return PostgresStorage(config)


# Storage type constants
POSTGRES = "postgres"
POSTGRESQL = "postgresql"
SUPABASE = "supabase"

SUPPORTED_STORAGE_TYPES = [POSTGRES, POSTGRESQL, SUPABASE]
