"""
Integration tests for AI content with email template system.
"""
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, AsyncMock

from leadfactory.email.service import EmailReportService, ReportDeliveryRequest
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.email.ai_content_generator import AIContentGenerator, EmailContentPersonalizer


class TestAIEmailIntegration:
    """Integration tests for AI-powered email system."""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock successful LLM responses."""
        return {
            "improvements": {
                "choices": [{
                    "message": {
                        "content": '["Add online booking for HVAC services", "Mobile-optimized design for field technicians", "Customer portal for service history", "Emergency service request form", "Seasonal maintenance reminders"]'
                    }
                }]
            },
            "intro": {
                "choices": [{
                    "message": {
                        "content": "As a leading HVAC service provider in Denver, your website is often the first point of contact for customers needing urgent heating and cooling repairs."
                    }
                }]
            },
            "cta": {
                "choices": [{
                    "message": {
                        "content": "Let's discuss how adding online booking can help you capture more service calls and grow your HVAC business. Schedule your free consultation today!"
                    }
                }]
            }
        }

    @pytest.mark.asyncio
    async def test_full_ai_email_generation_flow(self, mock_llm_response):
        """Test complete flow from AI content generation to email rendering."""
        # Create AI content generator with mocked LLM
        ai_generator = AIContentGenerator()

        def mock_chat_completion(**kwargs):
            prompt = kwargs['messages'][0]['content']
            if "improvement suggestions" in prompt:
                return mock_llm_response["improvements"]
            elif "introduction paragraph" in prompt:
                return mock_llm_response["intro"]
            elif "call-to-action" in prompt:
                return mock_llm_response["cta"]
            return {"choices": [{"message": {"content": "Default response"}}]}

        with patch.object(ai_generator.llm_client, 'chat_completion', side_effect=mock_chat_completion):
            # Generate AI content
            business_data = {
                "name": "Denver HVAC Pros",
                "vertical": "hvac",
                "website": "https://denverhvac.com",
                "city": "Denver",
                "state": "CO",
                "score": 55
            }

            improvements = await ai_generator.generate_email_improvements(business_data)
            intro = await ai_generator.generate_personalized_intro(business_data)
            cta = await ai_generator.generate_call_to_action(business_data, improvements)

            # Create personalization with AI content
            personalization = EmailPersonalization(
                user_name="Mike Johnson",
                user_email="mike@denverhvac.com",
                report_title="HVAC Website Audit Report",
                report_link="https://anthrasite.com/report/hvac123",
                agency_cta_link="https://anthrasite.com/agency/connect",
                company_name="Denver HVAC Pros",
                website_url="https://denverhvac.com",
                purchase_date=datetime.now(),
                expiry_date=datetime.now() + timedelta(days=30),
                ai_intro=intro,
                ai_improvements=improvements,
                ai_cta=cta,
                unsubscribe_link="https://anthrasite.com/unsubscribe/hvac123",
                business_data=business_data
            )

            # Render email template
            template_engine = EmailTemplateEngine()
            email_template = template_engine.create_report_delivery_email(personalization)

            # Verify AI content is in the rendered email
            assert "Denver HVAC Pros" in email_template.html_content
            assert "leading HVAC service provider in Denver" in email_template.html_content
            assert "Add online booking for HVAC services" in email_template.html_content
            assert "Schedule your free consultation today!" in email_template.html_content

            # Verify CAN-SPAM compliance
            assert "123 Main Street" in email_template.html_content
            assert "Unsubscribe" in email_template.html_content
            assert "You received this email because" in email_template.html_content

    @pytest.mark.asyncio
    async def test_email_service_with_ai_content_end_to_end(self, mock_llm_response):
        """Test email service integrating AI content generation."""
        with patch("leadfactory.email.service.EmailDeliveryService") as mock_delivery, \
             patch("leadfactory.email.service.SecureLinkGenerator") as mock_link_gen, \
             patch("leadfactory.email.service.EmailWorkflowEngine") as mock_workflow, \
             patch("leadfactory.email.service.EmailABTest") as mock_ab_test, \
             patch("leadfactory.email.service.get_storage") as mock_storage:

            # Set up email service
            service = EmailReportService()

            # Mock storage to return business data
            mock_storage_instance = Mock()
            mock_storage.return_value = mock_storage_instance
            mock_storage_instance.get_business.return_value = {
                "name": "Test HVAC Company",
                "vertical": "hvac",
                "website": "https://testhvac.com",
                "city": "Austin",
                "state": "TX",
                "score": 60
            }
            # Mock get_business_asset to return None (no screenshot)
            mock_storage_instance.get_business_asset.return_value = None

            # Mock AI content generation
            def mock_chat_completion(**kwargs):
                prompt = kwargs['messages'][0]['content']
                if "improvement suggestions" in prompt:
                    return mock_llm_response["improvements"]
                elif "introduction paragraph" in prompt:
                    return mock_llm_response["intro"]
                elif "call-to-action" in prompt:
                    return mock_llm_response["cta"]
                return {"choices": [{"message": {"content": "Default"}}]}

            with patch("leadfactory.email.ai_content_generator.LLMClient") as mock_llm_class:
                mock_llm = Mock()
                mock_llm.chat_completion = Mock(side_effect=mock_chat_completion)
                mock_llm_class.return_value = mock_llm

                # Re-initialize template engine to use mocked LLM
                from leadfactory.email.templates import EmailTemplateEngine
                service.template_engine = EmailTemplateEngine()

                # Mock other dependencies with actual Mock objects and proper return values
                service.link_generator.generate_secure_link = Mock(return_value="https://example.com/report")
                service.link_generator.generate_download_link = Mock(return_value="https://example.com/download")
                service.link_generator.create_tracking_link = Mock(return_value="https://example.com/cta")

                # Mock A/B test to return template with placeholders
                service.ab_test.generate_email_with_variant.return_value = (
                    "variant1",
                    {
                        "subject": "Your HVAC Website Audit Report",
                        "html_content": """<html>
                        <body>
                            <p>{{ user.ai_intro }}</p>
                            <ul>
                            {% for improvement in user.ai_improvements %}
                                <li>{{ improvement }}</li>
                            {% endfor %}
                            </ul>
                            <p>{{ user.ai_cta }}</p>
                            <div class="footer">
                                <p>123 Main Street<br>San Francisco, CA 94105</p>
                                <p><a href="{{ user.unsubscribe_link }}">Unsubscribe</a></p>
                            </div>
                        </body>
                        </html>""",
                        "template_name": "report_delivery"
                    }
                )

                service.delivery_service.send_email = AsyncMock(return_value="email123")
                service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

                # Create request with AI content enabled
                request = ReportDeliveryRequest(
                    user_id="user789",
                    user_email="test@testhvac.com",
                    user_name="Test User",
                    report_id="report789",
                    report_title="HVAC Website Audit Report",
                    purchase_id="purchase789",
                    company_name="Test HVAC Company",
                    website_url="https://testhvac.com",
                    business_id=789,
                    include_ai_content=True
                )

                # Deliver report
                result = await service.deliver_report(request)

                assert result.success is True
                assert result.email_id == "email123"

                # Verify send_email was called
                service.delivery_service.send_email.assert_called_once()

                # Get the personalization object that was passed
                call_args = service.delivery_service.send_email.call_args
                template = call_args[0][0]
                personalization = call_args[0][1]

                # Verify AI content was generated
                assert personalization.ai_intro is not None
                assert len(personalization.ai_improvements) > 0
                assert personalization.ai_cta is not None

    @pytest.mark.asyncio
    async def test_ai_content_with_different_verticals(self):
        """Test AI content generation for different business verticals."""
        ai_generator = AIContentGenerator()

        verticals = [
            ("plumber", ["24/7 emergency", "plumbing"]),
            ("electrician", ["electrical", "safety"]),
            ("restaurant", ["menu", "reservation"]),
            ("retail", ["product", "store"])
        ]

        # Mock LLM to fail so we get default content
        with patch.object(ai_generator.llm_client, 'chat_completion', side_effect=Exception("Test failure")):
            for vertical, keywords in verticals:
                business_data = {
                    "name": f"Test {vertical.title()}",
                    "vertical": vertical,
                    "website": f"https://test{vertical}.com",
                    "score": 50
                }

                improvements = await ai_generator.generate_email_improvements(business_data)

                assert len(improvements) == 5
                # Check vertical-specific content
                assert any(any(keyword in imp.lower() for keyword in keywords) for imp in improvements)

    @pytest.mark.asyncio
    async def test_email_personalization_with_score_based_content(self):
        """Test AI content adjusts based on score breakdown."""
        ai_generator = AIContentGenerator()

        business_data = {
            "name": "Low Score Business",
            "vertical": "contractor",
            "website": "https://lowscore.com",
            "score": 25
        }

        score_breakdown = {
            "performance_score": 20,  # Very low
            "mobile_score": 15,      # Very low
            "seo_score": 60,         # OK
            "technology_score": 55   # OK
        }

        # Mock LLM to fail so we get score-based defaults
        with patch.object(ai_generator.llm_client, 'chat_completion', side_effect=Exception("Test")):
            improvements = await ai_generator.generate_email_improvements(
                business_data,
                score_breakdown=score_breakdown
            )

            # Should prioritize performance and mobile improvements
            assert any("fast" in imp.lower() or "loading" in imp.lower() for imp in improvements[:2])
            assert any("mobile" in imp.lower() for imp in improvements[:2])

    def test_can_spam_compliance_with_ai_content(self):
        """Test CAN-SPAM compliance is maintained with AI-generated content."""
        template_engine = EmailTemplateEngine()

        # Create personalization with AI content
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            ai_intro="This is AI generated intro text that might be very long and contain various content",
            ai_improvements=["Improvement 1" * 50, "Improvement 2" * 50],  # Long content
            ai_cta="This is a very long AI generated call to action " * 10,
            unsubscribe_link="https://example.com/unsubscribe/test123"
        )

        template = template_engine.create_report_delivery_email(personalization)

        # Even with long AI content, CAN-SPAM elements must be present
        assert "123 Main Street" in template.html_content
        assert "San Francisco, CA 94105" in template.html_content
        assert "Unsubscribe" in template.html_content
        assert personalization.unsubscribe_link in template.html_content
        assert "You received this email because" in template.html_content
        assert ("© " in template.html_content or "&copy;" in template.html_content)
        assert "Anthrasite. All rights reserved." in template.html_content
