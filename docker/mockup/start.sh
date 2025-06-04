#!/bin/bash
set -e

# Start Xvfb for headless Chrome
Xvfb :99 -screen 0 1024x768x24 &
XVFB_PID=$!

# Wait for X11 to be ready
sleep 2

# Start the mockup service
echo "Starting mockup service..."
exec python -m leadfactory.pipeline.mockup --service-mode
