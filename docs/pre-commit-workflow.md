# Pre-commit Workflow Guide

This document explains how to use pre-commit hooks in the Anthrasite LeadFactory project to maintain code quality and consistency.

## Overview

Pre-commit hooks are automated checks that run before each commit to ensure code quality standards are met. Our project uses the following hooks:

1. **Ruff** - For fast Python linting
2. **Black** - For consistent code formatting
3. **Bandit** - For security vulnerability scanning
4. **Pre-commit-hooks** - For various file checks (trailing whitespace, YAML validation, etc.)

## Setup Instructions

### First-time Setup

1. Ensure you have Python 3.10+ installed
2. Install pre-commit in your virtual environment:
   ```bash
   pip install pre-commit
   ```
3. Install the git hooks:
   ```bash
   pre-commit install
   ```

### Updating Hooks

If the `.pre-commit-config.yaml` file is updated, refresh your hooks:

```bash
pre-commit autoupdate
```

## Using Pre-commit

### Automatic Execution

Once installed, pre-commit hooks will run automatically when you attempt to commit changes. If any hooks fail, the commit will be aborted.

### Manual Execution

You can also run the hooks manually:

```bash
# Run on all files
pre-commit run --all-files

# Run on specific files
pre-commit run --files path/to/file1.py path/to/file2.py

# Run a specific hook
pre-commit run black --all-files
```

## Understanding Hook Failures

### Ruff (Linting)

Ruff will automatically fix many issues. If it fails, review the output for specific linting errors.

### Black (Formatting)

Black will check if your code meets the formatting standards. If it fails:

```bash
# Format your code with black
black .
```

### Bandit (Security)

Bandit identifies potential security vulnerabilities. If it fails, review the output for security concerns and fix them accordingly.

## Temporarily Bypassing Hooks

In rare cases, you may need to bypass the hooks (not recommended):

```bash
git commit -m "Your message" --no-verify
```

**Note**: This should only be used in exceptional circumstances. Always ensure your code meets quality standards.

## Integration with Feature Development Workflow

Pre-commit hooks are a critical part of our Feature Development Workflow (Task #27):

1. **Development Phase**: Write code with hooks in mind
2. **Testing Phase**: Run tests on code that passes hooks
3. **Quality Assurance Phase**: Pre-commit hooks are part of this phase
4. **Pre-Commit Phase**: Run hooks before committing
5. **Commit Phase**: Commit only after hooks pass
6. **CI Verification Phase**: CI will also run these hooks

## Troubleshooting

### Hook Installation Issues

If hooks aren't running:

```bash
pre-commit uninstall
pre-commit install
```

### Environment Issues

Ensure your virtual environment is activated when running pre-commit commands.

## Adding New Hooks

To add new hooks, update the `.pre-commit-config.yaml` file and run:

```bash
pre-commit autoupdate
```

## Contact

If you encounter issues with the pre-commit setup, contact the development team.
