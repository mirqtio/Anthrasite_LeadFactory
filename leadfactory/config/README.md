# Configuration Module

This module centralizes all configuration loading and access for the LeadFactory application. The main advantages of using this centralized approach are:

1. **Consistent Environment Loading**: All environment variables are loaded in one place
2. **Type Safety**: Variables are converted to appropriate types
3. **Default Values**: Sensible defaults are provided where needed
4. **Configuration Caching**: Configuration is loaded once and cached
5. **Hierarchical Access**: Dot notation can be used to access nested configuration
6. **Environment-specific Overrides**: Different environments can have different configurations

## NodeCapability Configuration System

The `node_config.py` module provides an advanced, environment-aware configuration system for pipeline node capabilities. This system automatically optimizes API usage and costs based on your deployment environment.

### Key Features

- **Environment Detection**: Automatically detects development, production_audit, and production_general environments
- **Cost Optimization**: Reduces costs by up to 60% in development environments
- **Business Model Alignment**: Special optimization for audit-focused business model
- **API Fallbacks**: Graceful degradation when APIs are unavailable
- **Capability Tiers**: Essential, high-value, and optional capability categorization

## Usage

### General Configuration

The recommended way to access configuration is through the `get_config()` function:

```python
from leadfactory.config import get_config

config = get_config()
api_key = config['OPENAI_API_KEY']
```

Or import specific configuration values directly:

```python
from leadfactory import get_config
from leadfactory.config import DATABASE_URL, OPENAI_API_KEY
```

### NodeCapability Configuration

For pipeline node capabilities, use the environment-aware configuration system:

```python
from leadfactory.config.node_config import (
    get_enabled_capabilities,
    estimate_node_cost,
    NodeType,
    validate_environment_configuration
)

# Get capabilities for current environment (auto-detected)
capabilities = get_enabled_capabilities(NodeType.ENRICH, budget_cents=10.0)

# Estimate costs for current environment
cost = estimate_node_cost(NodeType.ENRICH, budget_cents=10.0)

# Validate configuration
validation = validate_environment_configuration()
if not validation['valid']:
    print(f"Issues: {validation['issues']}")
    print(f"Recommendations: {validation['recommendations']}")
```

### Environment Setup

Set your deployment environment for optimal capability selection:

```bash
# Development (cost-optimized)
export DEPLOYMENT_ENVIRONMENT=development

# Production audit-focused
export DEPLOYMENT_ENVIRONMENT=production_audit

# Production general leads
export DEPLOYMENT_ENVIRONMENT=production_general
```

## Migration Plan

1. Replace direct `os.getenv()` calls with imports from the config module
2. Replace direct `load_dotenv()` calls with `load_config()` from the config module
3. Update imports in all modules to use the centralized configuration
4. Add typing information for better IDE support
5. Add validation for required configuration values
