"""
Email generation and sending module for LeadFactory.

This module provides functionality to generate and send emails to businesses.
"""

import argparse
import base64
import html
import json
import logging
import os
import re
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, TypeVar, Union, cast

import requests

from leadfactory.config import load_config

# Use typing.Type for creating a type variable that can accept multiple class types
# This avoids type checking errors when assigning different class types to the same variable
T = TypeVar("T")


# Define our own base connection class for testing scenarios
class _EmailDBConnectionBase:
    def __init__(self, db_path: Optional[str] = None) -> None:
        pass

    def __enter__(self) -> "_EmailDBConnectionBase":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def execute(self, *args: Any, **kwargs: Any) -> None:
        pass

    def fetchall(self) -> list[Any]:
        return []

    def fetchone(self) -> Optional[Any]:
        return None

    def commit(self) -> None:
        pass


# Type variable for our database connection class
EmailDBConnection: Any = None

# Try to import the real database connection class
try:
    from leadfactory.utils.io import DatabaseConnection

    EmailDBConnection = DatabaseConnection  # Use the real one if available
except ImportError:
    EmailDBConnection = _EmailDBConnectionBase  # Use our base class if import fails

# Import logging utilities with conditional imports for testing
has_logger = False
try:
    from leadfactory.utils.logging_config import get_logger

    has_logger = True
except ImportError:
    # Dummy implementation only created if the import fails
    pass

# Define dummy get_logger only if needed
if not has_logger:

    def get_logger(name: str) -> logging.Logger:
        import logging

        return logging.getLogger(name)


# Debug flag - set to True to enable debug logging
DEBUG = True

# Load environment variables
load_config()

# Set up logging
logger = get_logger(__name__)

# Global flag for dry run mode
DRY_RUN = False


