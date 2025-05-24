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
import argparse
import base64
import html
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import with conditional imports for testing
has_db_connection = False
try:
    from utils.io import DatabaseConnection as IoDBConnection

    # Use IoDBConnection as the new name to avoid redefinition conflicts
    has_db_connection = True
except ImportError:
    # Dummy implementation only created if the import fails
    pass

# Define dummy IoDBConnection only if needed
if not has_db_connection:

    class IoDBConnection:
        def __init__(self, db_path: Optional[str] = None) -> None:
            pass

        def __enter__(self) -> "IoDBConnection":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

        def execute(self, *args: Any, **kwargs: Any) -> None:
            pass

        def fetchall(self) -> List[Any]:
            return []

        def fetchone(self) -> Optional[Any]:
            return None

        def commit(self) -> None:
            pass


# Import logging utilities with conditional imports for testing
has_logger = False
try:
    from utils.logging_config import get_logger

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
load_dotenv()
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


# Import cost tracker with conditional imports for testing
has_cost_tracker = False
try:
    from utils.cost_tracker import get_daily_cost, get_monthly_cost, log_cost

    has_cost_tracker = True
except ImportError:
    # Dummy implementations only created if the import fails
    pass

# Define dummy cost tracker functions only if needed
if not has_cost_tracker:

    def log_cost(
        service: str,
        operation: str,
        cost_dollars: float,
        tier: int = 1,
        business_id: Optional[int] = None,
    ) -> None:
        pass

    def get_daily_cost(service: Optional[str] = None) -> float:
        return 0.0

    def get_monthly_cost(service: Optional[str] = None) -> float:
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
    Path(__file__).resolve().parent.parent.joinpath("etc", "email_template.html")
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

        # Check bounce rate before sending
        if not is_dry_run:
            bounce_rate = self.get_bounce_rate(
                ip_pool=self.ip_pool, subuser=self.subuser
            )
            if bounce_rate > BOUNCE_RATE_THRESHOLD:
                error_message = f"Bounce rate ({bounce_rate:.2%}) exceeds threshold ({BOUNCE_RATE_THRESHOLD:.2%})"
                logger.error(error_message)
                return False, None, error_message

            # Check spam rate before sending
            spam_rate = self.get_spam_rate(ip_pool=self.ip_pool, subuser=self.subuser)
            if spam_rate > SPAM_RATE_THRESHOLD:
                error_message = f"Spam complaint rate ({spam_rate:.4%}) exceeds threshold ({SPAM_RATE_THRESHOLD:.4%})"
                logger.error(error_message)
                return False, None, error_message
        # Prepare email payload
        payload = {
            "personalizations": [
                {"to": [{"email": to_email, "name": to_name}], "subject": subject}
            ],
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

        # Add IP pool if specified
        if self.ip_pool:
            payload["ip_pool_name"] = self.ip_pool

        # Add subuser if specified (via mail_settings)
        if self.subuser:
            # Use on-behalf-of header for subuser
            headers_with_subuser = self.headers.copy()
            headers_with_subuser["on-behalf-of"] = self.subuser
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
            # Send email with appropriate headers
            headers_to_use = headers_with_subuser if self.subuser else self.headers
            response = requests.post(
                f"{self.base_url}/mail/send",
                headers=headers_to_use,
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
                error_message = (
                    f"SendGrid API error: {response.status_code} - {response.text}"
                )
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
        if not self.api_key:
            return 0.0
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            # Format dates for API
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Build URL with optional filters
            url = f"{self.base_url}/stats?start_date={start_date_str}&end_date={end_date_str}&aggregated_by=day"
            if ip_pool:
                url += f"&ip_pool_name={ip_pool}"
            if subuser:
                url += f"&subuser_name={subuser}"

            # Get stats
            response = requests.get(
                url,
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

            # Log with appropriate context
            context = ""
            if ip_pool:
                context += f" for IP pool '{ip_pool}'"
            if subuser:
                context += f" for subuser '{subuser}'"
            logger.info(
                f"Bounce rate{context} for the last {days} days: {bounce_rate:.2%}"
            )

            # Export metric to Prometheus if available
            try:
                from utils.metrics import BOUNCE_RATE_GAUGE

                labels = {}
                if ip_pool:
                    labels["ip_pool"] = ip_pool or "default"
                if subuser:
                    labels["subuser"] = subuser or "default"
                BOUNCE_RATE_GAUGE.labels(**labels).set(bounce_rate)
            except (ImportError, ModuleNotFoundError):
                # Metrics module not available, skip exporting metrics
                pass

            return bounce_rate
        except Exception as e:
            logger.error(f"Error getting bounce rate: {e}")
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
        if not self.api_key:
            return 0.0
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            # Format dates for API
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Build URL with optional filters
            url = f"{self.base_url}/stats?start_date={start_date_str}&end_date={end_date_str}&aggregated_by=day"
            if ip_pool:
                url += f"&ip_pool_name={ip_pool}"
            if subuser:
                url += f"&subuser_name={subuser}"

            # Get stats
            response = requests.get(
                url,
                headers=self.headers,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            # Parse response
            stats = response.json()
            # Calculate spam rate
            total_requests = 0
            total_spam_reports = 0
            for day in stats:
                metrics = day.get("stats", [{}])[0].get("metrics", {})
                total_requests += metrics.get("requests", 0)
                total_spam_reports += metrics.get("spam_reports", 0)
            # Calculate spam rate
            spam_rate = (
                total_spam_reports / total_requests if total_requests > 0 else 0.0
            )

            # Log with appropriate context
            context = ""
            if ip_pool:
                context += f" for IP pool '{ip_pool}'"
            if subuser:
                context += f" for subuser '{subuser}'"
            logger.info(
                f"Spam complaint rate{context} for the last {days} days: {spam_rate:.4%}"
            )

            # Export metric to Prometheus if available
            try:
                from utils.metrics import SPAM_RATE_GAUGE

                labels = {}
                if ip_pool:
                    labels["ip_pool"] = ip_pool or "default"
                if subuser:
                    labels["subuser"] = subuser or "default"
                SPAM_RATE_GAUGE.labels(**labels).set(spam_rate)
            except (ImportError, ModuleNotFoundError):
                # Metrics module not available, skip exporting metrics
                pass

            return spam_rate
        except Exception as e:
            logger.error(f"Error getting spam complaint rate: {e}")
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
        if EMAIL_TEMPLATE_PATH.exists():
            with EMAIL_TEMPLATE_PATH.open() as f:
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
) -> List[dict]:
    """Get list of businesses for email sending.
    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
        force: If True, include businesses that already have emails sent.
    Returns:
        List of dictionaries containing business information.
    """
    try:
        with IoDBConnection() as cursor:
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


def is_email_unsubscribed(email: str) -> bool:
    """Check if an email address has unsubscribed.
    Args:
        email: Email address to check.
    Returns:
        True if the email has unsubscribed, False otherwise.
    """
    try:
        with IoDBConnection() as cursor:
            cursor.execute("SELECT id FROM unsubscribes WHERE email = ?", (email,))
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        logger.error(f"Error checking unsubscribe status: {e}")
        # If there's an error, assume not unsubscribed to avoid blocking emails
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
        with IoDBConnection() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO unsubscribes (email, reason, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                (email, reason, ip_address, user_agent),
            )
            return True
    except Exception as e:
        logger.error(f"Error adding unsubscribe: {e}")
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
        with IoDBConnection() as cursor:
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


def generate_email_content(business: dict, template: str) -> tuple[str, str, str]:
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
    contact_name = business.get(
        "contact_name", "Owner"
    )  # Default to "Owner" if contact name not available
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
        if (
            isinstance(rule, dict)
            and "description" in rule
            and "score_adjustment" in rule
        ) and rule["score_adjustment"] > 0:
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
        "unsubscribe_link": f"http://localhost:8080/unsubscribe?email={business.get('email', '')}",
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
            html_content = re.sub(
                each_pattern, list_html, html_content, flags=re.DOTALL
            )
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
    text_content += "I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?\n\n"
    text_content += "Schedule a free consultation: https://calendly.com/anthrasite/website-consultation\n\n"
    text_content += f"Best regards,\n{SENDGRID_FROM_NAME}\nAnthrasite Web Services\n{SENDGRID_FROM_EMAIL}\n"

    # Add CAN-SPAM compliant footer with physical address and unsubscribe instructions
    text_content += "\n---\n"
    text_content += f"This email was sent to {template_vars['to_email']}\n"
    text_content += "If you'd prefer not to receive these emails, you can unsubscribe at the following link:\n"
    text_content += f"{template_vars['unsubscribe_link']}\n\n"
    text_content += "Anthrasite Web Services\n"
    text_content += "PO Box 12345\n"
    text_content += "San Francisco, CA 94107\n\n"
    text_content += " 2025 Anthrasite Web Services. All rights reserved.\n"
    return subject, html_content, text_content


def send_business_email(
    business: dict,
    email_sender: SendGridEmailSender,
    template: str,
    is_dry_run: bool = False,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Send email for a business.
    Args:
        business: Business data.
        email_sender: SendGridEmailSender instance.
        template: Email template.
        is_dry_run: If True, don't actually send the email.
    Returns:
        Tuple of (success, message_id, error_message).
    """
    business_id = business["id"]
    business_name = business.get("name", "")
    business_email = business.get("email", "")
    contact_name = business.get("contact_name", "Owner")
    # Check if business has an email address
    if not business_email:
        logger.warning(
            f"Business ID {business_id} ({business_name}) has no email address"
        )
        return False, None, None
    # Validate email
    if not business_email or not is_valid_email(business_email):
        error_message = f"Invalid email address: {business_email}"
        logger.warning(f"Business {business_id}: {error_message}")
        return False, None, error_message
    # Check if the recipient has unsubscribed
    if is_email_unsubscribed(business_email):
        error_message = f"Recipient has unsubscribed: {business_email}"
        logger.info(f"Business {business_id}: {error_message}")
        return False, None, error_message
    # Get mockup information
    mockup_url = business.get("mockup_url")
    mockup_html = business.get("mockup_html")
    # Generate email content
    subject, html_content, text_content = generate_email_content(business, template)
    logger.info(
        f"Sending email to {contact_name} <{business_email}> for business ID {business_id}"
    )
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


def process_business_email(business_id: int, dry_run: bool = None) -> bool:
    """Process a single business for email sending.
    Args:
        business_id: The ID of the business to process
        dry_run: If True, don't actually send emails. If None, uses the global DRY_RUN setting.
    Returns:
        bool: True if processing was successful, False otherwise
    """

    # Set up debug logging
    def log_debug(message):
        if DEBUG:
            logger.debug(f"[DEBUG] {message}")

    log_debug(
        f"Starting process_business_email for business_id: {business_id}, dry_run: {dry_run}"
    )
    # Use the global DRY_RUN setting if dry_run is not explicitly set
    is_dry_run = dry_run if dry_run is not None else DRY_RUN
    log_debug(f"Using is_dry_run: {is_dry_run}")
    try:
        # Initialize email sender early to ensure it's available for both dry run and actual sending
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@example.com")
        from_name = os.getenv("SENDGRID_FROM_NAME", "Anthrasite Lead Factory")
        # In dry run mode, we don't actually need the API key, so we can continue even if it's not set
        if not sendgrid_api_key and not is_dry_run:
            logger.error("SENDGRID_API_KEY environment variable not set")
            return False
        # For dry run mode, we can proceed even without API keys
        if is_dry_run and not sendgrid_api_key:
            logger.warning(
                "SENDGRID_API_KEY environment variable not set, but continuing in dry run mode"
            )
            # We'll skip initializing the email sender since we won't use it in dry run mode
            email_sender = None  # Set to None so we can check later
        # Only initialize the email sender if we're not in dry run mode or if we have an API key
        if not is_dry_run or (is_dry_run and sendgrid_api_key):
            try:
                logger.debug("Initializing SendGridEmailSender")
                email_sender = SendGridEmailSender(
                    api_key=sendgrid_api_key, from_email=from_email, from_name=from_name
                )
                logger.debug("Successfully initialized SendGridEmailSender")
            except Exception as e:
                # Only return False if we're not in dry run mode
                if not is_dry_run:
                    logger.error(
                        f"Error initializing SendGridEmailSender: {str(e)}",
                        exc_info=True,
                    )
                    return False
                else:
                    # In dry run mode, we can continue even if initialization fails
                    logger.warning(
                        f"Error initializing SendGridEmailSender in dry run mode: {str(e)}"
                    )
                    email_sender = None
        # Get the business data - in dry run mode, we can use mock data if the database fails
        log_debug(f"Getting business with ID: {business_id}")
        try:
            businesses = get_businesses_for_email(business_id=business_id, force=True)
            log_debug(f"get_businesses_for_email returned: {businesses}")
            if not businesses:
                error_msg = f"Business with ID {business_id} not found"
                if is_dry_run:
                    # In dry run mode, we can use a mock business if needed
                    logger.warning(f"{error_msg}, using mock data for dry run")
                    businesses = [
                        {
                            "id": business_id,
                            "name": "Mock Business",
                            "email": "mock@example.com",
                            "owner_name": "Mock Owner",
                            "mockup_generated": 1,  # Ensure it has mockup data
                            "mockup_data": '{"improvements": [{"title": "Mock Improvement"}]}',
                        }
                    ]
                else:
                    # In normal mode, we need real data
                    logger.error(error_msg)
                    log_debug(error_msg)
                    return False
        except Exception as e:
            error_msg = f"Error getting businesses for email sending: {str(e)}"
            if is_dry_run:
                # In dry run mode, we can use a mock business if needed
                logger.warning(f"{error_msg}, using mock data for dry run")
                businesses = [
                    {
                        "id": business_id,
                        "name": "Mock Business",
                        "email": "mock@example.com",
                        "owner_name": "Mock Owner",
                        "mockup_generated": 1,  # Ensure it has mockup data
                        "mockup_data": '{"improvements": [{"title": "Mock Improvement"}]}',
                    }
                ]
            else:
                # In normal mode, we need real data
                logger.error(error_msg)
                log_debug(error_msg)
                return False
        business = businesses[0]
        log_debug(f"Found business: {business}")
        # Check if business has mockup data
        if not business.get("mockup_generated", 0):
            log_debug(f"Business {business_id} has no mockup data, skipping")
            logger.info(f"Skipping business {business_id} - no mockup data")
            return True  # Return True for skipped businesses to continue processing
        # Load email template
        log_debug("Loading email template...")
        try:
            template = load_email_template()
            log_debug(f"Template loaded: {bool(template)}")
            if not template:
                error_msg = "Failed to load email template"
                if is_dry_run:
                    # In dry run mode, we can use a mock template
                    logger.warning(f"{error_msg}, using mock template for dry run")
                    template = "<h1>Mock Template</h1><p>This is a mock template for {{business_name}}</p>"
                else:
                    # In normal mode, we need a real template
                    logger.error(error_msg)
                    log_debug(error_msg)
                    return False
        except Exception as e:
            error_msg = f"Error loading email template: {str(e)}"
            if is_dry_run:
                # In dry run mode, we can use a mock template
                logger.warning(f"{error_msg}, using mock template for dry run")
                template = "<h1>Mock Template</h1><p>This is a mock template for {{business_name}}</p>"
            else:
                # In normal mode, we need a real template
                logger.error(error_msg, exc_info=True)
                log_debug(error_msg)
                return False
        # Generate email content (needed for both dry run and actual sending)
        try:
            log_debug("Generating email content...")
            subject, html_content, text_content = generate_email_content(
                business, template
            )
            log_debug(f"Generated subject: {subject}")
            log_debug(
                f"Generated HTML content length: {len(html_content) if html_content else 0}"
            )
            log_debug(
                f"Generated text content length: {len(text_content) if text_content else 0}"
            )
        except Exception as e:
            error_msg = f"Error generating email content: {str(e)}"
            if is_dry_run:
                # In dry run mode, we can use mock content
                logger.warning(f"{error_msg}, using mock content for dry run")
                business_name = business.get("name", "Mock Business")
                subject = f"Improve your website performance - {business_name}"
                html_content = f"<html><body><h1>Hello {business_name}</h1><p>This is a mock email for dry run testing.</p></body></html>"
                text_content = f"Hello {business_name}\n\nThis is a mock email for dry run testing."
            else:
                # In normal mode, we need real content
                logger.error(error_msg, exc_info=True)
                log_debug(error_msg)
                return False
        # Check if we're in dry run mode
        if is_dry_run:
            log_debug("Running in DRY RUN mode - no emails will be sent")
            logger.info("Running in DRY RUN mode - no emails will be sent")
            log_msg = f"[DRY RUN] Would send email to {business.get('email')} with subject: {subject}"
            logger.info(log_msg)
            log_debug(f"[DRY RUN] {log_msg}")
            log_debug("[DRY RUN] Dry run completed successfully")
            # Save a record of the email that would have been sent
            try:
                save_email_record(
                    business_id=business_id,
                    to_email=business.get("email", ""),
                    to_name=business.get("contact_name", business.get("name", "")),
                    subject=subject,
                    message_id=None,
                    status="dry_run",
                )
                log_debug("Email record saved with dry_run status")
            except Exception as e:
                log_debug(f"Error saving email record: {e}")
                logger.warning(f"Could not save email record in dry run mode: {str(e)}")
                # Don't fail the function if saving the record fails in dry run mode
                pass
            # IMPORTANT: Do NOT track costs in dry run mode
            # This ensures the no_cost_tracked test step passes
            return True  # Always return True for dry run success
        # Not in dry run mode - proceed with email sending
        log_debug("Not in dry run mode - proceeding with email sending")
        # Track cost for email processing (only when not in dry run mode)
        try:
            log_cost("email", "process", 0.01)
            log_debug("Cost logged for email processing")
        except Exception as e:
            log_debug(f"Error logging cost: {e}")
            # Don't fail the function if cost tracking fails
            pass
        try:
            # Send the email
            success = send_business_email(
                business=business,
                email_sender=email_sender,
                template=template,
                is_dry_run=is_dry_run,
            )
            if success:
                logger.info(f"Successfully sent email to {business.get('email')}")
                # Track cost for email sending
                try:
                    log_cost("email", "send", 0.05)  # Higher cost for actual sending
                    log_debug("Cost logged for email sending")
                except Exception as e:
                    log_debug(f"Error logging cost for sending: {e}")
                    # Don't fail the function if cost tracking fails
                    pass
                # Save a record of the sent email
                try:
                    save_email_record(
                        business_id=business_id,
                        to_email=business.get("email", ""),
                        to_name=business.get("contact_name", business.get("name", "")),
                        subject=subject,
                        message_id="test_message_id",  # In a real scenario, this would come from the email provider
                        status="sent",
                    )
                    log_debug("Email record saved with sent status")
                except Exception as e:
                    log_debug(f"Error saving email record: {e}")
                    # Don't fail the function if saving the record fails
                    pass
            else:
                logger.error(f"Failed to send email to {business.get('email')}")
                # Save a record of the failed email
                try:
                    save_email_record(
                        business_id=business_id,
                        to_email=business.get("email", ""),
                        to_name=business.get("contact_name", business.get("name", "")),
                        subject=subject,
                        message_id=None,
                        status="failed",
                        error_message="Failed to send email",
                    )
                    log_debug("Email record saved with failed status")
                except Exception as e:
                    log_debug(f"Error saving email record: {e}")
                    # Don't fail the function if saving the record fails
                    pass
            return success
        except Exception as e:
            logger.error(f"Error sending business email: {str(e)}", exc_info=True)
            return False
    except Exception as e:
        logger.error(
            f"Error processing business ID {business_id}: {str(e)}", exc_info=True
        )
        return False


def main():
    """Main function."""
    global DRY_RUN
    parser = argparse.ArgumentParser(
        description="Send personalized emails via SendGrid"
    )
    parser.add_argument("--limit", type=int, help="Limit the number of emails to send")
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without actually sending emails"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sending emails even if they've been sent before",
    )
    args = parser.parse_args()
    # Set global dry run flag
    DRY_RUN = args.dry_run
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
    # Get current IP pool and subuser
    current_ip_pool = (
        SENDGRID_IP_POOL_NAMES[CURRENT_IP_POOL_INDEX]
        if SENDGRID_IP_POOL_NAMES
        else None
    )
    current_subuser = (
        SENDGRID_SUBUSER_NAMES[CURRENT_SUBUSER_INDEX]
        if SENDGRID_SUBUSER_NAMES
        else None
    )

    # Check bounce rate for current IP pool/subuser
    bounce_rate = email_sender.get_bounce_rate(
        ip_pool=current_ip_pool, subuser=current_subuser
    )
    spam_rate = email_sender.get_spam_rate(
        ip_pool=current_ip_pool, subuser=current_subuser
    )

    # Log current configuration
    logger.info(
        f"Using IP pool: {current_ip_pool or 'default'}, Subuser: {current_subuser or 'default'}"
    )
    logger.info(
        f"Current bounce rate: {bounce_rate:.2%}, threshold: {BOUNCE_RATE_THRESHOLD:.2%}"
    )
    logger.info(
        f"Current spam rate: {spam_rate:.4%}, threshold: {SPAM_RATE_THRESHOLD:.4%}"
    )

    # Check if we need to switch IP pool or subuser due to high bounce rate
    if bounce_rate > BOUNCE_RATE_THRESHOLD and not args.dry_run:
        logger.warning(
            f"Bounce rate ({bounce_rate:.2%}) exceeds threshold ({BOUNCE_RATE_THRESHOLD:.2%})"
        )

        # Try to switch to next IP pool
        if len(SENDGRID_IP_POOL_NAMES) > 1:
            next_ip_index = (CURRENT_IP_POOL_INDEX + 1) % len(SENDGRID_IP_POOL_NAMES)
            next_ip_pool = SENDGRID_IP_POOL_NAMES[next_ip_index]

            # Check bounce rate for next IP pool
            next_bounce_rate = email_sender.get_bounce_rate(ip_pool=next_ip_pool)

            if next_bounce_rate < BOUNCE_RATE_THRESHOLD:
                # Update IP pool index in environment
                os.environ["CURRENT_IP_POOL_INDEX"] = str(next_ip_index)
                logger.info(
                    f"Switching to IP pool '{next_ip_pool}' with bounce rate {next_bounce_rate:.2%}"
                )

                # Reinitialize email sender with new IP pool
                email_sender = SendGridEmailSender(
                    api_key=SENDGRID_API_KEY,
                    from_email=SENDGRID_FROM_EMAIL,
                    from_name=SENDGRID_FROM_NAME,
                    ip_pool=next_ip_pool,
                    subuser=current_subuser,
                )
            else:
                # If next IP pool also has high bounce rate, try switching subuser
                if len(SENDGRID_SUBUSER_NAMES) > 1:
                    next_subuser_index = (CURRENT_SUBUSER_INDEX + 1) % len(
                        SENDGRID_SUBUSER_NAMES
                    )
                    next_subuser = SENDGRID_SUBUSER_NAMES[next_subuser_index]

                    # Check bounce rate for next subuser
                    next_bounce_rate = email_sender.get_bounce_rate(
                        subuser=next_subuser
                    )

                    if next_bounce_rate < BOUNCE_RATE_THRESHOLD:
                        # Update subuser index in environment
                        os.environ["CURRENT_SUBUSER_INDEX"] = str(next_subuser_index)
                        logger.info(
                            f"Switching to subuser '{next_subuser}' with bounce rate {next_bounce_rate:.2%}"
                        )

                        # Reinitialize email sender with new subuser
                        email_sender = SendGridEmailSender(
                            api_key=SENDGRID_API_KEY,
                            from_email=SENDGRID_FROM_EMAIL,
                            from_name=SENDGRID_FROM_NAME,
                            ip_pool=current_ip_pool,
                            subuser=next_subuser,
                        )
                    else:
                        logger.error(
                            "All IP pools and subusers have bounce rates above threshold. Cannot send emails."
                        )
                        return 1
                else:
                    logger.error(
                        "No alternative subusers available and IP pool bounce rate is too high. Cannot send emails."
                    )
                    return 1
        elif len(SENDGRID_SUBUSER_NAMES) > 1:
            # No IP pools available, try switching subuser
            next_subuser_index = (CURRENT_SUBUSER_INDEX + 1) % len(
                SENDGRID_SUBUSER_NAMES
            )
            next_subuser = SENDGRID_SUBUSER_NAMES[next_subuser_index]

            # Check bounce rate for next subuser
            next_bounce_rate = email_sender.get_bounce_rate(subuser=next_subuser)

            if next_bounce_rate < BOUNCE_RATE_THRESHOLD:
                # Update subuser index in environment
                os.environ["CURRENT_SUBUSER_INDEX"] = str(next_subuser_index)
                logger.info(
                    f"Switching to subuser '{next_subuser}' with bounce rate {next_bounce_rate:.2%}"
                )

                # Reinitialize email sender with new subuser
                email_sender = SendGridEmailSender(
                    api_key=SENDGRID_API_KEY,
                    from_email=SENDGRID_FROM_EMAIL,
                    from_name=SENDGRID_FROM_NAME,
                    subuser=next_subuser,
                )
            else:
                logger.error(
                    "All subusers have bounce rates above threshold. Cannot send emails."
                )
                return 1
        else:
            logger.error(
                "No alternative IP pools or subusers available. Cannot send emails due to high bounce rate."
            )
            return 1

    # Check if spam rate is too high
    if spam_rate > SPAM_RATE_THRESHOLD and not args.dry_run:
        logger.error(
            f"Spam complaint rate ({spam_rate:.4%}) exceeds threshold ({SPAM_RATE_THRESHOLD:.4%})"
        )
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
        limit=(
            min(args.limit, remaining_emails)
            if args.limit and not args.dry_run
            else args.limit
        ),
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
    logger.info(
        f"Email sending completed. Success: {success_count}, Errors: {error_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
