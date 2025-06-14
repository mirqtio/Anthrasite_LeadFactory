#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Batch Completion Monitor
Monitors batch completion status and sends alerts if batches don't complete on time.
"""

import argparse
import json
import logging
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

# Use lowercase versions for Python 3.9 compatibility

# Declare global variables that will be populated by setup_imports
get_logger: Any = None
check_batch_completion: Any = None
get_batch_status: Any = None


# Define utility functions to avoid module-level imports
def setup_imports() -> Any:
    # Add project root to path using pathlib for better compatibility
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Now we can import our local modules
    global get_logger, check_batch_completion, get_batch_status
    from utils_legacy.batch_tracker import check_batch_completion as check_func
    from utils_legacy.batch_tracker import get_batch_status as status_func

    try:
        from leadfactory.utils.logging import get_logger as logger_func
    except ImportError:
        # Fallback for legacy compatibility
        import logging

        def logger_func(name):
            return logging.getLogger(name)

    # Assign to global variables
    globals()["get_logger"] = logger_func
    globals()["check_batch_completion"] = check_func
    globals()["get_batch_status"] = status_func

    return logger_func


# Setup imports before using them
get_logger = setup_imports()

# Set up logging
logger: Any = get_logger(__name__)

# Constants
CHECK_INTERVAL = int(
    os.getenv("BATCH_COMPLETION_CHECK_INTERVAL_SECONDS", "300")
)  # 5 minutes
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "alerts@anthrasite.io")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "leadfactory@anthrasite.io")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.sendgrid.net")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "apikey")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", os.getenv("SENDGRID_API_KEY", ""))


def send_alert_email(subject: str, message: str) -> bool:
    """Send an alert email.

    Args:
        subject: Email subject.
        message: Email message.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = ALERT_EMAIL_FROM
        msg["To"] = ALERT_EMAIL_TO
        msg["Subject"] = subject

        # Add message body
        msg.attach(MIMEText(message, "plain"))

        # Connect to SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)

        # Send email
        server.send_message(msg)
        server.quit()

        logger.info(f"Sent alert email: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error sending alert email: {e}")
        return False


def check_and_alert() -> None:
    """Check batch completion status and send alerts if needed."""
    completed_on_time, reason = check_batch_completion()

    if not completed_on_time:
        # Get detailed batch status
        status = get_batch_status()

        # Create alert message
        subject = f"ALERT: Batch Completion Failure - {reason}"
        message = f"""
Batch Completion Alert

Status: FAILED
Reason: {reason}
Time: {datetime.utcnow().isoformat()}

Batch Details:
- Started: {status.get("current_batch_start", "Unknown")}
- Completion Percentage: {status.get("completion_percentage", 0):.2f}%
- Deadline: {status.get("deadline", "Unknown")}

Stage Completion:
"""

        # Add stage completion details
        stages = status.get("stages", {})
        for stage, details in stages.items():
            completion = details.get("completion_percentage", 0)
            timestamp = details.get("timestamp", "Unknown")
            message += f"- {stage.title()}: {completion:.2f}% at {timestamp}\n"

        # Add recent alerts
        message += "\nRecent Alerts:\n"
        alerts = status.get("alerts", [])
        for alert in alerts:
            message += f"- {alert.get('timestamp', 'Unknown')}: {alert.get('message', 'Unknown')}\n"

        # Send alert
        send_alert_email(subject, message)
        logger.warning(f"Batch completion alert sent: {reason}")
    else:
        logger.info(f"Batch completion check passed: {reason}")


def monitor_batch_completion(interval: int = CHECK_INTERVAL) -> None:
    """Monitor batch completion status continuously.

    Args:
        interval: Check interval in seconds.
    """
    logger.info(f"Starting batch completion monitor (interval: {interval}s)")

    while True:
        try:
            check_and_alert()
        except Exception as e:
            logger.error(f"Error in batch completion monitor: {e}")

        # Sleep until next check
        time.sleep(interval)


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Batch Completion Monitor")
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Check interval in seconds (default: {CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run check once and exit",
    )
    args = parser.parse_args()

    try:
        if args.once:
            # Run check once
            check_and_alert()
        else:
            # Run continuous monitor
            monitor_batch_completion(args.interval)
    except KeyboardInterrupt:
        logger.info("Batch completion monitor stopped by user")
    except Exception as e:
        logger.error(f"Batch completion monitor failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
