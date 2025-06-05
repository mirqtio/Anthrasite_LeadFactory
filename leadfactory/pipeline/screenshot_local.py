"""
Local screenshot capture using Playwright.

This module provides local screenshot capture functionality as a fallback
to the ScreenshotOne API, using Playwright for browser automation.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class LocalScreenshotCapture:
    """Captures screenshots using Playwright."""

    def __init__(self):
        """Initialize the local screenshot capture."""
        self.playwright = None
        self.browser = None
        self.browser_type = "chromium"  # Can be "chromium", "firefox", or "webkit"

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self):
        """Start Playwright and launch browser."""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()

            # Launch browser with specific options
            if self.browser_type == "chromium":
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-gpu",
                    ],
                )
            elif self.browser_type == "firefox":
                self.browser = await self.playwright.firefox.launch(headless=True)
            else:
                self.browser = await self.playwright.webkit.launch(headless=True)

            logger.info(f"Started {self.browser_type} browser for screenshot capture")

        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise

    async def stop(self):
        """Stop browser and Playwright."""
        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        logger.info("Stopped browser for screenshot capture")

    async def capture_screenshot(
        self,
        url: str,
        output_path: str,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        full_page: bool = False,
        timeout: int = 30000,
    ) -> bool:
        """
        Capture a screenshot of a website.

        Args:
            url: Website URL to capture
            output_path: Path to save the screenshot
            viewport_width: Browser viewport width
            viewport_height: Browser viewport height
            full_page: Whether to capture full page or just viewport
            timeout: Page load timeout in milliseconds

        Returns:
            True if successful, False otherwise
        """
        if not self.browser:
            logger.error("Browser not started. Call start() first.")
            return False

        page = None
        try:
            # Ensure URL has protocol
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            # Create a new page with viewport settings
            page = await self.browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )

            # Set user agent to appear as a real browser
            await page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )

            logger.info(f"Navigating to {url}")

            # Navigate to the page
            response = await page.goto(url, wait_until="networkidle", timeout=timeout)

            if not response or response.status >= 400:
                logger.error(
                    f"Failed to load {url}: HTTP {response.status if response else 'No response'}"
                )
                return False

            # Wait a bit for any dynamic content to load
            await page.wait_for_timeout(2000)

            # Take screenshot
            await page.screenshot(path=output_path, full_page=full_page, type="png")

            # Check if file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(
                    f"Screenshot saved to {output_path} ({os.path.getsize(output_path)} bytes)"
                )
                return True
            else:
                logger.error(f"Screenshot file not created or empty: {output_path}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"Timeout loading {url}")
            return False
        except Exception as e:
            logger.error(f"Error capturing screenshot of {url}: {e}")
            return False
        finally:
            if page:
                await page.close()


def capture_screenshot_sync(
    url: str,
    output_path: str,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    full_page: bool = False,
    timeout: int = 30000,
) -> bool:
    """
    Synchronous wrapper for screenshot capture.

    Args:
        url: Website URL to capture
        output_path: Path to save the screenshot
        viewport_width: Browser viewport width
        viewport_height: Browser viewport height
        full_page: Whether to capture full page or just viewport
        timeout: Page load timeout in milliseconds

    Returns:
        True if successful, False otherwise
    """

    async def _capture():
        async with LocalScreenshotCapture() as capture:
            return await capture.capture_screenshot(
                url=url,
                output_path=output_path,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                full_page=full_page,
                timeout=timeout,
            )

    try:
        # Create new event loop for this operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_capture())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        return False


def is_playwright_available() -> bool:
    """Check if Playwright is installed and browsers are available."""
    try:
        import playwright
        from playwright.sync_api import sync_playwright

        # Check if browsers are installed
        with sync_playwright() as p:
            # Try to get browser executable path
            try:
                browser_path = p.chromium.executable_path
                return os.path.exists(browser_path)
            except Exception:
                return False

    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"Error checking Playwright availability: {e}")
        return False


def install_playwright_browsers():
    """Install Playwright browsers if not already installed."""
    try:
        import subprocess
        import sys

        logger.info("Installing Playwright browsers...")

        # Run playwright install command
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Playwright browsers installed successfully")
            return True
        else:
            logger.error(f"Failed to install Playwright browsers: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {e}")
        return False
