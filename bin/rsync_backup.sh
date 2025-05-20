#!/bin/bash
#
# rsync_backup.sh - RSYNC backup script for Anthrasite Lead-Factory
#
# This script creates a nightly backup of the project data to a remote VPS
# to provide a SPOF (Single Point of Failure) fallback mechanism.
#
# Usage: ./rsync_backup.sh [OPTIONS]
#
# Options:
#   --config=FILE       Path to config file (default: ../etc/backup_config.yml)
#   --dry-run           Perform a trial run with no changes made
#   --verbose           Increase verbosity
#   --help              Display this help message

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOG_DIR}/rsync_backup_${TIMESTAMP}.log"
CONFIG_FILE="${PROJECT_ROOT}/etc/backup_config.yml"
LOCK_FILE="/tmp/anthrasite_rsync_backup.lock"
TIMEOUT=3600  # 1 hour timeout for rsync operations

# Default options
DRY_RUN=false
VERBOSE=false

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Function to parse YAML config
parse_yaml() {
    local yaml_file=$1
    local prefix=$2
    local s
    local w
    local fs
    
    s='[[:space:]]*'
    w='[a-zA-Z0-9_]*'
    fs="$(echo @|tr @ '\034')"
    
    (
        sed -e '/- [^\"]'"[^\']"'.*: /s|\([ ]*\)- \([[:space:]]*\)|\1-\'$'\n''  \1\2|g' |
        sed -ne '/^--/s|--||g; s|\"|\\\"|g; s/[[:space:]]*$//g;' \
            -e 's/\(^[^:]*\): \(.*\)/\1: "\2"/p' |
        sed -e "s|^\($s\)\($w\)$s:$s\"\(.*\)\"$s\$|\1$fs\2$fs\3|p" \
            -e "s|^\($s\)-$s\($w\)$s:$s\"\(.*\)\"$s\$|\1$fs\2$fs\3|p" |
        awk -F"$fs" '{
            indent = length($1)/2;
            if (indent == 0) {
                vname[indent] = $2;
            } else {
                vname[indent] = vname[indent-1]"_"$2;
            }
            if (length($3) > 0) {
                vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
                printf("%s%s%s=(\"%s\")\n", "'"$prefix"'",vn, $2, $3);
            }
        }'
    )
}

# Function to display help
show_help() {
    cat << EOF
Usage: ./rsync_backup.sh [OPTIONS]

RSYNC backup script for Anthrasite Lead-Factory that creates a nightly backup
of the project data to a remote VPS to provide a SPOF fallback mechanism.

Options:
  --config=FILE       Path to config file (default: ../etc/backup_config.yml)
  --dry-run           Perform a trial run with no changes made
  --verbose           Increase verbosity
  --help              Display this help message

Examples:
  ./rsync_backup.sh
  ./rsync_backup.sh --dry-run
  ./rsync_backup.sh --config=/path/to/custom/config.yml

Exit codes:
  0 - Success
  1 - Error in backup process
  2 - Invalid arguments
  3 - Lock file exists (another backup is running)
  4 - SSH connection failed
  5 - RSYNC failed
EOF
    exit 0
}

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --config=*)
            CONFIG_FILE="${arg#*=}"
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --verbose)
            VERBOSE=true
            ;;
        --help)
            show_help
            ;;
        *)
            log "ERROR" "Unknown argument: $arg"
            show_help
            exit 2
            ;;
    esac
done

# Check if another backup is running
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null; then
        log "ERROR" "Another backup is already running (PID: $PID)"
        exit 3
    else
        log "WARNING" "Found stale lock file, removing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"; log "INFO" "Backup process terminated"; exit 1' INT TERM EXIT

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log "ERROR" "Config file not found: $CONFIG_FILE"
    
    # Create a sample config file
    SAMPLE_CONFIG="${PROJECT_ROOT}/etc/backup_config.yml.sample"
    mkdir -p "$(dirname "$SAMPLE_CONFIG")"
    cat > "$SAMPLE_CONFIG" << EOF
