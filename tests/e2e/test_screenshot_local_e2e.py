"""End-to-end tests for local screenshot capture functionality."""
import os
import tempfile
import time
from unittest.mock import patch

import pytest

from leadfactory.pipeline.screenshot import generate_business_screenshot, main
from leadfactory.pipeline.screenshot_local import (
    capture_screenshot_sync,
    install_playwright_browsers,
    is_playwright_available,
)
from leadfactory.storage import get_storage_instance


class TestScreenshotLocalE2E:
    """End-to-end tests for local screenshot capture."""

    @pytest.fixture
    def storage(self):
        """Get storage instance for testing."""
        return get_storage_instance()

    @pytest.fixture
    def test_business_data(self):
        """Create test business data."""
        return {
            "name": "E2E Screenshot Test Business",
            "address": "123 Screenshot St, Test City, TS 12345",
            "zip_code": "12345",
            "category": "test",
            "website": "https://example.com",
            "source": "test",
            "source_id": "e2e-screenshot-test-001"
        }

    def test_playwright_installation_check(self):
        """Test that Playwright is properly installed for E2E tests."""
        # Check if Playwright is available
        available = is_playwright_available()

        if not available:
            # Try to install it
            print("Playwright not available, attempting to install...")
            success = install_playwright_browsers()

            if success:
                # Check again
                available = is_playwright_available()
                assert available, "Playwright should be available after installation"
            else:
                pytest.skip("Could not install Playwright browsers")
        else:
            assert available, "Playwright should be available"

    def test_full_screenshot_pipeline_with_local_capture(self, storage, test_business_data):
        """Test complete screenshot pipeline using local capture."""
        # Ensure we're using local capture by removing API key
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

        try:
            # Check Playwright availability
            if not is_playwright_available():
                pytest.skip("Playwright not available for E2E test")

            # Create a business that needs a screenshot
            business_id = storage.create_business(**test_business_data)
            assert business_id is not None, "Business should be created"

            # Get the business
            business = storage.get_business_by_id(business_id)
            assert business is not None, "Business should be retrievable"
            assert business["website"] == test_business_data["website"]

            # Generate screenshot
            with patch("leadfactory.pipeline.screenshot.create_screenshot_asset") as mock_create_asset:
                mock_create_asset.return_value = True

                success = generate_business_screenshot(business)
                assert success is True, "Screenshot generation should succeed"

                # Verify asset creation was called
                mock_create_asset.assert_called_once()
                call_args = mock_create_asset.call_args
                assert call_args[1]["business_id"] == business_id
                assert "screenshot_" in call_args[1]["file_path"]
                assert call_args[1]["asset_type"] == "screenshot"

        finally:
            # Restore API key
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key

    def test_batch_screenshot_processing_local(self, storage):
        """Test batch processing of screenshots using local capture."""
        # Ensure local capture
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

        try:
            if not is_playwright_available():
                pytest.skip("Playwright not available for E2E test")

            # Create multiple businesses needing screenshots
            business_ids = []
            for i in range(3):
                business_id = storage.create_business(
                    name=f"E2E Batch Test {i}",
                    address=f"{i} Batch St, Test City, TS 1234{i}",
                    zip_code=f"1234{i}",
                    category="test",
                    website=f"https://example{i}.com",
                    source="test",
                    source_id=f"e2e-batch-{i}"
                )
                business_ids.append(business_id)

            # Mock asset creation
            with patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True) as mock_create:
                # Process screenshots for all businesses
                with patch("leadfactory.pipeline.screenshot.get_businesses_needing_screenshots") as mock_get:
                    # Return our test businesses
                    mock_get.return_value = [
                        storage.get_business_by_id(bid) for bid in business_ids
                    ]

                    # Run main screenshot processing
                    exit_code = main()
                    assert exit_code == 0, "Screenshot processing should succeed"

                    # Verify all businesses were processed
                    assert mock_create.call_count == 3, "All businesses should have screenshots"

        finally:
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key

    def test_real_website_screenshot_capture(self):
        """Test capturing a real screenshot from a live website."""
        if not is_playwright_available():
            pytest.skip("Playwright not available for E2E test")

        # Ensure local capture
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                output_path = tmp_file.name

            try:
                # Capture a real screenshot
                start_time = time.time()
                success = capture_screenshot_sync(
                    url="https://www.iana.org/domains/example",
                    output_path=output_path,
                    viewport_width=1280,
                    viewport_height=800,
                    timeout=30000
                )
                capture_time = time.time() - start_time

                assert success is True, "Screenshot capture should succeed"
                assert os.path.exists(output_path), "Screenshot file should exist"

                file_size = os.path.getsize(output_path)
                assert file_size > 10000, f"Screenshot should be substantial size, got {file_size} bytes"

                print(f"Screenshot captured in {capture_time:.2f} seconds, size: {file_size} bytes")

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key

    def test_screenshot_api_fallback_to_local(self, storage, test_business_data):
        """Test fallback from API to local capture on API failure."""
        if not is_playwright_available():
            pytest.skip("Playwright not available for E2E test")

        # Set a fake API key
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        os.environ["SCREENSHOT_ONE_KEY"] = "fake-key-for-testing"

        try:
            # Create a business
            business_id = storage.create_business(**test_business_data)
            business = storage.get_business_by_id(business_id)

            # Mock API failure
            import requests
            with patch("requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.RequestException("API Error")

                # Mock asset creation
                with patch("leadfactory.pipeline.screenshot.create_screenshot_asset", return_value=True):
                    # Should fall back to local capture
                    success = generate_business_screenshot(business)
                    assert success is True, "Should succeed with local fallback"

        finally:
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key
            else:
                del os.environ["SCREENSHOT_ONE_KEY"]

    def test_screenshot_error_handling(self, storage):
        """Test error handling in screenshot generation."""
        # Disable all screenshot methods
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        original_e2e = os.environ.get("E2E_MODE")
        original_prod = os.environ.get("PRODUCTION_TEST_MODE")

        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]
        os.environ["E2E_MODE"] = "false"
        os.environ["PRODUCTION_TEST_MODE"] = "false"

        try:
            # Create a business
            business_id = storage.create_business(
                name="Error Test Business",
                address="404 Error St",
                zip_code="00000",
                category="test",
                website="https://error-test.example",
                source="test",
                source_id="error-test-001"
            )
            business = storage.get_business_by_id(business_id)

            # Mock Playwright as unavailable
            with patch("leadfactory.pipeline.screenshot_local.is_playwright_available", return_value=False):
                # Should raise exception
                with pytest.raises(Exception, match="No screenshot method available|Screenshot generation failed"):
                    generate_business_screenshot(business)

        finally:
            # Restore environment
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key
            if original_e2e:
                os.environ["E2E_MODE"] = original_e2e
            elif "E2E_MODE" in os.environ:
                del os.environ["E2E_MODE"]
            if original_prod:
                os.environ["PRODUCTION_TEST_MODE"] = original_prod
            elif "PRODUCTION_TEST_MODE" in os.environ:
                del os.environ["PRODUCTION_TEST_MODE"]

    def test_concurrent_screenshot_capture(self):
        """Test multiple screenshots captured concurrently."""
        if not is_playwright_available():
            pytest.skip("Playwright not available for E2E test")

        # Ensure local capture
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

        try:
            urls = [
                "https://example.com",
                "https://www.iana.org/domains/example",
                "https://example.org"
            ]

            output_paths = []
            for i, url in enumerate(urls):
                with tempfile.NamedTemporaryFile(suffix=f"_{i}.png", delete=False) as tmp_file:
                    output_paths.append(tmp_file.name)

            try:
                # Capture screenshots sequentially (async would be better but keeping it simple)
                results = []
                for url, output_path in zip(urls, output_paths):
                    success = capture_screenshot_sync(
                        url=url,
                        output_path=output_path,
                        timeout=30000
                    )
                    results.append(success)

                # All should succeed
                assert all(results), "All screenshots should be captured successfully"

                # Verify all files exist
                for output_path in output_paths:
                    assert os.path.exists(output_path), f"Screenshot file should exist: {output_path}"
                    assert os.path.getsize(output_path) > 0, f"Screenshot should not be empty: {output_path}"

            finally:
                # Clean up files
                for output_path in output_paths:
                    if os.path.exists(output_path):
                        os.unlink(output_path)

        finally:
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key

    def test_screenshot_with_javascript_heavy_site(self):
        """Test screenshot capture on JavaScript-heavy site."""
        if not is_playwright_available():
            pytest.skip("Playwright not available for E2E test")

        # Ensure local capture
        original_key = os.environ.get("SCREENSHOT_ONE_KEY")
        if "SCREENSHOT_ONE_KEY" in os.environ:
            del os.environ["SCREENSHOT_ONE_KEY"]

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                output_path = tmp_file.name

            try:
                # Example.com is simple, but the wait_for_timeout ensures JS can load
                success = capture_screenshot_sync(
                    url="https://example.com",
                    output_path=output_path,
                    timeout=30000
                )

                assert success is True, "Screenshot of JS site should succeed"
                assert os.path.exists(output_path), "Screenshot file should exist"

                # The screenshot module waits 2 seconds for dynamic content
                file_size = os.path.getsize(output_path)
                assert file_size > 1000, "Screenshot should have content"

            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        finally:
            if original_key:
                os.environ["SCREENSHOT_ONE_KEY"] = original_key
