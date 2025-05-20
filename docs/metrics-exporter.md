# Metrics Exporter

The Metrics Exporter provides Prometheus-compatible metrics for the Anthrasite Lead-Factory system. It exposes various metrics related to API usage, costs, and system health.

## Features

- **Cost Metrics**: Track daily and monthly costs by service
- **Budget Utilization**: Monitor budget usage as a percentage of allocated budget
- **Scaling Gate Status**: Check if the scaling gate is active
- **HTTP Metrics**: Track request counts and latencies
- **Health Checks**: Simple health check endpoint

## Endpoints

- `GET /metrics`: Prometheus metrics endpoint
- `GET /health`: Health check endpoint
- `GET /scaling-gate/status`: Get current scaling gate status
- `GET /costs/daily`: Get daily cost breakdown by service
- `GET /costs/monthly`: Get monthly cost breakdown by service

## Getting Started

### Prerequisites

- Python 3.8+
- Dependencies listed in `requirements-metrics.txt`

### Installation

1. Install the required dependencies:

```bash
pip install -r requirements-metrics.txt
```

2. Set up the required environment variables (see Configuration section below)

### Running the Exporter

Start the metrics server:

```bash
python -m utils.metrics
```

By default, the server will start on `http://0.0.0.0:8000`.

### Configuration

The following environment variables can be used to configure the exporter:

- `METRICS_HOST`: Host to bind to (default: `0.0.0.0`)
- `METRICS_PORT`: Port to listen on (default: `8000`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `ENVIRONMENT`: Environment name (e.g., `production`, `staging`, `development`)

## Prometheus Configuration

Add the following job to your Prometheus configuration to scrape metrics:

```yaml
scrape_configs:
  - job_name: 'lead-factory'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

## Grafana Dashboard

A sample Grafana dashboard is available in `grafana/dashboard.json`. Import this dashboard into your Grafana instance to visualize the metrics.

## Monitoring and Alerts

### Recommended Alerts

1. **High Budget Utilization**: Alert when daily or monthly budget utilization exceeds 80%
2. **Scaling Gate Active**: Alert when the scaling gate is activated
3. **High Error Rate**: Alert when the error rate exceeds 1%

### Example Alert Rules

```yaml
groups:
- name: lead-factory
  rules:
  - alert: HighDailyBudgetUtilization
    expr: lead_factory_budget_utilization{period="daily"} > 80
    for: 1h
    labels:
      severity: warning
    annotations:
      summary: High daily budget utilization
      description: 'Daily budget utilization is {{ $value }}%'

  - alert: ScalingGateActive
    expr: lead_factory_scaling_gate_active == 1
    labels:
      severity: critical
    annotations:
      summary: Scaling gate is active
      description: 'The scaling gate has been activated due to budget constraints'
```

## Development

### Running Tests

```bash
pytest tests/test_metrics.py
```

### Building the Docker Image

```bash
docker build -t lead-factory-metrics -f docker/metrics/Dockerfile .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
