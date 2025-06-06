"""Unit tests for AI JSON malformed response handling."""

import json
import unittest
from unittest.mock import Mock

from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode
from leadfactory.scoring.scoring_engine import ScoringEngine


class TestAIJSONHandling(unittest.TestCase):
    """Test AI JSON malformed response handling and fallback scoring."""

    def setUp(self):
        """Set up test environment."""
        self.node = UnifiedGPT4ONode()
        self.business_data = {
            "id": 123,
            "name": "Test Business",
            "website": "https://example.com"
        }
        self.prompt = "Test prompt"
        self.validation = {"valid": True}
        self.response = {
            "provider": "test_provider",
            "model": "test_model",
            "usage": {"tokens": 100}
        }

    def test_valid_json_parsing(self):
        """Test successful JSON parsing with valid structure."""
        valid_content = json.dumps({
            "mockup": {
                "layout_elements": [
                    {
                        "section_name": "Header",
                        "description": "Main navigation",
                        "priority": "high"
                    }
                ],
                "content_recommendations": [
                    {
                        "area": "Homepage",
                        "current_issue": "Low contrast",
                        "improvement": "Increase contrast"
                    }
                ]
            },
            "email": {
                "subject": "Test Subject",
                "body": "Test body content"
            }
        })

        result = self.node._parse_and_validate_json_response(
            valid_content, self.business_data, self.prompt, self.validation, self.response
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["ai_status"], "verified")
        self.assertIn("content", result)
        self.assertIn("mockup", result["content"])
        self.assertIn("email", result["content"])

    def test_invalid_json_parse_error(self):
        """Test handling of invalid JSON content."""
        invalid_json = "{ invalid json content without proper closing"

        result = self.node._parse_and_validate_json_response(
            invalid_json, self.business_data, self.prompt, self.validation, self.response
        )

        self.assertTrue(result["success"])  # Still successful but with uncertainty
        self.assertEqual(result["ai_status"], "AI-Uncertain")
        self.assertEqual(result["error_type"], "json_parse_error")
        self.assertEqual(result["score_weight"], 0.0)
        self.assertTrue(result["requires_manual_review"])

    def test_missing_required_fields(self):
        """Test handling of valid JSON with missing required fields."""
        incomplete_json = json.dumps({
            "mockup": {
                "layout_elements": []
                # Missing content_recommendations
            }
            # Missing email section entirely
        })

        result = self.node._parse_and_validate_json_response(
            incomplete_json, self.business_data, self.prompt, self.validation, self.response
        )

        self.assertTrue(result["success"])  # Still successful but with uncertainty
        self.assertEqual(result["ai_status"], "AI-Uncertain")
        self.assertEqual(result["error_type"], "json_validation_error")
        self.assertEqual(result["score_weight"], 0.0)
        self.assertTrue(result["requires_manual_review"])

    def test_json_structure_validation(self):
        """Test JSON structure validation method."""
        # Valid structure
        valid_json = {
            "mockup": {
                "layout_elements": [],
                "content_recommendations": []
            },
            "email": {
                "subject": "Test",
                "body": "Test body"
            }
        }
        self.assertTrue(self.node._validate_json_structure(valid_json))

        # Missing top-level keys
        missing_mockup = {"email": {"subject": "Test", "body": "Test"}}
        self.assertFalse(self.node._validate_json_structure(missing_mockup))

        # Missing mockup fields
        missing_mockup_fields = {
            "mockup": {"layout_elements": []},  # Missing content_recommendations
            "email": {"subject": "Test", "body": "Test"}
        }
        self.assertFalse(self.node._validate_json_structure(missing_mockup_fields))

        # Missing email fields
        missing_email_fields = {
            "mockup": {"layout_elements": [], "content_recommendations": []},
            "email": {"subject": "Test"}  # Missing body
        }
        self.assertFalse(self.node._validate_json_structure(missing_email_fields))

    def test_ai_uncertain_response_structure(self):
        """Test AI-Uncertain response structure."""
        result = self.node._generate_ai_uncertain_response(
            self.business_data, self.prompt, self.validation, "test_error"
        )

        # Check response structure
        self.assertTrue(result["success"])
        self.assertEqual(result["ai_status"], "AI-Uncertain")
        self.assertEqual(result["error_type"], "test_error")
        self.assertEqual(result["score_weight"], 0.0)
        self.assertTrue(result["requires_manual_review"])

        # Check content structure
        content = result["content"]
        self.assertIn("mockup", content)
        self.assertIn("email", content)
        self.assertEqual(content["ai_status"], "AI-Uncertain")
        self.assertEqual(content["score_weight"], 0.0)
        self.assertTrue(content["requires_manual_review"])

        # Check mockup content indicates uncertainty
        mockup = content["mockup"]
        self.assertEqual(mockup["ai_confidence_score"], 0.0)
        self.assertTrue(mockup["requires_manual_review"])
        self.assertIn("AI Analysis Unavailable", mockup["layout_elements"][0]["section_name"])

        # Check email content indicates uncertainty
        email = content["email"]
        self.assertEqual(email["ai_confidence"], 0.0)
        self.assertIn("technical difficulties", email["body"])


