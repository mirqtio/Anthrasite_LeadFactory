#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Batch Completion Metrics
Prometheus metrics for batch completion monitoring.
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import prometheus client
from prometheus_client import Counter, Gauge, Histogram

# Import batch tracker functions at runtime to avoid circular imports
# This prevents the circular import issue between batch_tracker.py and metrics.py
# Import logging configuration
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Define metrics
BATCH_COMPLETION_PERCENTAGE = Gauge(
    "anthrasite_batch_completion_percentage",
    "Overall batch completion percentage",
)

BATCH_STAGE_COMPLETION_PERCENTAGE = Gauge(
    "anthrasite_batch_stage_completion_percentage",
    "Completion percentage for each batch stage",
    ["stage"],
)

BATCH_COMPLETION_TIME = Histogram(
    "anthrasite_batch_completion_time_seconds",
    "Time taken to complete a batch",
    buckets=[1800, 3600, 7200, 14400, 28800, 43200],  # 30m, 1h, 2h, 4h, 8h, 12h
)

BATCH_COMPLETION_SUCCESS = Gauge(
    "anthrasite_batch_completion_success",
    "Whether the last batch completed successfully (1) or not (0)",
)

BATCH_COST_PER_LEAD = Gauge(
    "anthrasite_batch_cost_per_lead",
    "Cost per lead in the current batch",
)

BATCH_GPU_COST = Counter(
    "anthrasite_batch_gpu_cost_dollars",
    "Cumulative GPU cost in dollars",
)


def update_batch_metrics() -> None:
    """Update all batch-related metrics based on current batch status."""
    try:
        # Import at runtime to avoid circular imports
        from utils.batch_tracker import get_batch_status

        # Get current batch status
        status = get_batch_status()

        # Update overall completion percentage
        completion_percentage = status.get("completion_percentage", 0)
        BATCH_COMPLETION_PERCENTAGE.set(completion_percentage)

        # Update stage completion percentages
        stages = status.get("stages", {})
        for stage, details in stages.items():
            stage_percentage = details.get("completion_percentage", 0)
            BATCH_STAGE_COMPLETION_PERCENTAGE.labels(stage=stage).set(stage_percentage)

        # Update batch completion success
        if "current_batch_end" in status:
            BATCH_COMPLETION_SUCCESS.set(1)
        else:
            BATCH_COMPLETION_SUCCESS.set(0)

        # Update batch completion time if available
        if "current_batch_start" in status and "current_batch_end" in status:
            try:
                from datetime import datetime

                start_time = datetime.fromisoformat(status["current_batch_start"])
                end_time = datetime.fromisoformat(status["current_batch_end"])
                duration_seconds = (end_time - start_time).total_seconds()
                BATCH_COMPLETION_TIME.observe(duration_seconds)
            except Exception as e:
                logger.error(f"Error calculating batch duration: {e}")

        logger.debug(f"Updated batch metrics: completion={completion_percentage}%")
    except Exception as e:
        logger.error(f"Error updating batch metrics: {e}")


def record_cost_per_lead(cost_per_lead: float) -> None:
    """Record the cost per lead for the current batch.

    Args:
        cost_per_lead: Cost per lead in dollars.
    """
    try:
        BATCH_COST_PER_LEAD.set(cost_per_lead)
        logger.debug(f"Updated cost per lead metric: ${cost_per_lead:.2f}")
    except Exception as e:
        logger.error(f"Error updating cost per lead metric: {e}")


def increment_gpu_cost(cost_dollars: float) -> None:
    """Increment the GPU cost counter.

    Args:
        cost_dollars: Cost in dollars to add to the counter.
    """
    try:
        BATCH_GPU_COST.inc(cost_dollars)
        logger.debug(f"Incremented GPU cost metric by ${cost_dollars:.2f}")
    except Exception as e:
        logger.error(f"Error incrementing GPU cost metric: {e}")


def check_gpu_burst_and_record_cost() -> None:
    """Check if GPU_BURST environment flag is set and record cost if it is."""
    try:
        gpu_burst = os.getenv("GPU_BURST", "0").lower() in ("1", "true", "yes")
        if gpu_burst:
            # Default cost per GPU burst usage (can be configured via env var)
            cost_per_burst = float(os.getenv("GPU_BURST_COST_DOLLARS", "0.50"))
            increment_gpu_cost(cost_per_burst)
            logger.info(f"Recorded GPU burst cost: ${cost_per_burst:.2f}")
    except Exception as e:
        logger.error(f"Error checking GPU burst and recording cost: {e}")


def start_metrics_updater(interval_seconds: int = 60) -> None:
    """Start a background thread to periodically update metrics.

    Args:
        interval_seconds: Update interval in seconds.
    """
    import threading

    def updater_thread():
        logger.info(f"Starting batch metrics updater (interval: {interval_seconds}s)")
        while True:
            try:
                update_batch_metrics()
            except Exception as e:
                logger.error(f"Error in batch metrics updater: {e}")

            # Sleep until next update
            time.sleep(interval_seconds)

    # Start updater thread
    thread = threading.Thread(target=updater_thread, daemon=True)
    thread.start()
    logger.info("Batch metrics updater thread started")
