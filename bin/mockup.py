#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Mockup Generator
Generates website mockups for businesses based on their features and industry.

This is an entry point wrapper that calls the refactored module implementation.

Usage:
    python bin/mockup.py [--limit N] [--id BUSINESS_ID]
Options:
    --limit N        Limit the number of businesses to process (default: all)
    --id BUSINESS_ID Process only the specified business ID
"""

import sys

# Import the entry point from the refactored package
from leadfactory.pipeline.mockup import main

if __name__ == "__main__":
    sys.exit(main())
