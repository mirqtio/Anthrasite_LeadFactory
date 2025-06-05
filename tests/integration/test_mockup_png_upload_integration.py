"""
Integration tests for Task 7: Supabase PNG Upload Integration.

Tests the comprehensive mockup PNG upload functionality including:
- Reliable PNG upload to Supabase storage
- Error handling and retry logic
- Mockup images correctly linked to businesses
- CDN URL generation
- Cleanup for orphaned images
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PIL import Image

from leadfactory.services.mockup_png_uploader import (
    MockupPNGUploader,
    MockupUploadResult,
    cleanup_orphaned_mockups,
    upload_business_mockup,
)


class TestMockupPNGUploadIntegration:
    """Integration tests for mockup PNG upload functionality."""

    @pytest.fixture
    def test_image_path(self):
        """Create a test PNG image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Create a test image
            test_image = Image.new("RGBA", (800, 600), (255, 0, 0, 128))
            test_image.save(tmp_file.name, "PNG")
            yield Path(tmp_file.name)

            # Cleanup
            Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def large_test_image_path(self):
        """Create a large test PNG image for optimization testing."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Create a large test image
            test_image = Image.new("RGBA", (3000, 2000), (0, 255, 0, 128))
            test_image.save(tmp_file.name, "PNG")
            yield Path(tmp_file.name)

            # Cleanup
            Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def mock_storage(self):
        """Mock storage backend."""
        with patch(
            "leadfactory.services.mockup_png_uploader.get_storage"
        ) as mock_get_storage:
            mock_storage = Mock()
            mock_get_storage.return_value = mock_storage

            # Mock business validation
            mock_storage.get_business.return_value = {
                "id": 123,
                "name": "Test Business",
            }

            # Mock asset creation
            mock_storage.create_asset.return_value = True

            # Mock asset queries
            mock_storage.get_assets_by_path.return_value = []
            mock_storage.get_business_assets.return_value = []

            yield mock_storage

    @pytest.fixture
    def mock_supabase_storage(self):
        """Mock Supabase storage."""
        with patch(
            "leadfactory.services.mockup_png_uploader.SupabaseStorage"
        ) as mock_class:
            mock_storage = Mock()
            mock_class.return_value = mock_storage

            # Mock successful upload
            mock_storage.upload_file.return_value = {
                "storage_path": "mockups/123/homepage_test.png",
                "size_bytes": 1024,
            }

            # Mock URL generation
            mock_storage.generate_secure_report_url.return_value = {
                "signed_url": "https://example.com/signed-url"
            }

            # Mock file operations
            mock_storage.list_files.return_value = []
            mock_storage.delete_file.return_value = True

            yield mock_storage

    def test_successful_upload(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test successful PNG upload with all components working."""
        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=123, mockup_type="homepage"
        )

        assert result.success is True
        assert result.business_id == 123
        assert result.storage_path is not None
        assert result.cdn_url == "https://example.com/signed-url"
        assert result.error_message is None
        assert result.retry_count == 0

        # Verify storage interactions
        mock_supabase_storage.upload_file.assert_called_once()
        mock_storage.create_asset.assert_called_once()

    def test_file_not_found_error(self, mock_storage, mock_supabase_storage):
        """Test handling of non-existent file."""
        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path="nonexistent.png", business_id=123, mockup_type="homepage"
        )

        assert result.success is False
        assert "File not found" in result.error_message

        # Should not attempt upload
        mock_supabase_storage.upload_file.assert_not_called()

    def test_invalid_business_id(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test handling of invalid business ID."""
        # Mock business not found
        mock_storage.get_business.return_value = None

        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=999, mockup_type="homepage"
        )

        assert result.success is False
        assert "Business not found" in result.error_message

    def test_upload_retry_logic(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test retry logic on upload failures."""
        # Mock upload failures then success
        mock_supabase_storage.upload_file.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            {"storage_path": "mockups/123/homepage_test.png", "size_bytes": 1024},
        ]

        uploader = MockupPNGUploader()
        uploader.max_retries = 3
        uploader.retry_delay_base = 0.1  # Fast retries for testing

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=123, mockup_type="homepage"
        )

        assert result.success is True
        assert result.retry_count == 2  # Two retries before success
        assert mock_supabase_storage.upload_file.call_count == 3

    def test_upload_failure_all_retries_exhausted(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test handling when all retries are exhausted."""
        # Mock continuous upload failures
        mock_supabase_storage.upload_file.side_effect = Exception("Persistent error")

        uploader = MockupPNGUploader()
        uploader.max_retries = 2
        uploader.retry_delay_base = 0.1  # Fast retries for testing

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=123, mockup_type="homepage"
        )

        assert result.success is False
        assert "Upload failed after 3 attempts" in result.error_message
        assert result.retry_count == 3
        assert mock_supabase_storage.upload_file.call_count == 3

    def test_database_linking_failure_cleanup(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test cleanup when database linking fails after successful upload."""
        # Mock successful upload but failed database linking
        mock_storage.create_asset.return_value = False

        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=123, mockup_type="homepage"
        )

        assert result.success is False
        assert "Failed to link mockup to business" in result.error_message

        # Should have attempted cleanup
        mock_supabase_storage.delete_file.assert_called_once()

    def test_image_optimization(
        self, large_test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test image optimization for large images."""
        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path=large_test_image_path,
            business_id=123,
            mockup_type="homepage",
            optimize=True,
            max_width=1920,
        )

        assert result.success is True

        # Check that upload was called (optimization should have happened)
        mock_supabase_storage.upload_file.assert_called_once()

        # Verify metadata includes dimensions
        call_args = mock_supabase_storage.upload_file.call_args
        metadata = call_args[1]["metadata"]
        assert "dimensions" in metadata

    def test_orphaned_image_cleanup(self, mock_storage, mock_supabase_storage):
        """Test cleanup of orphaned images."""
        # Mock files in storage
        mock_supabase_storage.list_files.return_value = [
            {"name": "orphaned_file.png", "created_at": "2023-01-01T00:00:00Z"},
            {"name": "linked_file.png", "created_at": "2023-01-01T00:00:00Z"},
        ]

        # Mock linkage check - first file is orphaned, second is linked
        mock_storage.get_assets_by_path.side_effect = [[], [{"id": 1}]]

        uploader = MockupPNGUploader()

        cleanup_stats = uploader.cleanup_orphaned_images(max_age_hours=24)

        assert cleanup_stats["files_checked"] == 2
        assert cleanup_stats["orphaned_files_found"] == 1
        assert cleanup_stats["files_deleted"] == 1
        assert len(cleanup_stats["errors"]) == 0

        # Should have deleted only the orphaned file
        mock_supabase_storage.delete_file.assert_called_once_with(
            "mockups/orphaned_file.png"
        )

    def test_convenience_functions(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test convenience functions."""
        # Test upload convenience function
        result = upload_business_mockup(
            png_path=test_image_path, business_id=123, mockup_type="product"
        )

        assert result.success is True
        assert result.business_id == 123

        # Test cleanup convenience function
        cleanup_stats = cleanup_orphaned_mockups(max_age_hours=48)
        assert isinstance(cleanup_stats, dict)
        assert "files_checked" in cleanup_stats

    def test_cdn_url_generation_fallback(
        self, test_image_path, mock_storage, mock_supabase_storage
    ):
        """Test CDN URL generation with fallback."""
        # Mock primary URL generation failure, fallback success
        mock_supabase_storage.generate_secure_report_url.side_effect = Exception(
            "API error"
        )
        mock_supabase_storage.generate_signed_url.return_value = (
            "https://fallback.com/url"
        )

        uploader = MockupPNGUploader()

        result = uploader.upload_mockup_png(
            png_path=test_image_path, business_id=123, mockup_type="homepage"
        )

        assert result.success is True
        assert result.cdn_url == "https://fallback.com/url"

    def test_business_mockups_retrieval(self, mock_storage, mock_supabase_storage):
        """Test retrieval of business mockups with URL refresh."""
        # Mock existing assets with old URLs
        mock_storage.get_business_assets.return_value = [
            {
                "id": 1,
                "file_path": "mockups/123/homepage.png",
                "url": "https://old.url.com/expired",
                "created_at": "2023-01-01T00:00:00Z",  # Old enough to be expired
            }
        ]

        # Mock URL refresh
        mock_supabase_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://fresh.url.com/new"
        }

        uploader = MockupPNGUploader()

        mockups = uploader.get_business_mockups(123)

        assert len(mockups) == 1
        assert mockups[0]["url"] == "https://fresh.url.com/new"

        # Should have updated the URL in storage
        mock_storage.update_asset_url.assert_called_once()

    def test_file_size_validation(self, mock_storage, mock_supabase_storage):
        """Test file size validation."""
        # Create oversized image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Create a very large file
            with open(tmp_file.name, "wb") as f:
                f.write(b"0" * (15 * 1024 * 1024))  # 15MB file

            uploader = MockupPNGUploader()
            uploader.max_file_size = 10 * 1024 * 1024  # 10MB limit

            result = uploader.upload_mockup_png(
                png_path=tmp_file.name, business_id=123, mockup_type="homepage"
            )

            assert result.success is False
            assert "File too large" in result.error_message

            # Cleanup
            Path(tmp_file.name).unlink(missing_ok=True)


