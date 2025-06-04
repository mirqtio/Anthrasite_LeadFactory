"""
Unit tests for conflict resolution module.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from leadfactory.config.dedupe_config import DedupeConfig
from leadfactory.pipeline.conflict_resolution import (
    ConflictResolver,
    ConflictType,
    ResolutionStrategy,
    apply_conflict_resolution,
)


class TestConflictResolver(unittest.TestCase):
    """Test cases for ConflictResolver class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DedupeConfig()
        self.resolver = ConflictResolver(self.config)

        # Sample business records
        self.primary = {
            "id": 1,
            "name": "ABC Company",
            "phone": "555-1234",
            "email": None,
            "address": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
            "category": "Restaurant",
            "website": "www.abc.com",
            "updated_at": datetime.now().isoformat(),
            "source": "google",
        }

        self.secondary = {
            "id": 2,
            "name": "ABC Company Inc",
            "phone": "555-1234",
            "email": "info@abc.com",
            "address": "123 Main Street",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
            "category": "Restaurant & Bar",
            "website": None,
            "updated_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "source": "yelp",
        }

    def test_identify_conflicts(self):
        """Test conflict identification."""
        conflicts = self.resolver.identify_conflicts(self.primary, self.secondary)

        # Should identify conflicts for different values
        conflict_fields = [c["field"] for c in conflicts]
        self.assertIn("name", conflict_fields)
        self.assertIn("email", conflict_fields)
        self.assertIn("address", conflict_fields)
        self.assertIn("category", conflict_fields)
        self.assertIn("website", conflict_fields)

        # Should not include identical fields
        self.assertNotIn("phone", conflict_fields)
        self.assertNotIn("city", conflict_fields)
        self.assertNotIn("state", conflict_fields)
        self.assertNotIn("zip", conflict_fields)

    def test_determine_conflict_type(self):
        """Test conflict type determination."""
        # Both present and different
        conflict_type = self.resolver._determine_conflict_type("value1", "value2")
        self.assertEqual(conflict_type, ConflictType.BOTH_PRESENT_DIFFERENT)

        # Both present and same
        conflict_type = self.resolver._determine_conflict_type("value", "value")
        self.assertEqual(conflict_type, ConflictType.BOTH_PRESENT_SAME)

        # Missing in primary
        conflict_type = self.resolver._determine_conflict_type(None, "value")
        self.assertEqual(conflict_type, ConflictType.MISSING_IN_PRIMARY)

        # Missing in secondary
        conflict_type = self.resolver._determine_conflict_type("value", None)
        self.assertEqual(conflict_type, ConflictType.MISSING_IN_SECONDARY)

        # Both missing
        conflict_type = self.resolver._determine_conflict_type(None, None)
        self.assertEqual(conflict_type, ConflictType.BOTH_PRESENT_SAME)

    def test_resolve_conflicts_keep_primary(self):
        """Test KEEP_PRIMARY resolution strategy."""
        conflicts = [
            {
                "field": "name",
                "type": ConflictType.BOTH_PRESENT_DIFFERENT,
                "primary_value": "ABC Company",
                "secondary_value": "ABC Company Inc",
                "resolution_strategy": ResolutionStrategy.KEEP_PRIMARY,
            }
        ]

        updates = self.resolver.resolve_conflicts(
            conflicts, self.primary, self.secondary
        )

        # Should not update when keeping primary
        self.assertNotIn("name", updates)

    def test_resolve_conflicts_missing_in_primary(self):
        """Test resolution when value is missing in primary."""
        conflicts = [
            {
                "field": "email",
                "type": ConflictType.MISSING_IN_PRIMARY,
                "primary_value": None,
                "secondary_value": "info@abc.com",
                "resolution_strategy": ResolutionStrategy.KEEP_PRIMARY,
            }
        ]

        updates = self.resolver.resolve_conflicts(
            conflicts, self.primary, self.secondary
        )

        # Should update with secondary value when primary is missing
        self.assertEqual(updates["email"], "info@abc.com")

    def test_merge_concatenate(self):
        """Test concatenation merge strategy."""
        # Both values present
        result = self.resolver._merge_concatenate("Restaurant", "Bar")
        self.assertEqual(result, "Restaurant | Bar")

        # Only one value
        result = self.resolver._merge_concatenate("Restaurant", None)
        self.assertEqual(result, "Restaurant")

        result = self.resolver._merge_concatenate(None, "Bar")
        self.assertEqual(result, "Bar")

        # No values
        result = self.resolver._merge_concatenate(None, None)
        self.assertIsNone(result)

    def test_merge_longest(self):
        """Test longest value merge strategy."""
        # Different lengths
        result = self.resolver._merge_longest("Short", "Much longer value")
        self.assertEqual(result, "Much longer value")

        # Same length (keeps first)
        result = self.resolver._merge_longest("Same1", "Same2")
        self.assertEqual(result, "Same1")

        # One is None
        result = self.resolver._merge_longest("Value", None)
        self.assertEqual(result, "Value")

        result = self.resolver._merge_longest(None, "Value")
        self.assertEqual(result, "Value")

    def test_merge_newest(self):
        """Test newest value merge strategy."""
        # Secondary is newer
        newer_secondary = self.secondary.copy()
        newer_secondary["updated_at"] = datetime.now().isoformat()
        older_primary = self.primary.copy()
        older_primary["updated_at"] = (datetime.now() - timedelta(days=2)).isoformat()

        result = self.resolver._merge_newest("category", older_primary, newer_secondary)
        self.assertEqual(result, "Restaurant & Bar")

        # Primary is newer
        result = self.resolver._merge_newest("category", self.primary, self.secondary)
        self.assertEqual(result, "Restaurant")

    def test_merge_highest_quality(self):
        """Test highest quality merge strategy."""
        # Google has higher priority than Yelp by default
        result = self.resolver._merge_highest_quality(
            "category", self.primary, self.secondary
        )
        self.assertEqual(result, "Restaurant")

        # Test with manual source (highest priority)
        manual_secondary = self.secondary.copy()
        manual_secondary["source"] = "manual"
        result = self.resolver._merge_highest_quality(
            "category", self.primary, manual_secondary
        )
        self.assertEqual(result, "Restaurant & Bar")

    def test_generate_conflict_report(self):
        """Test conflict report generation."""
        conflicts = [
            {
                "field": "name",
                "type": ConflictType.BOTH_PRESENT_DIFFERENT,
                "primary_value": "ABC Company",
                "secondary_value": "ABC Company Inc",
                "resolution_strategy": ResolutionStrategy.KEEP_PRIMARY,
            },
            {
                "field": "email",
                "type": ConflictType.MISSING_IN_PRIMARY,
                "primary_value": None,
                "secondary_value": "info@abc.com",
                "resolution_strategy": ResolutionStrategy.KEEP_PRIMARY,
            },
            {
                "field": "critical_field",
                "type": ConflictType.BOTH_PRESENT_DIFFERENT,
                "primary_value": "value1",
                "secondary_value": "value2",
                "resolution_strategy": ResolutionStrategy.MANUAL_REVIEW,
            },
        ]

        report = self.resolver.generate_conflict_report(conflicts)

        self.assertEqual(report["total_conflicts"], 3)
        self.assertEqual(report["conflicts_by_type"]["both_present_different"], 2)
        self.assertEqual(report["conflicts_by_type"]["missing_in_primary"], 1)
        self.assertEqual(report["conflicts_by_field"]["name"], 1)
        self.assertEqual(report["conflicts_by_field"]["email"], 1)
        self.assertEqual(report["resolution_strategies"]["keep_primary"], 2)
        self.assertEqual(report["resolution_strategies"]["manual_review"], 1)
        self.assertEqual(len(report["manual_review_required"]), 1)


class TestApplyConflictResolution(unittest.TestCase):
    """Test the apply_conflict_resolution function."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DedupeConfig()
        self.primary = {
            "id": 1,
            "name": "Test Business",
            "email": None,
            "phone": "555-1234",
        }
        self.secondary = {
            "id": 2,
            "name": "Test Business Inc",
            "email": "test@example.com",
            "phone": "555-1234",
        }

    @patch("leadfactory.pipeline.conflict_resolution.logger")
    def test_apply_conflict_resolution(self, mock_logger):
        """Test the main conflict resolution function."""
        updates, report = apply_conflict_resolution(
            self.primary, self.secondary, self.config
        )

        # Should have updates for missing email
        self.assertIn("email", updates)
        self.assertEqual(updates["email"], "test@example.com")

        # Should have conflict report
        self.assertGreater(report["total_conflicts"], 0)

        # Should log the resolution
        mock_logger.info.assert_called()


if __name__ == "__main__":
    unittest.main()
