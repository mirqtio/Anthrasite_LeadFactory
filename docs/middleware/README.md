# LeadFactory Budget Guard Middleware

The LeadFactory Budget Guard Middleware provides seamless integration of budget monitoring, cost tracking, and throttling capabilities with popular web frameworks like Express.js, FastAPI, Flask, and Django.

## Features

- 🛡️ **Budget Protection**: Automatically monitor and enforce budget limits
- 🚦 **Smart Throttling**: Rate limiting and request throttling based on costs
- 📊 **Cost Tracking**: Real-time tracking of API usage and costs
- 🔔 **Alert System**: Multi-channel notifications for budget events
- ⚡ **Performance Optimized**: Minimal overhead with caching and async processing
- 🔧 **Framework Agnostic**: Works with Express.js, FastAPI, Flask, Django, and more
- 🎛️ **Highly Configurable**: Environment-based configuration with sensible defaults

## Quick Start

### FastAPI

```python
from fastapi import FastAPI
from leadfactory.middleware import create_fastapi_budget_middleware

app = FastAPI()

# Add budget middleware
app.middleware("http")(create_fastapi_budget_middleware())

@app.post("/api/chat")
async def chat_endpoint():
    # This endpoint is now protected by budget limits
    return {"message": "Hello from protected endpoint!"}
```

### Flask

```python
from flask import Flask
from leadfactory.middleware import create_flask_budget_middleware

app = Flask(__name__)

# Add budget middleware
app.before_request(create_flask_budget_middleware())

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    # This endpoint is now protected by budget limits
    return {"message": "Hello from protected endpoint!"}
```

### Express.js

```javascript
const express = require('express');
// Note: JavaScript/Node.js integration would require a separate package
// This is a conceptual example for the Python-based middleware

const app = express();

// Express.js integration would be implemented via a separate Node.js package
// that communicates with the Python middleware service
app.use('/api', budgetMiddleware);

app.post('/api/chat', (req, res) => {
  res.json({ message: 'Hello from protected endpoint!' });
});
```

## Configuration

### Environment Variables

```bash
# Framework type (optional, auto-detected)
LEADFACTORY_FRAMEWORK=fastapi

# Budget monitoring features
LEADFACTORY_ENABLE_BUDGET_MONITORING=true
LEADFACTORY_ENABLE_COST_TRACKING=true
LEADFACTORY_ENABLE_THROTTLING=true
LEADFACTORY_ENABLE_ALERTING=true

# Request filtering
LEADFACTORY_EXCLUDE_PATHS=/health,/metrics,/status
LEADFACTORY_INCLUDE_ONLY_PATHS=/api,/v1
LEADFACTORY_EXCLUDE_METHODS=OPTIONS,HEAD

# Performance options
LEADFACTORY_ASYNC_PROCESSING=true
LEADFACTORY_CACHE_DECISIONS=true
LEADFACTORY_CACHE_TTL_SECONDS=60

# Error handling
LEADFACTORY_FAIL_OPEN=true
LEADFACTORY_LOG_ERRORS=true
```

### Programmatic Configuration

```python
from leadfactory.middleware import (
    MiddlewareConfig,
    BudgetMiddlewareOptions,
    FrameworkType,
    create_budget_middleware
)

# Create custom configuration
budget_options = BudgetMiddlewareOptions(
    enable_budget_monitoring=True,
    enable_throttling=True,
    exclude_paths=['/health', '/admin'],
    cache_ttl_seconds=120,
    fail_open=False
)

config = MiddlewareConfig(
    framework=FrameworkType.FASTAPI,
    budget_options=budget_options,
    log_level="DEBUG"
)

# Create middleware with custom config
middleware = create_budget_middleware(config)
```

## Custom Extractors

```python
def extract_user_id(request):
    """Extract user ID from JWT token."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    # Decode JWT and extract user ID
    return decode_jwt(token).get('user_id')

def extract_operation(request):
    """Extract operation type from request."""
    if 'chat' in request.path:
        return 'chat_completion'
    elif 'embedding' in request.path:
        return 'text_embedding'
    return 'api_call'

def estimate_cost(request):
    """Estimate request cost based on content."""
    if hasattr(request, 'json'):
        content_length = len(str(request.json))
        return content_length * 0.0001  # $0.0001 per character
    return 0.01

# Configure middleware with custom extractors
budget_options = BudgetMiddlewareOptions(
    custom_user_extractor=extract_user_id,
    custom_operation_extractor=extract_operation,
    custom_cost_extractor=estimate_cost
)
```

## Response Handling

When requests exceed budget limits:

### Throttling (429 Too Many Requests)
```json
{
  "error": "Budget limit exceeded",
  "decision": "throttle",
  "user_id": "user123",
  "model": "gpt-4",
  "retry_after": 60
}
```

### Budget Exceeded (402 Payment Required)
```json
{
  "error": "Budget limit exceeded",
  "decision": "reject",
  "user_id": "user123",
  "model": "gpt-4",
  "retry_after": null
}
```

