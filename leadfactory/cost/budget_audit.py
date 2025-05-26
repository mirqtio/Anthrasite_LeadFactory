"""
Budget Audit Tool for LeadFactory

This module provides functionality for monitoring and managing the budget
and scaling gate status of the LeadFactory system.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Initialize logging
logger = logging.getLogger(__name__)


def get_cost_tracker():
    """Get cost tracker singleton instance."""
    try:
        from leadfactory.cost.cost_tracking import cost_tracker

        return cost_tracker
    except ImportError:
        logger.warning("Cost tracker not available")
        return None


def get_budget_gate():
    """Get budget gate singleton instance."""
    try:
        from leadfactory.cost.budget_gate import budget_gate

        return budget_gate
    except ImportError:
        logger.warning("Budget gate not available")
        return None


# Create instances to use in the code
cost_tracker = get_cost_tracker()
budget_gate = get_budget_gate()


class Colors:
    """Terminal colors for formatted output."""

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
    print(f"{Colors.HEADER}{text}{Colors.ENDC}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.OKGREEN}{text}{Colors.ENDC}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.WARNING}{text}{Colors.ENDC}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.FAIL}{text}{Colors.ENDC}")


def format_currency(amount: float) -> str:
    """Format a number as currency."""
    return f"${amount:.2f}"


def format_percentage(value: float) -> str:
    """Format a number as a percentage."""
    return f"{value * 100:.1f}%"


def show_summary() -> None:
    """Show a summary of current budget status."""
    if not cost_tracker:
        print_error("Cost tracker not available")
        return

    print_header("Budget Summary")
    print(f"Daily cost: {format_currency(cost_tracker.get_daily_cost())}")
    print(f"Monthly cost: {format_currency(cost_tracker.get_monthly_cost())}")

    # Budget threshold information
    if budget_gate:
        print(f"Budget threshold: {format_currency(budget_gate.threshold)}")
        is_active = budget_gate.is_active()
        status = "ACTIVE" if is_active else "inactive"
        color_fn = print_warning if is_active else print_success
        color_fn(f"Budget gate status: {status}")
    else:
        print_error("Budget gate not available")


def show_cost_breakdown(period: str = "day") -> None:
    """Show cost breakdown by service and operation."""
    if not cost_tracker:
        print_error("Cost tracker not available")
        return

    print_header(f"Cost Breakdown ({period})")

    # Get cost breakdown
    breakdown = {}
    if period == "day":
        breakdown = cost_tracker.get_daily_cost_breakdown()
    else:
        breakdown = cost_tracker.get_monthly_cost_breakdown()

    # Print breakdown
    if not breakdown:
        print("No cost data available")
        return

    for service, operations in breakdown.items():
        service_total = sum(operations.values())
        print(f"{service}: {format_currency(service_total)}")
        for operation, cost in operations.items():
            percentage = cost / service_total if service_total > 0 else 0
            print(
                f"  {operation}: {format_currency(cost)} ({format_percentage(percentage)})"
            )


def show_scaling_gate_status() -> None:
    """Show the current scaling gate status."""
    if not budget_gate:
        print_error("Budget gate not available")
        return

    print_header("Scaling Gate Status")
    is_active = budget_gate.is_active()
    status = "ACTIVE" if is_active else "inactive"
    color_fn = print_warning if is_active else print_success
    color_fn(f"Budget gate status: {status}")
    print(f"Enabled: {budget_gate.enabled}")
    print(f"Override: {budget_gate.override}")
    print(f"Threshold: {format_currency(budget_gate.threshold)}")


def manage_scaling_gate(activate: bool, reason: str = "") -> None:
    """Enable or disable the scaling gate."""
    if not budget_gate:
        print_error("Budget gate not available")
        return

    action = "Activating" if activate else "Deactivating"
    print_header(f"{action} Scaling Gate")

    if activate:
        budget_gate.set_override(False)
        print_success("Scaling gate activated")
    else:
        budget_gate.set_override(True)
        print_success("Scaling gate deactivated (override enabled)")


def export_report(period: str, output_file: str) -> None:
    """Export a cost report to a file."""
    if not cost_tracker:
        print_error("Cost tracker not available")
        return

    print_header(f"Exporting {period} cost report to {output_file}")

    # Generate report
    report = {}
    if period == "day":
        report = cost_tracker.get_daily_cost_report()
    else:
        report = cost_tracker.get_monthly_cost_report()

    # Write to file
    try:
        cost_tracker.export_cost_report(report, output_file)
        print_success(f"Report exported to {output_file}")
    except Exception as e:
        print_error(f"Failed to export report: {e}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Budget Audit Tool")

    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show budget summary")

    # Breakdown command
    breakdown_parser = subparsers.add_parser("breakdown", help="Show cost breakdown")
    breakdown_parser.add_argument(
        "--period",
        choices=["day", "month"],
        default="day",
        help="Period for cost breakdown (day or month)",
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show scaling gate status")

    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable scaling gate")
    enable_parser.add_argument(
        "--reason", type=str, help="Reason for enabling the gate"
    )

    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Disable scaling gate")
    disable_parser.add_argument(
        "--reason", type=str, help="Reason for disabling the gate"
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export cost report")
    export_parser.add_argument(
        "--period",
        choices=["day", "month"],
        default="month",
        help="Period for cost report (day or month)",
    )
    export_parser.add_argument(
        "--output", type=str, required=True, help="Output file path"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Execute command
    if args.command == "summary" or not args.command:
        show_summary()
    elif args.command == "breakdown":
        show_cost_breakdown(args.period)
    elif args.command == "status":
        show_scaling_gate_status()
    elif args.command == "enable":
        manage_scaling_gate(True, args.reason)
    elif args.command == "disable":
        manage_scaling_gate(False, args.reason)
    elif args.command == "export":
        export_report(args.period, args.output)
    else:
        parser.print_help()
        return 1

    return 0
