"""
Integration tests for the enhanced report delivery service with security features.

Tests the complete integration of access control, rate limiting, audit logging,
and secure URL generation in the report delivery workflow.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from leadfactory.services.report_delivery import ReportDeliveryService
from leadfactory.security.access_control import UserRole, PDFOperation
from leadfactory.security.rate_limiter import RateLimitType


class TestReportDeliveryServiceSecurity:
    """Integration tests for ReportDeliveryService with security features."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock all external dependencies before creating service instance
        self.mock_storage = Mock()
        self.mock_email_service = Mock()
        self.mock_link_generator = Mock()
        self.mock_secure_validator = Mock()
        self.mock_access_control = Mock()
        self.mock_rate_limiter = Mock()
        self.mock_audit_logger = Mock()

        # Create service instance with mocked dependencies
        self.service = ReportDeliveryService(
            storage=self.mock_storage,
            email_service=self.mock_email_service,
            link_generator=self.mock_link_generator,
            secure_validator=self.mock_secure_validator,
            access_control=self.mock_access_control,
            rate_limiter=self.mock_rate_limiter,
            audit_logger=self.mock_audit_logger
        )

        # Create test PDF content
        self.test_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"

        # Create temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        self.temp_file.write(self.test_pdf_content)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_upload_and_deliver_report_success_with_security(self):
        """Test successful report upload and delivery with security validation."""
        # Mock all dependencies for successful operation
        self.mock_storage.upload_pdf_report.return_value = {"success": True, "storage_path": "test/path"}
        self.mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://storage.example.com/signed-url",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        }
        self.mock_email_service.send_email.return_value = {"success": True}
        self.mock_secure_validator.validate_access_request.return_value = Mock(
            valid=True,
            error_message=None,
            rate_limit_info={}
        )
        self.mock_secure_validator.generate_secure_url.return_value = (True, "https://example.com/secure/link", None)
        self.mock_link_generator.generate_secure_link.return_value = "https://example.com/secure/link"

        # Test the upload and delivery
        result = self.service.upload_and_deliver_report(
            pdf_path=self.temp_file.name,
            report_id="test_report_123",
            user_id="test_user_456",
            user_email="test@example.com",
            purchase_id="purchase_789",
            business_name="Test Business"
        )

        # Verify result structure
        assert result["status"] == "delivered"
        assert result["report_id"] == "test_report_123"
        assert result["user_id"] == "test_user_456"
        assert "secure_url" in result
        assert "signed_url" in result
        assert result["security_validated"] is True

        # Verify security validation was called
        self.mock_secure_validator.validate_access_request.assert_called_once()

        # Verify storage upload was called
        self.mock_storage.upload_pdf_report.assert_called_once()

        # Verify email was sent
        self.mock_email_service.send_email.assert_called_once()

        # Verify audit logging
        self.mock_audit_logger.log_access_granted.assert_called()

    def test_upload_and_deliver_report_access_denied(self):
        """Test access denied scenario with security validation."""
        # Mock security validation to deny access
        self.mock_secure_validator.validate_access_request.return_value = Mock(
            valid=False,
            error_message="User not authorized for this report",
            rate_limit_info={}
        )

        # Test the upload and delivery - should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            self.service.upload_and_deliver_report(
                pdf_path=self.temp_file.name,
                report_id="test_report",
                user_id="test_user",
                user_email="test@example.com",
                purchase_id="purchase_123",
                business_name="Test Business"
            )

        # Verify the exception message
        assert "Access denied" in str(exc_info.value)
        assert "User not authorized" in str(exc_info.value)

        # Verify security validation was called
        self.mock_secure_validator.validate_access_request.assert_called_once()

        # Verify audit logging for denied access
        self.mock_audit_logger.log_access_denied.assert_called_once()

        # Verify storage upload was NOT called
        self.mock_storage.upload_pdf_report.assert_not_called()

        # Verify email was NOT sent
        self.mock_email_service.send_email.assert_not_called()

    def test_upload_and_deliver_report_rate_limited(self):
        """Test report delivery fails when rate limited."""
        # Mock security validation to indicate rate limiting
        self.mock_secure_validator.validate_access_request.return_value = Mock(
            valid=False,
            error_message="Rate limit exceeded for user",
            rate_limit_info={"requests_remaining": 0, "reset_time": "2024-01-01T12:00:00Z"}
        )

        # Test the upload and delivery - should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            self.service.upload_and_deliver_report(
                pdf_path=self.temp_file.name,
                report_id="test_report",
                user_id="test_user",
                user_email="test@example.com",
                purchase_id="purchase_123",
                business_name="Test Business"
            )

        # Verify the exception message
        assert "Access denied" in str(exc_info.value)
        assert "Rate limit exceeded" in str(exc_info.value)

        # Verify security validation was called
        self.mock_secure_validator.validate_access_request.assert_called_once()

        # Verify audit logging for denied access
        self.mock_audit_logger.log_access_denied.assert_called_once()

        # Verify storage upload was NOT called
        self.mock_storage.upload_pdf_report.assert_not_called()

        # Verify email was NOT sent
        self.mock_email_service.send_email.assert_not_called()

    def test_validate_and_get_report_access_success(self):
        """Test successful report access validation."""
        # Mock dependencies for successful validation
        mock_link_data = Mock()
        mock_link_data.user_id = "test_user"
        mock_link_data.report_id = "test_report"
        mock_link_data.purchase_id = "purchase_123"
        mock_link_data.access_type = "download"
        mock_link_data.expires_at = datetime.utcnow() + timedelta(hours=1)
        mock_link_data.metadata = {"storage_path": "test/path"}

        self.mock_link_generator.validate_secure_link.return_value = mock_link_data
        self.mock_secure_validator.is_access_revoked.return_value = False
        self.mock_secure_validator.validate_access_request.return_value = Mock(
            valid=True,
            error_message=None,
            rate_limit_info={}
        )
        self.mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://storage.example.com/signed-url",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        }

        # Test validation
        result = self.service.validate_and_get_report_access(
            secure_token="valid_token_123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        # Verify result
        assert result["valid"] is True
        assert result["user_id"] == "test_user"
        assert result["report_id"] == "test_report"
        assert result["security_validated"] is True

        # Verify audit logging
        self.mock_audit_logger.log_access_granted.assert_called_once()

    def test_validate_and_get_report_access_revoked_token(self):
        """Test validation fails for revoked token."""
        # Mock token as revoked
        self.mock_secure_validator.is_access_revoked.return_value = True

        # Test validation
        result = self.service.validate_and_get_report_access(
            secure_token="revoked_token_123"
        )

        # Verify result
        assert result["valid"] is False
        assert "revoked" in result["error"].lower()

    def test_validate_and_get_report_access_invalid_token(self):
        """Test validation fails for invalid token."""
        # Mock link generator to raise exception for invalid token
        self.mock_link_generator.validate_secure_link.side_effect = Exception("Invalid token")
        self.mock_secure_validator.is_access_revoked.return_value = False

        # Test validation
        result = self.service.validate_and_get_report_access(
            secure_token="invalid_token_123"
        )

        # Verify result
        assert result["valid"] is False
        assert "Invalid token" in result["error"]

    def test_revoke_report_access_success(self):
        """Test successful token revocation."""
        # Mock successful revocation
        self.mock_secure_validator.revoke_access.return_value = True

        # Test revocation
        result = self.service.revoke_report_access(
            token="token_to_revoke",
            reason="Security violation",
            revoked_by="admin_user"
        )

        # Verify result
        assert result["success"] is True
        assert "revoked successfully" in result["message"]
        assert "revoked_at" in result

    def test_revoke_report_access_failure(self):
        """Test token revocation failure."""
        # Mock failed revocation
        self.mock_secure_validator.revoke_access.return_value = False

        # Test revocation
        result = self.service.revoke_report_access(
            token="token_to_revoke",
            reason="Security violation"
        )

        # Verify result
        assert result["success"] is False
        assert "Failed to revoke" in result["error"]

    def test_get_user_access_stats(self):
        """Test getting user access statistics."""
        # Mock rate limiter and validator stats
        self.mock_rate_limiter.get_user_stats.return_value = {
            "test_user": {
                "pdf_generation": {"requests_made": 5, "requests_remaining": 15}
            }
        }

        self.mock_secure_validator.get_access_stats.return_value = {
            "total_attempts": 10,
            "successful_attempts": 8,
            "failed_attempts": 2
        }

        # Test getting stats
        result = self.service.get_user_access_stats("test_user")

        # Verify result
        assert result["user_id"] == "test_user"
        assert "rate_limiting" in result
        assert "access_control" in result
        assert "generated_at" in result

    def test_audit_logging_integration(self):
        """Test that audit events are properly logged during operations."""
        # Mock all dependencies for successful operation
        self.mock_storage.upload_pdf_report.return_value = {"success": True, "storage_path": "test/path"}
        self.mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://storage.example.com/signed-url",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        }
        self.mock_email_service.send_email.return_value = {"success": True}
        self.mock_secure_validator.validate_access_request.return_value = Mock(valid=True, error_message=None, rate_limit_info={})
        self.mock_secure_validator.generate_secure_url.return_value = (True, "https://example.com/secure/link", None)
        self.mock_link_generator.generate_secure_link.return_value = "https://example.com/secure/link"

        # Test operation
        self.service.upload_and_deliver_report(
            pdf_path=self.temp_file.name,
            report_id="test_report",
            user_id="test_user",
            user_email="test@example.com",
            purchase_id="purchase_123",
            business_name="Test Business"
        )

        # Verify audit logging was called
        self.mock_audit_logger.log_access_granted.assert_called()

        # Verify the audit logging includes the correct information
        call_args = self.mock_audit_logger.log_access_granted.call_args
        assert call_args is not None

    def test_security_error_handling(self):
        """Test error handling in security operations."""
        # Mock security service to raise exception
        self.mock_secure_validator.validate_access_request.side_effect = Exception("Security service error")

        # Test operation - should raise the exception
        with pytest.raises(Exception) as exc_info:
            self.service.upload_and_deliver_report(
                pdf_path=self.temp_file.name,
                report_id="test_report",
                user_id="test_user",
                user_email="test@example.com",
                purchase_id="purchase_123",
                business_name="Test Business"
            )

        # Verify the exception message
        assert "Security service error" in str(exc_info.value)

    def test_multiple_security_checks_integration(self):
        """Test integration of multiple security checks in sequence."""
        # Test sequence: access control -> rate limiting -> token validation -> audit logging

        # Mock link data for token validation
        mock_link_data = Mock()
        mock_link_data.user_id = "test_user"
        mock_link_data.report_id = "test_report"
        mock_link_data.metadata = {"storage_path": "reports/test.pdf"}

        self.mock_secure_validator.is_access_revoked.return_value = False
        self.mock_link_generator.validate_secure_link.return_value = mock_link_data

        # First call succeeds, second call rate limited
        self.mock_secure_validator.validate_access_request.side_effect = [
            Mock(valid=True, error_message=None, rate_limit_info={"requests_remaining": 1}),
            Mock(valid=False, error_message="Rate limit exceeded", rate_limit_info={"retry_after": datetime.utcnow()})
        ]

        self.mock_storage.generate_secure_report_url.return_value = {
            "signed_url": "https://example.com",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        }

        # First access should succeed
        result1 = self.service.validate_and_get_report_access(
            secure_token="token1"
        )
        assert result1["valid"] is True

        # Second access should be rate limited
        result2 = self.service.validate_and_get_report_access(
            secure_token="token2"
        )
        assert result2["valid"] is False
        assert "Rate limit exceeded" in result2["error"]

    def test_concurrent_access_handling(self):
        """Test handling of concurrent access requests."""
        # This test simulates concurrent access to test thread safety
        import threading
        import time

        results = []

        def access_report(token_suffix):
            """Simulate concurrent access."""
            try:
                self.mock_secure_validator.is_access_revoked.return_value = False

                mock_link_data = Mock()
                mock_link_data.user_id = f"user_{token_suffix}"
                mock_link_data.report_id = "shared_report"
                mock_link_data.metadata = {"storage_path": "reports/shared.pdf"}
                self.mock_link_generator.validate_secure_link.return_value = mock_link_data

                self.mock_secure_validator.validate_access_request.return_value = Mock(valid=True, error_message=None, rate_limit_info={})
                self.mock_storage.generate_secure_report_url.return_value = {
                    "signed_url": f"https://example.com/{token_suffix}",
                    "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
                }

                result = self.service.validate_and_get_report_access(
                    f"token_{token_suffix}"
                )
                results.append(result)
            except Exception as e:
                results.append({"valid": False, "error": str(e)})

        # Create multiple threads for concurrent access
        threads = []
        for i in range(5):
            thread = threading.Thread(target=access_report, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests were handled
        assert len(results) == 5
        # All should succeed in this test scenario
        assert all(result.get("valid", False) for result in results)
