"""
GPT API Usage Tracking Module
============================

This module provides comprehensive tracking and monitoring of GPT API usage,
including token counts, request frequency, and associated costs. It serves as
the foundation for budget monitoring and throttling.

Features:
- Token counting for input and output
- Cost calculation based on current pricing
- Persistent storage of usage data
- Usage statistics and historical trends
- Decorator pattern for non-intrusive API call wrapping
- Integration with existing cost tracking system
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.cost.cost_tracking import CostTracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class GPTUsageTracker:
    """
    Tracks GPT API usage including tokens, costs, and request patterns.

    This class provides detailed monitoring of GPT API calls, storing
    usage data persistently and providing analytics for budget management.
    """

    # Current OpenAI pricing (per 1K tokens)
    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "gpt-3.5-turbo-instruct": {"input": 0.0015, "output": 0.002},
    }

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the GPT usage tracker.

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        self.db_path = db_path or str(Path.home() / ".leadfactory" / "gpt_usage.db")
        self.cost_tracker = CostTracker()
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database for usage tracking."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create usage tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gpt_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                model TEXT NOT NULL,
                operation TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                input_cost REAL NOT NULL,
                output_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                request_duration REAL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                metadata TEXT,
                batch_id TEXT
            )
        """
        )

        # Create indices for efficient querying
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_gpt_timestamp ON gpt_usage (timestamp)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_model ON gpt_usage (model)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_gpt_batch_id ON gpt_usage (batch_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_gpt_success ON gpt_usage (success)"
        )

        conn.commit()
        conn.close()

        logger.debug(f"GPT usage database initialized at {self.db_path}")

    def track_usage(
        self,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        request_duration: Optional[float] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Track a GPT API usage event.

        Args:
            model: GPT model used (e.g., 'gpt-4o', 'gpt-3.5-turbo')
            operation: Operation type (e.g., 'chat_completion', 'completion')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            request_duration: Request duration in seconds
            success: Whether the request was successful
            error_message: Error message if request failed
            metadata: Additional metadata to store
            batch_id: Batch ID for grouping related requests

        Returns:
            Dictionary containing usage statistics and cost information
        """
        timestamp = time.time()
        total_tokens = input_tokens + output_tokens

        # Calculate costs (only for successful requests)
        if success:
            pricing = self.PRICING.get(
                model, self.PRICING["gpt-4o"]
            )  # Default to gpt-4o pricing
            input_cost = (input_tokens / 1000) * pricing["input"]
            output_cost = (output_tokens / 1000) * pricing["output"]
            total_cost = input_cost + output_cost
        else:
            # No cost for failed requests
            input_cost = 0.0
            output_cost = 0.0
            total_cost = 0.0

        # Store usage data
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO gpt_usage (
                    timestamp, model, operation, input_tokens, output_tokens,
                    total_tokens, input_cost, output_cost, total_cost,
                    request_duration, success, error_message, metadata, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    model,
                    operation,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    input_cost,
                    output_cost,
                    total_cost,
                    request_duration,
                    success,
                    error_message,
                    json.dumps(metadata) if metadata else None,
                    batch_id,
                ),
            )

            conn.commit()
            conn.close()

        # Track cost in the main cost tracker
        if success and total_cost > 0:
            self.cost_tracker.add_cost(
                amount=total_cost,
                service="openai",
                operation=f"{model}_{operation}",
                details={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "model": model,
                    "operation": operation,
                    "request_duration": request_duration,
                    **(metadata or {}),
                },
                batch_id=batch_id,
            )

        usage_info = {
            "timestamp": timestamp,
            "model": model,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "request_duration": request_duration,
            "success": success,
            "error_message": error_message,
        }

        logger.debug(
            f"Tracked GPT usage: {model} - {total_tokens} tokens, ${total_cost:.4f}"
        )
        return usage_info

    def get_usage_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        model: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a specified time period.

        Args:
            start_time: Start of time period (default: 24 hours ago)
            end_time: End of time period (default: now)
            model: Filter by specific model
            batch_id: Filter by specific batch ID

        Returns:
            Dictionary containing usage statistics
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.now()

        start_timestamp = start_time.timestamp()
        end_timestamp = end_time.timestamp()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query with filters
        where_clauses = ["timestamp BETWEEN ? AND ?"]
        params = [start_timestamp, end_timestamp]

        if model:
            where_clauses.append("model = ?")
            params.append(model)

        if batch_id:
            where_clauses.append("batch_id = ?")
            params.append(batch_id)

        where_clause = " AND ".join(where_clauses)

        # Get aggregate statistics
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_requests,
                COUNT(CASE WHEN success = 1 THEN 1 END) as successful_requests,
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_requests,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost) as total_cost,
                AVG(request_duration) as avg_request_duration,
                MIN(timestamp) as first_request,
                MAX(timestamp) as last_request
            FROM gpt_usage
            WHERE {where_clause}
        """,
            params,
        )

        stats = cursor.fetchone()

        # Get model breakdown
        cursor.execute(
            f"""
            SELECT
                model,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM gpt_usage
            WHERE {where_clause}
            GROUP BY model
            ORDER BY cost DESC
        """,
            params,
        )

        model_breakdown = [
            {"model": row[0], "requests": row[1], "tokens": row[2], "cost": row[3]}
            for row in cursor.fetchall()
        ]

        # Get hourly usage pattern
        cursor.execute(
            f"""
            SELECT
                strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(total_cost) as cost
            FROM gpt_usage
            WHERE {where_clause}
            GROUP BY hour
            ORDER BY hour
        """,
            params,
        )

        hourly_usage = [
            {"hour": row[0], "requests": row[1], "tokens": row[2], "cost": row[3]}
            for row in cursor.fetchall()
        ]

        conn.close()

        return {
            "period": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "filters": {"model": model, "batch_id": batch_id},
            "summary": {
                "total_requests": stats[0] or 0,
                "successful_requests": stats[1] or 0,
                "failed_requests": stats[2] or 0,
                "success_rate": (stats[1] / stats[0]) if stats[0] > 0 else 0,
                "total_input_tokens": stats[3] or 0,
                "total_output_tokens": stats[4] or 0,
                "total_tokens": stats[5] or 0,
                "total_cost": stats[6] or 0,
                "avg_request_duration": stats[7] or 0,
                "first_request": (
                    datetime.fromtimestamp(stats[8]).isoformat() if stats[8] else None
                ),
                "last_request": (
                    datetime.fromtimestamp(stats[9]).isoformat() if stats[9] else None
                ),
            },
            "model_breakdown": model_breakdown,
            "hourly_usage": hourly_usage,
        }

    def get_current_usage(self, period_hours: int = 1) -> Dict[str, Any]:
        """
        Get current usage statistics for the specified period.

        Args:
            period_hours: Number of hours to look back (default: 1)

        Returns:
            Dictionary containing current usage statistics
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=period_hours)
        return self.get_usage_stats(start_time, end_time)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a given text.

        This is a rough estimation based on the rule of thumb that
        1 token ≈ 4 characters for English text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Rough estimation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)

    def estimate_cost(
        self, model: str, input_text: str, estimated_output_tokens: int = 0
    ) -> float:
        """
        Estimate cost for a GPT API call.

        Args:
            model: GPT model to use
            input_text: Input text
            estimated_output_tokens: Estimated output tokens

        Returns:
            Estimated cost in USD
        """
        input_tokens = self.estimate_tokens(input_text)
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o"])

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost


def gpt_usage_tracker(
    model: str = "gpt-4o",
    operation: str = "chat_completion",
    tracker: Optional[GPTUsageTracker] = None,
):
    """
    Decorator to track GPT API usage.

    This decorator wraps GPT API calls to automatically track usage,
    including token counts, costs, and request patterns.

    Args:
        model: GPT model being used
        operation: Operation type
        tracker: GPTUsageTracker instance (creates new if None)

    Returns:
        Decorated function that tracks usage
    """
    if tracker is None:
        tracker = GPTUsageTracker()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_message = None
            input_tokens = 0
            output_tokens = 0

            try:
                # Try to extract input tokens from messages or prompt
                if "messages" in kwargs:
                    messages = kwargs["messages"]
                    if isinstance(messages, list):
                        input_text = " ".join(
                            msg.get("content", "")
                            for msg in messages
                            if isinstance(msg, dict) and "content" in msg
                        )
                        input_tokens = tracker.estimate_tokens(input_text)
                elif "prompt" in kwargs:
                    input_tokens = tracker.estimate_tokens(kwargs["prompt"])

                # Call the original function
                result = func(*args, **kwargs)
                success = True

                # Try to extract output tokens from result
                if isinstance(result, dict):
                    if "usage" in result:
                        # Standard OpenAI response format
                        usage = result["usage"]
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", 0)
                    elif "choices" in result and result["choices"]:
                        # Estimate from response content
                        choice = result["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            output_tokens = tracker.estimate_tokens(
                                choice["message"]["content"]
                            )
                        elif "text" in choice:
                            output_tokens = tracker.estimate_tokens(choice["text"])

                return result

            except Exception as e:
                error_message = str(e)
                logger.error(f"GPT API call failed: {error_message}")
                raise

            finally:
                request_duration = time.time() - start_time

                # Track the usage
                tracker.track_usage(
                    model=model,
                    operation=operation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_duration=request_duration,
                    success=success,
                    error_message=error_message,
                    metadata={
                        "function_name": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

        return wrapper

    return decorator


# Global instance for easy access
_global_tracker = None


def get_gpt_usage_tracker() -> GPTUsageTracker:
    """Get the global GPT usage tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = GPTUsageTracker()
    return _global_tracker
