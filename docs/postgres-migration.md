# PostgreSQL Migration Guide

This document outlines the migration process from SQLite to PostgreSQL (Supabase) for the Anthrasite LeadFactory project.

## Overview

The LeadFactory application has been updated to support both SQLite and PostgreSQL databases. SQLite is still supported for local development and testing, but PostgreSQL is recommended for production environments due to its improved performance, concurrency, and reliability.

## Configuration

### Environment Variables

The following environment variables are used to configure the database connection:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | None (falls back to SQLite) |
| `DATABASE_POOL_MIN_CONN` | Minimum number of connections in the pool | 2 |
| `DATABASE_POOL_MAX_CONN` | Maximum number of connections in the pool | 10 |

### Connection URL Format

The PostgreSQL connection URL should be in the following format:

```
postgresql://username:password@hostname:port/database
```

Example:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/leadfactory
```

For Supabase, the connection URL can be found in the Supabase dashboard under Project Settings > Database > Connection string.

## Migration Process

### Automatic Migration

To migrate your existing SQLite database to PostgreSQL, use the provided migration script:

```bash
python scripts/migrate_to_postgres.py
```

This script will:
1. Read data from the SQLite database
2. Create the necessary tables and indexes in PostgreSQL
3. Insert the data into PostgreSQL

### Manual Migration

If you prefer to perform the migration manually, follow these steps:

1. Create a new PostgreSQL database
2. Apply the schema from `scripts/postgres_schema.sql`
3. Export data from SQLite using `.dump` command
4. Convert the SQLite dump to PostgreSQL format
5. Import the data into PostgreSQL

## Backup and Recovery

### Automated Backups

A backup script is provided to create regular backups of the PostgreSQL database:

```bash
./scripts/backup_postgres.sh
```

This script:
- Creates a compressed backup of the database
- Stores backups in the `data/backups` directory
- Retains backups for 30 days by default
- Adds backups to the RSYNC backup set if configured

### Point-in-Time Recovery

The PostgreSQL database is configured with Write-Ahead Logging (WAL) for point-in-time recovery. This allows you to recover the database to any point in time since the last backup.

To configure WAL, run:

```bash
./scripts/configure_postgres_wal.sh
```

Note: Supabase PostgreSQL databases already have WAL enabled by default.

## Development Workflow

### Local Development

For local development, you can continue to use SQLite by not setting the `DATABASE_URL` environment variable. This is the simplest approach for development and testing.

### Testing with PostgreSQL

To test with PostgreSQL locally:

1. Install PostgreSQL on your development machine
2. Create a database for testing
3. Set the `DATABASE_URL` environment variable to point to your local PostgreSQL database

### CI/CD Pipeline

The CI/CD pipeline has been updated to test with both SQLite and PostgreSQL to ensure compatibility with both database engines.

## Fallback Mechanism

The application is designed to fall back to SQLite if:

1. The `DATABASE_URL` environment variable is not set
2. Connection to the PostgreSQL database fails

This ensures that the application can continue to function even if there are issues with the PostgreSQL connection.

## Troubleshooting

### Connection Issues

If you experience connection issues:

1. Verify that the PostgreSQL server is running
2. Check that the `DATABASE_URL` is correctly formatted
3. Ensure that the database user has the necessary permissions
4. Check firewall settings if connecting to a remote database

### Migration Errors

If the migration script fails:

1. Run with `--dry-run` flag to check what would be migrated
2. Check the logs for specific error messages
3. Ensure that the SQLite database is not corrupted
4. Verify that the PostgreSQL user has CREATE and INSERT permissions

## Performance Considerations

### Connection Pooling

The application uses connection pooling to improve performance. The pool size can be adjusted using the `DATABASE_POOL_MIN_CONN` and `DATABASE_POOL_MAX_CONN` environment variables.

### Indexes

Indexes have been created on frequently queried columns to improve query performance. Additional indexes can be added as needed based on query patterns.

### Query Optimization

When writing queries, be aware of the differences between SQLite and PostgreSQL, especially regarding:

- JSON handling (PostgreSQL uses JSONB)
- Date/time functions
- Text search capabilities
- Transaction isolation levels

## Security Considerations

### Connection Security

For production environments:

1. Use SSL/TLS for database connections
2. Store database credentials securely (not in version control)
3. Use a database user with minimal required permissions
4. Consider using connection pooling proxies like PgBouncer for additional security

### Data Protection

For sensitive data:

1. Consider using PostgreSQL's column-level encryption
2. Implement row-level security policies
3. Use database roles to control access to specific tables

## Monitoring

The application includes Prometheus metrics for database performance monitoring. Key metrics include:

- Connection pool utilization
- Query execution time
- Transaction rate
- Error rate

These metrics can be used to set up alerts for database performance issues.
