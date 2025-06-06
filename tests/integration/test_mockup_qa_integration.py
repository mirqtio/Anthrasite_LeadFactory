"""Integration tests for Mockup QA functionality."""

import json
import unittest
from unittest.mock import Mock, patch

from leadfactory.api.mockup_qa_api import mockup_qa


class TestMockupQAIntegration(unittest.TestCase):
    """Test Mockup QA API integration."""

    def setUp(self):
        """Set up test environment."""
        # Create a test Flask app
        from flask import Flask

        self.app = Flask(__name__)
        self.app.register_blueprint(mockup_qa)
        self.client = self.app.test_client()

        # Mock storage
        self.mock_storage = Mock()

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_list_mockups_endpoint(self, mock_get_storage):
        """Test the list mockups endpoint."""
        mock_get_storage.return_value = self.mock_storage

        # Mock mockups data
        self.mock_storage.list_mockups.return_value = [
            {
                "id": 1,
                "business_id": 123,
                "version": 1,
                "content": {
                    "mockup": {
                        "layout_elements": [
                            {"section_name": "Header", "description": "Navigation"}
                        ]
                    }
                },
                "status": "pending",
                "qa_score": 6.5,
                "business_name": "Test Business",
            }
        ]
        self.mock_storage.count_mockups.return_value = 1

        # Test endpoint
        response = self.client.get("/api/mockups")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIn("mockups", data)
        self.assertIn("total_count", data)
        self.assertEqual(len(data["mockups"]), 1)
        self.assertEqual(data["total_count"], 1)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_list_mockups_with_filters(self, mock_get_storage):
        """Test list mockups endpoint with filters."""
        mock_get_storage.return_value = self.mock_storage
        self.mock_storage.list_mockups.return_value = []
        self.mock_storage.count_mockups.return_value = 0

        # Test with status filter
        response = self.client.get("/api/mockups?status=approved&business_id=123")

        self.assertEqual(response.status_code, 200)

        # Verify filter parameters were passed
        self.mock_storage.list_mockups.assert_called_with(
            business_id=123, status="approved", limit=20, offset=0, version=None
        )

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_get_mockup_endpoint(self, mock_get_storage):
        """Test get single mockup endpoint."""
        mock_get_storage.return_value = self.mock_storage

        # Mock mockup data
        self.mock_storage.get_mockup_with_versions.return_value = {
            "id": 1,
            "business_id": 123,
            "content": {"mockup": {}},
            "status": "pending",
            "versions": [{"id": 1, "version": 1, "status": "pending"}],
        }

        # Test endpoint
        response = self.client.get("/api/mockups/1")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertEqual(data["id"], 1)
        self.assertIn("versions", data)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_get_mockup_not_found(self, mock_get_storage):
        """Test get mockup endpoint with non-existent mockup."""
        mock_get_storage.return_value = self.mock_storage
        self.mock_storage.get_mockup_with_versions.return_value = None

        # Test endpoint
        response = self.client.get("/api/mockups/999")

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_qa_override_endpoint(self, mock_get_storage):
        """Test QA override endpoint."""
        mock_get_storage.return_value = self.mock_storage

        # Mock existing mockup
        self.mock_storage.get_mockup_by_id.return_value = {
            "id": 1,
            "business_id": 123,
            "status": "pending",
        }
        self.mock_storage.apply_qa_override.return_value = True

        # Test override request
        response = self.client.post(
            "/api/mockups/1/qa-override",
            json={
                "new_status": "approved",
                "qa_score": 8.5,
                "reviewer_notes": "Looks good",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], "approved")
        self.assertEqual(data["qa_score"], 8.5)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_qa_override_with_regeneration(self, mock_get_storage):
        """Test QA override with regeneration trigger."""
        mock_get_storage.return_value = self.mock_storage

        # Mock existing mockup and business
        self.mock_storage.get_mockup_by_id.return_value = {
            "id": 1,
            "business_id": 123,
            "status": "pending",
        }
        self.mock_storage.get_business_by_id.return_value = {
            "id": 123,
            "name": "Test Business",
        }
        self.mock_storage.apply_qa_override.return_value = True

        # Mock GPT node
        with patch("leadfactory.pipeline.unified_gpt4o.UnifiedGPT4ONode") as mock_node:
            mock_instance = Mock()
            mock_node.return_value = mock_instance

            # Test override with revision
            response = self.client.post(
                "/api/mockups/1/qa-override",
                json={
                    "new_status": "needs_revision",
                    "qa_score": 3.0,
                    "revised_prompt": "Make it better",
                },
                content_type="application/json",
            )

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)

            self.assertTrue(data["success"])
            self.assertTrue(data["regeneration_triggered"])

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_qa_override_validation_errors(self, mock_get_storage):
        """Test QA override with validation errors."""
        mock_get_storage.return_value = self.mock_storage

        # Test missing status
        response = self.client.post(
            "/api/mockups/1/qa-override",
            json={"qa_score": 8.5},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("new_status is required", data["error"])

        # Test invalid status
        response = self.client.post(
            "/api/mockups/1/qa-override",
            json={"new_status": "invalid_status"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("Invalid status", data["error"])

        # Test invalid QA score
        response = self.client.post(
            "/api/mockups/1/qa-override",
            json={"new_status": "approved", "qa_score": 15},  # Out of range
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("qa_score must be between 1 and 10", data["error"])

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_get_mockup_versions_endpoint(self, mock_get_storage):
        """Test get mockup versions endpoint."""
        mock_get_storage.return_value = self.mock_storage

        # Mock versions data
        self.mock_storage.get_mockup_versions.return_value = [
            {"id": 1, "version": 1, "status": "rejected"},
            {"id": 2, "version": 2, "status": "approved"},
        ]

        # Test endpoint
        response = self.client.get("/api/mockups/1/versions")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertEqual(data["mockup_id"], 1)
        self.assertEqual(len(data["versions"]), 2)
        self.assertEqual(data["total_versions"], 2)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_compare_versions_endpoint(self, mock_get_storage):
        """Test compare versions endpoint."""
        mock_get_storage.return_value = self.mock_storage

        # Mock version data
        version1 = {
            "id": 1,
            "content": {
                "mockup": {
                    "layout_elements": [
                        {"section_name": "Header", "description": "Old header"}
                    ]
                }
            },
            "qa_score": 5.0,
            "status": "rejected",
        }

        version2 = {
            "id": 2,
            "content": {
                "mockup": {
                    "layout_elements": [
                        {"section_name": "Header", "description": "New improved header"}
                    ]
                }
            },
            "qa_score": 8.0,
            "status": "approved",
        }

        self.mock_storage.get_mockup_version_by_id.side_effect = [version1, version2]

        # Test comparison
        response = self.client.post(
            "/api/mockups/versions/compare",
            json={"version1_id": 1, "version2_id": 2},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertIn("version1", data)
        self.assertIn("version2", data)
        self.assertIn("diff", data)
        self.assertIn("comparison_summary", data)

        # Should detect changes
        self.assertTrue(data["comparison_summary"]["changes_detected"])

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_bulk_update_status_endpoint(self, mock_get_storage):
        """Test bulk update status endpoint."""
        mock_get_storage.return_value = self.mock_storage
        self.mock_storage.update_mockup_status.return_value = True

        # Test bulk update
        response = self.client.post(
            "/api/mockups/bulk-update",
            json={"mockup_ids": [1, 2, 3], "new_status": "approved"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["updated_count"], 3)
        self.assertEqual(data["total_requested"], 3)
        self.assertEqual(len(data["failed_ids"]), 0)

    @patch("leadfactory.api.mockup_qa_api.get_storage_instance")
    def test_bulk_update_validation_errors(self, mock_get_storage):
        """Test bulk update with validation errors."""
        mock_get_storage.return_value = self.mock_storage

        # Test missing mockup_ids
        response = self.client.post(
            "/api/mockups/bulk-update",
            json={"new_status": "approved"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("mockup_ids must be a non-empty list", data["error"])

        # Test invalid status for bulk update
        response = self.client.post(
            "/api/mockups/bulk-update",
            json={
                "mockup_ids": [1, 2],
                "new_status": "needs_revision",  # Not allowed for bulk
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("new_status must be approved or rejected", data["error"])

    def test_version_diff_generation(self):
        """Test version diff generation functionality."""
        from leadfactory.api.mockup_qa_api import _generate_version_diff

        version1 = {
            "content": {
                "mockup": {
                    "layout_elements": [
                        {
                            "section_name": "Header",
                            "description": "Old header",
                            "priority": "high",
                        }
                    ],
                    "content_recommendations": [
                        {"area": "Homepage", "improvement": "Old improvement"}
                    ],
                }
            },
            "qa_score": 5.0,
            "status": "rejected",
        }

        version2 = {
            "content": {
                "mockup": {
                    "layout_elements": [
                        {
                            "section_name": "Header",
                            "description": "New improved header",
                            "priority": "high",
                        }
                    ],
                    "content_recommendations": [
                        {
                            "area": "Homepage",
                            "improvement": "New improvement with specific details",
                        }
                    ],
                }
            },
            "qa_score": 8.0,
            "status": "approved",
        }

        diff = _generate_version_diff(version1, version2)

        self.assertTrue(diff["has_changes"])
        self.assertGreater(len(diff["layout_changes"]), 0)
        self.assertGreater(len(diff["content_changes"]), 0)
        self.assertIn("qa_score", diff["metadata_changes"])
        self.assertIn("status", diff["metadata_changes"])

        # Check specific changes
        layout_change = diff["layout_changes"][0]
        self.assertIn("description", layout_change["changes"])
        self.assertEqual(layout_change["changes"]["description"]["old"], "Old header")
        self.assertEqual(
            layout_change["changes"]["description"]["new"], "New improved header"
        )


if __name__ == "__main__":
    unittest.main()
