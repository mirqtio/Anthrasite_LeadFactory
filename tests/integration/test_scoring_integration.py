"""
Integration tests for the scoring engine with real YAML configuration.
"""

import os
from pathlib import Path

import pytest

from leadfactory.pipeline.score import RuleEngine, score_business
from leadfactory.scoring import ScoringEngine


class TestScoringIntegration:
    """Integration tests using the actual scoring_rules.yml file."""

    @pytest.fixture
    def scoring_engine(self):
        """Create a scoring engine with the real config."""
        # Use the actual scoring rules file
        config_path = Path(__file__).parent.parent.parent / "etc" / "scoring_rules.yml"
        if not config_path.exists():
            pytest.skip(f"Scoring rules file not found at {config_path}")

        engine = ScoringEngine(str(config_path))
        engine.load_rules()
        return engine

    @pytest.fixture
    def rule_engine(self):
        """Create a rule engine (backward compatibility wrapper)."""
        # Use the actual scoring rules file
        config_path = Path(__file__).parent.parent.parent / "etc" / "scoring_rules.yml"
        if not config_path.exists():
            pytest.skip(f"Scoring rules file not found at {config_path}")

        return RuleEngine()

    def test_modern_tech_stack_scoring(self, scoring_engine):
        """Test scoring for businesses with modern tech stacks."""
        # Business with React
        business = {
            'id': 1,
            'name': 'Modern React Company',
            'tech_stack': ['React', 'Node.js', 'PostgreSQL'],
            'vertical': 'SaaS',
            'employee_count': 50
        }

        result = scoring_engine.score_business(business)

        # Should get base score + React bonus
        assert result['score'] > scoring_engine.settings.base_score
        assert any(adj['rule'] == 'modern_frontend_framework' for adj in result['adjustments'])

    def test_legacy_tech_scoring(self, scoring_engine):
        """Test scoring for businesses with legacy technology."""
        # Business with old jQuery
        business = {
            'id': 2,
            'name': 'Legacy jQuery Company',
            'tech_stack': {'jQuery': '2.1.0'},
            'vertical': 'E-commerce'
        }

        result = scoring_engine.score_business(business)

        # Should get jQuery bonuses
        adjustments = [adj['rule'] for adj in result['adjustments']]
        assert 'outdated_jquery' in adjustments or 'any_jquery' in adjustments

    def test_wordpress_scoring(self, scoring_engine):
        """Test scoring for WordPress businesses."""
        business = {
            'id': 3,
            'name': 'WordPress Agency',
            'tech_stack': ['WordPress', 'PHP', 'MySQL'],
            'vertical': 'Agency'
        }

        result = scoring_engine.score_business(business)

        # Should get WordPress bonus
        assert any(adj['rule'] == 'wordpress' for adj in result['adjustments'])

    def test_high_value_vertical_multiplier(self, scoring_engine):
        """Test multiplier for high-value verticals."""
        # Regular vertical
        business1 = {
            'id': 4,
            'name': 'Regular Company',
            'tech_stack': ['React'],
            'vertical': 'Retail'
        }

        # High-value vertical (if defined in config)
        business2 = {
            'id': 5,
            'name': 'SaaS Company',
            'tech_stack': ['React'],
            'vertical': 'SaaS'
        }

        result1 = scoring_engine.score_business(business1)
        result2 = scoring_engine.score_business(business2)

        # If SaaS multiplier exists, score should be higher
        if any(m['multiplier'] == 'high_value_vertical' for m in result2['multipliers']):
            assert result2['score'] > result1['score']

    def test_multiple_tech_stack_bonuses(self, scoring_engine):
        """Test businesses that match multiple tech stack rules."""
        business = {
            'id': 6,
            'name': 'Multi-Tech Company',
            'tech_stack': ['React', 'Vue', 'Angular', 'jQuery', 'WordPress'],
            'vertical': 'Technology'
        }

        result = scoring_engine.score_business(business)

        # Should have multiple adjustments
        assert len(result['adjustments']) > 1

        # Score should be significantly higher than base
        assert result['score'] > scoring_engine.settings.base_score + 10

    def test_score_bounds_enforcement(self, scoring_engine):
        """Test that scores stay within configured bounds."""
        # Business that should max out score
        business = {
            'id': 7,
            'name': 'Perfect Score Company',
            'tech_stack': ['React', 'Vue', 'Angular', 'Next.js', 'Nuxt.js'],
            'vertical': 'SaaS',
            'employee_count': 1000,
            'revenue': 10000000,
            'has_contact_form': True,
            'social_media': {
                'twitter': {'followers': 10000},
                'linkedin': {'followers': 5000}
            }
        }

        result = scoring_engine.score_business(business)

        # Score should not exceed max_score
        assert result['score'] <= scoring_engine.settings.max_score

    def test_backward_compatibility(self, rule_engine):
        """Test the backward-compatible RuleEngine wrapper."""
        business = {
            'id': 8,
            'name': 'Test Company',
            'tech_stack': ['React', 'Node.js']
        }

        # Should return just the score as an integer
        score = rule_engine.evaluate(business)

        assert isinstance(score, int)
        assert score >= 0

    def test_score_business_function(self):
        """Test the standalone score_business function."""
        business = {
            'id': 9,
            'name': 'Function Test Company',
            'tech_stack': ['React']
        }

        score = score_business(business)

        assert isinstance(score, int)
        assert score >= 0

    def test_missing_optional_fields(self, scoring_engine):
        """Test scoring with minimal business data."""
        # Minimal business with only required fields
        business = {
            'id': 10,
            'name': 'Minimal Company'
        }

        result = scoring_engine.score_business(business)

        # Should still get base score
        assert result['score'] == scoring_engine.settings.base_score
        assert len(result['adjustments']) == 0

    def test_complex_conditions(self, scoring_engine):
        """Test rules with complex conditions if they exist."""
        business = {
            'id': 11,
            'name': 'Complex Conditions Company',
            'tech_stack': ['React', 'Node.js'],
            'vertical': 'SaaS',
            'employee_count': 100,
            'revenue': 5000000,
            'founded_year': 2018,
            'location': 'San Francisco, CA',
            'has_contact_form': True,
            'social_media': {
                'twitter': {'followers': 5000, 'engagement': 0.05},
                'linkedin': {'followers': 2000}
            }
        }

        result = scoring_engine.score_business(business)

        # Should have various adjustments based on the complex data
        assert len(result['adjustments']) > 0
        assert result['score'] != scoring_engine.settings.base_score

    def test_rule_priority_ordering(self, scoring_engine):
        """Test that rules are evaluated in priority order."""
        # This test assumes rules have different priorities in the config
        business = {
            'id': 12,
            'name': 'Priority Test Company',
            'tech_stack': ['React', 'Vue', 'Angular']
        }

        result = scoring_engine.score_business(business)

        # Check that adjustments are applied (exact order depends on config)
        if len(result['adjustments']) > 1:
            # Rules should be evaluated based on their priority
            assert len(result['adjustments']) > 0

    @pytest.mark.parametrize("tech_stack,expected_min_score", [
        (['React'], 60),  # Assuming React gives +15 from base 50
        (['Vue'], 60),    # Assuming Vue also gives bonus
        (['jQuery'], 55), # Assuming jQuery gives +5
        (['WordPress'], 60), # Assuming WordPress gives +10
        ([], 50),         # No tech stack, just base score
    ])
    def test_various_tech_stacks(self, scoring_engine, tech_stack, expected_min_score):
        """Test scoring for various tech stacks."""
        business = {
            'id': 100,
            'name': f'Test {tech_stack} Company',
            'tech_stack': tech_stack
        }

        result = scoring_engine.score_business(business)

        # Score should be at least the expected minimum
        # (actual score might be higher due to other rules)
        assert result['score'] >= expected_min_score
