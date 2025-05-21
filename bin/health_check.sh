#!/bin/bash
#
# health_check.sh - Health check and auto-boot script for Anthrasite Lead-Factory
#
# This script monitors the health of the Lead-Factory application and automatically
# boots the Docker stack on the backup VPS if the primary instance fails multiple checks.
#
# Usage: ./health_check.sh [OPTIONS]
#
# Options:
#   --config=FILE       Path to config file (default: ../etc/health_check_config.yml)
#   --check-only        Only perform health checks without auto-boot
#   --force-boot        Force boot on backup VPS without health checks
#   --verbose           Increase verbosity
#   --help              Display this help message

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOG_DIR}/health_check_${TIMESTAMP}.log"
CONFIG_FILE="${PROJECT_ROOT}/etc/health_check_config.yml"
STATE_FILE="${PROJECT_ROOT}/etc/health_check_state.json"
LOCK_FILE="/tmp/anthrasite_health_check.lock"
TIMEOUT=300  # 5 minute timeout for operations

# Default options
CHECK_ONLY=false
FORCE_BOOT=false
VERBOSE=false

# Default configuration
PRIMARY_URL="http://localhost:8080/health"
PRIMARY_EXPECTED_STATUS=200
PRIMARY_TIMEOUT=10
FAILURE_THRESHOLD=2  # Changed from 3 to 2 to match Phase 0 v1.3 spec
BACKUP_HOST="backup.example.com"
BACKUP_USER="backup"
BACKUP_PORT=22
BACKUP_KEY_FILE="~/.ssh/backup_key"
DOCKER_COMPOSE_PATH="/home/backup/anthrasite_backup/latest/docker-compose.yml"
NOTIFY_EMAIL=""
NOTIFY_SLACK_WEBHOOK=""

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

# Function to read state
read_state() {
    if [ -f "$STATE_FILE" ]; then
        FAILURE_COUNT=$(jq -r '.failure_count // 0' "$STATE_FILE")
        LAST_FAILURE=$(jq -r '.last_failure // ""' "$STATE_FILE")
        LAST_SUCCESS=$(jq -r '.last_success // ""' "$STATE_FILE")
        LAST_BOOT=$(jq -r '.last_boot // ""' "$STATE_FILE")
    else
        FAILURE_COUNT=0
        LAST_FAILURE=""
        LAST_SUCCESS=""
        LAST_BOOT=""
    fi
}

# Function to write state
write_state() {
    mkdir -p "$(dirname "$STATE_FILE")"
    cat > "$STATE_FILE" << EOF
{
  "failure_count": $FAILURE_COUNT,
  "last_failure": "$LAST_FAILURE",
  "last_success": "$LAST_SUCCESS",
  "last_boot": "$LAST_BOOT"
}
EOF
}

# Function to reset failure count
reset_failure_count() {
    FAILURE_COUNT=0
    LAST_SUCCESS=$(date +"%Y-%m-%d %H:%M:%S")
    write_state
}

# Function to increment failure count
increment_failure_count() {
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
    LAST_FAILURE=$(date +"%Y-%m-%d %H:%M:%S")
    write_state
}

# Function to set last boot time
set_last_boot() {
    LAST_BOOT=$(date +"%Y-%m-%d %H:%M:%S")
    write_state
}

# Function to display help
show_help() {
    cat << EOF
Usage: ./health_check.sh [OPTIONS]

Health check and auto-boot script for Anthrasite Lead-Factory that monitors
the health of the application and automatically boots the Docker stack on
the backup VPS if the primary instance fails multiple checks.

Options:
  --config=FILE       Path to config file (default: ../etc/health_check_config.yml)
  --check-only        Only perform health checks without auto-boot
  --force-boot        Force boot on backup VPS without health checks
  --verbose           Increase verbosity
  --help              Display this help message

Examples:
  ./health_check.sh
  ./health_check.sh --check-only
  ./health_check.sh --force-boot
  ./health_check.sh --config=/path/to/custom/config.yml

Exit codes:
  0 - Success (primary healthy or backup booted successfully)
  1 - Error in health check or boot process
  2 - Invalid arguments
  3 - Lock file exists (another health check is running)
  4 - Primary instance unhealthy but under threshold
  5 - Primary instance unhealthy and over threshold
  6 - Backup boot failed
EOF
    exit 0
}

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --config=*)
            CONFIG_FILE="${arg#*=}"
            ;;
        --check-only)
            CHECK_ONLY=true
            ;;
        --force-boot)
            FORCE_BOOT=true
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