# Backup configuration for Anthrasite Lead-Factory
backup:
  # Remote server details
  remote:
    host: backup.example.com
    user: backup
    port: 22
    key_file: ~/.ssh/backup_key
  
  # Directories to backup
  directories:
    - db
    - logs
    - etc
    - bin
  
  # Files to backup
  files:
    - .env
    - README.md
  
  # Exclude patterns
  exclude:
    - "*.tmp"
    - "*.log.gz"
    - "__pycache__"
    - ".git"
  
  # Retention policy
  retention:
    daily: 7
    weekly: 4
    monthly: 3
  
  # Notification settings
  notify:
    email: alerts@example.com
    slack_webhook: https://hooks.slack.com/services/XXXX/YYYY/ZZZZ
EOF
    
    log "ERROR" "Created sample config file at $SAMPLE_CONFIG"
    log "ERROR" "Please update the config file with your settings and try again"
    exit 1
fi

# Load configuration
log "INFO" "Loading configuration from $CONFIG_FILE"
eval "$(parse_yaml "$CONFIG_FILE")"

# Check required configuration
if [ -z "${backup_remote_host}" ] || [ -z "${backup_remote_user}" ]; then
    log "ERROR" "Missing required configuration: remote host and user"
    exit 1
fi

# Set default port if not specified
backup_remote_port=${backup_remote_port:-22}

# Set SSH options
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
if [ -n "${backup_remote_key_file}" ]; then
    SSH_OPTS="$SSH_OPTS -i ${backup_remote_key_file}"
fi

# Test SSH connection
log "INFO" "Testing SSH connection to ${backup_remote_user}@${backup_remote_host}:${backup_remote_port}"
if ! ssh $SSH_OPTS -p "${backup_remote_port}" "${backup_remote_user}@${backup_remote_host}" "echo 'SSH connection successful'" >> "$LOG_FILE" 2>&1; then
    log "ERROR" "SSH connection failed"
    exit 4
fi

# Create backup directory on remote server
REMOTE_BACKUP_DIR="/home/${backup_remote_user}/anthrasite_backup"
REMOTE_BACKUP_DATE_DIR="${REMOTE_BACKUP_DIR}/$(date +"%Y-%m-%d")"
ssh $SSH_OPTS -p "${backup_remote_port}" "${backup_remote_user}@${backup_remote_host}" "mkdir -p ${REMOTE_BACKUP_DATE_DIR}" >> "$LOG_FILE" 2>&1

# Prepare rsync exclude patterns
EXCLUDE_OPTS=""
if [ -n "${backup_exclude}" ]; then
    for exclude in "${backup_exclude[@]}"; do
        EXCLUDE_OPTS="$EXCLUDE_OPTS --exclude='$exclude'"
    done
fi

# Prepare rsync source paths
RSYNC_SOURCES=""
if [ -n "${backup_directories}" ]; then
    for dir in "${backup_directories[@]}"; do
        if [ -d "${PROJECT_ROOT}/${dir}" ]; then
            RSYNC_SOURCES="$RSYNC_SOURCES ${PROJECT_ROOT}/${dir}"
        else
            log "WARNING" "Directory not found: ${PROJECT_ROOT}/${dir}"
        fi
    done
fi

if [ -n "${backup_files}" ]; then
    for file in "${backup_files[@]}"; do
        if [ -f "${PROJECT_ROOT}/${file}" ]; then
            RSYNC_SOURCES="$RSYNC_SOURCES ${PROJECT_ROOT}/${file}"
        else
            log "WARNING" "File not found: ${PROJECT_ROOT}/${file}"
        fi
    done
fi

# Check if we have anything to backup
if [ -z "$RSYNC_SOURCES" ]; then
    log "ERROR" "No valid sources to backup"
    exit 1
fi

# Prepare rsync command
RSYNC_OPTS="-azP --delete"
if [ "$DRY_RUN" = true ]; then
    RSYNC_OPTS="$RSYNC_OPTS --dry-run"
fi
if [ "$VERBOSE" = true ]; then
    RSYNC_OPTS="$RSYNC_OPTS -v"
fi

# Run rsync with timeout
log "INFO" "Starting backup to ${backup_remote_user}@${backup_remote_host}:${REMOTE_BACKUP_DATE_DIR}"
RSYNC_CMD="rsync $RSYNC_OPTS $EXCLUDE_OPTS -e \"ssh $SSH_OPTS -p ${backup_remote_port}\" $RSYNC_SOURCES ${backup_remote_user}@${backup_remote_host}:${REMOTE_BACKUP_DATE_DIR}/"

