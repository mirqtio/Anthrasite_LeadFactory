#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Raw Data Processor
Processes pending websites and stores their HTML content.
Also manages data retention for raw HTML and LLM logs.

Usage:
    python bin/process_raw_data.py [--process-websites] [--check-retention] [--verbose]
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Use lowercase versions for Python 3.9 compatibility

# Use lowercase versions for Python 3.9 compatibility

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import utility functions
from utils.llm_logger import check_retention_status
from utils.logging_config import get_logger
from utils.website_scraper import process_pending_websites

# Set up logging
logger = get_logger(__name__)


def process_websites(verbose: bool = False) -> tuple[int, int]:
    """Process pending websites and store their HTML content.

    Args:
        verbose: Whether to print verbose output.

    Returns:
        tuple of (processed_count, success_count).
    """
    if verbose:
        logger.info("Processing pending websites...")

    processed_count, success_count = process_pending_websites()

    if verbose:
        logger.info(f"Processed {processed_count} websites, {success_count} successful")

    return processed_count, success_count


def check_retention(verbose: bool = False) -> dict[str, Any]:
    """Check data retention status.

    Args:
        verbose: Whether to print verbose output.

    Returns:
        dictionary with retention status information.
    """
    if verbose:
        logger.info("Checking data retention status...")

    status = check_retention_status()

    if verbose:
        # Print status report
        logger.info(f"Data Retention Status (Policy: {status['retention_days']} days)")
        logger.info(
            f"HTML Storage: {status['html_storage']['total_count']} total, "
            f"{status['html_storage']['expired_count']} expired, "
            f"{status['html_storage']['retention_percentage']:.2f}% retained"
        )
        logger.info(
            f"LLM Logs: {status['llm_logs']['total_count']} total, "
            f"{status['llm_logs']['expired_count']} expired, "
            f"{status['llm_logs']['retention_percentage']:.2f}% retained"
        )

    return status


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Raw Data Processor")
    parser.add_argument(
        "--process-websites",
        action="store_true",
        help="Process pending websites and store their HTML content",
    )
    parser.add_argument(
        "--check-retention",
        action="store_true",
        help="Check data retention status",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print verbose output",
    )
    args = parser.parse_args()

    # If no actions specified, show help
    if not (args.process_websites or args.check_retention):
        parser.print_help()
        return 0

    try:
        # Process websites if requested
        if args.process_websites:
            processed_count, success_count = process_websites(args.verbose)

        # Check retention if requested
        if args.check_retention:
            check_retention(args.verbose)

        return 0
    except Exception as e:
        logger.error(f"Error in raw data processor: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
