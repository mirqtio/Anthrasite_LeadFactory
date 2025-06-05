"""
Service Cost Decorators
-----------------------
Decorators for automatically enforcing per-service cost caps on functions and methods.
These decorators integrate with the cost tracking and per-service cap systems.
"""

import functools
import logging
from typing import Any, Callable, Dict, Optional

from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.cost.per_service_cost_caps import per_service_cost_caps
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceCostCapExceeded(Exception):
    """Exception raised when a service cost cap would be exceeded."""
    pass


def enforce_service_cost_cap(
    service: str,
    operation: str,
    estimated_cost: Optional[float] = None,
    cost_calculator: Optional[Callable] = None,
    track_actual_cost: bool = True,
):
    """
    Decorator to enforce service cost caps before executing a function.
    
    Args:
        service: Service name (e.g., 'openai', 'semrush')
        operation: Operation name (e.g., 'gpt-4', 'domain-overview')
        estimated_cost: Fixed estimated cost (optional)
        cost_calculator: Function to calculate cost from function args (optional)
        track_actual_cost: Whether to track the actual cost after execution
        
    Usage:
        @enforce_service_cost_cap('openai', 'gpt-4', estimated_cost=0.02)
        def call_openai_api():
            pass
            
        @enforce_service_cost_cap('semrush', 'domain-overview', cost_calculator=lambda *args, **kwargs: 0.10)
        def call_semrush_api():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Calculate estimated cost
            if estimated_cost is not None:
                cost_estimate = estimated_cost
            elif cost_calculator is not None:
                try:
                    cost_estimate = cost_calculator(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cost calculator failed for {service}.{operation}: {e}")
                    cost_estimate = 0.0
            else:
                # Use budget constraints system for estimation
                try:
                    from leadfactory.cost.budget_constraints import budget_constraints
                    estimate_obj = budget_constraints.estimate_operation_cost(service, operation)
                    cost_estimate = estimate_obj.estimated_cost
                except Exception as e:
                    logger.warning(f"Budget constraints estimation failed for {service}.{operation}: {e}")
                    cost_estimate = 0.0
            
            # Check if operation can be executed
            can_execute, reason, status = per_service_cost_caps.can_execute_operation(
                service, cost_estimate
            )
            
            if not can_execute:
                logger.error(f"Service cost cap exceeded for {service}.{operation}: {reason}")
                raise ServiceCostCapExceeded(f"{service} cost cap exceeded: {reason}")
            
            # Log pre-execution status if approaching limits
            if status.utilization_percent >= 70:  # Log when 70% of cap is used
                logger.warning(
                    f"Service {service} at {status.utilization_percent:.1f}% of daily cap "
                    f"(${status.daily_spent:.2f}/${status.daily_limit:.2f})"
                )
            
            # Execute the function
            try:
                result = func(*args, **kwargs)
                
                # Track actual cost if enabled
                if track_actual_cost:
                    # Try to extract actual cost from result if it's a dict with cost info
                    actual_cost = cost_estimate  # Default to estimate
                    
                    if isinstance(result, dict):
                        # Look for cost information in various formats
                        if 'cost' in result:
                            actual_cost = result['cost']
                        elif 'total_cost' in result:
                            actual_cost = result['total_cost']
                        elif 'usage' in result and isinstance(result['usage'], dict):
                            # OpenAI-style usage tracking
                            usage = result['usage']
                            if 'total_tokens' in usage:
                                # Estimate cost based on tokens (simplified)
                                tokens = usage['total_tokens']
                                if 'gpt-4' in operation:
                                    actual_cost = tokens * 0.00003  # Rough estimate
                                elif 'gpt-3.5' in operation:
                                    actual_cost = tokens * 0.000002  # Rough estimate
                    
                    # Track the actual cost
                    cost_tracker.add_cost(
                        amount=actual_cost,
                        service=service,
                        operation=operation,
                        details={
                            'function': func.__name__,
                            'estimated_cost': cost_estimate,
                            'actual_cost': actual_cost,
                            'pre_execution_status': status.status.value,
                        }
                    )
                    
                    logger.debug(
                        f"Tracked cost for {service}.{operation}: "
                        f"${actual_cost:.4f} (estimated: ${cost_estimate:.4f})"
                    )
                
                return result
                
            except Exception as e:
                # Still track cost even if function fails (for failed API calls that still charge)
                if track_actual_cost:
                    cost_tracker.add_cost(
                        amount=cost_estimate,  # Use estimate for failed calls
                        service=service,
                        operation=operation,
                        details={
                            'function': func.__name__,
                            'estimated_cost': cost_estimate,
                            'execution_failed': True,
                            'error': str(e),
                        }
                    )
                raise
        
        return wrapper
    return decorator


def track_service_cost(
    service: str,
    operation: str,
    cost_calculator: Optional[Callable] = None,
    extract_cost_from_result: bool = True,
):
    """
    Decorator to track service costs without enforcing caps.
    Useful for monitoring costs of operations that should always run.
    
    Args:
        service: Service name
        operation: Operation name
        cost_calculator: Function to calculate cost from function args
        extract_cost_from_result: Whether to try extracting cost from function result
        
    Usage:
        @track_service_cost('internal', 'database_query')
        def run_database_query():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute function first
            result = func(*args, **kwargs)
            
            # Calculate cost
            cost = 0.0
            
            if cost_calculator is not None:
                try:
                    cost = cost_calculator(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Cost calculator failed for {service}.{operation}: {e}")
            
            if extract_cost_from_result and isinstance(result, dict):
                # Try to extract cost from result
                if 'cost' in result:
                    cost = result['cost']
                elif 'total_cost' in result:
                    cost = result['total_cost']
            
            # Track the cost
            if cost > 0:
                cost_tracker.add_cost(
                    amount=cost,
                    service=service,
                    operation=operation,
                    details={
                        'function': func.__name__,
                        'tracking_only': True,
                    }
                )
                
                logger.debug(f"Tracked cost for {service}.{operation}: ${cost:.4f}")
            
            return result
        
        return wrapper
    return decorator


def cost_aware(
    service: str,
    operation: str,
    warn_threshold: float = 0.8,
    critical_threshold: float = 0.9,
):
    """
    Decorator that makes a function aware of service cost status.
    Adds cost status information to function execution and logs warnings.
    
    Args:
        service: Service name
        operation: Operation name
        warn_threshold: Threshold for warning logs (0.0-1.0)
        critical_threshold: Threshold for critical logs (0.0-1.0)
        
    Usage:
        @cost_aware('openai', 'gpt-4')
        def call_openai_with_awareness():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get current service status
            status = per_service_cost_caps.get_service_status(service)
            
            # Log warnings based on utilization
            utilization_ratio = status.utilization_percent / 100
            
            if utilization_ratio >= critical_threshold:
                logger.critical(
                    f"CRITICAL: Service {service} at {status.utilization_percent:.1f}% of daily cap! "
                    f"Remaining: ${status.remaining:.2f}"
                )
            elif utilization_ratio >= warn_threshold:
                logger.warning(
                    f"WARNING: Service {service} at {status.utilization_percent:.1f}% of daily cap. "
                    f"Remaining: ${status.remaining:.2f}"
                )
            
            # Add cost status to kwargs if function accepts it
            if 'cost_status' in func.__code__.co_varnames:
                kwargs['cost_status'] = status
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def conditional_execution(
    service: str,
    max_utilization: float = 0.95,
    fallback_function: Optional[Callable] = None,
):
    """
    Decorator that conditionally executes a function based on service cost utilization.
    Can provide a fallback function if the primary function shouldn't run.
    
    Args:
        service: Service name
        max_utilization: Maximum utilization (0.0-1.0) before skipping execution
        fallback_function: Function to call instead if utilization is too high
        
    Usage:
        def fallback_implementation():
            return "fallback result"
            
        @conditional_execution('openai', max_utilization=0.9, fallback_function=fallback_implementation)
        def expensive_ai_operation():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get current service status
            status = per_service_cost_caps.get_service_status(service)
            utilization_ratio = status.utilization_percent / 100
            
            if utilization_ratio >= max_utilization:
                logger.info(
                    f"Skipping {func.__name__} due to high {service} utilization "
                    f"({status.utilization_percent:.1f}% >= {max_utilization * 100:.1f}%)"
                )
                
                if fallback_function is not None:
                    logger.info(f"Executing fallback function instead")
                    return fallback_function(*args, **kwargs)
                else:
                    # Return None or raise exception based on preference
                    return None
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Convenience functions for common use cases

def openai_cost_cap(operation: str = "gpt-4", estimated_cost: Optional[float] = None):
    """Convenience decorator for OpenAI API calls."""
    return enforce_service_cost_cap("openai", operation, estimated_cost)


def semrush_cost_cap(operation: str = "domain-overview", estimated_cost: float = 0.10):
    """Convenience decorator for Semrush API calls."""
    return enforce_service_cost_cap("semrush", operation, estimated_cost)


def screenshot_cost_cap(operation: str = "capture", estimated_cost: float = 0.001):
    """Convenience decorator for screenshot operations."""
    return enforce_service_cost_cap("screenshot", operation, estimated_cost)


def gpu_cost_cap(operation: str = "processing", cost_calculator: Optional[Callable] = None):
    """Convenience decorator for GPU operations."""
    return enforce_service_cost_cap("gpu", operation, cost_calculator=cost_calculator)