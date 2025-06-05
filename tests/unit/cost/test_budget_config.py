"""
Unit tests for Budget Configuration System.

Tests the comprehensive budget configuration system including:
- Budget limit management
- Alert threshold configuration
- Multiple configuration sources (env, file, database)
- Validation and error handling
- Runtime updates and persistence
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.cost.budget_config import (
    AlertLevel,
    AlertThreshold,
    BudgetConfiguration,
    BudgetConfigurationError,
    BudgetLimit,
    BudgetPeriod,
    get_budget_config,
    reset_budget_config,
)


class TestBudgetLimit:
    """Test BudgetLimit dataclass."""

    def test_budget_limit_creation(self):
        """Test creating a budget limit."""
        limit = BudgetLimit(
            amount=100.0,
            period=BudgetPeriod.DAILY,
            model="gpt-4o",
            endpoint="/chat/completions",
            description="Daily limit for GPT-4o",
        )

        assert limit.amount == 100.0
        assert limit.period == BudgetPeriod.DAILY
        assert limit.model == "gpt-4o"
        assert limit.endpoint == "/chat/completions"
        assert limit.description == "Daily limit for GPT-4o"

    def test_budget_limit_string_period(self):
        """Test budget limit with string period conversion."""
        limit = BudgetLimit(amount=50.0, period="weekly")
        assert limit.period == BudgetPeriod.WEEKLY

    def test_budget_limit_validation(self):
        """Test budget limit validation."""
        with pytest.raises(ValueError, match="Budget amount must be positive"):
            BudgetLimit(amount=-10.0, period=BudgetPeriod.DAILY)

        with pytest.raises(ValueError, match="Budget amount must be positive"):
            BudgetLimit(amount=0.0, period=BudgetPeriod.MONTHLY)


class TestAlertThreshold:
    """Test AlertThreshold dataclass."""

    def test_alert_threshold_creation(self):
        """Test creating an alert threshold."""
        threshold = AlertThreshold(
            level=AlertLevel.WARNING, percentage=0.8, enabled=True
        )

        assert threshold.level == AlertLevel.WARNING
        assert threshold.percentage == 0.8
        assert threshold.enabled is True

    def test_alert_threshold_string_level(self):
        """Test alert threshold with string level conversion."""
        threshold = AlertThreshold(level="warning", percentage=0.75)
        assert threshold.level == AlertLevel.WARNING

    def test_alert_threshold_validation(self):
        """Test alert threshold validation."""
        with pytest.raises(
            ValueError, match="Alert percentage must be between 0 and 1"
        ):
            AlertThreshold(level=AlertLevel.WARNING, percentage=1.5)

        with pytest.raises(
            ValueError, match="Alert percentage must be between 0 and 1"
        ):
            AlertThreshold(level=AlertLevel.CRITICAL, percentage=0.0)


class TestBudgetConfiguration:
    """Test BudgetConfiguration class."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_budget.db")
        self.config_file = os.path.join(self.temp_dir, "test_config.json")

        # Reset global config for clean tests
        reset_budget_config()

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_budget_config()

    def test_initialization(self):
        """Test budget configuration initialization."""
        config = BudgetConfiguration(db_path=self.db_path)

        assert config.db_path == self.db_path
        assert config.is_enabled() is True
        assert (
            len(config.get_all_alert_thresholds()) == 2
        )  # Default warning and critical

        # Check default thresholds
        warning = config.get_alert_threshold(AlertLevel.WARNING)
        critical = config.get_alert_threshold(AlertLevel.CRITICAL)

        assert warning.percentage == 0.8
        assert critical.percentage == 0.95
        assert warning.enabled is True
        assert critical.enabled is True

    def test_database_initialization(self):
        """Test database table creation."""
        BudgetConfiguration(db_path=self.db_path)

        # Check that tables were created
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('budget_limits', 'alert_thresholds', 'config_settings')
            """)
            tables = [row[0] for row in cursor.fetchall()]

        assert "budget_limits" in tables
        assert "alert_thresholds" in tables
        assert "config_settings" in tables

    def test_add_budget_limit(self):
        """Test adding budget limits."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Add daily limit
        budget_id = config.add_budget_limit(
            amount=100.0,
            period=BudgetPeriod.DAILY,
            model="gpt-4o",
            description="Daily GPT-4o limit",
        )

        assert budget_id == "daily_gpt-4o"

        # Retrieve and verify
        limit = config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit is not None
        assert limit.amount == 100.0
        assert limit.period == BudgetPeriod.DAILY
        assert limit.model == "gpt-4o"
        assert limit.description == "Daily GPT-4o limit"

    def test_budget_limit_fallback(self):
        """Test budget limit fallback matching."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Add general daily limit
        config.add_budget_limit(amount=200.0, period=BudgetPeriod.DAILY)

        # Add model-specific limit
        config.add_budget_limit(
            amount=50.0, period=BudgetPeriod.DAILY, model="gpt-3.5-turbo"
        )

        # Test exact match
        limit = config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-3.5-turbo")
        assert limit.amount == 50.0

        # Test fallback to general limit
        limit = config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit.amount == 200.0

        # Test no match
        limit = config.get_budget_limit(BudgetPeriod.WEEKLY, model="gpt-4o")
        assert limit is None

    def test_remove_budget_limit(self):
        """Test removing budget limits."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Add and then remove
        config.add_budget_limit(amount=100.0, period=BudgetPeriod.DAILY, model="gpt-4o")

        assert config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o") is not None

        removed = config.remove_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert removed is True

        assert config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o") is None

        # Try to remove non-existent limit
        removed = config.remove_budget_limit(BudgetPeriod.WEEKLY, model="gpt-4o")
        assert removed is False

    def test_alert_thresholds(self):
        """Test alert threshold management."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Set custom warning threshold
        config.set_alert_threshold(AlertLevel.WARNING, 0.75)

        threshold = config.get_alert_threshold(AlertLevel.WARNING)
        assert threshold.percentage == 0.75
        assert threshold.enabled is True

        # Set disabled critical threshold
        config.set_alert_threshold(AlertLevel.CRITICAL, 0.9, enabled=False)

        threshold = config.get_alert_threshold(AlertLevel.CRITICAL)
        assert threshold.percentage == 0.9
        assert threshold.enabled is False

    def test_global_enabled_setting(self):
        """Test global enabled/disabled setting."""
        config = BudgetConfiguration(db_path=self.db_path)

        assert config.is_enabled() is True

        config.set_enabled(False)
        assert config.is_enabled() is False

        config.set_enabled(True)
        assert config.is_enabled() is True

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "BUDGET_ENABLED": "false",
            "BUDGET_LIMIT_DAILY_GPT4O_CHAT": "150.0",
            "BUDGET_LIMIT_WEEKLY_ALL_ALL": "500.0",
            "BUDGET_WARNING_THRESHOLD": "0.85",
            "BUDGET_CRITICAL_THRESHOLD": "0.98",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = BudgetConfiguration(db_path=self.db_path)

            # Check global setting
            assert config.is_enabled() is False

            # Check budget limits
            daily_limit = config.get_budget_limit(
                BudgetPeriod.DAILY, model="gpt4o", endpoint="chat"
            )
            assert daily_limit is not None
            assert daily_limit.amount == 150.0

            weekly_limit = config.get_budget_limit(BudgetPeriod.WEEKLY)
            assert weekly_limit is not None
            assert weekly_limit.amount == 500.0

            # Check alert thresholds
            warning = config.get_alert_threshold(AlertLevel.WARNING)
            critical = config.get_alert_threshold(AlertLevel.CRITICAL)

            assert warning.percentage == 0.85
            assert critical.percentage == 0.98

    def test_file_configuration_loading(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "enabled": True,
            "budget_limits": [
                {
                    "amount": 75.0,
                    "period": "daily",
                    "model": "gpt-3.5-turbo",
                    "description": "Daily GPT-3.5 limit",
                },
                {
                    "amount": 300.0,
                    "period": "monthly",
                    "description": "Monthly total limit",
                },
            ],
            "alert_thresholds": [
                {"level": "warning", "percentage": 0.7, "enabled": True},
                {"level": "critical", "percentage": 0.9, "enabled": True},
            ],
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        config = BudgetConfiguration(config_file=self.config_file, db_path=self.db_path)

        # Check budget limits
        daily_limit = config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-3.5-turbo")
        assert daily_limit is not None
        assert daily_limit.amount == 75.0

        monthly_limit = config.get_budget_limit(BudgetPeriod.MONTHLY)
        assert monthly_limit is not None
        assert monthly_limit.amount == 300.0

        # Check alert thresholds
        warning = config.get_alert_threshold(AlertLevel.WARNING)
        critical = config.get_alert_threshold(AlertLevel.CRITICAL)

        assert warning.percentage == 0.7
        assert critical.percentage == 0.9

    def test_database_persistence(self):
        """Test database persistence of configuration."""
        # Create config and add data
        config1 = BudgetConfiguration(db_path=self.db_path)
        config1.add_budget_limit(
            amount=100.0, period=BudgetPeriod.DAILY, model="gpt-4o"
        )
        config1.set_alert_threshold(AlertLevel.WARNING, 0.75)
        config1.set_enabled(False)

        # Create new config instance and verify persistence
        config2 = BudgetConfiguration(db_path=self.db_path)

        limit = config2.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit is not None
        assert limit.amount == 100.0

        threshold = config2.get_alert_threshold(AlertLevel.WARNING)
        assert threshold.percentage == 0.75

        assert config2.is_enabled() is False

    def test_configuration_validation(self):
        """Test configuration validation."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Add valid configuration
        config.add_budget_limit(amount=100.0, period=BudgetPeriod.DAILY)
        config.set_alert_threshold(AlertLevel.WARNING, 0.8)
        config.set_alert_threshold(AlertLevel.CRITICAL, 0.95)

        issues = config.validate_configuration()
        assert len(issues) == 0

        # Add invalid configuration
        config.set_alert_threshold(AlertLevel.WARNING, 0.98)  # Higher than critical

        issues = config.validate_configuration()
        assert len(issues) > 0
        assert any(
            "Warning threshold must be less than critical threshold" in issue
            for issue in issues
        )

    def test_export_import_configuration(self):
        """Test configuration export and import."""
        config1 = BudgetConfiguration(db_path=self.db_path)

        # Add some configuration
        config1.add_budget_limit(
            amount=100.0, period=BudgetPeriod.DAILY, model="gpt-4o"
        )
        config1.add_budget_limit(amount=500.0, period=BudgetPeriod.WEEKLY)
        config1.set_alert_threshold(AlertLevel.WARNING, 0.75)
        config1.set_enabled(False)

        # Export configuration
        exported = config1.export_configuration()

        assert exported["enabled"] is False
        assert len(exported["budget_limits"]) == 2
        assert len(exported["alert_thresholds"]) == 2
        assert "exported_at" in exported

        # Create new config and import
        config2 = BudgetConfiguration(db_path=os.path.join(self.temp_dir, "test2.db"))
        config2.import_configuration(exported)

        # Verify imported configuration
        assert config2.is_enabled() is False

        limit = config2.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit is not None
        assert limit.amount == 100.0

        weekly_limit = config2.get_budget_limit(BudgetPeriod.WEEKLY)
        assert weekly_limit is not None
        assert weekly_limit.amount == 500.0

        threshold = config2.get_alert_threshold(AlertLevel.WARNING)
        assert threshold.percentage == 0.75

    def test_error_handling(self):
        """Test error handling in configuration."""
        # Test invalid database path
        with pytest.raises(BudgetConfigurationError):
            BudgetConfiguration(db_path="/invalid/path/budget.db")

        # Test invalid import data
        config = BudgetConfiguration(db_path=self.db_path)

        invalid_data = {
            "budget_limits": [
                {
                    "amount": -50.0,  # Invalid negative amount
                    "period": "daily",
                }
            ]
        }

        with pytest.raises(BudgetConfigurationError):
            config.import_configuration(invalid_data)


