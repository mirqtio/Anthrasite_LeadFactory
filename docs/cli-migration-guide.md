# CLI Migration Guide

## Overview

The Anthrasite Lead Factory has migrated from legacy bin/ scripts to a modern CLI interface using the Click framework. This guide explains the new CLI commands and how they map to the old scripts.

## New CLI Interface

### Main CLI Command
```bash
python3 -m leadfactory.cli.main [OPTIONS] COMMAND [ARGS]...
```

### Available Commands

#### Pipeline Operations
- `python3 -m leadfactory.cli.main pipeline scrape` - Scrape business listings
- `python3 -m leadfactory.cli.main pipeline enrich` - Enrich business data
- `python3 -m leadfactory.cli.main pipeline dedupe` - Deduplicate business records
- `python3 -m leadfactory.cli.main pipeline email` - Send emails

#### Administrative Operations
- `python3 -m leadfactory.cli.main admin setup-db` - Set up database
- `python3 -m leadfactory.cli.main admin migrate` - Run migrations
- `python3 -m leadfactory.cli.main admin backup` - Backup database

#### Development Operations
- `python3 -m leadfactory.cli.main dev test` - Run tests
- `python3 -m leadfactory.cli.main dev lint` - Run linting
- `python3 -m leadfactory.cli.main dev format` - Format code

## Migration from Legacy Scripts

### Script Mapping

| Legacy Script | New CLI Command |
|---------------|-----------------|
| `python3 bin/scrape.py` | `python3 -m leadfactory.cli.main pipeline scrape` |
| `python3 bin/enrich.py` | `python3 -m leadfactory.cli.main pipeline enrich` |
| `python3 bin/dedupe.py` | `python3 -m leadfactory.cli.main pipeline dedupe` |
| `python3 bin/email_queue.py` | `python3 -m leadfactory.cli.main pipeline email` |

### Parameter Mapping

#### Scrape Command
- Legacy: `python3 bin/scrape.py --limit 100 --zip 12345 --vertical tech`
- New: `python3 -m leadfactory.cli.main pipeline scrape --limit 100 --zip-code 12345 --vertical tech`

#### Enrich Command
- Legacy: `python3 bin/enrich.py --limit 50 --business_id 123 --tier 2`
- New: `python3 -m leadfactory.cli.main pipeline enrich --limit 50 --id 123 --tier 2`

#### Dedupe Command
- Legacy: `python3 bin/dedupe.py --limit 200 --threshold 0.8`
- New: `python3 -m leadfactory.cli.main pipeline dedupe --limit 200 --threshold 0.8`

#### Email Command
- Legacy: `python3 bin/email_queue.py --limit 25 --business_id 456 --force`
- New: `python3 -m leadfactory.cli.main pipeline email --limit 25 --id 456 --force`

## Backward Compatibility

The legacy bin/ scripts are still functional and will continue to work. However, they are deprecated and will be removed in a future version. We recommend migrating to the new CLI interface.

## Global Options

The new CLI provides global options that work with all commands:

- `--verbose` / `-v`: Enable verbose logging
- `--dry-run`: Run without making changes
- `--version`: Show version information
- `--help`: Show help information

## Examples

### Basic Usage
```bash
# Get help
python3 -m leadfactory.cli.main --help

# Scrape businesses with verbose output
python3 -m leadfactory.cli.main --verbose pipeline scrape --limit 10

# Dry run enrichment
python3 -m leadfactory.cli.main --dry-run pipeline enrich --limit 5

# Run tests
python3 -m leadfactory.cli.main dev test
```

### Advanced Usage
```bash
# Scrape specific ZIP code
python3 -m leadfactory.cli.main pipeline scrape --zip-code 90210 --vertical restaurants

# Enrich specific business
python3 -m leadfactory.cli.main pipeline enrich --id 12345 --tier 3

# Force send emails
python3 -m leadfactory.cli.main pipeline email --force --limit 10
```

## Benefits of the New CLI

1. **Consistent Interface**: All operations use the same CLI structure
2. **Better Help**: Comprehensive help system with `--help` option
3. **Global Options**: Verbose mode, dry-run, and other global options
4. **Modular Design**: Commands are organized into logical groups
5. **Better Error Handling**: Improved error messages and validation
6. **Future-Proof**: Easier to extend with new commands and features

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the project root directory
2. **Module Not Found**: Make sure all dependencies are installed (`pip install -r requirements.txt`)
3. **Permission Errors**: Check database and file permissions

### Getting Help

- Use `--help` with any command for detailed usage information
- Check the logs with `--verbose` for debugging
- Review the test suite in `tests/unit/test_cli_simple.py` for examples

## Future Plans

- Integration with setup.py entry points for global CLI access
- Additional administrative commands
- Enhanced logging and monitoring features
- Configuration file support
