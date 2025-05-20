#!/bin/bash
#
# run_nightly.sh - Nightly batch script for Anthrasite Lead-Factory
#
# This script orchestrates the execution of all pipeline stages in sequence.
# It aborts on the first non-zero exit code and logs all activity.
#
# Usage: ./run_nightly.sh [--debug] [--skip-stage=<stage_number>]
#
# Options:
#   --debug             Enable debug mode with verbose output
#   --skip-stage=N      Skip stage N (1-6)
#   --limit=N           Limit the number of leads processed in each stage
#   --dry-run           Run without making external API calls or sending emails
#   --help              Display this help message

set -e  # Exit immediately if a command exits with a non-zero status

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOG_DIR}/nightly_${TIMESTAMP}.log"
METRICS_FILE="${LOG_DIR}/metrics_${TIMESTAMP}.json"
PYTHON_CMD="python"
VENV_DIR="${PROJECT_ROOT}/.venv"

# Default options
DEBUG=false
DRY_RUN=false
SKIP_STAGES=()
LEAD_LIMIT=""

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Function to log metrics
log_metric() {
    local stage="$1"
    local status="$2"
    local duration="$3"
    local count="$4"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    
    # Create metrics file if it doesn't exist
    if [ ! -f "$METRICS_FILE" ]; then
        echo '{"metrics":[]}' > "$METRICS_FILE"
    fi
    
    # Add metric to JSON file
    local tmp_file="${METRICS_FILE}.tmp"
    jq ".metrics += [{\"timestamp\": \"$timestamp\", \"stage\": \"$stage\", \"status\": \"$status\", \"duration_seconds\": $duration, \"count\": $count}]" "$METRICS_FILE" > "$tmp_file"
    mv "$tmp_file" "$METRICS_FILE"
}

# Function to run a pipeline stage
run_stage() {
    local stage_num="$1"
    local stage_name="$2"
    local script="$3"
    local args="$4"
    
    # Check if stage should be skipped
    if [[ " ${SKIP_STAGES[@]} " =~ " ${stage_num} " ]]; then
        log "INFO" "Skipping stage $stage_num: $stage_name"
        return 0
    fi
    
    log "INFO" "Starting stage $stage_num: $stage_name"
    
    # Measure execution time
    local start_time=$(date +%s)
    
    # Run the script
    if [ "$DEBUG" = true ]; then
        log "DEBUG" "Running: $PYTHON_CMD $script $args"
    fi
    
    local count=0
    local status="success"
    
    if [ "$DRY_RUN" = true ] && [ "$stage_num" != "1" ]; then
        # In dry-run mode, don't actually run stages 2-6 except with --dry-run flag
        log "INFO" "DRY RUN: Would execute $PYTHON_CMD $script $args"
        sleep 2  # Simulate some processing time
    else
        # Actually run the command
        if ! output=$($PYTHON_CMD "$script" $args 2>&1); then
            status="failed"
            log "ERROR" "Stage $stage_num failed with exit code $?"
            log "ERROR" "$output"
            log_metric "$stage_name" "$status" $(($(date +%s) - start_time)) $count
            exit 1
        fi
        
        # Extract count of processed items if available
        if [[ $output =~ Processed\ ([0-9]+)\ items ]]; then
            count=${BASH_REMATCH[1]}
        fi
        
        log "INFO" "$output"
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log "INFO" "Completed stage $stage_num: $stage_name in $duration seconds"
    log_metric "$stage_name" "$status" $duration $count
    
    return 0
}

# Function to display help
show_help() {
    cat << EOF
Usage: ./run_nightly.sh [OPTIONS]

Nightly batch script for Anthrasite Lead-Factory that orchestrates the execution
of all pipeline stages in sequence.

Options:
  --debug             Enable debug mode with verbose output
  --skip-stage=N      Skip stage N (1-6)
  --limit=N           Limit the number of leads processed in each stage
  --dry-run           Run without making external API calls or sending emails
  --help              Display this help message

Examples:
  ./run_nightly.sh --debug
  ./run_nightly.sh --skip-stage=3 --limit=10
  ./run_nightly.sh --dry-run

Exit codes:
  0 - Success
  1 - Error in one of the pipeline stages
  2 - Invalid arguments
EOF
    exit 0
}

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --debug)
            DEBUG=true
            ;;
        --skip-stage=*)
            SKIP_STAGES+=(${arg#*=})
            ;;
        --limit=*)
            LEAD_LIMIT="--limit=${arg#*=}"
            ;;
        --dry-run)
            DRY_RUN=true
            LEAD_LIMIT="--limit=5"  # Default limit for dry runs
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

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    log "INFO" "Activating virtual environment"
    source "${VENV_DIR}/bin/activate"
    PYTHON_CMD="${VENV_DIR}/bin/python"
fi

# Load environment variables
if [ -f "${PROJECT_ROOT}/.env" ]; then
    log "INFO" "Loading environment variables from .env"
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
else
    log "WARNING" "No .env file found, using system environment variables"
fi

# Log script start
log "INFO" "Starting Anthrasite Lead-Factory nightly batch process"
log "INFO" "Project root: $PROJECT_ROOT"
log "INFO" "Log file: $LOG_FILE"

if [ "$DEBUG" = true ]; then
    log "DEBUG" "Debug mode enabled"
fi

if [ "$DRY_RUN" = true ]; then
    log "INFO" "DRY RUN mode enabled - no external API calls or emails will be sent"
fi

# Common args for all stages
COMMON_ARGS=""
if [ "$DEBUG" = true ]; then
    COMMON_ARGS="$COMMON_ARGS --verbose"
fi
if [ "$DRY_RUN" = true ]; then
    COMMON_ARGS="$COMMON_ARGS --dry-run"
fi
if [ ! -z "$LEAD_LIMIT" ]; then
    COMMON_ARGS="$COMMON_ARGS $LEAD_LIMIT"
fi

# Run all pipeline stages in sequence
run_stage 1 "Scraping" "${SCRIPT_DIR}/01_scrape.py" "$COMMON_ARGS"
run_stage 2 "Enrichment" "${SCRIPT_DIR}/02_enrich.py" "$COMMON_ARGS"
run_stage 3 "Deduplication" "${SCRIPT_DIR}/03_dedupe.py" "$COMMON_ARGS"
run_stage 4 "Scoring" "${SCRIPT_DIR}/04_score.py" "$COMMON_ARGS"
run_stage 5 "Mockup Generation" "${SCRIPT_DIR}/05_mockup.py" "$COMMON_ARGS"
run_stage 6 "Email Queue" "${SCRIPT_DIR}/06_email_queue.py" "$COMMON_ARGS"

# Log completion
log "INFO" "Nightly batch process completed successfully"

# Make the script executable
chmod +x "${SCRIPT_DIR}/run_nightly.sh"

exit 0