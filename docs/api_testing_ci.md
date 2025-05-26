# API Integration Testing in CI

This document explains how API integration tests are configured to run in CI environments for the Anthrasite LeadFactory application.

## Overview

The CI pipeline for API integration tests is designed to:

1. Run tests with mock APIs by default to avoid costs and external dependencies
2. Provide options to run tests with real APIs when needed
3. Collect metrics on API usage, performance, and costs
4. Generate reports for analysis and cost tracking
5. Implement safeguards against excessive API usage

## Workflow Configuration

The API integration tests are configured in the GitHub Actions workflow file:
`.github/workflows/api-integration-tests.yml`

This workflow runs in the following scenarios:

- **On schedule**: Weekly on Sunday at 3am UTC to test with real APIs
- **On push/PR**: When changes are made to pipeline code or test files (using mocks by default)
- **Manual trigger**: On-demand via GitHub Actions UI with configurable options

## Environment Variables

The following environment variables control the behavior of API tests:

| Variable | Description | Default |
|----------|-------------|---------|
| `LEADFACTORY_USE_REAL_APIS` | Enable real API calls | `0` (false) |
| `LEADFACTORY_TEST_APIS` | Comma-separated list of APIs to test | `all` |
| `LEADFACTORY_LOG_API_METRICS` | Enable metrics collection | `1` (true) |
| `LEADFACTORY_LOG_METRICS_TO_FILE` | Log metrics to files | `1` (true) |
| `METRICS_DIR` | Directory for metrics storage | `metrics` |
| `GENERATE_PER_TEST_REPORTS` | Generate individual test reports | `0` (false) |

### API-Specific Variables

For each supported API (Yelp, Google, OpenAI, etc.), you can set:

- `LEADFACTORY_TEST_<API>_API`: Enable testing with this specific API
- `LEADFACTORY_THROTTLE_<API>_API`: Enable rate limiting for this API
- `LEADFACTORY_<API>_RPM`: Requests per minute limit
- `LEADFACTORY_<API>_RPD`: Requests per day limit

## API Keys in CI

API keys are stored as GitHub Secrets and are only used when tests are configured to use real APIs:

- `YELP_API_KEY`
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `SENDGRID_API_KEY`
- `SCREENSHOTONE_API_KEY`
- `ANTHROPIC_API_KEY`

If a key is missing, tests for that API will automatically fall back to mocks.

## Manual Workflow Trigger Options

When manually triggering the workflow, you can configure:

1. **Use real APIs**: Enable real API calls instead of mocks
2. **APIs to test**: Specify which APIs to test (comma-separated)
3. **Generate report**: Enable comprehensive metrics reporting

## Cost Control Measures

The workflow implements several measures to control API costs:

1. **Default to mocks**: Tests use mock APIs by default
2. **API throttling**: Rate limits prevent excessive API calls
3. **Selective API testing**: Option to test only specific APIs
4. **Fail-fast**: Tests stop after first failure to avoid wasting API calls
5. **Cost monitoring**: Tests report estimated costs and alert if thresholds are exceeded
6. **Weekly schedule**: Limits real API testing to once per week

## Reports and Artifacts

The workflow generates several reports as artifacts:

1. **API Metrics Reports**: Detailed logs of API calls, performance, and costs
2. **Cost Report**: Breakdown of API usage and estimated costs
3. **Weekly Report** (scheduled runs only): Summary of API usage over time with visualizations

## Fallback Mechanism

If tests fail with real APIs, the workflow automatically retries with mocks to verify that the test code itself is valid. This helps distinguish between test failures due to API issues versus actual code problems.

## Extending the API Testing Framework

To add support for a new API:

1. Add the API to the `SUPPORTED_APIS` list in `api_test_config.py`
2. Define the API's endpoints in `API_ENDPOINTS`
3. Add appropriate test fixtures and mocks
4. Update CI configuration to include the new API's keys and settings

## Troubleshooting

### Common Issues

1. **API key missing or invalid**: Tests will automatically fall back to mocks
2. **Rate limiting**: Reduce the number of APIs being tested or adjust throttling settings
3. **Cost alerts**: Review the cost report to identify expensive API calls

### Debugging CI Failures

1. Check the API metrics reports to identify which API calls failed
2. Review the cost report to see if budget thresholds were exceeded
3. Examine the test logs for specific error messages
4. If tests fail with real APIs but pass with mocks, the issue is likely with the external API

## Best Practices

1. **Use mocks for development**: Always use mock APIs during local development
2. **Test with real APIs before merging**: Run manual tests with real APIs before merging critical changes
3. **Monitor costs**: Regularly review the weekly reports to track API usage and costs
4. **Update mock responses**: Keep mock responses up-to-date with actual API responses
5. **Add test coverage**: Ensure all API interactions have appropriate test coverage
