"""
Tests for Supabase storage implementation.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from leadfactory.storage.supabase_storage import SupabaseStorage


class TestSupabaseStorage:
    """Test suite for SupabaseStorage class."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client for testing."""
        with patch('leadfactory.storage.supabase_storage.create_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def storage(self, mock_supabase_client):
        """Create SupabaseStorage instance for testing."""
        with patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env:
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key'
            }.get(key)

            return SupabaseStorage(bucket_name="test-bucket")

    def test_initialization_success(self, mock_supabase_client):
        """Test successful SupabaseStorage initialization."""
        with patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env:
            mock_get_env.side_effect = lambda key: {
                'SUPABASE_URL': 'https://test.supabase.co',
                'SUPABASE_KEY': 'test-key'
            }.get(key)

            storage = SupabaseStorage(bucket_name="reports")

            assert storage.bucket_name == "reports"
            assert storage.supabase_url == 'https://test.supabase.co'
            assert storage.supabase_key == 'test-key'

    def test_initialization_missing_env_vars(self):
        """Test initialization fails with missing environment variables."""
        with patch('leadfactory.storage.supabase_storage.get_env') as mock_get_env:
            mock_get_env.return_value = None

            with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_KEY"):
                SupabaseStorage()

    def test_upload_file_success(self, storage, mock_supabase_client):
        """Test successful file upload."""
        # Mock file system
        test_content = b"test file content"

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=test_content)):

            # Mock Supabase upload
            mock_supabase_client.storage.from_.return_value.upload.return_value = {
                "path": "test/file.pdf"
            }

            result = storage.upload_file(
                file_path="test_file.pdf",
                storage_path="test/file.pdf",
                content_type="application/pdf",
                metadata={"test": "value"}
            )

            # Verify upload was called correctly
            mock_supabase_client.storage.from_.assert_called_with("test-bucket")
            mock_supabase_client.storage.from_.return_value.upload.assert_called_once()

            # Verify result
            assert result["storage_path"] == "test/file.pdf"
            assert result["bucket"] == "test-bucket"
            assert result["size_bytes"] == len(test_content)
            assert result["content_type"] == "application/pdf"
            assert result["metadata"]["test"] == "value"

    def test_upload_file_not_found(self, storage):
        """Test upload fails when file doesn't exist."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                storage.upload_file("nonexistent.pdf", "test/file.pdf")

    def test_upload_pdf_report(self, storage, mock_supabase_client):
        """Test PDF report upload with standardized naming."""
        test_content = b"PDF content"

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=test_content)), \
             patch('leadfactory.storage.supabase_storage.datetime') as mock_datetime:

            # Mock datetime for consistent timestamps
            mock_datetime.utcnow.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            # Mock Supabase upload
            mock_supabase_client.storage.from_.return_value.upload.return_value = {
                "path": "reports/user123/report456_20240101_120000.pdf"
            }

            result = storage.upload_pdf_report(
                pdf_path="test.pdf",
                report_id="report456",
                user_id="user123",
                purchase_id="purchase789"
            )

            # Verify the storage path follows the expected pattern
            expected_path = "reports/user123/report456_20240101_120000.pdf"
            assert result["storage_path"] == expected_path

            # Verify metadata
            assert result["metadata"]["report_id"] == "report456"
            assert result["metadata"]["user_id"] == "user123"
            assert result["metadata"]["purchase_id"] == "purchase789"
            assert result["metadata"]["file_type"] == "pdf_report"

    def test_upload_png_image(self, storage, mock_supabase_client):
        """Test PNG image upload with standardized naming."""
        test_content = b"PNG content"

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=test_content)), \
             patch('leadfactory.storage.supabase_storage.datetime') as mock_datetime:

            # Mock datetime for consistent timestamps
            mock_datetime.utcnow.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            # Mock Supabase upload
            mock_supabase_client.storage.from_.return_value.upload.return_value = {
                "path": "mockups/image123_20240101_120000.png"
            }

            result = storage.upload_png_image(
                png_path="test.png",
                image_id="image123",
                category="mockups"
            )

            # Verify the storage path follows the expected pattern
            expected_path = "mockups/image123_20240101_120000.png"
            assert result["storage_path"] == expected_path

            # Verify metadata
            assert result["metadata"]["image_id"] == "image123"
            assert result["metadata"]["category"] == "mockups"
            assert result["metadata"]["file_type"] == "png_image"

    def test_generate_signed_url_success(self, storage, mock_supabase_client):
        """Test successful signed URL generation."""
        # Mock Supabase signed URL response
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test-bucket/file.pdf?token=abc123"
        }

        signed_url = storage.generate_signed_url("file.pdf", expires_in_seconds=3600)

        # Verify the call
        mock_supabase_client.storage.from_.assert_called_with("test-bucket")
        mock_supabase_client.storage.from_.return_value.create_signed_url.assert_called_with(
            path="file.pdf",
            expires_in=3600
        )

        assert "token=abc123" in signed_url

    def test_generate_signed_url_failure(self, storage, mock_supabase_client):
        """Test signed URL generation failure."""
        # Mock Supabase error response
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "error": "File not found"
        }

        with pytest.raises(Exception, match="Failed to generate signed URL"):
            storage.generate_signed_url("nonexistent.pdf")

    def test_generate_secure_report_url(self, storage, mock_supabase_client):
        """Test secure report URL generation with metadata."""
        # Mock Supabase signed URL response
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test-bucket/report.pdf?token=xyz789"
        }

        with patch('leadfactory.storage.supabase_storage.datetime') as mock_datetime:
            # Mock current time
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = storage.generate_secure_report_url("report.pdf", expires_in_hours=48)

            # Verify result structure
            assert "signed_url" in result
            assert "storage_path" in result
            assert "expires_at" in result
            assert "expires_in_hours" in result
            assert "generated_at" in result

            assert result["storage_path"] == "report.pdf"
            assert result["expires_in_hours"] == 48
            assert "token=xyz789" in result["signed_url"]

    def test_list_files(self, storage, mock_supabase_client):
        """Test file listing functionality."""
        # Mock Supabase list response
        mock_files = [
            {"name": "file1.pdf", "size": 1024},
            {"name": "file2.pdf", "size": 2048}
        ]
        mock_supabase_client.storage.from_.return_value.list.return_value = mock_files

        result = storage.list_files(prefix="reports/", limit=50)

        # Verify the call
        mock_supabase_client.storage.from_.assert_called_with("test-bucket")
        mock_supabase_client.storage.from_.return_value.list.assert_called_with(
            path="reports/",
            limit=50
        )

        assert len(result) == 2
        assert result[0]["name"] == "file1.pdf"

    def test_delete_file_success(self, storage, mock_supabase_client):
        """Test successful file deletion."""
        # Mock Supabase delete response
        mock_supabase_client.storage.from_.return_value.remove.return_value = [
            {"name": "file.pdf"}
        ]

        result = storage.delete_file("file.pdf")

        # Verify the call
        mock_supabase_client.storage.from_.assert_called_with("test-bucket")
        mock_supabase_client.storage.from_.return_value.remove.assert_called_with(["file.pdf"])

        assert result is True

    def test_get_file_info_found(self, storage, mock_supabase_client):
        """Test getting file info when file exists."""
        # Mock Supabase list response
        mock_files = [
            {"name": "target.pdf", "size": 1024, "created_at": "2024-01-01T12:00:00Z"},
            {"name": "other.pdf", "size": 2048, "created_at": "2024-01-01T11:00:00Z"}
        ]
        mock_supabase_client.storage.from_.return_value.list.return_value = mock_files

        result = storage.get_file_info("reports/target.pdf")

        # Should find the matching file
        assert result is not None
        assert result["name"] == "target.pdf"
        assert result["size"] == 1024

    def test_get_file_info_not_found(self, storage, mock_supabase_client):
        """Test getting file info when file doesn't exist."""
        # Mock Supabase list response with no matching files
        mock_files = [
            {"name": "other.pdf", "size": 2048, "created_at": "2024-01-01T11:00:00Z"}
        ]
        mock_supabase_client.storage.from_.return_value.list.return_value = mock_files

        result = storage.get_file_info("reports/nonexistent.pdf")

        # Should return None for non-existent file
        assert result is None

    def test_content_type_auto_detection(self, storage, mock_supabase_client):
        """Test automatic content type detection."""
        test_content = b"test content"

        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=test_content)):

            # Mock Supabase upload
            mock_supabase_client.storage.from_.return_value.upload.return_value = {
                "path": "test/file.pdf"
            }

            result = storage.upload_file(
                file_path="test_file.pdf",  # .pdf extension should auto-detect as application/pdf
                storage_path="test/file.pdf"
            )

            assert result["content_type"] == "application/pdf"
