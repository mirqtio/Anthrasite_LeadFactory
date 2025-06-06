"""Integration tests for handoff queue functionality."""

import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from leadfactory.api.handoff_queue_api import handoff_queue
from leadfactory.services.handoff_queue_service import HandoffQueueService
from leadfactory.services.qualification_engine import QualificationEngine


class TestHandoffQueueIntegration(unittest.TestCase):
    """Integration tests for handoff queue API and services."""

    def setUp(self):
        """Set up test fixtures."""
        # Create Flask test app
        from flask import Flask
        self.app = Flask(__name__)
        self.app.register_blueprint(handoff_queue)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Mock storage for all services
        self.mock_storage = MagicMock()

        # Patch storage instances
        self.storage_patcher = patch('leadfactory.services.handoff_queue_service.get_storage_instance')
        self.mock_get_storage = self.storage_patcher.start()
        self.mock_get_storage.return_value = self.mock_storage

        # Patch qualification engine storage
        self.qual_storage_patcher = patch('leadfactory.services.qualification_engine.get_storage_instance')
        self.mock_qual_storage = self.qual_storage_patcher.start()
        self.mock_qual_storage.return_value = self.mock_storage

        # Patch engagement analytics
        self.engagement_patcher = patch('leadfactory.services.qualification_engine.EngagementAnalytics')
        self.mock_engagement_class = self.engagement_patcher.start()
        self.mock_engagement = MagicMock()
        self.mock_engagement_class.return_value = self.mock_engagement

        # Patch scoring engine
        self.scoring_patcher = patch('leadfactory.services.qualification_engine.ScoringEngine')
        self.mock_scoring_class = self.scoring_patcher.start()
        self.mock_scoring = MagicMock()
        self.mock_scoring_class.return_value = self.mock_scoring

    def tearDown(self):
        """Clean up test fixtures."""
        self.storage_patcher.stop()
        self.qual_storage_patcher.stop()
        self.engagement_patcher.stop()
        self.scoring_patcher.stop()

    def test_bulk_qualify_api_success(self):
        """Test successful bulk qualification API call."""
        # Mock business data
        self.mock_storage.get_business_by_id.side_effect = [
            {"id": 1, "name": "Business 1", "email": "test1@example.com", "score": 85},
            {"id": 2, "name": "Business 2", "email": "test2@example.com", "score": 90}
        ]

        # Mock criteria data
        mock_criteria_row = (
            1, "Test Criteria", "Description", 50, None,
            '["name", "email"]', '{}', '{}',
            True, datetime.now(), datetime.now()
        )
        mock_criteria_columns = [
            "id", "name", "description", "min_score", "max_score",
            "required_fields", "engagement_requirements", "custom_rules",
            "is_active", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_criteria_row
        mock_cursor.description = [(col, None) for col in mock_criteria_columns]
        mock_cursor.fetchall.return_value = []  # For list operations

        # Mock queue insertion
        mock_cursor.fetchone.side_effect = [
            mock_criteria_row,  # For criteria lookup
            (1,),  # For queue insertion
            (2,),  # For queue insertion
        ]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock JSON parsing
        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                ["name", "email"],  # required_fields
                {},  # engagement_requirements
                {},  # custom_rules
            ]

            # Make API call
            response = self.client.post('/api/handoff/qualify-bulk',
                json={
                    "business_ids": [1, 2],
                    "criteria_id": 1,
                    "performed_by": "test_user"
                })

        # Verify response
        self.assertEqual(response.status_code, 202)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("operation_id", data)

    def test_bulk_qualify_api_missing_criteria(self):
        """Test bulk qualification with missing criteria."""
        response = self.client.post('/api/handoff/qualify-bulk',
            json={
                "business_ids": [1, 2]
                # Missing criteria_id
            })

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("criteria_id is required", data["error"])

    def test_bulk_qualify_api_invalid_criteria(self):
        """Test bulk qualification with invalid criteria."""
        # Mock empty criteria response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        response = self.client.post('/api/handoff/qualify-bulk',
            json={
                "business_ids": [1, 2],
                "criteria_id": 999
            })

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn("not found", data["error"])

    def test_list_handoff_queue_api(self):
        """Test listing handoff queue API."""
        # Mock queue entries
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

        # Mock business data for enrichment
        self.mock_storage.get_business_by_id.side_effect = [
            {"id": 123, "name": "Business 1", "email": "test1@example.com"},
            {"id": 124, "name": "Business 2", "email": "test2@example.com"}
        ]

        # Mock criteria data for enrichment
        mock_criteria_row = (
            1, "Test Criteria", "Description", 50, None,
            '["name", "email"]', '{}', '{}',
            True, datetime.now(), datetime.now()
        )
        mock_criteria_columns = [
            "id", "name", "description", "min_score", "max_score",
            "required_fields", "engagement_requirements", "custom_rules",
            "is_active", "created_at", "updated_at"
        ]

        # Configure cursor for multiple calls
        mock_cursor.fetchone.side_effect = [
            mock_criteria_row,  # First criteria lookup
            mock_criteria_row,  # Second criteria lookup
        ]

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                ["name", "email"], {}, {},  # First criteria
                ["name", "email"], {}, {},  # Second criteria
            ]

            response = self.client.get('/api/handoff/queue')

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("entries", data)
        self.assertEqual(len(data["entries"]), 2)

    def test_bulk_assign_api_success(self):
        """Test successful bulk assignment API call."""
        # Mock queue entries
        mock_queue_rows = [
            (1, 123, 1, "qualified", 75, 85, '{}', None, None, None,
             None, None, "", '{}', None, datetime.now(), datetime.now()),
            (2, 124, 1, "qualified", 80, 90, '{}', None, None, None,
             None, None, "", '{}', None, datetime.now(), datetime.now())
        ]
        mock_queue_columns = [
            "id", "business_id", "qualification_criteria_id", "status", "priority",
            "qualification_score", "qualification_details", "assigned_to",
            "assigned_at", "contacted_at", "closed_at", "closure_reason", "notes",
            "engagement_summary", "source_campaign_id", "created_at", "updated_at"
        ]

        # Mock sales team member
        mock_sales_row = (
            1, "sales_rep_1", "John Doe", "john@example.com", "sales_rep",
            '["technology"]', 50, 10, True, "UTC", '{"start": "09:00", "end": "17:00"}',
            datetime.now(), datetime.now()
        )
        mock_sales_columns = [
            "id", "user_id", "name", "email", "role", "specialties",
            "max_capacity", "current_capacity", "is_active", "timezone",
            "working_hours", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            mock_queue_rows[0],  # First queue entry lookup
            mock_queue_rows[1],  # Second queue entry lookup
            mock_sales_row,      # Sales member lookup
        ]
        mock_cursor.description = [
            [(col, None) for col in mock_queue_columns],  # Queue columns
            [(col, None) for col in mock_queue_columns],  # Queue columns
            [(col, None) for col in mock_sales_columns],  # Sales columns
        ]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                {}, {},  # Queue entry JSON fields
                {}, {},  # Queue entry JSON fields
                ["technology"], {"start": "09:00", "end": "17:00"},  # Sales member JSON fields
            ]

            response = self.client.post('/api/handoff/assign-bulk',
                json={
                    "queue_entry_ids": [1, 2],
                    "assignee_user_id": "sales_rep_1",
                    "performed_by": "admin"
                })

        # Verify response
        self.assertEqual(response.status_code, 202)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("operation_id", data)

    def test_bulk_assign_api_capacity_exceeded(self):
        """Test bulk assignment when capacity is exceeded."""
        # Mock sales team member at capacity
        mock_sales_row = (
            1, "sales_rep_1", "John Doe", "john@example.com", "sales_rep",
            '["technology"]', 10, 10, True, "UTC", '{"start": "09:00", "end": "17:00"}',
            datetime.now(), datetime.now()
        )
        mock_sales_columns = [
            "id", "user_id", "name", "email", "role", "specialties",
            "max_capacity", "current_capacity", "is_active", "timezone",
            "working_hours", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_sales_row
        mock_cursor.description = [(col, None) for col in mock_sales_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                ["technology"], {"start": "09:00", "end": "17:00"}
            ]

            response = self.client.post('/api/handoff/assign-bulk',
                json={
                    "queue_entry_ids": [1, 2],
                    "assignee_user_id": "sales_rep_1",
                    "performed_by": "admin"
                })

        # Verify response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("exceed capacity", data["error"])

    def test_list_qualification_criteria_api(self):
        """Test listing qualification criteria API."""
        # Mock criteria data
        mock_rows = [
            (1, "Criteria 1", "Desc 1", 50, None, '[]', '{}', '{}', True, datetime.now(), datetime.now()),
            (2, "Criteria 2", "Desc 2", 70, None, '[]', '{}', '{}', True, datetime.now(), datetime.now())
        ]
        mock_columns = [
            "id", "name", "description", "min_score", "max_score",
            "required_fields", "engagement_requirements", "custom_rules",
            "is_active", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.description = [(col, None) for col in mock_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                [], {}, {},  # First criteria
                [], {}, {},  # Second criteria
            ]

            response = self.client.get('/api/handoff/criteria')

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("criteria", data)
        self.assertEqual(len(data["criteria"]), 2)

    def test_create_qualification_criteria_api(self):
        """Test creating qualification criteria API."""
        # Mock criteria creation
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # Creation returns ID
            (1, "New Criteria", "Description", 60, None,
             '["name", "email"]', '{}', '{}',
             True, datetime.now(), datetime.now())  # Get created criteria
        ]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                ["name", "email"], {}, {}
            ]

            response = self.client.post('/api/handoff/criteria',
                json={
                    "name": "New Criteria",
                    "description": "Test criteria",
                    "min_score": 60,
                    "required_fields": ["name", "email"]
                })

        # Verify response
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["criteria_id"], 1)

    def test_get_handoff_analytics_summary_api(self):
        """Test getting handoff analytics summary API."""
        # Mock analytics data
        mock_status_rows = [
            ("qualified", 10, 75.5, 82.3),
            ("assigned", 5, 80.0, 85.0)
        ]

        mock_assignment_rows = [
            ("sales_rep_1", 3),
            ("sales_rep_2", 2)
        ]

        mock_criteria_rows = [
            (1, "Criteria 1", 8, 83.5),
            (2, "Criteria 2", 7, 78.2)
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = [
            mock_status_rows,
            mock_assignment_rows,
            mock_criteria_rows
        ]
        mock_cursor.fetchone.side_effect = [
            (15,),  # total queue entries
            (10,),  # unassigned count
            (3,),   # active sales members
        ]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock sales team member lookup
        sales_member = MagicMock()
        sales_member.name = "John Doe"

        with patch.object(HandoffQueueService, 'get_sales_team_member') as mock_get_member:
            mock_get_member.return_value = sales_member

            response = self.client.get('/api/handoff/analytics/summary')

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("summary", data)
        self.assertIn("status_breakdown", data)
        self.assertIn("assignment_breakdown", data)
        self.assertEqual(data["summary"]["total_queue_entries"], 15)

    def test_get_queue_entry_details_api(self):
        """Test getting specific queue entry details API."""
        # Mock queue entry data
        mock_queue_row = (
            1, 123, 1, "qualified", 75, 85, '{"test": "data"}', None, None, None,
            None, None, "Test notes", '{"engagement": "data"}', None, datetime.now(), datetime.now()
        )
        mock_queue_columns = [
            "id", "business_id", "qualification_criteria_id", "status", "priority",
            "qualification_score", "qualification_details", "assigned_to",
            "assigned_at", "contacted_at", "closed_at", "closure_reason", "notes",
            "engagement_summary", "source_campaign_id", "created_at", "updated_at"
        ]

        # Mock business data
        business_data = {
            "id": 123, "name": "Test Business", "email": "test@example.com",
            "website": "https://example.com", "category": "Technology", "score": 85
        }

        # Mock criteria data
        mock_criteria_row = (
            1, "Test Criteria", "Description", 50, None,
            '["name", "email"]', '{}', '{}',
            True, datetime.now(), datetime.now()
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            mock_queue_row,      # Queue entry lookup
            mock_criteria_row,   # Criteria lookup
        ]
        mock_cursor.description = [
            [(col, None) for col in mock_queue_columns],  # Queue columns
        ]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor
        self.mock_storage.get_business_by_id.return_value = business_data

        with patch('json.loads') as mock_json_loads:
            mock_json_loads.side_effect = [
                {"test": "data"},     # qualification_details
                {"engagement": "data"},  # engagement_summary
                ["name", "email"], {}, {},  # criteria fields
            ]

            response = self.client.get('/api/handoff/queue/1')

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["business"]["name"], "Test Business")
        self.assertEqual(data["criteria"]["name"], "Test Criteria")


if __name__ == '__main__':
    unittest.main()
