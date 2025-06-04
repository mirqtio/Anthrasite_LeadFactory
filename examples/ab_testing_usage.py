#!/usr/bin/env python3
"""
A/B Testing Usage Examples
==========================

This file demonstrates how to use the A/B testing framework for email subject lines
and pricing optimization in the Lead Factory system.

Examples include:
1. Creating email subject line tests
2. Setting up pricing experiments
3. Integrating with existing email and payment systems
4. Analyzing test results and statistical significance
5. Making data-driven decisions
"""

import asyncio
from datetime import datetime
from typing import Any, Dict

# Note: In actual usage, these imports would work
# from leadfactory.ab_testing import ABTestManager, EmailABTest, PricingABTest, ABTestAnalytics
# from leadfactory.email.service import EmailReportService
# from leadfactory.api.payment_api import router as payment_router


def example_email_subject_line_testing():
    """
    Example: Creating and managing email subject line A/B tests.
    """
    print("=" * 60)
    print("EMAIL SUBJECT LINE A/B TESTING")
    print("=" * 60)

    # Example 1: Create subject line test
    print("\n1. Creating Email Subject Line Test")

    email_test_code = """
    from leadfactory.ab_testing import EmailABTest

    # Initialize email A/B testing
    email_ab_test = EmailABTest()

    # Define subject line variants to test
    subject_variants = [
        {
            "subject": "Your audit report is ready! 📊",
            "weight": 0.25,
            "metadata": {"tone": "friendly", "emoji": True}
        },
        {
            "subject": "Don't miss your business insights",
            "weight": 0.25,
            "metadata": {"tone": "urgent", "emoji": False}
        },
        {
            "subject": "Action required: Review your audit results",
            "weight": 0.25,
            "metadata": {"tone": "formal", "emoji": False}
        },
        {
            "subject": "🎉 Your comprehensive audit report awaits",
            "weight": 0.25,
            "metadata": {"tone": "celebratory", "emoji": True}
        }
    ]

    # Create the A/B test
    test_id = email_ab_test.create_subject_line_test(
        name="Q1 2024 Report Delivery Subject Lines",
        description="Test different subject line tones and emoji usage",
        subject_variants=subject_variants,
        target_sample_size=2000,
        email_template="report_delivery",
        metadata={
            "campaign": "q1_2024",
            "goal": "improve_open_rates",
            "hypothesis": "Emojis and friendly tone will increase open rates"
        }
    )

    print(f"Created email A/B test: {test_id}")
    """

    print(email_test_code)

    # Example 2: Using A/B test in email delivery
    print("\n2. Integration with Email Delivery System")

    email_integration_code = """
    from leadfactory.email.service import EmailReportService
    from leadfactory.email.templates import EmailPersonalization

    # Email service automatically uses A/B testing
    email_service = EmailReportService()

    # When delivering a report, the service automatically:
    # 1. Checks for active email A/B tests
    # 2. Assigns user to a variant
    # 3. Uses the variant's subject line
    # 4. Records the email sent event

    async def deliver_report_with_ab_testing(user_data, report_data):
        request = ReportDeliveryRequest(
            user_id=user_data["id"],
            user_email=user_data["email"],
            user_name=user_data["name"],
            report_id=report_data["id"],
            report_title=report_data["title"],
            purchase_id=report_data["purchase_id"]
        )

        # This automatically uses A/B testing if active
        response = await email_service.deliver_report(request)

        # The email was sent with an A/B test variant
        # The variant is recorded in metadata for tracking
        return response
    """

    print(email_integration_code)

    # Example 3: Recording email events
    print("\n3. Recording Email Events for A/B Testing")

    event_tracking_code = """
    # Email events are automatically tracked, but you can also manually track
    from leadfactory.ab_testing import EmailABTest

    email_ab_test = EmailABTest()

    # Record when email is opened (usually via webhook)
    def handle_email_opened(email_id, user_id, test_id):
        email_ab_test.record_email_event(
            test_id=test_id,
            user_id=user_id,
            event_type="opened",
            metadata={
                "email_id": email_id,
                "timestamp": datetime.utcnow().isoformat(),
                "user_agent": request.headers.get("User-Agent"),
                "ip_address": request.client.host
            }
        )

    # Record when user clicks a link
    def handle_email_clicked(email_id, user_id, test_id, link_url):
        email_ab_test.record_email_event(
            test_id=test_id,
            user_id=user_id,
            event_type="clicked",
            metadata={
                "email_id": email_id,
                "link_url": link_url,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    """

    print(event_tracking_code)


