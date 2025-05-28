# CLI Framework Evaluation for Legacy bin/ Scripts

## Current State Analysis

### Existing Scripts Pattern
All bin/ scripts currently use `argparse` with similar patterns:
- Standard argument parsing with `--limit`, `--id`, `--dry-run` options
- Manual path setup with `sys.path.append()`
- Dotenv loading for environment variables
- Basic logging setup
- Similar error handling patterns

### Scripts to Modernize
1. `bin/scrape.py` - Web scraping with Yelp/Google APIs
2. `bin/enrich.py` - Website analysis and tech stack detection
3. `bin/dedupe.py` - Duplicate business record merging
4. `bin/email_queue.py` - Email sending via SendGrid
5. Additional pipeline scripts

## CLI Framework Options

### 1. Click (Recommended)
**Pros:**
- Modern, decorator-based approach
- Excellent composability and command grouping
- Built-in support for subcommands
- Rich help generation
- Type validation and conversion
- Progress bars and styling
- Wide adoption in Python ecosystem

**Cons:**
- Additional dependency
- Learning curve for team
- Migration effort from argparse

**Example:**
```python
@click.group()
def cli():
    """Anthrasite Lead Factory CLI"""
    pass

@cli.command()
@click.option('--limit', default=50, help='Limit number of businesses')
@click.option('--zip-code', help='Process specific ZIP code')
def scrape(limit, zip_code):
    """Scrape business listings from APIs"""
    pass
```

### 2. Typer (Alternative)
**Pros:**
- Type hints based
- Automatic help generation
- Built on Click
- Modern Python approach
- Excellent IDE support

**Cons:**
- Newer framework, less established
- Additional dependency
- Python 3.6+ requirement

### 3. Enhanced argparse (Conservative)
**Pros:**
- No new dependencies
- Minimal migration effort
- Team already familiar
- Standard library

**Cons:**
- More verbose
- Limited composability
- Manual subcommand handling
- Less modern features

## Recommendation: Click

### Rationale
1. **Composability**: Perfect for grouping related commands (scrape, enrich, dedupe, email)
2. **Maintainability**: Cleaner, more readable code
3. **Extensibility**: Easy to add new commands and options
4. **User Experience**: Better help, validation, and error messages
5. **Industry Standard**: Widely used in production systems

### Implementation Plan
1. Add Click to requirements.txt
2. Create main CLI entry point with command groups
3. Migrate scripts one by one to Click commands
4. Maintain backward compatibility with wrapper scripts
5. Update documentation

### Command Structure
```
leadfactory
├── pipeline
│   ├── scrape
│   ├── enrich
│   ├── dedupe
│   └── email
├── admin
│   ├── db-setup
│   ├── migrate
│   └── backup
└── dev
    ├── test
    ├── lint
    └── format
```

## Next Steps
1. Install Click dependency
2. Create base CLI structure
3. Implement common utilities
4. Migrate first script (scrape.py)
5. Test and validate approach
