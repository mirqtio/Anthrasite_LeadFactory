# LeadFactory Troubleshooting Guide

## Common Issues and Solutions

### 1. API Authentication Issues

#### Problem: "401 Unauthorized" error
**Symptoms:**
- API calls return 401 status code
- Error message: "Invalid API key" or "Missing authentication"

**Solutions:**
1. Verify API key is correct:
   ```bash
   echo $API_KEY  # Check if environment variable is set
   ```

2. Ensure API key is included in headers:
   ```bash
   curl -H "X-API-Key: your-api-key" https://api.leadfactory.com/health
   ```

3. Check API key hasn't expired or been revoked:
   - Log into dashboard at https://app.leadfactory.com
   - Navigate to Settings > API Keys
   - Verify key status

4. For JWT tokens, ensure token hasn't expired:
   ```python
   import jwt
   from datetime import datetime

   # Decode token (without verification) to check expiry
   decoded = jwt.decode(token, options={"verify_signature": False})
   exp_timestamp = decoded.get('exp')
   if exp_timestamp and datetime.fromtimestamp(exp_timestamp) < datetime.utcnow():
       print("Token has expired")
   ```

### 2. Rate Limiting Issues

#### Problem: "429 Too Many Requests" error
**Symptoms:**
- API returns 429 status code
- Error message: "Rate limit exceeded"

**Solutions:**
1. Check rate limit headers:
   ```python
   response = requests.get(url, headers=headers)
   print(f"Limit: {response.headers.get('X-RateLimit-Limit')}")
   print(f"Remaining: {response.headers.get('X-RateLimit-Remaining')}")
   print(f"Reset: {response.headers.get('X-RateLimit-Reset')}")
   ```

2. Implement exponential backoff:
   ```python
   import time
   import random

   def make_request_with_retry(url, headers, max_retries=3):
       for attempt in range(max_retries):
           response = requests.get(url, headers=headers)
           if response.status_code != 429:
               return response

           # Exponential backoff with jitter
           wait_time = (2 ** attempt) + random.uniform(0, 1)
           time.sleep(wait_time)

       return response
   ```

3. Batch requests to reduce API calls:
   ```python
   # Instead of individual requests
   for item in items:
       api_call(item)

   # Use batch endpoints
   api_batch_call(items)
   ```

### 3. Pipeline Processing Issues

#### Problem: Pipeline stuck in "running" state
**Symptoms:**
- Pipeline status remains "running" for extended period
- No progress updates
- No error messages

**Solutions:**
1. Check pipeline logs:
   ```bash
   curl -X GET "https://api.leadfactory.com/api/v1/logs?pipeline_id=pipe_123" \
     -H "X-API-Key: your-api-key"
   ```

2. Verify stage-specific status:
   ```python
   status = get_pipeline_status(pipeline_id)
   for stage, stage_status in status['progress'].items():
       print(f"{stage}: {stage_status}")
       if stage_status == 'error':
           # Check stage-specific logs
           logs = get_stage_logs(pipeline_id, stage)
   ```

3. Common stage-specific issues:
   - **Scraping stage**: Check if target websites are accessible
   - **Enrichment stage**: Verify API keys for third-party services
   - **Deduplication stage**: May be slow for large datasets
   - **Scoring stage**: Check scoring rules configuration

4. Force pipeline cancellation (if needed):
   ```bash
   curl -X POST "https://api.leadfactory.com/api/v1/pipeline/cancel/pipe_123" \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"reason": "Stuck pipeline"}'
   ```

### 4. Database Connection Issues

#### Problem: "Database connection failed" errors
**Symptoms:**
- 500 Internal Server Error
- Timeout errors
- "Connection refused" in logs

**Solutions:**
1. Check database connectivity:
   ```bash
   # Test PostgreSQL connection
   PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"
   ```

2. Verify connection pool settings:
   ```python
   # Check current connections
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'leadfactory';

   # Check max connections
   SHOW max_connections;
   ```

3. Monitor connection pool exhaustion:
   ```python
   # In application logs, look for:
   # "QueuePool limit of size X overflow Y reached"
   # Solution: Increase pool size or fix connection leaks
   ```

