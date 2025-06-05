"""
IP Rotation API Endpoints

This module provides REST API endpoints for manual control and configuration
of the IP rotation system. It includes endpoints for monitoring, control,
and configuration management.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

# Import logging with fallback
try:
    from leadfactory.utils.logging_utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

# Import IP rotation services
try:
    from leadfactory.services.ip_rotation import (
        IPRotationService,
        IPSubuserPool,
        IPSubuserStatus,
        RotationReason,
    )
    from leadfactory.services.ip_rotation_alerting import (
        AlertSeverity,
        AlertType,
        IPRotationAlerting,
    )
except ImportError:
    logger.warning("IP rotation services not available")


# Pydantic models for API requests/responses
class IPSubuserRequest(BaseModel):
    """Request model for adding IP/subuser."""

    ip_address: str = Field(..., description="IP address")
    subuser: str = Field(..., description="Subuser name")
    priority: int = Field(default=1, description="Priority level (1-10)")


class IPSubuserResponse(BaseModel):
    """Response model for IP/subuser information."""

    ip_address: str
    subuser: str
    status: str
    priority: int
    performance_score: float
    total_sent: int
    total_bounced: int
    bounce_rate: float
    cooldown_until: Optional[str]
    last_used: Optional[str]


class RotationRequest(BaseModel):
    """Request model for manual rotation."""

    from_ip: str = Field(..., description="Source IP address")
    from_subuser: str = Field(..., description="Source subuser")
    to_ip: Optional[str] = Field(None, description="Target IP address (optional)")
    to_subuser: Optional[str] = Field(None, description="Target subuser (optional)")
    reason: str = Field(default="manual_rotation", description="Rotation reason")


class ConfigurationUpdate(BaseModel):
    """Request model for configuration updates."""

    bounce_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    cooldown_minutes: Optional[int] = Field(None, ge=0)
    rotation_delay_seconds: Optional[int] = Field(None, ge=0)
    min_performance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    enable_automatic_rotation: Optional[bool] = None


class SystemStatus(BaseModel):
    """System status response model."""

    status: str
    total_ips: int
    active_ips: int
    disabled_ips: int
    cooldown_ips: int
    automatic_rotation_enabled: bool
    circuit_breaker_status: str
    last_rotation: Optional[str]
    total_rotations: int


class AlertSummary(BaseModel):
    """Alert summary response model."""

    total_alerts: int
    by_severity: dict[str, int]
    by_type: dict[str, int]
    time_period_hours: int


# Global service instances (would be dependency injected in production)
_rotation_service: Optional[IPRotationService] = None
_alerting_service: Optional[IPRotationAlerting] = None


def get_rotation_service() -> IPRotationService:
    """Dependency to get rotation service instance."""
    global _rotation_service
    if _rotation_service is None:
        _rotation_service = IPRotationService()
    return _rotation_service


def get_alerting_service() -> IPRotationAlerting:
    """Dependency to get alerting service instance."""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = IPRotationAlerting()
    return _alerting_service


# Create router
router = APIRouter(prefix="/api/v1/ip-rotation", tags=["IP Rotation"])


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Get overall system status."""
    try:
        pool_status = rotation_service.get_pool_status()
        dashboard_data = alerting_service.get_dashboard_data()

        status_counts = {"active": 0, "disabled": 0, "cooldown": 0, "maintenance": 0}
        for ip_info in pool_status:
            status_counts[ip_info["status"]] += 1

        return SystemStatus(
            status=dashboard_data["system_status"]["health"],
            total_ips=len(pool_status),
            active_ips=status_counts["active"],
            disabled_ips=status_counts["disabled"],
            cooldown_ips=status_counts["cooldown"],
            automatic_rotation_enabled=rotation_service.enable_automatic_rotation,
            circuit_breaker_status=dashboard_data["circuit_breaker_status"]["state"],
            last_rotation=dashboard_data["system_status"]["last_rotation"],
            total_rotations=dashboard_data["system_status"]["total_rotations"],
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}",
        )


