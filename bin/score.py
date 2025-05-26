#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Lead Scoring
Scores businesses based on various criteria and prioritizes them for outreach.

This is an entry point wrapper that calls the refactored module implementation.

Usage:
    python bin/score.py [--limit N] [--id BUSINESS_ID]
Options:
    --limit N        Limit the number of businesses to score (default: all)
    --id BUSINESS_ID Process only the specified business ID
"""
import sys

# Import the entry point from the refactored package
from leadfactory.pipeline.score import main

if __name__ == "__main__":
    sys.exit(main())
