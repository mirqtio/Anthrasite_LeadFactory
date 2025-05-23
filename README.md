# Anthrasite Lead-Factory

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

1. **Scraping** (`01_scrape.py`): Fetches business listings from Yelp Fusion and Google Places APIs.
2. **Enrichment** (`02_enrich.py`): Analyzes websites for tech stack and Core Web Vitals, with tier-based additional enrichment.
3. **Deduplication** (`03_dedupe.py`): Uses Ollama Llama-3 8B to identify and merge duplicate leads.
4. **Scoring** (`04_score.py`): Applies YAML-defined rules to score leads based on their features.
5. **Mock-up Generation** (`05_mockup.py`): Creates website improvement mock-ups using GPT-4o (with Claude fallback).
6. **Email Queueing** (`06_email_queue.py`): Sends personalized outreach via SendGrid.

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
   git clone https://github.com/anthrasite/lead-factory.git
   cd lead-factory
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
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

These metrics can be visualized in Grafana Cloud with the provided alert rules.

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

The project uses GitHub Actions for continuous integration. The CI pipeline includes:

1. **Pre-commit Checks**: Runs all pre-commit hooks to enforce code quality
2. **Linting**: Checks code quality using flake8, black, and isort
3. **Testing**: Runs unit tests and BDD acceptance tests with coverage reporting
4. **Database Validation**: Verifies database schema integrity
5. **Docker Build**: Creates and validates a Docker image

The CI workflow runs automatically on:
- Push to `main` and `develop` branches
- Pull requests to `main` and `develop` branches
- Manual trigger via GitHub Actions interface

To manually trigger the CI workflow:
1. Go to the GitHub repository
2. Navigate to Actions > Anthrasite Lead-Factory CI
3. Click "Run workflow"
4. Select the environment (test or staging)
5. Click "Run workflow"

The CI workflow can be configured in `.github/workflows/ci.yml`.

## Budget Monitoring

The pipeline includes cost tracking for all API calls and operations. A budget audit is triggered after the first 1,000-lead batch to validate unit economics before scaling to 10,000 leads.

## License

Proprietary - Anthrasite, Inc. © 2025
