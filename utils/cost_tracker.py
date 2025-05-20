#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Cost Tracker Utility
Tracks API and service costs for monitoring and budgeting.

This module provides functions to log costs, retrieve daily and monthly
totals, and check against budget thresholds.
"""

import os
import sys
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

# Import logging configuration
from .logging_config import get_logger

# Set up logging
logger = get_logger(__name__)

# Constants
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "lead_factory.db")
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "50.0"))  # $50 per day
MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", "1000.0"))  # $1000 per month
DAILY_ALERT_THRESHOLD = float(os.getenv("DAILY_ALERT_THRESHOLD", "0.8"))  # 80% of daily budget
MONTHLY_ALERT_THRESHOLD = float(os.getenv("MONTHLY_ALERT_THRESHOLD", "0.8"))  # 80% of monthly budget

# Scaling gate thresholds
SCALING_GATE_DAILY_THRESHOLD = float(os.getenv("SCALING_GATE_DAILY_THRESHOLD", "0.9"))  # 90% of daily budget
SCALING_GATE_MONTHLY_THRESHOLD = float(os.getenv("SCALING_GATE_MONTHLY_THRESHOLD", "0.9"))  # 90% of monthly budget
SCALING_GATE_ENABLED = os.getenv("SCALING_GATE_ENABLED", "true").lower() == "true"  # Enable/disable scaling gate
SCALING_GATE_LOCKFILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "scaling_gate.lock",
)
SCALING_GATE_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "scaling_gate_history.json",
)


def get_db_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database.

    Returns:
        SQLite connection object.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database: {e}")
        raise


def log_cost(service: str, operation: str, cost_dollars: float, check_scaling_gate: bool = True) -> bool:
    """Log a cost entry to the database.

    Args:
        service: Service name (e.g., 'openai', 'sendgrid').
        operation: Operation name (e.g., 'mockup_generation', 'email').
        cost_dollars: Cost in dollars.
        check_scaling_gate: Whether to check if operation is allowed by scaling gate.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Validate inputs
        if not service or not operation:
            logger.error("Service and operation are required")
            return False

        if cost_dollars < 0:
            logger.error("Cost cannot be negative")
            return False

        # Check if operation is allowed by scaling gate
        if check_scaling_gate:
            allowed, reason = should_allow_operation(service, operation)
            if not allowed:
                logger.warning(f"Operation not allowed by scaling gate: {service}.{operation} - {reason}")
                return False

        # Round cost to 4 decimal places
        cost_dollars = round(cost_dollars, 4)

        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert cost record
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO cost_tracking 
                (service, operation, cost_dollars, timestamp) 
                VALUES (?, ?, ?, ?)
                """,
                (service, operation, cost_dollars, timestamp),
            )
            conn.commit()

        logger.info(f"Logged cost: {service} {operation} ${cost_dollars:.4f}")

        # Check budget thresholds
        check_budget_thresholds()

        return True

    except Exception as e:
        logger.error(f"Error logging cost: {e}")
        return False


def get_daily_cost(service: Optional[str] = None) -> float:
    """Get total cost for today.

    Args:
        service: Optional service name to filter by.

    Returns:
        Total cost in dollars.
    """
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Build query
        query = """
            SELECT SUM(cost_dollars) as total_cost 
            FROM cost_tracking 
            WHERE date(timestamp) = ?
        """
        params = [today]

        # Add service filter if specified
        if service:
            query += " AND service = ?"
            params.append(service)

        # Execute query
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()

        # Return total cost or 0 if no results
        return float(result["total_cost"]) if result and result["total_cost"] else 0.0

    except Exception as e:
        logger.error(f"Error getting daily cost: {e}")
        return 0.0


def get_monthly_cost(service: Optional[str] = None) -> float:
    """Get total cost for the current month.

    Args:
        service: Optional service name to filter by.

    Returns:
        Total cost in dollars.
    """
    try:
        # Get current month
        current_month = datetime.now().strftime("%Y-%m")

        # Build query
        query = """
            SELECT SUM(cost_dollars) as total_cost 
            FROM cost_tracking 
            WHERE strftime('%Y-%m', timestamp) = ?
        """
        params = [current_month]

        # Add service filter if specified
        if service:
            query += " AND service = ?"
            params.append(service)

        # Execute query
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()

        # Return total cost or 0 if no results
        return float(result["total_cost"]) if result and result["total_cost"] else 0.0

    except Exception as e:
        logger.error(f"Error getting monthly cost: {e}")
        return 0.0


def get_cost_breakdown_by_service(
    period: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, float]:
    """Get cost breakdown by service for a specific period.

    Args:
        period: Time period ('day', 'week', 'month', 'custom').
        start_date: Start date for custom period (YYYY-MM-DD).
        end_date: End date for custom period (YYYY-MM-DD).

    Returns:
        Dictionary mapping service names to costs.
    """
    try:
        # Determine date range
        today = datetime.now()

        if period == "day":
            start_date = today.strftime("%Y-%m-%d")
            end_date = start_date
        elif period == "week":
            start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        elif period == "month":
            start_date = today.strftime("%Y-%m-01")
            end_date = today.strftime("%Y-%m-%d")
        elif period == "custom":
            if not start_date or not end_date:
                logger.error("Start date and end date are required for custom period")
                return {}
        else:
            logger.error(f"Invalid period: {period}")
            return {}

        # Build query
        query = """
            SELECT service, SUM(cost_dollars) as total_cost 
            FROM cost_tracking 
            WHERE date(timestamp) BETWEEN ? AND ?
            GROUP BY service
            ORDER BY total_cost DESC
        """

        # Execute query
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

        # Build result dictionary
        cost_breakdown = {}
        for row in results:
            cost_breakdown[row["service"]] = float(row["total_cost"])

        return cost_breakdown

    except Exception as e:
        logger.error(f"Error getting cost breakdown: {e}")
        return {}


def get_cost_breakdown_by_operation(
    service: str,
    period: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, float]:
    """Get cost breakdown by operation for a specific service and period.

    Args:
        service: Service name.
        period: Time period ('day', 'week', 'month', 'custom').
        start_date: Start date for custom period (YYYY-MM-DD).
        end_date: End date for custom period (YYYY-MM-DD).

    Returns:
        Dictionary mapping operation names to costs.
    """
    try:
        # Determine date range
        today = datetime.now()

        if period == "day":
            start_date = today.strftime("%Y-%m-%d")
            end_date = start_date
        elif period == "week":
            start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        elif period == "month":
            start_date = today.strftime("%Y-%m-01")
            end_date = today.strftime("%Y-%m-%d")
        elif period == "custom":
            if not start_date or not end_date:
                logger.error("Start date and end date are required for custom period")
                return {}
        else:
            logger.error(f"Invalid period: {period}")
            return {}

        # Build query
        query = """
            SELECT operation, SUM(cost_dollars) as total_cost 
            FROM cost_tracking 
            WHERE service = ? AND date(timestamp) BETWEEN ? AND ?
            GROUP BY operation
            ORDER BY total_cost DESC
        """

        # Execute query
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service, start_date, end_date))
            results = cursor.fetchall()

        # Build result dictionary
        cost_breakdown = {}
        for row in results:
            cost_breakdown[row["operation"]] = float(row["total_cost"])

        return cost_breakdown

    except Exception as e:
        logger.error(f"Error getting cost breakdown: {e}")
        return {}


def check_budget_thresholds() -> Dict[str, Any]:
    """Check if daily or monthly costs exceed budget thresholds.

    Returns:
        Dictionary with threshold status information.
    """
    try:
        # Get current costs
        daily_cost = get_daily_cost()
        monthly_cost = get_monthly_cost()

        # Calculate percentages
        daily_percentage = daily_cost / DAILY_BUDGET if DAILY_BUDGET > 0 else 0
        monthly_percentage = monthly_cost / MONTHLY_BUDGET if MONTHLY_BUDGET > 0 else 0

        # Check thresholds
        daily_threshold_exceeded = daily_percentage >= DAILY_ALERT_THRESHOLD
        monthly_threshold_exceeded = monthly_percentage >= MONTHLY_ALERT_THRESHOLD

        # Check scaling gate thresholds
        scaling_gate_daily_triggered = daily_percentage >= SCALING_GATE_DAILY_THRESHOLD
        scaling_gate_monthly_triggered = monthly_percentage >= SCALING_GATE_MONTHLY_THRESHOLD
        scaling_gate_triggered = scaling_gate_daily_triggered or scaling_gate_monthly_triggered

        # Get current scaling gate status
        scaling_gate_active, scaling_gate_reason = is_scaling_gate_active()

        # Log alerts if thresholds exceeded
        if daily_threshold_exceeded:
            logger.warning(
                f"Daily cost threshold exceeded: ${daily_cost:.2f} / ${DAILY_BUDGET:.2f} " f"({daily_percentage:.1%})"
            )

        if monthly_threshold_exceeded:
            logger.warning(
                f"Monthly cost threshold exceeded: ${monthly_cost:.2f} / ${MONTHLY_BUDGET:.2f} "
                f"({monthly_percentage:.1%})"
            )

        # Update scaling gate if needed
        if scaling_gate_triggered and not scaling_gate_active:
            reason = ""
            if scaling_gate_daily_triggered:
                reason = (
                    f"Daily budget threshold exceeded: ${daily_cost:.2f} / ${DAILY_BUDGET:.2f} ({daily_percentage:.1%})"
                )
            elif scaling_gate_monthly_triggered:
                reason = f"Monthly budget threshold exceeded: ${monthly_cost:.2f} / ${MONTHLY_BUDGET:.2f} ({monthly_percentage:.1%})"

            if SCALING_GATE_ENABLED:
                set_scaling_gate(True, reason)
                logger.critical(f"Scaling gate activated: {reason}")
        elif not scaling_gate_triggered and scaling_gate_active:
            set_scaling_gate(False, "Budget now within thresholds")
            logger.info("Scaling gate deactivated: Budget now within thresholds")

        # Return threshold status
        return {
            "daily_cost": daily_cost,
            "monthly_cost": monthly_cost,
            "daily_budget": DAILY_BUDGET,
            "monthly_budget": MONTHLY_BUDGET,
            "daily_percentage": daily_percentage,
            "monthly_percentage": monthly_percentage,
            "daily_threshold_exceeded": daily_threshold_exceeded,
            "monthly_threshold_exceeded": monthly_threshold_exceeded,
            "scaling_gate_triggered": scaling_gate_triggered,
            "scaling_gate_active": scaling_gate_active,
            "scaling_gate_reason": scaling_gate_reason,
        }

    except Exception as e:
        logger.error(f"Error checking budget thresholds: {e}")
        return {
            "error": str(e),
            "daily_threshold_exceeded": False,
            "monthly_threshold_exceeded": False,
            "scaling_gate_triggered": False,
            "scaling_gate_active": False,
            "scaling_gate_reason": f"Error: {str(e)}",
        }


def is_scaling_gate_active() -> Tuple[bool, str]:
    """Check if the scaling gate is currently active.

    Returns:
        Tuple of (is_active, reason).
    """
    if not SCALING_GATE_ENABLED:
        return False, "Scaling gate disabled by configuration"

    if not os.path.exists(SCALING_GATE_LOCKFILE):
        return False, "Scaling gate not active"

    try:
        with open(SCALING_GATE_LOCKFILE, "r") as f:
            content = f.read().strip()
        return True, content
    except Exception as e:
        logger.error(f"Error reading scaling gate lock file: {e}")
        return False, "Error reading scaling gate status"


def set_scaling_gate(activated: bool, reason: str) -> bool:
    """Set the scaling gate status.

    Args:
        activated: Whether the scaling gate is activated (True) or deactivated (False).
        reason: The reason for the status change.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(SCALING_GATE_LOCKFILE), exist_ok=True)

        # Create or remove lock file based on status
        if activated:
            with open(SCALING_GATE_LOCKFILE, "w") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp}: {reason}\n")
        else:
            if os.path.exists(SCALING_GATE_LOCKFILE):
                os.remove(SCALING_GATE_LOCKFILE)

        # Log to history file
        history_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "activated" if activated else "deactivated",
            "reason": reason,
            "daily_cost": get_daily_cost(),
            "monthly_cost": get_monthly_cost(),
            "daily_budget": DAILY_BUDGET,
            "monthly_budget": MONTHLY_BUDGET,
        }

        # Create history file if it doesn't exist
        os.makedirs(os.path.dirname(SCALING_GATE_HISTORY_FILE), exist_ok=True)
        if not os.path.exists(SCALING_GATE_HISTORY_FILE):
            with open(SCALING_GATE_HISTORY_FILE, "w") as f:
                json.dump({"history": []}, f)

        # Append to history file
        with open(SCALING_GATE_HISTORY_FILE, "r+") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"history": []}

            data["history"].append(history_entry)

            # Keep only the last 100 entries
            if len(data["history"]) > 100:
                data["history"] = data["history"][-100:]

            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)

        logger.info(f"Scaling gate {'activated' if activated else 'deactivated'}: {reason}")
        return True
    except Exception as e:
        logger.error(f"Error setting scaling gate status: {e}")
        return False


