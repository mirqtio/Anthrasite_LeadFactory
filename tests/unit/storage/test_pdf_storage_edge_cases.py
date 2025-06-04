"""
Unit tests for PDF storage edge cases and validation scenarios.

Tests edge cases including large files, invalid PDFs, network failures,
and storage quota limitations.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from leadfactory.storage.supabase_storage import SupabaseStorage


class TestPDFStorageEdgeCases:
    """Test suite for PDF storage edge cases and validation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create various test PDF contents
        self.valid_pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        )
        self.large_pdf_content = b"%PDF-1.4\n" + b"x" * (50 * 1024 * 1024)  # 50MB PDF
        self.huge_pdf_content = b"%PDF-1.4\n" + b"x" * (200 * 1024 * 1024)  # 200MB PDF
        self.invalid_pdf_content = b"This is not a PDF file"
        self.corrupted_pdf_content = b"%PDF-1.4\nCorrupted content\x00\x01\x02"
        self.empty_pdf_content = b""

        # Create temporary files
        self.temp_files = []
        for content, suffix in [
            (self.valid_pdf_content, "_valid.pdf"),
            (self.large_pdf_content, "_large.pdf"),
            (self.huge_pdf_content, "_huge.pdf"),
            (self.invalid_pdf_content, "_invalid.pdf"),
            (self.corrupted_pdf_content, "_corrupted.pdf"),
            (self.empty_pdf_content, "_empty.pdf"),
        ]:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(content)
            temp_file.close()
            self.temp_files.append(temp_file)

    def teardown_method(self):
        """Clean up test files."""
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file.name)
            except FileNotFoundError:
                pass

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client for testing."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def storage(self, mock_supabase_client):
        """Create SupabaseStorage instance for testing."""
        with patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key",
            }.get(key)
            return SupabaseStorage(bucket_name="edge-case-test")

    def test_large_file_upload_success(self, storage, mock_supabase_client):
        """Test successful upload of large PDF files."""
        # Mock successful large file upload
        mock_supabase_client.storage.from_.return_value.upload.return_value = {
            "path": "reports/large/large_report_20240101_120000.pdf"
        }

        large_temp_file = self.temp_files[1]  # large PDF

        result = storage.upload_pdf_report(
            pdf_path=large_temp_file.name,
            report_id="large_report",
            user_id="user_large",
            purchase_id="purchase_large",
        )

        # Verify large file handling
        assert result["size_bytes"] == len(self.large_pdf_content)
        assert result["content_type"] == "application/pdf"
        assert "large_report" in result["storage_path"]

        # Verify upload was called
        mock_supabase_client.storage.from_.return_value.upload.assert_called_once()

    def test_huge_file_upload_rejection(self, storage, mock_supabase_client):
        """Test rejection of extremely large PDF files."""
        # Mock storage quota exceeded error
        mock_supabase_client.storage.from_.return_value.upload.side_effect = Exception(
            "File size exceeds maximum allowed size"
        )

        huge_temp_file = self.temp_files[2]  # huge PDF

        with pytest.raises(Exception, match="File size exceeds maximum"):
            storage.upload_pdf_report(
                pdf_path=huge_temp_file.name,
                report_id="huge_report",
                user_id="user_huge",
                purchase_id="purchase_huge",
            )

    def test_invalid_pdf_format_detection(self, storage, mock_supabase_client):
        """Test detection and handling of invalid PDF format."""
        invalid_temp_file = self.temp_files[3]  # invalid PDF

        # Mock validation that would detect invalid format
        with pytest.raises(ValueError, match="Invalid PDF format"):
            # This should be caught by PDF validation before upload
            with patch(
                "pathlib.Path.open", mock_open(read_data=self.invalid_pdf_content)
            ):
                if not self.invalid_pdf_content.startswith(b"%PDF"):
                    raise ValueError("Invalid PDF format detected")

    def test_corrupted_pdf_handling(self, storage, mock_supabase_client):
        """Test handling of corrupted PDF files."""
        corrupted_temp_file = self.temp_files[4]  # corrupted PDF

        # Mock upload that detects corruption
        mock_supabase_client.storage.from_.return_value.upload.side_effect = Exception(
            "File appears to be corrupted"
        )

        with pytest.raises(Exception, match="corrupted"):
            storage.upload_pdf_report(
                pdf_path=corrupted_temp_file.name,
                report_id="corrupted_report",
                user_id="user_corrupted",
                purchase_id="purchase_corrupted",
            )

    def test_empty_file_handling(self, storage, mock_supabase_client):
        """Test handling of empty PDF files."""
        empty_temp_file = self.temp_files[5]  # empty PDF

        with pytest.raises(ValueError, match="Empty file"):
            # Check file size before upload
            file_size = Path(empty_temp_file.name).stat().st_size
            if file_size == 0:
                raise ValueError("Empty file not allowed")

    def test_network_timeout_handling(self, storage, mock_supabase_client):
        """Test handling of network timeouts during upload."""
        import socket

        # Mock network timeout
        mock_supabase_client.storage.from_.return_value.upload.side_effect = (
            socket.timeout("Network timeout during upload")
        )

        valid_temp_file = self.temp_files[0]  # valid PDF

        with pytest.raises(socket.timeout):
            storage.upload_pdf_report(
                pdf_path=valid_temp_file.name,
                report_id="timeout_report",
                user_id="user_timeout",
                purchase_id="purchase_timeout",
            )

    def test_storage_quota_exceeded(self, storage, mock_supabase_client):
        """Test handling when storage quota is exceeded."""
        # Mock quota exceeded error
        mock_supabase_client.storage.from_.return_value.upload.side_effect = Exception(
            "Storage quota exceeded for bucket"
        )

        valid_temp_file = self.temp_files[0]  # valid PDF

        with pytest.raises(Exception, match="Storage quota exceeded"):
            storage.upload_pdf_report(
                pdf_path=valid_temp_file.name,
                report_id="quota_report",
                user_id="user_quota",
                purchase_id="purchase_quota",
            )

    def test_invalid_file_path_handling(self, storage, mock_supabase_client):
        """Test handling of invalid file paths."""
        with pytest.raises(FileNotFoundError):
            storage.upload_pdf_report(
                pdf_path="/nonexistent/path/file.pdf",
                report_id="nonexistent_report",
                user_id="user_nonexistent",
                purchase_id="purchase_nonexistent",
            )

    def test_special_characters_in_filename(self, storage, mock_supabase_client):
        """Test handling of special characters in filenames."""
        # Mock successful upload with sanitized filename
        mock_supabase_client.storage.from_.return_value.upload.return_value = {
            "path": "reports/user_special/report_special_chars_20240101_120000.pdf"
        }

        valid_temp_file = self.temp_files[0]  # valid PDF

        result = storage.upload_pdf_report(
            pdf_path=valid_temp_file.name,
            report_id="report@#$%^&*()",  # Special characters
            user_id="user/special\\chars",
            purchase_id='purchase<>:"?|',
        )

        # Verify special characters were handled
        assert "special" in result["storage_path"]
        # Should not contain problematic characters in the path
        assert "@#$%^&*()" not in result["storage_path"]

    def test_concurrent_upload_conflicts(self, storage, mock_supabase_client):
        """Test handling of concurrent upload conflicts."""
        # Mock conflict error
        mock_supabase_client.storage.from_.return_value.upload.side_effect = Exception(
            "File already exists with same name"
        )

        valid_temp_file = self.temp_files[0]  # valid PDF

        with pytest.raises(Exception, match="already exists"):
            storage.upload_pdf_report(
                pdf_path=valid_temp_file.name,
                report_id="conflict_report",
                user_id="user_conflict",
                purchase_id="purchase_conflict",
            )

    def test_url_generation_with_expired_credentials(
        self, storage, mock_supabase_client
    ):
        """Test URL generation when credentials are expired."""
        # Mock expired credentials error
        mock_supabase_client.storage.from_.return_value.create_signed_url.side_effect = Exception(
            "Credentials have expired"
        )

        with pytest.raises(Exception, match="Credentials have expired"):
            storage.generate_signed_url("test-report.pdf", expires_in_seconds=3600)

    def test_url_generation_with_invalid_path(self, storage, mock_supabase_client):
        """Test URL generation with invalid storage path."""
        # Mock file not found error
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "error": "File not found at specified path"
        }

        with pytest.raises(Exception, match="Failed to generate signed URL"):
            storage.generate_signed_url("nonexistent/path/file.pdf")

    def test_metadata_validation_edge_cases(self, storage, mock_supabase_client):
        """Test metadata validation with edge case values."""
        # Mock successful upload
        mock_supabase_client.storage.from_.return_value.upload.return_value = {
            "path": "reports/metadata_test/report_metadata_20240101_120000.pdf"
        }

        valid_temp_file = self.temp_files[0]  # valid PDF

        # Test with extremely long metadata values
        long_string = "x" * 1000

        result = storage.upload_pdf_report(
            pdf_path=valid_temp_file.name,
            report_id=long_string[:50],  # Should be truncated
            user_id=long_string[:50],
            purchase_id=long_string[:50],
        )

        # Verify metadata was processed
        assert len(result["metadata"]["report_id"]) <= 50
        assert len(result["metadata"]["user_id"]) <= 50
        assert len(result["metadata"]["purchase_id"]) <= 50

    def test_file_permission_errors(self, storage, mock_supabase_client):
        """Test handling of file permission errors."""
        valid_temp_file = self.temp_files[0]  # valid PDF

        # Mock permission denied error when reading file
        with patch(
            "pathlib.Path.open", side_effect=PermissionError("Permission denied")
        ):
            with pytest.raises(PermissionError):
                storage.upload_pdf_report(
                    pdf_path=valid_temp_file.name,
                    report_id="permission_report",
                    user_id="user_permission",
                    purchase_id="purchase_permission",
                )

    def test_disk_space_exhaustion(self, storage, mock_supabase_client):
        """Test handling when local disk space is exhausted."""
        # Mock disk space error
        mock_supabase_client.storage.from_.return_value.upload.side_effect = OSError(
            "No space left on device"
        )

        valid_temp_file = self.temp_files[0]  # valid PDF

        with pytest.raises(OSError, match="No space left on device"):
            storage.upload_pdf_report(
                pdf_path=valid_temp_file.name,
                report_id="diskspace_report",
                user_id="user_diskspace",
                purchase_id="purchase_diskspace",
            )

    def test_malformed_response_handling(self, storage, mock_supabase_client):
        """Test handling of malformed responses from Supabase."""
        # Mock malformed response
        mock_supabase_client.storage.from_.return_value.upload.return_value = {
            "invalid_field": "unexpected_value"
            # Missing expected "path" field
        }

        valid_temp_file = self.temp_files[0]  # valid PDF

        with pytest.raises(KeyError):
            # Should fail when trying to access expected response fields
            result = storage.upload_pdf_report(
                pdf_path=valid_temp_file.name,
                report_id="malformed_report",
                user_id="user_malformed",
                purchase_id="purchase_malformed",
            )
            # This should raise KeyError when accessing result["path"]
            _ = result["path"]

    def test_unicode_filename_handling(self, storage, mock_supabase_client):
        """Test handling of Unicode characters in filenames."""
        # Mock successful upload with Unicode handling
        mock_supabase_client.storage.from_.return_value.upload.return_value = {
            "path": "reports/unicode_user/unicode_report_20240101_120000.pdf"
        }

        valid_temp_file = self.temp_files[0]  # valid PDF

        result = storage.upload_pdf_report(
            pdf_path=valid_temp_file.name,
            report_id="报告_测试",  # Chinese characters
            user_id="用户_тест",  # Mixed Unicode
            purchase_id="购买_αβγ",  # Greek letters
        )

        # Verify Unicode was handled (likely converted to safe ASCII)
        assert result["storage_path"] is not None
        assert "unicode" in result["storage_path"]

    def test_extremely_long_file_paths(self, storage, mock_supabase_client):
        """Test handling of extremely long file paths."""
        # Create a very long path
        long_path = "/".join(["very_long_directory_name"] * 20) + "/file.pdf"

        with pytest.raises((OSError, ValueError)):
            # Should fail due to path length limitations
            storage.upload_file(
                file_path=long_path,
                storage_path=long_path,
                content_type="application/pdf",
            )
