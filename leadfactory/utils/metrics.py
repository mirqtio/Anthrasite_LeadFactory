"""
Metrics collection and reporting module for LeadFactory.

This module provides functionality to collect and report metrics for the LeadFactory pipeline.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Import our unified logging system
from .logging import get_logger

# Set up logging
logger = get_logger(__name__)

# Import prometheus_client with error handling
try:
    import prometheus_client
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        push_to_gateway,
        start_http_server,
    )

    METRICS_AVAILABLE = True
except (ImportError, SyntaxError) as e:
    METRICS_AVAILABLE = False
    logger.warning(
        f"Prometheus client not available - {e}"
    )

# Define metrics
if METRICS_AVAILABLE:
    # Pipeline metrics
    LEADS_SCRAPED = Counter(
        "leads_scraped_total", "Total number of leads scraped", ["source", "vertical"]
    )
    LEADS_ENRICHED = Counter(
        "leads_enriched_total", "Total number of leads enriched", ["tier"]
    )
    LEADS_DEDUPLICATED = Counter(
        "leads_deduplicated_total", "Total number of leads deduplicated"
    )
    LEADS_SCORED = Counter(
        "leads_scored_total", "Total number of leads scored", ["score_range"]
    )
    EMAILS_SENT = Counter(
        "emails_sent_total", "Total number of emails sent", ["template"]
    )
    EMAILS_OPENED = Counter(
        "emails_opened_total", "Total number of emails opened", ["template"]
    )
    EMAILS_CLICKED = Counter(
        "emails_clicked_total",
        "Total number of emails clicked",
        ["template", "link_type"],
    )
    MOCKUPS_GENERATED = Counter(
        "mockups_generated_total", "Total number of mockups generated", ["status"]
    )

    # Error and failure metrics
    PIPELINE_ERRORS = Counter(
        "pipeline_errors_total",
        "Total number of errors in the pipeline",
        ["stage", "error_type"],
    )
    API_FAILURES = Counter(
        "api_failures_total",
        "Total number of API failures",
        ["api_name", "endpoint", "status_code"],
    )
    RETRY_ATTEMPTS = Counter(
        "retry_attempts_total", "Total number of retry attempts", ["operation"]
    )

    # Performance metrics
    API_LATENCY = Histogram(
        "api_request_latency_seconds",
        "API request latency in seconds",
        ["api_name", "endpoint", "status"],
    )
    PIPELINE_DURATION = Histogram(
        "pipeline_stage_duration_seconds",
        "Duration of pipeline stages in seconds",
        ["stage", "status"],
    )
    BATCH_PROCESSING_TIME = Histogram(
        "batch_processing_time_seconds",
        "Time to process a batch of leads",
        ["batch_size", "operation"],
    )

    # Resource metrics
    COST_COUNTER = Counter(
        "api_cost_dollars_total",
        "Total API costs in dollars",
        ["api_name", "operation"],
    )
    COST_PER_LEAD = Gauge(
        "cost_per_lead_dollars", "Cost per lead in dollars", ["vertical"]
    )
    MEMORY_USAGE = Gauge("memory_usage_bytes", "Memory usage in bytes")
    CPU_USAGE = Gauge("cpu_usage_percent", "CPU usage percentage")
    DISK_USAGE = Gauge("disk_usage_bytes", "Disk usage in bytes")
    NETWORK_IO = Counter(
        "network_io_bytes_total", "Network I/O in bytes", ["direction"]
    )

    # Business metrics
    CONVERSION_RATE = Gauge(
        "conversion_rate_percent", "Conversion rate percentage", ["vertical"]
    )
    REPLIES_RECEIVED = Counter(
        "replies_received_total", "Total number of replies received", ["sentiment"]
    )
    BOUNCE_RATE = Gauge(
        "bounce_rate_percent", "Email bounce rate percentage", ["template"]
    )
    SPAM_RATE = Gauge(
        "spam_rate_percent", "Email spam complaint rate percentage", ["template"]
    )
    LEAD_QUALITY_SCORE = Gauge(
        "lead_quality_score", "Lead quality score", ["vertical", "source"]
    )
    PIPELINE_FAILURE_RATE = Gauge(
        "pipeline_failure_rate",
        "Failure rate of pipeline operations",
        ["operation", "stage"],
    )

    # Purchase and revenue metrics
    PURCHASES_TOTAL = Counter(
        "purchases_total",
        "Total number of successful purchases",
        ["audit_type", "currency"],
    )
    REVENUE_TOTAL = Counter(
        "revenue_total_cents", "Total revenue in cents", ["audit_type", "currency"]
    )
    STRIPE_FEES_TOTAL = Counter(
        "stripe_fees_total_cents", "Total Stripe fees in cents", ["currency"]
    )
    REFUNDS_TOTAL = Counter(
        "refunds_total", "Total number of refunds", ["reason", "currency"]
    )
    REFUND_AMOUNT_TOTAL = Counter(
        "refund_amount_total_cents", "Total refund amount in cents", ["currency"]
    )
    AVERAGE_ORDER_VALUE = Gauge(
        "average_order_value_cents", "Average order value in cents", ["audit_type"]
    )
    CUSTOMER_LIFETIME_VALUE = Gauge(
        "customer_lifetime_value_cents", "Customer lifetime value in cents"
    )
    MONTHLY_RECURRING_REVENUE = Gauge(
        "monthly_recurring_revenue_cents", "Monthly recurring revenue in cents"
    )
    DAILY_REVENUE = Gauge("daily_revenue_cents", "Daily revenue in cents", ["date"])
    CONVERSION_FUNNEL = Gauge(
        "conversion_funnel_rate", "Conversion funnel metrics", ["stage", "audit_type"]
    )

    # GPU Auto-Scaling metrics
    GPU_INSTANCES_ACTIVE = Gauge(
        "gpu_instances_active", "Number of active GPU instances", ["provider", "instance_type"]
    )
    GPU_QUEUE_SIZE = Gauge(
        "gpu_queue_size", "Size of personalization queue", ["status"]
    )
    GPU_PROVISIONING_TIME = Histogram(
        "gpu_provisioning_time_seconds", "Time to provision GPU instances", ["provider", "instance_type"]
    )
    GPU_COST_HOURLY = Gauge(
        "gpu_cost_hourly_dollars", "Hourly cost of GPU instances", ["provider", "instance_type"]
    )
    GPU_UTILIZATION = Gauge(
        "gpu_utilization_percent", "GPU utilization percentage", ["instance_id", "instance_type"]
    )
    GPU_SCALING_EVENTS = Counter(
        "gpu_scaling_events_total", "Total GPU scaling events", ["action", "provider", "instance_type"]
    )
else:
    # Define a more robust placeholder metric class that logs metric operations when Prometheus isn't available
    class LoggingNoOpMetric:
        def __init__(self, name, description, *args, **kwargs):
            self.name = name
            self.description = description
            self.labels_schema = args[0] if args else []
            self.log = get_logger(f"metrics.{name}")
            self.log.debug(f"Created placeholder metric: {name} ({description})")

        def inc(self, value=1, *args, **kwargs):
            labels_str = (
                ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
            )
            self.log.debug(f"Metric {self.name} increment: +{value} {labels_str}")

        def observe(self, value, *args, **kwargs):
            labels_str = (
                ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
            )
            self.log.debug(f"Metric {self.name} observation: {value} {labels_str}")

        def set(self, value, *args, **kwargs):
            labels_str = (
                ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
            )
            self.log.debug(f"Metric {self.name} set: {value} {labels_str}")

        def labels(self, *args, **kwargs):
            return self

    # Create placeholder metrics with appropriate names and descriptions
    LEADS_SCRAPED = LoggingNoOpMetric(
        "leads_scraped_total", "Total number of leads scraped", ["source", "vertical"]
    )
    LEADS_ENRICHED = LoggingNoOpMetric(
        "leads_enriched_total", "Total number of leads enriched", ["tier"]
    )
    LEADS_DEDUPLICATED = LoggingNoOpMetric(
        "leads_deduplicated_total", "Total number of leads deduplicated"
    )
    LEADS_SCORED = LoggingNoOpMetric(
        "leads_scored_total", "Total number of leads scored", ["score_range"]
    )
    EMAILS_SENT = LoggingNoOpMetric(
        "emails_sent_total", "Total number of emails sent", ["template"]
    )
    EMAILS_OPENED = LoggingNoOpMetric(
        "emails_opened_total", "Total number of emails opened", ["template"]
    )
    EMAILS_CLICKED = LoggingNoOpMetric(
        "emails_clicked_total",
        "Total number of emails clicked",
        ["template", "link_type"],
    )
    MOCKUPS_GENERATED = LoggingNoOpMetric(
        "mockups_generated_total", "Total number of mockups generated", ["status"]
    )

    PIPELINE_ERRORS = LoggingNoOpMetric(
        "pipeline_errors_total",
        "Total number of errors in the pipeline",
        ["stage", "error_type"],
    )
    API_FAILURES = LoggingNoOpMetric(
        "api_failures_total",
        "Total number of API failures",
        ["api_name", "endpoint", "status_code"],
    )
    RETRY_ATTEMPTS = LoggingNoOpMetric(
        "retry_attempts_total", "Total number of retry attempts", ["operation"]
    )

    API_LATENCY = LoggingNoOpMetric(
        "api_request_latency_seconds",
        "API request latency in seconds",
        ["api_name", "endpoint", "status"],
    )
    PIPELINE_DURATION = LoggingNoOpMetric(
        "pipeline_stage_duration_seconds",
        "Duration of pipeline stages in seconds",
        ["stage", "status"],
    )
    BATCH_PROCESSING_TIME = LoggingNoOpMetric(
        "batch_processing_time_seconds",
        "Time to process a batch of leads",
        ["batch_size", "operation"],
    )

    COST_COUNTER = LoggingNoOpMetric(
        "api_cost_dollars_total",
        "Total API costs in dollars",
        ["api_name", "operation"],
    )
    COST_PER_LEAD = LoggingNoOpMetric(
        "cost_per_lead_dollars", "Cost per lead in dollars", ["vertical"]
    )
    MEMORY_USAGE = LoggingNoOpMetric("memory_usage_bytes", "Memory usage in bytes")
    CPU_USAGE = LoggingNoOpMetric("cpu_usage_percent", "CPU usage percentage")
    DISK_USAGE = LoggingNoOpMetric("disk_usage_bytes", "Disk usage in bytes")
    NETWORK_IO = LoggingNoOpMetric(
        "network_io_bytes_total", "Network I/O in bytes", ["direction"]
    )

    CONVERSION_RATE = LoggingNoOpMetric(
        "conversion_rate_percent", "Conversion rate percentage", ["vertical"]
    )
    REPLIES_RECEIVED = LoggingNoOpMetric(
        "replies_received_total", "Total number of replies received", ["sentiment"]
    )
    BOUNCE_RATE = LoggingNoOpMetric(
        "bounce_rate_percent", "Email bounce rate percentage", ["template"]
    )
    SPAM_RATE = LoggingNoOpMetric(
        "spam_rate_percent", "Email spam complaint rate percentage", ["template"]
    )
    LEAD_QUALITY_SCORE = LoggingNoOpMetric(
        "lead_quality_score", "Lead quality score", ["vertical", "source"]
    )
    PIPELINE_FAILURE_RATE = LoggingNoOpMetric(
        "pipeline_failure_rate",
        "Failure rate of pipeline operations",
        ["operation", "stage"],
    )

    # Purchase and revenue metrics
    PURCHASES_TOTAL = LoggingNoOpMetric(
        "purchases_total",
        "Total number of successful purchases",
        ["audit_type", "currency"],
    )
    REVENUE_TOTAL = LoggingNoOpMetric(
        "revenue_total_cents", "Total revenue in cents", ["audit_type", "currency"]
    )
    STRIPE_FEES_TOTAL = LoggingNoOpMetric(
        "stripe_fees_total_cents", "Total Stripe fees in cents", ["currency"]
    )
    REFUNDS_TOTAL = LoggingNoOpMetric(
        "refunds_total", "Total number of refunds", ["reason", "currency"]
    )
    REFUND_AMOUNT_TOTAL = LoggingNoOpMetric(
        "refund_amount_total_cents", "Total refund amount in cents", ["currency"]
    )
    AVERAGE_ORDER_VALUE = LoggingNoOpMetric(
        "average_order_value_cents", "Average order value in cents", ["audit_type"]
    )
    CUSTOMER_LIFETIME_VALUE = LoggingNoOpMetric(
        "customer_lifetime_value_cents", "Customer lifetime value in cents"
    )
    MONTHLY_RECURRING_REVENUE = LoggingNoOpMetric(
        "monthly_recurring_revenue_cents", "Monthly recurring revenue in cents"
    )
    DAILY_REVENUE = LoggingNoOpMetric(
        "daily_revenue_cents", "Daily revenue in cents", ["date"]
    )
    CONVERSION_FUNNEL = LoggingNoOpMetric(
        "conversion_funnel_rate", "Conversion funnel metrics", ["stage", "audit_type"]
    )

    # GPU Auto-Scaling metrics
    GPU_INSTANCES_ACTIVE = LoggingNoOpMetric(
        "gpu_instances_active", "Number of active GPU instances", ["provider", "instance_type"]
    )
    GPU_QUEUE_SIZE = LoggingNoOpMetric(
        "gpu_queue_size", "Size of personalization queue", ["status"]
    )
    GPU_PROVISIONING_TIME = LoggingNoOpMetric(
        "gpu_provisioning_time_seconds", "Time to provision GPU instances", ["provider", "instance_type"]
    )
    GPU_COST_HOURLY = LoggingNoOpMetric(
        "gpu_cost_hourly_dollars", "Hourly cost of GPU instances", ["provider", "instance_type"]
    )
    GPU_UTILIZATION = LoggingNoOpMetric(
        "gpu_utilization_percent", "GPU utilization percentage", ["instance_id", "instance_type"]
    )
    GPU_SCALING_EVENTS = LoggingNoOpMetric(
        "gpu_scaling_events_total", "Total GPU scaling events", ["action", "provider", "instance_type"]
    )


def initialize_metrics():
    """
    Initialize metrics tracking.

    This function sets up the metrics collection system. Currently a no-op
    as metrics are initialized when the module is imported, but provided
    for compatibility with existing test code.
    """
    logger.info("Metrics system initialized")
    return True


def start_metrics_server(port: int = 9090) -> bool:
    """
    Start the Prometheus metrics HTTP server.

    Args:
        port: The port to expose metrics on

    Returns:
        bool: True if server started successfully, False otherwise
    """
    if not METRICS_AVAILABLE:
        logger.warning("Prometheus client not available, metrics server not started")
        return False

    try:
        start_http_server(port)
        logger.info(f"Started metrics server on port {port}", extra={"port": port})
        return True
    except Exception as e:
        logger.error(
            f"Failed to start metrics server: {e}",
            extra={"error": str(e), "port": port},
        )
        return False


def push_metrics(gateway: str, job: str, instance: str = None) -> bool:
    """
    Push metrics to a Prometheus Pushgateway.

    Args:
        gateway: The URL of the Pushgateway (e.g., 'localhost:9091')
        job: The job label to use
        instance: The instance label to use (default: hostname)

    Returns:
        bool: True if metrics were pushed successfully, False otherwise
    """
    if not METRICS_AVAILABLE:
        logger.warning("Prometheus client not available, metrics not pushed")
        return False

    try:
        instance = instance or os.uname().nodename
        push_to_gateway(gateway, job, grouping_key={"instance": instance})
        logger.info(
            f"Pushed metrics to gateway {gateway}",
            extra={"gateway": gateway, "job": job, "instance": instance},
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to push metrics to gateway: {e}",
            extra={"error": str(e), "gateway": gateway, "job": job},
        )
        return False


def collect_system_metrics() -> None:
    """
    Collect and update system resource metrics (CPU, memory, disk, network).
    """
    if not METRICS_AVAILABLE or not PSUTIL_AVAILABLE:
        return

    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        CPU_USAGE.set(cpu_percent)

        # Memory usage
        memory = psutil.virtual_memory()
        MEMORY_USAGE.set(memory.used)

        # Disk usage
        disk = psutil.disk_usage("/")
        DISK_USAGE.set(disk.used)

        # Network I/O
        net_io = psutil.net_io_counters()
        NETWORK_IO.labels(direction="sent").inc(net_io.bytes_sent)
        NETWORK_IO.labels(direction="received").inc(net_io.bytes_recv)

        logger.debug(
            "System metrics updated",
            extra={
                "cpu_percent": cpu_percent,
                "memory_used": memory.used,
                "disk_used": disk.used,
                "net_sent": net_io.bytes_sent,
                "net_recv": net_io.bytes_recv,
            },
        )
    except Exception as e:
        logger.error(f"Failed to collect system metrics: {e}", extra={"error": str(e)})


class MetricsTimer:
    """
    Context manager for timing operations and reporting to Prometheus.

    Usage:
        with MetricsTimer(PIPELINE_DURATION, stage='enrichment'):
            # Code to time
    """

    def __init__(self, metric, **labels):
        self.metric = metric
        self.labels = labels
        self.start_time = None
        self.logger = get_logger("metrics.timer")

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is not None:
            # Operation failed
            self.labels["status"] = "error"
            self.logger.warning(
                f"Operation failed after {duration:.2f}s",
                extra={"duration": duration, "error": str(exc_val), **self.labels},
            )
        else:
            # Operation succeeded
            self.labels["status"] = "success"
            self.logger.debug(
                f"Operation completed in {duration:.2f}s",
                extra={"duration": duration, **self.labels},
            )

        try:
            self.metric.labels(**self.labels).observe(duration)
        except Exception as e:
            self.logger.error(f"Failed to record metric: {e}", extra={"error": str(e)})


def record_metric(metric, value=1, **labels):
    """
    Helper function to record a metric with error handling.

    Args:
        metric: The metric to record
        value: The value to record
        **labels: Labels to apply to the metric
    """
    try:
        if hasattr(metric, "labels") and labels:
            if hasattr(metric.labels(**labels), "inc"):
                metric.labels(**labels).inc(value)
            elif hasattr(metric.labels(**labels), "set"):
                metric.labels(**labels).set(value)
            elif hasattr(metric.labels(**labels), "observe"):
                metric.labels(**labels).observe(value)
        elif hasattr(metric, "inc"):
            metric.inc(value)
        elif hasattr(metric, "set"):
            metric.set(value)
        elif hasattr(metric, "observe"):
            metric.observe(value)
    except Exception as e:
        logger = get_logger("metrics.record")
        logger.error(
            f"Failed to record metric: {e}",
            extra={"metric": getattr(metric, "name", str(metric)), "error": str(e)},
        )


def get_queue_metrics(queue_name: str = "personalization") -> Optional[dict]:
    """
    Get metrics for a specific queue.
    
    Args:
        queue_name: Name of the queue to get metrics for
        
    Returns:
        dict: Queue metrics including total, pending, processing tasks, etc.
        None: If unable to get metrics
    """
    logger = get_logger("metrics.queue")
    
    if queue_name == "personalization":
        try:
            # Import here to avoid circular imports
            from leadfactory.storage.factory import get_storage_backend
            
            storage = get_storage_backend()
            
            # Get current queue state from personalization_queue table
            total_query = "SELECT COUNT(*) FROM personalization_queue"
            pending_query = "SELECT COUNT(*) FROM personalization_queue WHERE status = 'pending'"
            processing_query = "SELECT COUNT(*) FROM personalization_queue WHERE status = 'processing'"
            
            # Get average processing time from completed tasks in last hour
            avg_time_query = """
                SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) 
                FROM personalization_queue 
                WHERE status = 'completed' 
                AND completed_at > NOW() - INTERVAL '1 hour'
            """
            
            # Get queue growth rate (tasks added in last 10 minutes)
            growth_query = """
                SELECT COUNT(*) 
                FROM personalization_queue 
                WHERE created_at > NOW() - INTERVAL '10 minutes'
            """
            
            total_tasks = storage.execute_query(total_query)[0][0] if storage.execute_query(total_query) else 0
            pending_tasks = storage.execute_query(pending_query)[0][0] if storage.execute_query(pending_query) else 0
            processing_tasks = storage.execute_query(processing_query)[0][0] if storage.execute_query(processing_query) else 0
            
            avg_time_result = storage.execute_query(avg_time_query)
            avg_processing_time = float(avg_time_result[0][0]) if avg_time_result and avg_time_result[0][0] else 300.0
            
            growth_result = storage.execute_query(growth_query)
            recent_additions = growth_result[0][0] if growth_result else 0
            growth_rate = recent_additions * 6.0  # Extrapolate to per hour
            
            # Calculate estimated completion time
            if processing_tasks > 0 and avg_processing_time > 0:
                eta = (pending_tasks / processing_tasks) * avg_processing_time
            else:
                eta = pending_tasks * avg_processing_time
            
            return {
                "total": total_tasks,
                "pending": pending_tasks,
                "processing": processing_tasks,
                "avg_time": avg_processing_time,
                "eta": eta,
                "growth_rate": growth_rate
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            return None
    
    logger.warning(f"Unknown queue name: {queue_name}")
    return None


def main() -> int:
    """
    Main entry point for the metrics server.

    Returns:
        int: Exit code
    """
    parser = argparse.ArgumentParser(description="LeadFactory Metrics Server")
    parser.add_argument(
        "--port", type=int, default=9090, help="Port to expose metrics on"
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push metrics to gateway instead of starting server",
    )
    parser.add_argument(
        "--gateway", type=str, default="localhost:9091", help="Pushgateway URL"
    )
    parser.add_argument(
        "--job", type=str, default="leadfactory", help="Job name for pushgateway"
    )
    parser.add_argument(
        "--collect-system", action="store_true", help="Collect system metrics"
    )
    parser.add_argument(
        "--interval", type=int, default=15, help="Collection interval in seconds"
    )
    args = parser.parse_args()

    if not METRICS_AVAILABLE:
        logger.error("Metrics not available - install prometheus_client package")
        return 1

    try:
        if args.push:
            # Push mode
            logger.info(f"Starting metrics push mode to {args.gateway}")
            while True:
                if args.collect_system:
                    collect_system_metrics()
                push_metrics(args.gateway, args.job)
                time.sleep(args.interval)
        else:
            # Server mode
            if not start_metrics_server(args.port):
                return 1

            logger.info(f"Metrics server started on port {args.port}")
            logger.info("Press Ctrl+C to exit")

            while True:
                if args.collect_system:
                    collect_system_metrics()
                time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Shutting down metrics server")
    except Exception as e:
        logger.error(f"Error: {e}", extra={"error": str(e)})
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
