# Import Migration Plan

This document outlines the mapping of old imports to new package structure imports for the LeadFactory refactoring.

## Import Mapping Rules

### Pipeline Modules

| Old Import | New Import |
|------------|------------|
| `from bin import scrape` | `from leadfactory.pipeline import scrape` |
| `from bin.scrape import *` | `from leadfactory.pipeline.scrape import *` |
| `from bin import enrich` | `from leadfactory.pipeline import enrich` |
| `from bin.enrich import *` | `from leadfactory.pipeline.enrich import *` |
| `from bin import dedupe` | `from leadfactory.pipeline import dedupe` |
| `from bin.dedupe import *` | `from leadfactory.pipeline.dedupe import *` |
| `from bin import score` | `from leadfactory.pipeline import score` |
| `from bin.score import *` | `from leadfactory.pipeline.score import *` |
| `from bin import email_queue` | `from leadfactory.pipeline import email_queue` |
| `from bin.email_queue import *` | `from leadfactory.pipeline.email_queue import *` |
| `from bin import mockup` | `from leadfactory.pipeline import mockup` |
| `from bin.mockup import *` | `from leadfactory.pipeline.mockup import *` |

### Utility Modules

| Old Import | New Import |
|------------|------------|
| `from bin.utils import *` | `from leadfactory.utils import *` |
| `from bin.utils.string_utils import *` | `from leadfactory.utils.string_utils import *` |
| `from bin.metrics import metrics` | `from leadfactory.utils import metrics` |
| `from bin import batch_completion_monitor` | `from leadfactory.utils import batch_completion_monitor` |
| `from bin.batch_completion_monitor import *` | `from leadfactory.utils.batch_completion_monitor import *` |

### Cost Tracking Modules

| Old Import | New Import |
|------------|------------|
| `from bin import budget_gate` | `from leadfactory.cost import budget_gate` |
| `from bin.budget_gate import *` | `from leadfactory.cost.budget_gate import *` |
| `from bin.cost_tracking import cost_tracker` | `from leadfactory.cost.cost_tracking import cost_tracker` |
| `from bin import budget_audit` | `from leadfactory.cost import budget_audit` |

### Configuration

| Old Import | New Import |
|------------|------------|
| Direct `os.getenv` calls | `from leadfactory.config import get_config` |
| Direct `load_dotenv()` calls | `from leadfactory.config import load_config` |

## Implementation Steps

1. Move files to their new locations in the package structure
2. Update imports in each module to reference the new locations
3. Create import compatibility shims in the original locations if needed
4. Update tests to use the new import structure
5. Run tests to ensure all imports resolve correctly

## Legacy Compatibility

For backwards compatibility during migration, we can create simple forwarding modules in the original locations:

```python
# bin/scrape.py
# Legacy compatibility shim
from leadfactory.pipeline.scrape import *

# Re-export everything from the new module
__all__ = ['YelpAPI', 'GooglePlacesAPI', 'scrape_businesses', 'main', ...]
```
