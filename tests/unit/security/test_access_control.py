"""
Unit tests for the access control system.

Tests role-based access control, permissions, session management,
and token revocation functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.security.access_control import (
    AccessControlService,
    UserRole,
    PDFOperation,
    UserContext,
    AccessPermission,
    get_access_control_service
)


class TestAccessControlService:
    """Test cases for AccessControlService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.access_control = AccessControlService()

        # Create test user contexts
        self.admin_user = UserContext(
            user_id="admin_123",
            role=UserRole.ADMIN,
            permissions=[],
            session_id="session_admin",
            ip_address="192.168.1.100"
        )

        self.customer_user = UserContext(
            user_id="customer_456",
            role=UserRole.CUSTOMER,
            permissions=[],
            session_id="session_customer",
            ip_address="192.168.1.101"
        )

        self.support_user = UserContext(
            user_id="support_789",
            role=UserRole.SUPPORT,
            permissions=[],
            session_id="session_support",
            ip_address="192.168.1.102"
        )

    def test_admin_has_all_permissions(self):
        """Test that admin users have access to all operations."""
        for operation in PDFOperation:
            assert self.access_control.check_permission(
                user_context=self.admin_user,
                operation=operation,
                resource_id="test_resource"
            )

    def test_customer_has_basic_permissions(self):
        """Test that customer users have access to basic operations."""
        # Customers should be able to view and download
        assert self.access_control.check_permission(
            user_context=self.customer_user,
            operation=PDFOperation.VIEW,
            resource_id="test_resource",
            resource_owner_id="customer_456"  # Own resource
        )

        assert self.access_control.check_permission(
            user_context=self.customer_user,
            operation=PDFOperation.DOWNLOAD,
            resource_id="test_resource",
            resource_owner_id="customer_456"  # Own resource
        )

    def test_customer_cannot_access_others_resources(self):
        """Test that customers cannot access resources they don't own."""
        assert not self.access_control.check_permission(
            user_context=self.customer_user,
            operation=PDFOperation.VIEW,
            resource_id="test_resource",
            resource_owner_id="other_user"  # Not their resource
        )

    def test_customer_cannot_delete_or_revoke(self):
        """Test that customers cannot delete or revoke access."""
        assert not self.access_control.check_permission(
            user_context=self.customer_user,
            operation=PDFOperation.DELETE,
            resource_id="test_resource",
            resource_owner_id="customer_456"
        )

        assert not self.access_control.check_permission(
            user_context=self.customer_user,
            operation=PDFOperation.REVOKE_ACCESS,
            resource_id="test_resource",
            resource_owner_id="customer_456"
        )

    def test_support_has_view_permissions(self):
        """Test that support users can view resources."""
        assert self.access_control.check_permission(
            user_context=self.support_user,
            operation=PDFOperation.VIEW,
            resource_id="test_resource",
            resource_owner_id="any_user"
        )

    def test_support_cannot_delete(self):
        """Test that support users cannot delete resources."""
        assert not self.access_control.check_permission(
            user_context=self.support_user,
            operation=PDFOperation.DELETE,
            resource_id="test_resource"
        )

    def test_viewer_has_limited_permissions(self):
        """Test that viewer users have very limited permissions."""
        viewer_user = UserContext(
            user_id="viewer_999",
            role=UserRole.VIEWER,
            permissions=[],
            session_id="session_viewer",
            ip_address="192.168.1.103"
        )

        # Viewers can only view
        assert self.access_control.check_permission(
            viewer_user,
            PDFOperation.VIEW,
            "test_resource"
        )

        # Viewers cannot download, generate, etc.
        assert not self.access_control.check_permission(
            viewer_user,
            PDFOperation.DOWNLOAD,
            "test_resource"
        )

        assert not self.access_control.check_permission(
            viewer_user,
            PDFOperation.GENERATE,
            "test_resource"
        )

    def test_session_management(self):
        """Test session creation and validation."""
        session_id = self.access_control.create_session(
            user_id="test_user",
            role=UserRole.CUSTOMER,
            ip_address="192.168.1.200"
        )

        assert session_id is not None
        assert self.access_control.validate_session(session_id)

    def test_session_expiry(self):
        """Test that sessions expire after the configured time."""
        # Create a session
        session_id = self.access_control.create_session(
            user_id="test_user",
            role=UserRole.CUSTOMER,
            ip_address="192.168.1.200"
        )

        # Manually expire the session
        if session_id in self.access_control._active_sessions:
            self.access_control._active_sessions[session_id]["expires_at"] = (
                datetime.utcnow() - timedelta(minutes=1)
            )

        assert not self.access_control.validate_session(session_id)

    def test_session_revocation(self):
        """Test session revocation."""
        session_id = self.access_control.create_session(
            user_id="test_user",
            role=UserRole.CUSTOMER,
            ip_address="192.168.1.200"
        )

        assert self.access_control.validate_session(session_id)

        self.access_control.revoke_session(session_id)

        assert not self.access_control.validate_session(session_id)

    def test_token_revocation(self):
        """Test token revocation functionality."""
        token = "test_token_12345"

        # Token should not be revoked initially
        assert not self.access_control.is_token_revoked(token)

        # Revoke the token
        self.access_control.revoke_token(token)

        # Token should now be revoked
        assert self.access_control.is_token_revoked(token)

    def test_user_revocation(self):
        """Test user revocation functionality."""
        user_id = "test_user_revoke"

        # User should not be revoked initially
        assert not self.access_control.is_user_revoked(user_id)

        # Revoke the user
        self.access_control.revoke_user(user_id)

        # User should now be revoked
        assert self.access_control.is_user_revoked(user_id)

    def test_revoked_user_has_no_permissions(self):
        """Test that revoked users have no permissions."""
        # Create user context
        revoked_user = UserContext(
            user_id="revoked_user",
            role=UserRole.CUSTOMER,
            permissions=[],
            session_id="session_revoked",
            ip_address="192.168.1.104"
        )

        # Revoke the user
        self.access_control.revoke_user("revoked_user")

        # User should have no permissions
        assert not self.access_control.check_permission(
            revoked_user,
            PDFOperation.VIEW,
            "test_resource",
            resource_owner_id="revoked_user"
        )

    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        # Create multiple sessions
        session1 = self.access_control.create_session("user1", UserRole.CUSTOMER, "192.168.1.1")
        session2 = self.access_control.create_session("user2", UserRole.CUSTOMER, "192.168.1.2")

        # Manually expire one session
        if session1 in self.access_control._active_sessions:
            self.access_control._active_sessions[session1]["expires_at"] = (
                datetime.utcnow() - timedelta(minutes=1)
            )

        # Cleanup expired sessions
        self.access_control.cleanup_expired_sessions()

        # Expired session should be gone, active session should remain
        assert not self.access_control.validate_session(session1)
        assert self.access_control.validate_session(session2)

    def test_get_user_permissions(self):
        """Test getting user permissions."""
        permissions = self.access_control.get_user_permissions(UserRole.ADMIN)

        # Admin should have all permissions
        assert len(permissions) > 0
        assert any(p.operation == PDFOperation.DELETE for p in permissions)
        assert any(p.operation == PDFOperation.REVOKE_ACCESS for p in permissions)

    def test_permission_conditions(self):
        """Test permission conditions like owner-only access."""
        # Test owner-only condition
        assert self.access_control.check_permission(
            self.customer_user,
            PDFOperation.VIEW,
            "resource_123",
            resource_owner_id="customer_456"  # Same as user_id
        )

        assert not self.access_control.check_permission(
            self.customer_user,
            PDFOperation.VIEW,
            "resource_123",
            resource_owner_id="different_user"  # Different from user_id
        )


class TestAccessControlServiceSingleton:
    """Test the singleton pattern for access control service."""

    def test_singleton_instance(self):
        """Test that get_access_control_service returns the same instance."""
        service1 = get_access_control_service()
        service2 = get_access_control_service()

        assert service1 is service2
        assert isinstance(service1, AccessControlService)


class TestUserContext:
    """Test UserContext dataclass."""

    def test_user_context_creation(self):
        """Test creating a UserContext instance."""
        context = UserContext(
            user_id="test_user",
            role=UserRole.CUSTOMER,
            permissions=[],
            session_id="test_session",
            ip_address="192.168.1.1",
            user_agent="Test Agent"
        )

        assert context.user_id == "test_user"
        assert context.role == UserRole.CUSTOMER
        assert context.session_id == "test_session"
        assert context.ip_address == "192.168.1.1"
        assert context.user_agent == "Test Agent"


class TestAccessPermission:
    """Test AccessPermission dataclass."""

    def test_access_permission_creation(self):
        """Test creating an AccessPermission instance."""
        permission = AccessPermission(
            operation=PDFOperation.VIEW,
            conditions={"owner_only": True}
        )

        assert permission.operation == PDFOperation.VIEW
        assert permission.conditions["owner_only"] is True
