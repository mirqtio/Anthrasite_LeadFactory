# Scoring Rules Migration Guide

## Overview

This guide walks through migrating from legacy YAML scoring rules to the new simplified audit-focused format. The migration process maintains scoring accuracy while improving maintainability and audit focus.

## Prerequisites

- Backup existing scoring rules
- Test environment for validation
- Understanding of current scoring logic

## Migration Process

### Step 1: Analysis Phase

#### Inventory Current Rules
```bash
# Count rules in legacy format
grep -c "^  - name:" etc/scoring_rules.yml

# List all rule names
grep "name:" etc/scoring_rules.yml | sed 's/.*name: //'
```

#### Identify Patterns
1. **Technology Rules**: jQuery, WordPress, framework detection
2. **Performance Rules**: Page speed, Core Web Vitals
3. **Business Rules**: Category, location, size indicators
4. **Exclusion Rules**: Modern tech stacks, enterprise sites

#### Document Dependencies
- Note rule interdependencies
- Identify scoring thresholds
- Map business logic requirements

### Step 2: Template Creation

#### Common Templates
Create templates for frequent patterns:

```yaml
templates:
  tech_modernization:
    description: "Technology modernization opportunity identified"
    score: 15
    audit_category: "technology_upgrade"

  performance_optimization:
    description: "Website performance optimization needed"
    score: 20
    audit_category: "performance_improvement"

  seo_opportunity:
    description: "SEO improvement opportunity available"
    score: 12
    audit_category: "seo_enhancement"

  business_alignment:
    description: "Business type aligned with services"
    score: 10
    audit_category: "market_fit"
```

#### Template Strategy
- **High-Impact**: 15-20 points for major opportunities
- **Medium-Impact**: 8-12 points for moderate opportunities
- **Low-Impact**: 3-7 points for minor opportunities
- **Exclusions**: Negative points to reduce audit potential

### Step 3: Automated Conversion

#### Run the Converter
```bash
# Basic conversion
python -m leadfactory.scoring.rule_converter \
  etc/scoring_rules.yml \
  etc/scoring_rules_migrated.yml

# With validation
python -m leadfactory.scoring.rule_converter \
  etc/scoring_rules.yml \
  etc/scoring_rules_migrated.yml \
  --validate
```

#### Converter Features
- Automatic template assignment
- Condition simplification
- Priority calculation
- Audit potential categorization

### Step 4: Manual Refinement

#### Review Generated Rules
Check each converted rule for:
- Appropriate template assignment
- Correct audit potential level
- Sensible priority values
- Simplified conditions

#### Optimize Templates
- Merge similar rules under common templates
- Adjust scoring values for audit focus
- Refine audit categories

#### Example Refinement
**Before (auto-generated)**:
```yaml
- name: jquery_outdated
  template: tech_modernization
  when:
    technology: "jQuery"
    version: "<3.0.0"
  audit_potential: "medium"
  priority: 50
```

**After (refined)**:
```yaml
- name: jquery_upgrade_opportunity
  template: tech_modernization
  when:
    technology: "jQuery"
    version: "<3.0.0"
  audit_potential: "high"
  priority: 85
```

### Step 5: Priority Assignment

#### Priority Framework
```
90-100: Critical opportunities (poor performance + outdated tech)
80-89:  High-value opportunities (major tech upgrades)
70-79:  Standard opportunities (moderate improvements)
60-69:  Business alignment (target markets/categories)
50-59:  Minor improvements (small optimizations)
40-49:  Low-priority items (nice-to-have)
30-39:  Edge cases (rare conditions)
20-29:  Experimental rules (testing)
10-19:  Deprecated rules (phase out)
0-9:    Disabled rules (keep for reference)
```

#### Priority Examples
```yaml
# Critical: Poor performance with outdated tech
- name: critical_performance_tech_combo
  priority: 95
  when:
    all:
      - performance_score: "<40"
      - technology: "jQuery"
      - version: "<2.0.0"

# High: Major technology upgrade
- name: jquery_upgrade_opportunity
  priority: 85
  when:
    technology: "jQuery"
    version: "<3.0.0"

# Standard: WordPress optimization
- name: wordpress_optimization
  priority: 70
  when:
    all:
      - technology: "WordPress"
      - performance_score: "<65"
```

### Step 6: Condition Simplification

#### Legacy to Simplified Mapping

| Legacy Condition | Simplified Condition |
|------------------|----------------------|
| `tech_stack_contains: jQuery` | `technology: "jQuery"` |
| `tech_stack_contains_any: [React, Vue]` | `technology: ["React", "Vue"]` |
| `performance_score_lt: 50` | `performance_score: "<50"` |
| `lcp_gt: 2500` | `lcp: ">2.5s"` |
| `category_contains_any: [restaurant, cafe]` | `business_type: ["restaurant", "cafe"]` |
| `state_equals: "NY"` | `location: "NY"` |

#### Complex Condition Patterns
```yaml
# Legacy nested conditions
condition:
  tech_stack_contains: WordPress
  performance_score_lt: 60
  category_contains_any: [restaurant, retail]

# Simplified composite conditions
when:
  all:
    - technology: "WordPress"
    - performance_score: "<60"
    - business_type: ["restaurant", "retail"]
```

### Step 7: Validation

#### Automated Validation
```bash
# Test rule loading
python -c "
from leadfactory.scoring.simplified_yaml_parser import SimplifiedYamlParser
parser = SimplifiedYamlParser('etc/scoring_rules_migrated.yml')
config = parser.load_and_validate()
print(f'Loaded {len(config.audit_opportunities)} opportunities')
"

# Test scoring consistency
python scripts/validate_scoring_migration.py
```