## Integration Examples

### FastAPI with Advanced Configuration

```python
from fastapi import FastAPI, Request
from leadfactory.middleware import (
    create_fastapi_budget_middleware,
    MiddlewareConfig,
    BudgetMiddlewareOptions
)

app = FastAPI()

def extract_user_from_token(request: Request):
    """Extract user ID from JWT token."""
    auth_header = request.headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return decode_jwt_token(token).get('user_id')
    return None

def estimate_openai_cost(request: Request):
    """Estimate OpenAI API cost based on request."""
    try:
        body = request.json()
        model = body.get('model', 'gpt-3.5-turbo')
        messages = body.get('messages', [])

        # Estimate tokens
        total_chars = sum(len(msg.get('content', '')) for msg in messages)
        estimated_tokens = total_chars // 4

        # Cost per token
        rates = {
            'gpt-4': 0.00003,
            'gpt-3.5-turbo': 0.000002,
        }

        return estimated_tokens * rates.get(model, 0.000002)
    except:
        return 0.01

budget_options = BudgetMiddlewareOptions(
    custom_user_extractor=extract_user_from_token,
    custom_cost_extractor=estimate_openai_cost,
    exclude_paths=['/docs', '/redoc', '/openapi.json'],
    cache_ttl_seconds=30,
    fail_open=True
)

config = MiddlewareConfig(budget_options=budget_options)
app.middleware("http")(create_fastapi_budget_middleware(config))

@app.post("/api/chat")
async def chat_completion(request: Request):
    return {"response": "Chat completion response"}
```

### Flask with Database Integration

```python
from flask import Flask, request, session
from leadfactory.middleware import create_flask_budget_middleware
from your_app.models import User, PricingModel

app = Flask(__name__)

def get_user_from_session():
    """Get user from session or API key."""
    if 'user_id' in session:
        return session['user_id']

    api_key = request.headers.get('X-API-Key')
    if api_key:
        user = User.query.filter_by(api_key=api_key).first()
        return user.id if user else None

    return None

def estimate_cost_from_db(request):
    """Estimate cost using database pricing."""
    endpoint = request.endpoint
    pricing = PricingModel.query.filter_by(endpoint=endpoint).first()

    if pricing:
        return pricing.base_cost

    return 0.01

budget_options = BudgetMiddlewareOptions(
    custom_user_extractor=get_user_from_session,
    custom_cost_extractor=estimate_cost_from_db
)

app.before_request(create_flask_budget_middleware(
    MiddlewareConfig(budget_options=budget_options)
))

@app.route('/api/process', methods=['POST'])
def process_data():
    return {"status": "processed"}
```

## Performance Considerations

### Caching

```python
budget_options = BudgetMiddlewareOptions(
    cache_decisions=True,      # Enable decision caching
    cache_ttl_seconds=60,      # Cache for 60 seconds
    async_processing=True      # Process alerts asynchronously
)
```

### Request Filtering

```python
budget_options = BudgetMiddlewareOptions(
    exclude_paths=[
        '/health', '/metrics', '/status',  # Health checks
        '/static', '/assets',              # Static files
        '/favicon.ico', '/robots.txt'      # Common files
    ],
    exclude_methods=['OPTIONS', 'HEAD'],   # Preflight requests
    include_only_paths=['/api', '/v1']     # Only protect API endpoints
)
```

## Testing

```python
import pytest
from leadfactory.middleware import create_budget_middleware

def test_middleware_integration():
    """Test middleware with mock request."""
    middleware = create_budget_middleware()

    # Create mock request
    class MockRequest:
        def __init__(self, path, headers=None):
            self.path = path
            self.headers = headers or {}

    request = MockRequest(
        path="/api/test",
        headers={"X-User-ID": "test_user"}
    )

    result = middleware.process_request(request)
    assert result is None  # Should allow request
```

## API Reference

### Classes

- `BudgetGuardMiddleware`: Core middleware class
- `MiddlewareConfig`: Main configuration class
- `BudgetMiddlewareOptions`: Budget-specific options
- `FrameworkType`: Supported framework enumeration

### Factory Functions

- `create_budget_middleware()`: Generic middleware
- `create_fastapi_budget_middleware()`: FastAPI middleware
- `create_flask_budget_middleware()`: Flask middleware

## Troubleshooting

### Common Issues

1. **Middleware not triggering**
   - Check that paths are not excluded
   - Verify framework integration is correct
   - Enable debug logging

2. **High latency**
   - Enable caching with appropriate TTL
   - Use async processing for alerts
   - Exclude static file paths

3. **Budget limits not working**
   - Verify budget configuration is loaded
   - Check user extraction is working
   - Review cost estimation logic

### Debug Mode

```python
config = MiddlewareConfig(
    log_level="DEBUG",
    enable_request_logging=True
)
```

## License

This project is licensed under the MIT License.
