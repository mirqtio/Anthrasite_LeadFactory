import os
import unittest
from unittest.mock import MagicMock, Mock, call, patch

from leadfactory.config.dedupe_config import DedupeConfig
from leadfactory.pipeline.data_preservation import DataPreservationManager
from leadfactory.pipeline.dedupe_unified import merge_businesses


class TestDedupePreservationIntegration(unittest.TestCase):
    """Integration tests for deduplication with data preservation."""

    def setUp(self):
        """Set up test configuration."""
        # Set a dummy DATABASE_URL to prevent errors
        os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"

        self.config = DedupeConfig(
            enable_manual_review=True,
            manual_review_fields=["email", "phone"],
            conflict_resolution_rules={
                "name": "KEEP_PRIMARY",
                "email": "KEEP_PRIMARY",  # Changed to avoid manual review
                "phone": "KEEP_PRIMARY"   # Changed to avoid manual review
            }
        )

    def tearDown(self):
        """Clean up after tests."""
        # Remove the test DATABASE_URL
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    @patch("leadfactory.pipeline.dedupe_unified.merge_business_records")
    @patch("leadfactory.pipeline.dedupe_unified.update_business_fields")
    def test_merge_with_preservation_success(self, mock_update, mock_merge,
                                           mock_get_business, mock_preservation_class):
        """Test successful merge with data preservation."""
        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation
        mock_preservation.create_backup.return_value = "backup_123"
        mock_preservation.create_transaction_savepoint.return_value = True
        mock_preservation.release_savepoint.return_value = True

        # Mock business data
        mock_get_business.side_effect = [
            {"id": 1, "name": "Business A", "email": "a@example.com"},
            {"id": 2, "name": "Business B", "email": "b@example.com"}
        ]

        # Mock successful operations
        mock_update.return_value = True
        mock_merge.return_value = True

        # Perform merge
        result = merge_businesses(1, 2, self.config)

        # Verify result
        self.assertEqual(result, 1)

        # Verify preservation operations were called
        mock_preservation.create_backup.assert_called_once_with([1, 2], "merge")
        mock_preservation.log_operation.assert_called()

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    @patch("leadfactory.pipeline.dedupe_unified.merge_business_records")
    @patch("leadfactory.pipeline.dedupe_unified.update_business_fields")
    def test_merge_with_preservation_failure(self, mock_update, mock_merge,
                                           mock_get_business, mock_preservation_class):
        """Test failed merge with data preservation rollback."""
        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation
        mock_preservation.create_backup.return_value = "backup_123"
        mock_preservation.create_transaction_savepoint.return_value = True
        mock_preservation.rollback_to_savepoint.return_value = True

        # Mock business data
        mock_get_business.side_effect = [
            {"id": 1, "name": "Business A", "email": "a@example.com"},
            {"id": 2, "name": "Business B", "email": "b@example.com"}
        ]

        # Mock failed merge
        mock_update.return_value = True
        mock_merge.return_value = False  # Simulate merge failure

        # Perform merge
        result = merge_businesses(1, 2, self.config)

        # Verify result is None (failure)
        self.assertIsNone(result)

        # Verify rollback was called
        mock_preservation.rollback_to_savepoint.assert_called_once()

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    @patch("leadfactory.pipeline.dedupe_unified.add_to_review_queue")
    def test_merge_with_manual_review(self, mock_add_review, mock_get_business,
                                    mock_preservation_class):
        """Test merge that requires manual review."""
        # Create config that requires manual review
        config = DedupeConfig(
            enable_manual_review=True,
            manual_review_fields=["email"],
            conflict_resolution_rules={
                "name": "KEEP_PRIMARY",
                "email": "MANUAL_REVIEW"
            }
        )

        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation
        mock_preservation.create_backup.return_value = "backup_123"
        mock_preservation.create_transaction_savepoint.return_value = True

        # Mock business data with conflicting emails
        mock_get_business.side_effect = [
            {"id": 1, "name": "Business A", "email": "a@example.com"},
            {"id": 2, "name": "Business B", "email": "b@example.com"}
        ]

        # Mock review queue
        mock_add_review.return_value = "review_123"

        # Perform merge
        result = merge_businesses(1, 2, config)

        # Verify result is None (pending review)
        self.assertIsNone(result)

        # Verify review was added
        mock_add_review.assert_called_once()

        # Verify preservation operations
        mock_preservation.create_backup.assert_called_once_with([1, 2], "merge")
        mock_preservation.log_operation.assert_called()

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    def test_merge_with_invalid_businesses(self, mock_get_business,
                                         mock_preservation_class):
        """Test merge with invalid business IDs."""
        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation

        # Mock missing business
        mock_get_business.side_effect = [None, None]

        # Perform merge
        result = merge_businesses(999, 888, self.config)

        # Verify result is None
        self.assertIsNone(result)

        # Verify no backup was created
        mock_preservation.create_backup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