#### Manual Testing
Create test cases covering:
- High-scoring businesses (should maintain high scores)
- Low-scoring businesses (should maintain low scores)
- Edge cases (boundary conditions)
- New rule interactions

#### Sample Test Business
```python
test_business = {
    "tech_stack": ["jQuery", "WordPress"],
    "tech_stack_versions": {"jQuery": "2.1.4"},
    "performance_score": 45,
    "lcp": 3200,  # milliseconds
    "cls": 0.3,
    "category": ["restaurant"],
    "state": "NY",
    "review_count": 25
}
```

### Step 8: A/B Testing

#### Parallel Scoring
Run both systems simultaneously:
```python
from leadfactory.scoring.unified_scoring_engine import UnifiedScoringEngine

# Legacy scoring
legacy_engine = UnifiedScoringEngine('etc/scoring_rules.yml')
legacy_engine.load_rules()
legacy_result = legacy_engine.score_business(business_data)

# Simplified scoring
simplified_engine = UnifiedScoringEngine('etc/scoring_rules_migrated.yml')
simplified_engine.load_rules()
simplified_result = simplified_engine.score_business(business_data)

# Compare results
score_diff = abs(legacy_result['final_score'] - simplified_result['final_score'])
if score_diff > 5:  # Threshold for investigation
    print(f"Significant score difference: {score_diff}")
```

#### Gradual Rollout
1. **Shadow Mode**: Run simplified rules alongside legacy (no impact)
2. **Canary**: Use simplified rules for 5% of scoring requests
3. **Ramp**: Gradually increase to 50%, then 100%
4. **Full**: Replace legacy rules entirely

### Step 9: Documentation Updates

#### Update Configuration Files
```yaml
# Add format indicator
format_version: "2.0"
migration_date: "2025-06-04"
migrated_from: "legacy_v1.3"
```

#### Create Migration Log
Document changes made during migration:
- Rules modified or merged
- Priority adjustments
- Template assignments
- Validation results

### Step 10: Production Deployment

#### Pre-deployment Checklist
- [ ] All rules validated
- [ ] Performance testing completed
- [ ] A/B testing results reviewed
- [ ] Documentation updated
- [ ] Rollback plan prepared

#### Deployment Steps
1. **Backup**: Save current production rules
2. **Deploy**: Upload new simplified rules
3. **Monitor**: Watch scoring metrics and alerts
4. **Validate**: Confirm expected behavior
5. **Cleanup**: Remove legacy rule files

## Troubleshooting

### Common Migration Issues

#### Template Assignment Errors
**Problem**: Rule references non-existent template
**Solution**: Define missing template or remove template reference

#### Priority Conflicts
**Problem**: Multiple rules with same priority
**Solution**: Assign unique priorities or accept default ordering

#### Condition Translation Errors
**Problem**: Complex legacy conditions don't convert cleanly
**Solution**: Manually simplify conditions or use composite conditions

#### Score Variance
**Problem**: Significant differences in business scores
**Solution**: Adjust template scores or rule conditions

### Debugging Tools

#### Rule Evaluation Tracer
```python
# Enable detailed logging
import logging
logging.getLogger('leadfactory.scoring').setLevel(logging.DEBUG)

# Trace rule evaluation
result = engine.score_business(business_data)
for rule in result['applied_rules']:
    print(f"Rule: {rule['rule']}, Score: {rule['score_adjustment']}")
```

#### Score Comparison Tool
```bash
python scripts/compare_scoring_formats.py \
  --legacy etc/scoring_rules.yml \
  --simplified etc/scoring_rules_migrated.yml \
  --test-data test_businesses.json
```

## Best Practices

### Rule Design
- Keep conditions simple and readable
- Use descriptive names that indicate audit potential
- Group related rules with similar templates
- Set priorities based on business value

### Template Management
- Create templates for common patterns
- Use consistent scoring scales within templates
- Document template usage guidelines
- Review and update templates regularly

### Testing Strategy
- Test with real business data
- Include edge cases and boundary conditions
- Validate scoring consistency
- Monitor performance impact

### Maintenance
- Regular rule effectiveness reviews
- Update priorities based on conversion data
- Retire obsolete rules
- Add new rules for emerging technologies

## Migration Timeline

### Phase 1: Preparation (Week 1)
- Rule analysis and documentation
- Template design
- Test environment setup

### Phase 2: Conversion (Week 2)
- Automated rule conversion
- Manual refinement
- Priority assignment

### Phase 3: Validation (Week 3)
- Automated testing
- A/B testing setup
- Performance validation

### Phase 4: Deployment (Week 4)
- Production deployment
- Monitoring and adjustment
- Documentation finalization

## Success Metrics

- **Rule Count**: Reduced from complex nested rules
- **Maintainability**: Faster rule updates and additions
- **Performance**: Improved scoring execution time
- **Accuracy**: Maintained or improved scoring precision
- **Audit Focus**: Better identification of audit opportunities

## Support and Resources

- **Documentation**: `/docs/simplified-yaml-scoring-rules.md`
- **Examples**: `/etc/scoring_rules_simplified.yml`
- **Tools**: `/leadfactory/scoring/rule_converter.py`
- **Tests**: `/tests/unit/scoring/`
- **Migration Scripts**: `/scripts/scoring/`
