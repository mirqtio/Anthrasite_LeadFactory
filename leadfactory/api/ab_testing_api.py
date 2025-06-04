"""
A/B Testing API - Admin interface for managing A/B tests.

Provides REST API endpoints for creating, managing, and analyzing A/B tests
for email subject lines and pricing optimization.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from leadfactory.ab_testing.ab_test_manager import (
    ABTestManager,
    TestType,
    ab_test_manager,
)
from leadfactory.ab_testing.analytics import ABTestAnalytics
from leadfactory.ab_testing.email_ab_test import EmailABTest
from leadfactory.ab_testing.pricing_ab_test import PricingABTest
from leadfactory.ab_testing.statistical_engine import StatisticalEngine

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/ab-testing", tags=["ab-testing"])


class CreateEmailTestRequest(BaseModel):
    """Request model for creating email A/B test."""

    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    email_template: str = Field(default="report_delivery", description="Email template")
    subject_variants: List[Dict[str, Any]] = Field(
        ..., description="Subject line variants"
    )
    target_sample_size: int = Field(default=1000, description="Target sample size")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CreatePricingTestRequest(BaseModel):
    """Request model for creating pricing A/B test."""

    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    audit_type: str = Field(..., description="Audit type (seo, security, etc.)")
    price_variants: List[Dict[str, Any]] = Field(..., description="Price variants")
    target_sample_size: int = Field(default=1000, description="Target sample size")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TestStatusUpdate(BaseModel):
    """Request model for updating test status."""

    action: str = Field(..., description="Action: start, stop, pause")


def get_ab_test_manager() -> ABTestManager:
    """Dependency to get A/B test manager instance."""
    return ab_test_manager


def get_email_ab_test() -> EmailABTest:
    """Dependency to get email A/B test instance."""
    return EmailABTest()


def get_pricing_ab_test() -> PricingABTest:
    """Dependency to get pricing A/B test instance."""
    return PricingABTest()


def get_ab_test_analytics() -> ABTestAnalytics:
    """Dependency to get A/B test analytics instance."""
    return ABTestAnalytics()


def get_statistical_engine() -> StatisticalEngine:
    """Dependency to get statistical engine instance."""
    return StatisticalEngine()


@router.post("/email-tests")
async def create_email_test(
    request: CreateEmailTestRequest,
    email_ab_test: EmailABTest = Depends(get_email_ab_test),
):
    """Create a new email subject line A/B test."""
    try:
        logger.info(f"Creating email A/B test: {request.name}")

        test_id = email_ab_test.create_subject_line_test(
            name=request.name,
            description=request.description,
            subject_variants=request.subject_variants,
            target_sample_size=request.target_sample_size,
            email_template=request.email_template,
            metadata=request.metadata,
        )

        return {
            "test_id": test_id,
            "message": "Email A/B test created successfully",
            "status": "draft",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating email A/B test: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create email A/B test")


@router.post("/pricing-tests")
async def create_pricing_test(
    request: CreatePricingTestRequest,
    pricing_ab_test: PricingABTest = Depends(get_pricing_ab_test),
):
    """Create a new pricing A/B test."""
    try:
        logger.info(f"Creating pricing A/B test: {request.name}")

        test_id = pricing_ab_test.create_price_point_test(
            name=request.name,
            description=request.description,
            audit_type=request.audit_type,
            price_variants=request.price_variants,
            target_sample_size=request.target_sample_size,
            metadata=request.metadata,
        )

        return {
            "test_id": test_id,
            "message": "Pricing A/B test created successfully",
            "status": "draft",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating pricing A/B test: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create pricing A/B test")


@router.get("/tests")
async def list_tests(
    test_type: Optional[str] = Query(None, description="Filter by test type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    test_manager: ABTestManager = Depends(get_ab_test_manager),
):
    """List all A/B tests with optional filters."""
    try:
        # Convert string to enum if provided
        test_type_enum = None
        if test_type:
            try:
                test_type_enum = TestType(test_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid test type: {test_type}"
                )

        # Get tests (for now, just get active tests)
        if status == "active":
            tests = test_manager.get_active_tests(test_type_enum)
        else:
            # For other statuses, we'd need to add more methods to test_manager
            tests = test_manager.get_active_tests(test_type_enum)

        # Convert to response format
        test_list = []
        for test in tests:
            test_list.append(
                {
                    "id": test.id,
                    "name": test.name,
                    "description": test.description,
                    "test_type": test.test_type.value,
                    "status": test.status.value,
                    "start_date": (
                        test.start_date.isoformat() if test.start_date else None
                    ),
                    "end_date": test.end_date.isoformat() if test.end_date else None,
                    "target_sample_size": test.target_sample_size,
                    "variants_count": len(test.variants),
                    "metadata": test.metadata,
                    "created_at": test.created_at.isoformat(),
                    "updated_at": test.updated_at.isoformat(),
                }
            )

        return {
            "tests": test_list,
            "total": len(test_list),
            "filters": {"test_type": test_type, "status": status},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing A/B tests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list A/B tests")


@router.get("/tests/{test_id}")
async def get_test(
    test_id: str,
    test_manager: ABTestManager = Depends(get_ab_test_manager),
):
    """Get detailed information about a specific A/B test."""
    try:
        test_config = test_manager.get_test_config(test_id)

        if not test_config:
            raise HTTPException(status_code=404, detail="Test not found")

        return {
            "id": test_config.id,
            "name": test_config.name,
            "description": test_config.description,
            "test_type": test_config.test_type.value,
            "status": test_config.status.value,
            "start_date": (
                test_config.start_date.isoformat() if test_config.start_date else None
            ),
            "end_date": (
                test_config.end_date.isoformat() if test_config.end_date else None
            ),
            "target_sample_size": test_config.target_sample_size,
            "significance_threshold": test_config.significance_threshold,
            "minimum_effect_size": test_config.minimum_effect_size,
            "variants": test_config.variants,
            "metadata": test_config.metadata,
            "created_at": test_config.created_at.isoformat(),
            "updated_at": test_config.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting A/B test {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get A/B test")


@router.put("/tests/{test_id}/status")
async def update_test_status(
    test_id: str,
    request: TestStatusUpdate,
    test_manager: ABTestManager = Depends(get_ab_test_manager),
):
    """Update the status of an A/B test."""
    try:
        if request.action == "start":
            success = test_manager.start_test(test_id)
            message = "Test started successfully" if success else "Failed to start test"
        elif request.action == "stop":
            success = test_manager.stop_test(test_id)
            message = "Test stopped successfully" if success else "Failed to stop test"
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid action: {request.action}"
            )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "test_id": test_id,
            "action": request.action,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating test status for {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update test status")


@router.get("/tests/{test_id}/results")
async def get_test_results(
    test_id: str,
    analytics: ABTestAnalytics = Depends(get_ab_test_analytics),
):
    """Get comprehensive results and analysis for an A/B test."""
    try:
        report = analytics.generate_test_report(test_id)
        return report

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting test results for {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get test results")


@router.get("/tests/{test_id}/performance")
async def get_test_performance(
    test_id: str,
    test_manager: ABTestManager = Depends(get_ab_test_manager),
    email_ab_test: EmailABTest = Depends(get_email_ab_test),
    pricing_ab_test: PricingABTest = Depends(get_pricing_ab_test),
):
    """Get performance metrics for a specific test type."""
    try:
        test_config = test_manager.get_test_config(test_id)

        if not test_config:
            raise HTTPException(status_code=404, detail="Test not found")

        if test_config.test_type == TestType.EMAIL_SUBJECT:
            performance = email_ab_test.get_email_test_performance(test_id)
        elif test_config.test_type == TestType.PRICING:
            performance = pricing_ab_test.get_pricing_test_performance(test_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported test type: {test_config.test_type}",
            )

        return performance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test performance for {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get test performance")


@router.get("/dashboard")
async def get_dashboard(
    test_type: Optional[str] = Query(None, description="Filter by test type"),
    analytics: ABTestAnalytics = Depends(get_ab_test_analytics),
):
    """Get A/B testing dashboard overview."""
    try:
        # Convert string to enum if provided
        test_type_enum = None
        if test_type:
            try:
                test_type_enum = TestType(test_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid test type: {test_type}"
                )

        portfolio_overview = analytics.get_portfolio_overview(test_type_enum)
        return portfolio_overview

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard")


@router.post("/tests/{test_id}/record-event")
async def record_test_event(
    test_id: str,
    event_type: str = Query(..., description="Event type"),
    user_id: str = Query(..., description="User identifier"),
    conversion_value: Optional[float] = Query(None, description="Conversion value"),
    metadata: Optional[Dict[str, Any]] = None,
    test_manager: ABTestManager = Depends(get_ab_test_manager),
):
    """Record a conversion event for an A/B test."""
    try:
        conversion_id = test_manager.record_conversion(
            test_id=test_id,
            user_id=user_id,
            conversion_type=event_type,
            conversion_value=conversion_value,
            metadata=metadata or {},
        )

        return {
            "conversion_id": conversion_id,
            "test_id": test_id,
            "event_type": event_type,
            "user_id": user_id,
            "recorded_at": datetime.utcnow().isoformat(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording test event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record test event")


@router.get("/tests/{test_id}/export")
async def export_test_data(
    test_id: str,
    format_type: str = Query("json", description="Export format (json, csv)"),
    analytics: ABTestAnalytics = Depends(get_ab_test_analytics),
):
    """Export test data in specified format."""
    try:
        exported_data = analytics.export_test_data(test_id, format_type)

        if format_type.lower() == "csv":
            return JSONResponse(
                content={"data": exported_data}, headers={"Content-Type": "text/csv"}
            )
        else:
            return JSONResponse(content={"data": exported_data})

    except ValueError as e:
        if "Test not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting test data for {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export test data")


@router.get("/stats/sample-size")
async def calculate_sample_size(
    baseline_rate: float = Query(..., description="Expected baseline conversion rate"),
    effect_size: float = Query(..., description="Minimum detectable effect size"),
    alpha: float = Query(0.05, description="Significance level"),
    power: float = Query(0.8, description="Statistical power"),
    statistical_engine: StatisticalEngine = Depends(get_statistical_engine),
):
    """Calculate required sample size for A/B test."""
    try:
        sample_size = statistical_engine.calculate_sample_size(
            baseline_rate=baseline_rate,
            minimum_detectable_effect=effect_size,
            alpha=alpha,
            power=power,
        )

        return {
            "required_sample_size_per_variant": sample_size,
            "total_sample_size": sample_size * 2,
            "parameters": {
                "baseline_rate": baseline_rate,
                "effect_size": effect_size,
                "alpha": alpha,
                "power": power,
            },
        }

    except Exception as e:
        logger.error(f"Error calculating sample size: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate sample size")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ab_testing_api",
        "timestamp": datetime.utcnow().isoformat(),
    }