def example_pricing_ab_testing():
    """
    Example: Creating and managing pricing A/B tests.
    """
    print("\n" + "=" * 60)
    print("PRICING A/B TESTING")
    print("=" * 60)

    # Example 1: Create pricing test
    print("\n1. Creating Pricing A/B Test")

    pricing_test_code = """
    from leadfactory.ab_testing import PricingABTest

    # Initialize pricing A/B testing
    pricing_ab_test = PricingABTest()

    # Define price variants to test for SEO audits
    price_variants = [
        {
            "price": 7900,  # $79.00
            "weight": 0.25,
            "metadata": {"strategy": "value", "position": "low"}
        },
        {
            "price": 9900,  # $99.00 (current price)
            "weight": 0.25,
            "metadata": {"strategy": "current", "position": "baseline"}
        },
        {
            "price": 12900, # $129.00
            "weight": 0.25,
            "metadata": {"strategy": "premium", "position": "high"}
        },
        {
            "price": 14900, # $149.00
            "weight": 0.25,
            "metadata": {"strategy": "luxury", "position": "very_high"}
        }
    ]

    # Create pricing test for SEO audits
    test_id = pricing_ab_test.create_price_point_test(
        name="SEO Audit Price Optimization Q1 2024",
        description="Test different price points to maximize revenue per visitor",
        audit_type="seo",
        price_variants=price_variants,
        target_sample_size=1000,
        metadata={
            "campaign": "q1_2024",
            "goal": "maximize_revenue_per_visitor",
            "hypothesis": "Premium pricing ($129) will maximize total revenue"
        }
    )

    print(f"Created pricing A/B test: {test_id}")
    """

    print(pricing_test_code)

    # Example 2: Integration with payment API
    print("\n2. Integration with Payment API")

    payment_integration_code = """
    # The payment API automatically uses pricing A/B tests

    @router.post("/checkout")
    async def create_checkout_session(
        request: CheckoutRequest,
        payment_service: StripePaymentService = Depends(get_payment_service),
        pricing_ab_test: PricingABTest = Depends(get_pricing_ab_test),
    ):
        # Get A/B test pricing for this user
        user_id = f"email_{request.customer_email}"

        # This automatically assigns user to pricing variant
        variant_id, pricing_config = pricing_ab_test.get_price_for_user(
            user_id=user_id,
            audit_type=request.audit_type
        )

        # Use A/B test price instead of default
        final_amount = pricing_config['price']

        # Record pricing view event
        pricing_ab_test.record_pricing_event(
            test_id=active_test.id,
            user_id=user_id,
            event_type="view",
            metadata={
                "variant_id": variant_id,
                "price": final_amount,
                "audit_type": request.audit_type
            }
        )

        # Create Stripe checkout with A/B test price
        result = payment_service.create_checkout_session(
            customer_email=request.customer_email,
            customer_name=request.customer_name,
            audit_type=request.audit_type,
            amount=final_amount,  # A/B test price
            metadata={
                "ab_test_variant_id": variant_id,
                "ab_test_pricing_config": pricing_config
            }
        )

        return result
    """

    print(payment_integration_code)

    # Example 3: Discount testing
    print("\n3. Creating Discount A/B Tests")

    discount_test_code = """
    # Test different discount offers
    discount_variants = [
        {
            "discount_percentage": 0,    # No discount (control)
            "weight": 0.25,
            "offer_text": ""
        },
        {
            "discount_percentage": 10,   # 10% off
            "weight": 0.25,
            "offer_text": "Save 10% - Limited time!"
        },
        {
            "discount_percentage": 20,   # 20% off
            "weight": 0.25,
            "offer_text": "20% off for first-time customers"
        },
        {
            "discount_percentage": 15,   # 15% off with urgency
            "weight": 0.25,
            "offer_text": "15% off - Expires in 24 hours!"
        }
    ]

    discount_test_id = pricing_ab_test.create_discount_test(
        name="First-Time Customer Discount Test",
        description="Test different discount offers for new customers",
        audit_type="comprehensive",
        base_price=24900,  # $249.00
        discount_variants=discount_variants,
        target_sample_size=800,
        metadata={
            "customer_segment": "first_time",
            "goal": "increase_conversion_rate"
        }
    )
    """

    print(discount_test_code)


