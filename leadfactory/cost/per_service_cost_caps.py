"""
Per-Service Daily Cost Caps
---------------------------
This module enforces daily cost caps per service to prevent any single service
from consuming the entire budget. It provides granular cost control and automatic
service throttling when limits are reached.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceStatus(str, Enum):
    """Service cost status levels."""
    AVAILABLE = "available"
    WARNING = "warning"
    CRITICAL = "critical"
    CAPPED = "capped"


@dataclass
class ServiceCostCap:
    """Configuration for a service cost cap."""
    service: str
    daily_limit: float
    warning_threshold: float = 0.8  # 80% of limit
    critical_threshold: float = 0.9  # 90% of limit
    enabled: bool = True


@dataclass
class ServiceCostStatus:
    """Current cost status for a service."""
    service: str
    daily_spent: float
    daily_limit: float
    remaining: float
    utilization_percent: float
    status: ServiceStatus
    last_updated: datetime


class PerServiceCostCaps:
    """Manages per-service daily cost caps and enforcement."""
    
    def __init__(self):
        """Initialize per-service cost caps system."""
        self.cost_tracker = cost_tracker
        self.service_caps = self._load_service_caps()
        self.enforcement_enabled = self._get_enforcement_setting()
        
        logger.info(f"Per-service cost caps initialized with {len(self.service_caps)} services")
    
    def _load_service_caps(self) -> Dict[str, ServiceCostCap]:
        """Load service cost caps from environment variables."""
        # Default service caps - these can be overridden by environment variables
        default_caps = {
            "openai": ServiceCostCap(
                service="openai",
                daily_limit=float(os.environ.get("OPENAI_DAILY_CAP", "20.0")),
                warning_threshold=float(os.environ.get("OPENAI_WARNING_THRESHOLD", "0.8")),
                critical_threshold=float(os.environ.get("OPENAI_CRITICAL_THRESHOLD", "0.9")),
            ),
            "semrush": ServiceCostCap(
                service="semrush", 
                daily_limit=float(os.environ.get("SEMRUSH_DAILY_CAP", "5.0")),
                warning_threshold=float(os.environ.get("SEMRUSH_WARNING_THRESHOLD", "0.8")),
                critical_threshold=float(os.environ.get("SEMRUSH_CRITICAL_THRESHOLD", "0.9")),
            ),
            "screenshot": ServiceCostCap(
                service="screenshot",
                daily_limit=float(os.environ.get("SCREENSHOT_DAILY_CAP", "2.0")),
                warning_threshold=float(os.environ.get("SCREENSHOT_WARNING_THRESHOLD", "0.8")),
                critical_threshold=float(os.environ.get("SCREENSHOT_CRITICAL_THRESHOLD", "0.9")),
            ),
            "gpu": ServiceCostCap(
                service="gpu",
                daily_limit=float(os.environ.get("GPU_DAILY_CAP", "10.0")),
                warning_threshold=float(os.environ.get("GPU_WARNING_THRESHOLD", "0.8")),
                critical_threshold=float(os.environ.get("GPU_CRITICAL_THRESHOLD", "0.9")),
            ),
            "sendgrid": ServiceCostCap(
                service="sendgrid",
                daily_limit=float(os.environ.get("SENDGRID_DAILY_CAP", "1.0")),
                warning_threshold=float(os.environ.get("SENDGRID_WARNING_THRESHOLD", "0.8")),
                critical_threshold=float(os.environ.get("SENDGRID_CRITICAL_THRESHOLD", "0.9")),
            ),
        }
        
        return default_caps
    
    def _get_enforcement_setting(self) -> bool:
        """Check if cost cap enforcement is enabled."""
        return os.environ.get("ENFORCE_SERVICE_COST_CAPS", "true").lower() == "true"
    
    def get_service_status(self, service: str) -> ServiceCostStatus:
        """Get current cost status for a service."""
        if service not in self.service_caps:
            # Return default status for unknown services
            return ServiceCostStatus(
                service=service,
                daily_spent=0.0,
                daily_limit=0.0,
                remaining=0.0,
                utilization_percent=0.0,
                status=ServiceStatus.AVAILABLE,
                last_updated=datetime.now(),
            )
        
        cap = self.service_caps[service]
        daily_spent = self.cost_tracker.get_daily_cost(service)
        remaining = max(0.0, cap.daily_limit - daily_spent)
        utilization_percent = (daily_spent / cap.daily_limit * 100) if cap.daily_limit > 0 else 0.0
        
        # Determine status
        if not cap.enabled:
            status = ServiceStatus.AVAILABLE
        elif utilization_percent >= 100:
            status = ServiceStatus.CAPPED
        elif utilization_percent >= (cap.critical_threshold * 100):
            status = ServiceStatus.CRITICAL
        elif utilization_percent >= (cap.warning_threshold * 100):
            status = ServiceStatus.WARNING
        else:
            status = ServiceStatus.AVAILABLE
        
        return ServiceCostStatus(
            service=service,
            daily_spent=daily_spent,
            daily_limit=cap.daily_limit,
            remaining=remaining,
            utilization_percent=utilization_percent,
            status=status,
            last_updated=datetime.now(),
        )
    
    def can_execute_operation(
        self, 
        service: str, 
        estimated_cost: float
    ) -> Tuple[bool, str, ServiceCostStatus]:
        """
        Check if an operation can be executed without exceeding service cap.
        
        Args:
            service: Service name
            estimated_cost: Estimated cost of the operation
            
        Returns:
            Tuple of (can_execute, reason, status)
        """
        if not self.enforcement_enabled:
            # If enforcement is disabled, always allow
            status = self.get_service_status(service)
            return True, "Cost cap enforcement disabled", status
        
        status = self.get_service_status(service)
        
        # If service is already capped, deny
        if status.status == ServiceStatus.CAPPED:
            return False, f"Service {service} has exceeded daily cap of ${status.daily_limit:.2f}", status
        
        # Check if operation would exceed cap
        projected_spent = status.daily_spent + estimated_cost
        if projected_spent > status.daily_limit:
            return (
                False,
                f"Operation would exceed {service} daily cap: "
                f"${projected_spent:.2f} > ${status.daily_limit:.2f}",
                status,
            )
        
        return True, "Operation within service cap", status
    
    def get_all_service_statuses(self) -> Dict[str, ServiceCostStatus]:
        """Get cost status for all configured services."""
        statuses = {}
        for service in self.service_caps:
            statuses[service] = self.get_service_status(service)
        return statuses
    
    def get_capped_services(self) -> List[str]:
        """Get list of services that have reached their daily cap."""
        capped_services = []
        for service in self.service_caps:
            status = self.get_service_status(service)
            if status.status == ServiceStatus.CAPPED:
                capped_services.append(service)
        return capped_services
    
    def get_warning_services(self) -> List[str]:
        """Get list of services approaching their daily cap."""
        warning_services = []
        for service in self.service_caps:
            status = self.get_service_status(service)
            if status.status in [ServiceStatus.WARNING, ServiceStatus.CRITICAL]:
                warning_services.append(service)
        return warning_services
    
    def update_service_cap(
        self, 
        service: str, 
        daily_limit: float,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """
        Update the cost cap for a service.
        
        Args:
            service: Service name
            daily_limit: New daily limit
            warning_threshold: Warning threshold (optional)
            critical_threshold: Critical threshold (optional)
            enabled: Whether the cap is enabled (optional)
            
        Returns:
            True if successful
        """
        try:
            if service not in self.service_caps:
                # Create new cap
                self.service_caps[service] = ServiceCostCap(
                    service=service,
                    daily_limit=daily_limit,
                    warning_threshold=warning_threshold or 0.8,
                    critical_threshold=critical_threshold or 0.9,
                    enabled=enabled if enabled is not None else True,
                )
            else:
                # Update existing cap
                cap = self.service_caps[service]
                cap.daily_limit = daily_limit
                if warning_threshold is not None:
                    cap.warning_threshold = warning_threshold
                if critical_threshold is not None:
                    cap.critical_threshold = critical_threshold
                if enabled is not None:
                    cap.enabled = enabled
            
            logger.info(f"Updated cost cap for {service}: ${daily_limit:.2f}/day")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update service cap for {service}: {e}")
            return False
    
    def disable_service_cap(self, service: str) -> bool:
        """Disable cost cap for a service."""
        if service in self.service_caps:
            self.service_caps[service].enabled = False
            logger.info(f"Disabled cost cap for {service}")
            return True
        return False
    
    def enable_service_cap(self, service: str) -> bool:
        """Enable cost cap for a service."""
        if service in self.service_caps:
            self.service_caps[service].enabled = True
            logger.info(f"Enabled cost cap for {service}")
            return True
        return False
    
    def get_cost_cap_report(self) -> Dict[str, any]:
        """Generate a comprehensive cost cap report."""
        statuses = self.get_all_service_statuses()
        
        # Aggregate statistics
        total_daily_limit = sum(cap.daily_limit for cap in self.service_caps.values() if cap.enabled)
        total_daily_spent = sum(status.daily_spent for status in statuses.values())
        
        capped_count = len([s for s in statuses.values() if s.status == ServiceStatus.CAPPED])
        warning_count = len([s for s in statuses.values() if s.status in [ServiceStatus.WARNING, ServiceStatus.CRITICAL]])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "enforcement_enabled": self.enforcement_enabled,
            "summary": {
                "total_daily_limit": total_daily_limit,
                "total_daily_spent": total_daily_spent,
                "total_remaining": total_daily_limit - total_daily_spent,
                "overall_utilization_percent": (total_daily_spent / total_daily_limit * 100) if total_daily_limit > 0 else 0,
                "services_capped": capped_count,
                "services_warning": warning_count,
                "services_total": len(self.service_caps),
            },
            "services": {
                service: {
                    "daily_limit": status.daily_limit,
                    "daily_spent": status.daily_spent,
                    "remaining": status.remaining,
                    "utilization_percent": status.utilization_percent,
                    "status": status.status.value,
                    "enabled": self.service_caps[service].enabled,
                }
                for service, status in statuses.items()
            },
            "capped_services": self.get_capped_services(),
            "warning_services": self.get_warning_services(),
        }
    
    def reset_daily_caps(self) -> bool:
        """
        Reset daily caps (typically called at start of new day).
        Note: This doesn't reset the cost tracking data, just the cap status.
        """
        try:
            logger.info("Daily cost caps reset for new day")
            return True
        except Exception as e:
            logger.error(f"Failed to reset daily caps: {e}")
            return False
    
    def estimate_remaining_capacity(self, service: str) -> Dict[str, any]:
        """
        Estimate remaining capacity for a service based on current usage patterns.
        
        Args:
            service: Service name
            
        Returns:
            Dictionary with capacity estimates
        """
        status = self.get_service_status(service)
        
        if status.daily_limit <= 0:
            return {
                "service": service,
                "remaining_budget": 0.0,
                "estimated_operations": 0,
                "time_until_cap": "unlimited",
            }
        
        # Get cost breakdown to estimate operation costs
        breakdown = self.cost_tracker.get_daily_cost_breakdown()
        service_breakdown = breakdown.get(service, {})
        
        # Estimate average cost per operation
        total_operations = sum(1 for _ in service_breakdown.keys())  # Simple count
        avg_cost_per_operation = status.daily_spent / total_operations if total_operations > 0 else 0.1
        
        estimated_operations = int(status.remaining / avg_cost_per_operation) if avg_cost_per_operation > 0 else 0
        
        # Estimate time until cap based on current burn rate
        now = datetime.now()
        start_of_day = datetime.combine(now.date(), datetime.min.time())
        hours_elapsed = (now - start_of_day).total_seconds() / 3600
        
        if hours_elapsed > 0 and status.daily_spent > 0:
            hourly_burn_rate = status.daily_spent / hours_elapsed
            hours_until_cap = status.remaining / hourly_burn_rate if hourly_burn_rate > 0 else float('inf')
            
            if hours_until_cap < float('inf'):
                time_until_cap = f"{hours_until_cap:.1f} hours"
            else:
                time_until_cap = "unlimited"
        else:
            time_until_cap = "unlimited"
        
        return {
            "service": service,
            "remaining_budget": status.remaining,
            "estimated_operations": estimated_operations,
            "time_until_cap": time_until_cap,
            "current_burn_rate": status.daily_spent / hours_elapsed if hours_elapsed > 0 else 0,
        }


# Create singleton instance
per_service_cost_caps = PerServiceCostCaps()


def can_execute_service_operation(service: str, estimated_cost: float) -> Tuple[bool, str]:
    """
    Convenience function to check if a service operation can be executed.
    
    Args:
        service: Service name
        estimated_cost: Estimated cost of the operation
        
    Returns:
        Tuple of (can_execute, reason)
    """
    can_execute, reason, _ = per_service_cost_caps.can_execute_operation(service, estimated_cost)
    return can_execute, reason


def get_service_cost_status(service: str) -> ServiceCostStatus:
    """
    Convenience function to get service cost status.
    
    Args:
        service: Service name
        
    Returns:
        ServiceCostStatus object
    """
    return per_service_cost_caps.get_service_status(service)


def get_cost_caps_summary() -> Dict[str, any]:
    """
    Convenience function to get cost caps summary.
    
    Returns:
        Cost caps report dictionary
    """
    return per_service_cost_caps.get_cost_cap_report()