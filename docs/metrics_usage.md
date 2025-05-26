# Metrics Usage Guide

This document explains how to use the metrics system to track application performance, resource usage, and business metrics in the Anthrasite LeadFactory project.

## Basic Usage

The metrics system is built on top of Prometheus and provides a standardized way to record various types of metrics throughout the application.

### Import the Metrics Module

```python
from leadfactory.utils.metrics import (
    LEADS_SCRAPED, LEADS_ENRICHED, API_LATENCY, PIPELINE_DURATION,
    COST_COUNTER, MetricsTimer, record_metric
)
```

### Recording Counter Metrics

Use counters to track occurrences of events:

```python
# Basic counter increment
LEADS_SCRAPED.inc()

# With labels
LEADS_SCRAPED.labels(source="yelp", vertical="plumbing").inc()

# With specific value
EMAILS_SENT.labels(template="welcome").inc(5)  # Increment by 5

# Using the helper function for more robust error handling
record_metric(LEADS_SCRAPED, value=1, source="yelp", vertical="plumbing")
```

### Recording Gauge Metrics

Use gauges to track values that can go up and down:

```python
# Set CPU usage to current value
CPU_USAGE.set(75.5)  # 75.5%

# Cost per lead metric with label
COST_PER_LEAD.labels(vertical="electricians").set(3.25)  # $3.25 per lead

# Using the helper function
record_metric(CPU_USAGE, value=75.5)
```

### Timing Operations

Use the `MetricsTimer` context manager to time operations and automatically record their duration:

```python
# Time a function execution
with MetricsTimer(PIPELINE_DURATION, stage="enrichment"):
    # Code to be timed
    enrich_business_data(business_id)

# The timer automatically adds status='success' or status='error'
# based on whether an exception occurred
```

### Manual Timing

For more control over timing:

```python
import time

start_time = time.time()
try:
    # Operation to time
    result = api_client.get_business_details(business_id)
    duration = time.time() - start_time

    # Record successful operation
    API_LATENCY.labels(
        api_name="yelp",
        endpoint="business_details",
        status="success"
    ).observe(duration)

except Exception as e:
    duration = time.time() - start_time

    # Record failed operation
    API_LATENCY.labels(
        api_name="yelp",
        endpoint="business_details",
        status="error"
    ).observe(duration)

    # Also increment the failure counter
    API_FAILURES.labels(
        api_name="yelp",
        endpoint="business_details",
        status_code=getattr(e, "status_code", 500)
    ).inc()
```

## System Metrics Collection

For automated system metrics collection:

```python
from leadfactory.utils.metrics import collect_system_metrics

# Call this periodically to update CPU, memory, disk, and network metrics
collect_system_metrics()
```

## Running the Metrics Server

Start a metrics server to expose metrics to Prometheus:

```bash
# Start the metrics server on default port 9090
python -m leadfactory.utils.metrics

# Specify a custom port
python -m leadfactory.utils.metrics --port 8080

# Collect system metrics automatically
python -m leadfactory.utils.metrics --collect-system

# Use push mode instead of pull mode
python -m leadfactory.utils.metrics --push --gateway localhost:9091 --job leadfactory
```

## Available Metrics

The following metrics are available:

### Pipeline Metrics
- `leads_scraped_total` - Total number of leads scraped
- `leads_enriched_total` - Total number of leads enriched
- `leads_deduplicated_total` - Total number of leads deduplicated
- `leads_scored_total` - Total number of leads scored
- `emails_sent_total` - Total number of emails sent
- `emails_opened_total` - Total number of emails opened
- `emails_clicked_total` - Total number of emails clicked
- `mockups_generated_total` - Total number of mockups generated

### Error Metrics
- `pipeline_errors_total` - Total number of errors in the pipeline
- `api_failures_total` - Total number of API failures
- `retry_attempts_total` - Total number of retry attempts

### Performance Metrics
- `api_request_latency_seconds` - API request latency in seconds
- `pipeline_stage_duration_seconds` - Duration of pipeline stages in seconds
- `batch_processing_time_seconds` - Time to process a batch of leads

### Resource Metrics
- `api_cost_dollars_total` - Total API costs in dollars
- `cost_per_lead_dollars` - Cost per lead in dollars
- `memory_usage_bytes` - Memory usage in bytes
- `cpu_usage_percent` - CPU usage percentage
- `disk_usage_bytes` - Disk usage in bytes
- `network_io_bytes_total` - Network I/O in bytes

### Business Metrics
- `conversion_rate_percent` - Conversion rate percentage
- `replies_received_total` - Total number of replies received
- `bounce_rate_percent` - Email bounce rate percentage
- `spam_rate_percent` - Email spam complaint rate percentage
- `lead_quality_score` - Lead quality score

## Integration with Prometheus and Grafana

### Prometheus Configuration

Example Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'leadfactory'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
```

### Grafana Dashboard

A sample Grafana dashboard is available at `monitoring/grafana-dashboards/leadfactory.json`.
