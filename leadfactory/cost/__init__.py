"""
Cost tracking and budget management package for LeadFactory.

This package contains modules for tracking API costs, managing budgets,
and implementing budget constraints to control expensive operations.
"""

# Import cost tracking and budget management modules
from leadfactory.cost.budget_constraints import (
    budget_check,
    budget_constraints,
    estimate_cost,
    get_budget_summary,
)
from leadfactory.cost.budget_decorators import (
    BudgetConstraintError,
    budget_constrained,
    enforce_budget_constraint,
    gpu_budget_check,
    openai_budget_check,
    screenshot_budget_check,
    semrush_budget_check,
    simulate_operation_cost,
)
from leadfactory.cost.budget_gate import budget_gate
from leadfactory.cost.cost_tracking import cost_tracker, track_cost

# Import per-service cost caps
from leadfactory.cost.per_service_cost_caps import (
    ServiceStatus,
    can_execute_service_operation,
    get_cost_caps_summary,
    get_service_cost_status,
    per_service_cost_caps,
)
from leadfactory.cost.service_cost_decorators import (
    ServiceCostCapExceeded,
    conditional_execution,
    cost_aware,
    enforce_service_cost_cap,
    gpu_cost_cap,
    openai_cost_cap,
    screenshot_cost_cap,
    semrush_cost_cap,
    track_service_cost,
)

__all__ = [
    # Core tracking
    "cost_tracker",
    "track_cost",
    # Budget constraints
    "budget_constraints",
    "budget_check",
    "estimate_cost",
    "get_budget_summary",
    # Budget decorators
    "budget_constrained",
    "openai_budget_check",
    "semrush_budget_check",
    "screenshot_budget_check",
    "gpu_budget_check",
    "BudgetConstraintError",
    "enforce_budget_constraint",
    "simulate_operation_cost",
    # Legacy budget gate
    "budget_gate",
    # Per-service cost caps
    "per_service_cost_caps",
    "can_execute_service_operation",
    "get_cost_caps_summary",
    "get_service_cost_status",
    "ServiceStatus",
    # Service cost decorators
    "enforce_service_cost_cap",
    "track_service_cost",
    "cost_aware",
    "conditional_execution",
    "openai_cost_cap",
    "semrush_cost_cap",
    "screenshot_cost_cap",
    "gpu_cost_cap",
    "ServiceCostCapExceeded",
]
