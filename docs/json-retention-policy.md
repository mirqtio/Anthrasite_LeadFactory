# JSON Response Retention Policy

This document describes the configurable JSON retention policy for raw API responses from external services like Yelp and Google Places.

## Overview

The LeadFactory system can optionally store raw JSON responses from external APIs for debugging, analytics, and data recovery purposes. However, these responses may contain personally identifiable information (PII) that requires careful handling for privacy compliance.

The JSON retention policy provides configurable options to:
- Enable/disable JSON storage entirely
- Set retention periods with automatic cleanup
- Anonymize JSON data by removing PII while preserving analytical value
- Configure field preservation for anonymization

## Configuration Variables

### `JSON_RETENTION_ENABLED`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Master switch to enable/disable JSON response storage

### `JSON_RETENTION_DAYS`
- **Type**: Integer
- **Default**: `90`
- **Description**: Number of days to retain JSON responses
- **Special Values**:
  - `0`: Purge immediately (no storage)
  - `-1`: Keep forever (no automatic cleanup)
  - `> 0`: Retain for specified number of days

### `JSON_RETENTION_ANONYMIZE`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Whether to anonymize JSON responses before storage

### `JSON_RETENTION_PRESERVE_FIELDS`
- **Type**: String (comma-separated)
- **Default**: `"id,rating,price,categories,hours,location.zip_code,location.state"`
- **Description**: Fields to preserve when anonymization is enabled

## Usage Scenarios

### Scenario 1: Full Data Retention (Development/Debug)
```bash
export JSON_RETENTION_ENABLED=true
export JSON_RETENTION_DAYS=90
export JSON_RETENTION_ANONYMIZE=false
```
- Stores complete JSON responses for 90 days
- Useful for development and debugging
- Requires careful handling of PII

### Scenario 2: Privacy-First with Anonymization
```bash
export JSON_RETENTION_ENABLED=true
export JSON_RETENTION_DAYS=30
export JSON_RETENTION_ANONYMIZE=true
export JSON_RETENTION_PRESERVE_FIELDS="id,rating,categories,hours"
```
- Stores anonymized JSON responses for 30 days
- Removes PII fields while preserving analytical data
- Good balance between privacy and functionality

### Scenario 3: No Data Retention (Maximum Privacy)
```bash
export JSON_RETENTION_ENABLED=false
# or
export JSON_RETENTION_ENABLED=true
export JSON_RETENTION_DAYS=0
```
- No JSON responses are stored
- Maximum privacy compliance
- Limited debugging and analytics capabilities

### Scenario 4: Permanent Retention (Legacy Systems)
```bash
export JSON_RETENTION_ENABLED=true
export JSON_RETENTION_DAYS=-1
export JSON_RETENTION_ANONYMIZE=true
```
- Stores anonymized JSON responses permanently
- No automatic cleanup
- Requires manual data management

## Anonymization Details

When `JSON_RETENTION_ANONYMIZE=true`, the system:

1. **Identifies PII Fields**: Automatically detects fields containing:
   - Email addresses (contains `@` and `.`)
   - Phone numbers (10+ digits with formatting)
   - Name fields (contains keywords like `name`, `contact`, `owner`)
   - Address information (contains keywords like `address`, `street`)

2. **Preserves Specified Fields**: Keeps fields listed in `JSON_RETENTION_PRESERVE_FIELDS`

3. **Redacts PII**: Replaces PII field values with `[REDACTED]`

4. **Maintains Structure**: Preserves JSON structure for analytical queries

### Example Anonymization

**Original JSON**:
```json
{
  "id": "yelp-123",
  "name": "John's Restaurant",
  "rating": 4.5,
  "phone": "555-123-4567",
  "owner_name": "John Smith",
  "location": {
    "address": "123 Main St",
    "zip_code": "12345",
    "state": "CA"
  },
  "categories": ["restaurant", "pizza"]
}
```

**Anonymized JSON** (with preserve fields: `id,rating,categories,location.zip_code,location.state`):
```json
{
  "id": "yelp-123",
  "name": "[REDACTED]",
  "rating": 4.5,
  "phone": "[REDACTED]",
  "owner_name": "[REDACTED]",
  "location": {
    "address": "[REDACTED]",
    "zip_code": "12345",
    "state": "CA"
  },
  "categories": ["restaurant", "pizza"]
}
```

## Database Schema

The retention policy uses the following database fields:

```sql
ALTER TABLE businesses ADD COLUMN json_retention_expires_at TIMESTAMP WITH TIME ZONE;
```

- `yelp_response_json`: JSONB field for Yelp API responses
- `google_response_json`: JSONB field for Google Places API responses
- `json_retention_expires_at`: Timestamp when JSON data should be purged

