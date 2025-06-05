"""
Access control system for PDF report operations.

This module provides role-based access control (RBAC) for PDF report
generation, access, and management operations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for access control."""

    ADMIN = "admin"
    CUSTOMER = "customer"
    SUPPORT = "support"
    VIEWER = "viewer"


class PDFOperation(Enum):
    """PDF operations that can be controlled."""

    GENERATE = "generate"
    VIEW = "view"
    DOWNLOAD = "download"
    DELETE = "delete"
    SHARE = "share"
    REVOKE_ACCESS = "revoke_access"


@dataclass
class AccessPermission:
    """Represents an access permission for a specific operation."""

    operation: PDFOperation
    resource_type: str = "pdf_report"
    conditions: Optional[dict] = None

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = {}


@dataclass
class UserContext:
    """User context for access control decisions."""

    user_id: str
    role: UserRole
    permissions: list[AccessPermission]
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


class AccessControlService:
    """Service for managing role-based access control for PDF operations."""

    def __init__(self):
        """Initialize the access control service."""
        self._role_permissions = self._initialize_role_permissions()
        self._user_sessions: dict[str, UserContext] = {}
        self._revoked_tokens: set[str] = set()

        logger.info("Access control service initialized")

    def _initialize_role_permissions(self) -> dict[UserRole, list[AccessPermission]]:
        """Initialize default role-based permissions."""
        return {
            UserRole.ADMIN: [
                AccessPermission(PDFOperation.GENERATE),
                AccessPermission(PDFOperation.VIEW),
                AccessPermission(PDFOperation.DOWNLOAD),
                AccessPermission(PDFOperation.DELETE),
                AccessPermission(PDFOperation.SHARE),
                AccessPermission(PDFOperation.REVOKE_ACCESS),
            ],
            UserRole.CUSTOMER: [
                AccessPermission(PDFOperation.VIEW, conditions={"owner_only": True}),
                AccessPermission(
                    PDFOperation.DOWNLOAD, conditions={"owner_only": True}
                ),
                AccessPermission(
                    PDFOperation.SHARE, conditions={"owner_only": True, "max_shares": 5}
                ),
            ],
            UserRole.SUPPORT: [
                AccessPermission(PDFOperation.VIEW),
                AccessPermission(PDFOperation.DOWNLOAD),
                AccessPermission(PDFOperation.SHARE, conditions={"max_shares": 3}),
            ],
            UserRole.VIEWER: [
                AccessPermission(PDFOperation.VIEW, conditions={"read_only": True}),
            ],
        }

    def check_permission(
        self,
        user_context: UserContext,
        operation: PDFOperation,
        resource_id: str,
        resource_owner_id: Optional[str] = None,
        additional_context: Optional[dict] = None,
    ) -> bool:
        """
        Check if a user has permission to perform an operation.

        Args:
            user_context: User context with role and permissions
            operation: The operation to check
            resource_id: ID of the resource being accessed
            resource_owner_id: ID of the resource owner
            additional_context: Additional context for permission evaluation

        Returns:
            True if permission is granted, False otherwise
        """
        try:
            # Check if user session is valid
            if not self._is_session_valid(user_context):
                logger.warning(f"Invalid session for user {user_context.user_id}")
                return False

            # Get permissions for user's role
            role_permissions = self._role_permissions.get(user_context.role, [])

            # Check if operation is allowed for this role
            allowed_permission = None
            for permission in role_permissions:
                if permission.operation == operation:
                    allowed_permission = permission
                    break

            if not allowed_permission:
                logger.warning(
                    f"Operation {operation.value} not allowed for role {user_context.role.value}"
                )
                return False

            # Check conditions
            if not self._check_conditions(
                allowed_permission.conditions,
                user_context,
                resource_id,
                resource_owner_id,
                additional_context or {},
            ):
                logger.warning(
                    f"Conditions not met for operation {operation.value} by user {user_context.user_id}"
                )
                return False

            logger.info(
                f"Permission granted: user {user_context.user_id} can {operation.value} resource {resource_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False

    def _is_session_valid(self, user_context: UserContext) -> bool:
        """Check if user session is valid."""
        if not user_context.session_id:
            return True  # No session validation required

        stored_context = self._user_sessions.get(user_context.session_id)
        if not stored_context:
            return False

        return stored_context.user_id == user_context.user_id

    def _check_conditions(
        self,
        conditions: dict,
        user_context: UserContext,
        resource_id: str,
        resource_owner_id: Optional[str],
        additional_context: dict,
    ) -> bool:
        """Check if permission conditions are met."""
        if not conditions:
            return True

        # Check owner-only condition
        if conditions.get("owner_only", False):
            if not resource_owner_id or resource_owner_id != user_context.user_id:
                return False

        # Check max shares condition
        max_shares = conditions.get("max_shares")
        if max_shares is not None:
            current_shares = additional_context.get("current_shares", 0)
            if current_shares >= max_shares:
                return False

        # Check read-only condition
        if conditions.get("read_only", False):
            # Read-only users can only view, not download or share
            pass

        return True

    def create_user_session(self, user_context: UserContext) -> str:
        """Create a new user session."""
        if not user_context.session_id:
            user_context.session_id = (
                f"session_{user_context.user_id}_{int(datetime.utcnow().timestamp())}"
            )

        self._user_sessions[user_context.session_id] = user_context
        logger.info(
            f"Created session {user_context.session_id} for user {user_context.user_id}"
        )

        return user_context.session_id

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a user session."""
        if session_id in self._user_sessions:
            del self._user_sessions[session_id]
            logger.info(f"Revoked session {session_id}")
            return True

        return False

    def revoke_token(self, token: str) -> bool:
        """Revoke a specific access token."""
        self._revoked_tokens.add(token)
        logger.info(f"Revoked token: {token[:10]}...")
        return True

    def is_token_revoked(self, token: str) -> bool:
        """Check if a token has been revoked."""
        return token in self._revoked_tokens

    def get_user_permissions(self, role: UserRole) -> list[AccessPermission]:
        """Get permissions for a specific role."""
        return self._role_permissions.get(role, [])

    def validate_resource_access(
        self, user_id: str, resource_id: str, operation: PDFOperation, token: str
    ) -> bool:
        """
        Validate that a user can access a specific resource.

        Args:
            user_id: ID of the user requesting access
            resource_id: ID of the resource being accessed
            operation: The operation being performed
            token: Access token for the request

        Returns:
            True if access is valid, False otherwise
        """
        # Check if token is revoked
        if self.is_token_revoked(token):
            logger.warning(f"Attempted access with revoked token by user {user_id}")
            return False

        # Additional validation logic can be added here
        # For now, we'll assume the token validation is handled elsewhere

        return True


# Global access control service instance
_access_control_service: Optional[AccessControlService] = None


def get_access_control_service() -> AccessControlService:
    """Get the global access control service instance."""
    global _access_control_service
    if _access_control_service is None:
        _access_control_service = AccessControlService()
    return _access_control_service
