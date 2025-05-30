"""
Cost Tracking and Metrics
----------------------
This module provides cost tracking and metrics for the LeadFactory system.

It offers the following core features:
- Tracking of API costs per request/operation
- Batch-level cost tracking
- Monthly budget management
- GPU usage cost tracking
- Cost per lead calculation
- Integration with budget gate for cost control

The CostTracker class is exposed as a singleton instance at the module level.
"""

import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Import the unified logging system
from leadfactory.utils.logging import get_logger

# Set up logging using the unified system
logger = get_logger(__name__)


def _get_metrics():
    """Get metrics singleton instance."""
    try:
        from leadfactory.utils.metrics import metrics

        return metrics
    except ImportError:
        logger.warning("Metrics not available")
        return None


# Create reference to use in the code
metrics = _get_metrics()


class CostTracker:
    """Cost tracking and metrics for LeadFactory."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize cost tracker.

        Args:
            db_path: Path to SQLite database for cost tracking
        """
        # Set default database path if not provided
        if not db_path:
            # Use pathlib for better path handling
            db_dir = Path(__file__).parent.parent / "data"
            # Create directory if it doesn't exist
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "cost_tracking.db")

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
        self.current_batch_costs: dict[str, float] = {}

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

        logger.info(f"Cost tracker initialized (db_path={db_path})")

    def _init_db(self) -> None:
        """Initialize the cost tracking database."""
        # Create connection
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                service TEXT NOT NULL,
                operation TEXT,
                amount REAL NOT NULL,
                details TEXT,
                batch_id TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                tier TEXT NOT NULL,
                leads_processed INTEGER,
                total_cost REAL,
                cost_per_lead REAL,
                status TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_budgets (
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                budget REAL NOT NULL,
                spent REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (year, month)
            )
            """
        )

        # Create indices
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_costs_timestamp ON costs (timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_costs_service ON costs (service)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_costs_batch_id ON costs (batch_id)"
        )

        # Commit and close
        conn.commit()
        conn.close()

        logger.debug("Database initialized")

    def add_cost(
        self,
        amount: float,
        service: str,
        operation: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        batch_id: Optional[str] = None,
    ) -> None:
        """Add a cost entry.

        Args:
            amount: Cost amount in USD
            service: Service name (e.g., openai, semrush, gpu)
            operation: Operation name (e.g., gpt-4, domain-overview)
            details: Additional details as a dictionary
            batch_id: Batch ID for batch-specific costs
        """
        # Ensure positive amount
        amount = max(0, amount)

        # Use current batch ID if not specified
        if batch_id is None and self.current_batch_id is not None:
            batch_id = self.current_batch_id

        # Add to current batch costs
        if batch_id == self.current_batch_id:
            service_key = f"{service}/{operation or 'unknown'}"
            if service_key not in self.current_batch_costs:
                self.current_batch_costs[service_key] = 0
            self.current_batch_costs[service_key] += amount

        # Serialize details
        details_json = None
        if details:
            details_json = json.dumps(details)

        # Record timestamp
        timestamp = datetime.now().isoformat()

        # Insert into database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO costs (timestamp, service, operation, amount, details, batch_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (timestamp, service, operation, amount, details_json, batch_id),
        )
        conn.commit()
        conn.close()

        # Update monthly spent
        self._update_monthly_spent(amount)

        # Update metrics
        if metrics:
            metrics.add_cost(amount, service)

        logger.debug(
            f"Cost added: ${amount:.2f} for {service}/{operation or 'unknown'}"
        )

    def get_daily_cost(self, service: Optional[str] = None) -> float:
        """Get the total cost for the current day.

        Args:
            service: Optional service name to filter by

        Returns:
            Total cost for the day
        """
        # Get today's date
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time()).isoformat()
        end_time = datetime.now().isoformat()

        # Query database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if service:
            cursor.execute(
                """
                SELECT SUM(amount) FROM costs
                WHERE timestamp >= ? AND timestamp <= ? AND service = ?
                """,
                (start_time, end_time, service),
            )
        else:
            cursor.execute(
                """
                SELECT SUM(amount) FROM costs
                WHERE timestamp >= ? AND timestamp <= ?
                """,
                (start_time, end_time),
            )

        result = cursor.fetchone()[0]
        conn.close()

        return result or 0.0

    def get_monthly_cost(self, service: Optional[str] = None) -> float:
        """Get the total cost for the current month.

        Args:
            service: Optional service name to filter by

        Returns:
            Total cost for the month
        """
        # Get current month
        today = datetime.now()
        year = today.year
        month = today.month

        # Get costs for this month
        return self.get_monthly_costs(year, month).get("spent", 0.0)

    def get_monthly_costs(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> dict[str, Any]:
        """Get costs for a specific month.

        Args:
            year: Year (default: current year)
            month: Month (default: current month)

        Returns:
            Dictionary with monthly costs
        """
        # Use current year/month if not specified
        if year is None or month is None:
            today = datetime.now()
            year = year or today.year
            month = month or today.month

        # Calculate start and end dates
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        start_time = start_date.isoformat()
        end_time = end_date.isoformat()

        # Query database for costs
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get total spent
        cursor.execute(
            """
            SELECT SUM(amount) FROM costs
            WHERE timestamp >= ? AND timestamp < ?
            """,
            (start_time, end_time),
        )
        spent = cursor.fetchone()[0] or 0.0

        # Get budget
        cursor.execute(
            """
            SELECT budget FROM monthly_budgets
            WHERE year = ? AND month = ?
            """,
            (year, month),
        )
        result = cursor.fetchone()
        budget = result[0] if result else 0.0

        # Get breakdown by service
        cursor.execute(
            """
            SELECT service, SUM(amount) FROM costs
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY service
            """,
            (start_time, end_time),
        )
        services = {row[0]: row[1] for row in cursor.fetchall()}

        # Get breakdown by service and operation
        cursor.execute(
            """
            SELECT service, operation, SUM(amount) FROM costs
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY service, operation
            """,
            (start_time, end_time),
        )
        operations = {}
        for row in cursor.fetchall():
            service, operation, amount = row
            if service not in operations:
                operations[service] = {}
            operations[service][operation or "unknown"] = amount

        conn.close()

        return {
            "year": year,
            "month": month,
            "budget": budget,
            "spent": spent,
            "remaining": budget - spent if budget > 0 else 0.0,
            "services": services,
            "operations": operations,
        }

    def get_daily_cost_breakdown(self) -> dict[str, dict[str, float]]:
        """Get cost breakdown by service and operation for the current day.

        Returns:
            Dictionary mapping service names to dictionaries of operation costs
        """
        # Get today's date
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time()).isoformat()
        end_time = datetime.now().isoformat()

        # Query database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT service, operation, SUM(amount) FROM costs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY service, operation
            """,
            (start_time, end_time),
        )

        # Build breakdown
        breakdown = {}
        for row in cursor.fetchall():
            service, operation, amount = row
            if service not in breakdown:
                breakdown[service] = {}
            breakdown[service][operation or "unknown"] = amount

        conn.close()

        return breakdown

    def get_monthly_cost_breakdown(self) -> dict[str, dict[str, float]]:
        """Get cost breakdown by service and operation for the current month.

        Returns:
            Dictionary mapping service names to dictionaries of operation costs
        """
        # Get current month
        today = datetime.now()
        year = today.year
        month = today.month

        # Get costs for this month
        costs = self.get_monthly_costs(year, month)
        return costs.get("operations", {})

    def set_monthly_budget(
        self, amount: float, year: Optional[int] = None, month: Optional[int] = None
    ) -> bool:
        """Set budget for a specific month.

        Args:
            amount: Budget amount in USD
            year: Year (default: current year)
            month: Month (default: current month)

        Returns:
            True if successful, False otherwise
        """
        # Use current year/month if not specified
        if year is None or month is None:
            today = datetime.now()
            year = year or today.year
            month = month or today.month

        # Ensure positive amount
        amount = max(0, amount)

        # Set budget in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if budget exists
        cursor.execute(
            """
            SELECT budget FROM monthly_budgets
            WHERE year = ? AND month = ?
            """,
            (year, month),
        )
        result = cursor.fetchone()

        if result:
            # Update existing budget
            cursor.execute(
                """
                UPDATE monthly_budgets
                SET budget = ?
                WHERE year = ? AND month = ?
                """,
                (amount, year, month),
            )
        else:
            # Create new budget
            cursor.execute(
                """
                INSERT INTO monthly_budgets (year, month, budget, spent)
                VALUES (?, ?, ?, 0.0)
                """,
                (year, month, amount),
            )

        conn.commit()
        conn.close()

        logger.info(f"Monthly budget set: ${amount:.2f} for {year}-{month}")
        return True

    def _update_monthly_spent(self, amount: float) -> None:
        """Update the spent amount for the current month.

        Args:
            amount: Amount to add to spent
        """
        # Get current month
        today = datetime.now()
        year = today.year
        month = today.month

        # Update spent in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if budget exists
        cursor.execute(
            """
            SELECT budget, spent FROM monthly_budgets
            WHERE year = ? AND month = ?
            """,
            (year, month),
        )
        result = cursor.fetchone()

        if result:
            # Update existing spent
            budget, spent = result
            new_spent = spent + amount
            cursor.execute(
                """
                UPDATE monthly_budgets
                SET spent = ?
                WHERE year = ? AND month = ?
                """,
                (new_spent, year, month),
            )

            # Check if over budget and update metrics
            if metrics and budget > 0 and new_spent >= budget:
                self.budget_gate_active = True
                metrics.update_budget_gate_status(active=True)
        else:
            # Create new budget with default values
            default_budget = self.budget_gate_threshold
            cursor.execute(
                """
                INSERT INTO monthly_budgets (year, month, budget, spent)
                VALUES (?, ?, ?, ?)
                """,
                (year, month, default_budget, amount),
            )

        conn.commit()
        conn.close()

    def is_budget_gate_active(self) -> bool:
        """Check if the budget gate is active.

        Returns:
            True if budget gate is active, False otherwise
        """
        # Get current month costs
        monthly_cost = self.get_monthly_cost()
        is_active = monthly_cost >= self.budget_gate_threshold

        # Update metrics
        if metrics and is_active:
            metrics.update_budget_gate_status(active=True)

        return is_active

    def export_cost_report(self, report_data: dict[str, Any], output_file: str) -> bool:
        """Export a cost report to a file.

        Args:
            report_data: Report data as a dictionary
            output_file: Output file path

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_file, "w") as f:
                json.dump(report_data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export cost report: {e}")
            return False

    def get_daily_cost_report(self) -> dict[str, Any]:
        """Get a cost report for the current day.

        Returns:
            Dictionary with cost report data
        """
        # Get today's date
        today = datetime.now()

        # Basic info
        report = {
            "date": today.strftime("%Y-%m-%d"),
            "total_cost": self.get_daily_cost(),
            "breakdown": self.get_daily_cost_breakdown(),
        }

        return report

    def get_monthly_cost_report(self) -> dict[str, Any]:
        """Get a cost report for the current month.

        Returns:
            Dictionary with cost report data
        """
        # Get current month
        today = datetime.now()

        # Get costs for this month
        costs = self.get_monthly_costs(today.year, today.month)

        # Add additional info
        costs["date"] = today.strftime("%Y-%m")
        costs["days_in_month"] = (
            datetime(today.year, today.month % 12 + 1, 1)
            if today.month < 12
            else datetime(today.year + 1, 1, 1)
        ).day
        costs["days_elapsed"] = today.day

        # Calculate projected costs
        if costs["days_elapsed"] > 0:
            daily_avg = costs["spent"] / costs["days_elapsed"]
            costs["projected_total"] = daily_avg * costs["days_in_month"]
        else:
            costs["projected_total"] = costs["spent"]

        return costs


def get_daily_cost(service: Optional[str] = None) -> float:
    """Get the total cost for the current day.

    Args:
        service: Optional service name to filter by

    Returns:
        Total cost for the day
    """
    return cost_tracker.get_daily_cost(service)


def get_monthly_cost(service: Optional[str] = None) -> float:
    """Get the total cost for the current month.

    Args:
        service: Optional service name to filter by

    Returns:
        Total cost for the month
    """
    return cost_tracker.get_monthly_cost(service)


def track_cost(
    service: str,
    operation: str,
    cost_dollars: float,
    tier: int = 1,
    business_id: Optional[int] = None,
) -> None:
    """Track a cost for an API call or operation.

    Args:
        service: Service name (e.g., openai, semrush)
        operation: Operation name (e.g., gpt-4, domain-overview)
        cost_dollars: Cost in USD
        tier: Tier level (1, 2, or 3)
        business_id: Optional business ID for cost attribution
    """
    details = {}
    if tier is not None:
        details["tier"] = tier
    if business_id is not None:
        details["business_id"] = business_id

    cost_tracker.add_cost(cost_dollars, service, operation, details)


def main() -> int:
    """Main entry point for the cost tracking module."""
    parser = argparse.ArgumentParser(description="Cost Tracking Tool")

    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Daily command
    daily_parser = subparsers.add_parser("daily", help="Show daily costs")
    daily_parser.add_argument("--service", type=str, help="Filter by service")
    daily_parser.add_argument("--export", type=str, help="Export to file")

    # Monthly command
    monthly_parser = subparsers.add_parser("monthly", help="Show monthly costs")
    monthly_parser.add_argument("--service", type=str, help="Filter by service")
    monthly_parser.add_argument("--year", type=int, help="Year (default: current year)")
    monthly_parser.add_argument(
        "--month", type=int, help="Month (default: current month)"
    )
    monthly_parser.add_argument("--export", type=str, help="Export to file")

    # Budget command
    budget_parser = subparsers.add_parser("budget", help="Set monthly budget")
    budget_parser.add_argument(
        "--amount", type=float, required=True, help="Budget amount in USD"
    )
    budget_parser.add_argument("--year", type=int, help="Year (default: current year)")
    budget_parser.add_argument(
        "--month", type=int, help="Month (default: current month)"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Execute command
    if args.command == "daily" or not args.command:
        # Get daily costs
        costs = cost_tracker.get_daily_cost(
            args.service if hasattr(args, "service") else None
        )
        logger.info(f"Daily costs: ${costs:.2f}")

        # Export if requested
        if hasattr(args, "export") and args.export:
            report = cost_tracker.get_daily_cost_report()
            if cost_tracker.export_cost_report(report, args.export):
                logger.info(
                    f"Daily cost report exported to {args.export}",
                    extra={"export_path": args.export},
                )
            else:
                logger.error("Failed to export daily cost report")
                return 1

    elif args.command == "monthly":
        # Get monthly costs
        year = args.year if hasattr(args, "year") and args.year else None
        month = args.month if hasattr(args, "month") and args.month else None

        if year and month:
            costs = cost_tracker.get_monthly_costs(year, month)
        else:
            costs = cost_tracker.get_monthly_costs()

        logger.info(
            f"Monthly costs for {costs['year']}-{costs['month']}",
            extra={
                "year": costs["year"],
                "month": costs["month"],
                "budget": costs["budget"],
                "spent": costs["spent"],
                "remaining": costs["remaining"],
            },
        )
        logger.info(f"  Budget: ${costs['budget']:.2f}")
        logger.info(f"  Spent: ${costs['spent']:.2f}")
        logger.info(f"  Remaining: ${costs['remaining']:.2f}")

        # Show breakdown by service
        logger.info("Breakdown by service:")
        for service, amount in costs["services"].items():
            logger.info(
                f"  {service}: ${amount:.2f}",
                extra={"service": service, "amount": amount},
            )

        # Export if requested
        if hasattr(args, "export") and args.export:
            report = (
                cost_tracker.get_monthly_cost_report()
                if not year and not month
                else costs
            )
            if cost_tracker.export_cost_report(report, args.export):
                logger.info(
                    f"Monthly cost report exported to {args.export}",
                    extra={"export_path": args.export},
                )
            else:
                logger.error("Failed to export monthly cost report")
                return 1

    elif args.command == "budget":
        # Set monthly budget
        year = args.year if hasattr(args, "year") and args.year else None
        month = args.month if hasattr(args, "month") and args.month else None

        if cost_tracker.set_monthly_budget(args.amount, year, month):
            logger.info(
                f"Monthly budget set to ${args.amount:.2f}",
                extra={"budget": args.amount},
            )
        else:
            logger.error("Failed to set monthly budget")
            return 1

    else:
        parser.print_help()
        return 1

    return 0


# Create a singleton instance
cost_tracker = CostTracker()