def is_valid_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        bool: True if email is valid, False otherwise
    """
    # Basic email validation pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


# Define the log_cost function at the module level to ensure it's available
# This avoids attribute errors when checking for its existence
def log_cost(
    service: str,
    operation: str,
    cost_dollars: float,
    tier: int = 1,
    business_id: Optional[int] = None,
) -> None:
    """Dummy implementation of log_cost for when the real one is not available."""
    pass


# Import cost tracker functions with a more direct approach for Python 3.9 compatibility
# Always define our own versions first, then try to import the real ones


# Our dummy implementations
def get_daily_cost(service: Optional[str] = None) -> float:
    return 0.0


def get_monthly_cost(service: Optional[str] = None) -> float:
    return 0.0


# Try to import the real implementations without risking attribute errors
try:
    # Import the module itself first
    from leadfactory.cost import cost_tracker as cost_tracker_module

    # Use getattr with fallbacks to safely access attributes
    # This avoids the "no attribute" errors that can happen with direct imports
    get_daily_cost = getattr(cost_tracker_module, "get_daily_cost", get_daily_cost)
    get_monthly_cost = getattr(
        cost_tracker_module, "get_monthly_cost", get_monthly_cost
    )

    # For log_cost, keep using our own implementation if it doesn't exist
    if hasattr(cost_tracker_module, "log_cost"):
        log_cost = cost_tracker_module.log_cost
    # If log_cost doesn't exist in the module, we keep our own implementation

except ImportError:
    # If the module import fails entirely, we keep using our own implementations
    # This will happen during testing or if the module isn't available
    pass

# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_EMAILS", "5"))
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "leads@anthrasite.com")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Anthrasite Web Services")
DAILY_EMAIL_LIMIT = int(os.getenv("DAILY_EMAIL_LIMIT", "50"))
BOUNCE_RATE_THRESHOLD = float(
    os.getenv("BOUNCE_RATE_THRESHOLD", "0.02")
)  # 2% bounce rate threshold
SPAM_RATE_THRESHOLD = float(
    os.getenv("SPAM_RATE_THRESHOLD", "0.001")
)  # 0.1% spam rate threshold
COST_PER_EMAIL = float(os.getenv("COST_PER_EMAIL", "0.10"))  # $0.10 per email
MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", "250"))  # $250 monthly budget

# SendGrid IP/Sub-user configuration
SENDGRID_IP_POOL_NAMES = os.getenv(
    "SENDGRID_IP_POOL_NAMES", "primary,secondary,tertiary"
).split(",")
SENDGRID_SUBUSER_NAMES = os.getenv(
    "SENDGRID_SUBUSER_NAMES", "primary,secondary,tertiary"
).split(",")
CURRENT_IP_POOL_INDEX = int(os.getenv("CURRENT_IP_POOL_INDEX", "0"))
CURRENT_SUBUSER_INDEX = int(os.getenv("CURRENT_SUBUSER_INDEX", "0"))
EMAIL_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent.joinpath("etc", "email_template.html")
)


class SendGridEmailSender:
    """Sends emails via SendGrid API."""

    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str,
        ip_pool: str = None,
        subuser: str = None,
    ):
        """Initialize the SendGrid email sender.
        Args:
            api_key: SendGrid API key.
            from_email: Sender email address.
            from_name: Sender name.
            ip_pool: Optional IP pool name to use for sending emails.
            subuser: Optional subuser name to use for sending emails.
        """
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.ip_pool = ip_pool
        self.subuser = subuser
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
    ) -> tuple[bool, Optional[str], Optional[str]]:
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
            tuple of (success, message_id, error_message).
        """
        if is_dry_run:
            logger.info(f"Dry run: would send email to {to_email}")
            return True, "dry-run-message-id", None

        # Validate inputs
        if not is_valid_email(to_email):
            error_msg = f"Invalid email address: {to_email}"
            logger.error(error_msg)
            return False, None, error_msg

        if not all([subject, html_content, text_content]):
            error_msg = "Missing required email content"
            logger.error(error_msg)
            return False, None, error_msg

        # Define unsubscribe tracking parameters
        # We'll use the unsubscribe handler that we'll implement later
        unsubscribe_url = "https://app.anthrasite.com/unsubscribe"

        # Build the email payload for SendGrid
        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email, "name": to_name}],
                    "subject": subject,
                    "custom_args": {"email": to_email},  # For tracking
                }
            ],
            "from": {"email": self.from_email, "name": self.from_name},
            "reply_to": {"email": self.from_email, "name": self.from_name},
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
            "tracking_settings": {
                "click_tracking": {"enable": True, "enable_text": True},
                "open_tracking": {"enable": True},
                "subscription_tracking": {
                    "enable": True,
                    "substitution_tag": "{unsubscribe}",
                    "url": unsubscribe_url,
                    "html": f'<a href="{unsubscribe_url}?email={to_email}">Unsubscribe</a>',
                    "text": f"Unsubscribe: {unsubscribe_url}?email={to_email}",
                },
            },
            "mail_settings": {
                "bypass_list_management": {"enable": False},
                "footer": {"enable": True},
                "sandbox_mode": {"enable": is_dry_run},
            },
        }

        # Add IP pool if specified
        if self.ip_pool:
            payload["ip_pool_name"] = self.ip_pool

        # Add a category for tracking
        payload["categories"] = ["lead-generation"]

        # Add mockup attachment if provided
        if mockup_image_url:
            try:
                # Download the mockup image
                response = requests.get(mockup_image_url, timeout=DEFAULT_TIMEOUT)
                if response.status_code == 200:
                    # Encode the image as base64
                    image_content = base64.b64encode(response.content).decode()
                    # Add as attachment
                    if "attachments" not in payload:
                        payload["attachments"] = []
                    payload["attachments"].append(
                        {
                            "content": image_content,
                            "type": "image/png",
                            "filename": "website-mockup.png",
                            "disposition": "attachment",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to attach mockup image: {e}")

        # Send the email via SendGrid API
        try:
            url = f"{self.base_url}/mail/send"

            # Add subuser to headers if specified
            headers = self.headers.copy()
            if self.subuser:
                headers["On-Behalf-Of"] = self.subuser

            # Send the request to SendGrid
            response = requests.post(
                url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT
            )

            # Check for success
            if response.status_code in (200, 201, 202):
                # Extract message ID from headers
                message_id = response.headers.get("X-Message-Id")
                logger.info(f"Email sent successfully to {to_email} (ID: {message_id})")
                return True, message_id, None
            else:
                # Handle error
                error_msg = (
                    f"Failed to send email: {response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                return False, None, error_msg
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            logger.exception(error_msg)
            return False, None, error_msg

    def get_bounce_rate(
        self, days: int = 7, ip_pool: str = None, subuser: str = None
    ) -> float:
        """Get bounce rate for the last N days.

        Args:
            days: Number of days to look back.
            ip_pool: Optional IP pool name to filter stats.
            subuser: Optional subuser name to filter stats.

        Returns:
            Bounce rate as a float (0.0 to 1.0).
        """
        try:
            # Calculate start and end dates
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Build the URL with query parameters
            url = f"{self.base_url}/stats"
            params = {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "aggregated_by": "day",
            }

            # Add optional filters
            if ip_pool:
                params["ip_pool_name"] = ip_pool
            if subuser:
                url = f"{self.base_url}/subusers/{subuser}/stats"

            # Get the stats from SendGrid
            response = requests.get(
                url, headers=self.headers, params=params, timeout=DEFAULT_TIMEOUT
            )

            # Check for success
            if response.status_code == 200:
                data = response.json()
                if not data:
                    return 0.0

                # Calculate totals
                total_requests = 0
                total_bounces = 0
                for day in data:
                    metrics = day.get("stats", [{}])[0].get("metrics", {})
                    total_requests += metrics.get("requests", 0)
                    total_bounces += metrics.get("bounces", 0)

                # Calculate bounce rate
                if total_requests > 0:
                    return float(total_bounces) / float(total_requests)
                else:
                    return 0.0
            else:
                logger.error(
                    f"Failed to get bounce rate: {response.status_code} - {response.text}"
                )
                return 0.0
        except Exception as e:
            logger.exception(f"Error getting bounce rate: {str(e)}")
            return 0.0

    def get_spam_rate(
        self, days: int = 7, ip_pool: str = None, subuser: str = None
    ) -> float:
        """Get spam complaint rate for the last N days.

        Args:
            days: Number of days to look back.
            ip_pool: Optional IP pool name to filter stats.
            subuser: Optional subuser name to filter stats.

        Returns:
            Spam complaint rate as a float (0.0 to 1.0).
        """
        try:
            # Calculate start and end dates
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Build the URL with query parameters
            url = f"{self.base_url}/stats"
            params = {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "aggregated_by": "day",
            }

            # Add optional filters
            if ip_pool:
                params["ip_pool_name"] = ip_pool
            if subuser:
                url = f"{self.base_url}/subusers/{subuser}/stats"

            # Get the stats from SendGrid
            response = requests.get(
                url, headers=self.headers, params=params, timeout=DEFAULT_TIMEOUT
            )

            # Check for success
            if response.status_code == 200:
                data = response.json()
                if not data:
                    return 0.0

                # Calculate totals
                total_requests = 0
                total_spam_reports = 0
                for day in data:
                    metrics = day.get("stats", [{}])[0].get("metrics", {})
                    total_requests += metrics.get("requests", 0)
                    total_spam_reports += metrics.get("spam_reports", 0)

                # Calculate spam rate
                if total_requests > 0:
                    return float(total_spam_reports) / float(total_requests)
                else:
                    return 0.0
            else:
                logger.error(
                    f"Failed to get spam rate: {response.status_code} - {response.text}"
                )
                return 0.0
        except Exception as e:
            logger.exception(f"Error getting spam rate: {str(e)}")
            return 0.0

    def get_daily_sent_count(self) -> int:
        """Get number of emails sent today.

        Returns:
            Number of emails sent today.
        """
        try:
            # Get today's date
            today = datetime.now().date()
            today_str = today.strftime("%Y-%m-%d")

            # Build the URL with query parameters
            url = f"{self.base_url}/stats"
            params = {
                "start_date": today_str,
                "end_date": today_str,
                "aggregated_by": "day",
            }

            # Get the stats from SendGrid
            response = requests.get(
                url, headers=self.headers, params=params, timeout=DEFAULT_TIMEOUT
            )

            # Check for success
            if response.status_code == 200:
                data = response.json()
                if not data:
                    return 0

                # Get the requests count for today
                try:
                    requests_count = (
                        data[0]
                        .get("stats", [{}])[0]
                        .get("metrics", {})
                        .get("requests", 0)
                    )
                    return int(requests_count)
                except (IndexError, KeyError, TypeError):
                    return 0
            else:
                logger.error(
                    f"Failed to get daily sent count: {response.status_code} - {response.text}"
                )
                return 0
        except Exception as e:
            logger.exception(f"Error getting daily sent count: {str(e)}")
            return 0


def load_email_template() -> str:
    """Load email template from file.

    Returns:
        Email template as string.
    """
    try:
        # Load the template file
        with open(EMAIL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()
        return template
    except Exception as e:
        logger.exception(f"Error loading email template: {str(e)}")
        # Fallback template
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anthrasite Web Services</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        </head>
        <body>
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <h1 style="color: #333;">Anthrasite Web Services</h1>
                </div>

                <p>Hello {{name}},</p>

                <p>We noticed that {{business_name}} doesn't have a modern website that showcases your business effectively.</p>

                <p>We've created a free mockup of what your website could look like. No strings attached, just a demonstration of what we can do for you.</p>

                <p>Our services include:</p>
                <ul>
                    <li>Professional website design</li>
                    <li>Mobile optimization</li>
                    <li>SEO to help customers find you</li>
                    <li>Easy content management</li>
                </ul>

                <p>Check out your free mockup attached to this email.</p>

                <p>If you're interested in learning more, reply to this email or call us at (555) 123-4567.</p>

                <p>Best regards,<br>
                The Anthrasite Team</p>

                <div style="font-size: 12px; color: #999; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px;">
                    <p>This is a one-time email. {{unsubscribe}}</p>
                    <p>Anthrasite Web Services, 123 Tech Way, San Francisco, CA 94107</p>
                </div>
            </div>
        </body>
        </html>
        """


def get_businesses_for_email(
    limit: Optional[int] = None, business_id: Optional[int] = None, force: bool = False
) -> list[dict]:
    """Get list of businesses for email sending.

    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
        force: If True, include businesses that already have emails sent.

    Returns:
        list of dictionaries containing business information.
    """
    try:
        # Connect to the database
        with EmailDBConnection() as conn:
            # Build the query
            query = """
            SELECT b.id, b.name, b.email, b.phone, b.address, b.city, b.state, b.zip_code,
                   b.website, b.mockup_url, b.contact_name, b.score, b.notes
            FROM businesses b
            LEFT JOIN emails e ON b.id = e.business_id
            WHERE b.email IS NOT NULL
              AND b.email != ''
              AND b.mockup_url IS NOT NULL
              AND b.mockup_url != ''
            """

            # Add filters
            params = []
            if not force:
                # Only include businesses that haven't been emailed yet
                query += " AND e.id IS NULL"

            if business_id is not None:
                # Filter by business ID
                query += " AND b.id = ?"
                params.append(business_id)

            # Order by score (highest first) and limit
            query += " ORDER BY b.score DESC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            # Execute the query
            conn.execute(query, params)
            rows = conn.fetchall()

            # Convert to list of dictionaries
            businesses = [dict(row) for row in rows]
            logger.info(f"Found {len(businesses)} businesses for email sending")
            return businesses
    except Exception as e:
        logger.exception(f"Error getting businesses for email: {str(e)}")
        return []


def is_email_unsubscribed(email: str) -> bool:
    """Check if an email address has unsubscribed.

    Args:
        email: Email address to check.

    Returns:
        True if the email has unsubscribed, False otherwise.
    """
    try:
        # Connect to the database
        with EmailDBConnection() as conn:
            # Check if the email is in the unsubscribe table
            conn.execute(
                "SELECT id FROM unsubscribes WHERE email = ? LIMIT 1", [email.lower()]
            )
            result = conn.fetchone()
            return result is not None
    except Exception as e:
        logger.exception(f"Error checking unsubscribe status: {str(e)}")
        return False


def add_unsubscribe(
    email: str,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Add an email address to the unsubscribe list.

    Args:
        email: Email address to unsubscribe.
        reason: Optional reason for unsubscribing.
        ip_address: Optional IP address of the user.
        user_agent: Optional user agent of the user.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Validate the email
        if not is_valid_email(email):
            logger.error(f"Invalid email address for unsubscribe: {email}")
            return False

        # Normalize the email
        email = email.lower()

        # Connect to the database
        with EmailDBConnection() as conn:
            # Check if already unsubscribed
            conn.execute("SELECT id FROM unsubscribes WHERE email = ?", [email])
            if conn.fetchone() is not None:
                logger.info(f"Email already unsubscribed: {email}")
                return True

            # Add to unsubscribe list
            conn.execute(
                """
                INSERT INTO unsubscribes (email, reason, ip_address, user_agent, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                [email, reason or "", ip_address or "", user_agent or ""],
            )
            conn.commit()
            logger.info(f"Added to unsubscribe list: {email}")
            return True
    except Exception as e:
        logger.exception(f"Error adding unsubscribe: {str(e)}")
        return False


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
        # Connect to the database
        with EmailDBConnection() as conn:
            # Insert the email record
            conn.execute(
                """
                INSERT INTO emails (
                    business_id, recipient_email, recipient_name, subject,
                    message_id, status, error_message, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                [
                    business_id,
                    to_email,
                    to_name,
                    subject,
                    message_id or "",
                    status,
                    error_message or "",
                ],
            )
            conn.commit()
            logger.info(f"Saved email record for business {business_id}")
            return True
    except Exception as e:
        logger.exception(f"Error saving email record: {str(e)}")
        return False


def generate_email_content(business: dict, template: str) -> tuple[str, str, str]:
    """Generate email content for a business.

    Args:
        business: Business data.
        template: Email template.

    Returns:
        tuple of (subject, html_content, text_content).
    """
    try:
        # Extract business data
        business_name = business["name"]
        contact_name = business.get("contact_name") or "Owner"
        business_type = business.get("business_type") or "business"

        # Generate subject line
        subject = f"Website proposal for {business_name}"

        # Apply template variables
        html_content = template
        html_content = html_content.replace(
            "{{business_name}}", html.escape(business_name)
        )
        html_content = html_content.replace("{{name}}", html.escape(contact_name))
        html_content = html_content.replace(
            "{{business_type}}", html.escape(business_type)
        )

        # Generate plain text version
        text_content = f"""
        Hello {contact_name},

        We noticed that {business_name} doesn't have a modern website that showcases your business effectively.

        We've created a free mockup of what your website could look like. No strings attached, just a demonstration of what we can do for you.

        Our services include:
        - Professional website design
        - Mobile optimization
        - SEO to help customers find you
        - Easy content management

        Check out your free mockup attached to this email.

        If you're interested in learning more, reply to this email or call us at (555) 123-4567.

        Best regards,
        The Anthrasite Team

        ---
        This is a one-time email. If you wish to unsubscribe, please visit: https://app.anthrasite.com/unsubscribe?email={business['email']}
        Anthrasite Web Services, 123 Tech Way, San Francisco, CA 94107
        """

        return subject, html_content, text_content
    except Exception as e:
        logger.exception(f"Error generating email content: {str(e)}")
        # Return fallback content
        return (
            f"Website proposal for your business",
            f"<p>Hello! We've created a website mockup for your business.</p>",
            f"Hello! We've created a website mockup for your business.",
        )


def send_business_email(
    business: dict,
    email_sender: SendGridEmailSender,
    template: str,
    is_dry_run: bool = False,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Send email for a business.

    Args:
        business: Business data.
        email_sender: SendGridEmailSender instance.
        template: Email template.
        is_dry_run: If True, don't actually send the email.

    Returns:
        tuple of (success, message_id, error_message).
    """
    try:
        # Extract business data
        business_id = business["id"]
        to_email = business["email"]
        to_name = (
            business.get("contact_name") or business.get("name") or "Business Owner"
        )
        mockup_url = business.get("mockup_url")

        # Check if the email has unsubscribed
        if is_email_unsubscribed(to_email):
            error_msg = f"Email {to_email} has unsubscribed"
            logger.warning(error_msg)
            # Save as failed email record
            save_email_record(
                business_id, to_email, to_name, "[UNSUBSCRIBED]", None, "unsubscribed"
            )
            return False, None, error_msg

        # Generate email content
        subject, html_content, text_content = generate_email_content(business, template)

        # Log the cost
        try:
            log_cost("email", "send", COST_PER_EMAIL, business_id=business_id)
        except Exception as e:
            logger.warning(f"Error logging email cost: {e}")

        # Send the email
        success, message_id, error_message = email_sender.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            mockup_image_url=mockup_url,
            is_dry_run=is_dry_run,
        )

        # Save the email record
        status = "sent" if success else "failed"
        save_email_record(
            business_id, to_email, to_name, subject, message_id, status, error_message
        )

        return success, message_id, error_message
    except Exception as e:
        error_msg = f"Error sending business email: {str(e)}"
        logger.exception(error_msg)
        return False, None, error_msg


def process_business_email(
    business_id: int, dry_run: bool = None
) -> Union[bool, tuple[bool, Optional[str], Optional[str]]]:
    """Process a single business for email sending.

    Args:
        business_id: The ID of the business to process
        dry_run: If True, don't actually send emails. If None, uses the global DRY_RUN setting.

    Returns:
        Union[bool, tuple[bool, Optional[str], Optional[str]]]:
            Either a boolean indicating success, or a tuple with (success, message_id, error)
    """
    # Use global dry run flag if not specified
    is_dry_run = DRY_RUN if dry_run is None else dry_run

    try:
        # Get the business data
        businesses = get_businesses_for_email(business_id=business_id, force=True)
        if not businesses:
            logger.error(
                f"Business ID {business_id} not found or not eligible for email"
            )
            return False

        business = businesses[0]

        # Load the email template
        template = load_email_template()
        if not template:
            logger.error("Failed to load email template")
            return False

        # Check for required environment variables
        if not SENDGRID_API_KEY:
            logger.error("SendGrid API key not found in environment variables")
            return False

        # Create SendGrid sender
        # Use current IP pool and subuser if available
        ip_pool = (
            SENDGRID_IP_POOL_NAMES[CURRENT_IP_POOL_INDEX]
            if SENDGRID_IP_POOL_NAMES
            else None
        )
        subuser = (
            SENDGRID_SUBUSER_NAMES[CURRENT_SUBUSER_INDEX]
            if SENDGRID_SUBUSER_NAMES
            else None
        )

        sender = SendGridEmailSender(
            api_key=SENDGRID_API_KEY,
            from_email=SENDGRID_FROM_EMAIL,
            from_name=SENDGRID_FROM_NAME,
            ip_pool=ip_pool,
            subuser=subuser,
        )

        # Check SendGrid health
        if not is_dry_run:
            # Check bounce rate
            bounce_rate = sender.get_bounce_rate(ip_pool=ip_pool, subuser=subuser)
            if bounce_rate > BOUNCE_RATE_THRESHOLD:
                logger.error(
                    f"Bounce rate too high: {bounce_rate:.2%} > {BOUNCE_RATE_THRESHOLD:.2%}"
                )
                return False

            # Check spam complaint rate
            spam_rate = sender.get_spam_rate(ip_pool=ip_pool, subuser=subuser)
            if spam_rate > SPAM_RATE_THRESHOLD:
                logger.error(
                    f"Spam complaint rate too high: {spam_rate:.4%} > {SPAM_RATE_THRESHOLD:.4%}"
                )
                return False

            # Check daily email limit
            daily_sent = sender.get_daily_sent_count()
            if daily_sent >= DAILY_EMAIL_LIMIT:
                logger.error(
                    f"Daily email limit reached: {daily_sent} >= {DAILY_EMAIL_LIMIT}"
                )
                return False

            # Check monthly budget
            monthly_cost = get_monthly_cost("email")
            if monthly_cost >= MONTHLY_BUDGET:
                logger.error(
                    f"Monthly budget exceeded: ${monthly_cost:.2f} >= ${MONTHLY_BUDGET:.2f}"
                )
                return False

        # Send the email
        result = send_business_email(business, sender, template, is_dry_run)
        return result
    except Exception as e:
        logger.exception(f"Error processing business email: {str(e)}")
        return False


def main() -> int:
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Send emails to businesses")
    parser.add_argument("--limit", type=int, help="Limit the number of emails to send")
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually sending emails",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sending emails even if they've been sent before",
    )
    args = parser.parse_args()

    # Set the global dry run flag
    global DRY_RUN
    DRY_RUN = args.dry_run

    # Log the start of the process
    logger.info("Starting email queue processing")
    logger.info(f"Dry run mode: {DRY_RUN}")

    # Get the list of businesses to process
    businesses = get_businesses_for_email(
        limit=args.limit, business_id=args.id, force=args.force
    )

    if not businesses:
        logger.warning("No businesses found for email sending")
        return 0

    # Log the number of businesses found
    logger.info(f"Found {len(businesses)} businesses for email sending")

    # Check for required environment variables
    if not SENDGRID_API_KEY:
        logger.error("SendGrid API key not found in environment variables")
        return 1

    # Load the email template
    template = load_email_template()
    if not template:
        logger.error("Failed to load email template")
        return 1

    # Create SendGrid sender
    # Use current IP pool and subuser if available
    ip_pool = (
        SENDGRID_IP_POOL_NAMES[CURRENT_IP_POOL_INDEX]
        if SENDGRID_IP_POOL_NAMES
        else None
    )
    subuser = (
        SENDGRID_SUBUSER_NAMES[CURRENT_SUBUSER_INDEX]
        if SENDGRID_SUBUSER_NAMES
        else None
    )

    sender = SendGridEmailSender(
        api_key=SENDGRID_API_KEY,
        from_email=SENDGRID_FROM_EMAIL,
        from_name=SENDGRID_FROM_NAME,
        ip_pool=ip_pool,
        subuser=subuser,
    )

    # Check SendGrid health
    if not DRY_RUN:
        # Check bounce rate
        bounce_rate = sender.get_bounce_rate(ip_pool=ip_pool, subuser=subuser)
        if bounce_rate > BOUNCE_RATE_THRESHOLD:
            logger.error(
                f"Bounce rate too high: {bounce_rate:.2%} > {BOUNCE_RATE_THRESHOLD:.2%}"
            )
            return 1

        # Check spam complaint rate
        spam_rate = sender.get_spam_rate(ip_pool=ip_pool, subuser=subuser)
        if spam_rate > SPAM_RATE_THRESHOLD:
            logger.error(
                f"Spam complaint rate too high: {spam_rate:.4%} > {SPAM_RATE_THRESHOLD:.4%}"
            )
            return 1

        # Check daily email limit
        daily_sent = sender.get_daily_sent_count()
        if daily_sent >= DAILY_EMAIL_LIMIT:
            logger.error(
                f"Daily email limit reached: {daily_sent} >= {DAILY_EMAIL_LIMIT}"
            )
            return 1

        # Check monthly budget
        monthly_cost = get_monthly_cost("email")
        if monthly_cost >= MONTHLY_BUDGET:
            logger.error(
                f"Monthly budget exceeded: ${monthly_cost:.2f} >= ${MONTHLY_BUDGET:.2f}"
            )
            return 1

    # Process businesses
    total_sent = 0
    total_failed = 0

    # Limit concurrent requests
    concurrent_limit = min(MAX_CONCURRENT_REQUESTS, len(businesses))
    logger.info(f"Processing up to {concurrent_limit} businesses concurrently")

    # Process in batches for concurrency control
    for i in range(0, len(businesses), concurrent_limit):
        batch = businesses[i : i + concurrent_limit]
        logger.info(f"Processing batch of {len(batch)} businesses")

        for business in batch:
            business_id = business["id"]
            business_name = business["name"]
            business_email = business["email"]

            logger.info(f"Processing business {business_id}: {business_name}")

            # Send the email
            success, message_id, error_message = send_business_email(
                business, sender, template, DRY_RUN
            )

            if success:
                total_sent += 1
                logger.info(
                    f"Email sent successfully to {business_name} <{business_email}>"
                )
            else:
                total_failed += 1
                logger.error(
                    f"Failed to send email to {business_name} <{business_email}>: {error_message}"
                )

            # Sleep to avoid hitting rate limits
            if not DRY_RUN and i < len(businesses) - 1:
                time.sleep(1)  # Sleep for 1 second between requests

    # Log the results
    logger.info(
        f"Email sending complete. Sent: {total_sent}, Failed: {total_failed}, Total: {total_sent + total_failed}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
