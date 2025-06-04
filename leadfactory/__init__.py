"""
Anthrasite LeadFactory package for business lead generation and outreach.

This package contains modules for lead generation, data enrichment, scoring,
email creation, and campaign management for Anthrasite LeadFactory.
"""

__version__ = "0.1.0"

# Import key modules to expose at the package level
from . import api, cost, pipeline, scoring, utils

# Configuration
from .config import get_config, load_config

# These will be populated as modules are migrated
# from leadfactory.pipeline import scrape, enrich, dedupe, score, email_queue
# from leadfactory.utils import batch_metrics, batch_tracker, logging_config, metrics
# from leadfactory.cost import budget_gate, cost_tracking

__all__ = [
    "api",
    "cost",
    "pipeline",
    "scoring",
    "utils",
    "get_config",
    "load_config",
    "__version__",
]
