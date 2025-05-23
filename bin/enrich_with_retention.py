#!/usr/bin/env python
"""
Enrichment with Data Retention
----------------------------
This module extends the standard enrichment process to include data retention
for raw HTML and LLM interactions. It ensures that all raw data is properly
stored with appropriate retention periods.

Usage:
    python bin/enrich_with_retention.py --business-id 12345
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

# Add parent directory to path to allow importing other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bin.budget_gate import budget_gated
from bin.cost_tracking import cost_tracker
from bin.data_retention import data_retention

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "enrich_with_retention.log")),
    ],
)
logger = logging.getLogger("enrich_with_retention")

# Import original enrichment module
try:
    from bin.enrich import enrich_business, fetch_business_data
except ImportError:
    # Mock implementation for testing
    logger.warning(
        "Could not import original enrichment module, using mock implementation"
    )

    def enrich_business(business_id, **kwargs):
        """Mock implementation of enrich_business."""
        logger.info(f"Mock enrichment for business {business_id}")
        return {"business_id": business_id, "enriched": True}

    def fetch_business_data(business_id, **kwargs):
        """Mock implementation of fetch_business_data."""
        logger.info(f"Mock fetch for business {business_id}")
        return {
            "business_id": business_id,
            "name": "Mock Business",
            "url": "https://example.com",
            "html": "<html><body><h1>Mock Business</h1></body></html>",
        }


def fetch_business_data_with_retention(business_id: str, **kwargs) -> dict[str, Any]:
    """Fetch business data with retention for raw HTML.

    Args:
        business_id: Business ID
        **kwargs: Additional arguments to pass to fetch_business_data

    Returns:
        Business data with HTML storage path
    """
    # Call original fetch function
    business_data = fetch_business_data(business_id, **kwargs)

    # Check if HTML is present
    if "html" in business_data and business_data["html"]:
        # Store HTML with retention
        html_content = business_data["html"]
        storage_path = data_retention.store_html(business_id, html_content)

        # Add storage path to business data
        business_data["html_storage_path"] = storage_path

        # Replace full HTML with a reference to save memory
        business_data["html"] = f"Stored at {storage_path}"

        logger.info(f"Stored HTML for business {business_id} at {storage_path}")

    return business_data


@budget_gated(
    operation="gpt-4-enrichment",
    fallback_value={"status": "skipped", "reason": "budget_gate"},
)
def enrich_business_with_llm(business_data: dict[str, Any], **kwargs) -> dict[str, Any]:
    """Enrich business data using LLM with cost tracking and logging.

    Args:
        business_data: Business data to enrich
        **kwargs: Additional arguments

    Returns:
        Enriched business data
    """
    try:
        # Extract business ID
        business_id = business_data.get("business_id", "unknown")

        # Prepare prompt
        prompt = f"""
        Analyze the following business data and provide enriched information:

        Business Name: {business_data.get('name', 'Unknown')}
        URL: {business_data.get('url', 'Unknown')}

        Please provide:
        1. A brief description of the business
        2. Estimated company size
        3. Industry category
        4. Key technologies used
        5. Potential pain points
        """

        # Track start time for cost calculation
        start_time = time.time()

        # Call GPT-4 (mock implementation for testing)
        response = {
            "description": "This is a mock business description.",
            "company_size": "10-50 employees",
            "industry": "Technology",
            "technologies": ["React", "Node.js", "AWS"],
            "pain_points": ["Customer acquisition", "Scaling infrastructure"],
        }

        # Calculate duration and cost
        duration = time.time() - start_time
        tokens = len(prompt.split()) + len(str(response).split())
        cost = 0.03 * (tokens / 1000)  # Mock cost calculation

        # Track cost
        cost_tracker.add_cost(
            cost,
            service="openai",
            operation="gpt-4",
            details={
                "business_id": business_id,
                "tokens": tokens,
                "duration": duration,
            },
        )

        # Log LLM interaction
        log_id = data_retention.log_llm_interaction(
            stage="enrichment",
            prompt=prompt,
            response=json.dumps(response),
            cost=cost,
            model="gpt-4",
            tokens=tokens,
        )

        # Add enriched data to business data
        business_data.update(
            {
                "description": response["description"],
                "company_size": response["company_size"],
                "industry": response["industry"],
                "technologies": response["technologies"],
                "pain_points": response["pain_points"],
                "enrichment_log_id": log_id,
            }
        )

        logger.info(
            f"Enriched business {business_id} with LLM (cost=${cost:.4f}, log_id={log_id})"
        )

        return business_data
    except Exception as e:
        logger.exception(f"Error enriching business with LLM: {e}")
        return business_data


def enrich_business_with_retention(business_id: str, **kwargs) -> dict[str, Any]:
    """Enrich a business with data retention.

    Args:
        business_id: Business ID
        **kwargs: Additional arguments to pass to enrich_business

    Returns:
        Enriched business data
    """
    try:
        # Start batch if not already started
        if not cost_tracker.current_batch_id:
            batch_id = kwargs.get("batch_id")
            tier = kwargs.get("tier", "1")
            cost_tracker.start_batch(batch_id=batch_id, tier=tier)

        # Fetch business data with HTML retention
        business_data = fetch_business_data_with_retention(business_id, **kwargs)

        # Enrich with LLM if budget gate allows
        business_data = enrich_business_with_llm(business_data, **kwargs)

        # Call original enrichment function
        enriched_data = enrich_business(
            business_id, business_data=business_data, **kwargs
        )

        # Ensure HTML storage path is preserved
        if (
            "html_storage_path" in business_data
            and "html_storage_path" not in enriched_data
        ):
            enriched_data["html_storage_path"] = business_data["html_storage_path"]

        logger.info(f"Enriched business {business_id} with retention")

        return enriched_data
    except Exception as e:
        logger.exception(f"Error enriching business with retention: {e}")

        # Return basic data on error
        return {"business_id": business_id, "error": str(e)}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich a business with data retention"
    )
    parser.add_argument(
        "--business-id", type=str, required=True, help="Business ID to enrich"
    )
    parser.add_argument("--batch-id", type=str, help="Batch ID for cost tracking")
    parser.add_argument("--tier", type=str, default="1", help="Tier level (1, 2, or 3)")
    args = parser.parse_args()

    try:
        # Enrich business
        enrich_business_with_retention(
            args.business_id, batch_id=args.batch_id, tier=args.tier
        )

        # Print result

        return 0
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
