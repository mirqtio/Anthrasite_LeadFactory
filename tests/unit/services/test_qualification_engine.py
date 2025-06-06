"""Unit tests for qualification engine."""

import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from leadfactory.services.qualification_engine import (
    QualificationCriteria,
    QualificationEngine,
    QualificationResult,
    QualificationStatus,
)


class TestQualificationEngine(unittest.TestCase):
    """Test cases for QualificationEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.engine = QualificationEngine()

        # Mock storage
        self.mock_storage = MagicMock()
        self.engine.storage = self.mock_storage

        # Mock engagement analytics
        self.mock_engagement = MagicMock()
        self.engine.engagement_analytics = self.mock_engagement

        # Mock scoring engine
        self.mock_scoring = MagicMock()
        self.engine.scoring_engine = self.mock_scoring

    def test_qualify_business_success(self):
        """Test successful business qualification."""
        # Mock business data
        business = {
            "id": 1,
            "name": "Test Business",
            "email": "test@example.com",
            "website": "https://example.com",
            "score": 85
        }

        # Mock criteria
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={"min_page_views": 2},
            custom_rules={"has_website": True}
        )

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)
        self.mock_engagement.get_user_engagement_summary.return_value = {
            "total_page_views": 5,
            "avg_session_duration": 120,
            "conversions": 1
        }

        # Test qualification
        result = self.engine.qualify_business(1, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.QUALIFIED)
        self.assertEqual(result.business_id, 1)
        self.assertEqual(result.score, 85)

    def test_qualify_business_missing_required_fields(self):
        """Test qualification with missing required fields."""
        # Mock business data without email
        business = {
            "id": 1,
            "name": "Test Business",
            "website": "https://example.com",
            "score": 85
        }

        # Mock criteria requiring email
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email", "website"],
            engagement_requirements={},
            custom_rules={}
        )

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)

        # Test qualification
        result = self.engine.qualify_business(1, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.INSUFFICIENT_DATA)
        self.assertIn("email", result.notes)

    def test_qualify_business_low_score(self):
        """Test qualification with score below threshold."""
        # Mock business data with low score
        business = {
            "id": 1,
            "name": "Test Business",
            "email": "test@example.com",
            "website": "https://example.com",
            "score": 30
        }

        # Mock criteria with high min score
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={},
            custom_rules={}
        )

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)

        # Test qualification
        result = self.engine.qualify_business(1, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.REJECTED)
        self.assertIn("Score 30 does not meet criteria", result.notes)

    def test_qualify_business_failed_engagement_requirements(self):
        """Test qualification with failed engagement requirements."""
        # Mock business data
        business = {
            "id": 1,
            "name": "Test Business",
            "email": "test@example.com",
            "website": "https://example.com",
            "score": 85
        }

        # Mock criteria with engagement requirements
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={"min_page_views": 10, "has_conversions": True},
            custom_rules={}
        )

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)
        self.mock_engagement.get_user_engagement_summary.return_value = {
            "total_page_views": 2,  # Below requirement
            "avg_session_duration": 120,
            "conversions": 0  # No conversions
        }

        # Test qualification
        result = self.engine.qualify_business(1, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.REJECTED)
        self.assertIn("engagement requirements", result.notes)

    def test_qualify_business_failed_custom_rules(self):
        """Test qualification with failed custom rules."""
        # Mock business data without website
        business = {
            "id": 1,
            "name": "Test Business",
            "email": "test@example.com",
            "website": "",  # Empty website
            "score": 85
        }

        # Mock criteria requiring website
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={},
            custom_rules={"has_website": True}
        )

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)

        # Test qualification
        result = self.engine.qualify_business(1, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.REJECTED)
        self.assertIn("Failed custom rules", result.notes)

    def test_qualify_businesses_bulk(self):
        """Test bulk business qualification."""
        # Mock multiple businesses
        businesses = [
            {"id": 1, "name": "Business 1", "email": "test1@example.com", "score": 85},
            {"id": 2, "name": "Business 2", "email": "test2@example.com", "score": 30},
            {"id": 3, "name": "Business 3", "email": "test3@example.com", "score": 90}
        ]

        # Mock criteria
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={},
            custom_rules={}
        )

        # Setup mocks
        def mock_get_business(business_id):
            return businesses[business_id - 1] if business_id <= len(businesses) else None

        self.mock_storage.get_business_by_id.side_effect = mock_get_business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)

        # Test bulk qualification
        results = self.engine.qualify_businesses_bulk([1, 2, 3], 1)

        # Verify results
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].status, QualificationStatus.QUALIFIED)  # Score 85
        self.assertEqual(results[1].status, QualificationStatus.REJECTED)   # Score 30
        self.assertEqual(results[2].status, QualificationStatus.QUALIFIED)  # Score 90

    def test_business_not_found(self):
        """Test qualification when business is not found."""
        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = None

        # Test qualification
        result = self.engine.qualify_business(999, 1)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.REJECTED)
        self.assertIn("Business not found", result.notes)

    def test_criteria_not_found(self):
        """Test qualification when criteria is not found."""
        # Mock business data
        business = {"id": 1, "name": "Test Business", "score": 85}

        # Setup mocks
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=None)

        # Test qualification
        result = self.engine.qualify_business(1, 999)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.REJECTED)
        self.assertIn("Qualification criteria not found", result.notes)

    def test_force_rescore(self):
        """Test qualification with forced rescoring."""
        # Mock business data with low score
        business = {
            "id": 1,
            "name": "Test Business",
            "email": "test@example.com",
            "score": 30
        }

        # Mock criteria
        criteria = QualificationCriteria(
            id=1,
            name="Test Criteria",
            description="Test",
            min_score=50,
            required_fields=["name", "email"],
            engagement_requirements={},
            custom_rules={}
        )

        # Setup mocks - scoring engine returns higher score
        self.mock_storage.get_business_by_id.return_value = business
        self.engine.get_criteria_by_id = MagicMock(return_value=criteria)
        self.mock_scoring.load_rules.return_value = None
        self.mock_scoring.score_business.return_value = {"score": 80}
        self.mock_storage.update_business_score.return_value = True

        # Test qualification with force rescore
        result = self.engine.qualify_business(1, 1, force_rescore=True)

        # Verify result
        self.assertEqual(result.status, QualificationStatus.QUALIFIED)
        self.assertEqual(result.score, 80)
        self.mock_scoring.load_rules.assert_called_once()
        self.mock_scoring.score_business.assert_called_once()

    @patch('leadfactory.services.qualification_engine.json')
    def test_get_criteria_by_id(self, mock_json):
        """Test getting criteria by ID."""
        # Mock database response
        mock_row = (
            1, "Test Criteria", "Description", 50, None,
            '["name", "email"]', '{"min_page_views": 2}', '{"has_website": true}',
            True, datetime.now(), datetime.now()
        )
        mock_columns = [
            "id", "name", "description", "min_score", "max_score",
            "required_fields", "engagement_requirements", "custom_rules",
            "is_active", "created_at", "updated_at"
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_cursor.description = [(col, None) for col in mock_columns]

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock JSON parsing
        mock_json.loads.side_effect = [
            ["name", "email"],
            {"min_page_views": 2},
            {"has_website": True}
        ]

        # Test
        criteria = self.engine.get_criteria_by_id(1)

        # Verify
        self.assertIsNotNone(criteria)
        self.assertEqual(criteria.id, 1)
        self.assertEqual(criteria.name, "Test Criteria")
        self.assertEqual(criteria.required_fields, ["name", "email"])

    def test_list_criteria(self):
        """Test listing criteria."""
        # Mock database response
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

        # Test
        criteria_list = self.engine.list_criteria()

        # Verify
        self.assertEqual(len(criteria_list), 2)
        self.assertEqual(criteria_list[0].name, "Criteria 1")
        self.assertEqual(criteria_list[1].name, "Criteria 2")

    def test_create_criteria(self):
        """Test creating new criteria."""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        self.mock_storage.cursor.return_value.__enter__.return_value = mock_cursor

        # Test
        criteria_id = self.engine.create_criteria(
            name="New Criteria",
            description="Test criteria",
            min_score=60,
            required_fields=["name", "email"],
            engagement_requirements={"min_page_views": 3},
            custom_rules={"has_website": True}
        )

        # Verify
        self.assertEqual(criteria_id, 1)
        mock_cursor.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
