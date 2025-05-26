# Dependency Management

This document explains the dependency management system for the Anthrasite LeadFactory project.

## Requirements Files Overview

The project uses multiple specialized requirements files to maintain a clean separation of dependencies for different environments and use cases:

- `requirements.txt`: Core production dependencies only
- `requirements-test.txt`: Testing dependencies (includes production deps)
- `requirements-ci.txt`: CI environment dependencies (includes test deps)
- `requirements-dev.txt`: Development environment dependencies (includes CI deps)
- `requirements-metrics.txt`: Metrics-specific dependencies
- `constraints.txt`: Version constraints to enforce specific dependency versions

## File Hierarchy

The requirements files are organized in a hierarchical structure:

```
requirements.txt           <- Base production dependencies
    ↑
requirements-test.txt      <- Imports requirements.txt
    ↑
requirements-ci.txt        <- Imports requirements-test.txt
    ↑
requirements-dev.txt       <- Imports requirements-ci.txt
```

## Installation Instructions

### Production Environment

```bash
pip install -r requirements.txt -c constraints.txt
```

### Testing Environment

```bash
pip install -r requirements-test.txt -c constraints.txt
```

### CI Environment

```bash
pip install -r requirements-ci.txt -c constraints.txt
```

### Development Environment

```bash
pip install -r requirements-dev.txt -c constraints.txt
```

### Metrics Server

```bash
pip install -r requirements-metrics.txt -c constraints.txt
```

## Constraints File

The `constraints.txt` file is used to enforce specific versions of transitive dependencies. This is particularly useful for securing dependencies with known vulnerabilities, such as the Starlette package.

## Updating Dependencies

When adding or updating dependencies, follow these guidelines:

1. Add core dependencies to `requirements.txt`
2. Add testing-specific dependencies to `requirements-test.txt`
3. Add CI-specific dependencies to `requirements-ci.txt`
4. Add development-only dependencies to `requirements-dev.txt`
5. Add metrics-specific dependencies to `requirements-metrics.txt`

Always pin dependencies to specific versions for reproducibility.

## Security Considerations

All dependencies are pinned to specific versions and regularly audited for security vulnerabilities using the `pip-audit` tool. The project uses GitHub Dependabot to automatically monitor for security updates.

To manually check for vulnerabilities:

```bash
pip-audit -r requirements.txt -c constraints.txt
```

## CI Integration

The GitHub Actions workflows are configured to use the appropriate requirements file for each job:

- `unified-ci.yml`: Uses `requirements-ci.txt`
- `api-integration-tests.yml`: Uses `requirements-test.txt`

## Adding New Dependencies

When adding a new dependency, follow these steps:

1. Determine which environment needs the dependency
2. Add it to the appropriate requirements file with an exact version pin
3. Document why the dependency is needed (add a comment)
4. Run security audit to check for vulnerabilities
5. Test the application to ensure compatibility

Remember to maintain the hierarchical structure to avoid duplication across requirements files.
