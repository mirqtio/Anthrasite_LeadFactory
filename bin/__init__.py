"""
Package containing all the main scripts for the Anthrasite LeadFactory.
This makes the bin directory a proper Python package, allowing for cleaner imports.
"""

# Import modules to make them available when importing from bin
from . import budget_audit, dedupe, email_queue, enrich, mockup, score, scrape

# Make the modules available at the package level
__all__ = [
    "scrape",
    "enrich",
    "dedupe",
    "score",
    "mockup",
    "email_queue",
    "budget_audit",
]
