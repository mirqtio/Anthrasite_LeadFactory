"""
Unit tests for the report delivery service with local delivery modes.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.services.local_pdf_delivery import LocalPDFDeliveryService


class TestReportDeliveryLocalModes:
    """Test report delivery service with local delivery configurations."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
    
    @pytest.fixture
    def sample_pdf(self, temp_dir):
        """Create a sample PDF file for testing."""
        pdf_path = Path(temp_dir) / "sample.pdf"
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Test PDF content\n%%EOF")
        return str(pdf_path)
    
    @patch('leadfactory.config.settings.PDF_DELIVERY_MODE', 'email')
    @patch('leadfactory.services.report_delivery.SupabaseStorage')
    @patch('leadfactory.services.report_delivery.EmailDeliveryService')
    def test_email_delivery_mode_routing(self, mock_email_service, mock_supabase, temp_dir, sample_pdf):
        """Test that email delivery mode routes to email attachment method."""
        from leadfactory.services.report_delivery import ReportDeliveryService
        
        # Mock dependencies
        mock_email_service.return_value = MagicMock()
        mock_supabase.return_value = MagicMock()
        
        # Create service with mocked delivery mode
        with patch.object(LocalPDFDeliveryService, '__init__', return_value=None):
            service = ReportDeliveryService()
            service.delivery_mode = 'email'
            service.local_delivery = MagicMock()
            
            # Mock the email attachment method
            service.local_delivery.deliver_via_email_attachment.return_value = {
                "success": True,
                "delivery_method": "email_attachment",
                "email_sent": True,
                "message_id": "test-123",
                "attachment_size": 1024,
                "delivered_at": "2024-01-01T12:00:00"
            }
            
            # Mock security components to bypass validation
            service.secure_validator = MagicMock()
            service.access_control = MagicMock()
            service.audit_logger = MagicMock()
            service.rate_limiter = MagicMock()
            
            # Mock validation result
            validation_result = MagicMock()
            validation_result.valid = True
            service.secure_validator.validate_access_request.return_value = validation_result
            
            # Test delivery
            result = service.upload_and_deliver_report(
                pdf_path=sample_pdf,
                report_id="test-report",
                user_id="test-user",
                user_email="test@example.com",
                purchase_id="purchase-123",
                business_name="Test Business"
            )
            
            # Verify it routed to email attachment
            assert result["delivery_method"] == "email_attachment"
            assert result["status"] == "delivered"
            service.local_delivery.deliver_via_email_attachment.assert_called_once()
    
    @patch('leadfactory.config.settings.PDF_DELIVERY_MODE', 'local')
    @patch('leadfactory.services.report_delivery.SupabaseStorage')
    @patch('leadfactory.services.report_delivery.EmailDeliveryService')
    def test_local_delivery_mode_routing(self, mock_email_service, mock_supabase, temp_dir, sample_pdf):
        """Test that local delivery mode routes to local HTTP method."""
        from leadfactory.services.report_delivery import ReportDeliveryService
        
        # Mock dependencies
        mock_email_service.return_value = MagicMock()
        mock_supabase.return_value = MagicMock()
        
        # Create service with mocked delivery mode
        with patch.object(LocalPDFDeliveryService, '__init__', return_value=None):
            service = ReportDeliveryService()
            service.delivery_mode = 'local'
            service.local_delivery = MagicMock()
            
            # Mock the local HTTP method
            service.local_delivery.deliver_via_local_http.return_value = {
                "success": True,
                "delivery_method": "local_http",
                "download_url": "http://localhost:8000/reports/user/report.pdf",
                "email_sent": True,
                "message_id": "test-456",
                "delivered_at": "2024-01-01T12:00:00"
            }
            
            # Mock security components to bypass validation
            service.secure_validator = MagicMock()
            service.access_control = MagicMock()
            service.audit_logger = MagicMock()
            service.rate_limiter = MagicMock()
            
            # Mock validation result
            validation_result = MagicMock()
            validation_result.valid = True
            service.secure_validator.validate_access_request.return_value = validation_result
            
            # Test delivery
            result = service.upload_and_deliver_report(
                pdf_path=sample_pdf,
                report_id="test-report",
                user_id="test-user",
                user_email="test@example.com",
                purchase_id="purchase-123",
                business_name="Test Business"
            )
            
            # Verify it routed to local HTTP
            assert result["delivery_method"] == "local_http"
            assert result["status"] == "delivered"
            assert "download_url" in result
            service.local_delivery.deliver_via_local_http.assert_called_once()
    
    @patch('leadfactory.config.settings.PDF_DELIVERY_MODE', 'cloud')
    @patch('leadfactory.services.report_delivery.SupabaseStorage')
    @patch('leadfactory.services.report_delivery.EmailDeliveryService')
    def test_cloud_delivery_mode_routing(self, mock_email_service, mock_supabase, temp_dir, sample_pdf):
        """Test that cloud delivery mode routes to original Supabase method."""
        from leadfactory.services.report_delivery import ReportDeliveryService
        
        # Mock dependencies
        mock_email_service.return_value = MagicMock()
        mock_supabase_instance = MagicMock()
        mock_supabase.return_value = mock_supabase_instance
        
        # Create service with mocked delivery mode
        with patch.object(LocalPDFDeliveryService, '__init__', return_value=None):
            service = ReportDeliveryService()
            service.delivery_mode = 'cloud'
            service.local_delivery = MagicMock()
            
            # Mock Supabase operations
            mock_supabase_instance.upload_pdf_report.return_value = {
                "storage_path": "reports/test-user/test-report.pdf"
            }
            mock_supabase_instance.generate_secure_report_url.return_value = {
                "signed_url": "https://supabase.co/storage/signed-url",
                "expires_at": "2024-01-08T12:00:00Z"
            }
            
            # Mock security components
            service.secure_validator = MagicMock()
            service.access_control = MagicMock()
            service.audit_logger = MagicMock()
            service.rate_limiter = MagicMock()
            service.email_service = MagicMock()
            
            # Mock validation and URL generation
            validation_result = MagicMock()
            validation_result.valid = True
            validation_result.rate_limit_info = {"remaining": 100}
            service.secure_validator.validate_access_request.return_value = validation_result
            service.secure_validator.generate_secure_url.return_value = (
                True, "https://app.com/secure-token", None
            )
            
            # Mock email sending
            service.email_service.send_email.return_value = {"success": True, "email_id": "email-123"}
            
            # Test delivery
            result = service.upload_and_deliver_report(
                pdf_path=sample_pdf,
                report_id="test-report",
                user_id="test-user",
                user_email="test@example.com",
                purchase_id="purchase-123",
                business_name="Test Business"
            )
            
            # Verify it used cloud storage
            assert result["status"] == "delivered"
            assert "signed_url" in result
            assert "storage_path" in result
            mock_supabase_instance.upload_pdf_report.assert_called_once()
            mock_supabase_instance.generate_secure_report_url.assert_called_once()
            
            # Verify local delivery methods were NOT called
            service.local_delivery.deliver_via_email_attachment.assert_not_called()
            service.local_delivery.deliver_via_local_http.assert_not_called()
    
    def test_email_attachment_fallback_to_local_http(self, temp_dir, sample_pdf):
        """Test fallback from email attachment to local HTTP when attachment fails."""
        from leadfactory.services.report_delivery import ReportDeliveryService
        
        # Create service instance with mocks
        with patch.object(LocalPDFDeliveryService, '__init__', return_value=None):
            service = ReportDeliveryService.__new__(ReportDeliveryService)
            service.delivery_mode = 'email'
            service.local_delivery = MagicMock()
            service.audit_logger = MagicMock()
            service.email_service = MagicMock()
            
            # Mock email attachment failure with fallback required
            service.local_delivery.deliver_via_email_attachment.return_value = {
                "success": False,
                "fallback_required": True,
                "reason": "file_too_large"
            }
            
            # Mock successful local HTTP fallback
            service.local_delivery.deliver_via_local_http.return_value = {
                "success": True,
                "delivery_method": "local_http",
                "download_url": "http://localhost:8000/reports/user/report.pdf",
                "email_sent": True,
                "delivered_at": "2024-01-01T12:00:00"
            }
            
            # Test the fallback mechanism
            result = service._deliver_via_email_attachment(
                pdf_path=sample_pdf,
                report_id="test-report",
                user_id="test-user",
                user_email="test@example.com",
                business_name="Test Business",
                purchase_id="purchase-123",
                expiry_hours=720,
                ip_address=None,
                user_agent=None
            )
            
            # Verify it fell back to local HTTP
            assert result["delivery_method"] == "local_http"
            assert result["status"] == "delivered"
            service.local_delivery.deliver_via_email_attachment.assert_called_once()
            service.local_delivery.deliver_via_local_http.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])