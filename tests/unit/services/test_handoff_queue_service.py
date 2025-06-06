"""Unit tests for handoff queue service."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from leadfactory.services.handoff_queue_service import (
    BulkOperation,
    BulkOperationType,
    HandoffQueueEntry,
    HandoffQueueService,
    HandoffStatus,
    SalesTeamMember,
)
from leadfactory.services.qualification_engine import QualificationResult, QualificationStatus


class TestHandoffQueueService(unittest.TestCase):
    """Test cases for HandoffQueueService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HandoffQueueService()

        # Mock storage
        self.mock_storage = MagicMock()
        self.service.storage = self.mock_storage

        # Mock qualification engine
        self.mock_qualification_engine = MagicMock()
        self.service.qualification_engine = self.mock_qualification_engine

    @patch('leadfactory.services.handoff_queue_service.uuid')
    def test_bulk_qualify_success(self, mock_uuid):
        """Test successful bulk qualification."""
        # Mock operation ID
        mock_uuid.uuid4.return_value.str = "test-operation-id"
        mock_uuid.uuid4.return_value.__str__ = lambda x: "test-operation-id"

        # Mock qualification results
        qualified_result = QualificationResult(
            business_id=1,
            status=QualificationStatus.QUALIFIED,
            score=85,
            criteria_id=1,
            details={"criteria_name": "Test Criteria"}
        )

        rejected_result = QualificationResult(
            business_id=2,
            status=QualificationStatus.REJECTED,
            score=30,
            criteria_id=1,
            details={"criteria_name": "Test Criteria"}
        )

        # Setup mocks
        self.mock_qualification_engine.qualify_businesses_bulk.return_value = [
            qualified_result, rejected_result
        ]
        self.service._create_bulk_operation = MagicMock(return_value=True)
        self.service._add_to_queue = MagicMock(return_value=1)
        self.service._update_bulk_operation = MagicMock(return_value=True)

        # Test
        operation_id = self.service.bulk_qualify([1, 2], 1, "test_user")

        # Verify
        self.assertEqual(operation_id, "test-operation-id")
        self.service._add_to_queue.assert_called_once()  # Only qualified business added
        self.mock_qualification_engine.qualify_businesses_bulk.assert_called_once_with(
            [1, 2], 1, False
        )

    def test_bulk_assign_success(self):
        """Test successful bulk assignment."""
        # Mock queue entries
        entry1 = HandoffQueueEntry(
            id=1, business_id=1, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED
        )
        entry2 = HandoffQueueEntry(
            id=2, business_id=2, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED
        )

        # Mock sales team member
        sales_member = SalesTeamMember(
            id=1, user_id="sales_rep_1", name="John Doe", email="john@example.com",
            max_capacity=50, current_capacity=10, is_active=True
        )

        # Setup mocks
        self.service.get_queue_entry = MagicMock(side_effect=[entry1, entry2])
        self.service.get_sales_team_member = MagicMock(return_value=sales_member)
        self.service.assign_queue_entry = MagicMock(return_value=True)
        self.service._create_bulk_operation = MagicMock(return_value=True)
        self.service._update_bulk_operation = MagicMock(return_value=True)

        # Test
        with patch('leadfactory.services.handoff_queue_service.uuid') as mock_uuid:
            mock_uuid.uuid4.return_value.__str__ = lambda: "test-operation-id"
            operation_id = self.service.bulk_assign([1, 2], "sales_rep_1", "admin")

        # Verify
        self.assertEqual(operation_id, "test-operation-id")
        self.assertEqual(self.service.assign_queue_entry.call_count, 2)

    def test_bulk_assign_capacity_exceeded(self):
        """Test bulk assignment when capacity is exceeded."""
        # Mock sales team member at capacity
        sales_member = SalesTeamMember(
            id=1, user_id="sales_rep_1", name="John Doe", email="john@example.com",
            max_capacity=10, current_capacity=10, is_active=True  # At capacity
        )

        # Setup mocks
        self.service.get_sales_team_member = MagicMock(return_value=sales_member)

        # Test - should raise error
        with self.assertRaises(ValueError) as context:
            self.service.bulk_assign([1, 2], "sales_rep_1", "admin")

        self.assertIn("exceed capacity", str(context.exception))

    def test_calculate_priority(self):
        """Test priority calculation."""
        # Test high score result
        high_score_result = QualificationResult(
            business_id=1,
            status=QualificationStatus.QUALIFIED,
            score=95,
            criteria_id=1,
            details={
                "engagement_data": {
                    "engagement_summary": {
                        "conversions": 2,
                        "total_page_views": 15
                    }
                }
            }
        )

        priority = self.service._calculate_priority(high_score_result)

        # High score (95) + conversions + high page views should give high priority
        self.assertGreater(priority, 80)

        # Test low score result
        low_score_result = QualificationResult(
            business_id=2,
            status=QualificationStatus.QUALIFIED,
            score=55,
            criteria_id=1,
            details={"engagement_data": {"engagement_summary": {}}}
        )

        priority = self.service._calculate_priority(low_score_result)

        # Low score should give lower priority
        self.assertLess(priority, 70)

    def test_add_to_queue(self):
        """Test adding entry to queue."""
        # Mock queue entry
        entry = HandoffQueueEntry(
            id=None, business_id=1, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED, priority=75
        )

        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Return ID
        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        entry_id = self.service._add_to_queue(entry)

        # Verify
        self.assertEqual(entry_id, 1)
        mock_cursor.execute.assert_called_once()

    def test_get_queue_entry(self):
        """Test getting queue entry by ID."""
        # Mock database response
        mock_row = (
            1, 123, 1, "qualified", 75, 85, '{"test": "data"}', None, None, None,
            None, None, "", '{}', None, datetime.now(), datetime.now()
        )
        mock_columns = [
            "id", "business_id", "qualification_criteria_id", "status", "priority",
            "qualification_score", "qualification_details", "assigned_to",
            "assigned_at", "contacted_at", "closed_at", "closure_reason", "notes",
            "engagement_summary", "source_campaign_id", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_cursor.description = [(col, None) for col in mock_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        entry = self.service.get_queue_entry(1)

        # Verify
        self.assertIsNotNone(entry)
        self.assertEqual(entry.id, 1)
        self.assertEqual(entry.business_id, 123)
        self.assertEqual(entry.status, HandoffStatus.QUALIFIED)

    def test_list_queue_entries(self):
        """Test listing queue entries with filters."""
        # Mock database response
        mock_rows = [
            (1, 123, 1, "qualified", 75, 85, '{}', None, None, None,
             None, None, "", '{}', None, datetime.now(), datetime.now()),
            (2, 124, 1, "assigned", 80, 90, '{}', "sales_rep_1", datetime.now(), None,
             None, None, "", '{}', None, datetime.now(), datetime.now())
        ]
        mock_columns = [
            "id", "business_id", "qualification_criteria_id", "status", "priority",
            "qualification_score", "qualification_details", "assigned_to",
            "assigned_at", "contacted_at", "closed_at", "closure_reason", "notes",
            "engagement_summary", "source_campaign_id", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.description = [(col, None) for col in mock_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        entries = self.service.list_queue_entries(status="qualified", limit=10)

        # Verify
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].status, HandoffStatus.QUALIFIED)
        self.assertEqual(entries[1].status, HandoffStatus.ASSIGNED)

    def test_assign_queue_entry(self):
        """Test assigning individual queue entry."""
        # Mock queue entry
        entry = HandoffQueueEntry(
            id=1, business_id=123, qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED
        )

        # Mock sales team member
        sales_member = SalesTeamMember(
            id=1, user_id="sales_rep_1", name="John Doe", email="john@example.com",
            max_capacity=50, current_capacity=10, is_active=True
        )

        # Setup mocks
        self.service.get_queue_entry = MagicMock(return_value=entry)
        self.service.get_sales_team_member = MagicMock(return_value=sales_member)

        mock_cursor = MagicMock()
        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        success = self.service.assign_queue_entry(1, "sales_rep_1", "admin")

        # Verify
        self.assertTrue(success)
        self.assertEqual(mock_cursor.execute.call_count, 3)  # Update entry, history, capacity

    def test_assign_queue_entry_invalid_status(self):
        """Test assigning entry with invalid status."""
        # Mock queue entry that's already assigned
        entry = HandoffQueueEntry(
            id=1, business_id=123, qualification_criteria_id=1,
            status=HandoffStatus.ASSIGNED  # Already assigned
        )

        # Setup mocks
        self.service.get_queue_entry = MagicMock(return_value=entry)

        # Test
        success = self.service.assign_queue_entry(1, "sales_rep_1", "admin")

        # Verify
        self.assertFalse(success)

    def test_get_sales_team_member(self):
        """Test getting sales team member."""
        # Mock database response
        mock_row = (
            1, "sales_rep_1", "John Doe", "john@example.com", "sales_rep",
            '["technology"]', 50, 10, True, "UTC", '{"start": "09:00", "end": "17:00"}',
            datetime.now(), datetime.now()
        )
        mock_columns = [
            "id", "user_id", "name", "email", "role", "specialties",
            "max_capacity", "current_capacity", "is_active", "timezone",
            "working_hours", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_cursor.description = [(col, None) for col in mock_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        member = self.service.get_sales_team_member("sales_rep_1")

        # Verify
        self.assertIsNotNone(member)
        self.assertEqual(member.user_id, "sales_rep_1")
        self.assertEqual(member.name, "John Doe")
        self.assertEqual(member.current_capacity, 10)

    def test_create_bulk_operation(self):
        """Test creating bulk operation record."""
        # Create operation
        operation = BulkOperation(
            operation_id="test-op-id",
            operation_type=BulkOperationType.QUALIFY,
            criteria_id=1,
            business_ids=[1, 2, 3]
        )

        # Mock cursor
        mock_cursor = MagicMock()
        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        success = self.service._create_bulk_operation(operation)

        # Verify
        self.assertTrue(success)
        mock_cursor.execute.assert_called_once()

    def test_update_bulk_operation(self):
        """Test updating bulk operation record."""
        # Create operation with results
        operation = BulkOperation(
            operation_id="test-op-id",
            operation_type=BulkOperationType.QUALIFY,
            criteria_id=1,
            business_ids=[1, 2, 3],
            success_count=2,
            failure_count=1,
            status="completed"
        )
        operation.completed_at = datetime.now()

        # Mock cursor
        mock_cursor = MagicMock()
        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        success = self.service._update_bulk_operation(operation)

        # Verify
        self.assertTrue(success)
        mock_cursor.execute.assert_called_once()


class TestDataClasses(unittest.TestCase):
    """Test data class functionality."""

    def test_handoff_queue_entry_to_dict(self):
        """Test HandoffQueueEntry to_dict conversion."""
        entry = HandoffQueueEntry(
            id=1,
            business_id=123,
            qualification_criteria_id=1,
            status=HandoffStatus.QUALIFIED,
            priority=75
        )

        data = entry.to_dict()

        self.assertEqual(data["id"], 1)
        self.assertEqual(data["business_id"], 123)
        self.assertEqual(data["status"], "qualified")
        self.assertEqual(data["priority"], 75)

    def test_sales_team_member_to_dict(self):
        """Test SalesTeamMember to_dict conversion."""
        member = SalesTeamMember(
            id=1,
            user_id="sales_rep_1",
            name="John Doe",
            email="john@example.com",
            max_capacity=50,
            current_capacity=10
        )

        data = member.to_dict()

        self.assertEqual(data["user_id"], "sales_rep_1")
        self.assertEqual(data["name"], "John Doe")
        self.assertEqual(data["max_capacity"], 50)
        self.assertEqual(data["current_capacity"], 10)

    def test_bulk_operation_to_dict(self):
        """Test BulkOperation to_dict conversion."""
        operation = BulkOperation(
            operation_id="test-op-id",
            operation_type=BulkOperationType.ASSIGN,
            criteria_id=None,
            business_ids=[1, 2, 3]
        )

        data = operation.to_dict()

        self.assertEqual(data["operation_id"], "test-op-id")
        self.assertEqual(data["operation_type"], "assign")
        self.assertEqual(data["total_count"], 3)
        self.assertEqual(data["business_ids"], [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
