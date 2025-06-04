"""
Email delivery and tracking service for report distribution.

This module handles the actual sending of emails through SendGrid
with tracking capabilities for opens, clicks, and delivery status.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import uuid4

import sendgrid
from pydantic import BaseModel, Field
from sendgrid.helpers.mail import (
    Attachment,
    ClickTracking,
    Content,
    Email,
    Mail,
    OpenTracking,
    Personalization,
    SubscriptionTracking,
    TrackingSettings,
)

from leadfactory.config import get_env
from leadfactory.email.templates import EmailPersonalization, EmailTemplate
from leadfactory.storage.factory import get_storage_instance

logger = logging.getLogger(__name__)


class EmailStatus(str, Enum):
    """Email delivery status."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"


class EmailEvent(BaseModel):
    """Email tracking event."""

    email_id: str = Field(..., description="Email identifier")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    user_agent: Optional[str] = Field(None, description="User agent")
    ip_address: Optional[str] = Field(None, description="IP address")
    url: Optional[str] = Field(None, description="Clicked URL")
    metadata: Dict = Field(default_factory=dict, description="Additional event data")


class EmailDeliveryRecord(BaseModel):
    """Email delivery record for tracking."""

    email_id: str = Field(..., description="Unique email identifier")
    user_id: str = Field(..., description="Recipient user ID")
    email_address: str = Field(..., description="Recipient email address")
    template_name: str = Field(..., description="Template used")
    subject: str = Field(..., description="Email subject")
    status: EmailStatus = Field(
        default=EmailStatus.QUEUED, description="Current status"
    )
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")
    delivered_at: Optional[datetime] = Field(None, description="Delivery timestamp")
    opened_at: Optional[datetime] = Field(None, description="First open timestamp")
    clicked_at: Optional[datetime] = Field(None, description="First click timestamp")
    bounce_reason: Optional[str] = Field(
        None, description="Bounce reason if applicable"
    )
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class EmailDeliveryService:
    """Service for delivering emails with tracking and retry logic."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the email delivery service."""
        self.api_key = api_key or get_env("SENDGRID_API_KEY")
        self.client = sendgrid.SendGridAPIClient(api_key=self.api_key)
        self.storage = get_storage_instance()

    async def send_email(
        self,
        template: EmailTemplate,
        personalization: EmailPersonalization,
        email_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Send an email using the configured template and personalization.

        Args:
            template: Rendered email template
            personalization: Email personalization data
            email_id: Optional custom email ID
            metadata: Additional metadata to store

        Returns:
            Email ID for tracking

        Raises:
            Exception: If email sending fails
        """
        email_id = email_id or str(uuid4())

        try:
            # Create delivery record
            delivery_record = EmailDeliveryRecord(
                email_id=email_id,
                user_id=personalization.user_email,  # Using email as user_id for now
                email_address=personalization.user_email,
                template_name=template.name,
                subject=template.subject,
                metadata=metadata or {},
            )

            # Store initial record
            await self._store_delivery_record(delivery_record)

            # Prepare SendGrid email
            mail = self._prepare_sendgrid_email(template, personalization, email_id)

            # Send email
            response = self.client.send(mail)

            if response.status_code in [200, 202]:
                # Update status to sent
                delivery_record.status = EmailStatus.SENT
                delivery_record.sent_at = datetime.utcnow()
                await self._store_delivery_record(delivery_record)

                logger.info(f"Email sent successfully: {email_id}")
                return email_id
            else:
                raise Exception(
                    f"SendGrid API error: {response.status_code} - {response.body}"
                )

        except Exception as e:
            # Update status to failed
            delivery_record.status = EmailStatus.FAILED
            delivery_record.bounce_reason = str(e)
            await self._store_delivery_record(delivery_record)

            logger.error(f"Failed to send email {email_id}: {str(e)}")
            raise

    def _prepare_sendgrid_email(
        self,
        template: EmailTemplate,
        personalization: EmailPersonalization,
        email_id: str,
    ) -> Mail:
        """Prepare SendGrid email object."""

        # Create email objects
        from_email = Email("reports@anthrasite.com", "Anthrasite Reports")
        to_email = Email(personalization.user_email, personalization.user_name)

        # Create content
        html_content = Content("text/html", template.html_content)

        # Create mail object
        mail = Mail(from_email, to_email, template.subject, html_content)

        # Add plain text content if available
        if template.text_content:
            mail.add_content(Content("text/plain", template.text_content))

        # Configure tracking
        tracking_settings = TrackingSettings()

        # Click tracking
        click_tracking = ClickTracking()
        click_tracking.enable = True
        click_tracking.enable_text = True
        tracking_settings.click_tracking = click_tracking

        # Open tracking
        open_tracking = OpenTracking()
        open_tracking.enable = True
        open_tracking.substitution_tag = "%open_tracking_pixel%"
        tracking_settings.open_tracking = open_tracking

        # Subscription tracking
        subscription_tracking = SubscriptionTracking()
        subscription_tracking.enable = True
        if personalization.unsubscribe_link:
            subscription_tracking.substitution_tag = personalization.unsubscribe_link
        tracking_settings.subscription_tracking = subscription_tracking

        mail.tracking_settings = tracking_settings

        # Add custom headers for tracking
        mail.add_header("X-Email-ID", email_id)
        mail.add_header("X-Template", template.name)

        return mail

    async def _store_delivery_record(self, record: EmailDeliveryRecord) -> None:
        """Store email delivery record in database."""
        try:
            query = """
                INSERT INTO email_deliveries
                (email_id, user_id, email_address, template_name, subject, status,
                 sent_at, delivered_at, opened_at, clicked_at, bounce_reason,
                 metadata, retry_count, max_retries)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (email_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    sent_at = EXCLUDED.sent_at,
                    delivered_at = EXCLUDED.delivered_at,
                    opened_at = EXCLUDED.opened_at,
                    clicked_at = EXCLUDED.clicked_at,
                    bounce_reason = EXCLUDED.bounce_reason,
                    metadata = EXCLUDED.metadata,
                    retry_count = EXCLUDED.retry_count
            """

            await self.storage.execute_query(
                query,
                record.email_id,
                record.user_id,
                record.email_address,
                record.template_name,
                record.subject,
                record.status.value,
                record.sent_at,
                record.delivered_at,
                record.opened_at,
                record.clicked_at,
                record.bounce_reason,
                json.dumps(record.metadata),
                record.retry_count,
                record.max_retries,
            )

        except Exception as e:
            logger.error(f"Failed to store delivery record: {str(e)}")

    async def handle_webhook_event(self, event_data: Dict) -> None:
        """
        Handle SendGrid webhook events for tracking.

        Args:
            event_data: Webhook event data from SendGrid
        """
        try:
            event_type = event_data.get("event")
            email_id = event_data.get("email_id") or event_data.get("sg_message_id")

            if not email_id:
                logger.warning("Received webhook event without email ID")
                return

            # Create event record
            event = EmailEvent(
                email_id=email_id,
                event_type=event_type,
                timestamp=datetime.fromtimestamp(event_data.get("timestamp", 0)),
                user_agent=event_data.get("useragent"),
                ip_address=event_data.get("ip"),
                url=event_data.get("url"),
                metadata=event_data,
            )

            # Store event
            await self._store_email_event(event)

            # Update delivery record status
            await self._update_delivery_status(email_id, event_type, event.timestamp)

        except Exception as e:
            logger.error(f"Failed to handle webhook event: {str(e)}")

    async def _store_email_event(self, event: EmailEvent) -> None:
        """Store email tracking event."""
        try:
            query = """
                INSERT INTO email_events
                (email_id, event_type, timestamp, user_agent, ip_address, url, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            await self.storage.execute_query(
                query,
                event.email_id,
                event.event_type,
                event.timestamp,
                event.user_agent,
                event.ip_address,
                event.url,
                json.dumps(event.metadata),
            )

        except Exception as e:
            logger.error(f"Failed to store email event: {str(e)}")

    async def _update_delivery_status(
        self, email_id: str, event_type: str, timestamp: datetime
    ) -> None:
        """Update delivery record status based on event."""
        try:
            status_updates = {
                "delivered": (EmailStatus.DELIVERED, "delivered_at"),
                "open": (EmailStatus.OPENED, "opened_at"),
                "click": (EmailStatus.CLICKED, "clicked_at"),
                "bounce": (EmailStatus.BOUNCED, None),
                "dropped": (EmailStatus.FAILED, None),
                "unsubscribe": (EmailStatus.UNSUBSCRIBED, None),
            }

            if event_type not in status_updates:
                return

            status, timestamp_field = status_updates[event_type]

            # Build update query
            if timestamp_field:
                query = f"""
                    UPDATE email_deliveries
                    SET status = $1, {timestamp_field} = $2
                    WHERE email_id = $3 AND {timestamp_field} IS NULL
                """
                await self.storage.execute_query(
                    query, status.value, timestamp, email_id
                )
            else:
                query = """
                    UPDATE email_deliveries
                    SET status = $1
                    WHERE email_id = $2
                """
                await self.storage.execute_query(query, status.value, email_id)

        except Exception as e:
            logger.error(f"Failed to update delivery status: {str(e)}")

    async def get_delivery_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        template_name: Optional[str] = None,
    ) -> Dict:
        """
        Get email delivery statistics.

        Args:
            start_date: Start date for stats
            end_date: End date for stats
            template_name: Filter by template name

        Returns:
            Dictionary with delivery statistics
        """
        try:
            conditions = []
            params = []
            param_count = 0

            if start_date:
                param_count += 1
                conditions.append(f"sent_at >= ${param_count}")
                params.append(start_date)

            if end_date:
                param_count += 1
                conditions.append(f"sent_at <= ${param_count}")
                params.append(end_date)

            if template_name:
                param_count += 1
                conditions.append(f"template_name = ${param_count}")
                params.append(template_name)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
                SELECT
                    COUNT(*) as total_sent,
                    COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
                    COUNT(CASE WHEN status = 'opened' THEN 1 END) as opened,
                    COUNT(CASE WHEN status = 'clicked' THEN 1 END) as clicked,
                    COUNT(CASE WHEN status = 'bounced' THEN 1 END) as bounced,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
                FROM email_deliveries
                {where_clause}
            """

            result = await self.storage.fetch_one(query, *params)

            if result:
                total = result["total_sent"] or 0
                return {
                    "total_sent": total,
                    "delivered": result["delivered"] or 0,
                    "opened": result["opened"] or 0,
                    "clicked": result["clicked"] or 0,
                    "bounced": result["bounced"] or 0,
                    "failed": result["failed"] or 0,
                    "delivery_rate": (
                        (result["delivered"] or 0) / total if total > 0 else 0
                    ),
                    "open_rate": (result["opened"] or 0) / total if total > 0 else 0,
                    "click_rate": (result["clicked"] or 0) / total if total > 0 else 0,
                    "bounce_rate": (result["bounced"] or 0) / total if total > 0 else 0,
                }

            return {
                "total_sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "bounced": 0,
                "failed": 0,
                "delivery_rate": 0,
                "open_rate": 0,
                "click_rate": 0,
                "bounce_rate": 0,
            }

        except Exception as e:
            logger.error(f"Failed to get delivery stats: {str(e)}")
            return {}

    async def retry_failed_emails(self, max_age_hours: int = 24) -> int:
        """
        Retry failed email deliveries.

        Args:
            max_age_hours: Maximum age of emails to retry

        Returns:
            Number of emails retried
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            query = """
                SELECT email_id, user_id, template_name, subject, metadata
                FROM email_deliveries
                WHERE status = 'failed'
                AND retry_count < max_retries
                AND sent_at >= $1
            """

            failed_emails = await self.storage.fetch_all(query, cutoff_time)

            retry_count = 0
            for email_record in failed_emails:
                try:
                    # Increment retry count
                    await self.storage.execute_query(
                        "UPDATE email_deliveries SET retry_count = retry_count + 1 WHERE email_id = $1",
                        email_record["email_id"],
                    )

                    # TODO: Re-queue email for sending
                    # This would typically involve adding to a message queue
                    retry_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to retry email {email_record['email_id']}: {str(e)}"
                    )

            return retry_count

        except Exception as e:
            logger.error(f"Failed to retry failed emails: {str(e)}")
            return 0


def get_email_delivery_service() -> EmailDeliveryService:
    """Get a configured email delivery service instance."""
    return EmailDeliveryService()