class TestMockupPNGUploadEndToEnd:
    """End-to-end tests for the complete upload flow."""

    @pytest.mark.integration
    def test_complete_upload_flow_with_mocked_dependencies(self):
        """Test complete upload flow with all mocked dependencies."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Create test image
            test_image = Image.new("RGBA", (800, 600), (255, 0, 0, 128))
            test_image.save(tmp_file.name, "PNG")

            try:
                with (
                    patch(
                        "leadfactory.services.mockup_png_uploader.SupabaseStorage"
                    ) as mock_supabase_class,
                    patch(
                        "leadfactory.services.mockup_png_uploader.get_storage"
                    ) as mock_get_storage,
                ):
                    # Setup mocks
                    mock_supabase = Mock()
                    mock_supabase_class.return_value = mock_supabase
                    mock_supabase.upload_file.return_value = {
                        "storage_path": "test/path.png"
                    }
                    mock_supabase.generate_secure_report_url.return_value = {
                        "signed_url": "https://test.com/url"
                    }

                    mock_storage = Mock()
                    mock_get_storage.return_value = mock_storage
                    mock_storage.get_business.return_value = {"id": 123}
                    mock_storage.create_asset.return_value = True

                    # Run test
                    result = upload_business_mockup(
                        png_path=tmp_file.name, business_id=123, mockup_type="homepage"
                    )

                    # Verify results
                    assert result.success is True
                    assert result.business_id == 123
                    assert result.cdn_url == "https://test.com/url"
                    assert result.upload_duration is not None
                    assert result.upload_duration > 0

            finally:
                # Cleanup
                Path(tmp_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    # Run a simple test

    # Create a simple test image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        test_image = Image.new("RGBA", (400, 300), (0, 0, 255, 128))
        test_image.save(tmp_file.name, "PNG")


        # Test basic functionality (would need real config for full test)
        try:
            from datetime import datetime

            from leadfactory.services.mockup_png_uploader import MockupImageMetadata

            metadata = MockupImageMetadata(
                business_id=123,
                mockup_type="test",
                generated_at=datetime.utcnow(),
                original_dimensions=(400, 300),
                optimized_dimensions=(400, 300),
                file_size_bytes=1024,
            )


        except Exception:
            pass

        finally:
            # Cleanup
            Path(tmp_file.name).unlink(missing_ok=True)
