#!/bin/bash
#
# install_gpu_tracker_service.sh - Install GPU Usage Tracker Service
#
# This script installs the GPU usage tracker as a systemd service.
# It must be run with sudo privileges.
#

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="gpu-usage-tracker"
SERVICE_FILE="${PROJECT_ROOT}/etc/${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file not found at $SERVICE_FILE"
    exit 1
fi

# Copy service file to systemd directory
echo "Installing service file to $SYSTEMD_DIR/$SERVICE_NAME.service"
cp "$SERVICE_FILE" "$SYSTEMD_DIR/"

# Reload systemd
echo "Reloading systemd"
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting $SERVICE_NAME service"
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Check service status
echo "Service status:"
systemctl status "$SERVICE_NAME"

echo "Installation complete. The GPU usage tracker service is now running."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo "View logs with: sudo journalctl -u $SERVICE_NAME"

exit 0
