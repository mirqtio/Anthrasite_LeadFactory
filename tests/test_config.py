"""
Test the centralized configuration module.
"""

import os
from unittest import mock

import pytest

# The following import will be used once we start using the config module in the codebase
# from leadfactory import config


def test_config_loads_environment_variables():
    """Test that the config module correctly loads environment variables."""
    # Mock environment variables for testing
    test_env = {
        "TIER": "2",
        "OPENAI_API_KEY": "test-key-123",
        "MAX_COST_PER_LEAD": "0.75",
        "MONTHLY_BUDGET": "500.0",
    }

    with mock.patch.dict(os.environ, test_env):
        # Re-import to load the mocked environment variables
        from importlib import reload

        from leadfactory import config

        reload(config)

        # Check that environment variables are correctly loaded
        assert config.TIER == 2
        assert config.OPENAI_API_KEY == "test-key-123"
        assert config.MAX_COST_PER_LEAD == 0.75
        assert config.MONTHLY_BUDGET == 500.0


def test_config_provides_default_values():
    """Test that the config module provides default values for missing environment variables."""
    # Mock environment with missing variables
    test_env = {"TIER": "1"}  # Only set TIER

    with mock.patch.dict(os.environ, test_env, clear=True):
        # Re-import to load the mocked environment variables
        from importlib import reload

        from leadfactory import config

        reload(config)

        # Check that default values are correctly provided
        assert config.TIER == 1
        assert config.MAX_LEADS_PER_BATCH == 100
        assert config.BUDGET_ALERT_THRESHOLD == 0.8
        assert config.LOG_LEVEL == "INFO"
        assert config.DATA_RETENTION_DAYS == 90


def test_tiered_value_helper():
    """Test the get_tiered_value helper function."""
    from leadfactory import config

    # Test with all tiers specified
    assert config.get_tiered_value("basic", "advanced", "premium") == "basic"

    with mock.patch.object(config, "TIER", 2):
        assert config.get_tiered_value("basic", "advanced", "premium") == "advanced"

    with mock.patch.object(config, "TIER", 3):
        assert config.get_tiered_value("basic", "advanced", "premium") == "premium"

    # Test with defaults
    assert config.get_tiered_value("basic") == "basic"

    with mock.patch.object(config, "TIER", 2):
        assert config.get_tiered_value("basic") == "basic"

    with mock.patch.object(config, "TIER", 3):
        assert config.get_tiered_value("basic") == "basic"


def test_environment_helpers():
    """Test the environment helper functions."""
    from leadfactory import config

    # Test production environment
    with mock.patch.object(config, "ENVIRONMENT", "production"):
        assert config.is_production() is True
        assert config.is_development() is False
        assert config.is_staging() is False

    # Test development environment
    with mock.patch.object(config, "ENVIRONMENT", "development"):
        assert config.is_production() is False
        assert config.is_development() is True
        assert config.is_staging() is False

    # Test staging environment
    with mock.patch.object(config, "ENVIRONMENT", "staging"):
        assert config.is_production() is False
        assert config.is_development() is False
        assert config.is_staging() is True
