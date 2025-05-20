# Scaling Gate Guide

The Scaling Gate is a critical component of the Anthrasite Lead-Factory that helps control costs by automatically or manually restricting non-essential operations when budget thresholds are approached or exceeded.

## Overview

The Scaling Gate works by monitoring budget utilization and can be configured to automatically activate when certain thresholds are reached. When active, the gate will block non-essential operations while allowing critical functions to continue.

## Configuration

### Environment Variables

The following environment variables control the scaling gate behavior:

```bash
# Enable/disable the scaling gate feature
SCALING_GATE_ENABLED=true

# Budget thresholds (in USD)
DAILY_BUDGET=50.0
MONTHLY_BUDGET=1000.0

# Threshold percentages for warnings and auto-activation
BUDGET_WARNING_THRESHOLD=75.0  # Percentage of budget that triggers a warning
BUDGET_CRITICAL_THRESHOLD=90.0 # Percentage of budget that triggers auto-activation

# Critical operation whitelist (comma-separated list of operation names)
CRITICAL_OPERATIONS=health_check,metrics,scaling_gate_status
```

### Configuration File

You can also configure the scaling gate using a YAML configuration file at `config/scaling_gate.yml`:

```yaml
enabled: true
budgets:
  daily: 50.0
  monthly: 1000.0
thresholds:
  warning: 75.0  # Percentage
  critical: 90.0  # Percentage
critical_operations:
  - health_check
  - metrics
  - scaling_gate_status
  - billing_status
  - admin_*
```

## Usage

### Checking Status

You can check the current status of the scaling gate using the budget audit tool:

```bash
./bin/budget_audit.py gate status
```

### Manual Control

#### Enable the Scaling Gate

```bash
./bin/budget_audit.py gate enable --reason "Monthly budget threshold reached"
```

#### Disable the Scaling Gate

```bash
./bin/budget_audit.py gate disable --reason "New budget cycle started"
```

### Programmatic API

You can also interact with the scaling gate programmatically:

```python
from utils.cost_tracker import (
    is_scaling_gate_active,
    set_scaling_gate,
    should_allow_operation,
    get_scaling_gate_history
)

# Check if the gate is active
is_active, reason = is_scaling_gate_active()

# Enable the gate
set_scaling_gate(True, reason="Manual activation")

# Disable the gate
set_scaling_gate(False, reason="Manual deactivation")


# Check if an operation is allowed
operation_allowed = should_allow_operation("send_email")

# Get gate history
history = get_scaling_gate_history(limit=10)
```

## Critical Operations

Critical operations are always allowed, even when the scaling gate is active. These should be limited to essential system functions.

### Default Critical Operations

- `health_check`: System health monitoring
- `metrics`: Metrics collection and export
- `scaling_gate_status`: Checking the status of the scaling gate
- `billing_status`: Billing and cost-related operations
- `admin_*`: All admin operations (wildcard)

### Adding Custom Critical Operations

Add operation names to the `CRITICAL_OPERATIONS` environment variable or the configuration file.

## Automatic Activation

The scaling gate will automatically activate when:
1. The daily cost exceeds the critical threshold
2. The monthly cost exceeds the critical threshold

## Best Practices

1. **Monitor Alerts**: Set up alerts for budget warnings (75% by default)
2. **Review Critical Operations**: Regularly review and update the list of critical operations
3. **Test Manually**: Test the scaling gate in a staging environment
4. **Document Procedures**: Document procedures for handling budget overruns
5. **Regular Reviews**: Review scaling gate activations to adjust budgets or thresholds

## Troubleshooting

### Common Issues

1. **Gate Not Activating**
   - Verify `SCALING_GATE_ENABLED` is set to `true`
   - Check that budget thresholds are properly configured
   - Verify the cost tracking database is being updated

2. **Critical Operations Being Blocked**
   - Ensure the operation is in the `CRITICAL_OPERATIONS` list
   - Check for typos in operation names
   - Verify the operation is properly registered in the code

3. **Performance Issues**
   - The scaling gate adds minimal overhead, but frequent status checks can impact performance
   - Consider caching the gate status for non-critical operations

## Monitoring

Monitor the scaling gate using the following metrics:

- `scaling_gate_active`: 1 if active, 0 if not
- `scaling_gate_activations_total`: Total number of activations
- `scaling_gate_operation_blocks_total`: Count of blocked operations

## Integration

### Prometheus

The scaling gate exposes metrics in Prometheus format at `/metrics` when using the budget audit tool's web interface.

### Logging

All scaling gate state changes are logged with the `scaling_gate` logger at the INFO level.
