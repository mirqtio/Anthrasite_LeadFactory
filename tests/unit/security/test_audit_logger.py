"""
Unit tests for the security audit logger.

Tests audit event logging, severity levels, structured logging,
and audit trail functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, call
import json

from leadfactory.security.audit_logger import (
    SecurityAuditLogger,
    AuditEventType,
    AuditSeverity,
    AuditEvent,
    get_audit_logger
)


class TestAuditEvent:
    """Test cases for AuditEvent dataclass."""

    def test_audit_event_creation(self):
        """Test creating an AuditEvent instance."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            user_id="test_user",
            resource_id="test_resource",
            operation="view",
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            additional_data={"key": "value"}
        )

        assert event.event_type == AuditEventType.ACCESS_GRANTED
        assert event.severity == AuditSeverity.INFO
        assert event.user_id == "test_user"
        assert event.resource_id == "test_resource"
        assert event.operation == "view"
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "Test Agent"
        assert event.additional_data["key"] == "value"

    def test_audit_event_to_dict(self):
        """Test converting AuditEvent to dictionary."""
        timestamp = datetime.utcnow()
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.WARNING,
            user_id="test_user",
            resource_id="test_resource",
            operation="delete",
            timestamp=timestamp,
            reason="Insufficient permissions"
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "ACCESS_DENIED"
        assert event_dict["severity"] == "WARNING"
        assert event_dict["user_id"] == "test_user"
        assert event_dict["resource_id"] == "test_resource"
        assert event_dict["operation"] == "delete"
        assert event_dict["timestamp"] == timestamp.isoformat()
        assert event_dict["reason"] == "Insufficient permissions"


