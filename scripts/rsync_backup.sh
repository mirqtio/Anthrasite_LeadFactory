#!/bin/bash
# rsync_backup.sh - Enhanced backup script with configurable retention period
#
# This script performs database dumps and syncs them to a remote VPS
# It maintains a configurable retention period for backups (default: 90 days)
#
# Usage: ./rsync_backup.sh [options]
#   Options:
#     --dry-run: Show what would be done without making changes

set -e

# Load environment variables
if [ -f .env ]; then
  source .env
elif [ -f .env.production ]; then
  source .env.production
fi

# Default retention period (90 days) if not set in environment
RETENTION_DAYS_DB_BACKUPS=${RETENTION_DAYS_DB_BACKUPS:-90}
REMOTE_HOST=${BACKUP_REMOTE_HOST:-"backup-vps.example.com"}
REMOTE_USER=${BACKUP_REMOTE_USER:-"backup"}
REMOTE_PATH=${BACKUP_REMOTE_PATH:-"/var/backups/leadfactory"}
DB_NAME=${DB_NAME:-"postgres"}
DB_USER=${DB_USER:-"postgres"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-5432}

# Parse command line arguments
DRY_RUN=0
for arg in "$@"; do
  case $arg in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
  esac
done

# Create local backup directories
BACKUP_DIR="./backups"
DB_BACKUP_DIR="$BACKUP_DIR/db"
STORAGE_BACKUP_DIR="$BACKUP_DIR/storage"

mkdir -p "$DB_BACKUP_DIR"
mkdir -p "$STORAGE_BACKUP_DIR"

# Get current timestamp for backup files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_BACKUP_FILE="$DB_BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

echo "Starting database backup at $(date)"

# Create database dump
if [ $DRY_RUN -eq 1 ]; then
  echo "[DRY RUN] Would execute: pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME | gzip > $DB_BACKUP_FILE"
else
  pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$DB_BACKUP_FILE"
  echo "Database backup completed: $DB_BACKUP_FILE"
fi

# Sync backups to remote server
if [ $DRY_RUN -eq 1 ]; then
  echo "[DRY RUN] Would execute: rsync -avz --delete $BACKUP_DIR/ $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
else
  rsync -avz --delete "$BACKUP_DIR/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
  echo "Backup synced to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
fi

# Clean up old backups on remote server
if [ $DRY_RUN -eq 1 ]; then
  echo "[DRY RUN] Would execute: ssh $REMOTE_USER@$REMOTE_HOST \"find $REMOTE_PATH/db -name 'db_backup_*.sql.gz' -mtime +$RETENTION_DAYS_DB_BACKUPS -delete\""
else
  ssh "$REMOTE_USER@$REMOTE_HOST" "find $REMOTE_PATH/db -name 'db_backup_*.sql.gz' -mtime +$RETENTION_DAYS_DB_BACKUPS -delete"
  echo "Removed backups older than $RETENTION_DAYS_DB_BACKUPS days from remote server"
fi

# Clean up local backups (keep only the latest)
if [ $DRY_RUN -eq 1 ]; then
  echo "[DRY RUN] Would execute: find $DB_BACKUP_DIR -name 'db_backup_*.sql.gz' -not -name $(basename $DB_BACKUP_FILE) -delete"
else
  find "$DB_BACKUP_DIR" -name "db_backup_*.sql.gz" -not -name "$(basename "$DB_BACKUP_FILE")" -delete
  echo "Cleaned up local backup directory, keeping only the latest backup"
fi

echo "Backup process completed successfully at $(date)"
