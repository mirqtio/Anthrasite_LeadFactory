#!/usr/bin/env python3
"""
Budget Audit Tool for Anthrasite Lead-Factory
This script provides a command-line interface for monitoring and managing the budget
and scaling gate status of the Anthrasite Lead-Factory system.
"""
import argparse
import os
import sys

from dotenv import load_dotenv

from utils.cost_tracker import (
    check_budget_thresholds,
    export_cost_report,
    export_prometheus_metrics,
    get_cost_breakdown_by_operation,
    get_cost_breakdown_by_service,
    get_daily_cost,
    get_monthly_cost,
    get_scaling_gate_history,
    is_scaling_gate_active,
    set_scaling_gate,
)
from utils.logging_config import get_logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Load environment variables
load_dotenv()
# Set up logging
logger = get_logger(__name__)


# Color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text: str) -> None:
    """Print a formatted header."""


def print_success(text: str) -> None:
    """Print a success message."""


def print_warning(text: str) -> None:
    """Print a warning message."""


def print_error(text: str) -> None:
    """Print an error message."""


def format_currency(amount: float) -> str:
    """Format a number as currency."""
    return f"${amount:.2f}"


def format_percentage(value: float) -> str:
    """Format a number as a percentage."""
    return f"{value:.1f}%"


def show_summary() -> None:
    """Show a summary of current budget status."""
    print_header("Budget Summary")
    # Get current costs
    daily_cost = get_daily_cost()
    monthly_cost = get_monthly_cost()
    # Get budget thresholds
    budget_info = check_budget_thresholds()
    # Print daily budget
    daily_budget = budget_info.get("daily_budget", 0)
    (daily_cost / daily_budget) * 100 if daily_budget > 0 else 0
    # Print monthly budget
    monthly_budget = budget_info.get("monthly_budget", 0)
    ((monthly_cost / monthly_budget) * 100 if monthly_budget > 0 else 0)
    # Print alerts if any
    if budget_info.get("daily_alert", False):
        print_warning("Daily budget alert threshold reached!")
    if budget_info.get("monthly_alert", False):
        print_warning("Monthly budget alert threshold reached!")


def show_cost_breakdown(period: str = "day") -> None:
    """Show cost breakdown by service and operation."""
    period_display = "Daily" if period == "day" else "Monthly"
    print_header(f"{period_display} Cost Breakdown by Service")
    # Get cost breakdown by service
    costs_by_service = get_cost_breakdown_by_service(period=period)
    if not costs_by_service:
        return
    # Print table header
    # Print each service's cost
    total = 0
    for service, cost in costs_by_service.items():
        total += cost
    # Print total
    # Show top operations for each service
    print_header(f"\n{period_display} Top Operations by Cost")
    for service in costs_by_service:
        operations = get_cost_breakdown_by_operation(service, period=period)
        if operations:
            for _op, cost in operations.items():
                pass


def show_scaling_gate_status() -> None:
    """Show the current scaling gate status."""
    print_header("Scaling Gate Status")
    active, reason = is_scaling_gate_active()
    # Show scaling gate history
    history = get_scaling_gate_history(limit=5)
    if history:
        print_header("\nRecent History")
        for entry in history:
            entry.get("timestamp", "")
            "Activated" if entry.get("activated", False) else "Deactivated"
            entry.get("reason", "")


def manage_scaling_gate(activate: bool, reason: str = "") -> None:
    """Enable or disable the scaling gate."""
    action = "activate" if activate else "deactivate"
    if not reason:
        reason = input(f"Enter reason to {action} the scaling gate: ")
    try:
        success = set_scaling_gate(activate, reason)
        if success:
            status = "activated" if activate else "deactivated"
            print_success(f"Scaling gate {status} successfully.")
        else:
            print_error("Failed to update scaling gate status.")
    except Exception as e:
        print_error(f"Error updating scaling gate: {str(e)}")


def export_report(period: str, output_file: str) -> None:
    """Export a cost report to a file."""
    try:
        success = export_cost_report(output_file, period=period)
        if success:
            print_success(f"Report exported to {output_file}")
        else:
            print_error("Failed to export report.")
    except Exception as e:
        print_error(f"Error exporting report: {str(e)}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Budget Audit Tool for Anthrasite Lead-Factory")
    # Main commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    # Summary command - store in _ to indicate it's intentionally unused
    _ = subparsers.add_parser("summary", help="Show budget summary")
    # Cost breakdown command
    cost_parser = subparsers.add_parser("costs", help="Show cost breakdown")
    cost_parser.add_argument(
        "--period",
        choices=["day", "month"],
        default="day",
        help="Time period (day or month)",
    )
    # Scaling gate command
    gate_parser = subparsers.add_parser("gate", help="Manage scaling gate")
    gate_subparsers = gate_parser.add_subparsers(dest="gate_command", help="Scaling gate command")
    # Enable gate
    enable_parser = gate_subparsers.add_parser("enable", help="Enable the scaling gate")
    enable_parser.add_argument("--reason", help="Reason for enabling the gate")
    # Disable gate
    disable_parser = gate_subparsers.add_parser("disable", help="Disable the scaling gate")
    disable_parser.add_argument("--reason", help="Reason for disabling the gate")
    # Status gate
    gate_subparsers.add_parser("status", help="Show scaling gate status")
    # Export command
    export_parser = subparsers.add_parser("export", help="Export cost report")
    export_parser.add_argument(
        "--period",
        choices=["day", "week", "month"],
        default="month",
        help="Time period for the report",
    )
    export_parser.add_argument("--output", default="cost_report.json", help="Output file path")
    # Export Prometheus metrics
    prom_parser = subparsers.add_parser("export-prometheus", help="Export Prometheus metrics")
    prom_parser.add_argument("--output", default="metrics.prom", help="Output file path")
    # Set default command
    parser.set_defaults(func=show_summary)
    # Parse arguments
    args = parser.parse_args()
    # Map commands to functions
    if args.command == "summary":
        args.func = show_summary
    elif args.command == "costs":
        args.func = lambda: show_cost_breakdown(args.period)
    elif args.command == "gate":
        if args.gate_command == "enable":
            args.func = lambda: manage_scaling_gate(True, args.reason)
        elif args.gate_command == "disable":
            args.func = lambda: manage_scaling_gate(False, args.reason)
        elif args.gate_command == "status":
            args.func = show_scaling_gate_status
    elif args.command == "export":
        args.func = lambda: export_report(args.period, args.output)
    elif args.command == "export-prometheus":
        args.func = lambda: export_prometheus_metrics(args.output)
    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()
        args.func()
        return 0
    except KeyboardInterrupt:
        return 1
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        if os.getenv("DEBUG"):
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