# Check if another health check is running
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null; then
        log "ERROR" "Another health check is already running (PID: $PID)"
        exit 3
    else
        log "WARNING" "Found stale lock file, removing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"; log "INFO" "Health check process terminated"; exit 1' INT TERM EXIT

# Check if config file exists
if [ -f "$CONFIG_FILE" ]; then
    log "INFO" "Loading configuration from $CONFIG_FILE"
    eval "$(parse_yaml "$CONFIG_FILE")"

    # Override defaults with config values
    PRIMARY_URL=${health_check_primary_url:-$PRIMARY_URL}
    PRIMARY_EXPECTED_STATUS=${health_check_primary_expected_status:-$PRIMARY_EXPECTED_STATUS}
    PRIMARY_TIMEOUT=${health_check_primary_timeout:-$PRIMARY_TIMEOUT}
    FAILURE_THRESHOLD=${health_check_failure_threshold:-$FAILURE_THRESHOLD}
    BACKUP_HOST=${health_check_backup_host:-$BACKUP_HOST}
    BACKUP_USER=${health_check_backup_user:-$BACKUP_USER}
    BACKUP_PORT=${health_check_backup_port:-$BACKUP_PORT}
    BACKUP_KEY_FILE=${health_check_backup_key_file:-$BACKUP_KEY_FILE}
    DOCKER_COMPOSE_PATH=${health_check_docker_compose_path:-$DOCKER_COMPOSE_PATH}
    NOTIFY_EMAIL=${health_check_notify_email:-$NOTIFY_EMAIL}
    NOTIFY_SLACK_WEBHOOK=${health_check_notify_slack_webhook:-$NOTIFY_SLACK_WEBHOOK}
else
    log "WARNING" "Config file not found: $CONFIG_FILE, using defaults"

    # Create a sample config file
    SAMPLE_CONFIG="${PROJECT_ROOT}/etc/health_check_config.yml.sample"
    mkdir -p "$(dirname "$SAMPLE_CONFIG")"
    cat > "$SAMPLE_CONFIG" << EOF
# Health check configuration for Anthrasite Lead-Factory
health_check:
  # Primary instance details
  primary:
    url: http://localhost:8080/health
    expected_status: 200
    timeout: 10  # seconds

  # Failure threshold
  failure_threshold: 3

  # Backup instance details
  backup:
    host: backup.example.com
    user: backup
    port: 22
    key_file: ~/.ssh/backup_key
    docker_compose_path: /home/backup/anthrasite_backup/latest/docker-compose.yml

  # Notification settings
  notify:
    email: alerts@example.com
    slack_webhook: https://hooks.slack.com/services/XXXX/YYYY/ZZZZ
EOF

    log "INFO" "Created sample config file at $SAMPLE_CONFIG"
fi

# Load state
read_state

# Log start
log "INFO" "Starting Anthrasite Lead-Factory health check"
log "INFO" "Current failure count: $FAILURE_COUNT/$FAILURE_THRESHOLD"

# Check if force boot is enabled
if [ "$FORCE_BOOT" = true ]; then
    log "INFO" "Force boot enabled, skipping health checks"
    if [ "$CHECK_ONLY" = true ]; then
        log "WARNING" "Both --check-only and --force-boot specified, --force-boot takes precedence"
    fi

    # Set failure count to threshold to trigger boot
    FAILURE_COUNT=$FAILURE_THRESHOLD
