"""Unit tests for MockupQAService."""

import unittest
from unittest.mock import Mock, patch

from leadfactory.services.mockup_qa_service import MockupQAService


class TestMockupQAService(unittest.TestCase):
    """Test MockupQAService functionality."""

    def setUp(self):
        """Set up test environment."""
        self.qa_service = MockupQAService()
        self.qa_service.storage = Mock()

    def test_evaluate_high_quality_mockup(self):
        """Test evaluation of high-quality mockup."""
        mockup_content = {
            "mockup": {
                "layout_elements": [
                    {
                        "section_name": "Header Navigation",
                        "description": "Professional header with clear navigation menu and company branding",
                        "priority": "high",
                    },
                    {
                        "section_name": "Hero Section",
                        "description": "Compelling hero section with clear value proposition and call-to-action",
                        "priority": "high",
                    },
                    {
                        "section_name": "Services Overview",
                        "description": "Grid layout showcasing key services with icons and descriptions",
                        "priority": "medium",
                    },
                    {
                        "section_name": "Contact Information",
                        "description": "Prominent contact details including phone, email, and address",
                        "priority": "medium",
                    },
                    {
                        "section_name": "Footer",
                        "description": "Footer with additional navigation and business information",
                        "priority": "low",
                    },
                ],
                "content_recommendations": [
                    {
                        "area": "Homepage",
                        "current_issue": "Unclear value proposition",
                        "improvement": "Add clear headline explaining the business specializes in emergency plumbing services",
                    },
                    {
                        "area": "Services",
                        "current_issue": "Generic service descriptions",
                        "improvement": "Create specific service cards for pipe repair, drain cleaning, and emergency calls",
                    },
                ],
                "ai_confidence_score": 0.85,
            }
        }

        evaluation = self.qa_service.evaluate_mockup_quality(mockup_content)

        # Should be high quality
        self.assertGreater(evaluation["overall_score"], 7.0)
        self.assertFalse(evaluation["requires_human_review"])
        self.assertIn("layout_completeness", evaluation["quality_factors"])
        self.assertIn("content_quality", evaluation["quality_factors"])
        self.assertIn("ai_confidence", evaluation["quality_factors"])
        self.assertIn("detail_level", evaluation["quality_factors"])

    def test_evaluate_low_quality_mockup(self):
        """Test evaluation of low-quality mockup."""
        mockup_content = {
            "mockup": {
                "layout_elements": [
                    {
                        "section_name": "Page",
                        "description": "Basic page",
                        "priority": "medium",
                    }
                ],
                "content_recommendations": [
                    {"area": "Site", "current_issue": "Issues", "improvement": "Fix"}
                ],
                "ai_confidence_score": 0.3,
            }
        }

        evaluation = self.qa_service.evaluate_mockup_quality(mockup_content)

        # Should be low quality
        self.assertLess(evaluation["overall_score"], 5.0)
        self.assertTrue(evaluation["requires_human_review"])
        self.assertGreater(len(evaluation["recommendations"]), 0)

    def test_evaluate_layout_completeness(self):
        """Test layout completeness evaluation."""
        # Test with essential sections
        good_layout = [
            {"section_name": "Header Navigation", "description": "Nav menu"},
            {"section_name": "Hero Section", "description": "Main content"},
            {"section_name": "Contact Information", "description": "Contact details"},
            {"section_name": "Footer", "description": "Footer content"},
            {"section_name": "Services", "description": "Service list"},
        ]
        score = self.qa_service._evaluate_layout_completeness(good_layout)
        self.assertGreater(score, 7.0)

        # Test with minimal layout
        minimal_layout = [{"section_name": "Basic Page", "description": "Simple page"}]
        score = self.qa_service._evaluate_layout_completeness(minimal_layout)
        self.assertLess(score, 5.0)

        # Test with empty layout
        score = self.qa_service._evaluate_layout_completeness([])
        self.assertEqual(score, 2.0)

    def test_evaluate_content_quality(self):
        """Test content quality evaluation."""
        # Test with good content
        good_content = [
            {
                "area": "Homepage",
                "current_issue": "Unclear messaging about emergency services",
                "improvement": "Add prominent banner highlighting 24/7 emergency plumbing availability",
            },
            {
                "area": "Services",
                "current_issue": "Generic service descriptions without pricing",
                "improvement": "Create detailed service pages with specific pricing and response times",
            },
        ]
        score = self.qa_service._evaluate_content_quality(good_content)
        self.assertGreater(score, 6.0)

        # Test with poor content
        poor_content = [{"area": "Site", "current_issue": "Bad", "improvement": "Fix"}]
        score = self.qa_service._evaluate_content_quality(poor_content)
        self.assertLess(score, 5.0)

        # Test with empty content
        score = self.qa_service._evaluate_content_quality([])
        self.assertEqual(score, 3.0)

    def test_evaluate_detail_level(self):
        """Test detail level evaluation."""
        detailed_layout = [
            {
                "section_name": "Header",
                "description": "Professional header with responsive navigation menu, company logo, and contact information",
                "priority": "high",
            }
        ]
        detailed_content = [
            {
                "area": "Homepage",
                "current_issue": "The current homepage lacks a clear value proposition",
                "improvement": "Add a prominent hero section with compelling headline that clearly communicates the business specializes in emergency plumbing services",
            }
        ]

        score = self.qa_service._evaluate_detail_level(
            detailed_layout, detailed_content
        )
        self.assertGreater(score, 7.0)

        # Test with minimal detail
        minimal_layout = [{"section_name": "Page", "description": "Basic"}]
        minimal_content = [{"area": "Site", "improvement": "Fix"}]

        score = self.qa_service._evaluate_detail_level(minimal_layout, minimal_content)
        self.assertLess(score, 5.0)

    def test_generate_recommendations(self):
        """Test recommendation generation."""
        # Test with low scores
        low_quality_factors = {
            "layout_completeness": 3.0,
            "content_quality": 4.0,
            "ai_confidence": 2.0,
            "detail_level": 3.5,
        }

        recommendations = self.qa_service._generate_recommendations(low_quality_factors)

        # Should generate recommendations for all low-scoring areas
        self.assertGreater(len(recommendations), 2)
        self.assertTrue(any("layout" in rec.lower() for rec in recommendations))
        self.assertTrue(any("content" in rec.lower() for rec in recommendations))
        self.assertTrue(any("confidence" in rec.lower() for rec in recommendations))

        # Test with high scores
        high_quality_factors = {
            "layout_completeness": 9.0,
            "content_quality": 8.5,
            "ai_confidence": 8.0,
            "detail_level": 9.0,
        }

        recommendations = self.qa_service._generate_recommendations(
            high_quality_factors
        )

        # Should generate few or no recommendations
        self.assertEqual(len(recommendations), 0)

    @patch("leadfactory.pipeline.unified_gpt4o.UnifiedGPT4ONode")
    def test_trigger_mockup_regeneration(self, mock_node_class):
        """Test mockup regeneration trigger."""
        # Mock storage methods
        self.qa_service.storage.get_business_by_id.return_value = {
            "id": 123,
            "name": "Test Business",
            "website": "https://example.com",
        }
        self.qa_service.storage.get_mockup_versions_by_business.return_value = [
            {"version": 1},
            {"version": 2},
        ]
        self.qa_service.storage.create_mockup.return_value = 456

        # Mock GPT node
        mock_node = Mock()
        mock_node.generate_unified_content.return_value = {
            "success": True,
            "content": {"mockup": {"layout_elements": [], "ai_confidence_score": 0.8}},
        }
        mock_node_class.return_value = mock_node

        # Test regeneration
        result = self.qa_service.trigger_mockup_regeneration(
            business_id=123,
            revised_prompt="Create a better mockup",
            original_mockup_id=321,
        )

        self.assertEqual(result, 456)
        mock_node.generate_unified_content.assert_called_once()
        self.qa_service.storage.create_mockup.assert_called_once()

    def test_auto_approve_high_quality_mockups(self):
        """Test automatic approval of high-quality mockups."""
        # Mock pending mockups
        high_quality_mockup = {
            "id": 1,
            "content": {
                "mockup": {
                    "layout_elements": [
                        {
                            "section_name": "Header Navigation",
                            "description": "Professional header with comprehensive navigation menu and company branding",
                            "priority": "high",
                        },
                        {
                            "section_name": "Hero Section",
                            "description": "Compelling hero section with clear value proposition and strong call-to-action",
                            "priority": "high",
                        },
                        {
                            "section_name": "Services Overview",
                            "description": "Detailed service offerings with specific pricing and features",
                            "priority": "medium",
                        },
                        {
                            "section_name": "Contact Information",
                            "description": "Prominent contact details with multiple communication options",
                            "priority": "medium",
                        },
                        {
                            "section_name": "Footer",
                            "description": "Comprehensive footer with additional navigation and business information",
                            "priority": "low",
                        },
                        {
                            "section_name": "About Section",
                            "description": "Company background and team information",
                            "priority": "medium",
                        },
                        {
                            "section_name": "Testimonials",
                            "description": "Customer reviews and success stories",
                            "priority": "medium",
                        },
                    ],
                    "content_recommendations": [
                        {
                            "area": "Homepage",
                            "current_issue": "Value proposition could be more specific to emergency plumbing services",
                            "improvement": "Add prominent banner highlighting 24/7 emergency plumbing availability with response time guarantees",
                        },
                        {
                            "area": "Services",
                            "current_issue": "Service descriptions lack specific pricing information",
                            "improvement": "Create detailed service pages with transparent pricing and estimated completion times",
                        },
                    ],
                    "ai_confidence_score": 0.95,
                }
            },
        }

        self.qa_service.storage.list_mockups.return_value = [high_quality_mockup]
        self.qa_service.storage.apply_qa_override.return_value = True

        # Test auto-approval
        approved_count = self.qa_service.auto_approve_high_quality_mockups()

        self.assertEqual(approved_count, 1)
        self.qa_service.storage.apply_qa_override.assert_called_once()

    def test_flag_low_quality_mockups(self):
        """Test flagging of low-quality mockups."""
        # Mock low-quality mockup
        low_quality_mockup = {
            "id": 1,
            "content": {
                "mockup": {
                    "layout_elements": [
                        {"section_name": "Page", "description": "Basic"}
                    ],
                    "content_recommendations": [{"area": "Site", "improvement": "Fix"}],
                    "ai_confidence_score": 0.2,
                }
            },
        }

        self.qa_service.storage.list_mockups.return_value = [low_quality_mockup]
        self.qa_service.storage.apply_qa_override.return_value = True

        # Test flagging
        flagged_count = self.qa_service.flag_low_quality_mockups()

        self.assertEqual(flagged_count, 1)
        self.qa_service.storage.apply_qa_override.assert_called_once()

    def test_get_qa_dashboard_stats(self):
        """Test QA dashboard statistics."""
        # Mock mockups data
        mockups = [
            {"id": 1, "status": "approved", "qa_score": 8.5},
            {"id": 2, "status": "pending", "qa_score": None},
            {"id": 3, "status": "rejected", "qa_score": 3.2},
            {"id": 4, "status": "needs_revision", "qa_score": 4.1},
        ]

        self.qa_service.storage.list_mockups.return_value = mockups

        # Test stats generation
        stats = self.qa_service.get_qa_dashboard_stats()

        self.assertEqual(stats["total_mockups"], 4)
        self.assertEqual(stats["by_status"]["approved"], 1)
        self.assertEqual(stats["by_status"]["pending"], 1)
        self.assertEqual(stats["by_status"]["rejected"], 1)
        self.assertEqual(stats["by_status"]["needs_revision"], 1)
        self.assertEqual(stats["pending_review"], 1)
        self.assertEqual(stats["auto_approved"], 1)
        self.assertEqual(stats["needs_revision"], 1)

        # Average of 8.5, 3.2, 4.1 = 5.27, rounded to 5.3
        self.assertAlmostEqual(stats["avg_qa_score"], 5.3, places=1)


if __name__ == "__main__":
    unittest.main()