class TestSecurityAuditLogger:
    """Test cases for SecurityAuditLogger."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = SecurityAuditLogger()

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_access_granted(self, mock_logger):
        """Test logging access granted events."""
        self.logger.log_access_granted(
            user_id="test_user",
            resource_id="test_resource",
            operation="view",
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            additional_data={"purchase_id": "12345"}
        )

        # Verify logger was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.info.call_args[0][0]
        assert "ACCESS_GRANTED" in logged_call
        assert "test_user" in logged_call
        assert "test_resource" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_access_denied(self, mock_logger):
        """Test logging access denied events."""
        self.logger.log_access_denied(
            user_id="test_user",
            resource_id="test_resource",
            operation="delete",
            reason="Insufficient permissions",
            ip_address="192.168.1.1"
        )

        # Verify logger was called
        mock_logger.warning.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.warning.call_args[0][0]
        assert "ACCESS_DENIED" in logged_call
        assert "test_user" in logged_call
        assert "Insufficient permissions" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_token_generated(self, mock_logger):
        """Test logging token generation events."""
        self.logger.log_token_generated(
            user_id="test_user",
            token_id="token_12345",
            expires_at=datetime.utcnow(),
            token_type="access",
            additional_data={"resource_id": "test_resource"}
        )

        # Verify logger was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.info.call_args[0][0]
        assert "TOKEN_GENERATED" in logged_call
        assert "token_12345" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_token_revoked(self, mock_logger):
        """Test logging token revocation events."""
        self.logger.log_token_revoked(
            user_id="admin_user",
            token_id="token_67890",
            reason="Security breach",
            revoked_by="admin_user"
        )

        # Verify logger was called
        mock_logger.warning.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.warning.call_args[0][0]
        assert "TOKEN_REVOKED" in logged_call
        assert "token_67890" in logged_call
        assert "Security breach" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_session_created(self, mock_logger):
        """Test logging session creation events."""
        self.logger.log_session_created(
            user_id="test_user",
            session_id="session_12345",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )

        # Verify logger was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.info.call_args[0][0]
        assert "SESSION_CREATED" in logged_call
        assert "session_12345" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_session_expired(self, mock_logger):
        """Test logging session expiration events."""
        self.logger.log_session_expired(
            user_id="test_user",
            session_id="session_67890",
            reason="Timeout"
        )

        # Verify logger was called
        mock_logger.info.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.info.call_args[0][0]
        assert "SESSION_EXPIRED" in logged_call
        assert "session_67890" in logged_call
        assert "Timeout" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_rate_limit_violation(self, mock_logger):
        """Test logging rate limit violation events."""
        self.logger.log_rate_limit_violation(
            user_id="test_user",
            operation="pdf_generation",
            limit_type="per_minute",
            limit_exceeded=5,
            ip_address="192.168.1.1"
        )

        # Verify logger was called
        mock_logger.warning.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.warning.call_args[0][0]
        assert "RATE_LIMIT_VIOLATION" in logged_call
        assert "pdf_generation" in logged_call
        assert "per_minute" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_security_violation(self, mock_logger):
        """Test logging security violation events."""
        self.logger.log_security_violation(
            user_id="suspicious_user",
            violation_type="invalid_token",
            description="Attempted access with invalid token",
            ip_address="192.168.1.100",
            user_agent="Suspicious Agent"
        )

        # Verify logger was called
        mock_logger.error.assert_called_once()

        # Check the logged message contains expected information
        logged_call = mock_logger.error.call_args[0][0]
        assert "SECURITY_VIOLATION" in logged_call
        assert "invalid_token" in logged_call
        assert "Attempted access with invalid token" in logged_call

    @patch('leadfactory.security.audit_logger.logger')
    def test_log_audit_event_generic(self, mock_logger):
        """Test logging generic audit events."""
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            user_id="test_user",
            resource_id="test_resource",
            operation="view",
            timestamp=datetime.utcnow()
        )

        self.logger.log_audit_event(event)

        # Verify logger was called with appropriate severity
        mock_logger.info.assert_called_once()

    @patch('leadfactory.security.audit_logger.logger')
    def test_different_severity_levels(self, mock_logger):
        """Test that different severity levels use appropriate log methods."""
        # Test INFO level
        info_event = AuditEvent(
            event_type=AuditEventType.SESSION_CREATED,
            severity=AuditSeverity.INFO,
            user_id="test_user",
            timestamp=datetime.utcnow()
        )
        self.logger.log_audit_event(info_event)
        mock_logger.info.assert_called()

        # Test WARNING level
        warning_event = AuditEvent(
            event_type=AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.WARNING,
            user_id="test_user",
            timestamp=datetime.utcnow()
        )
        self.logger.log_audit_event(warning_event)
        mock_logger.warning.assert_called()

        # Test ERROR level
        error_event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.ERROR,
            user_id="test_user",
            timestamp=datetime.utcnow()
        )
        self.logger.log_audit_event(error_event)
        mock_logger.error.assert_called()

        # Test CRITICAL level
        critical_event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            user_id="test_user",
            timestamp=datetime.utcnow()
        )
        self.logger.log_audit_event(critical_event)
        mock_logger.critical.assert_called()

    def test_get_audit_trail(self):
        """Test getting audit trail for a user."""
        user_id = "test_user"

        # Add some events to the audit trail
        self.logger.audit_events.extend([
            AuditEvent(
                event_type=AuditEventType.ACCESS_GRANTED,
                severity=AuditSeverity.INFO,
                user_id=user_id,
                resource_id="resource1",
                operation="view",
                timestamp=datetime.utcnow()
            ),
            AuditEvent(
                event_type=AuditEventType.ACCESS_DENIED,
                severity=AuditSeverity.WARNING,
                user_id=user_id,
                resource_id="resource2",
                operation="delete",
                timestamp=datetime.utcnow()
            ),
            AuditEvent(
                event_type=AuditEventType.ACCESS_GRANTED,
                severity=AuditSeverity.INFO,
                user_id="other_user",
                resource_id="resource3",
                operation="view",
                timestamp=datetime.utcnow()
            )
        ])

        # Get audit trail for specific user
        trail = self.logger.get_audit_trail(user_id)

        # Should only return events for the specified user
        assert len(trail) == 2
        assert all(event["user_id"] == user_id for event in trail)

    def test_get_audit_trail_with_limit(self):
        """Test getting audit trail with limit."""
        user_id = "test_user"

        # Add multiple events
        for i in range(10):
            self.logger.audit_events.append(
                AuditEvent(
                    event_type=AuditEventType.ACCESS_GRANTED,
                    severity=AuditSeverity.INFO,
                    user_id=user_id,
                    resource_id=f"resource{i}",
                    operation="view",
                    timestamp=datetime.utcnow()
                )
            )

        # Get audit trail with limit
        trail = self.logger.get_audit_trail(user_id, limit=5)

        # Should return only the specified number of events
        assert len(trail) == 5

    def test_get_security_summary(self):
        """Test getting security summary."""
        # Add various types of events
        self.logger.audit_events.extend([
            AuditEvent(AuditEventType.ACCESS_GRANTED, AuditSeverity.INFO, "user1", timestamp=datetime.utcnow()),
            AuditEvent(AuditEventType.ACCESS_DENIED, AuditSeverity.WARNING, "user1", timestamp=datetime.utcnow()),
            AuditEvent(AuditEventType.SECURITY_VIOLATION, AuditSeverity.ERROR, "user2", timestamp=datetime.utcnow()),
            AuditEvent(AuditEventType.RATE_LIMIT_VIOLATION, AuditSeverity.WARNING, "user3", timestamp=datetime.utcnow())
        ])

        summary = self.logger.get_security_summary()

        assert summary["total_events"] == 4
        assert summary["access_granted"] == 1
        assert summary["access_denied"] == 1
        assert summary["security_violations"] == 1
        assert summary["rate_limit_violations"] == 1

    def test_cleanup_old_events(self):
        """Test cleanup of old audit events."""
        # Add old and new events
        old_event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            user_id="test_user",
            timestamp=datetime.utcnow() - timedelta(days=100)  # Old event
        )

        new_event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            user_id="test_user",
            timestamp=datetime.utcnow()  # Recent event
        )

        self.logger.audit_events.extend([old_event, new_event])

        # Cleanup events older than 90 days
        self.logger.cleanup_old_events(days=90)

        # Should only have the new event
        assert len(self.logger.audit_events) == 1
        assert self.logger.audit_events[0] == new_event


class TestSecurityAuditLoggerSingleton:
    """Test the singleton pattern for security audit logger."""

    def test_singleton_instance(self):
        """Test that get_audit_logger returns the same instance."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2
        assert isinstance(logger1, SecurityAuditLogger)


class TestAuditEventTypes:
    """Test audit event types and severity levels."""

    def test_audit_event_types_exist(self):
        """Test that all required audit event types exist."""
        required_types = [
            "ACCESS_GRANTED",
            "ACCESS_DENIED",
            "TOKEN_GENERATED",
            "TOKEN_REVOKED",
            "SESSION_CREATED",
            "SESSION_EXPIRED",
            "RATE_LIMIT_VIOLATION",
            "SECURITY_VIOLATION"
        ]

        for event_type in required_types:
            assert hasattr(AuditEventType, event_type)

    def test_audit_severity_levels_exist(self):
        """Test that all required severity levels exist."""
        required_levels = ["INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in required_levels:
            assert hasattr(AuditSeverity, level)
