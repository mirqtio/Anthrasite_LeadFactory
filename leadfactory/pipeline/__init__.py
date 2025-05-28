"""
Pipeline package for LeadFactory.

This package contains the core pipeline modules for the LeadFactory application,
including scraping, enrichment, deduplication, scoring, and email generation.
"""

# Import the available pipeline modules
from . import dedupe, email_queue, enrich, mockup, score, scrape

__all__ = [
    "scrape",
    "enrich",
    "dedupe",
    "score",
    "email_queue",
    "mockup",
]
