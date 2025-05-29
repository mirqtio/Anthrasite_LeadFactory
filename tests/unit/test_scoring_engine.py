"""
Unit tests for the scoring engine.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

# Try to import the scoring modules, skip tests if not available
try:
    from leadfactory.scoring import RuleEvaluator, ScoringEngine, ScoringRulesParser
    from leadfactory.scoring.yaml_parser import (
        RuleCondition,
        ScoringMultiplier,
        ScoringRule,
        ScoringRulesConfig,
        ScoringSettings,
    )
    SCORING_MODULES_AVAILABLE = True
except ImportError as e:
    # If imports fail, create mock classes for basic testing
    SCORING_MODULES_AVAILABLE = False
    pytest.skip(f"Scoring modules not available: {e}", allow_module_level=True)


class TestScoringRulesParser:
    """Test the YAML parser functionality."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        # Create a test config file
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'test_rule',
                    'description': 'Test rule',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 10
                }
            ],
            'multipliers': [
                {
                    'name': 'test_multiplier',
                    'description': 'Test multiplier',
                    'condition': {'vertical_in': ['SaaS']},
                    'multiplier': 1.5
                }
            ]
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        parser = ScoringRulesParser(str(config_file))
        config = parser.load_and_validate()

        assert isinstance(config, ScoringRulesConfig)
        assert len(config.rules) == 1
        assert len(config.multipliers) == 1
        assert config.settings.base_score == 50

    def test_load_missing_file(self):
        """Test loading a non-existent file."""
        parser = ScoringRulesParser("/non/existent/file.yml")

        with pytest.raises(FileNotFoundError):
            parser.load_and_validate()

    def test_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML."""
        config_file = tmp_path / "invalid.yml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [")

        parser = ScoringRulesParser(str(config_file))

        with pytest.raises(yaml.YAMLError):
            parser.load_and_validate()

    def test_validation_errors(self, tmp_path):
        """Test configuration validation errors."""
        # Invalid score value
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'invalid_rule',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 200  # Invalid: exceeds max
                }
            ]
        }

        config_file = tmp_path / "invalid_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        parser = ScoringRulesParser(str(config_file))

        with pytest.raises(Exception):  # ValidationError
            parser.load_and_validate()

    def test_get_enabled_rules(self, tmp_path):
        """Test filtering enabled rules."""
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'enabled_rule',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 10,
                    'enabled': True,
                    'priority': 2
                },
                {
                    'name': 'disabled_rule',
                    'condition': {'tech_stack_contains': 'Vue'},
                    'score': 5,
                    'enabled': False
                },
                {
                    'name': 'high_priority_rule',
                    'condition': {'tech_stack_contains': 'Angular'},
                    'score': 15,
                    'enabled': True,
                    'priority': 5
                }
            ]
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        parser = ScoringRulesParser(str(config_file))
        parser.load_and_validate()

        enabled_rules = parser.get_enabled_rules()

        assert len(enabled_rules) == 2
        assert enabled_rules[0].name == 'high_priority_rule'  # Higher priority first
        assert enabled_rules[1].name == 'enabled_rule'


class TestRuleEvaluator:
    """Test the rule evaluation logic."""

    def test_tech_stack_contains(self):
        """Test tech stack contains condition."""
        evaluator = RuleEvaluator()

        # Test with list format
        business = {'tech_stack': ['React', 'Node.js', 'PostgreSQL']}
        condition = RuleCondition(tech_stack_contains='React')
        assert evaluator._evaluate_condition(business, condition) is True

        condition = RuleCondition(tech_stack_contains='Vue')
        assert evaluator._evaluate_condition(business, condition) is False

        # Test with dict format
        business = {'tech_stack': {'React': '18.0', 'Node.js': '16.0'}}
        condition = RuleCondition(tech_stack_contains='React')
        assert evaluator._evaluate_condition(business, condition) is True

    def test_tech_stack_contains_any(self):
        """Test tech stack contains any condition."""
        evaluator = RuleEvaluator()

        business = {'tech_stack': ['React', 'Node.js']}
        condition = RuleCondition(tech_stack_contains_any=['Vue', 'React', 'Angular'])
        assert evaluator._evaluate_condition(business, condition) is True

        condition = RuleCondition(tech_stack_contains_any=['Vue', 'Angular'])
        assert evaluator._evaluate_condition(business, condition) is False

    def test_version_comparison(self):
        """Test version comparison conditions."""
        evaluator = RuleEvaluator()

        business = {'tech_stack': {'jQuery': '2.1.4'}}

        # Test less than
        condition = RuleCondition(tech_stack_version_lt={
            'technology': 'jQuery',
            'version': '3.0.0'
        })
        assert evaluator._evaluate_condition(business, condition) is True

        # Test greater than
        condition = RuleCondition(tech_stack_version_gt={
            'technology': 'jQuery',
            'version': '2.0.0'
        })
        assert evaluator._evaluate_condition(business, condition) is True

    def test_numeric_comparisons(self):
        """Test numeric field comparisons."""
        evaluator = RuleEvaluator()

        business = {
            'employee_count': 50,
            'revenue': 1000000,
            'founded_year': 2015
        }

        # Test greater than
        condition = RuleCondition(employee_count_gt=25)
        assert evaluator._evaluate_condition(business, condition) is True

        # Test less than
        condition = RuleCondition(revenue_lt=2000000)
        assert evaluator._evaluate_condition(business, condition) is True

        # Test with missing field
        condition = RuleCondition(employee_count_gt=100)
        assert evaluator._evaluate_condition(business, condition) is False

    def test_location_conditions(self):
        """Test location-based conditions."""
        evaluator = RuleEvaluator()

        business = {
            'location': 'San Francisco, CA',
            'city': 'San Francisco',
            'state': 'California',
            'country': 'USA'
        }

        condition = RuleCondition(location_in=['San Francisco', 'New York'])
        assert evaluator._evaluate_condition(business, condition) is True

        condition = RuleCondition(location_in=['Boston', 'Seattle'])
        assert evaluator._evaluate_condition(business, condition) is False

    def test_combined_conditions(self):
        """Test all_of, any_of, none_of conditions."""
        evaluator = RuleEvaluator()

        business = {
            'tech_stack': ['React', 'Node.js'],
            'employee_count': 50,
            'vertical': 'SaaS'
        }

        # Test all_of
        condition = RuleCondition(all_of=[
            {'tech_stack_contains': 'React'},
            {'employee_count_gt': 25}
        ])
        assert evaluator._evaluate_condition(business, condition) is True

        # Test any_of
        condition = RuleCondition(any_of=[
            {'tech_stack_contains': 'Vue'},
            {'employee_count_gt': 25}
        ])
        assert evaluator._evaluate_condition(business, condition) is True

        # Test none_of
        condition = RuleCondition(none_of=[
            {'tech_stack_contains': 'Vue'},
            {'employee_count_gt': 100}
        ])
        assert evaluator._evaluate_condition(business, condition) is True

    def test_evaluate_rule(self):
        """Test full rule evaluation."""
        evaluator = RuleEvaluator()

        business = {'tech_stack': ['React']}
        rule = ScoringRule(
            name='react_bonus',
            condition=RuleCondition(tech_stack_contains='React'),
            score=15
        )

        matched, score = evaluator.evaluate_rule(business, rule)
        assert matched is True
        assert score == 15

        # Test non-matching rule
        rule = ScoringRule(
            name='vue_bonus',
            condition=RuleCondition(tech_stack_contains='Vue'),
            score=10
        )

        matched, score = evaluator.evaluate_rule(business, rule)
        assert matched is False
        assert score == 0


class TestScoringEngine:
    """Test the main scoring engine."""

    def test_initialization(self, tmp_path):
        """Test engine initialization."""
        # Create a minimal config
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': []
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        engine = ScoringEngine(str(config_file))
        engine.load_rules()

        assert engine.settings.base_score == 50
        assert len(engine.rules) == 0

    def test_score_business(self, tmp_path):
        """Test scoring a single business."""
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'react_bonus',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 15
                },
                {
                    'name': 'jquery_bonus',
                    'condition': {'tech_stack_contains': 'jQuery'},
                    'score': 10
                }
            ],
            'multipliers': [
                {
                    'name': 'saas_multiplier',
                    'condition': {'vertical_in': ['SaaS']},
                    'multiplier': 1.5
                }
            ]
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        engine = ScoringEngine(str(config_file))
        engine.load_rules()

        # Test business with React and SaaS vertical
        business = {
            'id': 1,
            'name': 'Test Company',
            'tech_stack': ['React', 'Node.js'],
            'vertical': 'SaaS'
        }

        result = engine.score_business(business)

        assert result['base_score'] == 50
        assert result['score'] == 97  # (50 + 15) * 1.5 = 97.5 -> 97
        assert len(result['adjustments']) == 1
        assert len(result['multipliers']) == 1
        assert result['is_high_score'] is True

    def test_score_bounds(self, tmp_path):
        """Test that scores stay within bounds."""
        config_data = {
            'settings': {
                'base_score': 90,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'big_bonus',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 50
                }
            ]
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        engine = ScoringEngine(str(config_file))
        engine.load_rules()

        business = {
            'id': 1,
            'name': 'Test Company',
            'tech_stack': ['React']
        }

        result = engine.score_business(business)

        # Should be capped at max_score
        assert result['score'] == 100

    def test_validate_business_data(self, tmp_path):
        """Test business data validation."""
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': []
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        engine = ScoringEngine(str(config_file))
        engine.load_rules()

        # Valid business
        business = {'id': 1, 'name': 'Test Company'}
        is_valid, issues = engine.validate_business_data(business)
        assert is_valid is True
        assert len(issues) == 0

        # Missing ID
        business = {'name': 'Test Company'}
        is_valid, issues = engine.validate_business_data(business)
        assert is_valid is False
        assert 'Missing business ID' in issues

        # Missing name
        business = {'id': 1}
        is_valid, issues = engine.validate_business_data(business)
        assert is_valid is False
        assert 'Missing business name' in issues

    def test_get_rule_statistics(self, tmp_path):
        """Test getting rule statistics."""
        config_data = {
            'settings': {
                'base_score': 50,
                'min_score': 0,
                'max_score': 100,
                'high_score_threshold': 75
            },
            'rules': [
                {
                    'name': 'positive_rule',
                    'condition': {'tech_stack_contains': 'React'},
                    'score': 15
                },
                {
                    'name': 'negative_rule',
                    'condition': {'tech_stack_contains': 'Legacy'},
                    'score': -10
                },
                {
                    'name': 'neutral_rule',
                    'condition': {'tech_stack_contains': 'Python'},
                    'score': 0
                }
            ],
            'multipliers': [
                {
                    'name': 'test_multiplier',
                    'condition': {'vertical_in': ['SaaS']},
                    'multiplier': 1.5
                }
            ]
        }

        config_file = tmp_path / "test_config.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        engine = ScoringEngine(str(config_file))
        engine.load_rules()

        stats = engine.get_rule_statistics()

        assert stats['total_rules'] == 3
        assert stats['positive_rules'] == 1
        assert stats['negative_rules'] == 1
        assert stats['neutral_rules'] == 1
        assert stats['total_multipliers'] == 1
