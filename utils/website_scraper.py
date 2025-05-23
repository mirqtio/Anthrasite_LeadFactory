#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Website Scraper
Utilities for scraping websites and storing HTML content.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import database utilities
from utils.io import DatabaseConnection

# Import logging configuration
from utils.logging_config import get_logger

# Import raw data retention utilities
from utils.raw_data_retention import fetch_website_html, store_html

# Set up logging
logger = get_logger(__name__)


def extract_email_from_html(html_content: str) -> str | None:
    """Extract email address from HTML content using regex.

    Args:
        html_content: HTML content to extract email from.

    Returns:
        Email address if found, None otherwise.
    """
    if not html_content:
        return None

    try:
        # Simple regex for email addresses
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, html_content)

        # Filter out common false positives
        filtered_emails = [
            email
            for email in emails
            if not any(
                exclude in email.lower()
                for exclude in [
                    "example.com",
                    "yourdomain",
                    "@image",
                    "@png",
                    "@jpg",
                ]
            )
        ]

        if filtered_emails:
            return filtered_emails[0]
    except Exception as e:
        logger.warning(f"Error extracting email from HTML: {e}")

    return None


def extract_email_from_website(
    website: str, business_id: int | None = None
) -> str | None:
    """Extract email from website and store HTML content.

    Args:
        website: Website URL.
        business_id: ID of the business associated with the website.

    Returns:
        Email address if found, None otherwise.
    """
    if not website:
        return None

    try:
        # Fetch HTML content
        html_content = fetch_website_html(website)

        # Store HTML content if business_id is provided
        if html_content and business_id:
            html_path = store_html(html_content, website, business_id)
            logger.info(
                f"Stored HTML for business {business_id}, "
                f"website: {website}, path: {html_path}"
            )

            # Update the business record with the HTML path
            with DatabaseConnection() as cursor:
                if cursor.connection.is_postgres:
                    cursor.execute(
                        "UPDATE businesses SET html_path = %s WHERE id = %s",
                        (html_path, business_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE businesses SET html_path = ? WHERE id = ?",
                        (html_path, business_id),
                    )

        # Extract email from HTML content
        if html_content:
            email = extract_email_from_html(html_content)
            if email:
                return email

        # Fall back to domain-based email if extraction fails
        domain = urlparse(website).netloc
        if domain:
            return f"info@{domain}"

    except Exception as e:
        logger.warning(f"Error processing website {website}: {e}")

    return None


def update_business_with_website_data(business_id: int, website: str) -> bool:
    """Update a business with data extracted from its website.

    Args:
        business_id: ID of the business to update.
        website: Website URL.

    Returns:
        True if successful, False otherwise.
    """
    if not business_id or not website:
        return False

    try:
        # Extract email from website
        email = extract_email_from_website(website, business_id)

        # Update business with extracted email
        if email:
            with DatabaseConnection() as cursor:
                if cursor.connection.is_postgres:
                    cursor.execute(
                        "UPDATE businesses SET email = %s WHERE id = %s",
                        (email, business_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE businesses SET email = ? WHERE id = ?",
                        (email, business_id),
                    )
            logger.info(f"Updated business {business_id} with email: {email}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error updating business {business_id} with website data: {e}")
        return False


def process_pending_websites() -> tuple[int, int]:
    """Process all businesses with websites but no HTML stored.

    Returns:
        Tuple of (processed_count, success_count).
    """
    processed_count = 0
    success_count = 0

    try:
        # Get businesses with websites but no HTML stored
        with DatabaseConnection() as cursor:
            query = (
                "SELECT id, website FROM businesses "
                "WHERE website IS NOT NULL AND website != '' AND html_path IS NULL"
            )
            if cursor.connection.is_postgres:
                cursor.execute(query)
            else:
                cursor.execute(query)

            businesses = cursor.fetchall()

        logger.info(
            f"Found {len(businesses)} businesses with websites but no HTML stored"
        )

        # Process each business
        for business in businesses:
            processed_count += 1
            business_id = business["id"]
            website = business["website"]

            # Update business with website data
            if update_business_with_website_data(business_id, website):
                success_count += 1

            # Log progress periodically
            if processed_count % 10 == 0:
                logger.info(f"Processed {processed_count}/{len(businesses)} businesses")

        logger.info(
            f"Finished processing {processed_count} businesses, "
            f"{success_count} successful"
        )

    except Exception as e:
        logger.error(f"Error processing pending websites: {e}")
        return processed_count, success_count

    return processed_count, success_count
