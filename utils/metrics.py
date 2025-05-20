"""
Anthrasite Lead-Factory: Prometheus Metrics Exporter

This module provides Prometheus metrics for monitoring the Lead-Factory system.
It exposes a /metrics endpoint that can be scraped by Prometheus.
"""

import os
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Response, Request, status
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
    Gauge,
    Counter,
    Histogram,
    Summary,
    Info,
    Enum,
)

from .cost_tracker import (
    get_daily_cost,
    get_monthly_cost,
    get_cost_breakdown_by_service,
    is_scaling_gate_active,
    get_scaling_gate_history,
    check_budget_thresholds,
)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "function": "%(funcName)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Anthrasite Lead-Factory Metrics",
    description="Prometheus metrics exporter for Anthrasite Lead-Factory",
    version="1.0.0",
)

# Prometheus metrics
# Gauges
DAILY_COST = Gauge("lead_factory_daily_cost", "Total cost for the current day in USD", ["service"])

MONTHLY_COST = Gauge("lead_factory_monthly_cost", "Total cost for the current month in USD", ["service"])

BUDGET_UTILIZATION = Gauge(
    "lead_factory_budget_utilization",
    "Budget utilization as a percentage",
    ["period"],  # 'daily' or 'monthly'
)

SCALING_GATE_STATUS = Gauge(
    "lead_factory_scaling_gate_active",
    "Current status of the scaling gate (1 = active, 0 = inactive)",
)

# Counters
REQUEST_COUNT = Counter(
    "lead_factory_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"],
)

# Histograms
REQUEST_LATENCY = Histogram(
    "lead_factory_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

# Info
VERSION_INFO = Info("lead_factory_build", "Build and version information")


def update_metrics() -> None:
    """Update all Prometheus metrics."""
    try:
        # Update daily costs by service
        daily_costs = get_cost_breakdown_by_service(period="day")
        for service, cost in daily_costs.items():
            DAILY_COST.labels(service=service).set(cost)

        # Update monthly costs by service
        monthly_costs = get_cost_breakdown_by_service(period="month")
        for service, cost in monthly_costs.items():
            MONTHLY_COST.labels(service=service).set(cost)

        # Update budget utilization
        budget_info = check_budget_thresholds()
        BUDGET_UTILIZATION.labels(period="daily").set(
            (budget_info.get("daily_cost", 0) / budget_info.get("daily_budget", 1)) * 100
            if budget_info.get("daily_budget", 0) > 0
            else 0
        )
        BUDGET_UTILIZATION.labels(period="monthly").set(
            (budget_info.get("monthly_cost", 0) / budget_info.get("monthly_budget", 1)) * 100
            if budget_info.get("monthly_budget", 0) > 0
            else 0
        )

        # Update scaling gate status
        gate_active, _ = is_scaling_gate_active()
        SCALING_GATE_STATUS.set(1 if gate_active else 0)

        # Update version info
        VERSION_INFO.info(
            {
                "version": "1.0.0",
                "build_date": datetime.utcnow().isoformat(),
                "environment": os.getenv("ENVIRONMENT", "development"),
            }
        )

    except Exception as e:
        logger.error(f"Error updating metrics: {str(e)}", exc_info=True)


@app.middleware("http")
async def http_metrics_middleware(request: Request, call_next):
    """Middleware to track HTTP request metrics."""
    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        raise e
    finally:
        # Record request metrics
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=status_code).inc()

        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    update_metrics()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/scaling-gate/status")
async def scaling_gate_status():
    """Get current scaling gate status."""
    is_active, reason = is_scaling_gate_active()
    return {
        "scaling_gate_active": is_active,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/costs/daily")
async def get_daily_costs():
    """Get daily cost breakdown by service."""
    return get_cost_breakdown_by_service(period="day")


@app.get("/costs/monthly")
async def get_monthly_costs():
    """Get monthly cost breakdown by service."""
    return get_cost_breakdown_by_service(period="month")


def start_metrics_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI metrics server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
    """
    import uvicorn

    logger.info(f"Starting metrics server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the Prometheus metrics server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")

    args = parser.parse_args()
    start_metrics_server(host=args.host, port=args.port)
