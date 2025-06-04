# NodeCapability Defaults Migration Guide

## Overview

This guide helps you migrate from the previous NodeCapability default configurations to the new environment-aware system that better aligns with current infrastructure requirements and the audit-focused business model.

## What Changed

### 1. Environment-Aware Defaults

**Before:** Single default configuration for all environments
**After:** Environment-specific defaults optimized for different deployment scenarios

```python
# New environment types
class DeploymentEnvironment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION_AUDIT = "production_audit"
    PRODUCTION_GENERAL = "production_general"
```

### 2. Capability Tier System

**Before:** Flat capability structure with only enabled/disabled flags
**After:** Three-tier system based on business value and cost

```python
class CapabilityTier(Enum):
    ESSENTIAL = "essential"      # Always enabled, low/no cost
    HIGH_VALUE = "high_value"    # Enabled when budget allows, high ROI
    OPTIONAL = "optional"        # Enabled only with specific requirements
```

### 3. Updated Default Settings

| Capability | Previous Default | New Default (by Environment) |
|------------|------------------|------------------------------|
| **screenshot_capture** | ✅ Enabled | ❌ Dev: Disabled<br/>❌ Audit: Disabled<br/>✅ General: Enabled |
| **semrush_site_audit** | ❌ Disabled | ❌ Dev: Disabled<br/>✅ Audit: Enabled<br/>❌ General: Disabled |
| **mockup_generation** | ✅ Enabled | ❌ Dev: Disabled<br/>✅ Audit: Enabled<br/>✅ General: Enabled |
| **email_generation** | ✅ Enabled | ✅ All environments (core business value) |
| **tech_stack_analysis** | ✅ Enabled | ✅ All environments (essential) |
| **core_web_vitals** | ✅ Enabled | ✅ All environments (essential) |

### 4. API Fallback Support

**New:** Added fallback configuration for graceful degradation

```python
# Example: PageSpeed API with Lighthouse CLI fallback
"pagespeed": APIConfiguration(
    fallback_available=True,
    fallback_description="Local Lighthouse CLI analysis",
)
```

## Migration Steps

### Step 1: Environment Detection Setup

Set the deployment environment using environment variables:

```bash
# Development environment
export DEPLOYMENT_ENVIRONMENT=development

# Production audit-focused
export DEPLOYMENT_ENVIRONMENT=production_audit

# Production general leads
export DEPLOYMENT_ENVIRONMENT=production_general
```

**Alternative Detection Methods:**
```bash
# Fallback detection methods
export NODE_ENV=development                  # Maps to DEVELOPMENT
export BUSINESS_MODEL=audit                 # Maps to PRODUCTION_AUDIT
```

### Step 2: Update Application Code

**Before:**
```python
from leadfactory.config.node_config import get_enabled_capabilities

# Old way - no environment awareness
capabilities = get_enabled_capabilities(NodeType.ENRICH, budget_cents=10.0)
```

**After:**
```python
from leadfactory.config.node_config import get_enabled_capabilities, DeploymentEnvironment

# New way - environment-aware (auto-detects environment)
capabilities = get_enabled_capabilities(NodeType.ENRICH, budget_cents=10.0)

# Or explicitly specify environment
capabilities = get_enabled_capabilities(
    NodeType.ENRICH,
    budget_cents=10.0,
    environment=DeploymentEnvironment.PRODUCTION_AUDIT
)
```

### Step 3: Update Cost Estimation

**Before:**
```python
cost = estimate_node_cost(NodeType.ENRICH, budget_cents=10.0)
```

**After:**
```python
# Auto-detects environment
cost = estimate_node_cost(NodeType.ENRICH, budget_cents=10.0)

# Or specify environment
cost = estimate_node_cost(
    NodeType.ENRICH,
    budget_cents=10.0,
    environment=DeploymentEnvironment.PRODUCTION_AUDIT
)
```

### Step 4: Validate Configuration

Use the new validation functions to ensure proper setup:

