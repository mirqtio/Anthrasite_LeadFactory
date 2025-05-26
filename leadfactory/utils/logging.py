"""
Unified logging system for the Anthrasite LeadFactory project.

This module provides a standardized logging interface for all components
of the application with consistent formatting, contextual information,
and appropriate log levels.

Usage:
    from leadfactory.utils.logging import get_logger

    # Get a logger for your module
    logger = get_logger(__name__)

    # Use the logger with appropriate levels
    logger.debug("Detailed information for debugging")
    logger.info("General information about program execution")
    logger.warning("Warning about potential issues")
    logger.error("Error that prevented something from working")
    logger.critical("Critical error that requires immediate attention")

    # With context
    logger.info("Processing business data", extra={"business_id": 123, "batch_id": "batch-456"})
"""

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional, Union


class RequestContextFilter(logging.Filter):
    """
    Filter that adds request context to log records.
    """

    def __init__(self, request_id: Optional[str] = None):
        super().__init__()
        self.request_id = request_id or str(uuid.uuid4())

    def filter(self, record):
        record.request_id = getattr(record, "request_id", self.request_id)
        return True


class JsonFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.
    """

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": getattr(record, "request_id", "-"),
        }

        # Include any extra fields from the log record
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logger(
    name: str,
    level: Union[int, str] = None,
    log_format: str = None,
    request_id: Optional[str] = None,
    add_console_handler: bool = True,
    add_file_handler: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure and return a logger with the specified settings.

    Args:
        name: The name of the logger (usually __name__)
        level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: The format to use (json or text)
        request_id: Optional request ID for tracking related log entries
        add_console_handler: Whether to add a console handler
        add_file_handler: Whether to add a file handler
        log_file: Path to the log file (if add_file_handler is True)

    Returns:
        A configured logger instance
    """
    # Set default values from environment or use fallbacks
    level = level or os.getenv("LOG_LEVEL", "INFO")
    log_format = log_format or os.getenv("LOG_FORMAT", "json")

    # Convert string log level to numeric value
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add request context filter
    context_filter = RequestContextFilter(request_id)
    logger.addFilter(context_filter)

    # Define formatters
    json_formatter = JsonFormatter()
    text_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(request_id)s] - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    formatter = json_formatter if log_format.lower() == "json" else text_formatter

    # Add console handler if requested
    if add_console_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if requested
    if add_file_handler and log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(
    name: str, level: Union[int, str] = None, request_id: Optional[str] = None
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger (usually __name__)
        level: Override the default logging level for this logger
        request_id: Optional request ID for tracking related log entries

    Returns:
        A configured logger instance
    """
    return setup_logger(name, level=level, request_id=request_id)


# Create a default app-wide logger
logger = get_logger("leadfactory")


class LogContext:
    """
    Context manager for temporarily adding context data to logs.

    Usage:
        with LogContext(logger, business_id=123, batch_id="abc"):
            logger.info("Processing business")  # Will include the context data
    """

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = None

    def __enter__(self):
        # Store original factory
        self.old_factory = logging.getLogRecordFactory()

        # Create new factory that adds our context
        old_factory = self.old_factory
        context = self.context

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra = getattr(record, "extra", {})
            record.extra.update(context)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original factory
        logging.setLogRecordFactory(self.old_factory)


def log_execution_time(func):
    """
    Decorator to log function execution time.

    Usage:
        @log_execution_time
        def my_function():
            ...
    """

    def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            func_logger.debug(
                f"Function '{func.__name__}' executed in {execution_time:.4f} seconds",
                extra={"execution_time": execution_time},
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            func_logger.error(
                f"Function '{func.__name__}' failed after {execution_time:.4f} seconds: {str(e)}",
                extra={"execution_time": execution_time, "error": str(e)},
            )
            raise

    return wrapper
