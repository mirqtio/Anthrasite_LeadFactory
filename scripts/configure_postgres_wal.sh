#!/bin/bash
# Anthrasite Lead-Factory: PostgreSQL WAL Configuration Script
# This script configures Write-Ahead Logging (WAL) and point-in-time recovery for PostgreSQL.
# It should be run once during initial setup.

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
LOG_FILE="./logs/configure_postgres_wal.log"
WAL_ARCHIVE_DIR="./data/wal_archive"

# Ensure log directory exists
mkdir -p "./logs"
mkdir -p "$WAL_ARCHIVE_DIR"

# Log function
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" | tee -a "$LOG_FILE"
}

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    log "ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Extract database connection details from DATABASE_URL
# Format: postgresql://username:password@hostname:port/database
DB_USER=$(echo $DATABASE_URL | sed -n 's/^postgresql:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's/^postgresql:\/\/[^:]*:\([^@]*\).*/\1/p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's/^postgresql:\/\/[^@]*@\([^:]*\).*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/^postgresql:\/\/[^@]*@[^:]*:\([^\/]*\).*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/^postgresql:\/\/[^@]*@[^\/]*\/\(.*\)$/\1/p')

# Validate connection details
if [ -z "$DB_USER" ] || [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ]; then
    log "ERROR: Could not parse DATABASE_URL correctly"
    log "DATABASE_URL format should be: postgresql://username:password@hostname:port/database"
    exit 1
fi

# Set default port if not specified
if [ -z "$DB_PORT" ]; then
    DB_PORT="5432"
fi

# Use password from environment variable or .pgpass file
if [ -n "$DB_PASS" ]; then
    export PGPASSWORD="$DB_PASS"
    log "Using password from DATABASE_URL"
else
    log "No password in DATABASE_URL, using .pgpass file if available"
fi

log "Checking if the connected PostgreSQL server is Supabase"
IS_SUPABASE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT current_database() LIKE 'postgres%' OR current_database() LIKE 'supabase%';")

if [[ "$IS_SUPABASE" == *"t"* ]]; then
    log "Connected to Supabase PostgreSQL server"
    log "NOTE: Supabase already has WAL and point-in-time recovery configured by default"
    log "No additional configuration needed for Supabase PostgreSQL"

    # Verify WAL settings
    log "Verifying WAL settings on Supabase PostgreSQL"
    WAL_LEVEL=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW wal_level;")
    ARCHIVE_MODE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW archive_mode;")

    log "Current WAL settings:"
    log "  wal_level: $WAL_LEVEL"
    log "  archive_mode: $ARCHIVE_MODE"

    log "Supabase PostgreSQL configuration verified"
    exit 0
fi

# For non-Supabase PostgreSQL servers, configure WAL
log "Configuring WAL for PostgreSQL server at $DB_HOST"

# Check if we have superuser privileges
IS_SUPERUSER=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT usesuper FROM pg_user WHERE usename = current_user;")

if [[ "$IS_SUPERUSER" != *"t"* ]]; then
    log "ERROR: Current user does not have superuser privileges"
    log "WAL configuration requires superuser privileges"
    log "Please contact your database administrator to configure WAL"
    exit 1
fi

# Configure WAL settings
log "Setting WAL configuration parameters"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ALTER SYSTEM SET wal_level = 'replica';"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ALTER SYSTEM SET archive_mode = 'on';"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ALTER SYSTEM SET archive_command = 'cp %p $WAL_ARCHIVE_DIR/%f';"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ALTER SYSTEM SET max_wal_senders = 10;"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ALTER SYSTEM SET wal_keep_segments = 64;"

# Reload PostgreSQL configuration
log "Reloading PostgreSQL configuration"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT pg_reload_conf();"

# Verify WAL settings
log "Verifying WAL settings"
WAL_LEVEL=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW wal_level;")
ARCHIVE_MODE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW archive_mode;")
ARCHIVE_COMMAND=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SHOW archive_command;")

log "Updated WAL settings:"
log "  wal_level: $WAL_LEVEL"
log "  archive_mode: $ARCHIVE_MODE"
log "  archive_command: $ARCHIVE_COMMAND"

# Unset PGPASSWORD for security
unset PGPASSWORD

log "WAL configuration completed successfully"
log "Point-in-time recovery is now enabled"
log "WAL archive directory: $WAL_ARCHIVE_DIR"
log "NOTE: For production environments, consider using a more robust archive_command that copies WAL files to a separate storage system"

exit 0
