"""
Unit tests for Task 7: MockupPNGUploader service.

Tests the core functionality of the MockupPNGUploader class including:
- Image validation and processing
- Metadata generation
- Error handling
- File operations
- Configuration handling
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PIL import Image

from leadfactory.services.mockup_png_uploader import (
    MockupImageMetadata,
    MockupPNGUploader,
    MockupUploadResult,
)


class TestMockupPNGUploaderUnit:
    """Unit tests for MockupPNGUploader class methods."""

    @pytest.fixture
    def uploader(self):
        """Create a MockupPNGUploader instance for testing."""
        with (
            patch("leadfactory.services.mockup_png_uploader.SupabaseStorage"),
            patch("leadfactory.services.mockup_png_uploader.get_storage"),
        ):
            return MockupPNGUploader()

    @pytest.fixture
    def test_image_path(self):
        """Create a test PNG image file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            test_image = Image.new("RGBA", (800, 600), (255, 0, 0, 128))
            test_image.save(tmp_file.name, "PNG")
            yield Path(tmp_file.name)
            Path(tmp_file.name).unlink(missing_ok=True)

    def test_init_configuration(self):
        """Test uploader initialization with different configurations."""
        with (
            patch(
                "leadfactory.services.mockup_png_uploader.SupabaseStorage"
            ) as mock_supabase,
            patch(
                "leadfactory.services.mockup_png_uploader.get_storage"
            ) as mock_storage,
        ):
            # Test default bucket
            uploader = MockupPNGUploader()
            mock_supabase.assert_called_with("mockups")
            assert uploader.max_retries == 3
            assert uploader.retry_delay_base == 1.0
            assert uploader.max_file_size == 10 * 1024 * 1024

            # Test custom bucket
            uploader_custom = MockupPNGUploader("custom-bucket")
            mock_supabase.assert_called_with("custom-bucket")

    def test_validate_input_success(self, uploader, test_image_path):
        """Test successful input validation."""
        uploader.storage.get_business.return_value = {
            "id": 123,
            "name": "Test Business",
        }

        result = uploader._validate_input(test_image_path, 123)
        assert result is None

    def test_validate_input_file_not_found(self, uploader):
        """Test validation with non-existent file."""
        result = uploader._validate_input(Path("nonexistent.png"), 123)
        assert "File not found" in result

    def test_validate_input_empty_file(self, uploader):
        """Test validation with empty file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            empty_path = Path(tmp_file.name)
            try:
                result = uploader._validate_input(empty_path, 123)
                assert "File is empty" in result
            finally:
                empty_path.unlink(missing_ok=True)

    def test_validate_input_file_too_large(self, uploader):
        """Test validation with oversized file."""
        uploader.max_file_size = 100  # Very small limit for testing

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # Write more than 100 bytes
            tmp_file.write(b"0" * 200)
            large_path = Path(tmp_file.name)

            try:
                result = uploader._validate_input(large_path, 123)
                assert "File too large" in result
            finally:
                large_path.unlink(missing_ok=True)

    def test_validate_input_invalid_business_id(self, uploader, test_image_path):
        """Test validation with invalid business ID."""
        result = uploader._validate_input(test_image_path, -1)
        assert "Invalid business_id" in result

        result = uploader._validate_input(test_image_path, 0)
        assert "Invalid business_id" in result

    def test_validate_input_business_not_found(self, uploader, test_image_path):
        """Test validation when business doesn't exist."""
        uploader.storage.get_business.return_value = None

        result = uploader._validate_input(test_image_path, 999)
        assert "Business not found" in result

    def test_process_image_no_optimization(self, uploader, test_image_path):
        """Test image processing without optimization."""
        result_path = uploader._process_image(
            test_image_path, optimize=False, max_width=1920, quality=85
        )
        assert result_path == test_image_path

    def test_process_image_with_optimization(self, uploader):
        """Test image processing with optimization for large image."""
        # Create a large test image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            large_image = Image.new("RGBA", (3000, 2000), (0, 255, 0, 128))
            large_image.save(tmp_file.name, "PNG")
            large_path = Path(tmp_file.name)

            try:
                result_path = uploader._process_image(
                    large_path, optimize=True, max_width=1920, quality=85
                )

                # Should return optimized version
                assert result_path != large_path
                assert result_path.exists()

                # Check optimized dimensions
                with Image.open(result_path) as optimized_img:
                    assert optimized_img.width <= 1920
                    assert optimized_img.mode == "RGBA"

                # Cleanup optimized version
                result_path.unlink(missing_ok=True)

            finally:
                large_path.unlink(missing_ok=True)

    def test_process_image_no_optimization_needed(self, uploader, test_image_path):
        """Test image processing when no optimization is needed."""
        # Small image that doesn't need optimization
        result_path = uploader._process_image(
            test_image_path, optimize=True, max_width=1920, quality=85
        )
        assert result_path == test_image_path

    def test_generate_metadata_success(self, uploader, test_image_path):
        """Test successful metadata generation."""
        metadata = uploader._generate_metadata(test_image_path, 123, "homepage")

        assert metadata.business_id == 123
        assert metadata.mockup_type == "homepage"
        assert isinstance(metadata.generated_at, datetime)
        assert metadata.original_dimensions == (800, 600)
        assert metadata.optimized_dimensions == (800, 600)
        assert metadata.file_size_bytes > 0
        assert metadata.quality_score is not None
        assert 0 <= metadata.quality_score <= 1

    def test_generate_metadata_error_handling(self, uploader):
        """Test metadata generation with invalid image."""
        # Test with non-existent file
        metadata = uploader._generate_metadata(Path("nonexistent.png"), 123, "homepage")

        assert metadata.business_id == 123
        assert metadata.mockup_type == "homepage"
        assert metadata.original_dimensions == (0, 0)
        assert metadata.optimized_dimensions == (0, 0)
        assert metadata.file_size_bytes == 0

    def test_calculate_file_hash(self, uploader, test_image_path):
        """Test file hash calculation."""
        hash1 = uploader._calculate_file_hash(test_image_path)
        hash2 = uploader._calculate_file_hash(test_image_path)

        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64-character hex string

    def test_calculate_file_hash_different_files(self, uploader):
        """Test that different files produce different hashes."""
        # Create two different test images
        with (
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp1,
            tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp2,
        ):
            image1 = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
            image2 = Image.new("RGBA", (100, 100), (0, 255, 0, 128))

            image1.save(tmp1.name, "PNG")
            image2.save(tmp2.name, "PNG")

            path1 = Path(tmp1.name)
            path2 = Path(tmp2.name)

            try:
                hash1 = uploader._calculate_file_hash(path1)
                hash2 = uploader._calculate_file_hash(path2)

                assert hash1 != hash2

            finally:
                path1.unlink(missing_ok=True)
                path2.unlink(missing_ok=True)

    def test_generate_cdn_url_success(self, uploader):
        """Test successful CDN URL generation."""
        uploader.supabase_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://example.com/secure-url"
        }

        url = uploader._generate_cdn_url("test/path.png", expires_hours=24)
        assert url == "https://example.com/secure-url"

        uploader.supabase_storage.generate_secure_report_url.assert_called_once_with(
            "test/path.png", 24
        )

    def test_generate_cdn_url_fallback(self, uploader):
        """Test CDN URL generation with fallback."""
        # Primary method fails
        uploader.supabase_storage.generate_secure_report_url.side_effect = Exception(
            "API error"
        )
        # Fallback succeeds
        uploader.supabase_storage.generate_signed_url.return_value = (
            "https://fallback.com/url"
        )

        url = uploader._generate_cdn_url("test/path.png", expires_hours=24)
        assert url == "https://fallback.com/url"

        uploader.supabase_storage.generate_signed_url.assert_called_once_with(
            "test/path.png", 24 * 3600
        )

    def test_generate_cdn_url_complete_failure(self, uploader):
        """Test CDN URL generation when both methods fail."""
        uploader.supabase_storage.generate_secure_report_url.side_effect = Exception(
            "API error"
        )
        uploader.supabase_storage.generate_signed_url.side_effect = Exception(
            "Fallback error"
        )

        url = uploader._generate_cdn_url("test/path.png", expires_hours=24)
        assert url == ""

    def test_link_to_business_success(self, uploader):
        """Test successful business linking."""
        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="homepage",
            generated_at=datetime.utcnow(),
            original_dimensions=(800, 600),
            optimized_dimensions=(800, 600),
            file_size_bytes=1024,
            quality_score=0.8,
        )

        uploader.storage.create_asset.return_value = True

        result = uploader._link_to_business(
            123, "test/path.png", "https://cdn.com/url", metadata
        )
        assert result is True

        uploader.storage.create_asset.assert_called_once()
        call_args = uploader.storage.create_asset.call_args
        assert call_args[1]["business_id"] == 123
        assert call_args[1]["asset_type"] == "mockup"
        assert call_args[1]["file_path"] == "test/path.png"
        assert call_args[1]["url"] == "https://cdn.com/url"

    def test_link_to_business_failure(self, uploader):
        """Test business linking failure."""
        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="homepage",
            generated_at=datetime.utcnow(),
            original_dimensions=(800, 600),
            optimized_dimensions=(800, 600),
            file_size_bytes=1024,
        )

        uploader.storage.create_asset.return_value = False

        result = uploader._link_to_business(
            123, "test/path.png", "https://cdn.com/url", metadata
        )
        assert result is False

    def test_cleanup_orphaned_file_success(self, uploader):
        """Test successful orphaned file cleanup."""
        uploader.supabase_storage.delete_file.return_value = True

        result = uploader._cleanup_orphaned_file("test/orphaned.png")
        assert result is True

        uploader.supabase_storage.delete_file.assert_called_once_with(
            "test/orphaned.png"
        )

    def test_cleanup_orphaned_file_failure(self, uploader):
        """Test orphaned file cleanup failure."""
        uploader.supabase_storage.delete_file.side_effect = Exception("Delete failed")

        result = uploader._cleanup_orphaned_file("test/orphaned.png")
        assert result is False

    def test_check_file_linked_to_business_linked(self, uploader):
        """Test checking file linkage when file is linked."""
        uploader.storage.get_assets_by_path.return_value = [{"id": 1}]

        result = uploader._check_file_linked_to_business("test/path.png")
        assert result is True

    def test_check_file_linked_to_business_orphaned(self, uploader):
        """Test checking file linkage when file is orphaned."""
        uploader.storage.get_assets_by_path.return_value = []

        result = uploader._check_file_linked_to_business("test/path.png")
        assert result is False

    def test_check_file_linked_to_business_error(self, uploader):
        """Test checking file linkage with database error."""
        uploader.storage.get_assets_by_path.side_effect = Exception("DB error")

        # Should return True to avoid accidental deletion
        result = uploader._check_file_linked_to_business("test/path.png")
        assert result is True

    def test_is_url_expired_true(self, uploader):
        """Test URL expiration check for expired URL."""
        old_date = "2023-01-01T00:00:00"
        result = uploader._is_url_expired(old_date, expiry_hours=20)
        assert result is True

    def test_is_url_expired_false(self, uploader):
        """Test URL expiration check for fresh URL."""
        recent_date = datetime.utcnow().isoformat()
        result = uploader._is_url_expired(recent_date, expiry_hours=20)
        assert result is False

    def test_is_url_expired_invalid_date(self, uploader):
        """Test URL expiration check with invalid date."""
        result = uploader._is_url_expired("invalid-date", expiry_hours=20)
        assert result is True  # Should assume expired for safety


