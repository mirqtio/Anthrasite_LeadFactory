#!/bin/bash
#
# setup_cron.sh - Setup script for Anthrasite Lead-Factory nightly cron job
#
# This script sets up a cron job to run the nightly batch process at the specified time.
# It also creates a log rotation configuration to manage log files.
#
# Usage: ./setup_cron.sh [--time=HH:MM] [--user=username]
#
# Options:
#   --time=HH:MM       Set the time for the nightly run (default: 01:00)
#   --user=username    Set the user for the cron job (default: current user)
#   --help             Display this help message

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NIGHTLY_SCRIPT="${SCRIPT_DIR}/run_nightly.sh"
DEFAULT_TIME="01:00"
DEFAULT_USER="$(whoami)"

# Default options
CRON_TIME="$DEFAULT_TIME"
CRON_USER="$DEFAULT_USER"

# Function to display help
show_help() {
    cat << EOF
Usage: ./setup_cron.sh [OPTIONS]

Setup script for Anthrasite Lead-Factory nightly cron job.

Options:
  --time=HH:MM       Set the time for the nightly run (default: 01:00)
  --user=username    Set the user for the cron job (default: current user)
  --help             Display this help message

Examples:
  ./setup_cron.sh
  ./setup_cron.sh --time=02:30
  ./setup_cron.sh --user=anthrasite --time=03:15

EOF
    exit 0
}

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --time=*)
            CRON_TIME="${arg#*=}"
            # Validate time format
            if ! [[ $CRON_TIME =~ ^([0-1][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
                echo "Error: Invalid time format. Please use HH:MM (24-hour format)."
                exit 1
            fi
            ;;
        --user=*)
            CRON_USER="${arg#*=}"
            # Check if user exists
            if ! id "$CRON_USER" &>/dev/null; then
                echo "Error: User '$CRON_USER' does not exist."
                exit 1
            fi
            ;;
        --help)
            show_help
            ;;
        *)
            echo "Error: Unknown argument: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Extract hours and minutes from the time
CRON_HOUR=$(echo "$CRON_TIME" | cut -d: -f1)
CRON_MINUTE=$(echo "$CRON_TIME" | cut -d: -f2)

# Remove leading zeros
CRON_HOUR=$(echo "$CRON_HOUR" | sed 's/^0//')
CRON_MINUTE=$(echo "$CRON_MINUTE" | sed 's/^0//')

# Check if the script exists and is executable
if [ ! -f "$NIGHTLY_SCRIPT" ]; then
    echo "Error: Nightly script not found at $NIGHTLY_SCRIPT"
    exit 1
fi

if [ ! -x "$NIGHTLY_SCRIPT" ]; then
    echo "Making nightly script executable..."
    chmod +x "$NIGHTLY_SCRIPT"
fi

# Create cron job entry
CRON_ENTRY="$CRON_MINUTE $CRON_HOUR * * * cd $PROJECT_ROOT && $NIGHTLY_SCRIPT >> $PROJECT_ROOT/logs/cron_nightly.log 2>&1"

echo "Setting up cron job for Anthrasite Lead-Factory nightly batch process:"
echo "- Time: $CRON_TIME ($CRON_MINUTE $CRON_HOUR * * *)"
echo "- User: $CRON_USER"
echo "- Command: cd $PROJECT_ROOT && $NIGHTLY_SCRIPT >> $PROJECT_ROOT/logs/cron_nightly.log 2>&1"

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Setup cron job
if [ "$CRON_USER" = "$(whoami)" ]; then
    # Current user - use crontab
    (crontab -l 2>/dev/null | grep -v "$NIGHTLY_SCRIPT" || true; echo "$CRON_ENTRY") | crontab -
    echo "Cron job installed for current user."
else
    # Different user - need sudo
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: You need to run this script as root to set up a cron job for another user."
        exit 1
    fi
    
    (sudo -u "$CRON_USER" crontab -l 2>/dev/null | grep -v "$NIGHTLY_SCRIPT" || true; echo "$CRON_ENTRY") | sudo -u "$CRON_USER" crontab -
    echo "Cron job installed for user $CRON_USER."
fi

# Setup log rotation
LOGROTATE_CONF="/etc/logrotate.d/anthrasite-lead-factory"
if [ "$(id -u)" -eq 0 ]; then
    cat > "$LOGROTATE_CONF" << EOF
$PROJECT_ROOT/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $CRON_USER $CRON_USER
    sharedscripts
    postrotate
        systemctl reload rsyslog >/dev/null 2>&1 || true
    endscript
}
EOF
    echo "Log rotation configuration created at $LOGROTATE_CONF"
else
    cat << EOF
To set up log rotation, run the following as root:

cat > $LOGROTATE_CONF << 'LOGROTATE'
$PROJECT_ROOT/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $CRON_USER $CRON_USER
    sharedscripts
    postrotate
        systemctl reload rsyslog >/dev/null 2>&1 || true
    endscript
}
LOGROTATE
EOF
fi

echo "Cron job setup completed successfully."
echo "The Anthrasite Lead-Factory nightly batch process will run at $CRON_TIME every day."

# Make the script executable
chmod +x "${SCRIPT_DIR}/setup_cron.sh"

exit 0