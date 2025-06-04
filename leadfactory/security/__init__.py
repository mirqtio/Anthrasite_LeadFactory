"""
Security module for PDF access control and audit logging.

This module provides comprehensive security features including:
- Role-based access control for PDF operations
- Security audit logging
- Rate limiting for PDF operations
- Secure access validation
- Token revocation mechanisms
"""

from .access_control import (
    AccessControlService,
    AccessPermission,
    PDFOperation,
    UserContext,
    UserRole,
    get_access_control_service,
)
from .audit_logger import (
    AuditEventType,
    AuditSeverity,
    SecurityAuditLogger,
    get_audit_logger,
)
from .rate_limiter import (
    PDFRateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitType,
    get_rate_limiter,
)
from .secure_access_validator import (
    AccessRequest,
    SecureAccessValidator,
    ValidationResult,
    get_secure_access_validator,
)

__all__ = [
    # Access Control
    "AccessControlService",
    "UserRole",
    "PDFOperation",
    "UserContext",
    "AccessPermission",
    "get_access_control_service",
    # Audit Logging
    "SecurityAuditLogger",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
    # Rate Limiting
    "PDFRateLimiter",
    "RateLimitType",
    "RateLimitConfig",
    "RateLimitResult",
    "get_rate_limiter",
    # Secure Access Validation
    "SecureAccessValidator",
    "AccessRequest",
    "ValidationResult",
    "get_secure_access_validator",
]
