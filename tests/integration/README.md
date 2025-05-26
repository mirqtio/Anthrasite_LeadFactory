# API Integration Tests

This directory contains integration tests for external API services used by Anthrasite LeadFactory.

## Test Configuration

The tests can be run in two modes:
1. **Mock Mode** (default): Uses mock API responses for fast, reliable testing without incurring costs
2. **Real API Mode**: Makes actual API calls to test real-world integrations

### Command Line Options

The following command line options control test behavior:

- `--use-real-apis`: Enable real API calls instead of using mocks
- `--apis=<list>`: Comma-separated list of APIs to test with real calls (options: yelp,google,openai,sendgrid,screenshotone,anthropic,mapbox,stripe,twilio)
- `--log-metrics`: Log API metrics to file for analysis
- `--metrics-dir=<path>`: Directory to store metrics data (default: 'metrics')
- `--generate-report`: Generate comprehensive API metrics report after tests complete
- `--throttle-apis`: Enable API throttling to respect rate limits

### Environment Variables

You can also set environment variables to control test behavior:

- `LEADFACTORY_USE_REAL_APIS=1`: Enable real API calls (equivalent to `--use-real-apis`)
- `LEADFACTORY_TEST_APIS=all|none|api1,api2,...`: Specify which APIs to test (default: all)
- `LEADFACTORY_TEST_YELP_API=1`: Test Yelp API with real calls
- `LEADFACTORY_TEST_GOOGLE_API=1`: Test Google API with real calls
- `LEADFACTORY_TEST_OPENAI_API=1`: Test OpenAI API with real calls
- `LEADFACTORY_TEST_SENDGRID_API=1`: Test SendGrid API with real calls
- `LEADFACTORY_TEST_SCREENSHOTONE_API=1`: Test ScreenshotOne API with real calls
- `LEADFACTORY_TEST_ANTHROPIC_API=1`: Test Anthropic API with real calls
- `LEADFACTORY_LOG_API_METRICS=1`: Log API metrics to file (equivalent to `--log-metrics`)
- `LEADFACTORY_LOG_METRICS_TO_FILE=1`: Log metrics to files (default: true)
- `LEADFACTORY_LOG_METRICS_TO_PROMETHEUS=1`: Log metrics to Prometheus if available (default: true)
- `METRICS_DIR=path/to/dir`: Directory to store metrics data (default: 'metrics')
- `GENERATE_PER_TEST_REPORTS=1`: Generate separate reports for each test (default: false)

#### API Throttling Environment Variables

- `LEADFACTORY_THROTTLE_YELP_API=1`: Enable throttling for Yelp API
- `LEADFACTORY_YELP_RPM=60`: Set requests per minute for Yelp API
- `LEADFACTORY_YELP_RPD=1000`: Set requests per day for Yelp API

(Similar throttling variables can be set for each API)

### API Keys

For real API testing, you need to set the following API keys in your environment:

- `YELP_API_KEY`: Yelp Fusion API key
- `GOOGLE_API_KEY`: Google Places API key
- `OPENAI_API_KEY`: OpenAI API key
- `SENDGRID_API_KEY`: SendGrid API key
- `SCREENSHOTONE_API_KEY`: ScreenshotOne API key
- `ANTHROPIC_API_KEY`: Anthropic API key (for Claude fallback)

## Running Tests

### Mock Mode (Default)

```bash
# Run all integration tests with mocks
pytest tests/integration

# Run specific test file with mocks
pytest tests/integration/test_pipeline_stages.py
```

### Real API Mode

```bash
# Test all APIs with real calls
pytest tests/integration --use-real-apis

# Test only specific APIs with real calls
pytest tests/integration --use-real-apis --apis=yelp,google

# Run specific test file with real APIs and log metrics
pytest tests/integration/test_pipeline_stages.py --use-real-apis --log-metrics

# Run tests with metrics and generate comprehensive report
pytest tests/integration --use-real-apis --log-metrics --generate-report

# Run tests with API throttling to respect rate limits
pytest tests/integration --use-real-apis --throttle-apis

# Specify custom metrics directory
pytest tests/integration --log-metrics --metrics-dir=./reports/api_metrics
```

## Test Markers

You can use the following markers to control which tests run with real APIs:

- `@pytest.mark.real_api`: Test requires real API connection
- `@pytest.mark.mock_only`: Test only works with mocks
- `@pytest.mark.api_metrics`: Test includes detailed API metrics collection
- `@pytest.mark.pipeline`: Test involves the full pipeline integration

Example:

```python
@pytest.mark.real_api
def test_yelp_api_live_connection():
    # This test will be skipped unless --use-real-apis is specified
    ...

@pytest.mark.mock_only
def test_with_specific_mock_response():
    # This test will be skipped if --use-real-apis is specified
    ...
```

## Enhanced Metrics System

### Metrics Logging

When `--log-metrics` is enabled, API metrics are logged with the following information:

- API name and endpoint
- Request time (seconds)
- Success/failure status
- Status code (for HTTP APIs)
- Cost (USD, calculated for relevant APIs)
- Token usage (for LLM APIs)
- Request metadata
- Test context

Metrics are stored in JSONL format in the specified metrics directory, with each test run creating a new file.

### Metrics Reporting

When `--generate-report` is enabled, comprehensive reports are generated after test completion:

- **JSON Report**: Complete metrics data in structured JSON format
- **CSV Report**: Tabular data for import into spreadsheets or data analysis tools
- **HTML Report**: Visual report with charts and tables showing API performance

Reports include:

- Summary statistics (total calls, success rates, average response times)
- Per-API metrics (call counts, token usage, estimated costs)
- Response time distributions
- Cost breakdowns by API provider

### Automated Metrics Collection

The metrics system automatically wraps API calls to collect data without requiring manual instrumentation:

```python
# Example of automatic metrics collection using the decorator
@api_metric_decorator("openai", "chat_completion")
def call_openai_api(prompt):
    # Function implementation
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
    return response
```

### Metrics Analysis

After running tests, you can analyze the collected metrics to:

1. **Optimize API Usage**: Identify expensive or slow API calls
2. **Monitor Costs**: Track estimated API expenses for budgeting
3. **Detect Performance Issues**: Identify APIs with high latency or error rates
4. **Validate Rate Limiting**: Ensure API throttling is working correctly

### Terminal Reporting

After test completion, a summary of API metrics is displayed in the terminal:

```
================ API Metrics Summary ================
Total API Calls: 42
Overall Success Rate: 97.6%
Average Response Time: 235.42 ms
Total Estimated Cost: $0.0582

---------------- Per-API Statistics ----------------

OPENAI API:
  Calls: 15
  Success Rate: 100.0%
  Avg Response Time: 512.34 ms
  Estimated Cost: $0.0450
  Total Tokens: 2250

YELP API:
  Calls: 18
  Success Rate: 94.4%
  Avg Response Time: 124.56 ms
```

### Integration with Prometheus

If Prometheus metrics collection is available in your environment, API metrics are automatically exported to the following metrics:

- `api_latency_seconds`: Histogram of API response times
- `api_cost_dollars_total`: Counter for total API costs
- `api_calls_total`: Counter for total API calls by status

This allows you to build dashboards and alerts around API usage.