def example_analytics_and_reporting():
    """
    Example: Analyzing A/B test results and making decisions.
    """
    print("\n" + "=" * 60)
    print("ANALYTICS AND REPORTING")
    print("=" * 60)

    # Example 1: Generate test reports
    print("\n1. Generating Test Reports")

    analytics_code = """
    from leadfactory.ab_testing import ABTestAnalytics

    # Initialize analytics
    analytics = ABTestAnalytics()

    # Generate comprehensive test report
    def analyze_test_performance(test_id: str):
        report = analytics.generate_test_report(test_id)

        print(f"Test: {report['test_name']}")
        print(f"Status: {report['status']}")
        print(f"Runtime: {report['runtime_days']} days")
        print(f"Participants: {report['total_participants']}")

        # Analyze performance metrics
        for metric in report['performance_metrics']:
            variant_id = metric['variant_id']
            conversion_rate = metric['conversion_rate']
            revenue_per_visitor = metric['revenue_per_visitor']
            is_winner = metric['is_winner']

            status = "🏆 WINNER" if is_winner else ""
            print(f"  {variant_id}: {conversion_rate:.2%} conversion, "
                  f"${revenue_per_visitor:.2f} RPV {status}")

        # Review insights
        print("\\nKey Insights:")
        for insight in report['insights']:
            if insight['actionable']:
                print(f"  • {insight['title']}: {insight['recommendation']}")

        # Statistical significance
        stats = report['statistical_result']
        if stats['is_significant']:
            print(f"\\n✅ Statistically significant (p={stats['p_value']:.3f})")
            print(f"Winner: {stats['winner']}")
        else:
            print(f"\\n⏳ Not yet significant (p={stats['p_value']:.3f})")
            print("Continue test or increase sample size")

        return report
    """

    print(analytics_code)

    # Example 2: Portfolio dashboard
    print("\n2. Portfolio Dashboard")

    dashboard_code = """
    # Get overview of all A/B tests
    def generate_ab_testing_dashboard():
        portfolio = analytics.get_portfolio_overview()

        summary = portfolio['summary']
        print(f"A/B Testing Portfolio Summary:")
        print(f"  Active Tests: {summary['total_active_tests']}")
        print(f"  Total Participants: {summary['total_participants']}")
        print(f"  Significant Tests: {summary['significant_tests']}")
        print(f"  Success Rate: {summary['significance_rate']:.1%}")
        print(f"  Health Score: {summary['avg_health_score']:.1f}/1.0")

        # Test type breakdown
        print(f"\\nTest Types:")
        for test_type, count in portfolio['test_type_distribution'].items():
            print(f"  {test_type}: {count} tests")

        # Actionable insights
        actionable_insights = portfolio['insights']['actionable']
        print(f"\\nActionable Insights: {actionable_insights}")

        return portfolio
    """

    print(dashboard_code)

    # Example 3: Making decisions
    print("\n3. Making Data-Driven Decisions")

    decision_code = """
    # Automated decision making based on test results
    def make_test_decisions():
        active_tests = analytics.test_manager.get_active_tests()

        for test in active_tests:
            report = analytics.generate_test_report(test.id)
            health = report['health_metrics']
            stats = report['statistical_result']

            # Check if test is ready for decision
            if health['progress_to_target'] >= 0.8:  # 80% of target reached

                if stats['is_significant'] and stats['winner']:
                    # We have a winner!
                    print(f"🎯 Test {test.name}: Implement {stats['winner']}")

                    # Stop the test and implement winner
                    analytics.test_manager.stop_test(test.id)

                    # Send notification to team
                    notify_team({
                        'type': 'test_completed',
                        'test_name': test.name,
                        'winner': stats['winner'],
                        'improvement': stats['effect_size']
                    })

                elif health['statistical_power'] < 0.8:
                    # Need more samples
                    print(f"⏳ Test {test.name}: Continue - need more data")

                else:
                    # No significant difference found
                    print(f"🤝 Test {test.name}: No clear winner - keep current")
                    analytics.test_manager.stop_test(test.id)
    """

    print(decision_code)


