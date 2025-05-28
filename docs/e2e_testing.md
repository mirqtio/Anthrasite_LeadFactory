# E2E Pipeline Validation Guide

This document provides instructions for running the end-to-end (E2E) validation of the LeadFactory pipeline, including real API integration and email delivery.

## Prerequisites

Before running the E2E test, ensure you have:

1. Access to all required API keys:
   - SendGrid API key
   - ScreenshotOne API key
   - OpenAI API key
   - Yelp Fusion API key
   - Google Places API key

2. A test email address to receive the test emails (configured as `EMAIL_OVERRIDE`)

3. Python environment with all dependencies installed

## Configuration

1. Configure the `.env.e2e` file with real API keys:

```
# Essential environment variables for E2E testing
EMAIL_OVERRIDE=your-test-email@example.com
SENDGRID_API_KEY=your_sendgrid_api_key
SCREENSHOT_ONE_API_KEY=your_screenshotone_api_key
OPENAI_API_KEY=your_openai_api_key
YELP_API_KEY=your_yelp_api_key
GOOGLE_API_KEY=your_google_api_key
MOCKUP_ENABLED=true
```

**IMPORTANT**: The `.env.e2e` file contains sensitive API keys and should NEVER be committed to version control.

## Running the E2E Test

To run the full E2E test:

```bash
python scripts/run_e2e_test.py
```

This script will:
1. Verify your `.env.e2e` configuration
2. Execute the BDD scenario that tests the full pipeline
3. Generate and display the test summary

## Test Validation

After running the test, verify the following:

1. **Email Delivery**:
   - Check the email address specified in `EMAIL_OVERRIDE` for the test email
   - Verify that the email contains the correct mockup image
   - Confirm that personalization is applied correctly
   - Verify the CAN-SPAM footer is present and valid

2. **Test Summary**:
   - Review the `e2e_summary.md` file generated in the project root
   - Confirm it contains:
     - Number of leads processed
     - API costs incurred
     - Paths to generated assets
     - Email content preview
     - SendGrid message ID

3. **Database Verification**:
   - The test automatically checks that a row was added to the `emails` table
   - Confirms the SendGrid API returned a 202 status code

## Troubleshooting

If the test fails, check:

1. **API Key Issues**:
   - Verify all API keys in `.env.e2e` are valid and have the necessary permissions
   - Check for any API usage limits or restrictions

2. **Email Delivery Issues**:
   - Verify the SendGrid API key has send permissions
   - Check spam folders for the test email
   - Verify the `EMAIL_OVERRIDE` address is correctly formatted

3. **Mockup Generation Issues**:
   - Ensure `MOCKUP_ENABLED=true` is set in the environment
   - Check that the ScreenshotOne API key is valid

## Notes

- The E2E test uses real API calls which may incur costs
- All external emails are redirected to the `EMAIL_OVERRIDE` address
- This test should be run manually, not in CI environments
- If a test fails, check the logs for detailed error information
