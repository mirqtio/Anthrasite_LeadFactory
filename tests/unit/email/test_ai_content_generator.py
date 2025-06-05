"""Tests for AI-powered email content generation."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from leadfactory.email.ai_content_generator import (
    AIContentGenerator,
    EmailContentPersonalizer
)


class TestAIContentGenerator:
    """Test AI content generation functionality."""
    
    @pytest.fixture
    def content_generator(self):
        """Create AI content generator instance."""
        return AIContentGenerator()
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response."""
        response = MagicMock()
        response.content = json.dumps([
            "Custom online booking system for HVAC service appointments",
            "Mobile-optimized design to capture customers searching on phones",
            "Local SEO optimization to rank higher for 'HVAC repair near me'",
            "Showcase emergency service availability with prominent contact buttons",
            "Add customer testimonials to build trust with potential clients"
        ])
        return response
    
    @pytest.mark.asyncio
    async def test_generate_email_improvements_with_ai(self, content_generator, mock_llm_response):
        """Test generating improvements with AI."""
        # Mock LLM client
        with patch.object(content_generator.llm_client, 'chat_completion') as mock_generate:
            mock_generate.return_value = {
                'choices': [{
                    'message': {
                        'content': mock_llm_response.content
                    }
                }]
            }
            
            business_data = {
                'name': 'Cool Air HVAC',
                'vertical': 'hvac',
                'website': 'http://coolairhvac.com',
                'score': 75
            }
            
            score_breakdown = {
                'technology_score': 30,  # Low tech score
                'performance_score': 45,  # Low performance
                'seo_score': 40,
                'mobile_score': 35
            }
            
            improvements = await content_generator.generate_email_improvements(
                business_data,
                score_breakdown
            )
            
            # Verify improvements were generated
            assert len(improvements) == 5
            assert "Custom online booking system" in improvements[0]
            assert "HVAC" in improvements[0]
            
            # Verify prompt was constructed properly
            mock_generate.assert_called_once()
            # The prompt is in the messages argument
            call_args = mock_generate.call_args[1]
            messages = call_args['messages']
            prompt = messages[0]['content']
            
            assert 'Cool Air HVAC' in prompt
            assert 'hvac' in prompt
            assert 'outdated technology stack' in prompt
            assert 'slow page loading speeds' in prompt
    
    @pytest.mark.asyncio
    async def test_generate_email_improvements_fallback(self, content_generator):
        """Test fallback when AI fails."""
        # Mock LLM client to raise error
        with patch.object(content_generator.llm_client, 'chat_completion') as mock_generate:
            mock_generate.side_effect = Exception("AI service unavailable")
            
            business_data = {
                'name': 'Test Plumbing',
                'vertical': 'plumber',
                'score': 65
            }
            
            improvements = await content_generator.generate_email_improvements(business_data)
            
            # Should return default improvements
            assert len(improvements) == 5
            assert any('24/7 emergency' in imp for imp in improvements)
            assert any('plumbing' in imp.lower() for imp in improvements)
    
    @pytest.mark.asyncio
    async def test_generate_personalized_intro(self, content_generator):
        """Test personalized intro generation."""
        with patch.object(content_generator.llm_client, 'chat_completion') as mock_generate:
            mock_generate.return_value = {
                'choices': [{
                    'message': {
                        'content': "As a leading HVAC service provider in Austin, Cool Air HVAC deserves a website that matches your professional reputation. I noticed your current site could better showcase your 24/7 emergency services to local customers."
                    }
                }]
            }
            
            business_data = {
                'name': 'Cool Air HVAC',
                'vertical': 'hvac',
                'city': 'Austin',
                'state': 'TX'
            }
            
            intro = await content_generator.generate_personalized_intro(business_data)
            
            assert 'HVAC' in intro
            assert 'Austin' in intro
            assert len(intro) > 50  # Should be substantial
    
    @pytest.mark.asyncio
    async def test_generate_call_to_action(self, content_generator):
        """Test CTA generation."""
        with patch.object(content_generator.llm_client, 'chat_completion') as mock_generate:
            mock_generate.return_value = {
                'choices': [{
                    'message': {
                        'content': "Ready to start attracting more HVAC customers online? Let's discuss how an online booking system can transform your business - schedule your free consultation today!"
                    }
                }]
            }
            
            business_data = {'name': 'Cool Air HVAC', 'vertical': 'hvac'}
            improvements = ["Online booking system for service appointments"]
            
            cta = await content_generator.generate_call_to_action(business_data, improvements)
            
            assert 'free consultation' in cta.lower()
            assert len(cta) > 20
    
    def test_get_default_improvements_by_vertical(self, content_generator):
        """Test default improvements for different verticals."""
        # Test HVAC improvements
        hvac_improvements = content_generator._get_default_improvements('hvac')
        assert len(hvac_improvements) == 5
        assert any('appointment' in imp.lower() for imp in hvac_improvements)
        
        # Test restaurant improvements
        restaurant_improvements = content_generator._get_default_improvements('restaurant')
        assert any('menu' in imp.lower() for imp in restaurant_improvements)
        assert any('reservation' in imp.lower() for imp in restaurant_improvements)
        
        # Test unknown vertical
        general_improvements = content_generator._get_default_improvements('unknown')
        assert len(general_improvements) == 5
        assert any('mobile' in imp.lower() for imp in general_improvements)
    
    def test_get_default_improvements_with_scores(self, content_generator):
        """Test improvements prioritization based on scores."""
        score_breakdown = {
            'performance_score': 20,  # Very low
            'mobile_score': 30  # Low
        }
        
        improvements = content_generator._get_default_improvements(
            'general',
            score_breakdown
        )
        
        # Should prioritize performance and mobile improvements
        assert any('fast' in imp.lower() or 'loading' in imp.lower() for imp in improvements[:2])
        assert any('mobile' in imp.lower() for imp in improvements[:2])


