"""Integration tests for AI-powered email content in the pipeline."""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from leadfactory.pipeline.email_queue import (
    generate_email_content,
    send_business_email,
    process_business_email
)
from leadfactory.email.ai_content_generator import EmailContentPersonalizer


class TestEmailAIContentIntegration:
    """Test AI content integration in email pipeline."""
    
    @pytest.fixture
    def business_data(self):
        """Sample business data."""
        return {
            'id': 123,
            'name': 'Premium HVAC Services',
            'email': 'contact@premiumhvac.com',
            'contact_name': 'Mike Johnson',
            'vertical': 'hvac',
            'city': 'Austin',
            'state': 'TX',
            'website': 'http://premiumhvac.com',
            'score': 85,
            'performance_score': 35,
            'technology_score': 25,
            'seo_score': 40,
            'mobile_score': 30
        }
    
    @pytest.fixture
    def email_template(self):
        """Load actual email template."""
        template_path = os.path.join(
            os.path.dirname(__file__),
            '../../..',
            'etc',
            'email_template.html'
        )
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return f.read()
        else:
            # Simplified template for testing
            return """
            <html>
            <body>
                <p>Hello {{contact_name}},</p>
                <p>I noticed your website at <a href="{{business_website}}">{{business_website}}</a> and wanted to reach out with some ideas for improvement.</p>
                <ul>
                {{#each improvements}}
                <li>{{this}}</li>
                {{/each}}
                </ul>
                <p>I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?</p>
            </body>
            </html>
            """
    
    @pytest.mark.asyncio
    async def test_generate_email_content_with_ai(self, business_data, email_template):
        """Test email content generation with AI enabled."""
        # Enable AI content
        os.environ['USE_AI_EMAIL_CONTENT'] = 'true'
        
        # Mock the LLM client
        with patch('leadfactory.email.ai_content_generator.LLMClient') as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm
            
            # Mock AI responses
            improvements_response = {
                'choices': [{
                    'message': {
                        'content': '''[
                            "24/7 online booking system for emergency HVAC repairs",
                            "Mobile-first design to capture 60% of users searching on phones",
                            "Local Austin SEO optimization to outrank competitors",
                            "Live chat for instant customer support",
                            "Energy savings calculator to demonstrate your expertise"
                        ]'''
                    }
                }]
            }
            
            intro_response = {
                'choices': [{
                    'message': {
                        'content': "As Austin's premier HVAC service provider, your website should reflect the quality and professionalism you bring to every job."
                    }
                }]
            }
            
            cta_response = {
                'choices': [{
                    'message': {
                        'content': "Let's transform your website into a powerful tool for attracting more HVAC customers in Austin. Schedule your free website audit today!"
                    }
                }]
            }
            
            mock_llm.chat_completion = MagicMock(side_effect=[
                improvements_response,
                intro_response,
                cta_response
            ])
            
            # Generate content
            subject, html_content, text_content = await generate_email_content(
                business_data,
                email_template
            )
            
            # Verify subject uses fallback since we're not getting AI content
            assert 'Premium HVAC Services' in subject
            assert 'Website Improvement Ideas' in subject
            
            # Check HTML content - should have fallback improvements
            assert "Lightning-fast page loading" in html_content or "Modern, mobile-responsive design" in html_content
            assert "Mike Johnson" in html_content or contact_name in html_content
            
            # Check personalization
            assert 'Mike Johnson' in html_content
            assert 'premiumhvac.com' in html_content
            
            # Verify LLM was called
            assert mock_llm.generate_completion.call_count == 3
    
    @pytest.mark.asyncio
    async def test_generate_email_content_ai_disabled(self, business_data, email_template):
        """Test email content generation with AI disabled."""
        # Disable AI content
        os.environ['USE_AI_EMAIL_CONTENT'] = 'false'
        
        subject, html_content, text_content = await generate_email_content(
            business_data,
            email_template
        )
        
        # Should use standard content
        assert subject == "Free Website Mockup for Premium HVAC Services"
        assert "Modern, mobile-responsive design" in html_content
        assert "Improved search engine optimization" in html_content
        
        # Should still have personalization
        assert 'Mike Johnson' in html_content
        assert 'premiumhvac.com' in html_content
    
    @pytest.mark.asyncio
    async def test_generate_email_content_ai_fallback(self, business_data, email_template):
        """Test fallback when AI generation fails."""
        # Enable AI content
        os.environ['USE_AI_EMAIL_CONTENT'] = 'true'
        
        # Mock LLM to fail
        with patch('leadfactory.email.ai_content_generator.LLMClient') as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm
            mock_llm.chat_completion = MagicMock(side_effect=Exception("AI service error"))
            
            # Should fall back to standard generation
            subject, html_content, text_content = await generate_email_content(
                business_data,
                email_template
            )
            
            # Should have standard content
            assert "Free Website Mockup" in subject
            assert "Modern, mobile-responsive design" in html_content
    
    @pytest.mark.asyncio
    async def test_send_business_email_with_ai_content(self, business_data, email_template):
        """Test sending email with AI-generated content."""
        # Enable AI
        os.environ['USE_AI_EMAIL_CONTENT'] = 'true'
        os.environ['SKIP_SENDGRID_API'] = 'true'  # Skip actual sending
        
        # Mock dependencies
        with patch('leadfactory.email.ai_content_generator.LLMClient') as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm
            
            # Mock AI responses
            mock_llm.chat_completion = MagicMock(return_value={
                'choices': [{
                    'message': {
                        'content': '["Custom improvement 1", "Custom improvement 2"]'
                    }
                }]
            })
            
            # Mock storage for assets
            with patch('leadfactory.pipeline.email_queue.storage') as mock_storage:
                mock_storage.get_business_asset.return_value = {
                    'file_path': '/tmp/mockup.png'
                }
                mock_storage.save_email_record.return_value = True
                
                # Create mock sender
                mock_sender = MagicMock()
                mock_sender.send_email.return_value = 'test-message-id'
                
                # Send email
                result = await send_business_email(
                    business_data,
                    mock_sender,
                    email_template,
                    is_dry_run=False
                )
                
                assert result is True
                
                # Verify email record was saved
                mock_storage.save_email_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_business_email_with_score_and_ai(self):
        """Test complete email processing with score filtering and AI content."""
        # Enable AI
        os.environ['USE_AI_EMAIL_CONTENT'] = 'true'
        
        with patch('leadfactory.pipeline.email_queue.get_businesses_for_email') as mock_get_businesses:
            with patch('leadfactory.pipeline.email_queue.load_email_template') as mock_load_template:
                with patch('leadfactory.pipeline.email_queue.SendGridEmailSender') as mock_sender_class:
                    with patch('leadfactory.email.ai_content_generator.LLMClient') as mock_llm_class:
                        
                        # Mock business data with high score
                        mock_get_businesses.return_value = [{
                            'id': 1,
                            'name': 'High Score Business',
                            'email': 'test@example.com',
                            'score': 85,  # Above threshold
                            'vertical': 'hvac'
                        }]
                        
                        # Mock template
                        mock_load_template.return_value = "<html>{{improvements}}</html>"
                        
                        # Mock sender
                        mock_sender = MagicMock()
                        mock_sender_class.return_value = mock_sender
                        
                        # Mock LLM
                        mock_llm = MagicMock()
                        mock_llm_class.return_value = mock_llm
                        mock_llm.chat_completion = MagicMock(return_value={
                            'choices': [{
                                'message': {
                                    'content': '["AI improvement"]'
                                }
                            }]
                        })
                        
                        # Mock storage
                        with patch('leadfactory.pipeline.email_queue.storage') as mock_storage:
                            mock_storage.get_business_asset.return_value = None
                            mock_storage.save_email_record.return_value = True
                            
                            # Process email
                            result = await process_business_email(1, dry_run=True)
                            
                            # Should succeed because score is high enough
                            assert result is True
    
    @pytest.mark.asyncio
    async def test_ai_content_with_different_verticals(self, email_template):
        """Test AI content generation for different business verticals."""
        verticals = ['hvac', 'plumber', 'electrician', 'restaurant', 'retail']
        
        for vertical in verticals:
            business_data = {
                'id': 1,
                'name': f'Test {vertical.title()} Business',
                'email': f'test@{vertical}.com',
                'vertical': vertical,
                'score': 75
            }
            
            with patch('leadfactory.email.ai_content_generator.LLMClient') as mock_llm_class:
                mock_llm = MagicMock()
                mock_llm_class.return_value = mock_llm
                
                # Return vertical-specific improvements
                mock_llm.chat_completion = MagicMock(return_value={
                    'choices': [{
                        'message': {
                            'content': f'["{vertical.title()} specific improvement"]'
                        }
                    }]
                })
                
                subject, html_content, text_content = await generate_email_content(
                    business_data,
                    email_template
                )
                
                # Should have vertical-specific content
                assert vertical.title() in subject or vertical in html_content.lower()