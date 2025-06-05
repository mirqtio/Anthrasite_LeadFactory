"""
Unit tests for AI content integration with email templates.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from leadfactory.email.ai_content_generator import (
    AIContentGenerator,
    EmailContentPersonalizer
)
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.email.service import EmailReportService, ReportDeliveryRequest


class TestAIContentIntegration:
    """Test cases for AI content integration with email templates."""

    @pytest.fixture
    def ai_generator(self):
        """Create an AI content generator instance."""
        with patch("leadfactory.email.ai_content_generator.LLMClient"):
            return AIContentGenerator()

    @pytest.fixture
    def email_personalizer(self):
        """Create an email content personalizer instance."""
        return EmailContentPersonalizer()

    @pytest.fixture
    def sample_business_data(self):
        """Sample business data for testing."""
        return {
            "id": 123,
            "name": "Joe's Plumbing",
            "vertical": "plumber",
            "website": "https://joesplumbing.com",
            "city": "San Francisco",
            "state": "CA",
            "score": 45
        }

    @pytest.fixture
    def sample_score_data(self):
        """Sample score breakdown data."""
        return {
            "overall_score": 45,
            "technology_score": 30,
            "performance_score": 40,
            "seo_score": 35,
            "mobile_score": 25
        }

    @pytest.mark.asyncio
    async def test_generate_email_improvements(self, ai_generator, sample_business_data, sample_score_data):
        """Test AI improvement generation."""
        # Mock LLM response
        mock_response = {
            "choices": [{
                "message": {
                    "content": '["24/7 emergency contact form for urgent plumbing issues", "Online booking system for routine maintenance", "Mobile-optimized design for on-the-go customers", "Customer testimonials to build trust", "Service area map showing coverage zones"]'
                }
            }]
        }

        with patch.object(ai_generator.llm_client, 'chat_completion', return_value=mock_response):
            improvements = await ai_generator.generate_email_improvements(
                sample_business_data,
                score_breakdown=sample_score_data
            )

            assert len(improvements) == 5
            assert "24/7 emergency contact form" in improvements[0]
            assert all(isinstance(imp, str) for imp in improvements)

    @pytest.mark.asyncio
    async def test_generate_email_improvements_fallback(self, ai_generator, sample_business_data):
        """Test fallback when AI fails."""
        # Mock LLM failure
        with patch.object(ai_generator.llm_client, 'chat_completion', side_effect=Exception("API Error")):
            improvements = await ai_generator.generate_email_improvements(sample_business_data)

            assert len(improvements) == 5
            # Should return plumber-specific defaults
            assert any("24/7 emergency" in imp for imp in improvements)

    @pytest.mark.asyncio
    async def test_generate_personalized_intro(self, ai_generator, sample_business_data):
        """Test personalized intro generation."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "As a trusted plumbing service in San Francisco, your online presence is crucial for attracting new customers who need urgent repairs."
                }
            }]
        }

        with patch.object(ai_generator.llm_client, 'chat_completion', return_value=mock_response):
            intro = await ai_generator.generate_personalized_intro(sample_business_data)

            assert "San Francisco" in intro
            assert "plumbing" in intro.lower()
            assert len(intro) > 20

    @pytest.mark.asyncio
    async def test_generate_call_to_action(self, ai_generator, sample_business_data):
        """Test CTA generation."""
        improvements = ["24/7 emergency contact form"]
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Let's add that emergency contact form to help you capture more urgent service calls. Schedule your free consultation today!"
                }
            }]
        }

        with patch.object(ai_generator.llm_client, 'chat_completion', return_value=mock_response):
            cta = await ai_generator.generate_call_to_action(sample_business_data, improvements)

            assert "free consultation" in cta.lower()
            assert len(cta) > 10