@router.get("/pool", response_model=list[IPSubuserResponse])
async def get_ip_pool(
    rotation_service: IPRotationService = Depends(get_rotation_service),
):
    """Get all IPs in the rotation pool."""
    try:
        pool_status = rotation_service.get_pool_status()

        return [
            IPSubuserResponse(
                ip_address=ip_info["ip_address"],
                subuser=ip_info["subuser"],
                status=ip_info["status"],
                priority=ip_info["priority"],
                performance_score=ip_info["performance_score"],
                total_sent=ip_info["total_sent"],
                total_bounced=ip_info["total_bounced"],
                bounce_rate=ip_info["bounce_rate"],
                cooldown_until=ip_info["cooldown_until"],
                last_used=ip_info["last_used"],
            )
            for ip_info in pool_status
        ]

    except Exception as e:
        logger.error(f"Error getting IP pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get IP pool: {str(e)}",
        )


@router.post("/pool", status_code=status.HTTP_201_CREATED)
async def add_ip_to_pool(
    request: IPSubuserRequest,
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Add a new IP/subuser to the rotation pool."""
    try:
        rotation_service.add_ip_subuser(
            request.ip_address, request.subuser, request.priority
        )

        alerting_service.send_alert(
            AlertType.SYSTEM_ERROR,  # Using system_error as generic info type
            AlertSeverity.INFO,
            f"IP/subuser added to pool: {request.ip_address}/{request.subuser}",
            metadata={
                "ip_address": request.ip_address,
                "subuser": request.subuser,
                "priority": request.priority,
            },
        )

        return {"message": "IP/subuser added successfully"}

    except Exception as e:
        logger.error(f"Error adding IP to pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add IP to pool: {str(e)}",
        )


@router.delete("/pool/{ip_address}/{subuser}")
async def remove_ip_from_pool(
    ip_address: str,
    subuser: str,
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Remove an IP/subuser from the rotation pool."""
    try:
        rotation_service.remove_ip_subuser(ip_address, subuser)

        alerting_service.send_alert(
            AlertType.SYSTEM_ERROR,  # Using system_error as generic info type
            AlertSeverity.INFO,
            f"IP/subuser removed from pool: {ip_address}/{subuser}",
            metadata={"ip_address": ip_address, "subuser": subuser},
        )

        return {"message": "IP/subuser removed successfully"}

    except Exception as e:
        logger.error(f"Error removing IP from pool: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to remove IP from pool: {str(e)}",
        )


@router.post("/rotate")
async def execute_manual_rotation(
    request: RotationRequest,
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Execute a manual rotation."""
    try:
        # Find the target if not specified
        if not request.to_ip or not request.to_subuser:
            alternative = rotation_service.find_best_alternative(
                request.from_ip, request.from_subuser
            )
            if not alternative:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No suitable alternative found",
                )
            target_ip, target_subuser = alternative
        else:
            target_ip, target_subuser = request.to_ip, request.to_subuser

        # Execute rotation
        success = rotation_service.execute_rotation(
            request.from_ip,
            request.from_subuser,
            target_ip,
            target_subuser,
            RotationReason.MANUAL_ROTATION,
        )

        if success:
            alerting_service.record_rotation(
                f"{request.from_ip}/{request.from_subuser}",
                f"{target_ip}/{target_subuser}",
                request.reason,
            )

            return {
                "message": "Rotation executed successfully",
                "from": f"{request.from_ip}/{request.from_subuser}",
                "to": f"{target_ip}/{target_subuser}",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rotation failed",
            )

    except Exception as e:
        logger.error(f"Error executing manual rotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute rotation: {str(e)}",
        )


@router.put("/config")
async def update_configuration(
    config: ConfigurationUpdate,
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Update system configuration."""
    try:
        updates = {}

        if config.bounce_threshold is not None:
            rotation_service.bounce_threshold = config.bounce_threshold
            updates["bounce_threshold"] = config.bounce_threshold

        if config.cooldown_minutes is not None:
            rotation_service.cooldown_minutes = config.cooldown_minutes
            updates["cooldown_minutes"] = config.cooldown_minutes

        if config.rotation_delay_seconds is not None:
            rotation_service.rotation_delay_seconds = config.rotation_delay_seconds
            updates["rotation_delay_seconds"] = config.rotation_delay_seconds

        if config.min_performance_score is not None:
            rotation_service.min_performance_score = config.min_performance_score
            updates["min_performance_score"] = config.min_performance_score

        if config.enable_automatic_rotation is not None:
            rotation_service.enable_automatic_rotation = (
                config.enable_automatic_rotation
            )
            updates["enable_automatic_rotation"] = config.enable_automatic_rotation

        alerting_service.send_alert(
            AlertType.SYSTEM_ERROR,  # Using system_error as generic info type
            AlertSeverity.INFO,
            f"Configuration updated: {', '.join(updates.keys())}",
            metadata={"updates": updates},
        )

        return {"message": "Configuration updated successfully", "updates": updates}

    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}",
        )


