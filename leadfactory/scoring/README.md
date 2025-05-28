# LeadFactory Scoring Engine

A flexible, YAML-driven scoring engine for evaluating business leads based on configurable rules and dimensions.

## Quick Start

```python
from leadfactory.scoring import ScoringEngine

# Initialize and load rules
engine = ScoringEngine("etc/scoring_rules.yml")
engine.load_rules()

# Score a business
business = {
    'name': 'Tech Corp',
    'tech_stack': ['React', 'Node.js'],
    'vertical': 'SaaS',
    'employee_count': 100
}

result = engine.score_business(business)
print(f"Score: {result['score']}")
```

## Components

### 1. `yaml_parser.py`
Handles loading and validation of YAML scoring configurations.

**Key Classes:**
- `ScoringRulesParser`: Main parser class
- `ScoringRulesConfig`: Configuration model
- `ScoringRule`: Individual rule model
- `Condition`: Rule condition model

### 2. `rule_evaluator.py`
Evaluates scoring rules against business data.

**Key Classes:**
- `RuleEvaluator`: Main evaluation engine

**Supported Operators:**
- Comparison: `equals`, `greater_than`, `less_than`, `between`
- String: `contains`, `starts_with`, `ends_with`, `regex`
- Collection: `in`, `contains_any`, `contains_all`
- Special: `exists`, `version_greater_than`

### 3. `scoring_engine.py`
Orchestrates the scoring process and manages score calculations.

**Key Classes:**
- `ScoringEngine`: Main scoring interface

**Features:**
- Rule prioritization
- Score bounds enforcement
- Multiplier support
- Detailed scoring breakdowns

## Configuration Format

```yaml
version: "1.0"
settings:
  base_score: 50
  max_score: 100
  min_score: 0

rules:
  - id: "modern_tech"
    name: "Modern Technology Stack"
    priority: 1
    conditions:
      - field: "tech_stack"
        operator: "contains_any"
        value: ["React", "Vue", "Angular"]
    score_adjustment: 15
    enabled: true

multipliers:
  - id: "high_value"
    name: "High-Value Vertical"
    conditions:
      - field: "vertical"
        operator: "in"
        value: ["SaaS", "FinTech"]
    multiplier: 1.2
    enabled: true
```

## Testing

```bash
# Run unit tests
pytest tests/unit/test_scoring_engine.py -v

# Run integration tests
pytest tests/integration/test_scoring_integration.py -v
```

## Extending the Engine

### Adding a New Operator

1. Add the operator logic to `RuleEvaluator._evaluate_condition()`
2. Add test cases
3. Update documentation

### Adding a New Field Type

The engine supports any field in the business data dictionary. For nested fields, use dot notation:

```yaml
conditions:
  - field: "social_media.twitter.followers"
    operator: "greater_than"
    value: 1000
```

## Performance Considerations

- Rules are evaluated in priority order (lower number = higher priority)
- Place most selective rules first for better performance
- The engine caches loaded configurations
- Batch process multiple businesses for efficiency

## Debugging

Enable debug logging to see detailed rule evaluation:

```python
import logging
logging.getLogger('leadfactory.scoring').setLevel(logging.DEBUG)
```

## API Reference

### ScoringEngine

```python
class ScoringEngine:
    def __init__(self, config_path: str = None)
    def load_rules(self) -> None
    def score_business(self, business: Dict[str, Any]) -> Dict[str, Any]
```

### Result Format

```python
{
    'score': 75,  # Final calculated score
    'base_score': 50,  # Starting score
    'adjustments': [  # Applied rules
        {
            'rule': 'modern_tech',
            'name': 'Modern Technology Stack',
            'adjustment': 15,
            'matched_conditions': [...]
        }
    ],
    'multipliers': [  # Applied multipliers
        {
            'multiplier': 'high_value',
            'name': 'High-Value Vertical',
            'factor': 1.2
        }
    ],
    'metadata': {
        'rules_evaluated': 10,
        'rules_matched': 3,
        'processing_time_ms': 2.5
    }
}
```

## Error Handling

The engine provides detailed error messages for:
- Invalid YAML syntax
- Missing required fields
- Invalid operator usage
- Type mismatches

## License

Part of the LeadFactory project. See main project LICENSE.
