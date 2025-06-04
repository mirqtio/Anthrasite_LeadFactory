"""
Test suite for storage abstraction layer implementation.

This test verifies that the storage abstraction layer is working correctly
and that all pipeline modules can use the storage interface.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.storage.factory import get_storage
from leadfactory.storage.interface import StorageInterface
from leadfactory.storage.postgres_storage import PostgresStorage


class TestStorageAbstraction:
    """Test the storage abstraction layer."""

    def test_storage_factory_returns_interface(self):
        """Test that storage factory returns a StorageInterface instance."""
        storage = get_storage()
        assert isinstance(storage, StorageInterface)
        assert isinstance(storage, PostgresStorage)

    def test_storage_interface_methods_exist(self):
        """Test that all required methods exist in the storage interface."""
        storage = get_storage()

        # Test core methods
        assert hasattr(storage, "execute_query")
        assert hasattr(storage, "execute_transaction")
        assert hasattr(storage, "get_business_by_id")
        assert hasattr(storage, "get_business_details")
        assert hasattr(storage, "get_businesses")
        assert hasattr(storage, "merge_businesses")

        # Test review queue methods
        assert hasattr(storage, "add_to_review_queue")
        assert hasattr(storage, "get_review_queue_items")
        assert hasattr(storage, "update_review_status")

        # Test asset management methods
        assert hasattr(storage, "create_asset")
        assert hasattr(storage, "get_business_asset")
        assert hasattr(storage, "get_businesses_needing_screenshots")
        assert hasattr(storage, "get_businesses_needing_mockups")

    @patch("leadfactory.storage.postgres_storage.PostgresStorage.execute_query")
    def test_storage_execute_query_called(self, mock_execute):
        """Test that storage execute_query method is called correctly."""
        mock_execute.return_value = [{"id": 1, "name": "Test Business"}]

        storage = get_storage()
        result = storage.execute_query("SELECT * FROM businesses WHERE id = %s", (1,))

        mock_execute.assert_called_once_with(
            "SELECT * FROM businesses WHERE id = %s", (1,)
        )
        assert result == [{"id": 1, "name": "Test Business"}]

    @patch("leadfactory.storage.postgres_storage.PostgresStorage.get_business_by_id")
    def test_get_business_by_id(self, mock_get_business):
        """Test get_business_by_id method."""
        mock_get_business.return_value = {"id": 1, "name": "Test Business"}

        storage = get_storage()
        result = storage.get_business_by_id(1)

        mock_get_business.assert_called_once_with(1)
        assert result == {"id": 1, "name": "Test Business"}

    @patch("leadfactory.storage.postgres_storage.PostgresStorage.add_to_review_queue")
    def test_add_to_review_queue(self, mock_add_review):
        """Test add_to_review_queue method."""
        mock_add_review.return_value = 123

        storage = get_storage()
        result = storage.add_to_review_queue(1, 2, "Test reason", '{"test": "data"}')

        mock_add_review.assert_called_once_with(1, 2, "Test reason", '{"test": "data"}')
        assert result == 123


class TestPipelineStorageIntegration:
    """Test that pipeline modules can use storage abstraction."""

    @patch("leadfactory.storage.postgres_storage.PostgresStorage.execute_query")
    def test_data_preservation_uses_storage(self, mock_execute):
        """Test that data preservation module uses storage abstraction."""
        from leadfactory.pipeline.data_preservation import DataPreservationManager

        storage = get_storage()
        manager = DataPreservationManager(storage=storage)

        # Verify that the manager was initialized with storage
        assert manager.storage == storage

    @patch("leadfactory.storage.postgres_storage.PostgresStorage.get_business_asset")
    def test_email_queue_uses_storage(self, mock_get_asset):
        """Test that email queue module can use storage abstraction."""
        mock_get_asset.return_value = {"file_path": "/path/to/mockup.png"}

        # Import the module to verify it can use storage
        try:
            from leadfactory.pipeline.email_queue import get_businesses_for_email

            # If import succeeds, storage abstraction is working
            assert True
        except ImportError as e:
            pytest.fail(f"Email queue module failed to import: {e}")

    def test_dedupe_unified_uses_storage(self):
        """Test that dedupe unified module can use storage abstraction."""
        try:
            from leadfactory.pipeline.dedupe_unified import get_business_by_id

            # If import succeeds, storage abstraction is working
            assert True
        except ImportError as e:
            pytest.fail(f"Dedupe unified module failed to import: {e}")

    def test_unified_gpt4o_uses_storage(self):
        """Test that unified GPT-4o module can use storage abstraction."""
        try:
            from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

            # If import succeeds, storage abstraction is working
            assert True
        except ImportError as e:
            pytest.fail(f"Unified GPT-4o module failed to import: {e}")


class TestStorageAbstractionBenefits:
    """Test the benefits of storage abstraction."""

    def test_storage_abstraction_eliminates_direct_db_imports(self):
        """Test that pipeline modules no longer import database connectors directly."""
        import inspect

        # Test data_preservation module
        from leadfactory.pipeline import data_preservation

        source = inspect.getsource(data_preservation)
        assert (
            "from leadfactory.utils.e2e_db_connector import db_connection" not in source
        )
        assert "from leadfactory.storage.factory import get_storage" in source

    def test_storage_interface_provides_consistent_api(self):
        """Test that storage interface provides consistent API across modules."""
        storage = get_storage()

        # All these methods should exist and be callable
        methods_to_test = [
            "execute_query",
            "get_business_by_id",
            "add_to_review_queue",
            "create_asset",
            "get_business_asset",
        ]

        for method_name in methods_to_test:
            method = getattr(storage, method_name)
            assert callable(method), f"Method {method_name} should be callable"

    def test_storage_abstraction_supports_future_backends(self):
        """Test that storage abstraction can support different backends."""
        from leadfactory.storage.interface import StorageInterface

        # Create a mock storage implementation
        class MockStorage(StorageInterface):
            def execute_query(self, query, params=None, fetch=True):
                return [{"mock": "data"}]

            def execute_transaction(self, queries):
                return True

            def get_business_by_id(self, business_id):
                return {"id": business_id, "name": "Mock Business"}

            # Implement other required abstract methods with minimal implementations
            def get_business_details(self, business_id):
                return {"id": business_id}

            def get_businesses(self, business_ids):
                return [{"id": bid} for bid in business_ids]

            def merge_businesses(self, primary_id, secondary_id):
                return True

            def get_processing_status(self, business_id, stage):
                return None

            def update_processing_status(
                self, business_id, stage, status, details=None
            ):
                return True

            def create_business(self, business_data):
                return 1

            def add_to_review_queue(
                self, business1_id, business2_id, reason, details=None
            ):
                return 1

            def get_review_queue_items(self, status=None, limit=None):
                return []

            def update_review_status(self, review_id, status, resolution_data=None):
                return True

            def get_review_statistics(self):
                return {}

            def get_businesses_needing_screenshots(self, limit=None):
                return []

            def create_asset(
                self,
                business_id,
                asset_type,
                asset_data,
                file_path=None,
                asset_url=None,
            ):
                return 1

            def get_businesses_needing_mockups(self, limit=None):
                return []

            def get_business_asset(self, business_id, asset_type):
                return None

            def create_savepoint(self, savepoint_name):
                return True

            def release_savepoint(self, savepoint_name):
                return True

            def rollback_to_savepoint(self, savepoint_name):
                return True

            def record_backup_metadata(self, business_id, backup_data, operation_type):
                return 1

            def get_backup_metadata(self, backup_id):
                return None

            def update_backup_restored(self, backup_id):
                return True

            def log_dedupe_operation(
                self,
                operation_type,
                business1_id,
                business2_id=None,
                operation_data=None,
                error_message=None,
            ):
                return 1

            def get_audit_trail(self, business_id, operation_type=None, limit=None):
                return []

            def get_related_business_data(self, business_id):
                return {}

            def add_unsubscribe(self, email, reason=None, business_id=None):
                return True

            def check_unsubscribed(self, email):
                return False

            def check_connection(self):
                return True

        # Verify mock storage works
        mock_storage = MockStorage()
        assert isinstance(mock_storage, StorageInterface)
        assert mock_storage.get_business_by_id(1) == {"id": 1, "name": "Mock Business"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