@router.get("/config")
async def get_configuration(
    rotation_service: IPRotationService = Depends(get_rotation_service),
):
    """Get current system configuration."""
    try:
        return {
            "bounce_threshold": rotation_service.bounce_threshold,
            "cooldown_minutes": rotation_service.cooldown_minutes,
            "rotation_delay_seconds": rotation_service.rotation_delay_seconds,
            "min_performance_score": rotation_service.min_performance_score,
            "enable_automatic_rotation": rotation_service.enable_automatic_rotation,
        }

    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}",
        )


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Reset the circuit breaker."""
    try:
        alerting_service.circuit_breaker.record_success()

        alerting_service.send_alert(
            AlertType.CIRCUIT_BREAKER_TRIGGERED,
            AlertSeverity.INFO,
            "Circuit breaker manually reset",
            metadata={},
        )

        return {"message": "Circuit breaker reset successfully"}

    except Exception as e:
        logger.error(f"Error resetting circuit breaker: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset circuit breaker: {str(e)}",
        )


@router.get("/alerts/summary", response_model=AlertSummary)
async def get_alert_summary(
    hours: int = Query(default=24, ge=1, le=168),  # 1 hour to 1 week
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Get alert summary for the specified time period."""
    try:
        summary = alerting_service.get_alert_summary(hours)
        return AlertSummary(**summary)

    except Exception as e:
        logger.error(f"Error getting alert summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert summary: {str(e)}",
        )


@router.get("/dashboard")
async def get_dashboard_data(
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Get comprehensive dashboard data."""
    try:
        return alerting_service.get_dashboard_data()

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard data: {str(e)}",
        )


@router.post("/maintenance/{ip_address}/{subuser}")
async def set_maintenance_mode(
    ip_address: str,
    subuser: str,
    enable: bool = Query(..., description="Enable or disable maintenance mode"),
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Set maintenance mode for an IP/subuser."""
    try:
        # Find the IP in the pool
        for pool_entry in rotation_service.ip_pool:
            if pool_entry.ip_address == ip_address and pool_entry.subuser == subuser:
                if enable:
                    pool_entry.status = IPSubuserStatus.MAINTENANCE
                    message = f"Maintenance mode enabled for {ip_address}/{subuser}"
                else:
                    pool_entry.status = IPSubuserStatus.ACTIVE
                    message = f"Maintenance mode disabled for {ip_address}/{subuser}"

                alerting_service.send_alert(
                    AlertType.SYSTEM_ERROR,  # Using system_error as generic info type
                    AlertSeverity.INFO,
                    message,
                    metadata={
                        "ip_address": ip_address,
                        "subuser": subuser,
                        "maintenance_enabled": enable,
                    },
                )

                return {"message": message}

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP/subuser not found in pool",
        )

    except Exception as e:
        logger.error(f"Error setting maintenance mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set maintenance mode: {str(e)}",
        )


@router.post("/cleanup")
async def cleanup_old_data(
    days: int = Query(default=7, ge=1, le=30),
    rotation_service: IPRotationService = Depends(get_rotation_service),
    alerting_service: IPRotationAlerting = Depends(get_alerting_service),
):
    """Clean up old rotation events and alerts."""
    try:
        rotation_service.cleanup_old_events(days)
        alerting_service.cleanup_old_alerts(days)

        return {"message": f"Cleaned up data older than {days} days"}

    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean up old data: {str(e)}",
        )
