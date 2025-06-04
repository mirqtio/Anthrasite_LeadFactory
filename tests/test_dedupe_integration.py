"""
Integration test for deduplication functionality.

This test verifies that the deduplication components work together correctly.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_dedupe_config_import():
    """Test that dedupe config can be imported."""
    try:
        from leadfactory.config.dedupe_config import DedupeConfig, load_dedupe_config

        # Test creating a config
        config = DedupeConfig()
        assert config.name_similarity_threshold == 0.85

        # Test config with custom values
        custom_config = DedupeConfig(name_similarity_threshold=0.90, batch_size=50)
        assert custom_config.name_similarity_threshold == 0.90
        assert custom_config.batch_size == 50

        return True
    except Exception:
        return False


def test_dedupe_connector_import():
    """Test that dedupe connector functions can be imported."""
    try:
        from leadfactory.utils.e2e_db_connector import (
            add_to_review_queue,
            check_dedupe_tables_exist,
            create_dedupe_tables,
            get_business_details,
            get_potential_duplicate_pairs,
            merge_business_records,
            update_business_fields,
        )

        return True
    except Exception:
        return False


def test_dedupe_unified_import():
    """Test that dedupe unified module can be imported."""
    try:
        from leadfactory.pipeline.dedupe_unified import (
            LevenshteinMatcher,
            OllamaVerifier,
            get_potential_duplicates,
            main,
            merge_businesses,
            process_duplicate_pair,
        )

        # Test creating a matcher
        matcher = LevenshteinMatcher(threshold=0.85)
        assert matcher.threshold == 0.85

        return True
    except Exception:
        return False


def test_integration():
    """Test that all components work together."""
    try:
        from leadfactory.config.dedupe_config import DedupeConfig
        from leadfactory.pipeline.dedupe_unified import LevenshteinMatcher

        # Create config
        config = DedupeConfig(name_similarity_threshold=0.88)

        # Create matcher with config threshold
        matcher = LevenshteinMatcher(threshold=config.name_similarity_threshold)

        # Test matching
        result = matcher.is_match("Business Name", "Business Name")
        assert result is True

        return True
    except Exception:
        return False


def main():
    """Run all integration tests."""

    tests = [
        test_dedupe_config_import,
        test_dedupe_connector_import,
        test_dedupe_unified_import,
        test_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
