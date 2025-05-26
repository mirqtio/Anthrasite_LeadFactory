# Pipeline Modules

This directory will contain the core pipeline modules migrated from the `bin` directory:

- `scrape.py` - Business scraping functionality
- `enrich.py` - Business enrichment functionality
- `dedupe.py` - Deduplication logic
- `score.py` - Business scoring logic
- `email_queue.py` - Email generation and sending

## Migration Plan

1. Move the modules from `bin/` to this directory
2. Update all imports to use relative imports within the package
3. Update entry points in `pyproject.toml` and `setup.py`
4. Remove any path manipulation hacks with `sys.path.insert()`
