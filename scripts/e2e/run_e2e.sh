#!/bin/bash
# E2E Pipeline Execution Script

# Set the E2E environment variables
export E2E_MODE=true
export SKIP_PIPELINE_VALIDATION=true
export SKIP_GOOGLE_MAPS_API=true
export SKIP_SENDGRID_API=true

# Run the pipeline executor with the E2E environment
python3 scripts/e2e/pipeline_executor.py --env .env.e2e "$@"
