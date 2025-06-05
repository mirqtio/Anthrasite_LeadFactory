"""
Unit tests for JSON retention policy implementation.
"""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from leadfactory.config.json_retention_policy import JSONRetentionPolicy


class TestJSONRetentionPolicy:
    """Test cases for JSONRetentionPolicy class."""

    def test_policy_initialization_default(self):
        """Test policy initialization with default settings."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "id,rating"):

            policy = JSONRetentionPolicy()

            assert policy.enabled is True
            assert policy.retention_days == 90
            assert policy.anonymize is False
            assert policy.preserve_fields == {"id", "rating"}

    def test_policy_initialization_disabled(self):
        """Test policy when JSON retention is disabled."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            policy = JSONRetentionPolicy()
            assert policy.enabled is False
            assert not policy.should_store_json()

    def test_should_store_json_scenarios(self):
        """Test should_store_json under different configurations."""
        # Enabled with normal retention
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90):
            policy = JSONRetentionPolicy()
            assert policy.should_store_json() is True

        # Disabled
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            policy = JSONRetentionPolicy()
            assert policy.should_store_json() is False

        # Immediate purge
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 0):
            policy = JSONRetentionPolicy()
            assert policy.should_store_json() is False

        # Keep forever
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", -1):
            policy = JSONRetentionPolicy()
            assert policy.should_store_json() is True

    def test_get_retention_expiry_date(self):
        """Test retention expiry date calculation."""
        # Normal retention period
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 30):
            policy = JSONRetentionPolicy()
            expiry = policy.get_retention_expiry_date()

            assert expiry is not None
            # Should be approximately 30 days from now
            expected = datetime.now() + timedelta(days=30)
            assert abs((expiry - expected).total_seconds()) < 60  # Within 1 minute

        # Keep forever
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", -1):
            policy = JSONRetentionPolicy()
            expiry = policy.get_retention_expiry_date()
            assert expiry is None

        # Disabled
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            policy = JSONRetentionPolicy()
            expiry = policy.get_retention_expiry_date()
            assert expiry is None

    def test_process_json_for_storage_disabled(self):
        """Test JSON processing when retention is disabled."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            policy = JSONRetentionPolicy()

            test_data = {"name": "Test Business", "id": "123"}
            result = policy.process_json_for_storage(test_data)

            assert result is None

    def test_process_json_for_storage_immediate_purge(self):
        """Test JSON processing with immediate purge setting."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 0):
            policy = JSONRetentionPolicy()

            test_data = {"name": "Test Business", "id": "123"}
            result = policy.process_json_for_storage(test_data)

            assert result is None

    def test_process_json_for_storage_no_anonymization(self):
        """Test JSON processing without anonymization."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", False):
            policy = JSONRetentionPolicy()

            test_data = {"name": "Test Business", "id": "123", "phone": "555-1234"}
            result = policy.process_json_for_storage(test_data)

            assert result == test_data

    def test_process_json_for_storage_with_anonymization(self):
        """Test JSON processing with anonymization."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "id,rating"):
            policy = JSONRetentionPolicy()

            test_data = {
                "id": "123",
                "name": "John's Restaurant",  # Should be redacted
                "rating": 4.5,  # Should be preserved
                "phone": "555-1234",  # Should be redacted
                "address": "123 Main St",  # Should be redacted
                "categories": ["restaurant", "food"]  # Not PII, should remain
            }

            result = policy.process_json_for_storage(test_data)

            assert result is not None
            assert result["id"] == "123"  # Preserved
            assert result["rating"] == 4.5  # Preserved
            assert result["name"] == "[REDACTED]"  # PII redacted
            assert result["phone"] == "[REDACTED]"  # PII redacted
            assert result["address"] == "[REDACTED]"  # PII redacted
            assert result["categories"] == ["restaurant", "food"]  # Not PII

    def test_anonymize_nested_objects(self):
        """Test anonymization of nested JSON structures."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "location.zip_code,rating"):
            policy = JSONRetentionPolicy()

            test_data = {
                "id": "123",
                "rating": 4.5,
                "location": {
                    "address": "123 Main St",  # Should be redacted
                    "zip_code": "12345",  # Should be preserved
                    "phone": "555-1234",  # Should be redacted
                },
                "owner": {
                    "name": "John Doe",  # Should be redacted
                    "email": "john@example.com"  # Should be redacted
                }
            }

            result = policy.process_json_for_storage(test_data)

            assert result is not None
            assert result["rating"] == 4.5  # Preserved
            assert result["location"]["zip_code"] == "12345"  # Preserved
            assert result["location"]["address"] == "[REDACTED]"  # PII redacted
            assert result["location"]["phone"] == "[REDACTED]"  # PII redacted
            assert result["owner"]["name"] == "[REDACTED]"  # PII redacted
            assert result["owner"]["email"] == "[REDACTED]"  # PII redacted

    def test_pii_field_detection(self):
        """Test PII field detection logic."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", ""):
            policy = JSONRetentionPolicy()

            # Test email detection
            assert policy._is_pii_field("email", "test@example.com") is True
            assert policy._is_pii_field("contact_email", "test@example.com") is True

            # Test phone detection
            assert policy._is_pii_field("phone", "555-123-4567") is True
            assert policy._is_pii_field("telephone", "(555) 123-4567") is True

            # Test name fields
            assert policy._is_pii_field("name", "John Doe") is True
            assert policy._is_pii_field("first_name", "John") is True
            assert policy._is_pii_field("owner_name", "John Doe") is True

            # Test non-PII fields
            assert policy._is_pii_field("rating", "4.5") is False
            assert policy._is_pii_field("category", "restaurant") is False
            assert policy._is_pii_field("id", "123") is False

    def test_preserve_fields_parsing(self):
        """Test parsing of preserve fields configuration."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 90), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "id,rating,location.zip_code, hours "):
            policy = JSONRetentionPolicy()

            expected_fields = {"id", "rating", "location.zip_code", "hours"}
            assert policy.preserve_fields == expected_fields

    def test_get_policy_summary(self):
        """Test policy summary generation."""
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 30), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ANONYMIZE", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_PRESERVE_FIELDS", "id,rating"):
            policy = JSONRetentionPolicy()

            summary = policy.get_policy_summary()

            assert summary["enabled"] is True
            assert summary["retention_days"] == 30
            assert summary["retention_behavior"] == "Keep for 30 days"
            assert summary["anonymize"] is True
            assert set(summary["preserve_fields"]) == {"id", "rating"}
            assert summary["should_store"] is True

    def test_retention_behavior_descriptions(self):
        """Test different retention behavior descriptions."""
        # Disabled
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", False):
            policy = JSONRetentionPolicy()
            assert policy._get_retention_behavior_description() == "Disabled - no JSON responses stored"

        # Keep forever
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", -1):
            policy = JSONRetentionPolicy()
            assert policy._get_retention_behavior_description() == "Keep forever"

        # Immediate purge
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 0):
            policy = JSONRetentionPolicy()
            assert policy._get_retention_behavior_description() == "Purge immediately - no storage"

        # Normal retention
        with patch("leadfactory.config.json_retention_policy.JSON_RETENTION_ENABLED", True), \
             patch("leadfactory.config.json_retention_policy.JSON_RETENTION_DAYS", 45):
            policy = JSONRetentionPolicy()
            assert policy._get_retention_behavior_description() == "Keep for 45 days"
