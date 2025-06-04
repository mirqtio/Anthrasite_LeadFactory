"""
Unit tests for the ReportDeliveryService.

Tests the complete report delivery workflow including PDF upload,
secure link generation, and email delivery.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from leadfactory.email.secure_links import SecureLinkData
from leadfactory.services.report_delivery import ReportDeliveryService


class TestReportDeliveryService:
    """Test cases for ReportDeliveryService."""

    @pytest.fixture
    def mock_storage(self):
        """Mock Supabase storage."""
        with patch("leadfactory.services.report_delivery.SupabaseStorage") as mock:
            storage_instance = Mock()
            mock.return_value = storage_instance
            yield storage_instance

    @pytest.fixture
    def mock_link_generator(self):
        """Mock secure link generator."""
        with patch("leadfactory.services.report_delivery.SecureLinkGenerator") as mock:
            generator_instance = Mock()
            mock.return_value = generator_instance
            yield generator_instance

    @pytest.fixture
    def mock_email_service(self):
        """Mock email delivery service."""
        with patch("leadfactory.services.report_delivery.EmailDeliveryService") as mock:
            email_instance = Mock()
            mock.return_value = email_instance
            yield email_instance

    @pytest.fixture
    def service(self, mock_storage, mock_link_generator, mock_email_service):
        """Create ReportDeliveryService instance with mocked dependencies."""
        return ReportDeliveryService(
            storage_bucket="test-reports", link_expiry_hours=24
        )

    @pytest.fixture
    def sample_pdf_path(self):
        """Create a temporary PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            yield f.name
        # Cleanup is handled by the test framework

    def test_service_initialization(
        self, mock_storage, mock_link_generator, mock_email_service
    ):
        """Test service initialization with custom parameters."""
        with (
            patch(
                "leadfactory.services.report_delivery.SupabaseStorage"
            ) as mock_storage_class,
            patch(
                "leadfactory.services.report_delivery.SecureLinkGenerator"
            ) as mock_link_class,
            patch(
                "leadfactory.services.report_delivery.EmailDeliveryService"
            ) as mock_email_class,
        ):
            service = ReportDeliveryService(
                storage_bucket="custom-bucket", link_expiry_hours=48
            )

            assert service.default_expiry_hours == 48
            mock_storage_class.assert_called_once_with(bucket_name="custom-bucket")
            mock_link_class.assert_called_once()
            mock_email_class.assert_called_once()

    def test_upload_and_deliver_report_success(
        self,
        service,
        mock_storage,
        mock_link_generator,
        mock_email_service,
        sample_pdf_path,
    ):
        """Test successful complete report delivery workflow."""
        # Setup mocks
        mock_storage.upload_pdf_report.return_value = {
            "storage_path": "reports/user123/audit_report_123.pdf",
            "file_size": 1024,
            "uploaded_at": "2023-06-01T12:00:00Z",
        }

        mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://supabase.co/storage/signed-url-123",
            "expires_at": "2023-06-02T12:00:00Z",
        }

        mock_link_generator.generate_secure_link.return_value = "jwt-token-123"

        mock_email_service.send_email.return_value = {
            "success": True,
            "email_id": "email-123",
        }

        # Execute
        result = service.upload_and_deliver_report(
            pdf_path=sample_pdf_path,
            report_id="report-123",
            user_id="user-123",
            user_email="test@example.com",
            purchase_id="pi_123",
            business_name="Test Business",
        )

        # Verify storage upload
        mock_storage.upload_pdf_report.assert_called_once_with(
            pdf_path=sample_pdf_path,
            report_id="report-123",
            user_id="user-123",
            purchase_id="pi_123",
        )

        # Verify secure link generation
        mock_link_generator.generate_secure_link.assert_called_once()
        link_data_arg = mock_link_generator.generate_secure_link.call_args[1]["data"]
        assert link_data_arg.report_id == "report-123"
        assert link_data_arg.user_id == "user-123"
        assert link_data_arg.purchase_id == "pi_123"
        assert link_data_arg.access_type == "download"

        # Verify Supabase signed URL generation
        mock_storage.generate_secure_report_url.assert_called_once_with(
            storage_path="reports/user123/audit_report_123.pdf", expires_in_hours=24
        )

        # Verify email sending
        mock_email_service.send_email.assert_called_once()
        email_args = mock_email_service.send_email.call_args[1]
        assert email_args["to_email"] == "test@example.com"
        assert "Test Business" in email_args["subject"]
        assert email_args["template_name"] == "report_delivery"

        # Verify result
        assert result["status"] == "delivered"
        assert result["report_id"] == "report-123"
        assert result["user_id"] == "user-123"
        assert result["purchase_id"] == "pi_123"
        assert result["secure_token"] == "jwt-token-123"
        assert result["email_sent"] is True

    def test_upload_and_deliver_report_with_custom_expiry(
        self,
        service,
        mock_storage,
        mock_link_generator,
        mock_email_service,
        sample_pdf_path,
    ):
        """Test report delivery with custom expiry time."""
        # Setup mocks
        mock_storage.upload_pdf_report.return_value = {
            "storage_path": "reports/user123/audit_report_123.pdf"
        }
        mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://supabase.co/storage/signed-url-123",
            "expires_at": "2023-06-08T12:00:00Z",
        }
        mock_link_generator.generate_secure_link.return_value = "jwt-token-123"
        mock_email_service.send_email.return_value = {"success": True}

        # Execute with custom expiry
        service.upload_and_deliver_report(
            pdf_path=sample_pdf_path,
            report_id="report-123",
            user_id="user-123",
            user_email="test@example.com",
            purchase_id="pi_123",
            business_name="Test Business",
            expiry_hours=168,  # 7 days
        )

        # Verify custom expiry was used
        mock_storage.generate_secure_report_url.assert_called_once_with(
            storage_path="reports/user123/audit_report_123.pdf", expires_in_hours=168
        )

        # Verify link generation used correct expiry (converted to days)
        mock_link_generator.generate_secure_link.assert_called_once()
        expiry_days_arg = mock_link_generator.generate_secure_link.call_args[1][
            "expiry_days"
        ]
        assert expiry_days_arg == 7.0  # 168 hours / 24

    def test_upload_and_deliver_report_storage_failure(
        self, service, mock_storage, sample_pdf_path
    ):
        """Test handling of storage upload failure."""
        # Setup storage to fail
        mock_storage.upload_pdf_report.side_effect = Exception("Storage upload failed")

        # Execute and expect exception
        with pytest.raises(Exception, match="Storage upload failed"):
            service.upload_and_deliver_report(
                pdf_path=sample_pdf_path,
                report_id="report-123",
                user_id="user-123",
                user_email="test@example.com",
                purchase_id="pi_123",
                business_name="Test Business",
            )

    def test_upload_and_deliver_report_email_failure(
        self,
        service,
        mock_storage,
        mock_link_generator,
        mock_email_service,
        sample_pdf_path,
    ):
        """Test handling of email delivery failure."""
        # Setup mocks - email fails but others succeed
        mock_storage.upload_pdf_report.return_value = {
            "storage_path": "reports/user123/audit_report_123.pdf"
        }
        mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://supabase.co/storage/signed-url-123",
            "expires_at": "2023-06-02T12:00:00Z",
        }
        mock_link_generator.generate_secure_link.return_value = "jwt-token-123"
        mock_email_service.send_email.return_value = {
            "success": False,
            "error": "Email sending failed",
        }

        # Execute
        result = service.upload_and_deliver_report(
            pdf_path=sample_pdf_path,
            report_id="report-123",
            user_id="user-123",
            user_email="test@example.com",
            purchase_id="pi_123",
            business_name="Test Business",
        )

        # Should still return success but with email_sent=False
        assert result["status"] == "delivered"
        assert result["email_sent"] is False

    def test_validate_and_get_report_access_success(
        self, service, mock_link_generator, mock_storage
    ):
        """Test successful token validation and access info retrieval."""
        # Setup mocks
        mock_link_data = SecureLinkData(
            report_id="report-123",
            user_id="user-123",
            purchase_id="pi_123",
            expires_at=int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
            access_type="download",
            metadata={"storage_path": "reports/user123/audit_report_123.pdf"},
        )
        mock_link_generator.validate_secure_link.return_value = mock_link_data

        mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://supabase.co/storage/fresh-url-123",
            "expires_at": "2023-06-01T13:00:00Z",
        }

        # Execute
        result = service.validate_and_get_report_access("jwt-token-123")

        # Verify
        assert result["valid"] is True
        assert result["report_id"] == "report-123"
        assert result["user_id"] == "user-123"
        assert result["purchase_id"] == "pi_123"
        assert result["access_type"] == "download"
        assert result["storage_path"] == "reports/user123/audit_report_123.pdf"
        assert result["download_url"] == "https://supabase.co/storage/fresh-url-123"

        # Verify fresh URL generation with short expiry
        mock_storage.generate_secure_report_url.assert_called_once_with(
            storage_path="reports/user123/audit_report_123.pdf", expires_in_hours=1
        )

    def test_validate_and_get_report_access_invalid_token(
        self, service, mock_link_generator
    ):
        """Test handling of invalid token."""
        # Setup mock to raise exception
        mock_link_generator.validate_secure_link.side_effect = Exception(
            "Invalid token"
        )

        # Execute
        result = service.validate_and_get_report_access("invalid-token")

        # Verify
        assert result["valid"] is False
        assert "Invalid token" in result["error"]

    def test_validate_and_get_report_access_missing_storage_path(
        self, service, mock_link_generator
    ):
        """Test handling of token without storage path in metadata."""
        # Setup mock with missing storage path
        mock_link_data = SecureLinkData(
            report_id="report-123",
            user_id="user-123",
            purchase_id="pi_123",
            expires_at=int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
            access_type="download",
            metadata={},  # Missing storage_path
        )
        mock_link_generator.validate_secure_link.return_value = mock_link_data

        # Execute
        result = service.validate_and_get_report_access("jwt-token-123")

        # Verify
        assert result["valid"] is False
        assert "Storage path not found" in result["error"]

    def test_get_delivery_status_found(self, service, mock_storage):
        """Test getting delivery status for existing report."""
        # Setup mock
        mock_storage.list_files.return_value = [
            {
                "name": "reports/user123/audit_report_123_456789.pdf",
                "size": 1024,
                "created_at": "2023-06-01T12:00:00Z",
            },
            {
                "name": "reports/user123/other_report.pdf",
                "size": 2048,
                "created_at": "2023-06-01T11:00:00Z",
            },
        ]

        # Execute
        result = service.get_delivery_status("report_123", "user123")

        # Verify
        assert result["status"] == "delivered"
        assert result["report_id"] == "report_123"
        assert result["user_id"] == "user123"
        assert result["files_found"] == 1
        assert (
            result["latest_file"]["name"]
            == "reports/user123/audit_report_123_456789.pdf"
        )

        # Verify correct prefix used
        mock_storage.list_files.assert_called_once_with(prefix="reports/user123/")

    def test_get_delivery_status_not_found(self, service, mock_storage):
        """Test getting delivery status for non-existent report."""
        # Setup mock
        mock_storage.list_files.return_value = [
            {
                "name": "reports/user123/other_report.pdf",
                "size": 2048,
                "created_at": "2023-06-01T11:00:00Z",
            }
        ]

        # Execute
        result = service.get_delivery_status("nonexistent_report", "user123")

        # Verify
        assert result["status"] == "not_found"
        assert result["report_id"] == "nonexistent_report"
        assert result["user_id"] == "user123"
        assert result["files_found"] == 0

    def test_get_delivery_status_error(self, service, mock_storage):
        """Test handling of errors in delivery status check."""
        # Setup mock to raise exception
        mock_storage.list_files.side_effect = Exception("Storage error")

        # Execute
        result = service.get_delivery_status("report-123", "user123")

        # Verify
        assert result["status"] == "error"
        assert "Storage error" in result["error"]

    def test_cleanup_expired_reports_success(self, service, mock_storage):
        """Test successful cleanup of expired reports."""
        # Setup mock with files of different ages
        old_date = (datetime.utcnow() - timedelta(days=35)).isoformat() + "Z"
        recent_date = (datetime.utcnow() - timedelta(days=5)).isoformat() + "Z"

        mock_storage.list_files.return_value = [
            {"name": "reports/user1/old_report.pdf", "created_at": old_date},
            {"name": "reports/user2/recent_report.pdf", "created_at": recent_date},
            {"name": "reports/user3/very_old_report.pdf", "created_at": old_date},
        ]

        # Execute
        result = service.cleanup_expired_reports(days_old=30)

        # Verify
        assert result["status"] == "completed"
        assert result["deleted_count"] == 2
        assert len(result["errors"]) == 0

        # Verify delete calls
        assert mock_storage.delete_file.call_count == 2
        deleted_files = [call[0][0] for call in mock_storage.delete_file.call_args_list]
        assert "reports/user1/old_report.pdf" in deleted_files
        assert "reports/user3/very_old_report.pdf" in deleted_files

    def test_cleanup_expired_reports_with_errors(self, service, mock_storage):
        """Test cleanup with some deletion errors."""
        # Setup mock
        old_date = (datetime.utcnow() - timedelta(days=35)).isoformat() + "Z"

        mock_storage.list_files.return_value = [
            {"name": "reports/user1/old_report1.pdf", "created_at": old_date},
            {"name": "reports/user2/old_report2.pdf", "created_at": old_date},
        ]

        # Make first delete succeed, second fail
        def delete_side_effect(file_path):
            if "old_report2" in file_path:
                raise Exception("Delete failed")

        mock_storage.delete_file.side_effect = delete_side_effect

        # Execute
        result = service.cleanup_expired_reports(days_old=30)

        # Verify
        assert result["status"] == "completed"
        assert result["deleted_count"] == 1  # Only first one succeeded
        assert len(result["errors"]) == 1
        assert "Delete failed" in result["errors"][0]

    def test_cleanup_expired_reports_list_error(self, service, mock_storage):
        """Test cleanup when file listing fails."""
        # Setup mock to fail
        mock_storage.list_files.side_effect = Exception("List files failed")

        # Execute
        result = service.cleanup_expired_reports(days_old=30)

        # Verify
        assert result["status"] == "error"
        assert "List files failed" in result["error"]

    def test_create_secure_link_data(self, service):
        """Test creation of secure link data structure."""
        # Execute
        link_data = service._create_secure_link_data(
            report_id="report-123",
            user_id="user-123",
            purchase_id="pi_123",
            storage_path="reports/user123/report.pdf",
            expiry_hours=48,
        )

        # Verify
        assert link_data.report_id == "report-123"
        assert link_data.user_id == "user-123"
        assert link_data.purchase_id == "pi_123"
        assert link_data.access_type == "download"
        assert link_data.metadata["storage_path"] == "reports/user123/report.pdf"
        assert link_data.metadata["delivery_method"] == "supabase_storage"
        assert link_data.metadata["expiry_hours"] == 48

        # Verify expiration is approximately correct (within 1 minute)
        expected_expiry = datetime.utcnow() + timedelta(hours=48)
        actual_expiry = datetime.fromtimestamp(link_data.expires_at)
        assert abs((expected_expiry - actual_expiry).total_seconds()) < 60
