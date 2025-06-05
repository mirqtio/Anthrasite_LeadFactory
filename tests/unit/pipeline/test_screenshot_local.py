"""
Unit tests for local screenshot capture using Playwright.
"""
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest

from leadfactory.pipeline.screenshot_local import (
    LocalScreenshotCapture,
    capture_screenshot_sync,
    install_playwright_browsers,
    is_playwright_available,
)


class TestLocalScreenshotCapture:
    """Test cases for LocalScreenshotCapture class."""

    @pytest.fixture
    def capture_instance(self):
        """Create a LocalScreenshotCapture instance."""
        return LocalScreenshotCapture()

    def test_init(self, capture_instance):
        """Test LocalScreenshotCapture initialization."""
        assert capture_instance.playwright is None
        assert capture_instance.browser is None
        assert capture_instance.browser_type == "chromium"

    @pytest.mark.asyncio
    async def test_start_success(self, capture_instance):
        """Test successful browser startup."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_async_playwright_instance = AsyncMock()

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_async_playwright_instance
            mock_async_playwright_instance.start.return_value = mock_playwright
            mock_playwright.chromium.launch.return_value = mock_browser

            await capture_instance.start()

            assert capture_instance.playwright == mock_playwright
            assert capture_instance.browser == mock_browser

            # Verify browser was launched with correct options
            mock_playwright.chromium.launch.assert_called_once()
            call_args = mock_playwright.chromium.launch.call_args
            assert call_args[1]["headless"] is True
            assert "--no-sandbox" in call_args[1]["args"]

    @pytest.mark.asyncio
    async def test_start_import_error(self, capture_instance):
        """Test browser startup with missing Playwright."""
        with patch("playwright.async_api.async_playwright", side_effect=ImportError):
            with pytest.raises(ImportError):
                await capture_instance.start()

    @pytest.mark.asyncio
    async def test_start_browser_launch_error(self, capture_instance):
        """Test browser startup failure."""
        mock_playwright = AsyncMock()
        mock_async_playwright_instance = AsyncMock()

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_async_playwright_instance
            mock_async_playwright_instance.start.return_value = mock_playwright
            mock_playwright.chromium.launch.side_effect = Exception("Browser launch failed")

            with pytest.raises(Exception, match="Browser launch failed"):
                await capture_instance.start()

    @pytest.mark.asyncio
    async def test_stop(self, capture_instance):
        """Test browser shutdown."""
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        capture_instance.browser = mock_browser
        capture_instance.playwright = mock_playwright

        await capture_instance.stop()

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert capture_instance.browser is None
        assert capture_instance.playwright is None

    @pytest.mark.asyncio
    async def test_capture_screenshot_no_browser(self, capture_instance):
        """Test screenshot capture without browser started."""
        result = await capture_instance.capture_screenshot("https://example.com", "/tmp/test.png")
        assert result is False

    @pytest.mark.asyncio
    async def test_capture_screenshot_success(self, capture_instance):
        """Test successful screenshot capture."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_response.status = 200

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name
            # Create a fake screenshot file
            tmp_file.write(b"fake png data")

        try:
            result = await capture_instance.capture_screenshot("https://example.com", output_path)

            assert result is True
            mock_browser.new_page.assert_called_once()
            mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle", timeout=30000)
            mock_page.screenshot.assert_called_once()
            mock_page.close.assert_called_once()
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_capture_screenshot_url_without_protocol(self, capture_instance):
        """Test screenshot capture with URL missing protocol."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_response.status = 200

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name
            tmp_file.write(b"fake png data")

        try:
            result = await capture_instance.capture_screenshot("example.com", output_path)

            assert result is True
            # Verify protocol was added
            mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle", timeout=30000)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_capture_screenshot_http_error(self, capture_instance):
        """Test screenshot capture with HTTP error."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_response.status = 404

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        result = await capture_instance.capture_screenshot("https://example.com", "/tmp/test.png")

        assert result is False
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_capture_screenshot_timeout(self, capture_instance):
        """Test screenshot capture with timeout."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_page.goto.side_effect = asyncio.TimeoutError()

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page

        result = await capture_instance.capture_screenshot("https://example.com", "/tmp/test.png", timeout=1000)

        assert result is False
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_capture_screenshot_custom_viewport(self, capture_instance):
        """Test screenshot capture with custom viewport."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_response.status = 200

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name
            tmp_file.write(b"fake png data")

        try:
            result = await capture_instance.capture_screenshot(
                "https://example.com",
                output_path,
                viewport_width=1920,
                viewport_height=1080,
                full_page=True
            )

            assert result is True
            # Verify viewport was set correctly
            mock_browser.new_page.assert_called_once_with(
                viewport={"width": 1920, "height": 1080}
            )
            # Verify full page screenshot
            mock_page.screenshot.assert_called_once_with(
                path=output_path, full_page=True, type="png"
            )
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_context_manager(self, capture_instance):
        """Test using LocalScreenshotCapture as async context manager."""
        with patch.object(capture_instance, "start") as mock_start, \
             patch.object(capture_instance, "stop") as mock_stop:

            async with capture_instance:
                mock_start.assert_called_once()

            mock_stop.assert_called_once()


