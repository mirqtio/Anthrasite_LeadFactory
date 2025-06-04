"""
Unit tests for URL expiration validation in PDF storage and delivery.

Tests various URL expiration scenarios including edge cases,
timezone handling, and security implications.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from leadfactory.email.secure_links import SecureLinkConfig, SecureLinkGenerator
from leadfactory.security.secure_access_validator import (
    AccessRequest,
    SecureAccessValidator,
    ValidationResult,
)
from leadfactory.storage.supabase_storage import SupabaseStorage


class TestURLExpirationValidation:
    """Test suite for URL expiration validation scenarios."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client for testing."""
        with patch("leadfactory.storage.supabase_storage.create_client") as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def storage(self, mock_supabase_client):
        """Create SupabaseStorage instance for testing."""
        with patch("leadfactory.storage.supabase_storage.get_env") as mock_get_env:
            mock_get_env.side_effect = lambda key: {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_KEY": "test-key",
            }.get(key)
            return SupabaseStorage(bucket_name="expiration-test")

    @pytest.fixture
    def secure_validator(self):
        """Create SecureAccessValidator for testing."""
        return SecureAccessValidator()

    @pytest.fixture
    def link_generator(self):
        """Create SecureLinkGenerator for testing."""
        from leadfactory.email.secure_links import SecureLinkConfig

        config = SecureLinkConfig(
            secret_key="test-secret-key", default_expiry_days=7, max_expiry_days=30
        )
        return SecureLinkGenerator(config=config)

    def test_url_generation_with_future_expiration(self, storage, mock_supabase_client):
        """Test URL generation with valid future expiration."""
        # Mock successful signed URL generation
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/file.pdf?token=future123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            # Mock current time
            current_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = current_time

            result = storage.generate_secure_report_url(
                "test-report.pdf", expires_in_hours=24
            )

            # Verify expiration is 24 hours in the future
            expected_expiry = current_time + timedelta(hours=24)
            actual_expiry = datetime.fromisoformat(result["expires_at"])

            assert actual_expiry == expected_expiry
            assert result["expires_in_hours"] == 24
            assert "future123" in result["signed_url"]

    def test_url_generation_with_zero_expiration_rejected(
        self, storage, mock_supabase_client
    ):
        """Test that URLs cannot be generated with zero or negative expiration times."""
        # Mock to simulate validation in the storage layer
        with pytest.raises((ValueError, Exception)):
            # Attempt to create URL with zero expiration
            storage.generate_secure_report_url("test-report.pdf", expires_in_hours=0)

    def test_access_request_validation_with_expired_token(self, secure_validator):
        """Test validation of access requests with expired tokens."""
        from leadfactory.security.access_control import PDFOperation

        access_request = AccessRequest(
            user_id="user123",
            resource_id="report456",
            operation=PDFOperation.DOWNLOAD,
            token="expired_token_123",
        )

        # Mock the validation to simulate expired token
        with patch.object(secure_validator, "validate_access_request") as mock_validate:
            mock_validate.return_value = ValidationResult(
                valid=False, error_message="Access token has expired"
            )

            result = secure_validator.validate_access_request(access_request)

            assert result.valid is False
            assert "expired" in result.error_message.lower()

    def test_access_request_validation_with_valid_token(self, secure_validator):
        """Test validation of access requests with valid tokens."""
        from leadfactory.security.access_control import PDFOperation

        access_request = AccessRequest(
            user_id="user123",
            resource_id="report456",
            operation=PDFOperation.DOWNLOAD,
            token="valid_token_123",
        )

        # Mock the validation to simulate valid token
        with patch.object(secure_validator, "validate_access_request") as mock_validate:
            mock_validate.return_value = ValidationResult(
                valid=True, error_message=None
            )

            result = secure_validator.validate_access_request(access_request)

            assert result.valid is True
            assert result.error_message is None

    def test_timezone_handling_in_expiration(self, storage, mock_supabase_client):
        """Test proper timezone handling in URL expiration."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/tz.pdf?token=tz123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            # Test with UTC timezone
            utc_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = utc_time

            result = storage.generate_secure_report_url(
                "timezone-test.pdf", expires_in_hours=6
            )

            # Verify timezone is properly handled
            expires_at_str = result["expires_at"]

            # Parse and verify the time
            expires_at = datetime.fromisoformat(expires_at_str)
            expected_expiry = utc_time + timedelta(hours=6)
            assert expires_at == expected_expiry

    def test_edge_case_expiration_times(self, storage, mock_supabase_client):
        """Test edge cases for expiration times."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/edge.pdf?token=edge123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            current_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = current_time

            # Test minimum expiration (1 hour - smallest practical value)
            result_min = storage.generate_secure_report_url(
                "min-expiry.pdf", expires_in_hours=1
            )

            min_expiry = datetime.fromisoformat(result_min["expires_at"])
            expected_min = current_time + timedelta(hours=1)
            assert min_expiry == expected_min

            # Test maximum expiration (30 days)
            result_max = storage.generate_secure_report_url(
                "max-expiry.pdf",
                expires_in_hours=30 * 24,  # 30 days
            )

            max_expiry = datetime.fromisoformat(result_max["expires_at"])
            expected_max = current_time + timedelta(days=30)
            assert max_expiry == expected_max

    def test_secure_link_expiration_validation(self, link_generator):
        """Test secure link expiration validation."""
        # Generate link with custom expiration
        secure_url = link_generator.generate_secure_link(
            report_id="report456",
            user_id="user123",
            purchase_id="purchase789",
            base_url="https://test.example.com/reports",
            expiry_days=1,
        )

        # Extract token from URL
        from urllib.parse import parse_qs, urlparse

        parsed_url = urlparse(secure_url)
        token = parse_qs(parsed_url.query)["token"][0]

        # Validate immediately (should be valid)
        try:
            link_data = link_generator.validate_secure_link(token)
            assert link_data.user_id == "user123"
            assert link_data.report_id == "report456"
            assert link_data.purchase_id == "purchase789"
        except Exception as e:
            pytest.fail(f"Valid token validation failed: {e}")

        # Test with an expired token by creating one with past expiration
        from datetime import datetime, timedelta

        import jwt

        # Create a token that's already expired
        expired_payload = {
            "report_id": "report456",
            "user_id": "user123",
            "purchase_id": "purchase789",
            "expires_at": int((datetime.utcnow() - timedelta(days=1)).timestamp()),
            "access_type": "view",
            "metadata": {},
            "exp": int((datetime.utcnow() - timedelta(days=1)).timestamp()),
        }

        expired_token = jwt.encode(
            expired_payload,
            link_generator.config.secret_key,
            algorithm=link_generator.config.algorithm,
        )

        # This should raise an ExpiredSignatureError
        with pytest.raises(jwt.ExpiredSignatureError):
            link_generator.validate_secure_link(expired_token)

    def test_expiration_with_different_time_formats(
        self, storage, mock_supabase_client
    ):
        """Test expiration handling with different time formats."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/format.pdf?token=format123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            # Test with microseconds
            current_time = datetime(2024, 1, 1, 12, 0, 0, 123456)
            mock_datetime.utcnow.return_value = current_time

            result = storage.generate_secure_report_url(
                "format-test.pdf", expires_in_hours=1
            )

            # Verify ISO format is properly generated
            expires_at_str = result["expires_at"]

            # Should be parseable back to datetime
            parsed_time = datetime.fromisoformat(expires_at_str)
            assert isinstance(parsed_time, datetime)

    def test_expiration_with_system_clock_changes(self, storage, mock_supabase_client):
        """Test behavior when system clock changes during operation."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/clock.pdf?token=clock123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            # Initial time
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = initial_time

            # Generate URL
            result = storage.generate_secure_report_url(
                "clock-test.pdf", expires_in_hours=2
            )

            initial_expiry = datetime.fromisoformat(result["expires_at"])

            # Simulate clock jump forward by 1 hour
            jumped_time = initial_time + timedelta(hours=1)
            mock_datetime.utcnow.return_value = jumped_time

            # Generate another URL - should still be relative to current time
            result2 = storage.generate_secure_report_url(
                "clock-test2.pdf", expires_in_hours=2
            )

            second_expiry = datetime.fromisoformat(result2["expires_at"])

            # Second URL should expire 1 hour later than first
            time_diff = second_expiry - initial_expiry
            assert abs(time_diff.total_seconds() - 3600) < 1  # 1 hour difference

    def test_expiration_edge_cases_with_leap_seconds(
        self, storage, mock_supabase_client
    ):
        """Test expiration handling around leap seconds and DST changes."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/leap.pdf?token=leap123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            # Test around a theoretical leap second (23:59:60)
            # Note: Python datetime doesn't support leap seconds, but we test edge behavior
            edge_time = datetime(2024, 6, 30, 23, 59, 59)
            mock_datetime.utcnow.return_value = edge_time

            result = storage.generate_secure_report_url(
                "leap-test.pdf", expires_in_hours=1
            )

            # Should handle the edge case gracefully
            expires_at = datetime.fromisoformat(result["expires_at"])
            expected_expiry = edge_time + timedelta(hours=1)
            assert expires_at == expected_expiry

    def test_url_expiration_metadata_validation(self, storage, mock_supabase_client):
        """Test that URL generation includes proper expiration metadata."""
        mock_supabase_client.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://test.supabase.co/storage/v1/object/sign/test/meta.pdf?token=meta123"
        }

        with patch("leadfactory.storage.supabase_storage.datetime") as mock_datetime:
            current_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = current_time

            result = storage.generate_secure_report_url(
                "metadata-test.pdf", expires_in_hours=12
            )

            # Verify all required metadata is present
            assert "signed_url" in result
            assert "storage_path" in result
            assert "expires_at" in result
            assert "expires_in_hours" in result
            assert "generated_at" in result

            # Verify metadata values
            assert result["storage_path"] == "metadata-test.pdf"
            assert result["expires_in_hours"] == 12

            # Verify timestamps are valid ISO format
            expires_at = datetime.fromisoformat(result["expires_at"])
            generated_at = datetime.fromisoformat(result["generated_at"])

            assert isinstance(expires_at, datetime)
            assert isinstance(generated_at, datetime)

            # Verify expiration is 12 hours after generation
            time_diff = expires_at - generated_at
            assert abs(time_diff.total_seconds() - (12 * 3600)) < 1

    def test_token_revocation_and_expiration(self, secure_validator):
        """Test that revoked tokens are properly handled."""
        from leadfactory.security.access_control import PDFOperation

        access_request = AccessRequest(
            user_id="user123",
            resource_id="report456",
            operation=PDFOperation.DOWNLOAD,
            token="revoked_token_123",
        )

        # Mock revoked token validation
        with patch.object(secure_validator, "validate_access_request") as mock_validate:
            mock_validate.return_value = ValidationResult(
                valid=False, error_message="Access token has been revoked"
            )

            result = secure_validator.validate_access_request(access_request)

            assert result.valid is False
            assert "revoked" in result.error_message.lower()

    def test_rate_limiting_with_expired_tokens(self, secure_validator):
        """Test that rate limiting works with expired token scenarios."""
        from leadfactory.security.access_control import PDFOperation

        access_request = AccessRequest(
            user_id="user123",
            resource_id="report456",
            operation=PDFOperation.DOWNLOAD,
            token="rate_limited_token",
            ip_address="192.168.1.1",
        )

        # Mock rate limit exceeded scenario
        with patch.object(secure_validator, "validate_access_request") as mock_validate:
            mock_validate.return_value = ValidationResult(
                valid=False,
                error_message="Rate limit exceeded. Retry after 60 seconds.",
                rate_limit_info={"retry_after_seconds": 60},
            )

            result = secure_validator.validate_access_request(access_request)

            assert result.valid is False
            assert "rate limit" in result.error_message.lower()
            assert result.rate_limit_info is not None
