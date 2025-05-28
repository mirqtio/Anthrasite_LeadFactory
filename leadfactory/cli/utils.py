"""
Common utilities for CLI commands
Provides shared functionality across all CLI operations.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from dotenv import load_dotenv


def setup_environment(verbose: bool = False) -> None:
    """
    Setup common environment for CLI commands.

    Args:
        verbose: Enable verbose logging
    """
    # Load environment variables
    load_dotenv()

    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Add project root to Python path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def validate_database_connection() -> bool:
    """
    Validate that database connection is available.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        from leadfactory.utils.e2e_db_connector import db_connection

        with db_connection() as conn:
            # Simple query to test connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
    except Exception as e:
        click.echo(f"Database connection failed: {e}", err=True)
        return False


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get configuration value from environment or config file.

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value
    """
    return os.getenv(key, default)


def confirm_operation(message: str, dry_run: bool = False) -> bool:
    """
    Confirm potentially destructive operations.

    Args:
        message: Confirmation message
        dry_run: If True, skip confirmation and return True

    Returns:
        True if confirmed, False otherwise
    """
    if dry_run:
        click.echo(f"DRY RUN: {message}")
        return True

    return click.confirm(message)


def handle_error(error: Exception, context: str = "") -> None:
    """
    Handle and log errors consistently.

    Args:
        error: Exception that occurred
        context: Additional context about the error
    """
    error_msg = f"Error in {context}: {str(error)}" if context else str(error)
    click.echo(f"❌ {error_msg}", err=True)
    logging.error(error_msg, exc_info=True)


def success_message(message: str) -> None:
    """
    Display success message with consistent formatting.

    Args:
        message: Success message to display
    """
    click.echo(f"✅ {message}")


def warning_message(message: str) -> None:
    """
    Display warning message with consistent formatting.

    Args:
        message: Warning message to display
    """
    click.echo(f"⚠️  {message}", err=True)


def info_message(message: str) -> None:
    """
    Display info message with consistent formatting.

    Args:
        message: Info message to display
    """
    click.echo(f"ℹ️  {message}")


class ProgressReporter:
    """Progress reporting utility for long-running operations."""

    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.description = description
        self.current = 0
        self.bar = None

    def __enter__(self):
        self.bar = click.progressbar(
            length=self.total, label=self.description, show_eta=True, show_percent=True
        )
        self.bar.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.bar:
            self.bar.__exit__(exc_type, exc_val, exc_tb)

    def update(self, increment: int = 1):
        """Update progress by increment."""
        if self.bar:
            self.bar.update(increment)
        self.current += increment

    def set_progress(self, value: int):
        """Set absolute progress value."""
        if self.bar:
            self.bar.update(value - self.current)
        self.current = value


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def validate_required_env_vars(required_vars: list) -> bool:
    """
    Validate that required environment variables are set.

    Args:
        required_vars: List of required environment variable names

    Returns:
        True if all required vars are set, False otherwise
    """
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        handle_error(ValueError(error_msg), "Environment validation")
        return False

    return True
