import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from leadfactory.config.dedupe_config import DedupeConfig
from leadfactory.pipeline.dedupe_unified import merge_businesses


class TestDedupePreservationUnit(unittest.TestCase):
    """Unit tests for deduplication with data preservation - focused on preservation aspects."""

    def setUp(self):
        """Set up test configuration."""
        # Set a dummy DATABASE_URL to prevent errors
        os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"

        self.config = DedupeConfig(
            enable_manual_review=False,  # Disable manual review for simpler tests
            conflict_resolution_rules={
                "name": "KEEP_PRIMARY",
                "email": "KEEP_PRIMARY",
                "phone": "KEEP_PRIMARY"
            }
        )

    def tearDown(self):
        """Clean up after tests."""
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    @patch("leadfactory.pipeline.dedupe_unified.merge_business_records")
    @patch("leadfactory.pipeline.dedupe_unified.update_business_fields")
    @patch("leadfactory.pipeline.dedupe_unified.apply_conflict_resolution")
    def test_preservation_lifecycle_success(self, mock_apply_conflict, mock_update,
                                          mock_merge, mock_get_business, mock_preservation_class):
        """Test complete preservation lifecycle during successful merge."""
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

        # Mock conflict resolution - no manual review needed
        mock_apply_conflict.return_value = (
            {},  # No updates needed
            {
                "total_conflicts": 0,
                "manual_review_required": []  # No manual review
            }
        )

        # Mock successful operations
        mock_update.return_value = True
        mock_merge.return_value = True

        # Perform merge
        result = merge_businesses(1, 2, self.config)

        # Verify result
        self.assertEqual(result, 1)

        # Verify preservation lifecycle
        mock_preservation.create_backup.assert_called_once_with([1, 2], "merge")
        mock_preservation.create_transaction_savepoint.assert_called_once()
        mock_preservation.release_savepoint.assert_called_once()
        mock_preservation.rollback_to_savepoint.assert_not_called()

        # Verify log operations
        self.assertGreaterEqual(mock_preservation.log_operation.call_count, 2)

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    @patch("leadfactory.pipeline.dedupe_unified.merge_business_records")
    @patch("leadfactory.pipeline.dedupe_unified.apply_conflict_resolution")
    def test_preservation_rollback_on_failure(self, mock_apply_conflict, mock_merge,
                                            mock_get_business, mock_preservation_class):
        """Test preservation rollback when merge fails."""
        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation
        mock_preservation.create_backup.return_value = "backup_123"
        mock_preservation.create_transaction_savepoint.return_value = True
        mock_preservation.rollback_to_savepoint.return_value = True

        # Mock business data
        mock_get_business.side_effect = [
            {"id": 1, "name": "Business A"},
            {"id": 2, "name": "Business B"}
        ]

        # Mock conflict resolution
        mock_apply_conflict.return_value = ({}, {"total_conflicts": 0, "manual_review_required": []})

        # Mock failed merge
        mock_merge.return_value = False

        # Perform merge
        result = merge_businesses(1, 2, self.config)

        # Verify failure
        self.assertIsNone(result)

        # Verify rollback was called
        mock_preservation.rollback_to_savepoint.assert_called_once()
        mock_preservation.release_savepoint.assert_not_called()

    @patch("leadfactory.pipeline.dedupe_unified.DataPreservationManager")
    @patch("leadfactory.pipeline.dedupe_unified.get_business_by_id")
    def test_preservation_with_missing_business(self, mock_get_business, mock_preservation_class):
        """Test preservation behavior when businesses don't exist."""
        # Create mock preservation manager
        mock_preservation = MagicMock()
        mock_preservation_class.return_value = mock_preservation
        mock_preservation.create_backup.return_value = "backup_123"

        # Mock missing business
        mock_get_business.side_effect = [None, {"id": 2}]

        # Perform merge
        result = merge_businesses(1, 2, self.config)

        # Verify failure
        self.assertIsNone(result)

        # Verify backup was created but no savepoint operations
        mock_preservation.create_backup.assert_called_once_with([1, 2], "merge")
        mock_preservation.rollback_to_savepoint.assert_not_called()
        mock_preservation.release_savepoint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