class TestScoringEngineAIUncertain(unittest.TestCase):
    """Test scoring engine handling of AI-Uncertain businesses."""

    def setUp(self):
        """Set up test environment."""
        self.engine = ScoringEngine()
        # Mock the settings and rules to avoid loading actual config
        self.engine.settings = Mock()
        self.engine.settings.base_score = 50
        self.engine.settings.min_score = 0
        self.engine.settings.max_score = 100
        self.engine.settings.high_score_threshold = 80
        self.engine.rules = []
        self.engine.multipliers = []

    def test_ai_uncertain_zero_score(self):
        """Test that AI-Uncertain businesses get zero score."""
        business = {
            "id": 123,
            "name": "Test Business",
            "ai_status": "AI-Uncertain",
            "score_weight": 0.0,
            "error_type": "json_parse_error"
        }

        result = self.engine._calculate_score(business)

        self.assertEqual(result["score"], 0)
        self.assertEqual(result["base_score"], 0)
        self.assertEqual(result["ai_status"], "AI-Uncertain")
        self.assertEqual(result["score_weight"], 0.0)
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual(result["error_type"], "json_parse_error")
        self.assertEqual(result["final_multiplier"], 0.0)
        self.assertEqual(len(result["adjustments"]), 0)
        self.assertEqual(len(result["multipliers"]), 0)

    def test_normal_business_scoring(self):
        """Test that normal businesses get regular scoring."""
        business = {
            "id": 123,
            "name": "Test Business",
            "ai_status": "verified",
            "score_weight": 1.0
        }

        result = self.engine._calculate_score(business)

        # Should get base score since no rules are loaded
        self.assertEqual(result["score"], 50)  # base_score
        self.assertEqual(result["base_score"], 50)
        self.assertEqual(result["ai_status"], "verified")
        self.assertEqual(result["score_weight"], 1.0)
        self.assertNotIn("requires_manual_review", result)
        self.assertEqual(result["final_multiplier"], 1.0)

    def test_partial_confidence_scoring(self):
        """Test scoring with partial AI confidence."""
        business = {
            "id": 123,
            "name": "Test Business",
            "ai_status": "verified",
            "score_weight": 0.5  # 50% confidence
        }

        result = self.engine._calculate_score(business)

        # Should get 50% of base score
        self.assertEqual(result["score"], 25)  # 50 * 0.5 = 25
        self.assertEqual(result["base_score"], 50)
        self.assertEqual(result["ai_status"], "verified")
        self.assertEqual(result["score_weight"], 0.5)

    def test_missing_ai_status_defaults(self):
        """Test that missing AI status defaults to verified."""
        business = {
            "id": 123,
            "name": "Test Business"
            # No ai_status or score_weight
        }

        result = self.engine._calculate_score(business)

        # Should get normal scoring with defaults
        self.assertEqual(result["score"], 50)  # base_score
        self.assertEqual(result["ai_status"], "verified")
        self.assertEqual(result["score_weight"], 1.0)


if __name__ == "__main__":
    unittest.main()
