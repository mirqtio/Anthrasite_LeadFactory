"""
Anthrasite Lead-Factory: Batch Completion Tracker
This module tracks batch completion status and provides alerts if batches don't
complete on time.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import logging configuration
from utils.logging_config import get_logger  # noqa: E402

# Initialize logger
logger = get_logger(__name__)

# Constants
DEFAULT_TRACKER_PATH = Path("data") / "batch_tracker.json"
BATCH_TRACKER_FILE = Path(os.getenv("BATCH_TRACKER_FILE", str(DEFAULT_TRACKER_PATH)))
BATCH_COMPLETION_DEADLINE_HOUR = int(
    os.getenv("BATCH_COMPLETION_DEADLINE_HOUR", "5")
)  # 5:00 AM EST
BATCH_COMPLETION_DEADLINE_MINUTE = int(
    os.getenv("BATCH_COMPLETION_DEADLINE_MINUTE", "0")
)  # 5:00 AM EST
BATCH_COMPLETION_TIMEZONE = os.getenv(
    "BATCH_COMPLETION_TIMEZONE", "America/New_York"
)  # EST

# Import metrics for updating batch completion gauge
from utils.metrics import BATCH_COMPLETION_GAUGE  # noqa: E402


def ensure_tracker_file_exists(tracker_file: Path = BATCH_TRACKER_FILE) -> None:
    """Ensure the batch tracker file exists."""
    tracker_file.parent.mkdir(parents=True, exist_ok=True)

    if not tracker_file.exists():
        # Create initial tracker file
        initial_data: Dict[str, Any] = {
            "last_batch_start": None,
            "last_batch_end": None,
            "current_batch_start": None,
            "current_batch_stages": {},
            "alerts": [],
        }
        with tracker_file.open("w") as f:
            json.dump(initial_data, f, indent=2)
        logger.info(f"Created batch tracker file: {tracker_file}")


def load_tracker_data() -> dict:
    """Load batch tracker data from file."""
    ensure_tracker_file_exists()
    try:
        with BATCH_TRACKER_FILE.open() as f:
            data: Dict[str, Any] = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error loading batch tracker data: {e}")
        return {
            "last_batch_start": None,
            "last_batch_end": None,
            "current_batch_start": None,
            "current_batch_stages": {},
            "alerts": [],
        }


def save_tracker_data(data: dict) -> bool:
    """Save batch tracker data to file.

    Args:
        data: Batch tracker data to save.

    Returns:
        True if successful, False otherwise.
    """
    ensure_tracker_file_exists()
    try:
        with BATCH_TRACKER_FILE.open("w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving batch tracker data: {e}")
        return False


def record_batch_start() -> bool:
    """Record the start of a new batch.

    Returns:
        True if successful, False otherwise.
    """
    try:
        data = load_tracker_data()

        # If there's an existing current batch, move it to last batch
        if data["current_batch_start"]:
            data["last_batch_start"] = data["current_batch_start"]

        # Record new batch start time
        current_time = datetime.utcnow().isoformat()
        data["current_batch_start"] = current_time
        data["current_batch_stages"] = {}

        # Reset batch completion gauge for all stages
        for stage in ["scrape", "enrich", "dedupe", "score", "mockup", "email"]:
            BATCH_COMPLETION_GAUGE.labels(stage=stage).set(0)

        # Save updated data
        success = save_tracker_data(data)
        if success:
            logger.info(f"Recorded batch start at {current_time}")

        return success
    except Exception as e:
        logger.error(f"Error recording batch start: {e}")
        return False


def record_batch_stage_completion(stage: str, completion_percentage: float) -> bool:
    """Record the completion of a batch stage.

    Args:
        stage: The stage that completed (scrape, enrich, dedupe, score, mockup, email).
        completion_percentage: The percentage of completion (0-100).

    Returns:
        True if successful, False otherwise.
    """
    try:
        data = load_tracker_data()

        # If no current batch, start one
        if not data["current_batch_start"]:
            record_batch_start()
            data = load_tracker_data()

        # Record stage completion
        current_time = datetime.utcnow().isoformat()
        data["current_batch_stages"][stage] = {
            "timestamp": current_time,
            "completion_percentage": completion_percentage,
        }

        # Update batch completion gauge
        BATCH_COMPLETION_GAUGE.labels(stage=stage).set(completion_percentage)

        # Save updated data
        success = save_tracker_data(data)
        if success:
            logger.info(
                f"Recorded {stage} stage completion: "
                f"{completion_percentage}% at {current_time}"
            )

        return success
    except Exception as e:
        logger.error(f"Error recording batch stage completion: {e}")
        return False


def record_batch_end() -> bool:
    """Record the end of the current batch.

    Returns:
        True if successful, False otherwise.
    """
    try:
        data = load_tracker_data()

        # If no current batch, log warning and return
        if not data["current_batch_start"]:
            logger.warning("No current batch to end")
            return False

        # Record batch end time
        current_time = datetime.utcnow().isoformat()
        data["last_batch_end"] = current_time

        # Set all stages to 100% completion
        for stage in ["scrape", "enrich", "dedupe", "score", "mockup", "email"]:
            if stage not in data["current_batch_stages"]:
                data["current_batch_stages"][stage] = {
                    "timestamp": current_time,
                    "completion_percentage": 100.0,
                }
            BATCH_COMPLETION_GAUGE.labels(stage=stage).set(100.0)

        # Save updated data
        success = save_tracker_data(data)
        if success:
            logger.info(f"Recorded batch end at {current_time}")

            # Calculate batch duration
            try:
                start_time = datetime.fromisoformat(data["current_batch_start"])
                end_time = datetime.fromisoformat(current_time)
                duration = end_time - start_time
                logger.info(f"Batch completed in {duration}")
            except Exception as e:
                logger.warning(f"Error calculating batch duration: {e}")

        return success
    except Exception as e:
        logger.error(f"Error recording batch end: {e}")
        return False


def check_batch_completion() -> Tuple[bool, Optional[str]]:
    """Check if the current batch completed on time.

    Returns:
        Tuple of (completed_on_time, reason).
    """
    try:
        data = load_tracker_data()

        # If no current batch, return True (nothing to check)
        if not data["current_batch_start"]:
            return True, "No current batch"

        # Get current time in EST
        import pytz

        est_tz = pytz.timezone(BATCH_COMPLETION_TIMEZONE)
        current_time = datetime.now(est_tz)

        # Check if it's past the deadline
        deadline_passed = current_time.hour > BATCH_COMPLETION_DEADLINE_HOUR or (
            current_time.hour == BATCH_COMPLETION_DEADLINE_HOUR
            and current_time.minute >= BATCH_COMPLETION_DEADLINE_MINUTE
        )

        if deadline_passed:
            # Check if batch has an end timestamp
            if data["last_batch_end"]:
                # Check if the end timestamp is from today
                last_end = datetime.fromisoformat(
                    data["last_batch_end"].replace("Z", "+00:00")
                )
                last_end_est = last_end.astimezone(est_tz)

                if last_end_est.date() == current_time.date():
                    # Batch completed today, we're good
                    return True, "Batch completed today"
                else:
                    # Batch didn't complete today
                    reason = (
                        f"Last batch completed on {last_end_est.date()}, "
                        f"not today ({current_time.date()})"
                    )
                    logger.warning(reason)

                    # Record alert
                    alert = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "type": "batch_completion",
                        "message": reason,
                    }
                    data["alerts"].append(alert)
                    save_tracker_data(data)

                    return False, reason
            else:
                # No end timestamp at all
                reason = "No batch completion recorded and deadline has passed"
                logger.warning(reason)

                # Record alert
                alert = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "batch_completion",
                    "message": reason,
                }
                data["alerts"].append(alert)
                save_tracker_data(data)

                return False, reason
        else:
            # Not past deadline yet
            return True, "Deadline not yet passed"
    except Exception as e:
        logger.error(f"Error checking batch completion: {e}")
        return False, f"Error checking batch completion: {e}"


def get_batch_status() -> dict:
    """Get the current batch status.

    Returns:
        Dictionary with batch status information.
    """
    try:
        data = load_tracker_data()

        # Calculate completion percentage across all stages
        completion_percentage = 0.0
        if data["current_batch_stages"]:
            stage_percentages = [
                stage_data["completion_percentage"]
                for stage_data in data["current_batch_stages"].values()
            ]
            completion_percentage = sum(stage_percentages) / len(stage_percentages)

        # Get deadline in EST
        import pytz

        est_tz = pytz.timezone(BATCH_COMPLETION_TIMEZONE)
        now = datetime.now(est_tz)
        deadline = now.replace(
            hour=BATCH_COMPLETION_DEADLINE_HOUR,
            minute=BATCH_COMPLETION_DEADLINE_MINUTE,
            second=0,
            microsecond=0,
        )

        # If deadline is in the past for today, set it to tomorrow
        if now > deadline:
            deadline = deadline + timedelta(days=1)

        # Format deadline for display
        deadline_str = deadline.strftime("%Y-%m-%d %H:%M:%S %Z")

        # Check if batch is complete
        completed_on_time, reason = check_batch_completion()

        return {
            "current_batch_start": data["current_batch_start"],
            "last_batch_end": data["last_batch_end"],
            "completion_percentage": completion_percentage,
            "stages": data["current_batch_stages"],
            "deadline": deadline_str,
            "completed_on_time": completed_on_time,
            "reason": reason,
            "alerts": (
                data["alerts"][-5:] if data["alerts"] else []
            ),  # Return last 5 alerts
        }
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        return {"error": f"Error getting batch status: {e}"}


# Initialize batch tracker on module import
ensure_tracker_file_exists()