class TestEmailTemplateWithAIContent:
    """Test email template rendering with AI content."""

    @pytest.fixture
    def template_engine(self):
        """Create template engine instance."""
        return EmailTemplateEngine()

    @pytest.fixture
    def sample_personalization_with_ai(self):
        """Create sample personalization with AI content."""
        return EmailPersonalization(
            user_name="John Doe",
            user_email="john@example.com",
            report_title="Website Audit Report",
            report_link="https://example.com/report/123",
            agency_cta_link="https://example.com/agency",
            company_name="Joe's Plumbing",
            website_url="https://joesplumbing.com",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            ai_intro="As a trusted plumbing service in San Francisco, your online presence is crucial.",
            ai_improvements=[
                "24/7 emergency contact form for urgent plumbing issues",
                "Online booking system for routine maintenance",
                "Mobile-optimized design for on-the-go customers"
            ],
            ai_cta="Let's discuss how these improvements can help grow your plumbing business. Schedule your free consultation!",
            unsubscribe_link="https://example.com/unsubscribe/abc123"
        )

    def test_render_email_with_ai_content(self, template_engine, sample_personalization_with_ai):
        """Test email rendering with AI content."""
        template = template_engine.create_report_delivery_email(sample_personalization_with_ai)

        assert template.name == "report_delivery"
        # Company name should be in the content (check both normal and HTML-encoded versions)
        assert ("Joe's Plumbing" in template.html_content or
                "Joe&#39;s Plumbing" in template.html_content or
                "Your Business" in template.html_content)

        # Check AI content is included
        assert sample_personalization_with_ai.ai_intro in template.html_content
        assert "24/7 emergency contact form" in template.html_content
        # Check for CTA with potential HTML encoding
        assert ("Let's discuss how these improvements can help grow your plumbing business" in template.html_content or
                "Let&#39;s discuss how these improvements can help grow your plumbing business" in template.html_content)

    def test_render_email_with_can_spam_footer(self, template_engine, sample_personalization_with_ai):
        """Test CAN-SPAM compliance footer is always included."""
        template = template_engine.create_report_delivery_email(sample_personalization_with_ai)

        # Check CAN-SPAM required elements
        assert "123 Main Street" in template.html_content  # Physical address
        assert "San Francisco, CA 94105" in template.html_content
        assert "Unsubscribe" in template.html_content
        assert sample_personalization_with_ai.unsubscribe_link in template.html_content
        assert "You received this email because" in template.html_content
        assert "Anthrasite. All rights reserved." in template.html_content

    def test_render_email_without_ai_content(self, template_engine):
        """Test email rendering falls back gracefully without AI content."""
        personalization = EmailPersonalization(
            user_name="Jane Doe",
            user_email="jane@example.com",
            report_title="Website Audit Report",
            report_link="https://example.com/report/456",
            agency_cta_link="https://example.com/agency",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            unsubscribe_link="https://example.com/unsubscribe/def456"
        )

        template = template_engine.create_report_delivery_email(personalization)

        # Should use default content
        assert "Great news!" in template.html_content
        assert "comprehensive audit report" in template.html_content

        # CAN-SPAM footer should still be present
        assert "123 Main Street" in template.html_content
        assert "Unsubscribe" in template.html_content


