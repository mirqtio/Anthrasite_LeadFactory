"""
Tests for secure link generation and validation.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest

from leadfactory.email.secure_links import (
    SecureLinkConfig,
    SecureLinkData,
    SecureLinkGenerator,
)


class TestSecureLinkGenerator:
    """Test suite for SecureLinkGenerator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = SecureLinkConfig(
            secret_key="test-secret-key-123", default_expiry_days=7, max_expiry_days=30
        )
        self.generator = SecureLinkGenerator(self.config)

    def test_generate_secure_link_basic(self):
        """Test basic secure link generation."""
        link = self.generator.generate_secure_link(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            base_url="https://example.com/reports",
        )

        assert "https://example.com/reports?" in link
        assert "token=" in link

        # Extract and validate token
        token = link.split("token=")[1]
        link_data = self.generator.validate_secure_link(token)

        assert link_data.report_id == "report_123"
        assert link_data.user_id == "user_456"
        assert link_data.purchase_id == "purchase_789"
        assert link_data.access_type == "view"

    def test_generate_secure_link_with_custom_expiry(self):
        """Test secure link generation with custom expiry."""
        link = self.generator.generate_secure_link(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            base_url="https://example.com/reports",
            expiry_days=3,
        )

        token = link.split("token=")[1]
        link_data = self.generator.validate_secure_link(token)

        # Check expiry is approximately 3 days from now
        expected_expiry = int(time.time() + 3 * 24 * 60 * 60)  # 3 days from now
        assert abs(link_data.expires_at - expected_expiry) < 60  # Within 1 minute

    def test_generate_secure_link_exceeds_max_expiry(self):
        """Test that exceeding max expiry raises error."""
        with pytest.raises(ValueError, match="Expiry days cannot exceed"):
            self.generator.generate_secure_link(
                report_id="report_123",
                user_id="user_456",
                purchase_id="purchase_789",
                base_url="https://example.com/reports",
                expiry_days=50,  # Exceeds max of 30
            )

    def test_generate_download_link(self):
        """Test download link generation."""
        link = self.generator.generate_download_link(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            base_url="https://example.com/download",
            expiry_hours=12,
        )

        token = link.split("token=")[1]
        link_data = self.generator.validate_secure_link(token)

        assert link_data.access_type == "download"
        assert link_data.metadata.get("download_only") is True

    def test_validate_secure_link_expired(self):
        """Test validation of expired link."""
        # Create link with past expiry
        past_time = int(time.time() - 3600)  # 1 hour ago

        link_data = SecureLinkData(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            expires_at=past_time,
        )

        token = jwt.encode(
            {**link_data.model_dump(), "exp": past_time},
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            self.generator.validate_secure_link(token)

    def test_validate_secure_link_invalid_token(self):
        """Test validation of invalid token."""
        with pytest.raises(jwt.InvalidTokenError):
            self.generator.validate_secure_link("invalid.token.here")

    def test_validate_secure_link_wrong_secret(self):
        """Test validation with wrong secret key."""
        # Generate token with different secret
        wrong_generator = SecureLinkGenerator(
            SecureLinkConfig(secret_key="wrong-secret")
        )

        link = wrong_generator.generate_secure_link(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            base_url="https://example.com/reports",
        )

        token = link.split("token=")[1]

        with pytest.raises(jwt.InvalidTokenError):
            self.generator.validate_secure_link(token)

    def test_create_tracking_link(self):
        """Test tracking link creation."""
        link = self.generator.create_tracking_link(
            original_url="https://example.com/agency",
            user_id="user_456",
            campaign_id="campaign_123",
            link_type="cta",
        )

        assert "utm_source=email" in link
        assert "utm_medium=report_delivery" in link
        assert "utm_campaign=campaign_123" in link
        assert "utm_content=cta" in link
        assert "user_id=user_456" in link
        assert "sig=" in link  # Signature present

    def test_create_tracking_link_with_existing_params(self):
        """Test tracking link creation with existing URL parameters."""
        link = self.generator.create_tracking_link(
            original_url="https://example.com/agency?existing=param",
            user_id="user_456",
            campaign_id="campaign_123",
        )

        assert "existing=param" in link
        assert "utm_source=email" in link
        # Should use & separator since ? already exists
        assert "&utm_source=" in link

    @patch("leadfactory.email.secure_links.get_env")
    def test_default_config_from_settings(self, mock_get_env):
        """Test default configuration from settings."""
        mock_get_env.return_value = "settings-secret"

        generator = SecureLinkGenerator()

        assert generator.config.secret_key == "settings-secret"
        assert generator.config.default_expiry_days == 7
        assert generator.config.max_expiry_days == 30

    def test_secure_link_data_validation(self):
        """Test SecureLinkData validation."""
        # Valid data
        data = SecureLinkData(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            expires_at=int(time.time()) + 3600,
        )
        assert data.access_type == "view"  # Default value
        assert data.metadata == {}  # Default value

        # Test with custom values
        data = SecureLinkData(
            report_id="report_123",
            user_id="user_456",
            purchase_id="purchase_789",
            expires_at=int(time.time()) + 3600,
            access_type="download",
            metadata={"custom": "value"},
        )
        assert data.access_type == "download"
        assert data.metadata["custom"] == "value"

    def test_secure_link_config_validation(self):
        """Test SecureLinkConfig validation."""
        # Valid config
        config = SecureLinkConfig(secret_key="test-key")
        assert config.default_expiry_days == 7
        assert config.max_expiry_days == 30
        assert config.algorithm == "HS256"

        # Custom config
        config = SecureLinkConfig(
            secret_key="test-key",
            default_expiry_days=14,
            max_expiry_days=60,
            algorithm="HS512",
        )
        assert config.default_expiry_days == 14
        assert config.max_expiry_days == 60
        assert config.algorithm == "HS512"

    def test_get_secure_link_generator_function(self):
        """Test the factory function."""
        from leadfactory.email.secure_links import get_secure_link_generator

        with patch("leadfactory.email.secure_links.get_env") as mock_get_env:
            mock_get_env.return_value = "factory-secret"

            generator = get_secure_link_generator()

            assert isinstance(generator, SecureLinkGenerator)
            assert generator.config.secret_key == "factory-secret"
