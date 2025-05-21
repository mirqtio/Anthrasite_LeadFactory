#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Cost Metrics
Utilities for tracking and reporting cost metrics.
"""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, Tuple
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import logging configuration
from utils.logging_config import get_logger

# Import batch metrics
from utils.batch_metrics import record_cost_per_lead, increment_gpu_cost

# Set up logging
logger = get_logger(__name__)

# Constants
COST_TRACKER_FILE = os.getenv("COST_TRACKER_FILE", "data/cost_tracker.json")
DATABASE_URL = os.getenv("DATABASE_URL", "leadfactory.db")
MONTHLY_BUDGET = float(
    os.getenv("MONTHLY_BUDGET", "250")
)  # Default $250 monthly budget


def ensure_cost_tracker_file() -> None:
    """Ensure the cost tracker file exists and has the correct structure."""
    os.makedirs(os.path.dirname(COST_TRACKER_FILE), exist_ok=True)

    if not os.path.exists(COST_TRACKER_FILE):
        # Create initial structure
        data = {
            "daily_costs": {},
            "monthly_costs": {},
            "cost_per_lead": 0.0,
            "gpu_costs": {
                "total": 0.0,
                "daily": 0.0,
                "monthly": 0.0,
            },
            "last_updated": datetime.utcnow().isoformat(),
        }

        # Write to file
        with open(COST_TRACKER_FILE, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Created new cost tracker file: {COST_TRACKER_FILE}")


def get_cost_data() -> Dict[str, Any]:
    """Get cost data from the cost tracker file."""
    ensure_cost_tracker_file()

    try:
        with open(COST_TRACKER_FILE, "r") as f:
            data = json.load(f)

        return data
    except Exception as e:
        logger.error(f"Error reading cost tracker file: {e}")
        return {
            "daily_costs": {},
            "monthly_costs": {},
            "cost_per_lead": 0.0,
            "gpu_costs": {
                "total": 0.0,
                "daily": 0.0,
                "monthly": 0.0,
            },
            "last_updated": datetime.utcnow().isoformat(),
        }


def save_cost_data(data: Dict[str, Any]) -> bool:
    """Save cost data to the cost tracker file.

    Args:
        data: Cost data to save.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Update last updated timestamp
        data["last_updated"] = datetime.utcnow().isoformat()

        # Write to file
        with open(COST_TRACKER_FILE, "w") as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        logger.error(f"Error saving cost tracker file: {e}")
        return False


def get_lead_count() -> int:
    """Get the total number of leads in the database.

    Returns:
        Total number of leads.
    """
    try:
        # Connect to database
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Get total number of leads
        cursor.execute("SELECT COUNT(*) FROM businesses")
        total_leads = cursor.fetchone()[0]

        conn.close()

        return total_leads
    except Exception as e:
        logger.error(f"Error getting lead count: {e}")
        return 0


def get_total_monthly_cost() -> float:
    """Get the total monthly cost from all services.

    Returns:
        Total monthly cost in dollars.
    """
    try:
        # Get cost data
        data = get_cost_data()

        # Sum all monthly costs
        total_cost = sum(
            float(cost) for service, cost in data.get("monthly_costs", {}).items()
        )

        return total_cost
    except Exception as e:
        logger.error(f"Error getting total monthly cost: {e}")
        return 0.0


def calculate_cost_per_lead() -> float:
    """Calculate the cost per lead.

    Returns:
        Cost per lead in dollars.
    """
    try:
        # Get total monthly cost
        total_cost = get_total_monthly_cost()

        # Get total number of leads
        total_leads = get_lead_count()

        # Calculate cost per lead
        if total_leads > 0:
            cost_per_lead = total_cost / total_leads
        else:
            cost_per_lead = 0.0

        # Update cost data
        data = get_cost_data()
        data["cost_per_lead"] = cost_per_lead
        save_cost_data(data)

        # Update Prometheus metric
        record_cost_per_lead(cost_per_lead)

        logger.info(f"Calculated cost per lead: ${cost_per_lead:.2f}")

        return cost_per_lead
    except Exception as e:
        logger.error(f"Error calculating cost per lead: {e}")
        return 0.0


def track_gpu_usage(cost_dollars: float = 0.5) -> bool:
    """Track GPU usage when GPU_BURST flag is set.

    Args:
        cost_dollars: Cost in dollars to add to the counter (default: $0.50).

    Returns:
        True if GPU usage was tracked, False otherwise.
    """
    try:
        # Check if GPU_BURST environment flag is set
        gpu_burst = os.getenv("GPU_BURST", "0").lower() in ("1", "true", "yes")

        if not gpu_burst:
            return False

        # Get cost data
        data = get_cost_data()

        # Update GPU costs
        data["gpu_costs"]["total"] += cost_dollars
        data["gpu_costs"]["daily"] += cost_dollars
        data["gpu_costs"]["monthly"] += cost_dollars

        # Save updated data
        save_cost_data(data)

        # Update Prometheus metric
        increment_gpu_cost(cost_dollars)

        logger.info(f"Tracked GPU usage: ${cost_dollars:.2f}")

        return True
    except Exception as e:
        logger.error(f"Error tracking GPU usage: {e}")
        return False


