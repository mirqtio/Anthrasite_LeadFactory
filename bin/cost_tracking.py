#!/usr/bin/env python
"""
Cost Tracking and Metrics
----------------------
This module provides cost tracking and metrics for the Anthrasite LeadFactory

It offers the following core features:
- Tracking of API costs per request/operation
- Batch-level cost tracking
- Monthly budget management
- GPU usage cost tracking
- Cost per lead calculation
- Integration with budget gate for cost control

The CostTracker class is exposed as a singleton instance at the module level.

Usage:
    from bin.cost_tracking import cost_tracker

    # Track a specific API cost
    cost_tracker.add_cost(0.25, "openai", "gpt-4", {"tokens": 1500})

    # Start a batch for grouping related costs
    batch_id = cost_tracker.start_batch()

    # Add costs to the batch
    cost_tracker.add_cost(0.10, "openai", "gpt-4", {"tokens": 500}, batch_id=batch_id)

    # End the batch and get summary
    summary = cost_tracker.end_batch(leads_processed=10)
    print(f"Cost per lead: ${summary['cost_per_lead']:.2f}")
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

# Import metrics - using proper path handling
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from bin.metrics import metrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "cost_tracking.log")),
    ],
)
logger = logging.getLogger(__name__)


class CostTracker:
    """Cost tracking and metrics for LeadFactory."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize cost tracker.

        Args:
            db_path: Path to SQLite database for cost tracking
        """
        # Set default database path if not provided
        if not db_path:
            db_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
            )
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "cost_tracking.db")

        self.db_path = db_path

        # Initialize database
        self._init_db()

        # Initialize GPU tracking
        self.gpu_tracking_active = False
        self.gpu_start_time: Optional[datetime] = None
        self.gpu_hourly_rate = float(os.environ.get("GPU_HOURLY_RATE", "2.5"))

        # Initialize batch tracking
        self.current_batch_id: Optional[str] = None
        self.current_batch_start_time: Optional[datetime] = None
        self.current_batch_costs: Dict[str, float] = {}

        # Load tier thresholds
        self.tier_thresholds = {
            "1": {"warning": 3.0, "critical": 4.0},
            "2": {"warning": 5.0, "critical": 7.0},
            "3": {"warning": 8.0, "critical": 10.0},
        }

        # Load budget gate threshold
        self.budget_gate_threshold = float(
            os.environ.get("BUDGET_GATE_THRESHOLD", "1000.0")
        )
        self.budget_gate_active = False

        # Start budget gate check thread
        self._start_budget_gate_check()

        logger.info(f"Cost tracker initialized (db_path={db_path})")

    def _init_db(self):
        """Initialize the cost tracking database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create costs table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                batch_id TEXT,
                service TEXT NOT NULL,
                operation TEXT,
                amount REAL NOT NULL,
                details TEXT
            )
            """
            )

            # Create batches table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                leads_processed INTEGER,
                tier TEXT,
                cost_per_lead REAL,
                total_cost REAL,
                status TEXT
            )
            """
            )

            # Create monthly budget table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS monthly_budget (
                year INTEGER,
                month INTEGER,
                budget REAL,
                spent REAL,
                PRIMARY KEY (year, month)
            )
            """
            )

            conn.commit()
            conn.close()

            logger.info("Cost tracking database initialized")
        except Exception as e:
            logger.exception(f"Error initializing database: {e}")

    def add_cost(
        self,
        amount: float,
        service: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        batch_id: Optional[str] = None,
    ):
        """Add a cost entry.

        Args:
            amount: Cost amount in USD
            service: Service name (e.g., openai, semrush, gpu)
            operation: Operation name (e.g., gpt-4, domain-overview)
            details: Additional details as a dictionary
            batch_id: Batch ID for batch-specific costs
        """
        try:
            # Use current batch ID if not provided
            if not batch_id and self.current_batch_id:
                batch_id = self.current_batch_id

            # Add to current batch costs if applicable
            if batch_id and batch_id == self.current_batch_id:
                if service not in self.current_batch_costs:
                    self.current_batch_costs[service] = 0
                self.current_batch_costs[service] += amount

            # Add to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            INSERT INTO costs (timestamp, batch_id, service, operation, amount, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.now().isoformat(),
                    batch_id,
                    service,
                    operation,
                    amount,
                    json.dumps(details) if details else None,
                ),
            )

            conn.commit()
            conn.close()

            # Update metrics
            metrics.add_cost(amount, service=service)

            # Update monthly budget
            self._update_monthly_spent(amount)

            logger.info(
                f"Added cost: ${amount:.2f} for {service}{f'/{operation}' if operation else ''}"
            )

            return True
        except Exception as e:
            logger.exception(f"Error adding cost: {e}")
            return False

    def start_batch(self, batch_id: Optional[str] = None, tier: str = "1"):
        """Start a new batch for cost tracking.

        Args:
            batch_id: Batch ID (default: generated from timestamp)
            tier: Tier level (1, 2, or 3)

        Returns:
            Batch ID
        """
        try:
            # Generate batch ID if not provided
            if not batch_id:
                batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Set current batch
            self.current_batch_id = batch_id
            self.current_batch_start_time = datetime.now()
            self.current_batch_costs = {}

            # Add to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Ensure current_batch_start_time is not None before calling isoformat
            start_time_iso = (
                self.current_batch_start_time.isoformat()
                if self.current_batch_start_time
                else datetime.now().isoformat()
            )

            cursor.execute(
                """
            INSERT INTO batches (id, start_time, tier, status)
            VALUES (?, ?, ?, ?)
            """,
                (batch_id, start_time_iso, tier, "running"),
            )

            conn.commit()
            conn.close()

            logger.info(f"Started batch: {batch_id} (tier={tier})")

            return batch_id
        except Exception as e:
            logger.exception(f"Error starting batch: {e}")
            return None

    def end_batch(self, leads_processed: int, status: str = "completed"):
        """End the current batch and calculate cost per lead.

        Args:
            leads_processed: Number of leads processed in the batch
            status: Batch status (completed, failed, etc.)

        Returns:
            Dictionary with batch summary
        """
        if not self.current_batch_id:
            logger.warning("No active batch to end")
            return None

        try:
            # Calculate total cost
            total_cost = sum(self.current_batch_costs.values())

            # Calculate cost per lead
            cost_per_lead = total_cost / leads_processed if leads_processed > 0 else 0

            # Get batch details
            batch_id = self.current_batch_id
            start_time = self.current_batch_start_time
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get tier
            cursor.execute("SELECT tier FROM batches WHERE id = ?", (batch_id,))
            result = cursor.fetchone()
            tier = result[0] if result else "1"

            cursor.execute(
                """
            UPDATE batches
            SET end_time = ?, leads_processed = ?, cost_per_lead = ?, total_cost = ?, status = ?
            WHERE id = ?
            """,
                (
                    end_time.isoformat(),
                    leads_processed,
                    cost_per_lead,
                    total_cost,
                    status,
                    batch_id,
                ),
            )

            conn.commit()
            conn.close()

            # Update metrics
            metrics.update_cost_per_lead(cost_per_lead, tier=tier)
            metrics.update_batch_completed()
            metrics.increment_batch_leads(leads_processed, status="processed")
            metrics.observe_batch_duration(duration)

            # Check against thresholds
            threshold_warning = self.tier_thresholds.get(tier, {}).get("warning", 999)
            threshold_critical = self.tier_thresholds.get(tier, {}).get("critical", 999)

            if cost_per_lead > threshold_critical:
                logger.critical(
                    f"Cost per lead (${cost_per_lead:.2f}) exceeds critical threshold "
                    f"(${threshold_critical:.2f}) for tier {tier}"
                )
            elif cost_per_lead > threshold_warning:
                logger.warning(
                    f"Cost per lead (${cost_per_lead:.2f}) exceeds warning threshold "
                    f"(${threshold_warning:.2f}) for tier {tier}"
                )

            # Reset current batch
            self.current_batch_id = None
            self.current_batch_start_time = None
            self.current_batch_costs = {}

            logger.info(
                f"Ended batch: {batch_id} (leads={leads_processed}, "
                f"cost_per_lead=${cost_per_lead:.2f}, total_cost=${total_cost:.2f})"
            )

            return {
                "batch_id": batch_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "leads_processed": leads_processed,
                "total_cost": total_cost,
                "cost_per_lead": cost_per_lead,
                "costs_by_service": self.current_batch_costs,
                "tier": tier,
                "status": status,
            }
        except Exception as e:
            logger.exception(f"Error ending batch: {e}")
            return None

    def calculate_cost_per_lead(self, leads_processed: int, tier: str = "1"):
        """Calculate cost per lead for the current batch.

        Args:
            leads_processed: Number of leads processed
            tier: Tier level (1, 2, or 3)

        Returns:
            Cost per lead
        """
        try:
            # Calculate total cost for current batch
            total_cost = sum(self.current_batch_costs.values())

            # Calculate cost per lead
            cost_per_lead = total_cost / leads_processed if leads_processed > 0 else 0

            # Update metrics
            metrics.update_cost_per_lead(cost_per_lead, tier=tier)

            # Check against thresholds
            threshold_warning = self.tier_thresholds.get(tier, {}).get("warning", 999)
            threshold_critical = self.tier_thresholds.get(tier, {}).get("critical", 999)

            if cost_per_lead > threshold_critical:
                logger.critical(
                    f"Cost per lead (${cost_per_lead:.2f}) exceeds critical threshold "
                    f"(${threshold_critical:.2f}) for tier {tier}"
                )
            elif cost_per_lead > threshold_warning:
                logger.warning(
                    f"Cost per lead (${cost_per_lead:.2f}) exceeds warning threshold "
                    f"(${threshold_warning:.2f}) for tier {tier}"
                )

            logger.info(
                f"Calculated cost per lead: ${cost_per_lead:.2f} "
                f"(tier={tier}, leads={leads_processed}, total_cost=${total_cost:.2f})"
            )

            return cost_per_lead
        except Exception as e:
            logger.exception(f"Error calculating cost per lead: {e}")
            return 0

    def start_gpu_tracking(self, hourly_rate: Optional[float] = None):
        """Start tracking GPU usage costs.

        Args:
            hourly_rate: Hourly rate for GPU usage in USD
        """
        if hourly_rate:
            self.gpu_hourly_rate = hourly_rate

        self.gpu_tracking_active = True
        # Update the existing gpu_start_time variable
        self.gpu_start_time = datetime.now()

        # Add initial cost entry
        self.add_cost(
            0.0,
            service="gpu",
            operation="start",
            details={
                "hourly_rate": self.gpu_hourly_rate,
                "start_time": (
                    self.gpu_start_time.isoformat()
                    if self.gpu_start_time
                    else datetime.now().isoformat()
                ),
            },
        )

        # Start tracking thread
        threading.Thread(target=self._track_gpu_cost, daemon=True).start()

        logger.info(f"Started GPU tracking (hourly_rate=${self.gpu_hourly_rate:.2f})")

    def stop_gpu_tracking(self):
        """Stop tracking GPU usage costs."""
        if not self.gpu_tracking_active:
            logger.warning("GPU tracking not active")
            return

        self.gpu_tracking_active = False
        end_time = datetime.now()

        # Calculate final cost
        if self.gpu_start_time:
            hours_used = (end_time - self.gpu_start_time).total_seconds() / 3600
            final_cost = hours_used * self.gpu_hourly_rate

            # Add final cost entry
            self.add_cost(
                final_cost,
                service="gpu",
                operation="stop",
                details={
                    "hourly_rate": self.gpu_hourly_rate,
                    "start_time": self.gpu_start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "hours_used": hours_used,
                },
            )

            logger.info(
                f"Stopped GPU tracking (hours_used={hours_used:.2f}, final_cost=${final_cost:.2f})"
            )
        else:
            logger.warning("GPU tracking stopped but no start time recorded")

    def _track_gpu_cost(self):
        """Background thread to track GPU costs."""
        last_update = datetime.now()
        daily_cost = 0.0

        while self.gpu_tracking_active:
            try:
                # Sleep for a while
                time.sleep(60)  # Update every minute

                # Skip if not active anymore
                if not self.gpu_tracking_active:
                    break

                # Calculate cost since last update
                now = datetime.now()
                hours_since_update = (now - last_update).total_seconds() / 3600
                cost_since_update = hours_since_update * self.gpu_hourly_rate

                # Add incremental cost
                if cost_since_update > 0:
                    self.add_cost(
                        cost_since_update,
                        service="gpu",
                        operation="usage",
                        details={
                            "hourly_rate": self.gpu_hourly_rate,
                            "start_time": last_update.isoformat(),
                            "end_time": now.isoformat(),
                            "hours_used": hours_since_update,
                        },
                    )

                # Update daily cost
                daily_cost += cost_since_update

                # Reset daily cost at midnight
                if now.date() != last_update.date():
                    logger.info(f"Daily GPU cost: ${daily_cost:.2f}")
                    daily_cost = 0.0

                # Update metrics
                metrics.update_gpu_cost_daily(daily_cost)

                # Update last update time
                last_update = now
            except Exception as e:
                logger.error(f"Error in GPU tracking thread: {e}")

    def get_monthly_costs(
        self, year: Optional[int] = None, month: Optional[int] = None
    ):
        """Get costs for a specific month.

        Args:
            year: Year (default: current year)
            month: Month (default: current month)

        Returns:
            Dictionary with monthly costs
        """
        try:
            # Use current year/month if not provided
            if not year or not month:
                now = datetime.now()
                year = year or now.year
                month = month or now.month

            # Query database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get monthly budget
            cursor.execute(
                """
            SELECT budget, spent FROM monthly_budget
            WHERE year = ? AND month = ?
            """,
                (year, month),
            )

            budget_row = cursor.fetchone()
            budget = budget_row["budget"] if budget_row else 0
            spent = budget_row["spent"] if budget_row else 0

            # Get costs by service
            cursor.execute(
                """
            SELECT service, SUM(amount) as total
            FROM costs
            WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?
            GROUP BY service
            """,
                (str(year), str(month).zfill(2)),
            )

            costs_by_service = {
                row["service"]: row["total"] for row in cursor.fetchall()
            }

            # Get batch statistics
            cursor.execute(
                """
            SELECT COUNT(*) as batch_count, AVG(cost_per_lead) as avg_cost_per_lead,
                   SUM(leads_processed) as total_leads
            FROM batches
            WHERE strftime('%Y', start_time) = ? AND strftime('%m', start_time) = ?
            """,
                (str(year), str(month).zfill(2)),
            )

            batch_stats = dict(cursor.fetchone())

            conn.close()

            result = {
                "year": year,
                "month": month,
                "budget": budget,
                "spent": spent,
                "remaining": budget - spent,
                "costs_by_service": costs_by_service,
                "batch_statistics": batch_stats,
            }

            logger.info(
                f"Retrieved monthly costs for {year}-{month}: spent=${spent:.2f}, budget=${budget:.2f}"
            )

            return result
        except Exception as e:
            logger.exception(f"Error getting monthly costs: {e}")
            return None

    def set_monthly_budget(
        self, amount: float, year: Optional[int] = None, month: Optional[int] = None
    ):
        """Set budget for a specific month.

        Args:
            amount: Budget amount in USD
            year: Year (default: current year)
            month: Month (default: current month)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use current year/month if not provided
            if not year or not month:
                now = datetime.now()
                year = year or now.year
                month = month or now.month

            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            INSERT OR REPLACE INTO monthly_budget (year, month, budget, spent)
            VALUES (?, ?, ?, COALESCE((SELECT spent FROM monthly_budget WHERE year = ? AND month = ?), 0))
            """,
                (year, month, amount, year, month),
            )

            conn.commit()
            conn.close()

            logger.info(f"Set monthly budget for {year}-{month}: ${amount:.2f}")

            return True
        except Exception as e:
            logger.exception(f"Error setting monthly budget: {e}")
            return False

    def _update_monthly_spent(self, amount: float):
        """Update the spent amount for the current month.

        Args:
            amount: Amount to add to spent
        """
        try:
            # Get current year/month
            now = datetime.now()
            year = now.year
            month = now.month

            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if entry exists
            cursor.execute(
                """
            SELECT spent FROM monthly_budget
            WHERE year = ? AND month = ?
            """,
                (year, month),
            )

            row = cursor.fetchone()

            if row:
                # Update existing entry
                cursor.execute(
                    """
                UPDATE monthly_budget
                SET spent = spent + ?
                WHERE year = ? AND month = ?
                """,
                    (amount, year, month),
                )
            else:
                # Create new entry
                cursor.execute(
                    """
                INSERT INTO monthly_budget (year, month, budget, spent)
                VALUES (?, ?, 0, ?)
                """,
                    (year, month, amount),
                )

            conn.commit()

            # Check if budget gate should be activated
            cursor.execute(
                """
            SELECT budget, spent FROM monthly_budget
            WHERE year = ? AND month = ?
            """,
                (year, month),
            )

            row = cursor.fetchone()

            if row and row[0] > 0:
                budget = row[0]
                spent = row[1]

                if spent >= budget:
                    self.budget_gate_active = True
                    logger.warning(
                        f"Budget gate activated: spent (${spent:.2f}) exceeds budget (${budget:.2f})"
                    )
                    metrics.update_budget_gate_status(True)

            conn.close()
        except Exception as e:
            logger.error(f"Error updating monthly spent: {e}")

    def is_budget_gate_active(self):
        """Check if the budget gate is active.

        Returns:
            True if budget gate is active, False otherwise
        """
        return self.budget_gate_active

    def _start_budget_gate_check(self):
        """Start a background thread to check the budget gate status."""

        def check_budget_gate():
            while True:
                try:
                    # Get current year/month
                    now = datetime.now()
                    year = now.year
                    month = now.month

                    # Query database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                    SELECT budget, spent FROM monthly_budget
                    WHERE year = ? AND month = ?
                    """,
                        (year, month),
                    )

                    row = cursor.fetchone()

                    if row and row[0] > 0:
                        budget = row[0]
                        spent = row[1]

                        # Update budget gate status
                        was_active = self.budget_gate_active
                        self.budget_gate_active = spent >= budget

                        if self.budget_gate_active != was_active:
                            if self.budget_gate_active:
                                logger.warning(
                                    f"Budget gate activated: spent (${spent:.2f}) exceeds budget (${budget:.2f})"
                                )
                            else:
                                logger.info(
                                    f"Budget gate deactivated: spent (${spent:.2f}) is below budget (${budget:.2f})"
                                )

                        # Update metrics
                        metrics.update_budget_gate_status(self.budget_gate_active)

                    conn.close()
                except Exception as e:
                    logger.error(f"Error in budget gate check thread: {e}")

                # Sleep for a while
                time.sleep(300)  # Check every 5 minutes

        # Start thread
        thread = threading.Thread(target=check_budget_gate, daemon=True)
        thread.start()
        logger.info("Started budget gate check thread")


# Create a singleton instance
cost_tracker = CostTracker()

# Example usage
if __name__ == "__main__":
    # Set monthly budget
    cost_tracker.set_monthly_budget(1000.0)

    # Start a batch
    batch_id = cost_tracker.start_batch(tier="1")

    # Add some costs
    cost_tracker.add_cost(0.12, service="openai", operation="gpt-4")
    cost_tracker.add_cost(0.05, service="semrush", operation="domain-overview")

    # Start GPU tracking
    cost_tracker.start_gpu_tracking(hourly_rate=2.5)

    # Simulate some time passing
    time.sleep(2)

    # Stop GPU tracking
    cost_tracker.stop_gpu_tracking()

    # End batch
    batch_summary = cost_tracker.end_batch(leads_processed=10)

    # Print batch summary

    # Get monthly costs
    monthly_costs = cost_tracker.get_monthly_costs()

    # Print monthly costs
