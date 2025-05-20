# Metrics Exporter for Anthrasite Lead-Factory

This service provides Prometheus metrics for monitoring the Anthrasite Lead-Factory system.

## Features

- Exposes Prometheus metrics at `/metrics`
- Provides cost tracking metrics (daily/monthly costs by service)
- Tracks budget utilization and scaling gate status
- Includes HTTP request metrics (count, latency, error rate)
- Health check endpoint at `/health`
- Simple REST API for cost and scaling gate status

## Getting Started

### Prerequisites

- Python 3.8+
- Docker and Docker Compose (for containerized deployment)

### Installation

1. Install Python dependencies:

```bash
pip install -r requirements-metrics.txt
```

### Running Locally

1. Set up environment variables (see `.env.example` for reference)
2. Start the metrics server:

```bash
python -m utils.metrics
```

The server will be available at `http://localhost:8000`

### Running with Docker

1. Build and start the services:

```bash
docker-compose -f docker-compose.metrics.yml up -d
```

This will start:
- Metrics exporter on port 8000
- Prometheus on port 9090
- Grafana on port 3000

## API Endpoints

- `GET /metrics`: Prometheus metrics endpoint
- `GET /health`: Health check endpoint
- `GET /scaling-gate/status`: Get current scaling gate status
- `GET /costs/daily`: Get daily cost breakdown by service
- `GET /costs/monthly`: Get monthly cost breakdown by service

## Monitoring Setup

### Prometheus

Prometheus is pre-configured to scrape the metrics exporter. Access the Prometheus UI at `http://localhost:9090`

### Grafana

1. Log in to Grafana at `http://localhost:3000` (admin/admin)
2. Add Prometheus as a data source:
   - URL: `http://prometheus:9090`
   - Save & Test
3. Import the dashboard from `grafana/dashboard.json`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (debug, info, warning, error) | `info` |
| `ENVIRONMENT` | Environment name (production, staging, development) | `production` |
| `DB_PATH` | Path to SQLite database file | `./db/lead_factory.db` |
| `DAILY_BUDGET` | Daily budget in USD | `50.0` |
| `MONTHLY_BUDGET` | Monthly budget in USD | `1000.0` |
| `DAILY_ALERT_THRESHOLD` | Alert threshold for daily budget (0-1) | `0.8` |
| `MONTHLY_ALERT_THRESHOLD` | Alert threshold for monthly budget (0-1) | `0.8` |
| `SCALING_GATE_ENABLED` | Enable/disable scaling gate | `true` |
| `SCALING_GATE_DAILY_THRESHOLD` | Scaling gate threshold for daily budget (0-1) | `0.9` |
| `SCALING_GATE_MONTHLY_THRESHOLD` | Scaling gate threshold for monthly budget (0-1) | `0.9` |

## Development

### Running Tests

```bash
pytest tests/test_metrics.py -v
```

### Linting

```bash
flake8 utils/metrics.py tests/test_metrics.py
```

### Building the Docker Image

```bash
docker build -t lead-factory-metrics -f docker/metrics/Dockerfile .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
