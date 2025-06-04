"""
String utility functions for text processing and manipulation.
"""

import html
import re


def normalize_text(text):
    """
    Normalize text by converting to lowercase, removing special characters,
    and standardizing whitespace.

    Args:
        text (str): The text to normalize

    Returns:
        str: The normalized text
    """
    if text is None:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Replace special characters with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Standardize whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip leading and trailing whitespace
    text = text.strip()

    return text


def clean_html(html_text):
    """
    Clean HTML by removing all tags and decoding HTML entities.

    Args:
        html_text (str): The HTML text to clean

    Returns:
        str: The cleaned text
    """
    if html_text is None:
        return ""

    if not html_text:
        return ""

    # Remove all HTML tags
    text = re.sub(r"<[^>]+>", " ", html_text)

    # Decode HTML entities
    text = html.unescape(text)

    # Standardize whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip leading and trailing whitespace
    text = text.strip()

    return text


def extract_domain(email):
    """
    Extract the domain from an email address.

    Args:
        email (str): The email address

    Returns:
        str: The domain (without subdomains)
    """
    if email is None:
        return ""

    if not email or "@" not in email:
        return ""

    # Extract the domain part
    domain = email.split("@")[-1]

    # Extract the main domain (without subdomains)
    parts = domain.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])

    return domain


# Re-export all functions
__all__ = [
    "normalize_text",
    "clean_html",
    "extract_domain",
]
