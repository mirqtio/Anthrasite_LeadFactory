"""
Security audit logging system for PDF report operations.

This module provides comprehensive audit logging for all PDF-related
security events, access attempts, and administrative actions.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from leadfactory.config import get_env

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""

    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    TOKEN_GENERATED = "token_generated"
    TOKEN_REVOKED = "token_revoked"
    SESSION_CREATED = "session_created"
    SESSION_REVOKED = "session_revoked"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PERMISSION_CHECK = "permission_check"
    RESOURCE_ACCESS = "resource_access"
    SECURITY_VIOLATION = "security_violation"


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a security audit event."""

    event_type: AuditEventType
    severity: AuditSeverity
    user_id: str
    resource_id: Optional[str] = None
    operation: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    additional_data: Optional[dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.additional_data is None:
            self.additional_data = {}


class SecurityAuditLogger:
    """Service for logging security audit events."""

    def __init__(self, log_file_path: Optional[str] = None):
        """
        Initialize the security audit logger.

        Args:
            log_file_path: Path to the audit log file. If None, uses default.
        """
        self.log_file_path = log_file_path or self._get_default_log_path()
        self._setup_audit_logger()

        logger.info(f"Security audit logger initialized: {self.log_file_path}")

    def _get_default_log_path(self) -> str:
        """Get the default audit log file path."""
        import tempfile

        default_log_dir = os.path.join(tempfile.gettempdir(), "leadfactory", "audit")
        log_dir = get_env("AUDIT_LOG_DIR", default_log_dir)  # nosec B108
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        return f"{log_dir}/security_audit.log"

    def _setup_audit_logger(self):
        """Setup the audit logger with proper formatting."""
        self.audit_logger = logging.getLogger("security_audit")
        self.audit_logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        for handler in self.audit_logger.handlers[:]:
            self.audit_logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file_path)
        file_handler.setLevel(logging.INFO)

        # Create formatter for structured logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        self.audit_logger.addHandler(file_handler)
        self.audit_logger.propagate = False

    def log_event(self, event: AuditEvent):
        """
        Log a security audit event.

        Args:
            event: The audit event to log
        """
        try:
            # Convert event to dictionary for JSON serialization
            event_dict = asdict(event)
            event_dict["timestamp"] = event.timestamp.isoformat()

            # Create log message
            log_message = json.dumps(event_dict, default=str)

            # Log at appropriate level based on severity
            if event.severity == AuditSeverity.CRITICAL:
                self.audit_logger.critical(log_message)
            elif event.severity == AuditSeverity.HIGH:
                self.audit_logger.error(log_message)
            elif event.severity == AuditSeverity.MEDIUM:
                self.audit_logger.warning(log_message)
            else:
                self.audit_logger.info(log_message)

            # Also log to main application logger for critical events
            if event.severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
                logger.warning(
                    f"Security audit: {event.event_type.value} - {event.user_id}"
                )

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    def log_access_granted(
        self,
        user_id: str,
        resource_id: str,
        operation: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log successful access grant."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.LOW,
            user_id=user_id,
            resource_id=resource_id,
            operation=operation,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=True,
            additional_data=additional_data,
        )
        self.log_event(event)

    def log_access_denied(
        self,
        user_id: str,
        resource_id: str,
        operation: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log access denial."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.MEDIUM,
            user_id=user_id,
            resource_id=resource_id,
            operation=operation,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=False,
            error_message=reason,
            additional_data=additional_data,
        )
        self.log_event(event)

    def log_token_generated(
        self,
        user_id: str,
        resource_id: str,
        token_id: str,
        expiry_time: datetime,
        ip_address: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log token generation."""
        event = AuditEvent(
            event_type=AuditEventType.TOKEN_GENERATED,
            severity=AuditSeverity.LOW,
            user_id=user_id,
            resource_id=resource_id,
            ip_address=ip_address,
            success=True,
            additional_data={
                "token_id": token_id,
                "expiry_time": expiry_time.isoformat(),
                **(additional_data or {}),
            },
        )
        self.log_event(event)

    def log_token_revoked(
        self,
        user_id: str,
        token_id: str,
        reason: str,
        revoked_by: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log token revocation."""
        event = AuditEvent(
            event_type=AuditEventType.TOKEN_REVOKED,
            severity=AuditSeverity.MEDIUM,
            user_id=user_id,
            success=True,
            additional_data={
                "token_id": token_id,
                "reason": reason,
                "revoked_by": revoked_by,
                **(additional_data or {}),
            },
        )
        self.log_event(event)

    def log_rate_limit_exceeded(
        self,
        user_id: str,
        operation: str,
        limit_type: str,
        current_count: int,
        limit_value: int,
        ip_address: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log rate limit violation."""
        event = AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            operation=operation,
            ip_address=ip_address,
            success=False,
            error_message=f"Rate limit exceeded: {current_count}/{limit_value}",
            additional_data={
                "limit_type": limit_type,
                "current_count": current_count,
                "limit_value": limit_value,
                **(additional_data or {}),
            },
        )
        self.log_event(event)

    def log_security_violation(
        self,
        user_id: str,
        violation_type: str,
        description: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log security violation."""
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message=description,
            additional_data={
                "violation_type": violation_type,
                **(additional_data or {}),
            },
        )
        self.log_event(event)

    def log_session_created(
        self,
        user_id: str,
        session_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log session creation."""
        event = AuditEvent(
            event_type=AuditEventType.SESSION_CREATED,
            severity=AuditSeverity.LOW,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            additional_data=additional_data,
        )
        self.log_event(event)

    def log_session_revoked(
        self,
        user_id: str,
        session_id: str,
        reason: str,
        revoked_by: Optional[str] = None,
        additional_data: Optional[dict] = None,
    ):
        """Log session revocation."""
        event = AuditEvent(
            event_type=AuditEventType.SESSION_REVOKED,
            severity=AuditSeverity.MEDIUM,
            user_id=user_id,
            session_id=session_id,
            success=True,
            additional_data={
                "reason": reason,
                "revoked_by": revoked_by,
                **(additional_data or {}),
            },
        )
        self.log_event(event)


# Global audit logger instance
_audit_logger: Optional[SecurityAuditLogger] = None


def get_audit_logger() -> SecurityAuditLogger:
    """Get the global security audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger
