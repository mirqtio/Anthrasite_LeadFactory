# Raw Data Retention Implementation

## Overview

This document describes the implementation of raw data retention features for the Anthrasite LeadFactory. These features ensure compliance with data retention policies and provide audit capabilities by storing raw HTML from scraped pages and logging LLM interactions.

## Features

### 1. HTML Storage

- Compressed storage of HTML content from scraped websites
- Association of HTML content with business records
- Automatic cleanup of expired HTML files based on retention policy

### 2. LLM Interaction Logging

- Logging of all LLM prompts and responses
- Metadata capture including tokens, duration, and operation type
- Business ID association for audit trails

### 3. 90-Day Retention Policy

- Configurable retention period (default: 90 days)
- Automatic identification of expired data
- Scheduled cleanup process via nightly batch job

## Implementation Details

### Database Schema

Two new tables have been added to the database:

1. `raw_html_storage` - Stores metadata about HTML content
   - `id` - Primary key
   - `business_id` - Foreign key to businesses table
   - `html_path` - Path to stored HTML file
   - `original_url` - URL the HTML was fetched from
   - `compression_ratio` - Ratio of compression achieved
   - `content_hash` - Hash of the HTML content for integrity verification
   - `size_bytes` - Size of the compressed HTML file
   - `retention_expires_at` - Date when the HTML should be deleted
   - `created_at` - Timestamp when the HTML was stored

2. `llm_logs` - Stores LLM interaction logs
   - `id` - Primary key
   - `operation` - Type of operation (e.g., deduplication, mockup_generation)
   - `model_version` - Version of the LLM model used
   - `prompt_text` - Text of the prompt sent to the LLM
   - `response_json` - JSON response from the LLM
   - `business_id` - Foreign key to businesses table (optional)
   - `tokens_prompt` - Number of tokens in the prompt
   - `tokens_completion` - Number of tokens in the completion
   - `duration_ms` - Duration of the interaction in milliseconds
   - `status` - Status of the interaction (success, error, etc.)
   - `metadata` - Additional metadata for the interaction
   - `created_at` - Timestamp when the interaction occurred

### Core Modules

1. `utils/raw_data_retention.py` - Core utilities for storing and retrieving raw HTML and logging LLM interactions
2. `utils/website_scraper.py` - Utilities for scraping websites and storing HTML content
3. `utils/llm_logger.py` - Utilities for logging LLM interactions and managing retention

### Command-line Scripts

1. `bin/process_raw_data.py` - Processes pending websites and stores their HTML content
2. `bin/cleanup_expired_data.py` - Cleans up expired HTML files and LLM logs

### Integration Points

1. **Scraper Integration** - The HTML storage functionality is integrated with the website scraper to automatically store HTML content when scraping websites.
2. **LLM Integration** - The LLM logging functionality is integrated with the deduplication and mockup generation processes to log all LLM interactions.
3. **Nightly Batch Job** - The raw data retention cleanup process is integrated with the nightly batch job to automatically clean up expired data.

## Configuration

The following environment variables can be used to configure the raw data retention features:

- `DATA_RETENTION_DAYS` - Number of days to retain raw data (default: 90)
- `RAW_DATA_DIR` - Directory to store raw data (default: `<project_root>/data`)
- `LLM_MODEL_VERSION` - Default LLM model version for logging (default: "gpt-3.5-turbo")

## Usage Examples

### Storing HTML Content

```python
from utils.raw_data_retention import store_html

# Store HTML content
html_path = store_html(html_content, url, business_id)
```

### Logging LLM Interactions

```python
from utils.llm_logger import LLMLogger

# Log an LLM interaction
with LLMLogger() as llm_logger:
    log_id = llm_logger.log(
        operation="deduplication",
        prompt_text=prompt,
        response_json=response,
        business_id=business_id
    )
```

### Processing Pending Websites

```bash
python bin/process_raw_data.py --process-websites --verbose
```

### Cleaning Up Expired Data

```bash
python bin/cleanup_expired_data.py --verbose
```

## Testing

The raw data retention features have been tested with the following scenarios:

1. **HTML Storage** - Verified that HTML content is properly stored and can be retrieved
2. **LLM Logging** - Verified that LLM interactions are properly logged and can be queried
3. **Retention Policy** - Verified that expired data is properly identified and cleaned up
4. **Integration** - Verified that the raw data retention features work correctly when integrated with the scraper and LLM processes

## Monitoring

The raw data retention features can be monitored using the following commands:

```bash
# Check retention status
python bin/process_raw_data.py --check-retention --verbose

# Dry run cleanup to see what would be deleted
python bin/cleanup_expired_data.py --dry-run --verbose
```

## Troubleshooting

### Common Issues

1. **Missing HTML Files** - If HTML files are missing, check the storage directory and database records
2. **Database Inconsistencies** - If database records don't match the files on disk, run the cleanup script with `--dry-run` to identify issues
3. **Permissions Issues** - Ensure the application has write permissions to the storage directory

### Logs

Relevant log messages are tagged with the following modules:

- `utils.raw_data_retention` - Core raw data retention utilities
- `utils.website_scraper` - Website scraping utilities
- `utils.llm_logger` - LLM logging utilities
- `bin.process_raw_data` - Raw data processing script
- `bin.cleanup_expired_data` - Data cleanup script

## Future Improvements

1. Add Prometheus metrics for raw data storage and retention
2. Implement a web interface for browsing stored HTML and LLM logs
3. Add support for exporting raw data for external analysis
4. Implement more sophisticated HTML parsing for better email extraction
