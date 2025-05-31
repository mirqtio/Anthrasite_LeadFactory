"""
Storage abstraction layer for LeadFactory.

This module provides a generic storage interface that abstracts away
database-specific implementation details, allowing for easy switching
between different storage backends.
"""

from .factory import get_storage, get_storage_instance
from .interface import StorageInterface
from .postgres_storage import PostgresStorage

__all__ = [
    "StorageInterface",
    "PostgresStorage",
    "get_storage_instance",
    "get_storage",
]
