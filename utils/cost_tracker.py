"""
Cost tracking utilities for API usage.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any


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
SCALING_GATE_FILE = os.getenv(
    "SCALING_GATE_FILE",
    os.path.join(os.path.dirname(__file__), "../data/scaling_gate.json"),
)

# Ensure the scaling gate file directory exists
os.makedirs(os.path.dirname(SCALING_GATE_FILE), exist_ok=True)

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
    business_id: Optional[int] = None,
) -> bool:
    """
    Track API cost for a service and operation.

    Args:
        service: The service name (e.g., 'openai', 'anthropic')
        operation: The operation name (e.g., 'completion', 'embedding')
        cost_dollars: The cost in dollars
        tier: The pricing tier (e.g., 'default', 'high', 'low')
        business_id: Optional business ID associated with the API call

    Returns:
        bool: True if the cost was tracked successfully
    """
    try:
        # Convert dollars to cents for storage
        cost_cents = int(cost_dollars * 100)

        # Get database connection
        from utils.io import DatabaseConnection

        # Store the cost in the database
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                INSERT INTO cost_tracking
                (service, operation, cost_cents, tier, business_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (service, operation, cost_cents, tier, business_id),
            )

        # Check budget thresholds
        check_budget_thresholds()

        return True
    except Exception as e:
        logger.error(f"Error tracking API cost: {e}")
        return False


def get_daily_cost(service: Optional[str] = None) -> float:
    """
    Get the total API cost for today.

    Args:
        service: Optional service name to filter by

    Returns:
        float: The total cost in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            if service:
                cursor.execute(
                    """
                    SELECT SUM(cost_cents)
                    FROM cost_tracking
                    WHERE date(timestamp) = ? AND service = ?
                    """,
                    (today, service),
                )
            else:
                cursor.execute(
                    """
                    SELECT SUM(cost_cents)
                    FROM cost_tracking
                    WHERE date(timestamp) = ?
                    """,
                    (today,),
                )

            result = cursor.fetchone()[0]
            if result is None:
                return 0.0
            return result / 100.0  # Convert cents to dollars
    except Exception as e:
        logger.error(f"Error getting daily cost: {e}")
        return 0.0