def example_advanced_usage():
    """
    Example: Advanced A/B testing scenarios.
    """
    print("\n" + "=" * 60)
    print("ADVANCED A/B TESTING SCENARIOS")
    print("=" * 60)

    # Example 1: Multi-variant testing
    print("\n1. Multi-Variant Testing")

    multivariate_code = """
    # Test multiple elements simultaneously
    def create_multivariate_email_test():
        # Test combinations of subject line and CTA button
        email_variants = [
            {
                "subject": "Your report is ready",
                "cta_text": "View Report",
                "cta_style": "primary",
                "weight": 0.25
            },
            {
                "subject": "Your report is ready",
                "cta_text": "Download Now",
                "cta_style": "secondary",
                "weight": 0.25
            },
            {
                "subject": "Don't miss your insights",
                "cta_text": "View Report",
                "cta_style": "primary",
                "weight": 0.25
            },
            {
                "subject": "Don't miss your insights",
                "cta_text": "Download Now",
                "cta_style": "secondary",
                "weight": 0.25
            }
        ]

        # This tests 2x2 = 4 combinations
        test_id = email_ab_test.create_content_test(
            name="Subject + CTA Multivariate Test",
            description="Test subject line and CTA combinations",
            content_variants=email_variants,
            target_sample_size=2000  # Larger sample needed for multivariate
        )

        return test_id
    """

    print(multivariate_code)

    # Example 2: Sequential testing
    print("\n2. Sequential Testing Strategy")

    sequential_code = """
    # Run tests in sequence to compound improvements
    async def run_sequential_optimization():

        # Phase 1: Optimize subject lines
        subject_test_id = email_ab_test.create_subject_line_test(
            name="Phase 1: Subject Line Optimization",
            description="Find best subject line approach",
            subject_variants=[
                {"subject": "Your report is ready", "weight": 0.5},
                {"subject": "Action required: Review results", "weight": 0.5}
            ]
        )

        # Wait for subject line winner
        winner_subject = await wait_for_test_completion(subject_test_id)

        # Phase 2: Optimize CTA with winning subject
        cta_test_id = email_ab_test.create_cta_test(
            name="Phase 2: CTA Optimization",
            description="Optimize CTA with winning subject line",
            cta_variants=[
                {"text": "View Your Report", "style": "primary", "weight": 0.5},
                {"text": "Download PDF", "style": "secondary", "weight": 0.5}
            ],
            metadata={"baseline_subject": winner_subject}
        )

        winner_cta = await wait_for_test_completion(cta_test_id)

        # Phase 3: Test final optimization
        final_test_id = create_final_optimization_test(winner_subject, winner_cta)

        return await wait_for_test_completion(final_test_id)
    """

    print(sequential_code)

    # Example 3: Audience segmentation
    print("\n3. Audience Segmentation")

    segmentation_code = """
    # Run different tests for different audience segments
    def create_segmented_pricing_tests():

        # Test for new customers (price sensitive)
        new_customer_test = pricing_ab_test.create_price_point_test(
            name="New Customer Pricing",
            description="Price optimization for first-time buyers",
            audit_type="seo",
            price_variants=[
                {"price": 6900, "weight": 0.5},  # Lower prices
                {"price": 7900, "weight": 0.5}
            ],
            metadata={"segment": "new_customers"}
        )

        # Test for returning customers (value focused)
        returning_customer_test = pricing_ab_test.create_price_point_test(
            name="Returning Customer Pricing",
            description="Price optimization for repeat buyers",
            audit_type="seo",
            price_variants=[
                {"price": 9900, "weight": 0.5},   # Standard prices
                {"price": 11900, "weight": 0.5}
            ],
            metadata={"segment": "returning_customers"}
        )

        # Test for enterprise customers (premium pricing)
        enterprise_test = pricing_ab_test.create_price_point_test(
            name="Enterprise Customer Pricing",
            description="Premium pricing for enterprise clients",
            audit_type="comprehensive",
            price_variants=[
                {"price": 39900, "weight": 0.5},  # Higher prices
                {"price": 49900, "weight": 0.5}
            ],
            metadata={"segment": "enterprise"}
        )

        return {
            "new_customers": new_customer_test,
            "returning_customers": returning_customer_test,
            "enterprise": enterprise_test
        }
    """

    print(segmentation_code)


