# Utility Modules

This directory will contain utility modules used throughout the LeadFactory application:

- `batch_metrics.py` - Metrics tracking for batch operations
- `batch_tracker.py` - Tracking batch processing status
- `logging_config.py` - Centralized logging configuration
- `metrics.py` - Core metrics collection and reporting
- `website_scraper.py` - Web scraping utilities

## Migration Plan

1. Move the utility modules from `utils/` to this directory
2. Consolidate duplicate utility modules from `bin/utils/`
3. Update all imports to use relative imports within the package
4. Remove any path manipulation hacks with `sys.path.insert()`
5. Create proper `__init__.py` file to expose key functionality
