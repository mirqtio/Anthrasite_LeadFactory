"""
Unit tests for the secure access validator.

Tests server-side validation, access control integration,
rate limiting, token revocation, and audit logging.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from leadfactory.security.secure_access_validator import (
    SecureAccessValidator,
    AccessRequest,
    ValidationResult,
    get_secure_access_validator
)
from leadfactory.security.access_control import UserRole, PDFOperation
from leadfactory.security.rate_limiter import RateLimitType


class TestAccessRequest:
    """Test cases for AccessRequest dataclass."""

    def test_access_request_creation(self):
        """Test creating an AccessRequest instance."""
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW,
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            token="test_token"
        )

        assert request.user_id == "test_user"
        assert request.resource_id == "test_resource"
        assert request.operation == PDFOperation.VIEW
        assert request.ip_address == "192.168.1.1"
        assert request.user_agent == "Test Agent"
        assert request.token == "test_token"


class TestAccessValidationResult:
    """Test cases for AccessValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating an AccessValidationResult instance."""
        result = ValidationResult(
            valid=True,
            user_context=None,
            rate_limit_info={"requests_remaining": 10},
            error_message=None
        )

        assert result.valid is True
        assert result.user_context is None
        assert result.rate_limit_info["requests_remaining"] == 10
        assert result.error_message is None


class TestSecureAccessValidator:
    """Test cases for SecureAccessValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mocks for dependencies
        self.mock_access_control = Mock()
        self.mock_rate_limiter = Mock()
        self.mock_audit_logger = Mock()

        # Create validator with mocked dependencies
        with patch('leadfactory.security.secure_access_validator.get_access_control_service', return_value=self.mock_access_control), \
             patch('leadfactory.security.secure_access_validator.get_rate_limiter', return_value=self.mock_rate_limiter), \
             patch('leadfactory.security.secure_access_validator.get_audit_logger', return_value=self.mock_audit_logger):
            self.validator = SecureAccessValidator()

    def test_validate_access_request_success(self):
        """Test successful access request validation."""
        # Setup mocks
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = True

        mock_rate_result = Mock()
        mock_rate_result.allowed = True
        mock_rate_result.requests_remaining = 10
        mock_rate_result.violation = None
        self.mock_rate_limiter.check_rate_limit.return_value = mock_rate_result

        # Create test request
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW,
            ip_address="192.168.1.1"
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        assert result.valid is True
        assert result.error_message is None
        assert result.rate_limit_info is not None

    def test_validate_access_request_user_revoked(self):
        """Test validation fails for revoked user."""
        # Setup mocks
        self.mock_access_control.is_user_revoked.return_value = True

        # Create test request
        request = AccessRequest(
            user_id="revoked_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        assert result.valid is False
        assert "revoked" in result.error_message.lower()

    def test_validate_access_request_permission_denied(self):
        """Test validation fails for insufficient permissions."""
        # Setup mocks
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = False

        # Create test request
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.DELETE
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        assert result.valid is False
        assert "permission" in result.error_message.lower()

    def test_validate_access_request_rate_limited(self):
        """Test validation fails for rate limit exceeded."""
        # Setup mocks
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = True

        mock_rate_result = Mock()
        mock_rate_result.allowed = False
        mock_rate_result.violation = Mock()
        mock_rate_result.violation.retry_after = datetime.utcnow() + timedelta(minutes=5)
        self.mock_rate_limiter.check_rate_limit.return_value = mock_rate_result

        # Create test request
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.GENERATE
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        assert result.valid is False
        assert "rate limit" in result.error_message.lower()

    def test_generate_secure_url_success(self):
        """Test successful secure URL generation."""
        # Setup validation to succeed
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = True

        mock_rate_result = Mock()
        mock_rate_result.allowed = True
        mock_rate_result.requests_remaining = 10
        self.mock_rate_limiter.check_rate_limit.return_value = mock_rate_result

        # Mock secure link generator
        with patch('leadfactory.security.secure_access_validator.SecureLinkGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_secure_link.return_value = "https://example.com/secure-link"
            mock_generator_class.return_value = mock_generator

            # Generate secure URL
            result = self.validator.generate_secure_url(
                user_id="test_user",
                resource_id="test_resource",
                operation=PDFOperation.VIEW,
                base_url="https://example.com",
                metadata={"storage_path": "/path/to/file"}
            )

            assert result["success"] is True
            assert "secure_url" in result
            assert result["secure_url"] == "https://example.com/secure-link"

    def test_generate_secure_url_validation_failed(self):
        """Test secure URL generation fails when validation fails."""
        # Setup validation to fail
        self.mock_access_control.is_user_revoked.return_value = True

        # Generate secure URL
        result = self.validator.generate_secure_url(
            user_id="revoked_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW,
            base_url="https://example.com"
        )

        assert result["success"] is False
        assert "error" in result

    def test_revoke_access_success(self):
        """Test successful access revocation."""
        token = "test_token_12345"

        # Revoke access
        success = self.validator.revoke_access(
            token=token,
            reason="Security breach",
            revoked_by="admin_user"
        )

        assert success is True
        assert token in self.validator.revoked_tokens

    def test_is_access_revoked(self):
        """Test checking if access is revoked."""
        token = "test_token_67890"

        # Token should not be revoked initially
        assert not self.validator.is_access_revoked(token)

        # Revoke the token
        self.validator.revoke_access(token, "Test revocation")

        # Token should now be revoked
        assert self.validator.is_access_revoked(token)

    def test_cleanup_expired_revocations(self):
        """Test cleanup of expired revocations."""
        token = "expired_token"

        # Add a revocation with past expiry
        self.validator.revoked_tokens[token] = {
            "revoked_at": datetime.utcnow() - timedelta(days=2),
            "expires_at": datetime.utcnow() - timedelta(days=1),
            "reason": "Test",
            "revoked_by": "admin"
        }

        # Cleanup expired revocations
        self.validator.cleanup_expired_revocations()

        # Token should no longer be revoked
        assert not self.validator.is_access_revoked(token)

    def test_get_access_stats(self):
        """Test getting access statistics for a user."""
        user_id = "test_user"

        # Mock some access attempts
        self.validator.access_attempts[user_id] = {
            "total_attempts": 10,
            "successful_attempts": 8,
            "failed_attempts": 2,
            "last_access": datetime.utcnow()
        }

        stats = self.validator.get_access_stats(user_id)

        assert stats["user_id"] == user_id
        assert stats["total_attempts"] == 10
        assert stats["successful_attempts"] == 8
        assert stats["failed_attempts"] == 2
        assert "last_access" in stats

    def test_validate_resource_access_with_conditions(self):
        """Test resource access validation with specific conditions."""
        # Setup mocks for conditional access
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = True

        mock_rate_result = Mock()
        mock_rate_result.allowed = True
        self.mock_rate_limiter.check_rate_limit.return_value = mock_rate_result

        # Create request with resource owner
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW,
            resource_owner_id="test_user"  # Same as user_id
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        # Should call check_permission with resource_owner_id
        self.mock_access_control.check_permission.assert_called_with(
            user_context=result.user_context,
            operation=PDFOperation.VIEW,
            resource_id="test_resource",
            resource_owner_id="test_user"
        )

    def test_audit_logging_on_validation(self):
        """Test that validation results are properly logged."""
        # Setup successful validation
        self.mock_access_control.is_user_revoked.return_value = False
        self.mock_access_control.check_permission.return_value = True

        mock_rate_result = Mock()
        mock_rate_result.allowed = True
        self.mock_rate_limiter.check_rate_limit.return_value = mock_rate_result

        # Create test request
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW,
            ip_address="192.168.1.1"
        )

        # Validate request
        self.validator.validate_access_request(request)

        # Verify audit logging was called
        self.mock_audit_logger.log_access_granted.assert_called()

    def test_error_handling_in_validation(self):
        """Test error handling during validation."""
        # Setup mocks to raise exception
        self.mock_access_control.is_user_revoked.side_effect = Exception("Database error")

        # Create test request
        request = AccessRequest(
            user_id="test_user",
            resource_id="test_resource",
            operation=PDFOperation.VIEW
        )

        # Validate request
        result = self.validator.validate_access_request(request)

        assert result.valid is False
        assert "error" in result.error_message.lower()


class TestSecureAccessValidatorSingleton:
    """Test the singleton pattern for secure access validator."""

    def test_singleton_instance(self):
        """Test that get_secure_access_validator returns the same instance."""
        with patch('leadfactory.security.secure_access_validator.get_access_control_service'), \
             patch('leadfactory.security.secure_access_validator.get_rate_limiter'), \
             patch('leadfactory.security.secure_access_validator.get_audit_logger'):

            validator1 = get_secure_access_validator()
            validator2 = get_secure_access_validator()

            assert validator1 is validator2
            assert isinstance(validator1, SecureAccessValidator)
