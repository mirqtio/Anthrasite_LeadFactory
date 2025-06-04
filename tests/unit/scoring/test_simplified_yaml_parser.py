"""
Unit tests for simplified YAML parser.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from leadfactory.scoring.simplified_yaml_parser import SimplifiedYamlParser


class TestSimplifiedYamlParser(unittest.TestCase):
    """Test suite for simplified YAML parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_config = {
            "settings": {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "audit_threshold": 60,
            },
            "templates": {
                "tech_modernization": {
                    "description": "Technology modernization opportunity",
                    "score": 15,
                    "audit_category": "technology_upgrade",
                }
            },
            "audit_opportunities": [
                {
                    "name": "jquery_upgrade",
                    "template": "tech_modernization",
                    "when": {"technology": "jQuery", "version": "<3.0.0"},
                    "audit_potential": "high",
                    "priority": 90,
                },
                {
                    "name": "poor_performance",
                    "description": "Website has poor performance",
                    "score": 20,
                    "audit_category": "performance",
                    "when": {"performance_score": "<50"},
                    "audit_potential": "high",
                },
            ],
            "exclusions": [
                {
                    "name": "modern_framework",
                    "description": "Uses modern framework",
                    "score": -15,
                    "when": {"technology": ["React", "Vue", "Angular"]},
                }
            ],
            "audit_multipliers": [
                {
                    "name": "perfect_candidate",
                    "description": "Perfect audit candidate",
                    "multiplier": 1.5,
                    "when": {
                        "all": [{"technology": "jQuery"}, {"performance_score": "<60"}]
                    },
                }
            ],
        }

    def test_load_valid_config(self):
        """Test loading a valid simplified configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            config = parser.load_and_validate()

            self.assertEqual(config.settings.base_score, 50)
            self.assertEqual(config.settings.audit_threshold, 60)
            self.assertEqual(len(config.audit_opportunities), 2)
            self.assertEqual(len(config.exclusions), 1)
            self.assertEqual(len(config.audit_multipliers), 1)

    def test_template_resolution(self):
        """Test that template references are properly resolved."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            config = parser.load_and_validate()

            # Check that template was resolved
            jquery_rule = config.audit_opportunities[0]
            self.assertEqual(jquery_rule.name, "jquery_upgrade")
            self.assertEqual(
                jquery_rule.description, "Technology modernization opportunity"
            )
            self.assertEqual(jquery_rule.score, 15)
            self.assertEqual(jquery_rule.audit_category, "technology_upgrade")

    def test_get_audit_opportunities(self):
        """Test getting audit opportunities with proper sorting."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            parser.load_and_validate()

            opportunities = parser.get_audit_opportunities()
            self.assertEqual(len(opportunities), 2)

            # Should be sorted by priority (higher first)
            self.assertEqual(opportunities[0].name, "jquery_upgrade")
            self.assertEqual(opportunities[0].priority, 90)

    def test_convert_to_legacy_format(self):
        """Test conversion to legacy format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            parser.load_and_validate()

            legacy_config = parser.convert_to_legacy_format()

            # Check structure
            self.assertIn("settings", legacy_config)
            self.assertIn("rules", legacy_config)
            self.assertIn("multipliers", legacy_config)

            # Check settings conversion
            self.assertEqual(legacy_config["settings"]["base_score"], 50)
            self.assertEqual(legacy_config["settings"]["high_score_threshold"], 60)

            # Check rules conversion
            self.assertEqual(
                len(legacy_config["rules"]), 3
            )  # 2 opportunities + 1 exclusion

    def test_performance_condition_parsing(self):
        """Test parsing of performance conditions."""
        config = {
            "settings": {"base_score": 50, "audit_threshold": 60},
            "audit_opportunities": [
                {"name": "slow_lcp", "score": 15, "when": {"lcp": ">2.5s"}},
                {"name": "high_cls", "score": 10, "when": {"cls": ">0.25"}},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            parser.load_and_validate()

            legacy_config = parser.convert_to_legacy_format()

            # Find the converted rules
            lcp_rule = next(
                r for r in legacy_config["rules"] if r["name"] == "slow_lcp"
            )
            cls_rule = next(
                r for r in legacy_config["rules"] if r["name"] == "high_cls"
            )

            # Check LCP conversion (should convert seconds to milliseconds)
            self.assertIn("lcp_gt", lcp_rule["condition"])
            self.assertEqual(lcp_rule["condition"]["lcp_gt"], 2500.0)

            # Check CLS conversion
            self.assertIn("cls_gt", cls_rule["condition"])
            self.assertEqual(cls_rule["condition"]["cls_gt"], ">0.25")

    def test_business_type_condition_parsing(self):
        """Test parsing of business type conditions."""
        config = {
            "settings": {"base_score": 50, "audit_threshold": 60},
            "audit_opportunities": [
                {
                    "name": "restaurant_bonus",
                    "score": 10,
                    "when": {"business_type": ["restaurant", "cafe"]},
                },
                {
                    "name": "retail_bonus",
                    "score": 5,
                    "when": {"business_type": "retail"},
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            parser.load_and_validate()

            legacy_config = parser.convert_to_legacy_format()

            restaurant_rule = next(
                r for r in legacy_config["rules"] if r["name"] == "restaurant_bonus"
            )
            retail_rule = next(
                r for r in legacy_config["rules"] if r["name"] == "retail_bonus"
            )

            # Check business type conversions
            self.assertIn("category_contains_any", restaurant_rule["condition"])
            self.assertEqual(
                restaurant_rule["condition"]["category_contains_any"],
                ["restaurant", "cafe"],
            )

            self.assertIn("category_contains", retail_rule["condition"])
            self.assertEqual(retail_rule["condition"]["category_contains"], "retail")

    def test_invalid_config_validation(self):
        """Test that invalid configurations are properly rejected."""
        invalid_configs = [
            # Missing required settings
            {"audit_opportunities": []},
            # Invalid score range
            {
                "settings": {"base_score": 50, "audit_threshold": 60},
                "audit_opportunities": [
                    {"name": "invalid", "score": 150, "when": {"technology": "test"}}
                ],
            },
            # Invalid audit potential
            {
                "settings": {"base_score": 50, "audit_threshold": 60},
                "audit_opportunities": [
                    {
                        "name": "invalid",
                        "score": 10,
                        "audit_potential": "super_high",
                        "when": {"technology": "test"},
                    }
                ],
            },
        ]

        for invalid_config in invalid_configs:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as f:
                yaml.dump(invalid_config, f)
                f.flush()

                parser = SimplifiedYamlParser(f.name)
                with self.assertRaises(Exception):
                    parser.load_and_validate()

    def test_composite_conditions(self):
        """Test parsing of composite conditions (all, any, none)."""
        config = {
            "settings": {"base_score": 50, "audit_threshold": 60},
            "audit_opportunities": [
                {
                    "name": "complex_rule",
                    "score": 20,
                    "when": {
                        "all": [
                            {"technology": "WordPress"},
                            {"performance_score": "<60"},
                        ]
                    },
                }
            ],
            "audit_multipliers": [
                {
                    "name": "any_condition",
                    "multiplier": 1.3,
                    "when": {"any": [{"lcp": ">3s"}, {"cls": ">0.5"}]},
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config, f)
            f.flush()

            parser = SimplifiedYamlParser(f.name)
            config_obj = parser.load_and_validate()

            # Verify complex conditions are preserved
            complex_rule = config_obj.audit_opportunities[0]
            self.assertIsNotNone(complex_rule.when.all)
            self.assertEqual(len(complex_rule.when.all), 2)

            any_mult = config_obj.audit_multipliers[0]
            self.assertIsNotNone(any_mult.when.any)
            self.assertEqual(len(any_mult.when.any), 2)


if __name__ == "__main__":
    unittest.main()
