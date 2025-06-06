"""
Browser test configuration and fixtures.

This module provides Playwright browser fixtures and configuration
for browser-based BDD tests.
"""

import os
import asyncio
from typing import Generator, Dict, Any
import pytest
from playwright.sync_api import Page, Browser, BrowserContext, Playwright, sync_playwright

from tests.browser.mock_server import start_mock_server, stop_mock_server, get_mock_server


# Set browser testing environment
os.environ["BROWSER_TEST_MODE"] = "True"
os.environ["HEADLESS"] = os.getenv("HEADLESS", "true")


@pytest.fixture(scope="session")
def playwright() -> Generator[Playwright, None, None]:
    """Session-scoped Playwright instance."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Generator[Browser, None, None]:
    """Session-scoped browser instance."""
    headless = os.getenv("HEADLESS", "true").lower() == "true"

    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor'
        ]
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def browser_context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Function-scoped browser context for test isolation."""
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(browser_context: BrowserContext) -> Generator[Page, None, None]:
    """Function-scoped page instance."""
    page = browser_context.new_page()

    # Set longer timeouts for CI
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(30000)

    yield page
    page.close()


@pytest.fixture(scope="function")
def browser_context_data() -> Dict[str, Any]:
    """Shared data storage for browser tests."""
    return {}


@pytest.fixture(scope="session")
def mock_server():
    """Session-scoped mock server for browser tests."""
    server = start_mock_server()
    yield server
    stop_mock_server()


@pytest.fixture(scope="function")
def mock_server_url(mock_server) -> str:
    """URL for the mock server used in browser tests."""
    return mock_server.url


@pytest.fixture(scope="function")
def test_data() -> Dict[str, Any]:
    """Test data for browser tests."""
    return {
        'businesses': [
            {
                'id': 1,
                'name': 'Test Restaurant',
                'email': 'test@restaurant.com',
                'website': 'https://testrestaurant.com',
                'category': 'restaurant',
                'score': 85,
                'status': 'pending',
                'city': 'San Francisco',
                'state': 'CA'
            },
            {
                'id': 2,
                'name': 'Sample Shop',
                'email': 'info@sampleshop.com',
                'website': 'https://sampleshop.com',
                'category': 'retail',
                'score': 72,
                'status': 'qualified',
                'city': 'Los Angeles',
                'state': 'CA'
            }
        ],
        'errors': [
            {
                'id': 'err-001',
                'timestamp': '2024-01-15T10:30:00Z',
                'stage': 'scrape',
                'operation': 'fetch_website',
                'severity': 'critical',
                'category': 'network',
                'business_id': 'biz-123',
                'content_preview': 'Connection timeout after 30s'
            },
            {
                'id': 'err-002',
                'timestamp': '2024-01-15T11:15:00Z',
                'stage': 'enrich',
                'operation': 'analyze_tech_stack',
                'severity': 'medium',
                'category': 'validation',
                'business_id': 'biz-456',
                'content_preview': 'Invalid HTML structure detected'
            }
        ],
        'queue_entries': [
            {
                'id': 1,
                'business': {'name': 'Test Restaurant', 'email': 'test@restaurant.com'},
                'qualification_score': 85,
                'priority': 80,
                'status': 'qualified',
                'assignee': None,
                'created_at': '2024-01-15T09:00:00Z'
            }
        ]
    }


# Browser test utilities
class BrowserTestHelpers:
    """Helper methods for browser testing."""

    @staticmethod
    def wait_for_network_idle(page: Page, timeout: int = 5000):
        """Wait for network to be idle."""
        page.wait_for_load_state('networkidle', timeout=timeout)

    @staticmethod
    def fill_form_field(page: Page, selector: str, value: str):
        """Fill a form field with proper waiting."""
        page.wait_for_selector(selector)
        page.fill(selector, value)

    @staticmethod
    def click_and_wait(page: Page, selector: str, wait_selector: str = None):
        """Click an element and optionally wait for another element."""
        page.click(selector)
        if wait_selector:
            page.wait_for_selector(wait_selector)

    @staticmethod
    def take_screenshot(page: Page, name: str):
        """Take a screenshot for debugging."""
        if not os.path.exists('screenshots'):
            os.makedirs('screenshots')
        page.screenshot(path=f'screenshots/{name}.png')

    @staticmethod
    def assert_text_visible(page: Page, text: str, timeout: int = 5000):
        """Assert that text is visible on the page."""
        try:
            page.wait_for_selector(f'text="{text}"', timeout=timeout)
            return True
        except:
            return False

    @staticmethod
    def assert_element_count(page: Page, selector: str, expected_count: int):
        """Assert the count of elements matching a selector."""
        elements = page.query_selector_all(selector)
        assert len(elements) == expected_count, f"Expected {expected_count} elements, found {len(elements)}"


@pytest.fixture(scope="function")
def browser_helpers() -> BrowserTestHelpers:
    """Provide browser test helper methods."""
    return BrowserTestHelpers()