class TestMockupUploadResult:
    """Unit tests for MockupUploadResult dataclass."""

    def test_success_result(self):
        """Test successful upload result."""
        result = MockupUploadResult(
            success=True,
            storage_path="test/path.png",
            cdn_url="https://cdn.com/url",
            file_size=1024,
            business_id=123,
            upload_duration=2.5,
            retry_count=1,
        )

        assert result.success is True
        assert result.storage_path == "test/path.png"
        assert result.cdn_url == "https://cdn.com/url"
        assert result.file_size == 1024
        assert result.business_id == 123
        assert result.upload_duration == 2.5
        assert result.retry_count == 1
        assert result.error_message is None

    def test_failure_result(self):
        """Test failed upload result."""
        result = MockupUploadResult(
            success=False, error_message="Upload failed", retry_count=3
        )

        assert result.success is False
        assert result.error_message == "Upload failed"
        assert result.retry_count == 3
        assert result.storage_path is None
        assert result.cdn_url is None


class TestMockupImageMetadata:
    """Unit tests for MockupImageMetadata dataclass."""

    def test_complete_metadata(self):
        """Test complete metadata creation."""
        now = datetime.utcnow()
        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="homepage",
            generated_at=now,
            original_dimensions=(800, 600),
            optimized_dimensions=(800, 600),
            file_size_bytes=1024,
            quality_score=0.8,
        )

        assert metadata.business_id == 123
        assert metadata.mockup_type == "homepage"
        assert metadata.generated_at == now
        assert metadata.original_dimensions == (800, 600)
        assert metadata.optimized_dimensions == (800, 600)
        assert metadata.file_size_bytes == 1024
        assert metadata.quality_score == 0.8

    def test_minimal_metadata(self):
        """Test metadata with minimal required fields."""
        now = datetime.utcnow()
        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="product",
            generated_at=now,
            original_dimensions=(1920, 1080),
            optimized_dimensions=(1920, 1080),
            file_size_bytes=2048,
        )

        assert metadata.business_id == 123
        assert metadata.mockup_type == "product"
        assert metadata.quality_score is None  # Optional field


if __name__ == "__main__":
    # Run simple validation tests
    print("Running MockupPNGUploader unit tests...")

    # Test dataclass creation
    try:
        result = MockupUploadResult(success=True, business_id=123)
        assert result.success is True
        assert result.business_id == 123
        print("✅ MockupUploadResult creation successful")

        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="test",
            generated_at=datetime.utcnow(),
            original_dimensions=(400, 300),
            optimized_dimensions=(400, 300),
            file_size_bytes=1024,
        )
        assert metadata.business_id == 123
        print("✅ MockupImageMetadata creation successful")

        print("✅ All unit test validations passed")

    except Exception as e:
        print(f"❌ Unit test validation failed: {e}")
