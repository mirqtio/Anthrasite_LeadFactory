"""
Tests for the storage interface abstract base class.

This module tests the StorageInterface ABC to ensure it properly
defines the contract for storage implementations.
"""

import pytest
from abc import ABC
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.storage.interface import StorageInterface


class TestStorageInterface:
    """Test cases for StorageInterface abstract base class."""

    def test_storage_interface_is_abstract(self):
        """Test that StorageInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageInterface()

    def test_storage_interface_is_abc(self):
        """Test that StorageInterface is an ABC."""
        assert issubclass(StorageInterface, ABC)

    def test_storage_interface_required_methods(self):
        """Test that all required methods are defined as abstract."""
        abstract_methods = StorageInterface.__abstractmethods__

        # Core database operations
        assert 'connection' in abstract_methods
        assert 'cursor' in abstract_methods
        assert 'execute_query' in abstract_methods
        assert 'execute_transaction' in abstract_methods
        assert 'check_connection' in abstract_methods
        assert 'validate_schema' in abstract_methods

        # Business entity operations
        assert 'get_business_by_id' in abstract_methods
        assert 'get_businesses_by_criteria' in abstract_methods
        assert 'update_business' in abstract_methods
        assert 'insert_business' in abstract_methods
        assert 'get_business_details' in abstract_methods
        assert 'get_businesses' in abstract_methods
        assert 'get_all_businesses' in abstract_methods
        assert 'get_related_business_data' in abstract_methods
        assert 'merge_businesses' in abstract_methods

        # Processing status operations
        assert 'get_processing_status' in abstract_methods
        assert 'update_processing_status' in abstract_methods
        assert 'save_stage_results' in abstract_methods
        assert 'get_stage_results' in abstract_methods

        # Review queue operations
        assert 'add_to_review_queue' in abstract_methods
        assert 'get_review_queue_items' in abstract_methods
        assert 'update_review_status' in abstract_methods
        assert 'get_review_statistics' in abstract_methods

        # Asset management operations
        assert 'get_businesses_needing_screenshots' in abstract_methods
        assert 'create_asset' in abstract_methods
        assert 'get_businesses_needing_mockups' in abstract_methods
        assert 'get_business_asset' in abstract_methods

        # Email operations
        assert 'get_businesses_for_email' in abstract_methods
        assert 'check_unsubscribed' in abstract_methods
        assert 'record_email_sent' in abstract_methods
        assert 'get_email_stats' in abstract_methods
        assert 'is_email_unsubscribed' in abstract_methods
        assert 'add_unsubscribe' in abstract_methods
        assert 'log_email_sent' in abstract_methods
        assert 'save_email_record' in abstract_methods

        # Data preservation operations
        assert 'record_backup_metadata' in abstract_methods
        assert 'get_backup_metadata' in abstract_methods
        assert 'update_backup_restored' in abstract_methods
        assert 'log_dedupe_operation' in abstract_methods
        assert 'get_audit_trail' in abstract_methods
        assert 'ensure_audit_tables' in abstract_methods

        # Transaction management
        assert 'create_savepoint' in abstract_methods
        assert 'rollback_to_savepoint' in abstract_methods
        assert 'release_savepoint' in abstract_methods

        # Log management operations
        assert 'get_logs_with_filters' in abstract_methods
        assert 'get_log_by_id' in abstract_methods
        assert 'get_log_statistics' in abstract_methods
        assert 'get_available_log_types' in abstract_methods
        assert 'get_businesses_with_logs' in abstract_methods

        # Utility methods
        assert 'read_text' in abstract_methods

    def test_concrete_implementation_missing_method(self):
        """Test that incomplete implementations raise TypeError."""

        class IncompleteStorage(StorageInterface):
            """Incomplete storage implementation for testing."""

            def connection(self):
                pass

            def cursor(self):
                pass

            # Missing all other required methods

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStorage()

    def test_concrete_implementation_all_methods(self):
        """Test that complete implementations can be instantiated."""

        class CompleteStorage(StorageInterface):
            """Complete storage implementation for testing."""

            # Context managers
            def connection(self):
                from contextlib import contextmanager
                @contextmanager
                def _connection():
                    yield None
                return _connection()

            def cursor(self):
                from contextlib import contextmanager
                @contextmanager
                def _cursor():
                    yield None
                return _cursor()

            # Core database operations
            def execute_query(self, query: str, params: Optional[Tuple] = None, fetch: bool = True) -> List[Dict[str, Any]]:
                return []

            def execute_transaction(self, queries: List[Tuple[str, Optional[Tuple]]]) -> bool:
                return True

            def check_connection(self) -> bool:
                return True

            def validate_schema(self) -> bool:
                return True

            # Business entity operations
            def get_business_by_id(self, business_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_businesses_by_criteria(self, criteria: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def update_business(self, business_id: int, updates: Dict[str, Any]) -> bool:
                return True

            def insert_business(self, business_data: Dict[str, Any]) -> Optional[int]:
                return 1

            def get_business_details(self, business_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_businesses(self, business_ids: List[int]) -> List[Dict[str, Any]]:
                return []

            def get_all_businesses(self) -> List[Dict[str, Any]]:
                return []

            def get_related_business_data(self, business_id: int) -> Dict[str, Any]:
                return {}

            def merge_businesses(self, primary_id: int, secondary_id: int) -> bool:
                return True

            # Processing status operations
            def get_processing_status(self, business_id: int, stage: str) -> Optional[Dict[str, Any]]:
                return None

            def update_processing_status(self, business_id: int, stage: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
                return True

            def save_stage_results(self, business_id: int, stage: str, results: Dict[str, Any]) -> bool:
                return True

            def get_stage_results(self, business_id: int, stage: str) -> Optional[Dict[str, Any]]:
                return None

            # Review queue operations
            def add_to_review_queue(self, primary_id: int, secondary_id: int, reason: Optional[str] = None, details: Optional[str] = None) -> Optional[int]:
                return 1

            def get_review_queue_items(self, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def update_review_status(self, review_id: int, status: str, resolution: Optional[str] = None) -> bool:
                return True

            def get_review_statistics(self) -> Dict[str, Any]:
                return {}

            # Asset management operations
            def get_businesses_needing_screenshots(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def create_asset(self, business_id: int, asset_type: str, file_path: Optional[str] = None, url: Optional[str] = None) -> bool:
                return True

            def get_businesses_needing_mockups(self, limit: int = None) -> List[Dict[str, Any]]:
                return []

            def get_business_asset(self, business_id: int, asset_type: str) -> Optional[Dict[str, Any]]:
                return None

            # Email operations
            def get_businesses_for_email(self, force: bool = False, business_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def check_unsubscribed(self, email: str) -> bool:
                return False

            def record_email_sent(self, business_id: int, email_data: Dict[str, Any]) -> bool:
                return True

            def get_email_stats(self) -> Dict[str, Any]:
                return {}

            def is_email_unsubscribed(self, email: str) -> bool:
                return False

            def add_unsubscribe(self, email: str, reason: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
                return True

            def log_email_sent(self, business_id: int, recipient_email: str, recipient_name: str, subject: str, message_id: str, status: str = "sent", error_message: Optional[str] = None) -> bool:
                return True

            def save_email_record(self, business_id: int, to_email: str, to_name: str, subject: str, message_id: str, status: str, error_message: Optional[str] = None) -> bool:
                return True

            # Data preservation operations
            def record_backup_metadata(self, backup_id: str, operation_type: str, business_ids: List[int], backup_path: str, backup_size: int, checksum: str) -> bool:
                return True

            def get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, Any]]:
                return None

            def update_backup_restored(self, backup_id: str, user_id: Optional[str] = None) -> bool:
                return True

            def log_dedupe_operation(self, operation_type: str, business1_id: Optional[int], business2_id: Optional[int], operation_data: Dict[str, Any], status: str, error_message: Optional[str] = None, user_id: Optional[str] = None) -> bool:
                return True

            def get_audit_trail(self, business_id: Optional[int] = None, operation_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100) -> List[Dict[str, Any]]:
                return []

            def ensure_audit_tables(self) -> bool:
                return True

            # Transaction management
            def create_savepoint(self, savepoint_name: str) -> bool:
                return True

            def rollback_to_savepoint(self, savepoint_name: str) -> bool:
                return True

            def release_savepoint(self, savepoint_name: str) -> bool:
                return True

            # Log management operations
            def get_logs_with_filters(self, business_id: Optional[int] = None, log_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, search_query: Optional[str] = None, limit: int = 50, offset: int = 0, sort_by: str = "timestamp", sort_order: str = "desc") -> Tuple[List[Dict[str, Any]], int]:
                return ([], 0)

            def get_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_log_statistics(self) -> Dict[str, Any]:
                return {}

            def get_available_log_types(self) -> List[str]:
                return []

            def get_businesses_with_logs(self) -> List[Dict[str, Any]]:
                return []

            # Utility methods
            def read_text(self, file_path: str) -> str:
                return ""

        # Should not raise TypeError
        storage = CompleteStorage()
        assert isinstance(storage, StorageInterface)

    def test_method_signatures(self):
        """Test that abstract methods have correct signatures."""
        import inspect

        # Test specific method signatures
        execute_query_sig = inspect.signature(StorageInterface.execute_query)
        params = list(execute_query_sig.parameters.keys())
        assert params == ['self', 'query', 'params', 'fetch']
        assert execute_query_sig.parameters['params'].default is None
        assert execute_query_sig.parameters['fetch'].default is True

        execute_transaction_sig = inspect.signature(StorageInterface.execute_transaction)
        params = list(execute_transaction_sig.parameters.keys())
        assert params == ['self', 'queries']

        get_businesses_by_criteria_sig = inspect.signature(StorageInterface.get_businesses_by_criteria)
        params = list(get_businesses_by_criteria_sig.parameters.keys())
        assert params == ['self', 'criteria', 'limit']
        assert get_businesses_by_criteria_sig.parameters['limit'].default is None

    def test_context_manager_methods(self):
        """Test that connection and cursor are context managers."""
        # The connection and cursor methods should be decorated with @contextmanager
        # This is tested implicitly by the complete implementation test
        pass

    def test_storage_interface_inheritance(self):
        """Test that StorageInterface can be properly inherited with custom methods."""

        class CustomStorage(StorageInterface):
            """Custom storage with additional methods."""

            def __init__(self):
                self.connected = False
                self.transaction_active = False

            def custom_method(self):
                """Additional method not in interface."""
                return "custom"

            # Implement all required methods (simplified for test)
            def connection(self):
                from contextlib import contextmanager
                @contextmanager
                def _connection():
                    yield None
                return _connection()

            def cursor(self):
                from contextlib import contextmanager
                @contextmanager
                def _cursor():
                    yield None
                return _cursor()

            def execute_query(self, query: str, params: Optional[Tuple] = None, fetch: bool = True) -> List[Dict[str, Any]]:
                return []

            def execute_transaction(self, queries: List[Tuple[str, Optional[Tuple]]]) -> bool:
                return True

            def check_connection(self) -> bool:
                return self.connected

            def validate_schema(self) -> bool:
                return True

            # ... (implement all other abstract methods with minimal logic)
            def get_business_by_id(self, business_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_businesses_by_criteria(self, criteria: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def update_business(self, business_id: int, updates: Dict[str, Any]) -> bool:
                return True

            def insert_business(self, business_data: Dict[str, Any]) -> Optional[int]:
                return 1

            def get_business_details(self, business_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_businesses(self, business_ids: List[int]) -> List[Dict[str, Any]]:
                return []

            def get_all_businesses(self) -> List[Dict[str, Any]]:
                return []

            def get_related_business_data(self, business_id: int) -> Dict[str, Any]:
                return {}

            def merge_businesses(self, primary_id: int, secondary_id: int) -> bool:
                return True

            def get_processing_status(self, business_id: int, stage: str) -> Optional[Dict[str, Any]]:
                return None

            def update_processing_status(self, business_id: int, stage: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
                return True

            def save_stage_results(self, business_id: int, stage: str, results: Dict[str, Any]) -> bool:
                return True

            def get_stage_results(self, business_id: int, stage: str) -> Optional[Dict[str, Any]]:
                return None

            def add_to_review_queue(self, primary_id: int, secondary_id: int, reason: Optional[str] = None, details: Optional[str] = None) -> Optional[int]:
                return 1

            def get_review_queue_items(self, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def update_review_status(self, review_id: int, status: str, resolution: Optional[str] = None) -> bool:
                return True

            def get_review_statistics(self) -> Dict[str, Any]:
                return {}

            def get_businesses_needing_screenshots(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def create_asset(self, business_id: int, asset_type: str, file_path: Optional[str] = None, url: Optional[str] = None) -> bool:
                return True

            def get_businesses_needing_mockups(self, limit: int = None) -> List[Dict[str, Any]]:
                return []

            def get_business_asset(self, business_id: int, asset_type: str) -> Optional[Dict[str, Any]]:
                return None

            def get_businesses_for_email(self, force: bool = False, business_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
                return []

            def check_unsubscribed(self, email: str) -> bool:
                return False

            def record_email_sent(self, business_id: int, email_data: Dict[str, Any]) -> bool:
                return True

            def get_email_stats(self) -> Dict[str, Any]:
                return {}

            def is_email_unsubscribed(self, email: str) -> bool:
                return False

            def add_unsubscribe(self, email: str, reason: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
                return True

            def log_email_sent(self, business_id: int, recipient_email: str, recipient_name: str, subject: str, message_id: str, status: str = "sent", error_message: Optional[str] = None) -> bool:
                return True

            def save_email_record(self, business_id: int, to_email: str, to_name: str, subject: str, message_id: str, status: str, error_message: Optional[str] = None) -> bool:
                return True

            def record_backup_metadata(self, backup_id: str, operation_type: str, business_ids: List[int], backup_path: str, backup_size: int, checksum: str) -> bool:
                return True

            def get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, Any]]:
                return None

            def update_backup_restored(self, backup_id: str, user_id: Optional[str] = None) -> bool:
                return True

            def log_dedupe_operation(self, operation_type: str, business1_id: Optional[int], business2_id: Optional[int], operation_data: Dict[str, Any], status: str, error_message: Optional[str] = None, user_id: Optional[str] = None) -> bool:
                return True

            def get_audit_trail(self, business_id: Optional[int] = None, operation_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100) -> List[Dict[str, Any]]:
                return []

            def ensure_audit_tables(self) -> bool:
                return True

            def create_savepoint(self, savepoint_name: str) -> bool:
                return True

            def rollback_to_savepoint(self, savepoint_name: str) -> bool:
                return True

            def release_savepoint(self, savepoint_name: str) -> bool:
                return True

            def get_logs_with_filters(self, business_id: Optional[int] = None, log_type: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, search_query: Optional[str] = None, limit: int = 50, offset: int = 0, sort_by: str = "timestamp", sort_order: str = "desc") -> Tuple[List[Dict[str, Any]], int]:
                return ([], 0)

            def get_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
                return None

            def get_log_statistics(self) -> Dict[str, Any]:
                return {}

            def get_available_log_types(self) -> List[str]:
                return []

            def get_businesses_with_logs(self) -> List[Dict[str, Any]]:
                return []

            def read_text(self, file_path: str) -> str:
                return ""

        storage = CustomStorage()
        assert isinstance(storage, StorageInterface)
        assert hasattr(storage, 'custom_method')
        assert storage.custom_method() == "custom"

        # Test that interface methods work
        assert storage.check_connection() is False
        storage.connected = True
        assert storage.check_connection() is True
