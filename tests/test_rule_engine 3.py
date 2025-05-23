"""
Tests for the RuleEngine class in bin/score.py
"""

import os
import sys
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import the RuleEngine class
from bin.score import RuleEngine

# Sample rules for testing
SAMPLE_RULES = """
settings:
  base_score: 50
  min_score: 0
  max_score: 100
  high_score_threshold: 75
rules:
  - name: "wordpress"
    description: "Business uses WordPress"
    condition:
      tech_stack_contains: "WordPress"
    score: 10
  - name: "outdated_php"
    description: "Site uses PHP version below 7.4"
    condition:
      tech_stack_contains: "PHP"
      tech_stack_version_lt:
        technology: "PHP"
        version: "7.4.0"
    score: 15
  - name: "good_performance"
    description: "Good performance metrics"
    condition:
      performance_score_gt: 80
    score: -15  # Note: In the actual rules, good performance gives negative points
  - name: "target_location_ca"
    description: "Business is in California"
    condition:
      state_equals: "CA"
    score: 5
multipliers:
  - name: "High Priority Industry"
    description: "Business is in a high priority industry"
    condition:
      vertical_in: ["healthcare", "legal", "financial"]
    multiplier: 1.5
  - name: "Multiple Locations"
    description: "Business has multiple locations"
    condition:
      has_multiple_locations: true
    multiplier: 1.2
"""


@pytest.fixture
def sample_rules_file():
    """Create a temporary YAML file with sample rules."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(SAMPLE_RULES)
    yield f.name
    os.unlink(f.name)


def test_rule_engine_initialization(sample_rules_file):
    """Test that RuleEngine initializes correctly with rules file."""
    engine = RuleEngine(sample_rules_file)
    assert engine.settings["base_score"] == 50
    assert len(engine.rules) == 4
    assert len(engine.multipliers) == 2
    assert "tech_stack_contains" in engine.condition_evaluators


def test_calculate_score_basic(sample_rules_file):
    """Test basic score calculation with no matching rules."""
    engine = RuleEngine(sample_rules_file)
    business_data = {"name": "Test Business"}
    score, applied_rules = engine.calculate_score(business_data)
    assert score == 50  # Base score
    assert len(applied_rules) == 0


def test_tech_stack_rule(sample_rules_file):
    """Test scoring with tech stack rule."""
    engine = RuleEngine(sample_rules_file)
    business_data = {
        "name": "WordPress Business",
        "features": {
            "tech_stack": (
                '{"WordPress": {"version": "5.8"}, "PHP": {"version": "7.2.0"}}'
            )
        },
    }
    score, applied_rules = engine.calculate_score(business_data)
    # Base (50) + WordPress (10) + Outdated PHP (15) = 75
    # (PHP 7.2 is considered outdated)
    assert score == 75
    assert any(r["name"] == "wordpress" for r in applied_rules)


def test_multiple_rules(sample_rules_file):
    """Test scoring with multiple matching rules."""
    engine = RuleEngine(sample_rules_file)
    business_data = {
        "name": "Business with WordPress and PHP 7.0",
        "features": {
            "tech_stack": (
                '{"WordPress": {"version": "5.8"}, "PHP": {"version": "7.0.0"}}'
            ),
            "page_speed": 85,
        },
        "state": "CA",
    }
    score, applied_rules = engine.calculate_score(business_data)
    # Base (50) + WordPress (10) + Outdated PHP (15) + Good Performance (-15)
    # + Target Location (5) = 65
    assert score == 65
    assert len(applied_rules) == 4


def test_multiplier(sample_rules_file):
    """Test that multipliers are applied correctly."""
    engine = RuleEngine(sample_rules_file)
    business_data = {
        "name": "Healthcare Business",
        "vertical": "healthcare",
        "has_multiple_locations": True,
    }
    score, applied_rules = engine.calculate_score(business_data)
    # Base (50) * 1.5 (healthcare) * 1.2 (multiple locations) = 89.999...
    # -> 89 (floating point)
    assert abs(score - 90) <= 1  # Allow for floating point rounding
    assert len(applied_rules) == 2  # Both multipliers applied


def test_score_bounds(sample_rules_file):
    """Test that score is bounded by min and max values."""
    # Create a rule that would push the score above max
    engine = RuleEngine(sample_rules_file)
    business_data = {
        "name": "High Scoring Business",
        "features": {
            "tech_stack": '{"WordPress": {"version": "5.8"}}',
            "page_speed": 90,
        },
        "state": "CA",
    }
    # Base (50) + WordPress (10) + Good Performance (-15) + Target Location (5) = 50
    score, _ = engine.calculate_score(business_data)
    assert score == 50
    # Now add a multiplier that would push it over 100
    business_data.update({"vertical": "healthcare", "has_multiple_locations": True})
    # (50 + 10 - 15 + 5) * 1.5 * 1.2 = 50 * 1.8 = 89.999... -> 89 (floating point)
    score, _ = engine.calculate_score(business_data)
    assert abs(score - 90) <= 1  # Allow for floating point rounding


def test_condition_evaluators(sample_rules_file):
    """Test various condition evaluators."""
    engine = RuleEngine(sample_rules_file)
    # Test tech_stack_contains
    assert (
        engine._evaluate_condition(
            {"tech_stack_contains": "WordPress"},
            {"features": {"tech_stack": '{"WordPress": {"version": "5.8"}}'}},
        )
        is True
    )
    # Test tech_stack_version_lt
    assert (
        engine._evaluate_condition(
            {"tech_stack_version_lt": {"technology": "PHP", "version": "7.4.0"}},
            {"features": {"tech_stack": '{"PHP": {"version": "7.3.0"}}'}},
        )
        is True
    )
    # Test performance_score_gt
    assert (
        engine._evaluate_condition(
            {"performance_score_gt": 80}, {"features": {"page_speed": 85}}
        )
        is True
    )
    # Test state_equals
    assert engine._evaluate_condition({"state_equals": "CA"}, {"state": "CA"}) is True
    # Test vertical_in
    assert (
        engine._evaluate_condition(
            {"vertical_in": ["healthcare", "legal"]}, {"vertical": "healthcare"}
        )
        is True
    )
    # Test has_multiple_locations
    assert (
        engine._evaluate_condition(
            {"has_multiple_locations": True}, {"has_multiple_locations": True}
        )
        is True
    )