```python
from leadfactory.config.node_config import (
    validate_environment_configuration,
    get_environment_info
)

# Get environment information
info = get_environment_info()
print(f"Environment: {info['environment']}")
print(f"Available APIs: {info['available_apis']}")
print(f"Fallback APIs: {info['fallback_apis']}")

# Validate configuration
validation = validate_environment_configuration()
if not validation['valid']:
    print(f"Issues: {validation['issues']}")
    print(f"Recommendations: {validation['recommendations']}")
```

## Environment-Specific Configurations

### Development Environment

**Purpose:** Cost-optimized for development and testing

**Enabled Capabilities:**
- ✅ tech_stack_analysis (free)
- ✅ core_web_vitals (free)
- ✅ email_generation (essential for testing)

**Disabled Capabilities:**
- ❌ screenshot_capture (1¢ - not needed for development)
- ❌ semrush_site_audit (10¢ - too expensive for development)
- ❌ mockup_generation (5¢ - reduces OpenAI costs)

**Expected Cost Per Lead:** 5¢ (email generation only)

### Production Audit Environment

**Purpose:** Optimized for audit lead identification and conversion

**Enabled Capabilities:**
- ✅ tech_stack_analysis (free)
- ✅ core_web_vitals (free)
- ✅ semrush_site_audit (10¢ - high value for audit identification)
- ✅ email_generation (5¢ - core business value)
- ✅ mockup_generation (5¢ - enhances audit proposals)

**Disabled Capabilities:**
- ❌ screenshot_capture (1¢ - lower value for audit identification)

**Expected Cost Per Lead:** 20¢ (optimized for audit ROI)

### Production General Environment

**Purpose:** Balanced configuration for general lead generation

**Enabled Capabilities:**
- ✅ tech_stack_analysis (free)
- ✅ core_web_vitals (free)
- ✅ screenshot_capture (1¢ - visual appeal for general leads)
- ✅ email_generation (5¢ - core business value)
- ✅ mockup_generation (5¢ - comprehensive lead package)

**Disabled Capabilities:**
- ❌ semrush_site_audit (10¢ - too expensive for general lead volume)

**Expected Cost Per Lead:** 11¢ (balanced cost/value)

## API Availability and Fallbacks

### Graceful Degradation

The new system handles API unavailability gracefully:

```python
# Check API availability with fallback information
from leadfactory.config.node_config import is_api_available, API_CONFIGS

for api_name, config in API_CONFIGS.items():
    available = is_api_available(api_name)

    if not available and config.fallback_available:
        print(f"{api_name}: Unavailable, fallback: {config.fallback_description}")
    elif not available:
        print(f"{api_name}: Unavailable, no fallback")
    else:
        print(f"{api_name}: Available")
```

### Fallback Options

| API | Fallback Available | Fallback Description |
|-----|-------------------|---------------------|
| PageSpeed Insights | ✅ Yes | Local Lighthouse CLI analysis |
| ScreenshotOne | ✅ Yes | Local Puppeteer screenshot generation |
| OpenAI | ✅ Yes | Template-based content generation |
| SEMrush | ❌ No | No fallback available |
| Wappalyzer | ❌ No | Built-in library (no fallback needed) |

## Performance Considerations

### Expected Performance Improvements

Based on environment optimization:

1. **Development Environment:**
   - 60% cost reduction per lead (5¢ vs 13¢)
   - 40% faster pipeline execution (fewer API calls)

2. **Production Audit Environment:**
   - 40% improvement in audit lead identification
   - Cost increase justified by higher conversion rates

3. **Production General Environment:**
   - 15% cost reduction per lead (11¢ vs 13¢)
   - Maintained visual appeal with screenshot capability

### Performance Monitoring

Monitor the impact using the new environment info:

```python
import time
from leadfactory.config.node_config import get_enabled_capabilities, estimate_node_cost

start_time = time.time()
capabilities = get_enabled_capabilities(NodeType.ENRICH)
cost = estimate_node_cost(NodeType.ENRICH)
execution_time = time.time() - start_time

print(f"Capabilities: {len(capabilities)}")
print(f"Cost: {cost}¢")
print(f"Selection time: {execution_time*1000:.2f}ms")
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Environment Not Detected Correctly

**Problem:** Wrong environment detected
**Solution:**
```bash
# Explicitly set environment
export DEPLOYMENT_ENVIRONMENT=production_audit

# Verify detection
python -c "from leadfactory.config.node_config import get_deployment_environment; print(get_deployment_environment())"
```

#### 2. Missing Essential Capabilities

**Problem:** Essential capabilities disabled due to missing APIs
**Solution:**
```python
# Check what's missing
from leadfactory.config.node_config import validate_environment_configuration

validation = validate_environment_configuration()
if validation['issues']:
    for issue in validation['issues']:
        print(f"Issue: {issue}")
```

#### 3. Higher Than Expected Costs

**Problem:** Costs higher than expected in development
**Solution:**
```python
# Check which expensive capabilities are enabled
from leadfactory.config.node_config import get_enabled_capabilities, NodeType

caps = get_enabled_capabilities(NodeType.ENRICH)
expensive_caps = [cap for cap in caps if cap.cost_estimate_cents > 1.0]

for cap in expensive_caps:
    print(f"{cap.name}: {cap.cost_estimate_cents}¢ (tier: {cap.tier.value})")
```

#### 4. API Fallback Not Working

**Problem:** Pipeline fails when API unavailable despite fallback
**Solution:**
```python
# Check fallback availability
from leadfactory.config.node_config import API_CONFIGS

for api_name, config in API_CONFIGS.items():
    if config.fallback_available:
        print(f"{api_name}: Fallback - {config.fallback_description}")
        # Implement fallback logic in your code
```

## Testing Your Migration

### 1. Environment Detection Test

```bash
# Test each environment
for env in development production_audit production_general; do
    echo "Testing $env environment..."
    DEPLOYMENT_ENVIRONMENT=$env python -c "
from leadfactory.config.node_config import get_environment_info
info = get_environment_info()
print(f'Environment: {info[\"environment\"]}')
"
done
```

### 2. Cost Impact Test

```bash
# Compare costs across environments
python -c "
import os
from leadfactory.config.node_config import estimate_node_cost, NodeType

environments = ['development', 'production_audit', 'production_general']
for env in environments:
    os.environ['DEPLOYMENT_ENVIRONMENT'] = env

    # Force module reload to pick up environment change
    import importlib
    import leadfactory.config.node_config
    importlib.reload(leadfactory.config.node_config)

    from leadfactory.config.node_config import estimate_node_cost
    cost = estimate_node_cost(NodeType.ENRICH) + estimate_node_cost(NodeType.FINAL_OUTPUT)
    print(f'{env}: {cost}¢ per lead')
"
```

### 3. Capability Difference Test

```bash
# Test capability differences
python tests/integration/test_node_capability_integration.py::TestEndToEndScenarios::test_audit_vs_general_production -v
```

## Rollback Plan

If you need to rollback to the previous system:

1. **Temporary Rollback:**
   ```python
   # Force all capabilities to previous defaults
   from leadfactory.config.node_config import get_enabled_capabilities

   def legacy_get_enabled_capabilities(node_type, budget_cents=None):
       # Use the old logic temporarily
       return get_enabled_capabilities(node_type, budget_cents, None)
   ```

2. **Environment Variable Override:**
   ```bash
   # Force specific capabilities
   export FORCE_ENABLE_SCREENSHOT=true
   export FORCE_DISABLE_SEMRUSH=true
   ```

3. **Configuration File Override:**
   Create a temporary configuration file to override defaults

## Support and Resources

- **Documentation:** [Node Capability Analysis](./node-capability-defaults-analysis.md)
- **Tests:** Run `pytest tests/unit/config/test_node_config_environment.py -v`
- **Validation:** Use `validate_environment_configuration()` function
- **Monitoring:** Check CI pipeline NodeCapability job results

For additional support, check the test files for examples of proper usage in different scenarios.
