"""
Configuration loader for LeadFactory.

This module provides functions for loading and accessing configuration
from environment variables, with caching for efficiency.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Removed circular import

# Centralized config dictionary cache
_config_cache = None


def load_config(env_file: Optional[str] = None) -> dict[str, Any]:
    """
    Load configuration from environment variables and/or .env file.

    Args:
        env_file: Optional path to a .env file to load

    Returns:
        Dictionary of configuration values
    """
    global _config_cache

    if env_file:
        load_dotenv(env_file)
    else:
        # Try to load from default locations
        env_paths = [
            ".env",
            ".env.local",
            f'.env.{os.getenv("ENVIRONMENT", "development")}',
        ]

        for env_path in env_paths:
            if Path(env_path).exists():
                load_dotenv(env_path)

    # Import all configuration values from the settings module
    from leadfactory.config.settings import get_all_settings

    # Get all configuration values as a dictionary
    config = get_all_settings()

    _config_cache = config
    return config


def get_config() -> dict[str, Any]:
    """
    Get the configuration dictionary.

    Returns:
        Dictionary of configuration values
    """
    global _config_cache

    if _config_cache is None:
        return load_config()

    return _config_cache


def get_env(name: str, default: Optional[Any] = None) -> Any:
    """
    Get an environment variable with a default value.
    This is a convenience function that should be used instead of os.getenv.

    Args:
        name: Name of the environment variable
        default: Default value if the environment variable is not set

    Returns:
        Value of the environment variable or the default
    """
    return os.getenv(name, default)


def get_boolean_env(name: str, default: bool = False) -> bool:
    """
    Get a boolean environment variable.

    Args:
        name: Name of the environment variable
        default: Default value if the environment variable is not set

    Returns:
        Boolean value of the environment variable
    """
    value = os.getenv(name, str(default)).lower()
    return value in ("true", "1", "yes", "y", "t")


def get_int_env(name: str, default: int = 0) -> int:
    """
    Get an integer environment variable.

    Args:
        name: Name of the environment variable
        default: Default value if the environment variable is not set

    Returns:
        Integer value of the environment variable
    """
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_float_env(name: str, default: float = 0.0) -> float:
    """
    Get a float environment variable.

    Args:
        name: Name of the environment variable
        default: Default value if the environment variable is not set

    Returns:
        Float value of the environment variable
    """
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