def get_monthly_cost(service: Optional[str] = None) -> float:
    """
    Get the total API cost for the current month.

    Args:
        service: Optional service name to filter by

    Returns:
        float: The total cost in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get the first day of the current month
        today = datetime.now()
        first_day = today.replace(day=1).strftime("%Y-%m-%d")
        last_day = today.strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            if service:
                cursor.execute(
                    """
                    SELECT SUM(cost_cents)
                    FROM cost_tracking
                    WHERE date(timestamp) BETWEEN ? AND ? AND service = ?
                    """,
                    (first_day, last_day, service),
                )
            else:
                cursor.execute(
                    """
                    SELECT SUM(cost_cents)
                    FROM cost_tracking
                    WHERE date(timestamp) BETWEEN ? AND ?
                    """,
                    (first_day, last_day),
                )

            result = cursor.fetchone()[0]
            if result is None:
                return 0.0
            return result / 100.0  # Convert cents to dollars
    except Exception as e:
        logger.error(f"Error getting monthly cost: {e}")
        return 0.0


def get_cost_by_service() -> Dict[str, float]:
    """
    Get the total API cost for each service for the current month.

    Returns:
        Dict[str, float]: A dictionary of service names to costs in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get the first day of the current month
        today = datetime.now()
        first_day = today.replace(day=1).strftime("%Y-%m-%d")
        last_day = today.strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                SELECT service, SUM(cost_cents)
                FROM cost_tracking
                WHERE date(timestamp) BETWEEN ? AND ?
                GROUP BY service
                """,
                (first_day, last_day),
            )

            results = cursor.fetchall()
            return {service: cost / 100.0 for service, cost in results}
    except Exception as e:
        logger.error(f"Error getting cost by service: {e}")
        return {}


def get_cost_by_operation(service: str) -> Dict[str, float]:
    """
    Get the total API cost for each operation for a service for the current month.

    Args:
        service: The service name

    Returns:
        Dict[str, float]: A dictionary of operation names to costs in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get the first day of the current month
        today = datetime.now()
        first_day = today.replace(day=1).strftime("%Y-%m-%d")
        last_day = today.strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                SELECT operation, SUM(cost_cents) as total_cost
                FROM cost_tracking
                WHERE service = ? AND date(timestamp) BETWEEN ? AND ?
                GROUP BY operation
                """,
                (service, first_day, last_day),
            )

            results = cursor.fetchall()
            return {operation: cost / 100.0 for operation, cost in results}
    except Exception as e:
        logger.error(f"Error getting cost by operation: {e}")
        return {}


def get_daily_costs(days: int = 30) -> Dict[str, float]:
    """
    Get the total API cost for each day for the last N days.

    Args:
        days: The number of days to get costs for

    Returns:
        Dict[str, float]: A dictionary of dates to costs in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get the date range
        today = datetime.now()
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                SELECT date(timestamp), SUM(cost_cents)
                FROM cost_tracking
                WHERE date(timestamp) BETWEEN ? AND ?
                GROUP BY date(timestamp)
                ORDER BY date(timestamp)
                """,
                (start_date, end_date),
            )

            results = cursor.fetchall()
            return {date: cost / 100.0 for date, cost in results}
    except Exception as e:
        logger.error(f"Error getting daily costs: {e}")
        return {}


def check_budget_thresholds() -> Dict[str, Any]:
    """
    Check if the daily or monthly budget thresholds have been exceeded.

    Returns:
        Dict[str, Any]: A dictionary with threshold status information
    """
    try:
        # Get the current costs
        daily_cost = get_daily_cost()
        monthly_cost = get_monthly_cost()

        # Calculate percentages
        daily_percentage = daily_cost / DAILY_BUDGET if DAILY_BUDGET > 0 else 0
        monthly_percentage = monthly_cost / MONTHLY_BUDGET if MONTHLY_BUDGET > 0 else 0

        # Check if thresholds are exceeded
        daily_threshold_exceeded = daily_percentage >= DAILY_THRESHOLD
        monthly_threshold_exceeded = monthly_percentage >= MONTHLY_THRESHOLD

        # Log warnings if thresholds are exceeded
        if daily_threshold_exceeded:
            logger.warning(
                f"Daily cost threshold exceeded: ${daily_cost:.2f} / "
                f"${DAILY_BUDGET:.2f} ({daily_percentage:.1%})"
            )

        if monthly_threshold_exceeded:
            logger.warning(
                f"Monthly cost threshold exceeded: ${monthly_cost:.2f} / "
                f"${MONTHLY_BUDGET:.2f} ({monthly_percentage:.1%})"
            )

        # Update scaling gate if needed
        scaling_gate_triggered = daily_threshold_exceeded or monthly_threshold_exceeded
        scaling_gate_daily_triggered = daily_threshold_exceeded
        scaling_gate_monthly_triggered = monthly_threshold_exceeded
        scaling_gate_active, scaling_gate_reason = is_scaling_gate_active()

        if scaling_gate_triggered and not scaling_gate_active:
            reason = ""
            if scaling_gate_daily_triggered:
                reason = (
                    f"Daily budget threshold exceeded: ${daily_cost:.2f} / "
                    f"${DAILY_BUDGET:.2f} ({daily_percentage:.1%})"
                )
            elif scaling_gate_monthly_triggered:
                reason = (
                    f"Monthly budget threshold exceeded: ${monthly_cost:.2f} / "
                    f"${MONTHLY_BUDGET:.2f} ({monthly_percentage:.1%})"
                )
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
            "daily_threshold": DAILY_THRESHOLD,
            "monthly_threshold": MONTHLY_THRESHOLD,
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
            "daily_cost": 0,
            "monthly_cost": 0,
            "daily_budget": DAILY_BUDGET,
            "monthly_budget": MONTHLY_BUDGET,
            "daily_percentage": 0,
            "monthly_percentage": 0,
            "daily_threshold": DAILY_THRESHOLD,
            "monthly_threshold": MONTHLY_THRESHOLD,
            "daily_threshold_exceeded": False,
            "monthly_threshold_exceeded": False,
            "scaling_gate_triggered": False,
            "scaling_gate_active": False,
            "scaling_gate_reason": f"Error: {str(e)}",
        }


def is_scaling_gate_active() -> Tuple[bool, str]:
    """Check if the scaling gate is currently active.
    Returns:
        Tuple[bool, str]: A tuple of (active, reason)
    """
    try:
        if not os.path.exists(SCALING_GATE_FILE):
            return False, ""

        with open(SCALING_GATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("active", False), data.get("reason", "")
    except Exception as e:
        logger.error(f"Error checking scaling gate: {e}")
        return False, f"Error: {str(e)}"


def set_scaling_gate(active: bool, reason: str) -> bool:
    """Set the scaling gate status.
    Args:
        active: Whether the scaling gate is active
        reason: The reason for the scaling gate status
    Returns:
        bool: True if the scaling gate was set successfully
    """
    try:
        # Create the scaling gate file if it doesn't exist
        if not os.path.exists(SCALING_GATE_FILE):
            with open(SCALING_GATE_FILE, "w") as f:
                json.dump(
                    {
                        "active": False,
                        "reason": "",
                        "timestamp": datetime.now().isoformat(),
                        "history": [],
                    },
                    f,
                    indent=2,
                )

        # Read the current scaling gate status
        with open(SCALING_GATE_FILE, "r") as f:
            data = json.load(f)

        # Update the history
        history = data.get("history", [])
        history.append(
            {
                "active": active,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Limit the history to the last 100 entries
        if len(history) > 100:
            history = history[-100:]

        # Update the scaling gate status
        data["active"] = active
        data["reason"] = reason
        data["timestamp"] = datetime.now().isoformat()
        data["history"] = history

        # Write the updated scaling gate status
        with open(SCALING_GATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        logger.error(f"Error setting scaling gate: {e}")
        return False


def check_operation_permission(
    service: str,
    operation: str,
    critical_operations: Optional[Dict[str, List[str]]] = None,
) -> Tuple[bool, str]:
    """Check if an operation is permitted based on the scaling gate status.
    Args:
        service: The service name
        operation: The operation name
        critical_operations: Optional dictionary of critical operations
    Returns:
        Tuple[bool, str]: A tuple of (permitted, reason)
    """
    # Get the scaling gate status
    scaling_gate_active, scaling_gate_reason = is_scaling_gate_active()

    # If the scaling gate is not active, all operations are permitted
    if not scaling_gate_active:
        return True, ""

    # If critical_operations is not provided, use the default
    if critical_operations is None:
        critical_operations = DEFAULT_CRITICAL_OPERATIONS

    # Check if operation is in the global critical operations list
    if operation in critical_operations.get("_global", []):
        logger.info(
            f"Global critical operation allowed despite scaling gate: "
            f"{service}.{operation}"
        )
        return True, "Global critical operation allowed despite scaling gate"
    # Check if operation is critical for the specific service
    if service in critical_operations and operation in critical_operations[service]:
        logger.info(
            f"Critical operation allowed despite scaling gate: {service}.{operation}"
        )
        return True, "Critical operation allowed despite scaling gate"
    # Block non-critical operations
    logger.warning(
        f"Operation blocked by scaling gate: {service}.{operation} - "
        f"{scaling_gate_reason}"
    )
    return False, f"Operation blocked by scaling gate: {scaling_gate_reason}"


def get_cost_metrics() -> List[str]:
    """
    Get Prometheus metrics for API costs.

    Returns:
        List[str]: A list of Prometheus metrics
    """
    try:
        # Get the current costs
        daily_cost = get_daily_cost()
        monthly_cost = get_monthly_cost()

        # Calculate percentages
        daily_percentage = daily_cost / DAILY_BUDGET if DAILY_BUDGET > 0 else 0
        monthly_percentage = monthly_cost / MONTHLY_BUDGET if MONTHLY_BUDGET > 0 else 0

        # Get the scaling gate status
        scaling_gate_active, _ = is_scaling_gate_active()

        # Create the metrics
        metrics = []
        metrics.append("# HELP anthrasite_daily_cost Daily API cost in dollars")
        metrics.append("# TYPE anthrasite_daily_cost gauge")
        metrics.append(f"anthrasite_daily_cost {daily_cost:.4f}")
        metrics.append("# HELP anthrasite_monthly_cost Monthly API cost in dollars")
        metrics.append("# TYPE anthrasite_monthly_cost gauge")
        metrics.append(f"anthrasite_monthly_cost {monthly_cost:.4f}")
        metrics.append("# HELP anthrasite_daily_budget Daily API budget in dollars")
        metrics.append("# TYPE anthrasite_daily_budget gauge")
        metrics.append(f"anthrasite_daily_budget {DAILY_BUDGET:.4f}")
        metrics.append("# HELP anthrasite_monthly_budget Monthly API budget in dollars")
        metrics.append("# TYPE anthrasite_monthly_budget gauge")
        metrics.append(f"anthrasite_monthly_budget {MONTHLY_BUDGET:.4f}")
        metrics.append(
            "# HELP anthrasite_daily_budget_percentage Percentage of daily budget used"
        )
        metrics.append("# TYPE anthrasite_daily_budget_percentage gauge")
        metrics.append(f"anthrasite_daily_budget_percentage {daily_percentage:.4f}")
        metrics.append(
            "# HELP anthrasite_monthly_budget_percentage "
            "Percentage of monthly budget used"
        )
        metrics.append("# TYPE anthrasite_monthly_budget_percentage gauge")
        metrics.append(f"anthrasite_monthly_budget_percentage {monthly_percentage:.4f}")
        metrics.append(
            "# HELP anthrasite_scaling_gate Scaling gate status (0=inactive, 1=active)"
        )
        metrics.append("# TYPE anthrasite_scaling_gate gauge")
        metrics.append(f"anthrasite_scaling_gate {1 if scaling_gate_active else 0}")

        # Get costs by service
        service_costs = get_cost_by_service()
        metrics.append("# HELP anthrasite_service_cost API cost by service in dollars")
        metrics.append("# TYPE anthrasite_service_cost gauge")
        for service, cost in service_costs.items():
            metrics.append(f'anthrasite_service_cost{{service="{service}"}} {cost:.4f}')

        # Get costs by operation for each service
        metrics.append(
            "# HELP anthrasite_operation_cost API cost by operation in dollars"
        )
        metrics.append("# TYPE anthrasite_operation_cost gauge")
        for service in service_costs:
            operation_costs = get_cost_by_operation(service)
            for operation, cost in operation_costs.items():
                metrics.append(
                    f'anthrasite_operation_cost{{service="{service}",'
                    f'operation="{operation}"}} {cost:.4f}'
                )

        return metrics
    except Exception as e:
        logger.error(f"Error getting cost metrics: {e}")
        return [
            "# HELP anthrasite_error Error getting cost metrics",
            "# TYPE anthrasite_error gauge",
            f'anthrasite_error{{error="{str(e)}"}} 1',
        ]


def get_daily_costs_endpoint() -> Dict[str, float]:
    """
    Get the total API cost for each day for the last 30 days.

    Returns:
        Dict[str, float]: A dictionary of dates to costs in dollars
    """
    return get_daily_costs(30)


def get_monthly_costs_endpoint() -> Dict[str, float]:
    """
    Get the total API cost for each month for the last 12 months.

    Returns:
        Dict[str, float]: A dictionary of months to costs in dollars
    """
    try:
        # Get database connection
        from utils.io import DatabaseConnection

        # Get the date range
        today = datetime.now()
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        # Query the database
        with DatabaseConnection() as cursor:
            cursor.execute(
                """
                SELECT strftime('%Y-%m', timestamp), SUM(cost_cents)
                FROM cost_tracking
                WHERE date(timestamp) BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', timestamp)
                ORDER BY strftime('%Y-%m', timestamp)
                """,
                (start_date, end_date),
            )

            results = cursor.fetchall()
            return {month: cost / 100.0 for month, cost in results}
    except Exception as e:
        logger.error(f"Error getting monthly costs: {e}")
        return {}


def get_cost_breakdown_endpoint() -> Dict[str, Any]:
    """
    Get a breakdown of API costs by service and operation.

    Returns:
        Dict[str, Any]: A dictionary with cost breakdown information
    """
    try:
        # Get costs by service
        service_costs = get_cost_by_service()

        # Get costs by operation for each service
        operation_costs = {}
        for service in service_costs:
            operation_costs[service] = get_cost_by_operation(service)

        return {
            "services": service_costs,
            "operations": operation_costs,
        }
    except Exception as e:
        logger.error(f"Error getting cost breakdown: {e}")
        return {
            "error": str(e),
            "services": {},
            "operations": {},
        }


def get_budget_status_endpoint() -> Dict[str, Any]:
    """
    Get the current budget status.

    Returns:
        Dict[str, Any]: A dictionary with budget status information
    """
    return check_budget_thresholds()


def get_scaling_gate_status_endpoint() -> Dict[str, Any]:
    """
    Get the current scaling gate status.

    Returns:
        Dict[str, Any]: A dictionary with scaling gate status information
    """
    try:
        # Get the scaling gate status
        active, reason = is_scaling_gate_active()

        # Read the scaling gate file for history
        if os.path.exists(SCALING_GATE_FILE):
            with open(SCALING_GATE_FILE, "r") as f:
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
