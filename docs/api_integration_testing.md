# API Integration Testing Guide

This document provides guidance on running and maintaining the API integration tests for the Anthrasite Lead-Factory project.

## Overview

The Lead-Factory codebase interacts with several external APIs:

- **Yelp Fusion API**: For business discovery and details
- **Google Places API**: For location data and business information
- **ScreenshotOne API**: For capturing website screenshots
- **OpenAI API**: For AI-powered content generation and analysis
- **SendGrid API**: For email delivery

The integration test suite allows testing these API integrations with both mock implementations (for CI and development) and real API calls (for validation and comprehensive testing).

## Running API Integration Tests

### Using the Test Runner Script

The easiest way to run API integration tests is using the provided runner script:

```bash
# Run with mock APIs (default)
python tests/run_api_integration_tests.py

# Run with real APIs where credentials are available
python tests/run_api_integration_tests.py --use-real-apis

# Run tests for a specific API only
python tests/run_api_integration_tests.py --api=yelp
python tests/run_api_integration_tests.py --api=openai --use-real-apis
```

### Using pytest Directly

You can also run the tests directly with pytest:

```bash
# Run with mock APIs (default)
pytest -xvs tests/integration/test_api_integrations.py

# Run with real APIs where credentials are available
LEADFACTORY_USE_REAL_APIS=1 pytest -xvs -m real_api tests/integration/test_api_integrations.py
```

## API Credentials

To run tests with real APIs, you need to provide valid API credentials in your `.env` file:

```
# Yelp Fusion API
YELP_KEY=your_yelp_fusion_api_key_here

# Google Places API
GOOGLE_KEY=your_google_places_api_key_here

# ScreenshotOne API
SCREENSHOT_ONE_KEY=your_screenshotone_api_key_here

# SendGrid Email API
SENDGRID_KEY=your_sendgrid_api_key_here
SENDGRID_FROM_EMAIL=outreach@anthrasite.com

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here
```

You can obtain these API keys from their respective services:

- [Yelp Fusion API](https://www.yelp.com/developers/documentation/v3/authentication)
- [Google Places API](https://developers.google.com/maps/documentation/places/web-service/get-api-key)
- [ScreenshotOne API](https://screenshotone.com/)
- [SendGrid API](https://sendgrid.com/docs/ui/account-and-settings/api-keys/)
- [OpenAI API](https://platform.openai.com/account/api-keys)

## Test Architecture

### Mock vs. Real API Testing

The test suite is designed to work with both mock and real APIs:

- **Mock APIs**: Used for CI pipelines, local development, and testing without API credentials
- **Real APIs**: Used for validation, comprehensive testing, and ensuring real-world compatibility

### Configuration

The `APITestConfig` class in `tests/integration/api_test_config.py` controls whether to use real or mock APIs based on:

1. Environment variable `LEADFACTORY_USE_REAL_APIS`
2. Presence of API-specific credentials
3. Test markers (real_api vs. mock_api)

### Metrics Collection

The test suite includes metrics collection for API calls:

- Response time
- Success/failure rate
- API-specific metrics (e.g., token usage for OpenAI)

These metrics are logged to `logs/api_metrics.log` during test execution.

## Adding New API Tests

When adding tests for a new API:

1. Create mock implementations in `tests/mocks/`
2. Add real API client in `leadfactory/utils/apis/`
3. Add test fixtures in `tests/conftest.py`
4. Add test cases in `tests/integration/test_api_integrations.py`
5. Register the API in `tests/integration/api_test_config.py`

## CI Integration

In CI environments, tests automatically use mock APIs regardless of configuration to:

- Avoid exposing API credentials
- Prevent unexpected costs
- Ensure consistent test behavior

## Troubleshooting

### Common Issues

- **API Rate Limits**: Some APIs have rate limits that can cause tests to fail if exceeded
- **API Changes**: External API changes may require updating tests or mock responses
- **Authentication Errors**: Check that your API keys are correct and have the necessary permissions

### Debugging

For detailed logging during API tests:

```bash
LEADFACTORY_DEBUG_API_CALLS=1 python tests/run_api_integration_tests.py --use-real-apis
```

## Maintenance

Regular maintenance of API tests is important:

1. Review and update mock responses to match current API behaviors
2. Verify real API tests continue to work with the latest API versions
3. Monitor API costs and usage during testing
4. Update documentation when API endpoints or requirements change
