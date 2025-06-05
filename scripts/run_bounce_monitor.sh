#!/bin/bash
#
# Bounce Rate Monitoring Cron Script
# Add to crontab: */5 * * * * /opt/leadfactory/scripts/run_bounce_monitor.sh
#

set -e

# Configuration
LEADFACTORY_HOME="/opt/leadfactory"
VENV_PATH="${LEADFACTORY_HOME}/venv"
LOG_DIR="/var/log/leadfactory"
LOG_FILE="${LOG_DIR}/bounce-monitor-cron.log"
PID_FILE="/var/run/leadfactory/bounce-monitor.pid"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"
mkdir -p "$(dirname ${PID_FILE})"

# Source environment
if [ -f "${LEADFACTORY_HOME}/.env" ]; then
    export $(cat "${LEADFACTORY_HOME}/.env" | xargs)
fi

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Change to project directory
cd "${LEADFACTORY_HOME}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "${LOG_FILE}"
}

# Check if monitoring is already running
if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p "${PID}" > /dev/null 2>&1; then
        log "Bounce monitor already running with PID ${PID}"
        exit 0
    else
        log "Removing stale PID file"
        rm -f "${PID_FILE}"
    fi
fi

# Start monitoring
log "Starting bounce rate monitor"

# Run in background and save PID
python -m leadfactory.cli monitoring start-bounce-monitor \
    --interval 300 \
    --daemon \
    >> "${LOG_FILE}" 2>&1 &

MONITOR_PID=$!
echo "${MONITOR_PID}" > "${PID_FILE}"

log "Started bounce monitor with PID ${MONITOR_PID}"

# Check if it started successfully
sleep 2
if ps -p "${MONITOR_PID}" > /dev/null 2>&1; then
    log "Bounce monitor started successfully"
else
    log "ERROR: Bounce monitor failed to start"
    rm -f "${PID_FILE}"
    exit 1
fi
