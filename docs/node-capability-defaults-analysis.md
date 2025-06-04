# NodeCapability Defaults Analysis

## Current State Assessment

This document analyzes the existing NodeCapability default configurations in the LeadFactory pipeline system and identifies areas for improvement to better align with current infrastructure requirements.

## Current Default Configuration

### API Configurations

| API | Enabled by Default | Cost (cents) | Budget Required | Required Environment Variables |
|-----|-------------------|--------------|-----------------|--------------------------------|
| Wappalyzer | ✅ Yes | 0.0 | ❌ No | None (built-in library) |
| PageSpeed Insights | ✅ Yes | 0.0 | ❌ No | PAGESPEED_API_KEY |
| ScreenshotOne | ✅ Yes | 1.0 | ✅ Yes | SCREENSHOT_ONE_API_KEY, SCREENSHOT_ONE_KEY |
| SEMrush | ❌ No | 10.0 | ✅ Yes | SEMRUSH_API_KEY, SEMRUSH_KEY |
| OpenAI | ✅ Yes | 5.0 | ✅ Yes | OPENAI_API_KEY |

### Node Capabilities

#### ENRICH Node Capabilities
1. **tech_stack_analysis**
   - Default: ✅ Enabled
   - Cost: 0.0 cents
   - APIs: wappalyzer
   - Input: website

2. **core_web_vitals**
   - Default: ✅ Enabled
   - Cost: 0.0 cents
   - APIs: pagespeed
   - Input: website

3. **screenshot_capture**
   - Default: ✅ Enabled
   - Cost: 1.0 cents
   - APIs: screenshot_one
   - Input: website

4. **semrush_site_audit**
   - Default: ❌ Disabled
   - Cost: 10.0 cents
   - APIs: semrush
   - Input: website

#### FINAL_OUTPUT Node Capabilities
1. **mockup_generation**
   - Default: ✅ Enabled
   - Cost: 5.0 cents
   - APIs: openai
   - Input: website, name

2. **email_generation**
   - Default: ✅ Enabled
   - Cost: 5.0 cents
   - APIs: openai
   - Input: website, name

## Infrastructure Alignment Issues

### 1. Cost vs Value Misalignment

**Issue**: Some high-cost capabilities are enabled by default without clear business value justification.

- **Screenshot capture (1 cent)**: Enabled by default but may not provide sufficient value for all use cases
- **OpenAI generation (5 cents each)**: Two capabilities add 10 cents per lead, significant cost for large-scale processing

**Impact**: Unnecessary cost accumulation in budget-constrained environments.

### 2. API Availability Dependencies

**Issue**: Default configurations don't account for API key availability in different deployment environments.

- **PageSpeed API**: Requires API key but is free - should handle graceful degradation
- **ScreenshotOne**: Expensive API enabled by default regardless of business model
- **SEMrush**: Correctly disabled by default due to high cost

**Impact**: Pipeline failures or reduced functionality when expected APIs are unavailable.

### 3. Audit Business Model Misalignment

**Issue**: Current defaults optimized for general lead generation rather than audit-focused business model.

- **SEMrush disabled**: High-value for audit identification but disabled due to cost
- **Screenshot enabled**: Lower value for audit identification but enabled
- **Performance analysis**: Critical for audit model but no cost optimization

**Impact**: Missing opportunities for audit lead identification while incurring costs for less valuable capabilities.

### 4. Environment-Specific Configuration Gaps

**Issue**: Single default configuration doesn't accommodate different deployment environments.

- **Development**: Should prioritize free/cheap APIs for testing
- **Production**: Should balance cost and quality based on business model
- **Demo/MVP**: Should minimize costs while maintaining core functionality

**Impact**: Suboptimal resource utilization across different environments.

## Performance Bottlenecks

### 1. Synchronous API Dependencies

**Issue**: All enabled capabilities must complete successfully, creating potential bottlenecks.

- PageSpeed API: 5-10 second response times
- ScreenshotOne API: 3-5 second response times
- OpenAI API: 2-8 second response times (varies by model)

