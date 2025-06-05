"""
Integration tests for local screenshot capture functionality.
"""
import os
import tempfile
from unittest.mock import patch

import pytest

from leadfactory.pipeline.screenshot import generate_business_screenshot
from leadfactory.pipeline.screenshot_local import (
    capture_screenshot_sync,
    is_playwright_available,
)


class TestScreenshotIntegration:
    """Integration test cases for screenshot functionality."""

    def test_playwright_availability_check(self):
        """Test that Playwright is properly installed and available."""
        # This test verifies the actual installation
        available = is_playwright_available()
        assert available is True, "Playwright should be available for integration tests"

    def test_real_screenshot_capture(self):
        """Test capturing a real screenshot from example.com."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            success = capture_screenshot_sync(
                url="https://example.com",
                output_path=output_path,
                viewport_width=1280,
                viewport_height=800,
                timeout=30000
            )

            assert success is True, "Screenshot capture should succeed"
            assert os.path.exists(output_path), "Screenshot file should be created"
            assert os.path.getsize(output_path) > 0, "Screenshot file should not be empty"

            # Verify it's a reasonable size for a PNG file (should be at least a few KB)
            file_size = os.path.getsize(output_path)
            assert file_size > 1000, f"Screenshot file seems too small: {file_size} bytes"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_screenshot_with_custom_viewport(self):
        """Test screenshot capture with custom viewport settings."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            success = capture_screenshot_sync(
                url="https://example.com",
                output_path=output_path,
                viewport_width=1920,
                viewport_height=1080,
                full_page=False,
                timeout=30000
            )

            assert success is True, "Screenshot capture with custom viewport should succeed"
            assert os.path.exists(output_path), "Screenshot file should be created"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_screenshot_with_invalid_url(self):
        """Test screenshot capture with an invalid URL."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            success = capture_screenshot_sync(
                url="https://nonexistent-domain-12345.com",
                output_path=output_path,
                timeout=10000  # Shorter timeout for invalid URL
            )

            # Should fail gracefully
            assert success is False, "Screenshot capture should fail for invalid URL"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_screenshot_url_without_protocol(self):
        """Test screenshot capture with URL missing protocol."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            success = capture_screenshot_sync(
                url="example.com",  # No https://
                output_path=output_path,
                timeout=30000
            )

            assert success is True, "Screenshot capture should add protocol automatically"
            assert os.path.exists(output_path), "Screenshot file should be created"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_business_screenshot_generation_with_playwright_fallback(self):
        """Test business screenshot generation using Playwright fallback."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        # Mock business data
        test_business = {
            "id": 12345,
            "name": "Test Business",
            "website": "https://example.com"
        }

        # Ensure we don't have ScreenshotOne API key to force Playwright fallback
        with patch.dict(os.environ, {"SCREENSHOT_ONE_KEY": ""}, clear=False), \
             patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True):

            success = generate_business_screenshot(test_business)
            assert success is True, "Business screenshot generation should succeed"

    def test_business_screenshot_generation_test_mode(self):
        """Test business screenshot generation in test mode."""
        test_business = {
            "id": 12345,
            "name": "Test Business",
            "website": "https://example.com"
        }

        # Test mode should create placeholder when Playwright not available
        with patch.dict(os.environ, {
            "SCREENSHOT_ONE_KEY": "",
            "E2E_MODE": "true"
        }, clear=False), \
             patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True), \
             patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=False):

            success = generate_business_screenshot(test_business)
            assert success is True, "Business screenshot generation should succeed in test mode"

    def test_screenshot_capture_multiple_urls(self):
        """Test capturing screenshots from multiple URLs."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        urls = [
            "https://example.com",
            "https://www.iana.org/domains/example",
        ]

        for i, url in enumerate(urls):
            with tempfile.NamedTemporaryFile(suffix=f"_{i}.png", delete=False) as tmp_file:
                output_path = tmp_file.name

            try:
                success = capture_screenshot_sync(
                    url=url,
                    output_path=output_path,
                    timeout=30000
                )

                assert success is True, f"Screenshot capture should succeed for {url}"
                assert os.path.exists(output_path), f"Screenshot file should be created for {url}"

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

    def test_screenshot_capture_stress_test(self):
        """Test capturing multiple screenshots in sequence (light stress test)."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        # Capture 3 screenshots to test stability
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=f"_stress_{i}.png", delete=False) as tmp_file:
                output_path = tmp_file.name

            try:
                success = capture_screenshot_sync(
                    url="https://example.com",
                    output_path=output_path,
                    timeout=30000
                )

                assert success is True, f"Screenshot capture {i} should succeed"
                assert os.path.exists(output_path), f"Screenshot file {i} should be created"

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

    def test_screenshot_capture_with_http_url(self):
        """Test screenshot capture with HTTP (non-HTTPS) URL."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            # Note: many HTTP sites redirect to HTTPS now, but this tests HTTP support
            success = capture_screenshot_sync(
                url="http://example.com",
                output_path=output_path,
                timeout=30000
            )

            # Should succeed (example.com likely redirects to HTTPS)
            assert success is True, "Screenshot capture should handle HTTP URLs"
            assert os.path.exists(output_path), "Screenshot file should be created"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_full_page_screenshot(self):
        """Test capturing full page screenshots."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            success = capture_screenshot_sync(
                url="https://example.com",
                output_path=output_path,
                full_page=True,
                timeout=30000
            )

            assert success is True, "Full page screenshot capture should succeed"
            assert os.path.exists(output_path), "Screenshot file should be created"

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestScreenshotFallbackIntegration:
    """Test integration between screenshot module and local screenshot fallback."""

    def test_screenshot_module_uses_local_fallback(self):
        """Test that main screenshot module properly uses local fallback."""
        if not is_playwright_available():
            pytest.skip("Playwright not available")

        test_business = {
            "id": 99999,
            "name": "Fallback Test Business",
            "website": "https://example.com"
        }

        # Remove ScreenshotOne API key to force fallback
        with patch.dict(os.environ, {"SCREENSHOT_ONE_KEY": ""}, clear=False), \
             patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True):

            success = generate_business_screenshot(test_business)
            assert success is True, "Screenshot generation should succeed using local fallback"

    def test_screenshot_module_handles_playwright_unavailable(self):
        """Test that screenshot module handles Playwright being unavailable."""
        test_business = {
            "id": 99999,
            "name": "No Playwright Test Business",
            "website": "https://example.com"
        }

        # Mock Playwright as unavailable and enable test mode
        with patch.dict(os.environ, {
            "SCREENSHOT_ONE_KEY": "",
            "E2E_MODE": "true"
        }, clear=False), \
             patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=False), \
             patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True):

            success = generate_business_screenshot(test_business)
            assert success is True, "Screenshot generation should succeed with placeholder in test mode"

    def test_screenshot_module_raises_exception_when_no_fallback(self):
        """Test that screenshot module raises exception when no fallback available."""
        test_business = {
            "id": 99999,
            "name": "No Fallback Test Business",
            "website": "https://example.com"
        }

        # Mock Playwright as unavailable and disable test mode
        with patch.dict(os.environ, {
            "SCREENSHOT_ONE_KEY": "",
            "E2E_MODE": "false"
        }, clear=False), \
             patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=False):

            with pytest.raises(Exception, match="No screenshot method available|Screenshot generation failed"):
                generate_business_screenshot(test_business)