class TestEmailServiceAIIntegration:
    """Test email service with AI content integration."""

    @pytest.fixture
    def email_service(self):
        """Create email service instance."""
        with patch("leadfactory.email.service.EmailDeliveryService"), \
             patch("leadfactory.email.service.SecureLinkGenerator"), \
             patch("leadfactory.email.service.EmailTemplateEngine") as mock_template_engine, \
             patch("leadfactory.email.service.EmailWorkflowEngine"), \
             patch("leadfactory.email.service.EmailABTest"):

            service = EmailReportService()

            # Mock template engine's generate_ai_content
            async def mock_generate_ai_content(personalization):
                personalization.ai_intro = "AI generated intro"
                personalization.ai_improvements = ["Improvement 1", "Improvement 2"]
                personalization.ai_cta = "AI generated CTA"
                return personalization

            # Create a Mock object that wraps the async function and tracks calls
            mock_wrapper = Mock(side_effect=mock_generate_ai_content)
            service.template_engine.generate_ai_content = mock_wrapper
            return service

    @pytest.fixture
    def sample_request_with_ai(self):
        """Create sample request with AI content enabled."""
        return ReportDeliveryRequest(
            user_id="user123",
            user_email="test@example.com",
            user_name="Test User",
            report_id="report456",
            report_title="Website Audit Report",
            purchase_id="purchase789",
            company_name="Test Company",
            website_url="https://example.com",
            business_id=123,
            include_ai_content=True,  # Enable AI content
            metadata={
                "business_data": {
                    "name": "Test Company",
                    "vertical": "hvac",
                    "score": 50
                }
            }
        )

    @pytest.mark.asyncio
    async def test_deliver_report_with_ai_content(self, email_service, sample_request_with_ai):
        """Test report delivery includes AI content generation."""
        # Mock dependencies with actual string values
        email_service.link_generator.generate_secure_link = Mock(return_value="https://example.com/report")
        email_service.link_generator.generate_download_link = Mock(return_value="https://example.com/download")
        email_service.link_generator.create_tracking_link = Mock(return_value="https://example.com/cta")

        email_service.ab_test.generate_email_with_variant.return_value = (
            "variant1",
            {
                "subject": "Your Report is Ready",
                "html_content": "<html>AI content: {{ user.ai_intro }}</html>",
                "template_name": "report_delivery"
            }
        )

        email_service.delivery_service.send_email = AsyncMock(return_value="email123")
        email_service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

        # Call deliver_report
        result = await email_service.deliver_report(sample_request_with_ai)

        assert result.success is True

        # Verify AI content generation was called
        assert email_service.template_engine.generate_ai_content.called
        assert email_service.template_engine.generate_ai_content.call_count == 1

    @pytest.mark.asyncio
    async def test_deliver_report_ai_content_failure(self, email_service, sample_request_with_ai):
        """Test report delivery continues when AI content generation fails."""
        # Make AI content generation fail
        async def failing_ai_content(personalization):
            raise Exception("AI service unavailable")

        email_service.template_engine.generate_ai_content = failing_ai_content

        # Mock other dependencies with actual string values
        email_service.link_generator.generate_secure_link = Mock(return_value="https://example.com/report")
        email_service.link_generator.generate_download_link = Mock(return_value="https://example.com/download")
        email_service.link_generator.create_tracking_link = Mock(return_value="https://example.com/cta")

        email_service.ab_test.generate_email_with_variant.return_value = (
            "variant1",
            {
                "subject": "Your Report is Ready",
                "html_content": "<html>Default content</html>",
                "template_name": "report_delivery"
            }
        )

        email_service.delivery_service.send_email = AsyncMock(return_value="email123")
        email_service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

        # Should still succeed without AI content
        result = await email_service.deliver_report(sample_request_with_ai)

        assert result.success is True
        assert result.email_id == "email123"


class TestCANSPAMCompliance:
    """Test CAN-SPAM compliance in all email scenarios."""

    @pytest.fixture
    def template_engine(self):
        """Create template engine instance."""
        return EmailTemplateEngine()

    def test_all_templates_have_physical_address(self, template_engine):
        """Test all email templates include physical address."""
        # Test report delivery template
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            unsubscribe_link="https://example.com/unsub"
        )

        delivery_template = template_engine.create_report_delivery_email(personalization)
        assert "123 Main Street" in delivery_template.html_content
        assert "San Francisco, CA 94105" in delivery_template.html_content
        assert "United States" in delivery_template.html_content

    def test_unsubscribe_link_always_present(self, template_engine):
        """Test unsubscribe link is always included."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            unsubscribe_link="https://example.com/unsubscribe/12345"
        )

        template = template_engine.create_report_delivery_email(personalization)

        assert "Unsubscribe" in template.html_content
        assert personalization.unsubscribe_link in template.html_content
        assert "Update Preferences" in template.html_content

    def test_email_reason_explanation(self, template_engine):
        """Test email includes explanation of why recipient received it."""
        personalization = EmailPersonalization(
            user_name="Test User",
            user_email="test@example.com",
            report_title="Test Report",
            report_link="https://example.com/report",
            agency_cta_link="https://example.com/cta",
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=30),
            unsubscribe_link="https://example.com/unsub"
        )

        template = template_engine.create_report_delivery_email(personalization)

        assert "You received this email because" in template.html_content
        assert "purchased a website audit report" in template.html_content