**Impact**: Extended pipeline execution times when all capabilities are enabled.

### 2. Budget Calculation Complexity

**Issue**: Current cost estimation doesn't account for capability combinations or failed requests.

- Multiple OpenAI calls (mockup + email) = 10 cents per lead
- Screenshot + multiple AI calls = 11+ cents per lead
- No consideration for API failure retry costs

**Impact**: Budget overruns and unpredictable cost scaling.

## Recommended Default Updates

### 1. Environment-Aware Defaults

```python
# Proposed environment-based configuration
ENVIRONMENT_DEFAULTS = {
    "development": {
        "screenshot_capture": False,  # Reduce costs in dev
        "semrush_site_audit": False,
        "mockup_generation": False,   # Reduce OpenAI costs
        "email_generation": True,     # Keep one AI capability for testing
    },
    "production_audit": {
        "screenshot_capture": False,  # Not critical for audit identification
        "semrush_site_audit": True,  # High value for audit model
        "mockup_generation": True,
        "email_generation": True,
    },
    "production_general": {
        "screenshot_capture": True,
        "semrush_site_audit": False, # Too expensive for general leads
        "mockup_generation": True,
        "email_generation": True,
    }
}
```

### 2. Cost-Aware Capability Prioritization

```python
# Proposed capability tiers by value/cost ratio
CAPABILITY_TIERS = {
    "essential": [  # Always enabled, low/no cost
        "tech_stack_analysis",
        "core_web_vitals",
    ],
    "high_value": [  # Enabled when budget allows, high ROI
        "email_generation",  # Core business value
        "semrush_site_audit",  # High audit value when budget allows
    ],
    "optional": [  # Enabled only with specific requirements
        "screenshot_capture",  # Visual appeal but high cost/value ratio
        "mockup_generation",   # Secondary to email generation
    ]
}
```

### 3. API Availability Graceful Degradation

```python
# Proposed fallback configuration
API_FALLBACKS = {
    "pagespeed": {
        "fallback": "lighthouse_cli",  # Local Lighthouse as backup
        "degraded_mode": "skip_performance_analysis",
    },
    "screenshot_one": {
        "fallback": "puppeteer_local",  # Local screenshot generation
        "degraded_mode": "skip_screenshot",
    },
    "openai": {
        "fallback": "template_generation",  # Template-based fallback
        "degraded_mode": "skip_ai_generation",
    }
}
```

## Implementation Priority

### High Priority (Immediate Impact)
1. Add environment variable for deployment mode (DEV/PROD_AUDIT/PROD_GENERAL)
2. Implement cost-tier based default selection
3. Add API availability checking with graceful degradation

### Medium Priority (Performance & Reliability)
1. Implement capability timeout configurations
2. Add retry logic with cost tracking
3. Create budget-aware capability selection

### Low Priority (Advanced Features)
1. Dynamic capability adjustment based on lead quality
2. A/B testing framework for capability combinations
3. Machine learning-based capability optimization

## Success Metrics

### Cost Optimization
- **Target**: 30% reduction in per-lead processing costs
- **Measurement**: Average cost per lead across different environments

### Performance Improvement
- **Target**: 25% reduction in average pipeline execution time
- **Measurement**: End-to-end processing time for standard lead batch

### Reliability Enhancement
- **Target**: 95% success rate regardless of API availability
- **Measurement**: Pipeline completion rate across different API availability scenarios

### Business Alignment
- **Target**: 40% improvement in audit lead identification rate
- **Measurement**: Conversion rate of processed leads to audit opportunities

## Next Steps

1. **Implement environment detection** - Add deployment environment configuration
2. **Create capability tier system** - Implement tiered defaults based on business value
3. **Add API availability checking** - Graceful degradation when APIs unavailable
4. **Update cost estimation** - Include retry costs and capability combinations
5. **Create migration plan** - Ensure backward compatibility during transition

This analysis provides the foundation for implementing more intelligent and business-aligned NodeCapability defaults in the LeadFactory pipeline system.
