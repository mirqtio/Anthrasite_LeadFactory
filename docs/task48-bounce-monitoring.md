# Task 48: Auto-Monitor Bounce Rate & IP Warmup

## Implementation Summary

Task 48 has been successfully implemented to provide automated monitoring of bounce rates with integration to the IP warmup and rotation systems.

## What Was Implemented

### 1. Automated Bounce Rate Monitor (`leadfactory/monitoring/bounce_rate_monitor.py`)
- **AutomatedBounceMonitor** class that continuously monitors bounce rates
- Configurable check intervals (default: 5 minutes)
- Threshold-based actions:
  - **Warning (5%)**: Alerts only
  - **Critical (10%)**: Deprioritizes IPs, slows warmup
  - **Block (15%)**: Pauses warmup or removes from rotation
- Alert history tracking to avoid duplicate alerts
- Webhook integration for external alerting

### 2. CLI Commands (`leadfactory/cli/commands/monitoring_commands.py`)
- `monitoring start-bounce-monitor`: Start automated monitoring
- `monitoring stop-bounce-monitor`: Stop monitoring
- `monitoring bounce-monitor-status`: Check current status
- `monitoring check-bounce-rate`: Check specific IP/subuser
- `monitoring warmup-status`: View warmup progress
- `monitoring monitoring-report`: Generate comprehensive report

### 3. Integration Features
- **Warmup Integration**: Automatically pauses warmup if bounce rate exceeds thresholds
- **Rotation Integration**: Removes problematic IPs from rotation pools
- **Alert System**: Multi-level alerts (info, warning, critical) via logging and webhooks
- **Insufficient Sample Protection**: Ignores IPs with < 10 emails sent

## Configuration

### Environment Variables
```bash
# Webhook for alerts (optional)
export BOUNCE_ALERT_WEBHOOK_URL="https://your-webhook.com/alerts"

# Thresholds (defaults shown)
export BOUNCE_WARNING_THRESHOLD=0.05  # 5%
export BOUNCE_CRITICAL_THRESHOLD=0.10 # 10%
export BOUNCE_BLOCK_THRESHOLD=0.15    # 15%
```

### Running as a Service

#### Systemd Service
```bash
# Copy service file
sudo cp etc/bounce-monitor.service /etc/systemd/system/

# Enable and start
sudo systemctl enable bounce-monitor
sudo systemctl start bounce-monitor

# Check status
sudo systemctl status bounce-monitor
```

#### Cron Job
```bash
# Add to crontab
*/5 * * * * /opt/leadfactory/scripts/run_bounce_monitor.sh
```

### CLI Usage

#### Start Monitoring
```bash
# Start with default settings
leadfactory monitoring start-bounce-monitor

# Custom interval and webhook
leadfactory monitoring start-bounce-monitor \
    --interval 600 \
    --webhook-url https://slack.com/webhook

# Run as daemon
leadfactory monitoring start-bounce-monitor --daemon
```

#### Check Status
```bash
# Monitor status
leadfactory monitoring bounce-monitor-status

# Check specific IP
leadfactory monitoring check-bounce-rate \
    --ip 192.168.1.1 \
    --subuser primary

# Warmup status
leadfactory monitoring warmup-status --days 7

# Full report
leadfactory monitoring monitoring-report --format json
```

## How It Works

### Monitoring Flow
1. Every 5 minutes (configurable), the monitor:
   - Gets all active IPs from warmup and rotation pools
   - Retrieves bounce statistics for each IP/subuser
   - Checks against configured thresholds
   - Takes appropriate action based on severity

### Actions by Threshold

#### Warning Threshold (5%)
- Logs warning message
- Sends alert (first occurrence or significant increase)
- No automated action

#### Critical Threshold (10%)
- For warmup IPs: Prevents stage advancement
- For production IPs: Deprioritizes in rotation pool
- Sends warning-level alert

#### Block Threshold (15%)
- For warmup IPs: Immediately pauses warmup
- For production IPs: Marks as failed and removes from rotation
- Sends critical-level alert

### Alert Management
- Deduplication: Only alerts on first occurrence or significant changes
- History tracking: Maintains alert history for reporting
- Auto-clear: Removes alerts when IP recovers to healthy levels

## Testing

### Unit Tests (`tests/unit/monitoring/test_bounce_rate_monitor.py`)
- ✅ Service lifecycle (start/stop)
- ✅ Threshold detection and handling
- ✅ Warmup vs production IP handling
- ✅ Alert generation and deduplication
- ✅ Error handling and recovery

### Integration Tests (`tests/integration/test_bounce_monitoring_integration.py`)
- ✅ Full integration with bounce monitor, warmup, and rotation
- ✅ Real database operations
- ✅ Alert history tracking
- ✅ CLI command testing

### BDD Tests (`tests/bdd/features/bounce_monitoring.feature`)
- ✅ High bounce rate scenarios
- ✅ IP status transitions
- ✅ Alert clearing for recovered IPs
- ✅ Insufficient sample handling

## Monitoring Examples

### Example Alert
```json
{
  "severity": "critical",
  "title": "IP Blocked - High Bounce Rate",
  "message": "IP 192.168.1.1 (subuser: primary) removed from rotation due to 18.00% bounce rate",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "service": "bounce_rate_monitor"
}
```

### Example Status Report
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "bounce_monitoring": {
    "running": true,
    "check_interval_seconds": 300,
    "active_alerts": 2,
    "alert_history": [
      {
        "ip_subuser": "192.168.1.1:primary",
        "bounce_rate": 0.12,
        "timestamp": "2024-01-15T10:25:00.000Z"
      }
    ]
  },
  "warmup_status": {
    "active_warmups": 3,
    "ips": [...]
  },
  "rotation_pools": {
    "total_pools": 2,
    "active_ips": 8
  }
}
```

## Benefits

1. **Proactive Protection**: Catches issues before they damage sender reputation
2. **Automated Response**: No manual intervention needed for problematic IPs
3. **Integrated System**: Works seamlessly with warmup and rotation
4. **Flexible Alerting**: Multiple notification channels
5. **Historical Tracking**: Maintains history for analysis
6. **Safe Defaults**: Protects against false positives with sample size requirements

## Next Steps

- Add predictive analytics to anticipate bounce rate increases
- Implement bounce pattern analysis (time of day, recipient domains)
- Create dashboard for visual monitoring
- Add automatic recovery procedures for paused IPs
- Integrate with email service provider webhooks for real-time updates
