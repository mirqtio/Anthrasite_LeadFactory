"""
Business enrichment module for LeadFactory.

This module provides functionality to enrich business data with additional information.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Import the unified logging system
from leadfactory.utils.logging import LogContext, get_logger, log_execution_time

# Import metrics
from leadfactory.utils.metrics import (
    LEADS_ENRICHED,
    PIPELINE_DURATION,
    PIPELINE_ERRORS,
    MetricsTimer,
    record_metric,
)

# Initialize logging with the unified system
logger = get_logger(__name__)


@log_execution_time
def enrich_business(business: dict[str, Any], tier: int = 1) -> bool:
    """
    Enrich a business with tech stack and performance data.

    Args:
        business: Business information dictionary.
        tier: Tier level (1, 2, or 3).

    Returns:
        True if successful, False otherwise.
    """
    business_id = business.get("id", "unknown")
    business_name = business.get("name", "unknown")

    # Use LogContext to add structured context to all log messages in this scope
    with LogContext(
        logger, business_id=business_id, business_name=business_name, tier=tier
    ):
        logger.info(
            f"Enriching business {business_name}",
            extra={"operation": "enrich_business"},
        )

        # Use MetricsTimer to measure and record the duration of the enrichment process
        with MetricsTimer(PIPELINE_DURATION, stage="enrichment", tier=str(tier)):
            try:
                # Implementation to be migrated from bin/enrich.py
                # ... actual enrichment logic would go here ...

                # Record successful enrichment in metrics
                LEADS_ENRICHED.labels(tier=str(tier)).inc()

                logger.info(
                    f"Successfully enriched business {business_name}",
                    extra={"outcome": "success"},
                )
                return True

            except Exception as e:
                # Record error in metrics
                PIPELINE_ERRORS.labels(
                    stage="enrichment", error_type=type(e).__name__
                ).inc()

                logger.error(
                    f"Failed to enrich business {business_name}: {str(e)}",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "outcome": "failure",
                    },
                )
                return False


@log_execution_time
def enrich_businesses(
    limit: Optional[int] = None,
    business_id: Optional[int] = None,
    tier: Optional[int] = None,
) -> int:
    """
    Enrich multiple businesses.

    Args:
        limit: Maximum number of businesses to process.
        business_id: Specific business ID to process.
        tier: Tier level (1, 2, or 3).

    Returns:
        Number of businesses successfully enriched.
    """
    # Default tier to 1 if not specified
    tier = tier or 1

    # Log with structured context
    logger.info(
        "Starting batch enrichment process",
        extra={
            "operation": "batch_enrichment",
            "limit": limit,
            "business_id": business_id,
            "tier": tier,
            "batch_id": f"enrich_{int(time.time())}",
        },
    )

    # Use MetricsTimer to measure and record the duration of the batch process
    with MetricsTimer(PIPELINE_DURATION, stage="batch_enrichment", tier=str(tier)):
        try:
            # Implementation to be migrated from bin/enrich.py
            # ... actual batch enrichment logic would go here ...

            # Mock implementation for demonstration
            successful = 0
            total = 0

            # For demonstration purposes only - would be replaced with actual implementation
            if business_id:
                # Process single business
                mock_business = {"id": business_id, "name": f"Business {business_id}"}
                result = enrich_business(mock_business, tier)
                successful += 1 if result else 0
                total = 1
            else:
                # Process multiple businesses (mock implementation)
                mock_businesses = [
                    {"id": i, "name": f"Business {i}"}
                    for i in range(1, (limit or 5) + 1)
                ]

                for business in mock_businesses:
                    result = enrich_business(business, tier)
                    successful += 1 if result else 0
                    total += 1

            # Log completion with structured data
            logger.info(
                f"Completed batch enrichment: {successful}/{total} businesses successfully enriched",
                extra={
                    "successful_count": successful,
                    "total_count": total,
                    "success_rate": successful / total if total > 0 else 0,
                    "outcome": "success",
                },
            )

            return successful

        except Exception as e:
            # Record error in metrics
            PIPELINE_ERRORS.labels(
                stage="batch_enrichment", error_type=type(e).__name__
            ).inc()

            logger.error(
                f"Batch enrichment process failed: {str(e)}",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "outcome": "failure",
                },
            )
            return 0


def main() -> int:
    """
    Main function for the enrichment module.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="Enrich business data")
    parser.add_argument(
        "--limit", type=int, help="Maximum number of businesses to process"
    )
    parser.add_argument("--id", type=int, help="Specific business ID to process")
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3], default=1, help="Tier level (1-3)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Configure log level if specified
    if args.log_level:
        logger.setLevel(args.log_level)

    try:
        # Start the process with structured logging
        logger.info(
            "Starting enrichment process",
            extra={"cli_args": vars(args), "operation": "cli_enrich"},
        )

        count = enrich_businesses(limit=args.limit, business_id=args.id, tier=args.tier)

        # Log result with structured data
        logger.info(
            f"Enriched {count} businesses", extra={"businesses_enriched": count}
        )

        return 0 if count > 0 else 1

    except Exception as e:
        # Log any unexpected errors
        logger.error(
            f"Enrichment process failed with unexpected error: {str(e)}",
            extra={"error_type": type(e).__name__, "error_message": str(e)},
        )
        return 1