class TestEmailContentPersonalizer:
    """Test email content personalization orchestration."""
    
    @pytest.fixture
    def personalizer(self):
        """Create personalizer instance."""
        return EmailContentPersonalizer()
    
    @pytest.fixture
    def email_template(self):
        """Sample email template."""
        return """
        <p>I noticed your website at <a href="{{business_website}}">{{business_website}}</a> and wanted to reach out with some ideas for improvement.</p>
        <ul>
        {{#each improvements}}
        <li>{{this}}</li>
        {{/each}}
        </ul>
        <p>I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?</p>
        """
    
    @pytest.mark.asyncio
    async def test_personalize_email_content(self, personalizer, email_template):
        """Test full email personalization."""
        business_data = {
            'name': 'Test Business',
            'vertical': 'hvac',
            'email': 'test@example.com',
            'score': 75
        }
        
        # Mock the content generator methods
        with patch.object(personalizer.content_generator, 'generate_email_improvements') as mock_improvements:
            with patch.object(personalizer.content_generator, 'generate_personalized_intro') as mock_intro:
                with patch.object(personalizer.content_generator, 'generate_call_to_action') as mock_cta:
                    
                    mock_improvements.return_value = [
                        "Improvement 1",
                        "Improvement 2",
                        "Improvement 3"
                    ]
                    mock_intro.return_value = "Custom intro for Test Business"
                    mock_cta.return_value = "Custom CTA - schedule now!"
                    
                    subject, html_content, text_content = await personalizer.personalize_email_content(
                        business_data,
                        email_template
                    )
                    
                    # Check subject
                    assert 'Test Business' in subject
                    
                    # Check HTML content
                    assert 'Custom intro for Test Business' in html_content
                    assert 'Improvement 1' in html_content
                    assert 'Improvement 2' in html_content
                    assert 'Custom CTA - schedule now!' in html_content
                    
                    # Check text content
                    assert 'Test Business' in text_content
                    assert 'Improvement 1' in text_content
    
    def test_generate_subject(self, personalizer):
        """Test subject line generation."""
        business_data = {'name': 'Cool Air HVAC'}
        improvements = [
            "Online booking system for instant appointments. No more phone tag!",
            "Mobile optimization for better customer experience"
        ]
        
        subject = personalizer._generate_subject(business_data, improvements)
        
        # Should include business name
        assert 'Cool Air HVAC' in subject
        # Since the improvement is long, it should use the fallback
        assert 'Website Improvement Ideas' in subject
        
        # Test fallback for long improvement
        long_improvements = ["This is a very long improvement that exceeds the character limit for email subject lines and should be truncated"]
        subject2 = personalizer._generate_subject(business_data, long_improvements)
        assert 'Website Improvement Ideas' in subject2
    
    def test_inject_ai_content(self, personalizer, email_template):
        """Test AI content injection into template."""
        intro = "Custom intro text"
        improvements = ["Improvement 1", "Improvement 2"]
        cta = "Custom CTA text"
        business_data = {'name': 'Test Business'}
        
        result = personalizer._inject_ai_content(
            email_template,
            business_data,
            intro,
            improvements,
            cta
        )
        
        assert intro in result
        assert "Improvement 1" in result
        assert "Improvement 2" in result
        assert cta in result
        
        # Check that Handlebars syntax was replaced
        assert "{{#each improvements}}" not in result
        assert "{{/each}}" not in result
    
    def test_generate_text_version(self, personalizer):
        """Test plain text email generation."""
        business_data = {
            'name': 'Test Business',
            'contact_name': 'John Doe'
        }
        intro = "Custom intro"
        improvements = ["Improvement 1", "Improvement 2"]
        cta = "Schedule now!"
        
        text = personalizer._generate_text_version(
            business_data,
            intro,
            improvements,
            cta
        )
        
        assert 'Hello John Doe' in text
        assert 'Custom intro' in text
        assert '1. Improvement 1' in text
        assert '2. Improvement 2' in text
        assert 'Schedule now!' in text
        assert 'calendly.com' in text
    
    @pytest.mark.asyncio
    async def test_basic_personalization_fallback(self, personalizer, email_template):
        """Test fallback when AI fails."""
        business_data = {'name': 'Test Business'}
        
        # Mock content generator to fail
        with patch.object(personalizer.content_generator, 'generate_email_improvements') as mock_improvements:
            mock_improvements.side_effect = Exception("AI failed")
            
            subject, html_content, text_content = await personalizer.personalize_email_content(
                business_data,
                email_template
            )
            
            # Should still return valid content
            assert 'Test Business' in subject
            assert 'Website Improvement Proposal' in subject
            assert len(html_content) > 0
            assert len(text_content) > 0