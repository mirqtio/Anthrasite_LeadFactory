# LLM Fallback System Guide

This guide covers the comprehensive LLM fallback system implemented for the LeadFactory pipeline, providing robust AI processing with automatic provider fallback, cost tracking, and intelligent error handling.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Fallback Strategies](#fallback-strategies)
5. [Cost Management](#cost-management)
6. [Error Handling](#error-handling)
7. [Integration Examples](#integration-examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Overview

The LLM fallback system provides a unified interface to multiple LLM providers (OpenAI, Anthropic, Ollama) with automatic failover, cost optimization, and intelligent error recovery. Key features include:

- **Automatic Fallback**: Seamlessly switches between providers on failure
- **Cost Optimization**: Choose providers based on cost, quality, or custom strategies
- **Rate Limiting**: Built-in rate limiting for all providers
- **Cost Tracking**: Real-time cost monitoring with budget controls
- **Caching**: Request caching to reduce costs and latency
- **Error Classification**: Intelligent error handling with provider-specific recovery

## Quick Start

### Basic Usage

```python
from leadfactory.llm import LLMClient

# Initialize client (loads configuration from environment)
client = LLMClient()

# Make a chat completion request
response = client.chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ],
    temperature=0.7,
    max_tokens=100
)

# Access the response
content = response['choices'][0]['message']['content']
provider = response['provider']
usage = response['usage']

print(f"Response from {provider}: {content}")
print(f"Usage: {usage}")
```

### Environment Setup

Create a `.env` file with your API keys:

```bash
# Provider API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OLLAMA_HOST=http://localhost:11434

# Fallback Configuration
LLM_FALLBACK_STRATEGY=smart_fallback
LLM_MAX_FALLBACK_ATTEMPTS=3

# Cost Controls
LLM_MAX_COST_PER_REQUEST=1.0
LLM_DAILY_COST_LIMIT=50.0
LLM_MONTHLY_COST_LIMIT=1000.0

# Rate Limiting
OPENAI_RATE_LIMIT_RPM=60
ANTHROPIC_RATE_LIMIT_TPM=100000
```

## Configuration

### Configuration Options

The system supports extensive configuration through environment variables:

#### General Settings
- `LLM_FALLBACK_STRATEGY`: Fallback strategy (`smart_fallback`, `cost_optimized`, `quality_optimized`, `round_robin`, `fail_fast`)
- `LLM_MAX_FALLBACK_ATTEMPTS`: Maximum number of providers to try (default: 3)
- `LLM_DEFAULT_TEMPERATURE`: Default temperature for requests (default: 0.7)
- `LLM_DEFAULT_MAX_TOKENS`: Default max tokens (default: 1000)
- `LLM_ENABLE_CACHING`: Enable request caching (default: true)
- `LLM_LOG_REQUESTS`: Log all requests (default: true)

#### Provider-Specific Settings

**OpenAI Configuration:**
```bash
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4
OPENAI_ENABLED=true
OPENAI_TIMEOUT=30
OPENAI_RATE_LIMIT_RPM=60
OPENAI_RATE_LIMIT_TPM=60000
OPENAI_COST_PER_1K_TOKENS=0.03
OPENAI_PRIORITY=2
OPENAI_MAX_RETRIES=3
OPENAI_RETRY_DELAY=1.0
```

**Anthropic Configuration:**
```bash
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-3-sonnet-20240229
ANTHROPIC_ENABLED=true
ANTHROPIC_TIMEOUT=30
ANTHROPIC_RATE_LIMIT_RPM=50
ANTHROPIC_RATE_LIMIT_TPM=100000
ANTHROPIC_COST_PER_1K_TOKENS=0.015
ANTHROPIC_PRIORITY=3
ANTHROPIC_MAX_RETRIES=3
ANTHROPIC_RETRY_DELAY=1.0
```

**Ollama Configuration:**
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_ENABLED=true
OLLAMA_TIMEOUT=60
OLLAMA_COST_PER_1K_TOKENS=0.0
OLLAMA_PRIORITY=1
OLLAMA_MAX_RETRIES=2
OLLAMA_RETRY_DELAY=0.5
```

#### Cost Control Settings
```bash
LLM_MAX_COST_PER_REQUEST=1.0    # Maximum cost per request
LLM_DAILY_COST_LIMIT=50.0       # Daily spending limit
LLM_MONTHLY_COST_LIMIT=1000.0   # Monthly spending limit
LLM_COST_TRACKING=true          # Enable cost tracking
LLM_BUDGET_ALERT_THRESHOLD=0.8  # Alert when 80% of budget used
```

### Programmatic Configuration

```python
from leadfactory.llm import LLMConfig, ProviderConfig, FallbackStrategy

# Create custom configuration
config = LLMConfig()
config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED
config.max_fallback_attempts = 5

# Add custom provider
config.providers['custom'] = ProviderConfig(
    name='custom',
    api_key='your_key',
    default_model='custom-model',
    cost_per_1k_tokens=0.01
)

# Initialize client with custom config
client = LLMClient(config)
```

## Fallback Strategies

### Smart Fallback (Default)
Balances cost and reliability by trying Ollama (free) first, then prioritizing by provider priority.

```python
config.fallback_strategy = FallbackStrategy.SMART_FALLBACK
```

**Order**: Ollama → Highest Priority → Lower Priority

### Cost Optimized
Always tries the cheapest provider first.

```python
config.fallback_strategy = FallbackStrategy.COST_OPTIMIZED
```

**Order**: $0.00 → $0.01 → $0.03 (by cost per 1k tokens)

### Quality Optimized
Prioritizes providers by quality/priority rating.

```python
config.fallback_strategy = FallbackStrategy.QUALITY_OPTIMIZED
```

**Order**: Priority 3 → Priority 2 → Priority 1

### Round Robin
Fixed order regardless of cost or quality.

```python
config.fallback_strategy = FallbackStrategy.ROUND_ROBIN
```

**Order**: Ollama → OpenAI → Anthropic

### Fail Fast
Only tries the first available provider.

```python
config.fallback_strategy = FallbackStrategy.FAIL_FAST
```

**Order**: First available provider only

## Cost Management

### Real-time Cost Tracking

```python
# Check provider costs
status = client.get_provider_status()
for provider, info in status.items():
    print(f"{provider}: ${info.get('daily_cost', 0):.4f} today")

# Reset cost tracking
client.reset_cost_tracking('openai')  # Reset single provider
client.reset_cost_tracking()          # Reset all providers
```

### Budget Controls

The system automatically enforces budget limits:

```python
from leadfactory.llm.exceptions import LLMQuotaExceededError

try:
    response = client.chat_completion(messages)
except LLMQuotaExceededError as e:
    print(f"Budget exceeded: {e}")
```

### Cost Estimation

```python
# Estimate cost before making request
estimated_tokens = client._estimate_tokens(messages, max_tokens=100)
cost = config.estimate_request_cost(estimated_tokens, 'openai')
print(f"Estimated cost: ${cost:.4f}")
```

## Error Handling

### Error Types

The system classifies errors into specific types for intelligent handling:

```python
from leadfactory.llm.exceptions import (
    LLMConnectionError,      # Network issues
    LLMRateLimitError,       # Rate limits exceeded
    LLMAuthenticationError,  # Invalid API keys
    LLMQuotaExceededError,   # Budget/quota limits
    LLMModelNotFoundError,   # Invalid model
    LLMTimeoutError,         # Request timeouts
    LLMValidationError,      # Input validation issues
    AllProvidersFailedError  # All providers failed
)

try:
    response = client.chat_completion(messages)
except LLMRateLimitError as e:
    print(f"Rate limited on {e.provider}, retry after {e.retry_after}s")
except AllProvidersFailedError as e:
    print(f"All providers failed: {e.provider_errors}")
```

### Retry Logic

```python
import time
from leadfactory.llm.exceptions import LLMRateLimitError

def robust_completion(client, messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.chat_completion(messages)
        except LLMRateLimitError as e:
            if e.retry_after and attempt < max_retries - 1:
                time.sleep(e.retry_after)
                continue
            raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Integration Examples

### Pipeline Integration

```python
from leadfactory.llm import LLMClient, LLMError

class MyPipelineNode:
    def __init__(self):
        self.llm_client = LLMClient()

    def process(self, data):
        try:
            response = self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a business analyst."},
                    {"role": "user", "content": f"Analyze this business: {data}"}
                ],
                temperature=0.3,
                max_tokens=500
            )

            return {
                'success': True,
                'content': response['choices'][0]['message']['content'],
                'provider': response['provider'],
                'cost': response.get('cost', 0)
            }

        except LLMError as e:
            return {
                'success': False,
                'error': str(e),
                'provider': getattr(e, 'provider', None)
            }
```

### Batch Processing

```python
async def process_batch(client, items, batch_size=10):
    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_results = []

        for item in batch:
            try:
                response = client.chat_completion(
                    messages=[{"role": "user", "content": item}]
                )
                batch_results.append({
                    'success': True,
                    'content': response['choices'][0]['message']['content']
                })
            except Exception as e:
                batch_results.append({
                    'success': False,
                    'error': str(e)
                })

        results.extend(batch_results)

        # Check costs periodically
        status = client.get_provider_status()
        total_cost = sum(p.get('daily_cost', 0) for p in status.values())
        if total_cost > 10.0:  # Stop if over $10
            break

    return results
```

## Best Practices

### 1. Provider Selection
- Use **Smart Fallback** for balanced cost/quality
- Use **Cost Optimized** for high-volume, low-criticality tasks
- Use **Quality Optimized** for important tasks requiring best results

### 2. Cost Management
- Set realistic daily/monthly budgets
- Monitor costs regularly using `get_provider_status()`
- Use caching for repeated requests
- Choose appropriate models for each task

### 3. Error Handling
- Always handle `AllProvidersFailedError`
- Implement retry logic for rate limits
- Log errors for debugging
- Have fallback responses for critical paths

### 4. Performance Optimization
- Enable caching for repeated requests
- Use appropriate timeouts for your use case
- Monitor rate limits to avoid delays
- Batch requests when possible

### 5. Security
- Store API keys in environment variables
- Rotate API keys regularly
- Monitor usage for unusual patterns
- Use least-privilege API keys when available

## Troubleshooting

### Common Issues

#### "No providers available"
```python
# Check provider status
client = LLMClient()
status = client.get_provider_status()
print(status)

# Verify environment variables
import os
print("OpenAI Key:", bool(os.getenv('OPENAI_API_KEY')))
print("Anthropic Key:", bool(os.getenv('ANTHROPIC_API_KEY')))
print("Ollama Host:", os.getenv('OLLAMA_HOST', 'not set'))
```

#### "All providers failed"
```python
try:
    response = client.chat_completion(messages)
except AllProvidersFailedError as e:
    for provider, error in e.provider_errors.items():
        print(f"{provider}: {error}")
```

#### High costs
```python
# Check current spending
status = client.get_provider_status()
for provider, info in status.items():
    cost = info.get('daily_cost', 0)
    if cost > 0:
        print(f"{provider}: ${cost:.4f} today")

# Reset if needed
client.reset_cost_tracking()
```

#### Rate limiting
```python
# Check rate limit configuration
config = LLMConfig.from_environment()
for name, provider in config.providers.items():
    print(f"{name}: {provider.rate_limit_rpm} RPM, {provider.rate_limit_tpm} TPM")
```

### Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# LLM client will now log all requests and responses
client = LLMClient()
```

Check configuration validation:

```python
config = LLMConfig.from_environment()
issues = config.validate()
if issues:
    print("Configuration issues:")
    for issue in issues:
        print(f"  - {issue}")
```

### Performance Monitoring

```python
import time

def monitor_performance(client, messages):
    start_time = time.time()

    try:
        response = client.chat_completion(messages)
        elapsed = time.time() - start_time

        print(f"Success in {elapsed:.2f}s using {response['provider']}")
        print(f"Tokens: {response['usage']['total_tokens']}")

        return response
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Failed in {elapsed:.2f}s: {e}")
        raise
```

For more examples, see the `examples/llm_fallback_demo.py` script.
