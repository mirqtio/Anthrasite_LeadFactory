#!/usr/bin/env python3
"""
Install Playwright browsers for local screenshot capture.

This script installs the necessary browsers for Playwright to work.
Run this after installing the Python dependencies.
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_playwright_installed():
    """Check if Playwright is installed."""
    try:
        import playwright
        return True
    except ImportError:
        return False


def install_playwright_browsers():
    """Install Playwright browsers."""
    logger.info("Installing Playwright browsers...")
    
    try:
        # Install chromium browser (most lightweight)
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✓ Chromium browser installed successfully")
            
            # Also install system dependencies
            logger.info("Installing system dependencies...")
            deps_result = subprocess.run(
                [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                capture_output=True,
                text=True
            )
            
            if deps_result.returncode == 0:
                logger.info("✓ System dependencies installed successfully")
            else:
                logger.warning(f"System dependencies installation had issues: {deps_result.stderr}")
                logger.info("You may need to run with sudo: sudo python -m playwright install-deps chromium")
                
            return True
        else:
            logger.error(f"Failed to install Chromium: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {e}")
        return False


def verify_installation():
    """Verify Playwright installation works."""
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info("Verifying Playwright installation...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            browser.close()
            
            if "Example" in title:
                logger.info("✓ Playwright is working correctly!")
                return True
            else:
                logger.warning("Playwright launched but page title unexpected")
                return False
                
    except Exception as e:
        logger.error(f"Failed to verify Playwright: {e}")
        return False


def main():
    """Main installation process."""
    logger.info("Playwright Browser Installation Script")
    logger.info("=" * 50)
    
    # Check if Playwright is installed
    if not check_playwright_installed():
        logger.error("Playwright is not installed!")
        logger.info("Please run: pip install playwright")
        return 1
        
    # Install browsers
    if not install_playwright_browsers():
        logger.error("Failed to install Playwright browsers")
        return 1
        
    # Verify installation
    if verify_installation():
        logger.info("\n✓ Playwright is ready for screenshot capture!")
        logger.info("\nYou can now use local screenshot capture as a fallback to ScreenshotOne API")
        return 0
    else:
        logger.warning("\nPlaywright installed but verification failed")
        logger.info("Try running the script again or check the Playwright documentation")
        return 1


if __name__ == "__main__":
    sys.exit(main())