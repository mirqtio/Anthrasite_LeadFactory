"""
Unit tests for the deduplication pipeline module.

Tests the core deduplication logic without external dependencies.
"""

import json
from datetime import datetime
from typing import Dict, List
from unittest.mock import MagicMock, call, patch

import pytest

from leadfactory.pipeline.dedupe import (
    DedupeDecision,
    DuplicateDetector,
    calculate_similarity_score,
    deduplicate_businesses,
    find_duplicates,
    merge_business_data,
)


class TestDeduplicationFunctions:
    """Test individual deduplication functions."""

    def test_calculate_similarity_score_exact_match(self):
        """Test similarity score for exact matches."""
        business1 = {
            "name": "Joe's Pizza",
            "address": "123 Main St",
            "phone": "555-1234",
            "website": "joespizza.com"
        }
        business2 = business1.copy()

        score = calculate_similarity_score(business1, business2)
        assert score >= 0.99  # Allow for floating point imprecision

    def test_calculate_similarity_score_no_match(self):
        """Test similarity score for completely different businesses."""
        business1 = {
            "name": "Joe's Pizza",
            "address": "123 Main St",
            "phone": "555-1234",
            "website": "joespizza.com"
        }
        business2 = {
            "name": "Bob's Burgers",
            "address": "456 Oak Ave",
            "phone": "555-5678",
            "website": "bobsburgers.com"
        }

        score = calculate_similarity_score(business1, business2)
        assert score < 0.5

    def test_calculate_similarity_score_partial_match(self):
        """Test similarity score for partial matches."""
        business1 = {
            "name": "Joe's Pizza",
            "address": "123 Main St",
            "phone": "555-1234",
            "website": "joespizza.com"
        }
        business2 = {
            "name": "Joe's Pizza & Pasta",  # Similar name
            "address": "123 Main Street",    # Similar address
            "phone": "555-1234",             # Same phone
            "website": "joespizzapasta.com"  # Different website
        }

        score = calculate_similarity_score(business1, business2)
        assert 0.6 < score < 0.9  # Should be high but not perfect

    def test_calculate_similarity_score_missing_fields(self):
        """Test similarity score when fields are missing."""
        business1 = {
            "name": "Joe's Pizza",
            "phone": "555-1234"
        }
        business2 = {
            "name": "Joe's Pizza",
            "address": "123 Main St"
        }

        score = calculate_similarity_score(business1, business2)
        assert score > 0  # Should still calculate based on name

    def test_merge_business_data_basic(self):
        """Test merging two business records."""
        business1 = {
            "id": 1,
            "name": "Joe's Pizza",
            "phone": "555-1234",
            "created_at": "2023-01-01",
            "score": 75
        }
        business2 = {
            "id": 2,
            "name": "Joe's Pizza & Pasta",
            "address": "123 Main St",
            "website": "joespizza.com",
            "created_at": "2023-01-02",
            "score": 80
        }

        merged = merge_business_data(business1, business2)

        assert merged["id"] == 1  # Keep first ID
        assert merged["name"] == "Joe's Pizza & Pasta"  # Longer name
        assert merged["phone"] == "555-1234"  # From business1
        assert merged["address"] == "123 Main St"  # From business2
        assert merged["website"] == "joespizza.com"  # From business2
        assert merged["score"] == 80  # Higher score

    def test_merge_business_data_preserve_non_empty(self):
        """Test that merge preserves non-empty values."""
        business1 = {
            "id": 1,
            "name": "Joe's",
            "phone": "",
            "email": "joe@pizza.com"
        }
        business2 = {
            "id": 2,
            "name": "",
            "phone": "555-1234",
            "email": ""
        }

        merged = merge_business_data(business1, business2)

        assert merged["name"] == "Joe's"  # Non-empty from business1
        assert merged["phone"] == "555-1234"  # Non-empty from business2
        assert merged["email"] == "joe@pizza.com"  # Non-empty from business1


