"""Unit tests for local screenshot capture functionality."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from leadfactory.pipeline.screenshot_local import (
    LocalScreenshotCapture,
    capture_screenshot_sync,
    install_playwright_browsers,
    is_playwright_available,
)


class TestLocalScreenshotCapture:
    """Test local screenshot capture functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        with patch("leadfactory.pipeline.screenshot_local.async_playwright") as mock_playwright:
            # Mock the playwright instance
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)

            # Mock async_playwright().start()
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

            async with LocalScreenshotCapture() as capture:
                assert capture.playwright is not None
                assert capture.browser is not None

            # Verify cleanup
            mock_browser.close.assert_called_once()
            mock_pw_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_capture_screenshot_success(self):
        """Test successful screenshot capture."""
        with patch("leadfactory.pipeline.screenshot_local.async_playwright") as mock_playwright:
            # Setup mocks
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200

            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock(return_value=mock_response)
            mock_page.screenshot = AsyncMock()

            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

            # Create temporary file for screenshot
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                # Write some data to simulate screenshot
                tmp.write(b"PNG_DATA")

            try:
                capture = LocalScreenshotCapture()
                await capture.start()

                # Mock os.path.exists and os.path.getsize
                with patch("os.path.exists", return_value=True), \
                     patch("os.path.getsize", return_value=1000):

                    result = await capture.capture_screenshot(
                        url="https://example.com",
                        output_path=tmp_path
                    )

                    assert result is True
                    mock_page.goto.assert_called_once()
                    mock_page.screenshot.assert_called_once()

                await capture.stop()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_capture_screenshot_timeout(self):
        """Test screenshot capture timeout handling."""
        with patch("leadfactory.pipeline.screenshot_local.async_playwright") as mock_playwright:
            # Setup mocks
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock(side_effect=asyncio.TimeoutError())

            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

            capture = LocalScreenshotCapture()
            await capture.start()

            result = await capture.capture_screenshot(
                url="https://slow-site.com",
                output_path="/tmp/test.png"
            )

            assert result is False
            await capture.stop()

    def test_capture_screenshot_sync(self):
        """Test synchronous wrapper."""
        with patch("leadfactory.pipeline.screenshot_local.LocalScreenshotCapture") as mock_capture_class:
            # Mock the capture instance
            mock_capture = AsyncMock()
            mock_capture.__aenter__ = AsyncMock(return_value=mock_capture)
            mock_capture.__aexit__ = AsyncMock()
            mock_capture.capture_screenshot = AsyncMock(return_value=True)

            mock_capture_class.return_value = mock_capture

            # Test sync wrapper
            with patch("asyncio.new_event_loop") as mock_loop:
                loop = Mock()
                mock_loop.return_value = loop
                loop.run_until_complete = Mock(return_value=True)

                result = capture_screenshot_sync(
                    url="https://example.com",
                    output_path="/tmp/test.png"
                )

                assert result is True
                loop.close.assert_called_once()

    def test_is_playwright_available_true(self):
        """Test Playwright availability check when installed."""
        with patch("leadfactory.pipeline.screenshot_local.sync_playwright") as mock_sync_pw:
            # Mock playwright context
            mock_pw = MagicMock()
            mock_pw.__enter__ = Mock(return_value=mock_pw)
            mock_pw.__exit__ = Mock(return_value=None)
            mock_pw.chromium.executable_path = "/usr/bin/chromium"

            mock_sync_pw.return_value = mock_pw

            with patch("os.path.exists", return_value=True):
                assert is_playwright_available() is True

    def test_is_playwright_available_false_no_import(self):
        """Test Playwright availability when not installed."""
        with patch("builtins.__import__", side_effect=ImportError("No module named 'playwright'")):
            assert is_playwright_available() is False

    def test_is_playwright_available_false_no_browser(self):
        """Test Playwright availability when browsers not installed."""
        with patch("leadfactory.pipeline.screenshot_local.sync_playwright") as mock_sync_pw:
            # Mock playwright context
            mock_pw = MagicMock()
            mock_pw.__enter__ = Mock(return_value=mock_pw)
            mock_pw.__exit__ = Mock(return_value=None)
            mock_pw.chromium.executable_path = "/usr/bin/chromium"

            mock_sync_pw.return_value = mock_pw

            with patch("os.path.exists", return_value=False):
                assert is_playwright_available() is False

    def test_install_playwright_browsers_success(self):
        """Test successful browser installation."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = install_playwright_browsers()

            assert result is True
            assert mock_run.called

    def test_install_playwright_browsers_failure(self):
        """Test browser installation failure."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Installation failed"
            mock_run.return_value = mock_result

            result = install_playwright_browsers()

            assert result is False

    @pytest.mark.asyncio
    async def test_capture_adds_protocol(self):
        """Test that capture adds https:// if missing."""
        with patch("leadfactory.pipeline.screenshot_local.async_playwright") as mock_playwright:
            # Setup mocks
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200

            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock(return_value=mock_response)

            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

            capture = LocalScreenshotCapture()
            await capture.start()

            with patch("os.path.exists", return_value=True), \
                 patch("os.path.getsize", return_value=1000):

                # Test with URL without protocol
                await capture.capture_screenshot(
                    url="example.com",
                    output_path="/tmp/test.png"
                )

                # Verify https:// was added
                mock_page.goto.assert_called_with(
                    "https://example.com",
                    wait_until="networkidle",
                    timeout=30000
                )

            await capture.stop()

    @pytest.mark.asyncio
    async def test_browser_not_started_error(self):
        """Test error when browser not started."""
        capture = LocalScreenshotCapture()
        # Don't call start()

        result = await capture.capture_screenshot(
            url="https://example.com",
            output_path="/tmp/test.png"
        )

        assert result is False
