#!/usr/bin/env python3
"""
Standalone validation script for Task 7: Mockup PNG Upload Integration.
Tests the implementation without relying on corrupted pytest environment.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


def test_basic_imports():
    """Test that all required modules can be imported."""
    try:
        from leadfactory.services.mockup_png_uploader import (
            MockupImageMetadata,
            MockupPNGUploader,
            MockupUploadResult,
            cleanup_orphaned_mockups,
            upload_business_mockup,
        )

        return True
    except Exception:
        return False


def test_dataclass_creation():
    """Test that dataclasses can be created and used."""
    try:
        from leadfactory.services.mockup_png_uploader import (
            MockupImageMetadata,
            MockupUploadResult,
        )

        # Test MockupUploadResult
        result = MockupUploadResult(success=True, business_id=123)
        assert result.success is True
        assert result.business_id == 123
        assert result.error_message is None

        # Test MockupImageMetadata
        metadata = MockupImageMetadata(
            business_id=123,
            mockup_type="homepage",
            generated_at=datetime.utcnow(),
            original_dimensions=(800, 600),
            optimized_dimensions=(800, 600),
            file_size_bytes=1024,
            quality_score=0.8,
        )
        assert metadata.business_id == 123
        assert metadata.mockup_type == "homepage"
        assert metadata.quality_score == 0.8

        return True

    except Exception:
        return False


def test_uploader_initialization():
    """Test MockupPNGUploader can be initialized with mocked dependencies."""
    try:
        from leadfactory.services.mockup_png_uploader import MockupPNGUploader

        with (
            patch(
                "leadfactory.services.mockup_png_uploader.SupabaseStorage"
            ) as mock_supabase,
            patch("leadfactory.services.mockup_png_uploader.get_storage"),
        ):
            # Test default bucket
            uploader = MockupPNGUploader()
            mock_supabase.assert_called_with("mockups")
            assert uploader.max_retries == 3
            assert uploader.retry_delay_base == 1.0

            # Test custom bucket
            MockupPNGUploader("custom-bucket")
            mock_supabase.assert_called_with("custom-bucket")

        return True

    except Exception:
        return False


def test_validation_methods():
    """Test validation methods work correctly."""
    try:
        from leadfactory.services.mockup_png_uploader import MockupPNGUploader

        with (
            patch("leadfactory.services.mockup_png_uploader.SupabaseStorage"),
            patch(
                "leadfactory.services.mockup_png_uploader.get_storage"
            ) as mock_get_storage,
        ):
            mock_storage = Mock()
            mock_get_storage.return_value = mock_storage
            uploader = MockupPNGUploader()

            # Test invalid business ID
            result = uploader._validate_input(Path("test.png"), -1)
            assert "Invalid business_id" in result

            # Test file not found
            result = uploader._validate_input(Path("nonexistent.png"), 123)
            assert "File not found" in result

        return True

    except Exception:
        return False


def test_file_hash_calculation():
    """Test file hash calculation works correctly."""
    try:
        from leadfactory.services.mockup_png_uploader import MockupPNGUploader

        with (
            patch("leadfactory.services.mockup_png_uploader.SupabaseStorage"),
            patch("leadfactory.services.mockup_png_uploader.get_storage"),
        ):
            uploader = MockupPNGUploader()

            # Create test file
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
                tmp_file.write("test content")
                test_path = Path(tmp_file.name)

            try:
                # Test hash calculation
                hash1 = uploader._calculate_file_hash(test_path)
                hash2 = uploader._calculate_file_hash(test_path)

                assert hash1 == hash2  # Same file should produce same hash
                assert len(hash1) == 64  # SHA-256 produces 64-character hex string

                return True

            finally:
                test_path.unlink(missing_ok=True)

    except Exception:
        return False


def test_convenience_functions():
    """Test convenience functions work correctly."""
    try:
        from leadfactory.services.mockup_png_uploader import (
            cleanup_orphaned_mockups,
            upload_business_mockup,
        )

        with patch(
            "leadfactory.services.mockup_png_uploader.mockup_uploader"
        ) as mock_uploader:
            from leadfactory.services.mockup_png_uploader import MockupUploadResult

            # Test upload convenience function
            mock_result = MockupUploadResult(success=True, business_id=123)
            mock_uploader.upload_mockup_png.return_value = mock_result

            result = upload_business_mockup("test.png", 123, "homepage")
            assert result.success is True
            assert result.business_id == 123

            # Test cleanup convenience function
            mock_uploader.cleanup_orphaned_images.return_value = {
                "files_checked": 5,
                "orphaned_files_found": 2,
                "files_deleted": 2,
                "errors": [],
            }

            cleanup_stats = cleanup_orphaned_mockups(max_age_hours=24)
            assert cleanup_stats["files_checked"] == 5
            assert cleanup_stats["files_deleted"] == 2

        return True

    except Exception:
        return False


def test_url_generation_methods():
    """Test URL generation and CDN methods."""
    try:
        from leadfactory.services.mockup_png_uploader import MockupPNGUploader

        with (
            patch(
                "leadfactory.services.mockup_png_uploader.SupabaseStorage"
            ) as mock_supabase_class,
            patch("leadfactory.services.mockup_png_uploader.get_storage"),
        ):
            mock_supabase = Mock()
            mock_supabase_class.return_value = mock_supabase
            uploader = MockupPNGUploader()

            # Test successful URL generation
            mock_supabase.generate_secure_report_url.return_value = {
                "signed_url": "https://example.com/secure-url"
            }

            url = uploader._generate_cdn_url("test/path.png", expires_hours=24)
            assert url == "https://example.com/secure-url"

            # Test fallback URL generation
            mock_supabase.generate_secure_report_url.side_effect = Exception(
                "API error"
            )
            mock_supabase.generate_signed_url.return_value = "https://fallback.com/url"

            url = uploader._generate_cdn_url("test/path.png", expires_hours=24)
            assert url == "https://fallback.com/url"

        return True

    except Exception:
        return False


def run_all_tests():
    """Run all validation tests."""

    tests = [
        ("Basic Imports", test_basic_imports),
        ("Dataclass Creation", test_dataclass_creation),
        ("Uploader Initialization", test_uploader_initialization),
        ("Validation Methods", test_validation_methods),
        ("File Hash Calculation", test_file_hash_calculation),
        ("Convenience Functions", test_convenience_functions),
        ("URL Generation Methods", test_url_generation_methods),
    ]

    passed = 0
    total = len(tests)

    for _test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                pass
        except Exception:
            pass

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
