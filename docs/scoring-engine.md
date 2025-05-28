# Scoring Engine Documentation

## Overview

The LeadFactory Scoring Engine is a YAML-driven system for evaluating businesses based on configurable rules and dimensions. It provides a flexible, maintainable way to score leads based on various business attributes such as technology stack, vertical, company size, and more.

## Table of Contents

1. [Architecture](#architecture)
2. [YAML Configuration Format](#yaml-configuration-format)
3. [Rule Types](#rule-types)
4. [Scoring Dimensions](#scoring-dimensions)
5. [Usage Examples](#usage-examples)
6. [Developer Guide](#developer-guide)
7. [Performance Optimization](#performance-optimization)
8. [Troubleshooting](#troubleshooting)

## Architecture

The scoring engine consists of three main components:

### 1. YAML Parser (`yaml_parser.py`)
- Loads and validates scoring rules from YAML configuration files
- Ensures configuration adheres to the required schema
- Provides type-safe access to configuration data using Pydantic models

### 2. Rule Evaluator (`rule_evaluator.py`)
- Evaluates individual rules against business data
- Supports multiple condition types and operators
- Returns match results and score adjustments

### 3. Scoring Engine (`scoring_engine.py`)
- Orchestrates the scoring process
- Applies rules in priority order
- Manages score bounds and multipliers
- Provides detailed scoring breakdowns

## YAML Configuration Format

The scoring configuration file follows this structure:

```yaml
version: "1.0"
settings:
  base_score: 50
  max_score: 100
  min_score: 0

rules:
  - id: "rule_id"
    name: "Rule Name"
    description: "What this rule does"
    priority: 1  # Lower numbers = higher priority
    conditions:
      - field: "tech_stack"
        operator: "contains"
        value: "React"
    score_adjustment: 15
    enabled: true

multipliers:
  - id: "multiplier_id"
    name: "Multiplier Name"
    conditions:
      - field: "vertical"
        operator: "in"
        value: ["SaaS", "Technology"]
    multiplier: 1.2
    enabled: true
```

### Configuration Fields

#### Settings
- `base_score`: Starting score for all businesses (default: 50)
- `max_score`: Maximum allowed score (default: 100)
- `min_score`: Minimum allowed score (default: 0)

#### Rules
- `id`: Unique identifier for the rule
- `name`: Human-readable name
- `description`: Detailed explanation of the rule
- `priority`: Execution order (lower = earlier)
- `conditions`: List of conditions that must be met
- `score_adjustment`: Points to add/subtract when rule matches
- `enabled`: Whether the rule is active

#### Multipliers
- `id`: Unique identifier for the multiplier
- `name`: Human-readable name
- `conditions`: Conditions for applying the multiplier
- `multiplier`: Factor to multiply the score by
- `enabled`: Whether the multiplier is active

## Rule Types

### 1. Technology Stack Rules
Evaluate businesses based on their technology choices:

```yaml
- id: "modern_frontend"
  name: "Modern Frontend Framework"
  conditions:
    - field: "tech_stack"
      operator: "contains_any"
      value: ["React", "Vue", "Angular"]
  score_adjustment: 15
```

### 2. Company Attribute Rules
Score based on company characteristics:

```yaml
- id: "enterprise_size"
  name: "Enterprise Company"
  conditions:
    - field: "employee_count"
      operator: "greater_than"
      value: 500
  score_adjustment: 20
```

### 3. Vertical-Specific Rules
Target specific industries:

```yaml
- id: "high_value_vertical"
  name: "High-Value Vertical"
  conditions:
    - field: "vertical"
      operator: "in"
      value: ["SaaS", "FinTech", "HealthTech"]
  score_adjustment: 10
```

### 4. Complex Multi-Condition Rules
Combine multiple conditions:

```yaml
- id: "ideal_prospect"
  name: "Ideal Prospect"
  conditions:
    - field: "tech_stack"
      operator: "contains"
      value: "React"
    - field: "employee_count"
      operator: "between"
      value: [50, 500]
    - field: "vertical"
      operator: "equals"
      value: "SaaS"
  score_adjustment: 25
```

## Scoring Dimensions

### Supported Operators

1. **Comparison Operators**
   - `equals`: Exact match
   - `not_equals`: Not equal to value
   - `greater_than`: Greater than numeric value
   - `less_than`: Less than numeric value
   - `greater_than_or_equal`: >= numeric value
   - `less_than_or_equal`: <= numeric value
   - `between`: Within numeric range [min, max]

2. **String Operators**
   - `contains`: Substring match
   - `starts_with`: String prefix match
   - `ends_with`: String suffix match
   - `regex`: Regular expression match

3. **Collection Operators**
   - `in`: Value in list
   - `not_in`: Value not in list
   - `contains_any`: Contains any value from list
   - `contains_all`: Contains all values from list

4. **Special Operators**
   - `exists`: Field exists (not null)
   - `not_exists`: Field is null/missing
   - `version_greater_than`: Semantic version comparison

## Usage Examples

### Basic Usage

```python
from leadfactory.scoring import ScoringEngine

# Initialize the scoring engine
engine = ScoringEngine("etc/scoring_rules.yml")
engine.load_rules()

# Score a business
business = {
    'id': 1,
    'name': 'Tech Startup Inc',
    'tech_stack': ['React', 'Node.js', 'PostgreSQL'],
    'vertical': 'SaaS',
    'employee_count': 75
}

result = engine.score_business(business)
print(f"Score: {result['score']}")
print(f"Adjustments: {result['adjustments']}")
print(f"Multipliers: {result['multipliers']}")
```

### Integration with Pipeline

```python
from leadfactory.pipeline.score import score_business

# Simple scoring function for pipeline integration
score = score_business(business_data)
```

### Custom Rule Configuration

Create a custom scoring configuration:

```yaml
version: "1.0"
settings:
  base_score: 60
  max_score: 100
  min_score: 0

rules:
  # Technology preferences
  - id: "cloud_native"
    name: "Cloud Native Stack"
    conditions:
      - field: "tech_stack"
        operator: "contains_any"
        value: ["Kubernetes", "Docker", "AWS", "GCP", "Azure"]
    score_adjustment: 20

  # Company maturity
  - id: "growth_stage"
    name: "Growth Stage Company"
    conditions:
      - field: "employee_count"
        operator: "between"
        value: [50, 200]
      - field: "revenue"
        operator: "greater_than"
        value: 5000000
    score_adjustment: 15
```

## Developer Guide

### Extending the Scoring Engine

#### Adding New Operators

To add a new operator, modify the `_evaluate_condition` method in `RuleEvaluator`:

```python
def _evaluate_condition(self, business: Dict[str, Any], condition: Condition) -> bool:
    # ... existing code ...

    elif operator == "your_new_operator":
        return your_operator_logic(field_value, condition.value)
```

#### Adding New Field Types

The scoring engine can handle any field in the business data. To add special handling for a new field type:

```python
# In rule_evaluator.py
def _get_field_value(self, business: Dict[str, Any], field_path: str) -> Any:
    """Get field value with support for nested fields."""
    parts = field_path.split('.')
    value = business

    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None

    return value
```

### Testing

#### Unit Tests

Run the unit tests:

```bash
python -m pytest tests/unit/test_scoring_engine.py -v
```

#### Integration Tests

Run integration tests with real YAML configuration:

```bash
python -m pytest tests/integration/test_scoring_integration.py -v
```

#### Creating Test Cases

```python
def test_custom_rule():
    """Test a custom scoring rule."""
    config = {
        "version": "1.0",
        "settings": {"base_score": 50},
        "rules": [{
            "id": "test_rule",
            "name": "Test Rule",
            "conditions": [{
                "field": "test_field",
                "operator": "equals",
                "value": "test_value"
            }],
            "score_adjustment": 10
        }]
    }

    engine = ScoringEngine()
    engine.config = ScoringRulesConfig(**config)

    business = {"test_field": "test_value"}
    result = engine.score_business(business)

    assert result['score'] == 60  # base 50 + adjustment 10
```

## Performance Optimization

### Best Practices

1. **Rule Ordering**: Place most selective rules first (lower priority number)
2. **Condition Complexity**: Use simple conditions when possible
3. **Caching**: The engine caches loaded configurations
4. **Batch Processing**: Score multiple businesses in a loop to amortize setup costs

### Performance Tips

```python
# Efficient batch scoring
engine = ScoringEngine("scoring_rules.yml")
engine.load_rules()  # Load once

# Score many businesses
results = []
for business in businesses:
    result = engine.score_business(business)
    results.append(result)
```

### Monitoring

Enable debug logging to track rule evaluation:

```python
import logging
logging.getLogger('leadfactory.scoring').setLevel(logging.DEBUG)
```

## Troubleshooting

### Common Issues

#### 1. YAML Validation Errors

**Problem**: "ValidationError: Invalid YAML configuration"

**Solution**: Check your YAML syntax and ensure all required fields are present:
- Each rule must have: id, name, conditions, score_adjustment
- Each condition must have: field, operator, value

#### 2. Score Out of Bounds

**Problem**: Scores exceed max_score or fall below min_score

**Solution**: The engine automatically clamps scores. Check your rules if scores are consistently at bounds.

#### 3. Rules Not Matching

**Problem**: Expected rules don't match businesses

**Debug Steps**:
1. Enable debug logging
2. Check field names match exactly
3. Verify operator logic
4. Test conditions individually

### Debug Mode

Enable detailed logging:

```python
# In your code
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('leadfactory.scoring')

# The engine will now log:
# - Rule evaluation details
# - Condition matching results
# - Score calculations
# - Applied adjustments
```

### Validation Tools

Validate your YAML configuration:

```python
from leadfactory.scoring import ScoringRulesParser

parser = ScoringRulesParser("your_config.yml")
try:
    config = parser.load_and_validate()
    print("Configuration is valid!")
except Exception as e:
    print(f"Configuration error: {e}")
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Scoring Engine Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-cov

    - name: Run scoring engine tests
      run: |
        pytest tests/unit/test_scoring_engine.py -v
        pytest tests/integration/test_scoring_integration.py -v

    - name: Validate scoring configuration
      run: |
        python -c "from leadfactory.scoring import ScoringRulesParser; \
                   parser = ScoringRulesParser('etc/scoring_rules.yml'); \
                   parser.load_and_validate()"
```

## Contributing

When contributing to the scoring engine:

1. Add tests for new operators or features
2. Update this documentation
3. Ensure backward compatibility
4. Follow the existing code style
5. Add logging for debugging

## Support

For issues or questions:
1. Check the troubleshooting section
2. Enable debug logging
3. Review test cases for examples
4. Submit issues with configuration samples and business data (sanitized)
