# Score Threshold Filtering

## Overview

The score threshold filtering feature ensures that only businesses with high audit potential receive marketing emails. This prevents wasting resources on businesses that are unlikely to need website improvement services.

## How It Works

1. **Scoring Stage**: Each business is scored based on various factors:
   - Technology stack (outdated tech scores higher)
   - Website performance metrics
   - SEO opportunities
   - Business type and location

2. **Threshold Check**: Before sending emails, businesses are filtered based on their audit score:
   - Default threshold: 60 points
   - Configurable via `etc/scoring_rules_simplified.yml`
   - Businesses below the threshold are automatically skipped

3. **Skip Tracking**: When a business is skipped, the system:
   - Logs the skip reason
   - Updates the `processing_status` table with skip details
   - Prevents future email attempts to low-score businesses

## Configuration

### Setting the Audit Threshold

Edit `etc/scoring_rules_simplified.yml`:

```yaml
settings:
  audit_threshold: 60  # Minimum score for audit opportunity
```

### Score Ranges

- **0-30**: Very low audit potential (modern sites, no issues)
- **31-59**: Below threshold (some issues but not enough)
- **60-79**: Good audit candidates
- **80-100**: Excellent audit candidates (outdated tech, poor performance)

## Database Schema

### New/Modified Fields

1. **processing_status.skip_reason**: Tracks why a business was skipped
2. **businesses.audit_score**: Cached score for quick filtering
3. **stage_results**: Stores detailed scoring results

### Migrations

Run the migration to add skip tracking:

```bash
psql $DATABASE_URL < db/migrations/add_skip_reason_tracking.sql
```

## Usage Examples

### Check if a Business Meets Threshold

```python
from leadfactory.pipeline.score import meets_audit_threshold

score = 75
if meets_audit_threshold(score):
    print("Business qualifies for audit email")
else:
    print("Business score too low")
```

### Custom Threshold

```python
# Use a custom threshold
if meets_audit_threshold(score, threshold=70):
    print("Meets higher threshold")
```

### Query Skipped Businesses

```sql
-- Find businesses skipped due to low scores
SELECT b.id, b.name, ps.skip_reason, b.audit_score
FROM businesses b
JOIN processing_status ps ON b.id = ps.business_id
WHERE ps.stage = 'email'
  AND ps.status = 'skipped'
  AND ps.skip_reason LIKE '%audit threshold%';
```

## Monitoring

### Dashboard Queries

1. **Score Distribution**:
```sql
SELECT
  CASE
    WHEN audit_score < 30 THEN '0-29'
    WHEN audit_score < 60 THEN '30-59'
    WHEN audit_score < 80 THEN '60-79'
    ELSE '80-100'
  END as score_range,
  COUNT(*) as count
FROM businesses
WHERE audit_score IS NOT NULL
GROUP BY score_range
ORDER BY score_range;
```

2. **Email Eligibility Rate**:
```sql
SELECT
  COUNT(CASE WHEN audit_score >= 60 THEN 1 END) as eligible,
  COUNT(CASE WHEN audit_score < 60 THEN 1 END) as ineligible,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(CASE WHEN audit_score >= 60 THEN 1 END) / COUNT(*), 2) as eligibility_rate
FROM businesses
WHERE audit_score IS NOT NULL;
```

3. **Skip Reasons Summary**:
```sql
SELECT
  skip_reason,
  COUNT(*) as skip_count
FROM processing_status
WHERE stage = 'email'
  AND status = 'skipped'
GROUP BY skip_reason
ORDER BY skip_count DESC;
```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_score_threshold.py -v
```

### Integration Tests
```bash
pytest tests/integration/test_score_threshold_integration.py -v
```

### BDD Tests
```bash
pytest tests/bdd/step_defs/test_score_threshold_steps.py -v
```

## Benefits

1. **Resource Efficiency**: Avoids sending emails to businesses unlikely to convert
2. **Better Targeting**: Focuses on businesses with genuine improvement needs
3. **Cost Savings**: Reduces email sending costs and preserves sender reputation
4. **Transparency**: Clear tracking of why businesses were skipped
5. **Flexibility**: Easily adjustable threshold based on business needs

## Troubleshooting

### Common Issues

1. **All businesses being skipped**:
   - Check if scoring is working correctly
   - Verify the threshold isn't set too high
   - Ensure scores are being saved to stage_results

2. **No filtering happening**:
   - Verify the migration has been run
   - Check that scores are being retrieved from database
   - Ensure email_queue.py is using the latest code

3. **Incorrect threshold being used**:
   - Check `etc/scoring_rules_simplified.yml` for the current setting
   - Verify the config file is being loaded correctly
   - Check for environment variable overrides

### Debug Commands

```bash
# Check current threshold
python -c "from leadfactory.scoring.simplified_yaml_parser import SimplifiedYamlParser; p = SimplifiedYamlParser(); c = p.load_and_validate(); print(f'Current threshold: {c.settings.audit_threshold}')"

# Test score filtering
python -c "from leadfactory.pipeline.score import meets_audit_threshold; print(meets_audit_threshold(55)); print(meets_audit_threshold(65))"

# Check businesses with scores
psql $DATABASE_URL -c "SELECT id, name, audit_score FROM businesses WHERE audit_score IS NOT NULL ORDER BY audit_score DESC LIMIT 10;"
```
