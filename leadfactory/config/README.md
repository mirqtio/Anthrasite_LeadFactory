# Configuration Module

This module centralizes all configuration loading and access for the LeadFactory application. The main advantages of using this centralized approach are:

1. **Consistent Environment Loading**: All environment variables are loaded in one place
2. **Type Safety**: Variables are converted to appropriate types
3. **Default Values**: Sensible defaults are provided where needed
4. **Configuration Caching**: Configuration is loaded once and cached
5. **Hierarchical Access**: Dot notation can be used to access nested configuration
6. **Environment-specific Overrides**: Different environments can have different configurations

## Usage

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

## Migration Plan

1. Replace direct `os.getenv()` calls with imports from the config module
2. Replace direct `load_dotenv()` calls with `load_config()` from the config module
3. Update imports in all modules to use the centralized configuration
4. Add typing information for better IDE support
5. Add validation for required configuration values
