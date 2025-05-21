#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: GPU Usage Tracker
Monitors and tracks GPU usage when GPU_BURST flag is set.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import cost metrics
from utils.cost_metrics import track_gpu_usage, check_gpu_cost_threshold
# Import logging configuration
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Constants
CHECK_INTERVAL = int(os.getenv("GPU_USAGE_CHECK_INTERVAL_SECONDS", "3600"))  # 1 hour
GPU_BURST_COST = float(os.getenv("GPU_BURST_COST_DOLLARS", "0.50"))  # $0.50 per hour
DAILY_THRESHOLD = float(os.getenv("GPU_COST_DAILY_THRESHOLD", "25.0"))  # $25 per day
MONTHLY_THRESHOLD = float(os.getenv("GPU_COST_MONTHLY_THRESHOLD", "100.0"))  # $100 per month


def check_and_track_gpu_usage() -> bool:
    """Check if GPU_BURST flag is set and track usage if it is.
    
    Returns:
        True if GPU usage was tracked, False otherwise.
    """
    # Check if GPU_BURST environment flag is set
    gpu_burst = os.getenv("GPU_BURST", "0").lower() in ("1", "true", "yes")
    
    if not gpu_burst:
        logger.debug("GPU_BURST flag is not set, skipping tracking")
        return False
    
    # Track GPU usage
    tracked = track_gpu_usage(GPU_BURST_COST)
    
    if tracked:
        # Check if thresholds are exceeded
        exceeded, reason = check_gpu_cost_threshold(DAILY_THRESHOLD, MONTHLY_THRESHOLD)
        
        if exceeded:
            logger.warning(f"GPU cost threshold exceeded: {reason}")
            
            # Send alert email if configured
            alert_email = os.getenv("ALERT_EMAIL_TO")
            if alert_email:
                try:
                    from utils.email_utils import send_alert_email
                    
                    subject = f"ALERT: GPU Cost Threshold Exceeded"
                    message = f"""
GPU Cost Alert

Status: THRESHOLD EXCEEDED
Reason: {reason}
Time: {datetime.utcnow().isoformat()}

Please check the GPU usage and consider disabling GPU_BURST if costs are too high.
"""
                    
                    send_alert_email(subject, message)
                    logger.info(f"Sent GPU cost alert email to {alert_email}")
                except Exception as e:
                    logger.error(f"Error sending GPU cost alert email: {e}")
    
    return tracked


def monitor_gpu_usage(interval: int = CHECK_INTERVAL) -> None:
    """Monitor GPU usage continuously.
    
    Args:
        interval: Check interval in seconds.
    """
    logger.info(f"Starting GPU usage monitor (interval: {interval}s)")
    
    while True:
        try:
            check_and_track_gpu_usage()
        except Exception as e:
            logger.error(f"Error in GPU usage monitor: {e}")
        
        # Sleep until next check
        time.sleep(interval)


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="GPU Usage Tracker")
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Check interval in seconds (default: {CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run check once and exit",
    )
    args = parser.parse_args()
    
    try:
        if args.once:
            # Run check once
            check_and_track_gpu_usage()
        else:
            # Run continuous monitor
            monitor_gpu_usage(args.interval)
    except KeyboardInterrupt:
        logger.info("GPU usage monitor stopped by user")
    except Exception as e:
        logger.error(f"GPU usage monitor failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