def example_api_usage():
    """
    Example: Using the A/B testing REST API.
    """
    print("\n" + "=" * 60)
    print("REST API USAGE")
    print("=" * 60)

    api_examples = """
    # Create email A/B test via API
    POST /api/v1/ab-testing/email-tests
    {
        "name": "Q1 Subject Line Test",
        "description": "Test different subject line approaches",
        "email_template": "report_delivery",
        "subject_variants": [
            {"subject": "Your report is ready!", "weight": 0.5},
            {"subject": "Don't miss your insights!", "weight": 0.5}
        ],
        "target_sample_size": 1000
    }

    # Create pricing A/B test via API
    POST /api/v1/ab-testing/pricing-tests
    {
        "name": "SEO Audit Pricing Test",
        "description": "Test different price points",
        "audit_type": "seo",
        "price_variants": [
            {"price": 7900, "weight": 0.5},
            {"price": 9900, "weight": 0.5}
        ],
        "target_sample_size": 500
    }

    # Start a test
    PUT /api/v1/ab-testing/tests/{test_id}/status
    {
        "action": "start"
    }

    # Get test results
    GET /api/v1/ab-testing/tests/{test_id}/results

    # Get dashboard overview
    GET /api/v1/ab-testing/dashboard

    # Calculate required sample size
    GET /api/v1/ab-testing/stats/sample-size?baseline_rate=0.05&effect_size=0.2&alpha=0.05&power=0.8

    # Record custom conversion event
    POST /api/v1/ab-testing/tests/{test_id}/record-event?event_type=purchase&user_id=user_123&conversion_value=99.00
    """

    print(api_examples)


def main():
    """
    Main function demonstrating A/B testing usage.
    """
    print("A/B TESTING FRAMEWORK USAGE EXAMPLES")
    print("=" * 60)
    print("This demonstrates how to use the A/B testing framework")
    print("for email subject lines and pricing optimization.")
    print()

    example_email_subject_line_testing()
    example_pricing_ab_testing()
    example_analytics_and_reporting()
    example_advanced_usage()
    example_api_usage()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    summary = """
    The A/B testing framework provides:

    ✅ Email Subject Line Testing
       - Multiple subject line variants
       - Automatic integration with email delivery
       - Open rate and click tracking

    ✅ Pricing Optimization
       - Price point testing
       - Discount offer experiments
       - Revenue per visitor optimization

    ✅ Statistical Analysis
       - Automatic significance testing
       - Sample size calculations
       - Bayesian analysis support

    ✅ Analytics & Reporting
       - Real-time performance dashboards
       - Automated insights and recommendations
       - Export capabilities

    ✅ Production Ready
       - REST API for external integrations
       - Database persistence
       - Error handling and logging

    Next Steps:
    1. Create your first email subject line test
    2. Set up pricing experiments for different audit types
    3. Monitor results through the dashboard
    4. Implement winning variants automatically
    """

    print(summary)


if __name__ == "__main__":
    main()
