"""
Storage interface definition for LeadFactory.

This module defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class StorageInterface(ABC):
    """
    Abstract interface for storage operations in LeadFactory.

    This interface defines the contract that all storage backends must implement,
    providing a consistent API for database operations across the pipeline.
    """

    @abstractmethod
    @contextmanager
    def connection(self):
        """
        Context manager for database connections.

        Yields:
            Connection object for the storage backend
        """
        pass

    @abstractmethod
    @contextmanager
    def cursor(self):
        """
        Context manager for database cursors.

        Yields:
            Cursor object for executing queries
        """
        pass

    @abstractmethod
    def execute_query(
        self, query: str, params: Optional[Tuple] = None, fetch: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch and return results

        Returns:
            List of result rows as dictionaries
        """
        pass

    @abstractmethod
    def execute_transaction(self, queries: List[Tuple[str, Optional[Tuple]]]) -> bool:
        """
        Execute multiple queries in a transaction.

        Args:
            queries: List of (query, params) tuples

        Returns:
            True if transaction succeeded, False otherwise
        """
        pass

    @abstractmethod
    def get_business_by_id(self, business_id: int) -> Optional[Dict[str, Any]]:
        """
        Get business data by ID.

        Args:
            business_id: ID of the business

        Returns:
            Business data dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_businesses_by_criteria(
        self, criteria: Dict[str, Any], limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get businesses matching specific criteria.

        Args:
            criteria: Dictionary of search criteria
            limit: Maximum number of results to return

        Returns:
            List of business data dictionaries
        """
        pass

    @abstractmethod
    def update_business(self, business_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update business record with new data.

        Args:
            business_id: ID of the business to update
            updates: Dictionary of field names and values to update

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def insert_business(self, business_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a new business record.

        Args:
            business_data: Dictionary containing business information

        Returns:
            ID of the inserted business or None if failed
        """
        pass

    @abstractmethod
    def get_business_details(self, business_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed business information including JSON responses.

        Args:
            business_id: ID of the business

        Returns:
            Business details dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_businesses(self, business_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get multiple businesses by their IDs.

        Args:
            business_ids: List of business IDs to retrieve

        Returns:
            List of business dictionaries
        """
        pass

    @abstractmethod
    def get_processing_status(
        self, business_id: int, stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get processing status for a business at a specific stage.

        Args:
            business_id: ID of the business
            stage: Pipeline stage name

        Returns:
            Status information dictionary or None if not found
        """
        pass

    @abstractmethod
    def update_processing_status(
        self,
        business_id: int,
        stage: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update processing status for a business at a specific stage.

        Args:
            business_id: ID of the business
            stage: Pipeline stage name
            status: New status value
            metadata: Optional metadata dictionary

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def save_stage_results(
        self, business_id: int, stage: str, results: Dict[str, Any]
    ) -> bool:
        """
        Save results from a pipeline stage.

        Args:
            business_id: ID of the business
            stage: Pipeline stage name
            results: Results dictionary to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_stage_results(
        self, business_id: int, stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get saved results from a pipeline stage.

        Args:
            business_id: ID of the business
            stage: Pipeline stage name

        Returns:
            Results dictionary or None if not found
        """
        pass

    @abstractmethod
    def check_connection(self) -> bool:
        """
        Check if the storage connection is working.

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    def validate_schema(self) -> bool:
        """
        Validate that the database schema is correct.

        Returns:
            True if schema is valid, False otherwise
        """
        pass

    # Review Queue Methods
    @abstractmethod
    def add_to_review_queue(
        self,
        primary_id: int,
        secondary_id: int,
        reason: Optional[str] = None,
        details: Optional[str] = None,
    ) -> Optional[int]:
        """
        Add a manual review request to the queue.

        Args:
            primary_id: ID of the primary business
            secondary_id: ID of the secondary business
            reason: Reason for manual review
            details: Additional details as JSON string

        Returns:
            Review request ID or None if failed
        """
        pass

    @abstractmethod
    def get_review_queue_items(
        self, status: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get review queue items.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of items to return

        Returns:
            List of review queue items
        """
        pass

    @abstractmethod
    def update_review_status(
        self, review_id: int, status: str, resolution: Optional[str] = None
    ) -> bool:
        """
        Update the status of a review request.

        Args:
            review_id: ID of the review request
            status: New status
            resolution: Resolution details as JSON string

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_review_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about manual reviews.

        Returns:
            Dictionary of review statistics
        """
        pass

    # Asset Management Methods
    @abstractmethod
    def get_businesses_needing_screenshots(
        self, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get businesses that need screenshots taken.

        Args:
            limit: Maximum number of businesses to return

        Returns:
            List of businesses needing screenshots
        """
        pass

    @abstractmethod
    def create_asset(
        self,
        business_id: int,
        asset_type: str,
        file_path: Optional[str] = None,
        url: Optional[str] = None,
    ) -> bool:
        """
        Create an asset record.

        Args:
            business_id: ID of the business
            asset_type: Type of asset (e.g., 'screenshot')
            file_path: Path to the asset file
            url: URL of the asset

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_businesses_needing_mockups(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get businesses that need mockups generated.

        Args:
            limit: Maximum number of businesses to return

        Returns:
            List of businesses needing mockups
        """
        pass

    @abstractmethod
    def get_business_asset(
        self, business_id: int, asset_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get asset for a business by type.

        Args:
            business_id: Business ID
            asset_type: Type of asset (e.g., 'screenshot', 'mockup')

        Returns:
            Asset record or None if not found
        """
        pass

    # Email queue methods
    @abstractmethod
    def get_businesses_for_email(
        self,
        force: bool = False,
        business_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get businesses ready for email sending.

        Args:
            force: If True, include businesses already emailed
            business_id: Optional specific business ID to filter
            limit: Optional limit on number of results

        Returns:
            List of business records with email and mockup data
        """
        pass

    @abstractmethod
    def check_unsubscribed(self, email: str) -> bool:
        """
        Check if an email address is unsubscribed.

        Args:
            email: Email address to check

        Returns:
            True if unsubscribed, False otherwise
        """
        pass

    @abstractmethod
    def record_email_sent(self, business_id: int, email_data: Dict[str, Any]) -> bool:
        """
        Record that an email was sent to a business.

        Args:
            business_id: Business ID
            email_data: Email metadata (subject, content, etc.)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_email_stats(self) -> Dict[str, Any]:
        """
        Get email sending statistics.

        Returns:
            Dictionary with email statistics
        """
        pass

    @abstractmethod
    def is_email_unsubscribed(self, email: str) -> bool:
        """
        Check if an email address is unsubscribed.

        Args:
            email: Email address to check

        Returns:
            True if unsubscribed, False otherwise
        """
        pass

    @abstractmethod
    def add_unsubscribe(
        self,
        email: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Add an email to the unsubscribe list.

        Args:
            email: Email address to unsubscribe
            reason: Optional reason for unsubscribing
            ip_address: Optional IP address of the request
            user_agent: Optional user agent of the request

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
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
        """
        Log that an email was sent.

        Args:
            business_id: Business ID
            recipient_email: Recipient email address
            recipient_name: Recipient name
            subject: Email subject
            message_id: Message ID from email service
            status: Email status (sent, failed, etc.)
            error_message: Optional error message if failed

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
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
        """
        Save an email record to the database.

        Args:
            business_id: Business ID
            to_email: Recipient email
            to_name: Recipient name
            subject: Email subject
            message_id: Message ID from email service
            status: Email status
            error_message: Optional error message

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def read_text(self, file_path: str) -> str:
        """
        Read text content from a file.

        Args:
            file_path: Path to the file

        Returns:
            File content as string
        """
        pass

    # Data Preservation Methods
    @abstractmethod
    def record_backup_metadata(
        self,
        backup_id: str,
        operation_type: str,
        business_ids: List[int],
        backup_path: str,
        backup_size: int,
        checksum: str,
    ) -> bool:
        """
        Record backup metadata in the database.

        Args:
            backup_id: Unique backup identifier
            operation_type: Type of operation (merge, delete, update)
            business_ids: List of business IDs included in backup
            backup_path: Path to the backup file
            backup_size: Size of backup file in bytes
            checksum: SHA256 checksum of backup file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_backup_metadata(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """
        Get backup metadata by backup ID.

        Args:
            backup_id: Backup identifier

        Returns:
            Backup metadata dictionary or None if not found
        """
        pass

    @abstractmethod
    def update_backup_restored(
        self, backup_id: str, user_id: Optional[str] = None
    ) -> bool:
        """
        Update backup metadata to mark as restored.

        Args:
            backup_id: Backup identifier
            user_id: User who performed the restoration

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def log_dedupe_operation(
        self,
        operation_type: str,
        business1_id: Optional[int],
        business2_id: Optional[int],
        operation_data: Dict[str, Any],
        status: str,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
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

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_audit_trail(
        self,
        business_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
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
        pass

    @abstractmethod
    def create_savepoint(self, savepoint_name: str) -> bool:
        """
        Create a database savepoint for transaction rollback.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def rollback_to_savepoint(self, savepoint_name: str) -> bool:
        """
        Rollback to a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def release_savepoint(self, savepoint_name: str) -> bool:
        """
        Release a database savepoint.

        Args:
            savepoint_name: Name of the savepoint

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def ensure_audit_tables(self) -> bool:
        """
        Ensure audit tables exist in the database.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_related_business_data(self, business_id: int) -> Dict[str, Any]:
        """
        Get related data for a business (e.g., responses, metadata).

        Args:
            business_id: Business ID

        Returns:
            Dictionary of related data
        """
        pass

    @abstractmethod
    def merge_businesses(self, primary_id: int, secondary_id: int) -> bool:
        """
        Merge two business records, keeping primary and removing secondary.

        Args:
            primary_id: ID of the business to keep
            secondary_id: ID of the business to merge and remove

        Returns:
            True if merge succeeded, False otherwise
        """
        pass

    # Log Management Methods for Web Interface
    @abstractmethod
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
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get logs with filtering, pagination, and search.

        Args:
            business_id: Filter by business ID
            log_type: Filter by log type (html, llm, raw_html, enrichment)
            start_date: Filter by start date
            end_date: Filter by end date
            search_query: Search query for content
            limit: Number of results to return
            offset: Pagination offset
            sort_by: Field to sort by
            sort_order: Sort order (asc, desc)

        Returns:
            Tuple of (logs list, total count)
        """
        pass

    @abstractmethod
    def get_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single log entry by ID.

        Args:
            log_id: Log entry ID

        Returns:
            Log entry dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Get statistical information about logs.

        Returns:
            Dictionary containing log statistics:
            - total_logs: Total number of logs
            - logs_by_type: Count by log type
            - logs_by_business: Count by business
            - date_range: Earliest and latest log dates
            - storage_usage: Storage usage information
        """
        pass

    @abstractmethod
    def get_available_log_types(self) -> List[str]:
        """
        Get list of available log types in the database.

        Returns:
            List of log type strings
        """
        pass

    @abstractmethod
    def get_businesses_with_logs(self) -> List[Dict[str, Any]]:
        """
        Get list of businesses that have log entries.

        Returns:
            List of business dictionaries with id and name
        """
        pass

    @abstractmethod
    def get_all_businesses(self) -> List[Dict[str, Any]]:
        """
        Get all businesses for general purposes.

        Returns:
            List of business dictionaries
        """
        pass
