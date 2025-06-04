"""
Budget Configuration System for GPT BudgetGuard Middleware.

This module provides a comprehensive configuration system for managing budget limits
at different levels (daily, weekly, monthly) and for different API endpoints or models.
Supports loading from environment variables, config files, and database with validation
and runtime updates.
"""

import json
import logging
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class BudgetPeriod(Enum):
    """Budget period types."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AlertLevel(Enum):
    """Alert threshold levels."""

    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BudgetLimit:
    """Represents a budget limit configuration."""

    amount: float
    period: BudgetPeriod
    model: Optional[str] = None
    endpoint: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Validate budget limit after initialization."""
        if self.amount <= 0:
            raise ValueError("Budget amount must be positive")
        if isinstance(self.period, str):
            self.period = BudgetPeriod(self.period)


@dataclass
class AlertThreshold:
    """Represents an alert threshold configuration."""

    level: AlertLevel
    percentage: float
    enabled: bool = True

    def __post_init__(self):
        """Validate alert threshold after initialization."""
        if isinstance(self.level, str):
            self.level = AlertLevel(self.level)
        if not 0 < self.percentage <= 1:
            raise ValueError("Alert percentage must be between 0 and 1")


class BudgetConfigurationError(Exception):
    """Exception raised for budget configuration errors."""

    pass


