# Batch Completion Monitoring

## Overview
The Batch Completion Monitoring system tracks the progress and completion status of nightly batch processes in the Anthrasite LeadFactory. It provides metrics, alerts, and monitoring capabilities to ensure that batches complete successfully and on time.

## Features
- Records batch start and end timestamps
- Tracks completion percentage for each pipeline stage
- Monitors batch completion against configurable deadlines
- Sends alert emails when batches don't complete on time
- Provides detailed status information for troubleshooting
- Integrates with Prometheus for metrics and Grafana for dashboards

## Implementation Details

### Batch Tracker
The `utils/batch_tracker.py` module provides core functionality for tracking batch status:

- `record_batch_start()`: Records the start of a new batch
- `record_batch_stage_completion(stage, percentage)`: Records completion of a pipeline stage
- `record_batch_end()`: Records the successful completion of a batch
- `check_batch_completion()`: Checks if the current batch completed on time
- `get_batch_status()`: Returns detailed status information about the current batch

### Batch Completion Monitor
The `bin/batch_completion_monitor.py` script provides a monitoring service that:

- Periodically checks batch completion status
- Sends alert emails when batches don't complete on time
- Can be run as a standalone script or as a systemd service

### Integration with Nightly Batch Process
The `bin/run_nightly.sh` script has been updated to:

- Record batch start at the beginning of the process
- Record stage completion after each pipeline stage
- Record batch end upon successful completion of all stages

### Systemd Service
The `etc/batch-completion-monitor.service` file provides a systemd service definition for running the monitor as a background service.

## Configuration

### Environment Variables
- `BATCH_TRACKER_FILE`: Path to the JSON file for storing batch tracking data (default: `data/batch_tracker.json`)
- `BATCH_COMPLETION_DEADLINE_HOUR`: Hour of the day (0-23) when batches must be completed (default: `5` for 5:00 AM)
- `BATCH_COMPLETION_TIMEZONE`: Timezone for the deadline (default: `America/New_York`)
- `BATCH_COMPLETION_CHECK_INTERVAL_SECONDS`: Interval for checking batch completion status (default: `300` for 5 minutes)
- `ALERT_EMAIL_TO`: Email address to send alerts to (default: `alerts@anthrasite.com`)
- `ALERT_EMAIL_FROM`: Email address to send alerts from (default: `leadfactory@anthrasite.com`)
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`: SMTP configuration for sending alert emails

## Installation

### Systemd Service Installation
To install the batch completion monitor as a systemd service:

```bash
sudo ./bin/install_batch_monitor_service.sh
```

This will:
1. Copy the service file to `/etc/systemd/system/`
2. Enable the service to start on boot
3. Start the service immediately

### Manual Execution
To run the batch completion monitor manually:

```bash
./bin/batch_completion_monitor.py
```

To run a single check:

```bash
./bin/batch_completion_monitor.py --once
```

## Testing
BDD tests for the batch completion monitoring system are available in:
- `tests/features/batch_completion.feature`: BDD feature file
- `tests/test_batch_completion.py`: BDD test implementation

Run the tests with:

```bash
pytest tests/test_batch_completion.py -v
```

## Metrics and Dashboards
The batch completion monitoring system exposes the following Prometheus metrics:

- `anthrasite_batch_completion_percentage`: Gauge showing overall batch completion percentage
- `anthrasite_batch_stage_completion_percentage`: Gauge showing completion percentage for each stage
- `anthrasite_batch_completion_time_seconds`: Histogram of batch completion times
- `anthrasite_batch_completion_success`: Gauge showing if the last batch completed successfully (1) or not (0)

These metrics can be visualized in Grafana dashboards for monitoring batch processing performance and health.

## Troubleshooting

### Common Issues

#### Batch Completion Alerts
If you receive a batch completion alert:

1. Check the batch status with:
   ```bash
   python -c "from utils.batch_tracker import get_batch_status; print(get_batch_status())"
   ```

2. Check the logs for the nightly batch process:
   ```bash
   cat logs/nightly_*.log | grep ERROR
   ```

3. Restart a failed batch if necessary:
   ```bash
   ./bin/run_nightly.sh
   ```

#### Service Issues
If the monitoring service is not running:

1. Check the service status:
   ```bash
   sudo systemctl status batch-completion-monitor
   ```

2. View the service logs:
   ```bash
   sudo journalctl -u batch-completion-monitor
   ```

3. Restart the service if needed:
   ```bash
   sudo systemctl restart batch-completion-monitor
   ```
