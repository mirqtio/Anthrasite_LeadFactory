"""
Anthrasite Lead-Factory: Prometheus Metrics Exporter
This module provides Prometheus metrics for monitoring the Lead-Factory system.
It exposes a /metrics endpoint that can be scraped by Prometheus.
"""

import os
import time
from datetime import datetime

from fastapi import FastAPI, Request, Response
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               Info, generate_latest)

from .cost_tracker import (check_budget_thresholds,
                           get_cost_breakdown_by_service,
                           is_scaling_gate_active)
from .batch_metrics import update_batch_metrics, start_metrics_updater
# Import logging configuration
from .logging_config import get_logger

# Set up logging
logger = get_logger(__name__)
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
# Email deliverability metrics
BOUNCE_RATE_GAUGE = Gauge(
    "lead_factory_email_bounce_rate",
    "Email bounce rate as a percentage",
    ["ip_pool", "subuser"],  # Optional labels for IP pool and subuser
)
SPAM_RATE_GAUGE = Gauge(
    "lead_factory_email_spam_rate",
    "Email spam complaint rate as a percentage",
    ["ip_pool", "subuser"],  # Optional labels for IP pool and subuser
)
BATCH_COMPLETION_GAUGE = Gauge(
    "lead_factory_batch_completion",
    "Percentage of batch processing completed",
    ["stage"],  # Pipeline stage (scrape, enrich, dedupe, score, mockup, email)
)
COST_PER_LEAD_GAUGE = Gauge(
    "lead_factory_cost_per_lead",
    "Average cost per lead in USD",
)
GPU_COST_GAUGE = Gauge(
    "lead_factory_gpu_cost",
    "GPU cost in USD",
    ["operation"],  # Operation using GPU (e.g., mockup_generation)
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


def update_metrics():
    """Update all Prometheus metrics."""
    try:
        # Update batch completion metrics
        update_batch_metrics()
        
        # Update cost metrics
        daily_costs = get_cost_breakdown_by_service(period="day")
        monthly_costs = get_cost_breakdown_by_service(period="month")

        # Update daily cost gauge
        for service, cost in daily_costs.items():
            DAILY_COST.labels(service=service).set(cost)

        # Update monthly cost gauge
        for service, cost in monthly_costs.items():
            MONTHLY_COST.labels(service=service).set(cost)

        # Calculate total costs
        total_daily_cost = sum(daily_costs.values())
        total_monthly_cost = sum(monthly_costs.values())

        # Get budget thresholds
        daily_budget, monthly_budget = check_budget_thresholds()

        # Update budget utilization gauge
        if daily_budget > 0:
            BUDGET_UTILIZATION.labels(period="daily").set(total_daily_cost / daily_budget * 100)
        if monthly_budget > 0:
            BUDGET_UTILIZATION.labels(period="monthly").set(total_monthly_cost / monthly_budget * 100)

        # Update scaling gate status
        SCALING_GATE_STATUS.set(1 if is_scaling_gate_active() else 0)
        
        # Update cost per lead metric if leads exist
        try:
            import sqlite3
            from pathlib import Path
            
            # Connect to database
            db_path = os.getenv("DATABASE_PATH", "leadfactory.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get total number of leads
            cursor.execute("SELECT COUNT(*) FROM businesses")
            total_leads = cursor.fetchone()[0]
            
            # Calculate cost per lead if leads exist
            if total_leads > 0:
                cost_per_lead = total_monthly_cost / total_leads
                COST_PER_LEAD_GAUGE.set(cost_per_lead)
                logger.debug(f"Cost per lead: ${cost_per_lead:.2f}")
            
            # Check if GPU burst mode is active
            gpu_burst = os.getenv("GPU_BURST", "0") == "1"
            if gpu_burst:
                # Track GPU cost for mockup generation
                gpu_cost = daily_costs.get("openai", 0) * 0.8  # Estimate 80% of OpenAI cost is GPU
                GPU_COST_GAUGE.labels(operation="mockup_generation").set(gpu_cost)
                logger.debug(f"GPU cost for mockup generation: ${gpu_cost:.2f}")
            
            conn.close()
        except Exception as e:
            logger.warning(f"Error updating cost per lead metric: {e}")

        logger.debug("Updated Prometheus metrics")
    except Exception as e:
        logger.error(f"Error updating Prometheus metrics: {e}")
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


def start_metrics_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the FastAPI metrics server.
    Args:
        host: Host to bind to. Default is localhost (127.0.0.1) for security.
              Set to 0.0.0.0 only in containerized environments with proper network security.
        port: Port to listen on.
    """
    import uvicorn
    
    # Start batch metrics updater thread
    logger.info("Starting batch metrics updater thread")
    start_metrics_updater(interval_seconds=int(os.getenv("BATCH_METRICS_UPDATE_INTERVAL", "60")))

    # Use environment variable to allow override in container environments
    bind_host = os.getenv("METRICS_BIND_HOST", host)
    logger.info(f"Starting metrics server on http://{bind_host}:{port}")
    uvicorn.run(app, host=bind_host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the Prometheus metrics server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (use 127.0.0.1 for security, 0.0.0.0 only in secure environments)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    start_metrics_server(host=args.host, port=args.port)
