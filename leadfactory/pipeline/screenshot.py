#!/usr/bin/env python3
"""
Screenshot generation module for the lead factory pipeline.
"""
import argparse
import logging
import os
import tempfile
from typing import Optional

from leadfactory.utils.e2e_db_connector import db_connection

logger = logging.getLogger(__name__)


def get_businesses_needing_screenshots(limit: Optional[int] = None) -> list[dict]:
    """Get businesses that need screenshots taken."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            # Get businesses that have websites but no screenshot assets
            query = """
            SELECT DISTINCT b.id, b.name, b.website
            FROM businesses b
            LEFT JOIN assets a ON b.id = a.business_id AND a.asset_type = 'screenshot'
            WHERE b.website IS NOT NULL
              AND b.website != ''
              AND a.id IS NULL
            ORDER BY b.id
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            businesses = []
            for row in rows:
                businesses.append({"id": row[0], "name": row[1], "website": row[2]})

            logger.info(f"Found {len(businesses)} businesses needing screenshots")
            return businesses

    except Exception as e:
        logger.exception(f"Error getting businesses for screenshots: {e}")
        return []


def create_screenshot_asset(
    business_id: int, screenshot_path: str, screenshot_url: str
) -> bool:
    """Create a screenshot asset record in the database."""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO assets (business_id, asset_type, file_path, url)
                VALUES (%s, 'screenshot', %s, %s)
            """,
                (business_id, screenshot_path, screenshot_url),
            )

            conn.commit()
            logger.info(f"Created screenshot asset for business {business_id}")
            return True

    except Exception as e:
        logger.exception(
            f"Error creating screenshot asset for business {business_id}: {e}"
        )
        return False


def generate_business_screenshot(business: dict) -> bool:
    """Generate a screenshot for a business website."""
    business_id = business["id"]
    business_name = business["name"]
    website = business["website"]

    logger.info(f"Generating screenshot for {business_name} ({website})")

    # Create screenshots directory if it doesn't exist
    screenshot_dir = tempfile.mkdtemp(prefix="screenshots_")  # nosec B108
    os.makedirs(screenshot_dir, exist_ok=True)

    screenshot_filename = f"screenshot_{business_id}.png"
    screenshot_path = f"{screenshot_dir}/{screenshot_filename}"

    # Check if we have ScreenshotOne API key for real screenshots
    screenshot_one_key = os.getenv("SCREENSHOT_ONE_KEY")

    if screenshot_one_key:
        # Use real ScreenshotOne API
        logger.info(f"Using ScreenshotOne API to capture {website}")

        # ScreenshotOne API parameters
        api_url = "https://api.screenshotone.com/take"
        params = {
            "access_key": screenshot_one_key,
            "url": website,
            "device_scale_factor": 1,
            "format": "png",
            "viewport_width": 1280,
            "viewport_height": 800,
            "full_page": False,
            "timeout": 30,  # 30 seconds (API expects seconds, not milliseconds)
        }

        import requests

        try:
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()

            # Save the screenshot file
            with open(screenshot_path, "wb") as f:
                f.write(response.content)

            logger.info(
                f"Screenshot saved to {screenshot_path} ({len(response.content)} bytes)"
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"ScreenshotOne API failed for {website}: {e}")
            logger.error("Cannot proceed without real screenshot - failing pipeline")
            raise Exception(f"Screenshot generation failed: {e}")

    else:
        # No API key provided - this is a configuration error
        logger.error(
            "No ScreenshotOne API key provided - cannot generate real screenshots"
        )
        raise Exception("SCREENSHOT_ONE_KEY is required for real screenshot generation")

    # Create storage URL (for now, use a placeholder URL)
    screenshot_url = f"https://storage.example.com/screenshots/{screenshot_filename}"

    # Create the asset record
    success = create_screenshot_asset(business_id, screenshot_path, screenshot_url)

    if success:
        logger.info(f"Successfully generated screenshot for business {business_id}")
        return True
    else:
        logger.error(f"Failed to create screenshot asset for business {business_id}")
        raise Exception(f"Failed to create screenshot asset for business {business_id}")


def main():
    """Main entry point for screenshot generation."""
    parser = argparse.ArgumentParser(
        description="Generate business website screenshots"
    )
    parser.add_argument("--id", type=int, help="Business ID to generate screenshot for")
    parser.add_argument(
        "--limit", type=int, help="Limit number of businesses to process"
    )

    args = parser.parse_args()

    if args.id:
        # Process single business
        try:
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, website FROM businesses WHERE id = %s", (args.id,)
                )
                row = cursor.fetchone()

                if row:
                    business = {"id": row[0], "name": row[1], "website": row[2]}
                    success = generate_business_screenshot(business)
                    return 0 if success else 1
                else:
                    logger.error(f"Business with ID {args.id} not found")
                    return 1
        except Exception as e:
            logger.exception(f"Error processing business {args.id}: {e}")
            return 1
    else:
        # Process all businesses needing screenshots
        businesses = get_businesses_needing_screenshots(limit=args.limit)

        if not businesses:
            logger.info("No businesses need screenshots")
            return 0

        total_processed = 0
        total_success = 0

        for business in businesses:
            total_processed += 1
            try:
                if generate_business_screenshot(business):
                    total_success += 1
            except Exception as e:
                logger.exception(
                    f"Error generating screenshot for business {business['id']}: {e}"
                )

        logger.info(
            f"Screenshot generation complete: {total_success}/{total_processed} successful"
        )

        # Return failure exit code if no screenshots were generated successfully
        if total_processed > 0 and total_success == 0:
            logger.error(
                "All screenshot generation attempts failed - returning failure exit code"
            )
            return 1
        elif total_success < total_processed:
            logger.warning(
                f"Some screenshot generation attempts failed ({total_success}/{total_processed} successful)"
            )
            return 1

        return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
