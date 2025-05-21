#!/bin/bash
# Anthrasite Lead-Factory: PostgreSQL Backup Script
# This script creates a backup of the PostgreSQL database and adds it to the RSYNC backup set.
# It should be run as a nightly cron job.

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
BACKUP_DIR="./data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/leadfactory_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=30
LOG_FILE="./logs/backup_postgres.log"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"
mkdir -p "./logs"

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

# Create backup
log "Starting PostgreSQL backup of database $DB_NAME on $DB_HOST"

# Use password from environment variable or .pgpass file
if [ -n "$DB_PASS" ]; then
    export PGPASSWORD="$DB_PASS"
    log "Using password from DATABASE_URL"
else
    log "No password in DATABASE_URL, using .pgpass file if available"
fi

# Run pg_dump and compress the output
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F p | gzip > "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    log "Backup completed successfully: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    log "ERROR: Backup failed"
    exit 1
fi

# Unset PGPASSWORD for security
unset PGPASSWORD

# Add to RSYNC backup set if RSYNC_TARGET_HOST is configured
if [ -n "$RSYNC_TARGET_HOST" ] && [ -n "$RSYNC_TARGET_USER" ] && [ -n "$RSYNC_TARGET_PATH" ]; then
    log "Adding backup to RSYNC backup set"
    
    # Check if SSH key is specified
    if [ -n "$RSYNC_SSH_KEY_PATH" ]; then
        RSYNC_SSH_OPTS="-e ssh -i $RSYNC_SSH_KEY_PATH"
    else
        RSYNC_SSH_OPTS=""
    fi
    
    # Sync backup to remote server
    rsync -avz $RSYNC_SSH_OPTS "$BACKUP_FILE" "$RSYNC_TARGET_USER@$RSYNC_TARGET_HOST:$RSYNC_TARGET_PATH/"
    
    if [ $? -eq 0 ]; then
        log "Backup successfully added to RSYNC backup set"
    else
        log "ERROR: Failed to add backup to RSYNC backup set"
        exit 1
    fi
else
    log "RSYNC backup set not configured, skipping"
fi

# Clean up old backups
log "Cleaning up backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "leadfactory_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

log "Backup process completed"
exit 0
