"""
Logging configuration utility for the Anthrasite Lead-Factory project.

This module provides a centralized way to configure logging across the project
with consistent formatting and behavior.
"""

import logging
import os
from typing import Optional


def setup_logging(
    log_level: Optional[str] = None, log_format: Optional[str] = None
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: The logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
                  If not provided, defaults to the LOG_LEVEL environment variable or 'INFO'.
        log_format: The log format ('json' or 'text').
                   If not provided, defaults to the LOG_FORMAT environment variable or 'json'.
    """
    # Set default values if not provided
    level = log_level or os.getenv("LOG_LEVEL", "INFO")
    fmt = log_format or os.getenv("LOG_FORMAT", "json")

    # Define log formats
    json_format = (
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"module": "%(module)s", "function": "%(funcName)s", "message": "%(message)s"}'
    )
    text_format = "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s"

    # Configure logging
    logging.basicConfig(
        level=level,
        format=json_format if fmt.lower() == "json" else text_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger (usually __name__).

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)
