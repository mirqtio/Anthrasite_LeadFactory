"""
Comprehensive tests for the storage factory module.

This module tests the factory pattern for creating storage instances,
ensuring proper configuration handling and singleton behavior.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.storage.factory import (
    POSTGRES,
    POSTGRESQL,
    SUPABASE,
    SUPPORTED_STORAGE_TYPES,
    configure_storage,
    get_default_storage,
    get_postgres_storage,
    get_storage,
    get_storage_instance,
    reset_storage_instance,
)
from leadfactory.storage.interface import StorageInterface
from leadfactory.storage.postgres_storage import PostgresStorage


class TestStorageFactory:
    """Test cases for storage factory functions."""

    def setup_method(self):
        """Reset storage instance before each test."""
        reset_storage_instance()

    def teardown_method(self):
        """Clean up after each test."""
        reset_storage_instance()

    def test_supported_storage_types(self):
        """Test that all expected storage types are supported."""
        assert POSTGRES in SUPPORTED_STORAGE_TYPES
        assert POSTGRESQL in SUPPORTED_STORAGE_TYPES
        assert SUPABASE in SUPPORTED_STORAGE_TYPES
        assert len(SUPPORTED_STORAGE_TYPES) == 3

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_default(self, mock_postgres_class):
        """Test getting default storage instance (PostgreSQL)."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance()

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(None)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_explicit_postgres(self, mock_postgres_class):
        """Test explicitly requesting PostgreSQL storage."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance(storage_type="postgres")

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(None)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_postgresql_alias(self, mock_postgres_class):
        """Test that 'postgresql' alias works for PostgreSQL."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance(storage_type="postgresql")

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(None)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_supabase(self, mock_postgres_class):
        """Test that Supabase uses PostgreSQL implementation."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance(storage_type="supabase")

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(None)

    def test_get_storage_instance_unsupported_type(self):
        """Test that unsupported storage type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported storage type: mysql"):
            get_storage_instance(storage_type="mysql")

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_with_config(self, mock_postgres_class):
        """Test passing configuration to storage instance."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance
        config = {"host": "localhost", "port": 5432}

        storage = get_storage_instance(config=config)

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(config)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_singleton_behavior(self, mock_postgres_class):
        """Test that storage instance follows singleton pattern."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage1 = get_storage_instance()
        storage2 = get_storage_instance()

        assert storage1 is storage2
        # Should only be called once due to singleton
        mock_postgres_class.assert_called_once()

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_force_new(self, mock_postgres_class):
        """Test forcing creation of new instance."""
        mock_instance1 = MagicMock(spec=StorageInterface)
        mock_instance2 = MagicMock(spec=StorageInterface)
        mock_postgres_class.side_effect = [mock_instance1, mock_instance2]

        storage1 = get_storage_instance()
        storage2 = get_storage_instance(force_new=True)

        assert storage1 is not storage2
        assert mock_postgres_class.call_count == 2

    @patch.dict(os.environ, {"STORAGE_TYPE": "supabase"})
    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_from_environment(self, mock_postgres_class):
        """Test reading storage type from environment variable."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance()

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(None)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_storage_instance_config_overrides_env(self, mock_postgres_class):
        """Test that config parameter overrides environment variable."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance
        config = {"storage_type": "postgres"}

        with patch.dict(os.environ, {"STORAGE_TYPE": "supabase"}):
            storage = get_storage_instance(config=config)

        assert storage == mock_instance

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_reset_storage_instance(self, mock_postgres_class):
        """Test resetting the singleton instance."""
        mock_instance1 = MagicMock(spec=StorageInterface)
        mock_instance2 = MagicMock(spec=StorageInterface)
        mock_postgres_class.side_effect = [mock_instance1, mock_instance2]

        storage1 = get_storage_instance()
        reset_storage_instance()
        storage2 = get_storage_instance()

        assert storage1 is not storage2
        assert mock_postgres_class.call_count == 2

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_configure_storage(self, mock_postgres_class):
        """Test configure_storage always returns new instance."""
        mock_instance1 = MagicMock(spec=StorageInterface)
        mock_instance2 = MagicMock(spec=StorageInterface)
        mock_postgres_class.side_effect = [mock_instance1, mock_instance2]

        storage1 = get_storage_instance()
        storage2 = configure_storage("postgres", {"host": "newhost"})

        assert storage1 is not storage2
        assert mock_postgres_class.call_count == 2
        mock_postgres_class.assert_called_with({"host": "newhost"})

    @patch("leadfactory.storage.factory.get_storage_instance")
    def test_get_default_storage(self, mock_get_instance):
        """Test get_default_storage is alias for get_storage_instance."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_get_instance.return_value = mock_instance

        storage = get_default_storage()

        assert storage == mock_instance
        mock_get_instance.assert_called_once_with()

    @patch("leadfactory.storage.factory.get_storage_instance")
    def test_get_storage(self, mock_get_instance):
        """Test get_storage is alias for get_storage_instance."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_get_instance.return_value = mock_instance

        storage = get_storage()

        assert storage == mock_instance
        mock_get_instance.assert_called_once_with()

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_postgres_storage(self, mock_postgres_class):
        """Test get_postgres_storage creates new PostgreSQL instance."""
        mock_instance = MagicMock(spec=PostgresStorage)
        mock_postgres_class.return_value = mock_instance
        config = {"host": "pghost", "port": 5432}

        storage = get_postgres_storage(config)

        assert storage == mock_instance
        mock_postgres_class.assert_called_once_with(config)

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_get_postgres_storage_not_singleton(self, mock_postgres_class):
        """Test that get_postgres_storage doesn't use singleton."""
        mock_instance1 = MagicMock(spec=PostgresStorage)
        mock_instance2 = MagicMock(spec=PostgresStorage)
        mock_postgres_class.side_effect = [mock_instance1, mock_instance2]

        storage1 = get_postgres_storage()
        storage2 = get_postgres_storage()

        assert storage1 is not storage2
        assert mock_postgres_class.call_count == 2

    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_case_insensitive_storage_type(self, mock_postgres_class):
        """Test that storage type is case insensitive."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage1 = get_storage_instance(storage_type="POSTGRES")
        reset_storage_instance()
        storage2 = get_storage_instance(storage_type="Postgres")
        reset_storage_instance()
        storage3 = get_storage_instance(storage_type="PoStGrEs")

        assert mock_postgres_class.call_count == 3

    @patch("leadfactory.storage.factory.logger")
    @patch("leadfactory.storage.factory.PostgresStorage")
    def test_logging(self, mock_postgres_class, mock_logger):
        """Test that storage creation is logged."""
        mock_instance = MagicMock(spec=StorageInterface)
        mock_postgres_class.return_value = mock_instance

        storage = get_storage_instance(storage_type="postgres")

        mock_logger.info.assert_called_once_with("Created postgres storage instance")
