# LeadFactory API Documentation

## Overview

LeadFactory provides a comprehensive REST API for lead generation, processing, and delivery. The API is organized around REST principles with predictable URLs, JSON request/response bodies, and standard HTTP response codes.

## Base URL

```
Production: https://api.leadfactory.com
Staging: https://staging-api.leadfactory.com
Development: http://localhost:8000
```

## Authentication

The API uses two authentication methods:

### API Key Authentication

Include your API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://api.leadfactory.com/api/v1/health
```

### JWT Bearer Token

For user-specific operations, use JWT tokens:

```bash
curl -H "Authorization: Bearer your-jwt-token" https://api.leadfactory.com/api/v1/user/profile
```

## Rate Limiting

- API calls are limited to 1000 requests per hour per API key
- Burst limit: 100 requests per minute
- Rate limit headers are included in responses:
  - `X-RateLimit-Limit`: Maximum requests per hour
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

## Common Response Codes

- `200 OK`: Request succeeded
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Valid authentication but insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Error Response Format

```json
{
  "error": {
    "code": "invalid_request",
    "message": "The zip_code parameter is required",
    "field": "zip_code",
    "request_id": "req_123abc"
  }
}
```

## Endpoints

### Health Check

#### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "application": "leadfactory-api",
  "version": "1.0.0"
}
```

### Payment API

#### POST /api/v1/payments/checkout

Create a Stripe checkout session for audit purchases.

**Request:**
```json
{
  "customer_email": "customer@example.com",
  "customer_name": "John Doe",
  "audit_type": "seo",
  "amount": 9900,
  "metadata": {
    "company": "Acme Corp"
  }
}
```

**Response:**
```json
{
  "session_id": "cs_test_123",
  "session_url": "https://checkout.stripe.com/pay/cs_test_123",
  "payment_intent_id": "pi_123",
  "publishable_key": "pk_test_123"
}
```

#### POST /api/v1/payments/webhook

Stripe webhook endpoint for payment events.

**Headers:**
- `stripe-signature`: Stripe webhook signature

**Note:** This endpoint is called by Stripe, not by your application.

#### GET /api/v1/payments/status/{payment_id}

Get payment status by ID.

**Response:**
```json
{
  "id": "pi_123",
  "status": "succeeded",
  "customer_email": "customer@example.com",
  "customer_name": "John Doe",
  "amount": 9900,
  "currency": "usd",
  "audit_type": "seo",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:01:00Z"
}
```

#### POST /api/v1/payments/refund/{payment_id}

Refund a payment (requires API key authentication).

**Request:**
```json
{
  "amount": 5000  // Optional, refunds full amount if not specified
}
```

**Response:**
```json
{
  "status": "refunded",
  "refund_id": "re_123",
  "amount": 5000,
  "payment_id": "pi_123"
}
```

### IP Rotation API

#### GET /api/v1/ip-rotation/status

Get current IP rotation status.

**Response:**
```json
{
  "current_pool": "pool_1",
  "current_ip": "192.168.1.100",
  "rotation_enabled": true,
  "last_rotation": "2024-01-01T00:00:00Z",
  "health_metrics": {
    "success_rate": 0.95,
    "response_time_ms": 250,
    "total_requests": 10000
  }
}
```

#### POST /api/v1/ip-rotation/rotate

Manually trigger IP rotation.

**Request:**
```json
{
  "reason": "High failure rate detected",
  "force": false
}
```

**Response:**
```json
{
  "success": true,
  "old_pool": "pool_1",
  "new_pool": "pool_2",
  "new_ip": "192.168.1.101",
  "rotation_time": "2024-01-01T00:05:00Z"
}
```

### Pipeline API

#### POST /api/v1/pipeline/start

Start a lead generation pipeline.

**Request:**
```json
{
  "zip_codes": ["10001", "10002"],
  "verticals": ["hvac", "plumbing"],
  "options": {
    "enrich": true,
    "dedupe": true,
    "score": true,
    "send_emails": false
  }
}
```

**Response:**
```json
{
  "pipeline_id": "pipe_123",
  "status": "started",
  "estimated_completion": "2024-01-01T01:00:00Z",
  "stages": [
    "scrape",
    "enrich",
    "dedupe",
    "score"
  ]
}
```

#### GET /api/v1/pipeline/status/{pipeline_id}

Get pipeline execution status.

**Response:**
```json
{
  "pipeline_id": "pipe_123",
  "status": "running",
  "progress": {
    "scrape": "completed",
    "enrich": "running",
    "dedupe": "pending",
    "score": "pending"
  },
  "statistics": {
    "businesses_found": 150,
    "businesses_enriched": 75,
    "businesses_deduped": 0,
    "businesses_scored": 0
  },
  "started_at": "2024-01-01T00:00:00Z",
  "estimated_completion": "2024-01-01T01:00:00Z"
}
```

### Logs API

#### GET /api/v1/logs

Retrieve system logs with filtering.

**Query Parameters:**
- `business_id`: Filter by business ID
- `log_type`: Filter by type (llm, raw_html)
- `start_date`: Start date (ISO 8601)
- `end_date`: End date (ISO 8601)
- `search`: Search query
- `limit`: Results per page (default: 50)
- `offset`: Pagination offset
- `sort_by`: Sort field (timestamp, business_id, log_type)
- `sort_order`: Sort order (asc, desc)

**Response:**
```json
{
  "logs": [
    {
      "id": 123,
      "business_id": 456,
      "log_type": "llm",
      "content": "Processing business data...",
      "timestamp": "2024-01-01T00:00:00Z",
      "metadata": {
        "model_version": "gpt-4",
        "tokens_used": 150
      }
    }
  ],
  "total": 1000,
  "limit": 50,
  "offset": 0
}
```

### A/B Testing API

#### GET /api/v1/ab-tests

List active A/B tests.

**Response:**
```json
{
  "tests": [
    {
      "id": "test_123",
      "name": "Pricing Test - SEO Audit",
      "type": "pricing",
      "status": "active",
      "variants": [
        {
          "id": "control",
          "name": "Original Price",
          "allocation": 0.5
        },
        {
          "id": "variant_a",
          "name": "10% Discount",
          "allocation": 0.5
        }
      ],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /api/v1/ab-tests/{test_id}/event

Record an A/B test event.

**Request:**
```json
{
  "user_id": "user_123",
  "event_type": "conversion",
  "variant_id": "variant_a",
  "metadata": {
    "purchase_amount": 9900
  }
}
```

**Response:**
```json
{
  "success": true,
  "event_id": "evt_123"
}
```

## Webhooks

LeadFactory can send webhooks for various events:

### Payment Events

- `payment.succeeded`: Payment completed successfully
- `payment.failed`: Payment failed
- `payment.refunded`: Payment refunded

### Pipeline Events

- `pipeline.completed`: Pipeline execution completed
- `pipeline.failed`: Pipeline execution failed

### Email Events

- `email.delivered`: Email delivered successfully
- `email.bounced`: Email bounced
- `email.opened`: Email opened
- `email.clicked`: Link clicked in email

### Webhook Payload Format

```json
{
  "id": "evt_123",
  "type": "payment.succeeded",
  "created": 1640995200,
  "data": {
    "object": {
      // Event-specific data
    }
  }
}
```

### Webhook Security

All webhooks include a signature in the `X-LeadFactory-Signature` header. Verify webhooks using:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):  # pragma: allowlist secret
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Code Examples

### Python

```python
import requests

# Initialize client
api_key = "your-api-key"  # pragma: allowlist secret
base_url = "https://api.leadfactory.com"

headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json"
}

# Start a pipeline
response = requests.post(
    f"{base_url}/api/v1/pipeline/start",
    headers=headers,
    json={
        "zip_codes": ["10001"],
        "verticals": ["hvac"],
        "options": {
            "enrich": True,
            "dedupe": True,
            "score": True
        }
    }
)

pipeline = response.json()
print(f"Started pipeline: {pipeline['pipeline_id']}")

# Check status
status_response = requests.get(
    f"{base_url}/api/v1/pipeline/status/{pipeline['pipeline_id']}",
    headers=headers
)

status = status_response.json()
print(f"Pipeline status: {status['status']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const apiKey = 'your-api-key';  // pragma: allowlist secret
const baseURL = 'https://api.leadfactory.com';

const client = axios.create({
  baseURL,
  headers: {
    'X-API-Key': apiKey,
    'Content-Type': 'application/json'
  }
});

// Start a pipeline
async function startPipeline() {
  try {
    const response = await client.post('/api/v1/pipeline/start', {
      zip_codes: ['10001'],
      verticals: ['hvac'],
      options: {
        enrich: true,
        dedupe: true,
        score: true
      }
    });

    console.log(`Started pipeline: ${response.data.pipeline_id}`);
    return response.data.pipeline_id;
  } catch (error) {
    console.error('Error starting pipeline:', error.response.data);
  }
}

// Check status
async function checkStatus(pipelineId) {
  try {
    const response = await client.get(`/api/v1/pipeline/status/${pipelineId}`);
    console.log(`Pipeline status: ${response.data.status}`);
    return response.data;
  } catch (error) {
    console.error('Error checking status:', error.response.data);
  }
}

// Usage
(async () => {
  const pipelineId = await startPipeline();
  if (pipelineId) {
    setTimeout(() => checkStatus(pipelineId), 5000);
  }
})();
```

### cURL

```bash
# Start a pipeline
curl -X POST https://api.leadfactory.com/api/v1/pipeline/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "zip_codes": ["10001"],
    "verticals": ["hvac"],
    "options": {
      "enrich": true,
      "dedupe": true,
      "score": true
    }
  }'

# Check status
curl -X GET https://api.leadfactory.com/api/v1/pipeline/status/pipe_123 \
  -H "X-API-Key: your-api-key"
```

## SDK Support

Official SDKs are available for:

- Python: `pip install leadfactory`
- Node.js: `npm install @leadfactory/sdk`
- Ruby: `gem install leadfactory`
- Go: `go get github.com/leadfactory/leadfactory-go`

## Support

For API support:
- Email: api-support@leadfactory.com
- Documentation: https://docs.leadfactory.com
- Status Page: https://status.leadfactory.com
