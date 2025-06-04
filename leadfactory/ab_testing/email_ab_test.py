"""
Email A/B Testing - Subject lines and content optimization.

This module provides specialized A/B testing for email campaigns including
subject line optimization, content variants, and CTA testing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.ab_testing.ab_test_manager import (
    ABTestManager,
    TestType,
    ab_test_manager,
)
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.utils.logging import get_logger


class EmailTestType(Enum):
    """Email A/B test types."""

    SUBJECT_LINE = "subject_line"
    CONTENT = "content"
    CTA_BUTTON = "cta_button"
    SENDER_NAME = "sender_name"
    SEND_TIME = "send_time"


@dataclass
class EmailVariant:
    """Email variant configuration."""

    id: str
    weight: float
    subject: Optional[str] = None
    content_template: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    cta_text: Optional[str] = None
    cta_style: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EmailABTest:
    """Email A/B testing manager with template integration."""

    def __init__(self, test_manager: Optional[ABTestManager] = None):
        """Initialize email A/B test manager.

        Args:
            test_manager: A/B test manager instance
        """
        self.test_manager = test_manager or ab_test_manager
        self.template_engine = EmailTemplateEngine()
        self.logger = get_logger(f"{__name__}.EmailABTest")

    def create_subject_line_test(
        self,
        name: str,
        description: str,
        subject_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        email_template: str = "report_delivery",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a subject line A/B test.

        Args:
            name: Test name
            description: Test description
            subject_variants: List of subject line variants with weights
            target_sample_size: Target number of email sends
            email_template: Base email template to use
            metadata: Additional test metadata

        Returns:
            Test ID

        Example:
            >>> test_id = email_ab_test.create_subject_line_test(
            ...     name="Q1 Report Delivery Subject Test",
            ...     description="Test different subject line urgency levels",
            ...     subject_variants=[
            ...         {"subject": "Your audit report is ready!", "weight": 0.25},
            ...         {"subject": "Don't miss your business insights!", "weight": 0.25},
            ...         {"subject": "🎉 Your report is here - download now!", "weight": 0.25},
            ...         {"subject": "Action required: Review your audit results", "weight": 0.25}
            ...     ]
            ... )
        """
        # Validate subject variants
        if not subject_variants or len(subject_variants) < 2:
            raise ValueError("Subject line test requires at least 2 variants")

        for variant in subject_variants:
            if "subject" not in variant:
                raise ValueError("Each variant must have a 'subject' field")
            if len(variant["subject"]) > 78:
                self.logger.warning(
                    f"Subject line may be too long: {variant['subject']}"
                )

        # Prepare variants for A/B test manager
        test_variants = []
        for i, variant in enumerate(subject_variants):
            test_variants.append(
                {
                    "id": f"subject_variant_{i}",
                    "subject": variant["subject"],
                    "weight": variant.get("weight", 1.0 / len(subject_variants)),
                    "email_template": email_template,
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {
            "email_template": email_template,
            "test_type": EmailTestType.SUBJECT_LINE.value,
            **(metadata or {}),
        }

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.EMAIL_SUBJECT,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created subject line A/B test: {test_id}")
        return test_id

    def create_content_test(
        self,
        name: str,
        description: str,
        content_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create an email content A/B test.

        Args:
            name: Test name
            description: Test description
            content_variants: List of content variants with templates
            target_sample_size: Target number of email sends
            metadata: Additional test metadata

        Returns:
            Test ID
        """
        # Validate content variants
        if not content_variants or len(content_variants) < 2:
            raise ValueError("Content test requires at least 2 variants")

        for variant in content_variants:
            if "template" not in variant:
                raise ValueError("Each variant must have a 'template' field")

        # Prepare variants
        test_variants = []
        for i, variant in enumerate(content_variants):
            test_variants.append(
                {
                    "id": f"content_variant_{i}",
                    "template": variant["template"],
                    "subject": variant.get("subject"),
                    "weight": variant.get("weight", 1.0 / len(content_variants)),
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {"test_type": EmailTestType.CONTENT.value, **(metadata or {})}

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.EMAIL_CONTENT,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created content A/B test: {test_id}")
        return test_id

    def create_cta_test(
        self,
        name: str,
        description: str,
        cta_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        email_template: str = "report_delivery",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a CTA button A/B test.

        Args:
            name: Test name
            description: Test description
            cta_variants: List of CTA variants
            target_sample_size: Target number of email sends
            email_template: Base email template to use
            metadata: Additional test metadata

        Returns:
            Test ID
        """
        # Validate CTA variants
        if not cta_variants or len(cta_variants) < 2:
            raise ValueError("CTA test requires at least 2 variants")

        for variant in cta_variants:
            if "text" not in variant:
                raise ValueError("Each CTA variant must have a 'text' field")

        # Prepare variants
        test_variants = []
        for i, variant in enumerate(cta_variants):
            test_variants.append(
                {
                    "id": f"cta_variant_{i}",
                    "cta_text": variant["text"],
                    "cta_style": variant.get("style", "primary"),
                    "cta_color": variant.get("color"),
                    "weight": variant.get("weight", 1.0 / len(cta_variants)),
                    "email_template": email_template,
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {
            "email_template": email_template,
            "test_type": EmailTestType.CTA_BUTTON.value,
            **(metadata or {}),
        }

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.CTA_BUTTON,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created CTA A/B test: {test_id}")
        return test_id

    def get_email_variant_for_user(
        self,
        user_id: str,
        user_email: str,
        test_id: Optional[str] = None,
        email_type: str = "report_delivery",
    ) -> Tuple[str, Dict[str, Any]]:
        """Get the email variant assigned to a user.

        Args:
            user_id: User identifier
            user_email: User email address
            test_id: Specific test ID (optional, will find active test)
            email_type: Type of email being sent

        Returns:
            Tuple of (variant_id, variant_config)
        """
        # Find active email test if not specified
        if not test_id:
            active_tests = self.test_manager.get_active_tests(TestType.EMAIL_SUBJECT)
            email_tests = [
                t
                for t in active_tests
                if t.metadata.get("email_template") == email_type
            ]

            if not email_tests:
                # No active test, return default variant
                return "default", {
                    "subject": "Your audit report is ready!",
                    "template": email_type,
                }

            test_id = email_tests[0].id

        # Get user's variant assignment
        variant_id = self.test_manager.assign_user_to_variant(
            user_id=user_id,
            test_id=test_id,
            metadata={"email": user_email, "email_type": email_type},
        )

        # Get test configuration
        test_config = self.test_manager.get_test_config(test_id)
        if not test_config:
            raise ValueError(f"Test not found: {test_id}")

        # Find variant configuration
        variant_index = int(variant_id.split("_")[-1])
        if variant_index >= len(test_config.variants):
            raise ValueError(f"Invalid variant index: {variant_index}")

        variant_config = test_config.variants[variant_index]

        self.logger.debug(f"Assigned user {user_id} to email variant {variant_id}")
        return variant_id, variant_config

    def generate_email_with_variant(
        self,
        user_id: str,
        personalization: EmailPersonalization,
        test_id: Optional[str] = None,
        email_type: str = "report_delivery",
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate personalized email using A/B test variant.

        Args:
            user_id: User identifier
            personalization: Email personalization data
            test_id: Specific test ID (optional)
            email_type: Type of email being sent

        Returns:
            Tuple of (variant_id, email_template)
        """
        # Get variant for user
        variant_id, variant_config = self.get_email_variant_for_user(
            user_id=user_id,
            user_email=personalization.user_email,
            test_id=test_id,
            email_type=email_type,
        )

        # Apply variant modifications to email
        modified_personalization = personalization

        # Apply subject line variant
        if "subject" in variant_config:
            # Create a copy with modified subject in template generation
            pass

        # Generate email template
        template_name = variant_config.get("email_template", email_type)

        if template_name == "report_delivery":
            email_template = self.template_engine.create_report_delivery_email(
                modified_personalization, include_download=True
            )
        elif template_name == "report_reminder":
            email_template = self.template_engine.create_reminder_email(
                modified_personalization, days_since_delivery=3
            )
        elif template_name == "agency_followup":
            email_template = self.template_engine.create_followup_email(
                modified_personalization, report_accessed=True
            )
        else:
            # Custom template
            email_template = self.template_engine.render_template(
                template_name, modified_personalization
            )

        # Apply variant-specific modifications
        if "subject" in variant_config:
            email_template.subject = variant_config["subject"]

        if "cta_text" in variant_config:
            # Modify CTA buttons in HTML content
            original_html = email_template.html_content
            # Simple replacement for demo - in production, use proper HTML parsing
            cta_replacements = {
                "View Your Report": variant_config.get("cta_text", "View Your Report"),
                "Download PDF": variant_config.get("cta_text", "Download PDF"),
                "Connect with an Agency": variant_config.get(
                    "cta_text", "Connect with an Agency"
                ),
            }

            modified_html = original_html
            for original_text, new_text in cta_replacements.items():
                if "cta_text" in variant_config:
                    modified_html = modified_html.replace(
                        f">{original_text}<", f">{new_text}<"
                    )

            email_template.html_content = modified_html

        self.logger.debug(f"Generated email for variant {variant_id}")
        return variant_id, {
            "subject": email_template.subject,
            "html_content": email_template.html_content,
            "text_content": email_template.text_content,
            "template_name": email_template.name,
            "variant_config": variant_config,
        }

    def record_email_event(
        self,
        test_id: str,
        user_id: str,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record an email-related event for A/B testing.

        Args:
            test_id: Test identifier
            user_id: User identifier
            event_type: Event type (sent, delivered, opened, clicked, unsubscribed)
            metadata: Additional event metadata
        """
        self.test_manager.record_conversion(
            test_id=test_id,
            user_id=user_id,
            conversion_type=f"email_{event_type}",
            metadata=metadata,
        )

        self.logger.debug(
            f"Recorded email event {event_type} for user {user_id} in test {test_id}"
        )

    def get_email_test_performance(self, test_id: str) -> Dict[str, Any]:
        """Get detailed performance metrics for an email A/B test.

        Args:
            test_id: Test identifier

        Returns:
            Dictionary with email-specific performance metrics
        """
        results = self.test_manager.get_test_results(test_id)

        # Calculate email-specific metrics
        email_metrics = {}

        for variant_id, variant_data in results["variant_results"].items():
            conversions = variant_data["conversion_rates"]
            assignments = variant_data["assignments"]

            # Calculate email funnel metrics
            sent_rate = conversions.get("email_sent", {}).get("rate", 0)
            delivered_rate = conversions.get("email_delivered", {}).get("rate", 0)
            open_rate = conversions.get("email_opened", {}).get("rate", 0)
            click_rate = conversions.get("email_clicked", {}).get("rate", 0)
            unsubscribe_rate = conversions.get("email_unsubscribed", {}).get("rate", 0)

            # Calculate engagement metrics
            engagement_score = open_rate + (click_rate * 2)  # Weight clicks higher

            email_metrics[variant_id] = {
                "assignments": assignments,
                "sent_rate": sent_rate,
                "delivery_rate": delivered_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "unsubscribe_rate": unsubscribe_rate,
                "engagement_score": engagement_score,
                "click_to_open_rate": click_rate / open_rate if open_rate > 0 else 0,
            }

        # Add test configuration
        test_config = results["test_config"]

        return {
            "test_id": test_id,
            "test_name": test_config.name,
            "test_type": test_config.test_type.value,
            "status": test_config.status.value,
            "email_metrics": email_metrics,
            "total_assignments": results["total_assignments"],
            "start_date": test_config.start_date,
            "end_date": test_config.end_date,
        }


# Global instance
email_ab_test = EmailABTest()
