"""
String utility functions for text processing and normalization.

This module provides a compatibility layer for string utilities,
importing functions from the original location in bin/utils/string_utils.py
"""

import re
from urllib.parse import urlparse

# Import specific functions instead of star import
try:
    from bin.utils.string_utils import clean_html, extract_domain, normalize_text
except ImportError:
    # Fallback implementations if import fails
    def normalize_text(text):
        """Normalize text by removing extra whitespace and converting to lowercase."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip().lower())

    def clean_html(text):
        """Remove HTML tags from text."""
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", text)

    def extract_domain(url):
        """Extract domain from URL."""
        if not url:
            return ""
        try:
            return urlparse(url).netloc
        except Exception:
            return ""


# Re-export everything from the original module
__all__ = [
    "normalize_text",
    "clean_html",
    "extract_domain",
]