class TestGlobalBudgetConfig:
    """Test global budget configuration functions."""

    def setup_method(self):
        """Set up test environment."""
        reset_budget_config()

    def teardown_method(self):
        """Clean up test environment."""
        reset_budget_config()

    def test_singleton_pattern(self):
        """Test that get_budget_config returns singleton instance."""
        config1 = get_budget_config()
        config2 = get_budget_config()

        assert config1 is config2
        assert isinstance(config1, BudgetConfiguration)

    def test_reset_global_config(self):
        """Test resetting global configuration."""
        # Use a temporary database for this test
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test_reset.db")

            # Create first config instance
            config1 = BudgetConfiguration(db_path=db_path)
            config1.add_budget_limit(amount=100.0, period=BudgetPeriod.DAILY)

            # Reset global config
            reset_budget_config()

            # Create new config instance with fresh database
            db_path2 = os.path.join(temp_dir, "test_reset2.db")
            config2 = BudgetConfiguration(db_path=db_path2)

            # Should be a new instance with no budget limits
            assert config2 is not config1
            assert len(config2.get_all_budget_limits()) == 0


class TestConfigurationIntegration:
    """Test integration scenarios for budget configuration."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_budget.db")
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        reset_budget_config()

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_budget_config()

    def test_configuration_source_priority(self):
        """Test that environment variables override file and database."""
        # Create database with some data
        config1 = BudgetConfiguration(db_path=self.db_path)
        config1.add_budget_limit(amount=100.0, period=BudgetPeriod.DAILY)
        config1.set_enabled(True)

        # Create config file with different data
        config_data = {
            "enabled": False,
            "budget_limits": [
                {"amount": 200.0, "period": "daily", "description": "File limit"}
            ],
        }

        with open(self.config_file, "w") as f:
            json.dump(config_data, f)

        # Set environment variables with different data
        env_vars = {"BUDGET_ENABLED": "true", "BUDGET_LIMIT_DAILY_ALL_ALL": "300.0"}

        with patch.dict(os.environ, env_vars, clear=False):
            config2 = BudgetConfiguration(
                config_file=self.config_file, db_path=self.db_path
            )

            # Environment should override everything
            assert config2.is_enabled() is True  # Environment override

            limit = config2.get_budget_limit(BudgetPeriod.DAILY)
            assert limit.amount == 300.0  # Environment override
            assert "Environment variable" in limit.description

    def test_runtime_configuration_updates(self):
        """Test runtime configuration updates and persistence."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Add initial configuration
        config.add_budget_limit(amount=100.0, period=BudgetPeriod.DAILY, model="gpt-4o")

        # Update configuration at runtime
        config.add_budget_limit(
            amount=150.0, period=BudgetPeriod.DAILY, model="gpt-4o"
        )  # Override
        config.set_alert_threshold(AlertLevel.WARNING, 0.85)

        # Verify updates
        limit = config.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit.amount == 150.0

        threshold = config.get_alert_threshold(AlertLevel.WARNING)
        assert threshold.percentage == 0.85

        # Create new instance to verify persistence
        config2 = BudgetConfiguration(db_path=self.db_path)

        limit2 = config2.get_budget_limit(BudgetPeriod.DAILY, model="gpt-4o")
        assert limit2.amount == 150.0

        threshold2 = config2.get_alert_threshold(AlertLevel.WARNING)
        assert threshold2.percentage == 0.85

    def test_complex_budget_hierarchy(self):
        """Test complex budget limit hierarchy and fallbacks."""
        config = BudgetConfiguration(db_path=self.db_path)

        # Set up hierarchy: general -> model-specific -> endpoint-specific
        config.add_budget_limit(amount=1000.0, period=BudgetPeriod.MONTHLY)  # General
        config.add_budget_limit(
            amount=300.0, period=BudgetPeriod.MONTHLY, model="gpt-4o"
        )  # Model-specific
        config.add_budget_limit(
            amount=100.0,
            period=BudgetPeriod.MONTHLY,
            model="gpt-4o",
            endpoint="/chat/completions",
        )  # Endpoint-specific

        # Test most specific match
        limit = config.get_budget_limit(
            BudgetPeriod.MONTHLY, model="gpt-4o", endpoint="/chat/completions"
        )
        assert limit.amount == 100.0

        # Test model fallback
        limit = config.get_budget_limit(
            BudgetPeriod.MONTHLY, model="gpt-4o", endpoint="/embeddings"
        )
        assert limit.amount == 300.0

        # Test general fallback
        limit = config.get_budget_limit(BudgetPeriod.MONTHLY, model="gpt-3.5-turbo")
        assert limit.amount == 1000.0

        # Test no match
        limit = config.get_budget_limit(BudgetPeriod.WEEKLY, model="gpt-4o")
        assert limit is None
