"""
Cost tracking utilities for API usage.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Import logger
from utils.logging_config import logger

# Constants
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "10.0"))  # Default $10/day
MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET", "300.0"))  # Default $300/month
DAILY_THRESHOLD = float(os.getenv("DAILY_THRESHOLD", "0.8"))  # 80% of daily budget
# 80% of monthly budget
MONTHLY_THRESHOLD = float(os.getenv("MONTHLY_THRESHOLD", "0.8"))
SCALING_GATE_ENABLED = os.getenv("SCALING_GATE_ENABLED", "true").lower() == "true"
# Path to scaling gate file
SCALING_GATE_FILE = Path(
    os.getenv(
        "SCALING_GATE_FILE",
        Path(__file__).parent.parent / "data" / "scaling_gate.json",
    )
)

# Path to scaling gate lock file
SCALING_GATE_LOCKFILE = Path(
    os.getenv(
        "SCALING_GATE_LOCKFILE",
        Path(__file__).parent.parent / "data" / "scaling_gate.lock",
    )
)

# Path to scaling gate history file
SCALING_GATE_HISTORY_FILE = Path(
    os.getenv(
        "SCALING_GATE_HISTORY_FILE",
        Path(__file__).parent.parent / "data" / "scaling_gate_history.json",
    )
)

# Ensure the scaling gate file directory exists
SCALING_GATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Critical operations that bypass the scaling gate
DEFAULT_CRITICAL_OPERATIONS = {
    "_global": ["health_check", "metrics", "status"],
    "openai": ["embeddings"],
    "anthropic": ["embeddings"],
}


def track_api_cost(
    service: str,
    operation: str,
    cost_dollars: float,
    tier: str = "default",
    business_id: int | None = None,
) -> bool:
    """
    Track API cost for a service and operation.

    Args:
        service: The service name (e.g., 'openai', 'anthropic')
        operation: The operation name (e.g., 'completion', 'embedding')
        cost_dollars: The cost in dollars
        tier: The pricing tier (e.g., 'default', 'premium')
        business_id: Optional business ID for attribution

    Returns:
        bool: True if the cost was tracked successfully
    """
    # Implementation would typically write to a database or log file
    # For now, we'll just log it
    logger.info(
        f"API Cost: ${cost_dollars:.4f} for {service}.{operation} " f"(tier: {tier}, business_id: {business_id})"
    )
    return True


def get_daily_cost(service: str | None = None) -> float:
    """
    Get the total API cost for today.

    Args:
        service: Optional service name to filter by

    Returns:
        float: The total cost in dollars
    """
    # Implementation would typically query a database
    # For now, we'll return a mock value
    if service:
        # Mock different costs for different services
        if service == "openai":
            return 3.25
        elif service == "anthropic":
            return 2.75
        else:
            return 1.0
    else:
        # Total cost across all services
        return 7.0


def get_monthly_cost(service: str | None = None) -> float:
    """
    Get the total API cost for the current month.

    Args:
        service: Optional service name to filter by

    Returns:
        float: The total cost in dollars
    """
    # Implementation would typically query a database
    # For now, we'll return a mock value
    if service:
        # Mock different costs for different services
        if service == "openai":
            return 95.50
        elif service == "anthropic":
            return 85.25
        else:
            return 30.0
    else:
        # Total cost across all services
        return 210.75


def get_cost_by_service() -> dict[str, float]:
    """
    Get the total API cost for each service for the current month.

    Returns:
        Dict[str, float]: A dictionary of service names to costs in dollars
    """
    # Implementation would typically query a database
    # For now, we'll return mock values
    return {
        "openai": 95.50,
        "anthropic": 85.25,
        "google": 20.0,
        "other": 10.0,
    }


def get_cost_by_operation(service: str) -> dict[str, float]:
    """
    Get the total API cost for each operation for a service for the current month.

    Args:
        service: The service name

    Returns:
        Dict[str, float]: A dictionary of operation names to costs in dollars
    """
    # Implementation would typically query a database
    # For now, we'll return mock values based on the service
    if service == "openai":
        return {
            "completion": 75.50,
            "embedding": 15.0,
            "image": 5.0,
        }
    elif service == "anthropic":
        return {
            "completion": 80.25,
            "embedding": 5.0,
        }
    else:
        return {
            "api": 30.0,
        }


def get_daily_costs(days: int = 30) -> dict[str, float]:
    """
    Get the total API cost for each day for the last N days.

    Args:
        days: The number of days to get costs for

    Returns:
        Dict[str, float]: A dictionary of dates to costs in dollars
    """
    # Implementation would typically query a database
    # For now, we'll return mock values
    result = {}
    today = datetime.now().date()
    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        # Generate a mock cost that varies by day
        cost = 5.0 + (i % 5) * 1.5
        result[date_str] = cost
    return result


def check_budget_thresholds() -> dict[str, Any]:
    """
    Check if the daily or monthly budget thresholds have been exceeded.

    Returns:
        Dict[str, Any]: A dictionary with threshold status information
    """
    daily_cost = get_daily_cost()
    monthly_cost = get_monthly_cost()

    daily_threshold_exceeded = daily_cost >= DAILY_BUDGET * DAILY_THRESHOLD
    monthly_threshold_exceeded = monthly_cost >= MONTHLY_BUDGET * MONTHLY_THRESHOLD
    daily_budget_exceeded = daily_cost >= DAILY_BUDGET
    monthly_budget_exceeded = monthly_cost >= MONTHLY_BUDGET

    return {
        "daily": {
            "cost": daily_cost,
            "budget": DAILY_BUDGET,
            "threshold": DAILY_BUDGET * DAILY_THRESHOLD,
            "threshold_exceeded": daily_threshold_exceeded,
            "budget_exceeded": daily_budget_exceeded,
            "percent_used": ((daily_cost / DAILY_BUDGET) * 100 if DAILY_BUDGET > 0 else 0),
        },
        "monthly": {
            "cost": monthly_cost,
            "budget": MONTHLY_BUDGET,
            "threshold": MONTHLY_BUDGET * MONTHLY_THRESHOLD,
            "threshold_exceeded": monthly_threshold_exceeded,
            "budget_exceeded": monthly_budget_exceeded,
            "percent_used": ((monthly_cost / MONTHLY_BUDGET) * 100 if MONTHLY_BUDGET > 0 else 0),
        },
        "any_threshold_exceeded": daily_threshold_exceeded or monthly_threshold_exceeded,
        "any_budget_exceeded": daily_budget_exceeded or monthly_budget_exceeded,
    }


def is_scaling_gate_active() -> tuple[bool, str]:
    """
    Check if the scaling gate is currently active.

    Returns:
        Tuple[bool, str]: A tuple of (active, reason)
    """
    # If scaling gate is disabled, it's never active
    if not SCALING_GATE_ENABLED:
        return False, "Scaling gate is disabled"

    # Check if the budget thresholds have been exceeded
    budget_status = check_budget_thresholds()
    if budget_status["any_budget_exceeded"]:
        return True, "Budget exceeded"

    # Check if the scaling gate file exists and is active
    if SCALING_GATE_FILE.exists():
        try:
            with SCALING_GATE_FILE.open() as f:
                data = json.load(f)
                if data.get("active", False):
                    return True, data.get("reason", "Unknown reason")
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return False, "Scaling gate is inactive"


def set_scaling_gate(active: bool, reason: str) -> bool:
    """
    Set the scaling gate status.

    Args:
        active: Whether the scaling gate is active
        reason: The reason for the scaling gate status

    Returns:
        bool: True if the scaling gate was set successfully
    """
    # If scaling gate is disabled, we can't set it
    if not SCALING_GATE_ENABLED:
        logger.warning("Cannot set scaling gate: Scaling gate is disabled")
        return False

    # Create the scaling gate file if it doesn't exist
    if not SCALING_GATE_FILE.exists():
        data = {
            "active": active,
            "reason": reason,
            "updated_at": datetime.now().isoformat(),
            "history": [],
        }
    else:
        try:
            with SCALING_GATE_FILE.open() as f:
                data = json.load(f)
                # Only add to history if the status changed
                if data.get("active", False) != active:
                    history_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "active": active,
                        "reason": reason,
                    }
                    if "history" not in data:
                        data["history"] = []
                    data["history"].append(history_entry)
                data["active"] = active
                data["reason"] = reason
                data["updated_at"] = datetime.now().isoformat()
        except (json.JSONDecodeError, FileNotFoundError):
            data = {
                "active": active,
                "reason": reason,
                "updated_at": datetime.now().isoformat(),
                "history": [],
            }

    try:
        with SCALING_GATE_FILE.open("w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to set scaling gate: {e}")
        return False


def check_operation_permission(
    service: str,
    operation: str,
    critical_operations: dict[str, list[str]] | None = None,
) -> tuple[bool, str]:
    """
    Check if an operation is permitted based on the scaling gate status.

    Args:
        service: The service name
        operation: The operation name
        critical_operations: Optional dictionary of critical operations

    Returns:
        Tuple[bool, str]: A tuple of (permitted, reason)
    """
    # If scaling gate is disabled, all operations are permitted
    if not SCALING_GATE_ENABLED:
        return True, "Scaling gate is disabled"

    # Check if the scaling gate is active
    active, reason = is_scaling_gate_active()
    if not active:
        return True, "Scaling gate is inactive"

    # Check if the operation is critical
    if critical_operations is None:
        critical_operations = DEFAULT_CRITICAL_OPERATIONS

    # Check global critical operations
    if "_global" in critical_operations and operation in critical_operations["_global"]:
        return True, f"Operation '{operation}' is globally critical"

    # Check service-specific critical operations
    if service in critical_operations and operation in critical_operations[service]:
        return True, f"Operation '{operation}' is critical for service '{service}'"

    return (
        False,
        f"Operation '{operation}' for service '{service}' is not permitted: {reason}",
    )


def should_allow_operation(
    service: str,
    operation: str,
    critical_operations: dict[str, list[str]] | None = None,
) -> bool:
    """
    Determine if an operation should be allowed based on the scaling gate status.

    Simplified version of check_operation_permission; returns a boolean.

    Args:
        service: The service name
        operation: The operation name
        critical_operations: Optional dictionary of critical operations

    Returns:
        bool: True if the operation is allowed, False otherwise
    """
    permitted, _ = check_operation_permission(service, operation, critical_operations)
    return permitted


def get_cost_metrics() -> list[str]:
    """
    Get Prometheus metrics for API costs.

    Returns:
        List[str]: A list of Prometheus metrics
    """
    metrics = []

    # Add daily cost metrics
    daily_cost = get_daily_cost()
    metrics.append(f"api_cost_daily_dollars{{}} {daily_cost}")

    # Add monthly cost metrics
    monthly_cost = get_monthly_cost()
    metrics.append(f"api_cost_monthly_dollars{{}} {monthly_cost}")

    # Add cost by service metrics
    cost_by_service = get_cost_by_service()
    for service, cost in cost_by_service.items():
        metrics.append(f'api_cost_monthly_by_service_dollars{{service="{service}"}} {cost}')

    # Add budget threshold metrics
    budget_status = check_budget_thresholds()
    metrics.append(f'api_cost_daily_budget_dollars{{}} {budget_status["daily"]["budget"]}')
    metrics.append(f"api_cost_daily_threshold_dollars{{}} " f'{budget_status["daily"]["threshold"]}')
    metrics.append(f'api_cost_monthly_budget_dollars{{}} {budget_status["monthly"]["budget"]}')
    metrics.append(f"api_cost_monthly_threshold_dollars{{}} " f'{budget_status["monthly"]["threshold"]}')
    metrics.append(f"api_cost_daily_threshold_exceeded{{}} " f'{int(budget_status["daily"]["threshold_exceeded"])}')
    metrics.append(f"api_cost_monthly_threshold_exceeded{{}} " f'{int(budget_status["monthly"]["threshold_exceeded"])}')
    metrics.append(f"api_cost_daily_budget_exceeded{{}} " f'{int(budget_status["daily"]["budget_exceeded"])}')
    metrics.append(f"api_cost_monthly_budget_exceeded{{}} " f'{int(budget_status["monthly"]["budget_exceeded"])}')
    metrics.append(f"api_cost_daily_percent_used{{}} " f'{budget_status["daily"]["percent_used"]}')
    metrics.append(f"api_cost_monthly_percent_used{{}} " f'{budget_status["monthly"]["percent_used"]}')

    # Add scaling gate metrics
    active, reason = is_scaling_gate_active()
    metrics.append(f"api_scaling_gate_active{{}} {int(active)}")
    metrics.append(f'api_scaling_gate_active_reason{{reason="{reason}"}} {int(active)}')

    return metrics


def get_daily_costs_endpoint() -> dict[str, float]:
    """
    Get the total API cost for each day for the last 30 days.

    Returns:
        Dict[str, float]: A dictionary of dates to costs in dollars
    """
    return get_daily_costs(30)


def get_monthly_costs_endpoint() -> dict[str, float]:
    """
    Get the total API cost for each month for the last 12 months.

    Returns:
        Dict[str, float]: A dictionary of months to costs in dollars
    """
    try:
        # Implementation would typically query a database
        # For now, we'll return mock values
        result = {}
        today = datetime.now().date()
        for i in range(12):
            # Get the first day of the month
            month = today.replace(day=1) - timedelta(days=1)
            month = month.replace(day=1)
            month_str = month.strftime("%Y-%m")
            # Generate a mock cost that varies by month
            cost = 150.0 + (i % 3) * 50.0
            result[month_str] = cost
            # Move to the previous month
            today = month
        return result
    except Exception as e:
        logger.error(f"Error getting monthly costs: {e}")
        return {}


def get_cost_breakdown_endpoint() -> dict[str, Any]:
    """
    Get a breakdown of API costs by service and operation.

    Returns:
        Dict[str, Any]: A dictionary with cost breakdown information
    """
    try:
        cost_by_service = get_cost_by_service()
        cost_by_operation = {}
        for service in cost_by_service:
            cost_by_operation[service] = get_cost_by_operation(service)

        return {
            "services": cost_by_service,
            "operations": cost_by_operation,
        }
    except Exception as e:
        logger.error(f"Error getting cost breakdown: {e}")
        return {
            "error": str(e),
            "services": {},
            "operations": {},
        }


def get_budget_status_endpoint() -> dict[str, Any]:
    """
    Get the current budget status.

    Returns:
        Dict[str, Any]: A dictionary with budget status information
    """
    return check_budget_thresholds()


def get_scaling_gate_status_endpoint() -> dict[str, Any]:
    """
    Get the current scaling gate status.

    Returns:
        Dict[str, Any]: A dictionary with scaling gate status information
    """
    try:
        # Get the scaling gate status
        active, reason = is_scaling_gate_active()

        # Read the scaling gate file for history
        if SCALING_GATE_FILE.exists():
            with SCALING_GATE_FILE.open() as f:
                data = json.load(f)
                history = data.get("history", [])
        else:
            history = []

        return {
            "active": active,
            "reason": reason,
            "history": history,
        }
    except Exception as e:
        logger.error(f"Error getting scaling gate status: {e}")
        return {
            "error": str(e),
            "active": False,
            "reason": f"Error: {str(e)}",
            "history": [],
        }


def get_cost_breakdown_by_service():
    """
    Get a breakdown of API costs by service.

    Returns:
        Dict[str, float]: A dictionary of service names to costs in dollars
    """
    return get_cost_by_service()


def get_cost_breakdown_by_operation(service: str):
    """
    Get a breakdown of API costs by operation for a specific service.

    Args:
        service: The service name

    Returns:
        Dict[str, float]: A dictionary of operation names to costs in dollars
    """
    return get_cost_by_operation(service)


def get_scaling_gate_history():
    """
    Get the history of scaling gate status changes.

    Returns:
        List[Dict[str, Any]]: A list of scaling gate status changes
    """
    # Check if the scaling gate file exists
    if not SCALING_GATE_FILE.exists():
        return []

    try:
        with SCALING_GATE_FILE.open() as f:
            data = json.load(f)
            if "history" in data:
                return data["history"]
            return []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def export_cost_report(output_file: str = "cost_report.json"):
    """
    Export a comprehensive cost report to a JSON file.

    Args:
        output_file: The path to the output file

    Returns:
        bool: True if the report was exported successfully
    """
    report = {
        "daily_cost": get_daily_cost(),
        "monthly_cost": get_monthly_cost(),
        "cost_by_service": get_cost_by_service(),
        "daily_costs": get_daily_costs(),
        "budget_status": check_budget_thresholds(),
        "scaling_gate": {
            "active": is_scaling_gate_active()[0],
            "reason": is_scaling_gate_active()[1],
            "history": get_scaling_gate_history(),
        },
    }

    try:
        with Path(output_file).open("w") as f:
            json.dump(report, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to export cost report: {e}")
        return False


def export_prometheus_metrics(output_file: str = "metrics.txt"):
    """
    Export Prometheus metrics to a text file.

    Args:
        output_file: The path to the output file

    Returns:
        bool: True if the metrics were exported successfully
    """
    metrics = get_cost_metrics()

    try:
        with Path(output_file).open("w") as f:
            f.write("\n".join(metrics))
        return True
    except Exception as e:
        logger.error(f"Failed to export Prometheus metrics: {e}")
        return False