if [ "$VERBOSE" = true ]; then
    log "DEBUG" "RSYNC command: $RSYNC_CMD"
fi

if ! timeout $TIMEOUT bash -c "$RSYNC_CMD" >> "$LOG_FILE" 2>&1; then
    log "ERROR" "RSYNC failed or timed out after $TIMEOUT seconds"
    exit 5
fi

# Create latest symlink on remote server
ssh $SSH_OPTS -p "${backup_remote_port}" "${backup_remote_user}@${backup_remote_host}" "ln -sf ${REMOTE_BACKUP_DATE_DIR} ${REMOTE_BACKUP_DIR}/latest" >> "$LOG_FILE" 2>&1

# Apply retention policy
if [ -n "${backup_retention_daily}" ] && [ "${backup_retention_daily}" -gt 0 ]; then
    log "INFO" "Applying retention policy: keeping ${backup_retention_daily} daily backups"
    
    # Get list of backup directories sorted by date (oldest first)
    BACKUP_DIRS=$(ssh $SSH_OPTS -p "${backup_remote_port}" "${backup_remote_user}@${backup_remote_host}" "find ${REMOTE_BACKUP_DIR} -maxdepth 1 -type d -name \"????-??-??\" | sort")
    
    # Count number of backups
    BACKUP_COUNT=$(echo "$BACKUP_DIRS" | wc -l)
    
    # Calculate number of backups to delete
    DELETE_COUNT=$((BACKUP_COUNT - backup_retention_daily))
    
    if [ "$DELETE_COUNT" -gt 0 ]; then
        log "INFO" "Removing $DELETE_COUNT old backups"
        
        # Get directories to delete
        DIRS_TO_DELETE=$(echo "$BACKUP_DIRS" | head -n "$DELETE_COUNT")
        
        # Delete old backups
        for dir in $DIRS_TO_DELETE; do
            if [ "$DRY_RUN" = true ]; then
                log "INFO" "DRY RUN: Would delete $dir"
            else
                log "INFO" "Deleting old backup: $dir"
                ssh $SSH_OPTS -p "${backup_remote_port}" "${backup_remote_user}@${backup_remote_host}" "rm -rf $dir" >> "$LOG_FILE" 2>&1
            fi
        done
    else
        log "INFO" "No old backups to remove"
    fi
fi

# Send notification if configured
if [ -n "${backup_notify_email}" ]; then
    log "INFO" "Sending email notification to ${backup_notify_email}"
    
    # Create email content
    EMAIL_SUBJECT="Anthrasite Lead-Factory Backup - $(date +"%Y-%m-%d")"
    EMAIL_BODY="Backup completed successfully at $(date).\n\nBackup location: ${backup_remote_user}@${backup_remote_host}:${REMOTE_BACKUP_DATE_DIR}\n\nSee attached log file for details."
    
    if [ "$DRY_RUN" = true ]; then
        log "INFO" "DRY RUN: Would send email to ${backup_notify_email}"
    else
        # Send email with log file attached
        if command -v mail > /dev/null; then
            echo -e "$EMAIL_BODY" | mail -s "$EMAIL_SUBJECT" -a "$LOG_FILE" "${backup_notify_email}"
        else
            log "WARNING" "mail command not found, skipping email notification"
        fi
    fi
fi

if [ -n "${backup_notify_slack_webhook}" ]; then
    log "INFO" "Sending Slack notification"
    
    # Create Slack message
    SLACK_MESSAGE="{\"text\":\"Anthrasite Lead-Factory Backup - $(date +"%Y-%m-%d")\",\"attachments\":[{\"color\":\"good\",\"text\":\"Backup completed successfully at $(date).\\nBackup location: ${backup_remote_user}@${backup_remote_host}:${REMOTE_BACKUP_DATE_DIR}\"}]}"
    
    if [ "$DRY_RUN" = true ]; then
        log "INFO" "DRY RUN: Would send Slack notification"
    else
        # Send Slack notification
        if command -v curl > /dev/null; then
            curl -s -X POST -H 'Content-type: application/json' --data "$SLACK_MESSAGE" "${backup_notify_slack_webhook}" >> "$LOG_FILE" 2>&1
        else
            log "WARNING" "curl command not found, skipping Slack notification"
        fi
    fi
fi

# Clean up lock file
rm -f "$LOCK_FILE"

log "INFO" "Backup completed successfully"
exit 0