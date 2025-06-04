"""
Unit tests for deduplication configuration module.

This module tests the configuration options and loading functionality
for the deduplication process.
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from leadfactory.config.dedupe_config import (
    DEFAULT_DEDUPE_CONFIG,
    DedupeConfig,
    load_dedupe_config,
)


class TestDedupeConfig:
    """Test DedupeConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DedupeConfig()

        # Test similarity thresholds
        assert config.name_similarity_threshold == 0.85
        assert config.address_similarity_threshold == 0.80
        assert config.phone_match_boost == 0.2

        # Test processing options
        assert config.batch_size == 100
        assert config.max_pairs_per_run is None
        assert config.use_llm_verification is False
        assert config.dry_run is False

        # Test LLM settings
        assert config.llm_model == "llama2"
        assert config.llm_base_url == "http://localhost:11434"
        assert config.llm_confidence_threshold == 0.8
        assert config.llm_timeout == 30

        # Test source priorities
        assert config.source_priorities == {"manual": 3, "google": 2, "yelp": 1}

        # Test fields
        assert "name" in config.matching_fields
        assert "phone" in config.matching_fields
        assert "email" in config.merge_fields
        assert "google_response" in config.merge_fields

        # Test review settings
        assert config.auto_flag_low_confidence is True
        assert config.low_confidence_threshold == 0.5
        assert config.flag_same_name_different_address is True

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = DedupeConfig(
            name_similarity_threshold=0.95,
            batch_size=50,
            use_llm_verification=True,
            llm_model="llama3",
            dry_run=True,
        )

        assert config.name_similarity_threshold == 0.95
        assert config.batch_size == 50
        assert config.use_llm_verification is True
        assert config.llm_model == "llama3"
        assert config.dry_run is True

    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "name_similarity_threshold": 0.90,
            "batch_size": 200,
            "use_llm_verification": True,
            "source_priorities": {"custom": 4, "manual": 3},
        }

        config = DedupeConfig.from_dict(config_dict)

        assert config.name_similarity_threshold == 0.90
        assert config.batch_size == 200
        assert config.use_llm_verification is True
        assert config.source_priorities["custom"] == 4

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = DedupeConfig(name_similarity_threshold=0.88, batch_size=75)

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["name_similarity_threshold"] == 0.88
        assert config_dict["batch_size"] == 75
        assert "source_priorities" in config_dict
        assert "matching_fields" in config_dict
        assert "merge_fields" in config_dict

    def test_custom_fields(self):
        """Test custom matching and merge fields."""
        custom_matching = ["name", "phone"]
        custom_merge = ["email", "website"]

        config = DedupeConfig(
            matching_fields=custom_matching, merge_fields=custom_merge
        )

        assert config.matching_fields == custom_matching
        assert config.merge_fields == custom_merge


class TestLoadDedupeConfig:
    """Test configuration loading functionality."""

    def test_load_default_config(self):
        """Test loading default config when no path provided."""
        config = load_dedupe_config()

        assert isinstance(config, DedupeConfig)
        assert config.name_similarity_threshold == 0.85

    def test_load_from_file(self):
        """Test loading config from JSON file."""
        config_data = {
            "name_similarity_threshold": 0.92,
            "batch_size": 150,
            "use_llm_verification": True,
            "llm_model": "custom-model",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_dedupe_config(temp_path)

            assert config.name_similarity_threshold == 0.92
            assert config.batch_size == 150
            assert config.use_llm_verification is True
            assert config.llm_model == "custom-model"
        finally:
            os.unlink(temp_path)

    def test_load_from_invalid_file(self):
        """Test handling of invalid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            # Should return default config on error
            config = load_dedupe_config(temp_path)
            assert isinstance(config, DedupeConfig)
            assert config.name_similarity_threshold == 0.85  # Default value
        finally:
            os.unlink(temp_path)

    @patch.dict(
        os.environ,
        {
            "DEDUPE_NAME_THRESHOLD": "0.75",
            "DEDUPE_USE_LLM": "true",
            "DEDUPE_LLM_MODEL": "env-model",
            "DEDUPE_BATCH_SIZE": "250",
        },
    )
    def test_load_from_environment(self):
        """Test loading config from environment variables."""
        config = load_dedupe_config()

        assert config.name_similarity_threshold == 0.75
        assert config.use_llm_verification is True
        assert config.llm_model == "env-model"
        assert config.batch_size == 250

    @patch.dict(os.environ, {"DEDUPE_USE_LLM": "false"})
    def test_env_var_false_value(self):
        """Test parsing false boolean from environment."""
        config = load_dedupe_config()
        assert config.use_llm_verification is False

    @patch.dict(os.environ, {"DEDUPE_USE_LLM": "FALSE"})
    def test_env_var_case_insensitive(self):
        """Test case-insensitive boolean parsing."""
        config = load_dedupe_config()
        assert config.use_llm_verification is False


class TestConfigIntegration:
    """Test configuration integration with dedupe module."""

    def test_config_affects_matching(self):
        """Test that config values affect matching behavior."""
        from leadfactory.pipeline.dedupe_unified import LevenshteinMatcher

        # Test with different thresholds
        matcher1 = LevenshteinMatcher(threshold=0.8)
        matcher2 = LevenshteinMatcher(threshold=0.9)

        str1 = "Business Name"
        str2 = "Business Nam"  # One character different

        # Should match with lower threshold
        assert matcher1.is_match(str1, str2) is True

        # Might not match with higher threshold
        similarity = matcher1.calculate_similarity(str1, str2)
        if similarity < 0.9:
            assert matcher2.is_match(str1, str2) is False

    def test_config_serialization_roundtrip(self):
        """Test that config can be serialized and deserialized."""
        original_config = DedupeConfig(
            name_similarity_threshold=0.87,
            batch_size=123,
            source_priorities={"test": 5},
            matching_fields=["name", "custom_field"],
        )

        # Convert to dict and back
        config_dict = original_config.to_dict()
        restored_config = DedupeConfig.from_dict(config_dict)

        assert (
            restored_config.name_similarity_threshold
            == original_config.name_similarity_threshold
        )
        assert restored_config.batch_size == original_config.batch_size
        assert restored_config.source_priorities == original_config.source_priorities
        assert restored_config.matching_fields == original_config.matching_fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
