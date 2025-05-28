# Production Test Pipeline

This allows you to run a REAL test of the LeadFactory pipeline using production APIs but with safety measures in place.

## What it does:

1. **Uses REAL APIs**: OpenAI, Google Maps, SendGrid, Yelp, etc.
2. **Scrapes REAL business data**: From Yelp for actual restaurants in New York (ZIP 10001)
3. **Generates REAL content**: Uses OpenAI to create personalized emails
4. **Sends REAL emails**: But ALL emails go to the EMAIL_OVERRIDE address (charlie@anthrasite.io)

## Safety Features:

- **EMAIL_OVERRIDE**: All emails are redirected to your address instead of the actual businesses
- **Limited scope**: Only processes 3 businesses (controlled in the wrapper script)
- **Specific vertical**: Tests with "restaurants" vertical
- **Specific ZIP**: Uses New York ZIP code 10001

## How to run:

```bash
# Make sure Docker is running for the database
docker-compose up -d

# Run the production test
./scripts/e2e/run_prod_test.sh
```

## What to expect:

1. The pipeline will:
   - Run preflight checks
   - Scrape 3 restaurants from Yelp in ZIP 10001
   - Generate screenshots of their websites
   - Create mockups showing their sites on different devices
   - Generate personalized marketing emails
   - Send all 3 emails to charlie@anthrasite.io

2. You should receive 3 real emails at charlie@anthrasite.io with:
   - Personalized content for each restaurant
   - Mockup images attached
   - Professional formatting

## Files involved:

- `.env.prod_test`: Production test environment configuration
- `scripts/e2e/run_prod_test.sh`: Runner script
- `scripts/pipeline/01_scrape.py`: Modified to detect PRODUCTION_TEST_MODE

## Logs:

Check `logs/` directory for detailed execution logs.

## Cost:

This will use real API calls, so there will be minimal costs:
- OpenAI API: ~$0.01-0.02 for email generation
- Yelp API: Free tier should cover it
- SendGrid: 3 emails from your quota
- Google Maps: Minimal geocoding costs
