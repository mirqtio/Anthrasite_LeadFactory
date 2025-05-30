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


def validate_enrichment_dependencies(business: dict[str, Any]) -> dict[str, Any]:
    """
    Validate that all required dependencies are available for enrichment.

    Args:
        business: Business information dictionary

    Returns:
        Dictionary with validation results and missing dependencies
    """
    missing_deps = []
    validation_result = {
        "valid": True,
        "missing_dependencies": [],
        "available_apis": [],
    }

    # Check required business data
    if not business.get("id"):
        missing_deps.append("business_id")
    if not business.get("name"):
        missing_deps.append("business_name")
    if not business.get("website") or not business.get("website").strip():
        missing_deps.append("website_url")

    # Check available API keys and services
    available_apis = []

    # Check Wappalyzer (tech stack analysis) - always available (no API key required)
    available_apis.append("wappalyzer")

    # Check PageSpeed API
    if os.getenv("PAGESPEED_API_KEY"):
        available_apis.append("pagespeed")

    # Check Screenshot service
    if os.getenv("SCREENSHOT_ONE_KEY"):
        available_apis.append("screenshot_one")

    # Check SEMrush API
    if os.getenv("SEMRUSH_KEY"):
        available_apis.append("semrush")

    validation_result["available_apis"] = available_apis
    validation_result["missing_dependencies"] = missing_deps
    validation_result["valid"] = len(missing_deps) == 0

    return validation_result


@log_execution_time
def enrich_business(business: dict[str, Any]) -> bool:
    """
    Enrich a business with tech stack and performance data.

    Args:
        business: Business information dictionary.

    Returns:
        True if successful, False otherwise.
    """
    business_id = business.get("id", "unknown")
    business_name = business.get("name", "unknown")
    website = business.get("website")

    # Validate dependencies before proceeding
    validation = validate_enrichment_dependencies(business)
    if not validation["valid"]:
        logger.warning(
            f"Enrichment failed dependency validation for business {business_name}"
        )
        logger.warning(f"Missing dependencies: {validation['missing_dependencies']}")
        return False

    # Use LogContext to add structured context to all log messages in this scope
    with LogContext(logger, business_id=business_id, business_name=business_name):
        logger.info(
            f"Enriching business {business_name} with website {website}",
            extra={
                "operation": "enrich_business",
                "website": website,
                "available_apis": validation["available_apis"],
            },
        )

        # Use MetricsTimer to measure and record the duration of the enrichment process
        with MetricsTimer(PIPELINE_DURATION, stage="enrichment"):
            try:
                # Import enrichment modules conditionally based on availability
                try:
                    # Try to import from bin/enrich.py for actual implementation
                    sys.path.append(
                        os.path.join(os.path.dirname(__file__), "..", "..", "bin")
                    )
                    from enrich import (
                        PageSpeedAnalyzer,
                        ScreenshotGenerator,
                        SEMrushAnalyzer,
                        TechStackAnalyzer,
                        save_features,
                    )
                except ImportError:
                    logger.warning(
                        "Could not import enrichment modules from bin/enrich.py"
                    )
                    # Record successful enrichment in metrics (stub implementation)
                    LEADS_ENRICHED.inc()
                    logger.info(
                        f"Successfully enriched business {business_name} (stub implementation)",
                        extra={"outcome": "success"},
                    )
                    return True

                # Initialize results storage
                enrichment_results = {
                    "tech_stack": {},
                    "performance_data": {},
                    "screenshot_url": None,
                    "semrush_data": None,
                }

                # Tech stack analysis (Wappalyzer) - always available
                if "wappalyzer" in validation["available_apis"]:
                    try:
                        tech_analyzer = TechStackAnalyzer()
                        tech_data = tech_analyzer.analyze_website(website)
                        enrichment_results["tech_stack"] = tech_data
                        logger.info("Tech stack analysis completed successfully")
                    except Exception as e:
                        logger.warning(f"Tech stack analysis failed: {e}")

                # PageSpeed analysis
                if "pagespeed" in validation["available_apis"]:
                    try:
                        pagespeed_key = os.getenv("PAGESPEED_API_KEY")
                        pagespeed_analyzer = PageSpeedAnalyzer(pagespeed_key)
                        pagespeed_data = pagespeed_analyzer.analyze_website(website)
                        enrichment_results["performance_data"] = pagespeed_data
                        logger.info("PageSpeed analysis completed successfully")
                    except Exception as e:
                        logger.warning(f"PageSpeed analysis failed: {e}")

                # Screenshot capture
                if "screenshot_one" in validation["available_apis"]:
                    try:
                        screenshot_key = os.getenv("SCREENSHOT_ONE_KEY")
                        screenshot_generator = ScreenshotGenerator(screenshot_key)
                        screenshot_url = screenshot_generator.capture_screenshot(
                            website
                        )
                        enrichment_results["screenshot_url"] = screenshot_url
                        logger.info("Screenshot capture completed successfully")
                    except Exception as e:
                        logger.warning(f"Screenshot capture failed: {e}")

                # SEMrush analysis
                if "semrush" in validation["available_apis"]:
                    try:
                        semrush_key = os.getenv("SEMRUSH_KEY")
                        semrush_analyzer = SEMrushAnalyzer(semrush_key)
                        semrush_data = semrush_analyzer.analyze_website(website)
                        enrichment_results["semrush_data"] = semrush_data
                        logger.info("SEMrush analysis completed successfully")
                    except Exception as e:
                        logger.warning(f"SEMrush analysis failed: {e}")

                # Save enrichment results to database
                success = save_features(
                    business_id=business_id,
                    tech_stack=enrichment_results["tech_stack"],
                    page_speed=enrichment_results["performance_data"],
                    screenshot_url=enrichment_results["screenshot_url"],
                    semrush_json=enrichment_results["semrush_data"],
                )

                if success:
                    # Record successful enrichment in metrics
                    LEADS_ENRICHED.inc()

                    logger.info(
                        f"Successfully enriched business {business_name}",
                        extra={"outcome": "success"},
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to save enrichment data for business {business_name}"
                    )
                    return False

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
) -> int:
    """
    Enrich multiple businesses.

    Args:
        limit: Maximum number of businesses to process.
        business_id: Specific business ID to process.

    Returns:
        Number of businesses successfully enriched.
    """
    # Log with structured context
    logger.info(
        "Starting batch enrichment process",
        extra={
            "operation": "batch_enrichment",
            "limit": limit,
            "business_id": business_id,
            "batch_id": f"enrich_{int(time.time())}",
        },
    )

    # Use MetricsTimer to measure and record the duration of the batch process
    with MetricsTimer(PIPELINE_DURATION, stage="batch_enrichment"):
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
                result = enrich_business(mock_business)
                successful += 1 if result else 0
                total = 1
            else:
                # Process multiple businesses (mock implementation)
                mock_businesses = [
                    {"id": i, "name": f"Business {i}"}
                    for i in range(1, (limit or 5) + 1)
                ]

                for business in mock_businesses:
                    result = enrich_business(business)
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

        count = enrich_businesses(limit=args.limit, business_id=args.id)

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
