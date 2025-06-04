# YAML Scoring Rules Simplification

## Current Format Analysis

### Pain Points Identified

1. **Repetitive condition structures**: Similar conditions are repeated across many rules
2. **Mixed condition types**: Field names like `tech_stack_contains_any` vs `category_contains_any`
3. **Inconsistent naming**: Different condition names for similar operations
4. **Complex nested structures**: Version comparisons require nested dictionaries
5. **Audit-focus missing**: Rules aren't optimized for audit business model
6. **Poor readability**: Conditions are verbose and hard to scan
7. **Limited reusability**: No templates or rule composition

### Current Rule Categories

1. **Tech Stack Rules** (8 rules) - Modern frameworks, outdated libraries
2. **Performance Rules** (5 rules) - Core Web Vitals, performance scores
3. **Business Category Rules** (3 rules) - Industry categorization
4. **Website Presence Rules** (2 rules) - Website existence, social media
5. **Location Rules** (3 rules) - Geographic targeting
6. **Size Indicators** (3 rules) - Multiple locations, review counts
7. **Tier-specific Rules** (4 rules) - SEO, accessibility, SEMrush data

## Proposed Simplified Format

### Design Principles

1. **Audit-First Focus**: Rules should clearly identify audit opportunities
2. **Simplified Syntax**: Use intuitive, consistent condition names
3. **Template-Based**: Allow rule templates and composition
4. **Performance-Oriented**: Prioritize website performance and technical issues
5. **Readable**: Human-friendly YAML that business users can understand
6. **Extensible**: Easy to add new audit criteria

### New YAML Schema

```yaml
# Anthrasite Lead-Factory Audit Scoring Rules
# Simplified format optimized for audit business model

settings:
  base_score: 50
  min_score: 0
  max_score: 100
  audit_threshold: 60  # Minimum score for audit opportunity

# Rule templates for reusability
templates:
  tech_outdated:
    description: "Technology is outdated and needs modernization"
    score: +15
    audit_category: "technology_modernization"

  performance_poor:
    description: "Website performance issues identified"
    score: +20
    audit_category: "performance_optimization"

# Simplified scoring rules
audit_opportunities:
  # Technology Audit Opportunities
  - name: jquery_upgrade_needed
    template: tech_outdated
    when:
      technology: "jQuery"
      version: "<3.0.0"
    audit_potential: "high"

  - name: modern_framework_missing
    template: tech_outdated
    when:
      missing_any: ["React", "Vue", "Angular", "Svelte"]
      has_any: ["jQuery", "Vanilla JS"]
    audit_potential: "medium"

  # Performance Audit Opportunities
  - name: slow_website
    template: performance_poor
    when:
      performance_score: "<50"
    audit_potential: "high"

  - name: poor_core_vitals
    template: performance_poor
    when:
      any:
        - lcp: ">2.5s"
        - cls: ">0.25"
        - fid: ">100ms"
    audit_potential: "high"

  # Business Model Opportunities
  - name: high_value_business
    description: "Business type with high audit value"
    score: +10
    when:
      business_type: ["restaurant", "retail", "professional_service"]
    audit_potential: "medium"

  - name: local_business
    description: "Local business in target markets"
    score: +5
    when:
      location: ["NY", "WA", "IN"]
    audit_potential: "low"

# Negative indicators (reduce audit potential)
exclusions:
  - name: modern_tech_stack
    description: "Already uses modern technology"
    score: -15
    when:
      technology: ["React", "Vue", "Angular", "Next.js"]
      performance_score: ">80"

  - name: enterprise_website
    description: "Enterprise-level website (less audit potential)"
    score: -20
    when:
      indicators: ["multiple_locations", "high_review_count"]
      performance_score: ">70"

# Audit focus multipliers
audit_multipliers:
  - name: perfect_audit_candidate
    description: "Ideal combination for audit services"
    multiplier: 1.5
    when:
      all:
        - technology: ["jQuery", "WordPress"]
        - performance_score: "<60"
        - business_type: ["restaurant", "retail"]

  - name: quick_win_potential
    description: "Easy fixes with high impact"
    multiplier: 1.3
    when:
      any:
        - lcp: ">4s"
        - cls: ">0.5"
        - technology: "Outdated HTML"
```

### Key Improvements

1. **Audit-Focused Structure**: Rules are organized around audit opportunities
2. **Template System**: Reusable rule templates reduce duplication
3. **Simplified Conditions**: More intuitive condition syntax
4. **Business Context**: Clear audit potential ratings
5. **Performance Priority**: Core Web Vitals and performance emphasized
6. **Negative Indicators**: Explicit exclusions for non-audit candidates

### Migration Strategy

1. **Phase 1**: Implement new parser alongside existing one
2. **Phase 2**: Create conversion utility for existing rules
3. **Phase 3**: Update scoring engine to support both formats
4. **Phase 4**: Migrate existing rules to new format
5. **Phase 5**: Deprecate old format after validation

### Backward Compatibility

- Parser will detect format version automatically
- Old format will continue to work during transition
- Conversion tool will ensure semantic equivalence
- Test suite will validate both formats produce same results

## Implementation Plan

### Subtask 1: Design Validation
- [ ] Review current rule effectiveness with audit business model
- [ ] Validate new schema with stakeholders
- [ ] Create format specification document
- [ ] Design rule conversion mapping

### Subtask 2: Parser Implementation
- [ ] Create new YAML schema models
- [ ] Implement template system
- [ ] Add format detection logic
- [ ] Build conversion utilities

### Subtask 3: Scoring Engine Updates
- [ ] Extend scoring engine for new format
- [ ] Maintain backward compatibility
- [ ] Optimize for audit-focused evaluation
- [ ] Add audit potential scoring

### Subtask 4: Testing & Validation
- [ ] Create comprehensive test suite
- [ ] Validate rule conversion accuracy
- [ ] Performance benchmark comparison
- [ ] End-to-end scoring validation

This simplified format will make scoring rules more maintainable, audit-focused, and easier to understand while maintaining full backward compatibility.
