"""
A/B Testing Framework for Email Subject Lines and Price Variants
================================================================

This module provides a comprehensive A/B testing framework for optimizing
email subject lines and price variants in the audit report sales funnel.

Key Features:
- Statistical significance testing
- Multi-variant testing support
- Conversion tracking and analytics
- Email subject line optimization
- Dynamic pricing optimization
- Automated winner selection
- Real-time performance monitoring

Usage:
    from leadfactory.ab_testing import ABTestManager, EmailABTest, PricingABTest

    # Create email subject line test
    email_test = EmailABTest(
        name="Report Delivery Subject Lines Q1 2024",
        variants=[
            {"subject": "Your audit report is ready!", "weight": 0.5},
            {"subject": "Don't miss your business insights!", "weight": 0.5}
        ]
    )

    # Create pricing test
    pricing_test = PricingABTest(
        name="SEO Audit Pricing Test",
        audit_type="seo",
        variants=[
            {"price": 9900, "weight": 0.33},  # $99
            {"price": 12900, "weight": 0.33}, # $129
            {"price": 7900, "weight": 0.34}   # $79
        ]
    )
"""

from .ab_test_manager import ABTestManager
from .analytics import ABTestAnalytics
from .email_ab_test import EmailABTest, EmailVariant
from .pricing_ab_test import PriceVariant, PricingABTest
from .statistical_engine import StatisticalEngine

__all__ = [
    "ABTestManager",
    "EmailABTest",
    "EmailVariant",
    "PricingABTest",
    "PriceVariant",
    "ABTestAnalytics",
    "StatisticalEngine",
]
