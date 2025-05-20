#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Email Queue (06_email_queue.py)
Sends personalized emails via SendGrid with mockup attachments.

Usage:
    python bin/06_email_queue.py [--limit N] [--id BUSINESS_ID] [--dry-run] [--force]

Options:
    --limit N        Limit the number of emails to send (default: all)
    --id BUSINESS_ID Process only the specified business ID
    --dry-run        Run without actually sending emails
    --force          Force sending emails even if they've been sent before
"""

import os
import sys
import argparse
import json
import time
import base64
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from dotenv import load_dotenv
import concurrent.futures
import re
import requests
from datetime import datetime, timedelta
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import logging configuration first
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Import utility functions
from utils.io import DatabaseConnection, make_api_request, track_api_cost

# Try to import cost tracker
try:
    from utils.cost_tracker import log_cost, get_daily_cost, get_monthly_cost
except ImportError:
    # Define dummy functions if cost_tracker is not available
    def log_cost(service, operation, cost_dollars):
        pass

    def get_daily_cost():
        return 0.0

    def get_monthly_cost():
        return 0.0

# Load environment variables
load_dotenv()

# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_EMAILS", "5"))
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "leads@anthrasite.com")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Anthrasite Web Services")
DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", "50"))
BOUNCE_RATE_THRESHOLD = float(os.getenv("BOUNCE_RATE_THRESHOLD", "0.1"))  # 10% bounce rate threshold
COST_PER_EMAIL = float(os.getenv("COST_PER_EMAIL", "0.10"))  # $0.10 per email
EMAIL_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "etc",
    "email_template.html",
)


class SendGridEmailSender:
    """Sends emails via SendGrid API."""

    def __init__(self, api_key: str, from_email: str, from_name: str):
        """Initialize the SendGrid email sender.

        Args:
            api_key: SendGrid API key.
            from_email: Sender email address.
            from_name: Sender name.
        """
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.base_url = "https://api.sendgrid.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: str,
        mockup_image_url: Optional[str] = None,
        mockup_html: Optional[str] = None,
        is_dry_run: bool = False,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send an email via SendGrid.

        Args:
            to_email: Recipient email address.
            to_name: Recipient name.
            subject: Email subject.
            html_content: HTML content of the email.
            text_content: Plain text content of the email.
            mockup_image_url: URL to mockup image (optional).
            mockup_html: HTML code for mockup (optional).
            is_dry_run: If True, don't actually send the email.

        Returns:
            Tuple of (success, message_id, error_message).
        """
        if not self.api_key:
            return False, None, "SendGrid API key not provided"

        if is_dry_run:
            logger.info(f"[DRY RUN] Would send email to {to_name} <{to_email}>")
            return True, f"dry-run-{int(time.time())}", None

        # Prepare email payload
        payload = {
            "personalizations": [{"to": [{"email": to_email, "name": to_name}], "subject": subject}],
            "from": {"email": self.from_email, "name": self.from_name},
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
            "tracking_settings": {
                "click_tracking": {"enable": True, "enable_text": True},
                "open_tracking": {"enable": True},
            },
        }

        # Add mockup image as attachment if available
        if mockup_image_url:
            try:
                # Fetch image from URL
                response = requests.get(mockup_image_url, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()

                # Encode image as base64
                image_data = base64.b64encode(response.content).decode("utf-8")

                # Add attachment
                if "attachments" not in payload:
                    payload["attachments"] = []

                payload["attachments"].append(
                    {
                        "content": image_data,
                        "type": "image/png",
                        "filename": "website-mockup.png",
                        "disposition": "attachment",
                    }
                )

            except Exception as e:
                logger.warning(f"Error attaching mockup image: {e}")

        try:
            # Send email
            response = requests.post(
                f"{self.base_url}/mail/send",
                headers=self.headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )

            # Check for success
            if response.status_code == 202:
                # Extract message ID from headers
                message_id = response.headers.get("X-Message-Id")

                # Log cost
                log_cost("sendgrid", "email", COST_PER_EMAIL)

                return True, message_id, None

            else:
                error_message = f"SendGrid API error: {response.status_code} - {response.text}"
                logger.error(error_message)
                return False, None, error_message

        except requests.exceptions.RequestException as e:
            error_message = f"Error sending email: {str(e)}"
            logger.error(error_message)
            return False, None, error_message

        except Exception as e:
            error_message = f"Unexpected error sending email: {str(e)}"
            logger.error(error_message)
            return False, None, error_message

    def get_bounce_rate(self, days: int = 7) -> float:
        """Get bounce rate for the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Bounce rate as a float (0.0 to 1.0).
        """
        if not self.api_key:
            return 0.0

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Format dates for API
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Get global stats
            response = requests.get(
                f"{self.base_url}/stats?start_date={start_date_str}&end_date={end_date_str}&aggregated_by=day",
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()

            # Parse response
            stats = response.json()

            # Calculate bounce rate
            total_requests = 0
            total_bounces = 0

            for day in stats:
                metrics = day.get("stats", [{}])[0].get("metrics", {})
                total_requests += metrics.get("requests", 0)
                total_bounces += metrics.get("bounces", 0)

            # Calculate bounce rate
            bounce_rate = total_bounces / total_requests if total_requests > 0 else 0.0

            logger.info(f"Bounce rate for the last {days} days: {bounce_rate:.2%}")
            return bounce_rate

        except Exception as e:
            logger.error(f"Error getting bounce rate: {e}")
            return 0.0

    def get_daily_sent_count(self) -> int:
        """Get number of emails sent today.

        Returns:
            Number of emails sent today.
        """
        if not self.api_key:
            return 0

        try:
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")

            # Get global stats for today
            response = requests.get(
                f"{self.base_url}/stats?start_date={today}&end_date={today}",
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()

            # Parse response
            stats = response.json()

            # Get sent count
            sent_count = 0

            for day in stats:
                metrics = day.get("stats", [{}])[0].get("metrics", {})
                sent_count += metrics.get("requests", 0)

            logger.info(f"Emails sent today: {sent_count}")
            return sent_count

        except Exception as e:
            logger.error(f"Error getting daily sent count: {e}")
            return 0


def load_email_template() -> str:
    """Load email template from file.

    Returns:
        Email template as string.
    """
    try:
        if os.path.exists(EMAIL_TEMPLATE_PATH):
            with open(EMAIL_TEMPLATE_PATH, "r") as f:
                return f.read()

        # Return default template if file not found
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Website Improvement Proposal</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { text-align: center; margin-bottom: 20px; }
                .logo { max-width: 150px; }
                .mockup { max-width: 100%; margin: 20px 0; border: 1px solid #ddd; }
                .cta-button { display: inline-block; background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; }
                .footer { margin-top: 30px; font-size: 12px; color: #777; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Website Improvement Proposal for {{business_name}}</h1>
                </div>
                
                <p>Hello {{contact_name}},</p>
                
                <p>I noticed your website at <a href="{{business_website}}">{{business_website}}</a> and wanted to reach out with some ideas for improvement.</p>
                
                <p>Our team at Anthrasite Web Services specializes in helping {{business_category}} businesses like yours improve their online presence and attract more customers.</p>
                
                <p>We've created a custom mockup showing how your website could look with our improvements:</p>
                
                <p><strong>Key improvements we're suggesting:</strong></p>
                <ul>
                    {{#each improvements}}
                    <li>{{this}}</li>
                    {{/each}}
                </ul>
                
                <p>I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?</p>
                
                <p><a href="https://calendly.com/anthrasite/website-consultation" class="cta-button">Schedule a Free Consultation</a></p>
                
                <p>Best regards,<br>
                {{sender_name}}<br>
                Anthrasite Web Services<br>
                {{sender_email}}<br>
                {{sender_phone}}</p>
                
                <div class="footer">
                    <p>This email was sent to {{to_email}}. If you'd prefer not to receive these emails, you can <a href="{{unsubscribe_link}}">unsubscribe</a>.</p>
                </div>
            </div>
        </body>
        </html>
        """

    except Exception as e:
        logger.error(f"Error loading email template: {e}")
        return "<html><body><p>Hello {{contact_name}},</p><p>We have some ideas for improving your website.</p></body></html>"


def get_businesses_for_email(
    limit: Optional[int] = None, business_id: Optional[int] = None, force: bool = False
) -> List[Dict]:
    """Get list of businesses for email sending.

    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
        force: If True, include businesses that already have emails sent.

    Returns:
        List of dictionaries containing business information.
    """
    try:
        with DatabaseConnection() as cursor:
            # Build query based on parameters
            query_parts = ["SELECT b.*, f.*, m.* FROM businesses b"]
            query_parts.append("LEFT JOIN features f ON b.id = f.business_id")
            query_parts.append("LEFT JOIN mockups m ON b.id = m.business_id")
            query_parts.append("LEFT JOIN emails e ON b.id = e.business_id")

            where_clauses = []
            params = []

            # Add business ID filter if specified
            if business_id:
                where_clauses.append("b.id = ?")
                params.append(business_id)

            # Add status filter
            where_clauses.append("b.status = 'active'")

            # Add score filter
            where_clauses.append("b.score IS NOT NULL")

            # Add mockup filter
            where_clauses.append("m.id IS NOT NULL")

            # Add email filter if not forcing
            if not force:
                where_clauses.append("e.id IS NULL")

            # Combine where clauses
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))

            # Add order by score (highest first)
            query_parts.append("ORDER BY b.score DESC")

            # Add limit if specified
            if limit:
                query_parts.append(f"LIMIT {limit}")

            # Execute query
            query = " ".join(query_parts)
            cursor.execute(query, params)

            businesses = cursor.fetchall()

        logger.info(f"Found {len(businesses)} businesses for email sending")
        return businesses

    except Exception as e:
        logger.error(f"Error getting businesses for email sending: {e}")
        return []


def save_email_record(
    business_id: int,
    to_email: str,
    to_name: str,
    subject: str,
    message_id: Optional[str],
    status: str,
    error_message: Optional[str] = None,
) -> bool:
    """Save email record to database.

    Args:
        business_id: Business ID.
        to_email: Recipient email address.
        to_name: Recipient name.
        subject: Email subject.
        message_id: SendGrid message ID.
        status: Email status (sent, failed).
        error_message: Error message if failed.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with DatabaseConnection() as cursor:
            # Insert email record
            cursor.execute(
                """
                INSERT INTO emails 
                (business_id, to_email, to_name, subject, message_id, status, error_message, sent_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    business_id,
                    to_email,
                    to_name,
                    subject,
                    message_id,
                    status,
                    error_message,
                ),
            )

        logger.info(f"Saved email record for business ID {business_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving email record for business ID {business_id}: {e}")
        return False


def generate_email_content(business: Dict, template: str) -> Tuple[str, str, str]:
    """Generate email content for a business.

    Args:
        business: Business data.
        template: Email template.

    Returns:
        Tuple of (subject, html_content, text_content).
    """
    # Extract business information
    business_id = business["id"]
    business_name = business.get("name", "")
    business_category = business.get("category", "")
    business_website = business.get("website", "")
    contact_name = business.get("contact_name", "Owner")  # Default to "Owner" if contact name not available

    # Extract score information
    score = business.get("score", 0)
    score_details = business.get("score_details", "[]")

    if isinstance(score_details, str):
        try:
            score_details = json.loads(score_details)
        except json.JSONDecodeError:
            score_details = []

    # Generate improvements list based on score details
    improvements = []

    for rule in score_details:
        if isinstance(rule, dict) and "description" in rule and "score_adjustment" in rule:
            if rule["score_adjustment"] > 0:
                improvements.append(rule["description"])

    # Limit to top 5 improvements
    improvements = improvements[:5]

    # Add default improvements if none found
    if not improvements:
        improvements = [
            "Improve website loading speed",
            "Update to a modern, mobile-friendly design",
            "Add clear call-to-action buttons",
            "Optimize for search engines",
            "Improve user experience and navigation",
        ]

    # Prepare template variables
    template_vars = {
        "business_id": business_id,
        "business_name": business_name,
        "business_category": business_category,
        "business_website": business_website,
        "contact_name": contact_name,
        "score": score,
        "improvements": improvements,
        "sender_name": SENDGRID_FROM_NAME,
        "sender_email": SENDGRID_FROM_EMAIL,
        "sender_phone": "+1 (555) 123-4567",  # Example phone number
        "to_email": business.get("email", ""),
        "unsubscribe_link": "https://anthrasite.com/unsubscribe?email={{to_email}}",
    }

    # Generate subject line
    subject = f"Website Improvement Proposal for {business_name}"

    # Replace template variables
    html_content = template
    text_content = "Website Improvement Proposal\n\n"

    for key, value in template_vars.items():
        placeholder = "{{" + key + "}}"

        if isinstance(value, list):
            # Handle lists (like improvements)
            list_html = ""
            list_text = ""

            for item in value:
                list_html += f"<li>{html.escape(str(item))}</li>"
                list_text += f"- {item}\n"

            # Replace {{#each improvements}} ... {{/each}} with list items
            each_pattern = r"{{#each " + key + r"}}(.*?){{/each}}"
            html_content = re.sub(each_pattern, list_html, html_content, flags=re.DOTALL)

            # Add list to text content
            text_content += f"\n{key.upper()}:\n{list_text}\n"
        else:
            # Handle regular variables
            html_content = html_content.replace(placeholder, html.escape(str(value)))

            # Add key-value to text content for important fields
            if key in ["business_name", "contact_name", "business_website"]:
                text_content += f"{key.replace('_', ' ').title()}: {value}\n"

    # Add more content to text version
    text_content += "\nWe've created a custom mockup showing how your website could look with our improvements.\n\n"
    text_content += (
        "I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?\n\n"
    )
    text_content += "Schedule a free consultation: https://calendly.com/anthrasite/website-consultation\n\n"
    text_content += f"Best regards,\n{SENDGRID_FROM_NAME}\nAnthrasite Web Services\n{SENDGRID_FROM_EMAIL}\n"

    return subject, html_content, text_content


def send_business_email(
    business: Dict,
    email_sender: SendGridEmailSender,
    template: str,
    is_dry_run: bool = False,
) -> bool:
    """Send email for a business.

    Args:
        business: Business data.
        email_sender: SendGridEmailSender instance.
        template: Email template.
        is_dry_run: If True, don't actually send the email.

    Returns:
        True if successful, False otherwise.
    """
    business_id = business["id"]
    business_name = business.get("name", "")
    business_email = business.get("email", "")
    contact_name = business.get("contact_name", "Owner")

    # Check if business has an email address
    if not business_email:
        logger.warning(f"Business ID {business_id} ({business_name}) has no email address")
        return False

    # Get mockup information
    mockup_url = business.get("mockup_url")
    mockup_html = business.get("mockup_html")

    # Generate email content
    subject, html_content, text_content = generate_email_content(business, template)

    logger.info(f"Sending email to {contact_name} <{business_email}> for business ID {business_id}")

    # Send email
    success, message_id, error = email_sender.send_email(
        to_email=business_email,
        to_name=contact_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        mockup_image_url=mockup_url,
        mockup_html=mockup_html,
        is_dry_run=is_dry_run,
    )

    # Save email record
    status = "sent" if success else "failed"
    save_email_record(
        business_id=business_id,
        to_email=business_email,
        to_name=contact_name,
        subject=subject,
        message_id=message_id,
        status=status,
        error_message=error,
    )

    return success


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Send personalized emails via SendGrid")
    parser.add_argument("--limit", type=int, help="Limit the number of emails to send")
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument("--dry-run", action="store_true", help="Run without actually sending emails")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sending emails even if they've been sent before",
    )
    args = parser.parse_args()

    # Check API key
    if not SENDGRID_API_KEY and not args.dry_run:
        logger.error("SendGrid API key not provided")
        return 1

    # Initialize email sender
    email_sender = SendGridEmailSender(
        api_key=SENDGRID_API_KEY,
        from_email=SENDGRID_FROM_EMAIL,
        from_name=SENDGRID_FROM_NAME,
    )

    # Check bounce rate
    bounce_rate = email_sender.get_bounce_rate()
    if bounce_rate > BOUNCE_RATE_THRESHOLD and not args.dry_run:
        logger.error(f"Bounce rate ({bounce_rate:.2%}) exceeds threshold ({BOUNCE_RATE_THRESHOLD:.2%})")
        return 1

    # Check daily email limit
    daily_sent = email_sender.get_daily_sent_count()
    if daily_sent >= DAILY_EMAIL_LIMIT and not args.dry_run:
        logger.error(f"Daily email limit reached ({daily_sent}/{DAILY_EMAIL_LIMIT})")
        return 1

    # Calculate remaining emails for today
    remaining_emails = DAILY_EMAIL_LIMIT - daily_sent

    # Load email template
    template = load_email_template()

    # Get businesses for email sending
    businesses = get_businesses_for_email(
        limit=min(args.limit, remaining_emails) if args.limit and not args.dry_run else args.limit,
        business_id=args.id,
        force=args.force,
    )

    if not businesses:
        logger.warning("No businesses found for email sending")
        return 0

    logger.info(f"Sending emails for {len(businesses)} businesses")

    # Process businesses
    success_count = 0
    error_count = 0

    for business in businesses:
        try:
            success = send_business_email(
                business=business,
                email_sender=email_sender,
                template=template,
                is_dry_run=args.dry_run,
            )

            if success:
                success_count += 1
            else:
                error_count += 1

        except Exception as e:
            logger.error(f"Error processing business ID {business['id']}: {e}")
            error_count += 1

    logger.info(f"Email sending completed. Success: {success_count}, Errors: {error_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
