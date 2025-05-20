# Budget Audit Tool Guide

The Budget Audit Tool is a command-line utility for monitoring and managing the budget and scaling gate status of the Anthrasite Lead-Factory system. It provides insights into cost tracking, budget utilization, and scaling gate status.

## Features

- View current budget status and spending
- Analyze costs by service and operation
- Manage the scaling gate (enable/disable/status)
- Export cost reports in various formats
- Export Prometheus metrics

## Installation

No installation is required. The script is located at `bin/budget_audit.py` and can be run directly.

## Usage

### Show Budget Summary

```bash
./bin/budget_audit.py summary
```

### Show Cost Breakdown

View daily costs by service and operation:

```bash
./bin/budget_audit.py costs
```

View monthly costs:

```bash
./bin/budget_audit.py costs --period month
```

### Manage Scaling Gate

Show current status:

```bash
./bin/budget_audit.py gate status
```

Enable the scaling gate:

```bash
./bin/budget_audit.py gate enable --reason "Monthly budget threshold reached"
```

Disable the scaling gate:

```bash
./bin/budget_audit.py gate disable --reason "New budget cycle started"
```

### Export Reports

Export a cost report (JSON format):

```bash
./bin/budget_audit.py export --period month --output cost_report.json
```

Export Prometheus metrics:

```bash
./bin/budget_audit.py export-prometheus --output metrics.prom
```

## Output Examples

### Budget Summary

```
=== Budget Summary ===

Daily Budget: $50.00
Daily Spend:  $12.75 (25.5% of budget)

Monthly Budget: $1000.00
Monthly Spend:  $425.30 (42.5% of budget)
```

### Cost Breakdown

```
=== Daily Cost Breakdown by Service ===

Service              Amount
-----------------------------------
openai               $8.50
sendgrid             $3.25
aws                  $0.75
-----------------------------------
Total               $12.50

=== Daily Top Operations by Cost ===

openai:
  chat_completion: $6.50
  embeddings: $2.00

sendgrid:
  send_email: $3.25

aws:
  s3_storage: $0.75
```

### Scaling Gate Status

```
=== Scaling Gate Status ===

Status: INACTIVE
Reason: Below threshold

=== Recent History ===

2025-05-20 10:30:00: Deactivated - Below threshold
2025-05-20 09:15:00: Activated - Approaching daily budget
2025-05-19 16:45:00: Deactivated - Below threshold
```

## Error Handling

The tool provides meaningful error messages when something goes wrong. Common issues include:

- Database connection errors
- Permission issues
- Invalid command-line arguments

## Integration

The Budget Audit Tool can be integrated into monitoring systems by:

1. Using the `export-prometheus` command to generate metrics
2. Setting up a cron job to run periodic audits
3. Parsing the JSON output for custom dashboards

## License

This tool is part of the Anthrasite Lead-Factory project and is licensed under the same terms.
