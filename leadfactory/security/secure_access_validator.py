"""
Server-side validation system for secure PDF access.

This module provides comprehensive validation of user permissions
before generating URLs and handles access revocation mechanisms.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from leadfactory.email.secure_links import SecureLinkData, SecureLinkGenerator
from leadfactory.security.access_control import (
    AccessControlService,
    PDFOperation,
    UserContext,
    UserRole,
    get_access_control_service,
)
from leadfactory.security.audit_logger import get_audit_logger
from leadfactory.security.rate_limiter import RateLimitType, get_rate_limiter

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of access validation."""

    valid: bool
    error_message: Optional[str] = None
    user_context: Optional[UserContext] = None
    rate_limit_info: Optional[Dict] = None


@dataclass
class AccessRequest:
    """Represents a request for PDF access."""

    user_id: str
    resource_id: str
    operation: PDFOperation
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    token: Optional[str] = None


class SecureAccessValidator:
    """Service for validating secure access to PDF resources."""

    def __init__(self):
        """Initialize the secure access validator."""
        self.access_control = get_access_control_service()
        self.audit_logger = get_audit_logger()
        self.rate_limiter = get_rate_limiter()
        self.link_generator = SecureLinkGenerator()

        # Track revoked access tokens
        self._revoked_access_tokens: Dict[str, datetime] = {}

        logger.info("Secure access validator initialized")

    def validate_access_request(
        self, access_request: AccessRequest, resource_owner_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a complete access request with all security checks.

        Args:
            access_request: The access request to validate
            resource_owner_id: ID of the resource owner

        Returns:
            ValidationResult with validation outcome
        """
        try:
            # Step 1: Rate limiting check
            rate_limit_result = self.rate_limiter.check_rate_limit(
                user_id=access_request.user_id,
                operation_type=self._map_operation_to_rate_limit_type(
                    access_request.operation
                ),
                ip_address=access_request.ip_address,
            )

            if not rate_limit_result.allowed:
                self.audit_logger.log_access_denied(
                    user_id=access_request.user_id,
                    resource_id=access_request.resource_id,
                    operation=access_request.operation.value,
                    reason="Rate limit exceeded",
                    ip_address=access_request.ip_address,
                    user_agent=access_request.user_agent,
                    session_id=access_request.session_id,
                )
                return ValidationResult(
                    valid=False,
                    error_message=f"Rate limit exceeded. Retry after {rate_limit_result.retry_after_seconds} seconds.",
                    rate_limit_info={
                        "retry_after_seconds": rate_limit_result.retry_after_seconds,
                        "remaining_requests": rate_limit_result.remaining_requests,
                    },
                )

            # Step 2: Token revocation check
            if access_request.token and self.is_access_revoked(access_request.token):
                self.audit_logger.log_access_denied(
                    user_id=access_request.user_id,
                    resource_id=access_request.resource_id,
                    operation=access_request.operation.value,
                    reason="Access token revoked",
                    ip_address=access_request.ip_address,
                    user_agent=access_request.user_agent,
                    session_id=access_request.session_id,
                )
                return ValidationResult(
                    valid=False, error_message="Access token has been revoked"
                )

            # Step 3: Get user context (in real implementation, this would come from database)
            user_context = self._get_user_context(access_request)
            if not user_context:
                self.audit_logger.log_access_denied(
                    user_id=access_request.user_id,
                    resource_id=access_request.resource_id,
                    operation=access_request.operation.value,
                    reason="Invalid user context",
                    ip_address=access_request.ip_address,
                    user_agent=access_request.user_agent,
                    session_id=access_request.session_id,
                )
                return ValidationResult(
                    valid=False, error_message="Invalid user context"
                )

            # Step 4: Permission check
            has_permission = self.access_control.check_permission(
                user_context=user_context,
                operation=access_request.operation,
                resource_id=access_request.resource_id,
                resource_owner_id=resource_owner_id,
            )

            if not has_permission:
                self.audit_logger.log_access_denied(
                    user_id=access_request.user_id,
                    resource_id=access_request.resource_id,
                    operation=access_request.operation.value,
                    reason="Insufficient permissions",
                    ip_address=access_request.ip_address,
                    user_agent=access_request.user_agent,
                    session_id=access_request.session_id,
                )
                return ValidationResult(
                    valid=False,
                    error_message="Insufficient permissions for this operation",
                )

            # Step 5: Resource-specific validation
            if not self._validate_resource_access(access_request, user_context):
                self.audit_logger.log_access_denied(
                    user_id=access_request.user_id,
                    resource_id=access_request.resource_id,
                    operation=access_request.operation.value,
                    reason="Resource access validation failed",
                    ip_address=access_request.ip_address,
                    user_agent=access_request.user_agent,
                    session_id=access_request.session_id,
                )
                return ValidationResult(
                    valid=False, error_message="Resource access validation failed"
                )

            # All checks passed - log successful access
            self.audit_logger.log_access_granted(
                user_id=access_request.user_id,
                resource_id=access_request.resource_id,
                operation=access_request.operation.value,
                ip_address=access_request.ip_address,
                user_agent=access_request.user_agent,
                session_id=access_request.session_id,
            )

            return ValidationResult(
                valid=True,
                user_context=user_context,
                rate_limit_info={
                    "remaining_requests": rate_limit_result.remaining_requests,
                    "reset_time": (
                        rate_limit_result.reset_time.isoformat()
                        if rate_limit_result.reset_time
                        else None
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Error validating access request: {e}")
            return ValidationResult(
                valid=False, error_message="Internal validation error"
            )

    def generate_secure_url(
        self,
        user_id: str,
        resource_id: str,
        operation: PDFOperation,
        base_url: str,
        expiry_hours: int = 720,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate a secure URL after validating permissions.

        Args:
            user_id: ID of the user requesting access
            resource_id: ID of the resource
            operation: Operation to be performed
            base_url: Base URL for the secure link
            expiry_hours: Hours until link expires
            ip_address: IP address of the request
            user_agent: User agent of the request

        Returns:
            Tuple of (success, secure_url, error_message)
        """
        try:
            # Create access request
            access_request = AccessRequest(
                user_id=user_id,
                resource_id=resource_id,
                operation=operation,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Validate access
            validation_result = self.validate_access_request(access_request)
            if not validation_result.valid:
                return False, None, validation_result.error_message

            # Generate secure URL
            secure_url = self.link_generator.generate_secure_link(
                report_id=resource_id,
                user_id=user_id,
                purchase_id=f"purchase_{resource_id}",  # In real implementation, get from database
                base_url=base_url,
                expiry_days=expiry_hours / 24,
                access_type=operation.value,
            )

            # Log token generation
            self.audit_logger.log_token_generated(
                user_id=user_id,
                resource_id=resource_id,
                token_id=(
                    secure_url.split("token=")[-1][:10]
                    if "token=" in secure_url
                    else "unknown"
                ),
                expiry_time=datetime.utcnow() + timedelta(hours=expiry_hours),
                ip_address=ip_address,
            )

            return True, secure_url, None

        except Exception as e:
            logger.error(f"Error generating secure URL: {e}")
            return False, None, "Failed to generate secure URL"

    def revoke_access(
        self, token: str, reason: str, revoked_by: Optional[str] = None
    ) -> bool:
        """
        Revoke access for a specific token.

        Args:
            token: Token to revoke
            reason: Reason for revocation
            revoked_by: ID of user who revoked the token

        Returns:
            True if revocation was successful
        """
        try:
            # Add to revoked tokens
            self._revoked_access_tokens[token] = datetime.utcnow()

            # Also revoke in access control service
            self.access_control.revoke_token(token)

            # Log revocation
            self.audit_logger.log_token_revoked(
                user_id="system",  # In real implementation, extract from token
                token_id=token[:10],
                reason=reason,
                revoked_by=revoked_by,
            )

            logger.info(f"Access token revoked: {token[:10]}... Reason: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error revoking access token: {e}")
            return False

    def is_access_revoked(self, token: str) -> bool:
        """Check if a token has been revoked."""
        return (
            token in self._revoked_access_tokens
            or self.access_control.is_token_revoked(token)
        )

    def cleanup_expired_revocations(self, days_to_keep: int = 30):
        """Clean up old revocation records."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        expired_tokens = [
            token
            for token, revoked_time in self._revoked_access_tokens.items()
            if revoked_time < cutoff_date
        ]

        for token in expired_tokens:
            del self._revoked_access_tokens[token]

        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired revocation records")

    def _map_operation_to_rate_limit_type(
        self, operation: PDFOperation
    ) -> RateLimitType:
        """Map PDF operation to rate limit type."""
        mapping = {
            PDFOperation.GENERATE: RateLimitType.PDF_GENERATION,
            PDFOperation.VIEW: RateLimitType.PDF_ACCESS,
            PDFOperation.DOWNLOAD: RateLimitType.PDF_DOWNLOAD,
            PDFOperation.SHARE: RateLimitType.TOKEN_GENERATION,
        }
        return mapping.get(operation, RateLimitType.PDF_ACCESS)

    def _get_user_context(self, access_request: AccessRequest) -> Optional[UserContext]:
        """
        Get user context for access request.

        In a real implementation, this would query the database
        to get user role and permissions.
        """
        # For now, return a default customer context
        # In production, this would be replaced with database lookup
        return UserContext(
            user_id=access_request.user_id,
            role=UserRole.CUSTOMER,  # Default role
            permissions=[],  # Will be populated by access control service
            session_id=access_request.session_id,
            ip_address=access_request.ip_address,
            user_agent=access_request.user_agent,
        )

    def _validate_resource_access(
        self, access_request: AccessRequest, user_context: UserContext
    ) -> bool:
        """
        Validate resource-specific access rules.

        This can include checks like:
        - Resource exists
        - Resource is not expired
        - User has valid subscription
        - Resource is not under maintenance
        """
        # For now, always return True
        # In production, add specific resource validation logic
        return True

    def get_access_stats(self, user_id: str) -> Dict:
        """Get access statistics for a user."""
        return {
            "rate_limits": self.rate_limiter.get_user_stats(user_id),
            "revoked_tokens": len(
                [
                    token
                    for token, revoked_time in self._revoked_access_tokens.items()
                    if token.startswith(user_id[:8])  # Simple user association
                ]
            ),
        }


# Global secure access validator instance
_secure_access_validator: Optional[SecureAccessValidator] = None


def get_secure_access_validator() -> SecureAccessValidator:
    """Get the global secure access validator instance."""
    global _secure_access_validator
    if _secure_access_validator is None:
        _secure_access_validator = SecureAccessValidator()
    return _secure_access_validator
