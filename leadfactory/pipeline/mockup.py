"""
Mockup generation module for LeadFactory.

This module provides functionality to generate mockups of business websites.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

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
        logger.error(f"Error getting businesses needing mockups: {e}")
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
        logger.error(f"Error creating mockup asset for business {business_id}: {e}")
        return False


def validate_mockup_dependencies(business_id: int) -> dict[str, Any]:
    """
    Validate that all required dependencies are available for mockup generation.

    Args:
        business_id: ID of the business to validate dependencies for

    Returns:
        Dictionary with validation results and missing dependencies
    """
    missing_deps = []
    validation_result = {
        "valid": True,
        "missing_dependencies": [],
        "business_data": None,
        "screenshot_path": None,
    }

    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            # Check if business exists and has required data
            cursor.execute(
                "SELECT id, name, website FROM businesses WHERE id = %s", (business_id,)
            )
            business_row = cursor.fetchone()

            if not business_row:
                missing_deps.append("business_record")
            else:
                validation_result["business_data"] = {
                    "id": business_row[0],
                    "name": business_row[1],
                    "website": business_row[2],
                }

                # Validate website is present
                if not business_row[2] or not business_row[2].strip():
                    missing_deps.append("website_url")

            # Check for screenshot asset (required for mockup generation)
            cursor.execute(
                """
                SELECT file_path FROM assets
                WHERE business_id = %s AND asset_type = 'screenshot'
                ORDER BY created_at DESC LIMIT 1
                """,
                (business_id,),
            )
            screenshot_row = cursor.fetchone()

            if not screenshot_row:
                missing_deps.append("screenshot_asset")
            else:
                screenshot_path = screenshot_row[0]
                if not os.path.exists(screenshot_path):
                    missing_deps.append("screenshot_file")
                else:
                    validation_result["screenshot_path"] = screenshot_path

            # Update validation result
            validation_result["missing_dependencies"] = missing_deps
            validation_result["valid"] = len(missing_deps) == 0

            return validation_result

    except Exception as e:
        logger.error(
            f"Error validating mockup dependencies for business {business_id}: {e}"
        )
        return {
            "valid": False,
            "missing_dependencies": ["validation_error"],
            "error": str(e),
        }


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

    # Validate dependencies before proceeding
    validation = validate_mockup_dependencies(business_id)
    if not validation["valid"]:
        logger.warning(
            f"Mockup generation failed dependency validation for business {business_id}"
        )
        logger.warning(f"Missing dependencies: {validation['missing_dependencies']}")
        return {
            "business_id": business_id,
            "status": "failed",
            "error": f"Missing required dependencies: {', '.join(validation['missing_dependencies'])}",
            "missing_dependencies": validation["missing_dependencies"],
        }

    try:
        # Create mockups directory if it doesn't exist
        mockup_dir = "/tmp/mockups"
        os.makedirs(mockup_dir, exist_ok=True)

        mockup_filename = f"mockup_{business_id}.png"
        mockup_path = f"{mockup_dir}/{mockup_filename}"
        mockup_url = f"https://storage.example.com/mockups/{mockup_filename}"

        # Generate mockup from screenshot
        mockup_img = None
        screenshot_path = validation["screenshot_path"]

        from PIL import Image, ImageDraw, ImageFont

        logger.info(f"Creating mockup based on screenshot: {screenshot_path}")
        try:
            base_img = Image.open(screenshot_path)
            # Resize to mockup dimensions if needed
            mockup_img = base_img.resize((1200, 800), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.error(f"Could not load screenshot {screenshot_path}: {e}")
            raise Exception(f"Failed to load screenshot for mockup generation: {e}")

        if not mockup_img:
            raise Exception("Failed to generate mockup image")

        # Save the mockup
        mockup_img.save(mockup_path, "PNG")
        logger.info(f"Mockup saved to {mockup_path}")

        # Create the asset record
        success = create_mockup_asset(business_id, mockup_path, mockup_url)

        if success:
            result = {
                "business_id": business_id,
                "mockup_url": mockup_url,
                "status": "generated",
                "timestamp": "2025-05-25T08:57:00Z",
            }
            return result
        else:
            return {
                "business_id": business_id,
                "status": "failed",
                "error": "Failed to create mockup asset",
            }
    except Exception as e:
        logger.error(f"Error generating mockup for business {business_id}: {e}")
        return {
            "business_id": business_id,
            "status": "failed",
            "error": str(e),
        }


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
