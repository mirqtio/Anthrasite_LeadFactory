"""
JSON Response Retention Policy implementation.

This module implements the configurable retention policy for raw API JSON responses
from Yelp, Google Places, and other external APIs. It handles privacy compliance,
data anonymization, and retention period management.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from leadfactory.config.settings import (
    JSON_RETENTION_ANONYMIZE,
    JSON_RETENTION_DAYS,
    JSON_RETENTION_ENABLED,
    JSON_RETENTION_PRESERVE_FIELDS,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class JSONRetentionPolicy:
    """Manages JSON response retention according to configuration."""

    def __init__(self):
        """Initialize the retention policy with current configuration."""
        self.enabled = JSON_RETENTION_ENABLED
        self.retention_days = JSON_RETENTION_DAYS
        self.anonymize = JSON_RETENTION_ANONYMIZE
        self.preserve_fields = self._parse_preserve_fields(
            JSON_RETENTION_PRESERVE_FIELDS
        )

        logger.info(
            f"JSON retention policy initialized: enabled={self.enabled}, "
            f"retention_days={self.retention_days}, anonymize={self.anonymize}"
        )

    def _parse_preserve_fields(self, fields_str: str) -> Set[str]:
        """Parse comma-separated preserve fields string into a set."""
        if not fields_str:
            return set()

        fields = set()
        for field in fields_str.split(","):
            field = field.strip()
            if field:
                fields.add(field)

        return fields

    def should_store_json(self) -> bool:
        """Check if JSON responses should be stored at all."""
        return self.enabled and self.retention_days != 0

    def get_retention_expiry_date(self) -> Optional[datetime]:
        """Get the expiry date for newly stored JSON responses."""
        if not self.enabled:
            return None

        if self.retention_days == -1:
            # Keep forever
            return None

        if self.retention_days == 0:
            # Purge immediately
            return datetime.now()

        # Set expiry date based on retention period
        return datetime.now() + timedelta(days=self.retention_days)

    def process_json_for_storage(
        self, json_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process JSON data before storage according to retention policy.

        Args:
            json_data: Raw JSON response from API

        Returns:
            Processed JSON data for storage, or None if should not be stored
        """
        if not self.should_store_json():
            logger.debug("JSON retention disabled - not storing response")
            return None

        if self.retention_days == 0:
            logger.debug("Immediate purge configured - not storing response")
            return None

        # If anonymization is enabled, process the data
        if self.anonymize:
            return self._anonymize_json(json_data)

        # Store as-is
        return json_data

    def _anonymize_json(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize JSON data by removing PII while preserving specified fields.

        Args:
            json_data: Original JSON data

        Returns:
            Anonymized JSON data
        """
        if not json_data:
            return json_data

        try:
            # Create a deep copy to avoid modifying original
            anonymized = json.loads(json.dumps(json_data))

            # Apply anonymization rules
            self._anonymize_recursive(anonymized, "", self.preserve_fields)

            logger.debug(
                f"Anonymized JSON data, preserved {len(self.preserve_fields)} field patterns"
            )
            return anonymized

        except Exception as e:
            logger.error(f"Failed to anonymize JSON data: {e}")
            # Return empty dict rather than potentially exposing PII
            return {}

    def _anonymize_recursive(
        self, obj: Any, path: str, preserve_fields: Set[str]
    ) -> None:
        """
        Recursively anonymize a JSON object.

        Args:
            obj: Current object being processed
            path: Current field path (e.g., "location.address")
            preserve_fields: Set of field paths to preserve
        """
        if isinstance(obj, dict):
            keys_to_remove = []

            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key

                # Check if this field should be preserved
                if self._should_preserve_field(field_path, preserve_fields):
                    # Keep the field but continue processing nested objects
                    if isinstance(value, (dict, list)):
                        self._anonymize_recursive(value, field_path, preserve_fields)
                else:
                    # Check if this looks like PII
                    if self._is_pii_field(key, value):
                        keys_to_remove.append(key)
                    elif isinstance(value, (dict, list)):
                        # Continue processing nested objects
                        self._anonymize_recursive(value, field_path, preserve_fields)

            # Remove PII fields
            for key in keys_to_remove:
                obj[key] = "[REDACTED]"

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    self._anonymize_recursive(item, path, preserve_fields)

    def _should_preserve_field(
        self, field_path: str, preserve_fields: Set[str]
    ) -> bool:
        """Check if a field path should be preserved."""
        # Exact match
        if field_path in preserve_fields:
            return True

        # Check for partial matches (e.g., "location" preserves "location.zip_code")
        for preserve_pattern in preserve_fields:
            if field_path.startswith(preserve_pattern + "."):
                return True
            if preserve_pattern.startswith(field_path + "."):
                return True

        return False

    def _is_pii_field(self, key: str, value: Any) -> bool:
        """
        Check if a field appears to contain personally identifiable information.

        Args:
            key: Field name
            value: Field value

        Returns:
            True if field appears to contain PII
        """
        if not isinstance(value, str):
            return False

        key_lower = key.lower()

        # Common PII field names
        pii_keywords = {
            "name",
            "email",
            "phone",
            "address",
            "street",
            "owner",
            "contact",
            "manager",
            "employee",
            "staff",
            "person",
            "first_name",
            "last_name",
            "full_name",
            "display_name",
            "user_name",
            "username",
            "owner_name",
            "contact_name",
        }

        # Check if key contains PII keywords
        for keyword in pii_keywords:
            if keyword in key_lower:
                return True

        # Check for patterns that look like PII
        value_str = str(value).strip()

        # Email pattern (simple check)
        if "@" in value_str and "." in value_str:
            return True

        # Phone pattern (digits with formatting)
        phone_chars = "".join(c for c in value_str if c.isdigit())
        if len(phone_chars) >= 10 and any(c in value_str for c in "()-. "):
            return True

        return False

    def get_policy_summary(self) -> Dict[str, Any]:
        """Get a summary of the current retention policy."""
        return {
            "enabled": self.enabled,
            "retention_days": self.retention_days,
            "retention_behavior": self._get_retention_behavior_description(),
            "anonymize": self.anonymize,
            "preserve_fields": list(self.preserve_fields),
            "should_store": self.should_store_json(),
        }

    def _get_retention_behavior_description(self) -> str:
        """Get a human-readable description of the retention behavior."""
        if not self.enabled:
            return "Disabled - no JSON responses stored"

        if self.retention_days == -1:
            return "Keep forever"
        elif self.retention_days == 0:
            return "Purge immediately - no storage"
        else:
            return f"Keep for {self.retention_days} days"


# Global instance for easy access
retention_policy = JSONRetentionPolicy()


def get_retention_policy() -> JSONRetentionPolicy:
    """Get the global retention policy instance."""
    return retention_policy


def should_store_json() -> bool:
    """Quick check if JSON responses should be stored."""
    return retention_policy.should_store_json()


def process_json_for_storage(json_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process JSON data for storage according to retention policy."""
    return retention_policy.process_json_for_storage(json_data)


def get_retention_expiry_date() -> Optional[datetime]:
    """Get the expiry date for newly stored JSON responses."""
    return retention_policy.get_retention_expiry_date()
