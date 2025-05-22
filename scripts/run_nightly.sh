#!/bin/bash
# run_nightly.sh - Nightly batch processing script with metrics
#
# Usage: ./run_nightly.sh [--dry-run] [--test-metrics] [--check-supabase]
#
# This script runs the nightly batch processing pipeline for the Anthrasite LeadFactory
# and records metrics for monitoring and alerting.
#
# It ensures the pipeline completes by 05:00 EST and records a timestamp metric
# for alerting if the pipeline runs late.

set -e

# Parse command line arguments
DRY_RUN=false
TEST_METRICS=false
CHECK_SUPABASE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --test-metrics)
      TEST_METRICS=true
      shift
      ;;
    --check-supabase)
      CHECK_SUPABASE=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Load environment variables
if [ -f .env ]; then
  source .env
elif [ -f .env.production ]; then
  source .env.production
fi

# Set up logging
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/nightly_batch_$(date +"%Y%m%d").log"

# Log function
log() {
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1" | tee -a "$LOG_FILE"
}

# Error handling
handle_error() {
  local exit_code=$?
  log "ERROR: Command failed with exit code $exit_code"
  log "Pipeline failed at $(date)"

  # Send alert
  if [ -n "$NOTIFICATION_EMAIL" ]; then
    echo "Pipeline failed at $(date)" | mail -s "ALERT: LeadFactory Pipeline Failed" "$NOTIFICATION_EMAIL"
  fi

  # Record failure metric
  python -c "
import sys
sys.path.append('.')
from bin.metrics import metrics
metrics.batch_completed_timestamp.set(0)  # 0 indicates failure
"

  exit $exit_code
}

# Set up error handling
trap handle_error ERR

# Record start time
START_TIME=$(date +%s)
log "Starting nightly batch processing at $(date)"

# Start batch cost tracking
BATCH_ID="batch_$(date +"%Y%m%d")"
log "Starting cost tracking for batch $BATCH_ID"
python -c "
import sys
sys.path.append('.')
from bin.cost_tracking import cost_tracker
cost_tracker.start_batch('$BATCH_ID', tier='$TIER')
"

# Step 1: Fetch leads
log "Step 1: Fetching leads"
if [ "$DRY_RUN" = "false" ]; then
  python bin/fetch_leads.py --batch-id "$BATCH_ID" --output data/leads_$(date +"%Y%m%d").json
fi

# Step 2: Enrich leads
log "Step 2: Enriching leads"
if [ "$DRY_RUN" = "false" ]; then
  python bin/enrich_with_retention.py --batch-id "$BATCH_ID" --input data/leads_$(date +"%Y%m%d").json --output data/enriched_$(date +"%Y%m%d").json
fi

# Step 3: Score leads
log "Step 3: Scoring leads"
if [ "$DRY_RUN" = "false" ]; then
  python bin/score.py --batch-id "$BATCH_ID" --input data/enriched_$(date +"%Y%m%d").json --output data/scored_$(date +"%Y%m%d").json
fi

# Step 4: Generate mockups
log "Step 4: Generating mockups"
if [ "$MOCKUP_ENABLED" = "true" ]; then
  if [ "$DRY_RUN" = "false" ]; then
    python bin/generate_mockups.py --batch-id "$BATCH_ID" --input data/scored_$(date +"%Y%m%d").json --output data/mockups_$(date +"%Y%m%d")
  fi
else
  log "Mockup generation is disabled, skipping"
fi

# Step 5: Send emails
log "Step 5: Sending emails"
if [ "$DRY_RUN" = "false" ]; then
  python bin/send_emails.py --batch-id "$BATCH_ID" --input data/scored_$(date +"%Y%m%d").json
fi

# Step 6: Update database
log "Step 6: Updating database"
if [ "$DRY_RUN" = "false" ]; then
  python bin/update_database.py --batch-id "$BATCH_ID" --input data/scored_$(date +"%Y%m%d").json
fi

# Step 7: Generate reports
log "Step 7: Generating reports"
if [ "$DRY_RUN" = "false" ]; then
  python bin/generate_reports.py --batch-id "$BATCH_ID" --output reports/$(date +"%Y%m%d")
fi

# Calculate leads processed
if [ "$DRY_RUN" = "false" ]; then
  LEADS_PROCESSED=$(jq length data/scored_$(date +"%Y%m%d").json)
  log "Processed $LEADS_PROCESSED leads"
else
  LEADS_PROCESSED=0
  log "Dry run: No leads processed"
fi

# End batch cost tracking
log "Ending cost tracking for batch $BATCH_ID"
if [ "$DRY_RUN" = "false" ] && [ "$TEST_METRICS" = "false" ]; then
  python -c "
import sys
sys.path.append('.')
from bin.cost_tracking import cost_tracker
cost_tracker.end_batch($LEADS_PROCESSED)
"
fi

# Calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
DURATION_MINUTES=$((DURATION / 60))
log "Pipeline completed in $DURATION_MINUTES minutes"

# Record completion timestamp metric
log "Recording completion timestamp metric"
if [ "$DRY_RUN" = "false" ] || [ "$TEST_METRICS" = "true" ]; then
  python -c "
import sys
import time
sys.path.append('.')
from bin.metrics import metrics
metrics.batch_completed_timestamp.set(time.time())
metrics.observe_batch_duration($DURATION)
"
fi

# Check if completed before 05:00 EST
CURRENT_HOUR=$(TZ="America/New_York" date +"%H")
CURRENT_MINUTE=$(TZ="America/New_York" date +"%M")
if [ "$CURRENT_HOUR" -gt 5 ] || [ "$CURRENT_HOUR" -eq 5 -a "$CURRENT_MINUTE" -gt 0 ]; then
  log "WARNING: Pipeline completed after 05:00 EST"
  
  # Send alert
  if [ -n "$NOTIFICATION_EMAIL" ] && [ "$DRY_RUN" = "false" ]; then
    echo "Pipeline completed at $(TZ="America/New_York" date +"%H:%M") EST, which is after the 05:00 EST deadline" | mail -s "ALERT: LeadFactory Pipeline Late" "$NOTIFICATION_EMAIL"
  fi
else
  log "Pipeline completed before 05:00 EST deadline"
fi

# Run Supabase usage monitoring
log "Checking Supabase usage"
if [ "$DRY_RUN" = "false" ] || [ "$CHECK_SUPABASE" = "true" ]; then
  python scripts/monitor_supabase_usage.py --alert-threshold 80
fi

log "Nightly batch processing completed successfully at $(date)"
exit 0
