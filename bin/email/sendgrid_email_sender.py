#!/usr/bin/env python
"""
SendGrid Email Sender
------------------
This module provides a SendGrid-based email sender implementation for the
Anthrasite LeadFactory platform. It handles email sending, tracking, and
metrics collection for bounce and spam rates.

Usage:
    from bin.email.sendgrid_email_sender import SendGridEmailSender

    sender = SendGridEmailSender()
    sender.send_email(to="client@example.com", subject="Lead Factory Report",
                     content="<p>Your report is ready.</p>")
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail,
    Attachment,
    FileContent,
    FileName,
    FileType,
    Disposition,
    Content,
    Email,
    To,
    Cc,
    Bcc,
)

# Add project root to path using pathlib for better compatibility
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import dependencies after path setup
from bin.metrics import metrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "sendgrid_email_sender.log")),
    ],
)
logger = logging.getLogger("sendgrid_email_sender")


class SendGridEmailSender:
    """SendGrid-based email sender implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        pool: str = "shared",
        subuser: str = "prod",
    ):
        """Initialize SendGrid email sender.

        Args:
            api_key: SendGrid API key (defaults to SENDGRID_API_KEY env var)
            from_email: Sender email address (defaults to SENDGRID_FROM_EMAIL env var)
            from_name: Sender name (defaults to SENDGRID_FROM_NAME env var)
            pool: IP pool to use (shared or dedicated)
            subuser: SendGrid subuser (prod or test)
        """
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        self.from_email = from_email or os.environ.get(
            "SENDGRID_FROM_EMAIL", "noreply@anthrasite.com"
        )
        self.from_name = from_name or os.environ.get(
            "SENDGRID_FROM_NAME", "Anthrasite Lead Factory"
        )
        self.pool = pool
        self.subuser = subuser

        if not self.api_key:
            logger.warning("SendGrid API key not provided")

        # Initialize SendGrid client
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None

        # Start metrics collection thread
        self._start_metrics_collection()

        logger.info(
            f"SendGrid email sender initialized (pool={pool}, subuser={subuser})"
        )

    def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        custom_args: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send an email using SendGrid.

        Args:
            to: Recipient email address
            subject: Email subject
            content: Email content (HTML)
            attachments: List of attachment dictionaries with keys:
                - content: Base64-encoded content
                - filename: Attachment filename
                - type: MIME type (default: application/pdf)
                - disposition: Attachment disposition (default: attachment)
            cc: List of CC recipients
            bcc: List of BCC recipients
            categories: List of categories for tracking
            custom_args: Custom arguments for tracking

        Returns:
            Dictionary with send status and details
        """
        if not self.client:
            error_msg = "SendGrid client not initialized (missing API key)"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        try:
            # Create message
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=to,
                subject=subject,
                html_content=content,
            )

            # Add CC recipients
            if cc:
                for cc_email in cc:
                    message.add_cc(cc_email)

            # Add BCC recipients
            if bcc:
                for bcc_email in bcc:
                    message.add_bcc(bcc_email)

            # Add categories
            if categories:
                for category in categories:
                    message.add_category(category)

            # Add custom arguments
            if custom_args:
                for key, value in custom_args.items():
                    message.add_custom_arg(key, value)

            # Add IP pool
            if self.pool:
                message.ip_pool_name = self.pool

            # Add attachments
            if attachments:
                for attachment_data in attachments:
                    attachment = Attachment()
                    attachment.file_content = FileContent(attachment_data["content"])
                    attachment.file_name = FileName(attachment_data["filename"])
                    attachment.file_type = FileType(
                        attachment_data.get("type", "application/pdf")
                    )
                    attachment.disposition = Disposition(
                        attachment_data.get("disposition", "attachment")
                    )
                    message.add_attachment(attachment)

            # Send email
            response = self.client.send(message)

            # Log success
            logger.info(
                f"Email sent to {to} (subject: {subject}, status: {response.status_code})"
            )

            # Update metrics
            metrics.increment_email_sent(1, pool=self.pool, subuser=self.subuser)

            return {
                "status": "success",
                "message": "Email sent successfully",
                "response": {
                    "status_code": response.status_code,
                    "body": response.body.decode("utf-8") if response.body else None,
                    "headers": dict(response.headers) if response.headers else None,
                },
            }

        except Exception as e:
            # Log error
            logger.exception(f"Error sending email to {to}: {str(e)}")

            return {"status": "error", "message": f"Error sending email: {str(e)}"}

    def get_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        aggregated_by: str = "day",
    ) -> Dict[str, Any]:
        """Get email statistics from SendGrid.

        Args:
            start_date: Start date for statistics (default: 30 days ago)
            end_date: End date for statistics (default: today)
            aggregated_by: Aggregation period (day, week, month)

        Returns:
            Dictionary with statistics
        """
        if not self.client:
            error_msg = "SendGrid client not initialized (missing API key)"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        try:
            # Set default dates if not provided
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)

            if not end_date:
                end_date = datetime.now()

            # Format dates for SendGrid API
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Build query parameters
            query_params = {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "aggregated_by": aggregated_by,
            }

            # Add subuser filter if specified
            if self.subuser:
                query_params["subuser"] = self.subuser

            # Get statistics
            response = self.client.client.stats.get(query_params=query_params)

            # Parse response
            stats_data = json.loads(response.body)

            # Calculate metrics
            total_sent = 0
            total_delivered = 0
            total_bounces = 0
            total_spam_reports = 0

            for day_stats in stats_data:
                stats = day_stats.get("stats", [{}])[0].get("metrics", {})
                total_sent += stats.get("requests", 0)
                total_delivered += stats.get("delivered", 0)
                total_bounces += stats.get("bounces", 0)
                total_spam_reports += stats.get("spam_reports", 0)

            # Calculate rates
            bounce_rate = total_bounces / total_sent if total_sent > 0 else 0
            spam_rate = (
                total_spam_reports / total_delivered if total_delivered > 0 else 0
            )

            # Update metrics
            metrics.update_bounce_rate(
                bounce_rate, pool=self.pool, subuser=self.subuser
            )
            metrics.update_spam_rate(spam_rate, pool=self.pool, subuser=self.subuser)

            logger.info(
                f"Email stats retrieved: bounce_rate={bounce_rate:.4f}, spam_rate={spam_rate:.4f}"
            )

            return {
                "status": "success",
                "data": stats_data,
                "summary": {
                    "total_sent": total_sent,
                    "total_delivered": total_delivered,
                    "total_bounces": total_bounces,
                    "total_spam_reports": total_spam_reports,
                    "bounce_rate": bounce_rate,
                    "spam_rate": spam_rate,
                },
            }

        except Exception as e:
            # Log error
            logger.exception(f"Error getting email stats: {str(e)}")

            return {
                "status": "error",
                "message": f"Error getting email stats: {str(e)}",
            }

    def switch_ip_pool(self, new_pool: str) -> bool:
        """Switch to a different IP pool.

        Args:
            new_pool: New IP pool name

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Switching IP pool from {self.pool} to {new_pool}")
        self.pool = new_pool
        return True

    def _start_metrics_collection(self):
        """Start a background thread to collect metrics periodically."""

        def collect_metrics():
            while True:
                try:
                    # Get email stats and update metrics
                    self.get_stats()
                except Exception as e:
                    logger.error(f"Error collecting email metrics: {str(e)}")

                # Sleep for 1 hour
                time.sleep(3600)

        # Start thread
        thread = threading.Thread(target=collect_metrics, daemon=True)
        thread.start()
        logger.info("Started metrics collection thread")


# Example usage
if __name__ == "__main__":
    # Create sender
    sender = SendGridEmailSender()

    # Send test email
    result = sender.send_email(
        to="test@example.com",
        subject="Test Email",
        content="<p>This is a test email from the SendGrid Email Sender.</p>",
    )

    # Get stats
    stats = sender.get_stats()
