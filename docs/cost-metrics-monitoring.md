# Cost Metrics Monitoring

## Overview
The Cost Metrics Monitoring system tracks and reports on cost-related metrics in the Anthrasite LeadFactory, including cost-per-lead and GPU usage costs. It provides metrics, alerts, and monitoring capabilities to ensure that costs remain within acceptable thresholds.

## Features
- Calculates cost-per-lead at the end of each batch run
- Tracks GPU usage costs when the GPU_BURST flag is enabled
- Monitors costs against configurable thresholds
- Sends alert emails when costs exceed thresholds
- Provides detailed cost metrics for reporting and analysis
- Integrates with Prometheus for metrics and Grafana for dashboards

## Implementation Details

### Cost Metrics
The `utils/cost_metrics.py` module provides core functionality for tracking cost metrics:

- `calculate_cost_per_lead()`: Calculates the cost per lead based on total monthly cost and lead count
- `track_gpu_usage(cost_dollars)`: Tracks GPU usage when the GPU_BURST flag is set
- `check_cost_per_lead_threshold(threshold)`: Checks if cost per lead exceeds a threshold
- `check_gpu_cost_threshold(daily_threshold, monthly_threshold)`: Checks if GPU costs exceed thresholds
- `update_cost_metrics_at_batch_end()`: Updates all cost metrics at the end of a batch run

### GPU Usage Tracker
The `bin/track_gpu_usage.py` script provides a monitoring service that:

- Periodically checks if the GPU_BURST flag is set
- Tracks GPU usage costs when the flag is enabled
- Sends alert emails when GPU costs exceed thresholds
- Can be run as a standalone script or as a systemd service

### Integration with Nightly Batch Process
The `bin/run_nightly.sh` script has been updated to:

- Calculate and record cost-per-lead at the end of each batch run
- Update all cost metrics for reporting and analysis

### Systemd Service
The `etc/gpu-usage-tracker.service` file provides a systemd service definition for running the GPU usage tracker as a background service.

## Configuration

### Environment Variables
- `COST_TRACKER_FILE`: Path to the JSON file for storing cost tracking data (default: `data/cost_tracker.json`)
- `DATABASE_URL`: URL for the database connection (default: `leadfactory.db`)
- `MONTHLY_BUDGET`: Monthly budget in dollars (default: `250`)
- `GPU_BURST`: Flag to enable GPU burst mode (`0` or `1`, default: `0`)
- `GPU_BURST_COST_DOLLARS`: Cost per hour of GPU usage in dollars (default: `0.50`)
- `GPU_COST_DAILY_THRESHOLD`: Daily GPU cost threshold in dollars (default: `25.0`)
- `GPU_COST_MONTHLY_THRESHOLD`: Monthly GPU cost threshold in dollars (default: `100.0`)
- `GPU_USAGE_CHECK_INTERVAL_SECONDS`: Interval for checking GPU usage in seconds (default: `3600` for 1 hour)
- `ALERT_EMAIL_TO`: Email address to send alerts to (default: `alerts@anthrasite.io`)

## Installation

### Systemd Service Installation
To install the GPU usage tracker as a systemd service:

```bash
sudo ./bin/install_gpu_tracker_service.sh
```

This will:
1. Copy the service file to `/etc/systemd/system/`
2. Enable the service to start on boot
3. Start the service immediately

### Manual Execution
To run the GPU usage tracker manually:

```bash
./bin/track_gpu_usage.py
```

To run a single check:

```bash
./bin/track_gpu_usage.py --once
```

## Testing
BDD tests for the cost metrics monitoring system are available in:
- `tests/features/cost_metrics.feature`: BDD feature file
- `tests/test_cost_metrics.py`: BDD test implementation

Run the tests with:

```bash
pytest tests/test_cost_metrics.py -v
```

## Metrics and Dashboards
The cost metrics monitoring system exposes the following Prometheus metrics:

- `anthrasite_batch_cost_per_lead`: Gauge showing cost per lead in dollars
- `anthrasite_batch_gpu_cost_dollars`: Counter showing cumulative GPU cost in dollars

These metrics can be visualized in Grafana dashboards for monitoring costs and resource utilization.

## Alerts
The system provides the following alerts:

- **High Cost Per Lead**: Triggered when the cost per lead exceeds $3.00
- **High GPU Cost**: Triggered when the daily GPU cost exceeds $25.00 or the monthly GPU cost exceeds $100.00

## Troubleshooting

### Common Issues

#### Cost Calculation Issues
If cost calculations seem incorrect:

1. Check the cost tracker file:
   ```bash
   cat data/cost_tracker.json
   ```

2. Verify the lead count in the database:
   ```bash
   sqlite3 leadfactory.db "SELECT COUNT(*) FROM businesses"
   ```

3. Check the monthly cost data:
   ```bash
   python -c "from utils.cost_metrics import get_total_monthly_cost; print(get_total_monthly_cost())"
   ```

#### GPU Usage Tracking Issues
If GPU usage tracking is not working:

1. Check if the GPU_BURST flag is set:
   ```bash
   echo $GPU_BURST
   ```

2. Verify the GPU usage tracker service is running:
   ```bash
   sudo systemctl status gpu-usage-tracker
   ```

3. Check the service logs:
   ```bash
   sudo journalctl -u gpu-usage-tracker
   ```

4. Run the tracker manually to see any errors:
   ```bash
   ./bin/track_gpu_usage.py --once
   ```

## Integration with Other Systems

### Batch Completion Monitoring
The cost metrics system integrates with the batch completion monitoring system to provide a complete picture of batch processing performance and costs. At the end of each batch run, both systems update their respective metrics to provide a comprehensive view of the system's operation.

### Prometheus and Grafana
The cost metrics are exposed to Prometheus for collection and can be visualized in Grafana dashboards. The included dashboard configuration provides panels for cost-per-lead and GPU costs, along with alerts for when thresholds are exceeded.
