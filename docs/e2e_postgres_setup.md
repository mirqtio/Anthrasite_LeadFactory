# E2E Testing PostgreSQL Database Setup

This document describes the setup and usage of the dedicated PostgreSQL database for E2E testing.

## Overview

The E2E testing environment uses a Docker-based PostgreSQL database that:

- Runs on localhost:5432
- Uses the same schema as production
- Contains seed data for testing
- Persists data between test runs
- Is isolated from development and production environments

## Setup Instructions

### Prerequisites

- Docker and Docker Compose installed
- Python 3.6+ with psycopg2-binary package

### Starting the Database

```bash
# Start the database container
python scripts/manage_e2e_db.py start

# Alternatively, if you need to restart the database
python scripts/manage_e2e_db.py restart
```

The script will:
1. Start the PostgreSQL container
2. Wait for it to be ready
3. Validate the schema
4. Update the `.env.e2e` file with the connection string

### Stopping the Database

```bash
python scripts/manage_e2e_db.py stop
```

### Validating the Setup

```bash
# Test the database connection
python scripts/test_e2e_db_connection.py

# Validate the database schema
python scripts/manage_e2e_db.py validate
```

## Configuration Details

### Connection String

The database connection string is automatically added to the `.env.e2e` file:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/leadfactory  # pragma: allowlist secret
```

### Docker Container

- Container name: `leadfactory_e2e_db`
- Image: `postgres:14`
- Exposed port: 5432
- Data volume: `leadfactory_e2e_postgres_data`

### Database Schema

The database is initialized with the full schema required by the application, including:

- `businesses` - Lead information
- `emails` - Email delivery tracking
- `llm_logs` - AI operation logs
- `zip_queue` - ZIP codes for business scraping
- `verticals` - Business categories
- `assets` - Generated screenshots and mockups

## Testing with the E2E Database

When running E2E tests, ensure:

1. The database container is running
2. The `.env.e2e` file contains the correct `DATABASE_URL`
3. Your tests are configured to use the `.env.e2e` environment variables

## Troubleshooting

### Container Fails to Start

Check Docker logs:
```bash
docker logs leadfactory_e2e_db
```

### Connection Issues

Verify the container is running and healthy:
```bash
docker ps
docker inspect leadfactory_e2e_db --format='{{.State.Health.Status}}'
```

### Database Reset

If you need to completely reset the database:
```bash
docker-compose -f docker-compose.e2e.yml down -v
python scripts/manage_e2e_db.py start
```

### Schema Issues

Check the schema manually:
```bash
docker exec -it leadfactory_e2e_db psql -U postgres -d leadfactory -c '\dt'
```
