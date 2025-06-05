"""Integration tests for screenshot fallback functionality."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.screenshot import generate_business_screenshot
from leadfactory.storage.factory import get_storage


class TestScreenshotFallback:
    """Test screenshot generation with fallback to local capture."""

    @pytest.fixture
    def test_business(self):
        """Create a test business object."""
        return {
            "id": 999,
            "name": "Test Business",
            "website": "https://example.com"
        }

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for asset creation."""
        with patch("leadfactory.pipeline.screenshot.get_storage") as mock_get_storage:
            mock_storage = Mock()
            mock_storage.create_asset = Mock(return_value=True)
            mock_get_storage.return_value = mock_storage
            yield mock_storage

    def test_screenshot_with_api_key(self, test_business, mock_storage):
        """Test screenshot generation with ScreenshotOne API key."""
        with patch.dict(os.environ, {"SCREENSHOT_ONE_KEY": "test-api-key"}):
            with patch("requests.get") as mock_get:
                # Mock successful API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.content = b"PNG_IMAGE_DATA"
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                # Generate screenshot
                result = generate_business_screenshot(test_business)

                # Verify API was called
                assert mock_get.called
                call_args = mock_get.call_args
                assert "api.screenshotone.com" in call_args[0][0]

                # Verify asset was created
                assert mock_storage.create_asset.called
                assert result is True

    def test_screenshot_fallback_to_local(self, test_business, mock_storage):
        """Test fallback to local screenshot when no API key."""
        # No API key in environment
        with patch.dict(os.environ, {}, clear=True):
            # Mock Playwright availability and capture
            with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=True):
                with patch("leadfactory.pipeline.screenshot.capture_screenshot_sync", return_value=True):
                    # Generate screenshot
                    result = generate_business_screenshot(test_business)

                    # Verify asset was created
                    assert mock_storage.create_asset.called
                    assert result is True

    def test_screenshot_api_failure_fallback(self, test_business, mock_storage):
        """Test fallback when API fails."""
        with patch.dict(os.environ, {"SCREENSHOT_ONE_KEY": "test-api-key"}):
            with patch("requests.get") as mock_get:
                # Mock API failure
                mock_get.side_effect = Exception("API Error")

                # Mock successful local capture
                with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=True):
                    with patch("leadfactory.pipeline.screenshot.capture_screenshot_sync", return_value=True):
                        # Generate screenshot
                        result = generate_business_screenshot(test_business)

                        # Verify fallback was used
                        assert result is True

    def test_screenshot_placeholder_in_test_mode(self, test_business, mock_storage):
        """Test placeholder generation in test mode."""
        with patch.dict(os.environ, {"E2E_MODE": "true"}, clear=False):
            # Mock no API key and no Playwright
            with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=False):
                with patch("PIL.Image.new") as mock_image_new:
                    mock_img = Mock()
                    mock_img.save = Mock()
                    mock_image_new.return_value = mock_img

                    # Generate screenshot
                    result = generate_business_screenshot(test_business)

                    # Verify placeholder was created
                    assert mock_image_new.called
                    assert mock_img.save.called
                    assert result is True

    def test_screenshot_all_methods_fail(self, test_business, mock_storage):
        """Test when all screenshot methods fail."""
        # No API key, no test mode
        with patch.dict(os.environ, {}, clear=True):
            # Mock Playwright not available
            with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=False):
                # Should raise exception
                with pytest.raises(Exception, match="Playwright not available"):
                    generate_business_screenshot(test_business)

    def test_screenshot_file_creation(self, test_business, mock_storage):
        """Test actual file creation in temp directory."""
        with patch.dict(os.environ, {"E2E_MODE": "true"}):
            # Mock Playwright not available to force placeholder
            with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=False):
                # Capture the actual file path used
                saved_paths = []

                def mock_save(path, format):
                    saved_paths.append(path)
                    # Create actual file
                    with open(path, "wb") as f:
                        f.write(b"PLACEHOLDER_PNG")

                with patch("PIL.Image.Image.save", side_effect=mock_save):
                    # Generate screenshot
                    result = generate_business_screenshot(test_business)

                    assert result is True
                    assert len(saved_paths) == 1

                    # Verify temp file was created
                    assert saved_paths[0].startswith(tempfile.gettempdir())
                    assert saved_paths[0].endswith(".png")

    def test_screenshot_with_invalid_url(self, mock_storage):
        """Test screenshot with invalid URL."""
        business = {
            "id": 999,
            "name": "Bad URL Business",
            "website": "not-a-valid-url"
        }

        with patch.dict(os.environ, {"E2E_MODE": "true"}):
            with patch("leadfactory.pipeline.screenshot.is_playwright_available", return_value=True):
                with patch("leadfactory.pipeline.screenshot.capture_screenshot_sync", return_value=False):
                    # Should handle gracefully in test mode
                    with pytest.raises(Exception, match="Local screenshot capture failed"):
                        generate_business_screenshot(business)
