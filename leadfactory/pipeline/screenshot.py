#!/usr/bin/env python3
"""
Screenshot generation module for the lead factory pipeline.
"""

import argparse
import logging
import os
import tempfile
from typing import Optional

from leadfactory.storage import get_storage

logger = logging.getLogger(__name__)


def get_businesses_needing_screenshots(limit: Optional[int] = None) -> list[dict]:
    """Get businesses that need screenshots taken."""
    try:
        storage = get_storage()

        # Get businesses that have websites but no screenshot assets
        businesses = storage.get_businesses_needing_screenshots(limit=limit)

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
        storage = get_storage()

        success = storage.create_asset(
            business_id=business_id,
            asset_type="screenshot",
            file_path=screenshot_path,
            url=screenshot_url,
        )

        if success:
            logger.info(f"Created screenshot asset for business {business_id}")

        return success

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
    screenshot_success = False

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

        from leadfactory.cost.service_cost_decorators import enforce_service_cost_cap

        try:
            # Apply cost cap for screenshot API call (estimated $0.001 per screenshot)
            with enforce_service_cost_cap(
                "screenshotone", "capture", estimated_cost=0.001
            ):
                response = requests.get(api_url, params=params, timeout=30)
                response.raise_for_status()

            # Save the screenshot file
            with open(screenshot_path, "wb") as f:
                f.write(response.content)

            logger.info(
                f"Screenshot saved to {screenshot_path} ({len(response.content)} bytes)"
            )
            screenshot_success = True

        except requests.exceptions.RequestException as e:
            logger.error(f"ScreenshotOne API failed for {website}: {e}")
            logger.warning("Will try local screenshot capture as fallback")

    # If API failed or no key provided, try local screenshot capture
    if not screenshot_success:
        logger.info("Attempting local screenshot capture using Playwright")

        try:
            from .screenshot_local import (
                capture_screenshot_sync,
                is_playwright_available,
            )

            # Check if Playwright is available
            if not is_playwright_available():
                logger.warning(
                    "Playwright not available. Install with: pip install playwright && playwright install chromium"
                )
                # For now, create a placeholder image in test environments
                if (
                    os.getenv("E2E_MODE") == "true"
                    or os.getenv("PRODUCTION_TEST_MODE") == "true"
                ):
                    logger.info("Creating placeholder screenshot for test environment")
                    # Create a simple placeholder PNG
                    from PIL import Image, ImageDraw, ImageFont

                    # Create a simple image with text
                    img = Image.new("RGB", (1280, 800), color="#f0f0f0")
                    draw = ImageDraw.Draw(img)

                    # Add text
                    text = f"Screenshot Placeholder\n{business_name}\n{website}"
                    try:
                        # Try to use a nice font, fall back to default if not available
                        font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc", 36
                        )
                    except (OSError, IOError):
                        font = ImageFont.load_default()

                    # Calculate text position
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    position = ((1280 - text_width) // 2, (800 - text_height) // 2)

                    draw.text(position, text, fill="#333333", font=font)
                    img.save(screenshot_path, "PNG")

                    logger.info(f"Created placeholder screenshot at {screenshot_path}")
                    screenshot_success = True
                else:
                    raise Exception(
                        "Playwright not available for local screenshot capture"
                    )
            else:
                # Use Playwright for local screenshot
                screenshot_success = capture_screenshot_sync(
                    url=website,
                    output_path=screenshot_path,
                    viewport_width=1280,
                    viewport_height=800,
                    full_page=False,
                    timeout=30000,
                )

                if screenshot_success:
                    logger.info(
                        f"Local screenshot captured successfully at {screenshot_path}"
                    )
                else:
                    raise Exception("Local screenshot capture failed")

        except ImportError as e:
            logger.error(f"Failed to import screenshot_local module: {e}")
            if not (
                os.getenv("E2E_MODE") == "true"
                or os.getenv("PRODUCTION_TEST_MODE") == "true"
            ):
                raise Exception("No screenshot method available")
        except Exception as e:
            logger.error(f"Local screenshot capture failed: {e}")
            if not (
                os.getenv("E2E_MODE") == "true"
                or os.getenv("PRODUCTION_TEST_MODE") == "true"
            ):
                raise Exception(f"Screenshot generation failed: {e}")

    if not screenshot_success:
        logger.error("All screenshot methods failed")
        raise Exception("Failed to generate screenshot")

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
            storage = get_storage()
            business = storage.get_business(args.id)
            if business:
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