## Cleanup Process

The system includes an automated cleanup script: `bin/cleanup_json_responses.py`

### Manual Cleanup
```bash
# Show current retention policy
python bin/cleanup_json_responses.py --policy

# Show storage statistics
python bin/cleanup_json_responses.py --stats

# Dry run cleanup (show what would be cleaned)
python bin/cleanup_json_responses.py --dry-run

# Perform actual cleanup
python bin/cleanup_json_responses.py
```

### Automated Cleanup
The cleanup script can be scheduled via cron:
```bash
# Daily cleanup at 2 AM
0 2 * * * /path/to/venv/bin/python /path/to/leadfactory/bin/cleanup_json_responses.py
```

## Privacy Compliance

### GDPR Compliance
- **Right to be forgotten**: Use immediate purge (`JSON_RETENTION_DAYS=0`) or short retention periods
- **Data minimization**: Enable anonymization to reduce PII exposure
- **Purpose limitation**: Only store data necessary for defined business purposes

### CCPA Compliance
- **Data deletion**: Implement procedures to delete specific user data on request
- **Data transparency**: Document what JSON data is collected and how long it's retained

### General Recommendations
1. **Default to privacy**: Start with anonymization enabled and short retention periods
2. **Regular audits**: Monitor what data is being stored and for how long
3. **Access controls**: Restrict access to JSON data to authorized personnel only
4. **Documentation**: Maintain records of retention policy changes

## Monitoring and Alerts

### Storage Monitoring
The system tracks:
- Total JSON storage usage
- Number of records with JSON data
- Number of expired records awaiting cleanup

### Recommended Alerts
- Storage usage exceeding thresholds
- Cleanup failures
- Large numbers of expired records
- Unexpected changes in retention policy

## Migration Guide

### Enabling Retention Policy
If JSON retention was not previously configured:

1. **Update Configuration**:
   ```bash
   export JSON_RETENTION_ENABLED=true
   export JSON_RETENTION_DAYS=90
   export JSON_RETENTION_ANONYMIZE=true
   ```

2. **Run Database Migration**:
   ```bash
   python scripts/db/migrations/add_json_retention_policy.sql
   ```

3. **Test with Dry Run**:
   ```bash
   python bin/cleanup_json_responses.py --dry-run
   ```

### Changing Retention Period
To change retention from 90 to 30 days:

1. **Update Configuration**:
   ```bash
   export JSON_RETENTION_DAYS=30
   ```

2. **Update Existing Records** (optional):
   ```sql
   UPDATE businesses
   SET json_retention_expires_at = CURRENT_TIMESTAMP + INTERVAL '30 days'
   WHERE json_retention_expires_at > CURRENT_TIMESTAMP + INTERVAL '30 days';
   ```

### Disabling Retention
To stop storing JSON responses:

1. **Update Configuration**:
   ```bash
   export JSON_RETENTION_ENABLED=false
   ```

2. **Clean Existing Data** (optional):
   ```bash
   python bin/cleanup_json_responses.py --batch-size 1000
   ```

## Troubleshooting

### Common Issues

**Issue**: JSON data not being stored
- Check `JSON_RETENTION_ENABLED=true`
- Check `JSON_RETENTION_DAYS` is not `0`
- Verify database schema includes retention fields

**Issue**: Cleanup not working
- Check database connection
- Verify `json_retention_expires_at` field exists
- Check for sufficient disk space

**Issue**: Anonymization not working as expected
- Review `JSON_RETENTION_PRESERVE_FIELDS` configuration
- Check anonymization logic for specific field patterns
- Verify `JSON_RETENTION_ANONYMIZE=true`

### Debugging
Enable debug logging to troubleshoot issues:
```bash
export LOG_LEVEL=DEBUG
python bin/cleanup_json_responses.py --log-level DEBUG
```

## Performance Considerations

### Storage Impact
- JSON responses can be 5-50KB each
- 1000 businesses ≈ 5-50MB storage
- Enable compression for large datasets

### Query Performance
- JSON fields are indexed with GIN indexes
- Anonymization adds processing overhead
- Consider batch processing for large datasets

### Cleanup Performance
- Process in batches (default: 100 records)
- Run during low-traffic periods
- Monitor for database locks

## Security Considerations

### Access Control
- Limit database access to JSON fields
- Use separate read-only accounts for analytics
- Encrypt database backups containing JSON data

### Audit Trail
- Log all JSON cleanup operations
- Track configuration changes
- Monitor access to sensitive JSON data

### Data Leakage Prevention
- Review anonymization effectiveness regularly
- Test field preservation patterns
- Validate that PII is properly redacted
