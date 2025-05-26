# Anthrasite Lead-Factory

![CI](https://github.com/anthrasite/lead-factory/actions/workflows/ci.yml/badge.svg)

A pipeline for automatically scraping, enriching, scoring, and reaching out to SMB leads with positive unit economics.

## Project Overview

Anthrasite Lead-Factory is an automated pipeline designed to validate that Anthrasite can:

1. Scrape & enrich SMB leads overnight
2. Deduplicate, score, generate mock-ups, and personalize email
3. Send high-deliverability outreach
4. Hand warm replies to 1-3 pilot agencies with positive unit economics

The pipeline operates on a nightly batch process, processing leads from three verticals (HVAC, Plumbers, Vets) across three metro areas (NY 10002, WA 98908, Carmel IN).

## Pipeline Stages

The pipeline consists of six sequential stages:

1. **Scraping** (`leadfactory.pipeline.scrape`): Fetches business listings from Yelp Fusion and Google Places APIs.
2. **Enrichment** (`leadfactory.pipeline.enrich`): Analyzes websites for tech stack and Core Web Vitals, with tier-based additional enrichment.
3. **Deduplication** (`leadfactory.pipeline.dedupe`): Uses Ollama Llama-3 8B to identify and merge duplicate leads.
4. **Scoring** (`leadfactory.pipeline.score`): Applies YAML-defined rules to score leads based on their features.
5. **Mock-up Generation** (`leadfactory.pipeline.mockup`): Creates website improvement mock-ups using GPT-4o (with Claude fallback).
6. **Email Queueing** (`leadfactory.pipeline.email_queue`): Sends personalized outreach via SendGrid.

Additional components include:

- **Cost Management** (`leadfactory.cost.*`): Budget gating, auditing, and cost tracking.
- **Utilities** (`leadfactory.utils.*`): Metrics, logging, and other support functions.

## Environment Configuration

The project uses environment variables for configuration. These are managed through `.env` files:

### Environment File Structure

- **`.env.example`**: Template with all possible configuration options. This file is committed to the repository.
- **`.env`**: Main configuration file for local development. Contains real or mock API keys.
- **`.env.production`**: Production environment configuration. Used in production deployments.

### Setting Up Your Environment

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys and configuration values. Required API keys include:
   - Yelp Fusion API (YELP_API_KEY or YELP_KEY)
   - Google Places API (GOOGLE_API_KEY or GOOGLE_KEY)
   - OpenAI API (OPENAI_API_KEY)
   - SendGrid API (SENDGRID_API_KEY or SENDGRID_KEY)
   - ScreenshotOne API (SCREENSHOT_ONE_API_KEY or SCREENSHOT_ONE_KEY) - for Tier 2+
   - Anthropic API (ANTHROPIC_API_KEY) - optional, used as fallback

3. For production deployment, create a `.env.production` file with production settings:
   ```bash
   cp .env.example .env.production
   # Edit .env.production with production values
   ```

### Testing API Integrations

To validate your API configuration and ensure all integrations work correctly:

```bash
python tests/validate_real_api_integration_fixed.py
```

This script will check if all required API keys are available and make test API calls to verify connectivity.

### Feature Flags

Key feature flags include:

- `MOCKUP_ENABLED`: Set to `true` to enable mockup generation (Tier 2+)
- `DEBUG_MODE`: Set to `true` for additional debug logging
- `TEST_MODE`: Set to `true` to use mock data in development
- `USE_MOCKS`: Set to `true` to skip real API calls

For more details on environment configuration, see [API Integration Testing](docs/api_integration_testing.md).

### Important Note on Environment Variables

When using Python's `dotenv` library, system environment variables take precedence over values in `.env` files by default. If you have conflicting environment variables set in your system, they will override values in your `.env` file.

In scripts that need to ensure `.env` file values are used regardless of system environment:

```python
from dotenv import load_dotenv
# Force .env values to override system environment variables
load_dotenv(override=True)
```
- **Utilities** (`leadfactory.utils.*`): Metrics, logging, and other support functions.

## Setup Instructions

### Prerequisites

- Python 3.10+
- Docker (for containerized deployment)
- Supabase account (for storage and database)
- Ollama with Llama-3 8B model
- API keys for: Yelp Fusion, Google Places, ScreenshotOne, PageSpeed, SEMrush, SendGrid, OpenAI, Anthropic

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/mirqtio/Anthrasite_LeadFactory.git
   cd Anthrasite_LeadFactory
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the package and dependencies:
   ```bash
   # For development installation with all tools
   pip install -e ".[dev]"

   # For metrics-only installation
   pip install -e ".[metrics]"

   # For basic installation
   pip install -e .
   ```

4. For development only - install pre-commit hooks:
   ```bash
   pre-commit install
   ```

5. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. Initialize the database:
   ```bash
   sqlite3 leadfactory.db < db/migrations/2025-05-19_init.sql
   ```

6. Seed initial data:
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('leadfactory.db'); c = conn.cursor(); c.execute('INSERT INTO zip_queue (zip, metro, done) VALUES (\"10002\", \"New York\", 0), (\"98908\", \"Yakima\", 0), (\"46032\", \"Carmel\", 0)'); conn.commit()"
   ```

### Configuration

The pipeline is configured through environment variables defined in the `.env` file. Key configuration options include:

- **Tier Level**: Set `TIER=1|2|3` to control the depth of enrichment:
  - Tier 1: Basic tech stack and Core Web Vitals
  - Tier 2: Adds screenshots
  - Tier 3: Adds SEMrush Site Audit

- **Mock-up Generation**: Set `MOCKUP_ENABLED=true|false` to toggle mock-up generation (false for Tier-1 control group, true for Tier-2/3).

- **AI Models**: Configure OpenAI (GPT-4o), Anthropic (Claude), and Ollama (Llama-3 8B) settings.

- **Alert Thresholds**: Set thresholds for bounce rates, spam rates, and cost per lead.

See `.env.example` for the complete list of configuration options.

## Usage

### Running Individual Pipeline Stages

Each pipeline stage can be run independently:

```bash
# Scrape leads (limit to 5 for testing)
python bin/01_scrape.py --limit 5

# Enrich leads
python bin/02_enrich.py

# Deduplicate leads
python bin/03_dedupe.py

# Score leads
python bin/04_score.py

# Generate mock-ups
python bin/05_mockup.py

# Queue emails
python bin/06_email_queue.py
```

### Running the Complete Pipeline

To run the complete pipeline as a nightly batch:

```bash
bash bin/run_nightly.sh
```

This will execute all pipeline stages in sequence, aborting on the first non-zero exit code.

#### Command-line Options

The nightly batch script supports several command-line options:

```bash
# Run in debug mode with verbose output
bin/run_nightly.sh --debug

# Skip specific pipeline stages
bin/run_nightly.sh --skip-stage=3 --skip-stage=5

# Limit the number of leads processed
bin/run_nightly.sh --limit=10

# Run in dry-run mode (no external API calls or emails)
bin/run_nightly.sh --dry-run

# Show help message
bin/run_nightly.sh --help
```

#### Setting Up as a Cron Job

To schedule the pipeline to run automatically every night, use the provided setup script:

```bash
# Set up with default settings (runs at 1:00 AM)
bin/setup_cron.sh

# Set a custom time (e.g., 2:30 AM)
bin/setup_cron.sh --time=02:30

# Set up for a different user
bin/setup_cron.sh --user=anthrasite --time=03:15
```

This will configure:
1. A cron job to run the pipeline at the specified time
2. Log rotation to manage log files
3. Proper error handling and notification

Logs for the cron job will be stored in `logs/cron_nightly.log`.

### Monitoring

The pipeline exports Prometheus metrics on port 9090 (configurable via `PROMETHEUS_PORT`). Key metrics include:

- `leads_scraped_total`: Counter of total leads scraped
- `batch_runtime_seconds`: Gauge of batch processing time
- `leadfactory_cpu_hours_per_lead`: Gauge of CPU usage per lead
- `pipeline_failure_rate`: Counter tracking pipeline failures

These metrics can be visualized in Grafana Cloud with the provided alert rules.

### Large-Scale Validation

The pipeline includes comprehensive large-scale validation tests that verify its ability to handle high volumes of leads efficiently. These tests are automatically run:

- Monthly (first Sunday of each month at 2am UTC)
- After significant changes to core pipeline components
- On-demand via GitHub Actions UI

The validation suite includes:

1. **Scale Testing**: Processes up to 10,000 leads through the complete pipeline
2. **Performance Metrics**: Tracks throughput, success rates, and processing times
3. **Failure Simulation**: Validates graceful handling of various error conditions
4. **Bottleneck Detection**: Identifies performance bottlenecks in the pipeline

Performance reports and visualizations are automatically generated and published as GitHub Actions artifacts. The system enforces the following performance requirements:

- **Minimum throughput**: 100 leads/minute
- **Maximum error rate**: 1%
- **Maximum runtime**: 180 minutes for 10,000 leads

Run the large-scale validation tests locally with:

```bash
# Run the complete validation suite
python scripts/run_large_scale_tests.py

# Run a smaller test for quick verification
python scripts/run_large_scale_tests.py --lead-count=100 --skip-10k
```

## Data Durability

- Primary data is stored in Supabase Postgres
- WAL (Write-Ahead Logging) is enabled for data integrity
- Nightly backups to S3
- RSYNC mirror to a backup VPS for SPOF (Single Point of Failure) protection

### RSYNC Fallback Mechanism

The project includes a comprehensive SPOF fallback mechanism that ensures business continuity in case of primary instance failure:

#### Backup Script

The `bin/rsync_backup.sh` script performs nightly data mirroring to a backup VPS:

```bash
# Run with default settings
bin/rsync_backup.sh

# Perform a dry run without making changes
bin/rsync_backup.sh --dry-run

# Use a custom configuration file
bin/rsync_backup.sh --config=/path/to/config.yml
```

Configuration is stored in `etc/backup_config.yml` and includes:
- Remote server details
- Directories and files to backup
- Exclusion patterns
- Retention policies
- Notification settings

#### Health Check and Auto-Boot

The `bin/health_check.sh` script monitors the primary instance and automatically boots the backup when needed:

```bash
# Run health check with default settings
bin/health_check.sh

# Only perform health check without auto-boot
bin/health_check.sh --check-only

# Force boot on backup VPS without health checks
bin/health_check.sh --force-boot
```

The health check script:
1. Monitors the primary instance health endpoint
2. Tracks failure count with configurable threshold (set to 2 consecutive failures per Phase 0 v1.3 spec)
3. Automatically boots the Docker stack on the backup VPS when threshold is reached
4. Sends notifications via email and Slack

Configuration is stored in `etc/health_check_config.yml`.

#### Setting Up the Fallback Mechanism

1. Copy the sample configuration files:
   ```bash
   cp etc/backup_config.yml.sample etc/backup_config.yml
   cp etc/health_check_config.yml.sample etc/health_check_config.yml
   ```

2. Edit the configuration files with your specific settings

3. Set up SSH keys for passwordless authentication between primary and backup servers

4. Schedule the scripts using cron:
   ```bash
   # Add to crontab
   # Nightly backup at 2:00 AM
   0 2 * * * /path/to/bin/rsync_backup.sh >> /path/to/logs/rsync_backup_cron.log 2>&1

   # Health check every 5 minutes
   */5 * * * * /path/to/bin/health_check.sh >> /path/to/logs/health_check_cron.log 2>&1
   ```

## Testing

The project includes BDD (Behavior-Driven Development) tests for each pipeline stage:

```bash
# Run all tests
pytest tests/

# Run tests for a specific stage
pytest tests/test_scraper.py
```

## Development Workflow

### Pre-commit Hooks

The project uses pre-commit hooks to enforce code quality standards. These hooks run automatically before each commit to ensure code meets quality and security requirements.

Key pre-commit hooks include:
- **Ruff**: Fast Python linting
- **Black**: Code formatting
- **Bandit**: Security vulnerability scanning
- **Pre-commit-hooks**: File checks (trailing whitespace, YAML validation, etc.)

For setup instructions and usage guide, see [Pre-commit Workflow Guide](docs/pre-commit-workflow.md).

### Feature Development Workflow

All feature development follows the standardized workflow:

1. **Development Phase**: Implement features with error handling and logging
2. **Testing Phase**: Run unit tests and BDD tests
3. **Quality Assurance Phase**: Run static analysis tools (ruff, bandit) and code formatting (black)
4. **Pre-Commit Phase**: Run pre-commit hooks locally and fix any issues
5. **Commit Phase**: Create feature branch with descriptive name and commit
6. **CI Verification Phase**: Verify CI pipeline passes before merging

## Continuous Integration

The project uses GitHub Actions for comprehensive continuous integration. All CI checks are now configured in strict blocking mode to ensure code quality and reliability.

### CI Workflows

The project has two main CI workflow configurations:

1. **API Integration Tests (`api-integration-tests.yml`)**: API-specific integration testing with both mock and real APIs
2. **Large-Scale Validation (`large-scale-validation.yml`)**: Performance testing at scale (10,000 leads)

### CI Gates and Requirements

All pull requests must pass the following quality gates before merging:

#### 1. Code Quality Gates (Blocking)

| Gate | Tool | Threshold | Configuration |
|------|------|-----------|---------------|
| Formatting | Black | 0 errors | `--check` mode |
| Linting | Ruff | 0 errors | Standard rules |
| Linting | Flake8 | 0 errors | See `setup.cfg` |
| Type checking | MyPy | 0 errors | See `mypy.ini` |
| Security | Bandit | 0 high/medium issues | `-ll` flag |

#### 2. Testing Gates (Blocking)

| Gate | Tool | Threshold | Configuration |
|------|------|-----------|---------------|
| Unit tests | Pytest | 100% pass | All test modules |
| Test coverage | Coverage | ≥80% coverage | `--cov-fail-under=80` |
| Integration tests | Pytest | 100% pass | Mock APIs by default |

#### 3. Performance Gates (Blocking)

| Gate | Metric | Threshold | Validation |
|------|--------|-----------|------------|
| Throughput | Leads/minute | ≥100 leads/min | Large-scale test |
| Error rate | Failed leads % | ≤1% | Large-scale test |
| Runtime | Total minutes | ≤180 minutes | Large-scale test |

### CI Workflow Execution

The CI workflows run automatically on:
- Push to `main` and `develop` branches
- Pull requests to `main` and `develop` branches
- Manual trigger via GitHub Actions interface
- Scheduled runs (weekly for API tests, monthly for large-scale validation)

### CI Artifacts

The CI process generates several important artifacts:

1. **Test Coverage Reports**: Uploaded to Codecov for tracking coverage trends
2. **Performance Metrics**: Generated during large-scale validation
3. **API Usage Reports**: Tracking API costs and usage statistics

### Triggering CI Workflows

#### Unified CI

```bash
# Trigger unified CI workflow manually
git push origin my-feature-branch
```

#### API Integration Tests

```bash
# Manual trigger with GitHub CLI
gh workflow run api-integration-tests.yml --ref my-branch --field use_real_apis=false
```

#### Large-Scale Validation

```bash
# Manual trigger with GitHub CLI
gh workflow run large-scale-validation.yml --ref my-branch --field lead_count=10000
```

### CI Configuration Files

- **API Tests**: `.github/workflows/api-integration-tests.yml`
- **Large-Scale**: `.github/workflows/large-scale-validation.yml`
- **Coverage**: `.codecov.yml`

### Environment Variable Handling in CI

CI workflows require special handling of environment variables to ensure tests run correctly:

#### Mock vs. Real API Keys

The CI system uses a two-tier approach to API keys:

1. **Mock API Keys**: Used by default in pull request builds and non-scheduled runs
2. **Real API Keys**: Used in scheduled runs and when explicitly enabled via workflow inputs

#### Configuring Environment Variables

```yaml
# Example from API Integration Tests workflow
- name: Setup test environment and mock API keys
  run: |
    # Create .env file with mock keys for testing
    cp .env.example .env
    echo "LEADFACTORY_USE_MOCKS=1" >> .env

- name: Set real API keys
  if: ${{ github.event.inputs.use_real_apis == 'true' || github.event_name == 'schedule' }}
  run: |
    echo "Setting up real API keys where available"
    echo "LEADFACTORY_USE_MOCKS=0" >> .env
```

#### GitHub Secrets

Secure API keys are stored in GitHub Secrets and accessed in the workflows. When setting up these secrets, use the exact environment variable names expected by the application:

- `YELP_API_KEY`
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `SENDGRID_API_KEY`
- `SCREENSHOT_ONE_KEY`
- `ANTHROPIC_API_KEY`
- `SLACK_WEBHOOK_URL`

> **Important**: The CI system uses `load_dotenv(override=True)` to ensure environment variables from `.env` files take precedence over system environment variables.

### Troubleshooting Common CI Failures

#### Context Access Issues

You may encounter "Context access might be invalid" warnings in GitHub Actions workflows. These occur when using expressions like `${{ secrets.SOME_SECRET }}` in places where GitHub's context is restricted for security reasons.

**Solution**: Use environment variables as intermediaries:

```yaml
# Instead of this (may cause warnings):
- run: echo "API_KEY=${{ secrets.API_KEY }}" >> .env

# Use this approach:
- name: Set up API keys
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: echo "API_KEY=$API_KEY" >> .env
```

#### API Validation Failures

1. **403 Forbidden errors**: Check API key permissions and verify correct scopes are enabled
2. **Rate limiting issues**: Implement retry logic or reduce parallel testing
3. **Timeout errors**: Adjust timeout settings in workflow configuration

#### Common Solutions

1. **Update API Keys**: Refresh expired or invalid API keys in GitHub Secrets
2. **Check CI Logs**: Review detailed error messages in the CI logs
3. **Local Validation**: Run the `validate_real_api_integration_fixed.py` script locally
4. **Mock API Testing**: Use `LEADFACTORY_USE_MOCKS=1` to bypass real APIs for faster testing

### Coverage Reports and Analysis

The CI process generates code coverage reports that help identify untested code paths.

#### Interpreting Coverage Reports

Coverage reports provide metrics in several categories:

1. **Line Coverage**: Percentage of code lines executed during tests
2. **Branch Coverage**: Percentage of code branches (if/else) executed
3. **Function Coverage**: Percentage of functions called during tests

#### Codecov Integration

Coverage reports are uploaded to Codecov for long-term tracking and visualization:

1. **Coverage Trends**: Track how coverage changes over time
2. **Coverage Gaps**: Identify files and functions with low coverage
3. **PR Coverage**: See how pull requests impact overall coverage

#### Coverage Requirements

The project maintains the following coverage requirements:

| Component | Minimum Coverage |
|-----------|------------------|
| Core pipeline | 85% |
| Utilities | 80% |
| Scripts | 70% |
| Overall | 80% |

#### Improving Coverage

To improve coverage in areas identified as lacking:

1. Add targeted unit tests for specific functions
2. Create integration tests for complex code paths
3. Use parameterized tests to cover multiple scenarios
4. Add explicit tests for error handling paths

## Budget Monitoring

The pipeline includes cost tracking for all API calls and operations. A budget audit is triggered after the first 1,000-lead batch to validate unit economics before scaling to 10,000 leads.

## License

Proprietary - Anthrasite, Inc. © 2025
