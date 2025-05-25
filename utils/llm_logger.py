#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: LLM Logger
Utilities for logging LLM interactions and managing retention.
"""

import datetime
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Union

# Use lowercase versions for Python 3.9 compatibility

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import database utilities
from utils.io import DatabaseConnection  # noqa: E402

# Import logging configuration
from utils.logging_config import get_logger  # noqa: E402

# Import raw data retention utilities
from utils.raw_data_retention import (  # noqa: E402
    get_llm_logs,
    identify_expired_data,
    log_llm_interaction,
)

# Set up logging
logger = get_logger(__name__)

# Constants
DEFAULT_MODEL_VERSION = os.getenv("LLM_MODEL_VERSION", "gpt-3.5-turbo")
RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))


class LLMLogger:
    """Logger for LLM interactions with retention management."""

    def __init__(self, model_version: str = DEFAULT_MODEL_VERSION):
        """Initialize LLM logger.

        Args:
            model_version: Version of the LLM model being used.
        """
        self.model_version = model_version
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start timing the LLM interaction."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing the LLM interaction."""
        self.end_time = time.time()
        if exc_type:
            logger.warning(f"LLM interaction failed: {exc_val}")

    def log(
        self,
        operation: str,
        prompt_text: str,
        response_json: Union[dict, str],
        business_id: Optional[int] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        status: str = "success",
        metadata: Optional[dict] = None,
    ) -> Optional[int]:
        """Log an LLM interaction.

        Args:
            operation: Type of operation (e.g., 'deduplication', 'mockup_generation').
            prompt_text: Text of the prompt sent to the LLM.
            response_json: JSON response from the LLM.
            business_id: Business ID associated with the interaction.
            tokens_prompt: Number of tokens in the prompt.
            tokens_completion: Number of tokens in the completion.
            status: Status of the interaction (success, error, etc.).
            metadata: Additional metadata for the interaction.

        Returns:
            ID of the log entry, or None if logging failed.
        """
        # Calculate duration if timing was used
        duration_ms = None
        if self.start_time and self.end_time:
            duration_ms = int((self.end_time - self.start_time) * 1000)

        # Log the interaction
        log_id = log_llm_interaction(
            operation=operation,
            model_version=self.model_version,
            prompt_text=prompt_text,
            response_json=response_json,
            business_id=business_id,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            duration_ms=duration_ms,
            status=status,
            metadata=metadata,
        )

        return log_id


def log_deduplication(
    prompt_text: str,
    response_json: dict,
    business_id1: int,
    business_id2: int,
    similarity_score: float,
    tokens_prompt: Optional[int] = None,
    tokens_completion: Optional[int] = None,
) -> Optional[int]:
    """Log a deduplication LLM interaction.

    Args:
        prompt_text: Text of the prompt sent to the LLM.
        response_json: JSON response from the LLM.
        business_id1: First business ID.
        business_id2: Second business ID.
        similarity_score: Similarity score between the businesses.
        tokens_prompt: Number of tokens in the prompt.
        tokens_completion: Number of tokens in the completion.

    Returns:
        ID of the log entry, or None if logging failed.
    """
    # Add metadata for deduplication
    metadata = {
        "business_id1": business_id1,
        "business_id2": business_id2,
        "similarity_score": similarity_score,
    }

    # Use the LLM logger
    with LLMLogger() as llm_logger:
        log_id = llm_logger.log(
            operation="deduplication",
            prompt_text=prompt_text,
            response_json=response_json,
            business_id=business_id1,  # Use the first business ID
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            metadata=metadata,
        )

    return log_id


def log_mockup_generation(
    prompt_text: str,
    response_json: dict,
    business_id: int,
    mockup_id: Optional[int] = None,
    tokens_prompt: Optional[int] = None,
    tokens_completion: Optional[int] = None,
) -> Optional[int]:
    """Log a mockup generation LLM interaction.

    Args:
        prompt_text: Text of the prompt sent to the LLM.
        response_json: JSON response from the LLM.
        business_id: Business ID.
        mockup_id: Mockup ID if available.
        tokens_prompt: Number of tokens in the prompt.
        tokens_completion: Number of tokens in the completion.

    Returns:
        ID of the log entry, or None if logging failed.
    """
    # Add metadata for mockup generation
    metadata = {}
    if mockup_id:
        metadata["mockup_id"] = mockup_id

    # Use the LLM logger
    with LLMLogger() as llm_logger:
        log_id = llm_logger.log(
            operation="mockup_generation",
            prompt_text=prompt_text,
            response_json=response_json,
            business_id=business_id,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            metadata=metadata,
        )

    return log_id


def get_recent_llm_logs(
    operation: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Get recent LLM logs from the database.

    Args:
        operation: Filter by operation type.
        limit: Maximum number of logs to return.

    Returns:
        List of log entries.
    """
    return get_llm_logs(operation=operation, limit=limit)


def get_business_llm_logs(
    business_id: int,
    operation: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Get LLM logs for a specific business.

    Args:
        business_id: Business ID to filter by.
        operation: Filter by operation type.
        limit: Maximum number of logs to return.

    Returns:
        List of log entries.
    """
    return get_llm_logs(business_id=business_id, operation=operation, limit=limit)


def check_retention_status() -> dict[str, Any]:
    """Check the status of data retention.

    Returns:
        dictionary with retention status information.
    """
    # Identify expired data
    expired_html_files, expired_llm_logs = identify_expired_data()

    # Get counts of total data
    with DatabaseConnection() as cursor:
        # Count HTML files
        cursor.execute("SELECT COUNT(*) as count FROM raw_html_storage")
        html_count = cursor.fetchone()["count"]

        # Count LLM logs
        cursor.execute("SELECT COUNT(*) as count FROM llm_logs")
        llm_logs_count = cursor.fetchone()["count"]

    # Calculate retention percentages
    html_retention_percentage = (
        100 - (len(expired_html_files) / html_count * 100) if html_count > 0 else 100
    )
    llm_retention_percentage = (
        100 - (len(expired_llm_logs) / llm_logs_count * 100)
        if llm_logs_count > 0
        else 100
    )

    # Prepare status report
    status = {
        "retention_days": RETENTION_DAYS,
        "html_storage": {
            "total_count": html_count,
            "expired_count": len(expired_html_files),
            "retention_percentage": html_retention_percentage,
        },
        "llm_logs": {
            "total_count": llm_logs_count,
            "expired_count": len(expired_llm_logs),
            "retention_percentage": llm_retention_percentage,
        },
        "timestamp": datetime.datetime.now().isoformat(),
    }

    return status
