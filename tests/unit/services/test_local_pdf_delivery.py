"""
Unit tests for the local PDF delivery service.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.services.local_pdf_delivery import LocalPDFDeliveryService


class TestLocalPDFDeliveryService:
    """Test local PDF delivery functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup handled by OS for temp directories

    @pytest.fixture
    def sample_pdf(self, temp_dir):
        """Create a sample PDF file for testing."""
        pdf_path = Path(temp_dir) / "sample.pdf"
        # Create a simple PDF-like file
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Test PDF content for local delivery testing\n%%EOF")
        return str(pdf_path)

    @pytest.fixture
    def local_delivery_service(self, temp_dir):
        """Create local delivery service with temp directory."""
        storage_path = Path(temp_dir) / "pdf_storage"
        return LocalPDFDeliveryService(
            storage_path=str(storage_path),
            base_url="http://localhost:8000/reports",
            max_email_size_mb=20
        )

    def test_initialization(self, temp_dir):
        """Test service initialization."""
        storage_path = Path(temp_dir) / "pdf_storage"
        service = LocalPDFDeliveryService(
            storage_path=str(storage_path),
            base_url="http://localhost:8000/reports",
            max_email_size_mb=25
        )

        assert service.storage_path == storage_path
        assert service.base_url == "http://localhost:8000/reports"
        assert service.max_email_size_bytes == 25 * 1024 * 1024
        assert storage_path.exists()

    def test_store_pdf_locally(self, local_delivery_service, sample_pdf):
        """Test storing PDF in local storage."""
        result = local_delivery_service.store_pdf_locally(
            pdf_path=sample_pdf,
            report_id="test-report-123",
            user_id="user-456"
        )

        assert "local_path" in result
        assert "relative_path" in result
        assert "file_size" in result
        assert "filename" in result
        assert "stored_at" in result

        # Verify file was actually copied
        local_path = Path(result["local_path"])
        assert local_path.exists()
        assert result["file_size"] > 0
        assert "user-456" in result["relative_path"]
        assert "test-report-123" in result["filename"]

    def test_generate_local_url(self, local_delivery_service):
        """Test generating local HTTP URLs."""
        result = local_delivery_service.generate_local_url(
            relative_path="user-123/report-456_20240101_120000.pdf",
            expiry_hours=168
        )

        assert "download_url" in result
        assert "expires_at" in result
        assert "expiry_hours" in result
        assert "access_method" in result

        assert result["download_url"] == "http://localhost:8000/reports/user-123/report-456_20240101_120000.pdf"
        assert result["expiry_hours"] == 168
        assert result["access_method"] == "local_http"

    def test_prepare_email_attachment_success(self, local_delivery_service, sample_pdf):
        """Test preparing PDF for email attachment (small file)."""
        result = local_delivery_service.prepare_email_attachment(
            pdf_path=sample_pdf,
            report_id="test-report-123"
        )

        assert result["attachment_ready"] is True
        assert "pdf_content" in result
        assert "filename" in result
        assert "file_size" in result
        assert "content_type" in result
        assert result["fallback_required"] is False

        assert isinstance(result["pdf_content"], bytes)
        assert "test-report-123" in result["filename"]
        assert result["content_type"] == "application/pdf"

    def test_prepare_email_attachment_too_large(self, temp_dir):
        """Test preparing PDF for email attachment (large file)."""
        # Create service with very small max size
        service = LocalPDFDeliveryService(
            storage_path=str(Path(temp_dir) / "pdf_storage"),
            max_email_size_mb=0.001  # 1KB limit
        )

        # Create a larger PDF file
        large_pdf = Path(temp_dir) / "large.pdf"
        with open(large_pdf, "wb") as f:
            f.write(b"%PDF-1.4\n" + b"X" * 2000 + b"\n%%EOF")  # 2KB file

        result = service.prepare_email_attachment(
            pdf_path=str(large_pdf),
            report_id="large-report"
        )

        assert result["attachment_ready"] is False
        assert result["reason"] == "file_too_large"
        assert result["fallback_required"] is True
        assert result["file_size"] > result["max_size"]

    @patch("leadfactory.services.local_pdf_delivery.datetime")
    def test_deliver_via_email_attachment(self, mock_datetime, local_delivery_service, sample_pdf):
        """Test complete email attachment delivery."""
        # Mock datetime for consistent testing
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"

        # Mock email service
        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = {
            "success": True,
            "message_id": "test-message-123"
        }

        result = local_delivery_service.deliver_via_email_attachment(
            pdf_path=sample_pdf,
            report_id="test-report-123",
            user_email="test@example.com",
            business_name="Test Business",
            email_service=mock_email_service
        )

        assert result["delivery_method"] == "email_attachment"
        assert result["success"] is True
        assert result["email_sent"] is True
        assert result["message_id"] == "test-message-123"
        assert "attachment_size" in result
        assert result["delivered_at"] == "2024-01-01T12:00:00"

        # Verify email service was called with correct parameters
        mock_email_service.send_email.assert_called_once()
        call_args = mock_email_service.send_email.call_args[1]
        assert call_args["to_email"] == "test@example.com"
        assert "Test Business" in call_args["subject"]
        assert len(call_args["attachments"]) == 1
        assert call_args["attachments"][0]["content_type"] == "application/pdf"

    @patch("leadfactory.services.local_pdf_delivery.datetime")
    def test_deliver_via_local_http(self, mock_datetime, local_delivery_service, sample_pdf):
        """Test complete local HTTP delivery."""
        # Mock datetime for consistent testing
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"

        # Mock email service
        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = {
            "success": True,
            "message_id": "test-message-456"
        }

        result = local_delivery_service.deliver_via_local_http(
            pdf_path=sample_pdf,
            report_id="test-report-456",
            user_id="user-789",
            user_email="test@example.com",
            business_name="Test Business",
            expiry_hours=168,
            email_service=mock_email_service
        )

        assert result["delivery_method"] == "local_http"
        assert result["success"] is True
        assert result["email_sent"] is True
        assert result["message_id"] == "test-message-456"
        assert "download_url" in result
        assert "local_path" in result
        assert "file_size" in result
        assert "expires_at" in result

        # Verify download URL format
        assert "http://localhost:8000/reports" in result["download_url"]
        assert "user-789" in result["download_url"]

        # Verify email service was called
        mock_email_service.send_email.assert_called_once()
        call_args = mock_email_service.send_email.call_args[1]
        assert call_args["to_email"] == "test@example.com"
        assert "Test Business" in call_args["subject"]
        assert result["download_url"] in call_args["content"]

    def test_cleanup_expired_files(self, local_delivery_service, sample_pdf):
        """Test cleanup of expired PDF files."""
        # Store some PDFs
        local_delivery_service.store_pdf_locally(
            pdf_path=sample_pdf,
            report_id="report-1",
            user_id="user-1"
        )

        local_delivery_service.store_pdf_locally(
            pdf_path=sample_pdf,
            report_id="report-2",
            user_id="user-2"
        )

        # Run cleanup with 0 days (should remove all files)
        result = local_delivery_service.cleanup_expired_files(max_age_days=0)

        assert "files_removed" in result
        assert "bytes_freed" in result
        assert result["files_removed"] >= 2
        assert result["bytes_freed"] > 0

    def test_email_content_generation(self, local_delivery_service):
        """Test email content generation methods."""
        # Test attachment email content
        attachment_content = local_delivery_service._build_attachment_email_content(
            business_name="Test Corp",
            report_id="report-123"
        )

        assert "Test Corp" in attachment_content
        assert "report-123" in attachment_content
        assert "attached" in attachment_content.lower()

        # Test download email content
        download_content = local_delivery_service._build_download_email_content(
            business_name="Test Corp",
            report_id="report-456",
            download_url="http://localhost:8000/reports/user/report.pdf",
            expires_at="2024-01-08T12:00:00"
        )

        assert "Test Corp" in download_content
        assert "report-456" in download_content
        assert "http://localhost:8000/reports/user/report.pdf" in download_content
        assert "January" in download_content  # Should format the expiry date


if __name__ == "__main__":
    pytest.main([__file__])
