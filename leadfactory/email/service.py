"""
Main email service orchestrator for report delivery and follow-up workflows.

This module provides a high-level interface for managing all email-related
functionality including secure link generation, template rendering, delivery,
and automated follow-up workflows.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from leadfactory.ab_testing.email_ab_test import EmailABTest
from leadfactory.email.delivery import EmailDeliveryService
from leadfactory.email.secure_links import SecureLinkGenerator
from leadfactory.email.templates import EmailPersonalization, EmailTemplateEngine
from leadfactory.email.workflows import EmailWorkflowEngine

logger = logging.getLogger(__name__)


class ReportDeliveryRequest(BaseModel):
    """Request for report delivery via email."""

    user_id: str = Field(..., description="User identifier")
    user_email: str = Field(..., description="User email address")
    user_name: str = Field(..., description="User full name")
    report_id: str = Field(..., description="Report identifier")
    report_title: str = Field(..., description="Report title")
    purchase_id: str = Field(..., description="Purchase transaction ID")
    company_name: Optional[str] = Field(None, description="User's company name")
    include_download_link: bool = Field(
        default=True, description="Include direct download link"
    )
    custom_message: Optional[str] = Field(None, description="Custom message to include")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class EmailServiceResponse(BaseModel):
    """Response from email service operations."""

    success: bool = Field(..., description="Operation success status")
    email_id: Optional[str] = Field(None, description="Email identifier if sent")
    workflow_id: Optional[str] = Field(
        None, description="Workflow identifier if started"
    )
    message: str = Field(..., description="Response message")
    error_details: Optional[str] = Field(None, description="Error details if failed")


class EmailReportService:
    """High-level email service for report delivery and follow-up."""

    def __init__(self):
        """Initialize the email report service."""
        self.delivery_service = EmailDeliveryService()
        self.link_generator = SecureLinkGenerator()
        self.template_engine = EmailTemplateEngine()
        self.workflow_engine = EmailWorkflowEngine()
        self.ab_test = EmailABTest()

    async def deliver_report(
        self, request: ReportDeliveryRequest, start_followup_workflow: bool = True
    ) -> EmailServiceResponse:
        """
        Deliver a report via email with optional follow-up workflow.

        Args:
            request: Report delivery request
            start_followup_workflow: Whether to start automated follow-up

        Returns:
            Service response with delivery status
        """
        try:
            # Generate secure links
            report_link = self.link_generator.generate_secure_link(
                report_id=request.report_id,
                user_id=request.user_id,
                purchase_id=request.purchase_id,
                base_url="https://app.anthrasite.com/reports",
                expiry_days=7,
            )

            download_link = None
            if request.include_download_link:
                download_link = self.link_generator.generate_download_link(
                    report_id=request.report_id,
                    user_id=request.user_id,
                    purchase_id=request.purchase_id,
                    base_url="https://app.anthrasite.com/download",
                    expiry_hours=24,
                )

            agency_cta_link = self.link_generator.create_tracking_link(
                original_url="https://app.anthrasite.com/connect-agency",
                user_id=request.user_id,
                campaign_id=f"report_{request.report_id}",
                link_type="agency_cta",
            )

            # Create personalization
            personalization = EmailPersonalization(
                user_name=request.user_name,
                user_email=request.user_email,
                report_title=request.report_title,
                report_link=report_link,
                download_link=download_link,
                agency_cta_link=agency_cta_link,
                company_name=request.company_name,
                purchase_date=datetime.utcnow(),
                expiry_date=datetime.utcnow() + timedelta(days=7),
            )

            # Generate email with A/B testing variant
            variant_id, email_template = self.ab_test.generate_email_with_variant(
                user_id=request.user_id,
                personalization=personalization,
                email_type="report_delivery",
            )

            # Convert email_template dict to EmailTemplate object for delivery
            from leadfactory.email.templates import EmailTemplate

            template = EmailTemplate(
                name=email_template.get("template_name", "report_delivery"),
                subject=email_template["subject"],
                html_content=email_template["html_content"],
                text_content=email_template.get("text_content"),
                tracking_enabled=True,
            )

            # Send email
            email_id = await self.delivery_service.send_email(
                template,
                personalization,
                metadata={
                    "report_id": request.report_id,
                    "purchase_id": request.purchase_id,
                    "delivery_type": "report_delivery",
                    "ab_test_variant_id": variant_id,
                    "ab_test_variant_config": email_template.get("variant_config", {}),
                    **request.metadata,
                },
            )

            # Record email sent event for A/B testing
            try:
                # Find active email A/B test
                from leadfactory.ab_testing.ab_test_manager import TestType

                active_tests = self.ab_test.test_manager.get_active_tests(
                    TestType.EMAIL_SUBJECT
                )
                email_tests = [
                    t
                    for t in active_tests
                    if t.metadata.get("email_template") == "report_delivery"
                ]

                if email_tests:
                    self.ab_test.record_email_event(
                        test_id=email_tests[0].id,
                        user_id=request.user_id,
                        event_type="sent",
                        metadata={
                            "email_id": email_id,
                            "variant_id": variant_id,
                            "subject": template.subject,
                        },
                    )
            except Exception as e:
                logger.warning(f"Failed to record A/B test email event: {e}")

            # Start follow-up workflow if requested
            workflow_id = None
            if start_followup_workflow:
                workflow_id = await self.workflow_engine.start_workflow(
                    workflow_name="report_delivery",
                    user_id=request.user_id,
                    report_id=request.report_id,
                    purchase_id=request.purchase_id,
                    user_email=request.user_email,
                    user_name=request.user_name,
                    report_title=request.report_title,
                    metadata=request.metadata,
                )

            return EmailServiceResponse(
                success=True,
                email_id=email_id,
                workflow_id=workflow_id,
                message="Report delivered successfully",
            )

        except Exception as e:
            logger.error(f"Failed to deliver report: {str(e)}")
            return EmailServiceResponse(
                success=False, message="Failed to deliver report", error_details=str(e)
            )

    async def send_reminder_email(
        self,
        user_id: str,
        user_email: str,
        user_name: str,
        report_id: str,
        report_title: str,
        purchase_id: str,
        days_since_delivery: int,
        company_name: Optional[str] = None,
    ) -> EmailServiceResponse:
        """
        Send a reminder email for an unaccessed report.

        Args:
            user_id: User identifier
            user_email: User email address
            user_name: User full name
            report_id: Report identifier
            report_title: Report title
            purchase_id: Purchase transaction ID
            days_since_delivery: Days since original delivery
            company_name: User's company name

        Returns:
            Service response with send status
        """
        try:
            # Generate secure links
            report_link = self.link_generator.generate_secure_link(
                report_id=report_id,
                user_id=user_id,
                purchase_id=purchase_id,
                base_url="https://app.anthrasite.com/reports",
                expiry_days=7,
            )

            agency_cta_link = self.link_generator.create_tracking_link(
                original_url="https://app.anthrasite.com/connect-agency",
                user_id=user_id,
                campaign_id=f"reminder_{report_id}",
                link_type="agency_cta",
            )

            # Create personalization
            personalization = EmailPersonalization(
                user_name=user_name,
                user_email=user_email,
                report_title=report_title,
                report_link=report_link,
                agency_cta_link=agency_cta_link,
                company_name=company_name,
                purchase_date=datetime.utcnow() - timedelta(days=days_since_delivery),
                expiry_date=datetime.utcnow() + timedelta(days=7),
            )

            # Render reminder template
            template = self.template_engine.create_reminder_email(
                personalization, days_since_delivery
            )

            # Send email
            email_id = await self.delivery_service.send_email(
                template,
                personalization,
                metadata={
                    "report_id": report_id,
                    "purchase_id": purchase_id,
                    "delivery_type": "reminder",
                    "days_since_delivery": days_since_delivery,
                },
            )

            return EmailServiceResponse(
                success=True,
                email_id=email_id,
                message="Reminder email sent successfully",
            )

        except Exception as e:
            logger.error(f"Failed to send reminder email: {str(e)}")
            return EmailServiceResponse(
                success=False,
                message="Failed to send reminder email",
                error_details=str(e),
            )

    async def send_agency_followup(
        self,
        user_id: str,
        user_email: str,
        user_name: str,
        report_id: str,
        report_title: str,
        purchase_id: str,
        report_accessed: bool = True,
        company_name: Optional[str] = None,
    ) -> EmailServiceResponse:
        """
        Send an agency connection follow-up email.

        Args:
            user_id: User identifier
            user_email: User email address
            user_name: User full name
            report_id: Report identifier
            report_title: Report title
            purchase_id: Purchase transaction ID
            report_accessed: Whether the report was accessed
            company_name: User's company name

        Returns:
            Service response with send status
        """
        try:
            # Generate secure links
            report_link = self.link_generator.generate_secure_link(
                report_id=report_id,
                user_id=user_id,
                purchase_id=purchase_id,
                base_url="https://app.anthrasite.com/reports",
                expiry_days=7,
            )

            agency_cta_link = self.link_generator.create_tracking_link(
                original_url="https://app.anthrasite.com/connect-agency",
                user_id=user_id,
                campaign_id=f"followup_{report_id}",
                link_type="agency_followup",
            )

            # Create personalization
            personalization = EmailPersonalization(
                user_name=user_name,
                user_email=user_email,
                report_title=report_title,
                report_link=report_link,
                agency_cta_link=agency_cta_link,
                company_name=company_name,
                purchase_date=datetime.utcnow()
                - timedelta(days=5),  # Assume 5 days ago
                expiry_date=datetime.utcnow() + timedelta(days=7),
            )

            # Render follow-up template
            template = self.template_engine.create_followup_email(
                personalization, report_accessed
            )

            # Send email
            email_id = await self.delivery_service.send_email(
                template,
                personalization,
                metadata={
                    "report_id": report_id,
                    "purchase_id": purchase_id,
                    "delivery_type": "agency_followup",
                    "report_accessed": report_accessed,
                },
            )

            return EmailServiceResponse(
                success=True,
                email_id=email_id,
                message="Agency follow-up email sent successfully",
            )

        except Exception as e:
            logger.error(f"Failed to send agency follow-up email: {str(e)}")
            return EmailServiceResponse(
                success=False,
                message="Failed to send agency follow-up email",
                error_details=str(e),
            )

    async def process_email_workflows(self) -> Dict[str, int]:
        """
        Process all pending email workflows.

        Returns:
            Dictionary with processing statistics
        """
        try:
            # Process pending workflow steps
            steps_processed = await self.workflow_engine.process_pending_steps()

            # Retry failed emails
            emails_retried = await self.delivery_service.retry_failed_emails()

            return {
                "workflow_steps_processed": steps_processed,
                "failed_emails_retried": emails_retried,
                "total_actions": steps_processed + emails_retried,
            }

        except Exception as e:
            logger.error(f"Failed to process email workflows: {str(e)}")
            return {
                "workflow_steps_processed": 0,
                "failed_emails_retried": 0,
                "total_actions": 0,
                "error": str(e),
            }

    async def get_email_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        template_name: Optional[str] = None,
    ) -> Dict:
        """
        Get email analytics and performance metrics.

        Args:
            start_date: Start date for analytics
            end_date: End date for analytics
            template_name: Filter by template name

        Returns:
            Analytics data
        """
        try:
            # Get delivery statistics
            delivery_stats = await self.delivery_service.get_delivery_stats(
                start_date=start_date, end_date=end_date, template_name=template_name
            )

            # TODO: Add workflow analytics
            # TODO: Add conversion tracking

            return {
                "delivery_stats": delivery_stats,
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                },
                "filters": {"template_name": template_name},
            }

        except Exception as e:
            logger.error(f"Failed to get email analytics: {str(e)}")
            return {"error": str(e)}

    async def validate_secure_link(self, token: str) -> Dict:
        """
        Validate a secure link token.

        Args:
            token: JWT token from secure link

        Returns:
            Validation result with link data
        """
        try:
            link_data = self.link_generator.validate_secure_link(token)

            return {
                "valid": True,
                "report_id": link_data.report_id,
                "user_id": link_data.user_id,
                "purchase_id": link_data.purchase_id,
                "access_type": link_data.access_type,
                "expires_at": link_data.expires_at,
                "metadata": link_data.metadata,
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def cancel_user_workflows(self, user_id: str) -> int:
        """
        Cancel all active workflows for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of workflows cancelled
        """
        try:
            # TODO: Implement workflow cancellation by user
            # This would require querying active workflows for the user
            # and calling workflow_engine.cancel_workflow for each

            logger.info(f"Cancelled workflows for user: {user_id}")
            return 0

        except Exception as e:
            logger.error(f"Failed to cancel user workflows: {str(e)}")
            return 0


def get_email_report_service() -> EmailReportService:
    """Get a configured email report service instance."""
    return EmailReportService()
