#!/bin/bash
#
# test_health_check_threshold.sh - Test script for health check failover threshold
#
# This script tests the health check failover mechanism with the new threshold value
# of 2 consecutive failures as specified in the Phase 0 "Lead-Factory" spec v1.3.
#

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOG_DIR}/test_health_check_${TIMESTAMP}.log"
HEALTH_CHECK_SCRIPT="${PROJECT_ROOT}/bin/health_check.sh"
TEST_CONFIG_FILE="${PROJECT_ROOT}/tests/test_health_check_config.yml"
TEST_STATE_FILE="${PROJECT_ROOT}/tests/test_health_check_state.json"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
  local level="$1"
  local message="$2"
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Function to create a mock health check endpoint
create_mock_endpoint() {
  local port="$1"
  local status="$2"

  # Create a simple HTTP server using Python
  python3 -c "
import http.server
import socketserver
import sys

class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response($status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"status\": \"$status\"}')

    def log_message(self, format, *args):
        # Suppress log messages
        return

try:
    with socketserver.TCPServer(('localhost', $port), MockHandler) as httpd:
        print('Mock server running at port $port with status $status')
        httpd.serve_forever()
except KeyboardInterrupt:
    print('Server stopped')
except OSError as e:
    print(f'Error: {e}')
    sys.exit(1)
" &

  # Store the PID of the Python server
  echo $! > /tmp/mock_server_$port.pid

  # Give the server a moment to start
  sleep 1

  log "INFO" "Started mock endpoint on port $port with status $status"
}

# Function to stop the mock endpoint
stop_mock_endpoint() {
  local port="$1"

  if [ -f "/tmp/mock_server_$port.pid" ]; then
    local pid=$(cat "/tmp/mock_server_$port.pid")
    kill $pid 2>/dev/null || true
    rm "/tmp/mock_server_$port.pid"
    log "INFO" "Stopped mock endpoint on port $port"
  fi
}

# Function to create a test configuration file
create_test_config() {
  local port="$1"

  cat > "$TEST_CONFIG_FILE" << EOF
# Test health check configuration
health_check:
  # Primary instance details
  primary:
    url: http://localhost:$port/health
    expected_status: 200
    timeout: 2  # seconds

  # Failure threshold - set to 2 consecutive failures per Phase 0 v1.3 spec
  failure_threshold: 2

  # Backup instance details (mock for testing)
  backup:
    host: localhost
    user: $(whoami)
    port: 22
    key_file: ~/.ssh/id_rsa
    docker_compose_path: /tmp/test_docker_compose.yml

  # Notification settings (disabled for testing)
  notify:
    email: ""
    slack_webhook: ""
EOF

  log "INFO" "Created test configuration file at $TEST_CONFIG_FILE"
}

# Function to create a test state file
create_test_state() {
  local failures="$1"

  cat > "$TEST_STATE_FILE" << EOF
{
  "last_check": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "consecutive_failures": $failures,
  "last_status": "$([ $failures -eq 0 ] && echo "success" || echo "failure")",
  "last_boot": "$(date -u -v-1d +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

  log "INFO" "Created test state file with $failures failures"
}

# Function to run the health check script with test configuration
run_health_check() {
  log "INFO" "Running health check script with test configuration"

  # Run the health check script with test configuration
  $HEALTH_CHECK_SCRIPT --config="$TEST_CONFIG_FILE" --check-only --verbose 2>&1 | tee -a "$LOG_FILE"

  # Get the exit code
  local exit_code=${PIPESTATUS[0]}

  log "INFO" "Health check script exited with code $exit_code"
  return $exit_code
}

# Function to check the state file for consecutive failures
check_state_failures() {
  local expected_failures="$1"

  if [ -f "$TEST_STATE_FILE" ]; then
    local failures=$(grep -o '"consecutive_failures": [0-9]*' "$TEST_STATE_FILE" | awk '{print $2}')

    if [ "$failures" -eq "$expected_failures" ]; then
      log "INFO" "State file shows $failures consecutive failures as expected"
      return 0
    else
      log "ERROR" "State file shows $failures consecutive failures, expected $expected_failures"
      return 1
    fi
  else
    log "ERROR" "State file not found"
    return 1
  fi
}

# Function to run a test case
run_test_case() {
  local test_name="$1"
  local initial_failures="$2"
  local endpoint_status="$3"
  local expected_failures="$4"
  local expected_boot="$5"

  log "INFO" "=== Running test case: $test_name ==="

  # Create test state with initial failures
  create_test_state $initial_failures

  # Create mock endpoint with specified status
  create_mock_endpoint 8081 $endpoint_status

  # Create test configuration
  create_test_config 8081

  # Run health check script
  if [ "$expected_boot" = "true" ]; then
    log "INFO" "Expecting boot to be triggered"
    run_health_check || true
  else
    log "INFO" "Not expecting boot to be triggered"
    run_health_check
  fi

  # Check state file for consecutive failures
  check_state_failures $expected_failures
  local state_check_result=$?

  # Stop mock endpoint
  stop_mock_endpoint 8081

  # Return test result
  if [ $state_check_result -eq 0 ]; then
    log "INFO" "Test case passed: $test_name"
    return 0
  else
    log "ERROR" "Test case failed: $test_name"
    return 1
  fi
}

# Function to clean up after tests
cleanup() {
  log "INFO" "Cleaning up test resources"

  # Stop any running mock endpoints
  stop_mock_endpoint 8081

  # Remove test files
  rm -f "$TEST_CONFIG_FILE" "$TEST_STATE_FILE"

  log "INFO" "Cleanup complete"
}

# Register cleanup function to run on exit
trap cleanup EXIT

# Main test function
run_tests() {
  log "INFO" "Starting health check threshold tests"

  # Test case 1: 0 failures + success = 0 failures
  run_test_case "0 failures + success = 0 failures" 0 200 0 false

  # Test case 2: 0 failures + failure = 1 failure
  run_test_case "0 failures + failure = 1 failure" 0 500 1 false

  # Test case 3: 1 failure + failure = 2 failures (should trigger boot)
  run_test_case "1 failure + failure = 2 failures (should trigger boot)" 1 500 2 true

  # Test case 4: 1 failure + success = 0 failures
  run_test_case "1 failure + success = 0 failures" 1 200 0 false

  log "INFO" "All tests completed"
}

# Run the tests
run_tests

log "INFO" "Test script completed"
exit 0