class TestSynchronousFunctions:
    """Test cases for synchronous helper functions."""

    def test_capture_screenshot_sync_success(self):
        """Test synchronous screenshot capture wrapper."""
        with patch("leadfactory.pipeline.screenshot_local.LocalScreenshotCapture") as MockCapture:
            mock_instance = AsyncMock()
            MockCapture.return_value.__aenter__.return_value = mock_instance
            mock_instance.capture_screenshot.return_value = True

            result = capture_screenshot_sync("https://example.com", "/tmp/test.png")

            assert result is True
            mock_instance.capture_screenshot.assert_called_once_with(
                url="https://example.com",
                output_path="/tmp/test.png",
                viewport_width=1280,
                viewport_height=800,
                full_page=False,
                timeout=30000
            )

    def test_capture_screenshot_sync_custom_params(self):
        """Test synchronous screenshot capture with custom parameters."""
        with patch("leadfactory.pipeline.screenshot_local.LocalScreenshotCapture") as MockCapture:
            mock_instance = AsyncMock()
            MockCapture.return_value.__aenter__.return_value = mock_instance
            mock_instance.capture_screenshot.return_value = True

            result = capture_screenshot_sync(
                url="https://example.com",
                output_path="/tmp/test.png",
                viewport_width=1920,
                viewport_height=1080,
                full_page=True,
                timeout=60000
            )

            assert result is True
            mock_instance.capture_screenshot.assert_called_once_with(
                url="https://example.com",
                output_path="/tmp/test.png",
                viewport_width=1920,
                viewport_height=1080,
                full_page=True,
                timeout=60000
            )

    def test_capture_screenshot_sync_exception(self):
        """Test synchronous screenshot capture with exception."""
        with patch("leadfactory.pipeline.screenshot_local.LocalScreenshotCapture") as MockCapture:
            MockCapture.side_effect = Exception("Test error")

            result = capture_screenshot_sync("https://example.com", "/tmp/test.png")

            assert result is False

    def test_is_playwright_available_true(self):
        """Test Playwright availability check when available."""
        with patch("playwright.sync_api.sync_playwright") as mock_sync_playwright:
            mock_playwright = MagicMock()
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_playwright.chromium.executable_path = "/path/to/chromium"

            with patch("os.path.exists", return_value=True):
                result = is_playwright_available()
                assert result is True

    def test_is_playwright_available_import_error(self):
        """Test Playwright availability check with import error."""
        with patch("playwright.sync_api.sync_playwright", side_effect=ImportError):
            result = is_playwright_available()
            assert result is False

    def test_is_playwright_available_browser_not_found(self):
        """Test Playwright availability check when browser not installed."""
        with patch("playwright.sync_api.sync_playwright") as mock_sync_playwright:
            mock_playwright = MagicMock()
            mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
            mock_playwright.chromium.executable_path = "/path/to/chromium"

            with patch("os.path.exists", return_value=False):
                result = is_playwright_available()
                assert result is False

    def test_is_playwright_available_exception(self):
        """Test Playwright availability check with general exception."""
        with patch("playwright.sync_api.sync_playwright") as mock_sync_playwright:
            mock_sync_playwright.side_effect = Exception("General error")

            result = is_playwright_available()
            assert result is False

    def test_install_playwright_browsers_success(self):
        """Test successful Playwright browser installation."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = install_playwright_browsers()

            assert result is True

    def test_install_playwright_browsers_failure(self):
        """Test failed Playwright browser installation."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Installation failed"

        with patch("subprocess.run", return_value=mock_result):
            result = install_playwright_browsers()

            assert result is False

    def test_install_playwright_browsers_exception(self):
        """Test Playwright browser installation with exception."""
        with patch("subprocess.run", side_effect=Exception("Command failed")):
            result = install_playwright_browsers()

            assert result is False


class TestBrowserTypes:
    """Test cases for different browser types."""

    @pytest.mark.asyncio
    async def test_firefox_browser_type(self):
        """Test using Firefox browser."""
        capture_instance = LocalScreenshotCapture()
        capture_instance.browser_type = "firefox"

        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_async_playwright_instance = AsyncMock()

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_async_playwright_instance
            mock_async_playwright_instance.start.return_value = mock_playwright
            mock_playwright.firefox.launch.return_value = mock_browser

            await capture_instance.start()

            mock_playwright.firefox.launch.assert_called_once_with(headless=True)
            assert capture_instance.browser == mock_browser

    @pytest.mark.asyncio
    async def test_webkit_browser_type(self):
        """Test using WebKit browser."""
        capture_instance = LocalScreenshotCapture()
        capture_instance.browser_type = "webkit"

        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_async_playwright_instance = AsyncMock()

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value = mock_async_playwright_instance
            mock_async_playwright_instance.start.return_value = mock_playwright
            mock_playwright.webkit.launch.return_value = mock_browser

            await capture_instance.start()

            mock_playwright.webkit.launch.assert_called_once_with(headless=True)
            assert capture_instance.browser == mock_browser


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_screenshot_file_not_created(self):
        """Test handling when screenshot file is not created."""
        capture_instance = LocalScreenshotCapture()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_response.status = 200

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = mock_response

        # Use a path that won't be created by the mock
        nonexistent_path = "/tmp/nonexistent_screenshot.png"

        result = await capture_instance.capture_screenshot("https://example.com", nonexistent_path)

        assert result is False
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_creation_error(self):
        """Test handling page creation errors."""
        capture_instance = LocalScreenshotCapture()
        mock_browser = AsyncMock()
        mock_browser.new_page.side_effect = Exception("Page creation failed")

        capture_instance.browser = mock_browser

        result = await capture_instance.capture_screenshot("https://example.com", "/tmp/test.png")

        assert result is False

    @pytest.mark.asyncio
    async def test_no_response_from_goto(self):
        """Test handling when page.goto returns None."""
        capture_instance = LocalScreenshotCapture()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        capture_instance.browser = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.return_value = None

        result = await capture_instance.capture_screenshot("https://example.com", "/tmp/test.png")

        assert result is False
        mock_page.close.assert_called_once()
