"""
Secure link generation service for report delivery.

This module provides cryptographically signed URLs with expiration dates
for securely accessing purchased audit reports.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Union
from urllib.parse import urlencode

import jwt
from pydantic import BaseModel, Field

from leadfactory.config import get_env


class SecureLinkConfig(BaseModel):
    """Configuration for secure link generation."""

    secret_key: str = Field(..., description="Secret key for signing tokens")
    default_expiry_days: int = Field(
        default=7, description="Default link expiry in days"
    )
    max_expiry_days: int = Field(
        default=30, description="Maximum allowed expiry in days"
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")


class SecureLinkData(BaseModel):
    """Data structure for secure link payload."""

    report_id: str = Field(..., description="Unique report identifier")
    user_id: str = Field(..., description="User identifier")
    purchase_id: str = Field(..., description="Purchase transaction identifier")
    expires_at: int = Field(..., description="Expiration timestamp")
    access_type: str = Field(default="view", description="Type of access granted")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class SecureLinkGenerator:
    """Service for generating and validating secure report access links."""

    def __init__(self, config: Optional[SecureLinkConfig] = None):
        """Initialize the secure link generator."""
        self.config = config or self._get_default_config()

    def _get_default_config(self) -> SecureLinkConfig:
        """Get default configuration from settings."""
        secret_key = get_env("SECRET_KEY", "dev-secret-key-change-in-production")
        return SecureLinkConfig(
            secret_key=secret_key, default_expiry_days=7, max_expiry_days=30
        )

    def generate_secure_link(
        self,
        report_id: str,
        user_id: str,
        purchase_id: str,
        base_url: str,
        expiry_days: Optional[int] = None,
        access_type: str = "view",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Generate a secure link for report access.

        Args:
            report_id: Unique identifier for the report
            user_id: User identifier
            purchase_id: Purchase transaction identifier
            base_url: Base URL for the report access endpoint
            expiry_days: Number of days until link expires (default: 7)
            access_type: Type of access granted (view, download, etc.)
            metadata: Additional metadata to include in the token

        Returns:
            Secure URL with signed token

        Raises:
            ValueError: If expiry_days exceeds maximum allowed
        """
        expiry_days = expiry_days or self.config.default_expiry_days

        if expiry_days > self.config.max_expiry_days:
            raise ValueError(f"Expiry days cannot exceed {self.config.max_expiry_days}")

        # Calculate expiration timestamp
        expires_at = int((datetime.utcnow() + timedelta(days=expiry_days)).timestamp())

        # Create link data
        link_data = SecureLinkData(
            report_id=report_id,
            user_id=user_id,
            purchase_id=purchase_id,
            expires_at=expires_at,
            access_type=access_type,
            metadata=metadata or {},
        )

        # Generate JWT token
        payload = link_data.model_dump()
        payload["exp"] = expires_at  # Add standard JWT expiration claim
        token = jwt.encode(
            payload, self.config.secret_key, algorithm=self.config.algorithm
        )

        # Construct secure URL
        params = {"token": token}
        query_string = urlencode(params)

        return f"{base_url.rstrip('/')}?{query_string}"

    def validate_secure_link(self, token: str) -> SecureLinkData:
        """
        Validate a secure link token.

        Args:
            token: JWT token from the secure link

        Returns:
            Validated link data

        Raises:
            jwt.ExpiredSignatureError: If token has expired
            jwt.InvalidTokenError: If token is invalid
            ValueError: If token data is invalid
        """
        try:
            # Decode and validate JWT
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                options={"verify_exp": True},
            )

            # Parse link data
            link_data = SecureLinkData(**payload)

            # Additional expiration check
            if link_data.expires_at < int(time.time()):
                raise jwt.ExpiredSignatureError("Token has expired")

            return link_data

        except jwt.ExpiredSignatureError:
            raise
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise ValueError(f"Invalid token data: {str(e)}")

    def generate_download_link(
        self,
        report_id: str,
        user_id: str,
        purchase_id: str,
        base_url: str,
        expiry_hours: int = 24,
    ) -> str:
        """
        Generate a short-lived download link for immediate use.

        Args:
            report_id: Unique identifier for the report
            user_id: User identifier
            purchase_id: Purchase transaction identifier
            base_url: Base URL for the download endpoint
            expiry_hours: Number of hours until link expires

        Returns:
            Secure download URL
        """
        expiry_days = expiry_hours / 24.0

        return self.generate_secure_link(
            report_id=report_id,
            user_id=user_id,
            purchase_id=purchase_id,
            base_url=base_url,
            expiry_days=expiry_days,
            access_type="download",
            metadata={"download_only": True},
        )

    def create_tracking_link(
        self, original_url: str, user_id: str, campaign_id: str, link_type: str = "cta"
    ) -> str:
        """
        Create a tracking link for analytics.

        Args:
            original_url: The destination URL
            user_id: User identifier for tracking
            campaign_id: Campaign or email identifier
            link_type: Type of link (cta, report, etc.)

        Returns:
            Tracking URL with analytics parameters
        """
        tracking_params = {
            "utm_source": "email",
            "utm_medium": "report_delivery",
            "utm_campaign": campaign_id,
            "utm_content": link_type,
            "user_id": user_id,
            "timestamp": int(time.time()),
        }

        # Add tracking signature to prevent tampering
        tracking_data = json.dumps(tracking_params, sort_keys=True)
        signature = hmac.new(
            self.config.secret_key.encode(), tracking_data.encode(), hashlib.sha256
        ).hexdigest()[:16]

        tracking_params["sig"] = signature

        separator = "&" if "?" in original_url else "?"
        query_string = urlencode(tracking_params)

        return f"{original_url}{separator}{query_string}"


def get_secure_link_generator() -> SecureLinkGenerator:
    """Get a configured secure link generator instance."""
    return SecureLinkGenerator()
