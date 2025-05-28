#!/bin/bash
# Production Test Pipeline Execution Script
# This runs the pipeline with real APIs but sends all emails to EMAIL_OVERRIDE

echo "=========================================="
echo "Production Test Pipeline"
echo "=========================================="
echo "This will:"
echo "- Use REAL production APIs"
echo "- Scrape REAL business data"
echo "- Generate REAL mockups and emails"
echo "- Send ALL emails to EMAIL_OVERRIDE address"
echo ""

# Check if we have real API keys
if grep -q "YOUR_" .env.prod_test; then
    echo "ERROR: Please update .env.prod_test with your real API keys"
    echo "Replace all YOUR_* placeholders with actual API keys"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env.prod_test | xargs)

# Show where emails will go
EMAIL_OVERRIDE=$(grep EMAIL_OVERRIDE .env.prod_test | cut -d'=' -f2)
echo "All emails will be sent to: $EMAIL_OVERRIDE"
echo ""
read -p "Continue with production test? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Production test cancelled"
    exit 0
fi

# Set production test parameters
echo ""
echo "Running production test pipeline..."
echo "Using ZIP: 10001 (New York, NY)"
echo "Using Vertical: HVAC"
echo "Limiting to: 3 businesses"
echo ""

# Run the full pipeline with production test environment
python3 scripts/e2e/pipeline_executor.py --env .env.prod_test "$@"
