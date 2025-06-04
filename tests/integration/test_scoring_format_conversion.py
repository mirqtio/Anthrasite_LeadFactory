"""
Integration tests for scoring format conversion and compatibility.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from leadfactory.scoring.rule_converter import RuleConverter
from leadfactory.scoring.unified_scoring_engine import UnifiedScoringEngine
from leadfactory.scoring.yaml_parser import ScoringRulesParser


class TestScoringFormatConversion(unittest.TestCase):
    """Integration tests for scoring format conversion."""

    def setUp(self):
        """Set up test fixtures."""
        # Load actual scoring rules for testing
        self.current_rules_path = Path(__file__).parent.parent.parent / "etc" / "scoring_rules.yml"
        self.converter = RuleConverter()

        # Sample test businesses
        self.test_businesses = [
            # High audit potential business
            {
                "business_id": "test_001",
                "tech_stack": ["jQuery", "WordPress"],
                "tech_stack_versions": {"jQuery": "2.1.4"},
                "performance_score": 35,
                "lcp": 3500,
                "cls": 0.4,
                "category": ["restaurant"],
                "state": "NY",
                "review_count": 15,
                "website": "https://example-restaurant.com"
            },
            # Medium audit potential business
            {
                "business_id": "test_002",
                "tech_stack": ["WordPress", "Bootstrap"],
                "performance_score": 65,
                "lcp": 2200,
                "cls": 0.1,
                "category": ["retail"],
                "state": "WA",
                "review_count": 45,
                "website": "https://example-store.com"
            },
            # Low audit potential business (modern tech)
            {
                "business_id": "test_003",
                "tech_stack": ["React", "Next.js", "TypeScript"],
                "performance_score": 85,
                "lcp": 1800,
                "cls": 0.05,
                "category": ["professional_service"],
                "state": "IN",
                "review_count": 120,
                "website": "https://modern-business.com"
            },
            # Exclusion case (no website)
            {
                "business_id": "test_004",
                "tech_stack": [],
                "category": ["entertainment"],
                "state": "CA",
                "review_count": 5,
                "website_missing": True
            }
        ]

    def test_legacy_to_simplified_conversion(self):
        """Test converting legacy format to simplified format."""
        if not self.current_rules_path.exists():
            self.skipTest("Legacy scoring rules file not found")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as output_file:
            success = self.converter.convert_legacy_to_simplified(
                str(self.current_rules_path),
                output_file.name
            )

            self.assertTrue(success, "Conversion should succeed")

            # Verify the converted file is valid simplified format
            with open(output_file.name) as f:
                converted_config = yaml.safe_load(f)

            # Check required sections
            self.assertIn("settings", converted_config)
            self.assertIn("audit_opportunities", converted_config)

            # Check settings conversion
            self.assertIn("audit_threshold", converted_config["settings"])
            self.assertIsInstance(converted_config["audit_opportunities"], list)

            # Should have some rules converted
            self.assertGreater(len(converted_config["audit_opportunities"]), 0)

    def test_scoring_equivalence_both_formats(self):
        """Test that both formats produce similar scoring results."""
        if not self.current_rules_path.exists():
            self.skipTest("Legacy scoring rules file not found")

        # Convert to simplified format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as simplified_file:
            success = self.converter.convert_legacy_to_simplified(
                str(self.current_rules_path),
                simplified_file.name
            )
            self.assertTrue(success)

            # Create engines for both formats
            legacy_engine = UnifiedScoringEngine(str(self.current_rules_path))
            simplified_engine = UnifiedScoringEngine(simplified_file.name)

            legacy_engine.load_rules()
            simplified_engine.load_rules()

            # Score test businesses with both engines
            for business in self.test_businesses:
                with self.subTest(business_id=business["business_id"]):
                    legacy_result = legacy_engine.score_business(business)
                    simplified_result = simplified_engine.score_business(business)

                    # Verify both engines processed the business
                    self.assertIn("final_score", legacy_result)
                    self.assertIn("final_score", simplified_result)

                    # Format detection should work correctly
                    self.assertEqual(legacy_result["format_used"], "legacy")
                    self.assertEqual(simplified_result["format_used"], "simplified")

                    # Scores don't need to be identical but should be in same ballpark
                    # for businesses with clear audit indicators
                    if business["business_id"] in ["test_001", "test_002"]:
                        # Both should identify audit opportunities
                        self.assertGreater(legacy_result["final_score"], 50)
                        self.assertGreater(simplified_result["final_score"], 50)

    def test_rule_coverage_preservation(self):
        """Test that rule conversion preserves important scoring logic."""
        if not self.current_rules_path.exists():
            self.skipTest("Legacy scoring rules file not found")

        # Load original legacy rules
        legacy_parser = ScoringRulesParser(str(self.current_rules_path))
        legacy_config = legacy_parser.load_and_validate()

        # Convert to simplified
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as simplified_file:
            success = self.converter.convert_legacy_to_simplified(
                str(self.current_rules_path),
                simplified_file.name
            )
            self.assertTrue(success)

            # Load converted simplified rules
            simplified_engine = UnifiedScoringEngine(simplified_file.name)
            simplified_engine.load_rules()

            # Check that key rule categories are preserved
            rule_names = [rule.name for rule in simplified_engine.rules]

            # Should have technology-related rules
            tech_rules = [name for name in rule_names if "jquery" in name.lower() or "tech" in name.lower()]
            self.assertGreater(len(tech_rules), 0, "Should preserve technology rules")

            # Should have performance-related rules
            perf_rules = [name for name in rule_names if "performance" in name.lower() or "lcp" in name.lower()]
            self.assertGreater(len(perf_rules), 0, "Should preserve performance rules")

    def test_template_system_functionality(self):
        """Test that the template system works correctly in converted rules."""
        # Create a simple legacy config for testing templates
        test_legacy_config = {
            "settings": {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "high_score_threshold": 75
            },
            "rules": [
                {
                    "name": "jquery_old",
                    "description": "jQuery is outdated",
                    "condition": {"tech_stack_contains": "jQuery"},
                    "score": 15
                },
                {
                    "name": "performance_bad",
                    "description": "Performance is poor",
                    "condition": {"performance_score_lt": 50},
                    "score": 20
                }
            ],
            "multipliers": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as legacy_file:
            yaml.dump(test_legacy_config, legacy_file)
            legacy_file.flush()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as simplified_file:
                success = self.converter.convert_legacy_to_simplified(
                    legacy_file.name,
                    simplified_file.name
                )
                self.assertTrue(success)

                # Load and verify templates were created
                with open(simplified_file.name) as f:
                    converted = yaml.safe_load(f)

                # Should have templates section
                self.assertIn("templates", converted)
                templates = converted["templates"]

                # Should have common template categories
                template_names = list(templates.keys())
                self.assertTrue(any("tech" in name for name in template_names))

    def test_audit_potential_assignment(self):
        """Test that audit potential is correctly assigned during conversion."""
        test_legacy_config = {
            "settings": {"base_score": 50, "high_score_threshold": 75},
            "rules": [
                {"name": "high_impact", "score": 20, "condition": {"tech_stack_contains": "jQuery"}},
                {"name": "medium_impact", "score": 10, "condition": {"performance_score_lt": 60}},
                {"name": "low_impact", "score": 5, "condition": {"state_equals": "NY"}},
                {"name": "negative_impact", "score": -15, "condition": {"tech_stack_contains": "React"}}
            ],
            "multipliers": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as legacy_file:
            yaml.dump(test_legacy_config, legacy_file)
            legacy_file.flush()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as simplified_file:
                success = self.converter.convert_legacy_to_simplified(
                    legacy_file.name,
                    simplified_file.name
                )
                self.assertTrue(success)

                with open(simplified_file.name) as f:
                    converted = yaml.safe_load(f)

                # Check audit potential assignments
                opportunities = converted.get("audit_opportunities", [])
                exclusions = converted.get("exclusions", [])

                # High score rules should have high audit potential
                high_rule = next((r for r in opportunities if r["name"] == "high_impact"), None)
                self.assertIsNotNone(high_rule)
                self.assertEqual(high_rule.get("audit_potential"), "high")

                # Negative score rules should be in exclusions
                negative_rule = next((r for r in exclusions if r["name"] == "negative_impact"), None)
                self.assertIsNotNone(negative_rule)

    def test_performance_conditions_conversion(self):
        """Test specific conversion of performance-related conditions."""
        test_legacy_config = {
            "settings": {"base_score": 50, "high_score_threshold": 75},
            "rules": [
                {
                    "name": "slow_lcp",
                    "condition": {"lcp_gt": 2500},  # milliseconds
                    "score": 15
                },
                {
                    "name": "high_cls",
                    "condition": {"cls_gt": 0.25},
                    "score": 10
                },
                {
                    "name": "poor_performance",
                    "condition": {"performance_score_lt": 50},
                    "score": 20
                }
            ],
            "multipliers": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as legacy_file:
            yaml.dump(test_legacy_config, legacy_file)
            legacy_file.flush()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as simplified_file:
                success = self.converter.convert_legacy_to_simplified(
                    legacy_file.name,
                    simplified_file.name
                )
                self.assertTrue(success)

                # Test that converted rules work with actual business data
                engine = UnifiedScoringEngine(simplified_file.name)
                engine.load_rules()

                slow_business = {
                    "performance_score": 40,
                    "lcp": 3000,  # This should trigger LCP rule
                    "cls": 0.3    # This should trigger CLS rule
                }

                result = engine.score_business(slow_business)

                # Should have applied multiple performance rules
                self.assertGreater(len(result["applied_rules"]), 1)
                self.assertGreater(result["final_score"], 50)


if __name__ == '__main__':
    unittest.main()
