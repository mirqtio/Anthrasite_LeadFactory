"""
Mockup generation module for LeadFactory.

This module provides functionality to generate mockups of business websites.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from leadfactory.utils.e2e_db_connector import db_connection

# Set up logging using unified logging system
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


def get_businesses_needing_mockups(limit: Optional[int] = None) -> list[dict]:
    """Get businesses that need mockups generated."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            # Get businesses that have screenshot assets but no mockup assets
            query = """
            SELECT DISTINCT b.id, b.name, b.website
            FROM businesses b
            INNER JOIN assets screenshot_asset ON b.id = screenshot_asset.business_id
                AND screenshot_asset.asset_type = 'screenshot'
            LEFT JOIN assets mockup_asset ON b.id = mockup_asset.business_id
                AND mockup_asset.asset_type = 'mockup'
            WHERE mockup_asset.id IS NULL
            ORDER BY b.id
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            businesses = []
            for row in rows:
                businesses.append({"id": row[0], "name": row[1], "website": row[2]})

            logger.info(f"Found {len(businesses)} businesses needing mockups")
            return businesses

    except Exception as e:
        logger.exception(f"Error getting businesses for mockups: {e}")
        return []


def create_mockup_asset(business_id: int, mockup_path: str, mockup_url: str) -> bool:
    """Create a mockup asset record in the database."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO assets (business_id, asset_type, file_path, url)
                VALUES (%s, 'mockup', %s, %s)
            """,
                (business_id, mockup_path, mockup_url),
            )

            conn.commit()
            logger.info(f"Created mockup asset for business {business_id}")
            return True

    except Exception as e:
        logger.exception(f"Error creating mockup asset for business {business_id}: {e}")
        return False


# Mock implementation of generate_business_mockup
def generate_business_mockup(
    business_id: int, options: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Generate a mockup of a business website.

    Args:
        business_id: ID of the business to generate a mockup for
        options: Optional configuration options

    Returns:
        Dictionary containing mockup details
    """
    logger.info(
        f"Generating mockup for business ID {business_id} with options {options}"
    )

    try:
        # Create mockups directory if it doesn't exist
        mockup_dir = "/tmp/mockups"
        os.makedirs(mockup_dir, exist_ok=True)

        mockup_filename = f"mockup_{business_id}.png"
        mockup_path = f"{mockup_dir}/{mockup_filename}"
        mockup_url = f"https://storage.example.com/mockups/{mockup_filename}"

        # Get business details for mockup generation
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, website FROM businesses WHERE id = %s", (business_id,)
            )
            row = cursor.fetchone()

            if not row:
                logger.error(f"Business {business_id} not found")
                return {
                    "business_id": business_id,
                    "status": "failed",
                    "error": "Business not found",
                }

            business_name, website = row

            # Check if we have a screenshot to base the mockup on
            cursor.execute(
                """
                SELECT file_path FROM assets
                WHERE business_id = %s AND asset_type = 'screenshot'
                ORDER BY created_at DESC LIMIT 1
            """,
                (business_id,),
            )
            screenshot_row = cursor.fetchone()

        # Generate the mockup file
        from PIL import Image, ImageDraw, ImageFont

        if screenshot_row and os.path.exists(screenshot_row[0]):
            # Use existing screenshot as base for mockup
            logger.info(f"Creating mockup based on screenshot: {screenshot_row[0]}")
            try:
                base_img = Image.open(screenshot_row[0])
                # Resize to mockup dimensions if needed
                mockup_img = base_img.resize((1200, 800), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.error(f"Could not load screenshot {screenshot_row[0]}: {e}")
                raise Exception(f"Failed to load screenshot for mockup generation: {e}")
        else:
            # No real screenshot available - cannot create meaningful mockup
            logger.error(f"No real screenshot available for business {business_id}")
            logger.error(
                "Cannot create mockup without real screenshot - failing pipeline"
            )
            raise Exception(
                f"Mockup generation requires real screenshot, but none found for business {business_id}"
            )

        # Save the mockup
        mockup_img.save(mockup_path, "PNG")
        logger.info(f"Mockup saved to {mockup_path}")

        # Create the asset record
        success = create_mockup_asset(business_id, mockup_path, mockup_url)

        if success:
            return {
                "business_id": business_id,
                "mockup_url": mockup_url,
                "status": "generated",
                "timestamp": "2025-05-25T08:57:00Z",
            }
        else:
            return {
                "business_id": business_id,
                "status": "failed",
                "error": "Failed to create mockup asset",
            }
    except Exception as e:
        logger.exception(f"Error generating mockup for business {business_id}: {e}")
        return {"business_id": business_id, "status": "failed", "error": str(e)}


def generate_mockups_for_all_businesses(limit: Optional[int] = None) -> bool:
    """Generate mockups for all businesses that need them."""
    businesses = get_businesses_needing_mockups(limit=limit)

    if not businesses:
        logger.info("No businesses need mockups")
        return True

    total_processed = 0
    total_success = 0

    for business in businesses:
        business_id = business["id"]
        business_name = business["name"]

        logger.info(f"Generating mockup for {business_name} (ID: {business_id})")

        total_processed += 1
        result = generate_business_mockup(business_id)

        if result.get("status") == "generated":
            total_success += 1
            logger.info(f"Successfully generated mockup for business {business_id}")
        else:
            logger.error(
                f"Failed to generate mockup for business {business_id}: {result.get('error', 'Unknown error')}"
            )

    logger.info(
        f"Mockup generation complete: {total_success}/{total_processed} successful"
    )
    return total_success > 0


def main():
    """
    Main entry point for the mockup generation script.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Generate business website mockups")
    parser.add_argument("--id", type=int, help="Business ID to generate mockup for")
    parser.add_argument("--output", type=str, help="Output directory for mockups")

    args = parser.parse_args()

    if args.id:
        result = generate_business_mockup(args.id)
        logger.info(
            f"Generated mockup for business ID {args.id}", extra={"result": result}
        )
    else:
        logger.error("Please specify a business ID with --id")
        return 1

    return 0


__all__ = [
    "generate_business_mockup",
    "generate_mockups_for_all_businesses",
    "main",
]