def reset_daily_gpu_cost() -> bool:
    """Reset daily GPU cost at the start of a new day.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Get cost data
        data = get_cost_data()

        # Reset daily GPU cost
        data["gpu_costs"]["daily"] = 0.0

        # Save updated data
        save_cost_data(data)

        logger.info("Reset daily GPU cost")

        return True
    except Exception as e:
        logger.error(f"Error resetting daily GPU cost: {e}")
        return False


def reset_monthly_gpu_cost() -> bool:
    """Reset monthly GPU cost at the start of a new month.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Get cost data
        data = get_cost_data()

        # Reset monthly GPU cost
        data["gpu_costs"]["monthly"] = 0.0

        # Save updated data
        save_cost_data(data)

        logger.info("Reset monthly GPU cost")

        return True
    except Exception as e:
        logger.error(f"Error resetting monthly GPU cost: {e}")
        return False


def check_gpu_cost_threshold(
    daily_threshold: float = 25.0, monthly_threshold: float = 100.0
) -> Tuple[bool, str]:
    """Check if GPU cost exceeds thresholds.

    Args:
        daily_threshold: Daily GPU cost threshold in dollars.
        monthly_threshold: Monthly GPU cost threshold in dollars.

    Returns:
        Tuple of (exceeded, reason).
    """
    try:
        # Get cost data
        data = get_cost_data()

        # Check daily threshold
        daily_cost = data["gpu_costs"]["daily"]
        if daily_cost > daily_threshold:
            return (
                True,
                f"Daily GPU cost (${daily_cost:.2f}) exceeds threshold (${daily_threshold:.2f})",
            )

        # Check monthly threshold
        monthly_cost = data["gpu_costs"]["monthly"]
        if monthly_cost > monthly_threshold:
            return (
                True,
                f"Monthly GPU cost (${monthly_cost:.2f}) exceeds threshold (${monthly_threshold:.2f})",
            )

        return False, "GPU cost is within thresholds"
    except Exception as e:
        logger.error(f"Error checking GPU cost threshold: {e}")
        return False, f"Error checking GPU cost threshold: {e}"


def check_cost_per_lead_threshold(threshold: float = 3.0) -> Tuple[bool, str]:
    """Check if cost per lead exceeds threshold.

    Args:
        threshold: Cost per lead threshold in dollars.

    Returns:
        Tuple of (exceeded, reason).
    """
    try:
        # Get cost data
        data = get_cost_data()

        # Check threshold
        cost_per_lead = data["cost_per_lead"]
        if cost_per_lead > threshold:
            return (
                True,
                f"Cost per lead (${cost_per_lead:.2f}) exceeds threshold (${threshold:.2f})",
            )

        return False, "Cost per lead is within threshold"
    except Exception as e:
        logger.error(f"Error checking cost per lead threshold: {e}")
        return False, f"Error checking cost per lead threshold: {e}"


def update_cost_metrics_at_batch_end() -> Dict[str, Any]:
    """Update all cost metrics at the end of a batch run.

    Returns:
        Dictionary with updated metrics.
    """
    try:
        # Calculate cost per lead
        cost_per_lead = calculate_cost_per_lead()

        # Check thresholds
        cost_per_lead_exceeded, cost_per_lead_reason = check_cost_per_lead_threshold()
        gpu_cost_exceeded, gpu_cost_reason = check_gpu_cost_threshold()

        # Get cost data
        data = get_cost_data()

        # Prepare results
        results = {
            "cost_per_lead": cost_per_lead,
            "cost_per_lead_threshold_exceeded": cost_per_lead_exceeded,
            "cost_per_lead_reason": cost_per_lead_reason,
            "gpu_cost_daily": data["gpu_costs"]["daily"],
            "gpu_cost_monthly": data["gpu_costs"]["monthly"],
            "gpu_cost_total": data["gpu_costs"]["total"],
            "gpu_cost_threshold_exceeded": gpu_cost_exceeded,
            "gpu_cost_reason": gpu_cost_reason,
            "total_monthly_cost": get_total_monthly_cost(),
            "monthly_budget": MONTHLY_BUDGET,
            "budget_utilization": (
                (get_total_monthly_cost() / MONTHLY_BUDGET) * 100
                if MONTHLY_BUDGET > 0
                else 0.0
            ),
        }

        logger.info(f"Updated cost metrics at batch end: {results}")

        return results
    except Exception as e:
        logger.error(f"Error updating cost metrics at batch end: {e}")
        return {
            "error": str(e),
            "cost_per_lead": 0.0,
            "cost_per_lead_threshold_exceeded": False,
            "gpu_cost_daily": 0.0,
            "gpu_cost_monthly": 0.0,
            "gpu_cost_total": 0.0,
            "gpu_cost_threshold_exceeded": False,
        }
