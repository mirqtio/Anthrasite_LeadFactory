#!/usr/bin/env python
"""
Metrics Collection and Reporting
------------------------------
This module provides Prometheus metrics collection and reporting for the
Anthrasite LeadFactory platform. It exposes metrics via a Prometheus endpoint
and updates metrics from various components of the system.

Usage:
    # Import and use in other modules
    from bin.metrics import metrics
    metrics.update_bounce_rate(0.02, pool="shared", subuser="prod")

    # Run as standalone Prometheus exporter
    python bin/metrics.py --port 9090
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    push_to_gateway,
    start_http_server,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "metrics.log")),
    ],
)
logger = logging.getLogger("metrics")


class LeadFactoryMetrics:
    """Metrics collection and reporting for LeadFactory."""

    def __init__(self):
        """Initialize metrics."""
        # Email metrics
        self.email_bounce_rate = Gauge(
            "leadfactory_email_bounce_rate", "Email bounce rate", ["pool", "subuser"]
        )
        self.email_spam_rate = Gauge(
            "leadfactory_email_spam_rate", "Email spam rate", ["pool", "subuser"]
        )
        self.email_sent_count = Counter(
            "leadfactory_email_sent_total",
            "Total number of emails sent",
            ["pool", "subuser"],
        )
        self.email_delivered_count = Counter(
            "leadfactory_email_delivered_total",
            "Total number of emails delivered",
            ["pool", "subuser"],
        )
        self.email_opened_count = Counter(
            "leadfactory_email_opened_total",
            "Total number of emails opened",
            ["pool", "subuser"],
        )

        # Cost metrics
        self.cost_per_lead = Gauge(
            "leadfactory_cost_per_lead", "Cost per lead", ["tier"]
        )
        self.total_cost = Counter("leadfactory_total_cost", "Total cost", ["service"])
        self.gpu_cost_daily = Gauge("leadfactory_gpu_cost_daily", "Daily GPU cost")

        # Batch metrics
        self.batch_completed_timestamp = Gauge(
            "leadfactory_batch_completed_timestamp",
            "Timestamp when the batch completed",
        )
        self.batch_lead_count = Counter(
            "leadfactory_batch_lead_count",
            "Number of leads processed in batches",
            ["status"],
        )
        self.batch_duration = Histogram(
            "leadfactory_batch_duration_seconds",
            "Duration of batch processing",
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800],
        )

        # API metrics
        self.api_request_duration = Summary(
            "leadfactory_api_request_duration_seconds",
            "Duration of API requests",
            ["endpoint", "method"],
        )
        self.api_request_count = Counter(
            "leadfactory_api_request_total",
            "Total number of API requests",
            ["endpoint", "method", "status"],
        )

        # Supabase metrics
        self.supabase_storage_mb = Gauge(
            "supabase_storage_mb", "Supabase storage usage in MB"
        )
        self.supabase_row_count = Gauge(
            "supabase_row_count", "Supabase row count", ["table"]
        )

        # Budget gate metrics
        self.budget_gate_status = Gauge(
            "leadfactory_budget_gate_status",
            "Budget gate status (1=active, 0=inactive)",
        )
        self.budget_gate_skipped_operations = Counter(
            "leadfactory_budget_gate_skipped_operations_total",
            "Total number of operations skipped due to budget gate",
            ["operation"],
        )

        # System metrics
        self.system_memory_usage_mb = Gauge(
            "leadfactory_system_memory_usage_mb", "System memory usage in MB"
        )
        self.system_cpu_usage_percent = Gauge(
            "leadfactory_system_cpu_usage_percent", "System CPU usage in percent"
        )
        self.system_disk_usage_percent = Gauge(
            "leadfactory_system_disk_usage_percent",
            "System disk usage in percent",
            ["mount_point"],
        )

        logger.info("Metrics initialized")

    def update_bounce_rate(self, rate, pool="shared", subuser="prod"):
        """Update email bounce rate metric."""
        self.email_bounce_rate.labels(pool=pool, subuser=subuser).set(rate)
        logger.info(f"Updated bounce rate: {rate} (pool={pool}, subuser={subuser})")

    def update_spam_rate(self, rate, pool="shared", subuser="prod"):
        """Update email spam rate metric."""
        self.email_spam_rate.labels(pool=pool, subuser=subuser).set(rate)
        logger.info(f"Updated spam rate: {rate} (pool={pool}, subuser={subuser})")

    def increment_email_sent(self, count=1, pool="shared", subuser="prod"):
        """Increment email sent counter."""
        self.email_sent_count.labels(pool=pool, subuser=subuser).inc(count)
        logger.info(
            f"Incremented sent count by {count} (pool={pool}, subuser={subuser})"
        )

    def increment_email_delivered(self, count=1, pool="shared", subuser="prod"):
        """Increment email delivered counter."""
        self.email_delivered_count.labels(pool=pool, subuser=subuser).inc(count)
        logger.info(
            f"Incremented delivered count by {count} (pool={pool}, subuser={subuser})"
        )

    def increment_email_opened(self, count=1, pool="shared", subuser="prod"):
        """Increment email opened counter."""
        self.email_opened_count.labels(pool=pool, subuser=subuser).inc(count)
        logger.info(
            f"Incremented opened count by {count} (pool={pool}, subuser={subuser})"
        )

    def update_cost_per_lead(self, cost, tier="1"):
        """Update cost per lead metric."""
        self.cost_per_lead.labels(tier=tier).set(cost)
        logger.info(f"Updated cost per lead: ${cost:.2f} (tier={tier})")

    def add_cost(self, amount, service="api"):
        """Add to total cost counter."""
        self.total_cost.labels(service=service).inc(amount)
        logger.info(f"Added ${amount:.2f} to total cost (service={service})")

    def update_gpu_cost_daily(self, cost):
        """Update daily GPU cost metric."""
        self.gpu_cost_daily.set(cost)
        logger.info(f"Updated daily GPU cost: ${cost:.2f}")

    def update_batch_completed(self):
        """Update batch completed timestamp to current time."""
        timestamp = time.time()
        self.batch_completed_timestamp.set(timestamp)
        logger.info(
            f"Updated batch completed timestamp: {datetime.fromtimestamp(timestamp)}"
        )

    def increment_batch_leads(self, count=1, status="processed"):
        """Increment batch lead counter."""
        self.batch_lead_count.labels(status=status).inc(count)
        logger.info(f"Incremented batch lead count by {count} (status={status})")

    def observe_batch_duration(self, duration_seconds):
        """Observe batch processing duration."""
        self.batch_duration.observe(duration_seconds)
        logger.info(f"Observed batch duration: {duration_seconds:.2f} seconds")

    def observe_api_request(
        self, duration_seconds, endpoint, method="GET", status="success"
    ):
        """Observe API request duration and increment counter."""
        self.api_request_duration.labels(endpoint=endpoint, method=method).observe(
            duration_seconds
        )
        self.api_request_count.labels(
            endpoint=endpoint, method=method, status=status
        ).inc()
        logger.debug(
            f"Observed API request: {endpoint} {method} {status} {duration_seconds:.2f}s"
        )

    def update_supabase_storage(self, size_mb):
        """Update Supabase storage usage metric."""
        self.supabase_storage_mb.set(size_mb)
        logger.info(f"Updated Supabase storage usage: {size_mb} MB")

    def update_supabase_row_count(self, table, count):
        """Update Supabase row count metric."""
        self.supabase_row_count.labels(table=table).set(count)
        logger.info(f"Updated Supabase row count: {count} (table={table})")

    def update_budget_gate_status(self, active=False):
        """Update budget gate status metric."""
        status = 1 if active else 0
        self.budget_gate_status.set(status)
        logger.info(f"Updated budget gate status: {'active' if active else 'inactive'}")

    def increment_budget_gate_skipped(self, operation):
        """Increment budget gate skipped operations counter."""
        self.budget_gate_skipped_operations.labels(operation=operation).inc()
        logger.info(
            f"Incremented budget gate skipped operations (operation={operation})"
        )

    def update_system_metrics(self):
        """Update system metrics."""
        try:
            # Memory usage
            with open("/proc/meminfo", "r") as f:
                mem_info = {}
                for line in f:
                    key, value = line.split(":", 1)
                    mem_info[key.strip()] = int(value.strip().split()[0])

            total_memory = mem_info.get("MemTotal", 0)
            free_memory = mem_info.get("MemFree", 0)
            buffers = mem_info.get("Buffers", 0)
            cached = mem_info.get("Cached", 0)

            used_memory = total_memory - free_memory - buffers - cached
            used_memory_mb = used_memory / 1024

            self.system_memory_usage_mb.set(used_memory_mb)

            # CPU usage
            with open("/proc/stat", "r") as f:
                cpu_line = f.readline()

            cpu_parts = cpu_line.split()
            user = int(cpu_parts[1])
            nice = int(cpu_parts[2])
            system = int(cpu_parts[3])
            idle = int(cpu_parts[4])

            total = user + nice + system + idle
            usage = (total - idle) / total * 100

            self.system_cpu_usage_percent.set(usage)

            # Disk usage
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = parts[0]
                        mount_point = parts[1]

                        if device.startswith("/dev/"):
                            try:
                                stat = os.statvfs(mount_point)
                                total = stat.f_blocks * stat.f_frsize
                                free = stat.f_bfree * stat.f_frsize
                                used = total - free
                                usage_percent = used / total * 100

                                self.system_disk_usage_percent.labels(
                                    mount_point=mount_point
                                ).set(usage_percent)
                            except Exception as e:
                                logger.error(
                                    f"Error getting disk usage for {mount_point}: {e}"
                                )

            logger.info("Updated system metrics")
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def push_to_gateway(self, gateway, job):
        """Push metrics to a Prometheus Pushgateway."""
        try:
            registry = CollectorRegistry()

            # Add metrics to registry
            registry.register(self.email_bounce_rate)
            registry.register(self.email_spam_rate)
            registry.register(self.email_sent_count)
            registry.register(self.email_delivered_count)
            registry.register(self.email_opened_count)
            registry.register(self.cost_per_lead)
            registry.register(self.total_cost)
            registry.register(self.gpu_cost_daily)
            registry.register(self.batch_completed_timestamp)
            registry.register(self.batch_lead_count)
            registry.register(self.batch_duration)
            registry.register(self.api_request_duration)
            registry.register(self.api_request_count)
            registry.register(self.supabase_storage_mb)
            registry.register(self.supabase_row_count)
            registry.register(self.budget_gate_status)
            registry.register(self.budget_gate_skipped_operations)
            registry.register(self.system_memory_usage_mb)
            registry.register(self.system_cpu_usage_percent)
            registry.register(self.system_disk_usage_percent)

            # Push to gateway
            push_to_gateway(gateway, job=job, registry=registry)
            logger.info(f"Pushed metrics to gateway: {gateway} (job={job})")
        except Exception as e:
            logger.error(f"Error pushing metrics to gateway: {e}")

    def start_metrics_server(self, port=9090):
        """Start a Prometheus metrics server."""
        try:
            start_http_server(port)
            logger.info(f"Metrics server started on port {port}")

            # Start system metrics update thread
            def update_system_metrics_periodically():
                while True:
                    try:
                        self.update_system_metrics()
                    except Exception as e:
                        logger.error(f"Error in system metrics update thread: {e}")
                    time.sleep(15)

            thread = threading.Thread(
                target=update_system_metrics_periodically, daemon=True
            )
            thread.start()

            return True
        except Exception as e:
            logger.error(f"Error starting metrics server: {e}")
            return False


# Create a singleton instance
metrics = LeadFactoryMetrics()


def main():
    """Main entry point when run as a script."""
    parser = argparse.ArgumentParser(description="LeadFactory Metrics Server")
    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port to expose metrics on (default: 9090)",
    )
    args = parser.parse_args()

    try:
        # Start metrics server
        if metrics.start_metrics_server(args.port):
            logger.info(f"Metrics server running on port {args.port}")

            # Keep the server running
            while True:
                time.sleep(1)
        else:
            logger.error("Failed to start metrics server")
            return 1

    except KeyboardInterrupt:
        logger.info("Metrics server stopped")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
