# Simplified YAML Scoring Rules Documentation

## Overview

The simplified YAML scoring format provides a more maintainable and audit-focused approach to defining scoring rules. It introduces templates, audit opportunities, and clear audit potential indicators while maintaining backward compatibility with the legacy format.

## Format Comparison

### Legacy Format Issues
- Complex nested conditions
- Repeated rule patterns
- No clear audit focus
- Difficult to maintain
- Limited categorization

### Simplified Format Benefits
- Template-based rule definitions
- Audit-focused terminology
- Clear priority system
- Better maintainability
- Built-in categorization

## Structure

### Settings
```yaml
settings:
  base_score: 50          # Starting score for all leads
  min_score: 0            # Minimum possible score
  max_score: 100          # Maximum possible score
  audit_threshold: 60     # Minimum score for audit opportunity
```

### Templates
Templates allow reusable rule definitions:
```yaml
templates:
  tech_modernization:
    description: "Technology modernization opportunity identified"
    score: 15
    audit_category: "technology_upgrade"
```

### Audit Opportunities
Rules that identify potential audit clients:
```yaml
audit_opportunities:
  - name: jquery_upgrade_opportunity
    template: tech_modernization
    when:
      technology: "jQuery"
      version: "<3.0.0"
    audit_potential: "high"
    priority: 90
```

### Exclusions
Rules that reduce audit potential:
```yaml
exclusions:
  - name: modern_tech_stack
    description: "Already uses modern technology stack"
    score: -15
    when:
      technology: ["React", "Vue", "Angular"]
      performance_score: ">80"
```

### Audit Multipliers
Multipliers that amplify scores for ideal audit candidates:
```yaml
audit_multipliers:
  - name: perfect_audit_candidate
    description: "Ideal combination for comprehensive audit services"
    multiplier: 1.5
    when:
      all:
        - technology: ["jQuery", "WordPress"]
        - performance_score: "<60"
        - business_type: ["restaurant", "retail"]
```

## Condition Format

### Simple Conditions
```yaml
when:
  technology: "jQuery"                    # Single technology
  technology: ["React", "Vue"]            # Multiple technologies
  version: "<3.0.0"                      # Version comparison
  performance_score: "<50"               # Performance condition
  lcp: ">2.5s"                          # Core Web Vitals
  business_type: ["restaurant", "retail"] # Business categories
  location: ["NY", "CA"]                 # Geographic targeting
```

### Performance Conditions
```yaml
when:
  performance_score: "<50"  # Overall performance score
  lcp: ">2.5s"             # Largest Contentful Paint in seconds
  cls: ">0.25"             # Cumulative Layout Shift
  fid: ">100ms"            # First Input Delay in milliseconds
```

### Composite Conditions
```yaml
when:
  all:                     # All conditions must be true
    - technology: "WordPress"
    - performance_score: "<60"
  any:                     # Any condition can be true
    - lcp: ">3s"
    - cls: ">0.5"
  none:                    # No conditions should be true
    - technology: ["React", "Vue"]
```

## Audit Potential Levels

- **high**: Strong audit opportunity with significant improvement potential
- **medium**: Moderate audit opportunity with some improvement areas
- **low**: Limited audit opportunity or minor improvements only

## Priority System

Priority values (0-100) determine rule evaluation order:
- **90-100**: Critical audit opportunities
- **70-89**: High-value opportunities
- **50-69**: Standard opportunities
- **30-49**: Low-priority opportunities
- **0-29**: Minimal opportunities

## Migration from Legacy Format

### Automatic Conversion
Use the rule converter to migrate legacy rules:
```bash
python -m leadfactory.scoring.rule_converter legacy_rules.yml simplified_rules.yml
```

### Manual Migration Steps
1. **Identify Common Patterns**: Group similar rules for template creation
2. **Create Templates**: Define reusable rule components
3. **Convert Conditions**: Simplify complex nested conditions
4. **Set Priorities**: Assign priority values based on business importance
5. **Define Audit Potential**: Categorize rules by audit opportunity level

## Best Practices

### Template Design
- Create templates for common rule patterns
- Use descriptive audit categories
- Keep templates focused and specific

### Rule Organization
- Use clear, descriptive rule names
- Group related rules logically
- Set appropriate priorities

### Condition Writing
- Use simple, readable conditions
- Prefer composite conditions for complex logic
- Include meaningful comments

### Testing
- Test rule conversions thoroughly
- Validate audit potential assignments
- Verify scoring consistency

## Integration

### Unified Scoring Engine
The system automatically detects format type:
```python
from leadfactory.scoring.unified_scoring_engine import UnifiedScoringEngine

engine = UnifiedScoringEngine()
engine.load_rules()  # Auto-detects format
result = engine.score_business(business_data)
```

### Format Detection
The engine identifies formats by checking for:
- **Simplified**: `audit_opportunities`, `templates`, `audit_threshold`
- **Legacy**: `rules` and `multipliers` arrays

## Example Migration

### Legacy Rule
```yaml
rules:
  - name: outdated_jquery
    description: "Business uses outdated jQuery"
    condition:
      tech_stack_contains: jQuery
      tech_stack_version_lt:
        technology: jQuery
        version: "3.0.0"
    score: 10
```

### Simplified Rule
```yaml
audit_opportunities:
  - name: jquery_upgrade_opportunity
    template: tech_modernization
    when:
      technology: "jQuery"
      version: "<3.0.0"
    audit_potential: "high"
    priority: 90
```

## Validation

The simplified format includes comprehensive validation:
- Score ranges (-100 to 100)
- Valid audit potential values
- Required field validation
- Template reference validation

## Performance

The simplified format offers:
- Faster rule evaluation
- Reduced memory usage
- Better caching opportunities
- Optimized condition matching

## Troubleshooting

### Common Issues
1. **Template Not Found**: Ensure template is defined before use
2. **Invalid Conditions**: Check condition syntax and supported operators
3. **Priority Conflicts**: Use unique priorities or accept evaluation order
4. **Migration Errors**: Validate legacy format before conversion

### Debugging
- Enable debug logging for detailed rule evaluation
- Use format info to verify rule loading
- Test individual rules with sample data

## Future Enhancements

Planned improvements include:
- Visual rule editor
- Advanced condition builders
- Rule performance analytics
- A/B testing support
- Dynamic rule loading