4. Check for long-running queries:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
   AND state != 'idle';
   ```

### 5. Email Delivery Issues

#### Problem: Emails not being delivered
**Symptoms:**
- No delivery confirmation
- High bounce rates
- Emails in spam folder

**Solutions:**
1. Check email logs:
   ```python
   # Get email delivery status
   email_status = get_email_status(email_id)
   print(f"Status: {email_status['status']}")
   print(f"Bounce reason: {email_status.get('bounce_reason')}")
   ```

2. Verify sender reputation:
   ```bash
   # Check IP reputation
   curl "https://api.sendgrid.com/v3/ips/pools" \
     -H "Authorization: Bearer $SENDGRID_API_KEY"
   ```

3. Common issues and fixes:
   - **SPF/DKIM not configured**: Add DNS records
   - **High bounce rate**: Clean email list, verify addresses
   - **Spam complaints**: Review email content and frequency
   - **IP warming needed**: Gradually increase volume

4. Test email deliverability:
   ```python
   # Send test email
   test_result = send_test_email(
       to="test@mail-tester.com",  # Use mail testing service
       subject="Deliverability Test",
       content="Test content"
   )
   ```

### 6. Performance Issues

#### Problem: Slow API responses
**Symptoms:**
- Response times > 5 seconds
- Timeouts
- 504 Gateway Timeout errors

**Solutions:**
1. Check API metrics:
   ```bash
   curl -X GET "https://api.leadfactory.com/api/v1/metrics" \
     -H "X-API-Key: your-api-key"
   ```

2. Optimize queries:
   ```python
   # Use pagination for large datasets
   def get_all_businesses(limit=100):
       offset = 0
       while True:
           response = get_businesses(limit=limit, offset=offset)
           if not response['data']:
               break
           yield from response['data']
           offset += limit
   ```

3. Enable caching:
   ```python
   # Use ETags for conditional requests
   headers = {}
   if cached_etag:
       headers['If-None-Match'] = cached_etag

   response = requests.get(url, headers=headers)
   if response.status_code == 304:
       # Use cached data
       return cached_data
   ```

### 7. Data Quality Issues

#### Problem: Incorrect or missing business data
**Symptoms:**
- Missing phone numbers or emails
- Incorrect addresses
- Duplicate entries

**Solutions:**
1. Enable data validation:
   ```python
   pipeline_options = {
       "validate_phones": True,
       "validate_emails": True,
       "geocode_addresses": True,
       "aggressive_dedup": True
   }
   ```

2. Check data sources:
   ```python
   # Verify which sources provided data
   business_data = get_business(business_id)
   print(f"Google data: {business_data.get('google_response') is not None}")
   print(f"Yelp data: {business_data.get('yelp_response') is not None}")
   ```

3. Report data issues:
   ```python
   report_data_issue(
       business_id=123,
       issue_type="incorrect_phone",
       details="Phone number is disconnected"
   )
   ```

### 8. Integration Issues

#### Problem: Third-party API failures
**Symptoms:**
- "External API error" messages
- Partial data enrichment
- Timeout errors

**Solutions:**
1. Check API status:
   ```python
   # Check third-party API status
   services = ['google_places', 'yelp', 'openai']
   for service in services:
       status = check_service_status(service)
       print(f"{service}: {status}")
   ```

2. Configure fallbacks:
   ```python
   enrichment_config = {
       "primary_source": "google_places",
       "fallback_sources": ["yelp", "manual"],
       "retry_failed": True,
       "max_retries": 3
   }
   ```

3. Monitor API quotas:
   ```python
   # Check remaining quotas
   quotas = get_api_quotas()
   for api, quota in quotas.items():
       print(f"{api}: {quota['used']}/{quota['limit']}")
   ```

## Debugging Tools

### 1. Enable Debug Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('leadfactory')

# Or set via environment variable
os.environ['LOG_LEVEL'] = 'DEBUG'
```

### 2. Request Tracing

```python
# Enable request tracing
headers = {
    'X-API-Key': api_key,
    'X-Request-ID': str(uuid.uuid4())  # Track request through system
}

response = requests.get(url, headers=headers)
print(f"Request ID: {headers['X-Request-ID']}")
print(f"Response ID: {response.headers.get('X-Request-ID')}")
```

### 3. Health Check Script

```python
#!/usr/bin/env python3
import requests
import sys

def check_leadfactory_health(base_url, api_key):
    checks = {
        'API Health': f"{base_url}/health",
        'Database': f"{base_url}/api/v1/health/database",
        'Redis': f"{base_url}/api/v1/health/redis",
        'External APIs': f"{base_url}/api/v1/health/external"
    }

    headers = {'X-API-Key': api_key}
    all_healthy = True

    for name, url in checks.items():
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                print(f"✓ {name}: Healthy")
            else:
                print(f"✗ {name}: Unhealthy (Status: {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"✗ {name}: Failed ({str(e)})")
            all_healthy = False

    return all_healthy

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "https://api.leadfactory.com"
    api_key = os.getenv('LEADFACTORY_API_KEY', 'your-api-key')

    if check_leadfactory_health(base_url, api_key):
        print("\nAll systems operational")
        sys.exit(0)
    else:
        print("\nSome systems are experiencing issues")
        sys.exit(1)
```

## Getting Help

### Support Channels

1. **Documentation**: https://docs.leadfactory.com
2. **API Status**: https://status.leadfactory.com
3. **Email Support**: support@leadfactory.com
4. **Emergency Hotline**: +1-555-LEAD-911 (for critical production issues)

### When Contacting Support

Please provide:
1. API key (first 8 characters only)
2. Request ID or Pipeline ID
3. Timestamp of issue
4. Error messages and status codes
5. Steps to reproduce
6. Expected vs actual behavior

### Useful Commands

```bash
# Check system status
curl https://status.leadfactory.com/api/v2/status.json

# Get current incidents
curl https://status.leadfactory.com/api/v2/incidents.json

# Test connectivity
ping api.leadfactory.com
traceroute api.leadfactory.com

# Check DNS resolution
nslookup api.leadfactory.com
dig api.leadfactory.com

# Test SSL certificate
openssl s_client -connect api.leadfactory.com:443 -servername api.leadfactory.com
```

## Prevention Best Practices

1. **Monitor proactively**: Set up alerts for error rates, response times
2. **Test in staging**: Always test changes in staging environment first
3. **Use circuit breakers**: Prevent cascading failures
4. **Implement retries**: With exponential backoff
5. **Cache appropriately**: Reduce API calls and improve performance
6. **Keep SDKs updated**: Use latest versions for bug fixes and improvements
7. **Review logs regularly**: Catch issues before they become critical