def should_allow_operation(service: str, operation: str) -> Tuple[bool, str]:
    """Check if an operation should be allowed based on scaling gate status.

    Args:
        service: Service name (e.g., 'openai', 'sendgrid').
        operation: Operation name (e.g., 'mockup_generation', 'email').

    Returns:
        Tuple of (allowed, reason).
    """
    # Check if scaling gate is active
    scaling_gate_active, reason = is_scaling_gate_active()

    if not scaling_gate_active:
        return True, "Operation allowed: Scaling gate not active"

    # Define critical operations that are always allowed
    critical_operations = {
        "sendgrid": ["bounce_notification", "error_notification", "admin_alert"],
        "database": ["backup", "health_check", "error_log"],
        "monitoring": ["all"],
        "system": ["all"],
    }

    # Check if operation is critical
    if service in critical_operations:
        if "all" in critical_operations[service] or operation in critical_operations[service]:
            logger.info(f"Critical operation allowed despite scaling gate: {service}.{operation}")
            return True, "Critical operation allowed despite scaling gate"

    # Block non-critical operations
    logger.warning(f"Operation blocked by scaling gate: {service}.{operation}")
    return False, f"Operation blocked: {reason}"


def get_scaling_gate_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get the scaling gate activation/deactivation history.

    Args:
        limit: Maximum number of history entries to return.

    Returns:
        List of history entries, most recent first.
    """
    try:
        if not os.path.exists(SCALING_GATE_HISTORY_FILE):
            return []

        with open(SCALING_GATE_HISTORY_FILE, "r") as f:
            try:
                data = json.load(f)
                history = data.get("history", [])
                return history[-limit:] if limit > 0 else history
            except json.JSONDecodeError:
                return []
    except Exception as e:
        logger.error(f"Error getting scaling gate history: {e}")
        return []


def export_cost_report(
    output_file: str,
    period: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bool:
    """Export cost report to a JSON file.

    Args:
        output_file: Output file path.
        period: Time period ('day', 'week', 'month', 'custom').
        start_date: Start date for custom period (YYYY-MM-DD).
        end_date: End date for custom period (YYYY-MM-DD).

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Determine date range
        today = datetime.now()

        if period == "day":
            start_date = today.strftime("%Y-%m-%d")
            end_date = start_date
            period_label = f"day ({start_date})"
        elif period == "week":
            start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            period_label = f"week ({start_date} to {end_date})"
        elif period == "month":
            start_date = today.strftime("%Y-%m-01")
            end_date = today.strftime("%Y-%m-%d")
            period_label = f"month ({start_date} to {end_date})"
        elif period == "custom":
            if not start_date or not end_date:
                logger.error("Start date and end date are required for custom period")
                return False
            period_label = f"custom period ({start_date} to {end_date})"
        else:
            logger.error(f"Invalid period: {period}")
            return False

        # Get cost breakdown by service
        service_breakdown = get_cost_breakdown_by_service(period, start_date, end_date)

        # Get detailed breakdown by operation for each service
        operation_breakdown = {}
        for service in service_breakdown.keys():
            operation_breakdown[service] = get_cost_breakdown_by_operation(service, period, start_date, end_date)

        # Calculate total cost
        total_cost = sum(service_breakdown.values())

        # Build report
        report = {
            "period": period_label,
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_cost": total_cost,
            "service_breakdown": service_breakdown,
            "operation_breakdown": operation_breakdown,
        }

        # Write report to file
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Cost report exported to {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error exporting cost report: {e}")
        return False


def export_prometheus_metrics(output_file: str) -> bool:
    """Export cost metrics in Prometheus format.

    Args:
        output_file: Output file path.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Get current costs
        daily_cost = get_daily_cost()
        monthly_cost = get_monthly_cost()

        # Get cost breakdown by service for today
        service_breakdown = get_cost_breakdown_by_service("day")

        # Build metrics
        metrics = []

        # Add total cost metrics
        metrics.append(f"# HELP anthrasite_daily_cost Total cost for today in dollars")
        metrics.append(f"# TYPE anthrasite_daily_cost gauge")
        metrics.append(f"anthrasite_daily_cost {daily_cost:.4f}")

        metrics.append(f"# HELP anthrasite_monthly_cost Total cost for the current month in dollars")
        metrics.append(f"# TYPE anthrasite_monthly_cost gauge")
        metrics.append(f"anthrasite_monthly_cost {monthly_cost:.4f}")

        # Add budget percentage metrics
        daily_percentage = daily_cost / DAILY_BUDGET if DAILY_BUDGET > 0 else 0
        monthly_percentage = monthly_cost / MONTHLY_BUDGET if MONTHLY_BUDGET > 0 else 0

        metrics.append(f"# HELP anthrasite_daily_budget_percentage Percentage of daily budget used")
        metrics.append(f"# TYPE anthrasite_daily_budget_percentage gauge")
        metrics.append(f"anthrasite_daily_budget_percentage {daily_percentage:.4f}")

        metrics.append(f"# HELP anthrasite_monthly_budget_percentage Percentage of monthly budget used")
        metrics.append(f"# TYPE anthrasite_monthly_budget_percentage gauge")
        metrics.append(f"anthrasite_monthly_budget_percentage {monthly_percentage:.4f}")

        # Add service-specific metrics
        metrics.append(f"# HELP anthrasite_service_cost Cost by service in dollars")
        metrics.append(f"# TYPE anthrasite_service_cost gauge")
        for service, cost in service_breakdown.items():
            metrics.append(f'anthrasite_service_cost{{service="{service}"}} {cost:.4f}')

        # Write metrics to file
        with open(output_file, "w") as f:
            f.write("\n".join(metrics) + "\n")

        logger.info(f"Prometheus metrics exported to {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error exporting Prometheus metrics: {e}")
        return False


if __name__ == "__main__":
    # Command-line interface for cost tracking utilities
    import argparse

    parser = argparse.ArgumentParser(description="Cost tracking utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Log cost command
    log_parser = subparsers.add_parser("log", help="Log a cost entry")
    log_parser.add_argument("--service", required=True, help="Service name")
    log_parser.add_argument("--operation", required=True, help="Operation name")
    log_parser.add_argument("--cost", type=float, required=True, help="Cost in dollars")

    # Get daily cost command
    daily_parser = subparsers.add_parser("daily", help="Get daily cost")
    daily_parser.add_argument("--service", help="Filter by service")

    # Get monthly cost command
    monthly_parser = subparsers.add_parser("monthly", help="Get monthly cost")
    monthly_parser.add_argument("--service", help="Filter by service")

    # Export report command
    report_parser = subparsers.add_parser("report", help="Export cost report")
    report_parser.add_argument("--output", required=True, help="Output file path")
    report_parser.add_argument(
        "--period",
        default="month",
        choices=["day", "week", "month", "custom"],
        help="Time period",
    )
    report_parser.add_argument("--start-date", help="Start date for custom period (YYYY-MM-DD)")
    report_parser.add_argument("--end-date", help="End date for custom period (YYYY-MM-DD)")

    # Export Prometheus metrics command
    prometheus_parser = subparsers.add_parser("prometheus", help="Export Prometheus metrics")
    prometheus_parser.add_argument("--output", required=True, help="Output file path")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "log":
        success = log_cost(args.service, args.operation, args.cost)
        if success:
            print(f"Cost logged: {args.service} {args.operation} ${args.cost:.4f}")
        else:
            print("Error logging cost")
            sys.exit(1)

    elif args.command == "daily":
        cost = get_daily_cost(args.service)
        service_str = f" for {args.service}" if args.service else ""
        print(f"Daily cost{service_str}: ${cost:.2f}")

    elif args.command == "monthly":
        cost = get_monthly_cost(args.service)
        service_str = f" for {args.service}" if args.service else ""
        print(f"Monthly cost{service_str}: ${cost:.2f}")

    elif args.command == "report":
        success = export_cost_report(args.output, args.period, args.start_date, args.end_date)
        if success:
            print(f"Cost report exported to {args.output}")
        else:
            print("Error exporting cost report")
            sys.exit(1)

    elif args.command == "prometheus":
        success = export_prometheus_metrics(args.output)
        if success:
            print(f"Prometheus metrics exported to {args.output}")
        else:
            print("Error exporting Prometheus metrics")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0)
