"""
String utility functions for LeadFactory.

This module provides utility functions for string manipulation and processing.
"""

# This is a stub file that will be populated when the actual code is migrated
# For now, we'll re-export everything from the original module for compatibility

import sys
from pathlib import Path

# Add the parent directory to the path so we can import from bin
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import from the original location
from bin.utils.string_utils import *

# Re-export everything from the original module
__all__ = [
    "normalize_text",
    "clean_html",
    "extract_domain",
    # Add other exported symbols here
]