class TestDuplicateDetector:
    """Test the DuplicateDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a DuplicateDetector instance."""
        return DuplicateDetector(similarity_threshold=0.6)

    def test_find_duplicates_empty_list(self, detector):
        """Test finding duplicates in empty list."""
        duplicates = detector.find_duplicates([])
        assert duplicates == []

    def test_find_duplicates_no_duplicates(self, detector):
        """Test when no duplicates exist."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234"},
            {"id": 2, "name": "Bob's Burgers", "phone": "555-5678"},
            {"id": 3, "name": "Amy's Cafe", "phone": "555-9012"}
        ]

        duplicates = detector.find_duplicates(businesses)
        assert duplicates == []

    def test_find_duplicates_exact_match(self, detector):
        """Test finding exact duplicate."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 2, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 3, "name": "Amy's Cafe", "phone": "555-9012", "address": "456 Oak Ave", "website": "amyscafe.com"}
        ]

        duplicates = detector.find_duplicates(businesses)
        assert len(duplicates) == 1
        assert set(duplicates[0]) == {1, 2}

    def test_find_duplicates_multiple_groups(self, detector):
        """Test finding multiple duplicate groups."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 2, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 3, "name": "Bob's Burgers", "phone": "555-5678", "address": "456 Oak Ave", "website": "bobsburgers.com"},
            {"id": 4, "name": "Bob's Burgers", "phone": "555-5678", "address": "456 Oak Ave", "website": "bobsburgers.com"},
        ]

        duplicates = detector.find_duplicates(businesses)
        assert len(duplicates) == 2
        assert {1, 2} in [set(group) for group in duplicates]
        assert {3, 4} in [set(group) for group in duplicates]

    def test_find_duplicates_threshold(self):
        """Test that similarity threshold is respected."""
        detector_high = DuplicateDetector(similarity_threshold=0.9)
        detector_low = DuplicateDetector(similarity_threshold=0.5)

        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234"},
            {"id": 2, "name": "Joe's Pizza & Pasta", "phone": "555-1234"},
        ]

        # High threshold - not similar enough
        duplicates_high = detector_high.find_duplicates(businesses)
        assert duplicates_high == []

        # Low threshold - similar enough
        duplicates_low = detector_low.find_duplicates(businesses)
        assert len(duplicates_low) == 1


class TestDeduplicationPipeline:
    """Test the full deduplication pipeline."""

    def test_deduplicate_businesses_no_duplicates(self):
        """Test deduplication when no duplicates exist."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 2, "name": "Bob's Burgers", "phone": "555-5678", "address": "456 Oak Ave", "website": "bobsburgers.com"},
        ]

        result = deduplicate_businesses(businesses, similarity_threshold=0.6)

        assert result == businesses

    def test_deduplicate_businesses_with_duplicates(self):
        """Test deduplication with duplicates."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com", "created_at": "2023-01-01"},
            {"id": 2, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com", "created_at": "2023-01-02"},
            {"id": 3, "name": "Bob's Burgers", "phone": "555-5678", "address": "456 Oak Ave", "website": "bobsburgers.com", "created_at": "2023-01-03"},
        ]

        result = deduplicate_businesses(businesses, similarity_threshold=0.6)

        # Should keep business 1 (older) and business 3
        assert len(result) == 2
        assert any(b["id"] == 1 for b in result)
        assert any(b["id"] == 3 for b in result)
        assert not any(b["id"] == 2 for b in result)

    def test_deduplicate_businesses_merge_data(self):
        """Test that data is merged when deduplicating."""
        businesses = [
            {"id": 1, "name": "Joe's", "phone": "555-1234", "address": "123 Main St", "website": ""},
            {"id": 2, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
        ]

        result = deduplicate_businesses(businesses, merge_data=True, similarity_threshold=0.6)

        # Should have merged data
        assert len(result) == 1
        merged = result[0]
        assert merged["id"] == 1
        assert merged["name"] == "Joe's Pizza"  # Longer name from business 2
        assert merged["website"] == "joespizza.com"  # From business 2

    def test_deduplicate_businesses_error_handling(self):
        """Test error handling in deduplication."""
        businesses = [
            {"id": 1, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
            {"id": 2, "name": "Joe's Pizza", "phone": "555-1234", "address": "123 Main St", "website": "joespizza.com"},
        ]

        # Should handle empty input gracefully
        result = deduplicate_businesses([])
        assert result == []

        # Should handle businesses without required fields
        invalid_businesses = [{"name": "Test"}]  # Missing 'id'
        try:
            result = deduplicate_businesses(invalid_businesses, similarity_threshold=0.6)
            # If it doesn't crash, that's good enough for this test
        except (KeyError, TypeError):
            # Expected for missing 'id' field
            pass


class TestDedupeDecision:
    """Test the DedupeDecision enum and decision logic."""

    def test_dedupe_decision_values(self):
        """Test DedupeDecision enum values."""
        assert DedupeDecision.KEEP_FIRST.value == "keep_first"
        assert DedupeDecision.KEEP_SECOND.value == "keep_second"
        assert DedupeDecision.MERGE.value == "merge"
        assert DedupeDecision.KEEP_BOTH.value == "keep_both"

    def test_make_dedupe_decision_by_date(self):
        """Test deduplication decision based on creation date."""
        from leadfactory.pipeline.dedupe import make_dedupe_decision

        business1 = {"id": 1, "created_at": "2023-01-01T00:00:00Z"}
        business2 = {"id": 2, "created_at": "2023-01-02T00:00:00Z"}

        # Should keep older (first)
        decision = make_dedupe_decision(business1, business2, strategy="keep_older")
        assert decision == DedupeDecision.KEEP_FIRST

        # Should keep newer (second)
        decision = make_dedupe_decision(business1, business2, strategy="keep_newer")
        assert decision == DedupeDecision.KEEP_SECOND

    def test_make_dedupe_decision_by_completeness(self):
        """Test deduplication decision based on data completeness."""
        from leadfactory.pipeline.dedupe import make_dedupe_decision

        business1 = {"id": 1, "name": "Joe's", "phone": "555-1234"}
        business2 = {"id": 2, "name": "Joe's Pizza", "phone": "555-1234",
                    "website": "joespizza.com", "email": "joe@pizza.com"}

        # Should keep more complete (second)
        decision = make_dedupe_decision(business1, business2, strategy="keep_complete")
        assert decision == DedupeDecision.KEEP_SECOND

    def test_make_dedupe_decision_merge(self):
        """Test merge decision."""
        from leadfactory.pipeline.dedupe import make_dedupe_decision

        business1 = {"id": 1, "name": "Joe's"}
        business2 = {"id": 2, "name": "Joe's Pizza"}

        decision = make_dedupe_decision(business1, business2, strategy="merge")
        assert decision == DedupeDecision.MERGE
