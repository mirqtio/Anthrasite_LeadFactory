"""
Deduplication configuration settings.

This module provides configuration options for the deduplication process,
including thresholds, matching rules, and processing options.
"""

import contextlib
import json
import os
from typing import Any, Dict, List, Optional


class DedupeConfig:
    """Configuration for deduplication process."""

    def __init__(
        self,
        name_similarity_threshold: float = 0.85,
        address_similarity_threshold: float = 0.80,
        phone_match_boost: float = 0.2,
        batch_size: int = 100,
        max_pairs_per_run: Optional[int] = None,
        use_llm_verification: bool = False,
        dry_run: bool = False,
        llm_model: str = "llama2",
        llm_base_url: str = "http://localhost:11434",
        llm_confidence_threshold: float = 0.8,
        llm_timeout: int = 30,
        source_priorities: Optional[dict[str, int]] = None,
        matching_fields: Optional[list[str]] = None,
        merge_fields: Optional[list[str]] = None,
        auto_flag_low_confidence: bool = True,
        low_confidence_threshold: float = 0.5,
        flag_same_name_different_address: bool = True,
        conflict_resolution_rules: Optional[dict[str, str]] = None,
        enable_manual_review: bool = True,
        manual_review_fields: Optional[list[str]] = None,
    ):
        """Initialize deduplication configuration."""
        # Similarity thresholds
        self.name_similarity_threshold = name_similarity_threshold
        self.address_similarity_threshold = address_similarity_threshold
        self.phone_match_boost = phone_match_boost

        # Processing options
        self.batch_size = batch_size
        self.max_pairs_per_run = max_pairs_per_run
        self.use_llm_verification = use_llm_verification
        self.dry_run = dry_run

        # LLM settings
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.llm_confidence_threshold = llm_confidence_threshold
        self.llm_timeout = llm_timeout

        # Source priorities for quality-based conflict resolution
        self.source_priorities = source_priorities or {
            "manual": 100,
            "verified": 90,
            "google": 80,
            "yelp": 70,
            "scraped": 60,
            "imported": 50,
            "unknown": 0,
        }

        # Fields to consider for matching
        self.matching_fields = matching_fields or [
            "name",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "zip",
        ]

        # Fields to merge when combining records
        self.merge_fields = merge_fields or [
            "phone",
            "email",
            "website",
            "category",
            "google_response",
            "yelp_response",
            "manual_response",
        ]

        # Flagging options
        self.auto_flag_low_confidence = auto_flag_low_confidence
        self.low_confidence_threshold = low_confidence_threshold
        self.flag_same_name_different_address = flag_same_name_different_address

        # Conflict resolution settings
        self.conflict_resolution_rules = conflict_resolution_rules or {}
        self.enable_manual_review = enable_manual_review
        self.manual_review_fields = manual_review_fields or [
            "name",
            "phone",
            "email",
            "address",
        ]

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "DedupeConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "name_similarity_threshold": self.name_similarity_threshold,
            "address_similarity_threshold": self.address_similarity_threshold,
            "phone_match_boost": self.phone_match_boost,
            "batch_size": self.batch_size,
            "max_pairs_per_run": self.max_pairs_per_run,
            "use_llm_verification": self.use_llm_verification,
            "dry_run": self.dry_run,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "llm_confidence_threshold": self.llm_confidence_threshold,
            "llm_timeout": self.llm_timeout,
            "source_priorities": self.source_priorities,
            "matching_fields": self.matching_fields,
            "merge_fields": self.merge_fields,
            "auto_flag_low_confidence": self.auto_flag_low_confidence,
            "low_confidence_threshold": self.low_confidence_threshold,
            "flag_same_name_different_address": self.flag_same_name_different_address,
            "conflict_resolution_rules": self.conflict_resolution_rules,
            "enable_manual_review": self.enable_manual_review,
            "manual_review_fields": self.manual_review_fields,
        }


# Default configuration
DEFAULT_DEDUPE_CONFIG = DedupeConfig()


def load_dedupe_config(config_path: Optional[str] = None) -> DedupeConfig:
    """
    Load deduplication configuration from file or environment.

    Args:
        config_path: Optional path to JSON configuration file

    Returns:
        DedupeConfig instance
    """
    config_dict = {}

    # Load from file if provided
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config_dict = json.load(f)
        except Exception:
            pass

    # Override with environment variables
    env_mappings = {
        "DEDUPE_NAME_THRESHOLD": ("name_similarity_threshold", float),
        "DEDUPE_ADDRESS_THRESHOLD": ("address_similarity_threshold", float),
        "DEDUPE_PHONE_BOOST": ("phone_match_boost", float),
        "DEDUPE_BATCH_SIZE": ("batch_size", int),
        "DEDUPE_MAX_PAIRS": ("max_pairs_per_run", lambda x: int(x) if x else None),
        "DEDUPE_USE_LLM": ("use_llm_verification", lambda x: x.lower() == "true"),
        "DEDUPE_DRY_RUN": ("dry_run", lambda x: x.lower() == "true"),
        "DEDUPE_LLM_MODEL": ("llm_model", str),
        "DEDUPE_LLM_URL": ("llm_base_url", str),
        "DEDUPE_LLM_THRESHOLD": ("llm_confidence_threshold", float),
        "DEDUPE_LLM_TIMEOUT": ("llm_timeout", int),
    }

    for env_var, (config_key, converter) in env_mappings.items():
        if env_var in os.environ:
            with contextlib.suppress(Exception):
                config_dict[config_key] = converter(os.environ[env_var])

    return DedupeConfig.from_dict(config_dict) if config_dict else DEFAULT_DEDUPE_CONFIG