class BudgetConfiguration:
    """
    Budget configuration system that manages budget limits and alert thresholds.

    Supports loading configuration from multiple sources:
    - Environment variables
    - JSON configuration files
    - SQLite database

    Features:
    - Multiple budget periods (daily, weekly, monthly)
    - Model-specific and endpoint-specific budgets
    - Alert thresholds with warning and critical levels
    - Runtime configuration updates
    - Thread-safe operations
    """

    def __init__(
        self, config_file: Optional[str] = None, db_path: Optional[str] = None
    ):
        """
        Initialize budget configuration system.

        Args:
            config_file: Path to JSON configuration file
            db_path: Path to SQLite database for persistent storage
        """
        self.config_file = config_file or os.getenv("BUDGET_CONFIG_FILE")
        self.db_path = db_path or os.getenv("BUDGET_DB_PATH", "budget_config.db")

        self._lock = threading.RLock()
        self._budget_limits: Dict[str, BudgetLimit] = {}
        self._alert_thresholds: Dict[AlertLevel, AlertThreshold] = {}
        self._global_enabled = True

        # Initialize default alert thresholds
        self._set_default_thresholds()

        # Initialize database
        self._init_database()

        # Load configuration from all sources
        self._load_configuration()

    def _set_default_thresholds(self):
        """Set default alert thresholds."""
        self._alert_thresholds[AlertLevel.WARNING] = AlertThreshold(
            level=AlertLevel.WARNING, percentage=0.8
        )
        self._alert_thresholds[AlertLevel.CRITICAL] = AlertThreshold(
            level=AlertLevel.CRITICAL, percentage=0.95
        )

    def _init_database(self):
        """Initialize SQLite database for configuration storage."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS budget_limits (
                        id TEXT PRIMARY KEY,
                        amount REAL NOT NULL,
                        period TEXT NOT NULL,
                        model TEXT,
                        endpoint TEXT,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alert_thresholds (
                        level TEXT PRIMARY KEY,
                        percentage REAL NOT NULL,
                        enabled BOOLEAN DEFAULT TRUE,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS config_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.commit()
                logger.info(
                    f"Initialized budget configuration database: {self.db_path}"
                )
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise BudgetConfigurationError(f"Database initialization failed: {e}")

    def _load_configuration(self):
        """Load configuration from all available sources."""
        # Load from database first (persistent storage)
        self._load_from_database()

        # Load from config file (overrides database)
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file()

        # Load from environment variables (overrides everything)
        self._load_from_environment()

        logger.info(
            f"Loaded budget configuration with {len(self._budget_limits)} limits"
        )

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        # Global settings
        if os.getenv("BUDGET_ENABLED"):
            self._global_enabled = os.getenv("BUDGET_ENABLED", "true").lower() == "true"

        # Budget limits from environment
        # Format: BUDGET_LIMIT_<PERIOD>_<MODEL>_<ENDPOINT>=amount
        for key, value in os.environ.items():
            if key.startswith("BUDGET_LIMIT_"):
                try:
                    parts = key[13:].split("_")  # Remove 'BUDGET_LIMIT_' prefix
                    if len(parts) >= 1:
                        period = parts[0].lower()
                        model = (
                            parts[1].lower()
                            if len(parts) > 1 and parts[1] != "ALL"
                            else None
                        )
                        endpoint = (
                            parts[2].lower()
                            if len(parts) > 2 and parts[2] != "ALL"
                            else None
                        )

                        budget_id = self._generate_budget_id(period, model, endpoint)
                        budget_limit = BudgetLimit(
                            amount=float(value),
                            period=BudgetPeriod(period),
                            model=model,
                            endpoint=endpoint,
                            description=f"Environment variable: {key}",
                        )

                        with self._lock:
                            self._budget_limits[budget_id] = budget_limit

                        logger.info(
                            f"Loaded budget limit from environment: {budget_id} = ${value}"
                        )
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid environment budget limit {key}: {e}")

        # Alert thresholds from environment
        warning_threshold = os.getenv("BUDGET_WARNING_THRESHOLD")
        if warning_threshold:
            try:
                self._alert_thresholds[AlertLevel.WARNING].percentage = float(
                    warning_threshold
                )
            except ValueError:
                logger.warning(f"Invalid warning threshold: {warning_threshold}")

        critical_threshold = os.getenv("BUDGET_CRITICAL_THRESHOLD")
        if critical_threshold:
            try:
                self._alert_thresholds[AlertLevel.CRITICAL].percentage = float(
                    critical_threshold
                )
            except ValueError:
                logger.warning(f"Invalid critical threshold: {critical_threshold}")

    def _load_from_file(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_file) as f:
                config_data = json.load(f)

            # Load global settings
            if "enabled" in config_data:
                self._global_enabled = config_data["enabled"]

            # Load budget limits
            if "budget_limits" in config_data:
                for limit_config in config_data["budget_limits"]:
                    budget_limit = BudgetLimit(**limit_config)
                    budget_id = self._generate_budget_id(
                        budget_limit.period.value,
                        budget_limit.model,
                        budget_limit.endpoint,
                    )

                    with self._lock:
                        self._budget_limits[budget_id] = budget_limit

            # Load alert thresholds
            if "alert_thresholds" in config_data:
                for threshold_config in config_data["alert_thresholds"]:
                    threshold = AlertThreshold(**threshold_config)
                    self._alert_thresholds[threshold.level] = threshold

            logger.info(f"Loaded configuration from file: {self.config_file}")
        except Exception as e:
            logger.error(
                f"Failed to load configuration from file {self.config_file}: {e}"
            )

    def _load_from_database(self):
        """Load configuration from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Load budget limits
                cursor = conn.execute(
                    """
                    SELECT id, amount, period, model, endpoint, description
                    FROM budget_limits
                """
                )

                for row in cursor.fetchall():
                    budget_id, amount, period, model, endpoint, description = row
                    budget_limit = BudgetLimit(
                        amount=amount,
                        period=BudgetPeriod(period),
                        model=model,
                        endpoint=endpoint,
                        description=description,
                    )

                    with self._lock:
                        self._budget_limits[budget_id] = budget_limit

                # Load alert thresholds
                cursor = conn.execute(
                    """
                    SELECT level, percentage, enabled
                    FROM alert_thresholds
                """
                )

                for row in cursor.fetchall():
                    level_str, percentage, enabled = row
                    try:
                        level = AlertLevel(level_str)
                        threshold = AlertThreshold(
                            level=level, percentage=percentage, enabled=bool(enabled)
                        )
                        self._alert_thresholds[level] = threshold
                    except ValueError as e:
                        logger.warning(
                            f"Invalid alert level in database: {level_str} - {e}"
                        )
                        continue

                # Load global settings
                cursor = conn.execute(
                    """
                    SELECT value FROM config_settings WHERE key = 'global_enabled'
                """
                )
                result = cursor.fetchone()
                if result:
                    self._global_enabled = result[0].lower() == "true"

        except Exception as e:
            logger.error(f"Failed to load configuration from database: {e}")

    def _generate_budget_id(
        self, period: str, model: Optional[str], endpoint: Optional[str]
    ) -> str:
        """Generate a unique budget ID from period, model, and endpoint."""
        parts = [period]
        if model:
            parts.append(model)
        if endpoint:
            parts.append(endpoint)
        return "_".join(parts)

    def add_budget_limit(
        self,
        amount: float,
        period: BudgetPeriod,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        description: Optional[str] = None,
        persist: bool = True,
    ) -> str:
        """
        Add a new budget limit.

        Args:
            amount: Budget amount in dollars
            period: Budget period (daily, weekly, monthly)
            model: Specific model name (optional)
            endpoint: Specific endpoint (optional)
            description: Description of the budget limit
            persist: Whether to persist to database

        Returns:
            Budget ID for the created limit
        """
        budget_limit = BudgetLimit(
            amount=amount,
            period=period,
            model=model,
            endpoint=endpoint,
            description=description,
        )

        budget_id = self._generate_budget_id(period.value, model, endpoint)

        with self._lock:
            self._budget_limits[budget_id] = budget_limit

        if persist:
            self._persist_budget_limit(budget_id, budget_limit)

        logger.info(f"Added budget limit: {budget_id} = ${amount} per {period.value}")
        return budget_id

    def _persist_budget_limit(self, budget_id: str, budget_limit: BudgetLimit):
        """Persist budget limit to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO budget_limits
                    (id, amount, period, model, endpoint, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        budget_id,
                        budget_limit.amount,
                        budget_limit.period.value,
                        budget_limit.model,
                        budget_limit.endpoint,
                        budget_limit.description,
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist budget limit {budget_id}: {e}")

    def get_budget_limit(
        self,
        period: BudgetPeriod,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Optional[BudgetLimit]:
        """
        Get budget limit for specific criteria.

        Args:
            period: Budget period
            model: Model name (optional)
            endpoint: Endpoint (optional)

        Returns:
            BudgetLimit if found, None otherwise
        """
        budget_id = self._generate_budget_id(period.value, model, endpoint)

        with self._lock:
            # Try exact match first
            if budget_id in self._budget_limits:
                return self._budget_limits[budget_id]

            # Try fallback matches (less specific)
            fallback_ids = [
                self._generate_budget_id(period.value, model, None),  # Without endpoint
                self._generate_budget_id(period.value, None, endpoint),  # Without model
                self._generate_budget_id(period.value, None, None),  # Period only
            ]

            for fallback_id in fallback_ids:
                if fallback_id in self._budget_limits:
                    return self._budget_limits[fallback_id]

        return None

    def get_all_budget_limits(self) -> Dict[str, BudgetLimit]:
        """Get all configured budget limits."""
        with self._lock:
            return self._budget_limits.copy()

    def remove_budget_limit(
        self,
        period: BudgetPeriod,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        persist: bool = True,
    ) -> bool:
        """
        Remove a budget limit.

        Args:
            period: Budget period
            model: Model name (optional)
            endpoint: Endpoint (optional)
            persist: Whether to persist removal to database

        Returns:
            True if limit was removed, False if not found
        """
        budget_id = self._generate_budget_id(period.value, model, endpoint)

        with self._lock:
            if budget_id in self._budget_limits:
                del self._budget_limits[budget_id]

                if persist:
                    try:
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "DELETE FROM budget_limits WHERE id = ?", (budget_id,)
                            )
                            conn.commit()
                    except Exception as e:
                        logger.error(
                            f"Failed to remove budget limit from database: {e}"
                        )

                logger.info(f"Removed budget limit: {budget_id}")
                return True

        return False

    def set_alert_threshold(
        self,
        level: AlertLevel,
        percentage: float,
        enabled: bool = True,
        persist: bool = True,
    ):
        """
        Set alert threshold.

        Args:
            level: Alert level (WARNING or CRITICAL)
            percentage: Threshold percentage (0.0 to 1.0)
            enabled: Whether threshold is enabled
            persist: Whether to persist to database
        """
        threshold = AlertThreshold(level=level, percentage=percentage, enabled=enabled)
        self._alert_thresholds[level] = threshold

        if persist:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO alert_thresholds
                        (level, percentage, enabled, updated_at)
                        VALUES (?, ?, ?, ?)
                    """,
                        (level.value, percentage, enabled, datetime.now().isoformat()),
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to persist alert threshold: {e}")

        logger.info(f"Set alert threshold: {level.value} = {percentage * 100}%")

    def get_alert_threshold(self, level: AlertLevel) -> Optional[AlertThreshold]:
        """Get alert threshold for specific level."""
        return self._alert_thresholds.get(level)

    def get_all_alert_thresholds(self) -> Dict[AlertLevel, AlertThreshold]:
        """Get all alert thresholds."""
        return self._alert_thresholds.copy()

    def is_enabled(self) -> bool:
        """Check if budget system is globally enabled."""
        return self._global_enabled

    def set_enabled(self, enabled: bool, persist: bool = True):
        """
        Enable or disable budget system globally.

        Args:
            enabled: Whether to enable budget system
            persist: Whether to persist to database
        """
        self._global_enabled = enabled

        if persist:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO config_settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """,
                        (
                            "global_enabled",
                            str(enabled).lower(),
                            datetime.now().isoformat(),
                        ),
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to persist global enabled setting: {e}")

        logger.info(f"Budget system {'enabled' if enabled else 'disabled'}")

    def validate_configuration(self) -> List[str]:
        """
        Validate current configuration and return list of issues.

        Returns:
            List of validation error messages
        """
        issues = []

        with self._lock:
            # Validate budget limits
            for budget_id, limit in self._budget_limits.items():
                try:
                    if limit.amount <= 0:
                        issues.append(f"Budget {budget_id}: amount must be positive")

                    if limit.period not in BudgetPeriod:
                        issues.append(
                            f"Budget {budget_id}: invalid period {limit.period}"
                        )

                except Exception as e:
                    issues.append(f"Budget {budget_id}: validation error - {e}")

            # Validate alert thresholds
            for level, threshold in self._alert_thresholds.items():
                try:
                    if not 0 < threshold.percentage <= 1:
                        issues.append(
                            f"Alert {level.value}: percentage must be between 0 and 1"
                        )

                except Exception as e:
                    issues.append(f"Alert {level.value}: validation error - {e}")

            # Check for conflicting thresholds
            warning_pct = (
                self._alert_thresholds.get(AlertLevel.WARNING, {}).percentage or 0
            )
            critical_pct = (
                self._alert_thresholds.get(AlertLevel.CRITICAL, {}).percentage or 0
            )

            if warning_pct >= critical_pct:
                issues.append("Warning threshold must be less than critical threshold")

        return issues

    def export_configuration(self) -> Dict[str, Any]:
        """
        Export current configuration to dictionary.

        Returns:
            Configuration dictionary suitable for JSON serialization
        """
        with self._lock:
            return {
                "enabled": self._global_enabled,
                "budget_limits": [
                    {"id": budget_id, **asdict(limit)}
                    for budget_id, limit in self._budget_limits.items()
                ],
                "alert_thresholds": [
                    asdict(threshold) for threshold in self._alert_thresholds.values()
                ],
                "exported_at": datetime.now().isoformat(),
            }

    def import_configuration(self, config_data: Dict[str, Any], persist: bool = True):
        """
        Import configuration from dictionary.

        Args:
            config_data: Configuration dictionary
            persist: Whether to persist imported configuration
        """
        try:
            # Import global settings
            if "enabled" in config_data:
                self.set_enabled(config_data["enabled"], persist=persist)

            # Import budget limits
            if "budget_limits" in config_data:
                for limit_data in config_data["budget_limits"]:
                    limit_copy = limit_data.copy()
                    budget_id = limit_copy.pop("id", None)

                    # Convert period string to enum if needed
                    if "period" in limit_copy and isinstance(limit_copy["period"], str):
                        limit_copy["period"] = BudgetPeriod(limit_copy["period"])

                    budget_limit = BudgetLimit(**limit_copy)

                    if not budget_id:
                        budget_id = self._generate_budget_id(
                            budget_limit.period.value,
                            budget_limit.model,
                            budget_limit.endpoint,
                        )

                    with self._lock:
                        self._budget_limits[budget_id] = budget_limit

                    if persist:
                        self._persist_budget_limit(budget_id, budget_limit)

            # Import alert thresholds
            if "alert_thresholds" in config_data:
                for threshold_data in config_data["alert_thresholds"]:
                    # Convert level string to enum if needed
                    threshold_copy = threshold_data.copy()
                    if "level" in threshold_copy and isinstance(
                        threshold_copy["level"], str
                    ):
                        threshold_copy["level"] = AlertLevel(threshold_copy["level"])

                    threshold = AlertThreshold(**threshold_copy)
                    self.set_alert_threshold(
                        threshold.level,
                        threshold.percentage,
                        threshold.enabled,
                        persist=persist,
                    )

            logger.info("Successfully imported budget configuration")

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            raise BudgetConfigurationError(f"Import failed: {e}")


# Global budget configuration instance
_global_budget_config: Optional[BudgetConfiguration] = None
_config_lock = threading.Lock()


def get_budget_config() -> BudgetConfiguration:
    """
    Get global budget configuration instance (singleton pattern).

    Returns:
        BudgetConfiguration instance
    """
    global _global_budget_config

    if _global_budget_config is None:
        with _config_lock:
            if _global_budget_config is None:
                _global_budget_config = BudgetConfiguration()

    return _global_budget_config


def reset_budget_config():
    """Reset global budget configuration (mainly for testing)."""
    global _global_budget_config
    with _config_lock:
        _global_budget_config = None
