"""
Email template system for report delivery with CTA components.

This module provides a flexible email template system that includes
secure report links and call-to-action components for agency connection.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel, Field

from leadfactory.config import get_env


class EmailTemplate(BaseModel):
    """Email template configuration."""

    name: str = Field(..., description="Template name")
    subject: str = Field(..., description="Email subject line")
    html_content: str = Field(..., description="HTML email content")
    text_content: Optional[str] = Field(None, description="Plain text content")
    tracking_enabled: bool = Field(default=True, description="Enable tracking")


class EmailPersonalization(BaseModel):
    """Email personalization data."""

    user_name: str = Field(..., description="Recipient name")
    user_email: str = Field(..., description="Recipient email")
    report_title: str = Field(..., description="Report title")
    report_link: str = Field(..., description="Secure report access link")
    download_link: Optional[str] = Field(None, description="Direct download link")
    agency_cta_link: str = Field(..., description="Agency connection CTA link")
    company_name: Optional[str] = Field(None, description="User's company name")
    purchase_date: datetime = Field(..., description="Report purchase date")
    expiry_date: datetime = Field(..., description="Link expiry date")
    support_email: str = Field(
        default="support@anthrasite.com", description="Support contact"
    )
    unsubscribe_link: Optional[str] = Field(None, description="Unsubscribe link")


class CTAButton(BaseModel):
    """Call-to-action button configuration."""

    text: str = Field(..., description="Button text")
    url: str = Field(..., description="Button URL")
    style: str = Field(default="primary", description="Button style")
    tracking_id: Optional[str] = Field(None, description="Tracking identifier")


class EmailTemplateEngine:
    """Email template engine with Jinja2 support."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize the template engine."""
        self.template_dir = template_dir or self._get_default_template_dir()
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir), autoescape=True
        )

        # Add custom filters
        self.env.filters["format_date"] = self._format_date
        self.env.filters["format_currency"] = self._format_currency

    def _get_default_template_dir(self) -> str:
        """Get default template directory."""
        base_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(base_dir, "templates", "email")

    def _format_date(self, date: datetime, format_str: str = "%B %d, %Y") -> str:
        """Format date for email display."""
        return date.strftime(format_str)

    def _format_currency(self, amount: float, currency: str = "USD") -> str:
        """Format currency for email display."""
        return f"${amount:.2f} {currency}"

    def render_template(
        self,
        template_name: str,
        personalization: EmailPersonalization,
        cta_buttons: Optional[list[CTAButton]] = None,
        additional_context: Optional[dict] = None,
    ) -> EmailTemplate:
        """
        Render an email template with personalization data.

        Args:
            template_name: Name of the template file
            personalization: Personalization data
            cta_buttons: List of CTA buttons to include
            additional_context: Additional template context

        Returns:
            Rendered email template
        """
        try:
            # Load template
            template = self.env.get_template(f"{template_name}.html")

            # Prepare context
            context = {
                "user": personalization,
                "cta_buttons": cta_buttons or [],
                "current_year": datetime.now().year,
                **(additional_context or {}),
            }

            # Render HTML content
            html_content = template.render(**context)

            # Try to render text version
            text_content = None
            try:
                text_template = self.env.get_template(f"{template_name}.txt")
                text_content = text_template.render(**context)
            except jinja2.TemplateNotFound:
                # Generate basic text version from HTML
                text_content = self._html_to_text(html_content)

            # Extract subject from template or use default
            subject = self._extract_subject(template_name, context)

            return EmailTemplate(
                name=template_name,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

        except Exception as e:
            raise ValueError(f"Failed to render template {template_name}: {str(e)}")

    def _extract_subject(self, template_name: str, context: dict) -> str:
        """Extract subject line from template or generate default."""
        try:
            subject_template = self.env.get_template(f"{template_name}_subject.txt")
            return subject_template.render(**context).strip()
        except jinja2.TemplateNotFound:
            # Default subject based on template name
            if "delivery" in template_name:
                return f"Your {context['user'].report_title} is ready!"
            elif "reminder" in template_name:
                return f"Don't forget: Your {context['user'].report_title} is waiting"
            elif "followup" in template_name:
                return "Ready to connect with a growth agency?"
            else:
                return "Your audit report from Anthrasite"

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        # Simple HTML to text conversion
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html_content)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def create_report_delivery_email(
        self, personalization: EmailPersonalization, include_download: bool = True
    ) -> EmailTemplate:
        """
        Create a report delivery email.

        Args:
            personalization: Email personalization data
            include_download: Whether to include direct download link

        Returns:
            Rendered email template
        """
        cta_buttons = [
            CTAButton(
                text="View Your Report",
                url=personalization.report_link,
                style="primary",
                tracking_id="view_report",
            ),
            CTAButton(
                text="Connect with an Agency",
                url=personalization.agency_cta_link,
                style="secondary",
                tracking_id="agency_cta",
            ),
        ]

        if include_download and personalization.download_link:
            cta_buttons.insert(
                1,
                CTAButton(
                    text="Download PDF",
                    url=personalization.download_link,
                    style="outline",
                    tracking_id="download_pdf",
                ),
            )

        return self.render_template("report_delivery", personalization, cta_buttons)

    def create_reminder_email(
        self, personalization: EmailPersonalization, days_since_delivery: int
    ) -> EmailTemplate:
        """
        Create a reminder email for unaccessed reports.

        Args:
            personalization: Email personalization data
            days_since_delivery: Number of days since original delivery

        Returns:
            Rendered email template
        """
        cta_buttons = [
            CTAButton(
                text="Access Your Report Now",
                url=personalization.report_link,
                style="primary",
                tracking_id="reminder_access",
            )
        ]

        additional_context = {
            "days_since_delivery": days_since_delivery,
            "urgency_level": "high" if days_since_delivery >= 5 else "medium",
        }

        return self.render_template(
            "report_reminder", personalization, cta_buttons, additional_context
        )

    def create_followup_email(
        self, personalization: EmailPersonalization, report_accessed: bool = True
    ) -> EmailTemplate:
        """
        Create a follow-up email focusing on agency connection.

        Args:
            personalization: Email personalization data
            report_accessed: Whether the report was accessed

        Returns:
            Rendered email template
        """
        if report_accessed:
            message_type = "post_access"
            primary_cta_text = "Get Expert Help Now"
        else:
            message_type = "no_access"
            primary_cta_text = "View Report & Get Help"

        cta_buttons = [
            CTAButton(
                text=primary_cta_text,
                url=personalization.agency_cta_link,
                style="primary",
                tracking_id="followup_agency",
            )
        ]

        if not report_accessed:
            cta_buttons.insert(
                0,
                CTAButton(
                    text="Access Your Report",
                    url=personalization.report_link,
                    style="outline",
                    tracking_id="followup_report",
                ),
            )

        additional_context = {
            "message_type": message_type,
            "report_accessed": report_accessed,
        }

        return self.render_template(
            "agency_followup", personalization, cta_buttons, additional_context
        )


def get_email_template_engine() -> EmailTemplateEngine:
    """Get a configured email template engine instance."""
    return EmailTemplateEngine()
