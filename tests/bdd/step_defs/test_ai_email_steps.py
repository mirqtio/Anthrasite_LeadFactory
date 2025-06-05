"""
Step definitions for AI email integration BDD tests.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pytest_bdd import scenarios, given, when, then, parsers

from leadfactory.email.service import EmailReportService, ReportDeliveryRequest
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.email.ai_content_generator import AIContentGenerator


# Load scenarios from feature file
scenarios('../features/ai_email_integration.feature')


@pytest.fixture
def ai_email_context():
    """Context for AI email BDD tests."""
    return {
        "email_service": None,
        "ai_generator": None,
        "business": None,
        "email_result": None,
        "email_content": None,
        "ai_content": None,
        "ai_available": True,
        "businesses": [],
        "generated_emails": []
    }


@given("the email system is configured with AI content generation")
def configure_email_system_with_ai(ai_email_context):
    """Configure email system with AI content generation."""
    with patch("leadfactory.email.service.EmailDeliveryService"), \
         patch("leadfactory.email.service.SecureLinkGenerator"), \
         patch("leadfactory.email.service.EmailTemplateEngine") as mock_template_engine, \
         patch("leadfactory.email.service.EmailWorkflowEngine"), \
         patch("leadfactory.email.service.EmailABTest"), \
         patch("leadfactory.email.ai_content_generator.LLMClient") as mock_llm:

        service = EmailReportService()
        ai_generator = AIContentGenerator()

        # Mock LLM responses
        def mock_chat_completion(**kwargs):
            if not ai_email_context["ai_available"]:
                raise Exception("AI service unavailable")

            prompt = kwargs['messages'][0]['content']
            if "improvement suggestions" in prompt:
                return {
                    "choices": [{
                        "message": {
                            "content": '["Online booking system", "Mobile-optimized design", "Customer reviews section", "Service area map", "Emergency contact form"]'
                        }
                    }]
                }
            elif "introduction paragraph" in prompt:
                return {
                    "choices": [{
                        "message": {
                            "content": "Your business deserves a website that works as hard as you do."
                        }
                    }]
                }
            elif "call-to-action" in prompt:
                return {
                    "choices": [{
                        "message": {
                            "content": "Schedule your free consultation today!"
                        }
                    }]
                }

        mock_llm.return_value.chat_completion = Mock(side_effect=mock_chat_completion)

        ai_email_context["email_service"] = service
        ai_email_context["ai_generator"] = ai_generator


@given("I have a business with website audit data")
def setup_business_with_audit_data(ai_email_context):
    """Set up a business with audit data."""
    ai_email_context["business"] = {
        "id": 123,
        "name": "Test Business",
        "vertical": "general",
        "website": "https://testbusiness.com",
        "city": "San Francisco",
        "state": "CA",
        "score": 50,
        "score_breakdown": {
            "performance_score": 45,
            "mobile_score": 50,
            "seo_score": 55,
            "technology_score": 50
        }
    }


@given(parsers.parse('the business is "{business_name}" in the "{vertical}" vertical'))
def setup_specific_business(ai_email_context, business_name, vertical):
    """Set up a specific business."""
    ai_email_context["business"]["name"] = business_name
    ai_email_context["business"]["vertical"] = vertical


@given(parsers.parse('the business has a low website score of {score:d}'))
def set_business_score(ai_email_context, score):
    """Set business website score."""
    ai_email_context["business"]["score"] = score


@given("I have an email template with placeholders for AI content")
def setup_email_template(ai_email_context):
    """Set up email template with AI placeholders."""
    ai_email_context["template"] = """
    <html>
    <body>
        <p>{{ user.ai_intro|default('Default introduction') }}</p>
        <ul>
        {% for improvement in user.ai_improvements|default(['Default improvement']) %}
            <li>{{ improvement }}</li>
        {% endfor %}
        </ul>
        <p>{{ user.ai_cta|default('Default CTA') }}</p>
        <div class="footer">
            <p>123 Main Street<br>San Francisco, CA 94105</p>
            <p><a href="{{ user.unsubscribe_link }}">Unsubscribe</a></p>
        </div>
    </body>
    </html>
    """


@given("the AI service is unavailable")
def make_ai_unavailable(ai_email_context):
    """Make AI service unavailable."""
    ai_email_context["ai_available"] = False


@given("I have businesses in different verticals:")
def setup_multiple_businesses(ai_email_context, datatable):
    """Set up multiple businesses from table."""
    businesses = []
    headers = datatable[0]
    for row in datatable[1:]:
        business = dict(zip(headers, row))
        business["id"] = len(businesses) + 1
        business["website"] = f"https://{business['business_name'].lower().replace(' ', '')}.com"
        business["score"] = 50
        businesses.append(business)
    ai_email_context["businesses"] = businesses


@given("the business has the following scores:")
def set_business_scores(ai_email_context, datatable):
    """Set detailed business scores."""
    scores = {}
    headers = datatable[0]
    for row in datatable[1:]:
        score_data = dict(zip(headers, row))
        metric = score_data["metric"]
        score = int(score_data["score"])
        scores[f"{metric}_score"] = score
    ai_email_context["business"]["score_breakdown"] = scores


@given("the AI generates very long content:")
def setup_long_ai_content(ai_email_context, datatable):
    """Set up long AI content."""
    content_lengths = {}
    headers = datatable[0]
    for row in datatable[1:]:
        content_data = dict(zip(headers, row))
        content_type = content_data["content_type"]
        length = int(content_data["length"])
        content_lengths[content_type] = length

    ai_email_context["long_content"] = content_lengths


@given(parsers.parse('the business "{business_name}" is located in "{location}"'))
def set_business_location(ai_email_context, business_name, location):
    """Set business location."""
    city, state = location.split(", ")
    ai_email_context["business"]["name"] = business_name
    ai_email_context["business"]["city"] = city
    ai_email_context["business"]["state"] = state


@when("I request an email with AI-generated content")
async def request_email_with_ai(ai_email_context):
    """Request email with AI content."""
    service = ai_email_context["email_service"]
    business = ai_email_context["business"]

    # Mock template engine to use real AI generation
    from leadfactory.email.templates import EmailTemplateEngine
    service.template_engine = EmailTemplateEngine()

    # Mock other dependencies
    service.link_generator.generate_secure_link.return_value = "https://example.com/report"
    service.link_generator.create_tracking_link.return_value = "https://example.com/cta"

    service.ab_test.generate_email_with_variant.side_effect = lambda **kwargs: (
        "variant1",
        {
            "subject": f"Website Audit for {kwargs['personalization'].company_name}",
            "html_content": service.template_engine.create_report_delivery_email(kwargs['personalization']).html_content,
            "template_name": "report_delivery"
        }
    )

    service.delivery_service.send_email = AsyncMock(return_value="email123")
    service.workflow_engine.start_workflow = AsyncMock(return_value="workflow456")

    request = ReportDeliveryRequest(
        user_id="user123",
        user_email="test@example.com",
        user_name="Test User",
        report_id="report123",
        report_title="Website Audit Report",
        purchase_id="purchase123",
        company_name=business["name"],
        website_url=business["website"],
        business_id=business["id"],
        include_ai_content=True,
        metadata={"business_data": business}
    )

    import asyncio
    result = asyncio.run(service.deliver_report(request))
    ai_email_context["email_result"] = result

    # Capture the generated email content
    if service.ab_test.generate_email_with_variant.called:
        call_args = service.ab_test.generate_email_with_variant.call_args
        ai_email_context["email_content"] = call_args[1]['personalization']


@when("AI content is generated for the business")
async def generate_ai_content(ai_email_context):
    """Generate AI content for business."""
    ai_generator = ai_email_context["ai_generator"]
    business = ai_email_context["business"]

    import asyncio
    ai_intro = asyncio.run(ai_generator.generate_personalized_intro(business))
    ai_improvements = asyncio.run(ai_generator.generate_email_improvements(
        business,
        score_breakdown=business.get("score_breakdown")
    ))
    ai_cta = asyncio.run(ai_generator.generate_call_to_action(business, ai_improvements))

    ai_email_context["ai_content"] = {
        "intro": ai_intro,
        "improvements": ai_improvements,
        "cta": ai_cta
    }


@when("I generate AI content for each business")
async def generate_ai_for_multiple_businesses(ai_email_context):
    """Generate AI content for multiple businesses."""
    ai_generator = ai_email_context["ai_generator"]

    for business in ai_email_context["businesses"]:
        import asyncio
        improvements = asyncio.run(ai_generator.generate_email_improvements(business))
        ai_email_context["generated_emails"].append({
            "business": business,
            "improvements": improvements
        })


@when("AI content is generated")
async def generate_ai_content_with_scores(ai_email_context):
    """Generate AI content considering scores."""
    await generate_ai_content(ai_email_context)


@when("the email is rendered")
def render_email_with_long_content(ai_email_context):
    """Render email with long AI content."""
    lengths = ai_email_context.get("long_content", {})

    # Create long content
    long_intro = "This is a very long introduction. " * (lengths.get("introduction", 100) // 30)
    long_improvements = ["This is a very long improvement description. " * 10] * 5
    long_cta = "This is a very long call to action. " * (lengths.get("cta", 100) // 30)

    personalization = EmailPersonalization(
        user_name="Test User",
        user_email="test@example.com",
        report_title="Test Report",
        report_link="https://example.com/report",
        agency_cta_link="https://example.com/cta",
        purchase_date=datetime.now(),
        expiry_date=datetime.now() + timedelta(days=30),
        ai_intro=long_intro,
        ai_improvements=long_improvements,
        ai_cta=long_cta,
        unsubscribe_link="https://example.com/unsubscribe"
    )

    template_engine = EmailTemplateEngine()
    template = template_engine.create_report_delivery_email(personalization)
    ai_email_context["email_content"] = template.html_content


@then("the email should contain personalized AI introduction")
def verify_ai_introduction(ai_email_context):
    """Verify email contains AI introduction."""
    content = ai_email_context.get("email_content")
    if hasattr(content, 'ai_intro'):
        assert content.ai_intro is not None
        assert len(content.ai_intro) > 10
    else:
        # For rendered HTML
        assert isinstance(content, str)
        assert "Your business deserves" in content or "Default introduction" not in content


@then("the email should list AI-generated improvements specific to HVAC")
def verify_hvac_improvements(ai_email_context):
    """Verify HVAC-specific improvements."""
    content = ai_email_context.get("email_content")
    if hasattr(content, 'ai_improvements'):
        assert len(content.ai_improvements) > 0
        # Should have HVAC-related terms
        hvac_terms = ["heating", "cooling", "HVAC", "AC", "furnace", "temperature", "climate"]
        assert any(any(term.lower() in imp.lower() for term in hvac_terms)
                  for imp in content.ai_improvements)


@then("the email should have an AI-generated call to action")
def verify_ai_cta(ai_email_context):
    """Verify AI-generated CTA."""
    content = ai_email_context.get("email_content")
    if hasattr(content, 'ai_cta'):
        assert content.ai_cta is not None
        assert "consultation" in content.ai_cta.lower() or "schedule" in content.ai_cta.lower()


@then("the email should include all CAN-SPAM required elements")
def verify_can_spam_compliance(ai_email_context):
    """Verify CAN-SPAM compliance."""
    content = ai_email_context.get("email_content")

    # Get HTML content
    if hasattr(content, 'html_content'):
        html = content.html_content
    elif hasattr(content, '__dict__') and 'email_content' in content.__dict__:
        html = content.email_content
    else:
        html = str(content)

    # Check required elements
    assert "123 Main Street" in html or "physical address" in html.lower()
    assert "Unsubscribe" in html
    assert "San Francisco, CA" in html or "United States" in html
    assert "You received this email" in html or "why you received" in html.lower()


@then("the AI introduction replaces the default introduction")
def verify_intro_replacement(ai_email_context):
    """Verify AI intro replaces default."""
    ai_content = ai_email_context.get("ai_content", {})
    assert ai_content.get("intro") != "Default introduction"


@then("the AI improvements replace the static improvement list")
def verify_improvements_replacement(ai_email_context):
    """Verify AI improvements replace defaults."""
    ai_content = ai_email_context.get("ai_content", {})
    improvements = ai_content.get("improvements", [])
    assert len(improvements) > 0
    assert "Default improvement" not in improvements


@then("the AI call-to-action replaces the default CTA")
def verify_cta_replacement(ai_email_context):
    """Verify AI CTA replaces default."""
    ai_content = ai_email_context.get("ai_content", {})
    assert ai_content.get("cta") != "Default CTA"


@then("the footer remains unchanged with compliance information")
def verify_footer_unchanged(ai_email_context):
    """Verify footer compliance info unchanged."""
    # This is implicitly verified by verify_can_spam_compliance
    verify_can_spam_compliance(ai_email_context)


@then("the email should use default content for the introduction")
def verify_default_intro(ai_email_context):
    """Verify default intro is used."""
    content = ai_email_context.get("email_content")
    if hasattr(content, 'ai_intro'):
        # When AI fails, ai_intro should be None or default
        assert content.ai_intro is None or "Great news!" in str(content)


@then("the email should use vertical-specific default improvements")
def verify_default_improvements(ai_email_context):
    """Verify vertical-specific defaults are used."""
    content = ai_email_context.get("email_content")
    business = ai_email_context["business"]

    if hasattr(content, 'ai_improvements') and content.ai_improvements:
        # Should have vertical-specific content even with defaults
        if business["vertical"] == "hvac":
            assert any("heating" in imp.lower() or "cooling" in imp.lower()
                      for imp in content.ai_improvements)


@then("the email should use a standard call to action")
def verify_standard_cta(ai_email_context):
    """Verify standard CTA is used."""
    content = ai_email_context.get("email_content")
    if hasattr(content, 'ai_cta'):
        assert content.ai_cta is None or "Schedule your free" in str(content)


@then("the email should still include all CAN-SPAM elements")
def verify_can_spam_with_fallback(ai_email_context):
    """Verify CAN-SPAM compliance with fallback content."""
    verify_can_spam_compliance(ai_email_context)


@then("each email should contain vertical-specific improvements")
def verify_vertical_improvements(ai_email_context):
    """Verify each email has vertical-specific improvements."""
    for email_data in ai_email_context["generated_emails"]:
        business = email_data["business"]
        improvements = email_data["improvements"]

        assert len(improvements) > 0
        # Improvements should be relevant to the vertical
        assert any(business["vertical"] in imp.lower() or
                  business["expected_keyword"] in imp.lower()
                  for imp in improvements)


@then("each improvement should mention the expected keyword")
def verify_expected_keywords(ai_email_context):
    """Verify expected keywords in improvements."""
    for email_data in ai_email_context["generated_emails"]:
        business = email_data["business"]
        improvements = email_data["improvements"]
        expected_keyword = business["expected_keyword"]

        assert any(expected_keyword.lower() in imp.lower() for imp in improvements)


@then("the first improvements should address performance issues")
def verify_performance_priority(ai_email_context):
    """Verify performance issues are prioritized."""
    ai_content = ai_email_context.get("ai_content", {})
    improvements = ai_content.get("improvements", [])

    if improvements:
        # First improvements should mention speed/performance
        first_two = " ".join(improvements[:2]).lower()
        assert any(term in first_two for term in ["fast", "speed", "loading", "performance"])


@then("mobile optimization should be prominently mentioned")
def verify_mobile_priority(ai_email_context):
    """Verify mobile optimization is prominent."""
    ai_content = ai_email_context.get("ai_content", {})
    improvements = ai_content.get("improvements", [])

    if improvements:
        # Mobile should be in first few improvements
        first_three = " ".join(improvements[:3]).lower()
        assert "mobile" in first_three


@then("SEO improvements should have lower priority")
def verify_seo_lower_priority(ai_email_context):
    """Verify SEO has lower priority."""
    ai_content = ai_email_context.get("ai_content", {})
    improvements = ai_content.get("improvements", [])

    if improvements and len(improvements) >= 4:
        # SEO should not be in first 2 improvements
        first_two = " ".join(improvements[:2]).lower()
        assert "seo" not in first_two or "search engine" not in first_two


@then("the physical address is still visible")
def verify_address_visible(ai_email_context):
    """Verify physical address is visible."""
    content = ai_email_context["email_content"]
    assert "123 Main Street" in content
    assert "San Francisco, CA 94105" in content


@then("the unsubscribe link is still accessible")
def verify_unsubscribe_accessible(ai_email_context):
    """Verify unsubscribe link is accessible."""
    content = ai_email_context["email_content"]
    assert "Unsubscribe" in content
    assert "https://example.com/unsubscribe" in content


@then("the email reason explanation is present")
def verify_email_reason(ai_email_context):
    """Verify email reason is present."""
    content = ai_email_context["email_content"]
    assert "You received this email because" in content


@then("the copyright notice is included")
def verify_copyright(ai_email_context):
    """Verify copyright notice."""
    content = ai_email_context["email_content"]
    assert "©" in content or "&copy;" in content
    assert "Anthrasite. All rights reserved." in content


@then(parsers.parse('the introduction should mention "{location}"'))
def verify_location_in_intro(ai_email_context, location):
    """Verify location is mentioned in intro."""
    ai_content = ai_email_context.get("ai_content", {})
    intro = ai_content.get("intro", "")
    assert location in intro


# Additional step implementations would continue...
# This provides a comprehensive set of BDD step definitions for AI email integration
