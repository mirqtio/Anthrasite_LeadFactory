# Backend Implementation Gaps Analysis

## Date: 2025-05-30

This document identifies functional gaps between the Anthrasite LeadFactory v1.3 specification and the current backend implementation. Each gap has been converted into a discrete task for tracking and implementation.

## Summary of Gaps Identified

### 1. **Missing CLI Commands** (Task #16)
- **Gap**: Score and mockup pipeline stages are not exposed through the CLI framework
- **Spec Reference**: Sections 4 (Scoring) and 5 (Mockup generation)
- **Current State**: Only accessible via legacy bin/ scripts
- **Impact**: Inconsistent interface for pipeline operations

### 2. **Tier-Based Processing Not Implemented** (Task #17)
- **Gap**: System accepts tier parameter but doesn't implement tier-specific processing logic
- **Spec Reference**: Section 2 - Three tiers with different API calls
  - Tier-1: Basic scraping only
  - Tier-2: Adds ScreenshotOne + PageSpeed
  - Tier-3: Adds SEMrush Site Audit
- **Current State**: Tier parameter accepted but ignored
- **Impact**: All businesses processed the same regardless of tier

### 3. **No A/B Testing Implementation** (Task #18)
- **Gap**: Email variant A/B testing not implemented despite database support
- **Spec Reference**: Section 2 - "variant A/B testing"
- **Current State**: variant_id field exists in email_queue table but unused
- **Impact**: Cannot run variant campaigns or track performance

### 4. **Missing LLM Fallback Mechanism** (Task #19)
- **Gap**: No systematic fallback between GPT-4o and Claude on failures
- **Spec Reference**: Section 2 - "GPT-4o default; Claude fallback on rate-limit or cost spike"
- **Current State**: Single LLM usage without fallback
- **Impact**: Pipeline failures when primary LLM unavailable

### 5. **MOCKUP_ENABLED Flag Not Implemented** (Task #20)
- **Gap**: No control flag for tier-based mockup generation
- **Spec Reference**: Sections 2 & 5 - MOCKUP_ENABLED false for Tier-1, true for Tier-2/3
- **Current State**: Mockups always generated regardless of tier
- **Impact**: Unnecessary processing and costs for Tier-1

### 6. **No Automatic IP Pool Switching** (Task #21)
- **Gap**: No automatic switching to dedicated IP pool on bounce threshold
- **Spec Reference**: Section 2 - "auto-switch to dedicated sub-user if bounce > 2%"
- **Current State**: Manual SendGrid configuration only
- **Impact**: Risk of deliverability issues without automatic mitigation

### 7. **Missing GPU Auto-Scaling** (Task #22)
- **Gap**: No automatic GPU provisioning for large personalization queues
- **Spec Reference**: Section 2 - "auto-spin Hetzner GPU when personalisation_queue > 2000"
- **Current State**: No GPU management or auto-scaling
- **Impact**: Potential bottlenecks during high-volume processing

## Additional Observations

### Features Present but Not Exposed:
- Scoring engine exists (`leadfactory/pipeline/score.py`) but not in CLI
- Mockup generation exists (`leadfactory/pipeline/mockup.py`) but not in CLI
- Screenshot functionality exists separately from mockup generation

### Features with Partial Implementation:
- SendGrid webhook handler exists for bounce tracking
- Database schema supports variants and tiers
- Cost tracking infrastructure exists but not all cost gates implemented

### Features Working as Specified:
- Scrape, enrich, dedupe, and email pipeline stages
- PostgreSQL database with proper schema
- Deduplication with Ollama Llama-3
- Basic SendGrid email sending
- BDD test framework

## Next Steps

1. **Priority 1**: Implement missing CLI commands (Task #16) to ensure consistent interface
2. **Priority 2**: Implement tier-based processing (Task #17) for proper API usage
3. **Priority 3**: Implement LLM fallback (Task #19) for reliability
4. **Priority 4**: Implement MOCKUP_ENABLED flag (Task #20) for cost control
5. **Priority 5**: Implement automatic IP switching (Task #21) for deliverability
6. **Priority 6**: Implement A/B testing (Task #18) for optimization
7. **Priority 7**: Implement GPU auto-scaling (Task #22) for performance

Each task should include:
1. Implementation of the missing functionality
2. Automated test coverage (unit and BDD tests)
3. Integration with existing pipeline components
4. Documentation updates
5. CI/CD pipeline validation

## Testing Strategy

For each gap:
1. Write BDD scenarios matching spec requirements
2. Implement unit tests for new components
3. Add integration tests for pipeline flow
4. Ensure all tests pass in CI before marking complete
5. Update documentation with configuration examples

## Success Criteria

- All pipeline stages accessible via CLI
- Tier-based processing reduces unnecessary API calls
- A/B testing enables variant campaigns
- LLM fallback prevents pipeline failures
- Automatic thresholds protect deliverability
- GPU scaling handles high-volume batches
- All BDD tests pass matching specification scenarios
