"""
Unit tests for unified scoring engine.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from leadfactory.scoring.unified_scoring_engine import UnifiedScoringEngine


class TestUnifiedScoringEngine(unittest.TestCase):
    """Test suite for unified scoring engine."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample simplified format
        self.simplified_config = {
            "settings": {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "audit_threshold": 60,
            },
            "templates": {
                "tech_opportunity": {
                    "description": "Technology improvement opportunity",
                    "score": 15,
                    "audit_category": "technology",
                }
            },
            "audit_opportunities": [
                {
                    "name": "jquery_outdated",
                    "template": "tech_opportunity",
                    "when": {"technology": "jQuery", "version": "<3.0.0"},
                    "audit_potential": "high",
                },
                {
                    "name": "poor_performance",
                    "description": "Poor website performance",
                    "score": 20,
                    "when": {"performance_score": "<50"},
                    "audit_potential": "high",
                },
            ],
            "audit_multipliers": [
                {
                    "name": "perfect_combo",
                    "description": "Perfect audit combination",
                    "multiplier": 1.5,
                    "when": {
                        "all": [{"technology": "jQuery"}, {"performance_score": "<60"}]
                    },
                }
            ],
        }

        # Sample legacy format
        self.legacy_config = {
            "settings": {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "high_score_threshold": 75,
            },
            "rules": [
                {
                    "name": "outdated_jquery",
                    "description": "Business uses outdated jQuery",
                    "condition": {
                        "tech_stack_contains": "jQuery",
                        "tech_stack_version_lt": {
                            "technology": "jQuery",
                            "version": "3.0.0",
                        },
                    },
                    "score": 10,
                },
                {
                    "name": "poor_performance",
                    "description": "Poor performance score",
                    "condition": {"performance_score_lt": 50},
                    "score": 20,
                },
            ],
            "multipliers": [
                {
                    "name": "tech_stack_match",
                    "description": "Perfect tech stack match",
                    "condition": {
                        "tech_stack_contains": "jQuery",
                        "performance_score_lt": 60,
                    },
                    "multiplier": 1.5,
                }
            ],
        }

        # Sample business data for testing
        self.business_data = {
            "tech_stack": ["jQuery", "WordPress"],
            "tech_stack_versions": {"jQuery": "2.1.4"},
            "performance_score": 45,
            "lcp": 3000,  # milliseconds
            "cls": 0.3,
            "category": ["restaurant"],
            "state": "NY",
            "review_count": 25,
        }

    def test_format_detection_simplified(self):
        """Test detection of simplified format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            self.assertEqual(engine.format_type, "simplified")
            self.assertIsNotNone(engine.simplified_parser)
            self.assertIsNone(engine.legacy_parser)

    def test_format_detection_legacy(self):
        """Test detection of legacy format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.legacy_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            self.assertEqual(engine.format_type, "legacy")
            self.assertIsNotNone(engine.legacy_parser)
            self.assertIsNone(engine.simplified_parser)

    def test_scoring_with_simplified_format(self):
        """Test scoring business with simplified format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            result = engine.score_business(self.business_data)

            # Verify result structure
            self.assertIn("final_score", result)
            self.assertIn("format_used", result)
            self.assertIn("audit_potential", result)
            self.assertIn("applied_rules", result)
            self.assertIn("applied_multipliers", result)

            self.assertEqual(result["format_used"], "simplified")
            self.assertGreater(
                result["final_score"], 50
            )  # Should have positive adjustments

    def test_scoring_with_legacy_format(self):
        """Test scoring business with legacy format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.legacy_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            result = engine.score_business(self.business_data)

            # Verify result structure
            self.assertIn("final_score", result)
            self.assertIn("format_used", result)
            self.assertIn("applied_rules", result)
            self.assertIn("applied_multipliers", result)

            self.assertEqual(result["format_used"], "legacy")
            self.assertGreater(
                result["final_score"], 50
            )  # Should have positive adjustments

    def test_audit_potential_calculation(self):
        """Test audit potential calculation for simplified format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            # Test with high-scoring business (should have high audit potential)
            high_score_business = {
                "tech_stack": ["jQuery"],
                "tech_stack_versions": {"jQuery": "2.0.0"},
                "performance_score": 30,  # Very poor performance
                "category": ["restaurant"],
            }

            result = engine.score_business(high_score_business)
            self.assertIn("audit_potential", result)
            # High score in simplified format means high audit potential

    def test_scoring_consistency_between_formats(self):
        """Test that similar rules in both formats produce comparable results."""
        # Create similar business data that should trigger rules in both formats
        test_business = {
            "tech_stack": ["jQuery"],
            "tech_stack_versions": {"jQuery": "2.5.0"},
            "performance_score": 40,
        }

        # Test simplified format
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            simplified_engine = UnifiedScoringEngine(f.name)
            simplified_engine.load_rules()
            simplified_result = simplified_engine.score_business(test_business)

        # Test legacy format
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.legacy_config, f)
            f.flush()

            legacy_engine = UnifiedScoringEngine(f.name)
            legacy_engine.load_rules()
            legacy_result = legacy_engine.score_business(test_business)

        # Both should have scores above base score due to jQuery and poor performance
        self.assertGreater(simplified_result["final_score"], 50)
        self.assertGreater(legacy_result["final_score"], 50)

        # Both should have applied rules
        self.assertGreater(len(simplified_result["applied_rules"]), 0)
        self.assertGreater(len(legacy_result["applied_rules"]), 0)

    def test_get_format_info(self):
        """Test getting format information."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            info = engine.get_format_info()

            self.assertEqual(info["format_type"], "simplified")
            self.assertEqual(info["config_path"], f.name)
            self.assertGreater(info["rules_count"], 0)
            self.assertIn("settings", info)

    def test_score_bounds_enforcement(self):
        """Test that scores are properly bounded."""
        # Create config with extreme scores
        extreme_config = {
            "settings": {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "audit_threshold": 60,
            },
            "audit_opportunities": [
                {
                    "name": "extreme_positive",
                    "score": 200,  # This should be capped
                    "when": {"technology": "jQuery"},
                }
            ],
            "exclusions": [
                {
                    "name": "extreme_negative",
                    "score": -200,  # This should be floored
                    "when": {"technology": "React"},
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(extreme_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            # Test extreme positive
            positive_business = {"tech_stack": ["jQuery"]}
            result = engine.score_business(positive_business)
            self.assertLessEqual(result["final_score"], 100)

            # Test extreme negative
            negative_business = {"tech_stack": ["React"]}
            result = engine.score_business(negative_business)
            self.assertGreaterEqual(result["final_score"], 0)

    def test_empty_rules_handling(self):
        """Test handling of empty or minimal rule sets."""
        minimal_config = {
            "settings": {"base_score": 50, "audit_threshold": 60},
            "audit_opportunities": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(minimal_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            result = engine.score_business(self.business_data)

            # Should return base score with no adjustments
            self.assertEqual(result["final_score"], 50)
            self.assertEqual(len(result["applied_rules"]), 0)
            self.assertEqual(len(result["applied_multipliers"]), 0)

    def test_multiplier_application(self):
        """Test that multipliers are properly applied."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.simplified_config, f)
            f.flush()

            engine = UnifiedScoringEngine(f.name)
            engine.load_rules()

            # Business that should trigger both rules and multiplier
            multiplier_business = {
                "tech_stack": ["jQuery"],
                "tech_stack_versions": {"jQuery": "2.0.0"},
                "performance_score": 45,
            }

            result = engine.score_business(multiplier_business)

            # Should have applied multiplier
            self.assertGreater(len(result["applied_multipliers"]), 0)
            self.assertGreater(result["final_multiplier"], 1.0)

            # Final score should be higher than preliminary score
            self.assertGreater(result["final_score"], result["preliminary_score"])


if __name__ == "__main__":
    unittest.main()