else
    # Perform health check
    log "INFO" "Checking health of primary instance: $PRIMARY_URL"

    # Use curl to check health endpoint
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m "$PRIMARY_TIMEOUT" "$PRIMARY_URL" 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" = "$PRIMARY_EXPECTED_STATUS" ]; then
        log "INFO" "Primary instance is healthy (HTTP status: $HTTP_STATUS)"
        reset_failure_count

        # Clean up lock file
        rm -f "$LOCK_FILE"

        log "INFO" "Health check completed successfully"
        exit 0
    else
        log "WARNING" "Primary instance is unhealthy (HTTP status: $HTTP_STATUS, expected: $PRIMARY_EXPECTED_STATUS)"
        increment_failure_count

        log "INFO" "Failure count: $FAILURE_COUNT/$FAILURE_THRESHOLD"

        if [ "$FAILURE_COUNT" -lt "$FAILURE_THRESHOLD" ]; then
            log "INFO" "Below failure threshold, not booting backup yet"

            # Clean up lock file
            rm -f "$LOCK_FILE"

            exit 4
        else
            log "WARNING" "Failure threshold reached ($FAILURE_COUNT/$FAILURE_THRESHOLD)"

            if [ "$CHECK_ONLY" = true ]; then
                log "INFO" "Check-only mode enabled, not booting backup"

                # Clean up lock file
                rm -f "$LOCK_FILE"

                exit 5
            fi
        fi
    fi
fi

# If we reach here, we need to boot the backup
if [ "$CHECK_ONLY" = false ]; then
    log "INFO" "Booting backup instance on $BACKUP_HOST"

    # Set SSH options
    SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
    if [ -n "$BACKUP_KEY_FILE" ] && [ "$BACKUP_KEY_FILE" != "~/.ssh/backup_key" ]; then
        SSH_OPTS="$SSH_OPTS -i $BACKUP_KEY_FILE"
    fi

    # Test SSH connection
    log "INFO" "Testing SSH connection to ${BACKUP_USER}@${BACKUP_HOST}:${BACKUP_PORT}"
    if ! ssh $SSH_OPTS -p "$BACKUP_PORT" "${BACKUP_USER}@${BACKUP_HOST}" "echo 'SSH connection successful'" >> "$LOG_FILE" 2>&1; then
        log "ERROR" "SSH connection failed"

        # Send notification
        send_notification "Anthrasite Lead-Factory - Backup Boot Failed" "SSH connection to backup server failed. Manual intervention required."

        # Clean up lock file
        rm -f "$LOCK_FILE"

        exit 6
    fi

    # Boot Docker stack on backup
    log "INFO" "Starting Docker stack on backup server"
    if ! ssh $SSH_OPTS -p "$BACKUP_PORT" "${BACKUP_USER}@${BACKUP_HOST}" "cd $(dirname "$DOCKER_COMPOSE_PATH") && docker-compose -f $(basename "$DOCKER_COMPOSE_PATH") up -d" >> "$LOG_FILE" 2>&1; then
        log "ERROR" "Failed to start Docker stack on backup server"

        # Send notification
        send_notification "Anthrasite Lead-Factory - Backup Boot Failed" "Failed to start Docker stack on backup server. Manual intervention required."

        # Clean up lock file
        rm -f "$LOCK_FILE"

        exit 6
    fi

    # Update state
    set_last_boot

    log "INFO" "Backup instance booted successfully"

    # Send notification
    send_notification "Anthrasite Lead-Factory - Backup Booted" "Primary instance failed $FAILURE_COUNT health checks. Backup instance has been booted successfully."
fi

# Function to send notification
send_notification() {
    local subject="$1"
    local message="$2"

    # Send email notification
    if [ -n "$NOTIFY_EMAIL" ]; then
        log "INFO" "Sending email notification to $NOTIFY_EMAIL"

        if command -v mail > /dev/null; then
            echo -e "$message" | mail -s "$subject" -a "$LOG_FILE" "$NOTIFY_EMAIL"
        else
            log "WARNING" "mail command not found, skipping email notification"
        fi
    fi

    # Send Slack notification
    if [ -n "$NOTIFY_SLACK_WEBHOOK" ]; then
        log "INFO" "Sending Slack notification"

        local color="danger"
        if [[ "$subject" == *"Booted"* ]]; then
            color="warning"
        fi

        local slack_message="{\"text\":\"$subject\",\"attachments\":[{\"color\":\"$color\",\"text\":\"$message\"}]}"

        if command -v curl > /dev/null; then
            curl -s -X POST -H 'Content-type: application/json' --data "$slack_message" "$NOTIFY_SLACK_WEBHOOK" >> "$LOG_FILE" 2>&1
        else
            log "WARNING" "curl command not found, skipping Slack notification"
        fi
    fi
}

# Clean up lock file
rm -f "$LOCK_FILE"

log "INFO" "Health check completed successfully"
exit 0
